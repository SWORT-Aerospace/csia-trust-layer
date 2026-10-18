"""The two-gate 2x2 table, computed over an existing campaign artifact.

No plant is re-run for the campaign rows. The pre-action gate is a function of
the proposed action, the target magnitude, the plant and the declared envelope,
all of which every row already carries, so the gate is an analysis layer rather
than a new experiment. That is why `PREREGISTRATION_AMENDMENT_3.md` did not
trigger a third campaign.

Predicted output sets are seed-independent by construction, so the gate is
cached on (action, magnitude, plant) and the whole table costs a few thousand
noise-free integrations rather than a few hundred thousand.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time
from typing import Dict, List, Optional, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_independent_validation import evaluator as ev          # noqa: E402
from csia_independent_validation import gates                    # noqa: E402

RESULTS = ROOT / "research/active_evidence/independent_validation/results"


def _resolved_point(row: Dict) -> bool:
    if row["ae_r"] is None:
        return False
    return row["ae_r"] < ev.TAU_R_RELATIVE * row["magnitude"]


def build(campaign_path: pathlib.Path) -> Dict:
    campaign = json.loads(campaign_path.read_text())
    main = [r for r in campaign["rows"] if r["block"] == "main"]

    cache: Dict[Tuple, gates.PreGate] = {}
    started = time.time()
    prepared: List[Dict] = []
    for row in main:
        key = (row["action"], row["magnitude"], row["plant"])
        if key not in cache:
            cache[key] = gates.pre_gate(row["action"], row["magnitude"],
                                        plant=row["plant"], seed=0)
        pre = cache[key]
        prepared.append({
            "arm": row["arm"], "plant": row["plant"],
            "drift_state": row["drift_state"], "magnitude": row["magnitude"],
            "seed": row["seed"], "action": row["action"],
            "state": row["state"],
            "pre_pass": pre.passes,
            "pre_safe": pre.safe, "pre_separates": pre.separates,
            "pre_touching": pre.touching,
            "separation_margin_v": pre.separation_margin_v,
            "overlap_volume_v": pre.overlap_volume_v,
            "post_pass": gates.post_gate(row["state"]),
            "resolved_point": _resolved_point(row),
            "resolved_change": bool(row["resolved"]),
            "ae_r": row["ae_r"], "energy_as": row["energy_as"],
            "duration_s": row["duration_s"],
        })

    table = gates.gate_table(prepared)

    change_rows = [{**r, "resolved_point": r["resolved_change"]}
                   for r in prepared]
    change_table = gates.gate_table(change_rows)

    by_arm: Dict[str, Dict] = {}
    for arm in sorted({r["arm"] for r in prepared}):
        subset = [r for r in prepared if r["arm"] == arm]
        by_arm[arm] = {
            "n": len(subset),
            "pre_pass_fraction": sum(r["pre_pass"] for r in subset)
                / len(subset),
            "post_pass_fraction": sum(r["post_pass"] for r in subset)
                / len(subset),
            "both_fraction": sum(r["pre_pass"] and r["post_pass"]
                                 for r in subset) / len(subset),
        }

    return {
        "schema": "csia.independent_validation.gate_table/1",
        "source_campaign": str(campaign_path.relative_to(ROOT)),
        "partition": campaign["partition"],
        "n_main_rows": len(main),
        "distinct_pre_gate_evaluations": len(cache),
        "elapsed_s": time.time() - started,
        "primary_metric": "point (AE_R < tau_R), per amendment 3",
        "table_point_metric": table,
        "table_change_metric": change_table,
        "by_arm": by_arm,
        "safety_sub_gate_is_vacuous": all(r["pre_safe"] or r["action"] is None
                                          for r in prepared),
        "touching_cases": sum(r["pre_touching"] for r in prepared),
        "caveat": ("the safety sub-gate cannot fail for any admissible "
                   "action; all discriminating power is in the separation "
                   "sub-gate. See COUNTEREXAMPLE_LOG.md IV-19."),
        "rows": prepared,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", default="validation")
    args = parser.parse_args()
    path = RESULTS / f"CAMPAIGN_{args.partition.upper()}.json"
    if not path.is_file():
        print(f"no campaign artifact at {path.relative_to(ROOT)}")
        return 1
    document = build(path)
    out = RESULTS / f"GATE_TABLE_{args.partition.upper()}.json"
    out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")

    print(f"wrote {out.relative_to(ROOT)}")
    print(f"{document['n_main_rows']} main rows, "
          f"{document['distinct_pre_gate_evaluations']} distinct pre-gate "
          f"evaluations, {document['elapsed_s']:.0f} s")
    print(f"safety sub-gate vacuous: "
          f"{document['safety_sub_gate_is_vacuous']}  "
          f"touching cases: {document['touching_cases']}")
    for name, key in (("POINT METRIC (primary)", "table_point_metric"),
                      ("CHANGE METRIC", "table_change_metric")):
        table = document[key]
        print(f"\n--- {name} ---")
        for cell, stats in sorted(table["cells"].items()):
            print(f"  {cell:24s} n={stats['n']:5d} resolved={stats['resolved']:5d} "
                  f"wrong={stats['wrong']:5d}")
        print("  policy                 accepted  coverage  false  rate")
        for policy, stats in table["policies"].items():
            rate = ("n/a" if stats["false_accept_rate"] is None
                    else f"{stats['false_accept_rate']:.4f}")
            print(f"  {policy:20s} {stats['accepted']:8d}  "
                  f"{stats['coverage']:.4f}  {stats['false_accepted']:5d}  "
                  f"{rate}")
        print("  verdict:", json.dumps(table["verdict"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
