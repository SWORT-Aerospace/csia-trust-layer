"""Ablation + parameter sweep for the shadow hypothesis layer (slice 3B).

    python tools/hypothesis_campaign.py

Writes experiments/results/hypothesis_campaign.json with a full provenance
manifest. SHADOW ONLY — nothing here touches active behaviour.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csia.diagnosis import IsolationOutcome, run_shadow  # noqa: E402
from csia.experiments import EvidenceEnvironment, build  # noqa: E402
from csia.scenarios import SCENARIOS  # noqa: E402
from csia.sensors import Fault, generate_flight  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
SHARED_TRUTH = ("battery", "motor_esc")
SHARED_RESOURCE = "MAIN_POWER_PACK"
INDEP_TRUTH = ("imu0", "imu1")


def shared_power(depth_v=1.2, rpm_loss=350.0, onset=30.0, dur=6.0,
                 delay_second=0.0):
    """Shared-cause fault. delay_second staggers the second source, which is
    what distinguishes a shared rail from two coincidental faults."""
    return [Fault("power_sag", "battery", onset, dur, {"depth_v": depth_v}),
            Fault("power_sag", "motor_esc", onset + delay_second, dur,
                  {"rpm_loss": rpm_loss})]


def independent_imu(onset0=25.0, onset1=27.0, r0=0.18, r1=-0.15):
    return [Fault("bias_drift", "imu0", onset0, 30.0,
                  {"axis": 2, "rate": r0, "channel": "accel"}),
            Fault("bias_drift", "imu1", onset1, 28.0,
                  {"axis": 2, "rate": r1, "channel": "accel"})]


def summarize(run, truth, onset, shared=None):
    return {
        "root": None if run.first_root is None else run.first_root[1],
        "affected": [] if run.first_root is None else list(run.first_root[2]),
        "isolation": run.isolation(truth, shared_resource=shared),
        "latency_s": None if run.latency(onset) is None
        else round(run.latency(onset), 2),
        "peak_shared": round(run.peak_confidence.get(
            "H_SHARED_POWER_DEGRADATION", 0.0), 3),
        "peak_independent": round(run.peak_confidence.get(
            "H_MULTI_INDEPENDENT_IMU", 0.0), 3),
        "peak_unknown": round(run.peak_confidence.get(
            "H_UNKNOWN_CROSS_SENSOR_INCONSISTENCY", 0.0), 3),
        "ambiguity": round(max((r.diagnostic_ambiguity for r in run.reports),
                               default=0.0), 3),
        "tick_cost_us": round(run.tick_cost_us, 1),
    }


def ablation():
    """Part 13. Each row removes exactly one mechanism."""
    truth = generate_flight()
    faults = shared_power()
    configs = {
        "full_architecture": {},
        "shared_cause_disabled": {"enable_shared_cause": False},
        "temporal_evidence_removed": {"enable_temporal_evidence": False},
        "topology_evidence_removed": {"enable_topology_evidence": False},
        "no_dwell": {"dwell_ticks": 1},
        "no_arm_time": {"arm_time_s": 0.0},
    }
    rows = {}
    for name, kw in configs.items():
        r = run_shadow(faults, truth=truth, **kw)
        rows[name] = summarize(r, SHARED_TRUTH, 30.0, SHARED_RESOURCE)
    # Legacy single-source diagnoser on the same scenario, for comparison.
    from csia.scenarios import run_scenario
    _, _, _, _, diag = run_scenario("power_sag", truth=truth)
    nominal = diag.causes.index("nominal")
    non_nom = diag.posterior.copy()
    non_nom[:, nominal] = 0.0
    kk = int(non_nom.max(axis=1).argmax())
    rows["legacy_single_source"] = {
        "root": diag.top(kk)[0][0],
        "affected": ["battery"],          # power_fault names one source
        "isolation": "CORRECT_SINGLE_SOURCE (cannot express a source SET)",
        "latency_s": None, "peak_shared": None, "peak_independent": None,
        "peak_unknown": None, "ambiguity": None, "tick_cost_us": None,
        "note": "legacy posterior is 1-of-K; no affected-source set, no "
                "shared-resource concept",
    }
    return rows


def discrimination():
    """Part 9. Shared cause vs simultaneous independent faults."""
    truth = generate_flight()
    out = {}
    a = run_shadow(shared_power(), truth=truth)
    out["A_shared_cause"] = summarize(a, SHARED_TRUTH, 30.0, SHARED_RESOURCE)
    b = run_shadow(independent_imu(), truth=truth)
    out["B_independent_faults"] = summarize(b, INDEP_TRUTH, 25.0)
    # B': independent faults made near-simultaneous — the hard case.
    c = run_shadow(independent_imu(onset0=25.0, onset1=25.2), truth=truth)
    out["B_prime_near_simultaneous"] = summarize(c, INDEP_TRUTH, 25.0)
    d = run_shadow([], truth=truth)
    out["C_clean"] = summarize(d, (), 0.0)
    return out


def sweep():
    """Part 14. Development range vs synthetic held-out combinations."""
    truth = generate_flight()
    dev, held = [], []

    for depth in (0.6, 0.9, 1.2, 1.8, 2.4):
        r = run_shadow(shared_power(depth_v=depth), truth=truth)
        dev.append({"param": "depth_v", "value": depth,
                    **summarize(r, SHARED_TRUTH, 30.0, SHARED_RESOURCE)})
    for onset in (20.0, 25.0, 30.0, 40.0):
        r = run_shadow(shared_power(onset=onset), truth=truth)
        dev.append({"param": "onset", "value": onset,
                    **summarize(r, SHARED_TRUTH, onset, SHARED_RESOURCE)})
    for dur in (3.0, 6.0, 12.0):
        r = run_shadow(shared_power(dur=dur), truth=truth)
        dev.append({"param": "duration", "value": dur,
                    **summarize(r, SHARED_TRUTH, 30.0, SHARED_RESOURCE)})
    # Delayed degradation of one source — partial shared-resource effect.
    for delay in (0.0, 1.0, 3.0, 6.0):
        r = run_shadow(shared_power(delay_second=delay), truth=truth)
        dev.append({"param": "second_source_delay", "value": delay,
                    **summarize(r, SHARED_TRUTH, 30.0, SHARED_RESOURCE)})

    # Held-out: combinations never used while developing the scoring rules.
    for depth, rpm, onset in ((0.75, 200.0, 22.0), (1.5, 500.0, 35.0),
                              (2.1, 120.0, 27.5), (0.5, 620.0, 44.0)):
        r = run_shadow(shared_power(depth_v=depth, rpm_loss=rpm, onset=onset),
                       truth=truth)
        held.append({"depth_v": depth, "rpm_loss": rpm, "onset": onset,
                     **summarize(r, SHARED_TRUTH, onset, SHARED_RESOURCE)})
    return {"development_range": dev, "synthetic_held_out": held}


def main() -> int:
    ab, disc, sw = ablation(), discrimination(), sweep()

    correct = [r for r in sw["synthetic_held_out"]
               if r["isolation"] == IsolationOutcome.CORRECT_COMMON_CAUSE.value]
    dev_correct = [r for r in sw["development_range"]
                   if r["isolation"] == IsolationOutcome.CORRECT_COMMON_CAUSE.value]

    man = build("hypothesis_campaign", EvidenceEnvironment.SIMULATION,
                output_paths=["experiments/results/hypothesis_campaign.json"])
    doc = {
        "result_schema_version": "1.0.0",
        "result_type": "SCENARIO",
        "evidence_environment": EvidenceEnvironment.SIMULATION.value,
        "experiment_manifest": man.to_dict(),
        "payload": {
            "authorization": "SHADOW_ONLY",
            "ablation": ab,
            "discrimination": disc,
            "sweep": sw,
            "summary": {
                "development_correct_common_cause":
                    f"{len(dev_correct)}/{len(sw['development_range'])}",
                "held_out_correct_common_cause":
                    f"{len(correct)}/{len(sw['synthetic_held_out'])}",
            },
        }}
    out = os.path.join(ROOT, "experiments", "results",
                       "hypothesis_campaign.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)

    print("=== ABLATION (shared-power scenario) ===")
    for k, v in ab.items():
        print(f"  {k:28s} iso={str(v['isolation'])[:26]:28s} "
              f"lat={v['latency_s']} shared={v['peak_shared']}")
    print("\n=== DISCRIMINATION ===")
    for k, v in disc.items():
        print(f"  {k:26s} root={str(v['root'])[:34]:36s} "
              f"shared={v['peak_shared']} indep={v['peak_independent']} "
              f"unk={v['peak_unknown']}")
    print("\n=== SWEEP ===")
    print(f"  development : {len(dev_correct)}/{len(sw['development_range'])} "
          "CORRECT_COMMON_CAUSE")
    print(f"  held-out    : {len(correct)}/{len(sw['synthetic_held_out'])} "
          "CORRECT_COMMON_CAUSE")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
