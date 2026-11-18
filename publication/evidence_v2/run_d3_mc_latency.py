#!/usr/bin/env python3
"""Deliverable 3, data: every latency stage of every faulted run of the UAV
fault-harness Monte Carlo, from a replay of its own seeded stream.

    python publication/evidence_v2/run_d3_mc_latency.py

The harness is `csia.validation.monte_carlo(runs=150, field_mode=True,
seed=0)`, whose output is the committed campaigns/monte_carlo.json. This script
draws from `numpy.random.default_rng(0)` in exactly the same order, builds the
same faults with `csia.validation.FAULTS` and runs them with
`csia.validation._run_one`, so the runs are the committed campaign's runs.
Checkpoint: re-aggregating them the way monte_carlo() does must reproduce
campaigns/monte_carlo.json field for field, or the script exits 1.

Per run it then calls `csia.metrics.latency.measure`, the repository's single
owner of latency logic (docs/validation/METRIC_DEFINITIONS.md section 3), with
its defaults: configured onset, analysis threshold 0.85, merge_s 10.0,
classification and isolation confidence 0.90.

Also run once: the catalogue scenario `gps_dropout` (csia/scenarios.py), which
the harness has no class for. Its catalogue description says trust must HOLD,
not alarm, so it is recorded as one deterministic run, not as a latency
distribution.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

sys.path.insert(0, C.ROOT)
import numpy as np  # noqa: E402

from csia import validation as V  # noqa: E402
from csia.metrics import alert_episodes  # noqa: E402
from csia.metrics.latency import measure  # noqa: E402
from csia.runtime import (FailsafePolicy, OnlineTrustLayer,  # noqa: E402
                          SimulatedFlightSource, TrustLayerRuntime)
from csia.scenarios import SCENARIOS  # noqa: E402
from csia.sensors import generate_flight  # noqa: E402

RUNS, SEED, FIELD_MODE = 150, 0, True
COMMITTED = os.path.join(C.ROOT, "campaigns", "monte_carlo.json")
OUT = os.path.join(C.DATA, "d3_mc_runs.json")
STAGES = ("time_to_trust_threshold_s", "time_to_alert_event_s", "time_to_alert_episode_s",
          "time_to_classification_s", "time_to_correct_isolation_s",
          "time_to_arbitration_recommendation_s")


def r6(x):
    return None if x is None else round(float(x), 6)


def replay():
    rng = np.random.default_rng(SEED)
    classes = list(V.FAULTS)
    faulted, clean = [], []
    for i in range(RUNS):
        rng.integers(1, 2 ** 31)                       # monte_carlo()'s stream-position draw
        truth = generate_flight()
        if rng.random() < 0.4:
            s = V._run_one(truth, [], FIELD_MODE)
            clean.append({"run": i, "hours": 60.0 / 3600.0,
                          "alert_episodes": len(alert_episodes(s.transitions))})
            continue
        cls = classes[int(rng.integers(len(classes)))]
        target, mk = V.FAULTS[cls]
        k = float(rng.uniform(0.5, 2.0))
        onset = float(rng.uniform(15.0, 35.0))
        fault = mk(k, onset)
        s = V._run_one(truth, [fault], FIELD_MODE)
        det, lat, _, _ = V._detection(s, target, onset)
        m = measure(s, fault, scenario_id=f"mc{SEED}-run{i:03d}").to_dict()
        row = {"run": i, "fault_class": cls, "target": target, "amplitude_scale": r6(k),
               "onset_s": r6(onset), "fault_kind": fault.kind, "fault_duration_s": fault.duration,
               "mc_detected_trust_lt_0_85": det, "mc_latency_s": r6(lat)}
        for key in STAGES:
            row[key] = r6(m[key])
        row.update({"alert_state": m["alert_state"], "classified_as": m["classified_as"],
                    "isolation_outcome": m["isolation_outcome"], "isolated_as": m["isolated_as"],
                    "arbitration_action": m["arbitration_action"], "outcome": m["outcome"],
                    "trust_threshold": m["trust_threshold"], "onset_basis": m["onset_basis"]})
        faulted.append(row)
        print(f"  run {i:3d} {cls:10s} k={k:.2f} onset={onset:5.2f} "
              f"trust<0.85 {row['time_to_trust_threshold_s']} alert {row['time_to_alert_event_s']}")
    return faulted, clean


def reaggregate(faulted, clean):
    """monte_carlo()'s own aggregation, verbatim in effect."""
    from scipy.stats import chi2
    rep = {"runs": RUNS, "field_mode": FIELD_MODE, "seed": SEED, "classes": {}, "clean": {}}
    for c in V.FAULTS:
        rs = [r for r in faulted if r["fault_class"] == c]
        if not rs:
            continue
        det = sum(r["mc_detected_trust_lt_0_85"] for r in rs)
        lats = sorted(r["mc_latency_s"] for r in rs if r["mc_latency_s"] is not None)
        lo, hi = V._wilson(det, len(rs))
        rep["classes"][c] = {
            "n": len(rs), "detected": det, "tpr": round(det / len(rs), 3),
            "ci95": [round(lo, 3), round(hi, 3)],
            "latency_p50_s": round(lats[len(lats) // 2], 2) if lats else None,
            "latency_p95_s": round(lats[int(0.95 * (len(lats) - 1))], 2) if lats else None}
    hours = sum(c["hours"] for c in clean)
    k = sum(c["alert_episodes"] for c in clean)
    lo = chi2.ppf(0.025, 2 * k) / 2 / hours if k else 0.0
    hi = chi2.ppf(0.975, 2 * k + 2) / 2 / hours
    rep["clean"] = {"flights": len(clean), "hours": round(hours, 2), "alarms": k,
                    "rate_per_hr": round(k / hours, 2), "ci95_per_hr": [round(lo, 2), round(hi, 2)]}
    return rep


def dropout_once():
    _, faults = SCENARIOS["gps_dropout"]
    src = SimulatedFlightSource("gps_dropout")
    rt = TrustLayerRuntime(src, layer=OnlineTrustLayer(field_mode=FIELD_MODE),
                           policy=FailsafePolicy(), keep_states=True)
    s = rt.run()
    m = measure(s, faults[0], scenario_id="catalogue-gps_dropout").to_dict()
    gps = [st.trust["gps"] for st in s.states if st.t >= faults[0].start]
    return {k: (r6(v) if isinstance(v, float) else v) for k, v in m.items()
            if k in STAGES or k in ("alert_state", "isolation_outcome", "outcome", "onset_s",
                                    "classified_as", "notes")} | {
        "min_gps_trust_after_onset": r6(min(gps)), "alert_episodes": len(alert_episodes(s.transitions)),
        "field_mode": FIELD_MODE, "catalogue_description": SCENARIOS["gps_dropout"][0]}


def main() -> int:
    faulted, clean = replay()
    rep = reaggregate(faulted, clean)
    committed = json.load(open(COMMITTED, encoding="utf-8"))
    same = rep == committed
    C.write_json(OUT, {
        "schema": "csia.evidence_v2.d3_mc_runs/1",
        "harness": "csia.validation.monte_carlo(runs=150, field_mode=True, seed=0)",
        "checkpoint_vs_campaigns_monte_carlo_json": "IDENTICAL" if same else "DIFFERS",
        "reaggregated": rep,
        "faulted_runs": faulted,
        "clean_runs": clean,
        "catalogue_gps_dropout_single_run": dropout_once(),
        "conditioning": [
            "every run flies the same trajectory (csia/validation.py comment; "
            "tests/test_flight_truth_determinism.py)",
            "every run uses the same sensor noise: csia/scenarios.make_sensors fixes seeds 1-8",
            "what varies is fault class, amplitude scale in [0.5, 2.0), onset in [15, 35) s, "
            "and the clean/faulted split"],
    })
    C.stamp(OUT, __file__, inputs=(COMMITTED,),
            configs=((os.path.join(C.ROOT, "csia", "validation.py"), "harness: FAULTS, _run_one, _detection"),
                     (os.path.join(C.ROOT, "csia", "metrics", "latency.py"), "latency stage definitions"),
                     (os.path.join(C.ROOT, "csia", "metrics", "events.py"), "alert episodes, merge_s"),
                     (os.path.join(C.ROOT, "csia", "runtime", "failsafe.py"), "FailsafeConfig defaults"),
                     (os.path.join(C.ROOT, "csia", "scenarios.py"), "sensor seeds, gps_dropout scenario")),
            datasets={"dataset_id": "synthetic UAV fault harness (csia.validation.monte_carlo)",
                      "trajectory": "csia.sensors.generate_flight() default"},
            seeds={"numpy_default_rng": SEED, "sensor_seeds": {"imu0": 1, "imu1": 2, "baro": 3, "mag": 4,
                                                               "gps": 5, "motor_esc": 6, "battery": 7,
                                                               "vibration": 8}},
            definitions=[{"metric": "latency stages", "source": "docs/validation/METRIC_DEFINITIONS.md",
                          "section": "3.2-3.7"}],
            notes=[f"checkpoint vs campaigns/monte_carlo.json: {'IDENTICAL' if same else 'DIFFERS'}"])
    print("checkpoint:", "IDENTICAL" if same else "DIFFERS")
    if not same:
        print(json.dumps(rep, indent=1))
    return 0 if same else 1


if __name__ == "__main__":
    C.main_guard(main)
