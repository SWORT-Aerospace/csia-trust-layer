#!/usr/bin/env python3
"""Deliverable 5, table: ArduPilot SITL mission and GPS-glitch injection,
pre-hardening rows against re-runs at the current HEAD.

    python publication/evidence_v2/tab_d5_sitl_before_after.py

BEFORE is prose, not data. The pre-hardening rows C12 and C13
(docs/evidence/evidence_matrix.md, "must be re-run") exist only as README
sentences, first written at f2786f6 (C12, v0.6.0) and 758f4ae (C13, v0.7.0);
docs/audit/WP_A2_CLAIM_PROVENANCE_MATRIX.csv row A9 records "no artifact". The
ArduPilot build they used is not recorded. They are quoted verbatim here, with
the commit that wrote them, and never treated as measurements.

AFTER is data/d5_sitl_ardupilot.json (measure_d5_sitl_ardupilot.py):
tools/sitl_validate.py, unchanged since 758f4ae, run at the current HEAD
against ArduCopter V4.8.0-dev @ 01a504b, three repetitions per mode. Fields are
the ones the tool itself prints; nothing is re-scored.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

DATA = os.path.join(C.DATA, "d5_sitl_ardupilot.json")
OUT = os.path.join(C.TABLES, "d5_sitl_before_after.csv")
BEFORE = (
    ("C12", "none", "f2786f6", "README.md validation table, v0.6.0",
     "PASS: 6 sensors monitored, min trust 0.78, zero false alarms, landed"),
    ("C13", "gps_glitch", "758f4ae", "README.md validation table, v0.7.0",
     "PASS: both faults detected live from the RAW receiver stream (GPS trust 0.99 -> 0.70, nav CAUTION raised)"),
)


def fmt_trust(d):
    if not isinstance(d, dict) or not d:
        return ""
    return "; ".join(f"{k} {v}" for k, v in sorted(d.items()))


def main() -> int:
    data = json.load(open(DATA, encoding="utf-8"))
    rows = []
    for row_id, mode, commit, where, text in BEFORE:
        rows.append(("before", row_id, mode, "", commit, "unrecorded", text, "", "", "", "", "", ""))
    for r in data["runs"]:
        p = r["parsed"]
        alarms = p.get("alarms", [])
        gps_alarms = [a for a in alarms if "gps" in a["reasons"].lower()]
        minimum = p.get("min_trust_after_30s") or {}
        rows.append((
            "after", "C12" if r["inject"] == "none" else "C13", r["inject"], r["rep"],
            data["csia_head_at_measurement"], f"{data['ardupilot_firmware']} @ {data['ardupilot_commit'][:7]}",
            p.get("verdict", "NO VERDICT PRINTED"),
            len(p.get("monitored_sensors") or []),
            min(minimum.values()) if isinstance(minimum, dict) and minimum else "",
            minimum.get("gps", "") if isinstance(minimum, dict) else "",
            len(alarms), len(gps_alarms),
            {True: "yes", False: "no"}.get(p.get("landed"), "not printed"),
        ))
    C.write_csv(OUT, ("column", "row", "inject", "rep", "csia_commit", "autopilot", "verdict_or_claim",
                      "monitored_sensors", "min_trust_any_after_30s", "min_gps_trust_after_30s",
                      "non_normal_transitions", "transitions_citing_gps", "landed"), rows)
    C.stamp(OUT, __file__, inputs=(DATA,),
            measured_at_utc=data["runs"][0]["wall_start_utc"] if data["runs"] else None,
            configs=((os.path.join(C.ROOT, "tools", "sitl_validate.py"), "mission, injection, verdict rule"),),
            datasets={"autopilot": data["ardupilot_firmware"], "ardupilot_commit": data["ardupilot_commit"],
                      "arducopter_binary_sha256": data["arducopter_binary_sha256"],
                      "copter_parm_sha256": data["copter_parm_sha256"],
                      "measurement_git_head": data["csia_head_at_measurement"],
                      "before_sources": [f"{b[3]} at {b[2]}" for b in BEFORE]},
            seeds={"note": "SITL runs on the wall clock with no seed; three repetitions per mode"},
            definitions=[{"metric": "verdict", "source": "tools/sitl_validate.py", "section": "verdict block"}],
            notes=["before values are README prose with no artifact (WP_A2 row A9); not measurements",
                   "PX4 SIH: INAPPLICABLE, no GPS-glitch parameter (research/v1_1/CURRENT_STACK_REPLICATION.md)"])
    return 0


if __name__ == "__main__":
    C.main_guard(main)
