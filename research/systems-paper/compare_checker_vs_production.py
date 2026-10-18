"""B3: does the independent checker agree with the production analysis?

    Compare against production analysis.
    Any disagreement blocks submission.

THE COMPARISON IS TICK-BY-TICK AND PAIR-BY-PAIR. Nine scenarios x 1500 ticks
x 28 unordered hypothesis pairs. For each, two answers:

    PRODUCTION   engineering/v1_1/support/decompose.py -- Decomposition
                 .discriminating(k, a, b): active terms whose NUMERIC
                 contribution to a and to b differs by more than tau
    CHECKER      research/systems-paper/independent_checker.py -- active
                 terms in the STRUCTURAL symmetric difference LOW(a) ^ LOW(b),
                 read from the committed signature matrix

They are computed from different inputs by different code. The checker imports
no csia module and no part of the support-aware implementation; this script
imports both, which is why the checker is run through its own module-level
functions here only after those functions have already produced the committed
`checker_verdicts.json` in a clean interpreter (see the test).

ONE DISAGREEMENT CLASS IS EXPECTED AND IS NOT A FAILURE. lo_j == hi_j exactly
when c_j == 0.5, so a structurally distinguishing feature can contribute zero
numeric difference at a tick. Production then omits it and the checker keeps
it. Those cases are counted separately as `degenerate` and are NOT counted as
agreement -- calling them agreement would hide the only place the two
definitions genuinely differ.

    python research/systems-paper/compare_checker_vs_production.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
SUPPORT = os.path.join(ROOT, "engineering", "v1_1", "support")
for p in (ROOT, SUPPORT, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import decompose as D                                        # noqa: E402
from csia.scenarios import run_scenario                      # noqa: E402
from export_active_sets import GATE_EPS, SCENARIOS           # noqa: E402
from independent_checker import (active_distinguishing,      # noqa: E402
                                 load_low_sets)

OUT = os.path.join(_HERE, "results", "checker_agreement.json")


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def compare_one(label: str, key: str, low: dict) -> dict:
    _t, _f, td, _h, _d = run_scenario(key)
    dec = D.decompose(td)
    names = sorted(low)
    assert sorted(dec.names) == names, (
        "the checker's hypothesis set and production's differ; the "
        "signature matrix is stale relative to csia/diagnosis/bayes.py")

    K = len(dec.t)
    agree = disagree = degenerate = 0
    examples, target_rows = [], []

    for k in range(K):
        active = set(dec.active_terms(k))
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                prod = set(dec.discriminating(k, a, b))
                mine = set(active_distinguishing(low, a, b, active))
                if prod == mine:
                    agree += 1
                    continue
                # Is the whole difference explained by numerically
                # degenerate terms (c == 0.5)?
                delta = np.abs(dec.delta(k, a, b))
                only_degenerate = all(
                    delta[dec.features.index(f)] <= D.TAU_NUM
                    for f in (mine - prod))
                if only_degenerate and not (prod - mine):
                    degenerate += 1
                    if len(examples) < 5:
                        examples.append({"tick": k, "pair": f"{a}|{b}",
                                         "class": "degenerate",
                                         "checker_only": sorted(mine - prod)})
                else:
                    disagree += 1
                    if len(examples) < 20:
                        examples.append({
                            "tick": k, "pair": f"{a}|{b}",
                            "class": "REAL_DISAGREEMENT",
                            "production": sorted(prod),
                            "checker": sorted(mine)})

    # The pair the paper is about, per tick, from BOTH sides.
    ia = names.index("gps_fault")
    for k in range(K):
        active = set(dec.active_terms(k))
        prod = sorted(dec.discriminating(k, "nominal", "gps_fault"))
        mine = sorted(active_distinguishing(low, "nominal", "gps_fault",
                                            active))
        target_rows.append((k, len(prod), len(mine)))
    blind_prod = sum(1 for _k, p, _m in target_rows if p == 0)
    blind_mine = sum(1 for _k, _p, m in target_rows if m == 0)

    return {
        "scenario": key, "ticks": K, "pairs_compared": agree + disagree + degenerate,
        "agree": agree, "real_disagreements": disagree,
        "degenerate_only": degenerate,
        "examples": examples,
        "target_pair_blind_ticks_production": blind_prod,
        "target_pair_blind_ticks_checker": blind_mine,
        "target_pair_blind_agrees": blind_prod == blind_mine,
        "_unused_ia": ia,
    }


def main() -> int:
    low = load_low_sets()
    doc = {
        "artifact": "CHECKER_AGREEMENT",
        "generation_command":
            "python research/systems-paper/compare_checker_vs_production.py",
        "commit": _git("rev-parse", "HEAD"),
        "gate_eps": GATE_EPS, "tau_num": D.TAU_NUM,
        "production": "engineering/v1_1/support/decompose.py "
                      "Decomposition.discriminating (numeric, |delta| > tau)",
        "checker": "research/systems-paper/independent_checker.py "
                   "(structural, LOW(a) ^ LOW(b) intersect active)",
        "known_disagreement_class":
            "c == 0.5 makes log(1-c+eps) == log(c+eps), so a structurally "
            "distinguishing term contributes zero numeric difference. "
            "Counted separately as `degenerate_only`, never as agreement.",
        "scenarios": {},
    }
    total = {"agree": 0, "real_disagreements": 0, "degenerate_only": 0}
    for label, key in sorted(SCENARIOS.items()):
        row = compare_one(label, key, low)
        row.pop("_unused_ia", None)
        doc["scenarios"][label] = row
        for f in total:
            total[f] += row[f]
        print(f"  {label:<22} agree={row['agree']:>7} "
              f"degenerate={row['degenerate_only']:>4} "
              f"REAL_DISAGREE={row['real_disagreements']:>4}  "
              f"blind(prod/checker)="
              f"{row['target_pair_blind_ticks_production']}/"
              f"{row['target_pair_blind_ticks_checker']}")
    doc["totals"] = total
    doc["blocks_submission"] = total["real_disagreements"] > 0
    doc["verdict"] = ("CHECKER_AGREES_WITH_PRODUCTION"
                      if total["real_disagreements"] == 0
                      else "DISAGREEMENT_BLOCKS_SUBMISSION")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\ntotals: {total}")
    print(f"verdict: {doc['verdict']}")
    print(OUT)
    return 0 if not doc["blocks_submission"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
