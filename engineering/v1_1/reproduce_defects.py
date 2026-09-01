"""Reproduce the known ingest defects, before and after the v1.1 fixes.

Item 4: *"Reproduce every defect BEFORE fixing it. Freeze pre-fix fixtures and
hashes."* This script is the reproduction. It is run once against unmodified
v1 ingestion to produce `KNOWN_DEFECTS_PRE_FIX.json`, and again after the
fixes to produce `KNOWN_DEFECTS_POST_FIX.json`.

It asserts nothing about which behaviour is correct. It records what each
ingest path *does* with one raw producer condition, hashes the record, and
leaves the judgement to the specs. That ordering is the point: a defect that
was never reproduced cannot be shown to have been fixed.

    python engineering/v1_1/reproduce_defects.py --out pre
    python engineering/v1_1/reproduce_defects.py --out post

Nothing here touches the frozen v1 core.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, ROOT)

import numpy as np                                            # noqa: E402

from csia.aircraft.adapters.ardupilot import ArduPilotAdapter  # noqa: E402
from csia.runtime.plugins import map_mavlink                   # noqa: E402
from csia.runtime.ulog_source import UlogSource                # noqa: E402


class Msg:
    """Minimal pymavlink-shaped message. `get_type()` plus attributes."""

    def __init__(self, type_name, **fields):
        self._t = type_name
        self.__dict__.update(fields)

    def get_type(self):
        return self._t


def _clock():
    """Deterministic monotonic clock: one tick per call, 20 ms apart."""
    _clock.t += 0.02
    return _clock.t


_clock.t = 0.0


def _fresh_adapter():
    _clock.t = 0.0
    return ArduPilotAdapter(clock=_clock)


def _cv(sample, group, channel):
    """Pull a ChannelValue out of an AircraftSample, as a plain dict.

    Groups are dicts keyed by the FULL channel name (`csia/aircraft/sample.py`
    :126-149), not attribute objects. Getting that wrong reports every channel
    as absent, which on this script would have made all five defects look
    identical and already fixed.
    """
    grp = getattr(sample, group, None)
    if not isinstance(grp, dict):
        return {"present": False, "note": f"group {group} absent"}
    cv = grp.get(channel)
    if cv is None:
        return {"present": False, "note": f"channel {channel} not in group",
                "group_keys": sorted(grp)}
    val = getattr(cv, "value", None)
    if isinstance(val, np.ndarray):
        val = [round(float(x), 6) for x in val.tolist()]
    elif isinstance(val, (int, float)):
        val = round(float(val), 6)
    reason = getattr(cv, "missing", None)
    return {
        "present": val is not None,
        "value": val,
        "missing_reason": (reason.name if hasattr(reason, "name")
                           else str(reason) if reason is not None else None),
        "quality": getattr(getattr(cv, "quality", None), "name", None),
        "note": getattr(cv, "note", ""),
    }


# ---------------------------------------------------------------- D1
def d1_battery_sentinel_ardupilot():
    """BATTERY_STATUS current_battery = -1 after a real reading.

    MAVLink common.xml declares invalid="-1" on this field: the producer is
    saying "not measured", not "zero amps". The question is what the adapter
    reports for battery.current on the tick after the sentinel arrives.
    """
    a = _fresh_adapter()
    a.ingest(Msg("BATTERY_STATUS", voltages=[4000, 4000, 4000] + [65535] * 7,
                 current_battery=500, time_boot_ms=0))     # 5.00 A, real
    a.ingest(Msg("BATTERY_STATUS", voltages=[4000, 4000, 4000] + [65535] * 7,
                 current_battery=-1, time_boot_ms=20))     # not measured
    s = a.sample()
    return {
        "raw_condition": "current_battery = -1 (documented not-measured "
                         "sentinel) arriving 20 ms after a real 5.00 A reading",
        "observed": _cv(s, "battery", "battery.current"),
        "sentinel_counts": a.sentinel_counts(),
    }


# ---------------------------------------------------------------- D2
def d2_mag_all_zero_ardupilot():
    """RAW_IMU with an all-zero magnetometer triple after a real field.

    A real magnetometer never reads exactly zero on all three axes; the
    adapter's own comment says so. The question is what happens to
    mag.field_ut when the all-zero triple arrives.
    """
    a = _fresh_adapter()
    a.ingest(Msg("RAW_IMU", xacc=0, yacc=0, zacc=-1000, xgyro=0, ygyro=0,
                 zgyro=0, xmag=200, ymag=100, zmag=400, time_usec=0))
    a.ingest(Msg("RAW_IMU", xacc=0, yacc=0, zacc=-1000, xgyro=0, ygyro=0,
                 zgyro=0, xmag=0, ymag=0, zmag=0, time_usec=20000))
    s = a.sample()
    return {
        "raw_condition": "all-zero magnetometer triple arriving 20 ms after a "
                         "real field reading",
        "observed": _cv(s, "magnetometer", "mag.field_ut"),
        "sentinel_counts": a.sentinel_counts(),
    }


# ---------------------------------------------------------------- D3
def d3_ulog_battery_current():
    """PX4 ULog battery_status.current_a == -1.

    The measured PX4 log in this repository carries 216 battery samples, all
    with current_a == -1.0. The question is whether the ULog path emits that
    as a valid physical current.
    """
    src = object.__new__(UlogSource)
    src.ulog = None
    src.include_esc = False
    src.path = "<synthetic>"

    class _T:
        def __init__(self, data):
            self.data = data

    n = 200
    t_us = (np.arange(n, dtype=np.uint64) * 4000)          # 250 Hz
    topics = {
        # _build_events needs sensor_combined to establish t0; the IMU content
        # is irrelevant to this case and is nominal.
        "sensor_combined": _T({
            "timestamp": t_us,
            "accelerometer_m_s2[0]": np.zeros(n),
            "accelerometer_m_s2[1]": np.zeros(n),
            "accelerometer_m_s2[2]": np.full(n, -9.80665),
            "gyro_rad[0]": np.zeros(n),
            "gyro_rad[1]": np.zeros(n),
            "gyro_rad[2]": np.zeros(n),
        }),
        "battery_status": _T({
            "timestamp": np.array([0, 20000, 40000], dtype=np.uint64),
            "voltage_v": np.array([12.0, 12.0, 12.0]),
            "current_a": np.array([-1.0, -1.0, -1.0]),
        }),
    }
    src._topic = lambda name, instance=None: (
        topics.get(name) if instance in (None, 0) else None)
    ev = src._build_events()
    bat = [e for e in ev if e[1] == "battery"]
    return {
        "raw_condition": "battery_status.current_a == -1.0 for every sample, "
                         "as in the repository's measured PX4 log",
        "event_count": len(bat),
        "first_event": (None if not bat else
                        {k: (round(float(v), 6)
                             if isinstance(v, (int, float)) else v)
                         for k, v in sorted(bat[0][2].items())}),
    }


# ---------------------------------------------------------------- D4
def d4_plugins_battery_current():
    """The plugins decode path on the same -1 sentinel."""
    msg = Msg("BATTERY_STATUS", voltages=[4000, 4000, 4000] + [65535] * 7,
              current_battery=-1, time_boot_ms=1000)
    out = map_mavlink(msg, {})
    bat = [o for o in (out or []) if o[0] == "battery"]
    return {
        "raw_condition": "BATTERY_STATUS.current_battery == -1",
        "event_count": len(bat),
        "first_event": (None if not bat else
                        {k: (round(float(v), 6)
                             if isinstance(v, (int, float)) else v)
                         for k, v in sorted(bat[0][2].items())}),
    }


# ---------------------------------------------------------------- D5
def d5_gnss_no_fix_ardupilot():
    """GPS_RAW_INT with fix_type < 3 after a 3D fix.

    Included as a CONTROL, not as a suspected defect: the v1 adapter already
    pops the retained position and records NO_3D_FIX. If this row changes
    between pre-fix and post-fix, the v1.1 edit broke something that worked.
    """
    a = _fresh_adapter()
    a.ingest(Msg("GPS_RAW_INT", fix_type=3, lat=473000000, lon=85000000,
                 alt=500000, vel=0, cog=0, time_usec=0))
    a.ingest(Msg("GPS_RAW_INT", fix_type=1, lat=473000000, lon=85000000,
                 alt=500000, vel=0, cog=0, time_usec=20000))
    s = a.sample()
    return {
        "raw_condition": "fix_type = 1 arriving 20 ms after a 3D fix",
        "observed": _cv(s, "gnss", "gnss.position"),
        "sentinel_counts": a.sentinel_counts(),
        "role": "CONTROL - already correct in v1; must not change",
    }


CASES = {
    "D1_battery_sentinel_ardupilot": d1_battery_sentinel_ardupilot,
    "D2_mag_all_zero_ardupilot": d2_mag_all_zero_ardupilot,
    "D3_ulog_battery_current": d3_ulog_battery_current,
    "D4_plugins_battery_current": d4_plugins_battery_current,
    "D5_gnss_no_fix_ardupilot": d5_gnss_no_fix_ardupilot,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", choices=("pre", "post"), required=True)
    args = ap.parse_args()

    results = {}
    for name, fn in CASES.items():
        results[name] = fn()

    body = json.dumps(results, indent=2, sort_keys=True)
    doc = {
        "artifact": f"KNOWN_DEFECTS_{args.out.upper()}_FIX",
        "note": "Recorded behaviour of each ingest path on one raw producer "
                "condition. This file states what the code DOES, not what is "
                "correct; CANONICAL_INGEST_SPEC.md states what is correct.",
        "cases": results,
        "sha256_of_cases": hashlib.sha256(body.encode()).hexdigest(),
    }
    path = os.path.join(_HERE, f"KNOWN_DEFECTS_{args.out.upper()}_FIX.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  wrote {os.path.relpath(path, ROOT)}")
    print(f"  sha256(cases) = {doc['sha256_of_cases']}")
    for name in sorted(results):
        r = results[name]
        obs = r.get("observed") or r.get("first_event") or {}
        print(f"    {name:<34} {json.dumps(obs, sort_keys=True)[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
