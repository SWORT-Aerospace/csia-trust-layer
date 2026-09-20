"""Mutation testing for the Phase-3.1 actionability-precondition study.

WHY A THIRD RUNNER AND NOT A LONGER SECOND ONE
-----------------------------------------------
`run_e2m_mutations.py` reports 38 evaluated / 36 killed / 2 survived, and that
number is quoted in Phase 3's write-up and pinned by a committed test.
Appending Phase-3.1 mutants would change the denominator, and adding
`tests/test_consequence_phase31.py` to that runner's selection could kill
`P3-03` or `P3-04` as a side effect -- which would be exactly the artificial
kill the Phase-3.1 brief forbids. So this is a sibling with its own list, its
own selection and its own output file, and `run_e2m_mutations.py` is not
touched at all.

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


EVAL = "research/consequence/phase31/evaluate31.py"
MODEL = "csia_consequence/consequence_model31.py"
CAMPAIGN = "research/consequence/phase31/campaign31.py"

# ------------------------------------------------------------- THE SPAN RULE
M("31-01", "SPAN", EVAL,
  '    return float(segment["ticks"]) / TICK_HZ',
  '    return segment["t_end"] - segment["t_start"]',
  "Reverts to Phase 3's span rule. A single-tick segment then measures zero, "
  "and since the frozen failsafe issues each action exactly once, every "
  "attributing action measures zero -- so an unsupported confident "
  "attribution becomes invisible. This is the defect Phase 3.1 exists to "
  "correct; if no test objects, the correction is not pinned.")

M("31-02", "SPAN", EVAL,
  "        if response in ATTRIBUTING:\n                unsupported_s += d",
  "        if False:\n                unsupported_s += d",
  "Stops counting a confident attribution issued while its separating "
  "evidence is gated off.")

# ------------------------------------------------------------- MATERIALITY
M("31-03", "MATERIALITY", EVAL,
  "    return RESPONSE_CLASS[a] != RESPONSE_CLASS[b]",
  "    return False",
  "Declares no two responses materially different, so no action conflict can "
  "ever be recorded.")

M("31-04", "MATERIALITY", EVAL,
  "    conflict = bool(kinds) and RESPONSE_CLASS[correct_response] not in classes",
  "    conflict = bool(kinds) and correct_response not in kinds",
  "Decides the conflict on response LABELS rather than classes, so "
  "CONTROLLED_DESCENT where PREPARE_LANDING was correct -- the same class -- "
  "would be reported as a conflict.")

# ------------------------------------------------------------- STATISTICS
M("31-05", "STATS", EVAL,
  "    low = 0.0 if k == 0 else bisect(lambda p: cdf_at_least(p, k), alpha / 2.0)",
  "    low = 0.0",
  "Pins the lower confidence bound at zero. A rate of 12/12 would then be "
  "reported as consistent with zero.")

M("31-06", "STATS", EVAL,
  "    return min(1.0, 2.0 * tail)",
  "    return tail",
  "Turns the exact McNemar test one-sided, halving every p-value in the "
  "study.")

# ------------------------------------------------------------- GROUND TRUTH
M("31-07", "TRUTH", MODEL,
  '    if fault_family == "power_sag":',
  "    if False:",
  "Drops the declared correct response for a sagging pack, so a power fault "
  "falls through to Phase 3's table and is scored against the wrong ground "
  "truth.")

M("31-08", "TRUTH", MODEL,
  "DRIFT_POWER_MPS = 0.0",
  "DRIFT_POWER_MPS = 1.20",
  "Invents a horizontal drift for a fault that causes no attitude error -- "
  "the precise thing the amendment declares zero in order not to do.")

M("31-09", "TRUTH", MODEL,
  "        base.FAULT_DRIFT = original",
  "        pass",
  "Leaves Phase 3.1's fault table installed in Phase 3's module after the "
  "call, so Phase 3's model would silently change underneath it.")

# ------------------------------------------------------------- DEFINITIONS
M("31-10", "DEFINITION", EVAL,
  '        if r["correct_response"] in r["policies"]["P0"]["responses_issued"]\n'
  '        and r["correct_response"] not in r["policies"]["P2"]["responses_issued"]]',
  '        if r["policies"]["P0"]["outcome"] == "CORRECT_ACTIONABLE"]',
  "Restores the false-refusal definition that a development run exposed: "
  "keyed on P0's outcome LABEL, it reported zero false refusals while twelve "
  "were happening, because P0's label in those scenarios is "
  "UNSUPPORTED_CONFIDENCE.")

M("31-11", "DEFINITION", CAMPAIGN,
  '    drop = (GATING_SENSOR,) if condition == "EG" else ()',
  "    drop = ()",
  "Stops gating the evidence in the gated condition, so EG becomes EA and "
  "the study compares a condition against itself.")

CANARY = {
    "id": "CANARY", "family": "CANARY", "path": EVAL,
    "old": 'IDENTIFIABLE = "IDENTIFIABLE"',
    "new": 'IDENTIFIABLE = "XXXX"',
    "breaks": "changes the support sentinel; nothing should classify",
}

SELECTION = ["tests/test_consequence_phase31.py"]

OUT = os.path.join(ROOT, "research", "consequence", "phase31", "results",
                   "PHASE31_MUTATION_RESULTS.json")


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
            raise SystemExit(
                "ABORT: the canary SURVIVED. The selection is wrong or the "
                "sandbox is not live; every result would be a false "
                "survivor.")

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
        "schema": "csia.consequence.phase31_mutation/1",
        "phase": "3.1 -- actionability precondition",
        "separate_from": ("research/bus_provenance/results/"
                          "E2M_MUTATION_RESULTS.json, which stays at 38 "
                          "evaluated / 36 killed / 2 survived and is not "
                          "touched by this runner"),
        "targets": sorted({m["path"] for m in MUTANTS}),
        "selection": selection,
        "working_tree_files_synced_into_sandbox": synced,
        "evaluated": len(evaluated), "killed": len(killed),
        "survived": len(evaluated) - len(killed),
        "invalid": len(results) - len(evaluated),
        "score": score,
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
            "not evidence about hardware, and not a second measurement of "
            "Phase 3. A high score means the tests would notice a change in "
            "the Phase-3.1 measurement code."),
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
