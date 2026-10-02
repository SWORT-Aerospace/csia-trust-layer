#!/usr/bin/env python3
"""PRIME B4: the matched physical A/B decision rule, frozen before any data. RESEARCH ONLY.

    python3 research/csia_prime/ab_scoring.py RUNS.json [--out VERDICT.json]

RUNS.json is a list of runs, one object each, with fields:
- `run_id`, `condition` ("N", "A", "B-phys", "B-syn"), `level` (eta for A; the
  matched A level for B), `ground_truth_cause` (from the run sheet);
- from the product's report for motor_0 (the bench configuration):
  `symptoms_any_time` (list), `telemetry_state` (esc.telemetry_response, at
  AFTER), `physical_state` (actuation.physical_response from the load-cell
  producer, at AFTER), `unique` (the UNIQUE candidate or null);
- `L_median` (the telemetry producer's local symptom over the hold steps);
- `independent_lines` (load cell vs ESC telemetry) and `esc_rpm_current_lines`
  (ESC RPM vs ESC current), from the report's lineage section.

Implements B4_MATCHED_AB_PROTOCOL.md sections 7, 8 and 10 exactly. Nothing in
it may change after the first fault run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MATCH_TOL = 0.03
MOTOR = "COMMAND_NO_RESPONSE|motor_0"


def classify(r: dict) -> str:
    if MOTOR in r["symptoms_any_time"] and r["physical_state"] == "VIOLATED":
        return "A_CONFIRMED"
    if r["physical_state"] in ("UNAVAILABLE", "NOT_APPLICABLE"):
        return "UNRESOLVED"
    if r["telemetry_state"] == "DEGRADED" and r["physical_state"] == "NOMINAL" and MOTOR not in r["symptoms_any_time"]:
        return "TELEMETRY_ONLY"
    if r["telemetry_state"] == "NOMINAL" and not r["symptoms_any_time"]:
        return "NO_CHANGE"
    return "OTHER"


def score(runs: list) -> dict:
    a_L = {}
    for r in runs:
        if r["condition"] == "A":
            a_L.setdefault(r["level"], []).append(r["L_median"])
    a_med = {k: sorted(v)[len(v) // 2] for k, v in a_L.items()}
    rows, errors = [], {"B_AS_A": [], "A_AS_B": [], "WRONG_UNIQUE": [], "WRONG_MOTOR": []}
    for r in runs:
        c = classify(r)
        matched = None
        if r["condition"] == "B-phys":
            matched = r["level"] in a_med and abs(r["L_median"] - a_med[r["level"]]) <= MATCH_TOL
        if r["condition"].startswith("B") and c == "A_CONFIRMED":
            errors["B_AS_A"].append(r["run_id"])
        if r["condition"] == "A" and c == "TELEMETRY_ONLY":
            errors["A_AS_B"].append(r["run_id"])
        if r.get("unique") and r["unique"] != r["ground_truth_cause"]:
            errors["WRONG_UNIQUE"].append(r["run_id"])
        if any(s.startswith("COMMAND_NO_RESPONSE|") and s != MOTOR for s in r["symptoms_any_time"]):
            errors["WRONG_MOTOR"].append(r["run_id"])
        rows.append({"run_id": r["run_id"], "condition": r["condition"], "level": r["level"],
                     "class": c, "matched": matched})
    a_runs = [x for x in rows if x["condition"] == "A"]
    s2_per_level = {}
    for x in a_runs:
        s2_per_level.setdefault(x["level"], []).append(x["class"])
    s2 = all(cls.count("A_CONFIRMED") >= len(cls) - 1 and "TELEMETRY_ONLY" not in cls
             for cls in s2_per_level.values())
    b_phys = [x for x in rows if x["condition"] == "B-phys"]
    lines_ok = all(r.get("independent_lines") == 2 and r.get("esc_rpm_current_lines") == 1
                   for r in runs if r["condition"] in ("A", "B-phys"))
    s5 = all(r["telemetry_state"] == "DEGRADED" for r in runs if r["condition"] in ("A", "B-phys"))
    crit = {"S1_zero_B_as_A": not errors["B_AS_A"], "S2_A_confirmed": s2,
            "S3_zero_wrong_unique_and_motor": not errors["WRONG_UNIQUE"] and not errors["WRONG_MOTOR"],
            "S4_lineage": lines_ok, "S5_local_symptom_in_A_and_B": s5}
    stop = bool(errors["B_AS_A"] or errors["WRONG_UNIQUE"] or not lines_ok)
    return {"rows": rows, "errors": errors, "criteria": crit,
            "unmatched_B_phys": [x["run_id"] for x in b_phys if not x["matched"]],
            "verdict": "PASS" if all(crit.values()) else "FAIL", "stop_condition": stop}


def main():
    runs = json.loads(Path(sys.argv[1]).read_text())
    out = score(runs)
    text = json.dumps(out, indent=1, sort_keys=True) + "\n"
    if "--out" in sys.argv:
        Path(sys.argv[sys.argv.index("--out") + 1]).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
