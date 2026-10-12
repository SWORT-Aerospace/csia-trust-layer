"""Phase 3 campaign runner — closed-loop consequence measurement.

WHAT IS REAL AND WHAT IS MODELLED, ONCE MORE AND IN ONE PLACE
--------------------------------------------------------------
Real, frozen, untouched:
  * `csia.sensors`               fault injection and sensor models
  * `csia.runtime.online`        the trust layer that produces TrustState
  * `csia.runtime.failsafe`      the policy that produces P0's response
  * `csia.diagnosis.causal`      the LOW-sets attribution is decided over

Modelled, and declared in the preregistration before any locked run:
  * `csia_consequence.consequence_model`   the vehicle's response to a response

**Nothing flew. Nothing was armed but a boolean. Nothing was commanded.**

SEEDS VARY NOISE, NOT THE TRAJECTORY
-------------------------------------
`csia.sensors.truth.generate_flight` is scripted: its `seed` argument has no
effect and its own docstring says so. A seed here therefore varies the sensor
NOISE realization and nothing else. Every scenario of a given profile flies the
same path. That is a real limit on what the campaign samples and it is recorded
in the output rather than left for a reader to discover.

    python research/consequence/phase3/campaign.py --partition development
    python research/consequence/phase3/campaign.py --partition locked \
        --i-am-opening-the-locked-partition
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

# research/consequence/phase3/campaign.py -> four levels up is the repo root
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from csia.runtime.failsafe import FailsafeConfig, FailsafePolicy  # noqa: E402
from csia.runtime.online import SENSORS, OnlineTrustLayer  # noqa: E402
from csia.sensors import (GPS, IMU, Barometer, Battery, Fault,  # noqa: E402
                          Magnetometer, MotorESC, VibrationSensor,
                          generate_flight)

from csia_consequence import action_adapter as aa  # noqa: E402
from csia_consequence import consequence_model as cm  # noqa: E402
from csia_consequence import phase3_partitions as parts  # noqa: E402

DURATION = 60.0
TICK_HZ = 25.0

#: Gate groups under test, and the decision each one bears on.
GATE_GROUPS = {
    "armed_gate_pair": {
        "gates": ("accel_motor_current", "accel_esc_rpm"),
        "closes_on": "vehicle_status.armed == False",
        "decision": "SELECT_IMU (imu0 versus imu1)",
        "fault_family": "imu_bias",
        "faulty_source": "imu0",
        "conditions": ("A", "B", "C", "F"),
    },
    "heading_course": {
        "gates": ("heading_course",),
        "closes_on": "speed_gate == 0 (ground speed below GATE_SPEED_LO)",
        "decision": "HEADING_HOLD_GYRO (mag untrusted)",
        "fault_family": "mag_emi",
        "faulty_source": "mag",
        "conditions": ("A", "B", "C", "F", "G"),
    },
}


def _sensors(seed: int) -> dict:
    """The eight nodes, with per-node seeds derived from one campaign seed."""
    def s(offset: int) -> int:
        return (seed + offset * 7919) % (2 ** 31 - 1)
    return {
        "imu0": IMU("imu0", seed=s(1)), "imu1": IMU("imu1", seed=s(2)),
        "baro": Barometer(seed=s(3)), "mag": Magnetometer(seed=s(4)),
        "gps": GPS(seed=s(5)), "motor_esc": MotorESC(seed=s(6)),
        "battery": Battery(seed=s(7)), "vibration": VibrationSensor(seed=s(8)),
    }


def _events(seed: int, profile: str, faults) -> tuple:
    truth = generate_flight(duration=DURATION, dt=0.01, profile=profile)
    streams = {n: s.sample(truth, faults) for n, s in _sensors(seed).items()}
    out = []
    for name, stream in streams.items():
        if name == "vibration":
            for i, t in enumerate(stream["t_rms"]):
                out.append((float(t), name,
                            {"rms": float(stream["rms"][i]), "valid": True}))
            continue
        keys = [k for k in stream if k != "t"]
        for i, t in enumerate(stream["t"]):
            ch = {}
            for k in keys:
                v = stream[k]
                ch[k] = bool(v[i]) if k == "valid" else v[i]
            out.append((float(t), name, ch))
    out.sort(key=lambda e: e[0])
    return truth, out


def _merge_armed(events, schedule):
    merged = [(float(t), "vehicle_status", {"armed": bool(a)})
              for t, a in schedule]
    merged.extend(events)
    merged.sort(key=lambda e: (e[0], e[1] != "vehicle_status"))
    return merged


def run_scenario(*, seed: int, group: str, condition: str) -> dict:
    """One scenario, three policies, one pass of the trust layer.

    The trust layer runs ONCE. All three policies consume the same
    `TrustState` stream, so any difference between them is the policy and not
    a different realization of the noise.
    """
    spec = GATE_GROUPS[group]
    profile = "hover_circle"
    faults = []
    schedule = [(0.0, True)]
    takeoff_s = 5.0

    if group == "armed_gate_pair":
        if condition != "A":
            faults = [Fault("bias_drift", "imu0", 1.0, 50.0,
                            {"axis": 2, "rate": 0.12, "channel": "accel"})]
        if condition == "B":
            # disarmed through the ground phase: the gate is hard zero while
            # every sensor stays fresh
            schedule = [(0.0, False), (5.0, True)]
        if condition == "F":
            # POSITIVE CONTROL, PHYSICALLY INCONSISTENT ON PURPOSE. The
            # vehicle reports disarmed from t=12 while its sensors show it
            # flying. No real multirotor does this. It exists so the campaign
            # can show that the apparatus WOULD register a conflict if the
            # occlusion window reached the decision window, which for this
            # gate it cannot. Note the conflation it carries: `armed=False`
            # also switches the failsafe off wholesale, so F mixes "the gate
            # closed" with "the decision layer stopped", and is read only as
            # evidence that the measurement responds at all.
            schedule = [(0.0, True), (12.0, False)]
    elif group == "heading_course":
        if condition == "C":
            profile = "fast_cruise"
        if condition in ("B", "C"):
            faults = [Fault("emi_spike", "mag", 20.0, 25.0,
                            {"amplitude": 10.0, "rate_hz": 12.0})]
        if condition == "F":
            # POSITIVE CONTROL, AND THIS ONE IS PHYSICALLY CONSISTENT. The
            # vehicle is armed, airborne, past arm_time, and hovering -- so
            # `speed_gate` is zero while the failsafe is fully live. The fault
            # runs inside the hover segment (45-50 s of `hover_circle`).
            # Nothing is faked; this is a flight regime the gate closes in.
            faults = [Fault("emi_spike", "mag", 45.5, 4.0,
                            {"amplitude": 10.0, "rate_hz": 12.0})]
        if condition == "G":
            # F's MATCHED CONTROL, and the reason it exists is a confound
            # found on development seeds. F's fault is 4 s long; B and C use
            # a 25 s fault. So F missing a detection could have been the
            # short fault rather than the closed gate, and F alone could not
            # tell those apart. G is the SAME 4 s fault at the same phase of
            # the same trajectory, moved to 25.0 s where the vehicle is
            # circling and `speed_gate` is open. F versus G isolates the gate;
            # F versus B does not.
            faults = [Fault("emi_spike", "mag", 25.0, 4.0,
                            {"amplitude": 10.0, "rate_hz": 12.0})]

    truth, events = _events(seed, profile, faults)
    merged = _merge_armed(events, schedule)

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
        airborne = state.t >= takeoff_s
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
                          for g in spec["gates"]},
                "any_stale": bool([n for n in monitored
                                   if not state.fresh.get(n, False)]),
            })

    for t, name, ch in merged:
        for state in layer.ingest(name, t, ch):
            handle(state)
    for state in layer.flush(DURATION):
        handle(state)

    fault_family = "none" if condition == "A" else spec["fault_family"]
    faulty = None if condition == "A" else spec["faulty_source"]
    correct = cm.correct_response(fault_family, faulty)

    window = ([float(faults[0].start),
               float(faults[0].start + faults[0].duration)]
              if faults else None)
    out = {
        "seed": seed, "gate_group": group, "condition": condition,
        # The fault window is what makes the occlusion measurable AGAINST the
        # fault. Total airborne closed time is the wrong denominator: in
        # `hover_circle` the speed gate is closed for about half the flight
        # whatever the fault is doing, so two conditions can share it and
        # still differ entirely in whether the gate was shut WHEN IT MATTERED.
        "fault_window_s": window,
        "profile": profile, "takeoff_s": takeoff_s,
        "armed_schedule": [[float(t), bool(a)] for t, a in schedule],
        "fault_family": fault_family, "faulty_source": faulty,
        "correct_response": correct,
        "gates_under_test": list(spec["gates"]),
        "closes_on": spec["closes_on"], "decision": spec["decision"],
        "policies": {},
    }
    for name, trace in rows.items():
        outcome = cm.simulate(
            [{"t": r["t"], "airborne": r["airborne"],
              "response": r["response"]} for r in trace],
            fault_family=fault_family, faulty_source=faulty, correct=correct)
        out["policies"][name] = {
            "segments": _rle(trace),
            "outcome": vars(outcome),
            "ticks": len(trace),
        }
    return out


def _rle(trace) -> list:
    """Run-length encode the trace on everything a classification depends on.

    A full per-tick trace over the whole campaign is hundreds of thousands of
    rows and nothing reads them individually. The encoding is lossless for
    every field the independent evaluator consumes, and the tick count is
    carried alongside so a reader can check nothing was dropped.
    """
    segments = []
    key = None
    for row in trace:
        k = (row["airborne"], row["level"], row["response"], row["support"],
             row["pair_support"], row["any_stale"],
             tuple(sorted((g, (v > 0.0)) for g, v in row["gates"].items())))
        if k != key:
            segments.append({"t_start": row["t"], "t_end": row["t"],
                             "airborne": row["airborne"],
                             "level": row["level"],
                             "response": row["response"],
                             "support": row["support"],
                             "pair_support": row["pair_support"],
                             "any_stale": row["any_stale"],
                             "gates_open": {g: bool(v > 0.0)
                                            for g, v in row["gates"].items()},
                             "gates_at_start": dict(row["gates"]),
                             "ticks": 1})
            key = k
        else:
            segments[-1]["t_end"] = row["t"]
            segments[-1]["ticks"] += 1
    return segments


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
        for group in GATE_GROUPS:
            for condition in GATE_GROUPS[group]["conditions"]:
                scenarios.append(run_scenario(seed=seed, group=group,
                                              condition=condition))
                print(f"  {group:18s} {condition} seed={seed}", flush=True)

    document = {
        "schema": "csia.consequence.phase3_traces/1",
        "partition": args.partition,
        "partition_manifest_hash": parts.manifest_hash(),
        "seeds": list(seeds),
        "evidence_level": "MODEL_BASED_ACTION_CONSEQUENCE",
        "executed_an_autopilot": False,
        "armed_a_vehicle": False,
        "touched_hardware": False,
        "seed_varies": ("sensor noise only; generate_flight is scripted and "
                        "its seed argument has no effect, by its own "
                        "docstring"),
        "condition_map": {
            "A": "nominal control, no fault",
            "B": "fault with the gate closed and data fresh",
            "C": "matched fault with the gate open",
            "G": ("matched control for F -- the same short fault at a moment "
                  "when the gate is OPEN. Added during the development phase "
                  "after F alone was found to confound fault duration with "
                  "gate state."),
            "F": ("positive control -- the occlusion forced into the decision "
                  "window. For heading_course this is a real flight regime "
                  "(armed, airborne, hovering). For armed_gate_pair it is "
                  "PHYSICALLY INCONSISTENT and labelled as such."),
            "D": "condition B evaluated under policy P1 (freshness fallback)",
            "E": "condition B evaluated under policy P2 (support-aware)",
        },
        "model_constants": cm.CONSTANTS,
        "gate_groups": GATE_GROUPS,
        "scenarios": scenarios,
    }
    out = args.out or os.path.join(
        ROOT, "research", "consequence", "phase3", "results",
        f"PHASE3_TRACES_{args.partition.upper()}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"\nwrote {os.path.relpath(out, ROOT)}  "
          f"({len(scenarios)} scenarios, sha256 "
          f"{hashlib.sha256(text.encode()).hexdigest()[:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
