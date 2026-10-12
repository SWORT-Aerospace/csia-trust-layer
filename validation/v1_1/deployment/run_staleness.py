"""Phase 4.5 Gate B: reproduce the staleness defect, then measure the fix.

ORDER OF OPERATIONS, and §4 makes it a rule:

  1. REPRODUCE the defect against the UNCHANGED deployment constructor.
  2. Only then derive the canonical timeout rule and measure the fix.
  3. Measure BOTH controls for every node (§7): a NOMINAL-RATE control for
     false-stale exposure, and a HARD-DROPOUT control for detection latency.
     A timeout relaxation that fixed the first by destroying the second would
     be worse than the defect.

EVIDENCE TIERS, labelled rather than blurred (§4):

  REAL_PX4_ULOG_TIMING
      Inter-arrival measured from real PX4 SITL flight logs. Real data, real
      timing -- but the ULog/uORB transport, NOT the MAVLink transport the
      shadow path consumes. It bounds nothing about MAVLink stream rates and
      is not offered as if it did.

  SYNTHETIC_DEPLOYMENT_REGRESSION
      The real platform adapter and the real `OnlineTrustLayer`, driven by
      synthesised MAVLink messages at the CONTRACT-DECLARED rates. Every
      component on the path is production code; only the wire is synthetic.
      This is tier C of §4 and is labelled as such everywhere it appears.

    python validation/v1_1/deployment/run_staleness.py
"""

from __future__ import annotations

import csv
import glob
import json
import os
import random
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.aircraft.adapters import get_adapter                    # noqa: E402
from csia.runtime.failsafe import FailsafePolicy                  # noqa: E402
from csia.runtime.online import STALE_TIMEOUT_S, OnlineTrustLayer  # noqa: E402
from csia.v1_1.staleness import (build_runtime_stale_timeouts,    # noqa: E402
                                 explain, required_channels)

TICK_HZ = 25.0
DURATION_S = 30.0
DROP_AT_S = 15.0
JITTER_FRACTION = 0.30          # +/-30% of the nominal period
SEED = 20260902                 # fixed, so the jitter arm reproduces

CONDITIONS = ("NOMINAL_RATE", "RATE_JITTER", "ONE_MISSED_MESSAGE",
              "SUSTAINED_DROPOUT")
NODES = ("imu0", "imu1", "baro", "mag", "gps", "motor_esc", "battery",
         "vibration")


class Msg:
    """Attribute-style MAVLink message, as pymavlink delivers it."""

    def __init__(self, type_, **fields):
        self._type = type_
        for k, v in fields.items():
            setattr(self, k, v)

    def get_type(self):
        return self._type


# ---------------------------------------------------------------------------
# One synthetic stream per message type, at the rate the CONTRACT declares for
# the channels it carries. Where one message carries several channels the
# stream runs at the fastest declared rate among them, because it is one
# stream on the wire -- which is itself a finding: see `mag` below.
# ---------------------------------------------------------------------------
def _imu_ardupilot(i, t):
    return Msg("SCALED_IMU", time_boot_ms=int(t * 1000),
               xacc=137, yacc=-241, zacc=-993,
               xgyro=53, ygyro=-27, zgyro=11,
               xmag=421, ymag=-133, zmag=377)


def _imu_px4(i, t):
    return Msg("HIGHRES_IMU", time_usec=int(t * 1e6), fields_updated=None,
               xacc=1.34, yacc=-2.36, zacc=-9.74,
               xgyro=0.053, ygyro=-0.027, zgyro=0.011,
               xmag=0.0421, ymag=-0.0133, zmag=0.0377)


def _imu1(i, t):
    return Msg("SCALED_IMU2", time_boot_ms=int(t * 1000),
               xacc=141, yacc=-238, zacc=-991,
               xgyro=49, ygyro=-31, zgyro=14, xmag=0, ymag=0, zmag=0)


def _baro(i, t):
    return Msg("SCALED_PRESSURE", time_boot_ms=int(t * 1000),
               press_abs=978.31 + 0.01 * i, press_diff=0.0, temperature=2317)


