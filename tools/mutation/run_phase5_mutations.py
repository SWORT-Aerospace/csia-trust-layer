"""Mutation testing for the Phase-5 hybrid study.

A FIFTH RUNNER, FOR THE SAME REASON THERE WAS A FOURTH
-------------------------------------------------------
Four runners already publish numbers that are quoted and pinned:
`run_e2m_mutations.py` at 38/36/2, `run_phase31_mutations.py` at 11/8/3,
`run_phase32_mutations.py` at 12/12/0 and `run_phase4_mutations.py` at
17/17/0. Appending to any of them would move a denominator, and widening any
of their selections could kill one of the five survivors in the first two --
the artificial kill the brief forbids. So this is a fifth sibling with its
own list, its own selection and its own output file.

**The Phase-4 score is not evidence about this code.** Different modules,
different mutants, different selection. Nothing here inherits 17/17.

    python tools/mutation/run_phase5_mutations.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "mutation"))

from run_e2m_mutations import (apply_from, package_files,  # noqa: E402
                               read_originals, restore_from,
                               sync_working_tree, working_tree_delta)
from run_mutations import (classify, drop_sandbox, make_sandbox,  # noqa: E402
                           run_tests)

MUTANTS = []


def M(mid, family, path, old, new, breaks):
    MUTANTS.append({"id": mid, "family": family, "path": path, "old": old,
                    "new": new, "breaks": breaks})


FAST = "csia_hybrid/fast_path.py"
SUPPORT = "csia_hybrid/support_view.py"
SHADOW = "csia_hybrid/fl029_shadow.py"
MULTI = "csia_hybrid/multiscale.py"
CAPAB = "csia_hybrid/capability.py"
BASE = "csia_hybrid/baselines.py"
EVAL = "research/phase5/evaluate5.py"

# ------------------------------------------- THE FAST PATH MAY NOT ATTRIBUTE
M("5-01", "FAST_PATH", FAST,
  "        if self.verdict not in VERDICTS:",
  "        if False:",
  "Opens the fast path's closed vocabulary, so it could emit a fault "
  "identity in the field the whole design exists to deny it.")

M("5-02", "FAST_PATH", FAST,
  "        self._bank.update(self.node, float(lam), active)",
  "        self._bank.update(self.node, float(lam), True)",
  "Feeds the fast path gated-off ticks as if they were live evidence, so it "
  "would accumulate on absence of evidence.")

M("5-03", "FAST_PATH", FAST,
  "PROVISIONAL_TICKS = 5",
  "PROVISIONAL_TICKS = 1",
  "Makes a single-tick excursion a PROVISIONAL_DEGRADATION, which is the "
  "alarm the hybrid's latency is measured from. It would flatter every "
  "hybrid baseline at once.")

M("5-04", "FAST_PATH", FAST,
  "MAY_ATTRIBUTE = False",
  "MAY_ATTRIBUTE = True",
  "Declares that the fast path may attribute, contradicting the structural "
  "guarantee the record advertises.")

# ------------------------------- SUPPORT MAY NOT BE CLAIMED WITHOUT SUPPORT
M("5-05", "SUPPORT", SUPPORT,
  "        if (self.attribution_status == SUPPORTED\n"
  "                and self.support_status != IDENTIFIABLE):",
  "        if False:",
  "Removes the one invariant this layer exists for: a SUPPORTED attribution "
  "without IDENTIFIABLE support becomes constructible.")

M("5-06", "SUPPORT", SUPPORT,
  "        if report.status == IDENTIFIABLE:\n"
  "            attribution = SUPPORTED",
  "        if self.leader_weight_is_high if False else True:\n"
  "            attribution = SUPPORTED",
  "Derives the attribution status from nothing at all, so every tick reports "
  "SUPPORTED regardless of the evidence.")

M("5-07", "SUPPORT", SUPPORT,
  "        stale = tuple(sorted(k for k in active\n"
  "                             if freshness.get(k, 1.0) < STALE_BELOW))",
  "        stale = ()",
  "Stops reporting stale evidence, so an edge reading old data is "
  "indistinguishable from one reading fresh data.")

M("5-08", "SUPPORT", SUPPORT,
  "        withdrawn = tuple(sorted(self._ever_active - set(active)))",
  "        withdrawn = ()",
  "Stops tracking withdrawn evidence, which is the state evidence-loss "
  "latency is measured from.")

# ------------------------------------------------------ THE FL-029 CORRECTION
M("5-09", "FL029", SHADOW,
  "        for feature, _reference in adds:\n"
  "            out[src].add(feature)",
  "        for feature, _reference in adds:\n"
  "            pass",
  "Makes the corrected map identical to the current one, so H3 would report "
  "no effect for a reason that is not the science.")

M("5-10", "FL029", SHADOW,
  "MODIFIES_FROZEN_CORE = False",
  "MODIFIES_FROZEN_CORE = True",
  "Claims the shadow module edits the frozen core, which would make every "
  "result in the phase a production-core claim.")

M("5-11", "FL029", SHADOW,
  "    return frozenset(mapping[a] ^ mapping[b])",
  "    return frozenset(mapping[a] | mapping[b])",
  "Replaces the symmetric difference with a union, so features that cancel "
  "exactly in the likelihood ratio would count as separating evidence.")

# ------------------------------------------------------------ MULTI-TIMESCALE
M("5-12", "MULTISCALE", MULTI,
  "                self._times[scale].append(float(t))",
  "                self._times[scale] = self._times[scale] or [float(t)]",
  "Restores the FL-038 defect: only the FIRST alarm per scale is kept, so a "
  "convergence transient hides every later detection.")

M("5-13", "MULTISCALE", MULTI,
  "        if gate <= GATE_EPS:\n"
  "            # Structural loss of support: the evidence is not being measured,\n"
  "            # so a partial run is not carried across the gap.\n"
  "            if self._run:\n"
  "                self._resets += 1\n"
  "            self._run = 0\n"
  "            return False",
  "        if gate <= GATE_EPS:\n"
  "            return False",
  "Carries a partial run across a gate closure, so persistence accumulates "
  "across an interval in which nothing was measured.")

# ------------------------------------------------------------- CAPABILITY
M("5-14", "CAPABILITY", CAPAB,
  "        elif hit:\n"
  "            states[fn], limiting[fn] = UNKNOWN, hit[0]",
  "        elif hit:\n"
  "            states[fn], limiting[fn] = INELIGIBLE, hit[0]",
  "Collapses UNKNOWN into INELIGIBLE, so 'something is wrong and we cannot "
  "say what' is reported as a confident restriction.")

M("5-15", "CAPABILITY", CAPAB,
  "FORGE_COMPATIBILITY_VERIFIED = False",
  "FORGE_COMPATIBILITY_VERIFIED = True",
  "Claims a verified Forge integration. There is no Forge in this "
  "repository and none may be written.")

# --------------------------------------------------------------- THE HYBRID
M("5-16", "HYBRID", BASE,
  "    if response in ATTRIBUTING and not pair_supported:\n"
  "        response = R_CAUTION_GENERIC",
  "    if response in ATTRIBUTING and not pair_supported:\n"
  "        response = R_ABSTAIN",
  "Turns the hybrid back into P2: it abstains instead of downgrading, which "
  "is the whole architectural difference the phase claims.")

M("5-17", "HYBRID", BASE,
  "    elif response == R_NONE and fast_provisional:\n"
  "        response = R_CAUTION_GENERIC",
  "    elif False:\n"
  "        response = R_CAUTION_GENERIC",
  "Removes the fast path's only effect on the response, so the latency "
  "mechanism stops existing while the latency claim remains.")

# ------------------------------------------------------------- THE EVALUATOR
M("5-18", "EVALUATOR", EVAL,
  "    chosen = match_operating_points(dev)",
  "    chosen = match_operating_points(locked)",
  "Tunes thresholds on the locked partition.")

M("5-19", "EVALUATOR", EVAL,
  '    return d["FAST"][threshold]["provisional"]',
  '    return d["FAST"][threshold]["suspected"]',
  "Reads the fast path's SUSPECTED series as the hybrid's alarm. The "
  "preregistration fixes it as PROVISIONAL precisely because a one-tick "
  "excursion would flatter every hybrid baseline.")

M("5-20", "EVALUATOR", EVAL,
  "NONINFERIORITY_DELTA = 0.05",
  "NONINFERIORITY_DELTA = 1.0",
  "Widens the non-inferiority margin to one, so any degradation whatever "
  "passes as 'no worse'.")

M("5-21", "EVALUATOR", EVAL,
  "MIN_AVAILABILITY_GAIN = 0.20",
  "MIN_AVAILABILITY_GAIN = 0.0",
  "Removes H3's declared effect size, so any gain however small would be "
  "called a demonstrated correction.")

M("5-22", "EVALUATOR", EVAL,
  "    values = sorted(values)\n    rng = random.Random(BOOTSTRAP_SEED)",
  "    rng = random.Random(BOOTSTRAP_SEED)",
  "Restores FL-037: the bootstrap resamples by index, so the interval "
  "depends on the order runs sit in the file.")

M("5-23", "EVALUATOR", EVAL,
  "    return min(1.0, 2.0 * tail)",
  "    return tail",
  "Turns the exact McNemar test one-sided, halving every p-value.")

CANARY = {
    "id": "CANARY", "family": "CANARY", "path": SUPPORT,
    "old": 'SUPPORTED = "SUPPORTED"',
    "new": 'SUPPORTED = "XXXX"',
    "breaks": "renames the support sentinel; nothing should classify",
}

#: DESELECTED, and not for convenience. A sha256 manifest guard fails for
#: EVERY mutant because mutating a file changes its hash, which manufactures
#: a perfect score (FL-033); and a test pinning this run's own score cannot
#: sit inside the selection that run measures.
DESELECT = [
    "tests/test_phase5_pipeline.py::test_the_manifest_matches_every_file_it_lists",
    "tests/test_phase5_pipeline.py::test_the_mutation_counts_match_the_write_up",
]

SELECTION = ["tests/test_phase5_hybrid.py",
             "tests/test_phase5_pipeline.py"] + \
            [f"--deselect={node}" for node in DESELECT]

OUT = os.path.join(ROOT, "research", "phase5", "results",
                   "PHASE5_MUTATION_RESULTS.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args(argv)

    selection = [s for s in SELECTION
                 if s.startswith("--")
                 or os.path.isfile(os.path.join(ROOT, s))]
    wanted = [m for m in MUTANTS
              if args.only is None or m["id"] in args.only]

    sandbox = make_sandbox()
    started = time.time()
    try:
        targets = sorted({m["path"] for m in MUTANTS} | {CANARY["path"]})
        synced = sync_working_tree(
            sandbox, targets + package_files(targets) + selection
            + working_tree_delta())
        originals = read_originals(sandbox, targets)

        baseline = run_tests(sandbox, selection, timeout=args.timeout)
        if baseline["returncode"] != 0:
            raise SystemExit(
                "ABORT: the UNMUTATED selection does not pass in the sandbox "
                f"(exit {baseline['returncode']}, first failure "
                f"{baseline['first_failure']!r}). Refusing to report.")

        if not apply_from(sandbox, originals, CANARY):
            raise SystemExit("ABORT: canary anchor not found")
        canary = run_tests(sandbox, selection, timeout=args.timeout)
        restore_from(sandbox, originals, CANARY["path"])
        if canary["returncode"] == 0:
            raise SystemExit("ABORT: the canary SURVIVED.")

        results = []
        for mutant in wanted:
            if not apply_from(sandbox, originals, mutant):
                results.append({**mutant, "verdict": "INVALID_MUTANT",
                                "why": "anchor text not found"})
                print(f"  {mutant['id']:8s} INVALID_MUTANT", flush=True)
                continue
            outcome = run_tests(sandbox, selection, timeout=args.timeout)
            restore_from(sandbox, originals, mutant["path"])
            verdict = classify(mutant, outcome)
            first = outcome["first_failure"]
            results.append({**mutant, "verdict": verdict,
                            "first_failure": first,
                            "first_failure_is_test_node":
                                bool(first) and "::" in first,
                            "seconds": outcome["seconds"]})
            print(f"  {mutant['id']:8s} {verdict:15s} {first or ''}",
                  flush=True)
    finally:
        drop_sandbox(sandbox)

    evaluated = [r for r in results if r["verdict"] in ("KILLED", "SURVIVED")]
    killed = [r for r in evaluated if r["verdict"] == "KILLED"]
    score = (len(killed) / len(evaluated)) if evaluated else None
    document = {
        "schema": "csia.phase5.mutation/1",
        "phase": "5 -- hybrid detector study",
        "is_experimental": True,
        "separate_from": ("E2M (38/36/2), Phase-3.1 (11/8/3), Phase-3.2 "
                          "(12/12/0) and Phase-4 (17/17/0), none of which "
                          "this runner touches. The Phase-4 score is NOT "
                          "evidence about this code."),
        "targets": sorted({m["path"] for m in MUTANTS}),
        "selection": selection,
        "deselected": DESELECT,
        "why_deselected": (
            "a sha256 manifest guard fails for every mutant because mutating "
            "a file changes its hash, and a test that pins this run's own "
            "score breaks the unmutated baseline. See FL-033."),
        "working_tree_files_synced_into_sandbox": synced,
        "evaluated": len(evaluated), "killed": len(killed),
        "survived": len(evaluated) - len(killed),
        "invalid": len(results) - len(evaluated), "score": score,
        "elapsed_s": round(time.time() - started, 1),
        "baseline_unmutated": {"returncode": baseline["returncode"],
                               "seconds": baseline["seconds"]},
        "canary": {"verdict": "KILLED",
                   "first_failure": canary["first_failure"]},
        "kills_attributed_to_a_test_node": sum(
            1 for r in results if r["verdict"] == "KILLED"
            and r.get("first_failure_is_test_node")),
        "kills_attributed_to_a_bare_file": sum(
            1 for r in results if r["verdict"] == "KILLED"
            and not r.get("first_failure_is_test_node")),
        "results": results,
        "what_this_is_not": (
            "not evidence about hardware, not a production-core result, and "
            "not a re-measurement of any earlier phase."),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"\nevaluated {len(evaluated)}  killed {len(killed)}  "
          f"survived {len(evaluated) - len(killed)}  "
          f"score {score if score is None else round(score, 4)}")
    print(f"wrote {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
