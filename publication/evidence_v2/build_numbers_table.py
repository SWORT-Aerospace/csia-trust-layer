#!/usr/bin/env python3
"""Every number evidence_v2 produced, with its source script and commit.

    python publication/evidence_v2/build_numbers_table.py

Reads each table under tables/ and its stamp, writes tables/all_numbers.csv
(stamped), and rewrites the section of EVIDENCE_V2_REPORT.md between
`<!-- NUMBERS:BEGIN -->` and `<!-- NUMBERS:END -->`. The report's prose is
hand-written; this section is not, so a number in it cannot drift from the
table it came from.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

REPORT = os.path.join(C.HERE, "EVIDENCE_V2_REPORT.md")
OUT = os.path.join(C.TABLES, "all_numbers.csv")
SOURCES = ("d2_alert_episode_rate_checkpoint.csv", "d3_latency_stages.csv", "d4_soak_summary.csv",
           "d5_sitl_before_after.csv", "d6_flat_monitor_locked.csv")
BEGIN, END = "<!-- NUMBERS:BEGIN -->", "<!-- NUMBERS:END -->"


def rows_for(name, r):
    if name.startswith("d2_"):
        yield "D2", r["quantity"], r["recomputed"]
    elif name.startswith("d3_"):
        stage = r["stage"]
        if r["runs_reaching_stage"] == "0":
            yield "D3", f"{r['fault_class']} {stage}", f"0/{r['runs']} runs reached it"
        else:
            yield "D3", f"{r['fault_class']} {stage}", (
                f"{r['runs_reaching_stage']}/{r['runs']} runs; median {r['median_s']} s; p95 {r['p95_s']} s")
    elif name.startswith("d4_"):
        yield "D4", r["quantity"], r["value"]
    elif name.startswith("d5_"):
        if r["column"] == "before":
            yield "D5", f"before {r['row']} ({r['inject']}), {r['csia_commit']}", r["verdict_or_claim"]
        else:
            yield "D5", f"after {r['row']} ({r['inject']}) rep {r['rep']}", (
                f"{r['verdict_or_claim']}; sensors {r['monitored_sensors']}; min trust {r['min_trust_any_after_30s']}; "
                f"min gps {r['min_gps_trust_after_30s']}; non-NORMAL transitions {r['non_normal_transitions']} "
                f"({r['transitions_citing_gps']} citing GPS); landed {r['landed']}")
    elif name.startswith("d6_"):
        yield "D6", f"{r['detector']} threshold {r['threshold']}", (
            f"detections {r['detections']}/{r['faulted_runs']}; false-alarm runs {r['false_alarm_runs']}/"
            f"{r['nominal_runs']}; median delay {r['median_delay_s']} s "
            f"[{r['median_delay_ci95_lo']}, {r['median_delay_ci95_hi']}]")


def main() -> int:
    table, inputs = [], []
    for name in SOURCES:
        path = os.path.join(C.TABLES, name)
        st = json.load(open(path + ".stamp.json", encoding="utf-8"))
        inputs.append(path)
        for item, quantity, value in (x for r in C.read_csv(path) for x in rows_for(name, r)):
            table.append((item, quantity, value, st["script"], st["git_commit"][:12]))
    C.write_csv(OUT, ("item", "quantity", "value", "script", "commit"), table)
    C.stamp(OUT, __file__, inputs=inputs, notes=["one row per number group; full precision is in the source tables"])

    md = ["| item | quantity | value | script | commit |", "|---|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | `{os.path.basename(d)}` | `{e}` |" for a, b, c, d, e in table]
    text = open(REPORT, encoding="utf-8").read()
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    with open(REPORT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(head + BEGIN + "\n" + "\n".join(md) + "\n" + END + tail)
    print(f"{len(table)} rows")
    return 0


if __name__ == "__main__":
    C.main_guard(main)
