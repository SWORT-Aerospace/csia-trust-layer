"""Phase 3.2 campaign — the direct preregistered H2 test.

Phase 3.1 found the conflict. Phase 3.2 tests it on a partition drawn after
that finding, with the design fixed beforehand, which is the difference
between a finding and a confirmation.

THE GRID IS ITERATED IN DECLARATION ORDER AND NOTHING IS PRUNED
----------------------------------------------------------------
Phase 3.1 measured crossing time to be NON-MONOTONE in fault rate: 0.12
crossed at 26.96 s while 0.18 and 0.25 crossed later. Any procedure that
sorted the grid, stopped early on a "sufficient" magnitude, or dropped a
point as redundant would be unsound here. `GRIDS` are declared lists and
every point is run on every seed.

**Nothing flew. Nothing was armed but a boolean. Nothing was commanded.**

    python research/consequence/phase32/campaign32.py --partition development
    python research/consequence/phase32/campaign32.py --partition locked \
        --i-am-opening-the-locked-partition
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import traceback

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
from csia_consequence import phase32_partitions as parts  # noqa: E402

TAKEOFF_S = 5.0
GATING_SENSOR = "motor_esc"

#: Declared grids. Iterated in THIS order; never sorted, pruned or shortened.
GRIDS = {
    "structural": [1.5, 2.0, 2.5, 3.0, 4.0],
    "imu_isolation": [0.03, 0.05, 0.08, 0.12, 0.18],
}

#: The single point that carries the H2 verdict. Everything else is a
#: preregistered dose-response secondary with no verdict resting on it.
CONFIRMATORY = {"structural": 3.0}

ARMS = {
    "structural": {
        "role": "PRIMARY",
        "fault_family": "vibration_anomaly",
        "faulty_source": "vibration",
        "onset_s": 28.0, "duration_s": 20.0,
        "gates_under_test": ("vibration_prop_freq",),
        "make": lambda g: [Fault("vibration_anomaly", "vibration", 28.0, 20.0,
                                 {"gain": g})],
    },
    "imu_isolation": {
        "role": "SECONDARY",
        "fault_family": "imu_bias",
        "faulty_source": "imu0",
        "onset_s": 15.0, "duration_s": 40.0,
        "gates_under_test": ("accel_motor_current", "accel_esc_rpm"),
        "make": lambda r: [Fault("bias_drift", "imu0", 15.0, 40.0,
                                 {"axis": 2, "rate": r, "channel": "accel"})],
    },
}


def run_scenario(*, seed: int, family: str, condition: str, magnitude):
    """One scenario. Returns (document, invalid_reason_or_None)."""
    spec = ARMS[family]
    faults = [] if condition == "N" else spec["make"](magnitude)
    drop = (GATING_SENSOR,) if condition == "EG" else ()

    try:
        _truth, events = _events(seed, "hover_circle", faults)
        if drop:
            events = [e for e in events if e[1] not in drop]
        merged = _merge_armed(events, [(0.0, True)])

        layer = OnlineTrustLayer(tick_hz=TICK_HZ)
        policies = {"P0": FailsafePolicy(FailsafeConfig()),
                    "P2": FailsafePolicy(FailsafeConfig())}
        rows = {k: [] for k in policies}
        levels = {}

        def handle(state):
            report = aa.p2_support(state)
            pair = aa.decision_pair_support(state)
            weights = aa.feature_weights(state)
            airborne = state.t >= TAKEOFF_S
            for name, policy in policies.items():
                actions = policy.update(state)
                level = int(policy.level)
                if name == "P0":
                    levels.setdefault(level, round(float(state.t), 3))
                    d = aa.p0_decide(state, level, actions)
                else:
                    d = aa.adapt(state, level, actions, report, pair)
                rows[name].append({
                    "t": round(float(state.t), 3),
                    "airborne": bool(airborne), "level": level,
                    "response": d.response, "support": report.status,
                    "pair_support": pair.status,
                    "gates": {g: round(float(weights.get(g, 0.0)), 4)
                              for g in spec["gates_under_test"]},
                    "any_stale": False,
                })

        for t, name, ch in merged:
            for state in layer.ingest(name, t, ch):
                handle(state)
        for state in layer.flush(DURATION):
            handle(state)

        if not rows["P0"]:
            return None, "zero ticks produced"
        if layer.bad_samples:
            return None, f"trust layer rejected {layer.bad_samples} samples"
    except Exception:                       # noqa: BLE001 - recorded, not hidden
        return None, "exception: " + traceback.format_exc(limit=2).strip()

    fault_family = "none" if condition == "N" else spec["fault_family"]
    faulty = None if condition == "N" else spec["faulty_source"]
    correct = cm31.correct_response_31(fault_family, faulty)
    window = ([spec["onset_s"], spec["onset_s"] + spec["duration_s"]]
              if faults else None)

    out = {
        "seed": seed, "gate_group": family, "family_role": spec["role"],
        "condition": condition, "magnitude": magnitude,
        "is_confirmatory": bool(condition in ("EA", "EG")
                                and CONFIRMATORY.get(family) == magnitude),
        "profile": "hover_circle", "takeoff_s": TAKEOFF_S,
        "armed_schedule": [[0.0, True]],
        "gating_sensor_dropped": list(drop),
        "fault_window_s": window,
        "fault_window_duration_s": (window[1] - window[0]) if window else 0.0,
        "fault_family": fault_family, "faulty_source": faulty,
        "correct_response": correct,
        "gates_under_test": list(spec["gates_under_test"]),
        "time_to_level_s": {str(k): v for k, v in sorted(levels.items())
                            if k > 0},
        "meaningful_consequence_fields": list(
            cm31.MEANINGFUL.get(fault_family, ())),
        "policies": {},
    }
    for name, trace in rows.items():
        outcome = cm31.simulate_31(
            [{"t": r["t"], "airborne": r["airborne"],
              "response": r["response"]} for r in trace],
            fault_family=fault_family, faulty_source=faulty, correct=correct)
        out["policies"][name] = {"segments": _rle(trace),
                                 "outcome": vars(outcome),
                                 "ticks": len(trace)}
    return out, None


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

    scenarios, invalid = [], []
    for seed in seeds:
        for family in ARMS:                       # declaration order
            doc, why = run_scenario(seed=seed, family=family, condition="N",
                                    magnitude=None)
            (scenarios if doc else invalid).append(
                doc or {"seed": seed, "gate_group": family, "condition": "N",
                        "magnitude": None, "reason": why})
            for magnitude in GRIDS[family]:       # declaration order, no sort
                for condition in ("EA", "EG"):
                    doc, why = run_scenario(seed=seed, family=family,
                                            condition=condition,
                                            magnitude=magnitude)
                    (scenarios if doc else invalid).append(
                        doc or {"seed": seed, "gate_group": family,
                                "condition": condition,
                                "magnitude": magnitude, "reason": why})
        print(f"  seed={seed}", flush=True)

    document = {
        "schema": "csia.consequence.phase32_traces/1",
        "phase": "3.2 -- direct preregistered consequence test",
        "partition": args.partition,
        "partition_manifest_hash": parts.manifest_hash(),
        "seeds": list(seeds),
        "evidence_level": "MODEL_BASED_ACTION_CONSEQUENCE",
        "executed_an_autopilot": False, "armed_a_vehicle": False,
        "touched_hardware": False, "uses_disarmed_gate_scenarios": False,
        "pooled_with_phase3": False, "pooled_with_phase31": False,
        "grids": GRIDS, "grid_order": "declaration order; never sorted or pruned",
        "confirmatory_point": CONFIRMATORY,
        "arms": {k: {kk: vv for kk, vv in v.items() if kk != "make"}
                 for k, v in ARMS.items()},
        "condition_map": {
            "N": "matched nominal, no fault, ESC telemetry present",
            "EA": "matched fault, evidence applicable (ESC present)",
            "EG": "matched fault, evidence gated (ESC absent), flying"},
        "model_constants": cm31.CONSTANTS_31,
        "not_meaningful_for_any_family": list(cm31.NOT_MEANINGFUL_ANY_FAMILY),
        "invalid_runs": invalid,
        "invalid_run_count": len(invalid),
        "scenarios": scenarios,
    }
    out = args.out or os.path.join(
        ROOT, "research", "consequence", "phase32", "results",
        f"PHASE32_TRACES_{args.partition.upper()}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"\nwrote {os.path.relpath(out, ROOT)}  ({len(scenarios)} scenarios, "
          f"{len(invalid)} invalid, sha256 "
          f"{hashlib.sha256(text.encode()).hexdigest()[:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
