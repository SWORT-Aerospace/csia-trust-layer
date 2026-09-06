"""Mutation testing against the scientific core, in a sandbox that cannot leak.

WHAT THIS ANSWERS
-----------------
A green suite proves the tests pass. It does not prove they would notice if the
science changed. Mutation testing asks the second question directly: break one
diagnostic decision on purpose, and see whether anything fails.

A SURVIVOR IS THE INTERESTING RESULT. It means a line of the frozen core can be
changed without a single test objecting, which means no claim in either
manuscript is pinned to that line. That is a finding about the EVIDENCE, not a
bug to fix by adding a test that happens to catch that mutant.

WHY A SANDBOX, AND WHY IT IS A GIT WORKTREE
--------------------------------------------
Mutating the frozen core means writing to `csia/diagnosis/bayes.py` and friends.
Doing that in the working tree is unacceptable: a crash, a timeout or a
Ctrl-C between "apply" and "revert" leaves the scientific core silently
modified, and the next commit ships it. `tests/test_evidence_extension_is_
append_only.py` would catch it -- eventually, on the next full run -- which is
not the same as it never happening.

So every mutant is applied in `git worktree add --detach`, a separate checkout
git manages. The working tree is never written to. If this process dies the
worktree is orphaned, not the repository.

THE TRAP THIS SCRIPT CHECKS FOR EXPLICITLY
-------------------------------------------
The development venv has CSIA installed editable, so `import csia` normally
resolves to the ORIGINAL repository even when pytest runs with cwd inside the
sandbox. A mutation run that silently imports the unmutated core reports every
mutant SURVIVED and looks like a devastating finding about the test suite.

`_verify_sandbox_is_live()` runs a canary mutation that MUST be killed before
any real mutant runs, and asserts the loaded `csia.__file__` is inside the
sandbox. If either check fails the run aborts rather than reporting.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYTHON = os.environ.get("CSIA_MUTATION_PYTHON",
                        os.path.join(ROOT, ".venv", "bin", "python"))

#: Every mutant: a family, the file, an exact old string, its replacement, and
#: WHY the change is scientifically meaningful. The last field is not decoration
#: -- a mutant nobody can justify is a mutant whose survival means nothing.
MUTANTS = []


def M(mid, family, path, old, new, breaks, expect="KILLED", note=""):
    MUTANTS.append({"id": mid, "family": family, "path": path, "old": old,
                    "new": new, "breaks": breaks, "expect": expect,
                    "note": note})


# ---------------------------------------------------------------- GATING
# The gates decide WHETHER a relation contributes evidence at all. They are the
# systems paper's subject: the deployed layer emitted health because a gate
# SKIPPED an inapplicable feature instead of marking it unassessable.

M("GATING-01", "GATING", "csia/prediction/comparator.py",
  "GATE_SPEED_LO = 2.0", "GATE_SPEED_LO = 0.0",
  "Opens the horizontal-speed gate at every speed. The gate exists because "
  "the heading/course relation contributes nothing below a speed threshold; "
  "removing it feeds noise into a relation as though it were evidence.")

M("GATING-02", "GATING", "csia/prediction/comparator.py",
  "GATE_SPEED_LO = 2.0", "GATE_SPEED_LO = 200.0",
  "Closes the same gate permanently. The mirror of GATING-01: a gate stuck "
  "shut removes a relation entirely, which the layer must report as "
  "unassessable rather than as healthy.")

M("GATING-03", "GATING", "csia/prediction/comparator.py",
  "armed_gate = np.clip((ticks - 5.0) / 1.0, 0.0, 1.0)",
  "armed_gate = np.clip((ticks - 5.0) / 1.0, 1.0, 1.0)",
  "Arms every propulsion relation from tick zero, before the vehicle is "
  "armed. Pre-arm ESC and current readings are not evidence about flight.")

M("GATING-04", "GATING", "csia/prediction/comparator.py",
  'gvalid = a["gps_valid"]', 'gvalid = a["gps_valid"] * 0 + 1',
  "Declares GPS valid at every tick, including during injected fix loss. "
  "This is the closest single-line analogue of the systems paper's headline "
  "mechanism, and it must not survive.")

# ---------------------------------------------------------------- EVIDENCE
# The four documented departures from a Bayes posterior. Every normalized
# hypothesis weight the deployed system emits depends on these.

M("EVIDENCE-01", "EVIDENCE", "csia/diagnosis/bayes.py",
  "EPS = ", "EPS = 10 * ",
  "Raises the likelihood floor tenfold. EPS is departure 1 of 4 from a Bayes "
  "posterior and is why the output is a normalized hypothesis weight.")

M("EVIDENCE-02", "EVIDENCE", "csia/diagnosis/bayes.py",
  "EVIDENCE_MULT = ", "EVIDENCE_MULT = 0 * ",
  "Removes evidence tempering entirely. Departure 3 of 4.")

M("EVIDENCE-03", "EVIDENCE", "csia/diagnosis/bayes.py",
  "SMOOTH_ALPHA = ", "SMOOTH_ALPHA = 1.0 - ",
  "Inverts the EWMA constant, turning ~15 ticks of smoothing into almost "
  "none. Departure 2 of 4, and the systems paper's latency figures rest on "
  "the resulting time constant.")

M("EVIDENCE-04", "EVIDENCE", "csia/trust_engine/engine.py",
  "w_phys: float = 0.30", "w_phys: float = 0.0",
  "Zeroes the physical-consistency weight, so cross-sensor relations stop "
  "contributing to any trust coefficient.")

M("EVIDENCE-05", "EVIDENCE", "csia/trust_engine/engine.py",
  "alpha0: float = 8.0", "alpha0: float = 800.0",
  "Multiplies the Beta prior mass by 100. S_0 = 475.6775 -- the measured "
  "settled mass in the 118.82 chain -- is a consequence of this prior.")

# ---------------------------------------------------------------- TIMING
# Staleness and dwell are how the layer distinguishes 'no evidence' from
# 'evidence of health'. This is the systems paper's central distinction.

M("TIMING-01", "TIMING", "csia/runtime/online.py",
  "STALE_TIMEOUT_S = ", "STALE_TIMEOUT_S = 1000.0 * ",
  "Makes nothing ever go stale, so a dead sensor's last value is treated as "
  "current evidence indefinitely.")

M("TIMING-02", "TIMING", "csia/runtime/online.py",
  "STALE_TIMEOUT_S = ", "STALE_TIMEOUT_S = 0.0 * ",
  "The mirror: everything is stale immediately, so no evidence is ever "
  "admissible. A layer that reports health under this mutant is reporting it "
  "from nothing.")

M("TIMING-03", "TIMING", "csia/runtime/failsafe.py",
  "dwell_up: float = 1.0", "dwell_up: float = 0.0",
  "Removes the escalation dwell, so a single tick flaps the failsafe level. "
  "The 1.0 s dwell is the term CUSUM_FAIRNESS.yaml removes before any "
  "latency comparison -- red team 2.3.")

M("TIMING-04", "TIMING", "csia/diagnosis/baselines.py",
  "DWELL_TICKS = ", "DWELL_TICKS = 0 * ",
  "Removes the baseline detectors' dwell. The Mechanism-B comparison is "
  "against these baselines; a baseline that fires instantly is not the "
  "baseline the paper describes.")

# ---------------------------------------------------------------- SUPPORT
# Whether a hypothesis is entitled to be asserted at all. The DEA core safety
# property lives here: a ranking alone is not attribution.

M("SUPPORT-01", "SUPPORT", "csia/diagnosis/hypothesis.py",
  "MAX_SOURCES_PER_HYPOTHESIS = ", "MAX_SOURCES_PER_HYPOTHESIS = 1 + 0 * ",
  "Caps every hypothesis at one source, so no multi-source hypothesis can "
  "form and shared-cause attribution becomes impossible.")

M("SUPPORT-02", "SUPPORT", "csia/diagnosis/hypothesis.py",
  "UNKNOWN_MIN_UNEXPLAINED = ", "UNKNOWN_MIN_UNEXPLAINED = 1000 + 0 * ",
  "Makes the UNKNOWN hypothesis unreachable, so unexplained evidence is "
  "always attributed to a modeled cause. This is precisely the failure the "
  "DEA profile forbids: attribution without separating evidence.")

M("SUPPORT-03", "SUPPORT", "csia/diagnosis/hypothesis.py",
  "ACTIVE_CONF = ", "ACTIVE_CONF = 0.0 * ",
  "Promotes every hypothesis to ACTIVE regardless of accumulated evidence.")

M("SUPPORT-04", "SUPPORT", "csia/diagnosis/baselines.py",
  "D_MIN_SOURCES = ", "D_MIN_SOURCES = 1 + 0 * ",
  "Lets a single degraded source establish a shared-resource verdict, "
  "removing the multi-source requirement the baselines are built on.")

# ---------------------------------------------------------------- CONFIG
# Deployment-visible thresholds. These are the values a wrong config could
# plausibly move, which is why the firewall work and this family overlap.

M("CONFIGURATION-01", "CONFIGURATION", "csia/runtime/failsafe.py",
  "nav_caution: float = ", "nav_caution: float = 0.0 * ",
  "Drops the navigation caution threshold to zero, so no trust value ever "
  "crosses it. T* = 0.75 is in the 118.82 chain and in every latency figure "
  "compared against CUSUM.")

M("CONFIGURATION-02", "CONFIGURATION", "csia/runtime/failsafe.py",
  "imu_isolation_gap: float = 0.12", "imu_isolation_gap: float = 0.99",
  "Makes IMU isolation unreachable, so a divergent dual-IMU pair is never "
  "resolved to one unit.")

M("CONFIGURATION-03", "CONFIGURATION", "csia/trust_engine/engine.py",
  "rho_min: float = 0.95", "rho_min: float = 0.10",
  "Collapses the forgetting factor's lower bound, so the engine discards "
  "history almost immediately under disagreement.")

# ---------------------------------------------------------------- DIAGNOSIS
# Which cause is named, and how confidently.

M("DIAGNOSIS-01", "DIAGNOSIS", "csia/diagnosis/causal.py",
  "TEMPORAL_FULL_S = ", "TEMPORAL_FULL_S = 0.0 * ",
  "Collapses the temporal-coherence window, so simultaneity carries no "
  "weight in shared-cause assessment.")

M("DIAGNOSIS-02", "DIAGNOSIS", "csia/diagnosis/causal.py",
  "SHARPNESS = ", "SHARPNESS = 0.0 * ",
  "Flattens the causal scoring curve, so every candidate cause scores alike "
  "and ranking becomes arbitrary.")

M("DIAGNOSIS-03", "DIAGNOSIS", "csia/diagnosis/causal.py",
  "SOURCE_DEGRADED = ", "SOURCE_DEGRADED = 0.0 * ",
  "Declares every source degraded, so shared-cause assessment always has a "
  "full membership set to reason over.")

M("DIAGNOSIS-04", "DIAGNOSIS", "csia/diagnosis/baselines.py",
  "VOTE_C = ", "VOTE_C = 0.0 * ",
  "Removes the voting baseline's threshold, so it detects at every tick.")


CANARY = {
    "id": "CANARY", "family": "SELF-CHECK",
    "path": "csia/diagnosis/bayes.py",
    "old": "PRIOR_NOMINAL = ", "new": "PRIOR_NOMINAL = 0.0 * ",
    "breaks": "Sets the nominal prior to zero. If the suite does not notice "
              "THIS, the sandbox is not being imported and no result below "
              "means anything.",
    "expect": "KILLED", "note": "self-check, not a finding",
}


#: Signals that a test detects a SOURCE CHANGE rather than a BEHAVIOUR CHANGE:
#: it hashes a file, or diffs the tree against a freeze tag.
INTEGRITY_SIGNALS = ("sha256", "hexdigest", "FROZEN_TAG", "_git(",
                     '"diff"', "'diff'", "_sha(")


def integrity_guards(selection, root=None) -> dict:
    """Derive the source-integrity tests in the selection. NOT a hand list.

    WHY THIS IS DERIVED, AND THE FINDING THAT FORCED IT
    ---------------------------------------------------
    The first campaign reported 23 of 24 mutants KILLED, and eleven were killed
    by one test: `test_diagnostic_core_is_unchanged_since_the_freeze`, which
    diffs the frozen core against its tag. That test fires identically on a
    reformatted comment. A mutant it kills has not been shown to change any
    observable behaviour, and counting it as killed overstates what the suite
    establishes about the science.

    The first fix was a hand-written list of such guards. It was WRONG ON ITS
    FIRST RUN -- it missed `test_v1_1_support.py::
    test_the_frozen_diagnosis_core_is_untouched` and `test_v1_1_staleness.py::
    test_the_frozen_core_is_still_untouched`, which then killed seven mutants
    each looking like a behavioural result. That is FL-001's lesson arriving in
    a third place in one session, so the list is derived from the test sources
    instead.

    HELPER CALLS ARE FOLLOWED ONE LEVEL, because the derivation ALSO got that
    wrong first: `test_every_recorded_hash_still_matches` hashes files through
    a module-level `_sha()` helper, so its own body contains no signal at all.
    """
    root = root or ROOT
    found = {}
    for rel in selection:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src, filename=path)
        helpers = {n.name: (ast.get_source_segment(src, n) or "")
                   for n in tree.body if isinstance(n, ast.FunctionDef)
                   and not n.name.startswith("test")}
        for node in tree.body:
            if not (isinstance(node, ast.FunctionDef)
                    and node.name.startswith("test")):
                continue
            seg = ast.get_source_segment(src, node) or ""
            called = {c.func.id for c in ast.walk(node)
                      if isinstance(c, ast.Call)
                      and isinstance(c.func, ast.Name)}
            text = seg + "".join(helpers.get(name, "") for name in called)
            hit = [s for s in INTEGRITY_SIGNALS if s in text]
            if hit:
                found[f"{rel}::{node.name}"] = hit
    return found


def _run(cmd, cwd=None, env=None, timeout=1800):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout)


def make_sandbox() -> str:
    tmp = tempfile.mkdtemp(prefix="csia-mutation-")
    path = os.path.join(tmp, "wt")
    proc = _run(["git", "worktree", "add", "--detach", path, "HEAD"], cwd=ROOT)
    if proc.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise SystemExit(f"could not create sandbox worktree:\n{proc.stderr}")
    return path


def drop_sandbox(path: str):
    _run(["git", "worktree", "remove", "--force", path], cwd=ROOT)
    shutil.rmtree(os.path.dirname(path), ignore_errors=True)


def apply_mutation(sandbox: str, mutant: dict) -> bool:
    """Restore the file, then substitute. False if the anchor is not present."""
    _run(["git", "checkout", "--", mutant["path"]], cwd=sandbox)
    full = os.path.join(sandbox, mutant["path"])
    with open(full, encoding="utf-8") as fh:
        text = fh.read()
    if text.count(mutant["old"]) < 1:
        return False
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text.replace(mutant["old"], mutant["new"], 1))
    return True


def _env(sandbox: str) -> dict:
    env = dict(os.environ)
    # PYTHONPATH ahead of the editable install, and cwd inside the sandbox.
    env["PYTHONPATH"] = sandbox + os.pathsep + env.get("PYTHONPATH", "")
    return env


def run_tests(sandbox: str, selection: list, timeout=1800,
              stop_first=True) -> dict:
    """Run the selection in the sandbox.

    `stop_first` is the pass-1/pass-2 difference. Pass 1 uses -x and only needs
    to know WHETHER anything failed. Pass 2 runs the whole selection so it can
    see EVERY failing test -- which is what decides whether a kill was
    behavioural or only a file-hash guard.

    NOTHING IS DESELECTED. An earlier version deselected the derived integrity
    guards in pass 2, and that was a worse design: mis-classifying one
    behavioural test as a guard would silently turn a real kill into a reported
    survivor. Collecting the failures and classifying afterwards cannot do
    that, because the behavioural test still appears in the list.
    """
    started = time.time()
    flags = ["-x"] if stop_first else ["--tb=no"]
    proc = _run([PYTHON, "-m", "pytest", *flags, "-q", "--no-header",
                 "-p", "no:cacheprovider", *selection],
                cwd=sandbox, env=_env(sandbox), timeout=timeout)
    lines = (proc.stdout or "").splitlines()
    failures = []
    for line in lines:
        if line.startswith(("FAILED ", "ERROR ")):
            node = line.split(" ", 1)[1].split(" - ")[0].strip()
            failures.append(node)
    return {
        "returncode": proc.returncode,
        "seconds": round(time.time() - started, 1),
        "tail": [ln for ln in lines if ln.strip()][-2:],
        "failures": failures,
        "first_failure": failures[0] if failures else None,
    }


def verify_sandbox_is_live(sandbox: str, selection: list) -> dict:
    """Two checks, both of which must pass before any real mutant runs."""
    proc = _run([PYTHON, "-c",
                 "import csia, json; print(json.dumps(csia.__file__))"],
                cwd=sandbox, env=_env(sandbox))
    if proc.returncode != 0:
        raise SystemExit(f"sandbox import failed:\n{proc.stderr}")
    loaded = json.loads(proc.stdout.strip())
    if not os.path.realpath(loaded).startswith(os.path.realpath(sandbox)):
        raise SystemExit(
            f"ABORT: the sandbox is not being imported. `import csia` "
            f"resolved to {loaded}, outside {sandbox}. Every result would be "
            f"a false SURVIVED. This is the editable-install trap the module "
            f"docstring describes.")

    if not apply_mutation(sandbox, CANARY):
        raise SystemExit(f"ABORT: canary anchor {CANARY['old']!r} not found")
    result = run_tests(sandbox, selection)
    _run(["git", "checkout", "--", CANARY["path"]], cwd=sandbox)
    if result["returncode"] == 0:
        raise SystemExit(
            "ABORT: the canary mutant SURVIVED. Setting PRIOR_NOMINAL to zero "
            "changed nothing the selected tests noticed, which means either "
            "the selection is wrong or the sandbox is not live. Refusing to "
            "report mutation results that would all be false survivors.")
    return {"csia_file": loaded, "canary": result}


def classify(mutant: dict, result: dict) -> str:
    """KILLED / SURVIVED / INVALID_MUTANT.

    EQUIVALENT and OUT_OF_SCOPE are AUTHOR judgements recorded in the plan,
    never inferred here: a script cannot know that two programs compute the
    same function, and pretending it can is how a survivor gets explained away.
    """
    if result["returncode"] == 0:
        return "SURVIVED"
    # pytest exit 2 (interrupted), 3 (internal), 4 (usage) are not evidence
    # that the mutant was detected -- they mean the run did not happen.
    if result["returncode"] in (2, 3, 4):
        return "INVALID_MUTANT"
    return "KILLED"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Mutation testing against the CSIA scientific core. "
                    "Runs in a git worktree; never writes to the working "
                    "tree.")
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "physical_validation", "mutation",
        "MUTATION_RESULTS.json"))
    ap.add_argument("--select", nargs="*", default=None,
                    help="pytest selection; default is the science subset")
    ap.add_argument("--only", nargs="*", default=None,
                    help="run only these mutant ids")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args(argv)

    selection = args.select or DEFAULT_SELECTION
    wanted = [m for m in MUTANTS
              if args.only is None or m["id"] in args.only]

    sandbox = make_sandbox()
    try:
        head = _run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
        guards = integrity_guards(selection)
        selfcheck = verify_sandbox_is_live(sandbox, selection)
        print(f"sandbox live: {selfcheck['csia_file']}")
        print(f"canary killed in {selfcheck['canary']['seconds']}s")
        print(f"{len(guards)} source-integrity guards derived from the "
              f"selection")

        results = []
        for mutant in wanted:
            if not apply_mutation(sandbox, mutant):
                results.append({**mutant, "verdict": "INVALID_MUTANT",
                                "detail": f"anchor {mutant['old']!r} not "
                                          f"found in {mutant['path']}"})
                print(f"{mutant['id']:18s} INVALID_MUTANT (anchor missing)")
                continue
            res = run_tests(sandbox, selection, timeout=args.timeout)
            verdict = classify(mutant, res)

            # PASS 2. Only for a mutant pass 1 killed: if nothing caught it,
            # there are no failures to classify.
            full = None
            behavioural_killers = []
            if verdict == "KILLED":
                full = run_tests(sandbox, selection, timeout=args.timeout,
                                 stop_first=False)
                behavioural_killers = [f for f in full["failures"]
                                       if f not in guards]
                if full["failures"] and not behavioural_killers:
                    verdict = "KILLED_BY_INTEGRITY_ONLY"

            results.append({**mutant, "verdict": verdict,
                            "result": res, "full_run": full,
                            "behavioural_killers": behavioural_killers,
                            "integrity_killers": [
                                f for f in (full or {}).get("failures", [])
                                if f in guards]})
            shown = (behavioural_killers or [res.get("first_failure") or ""])[0]
            print(f"{mutant['id']:18s} {verdict:26s} "
                  f"{res['seconds']:5.1f}s  {shown}"[:150])
            _run(["git", "checkout", "--", mutant["path"]], cwd=sandbox)

        summary = {
            "schema": "csia.research.mutation_results/1",
            "head": head,
            "python": PYTHON,
            "selection": selection,
            "integrity_guards": guards,
            "integrity_guards_note": (
                "DERIVED from the selection's own sources by "
                "integrity_guards(), not hand-listed -- the hand list was "
                "wrong on its first run. Nothing is deselected; these are the "
                "node ids a failure is classified AGAINST."),
            "verdict_vocabulary": {
                "KILLED": ("at least one failing test was not a source-"
                           "integrity guard, so a BEHAVIOUR change was "
                           "detected"),
                "KILLED_BY_INTEGRITY_ONLY": (
                    "every failing test was a source-integrity guard -- a "
                    "file-hash or tag diff, which would fire identically on a "
                    "reformatted comment. The change cannot reach a commit, "
                    "and NO test asserts the behaviour this line produces. "
                    "Treated as a survivor for the purpose of 'what do the "
                    "tests establish about the science'."),
                "SURVIVED": "no test failed at all",
                "INVALID_MUTANT": ("the mutated program does not run -- "
                                   "collection error or a pytest usage exit. "
                                   "Says nothing about the test suite."),
                "EQUIVALENT": ("author judgement, recorded in MUTATION_PLAN.md "
                               "and never inferred by this script"),
                "OUT_OF_SCOPE": "author judgement, recorded in MUTATION_PLAN.md",
            },
            "self_check": {
                "sandbox_csia_file": selfcheck["csia_file"],
                "canary_verdict": "KILLED",
                "why": ("The canary sets PRIOR_NOMINAL to zero. If it had "
                        "survived, every result here would be a false "
                        "survivor caused by the editable install resolving "
                        "`import csia` to the unmutated repository."),
            },
            "counts": {v: sum(1 for r in results if r["verdict"] == v)
                       for v in sorted({r["verdict"] for r in results})},
            "mutants": results,
        }
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"\nwrote {args.out}")
        print(json.dumps(summary["counts"], sort_keys=True))
        return 0
    finally:
        drop_sandbox(sandbox)


#: The science subset. Chosen to be the tests that pin DIAGNOSTIC behaviour,
#: not the whole suite: a full run per mutant would take hours and most of it
#: (packaging guards, markdown paths, bibliography ledgers) cannot possibly
#: respond to a change in bayes.py. The selection is recorded in the results
#: file so a reader can see exactly what a SURVIVED verdict was measured
#: against.
DEFAULT_SELECTION = [
    "tests/test_diagnosis.py",
    "tests/test_hypothesis.py",
    "tests/test_causal.py",
    "tests/test_engine.py",
    "tests/test_runtime.py",
    "tests/test_comparator.py",
    "tests/test_determinism.py",
    "tests/test_v1_frozen.py",
    "tests/test_v1_1_golden.py",
    "tests/test_v1_1_support.py",
    "tests/test_v1_1_staleness.py",
    "tests/test_phase_c_freeze.py",
    # THE TWO THAT MAKE THIS ABOUT THE PAPERS RATHER THAN ABOUT THE CODE.
    # A mutant that changes a diagnostic number but breaks no behavioural
    # assertion may still be caught here, because these bind the manuscripts'
    # printed figures to what the code computes. If a mutant survives even
    # these, no claim in either paper is pinned to the line it changed.
    "tests/test_prose_numeric_bindings.py",
    "tests/test_systems_paper_numeric_claims.py",
    # THE BEHAVIOURAL ORACLE ADDED AFTER THE FIRST CAMPAIGN. It re-derives
    # S_0 and T_0 from the frozen engine instead of reading the stored
    # artifact, which is what the first campaign found EVIDENCE-05 exploiting.
    # Added to the selection so the re-adjudication measures the same suite the
    # paper's numbers now actually depend on.
    "tests/test_scalar_rederivation.py",
]

if __name__ == "__main__":
    sys.exit(main())