def _gps(i, t):
    return Msg("GPS_RAW_INT", time_usec=int(t * 1e6), fix_type=3,
               lat=473_977_419 + i, lon=85_455_936, alt=488_231,
               eph=121, epv=178, vel=643, cog=13_742, satellites_visible=11)


def _battery(i, t):
    return Msg("BATTERY_STATUS", time_boot_ms=int(t * 1000),
               voltages=[3821, 3817, 3833, 3809] + [65535] * 6,
               current_battery=1731 + (i % 3), battery_remaining=76)


def _esc(i, t):
    return Msg("ESC_STATUS", time_usec=int(t * 1e6), index=0,
               rpm=[5210 + i, 5188, 5231, 5199],
               voltage=[15.8] * 4, current=[9.1, 9.3, 8.9, 9.2])


def _vibration(i, t):
    return Msg("VIBRATION", time_usec=int(t * 1e6),
               vibration_x=3.17, vibration_y=2.84, vibration_z=4.02,
               clipping_0=0, clipping_1=0, clipping_2=0)


def _heartbeat(i, t):
    return Msg("HEARTBEAT", type=2, base_mode=128 | 64, custom_mode=5,
               autopilot=3, system_status=4)


def streams(platform: str) -> dict:
    """`{stream: (rate_hz, builder, nodes_fed)}` at declared contract rates."""
    imu = _imu_px4 if platform == "px4" else _imu_ardupilot
    imu_rate = 50.0 if platform == "px4" else 25.0
    esc_rate = 1.0 if platform == "px4" else 10.0
    return {
        # `mag` rides the imu0 message on BOTH platforms: SCALED_IMU carries
        # xmag/ymag/zmag on ArduPilot and HIGHRES_IMU does on PX4. The
        # contract declares mag.field_ut at 25/14 Hz, but it is not an
        # independent stream and cannot arrive at its own rate.
        "imu0": (imu_rate, imu, ("imu0", "mag")),
        "imu1": (25.0, _imu1, ("imu1",)),
        "baro": (10.0, _baro, ("baro",)),
        "gps": (5.0, _gps, ("gps",)),
        "battery": (10.0, _battery, ("battery",)),
        "esc": (esc_rate, _esc, ("motor_esc",)),
        "vibration": (10.0, _vibration, ("vibration",)),
        "heartbeat": (1.0, _heartbeat, ()),
    }


def _stream_of(platform: str, node: str) -> str:
    for name, (_r, _b, nodes) in streams(platform).items():
        if node in nodes:
            return name
    raise KeyError(node)


def admissibility(platform: str) -> dict:
    """`{node: (admissible, [blocking channel:quality])}`.

    THE FINDING THAT REORDERS THIS WHOLE GATE. A node reaches the frozen core
    only if every required channel is `usable`, and usability is decided by
    the QUALIFICATION contract before any watchdog is consulted. A node whose
    channels are not admissible never arrives at all, so its staleness is not
    a staleness question and must not be reported as one.
    """
    from csia.aircraft.qualification import default_contract
    contract = default_contract(platform)
    out = {}
    for node in NODES:
        blocking = []
        for ch in required_channels(node):
            quality, may, _reason, _ = contract.effective(ch)
            if not may:
                blocking.append(f"{ch}:{quality.value}")
        out[node] = (not blocking, blocking)
    return out


# ---------------------------------------------------------------------------
def _schedule(platform, condition, target_stream, rng):
    """`[(t, stream, index)]` for the whole run, sorted by time."""
    events = []
    for name, (rate, _b, _n) in streams(platform).items():
        period = 1.0 / rate
        t, i = period, 0
        targeted = (name == target_stream)
        missed = False
        while t <= DURATION_S:
            emit_t = t
            if condition == "RATE_JITTER":
                emit_t = t + rng.uniform(-JITTER_FRACTION * period,
                                         JITTER_FRACTION * period)
            drop = False
            if targeted and condition == "SUSTAINED_DROPOUT" and t >= DROP_AT_S:
                drop = True
            if (targeted and condition == "ONE_MISSED_MESSAGE"
                    and not missed and t >= DROP_AT_S):
                drop, missed = True, True
            if not drop:
                events.append((max(emit_t, 1e-6), name, i))
            t += period
            i += 1
    events.sort()
    return events


