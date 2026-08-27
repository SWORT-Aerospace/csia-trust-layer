"""Item 24. Cross-platform feasibility: does the PX4 side of the codebase
present the same semantic states, and are they preserved?

Three questions, answered with execution rather than reading:

  1. Does the PX4 adapter present the same canonical states for the shared
     MAVLink messages? -> run the SAME contracts against `PX4Adapter`.
  2. Do the PX4-specific interfaces differ? -> diff the two adapters' handling
     of the states the contracts name.
  3. Are the invalid branches ever exercised by REAL PX4 data? -> read the
     committed 9.6 MB ULog and count.

Nothing is forced into identical semantics (item 24 says not to).

  python research/evidence_semantics/px4_probe.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

import contract_checker as C                                  # noqa: E402
import probe as P                                             # noqa: E402

OUT = os.path.join(_HERE, "results")


def _px4_adapter(clock):
    from csia.aircraft.adapters.px4 import PX4Adapter
    return PX4Adapter(clock=clock)


def install_px4_path():
    """A fourth path: the same probe, driven through `PX4Adapter`.

    Both adapters inherit `base.PlatformAdapter`, so T3/T4/T5 are the same
    code; only the ingest branch differs. That is exactly what makes the
    comparison informative -- any difference found is in the platform
    branch, not in the shared machinery.
    """
    def probe_px4(word, family):
        orig = P._mk_adapter
        P._mk_adapter = _px4_adapter
        try:
            return P.probe_a(word, family)
        finally:
            P._mk_adapter = orig
    P.PATHS["px4_adapter"] = probe_px4
    return probe_px4


def real_ulog():
    hits = sorted(glob.glob(os.path.join(
        ROOT, "research", "v1_1", "results", ".px4_link_probe", "*", "log",
        "*", "*.ulg")))
    return hits[0] if hits else None


def probe_real_log(path):
    """What states does a REAL PX4 log actually contain?"""
    from pyulog import ULog
    u = ULog(path)
    out = {"ulog": os.path.relpath(path, ROOT),
           "size_bytes": os.path.getsize(path)}

    def ds(name):
        try:
            return u.get_dataset(name, 0)
        except (KeyError, IndexError, ValueError):
            return None

    gp = ds("vehicle_gps_position")
    if gp is None:
        out["gnss"] = {"topic": "MISSING"}
    else:
        fix = list(gp.data["fix_type"])
        hist = {}
        for f in fix:
            hist[int(f)] = hist.get(int(f), 0) + 1
        out["gnss"] = {
            "topic": "vehicle_gps_position", "samples": len(fix),
            "fix_type_histogram": dict(sorted(hist.items())),
            "samples_below_3d_fix": sum(1 for f in fix if int(f) < 3),
            "invalid_branch_exercised": any(int(f) < 3 for f in fix)}

    bt = ds("battery_status")
    if bt is None:
        out["battery"] = {"topic": "MISSING"}
    else:
        cur = [float(x) for x in bt.data["current_a"]]
        out["battery"] = {
            "topic": "battery_status", "samples": len(cur),
            "min_current_a": round(min(cur), 4),
            "max_current_a": round(max(cur), 4),
            "negative_samples": sum(1 for x in cur if x < 0),
            "sentinel_encoding": "NONE DEFINED. uORB battery_status.current_a "
                                 "is a float in amps with no documented "
                                 "not-measured value, and ulog_source.py has "
                                 "no branch that could read one "
                                 "(ulog_source.py:196-199 emits valid=True "
                                 "unconditionally)."}
    return out


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    install_px4_path()
    contracts = C.load_contracts()

    results = {}
    for family in ("gnss", "battery"):
        ard = C.check_contract("v1_1_adapter", family, contracts[family])
        px4 = C.check_contract("px4_adapter", family, contracts[family])
        same = {
            "emitted_vocabulary_identical": (
                ard["emitted_state_vocabulary"]
                == px4["emitted_state_vocabulary"]),
            "clause_results_identical": (
                [c["result"] for c in ard["clause_results"]]
                == [c["result"] for c in px4["clause_results"]]),
            "first_collapse_identical": (
                [c["first_collapse_stage"] for c in ard["clause_results"]]
                == [c["first_collapse_stage"] for c in px4["clause_results"]]),
        }
        results[family] = {"ardupilot": ard, "px4": px4,
                           "agreement": same}

    # mag is deliberately NOT run against Px4Adapter: PX4 carries the
    # magnetometer on HIGHRES_IMU with a fields_updated bitmask, which is a
    # DIFFERENT source interface, not the same one under another name.
    mag_note = ("NOT RUN. PX4Adapter reads the magnetometer from HIGHRES_IMU "
                "and gates it on the `fields_updated` bitmask "
                "(csia/aircraft/adapters/px4.py:107-123, FIELD_XMAG). "
                "ArduPilotAdapter reads it from SCALED_IMU with no such "
                "bitmask (ardupilot.py:141-148). Driving the ArduPilot word "
                "alphabet through the PX4 branch would compare two different "
                "interfaces and report the difference as a semantic one. "
                "Item 24 says not to force identical semantics.")

    up = real_ulog()
    real = probe_real_log(up) if up else {
        "ulog": None, "note": "no ULog present in this checkout"}

    payload = {
        "artifact": "PX4_FEASIBILITY",
        "shared_message_families": ["gnss", "battery"],
        "results": results,
        "mag": mag_note,
        "real_log": real,
        "px4_specific_state_not_present_on_ardupilot": {
            "fields_updated_bitmask": "HIGHRES_IMU carries a per-field "
                                      "validity bitmask. This is a genuine "
                                      "extra source state -- 'this message "
                                      "arrived but this field was not "
                                      "updated' -- and PX4Adapter reads it "
                                      "(px4.py:107). ArduPilot's SCALED_IMU "
                                      "has no equivalent.",
            "estimator_status_ratios": "PX4 reports innovation RATIOS where "
                                       "ArduPilot reports variances; the "
                                       "adapter tags the source rather than "
                                       "conflating them (px4.py:196-200). "
                                       "Neither reaches the frozen core.",
        },
    }
    with open(os.path.join(OUT, "PX4_FEASIBILITY.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")

    for family, r in results.items():
        print(f"  {family}: ardupilot vocab "
              f"{r['ardupilot']['emitted_state_vocabulary']} / px4 vocab "
              f"{r['px4']['emitted_state_vocabulary']}  agreement="
              f"{r['agreement']}")
    if "gnss" in real:
        print(f"  real ULog: {real['gnss'].get('samples')} gps samples, "
              f"fix histogram {real['gnss'].get('fix_type_histogram')}, "
              f"invalid branch exercised: "
              f"{real['gnss'].get('invalid_branch_exercised')}")
        print(f"             battery {real['battery'].get('samples')} "
              f"samples, current range "
              f"[{real['battery'].get('min_current_a')}, "
              f"{real['battery'].get('max_current_a')}] A, negative: "
              f"{real['battery'].get('negative_samples')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
