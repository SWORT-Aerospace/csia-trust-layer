"""Mutation testing for the Phase-3.2 direct consequence test.

WHY A THIRD RUNNER AND NOT A LONGER SECOND ONE
-----------------------------------------------
Two earlier runners already report numbers that are quoted and pinned:
`run_e2m_mutations.py` at 38/36/2 with `P3-03` and `P3-04` alive, and
`run_phase31_mutations.py` at 11/8 with `31-03`, `31-07` and `31-11` alive.
Appending to either would move a denominator, and adding a new test file to
either selection could kill one of those five survivors as a side effect --
the artificial kill the brief forbids. So this is a third sibling with its own
list, its own selection and its own output file. Neither earlier runner is
touched.

The sandbox machinery is imported, not reimplemented, including the
unmutated-baseline check that has now caught three false-green results in this
programme.

    python tools/mutation/run_phase31_mutations.py
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
                           run_tests, _env, _run)

MUTANTS = []


def M(mid, family, path, old, new, breaks):
    MUTANTS.append({"id": mid, "family": family, "path": path, "old": old,
                    "new": new, "breaks": breaks})


EVAL = "research/consequence/phase32/evaluate32.py"
CAMPAIGN = "research/consequence/phase32/campaign32.py"

# ------------------------------------------------------- PREREGISTERED RULES
M("32-01", "PREREG", EVAL,
  "MIN_RD = 0.50",
  "MIN_RD = 0.0",
  "Removes the declared effect-size threshold, so any statistically "
  "significant difference however small would be called a demonstrated "
  "consequence. The threshold exists precisely to stop that, and it was "
  "declared before the locked run.")

M("32-02", "PREREG", EVAL,
  "MAX_DROPPED_PAIRS = 4",
  "MAX_DROPPED_PAIRS = 40",
  "Lets any number of exclusions pass without the test being reported as "
  "underpowered, so a verdict could be drawn from two surviving pairs.")

M("32-03", "PREREG", EVAL,
  '    primary = next(t for t in tests\n'
  '                   if t["family"] == "structural"\n'
  '                   and t["magnitude"] == confirm["structural"])',
  "    primary = max(tests, key=lambda t: t.get(\"risk_difference\", 0.0))",
  "Picks the best-performing grid point as the confirmatory one instead of "
  "the preregistered point. That is the cherry-pick the preregistration "
  "exists to prevent.")

M("32-04", "PREREG", CAMPAIGN,
  "            for magnitude in GRIDS[family]:       # declaration order, no sort",
  "            for magnitude in sorted(GRIDS[family], reverse=True):",
  "Sorts the declared grid. Phase 3.1 measured crossing time to be "
  "non-monotone in fault rate, so ordering the grid is not a cosmetic change.")

# --------------------------------------------------------------- STATISTICS
M("32-05", "STATS", EVAL,
  "    return min(1.0, 2.0 * tail)",
  "    return tail",
  "Turns the exact McNemar test one-sided, halving every p-value.")

M("32-06", "STATS", EVAL,
  '        "odds_ratio": None if c == 0 else round(b / c, 6),',
  '        "odds_ratio": round(b / max(c, 1), 6),',
  "Fabricates a finite odds ratio when c = 0 by substituting 1 for the zero "
  "denominator. The real quantity is not finite and the preregistration says "
  "no point estimate is reported in that case.")

M("32-07", "STATS", EVAL,
  '        "ci95_is_conditional_on_discordant_pairs": True,\n'
  '        "odds_ratio": None if c == 0 else round(b / c, 6),',
  '        "ci95_is_conditional_on_discordant_pairs": False,\n'
  '        "odds_ratio": None if c == 0 else round(b / c, 6),',
  "Drops the flag that says the risk-difference interval is conditional on "
  "the discordant-pair count, so a reader would take it for a marginal "
  "interval.")

M("32-08", "STATS", EVAL,
  "    low = 0.0 if k == 0 else bisect(lambda p: at_least(p, k), alpha / 2.0)",
  "    low = 0.0",
  "Pins every lower confidence bound at zero.")

# -------------------------------------------------------------- DEFINITIONS
M("32-09", "DEFINITION", EVAL,
  "    conflict = (want not in classes) if kinds else (correct_response != R_NONE)",
  "    conflict = (correct_response not in kinds) if kinds else False",
  "Decides the conflict on response LABELS rather than classes, and stops "
  "counting 'nothing issued where a response was required' as a conflict -- "
  "which is the entire Phase-3.2 finding.")

M("32-10", "DEFINITION", EVAL,
  '        "false_escalation": bool(correct_response == R_NONE\n'
  '                                 and actionable),',
  '        "false_escalation": False,',
  "Stops the matched nominal control from ever vetoing the verdict, so an "
  "H2 result could stand on a policy that escalates on clean flights.")

# ----------------------------------------------------------------- CAMPAIGN
M("32-11", "CAMPAIGN", CAMPAIGN,
  '    drop = (GATING_SENSOR,) if condition == "EG" else ()',
  "    drop = ()",
  "Stops gating the evidence in the gated condition, so EG becomes EA and "
  "the study compares a condition against itself.")

M("32-12", "CAMPAIGN", CAMPAIGN,
  "        if layer.bad_samples:\n"
  '            return None, f"trust layer rejected {layer.bad_samples} samples"',
  "        if False:\n"
  '            return None, f"trust layer rejected {layer.bad_samples} samples"',
  "Stops detecting one class of invalid run, so scenarios the trust layer "
  "rejected samples in would be counted as valid data.")

CANARY = {
    "id": "CANARY", "family": "CANARY", "path": EVAL,
    "old": 'IDENTIFIABLE = "IDENTIFIABLE"',
    "new": 'IDENTIFIABLE = "XXXX"',
    "breaks": "changes the support sentinel; nothing should classify",
}

SELECTION = ["tests/test_consequence_phase32.py"]

OUT = os.path.join(ROOT, "research", "consequence", "phase32", "results",
                   "PHASE32_MUTATION_RESULTS.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args(argv)

    selection = [s for s in SELECTION
                 if os.path.isfile(os.path.join(ROOT, s))]
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
        "schema": "csia.consequence.phase32_mutation/1",
        "phase": "3.2 -- direct preregistered consequence test",
        "separate_from": ("E2M_MUTATION_RESULTS.json (38/36/2) and "
                          "PHASE31_MUTATION_RESULTS.json (11/8), neither of "
                          "which is touched by this runner, so none of their "
                          "five survivors can be killed as a side effect"),
        "targets": sorted({m["path"] for m in MUTANTS}),
        "selection": selection,
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
            "not evidence about hardware, and not a re-measurement of any "
            "earlier phase."),
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
