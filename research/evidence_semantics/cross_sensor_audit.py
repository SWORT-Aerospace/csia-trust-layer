"""Item 23. Audit EVERY sensor family, then choose at most two more to probe.

Each row is a fact about committed source, and each fact is pinned by a regex
that must match EXACTLY ONCE in the named file; the line number is then
re-read and compared against the matched text. A regex that matches twice, or
a published line number that does not contain the match, aborts. This is the
same discipline `research/invalidity_masking/source_to_gate_trace.py` used
after a `\\s`-matches-newline bug resolved a line number one line early.

  python research/evidence_semantics/cross_sensor_audit.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
OUT = os.path.join(_HERE, "results")

AD = "csia/aircraft/adapters/ardupilot.py"
BASE = "csia/aircraft/adapters/base.py"
PLUG = "csia/runtime/plugins.py"
ULOG = "csia/runtime/ulog_source.py"


def pin(path, pattern):
    """Locate a unique source fact and return (line_no, text)."""
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        text = fh.read()
    hits = list(re.finditer(pattern, text, re.M))
    if len(hits) != 1:
        raise AssertionError(
            f"{path}: {pattern!r} matched {len(hits)} times, expected 1")
    line_no = text[:hits[0].start()].count("\n") + 1
    matched_first = hits[0].group(0).splitlines()[0]
    lines = text.splitlines()
    if lines[line_no - 1] != matched_first:
        raise AssertionError(
            f"{path}:{line_no} does not contain the matched text; the regex "
            f"resolved to the wrong line")
    return line_no, matched_first.strip()


# family -> channel -> facts. `explicit_source_state` is the question item 23
# prioritises: does the SOURCE have a way of saying "no value"?
ROWS = [
    {"family": "gnss", "channel": "gnss.position/velocity",
     "source_field": "GPS_RAW_INT.fix_type",
     "explicit_source_state": "YES -- fix_type < 3",
     "pin": (AD, r"^        fix = g\(\"fix_type\", 0\)$"),
     "adapter_branch": "pop + _reject_sentinel(NO_3D_FIX)",
     "reason_delivered": "YES (NO_3D_FIX)",
     "reaches_core": "YES (CORE_MAP['gps'])",
     "selected": "ALREADY PROBED (item 14)"},
    {"family": "battery", "channel": "battery.current",
     "source_field": "BATTERY_STATUS.current_battery",
     "explicit_source_state": "YES -- documented -1 'not measured'",
     "pin": (AD, r"^CURRENT_NOT_MEASURED = -1$"),
     "adapter_branch": "_reject_sentinel(default SENTINEL), NO pop",
     "reason_delivered": "NO -- counted, then overridden by the retained value",
     "reaches_core": "YES (CORE_MAP['battery'])",
     "selected": "ALREADY PROBED (item 13)"},
    {"family": "battery", "channel": "battery.voltage",
     "source_field": "BATTERY_STATUS.voltages[i]",
     "explicit_source_state": "YES -- 65535 'cell not present'",
     "pin": (AD, r"^CELL_ABSENT = 65535$"),
     "adapter_branch": "filtered out of the sum; NO rejection path at all",
     "reason_delivered": "NO -- `if volts:` simply does not _put",
     "reaches_core": "YES (CORE_MAP['battery'])",
     "selected": "NO -- same family as battery.current, would not be an "
                 "independent replication"},
    {"family": "mag", "channel": "mag.field_ut",
     "source_field": "SCALED_IMU.xmag/ymag/zmag",
     "explicit_source_state": "YES in the decoders' own reading -- an "
                              "all-zero triple; NOT a documented MAVLink "
                              "sentinel",
     "pin": (AD, r"^                if any\(mag\) and all\(finite\(x\) "
                 r"for x in mag\):$"),
     "adapter_branch": "no _put on the else branch; NO _reject_sentinel",
     "reason_delivered": "NO -- nothing is recorded at all",
     "reaches_core": "YES (CORE_MAP['mag'])",
     "selected": "YES -- ADDITIONAL FAMILY 1"},
    {"family": "estimator_health", "channel": "estimator.variances",
     "source_field": "EKF_STATUS_REPORT.flags + variances",
     "explicit_source_state": "YES -- the flags bitfield is the autopilot's "
                              "own estimator health signal",
     "pin": (AD, r"^            self\._put\(\"estimator\.variances\", \{$"),
     "adapter_branch": "_put only; no invalid path",
     "reason_delivered": "n/a",
     "reaches_core": "NO -- absent from CORE_MAP entirely",
     "selected": "YES -- ADDITIONAL FAMILY 2, as a STRUCTURAL row only: the "
                 "channel never crosses the core boundary, so there is no "
                 "trace to run and the finding is the absence itself"},
    {"family": "baro", "channel": "baro.altitude",
     "source_field": "SCALED_PRESSURE.press_abs",
     "explicit_source_state": "NO -- no sentinel; the adapter's own `p > 0` "
                              "guard is a plausibility check, not a source "
                              "state",
     "pin": (AD, r"^            if p is not None and finite\(p\) and p > 0:$"),
     "adapter_branch": "_put only when the guard passes; silent otherwise",
     "reason_delivered": "NO",
     "reaches_core": "YES (CORE_MAP['baro'])",
     "selected": "NO -- no explicit source state, so it cannot test "
                 "preservation of one"},
    {"family": "imu", "channel": "imu0.accel / imu0.gyro",
     "source_field": "RAW_IMU / SCALED_IMU x/y/z acc+gyro",
     "explicit_source_state": "NO -- MAVLink defines no per-axis invalid "
                              "encoding for these",
     "pin": (AD, r"^            acc = \[g\(\"xacc\", 0\), g\(\"yacc\", 0\), "
                 r"g\(\"zacc\", 0\)\]$"),
     "adapter_branch": "finite() guard only",
     "reason_delivered": "NO",
     "reaches_core": "YES (CORE_MAP['imu0'], ['imu1'])",
     "selected": "NO -- no explicit source state"},
    {"family": "motor_esc", "channel": "esc.rpm / esc.current",
     "source_field": "ESC_TELEMETRY_1_TO_4 / ESC_STATUS",
     "explicit_source_state": "NO -- the adapter defaults a missing current "
                              "array to zeros rather than reading a sentinel",
     "pin": (AD, r"^            cur = np\.asarray\(list\(g\(\"current\", "
                 r"\[0\] \* 4\)\)\[:4\], dtype=float\)$"),
     "adapter_branch": "_put; missing fields default to 0",
     "reason_delivered": "NO",
     "reaches_core": "YES (CORE_MAP['motor_esc'])",
     "selected": "NO -- a defaulted zero is a separate defect class "
                 "(fabricated value), already exercised by plugins.py in "
                 "the battery family"},
    {"family": "vibration", "channel": "vibration.rms",
     "source_field": "VIBRATION.vibration_x/y/z",
     "explicit_source_state": "NO",
     "pin": (AD, r"^            if all\(finite\(v\) for v in "
                 r"\(vx, vy, vz\)\):$"),
     "adapter_branch": "finite() guard only",
     "reason_delivered": "NO",
     "reaches_core": "YES (CORE_MAP['vibration'])",
     "selected": "NO -- no explicit source state"},
    {"family": "vehicle_status", "channel": "vehicle_status.armed",
     "source_field": "HEARTBEAT.base_mode",
     "explicit_source_state": "NO -- but the GCS/vehicle distinction is "
                              "handled (MAV_TYPE_GCS is excluded)",
     "pin": (AD, r"^MAV_TYPE_GCS = 6$"),
     "adapter_branch": "sender-type filter",
     "reason_delivered": "n/a",
     "reaches_core": "YES (CORE_MAP['vehicle_status'])",
     "selected": "NO -- not a measurement channel"},
]


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    out = []
    for r in ROWS:
        path, pattern = r["pin"]
        line_no, text = pin(path, pattern)
        row = {k: v for k, v in r.items() if k != "pin"}
        row["citation"] = f"{path}:{line_no}"
        row["cited_text"] = text
        out.append(row)

    with open(os.path.join(_HERE, "CROSS_SENSOR_AUDIT.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    chosen = [r for r in out if r["selected"].startswith("YES")]
    with open(os.path.join(OUT, "CROSS_SENSOR_AUDIT.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "CROSS_SENSOR_AUDIT",
                   "families_audited": len({r["family"] for r in out}),
                   "channels_audited": len(out),
                   "with_explicit_source_state": sum(
                       1 for r in out
                       if r["explicit_source_state"].startswith("YES")),
                   "additional_families_selected": [r["family"]
                                                    for r in chosen],
                   "limit": "item 23 permits at most TWO additional families",
                   "rows": out}, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  {len(out)} channels audited across "
          f"{len({r['family'] for r in out})} families; every citation "
          f"verified against the file")
    for r in out:
        print(f"    {r['family']:<16} {r['channel']:<24} "
              f"explicit source state: "
              f"{r['explicit_source_state'].split(' --')[0]:<4} "
              f"reaches core: {r['reaches_core'].split(' ')[0]:<4} "
              f"{r['citation']}")
    print(f"\n  additional families selected: "
          f"{[r['family'] for r in chosen]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
