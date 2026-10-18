"""Which other sensor families could even exhibit this? Source audit only.

Items 29 and 30. The question is NOT whether the split helps elsewhere -- that
would need experiments this work package does not run. It is the prior
question: does any other sensor family in this stack even HAVE the ingredients?

For a family to be a candidate it needs all four:

  1. an explicit INVALID state the source can report (not just absence);
  2. a path by which that invalid state becomes a no-update downstream;
  3. one gate controlling both operational and diagnostic use;
  4. some status or health field that remains meaningful once the value is
     inadmissible -- without this, T3 says the split provably cannot help.

Every cell is resolved from the tree. Nothing is inferred from a variable name.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
sys.path.insert(0, ROOT)

ADAPTERS = ("csia/aircraft/adapters/ardupilot.py",
            "csia/aircraft/adapters/px4.py")

# family -> (core sensor name, protocol messages, health/status fields the
# protocol carries that do NOT depend on the primary value being usable)
FAMILIES = {
    "gnss": ("gps", "GPS_RAW_INT / vehicle_gps_position",
             ["fix_type", "satellites_visible", "h_acc", "v_acc", "eph",
              "epv", "vel_acc", "hdg_acc"]),
    "barometer": ("baro", "SCALED_PRESSURE / sensor_baro",
                  []),
    "magnetometer": ("mag", "RAW_IMU / SCALED_IMU* / sensor_mag",
                     []),
    "imu0": ("imu0", "RAW_IMU / SCALED_IMU / HIGHRES_IMU",
             []),
    "imu1": ("imu1", "SCALED_IMU2 / HIGHRES_IMU",
             []),
    "battery": ("battery", "BATTERY_STATUS / battery_status",
                ["battery_remaining", "charge_state", "fault_bitmask",
                 "time_remaining", "temperature"]),
    "esc": ("motor_esc", "ESC_TELEMETRY_1_TO_4 / ESC_STATUS / esc_status",
            ["temperature"]),
    "vibration": ("vibration", "VIBRATION / vehicle_imu_status",
                  ["clipping_0", "clipping_1", "clipping_2"]),
    "estimator": (None, "EKF_STATUS_REPORT / estimator_status",
                  ["velocity_variance", "pos_horiz_variance",
                   "pos_vert_variance", "compass_variance", "flags"]),
    "rangefinder_or_air_data": (None, "NOT MAPPED IN THIS STACK", []),
}


def adapter_text():
    return {p: open(os.path.join(ROOT, p), encoding="utf-8").read()
            for p in ADAPTERS}


def explicit_invalid_path(texts, family):
    """Does an adapter reject a channel of this family with a NAMED reason?"""
    hits = []
    for path, t in texts.items():
        for m in re.finditer(r"_reject_sentinel\(([^)]*)\)", t, re.S):
            args = m.group(1)
            if f'"{family}.' in args or f"'{family}." in args:
                line = t.count("\n", 0, m.start()) + 1
                reason = re.search(r"MissingReason\.(\w+)", args)
                hits.append({
                    "cite": f"{path}:{line}",
                    "reason": reason.group(1) if reason else "SENTINEL",
                    "call": " ".join(args.split()),
                })
    return hits


def becomes_no_update(texts, family):
    """Does the reject also DELETE the retained value (pop from _latest)?"""
    out = []
    for path, t in texts.items():
        for m in re.finditer(
                rf'self\._latest\.pop\("({re.escape(family)}\.[a-z_]+)"',
                t):
            out.append(f"{path}:{t.count(chr(10), 0, m.start()) + 1} "
                       f"pops {m.group(1)}")
    return out


def failsafe_reads(sensor):
    """Does the operational policy read this sensor's freshness or trust?"""
    if sensor is None:
        return []
    t = open(os.path.join(ROOT, "csia/runtime/failsafe.py"),
             encoding="utf-8").read()
    out = []
    for pat, label in ((rf'fresh\.get\("{sensor}"', "fresh"),
                       (rf'T\["{sensor}"\]', "trust"),
                       (rf'"{sensor}"\) for n in', "fresh")):
        for m in re.finditer(pat, t):
            out.append(f"{label}@csia/runtime/failsafe.py:"
                       f"{t.count(chr(10), 0, m.start()) + 1}")
    return sorted(set(out))


