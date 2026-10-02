#!/usr/bin/env python3
"""Apply the preregistered S1-S3 criteria to the as-run evaluation. RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/as_run_verdict.py

Reads MANEUVER_RESULTS_EVAL.json (written once by evaluate_maneuver.py) and
writes MANEUVER_VERDICT_EVAL.json. It computes nothing new from the logs:
it only applies MANEUVER_PREREGISTRATION.md section 4 to the scored counts.

- S1: zero VIOLATED at any scored nominal event (EN1-EN4, ET1, ET2, and
  the PRE events of EF1-EF6 and EH1).
- S2: the injected motor VIOLATED at a POST or STRADDLE event in at least
  5 of the 6 EF flights, and in EH1.
- S3: zero VIOLATED on a non-injected motor at any POST or STRADDLE event.
"""
from __future__ import annotations

import json

import common_rb as C

EF = ("EF1", "EF2", "EF3", "EF4", "EF5", "EF6")


def verdict(sc):
    det = set(sc["detected"])
    s1 = sc["false_violated"] == 0
    s2 = sum(f in det for f in EF) >= 5 and "EH1" in det
    s3 = sc["wrong_motor"] == 0
    return {"S1_no_false_symptom": s1, "S2_detection": s2, "S3_no_wrong_motor": s3,
            "EF_detected": sum(f in det for f in EF), "EH1_detected": "EH1" in det,
            "verdict": "PASS" if s1 and s2 and s3 else
                       ("FAIL (S1: does not move to hardware)" if not s1 else "FAIL")}


def main():
    src = C.HERE / "MANEUVER_RESULTS_EVAL.json"
    res = json.loads(src.read_text())
    not_flown = [r["flight"] for r in res["flights"] if r.get("outcome") != "flown"]
    out = {"label": "as-run verdict: the preregistered criteria applied once to the as-run scores",
           "results_sha256": C.sha(src), "not_flown": not_flown,
           "candidates": {c: verdict(sc) for c, sc in res["score"].items()}}
    C.write_json(C.HERE / "MANEUVER_VERDICT_EVAL.json", out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
