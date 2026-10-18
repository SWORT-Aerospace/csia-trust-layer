"""Does suppressing the proven-stub channel restore R10 on the modern rig?

P0.5 established that ESC_TELEMETRY_1_TO_4 carries no information on
ArduCopter 4.8 SITL: `current` is a hard-coded 0.8 A liveness stub
(AP_ESC_Telem_SITL.cpp:72) and `rpm` is identically 0 because SITL derives
motor rpm from SIM_VIB_MOT_MAX, which defaults to 0.0 (SIM_Frame.cpp:901,
SITL.cpp:512).

That is an attribution, not yet a proof. RULE B says a mechanism is not
attributed until the intermediate is observed; this goes one step further and
INTERVENES on it. Three arms, identical in every other respect:

  A  baseline            the modern rig as flown in E1
  B  esc_suppressed      ESC_TELEMETRY_1_TO_4 dropped at ingestion, which
                         restores the LEGACY information architecture: the
                         motor_esc node returns to unavailable, exactly as it
                         was on ArduCopter 3.3
  C  battery_suppressed  BATTERY_STATUS dropped instead. The null control for
                         arm B: if dropping EITHER channel silences the alarm,
                         B proves nothing about which one is at fault, because
                         power_thrust needs both nodes fresh. B and C are
                         expected to behave the same on this edge, so the
                         DISCRIMINATOR is what else changes — C also removes
                         the genuine phys_battery channel.

WHAT THIS IS NOT. It is not a repair and not a proposed one. No threshold is
moved, no production file is touched, and the suppression is a research-only
shim in this file. R10's budget stays at zero.

Run:  PYTHONPATH=. python research/phase2/r10_attribution.py
Out:  research/phase2/results/r10_attribution.json
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.phase2.modern_rig import (                        # noqa: E402
    AP_BIN, Shim, connect, launch, new_state, pilot)

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
FLIGHT_S = 150.0


def fly(label, suppress, speedup, workdir):
    """`suppress` is a set of MAVLink message names dropped at ingestion."""
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink

    rec = {"label": label, "suppressed_messages": sorted(suppress),
           "transitions": [], "troughs": {}}
    proc = launch(workdir, speedup)
    try:
        time.sleep(6.0)
        m = connect()
        st = new_state()
        layer = OnlineTrustLayer(field_mode=True,
                                 stale_timeout_s={"vibration": 2.0})
        policy = FailsafePolicy(FailsafeConfig(arm_time=20.0))
        ctx = {"t0": None}
        seen_tr = 0
        low = {}
        fresh_seen = {}
        deadline = time.time() + (FLIGHT_S / speedup) * 4 + 180

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            if msg.get_type() in suppress:
                st["t"] = ctx.get("t_last", 0.0)
                pilot(m, st, mavutil)
                if st["t"] >= FLIGHT_S:
                    break
                continue

            for sensor, t, ch in map_mavlink(Shim(msg), ctx):
                for state in layer.ingest(sensor, t, ch):
                    policy.update(state)
                    for tr in policy.transitions[seen_tr:]:
                        rec["transitions"].append(
                            {"t": round(tr.t, 2), "level": tr.level.name,
                             "reasons": list(tr.reasons)})
                    seen_tr = len(policy.transitions)
                    if not state.armed:
                        continue
                    for n, v in state.trust.items():
                        low[f"trust_{n}"] = min(low.get(f"trust_{n}", 1.0), v)
                    for n, v in state.fresh.items():
                        fresh_seen[n] = fresh_seen.get(n, 0) + int(bool(v))
                    for key in ("power_thrust", "accel_motor_current",
                                "accel_esc_rpm", "vibration_prop_freq"):
                        e = state.edges.get(key)
                        if e and e[0] is not None:
                            low[f"edge_{key}"] = min(
                                low.get(f"edge_{key}", 1.0), float(e[0]))
                            low[f"gate_{key}"] = min(
                                low.get(f"gate_{key}", 1.0), float(e[1]))
            st["t"] = ctx.get("t_last", 0.0)
            pilot(m, st, mavutil)
            if st["t"] >= FLIGHT_S:
                break

        rec["troughs"] = {k: round(v, 6) for k, v in sorted(low.items())}
        rec["armed_ticks_with_fresh_sensor"] = fresh_seen
        rec["flight_time_s"] = round(st["t"], 2)
        rec["failsafe_transitions_out_of_normal"] = sum(
            1 for t in rec["transitions"] if t["level"] != "NORMAL")
        rec["R10_satisfied"] = rec["failsafe_transitions_out_of_normal"] == 0
        return rec
    except Exception as exc:                                   # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["R10_satisfied"] = None
        return rec
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "r10_attribution.json")
    if not (os.path.isfile(AP_BIN) and os.access(AP_BIN, os.X_OK)):
        json.dump({"status": "MODERN_TARGET_UNAVAILABLE"}, open(out, "w"))
        print("MODERN_TARGET_UNAVAILABLE")
        return 0

    arms = [("A_baseline", set()),
            ("B_esc_suppressed", {"ESC_TELEMETRY_1_TO_4"}),
            ("C_battery_suppressed", {"BATTERY_STATUS"})]
    rows = []
    for label, sup in arms:
        print(f"  {label:22s} suppress={sorted(sup) or '-'} ...", flush=True)
        r = fly(label, sup, 20, os.path.join(RESULTS, "_wd_r10attr"))
        rows.append(r)
        print(f"      transitions={r.get('failsafe_transitions_out_of_normal')}"
              f"  R10={r.get('R10_satisfied')}")
        for t in r["transitions"]:
            print(f"        {t['t']:7.2f}s {t['level']:9s} {t['reasons']}")
        tr = r.get("troughs", {})
        print(f"      trust troughs: batt={tr.get('trust_battery')} "
              f"motor={tr.get('trust_motor_esc')} vib={tr.get('trust_vibration')} "
              f"gps={tr.get('trust_gps')}")

    base = next(r for r in rows if r["label"] == "A_baseline")
    esc = next(r for r in rows if r["label"] == "B_esc_suppressed")
    batt = next(r for r in rows if r["label"] == "C_battery_suppressed")

    report = {
        "question": "is the modern R10 breach fully attributable to the "
                    "ESC telemetry stub?",
        "intervention": "drop one MAVLink message at ingestion; change "
                        "nothing else. No production file is modified and no "
                        "threshold is moved.",
        "arms": rows,
        "result": {
            "baseline_transitions": base.get(
                "failsafe_transitions_out_of_normal"),
            "esc_suppressed_transitions": esc.get(
                "failsafe_transitions_out_of_normal"),
            "battery_suppressed_transitions": batt.get(
                "failsafe_transitions_out_of_normal"),
            "suppressing_the_stub_restores_R10": esc.get("R10_satisfied"),
            "interpretation": (
                "arm B restores the LEGACY information architecture: the "
                "motor_esc node returns to unavailable, which is what it was "
                "on ArduCopter 3.3. If R10 holds in B and fails in A, the "
                "breach is caused by the arrival of a channel that carries no "
                "information, not by any change in CSIA or in the vehicle."),
        },
        "what_this_does_not_license": (
            "It does not license suppressing the channel in production. On "
            "real hardware ESC telemetry may carry genuine current, and the "
            "power_thrust relation has never been tested against data that "
            "could falsify it. Suppression here is an EXPERIMENTAL CONTROL "
            "used to configure a scientifically scoreable rig, and it is "
            "recorded as such."),
        "R10_budget_unchanged": 0,
    }
    json.dump(report, open(out, "w"), indent=1, sort_keys=True)
    print(f"\n  A baseline           {base.get('failsafe_transitions_out_of_normal')}")
    print(f"  B esc suppressed     {esc.get('failsafe_transitions_out_of_normal')}"
          f"   R10={esc.get('R10_satisfied')}")
    print(f"  C battery suppressed {batt.get('failsafe_transitions_out_of_normal')}"
          f"   R10={batt.get('R10_satisfied')}")
    print(f"wrote {os.path.relpath(out, os.path.join(HERE, '..', '..'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