def admissible_channels():
    from csia.aircraft.qualification import SemanticContract
    c = SemanticContract()
    return set(c.admissible_channels()), set(c.channels)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    texts = adapter_text()
    adm, allch = admissible_channels()

    rows = []
    for fam, (sensor, proto, health) in FAMILIES.items():
        inv = explicit_invalid_path(texts, fam)
        pops = becomes_no_update(texts, fam)
        fs = failsafe_reads(sensor)
        chans = sorted(c for c in allch if c.split(".")[0] == fam)
        adm_chans = sorted(c for c in chans if c in adm)
        candidate = bool(inv and pops and fs and health)
        rows.append({
            "family": fam,
            "core_sensor": sensor or "",
            "protocol": proto,
            "contract_channels": ";".join(chans),
            "admissible_channels": ";".join(adm_chans),
            "has_explicit_invalid_state": bool(inv),
            "explicit_invalid_sites": ";".join(h["cite"] for h in inv),
            "invalid_reason": ";".join(sorted({h["reason"] for h in inv})),
            "invalid_becomes_no_update": bool(pops),
            "no_update_sites": ";".join(pops),
            "one_gate_both_roles": bool(fs),
            "operational_consumer_sites": ";".join(fs),
            "health_fields_surviving_value_loss": ";".join(health),
            "candidate_for_split": candidate,
        })

    with open(os.path.join(OUT, "CROSS_SENSOR_CANDIDATE_AUDIT.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- ranking (item 30) ----------------------------------------------
    def score(r):
        return (int(r["has_explicit_invalid_state"])
                + int(r["invalid_becomes_no_update"])
                + int(r["one_gate_both_roles"])
                + int(bool(r["health_fields_surviving_value_loss"])))

    ranked = sorted(rows, key=lambda r: (-score(r), r["family"]))
    ranking = [{
        "rank": i + 1, "family": r["family"], "criteria_met": score(r),
        "candidate": r["candidate_for_split"],
        "blocker": ("none" if r["candidate_for_split"] else
                    "; ".join(filter(None, [
                        None if r["has_explicit_invalid_state"]
                        else "no explicit INVALID state in any adapter",
                        None if r["invalid_becomes_no_update"]
                        else "nothing to become a no-update",
                        None if r["one_gate_both_roles"]
                        else "no operational consumer reads it, so there is "
                             "no A to separate D from",
                        None if r["health_fields_surviving_value_loss"]
                        else "no health field survives value loss, so T3 "
                             "says the split provably cannot help",
                    ]))),
    } for i, r in enumerate(ranked)]

    payload = {
        "artifact": "CROSS_SENSOR_CANDIDATE_AUDIT",
        "scope": "SOURCE AUDIT ONLY. No cross-sensor experiment was run and "
                 "no generalisation is claimed.",
        "criteria": [
            "an explicit INVALID state the source can report",
            "a path by which invalid becomes no-update downstream",
            "one gate controlling both operational and diagnostic use",
            "a health field that stays meaningful once the value is "
            "inadmissible (T3's necessary condition)",
        ],
        "ranking": ranking,
        "candidates": [r["family"] for r in rows if r["candidate_for_split"]],
        "next_two_modalities": [r["family"] for r in ranked
                                if r["candidate_for_split"]][:2],
        "rows": rows,
    }
    with open(os.path.join(OUT, "CROSS_SENSOR_RANKING.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("CROSS-SENSOR CANDIDATE AUDIT (source only)")
    for r in ranking:
        print(f"  {r['rank']}. {r['family']:<24} {r['criteria_met']}/4  "
              f"candidate={r['candidate']}")
        if not r["candidate"]:
            print(f"       blocked: {r['blocker']}")
    print(f"\n  candidates: {payload['candidates']}")
    print(f"  -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
