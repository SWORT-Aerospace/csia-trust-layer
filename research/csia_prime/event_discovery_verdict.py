#!/usr/bin/env python3
"""Apply EVENT_DISCOVERY_PREREG.md section 4, once, to the as-run evaluation. RESEARCH ONLY.

    python3 research/csia_prime/event_discovery_verdict.py

Reads EVENT_DISCOVERY_EVAL.json; computes nothing new from the logs. Writes
EVENT_DISCOVERY_VERDICT.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUDGET = 6.0


def main():
    src = HERE / "EVENT_DISCOVERY_EVAL.json"
    d = json.loads(src.read_text())
    rows = d["flights"]

    def found(c):
        return {r["flight"] for r in rows if r["candidate"] == c and r["kind"] == "physical" and r["detected"]}
    e0 = found("E0")
    e0_rate = d["summary"]["E0"]["false_events_per_h"]
    out = {}
    for c, s in d["summary"].items():
        s1 = s["false_symptoms"] == 0 and s["wrong_unique"] == 0
        s2 = e0 <= found(c)
        s3 = s["false_events_per_h"] <= BUDGET
        verdict = ("PASS" if s1 and s2 and s3 else
                   "REDUCES" if s1 and s2 and s["false_events_per_h"] <= 0.5 * e0_rate else "FAIL")
        out[c] = {"S1_safety": s1, "S2_detection_superset_of_E0": s2, "S3_budget": s3,
                  "false_events_per_h": s["false_events_per_h"], "faults_detected": s["faults_detected"],
                  "verdict": verdict}
    (HERE / "EVENT_DISCOVERY_VERDICT.json").write_text(json.dumps(
        {"label": "as-run verdict: EVENT_DISCOVERY_PREREG.md section 4 applied once",
         "results_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
         "E0_detected": sorted(e0), "candidates": out}, indent=1, sort_keys=True) + "\n")
    for c, v in out.items():
        print(c, v)


if __name__ == "__main__":
    main()
