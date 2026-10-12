"""Phase 3.1 campaign — the actionability-precondition study.

Phase 3 asked whether a gate closure changed a decision and found it could
not, because the decisions it could reach never depended on the gated
evidence. Phase 3.1 asks the prior question: **is there any reachable,
physically consistent scenario in which an action conflict is possible at
all**, and in particular one in which the support-aware policy can act.

The same machinery as Phase 3, deliberately: the frozen trust layer, the
frozen failsafe, the frozen fault injector, the same three policies on one
pass, and the same run-length trace format, so Phase 3's already-controlled
independent evaluator reads these traces unchanged.

WHAT IS DIFFERENT
-----------------
Three fault families instead of two, chosen because the reachability
inventory in the amendment shows they reach three different failsafe levels.
And the gating variable is **absent ESC telemetry** rather than a disarmed
vehicle -- armed, airborne, past `arm_time`, and a configuration the frozen
core's own comments contemplate. No disarmed-gate scenario appears here at
all, as a condition or as a control.

**Nothing flew. Nothing was armed but a boolean. Nothing was commanded.**

    python research/consequence/phase31/campaign31.py --partition development
    python research/consequence/phase31/campaign31.py --partition locked \
        --i-am-opening-the-locked-partition
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "consequence", "phase3"))

from campaign import _events, _merge_armed, _rle, DURATION, TICK_HZ  # noqa: E402

from csia.runtime.failsafe import FailsafeConfig, FailsafePolicy  # noqa: E402
from csia.runtime.online import OnlineTrustLayer  # noqa: E402
from csia.sensors import Fault  # noqa: E402

from csia_consequence import action_adapter as aa  # noqa: E402
from csia_consequence import consequence_model31 as cm31  # noqa: E402
from csia_consequence import phase31_partitions as parts  # noqa: E402

TAKEOFF_S = 5.0

#: The sensor whose absence gates the evidence under test. Its absence is a
#: real airframe configuration, not a contrivance: `csia/runtime/online.py`
#: computes every edge as `gate * fresh[a] * fresh[b]`, and both
#: `accel_motor_current` and `accel_esc_rpm` have `motor_esc` as an endpoint,
#: as does the cross-sensor gate on `phys_vibration`.
GATING_SENSOR = "motor_esc"

FAMILIES = {
    "imu_isolation": {
        "faults": [Fault("bias_drift", "imu0", 15.0, 40.0,
                         {"axis": 2, "rate": 0.12, "channel": "accel"})],
        "fault_family": "imu_bias",
        "faulty_source": "imu0",
        "gates_under_test": ("accel_motor_current", "accel_esc_rpm"),
        "reaches": "CAUTION via imu_isolated (SELECT_IMU)",
        "why_here": "the only family that produces an attributing response",
    },
    "power": {
        # battery only, in BOTH conditions. The catalog scenario also sags
        # motor_esc rpm, and including that would have made the gated
        # condition change the FAULT as well as the evidence -- the same
        # confound Phase 3 found in its own condition F.
        "faults": [Fault("power_sag", "battery", 30.0, 20.0,
                         {"depth_v": 1.2})],
        "fault_family": "power_sag",
        "faulty_source": "battery",
        "gates_under_test": ("power_thrust",),
        "reaches": "CRITICAL via power_fault (REDUCE_POWER, LAND_NOW)",
        "why_here": "reaches a stronger level than Phase 3 ever did",
    },
    "structural": {
        "faults": [Fault("vibration_anomaly", "vibration", 28.0, 20.0,
                         {"gain": 3.0})],
        "fault_family": "vibration_anomaly",
        "faulty_source": "vibration",
        "gates_under_test": ("vibration_prop_freq",),
        "reaches": "CRITICAL via structural (LIMIT_THROTTLE, LAND_SOON)",
        "why_here": ("reaches CRITICAL by a different route, and its "
                     "phys_vibration evidence is gated by fresh[motor_esc] "
                     "-- one of the eight Phase-2 candidates"),
    },
}

CONDITIONS = ("N", "EA", "EG")


def run_scenario(*, seed: int, family: str, condition: str) -> dict:
    spec = FAMILIES[family]
    faults = [] if condition == "N" else list(spec["faults"])
    drop = (GATING_SENSOR,) if condition == "EG" else ()

    truth, events = _events(seed, "hover_circle", faults)
    if drop:
        events = [e for e in events if e[1] not in drop]
    merged = _merge_armed(events, [(0.0, True)])

    layer = OnlineTrustLayer(tick_hz=TICK_HZ)
    policies = {"P0": FailsafePolicy(FailsafeConfig()),
                "P1": FailsafePolicy(FailsafeConfig()),
                "P2": FailsafePolicy(FailsafeConfig())}
    rows = {k: [] for k in policies}
    monitored = set()

    def handle(state):
        for n, ok in state.fresh.items():
            if ok:
                monitored.add(n)
        weights = aa.feature_weights(state)
        report = aa.p2_support(state)
        pair = aa.decision_pair_support(state)
        airborne = state.t >= TAKEOFF_S
        for name, policy in policies.items():
            actions = policy.update(state)
            level = int(policy.level)
            if name == "P0":
                d = aa.p0_decide(state, level, actions)
            elif name == "P1":
                d = aa.p1_decide(state, level, actions, monitored=monitored)
            else:
                d = aa.adapt(state, level, actions, report, pair)
            rows[name].append({
                "t": round(float(state.t), 3),
                "airborne": bool(airborne),
                "level": level,
                "response": d.response,
                "support": report.status,
                "pair_support": pair.status,
                "pair_reason": pair.reason,
                "gates": {g: round(float(weights.get(g, 0.0)), 4)
                          for g in spec["gates_under_test"]},
                "any_stale": bool([n for n in monitored
                                   if not state.fresh.get(n, False)]),
            })

    for t, name, ch in merged:
        for state in layer.ingest(name, t, ch):
            handle(state)
    for state in layer.flush(DURATION):
        handle(state)

    fault_family = "none" if condition == "N" else spec["fault_family"]
    faulty = None if condition == "N" else spec["faulty_source"]
    correct = cm31.correct_response_31(fault_family, faulty)
    window = ([float(faults[0].start),
               float(faults[0].start + faults[0].duration)]
              if faults else None)

    out = {
        "seed": seed, "gate_group": family, "condition": condition,
        "profile": "hover_circle", "takeoff_s": TAKEOFF_S,
        "armed_schedule": [[0.0, True]],
        "gating_sensor_dropped": list(drop),
        "fault_window_s": window,
        "fault_family": fault_family, "faulty_source": faulty,
        "correct_response": correct,
        "gates_under_test": list(spec["gates_under_test"]),
        "reaches": spec["reaches"],
        "meaningful_consequence_fields": list(
            cm31.MEANINGFUL.get(fault_family, ())),
        "policies": {},
    }
    for name, trace in rows.items():
        outcome = cm31.simulate_31(
            [{"t": r["t"], "airborne": r["airborne"],
              "response": r["response"]} for r in trace],
            fault_family=fault_family, faulty_source=faulty, correct=correct)
        out["policies"][name] = {
            "segments": _rle(trace),
            "outcome": vars(outcome),
            "ticks": len(trace),
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--partition", default="development")
    ap.add_argument("--i-am-opening-the-locked-partition", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    seeds = parts.seeds(
        args.partition,
        i_am_opening_the_locked_partition=args.i_am_opening_the_locked_partition)
    if args.limit:
        seeds = seeds[:args.limit]

    scenarios = []
    for seed in seeds:
        for family in FAMILIES:
            for condition in CONDITIONS:
                scenarios.append(run_scenario(seed=seed, family=family,
                                              condition=condition))
        print(f"  seed={seed}", flush=True)

    document = {
        "schema": "csia.consequence.phase31_traces/1",
        "phase": "3.1 -- actionability precondition",
        "partition": args.partition,
        "partition_manifest_hash": parts.manifest_hash(),
        "seeds": list(seeds),
        "evidence_level": "MODEL_BASED_ACTION_CONSEQUENCE",
        "executed_an_autopilot": False,
        "armed_a_vehicle": False,
        "touched_hardware": False,
        "uses_disarmed_gate_scenarios": False,
        "pooled_with_phase3": False,
        "seed_varies": ("sensor noise only; generate_flight is scripted and "
                        "its seed argument has no effect, by its own "
                        "docstring"),
        "condition_map": {
            "N": "nominal, no fault",
            "EA": "fault, evidence applicable (ESC telemetry present)",
            "EG": ("fault, evidence gated (ESC telemetry absent) -- armed, "
                   "airborne, past arm_time, physically consistent"),
            "FP": "condition EG read under policy P1 (freshness path)",
            "SA": "condition EG read under policy P2 (support-aware)",
        },
        "model_constants": cm31.CONSTANTS_31,
        "not_meaningful_for_any_family": list(cm31.NOT_MEANINGFUL_ANY_FAMILY),
        "families": {k: {kk: (list(vv) if isinstance(vv, tuple) else vv)
                         for kk, vv in v.items() if kk != "faults"}
                     for k, v in FAMILIES.items()},
        "scenarios": scenarios,
    }
    out = args.out or os.path.join(
        ROOT, "research", "consequence", "phase31", "results",
        f"PHASE31_TRACES_{args.partition.upper()}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"\nwrote {os.path.relpath(out, ROOT)}  ({len(scenarios)} "
          f"scenarios, sha256 {hashlib.sha256(text.encode()).hexdigest()[:16]}"
          f"...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
