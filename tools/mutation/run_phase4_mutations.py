"""Mutation testing for the Phase-4 detector-performance study.

A FOURTH RUNNER, FOR THE SAME REASON THERE WAS A THIRD
-------------------------------------------------------
Three runners already publish numbers that are quoted and pinned:
`run_e2m_mutations.py` at 38/36/2, `run_phase31_mutations.py` at 11/8 with
three survivors, and `run_phase32_mutations.py` at 12/12. Appending to any of
them would move a denominator, and widening any of their selections could kill
one of the five earlier survivors as a side effect -- the artificial kill the
brief forbids. So this is a fourth sibling with its own mutant list, its own
test selection and its own output file. None of the three is touched.

The sandbox machinery is imported, not reimplemented, including the
unmutated-baseline check that has now caught four false-green results in this
programme.

    python tools/mutation/run_phase4_mutations.py
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


EVAL = "research/phase4/evaluate4.py"
CAMPAIGN = "research/phase4/campaign4.py"

# --------------------------------------------- THE PREREGISTERED MATCHING RULE
M("4-01", "PREREG", EVAL,
  "PRIMARY_TARGET = 0.00",
  "PRIMARY_TARGET = 0.10",
  "Moves the primary comparison off the zero-false-alarm point the "
  "preregistration names, to a level the preregistration says carries no "
  "verdict. Choosing the operating point after seeing the data is the "
  "cherry-pick the whole design exists to prevent.")

M("4-02", "PREREG", EVAL,
  "                if far is not None and far <= target + 1e-12:",
  "                if far is not None and far <= target + 0.05:",
  "Admits thresholds whose development false-alarm rate EXCEEDS the target, "
  "so a detector could be compared at an operating point it does not meet "
  "while another is held to the target exactly.")

M("4-03", "PREREG", EVAL,
  "    chosen = match_operating_points(dev)",
  "    chosen = match_operating_points(locked)",
  "Tunes thresholds on the locked partition. The preregistration says "
  "thresholds are selected on development only and applied unchanged.")

M("4-04", "PREREG", EVAL,
  '    return [repr(v) for v in document["grids"][detector]]',
  '    return [repr(v) for v in sorted(document["grids"][detector])]',
  "Sorts the declared grid. Phase 3.1 measured crossing time to be "
  "non-monotone in fault rate and the preregistration says so explicitly, so "
  "ordering a grid is not a cosmetic change.")

M("4-05", "PREREG", CAMPAIGN,
  "            for onset in ONSET_GRID:                    # exhaustive",
  "            for onset in ONSET_GRID[:1]:",
  "Prunes the onset grid to one point, so 'delay by onset' would be reported "
  "from a single onset and the exhaustiveness the campaign claims would be "
  "false.")

# -------------------------------------------------------- SCORING DEFINITIONS
M("4-06", "DEFINITION", EVAL,
  '               if r["alarms"][detector][threshold]["after_settle"] is not None)',
  '               if r["alarms"][detector][threshold]["first"] is not None)',
  "Restores the FL-035 false-alarm defect: a latched detector that crossed "
  "during the settling window and stayed above threshold for the rest of the "
  "flight would be scored as having no false alarm.")

M("4-07", "DEFINITION", EVAL,
  '        if a["after_onset"] is None:\n'
  "            misses += 1\n"
  "        else:\n"
  '            delays.append(round(a["after_onset"] - r["onset_s"], 6))',
  '        if a["first"] is None:\n'
  "            misses += 1\n"
  "        else:\n"
  '            delays.append(round(a["first"] - r["onset_s"], 6))',
  "Restores the FL-035 detection defect: an alarm raised BEFORE the fault "
  "onset is scored as a detection with negative delay.")

M("4-08", "DEFINITION", EVAL,
  '        "miss_rate": round(misses / n, 6) if n else None,',
  '        "miss_rate": 0.0,',
  "Reports every detector as never missing, which is the one number that "
  "makes a short delay meaningless.")

M("4-09", "DEFINITION", EVAL,
  '        "pre_onset_alarms_on_faulted_runs": pre_onset,',
  '        "pre_onset_alarms_on_faulted_runs": 0,',
  "Hides the count of alarms raised on faulted runs before the fault "
  "existed, which is how a reader detects a detector that is simply noisy.")

# ---------------------------------------------------------------- STATISTICS
M("4-10", "STATS", EVAL,
  "    low = 0.0 if k == 0 else bisect(lambda p: at_least(p, k), alpha / 2.0)",
  "    low = 0.0",
  "Pins every lower confidence bound at zero.")

M("4-11", "STATS", EVAL,
  "    pos = q * (len(xs) - 1)",
  "    pos = q * len(xs)",
  "Changes the declared quantile definition, so a p90 reported here would "
  "not be the p90 a reader reconstructs from the delays.")

M("4-12", "STATS", EVAL,
  "    if len(values) < MIN_DETECTIONS_FOR_CI:\n        return None",
  "    if False:\n        return None",
  "Computes a bootstrap interval from as few as one detection, where the "
  "resample is a constant and the interval is a point.")

M("4-13", "STATS", EVAL,
  "    rng = random.Random(BOOTSTRAP_SEED)",
  "    rng = random.Random()",
  "Unpins the bootstrap seed, so the reported intervals are not "
  "reproducible from the committed runs.")

# ------------------------------------------------------ CAMPAIGN MEASUREMENT
M("4-14", "CAMPAIGN", CAMPAIGN,
  "DWELL_TICKS = 25                                  # 1.0 s at 25 Hz",
  "DWELL_TICKS = 1",
  "Removes the persistence requirement, which IS the CSIA detector under "
  "test. A one-tick alarm is a bare threshold on trust, not trust "
  "persistence.")

M("4-15", "CAMPAIGN", CAMPAIGN,
  "            if gate[k] <= GATE_EPS:\n                continue",
  "            if False:\n                continue",
  "Counts persistence through ticks where the evidence is gated off, so the "
  "CSIA detector would alarm on absent evidence rather than on evidence of "
  "a fault.")

M("4-16", "CAMPAIGN", CAMPAIGN,
  "        bank.update(NODE, float(lam[k]), bool(gate[k] > GATE_EPS))",
  "        bank.update(NODE, float(lam[k]), True)",
  "Feeds the CUSUM gated-off ticks as if they were live evidence, which "
  "changes the baseline detector's statistic and so the comparison.")

M("4-17", "CAMPAIGN", CAMPAIGN,
  "SETTLE_S = float(FailsafeConfig().arm_time)      # 10.0",
  "SETTLE_S = 0.0",
  "Removes the settling window, so convergence transients at the start of "
  "every flight are counted as false alarms for every detector.")

CANARY = {
    "id": "CANARY", "family": "CANARY", "path": EVAL,
    "old": 'DETECTORS = ("CSIA", "CUSUM", "BINST")',
    "new": 'DETECTORS = ("XXXX",)',
    "breaks": "renames every detector; nothing should resolve",
}

#: DESELECTED, and not for convenience.
#:
#: A sha256 manifest guard compares every listed file's hash against the
#: manifest. Mutating a file changes its hash, so such a test fails for EVERY
#: mutant regardless of behaviour, and including it manufactures a perfect
#: score -- which is exactly what happened on the first Phase-3.2 run
#: (FL-033). A test that pins THIS run's own score cannot be inside the
#: selection this run measures either: changing the code changes the score, so
#: the unmutated baseline would fail for a reason unrelated to any mutant.
DESELECT = [
    "tests/test_phase4_pipeline.py::test_the_manifest_matches_every_file_it_lists",
    "tests/test_phase4_pipeline.py::test_the_mutation_counts_match_the_write_up",
]

SELECTION = ["tests/test_phase4_detectors.py",
             "tests/test_phase4_pipeline.py"] + \
            [f"--deselect={node}" for node in DESELECT]

OUT = os.path.join(ROOT, "research", "phase4", "results",
                   "PHASE4_MUTATION_RESULTS.json")


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
        targets = [m["path"] for m in MUTANTS] + [CANARY["path"]]
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
        "schema": "csia.phase4.mutation/1",
        "phase": "4 -- detector performance",
        "separate_from": ("E2M_MUTATION_RESULTS.json (38/36/2), "
                          "PHASE31_MUTATION_RESULTS.json (11/8) and "
                          "PHASE32_MUTATION_RESULTS.json (12/12), none of "
                          "which this runner touches, so none of the five "
                          "earlier survivors can be killed as a side effect"),
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
            "not evidence about hardware, not a consequence measurement, and "
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