def replay(platform, timeouts, condition, target_node):
    """Run the REAL adapter and the REAL layer. Returns per-tick rows."""
    rng = random.Random(SEED)
    target_stream = _stream_of(platform, target_node)
    adapter = get_adapter(platform)
    layer = OnlineTrustLayer(tick_hz=TICK_HZ, field_mode=True,
                             stale_timeout_s=timeouts)
    policy = FailsafePolicy()
    build = {n: b for n, (_r, b, _x) in streams(platform).items()}

    events = _schedule(platform, condition, target_stream, rng)
    rows, ei = [], 0
    dt = 1.0 / TICK_HZ
    tick = dt
    last_arrival = {}
    while tick <= DURATION_S:
        while ei < len(events) and events[ei][0] <= tick:
            t_e, name, i = events[ei]
            adapter.ingest(build[name](i, t_e))
            for n in streams(platform)[name][2]:
                last_arrival[n] = t_e
            ei += 1
        sample = adapter.sample(t_mono=tick)
        for sensor, t_s, chans in adapter.to_core_samples(sample):
            layer.ingest(sensor, t_s, chans)
        layer.flush(tick)
        row = {"t": round(tick, 4)}
        for n in NODES:
            slot = layer.slots[n]
            row[n] = bool(slot.valid and slot.seen
                          and (tick - slot.last_t) <= layer._stale[n])
        row["_last_arrival"] = last_arrival.get(target_node)
        rows.append(row)
        tick += dt
    del policy
    return rows


# ---------------------------------------------------------------------------
def _metrics(rows, node, condition):
    """False-stale exposure, dropout latency, recovery latency."""
    nominal = [r for r in rows if r["t"] < DROP_AT_S and r["t"] >= 2.0]
    false_stale = sum(1 for r in nominal if not r[node])
    out = {
        "nominal_ticks": len(nominal),
        "nominal_false_stale_ticks": false_stale,
        "nominal_false_stale_fraction": (round(false_stale / len(nominal), 4)
                                         if nominal else None),
        "dropout_stale_latency_s": None,
        "recovery_latency_s": None,
    }
    if condition in ("SUSTAINED_DROPOUT", "ONE_MISSED_MESSAGE"):
        after = [r for r in rows if r["t"] >= DROP_AT_S]
        first_stale = next((r["t"] for r in after if not r[node]), None)
        if first_stale is not None:
            out["dropout_stale_latency_s"] = round(first_stale - DROP_AT_S, 4)
            back = next((r["t"] for r in after
                         if r["t"] > first_stale and r[node]), None)
            if back is not None:
                out["recovery_latency_s"] = round(back - first_stale, 4)
    return out


# ---------------------------------------------------------------------------
def _ulog_rates():
    """REAL_PX4_ULOG_TIMING. Returns [] if no log is reachable."""
    pats = [os.path.join(ROOT, "**", "*.ulg"),
            "/tmp/claude-*/**/px4_probe_*/log/*/*.ulg"]
    files = []
    for p in pats:
        files.extend(sorted(glob.glob(p, recursive=True)))
    if not files:
        return []
    try:
        from pyulog import ULog
    except Exception:
        return []
    rows = []
    for path in files[:3]:
        try:
            u = ULog(path)
        except Exception:
            continue
        for d in u.data_list:
            t = np.asarray(d.data["timestamp"], dtype=float) / 1e6
            if len(t) < 4:
                continue
            gaps = np.diff(t)
            rows.append({
                "log": os.path.basename(path), "topic": d.name,
                "multi_id": d.multi_id, "samples": len(t),
                "span_s": round(float(t[-1] - t[0]), 3),
                "mean_rate_hz": round(float(1.0 / gaps.mean()), 3),
                "median_gap_s": round(float(np.median(gaps)), 5),
                "p99_gap_s": round(float(np.percentile(gaps, 99)), 5),
                "max_gap_s": round(float(gaps.max()), 5),
            })
    return rows


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    frozen = dict(STALE_TIMEOUT_S)
    derived = {p: build_runtime_stale_timeouts(p)
               for p in ("ardupilot", "px4")}

    # ---- 1. the pre-fix reproduction, PX4 motor_esc ---------------------
    pre = replay("px4", frozen, "NOMINAL_RATE", "motor_esc")
    post = replay("px4", derived["px4"], "NOMINAL_RATE", "motor_esc")

    from csia.aircraft.qualification import default_contract
    _c = default_contract("px4")
    _q = {ch: _c.effective(ch) for ch in ("esc.rpm", "esc.current")}

    def _esc_rows(rows, label):
        out = []
        for r in rows:
            out.append({
                "arm": label, "t_s": r["t"],
                "last_esc_status_arrival_s": r["_last_arrival"],
                "age_s": (None if r["_last_arrival"] is None
                          else round(r["t"] - r["_last_arrival"], 4)),
                "stale_timeout_s": (frozen["motor_esc"] if label == "PRE_FIX"
                                    else derived["px4"]["motor_esc"]),
                "motor_esc_reached_core": r["motor_esc"],
                # WHY the column above is False in BOTH arms. The node is
                # withheld by qualification before any watchdog runs, so the
                # timeout is not what is stopping it.
                "esc_rpm_admissible": _q["esc.rpm"][1],
                "esc_rpm_quality": _q["esc.rpm"][0].value,
                "esc_current_admissible": _q["esc.current"][1],
                "esc_current_quality": _q["esc.current"][0].value,
            })
        return out

    _write_csv(os.path.join(_HERE, "PX4_MOTOR_ESC_STALENESS_PRE_FIX.csv"),
               _esc_rows(pre, "PRE_FIX"))
    _write_csv(os.path.join(_HERE, "PX4_MOTOR_ESC_STALENESS_POST_FIX.csv"),
               _esc_rows(post, "POST_FIX"))

    pre_m = _metrics(pre, "motor_esc", "NOMINAL_RATE")
    post_m = _metrics(post, "motor_esc", "NOMINAL_RATE")

    # ---- 2. the full matrix: 8 nodes x 4 conditions x 2 platforms -------
    matrix = []
    adm = {p: admissibility(p) for p in ("ardupilot", "px4")}
    for platform in ("ardupilot", "px4"):
        for node in NODES:
            ok, blocking = adm[platform][node]
            for condition in CONDITIONS:
                for arm, tmo in (("FROZEN_DEFAULT", frozen),
                                 ("DERIVED_RULE", derived[platform])):
                    base = {
                        "platform": platform, "node": node,
                        "condition": condition, "arm": arm,
                        "admissible": ok,
                        "blocked_by": "|".join(blocking),
                        "stale_timeout_s": round(float(tmo[node]), 6),
                        "stream": _stream_of(platform, node),
                        "declared_stream_rate_hz":
                            streams(platform)[_stream_of(platform, node)][0],
                    }
                    if not ok:
                        # NOT a staleness measurement. The node never reaches
                        # the core, so reporting a false-stale fraction here
                        # would blame the watchdog for a qualification
                        # decision taken one layer earlier.
                        matrix.append({**base, "nominal_ticks": 0,
                                       "nominal_false_stale_ticks": None,
                                       "nominal_false_stale_fraction": None,
                                       "dropout_stale_latency_s": None,
                                       "recovery_latency_s": None})
                        continue
                    rows = replay(platform, tmo, condition, node)
                    matrix.append({**base,
                                   **_metrics(rows, node, condition)})
    _write_csv(os.path.join(_HERE, "STALENESS_MATRIX.csv"), matrix)

    # ---- 3. real PX4 log timing, clearly a different transport ----------
    ulog = _ulog_rates()
    _write_csv(os.path.join(_HERE, "PX4_ULOG_TOPIC_RATES.csv"), ulog)

    # ---- 4. summary + gates ---------------------------------------------
    def _sel(**kw):
        return [r for r in matrix
                if all(r[k] == v for k, v in kw.items())]

    worst_false, worst_latency, exposed = {}, {}, {}
    for arm in ("FROZEN_DEFAULT", "DERIVED_RULE"):
        for cond in ("NOMINAL_RATE", "RATE_JITTER"):
            rows = [r for r in _sel(arm=arm, condition=cond)
                    if r["admissible"]]
            worst_false[f"{arm}/{cond}"] = max(
                (r["nominal_false_stale_fraction"], r["platform"], r["node"])
                for r in rows)
            exposed[f"{arm}/{cond}"] = sorted(
                f"{r['platform']}/{r['node']}={r['nominal_false_stale_fraction']}"
                for r in rows if r["nominal_false_stale_fraction"] > 0.0)
        drows = [r for r in _sel(arm=arm, condition="SUSTAINED_DROPOUT")
                 if r["admissible"] and r["dropout_stale_latency_s"] is not None]
        worst_latency[arm] = max((r["dropout_stale_latency_s"], r["platform"],
                                  r["node"]) for r in drows)

    def _clean(cond):
        return all(r["nominal_false_stale_fraction"] == 0.0
                   for r in _sel(arm="DERIVED_RULE", condition=cond)
                   if r["admissible"])

    nominal_clean = _clean("NOMINAL_RATE")
    jitter_clean = _clean("RATE_JITTER")
    dropout_ok = all(
        r["dropout_stale_latency_s"] is not None
        for r in _sel(arm="DERIVED_RULE", condition="SUSTAINED_DROPOUT")
        if r["admissible"])

    summary = {
        "artifact": "STALENESS_REGRESSION_SUMMARY",
        "generation_command":
            "python validation/v1_1/deployment/run_staleness.py",
        "csia_sha": _git("rev-parse", "HEAD"),
        "evidence_tier": {
            "matrix": "SYNTHETIC_DEPLOYMENT_REGRESSION",
            "ulog_rates": ("REAL_PX4_ULOG_TIMING" if ulog
                           else "UNAVAILABLE"),
        },
        "tick_hz": TICK_HZ, "duration_s": DURATION_S,
        "drop_at_s": DROP_AT_S, "jitter_fraction": JITTER_FRACTION,
        "seed": SEED,
        "frozen_stale_timeout_s": frozen,
        "derived_stale_timeout_s": derived,
        "derivation": {p: explain(p) for p in ("ardupilot", "px4")},
        "px4_motor_esc": {
            "pre_fix": pre_m, "post_fix": post_m,
            "pre_fix_timeout_s": frozen["motor_esc"],
            "post_fix_timeout_s": derived["px4"]["motor_esc"],
            "declared_esc_status_rate_hz": 1.0,
        },
        "admissibility": {p: {n: {"admissible": v[0], "blocked_by": v[1]}
                              for n, v in adm[p].items()}
                          for p in adm},
        "nodes_exposed_to_false_stale": exposed,
        "worst_nominal_false_stale": {
            k: {"fraction": v[0], "platform": v[1], "node": v[2]}
            for k, v in worst_false.items()},
        "worst_sustained_dropout_latency_s": {
            k: {"latency_s": v[0], "platform": v[1], "node": v[2]}
            for k, v in worst_latency.items()},
        "gate_B_nominal_rate_pass": bool(nominal_clean),
        "gate_B_jitter_pass": bool(jitter_clean),
        "gate_C_hard_dropout_pass": bool(dropout_ok),
        "ulog_rows": len(ulog),
    }
    with open(os.path.join(_HERE, "STALENESS_REGRESSION_SUMMARY.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("PX4 motor_esc  PRE-FIX false-stale fraction: "
          f"{pre_m['nominal_false_stale_fraction']}  "
          f"(timeout {frozen['motor_esc']} s)")
    print("PX4 motor_esc POST-FIX false-stale fraction: "
          f"{post_m['nominal_false_stale_fraction']}  "
          f"(timeout {derived['px4']['motor_esc']} s)")
    for k in sorted(worst_false):
        print(f"  worst false-stale {k:28s} {worst_false[k]}")
    for k in sorted(exposed):
        print(f"  exposed {k:28s} {exposed[k]}")
    print(f"worst dropout latency      FROZEN={worst_latency['FROZEN_DEFAULT']} "
          f"DERIVED={worst_latency['DERIVED_RULE']}")
    print(f"gates: nominal={nominal_clean} jitter={jitter_clean} "
          f"dropout={dropout_ok}  ulog_rows={len(ulog)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
