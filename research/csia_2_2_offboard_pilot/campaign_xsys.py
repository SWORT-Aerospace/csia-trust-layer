#!/usr/bin/env python3
"""Phases 4, 8, 10 and 19: the whole XSYS-001 campaign through the 2.2 PX4
adapter and the Analyzer. NON-CONFIRMATORY. EXPLORATORY for anything about
the estimator, as XSYS-001's own preregistration (§7.4) made W_EST.

    .venv/bin/python research/csia_2_2_offboard_pilot/campaign_xsys.py

Reads the 66 raw flight logs (RAW_DATA_MANIFEST.json, each checked against
its recorded SHA-256), the sealed stage-1 features and the stage-0 key.
Nothing XSYS-001 wrote is changed.

| part | output |
|---|---|
| per flight | the estimator facts: claims, gates, faults, time slip, transitions, device ids, lag, cross-flight consistency |
| estimator informativeness | each innovation claim's change at onset, in A flights (motor degraded) against NB flights (nominal): is it informative, context or redundant for this fault class? |
| per trial (121) | the Analyzer on the trial (witnesses with the flight's estimator, V3_TEMPORAL): its C3 verdict against truth, the lineage of the adverse evidence, and the corroboration counts (naive, 2.2, ground truth) |

Writes CAMPAIGN_XSYS.json.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter

import numpy as np

import common_pilot as C

from csia_evidence_assurance import runs  # noqa: E402
from csia_evidence_assurance.adapters import px4_estimator as PX  # noqa: E402
from csia_evidence_assurance.adapters import xsys_witness as XW  # noqa: E402

OUT = C.HERE / "CAMPAIGN_XSYS.json"
CAMPAIGN = C.REPO / "research/xsys_001_confirmatory_campaign"
WINDOWS = {"pre": (-5.0, 0.0), "T1": (0.0, 0.2), "T2": (0.2, 2.0), "T3": (10.0, 15.0)}
#: Ground-truth source independence of the XSYS-001 witnesses and the
#: estimator, from the code paths (`xsys_extract.load_full`, PX4 547e2ca):
#: a pair is DEPENDENT if one source fault can corrupt both outputs.
GROUND_TRUTH_SOURCES = {
    "xsys:w_rpm": {"esc_status RPM telemetry", "motor command (actuator_outputs_sim)"},
    "xsys:w_dyn": {"IMU gyro (sensor_combined)", "rotor geometry (CA_ROTOR*)"},
    "xsys:w_ctrl": {"motor command (actuator_motors)", "rate controller",
                    "IMU gyro (vehicle_angular_velocity)", "EKF2 (bias, attitude)"},
    "px4:ekf2.estimator_status": {"IMU gyro and accel", "EKF2", "GNSS", "barometer", "magnetometer"},
}
#: The same physical source, named by different code paths.
SAME_SOURCE = [{"motor command (actuator_outputs_sim)", "motor command (actuator_motors)"},
               {"IMU gyro (sensor_combined)", "IMU gyro (vehicle_angular_velocity)",
                "IMU gyro and accel"},
               {"EKF2 (bias, attitude)", "EKF2"}]


def canon_source(s):
    for group in SAME_SOURCE:
        if s in group:
            return sorted(group)[0]
    return s


def gt_independent_lines(producers):
    """Ground truth: the largest set of producers no two of which share a source."""
    import itertools
    srcs = {p: {canon_source(s) for s in GROUND_TRUTH_SOURCES[p]} for p in producers}
    ps = sorted(srcs)
    for n in range(len(ps), 0, -1):
        for combo in itertools.combinations(ps, n):
            if all(srcs[a].isdisjoint(srcs[b]) for a, b in itertools.combinations(combo, 2)):
                return n
    return 0


def onset_s(name, ulg):
    sys.path.insert(0, str(XW.PIPELINE))
    import xsys_extract as XE
    from pyulog import ULog
    rec = json.loads((CAMPAIGN / "campaign/records" / f"{name}.json").read_text())
    u = ULog(str(ulg), ["parameter_update", "esc_status"])
    got = XE.onset_time(u, rec["onset_param"])
    return None if got is None else (got[1] - u.start_timestamp) * 1e-6


def flight_facts(name, ulg):
    log = PX.EstimatorLog.from_ulog(ulg)
    est = PX.EstimatorProducer(log)
    d = log.status[min(log.status)]
    ts = (d["timestamp"].astype(np.int64) - log.t0_us) * 1e-6
    tss = (d["timestamp_sample"].astype(np.int64) - log.t0_us) * 1e-6
    lag = ts - tss
    aligned = np.array([i["health"] is not PX.ProducerHealth.UNAVAILABLE for i in est._stream])
    rows = est._stream
    t_on = onset_s(name, ulg)
    claims = {}
    for claim, (fld, kind, _bits, _r) in sorted(PX.CLAIMS.items()):
        x = np.array([float(i["row"][fld]) for i in rows])
        xs = x[aligned]
        win = {}
        for w, (lo, hi) in WINDOWS.items():
            if t_on is None:
                break
            m = (tss >= t_on + lo) & (tss < t_on + hi) & aligned
            v = x[m]
            v = v[np.isfinite(v)]
            win[w] = round(float(v.max()), 6) if len(v) else None
        claims[claim] = {"max_after_alignment": round(float(np.nanmax(xs)), 6) if np.isfinite(xs).any() else None,
                         "over_gate_outputs": int(np.sum(np.isfinite(xs) & (xs > PX.GATE))),
                         "not_applicable_fraction_after_alignment": round(float(np.mean(~np.isfinite(xs))), 4),
                         "window_max": win}
    trans = Counter()
    times = {"reset": [], "aiding": []}
    for t in np.arange(0.0, ts[-1], 0.1):
        _cur, ev = est.context(round(float(t), 3))
        for k, desc in ev.items():
            kind = "reset" if k.startswith("ekf2.reset") else "aiding" if k.startswith("ekf2.aiding") else k
            trans[kind] += 1
            if kind in times:
                times[kind].append([round(float(t), 1), desc])
    faults = int(np.sum(d["filter_fault_flags"].astype(np.int64) & PX.FAULT_MASK != 0))
    slips = int(np.sum(np.diff(d["time_slip"].astype(float)) > 1e-9))
    return {"ver_sw": log.ver_sw[:7], "lane_mode": est._lane_mode,
            "SENS_IMU_MODE": log.params.get("SENS_IMU_MODE"),
            "device_ids": {k: sorted({int(v) for v in d[k]}) for k in
                           ("gyro_device_id", "accel_device_id", "baro_device_id", "mag_device_id")},
            "lag_s": {"p50": round(float(np.median(lag)), 4), "max": round(float(lag.max()), 4)},
            "period_s_median": round(float(np.median(np.diff(ts))), 4),
            "alignment_s": round(float(ts[np.argmax(aligned)]), 3),
            "filter_fault_outputs": faults, "time_slip_increments": slips,
            "transitions": dict(trans), "transition_times": times,
            "onset_s": None if t_on is None else round(t_on, 3), "claims": claims,
            "lineage_roots": sorted({r for e in est.envelopes_of(rows[-1]) for r in e.lineage.roots}),
            "epoch_keys": sorted(rows[-1]["epochs"])}


def trial_result(aid, k, ulg):
    run = runs.xsys_trial(aid, "V3_TEMPORAL", ulg)
    last = run.results[-1]
    loc = [x for x in last.localizations if x["subject"] == "motor_0"]
    adverse = [e for e in last.evidence["used"] if e in last.state["abnormal"]["adverse_evidence"]]
    producers = sorted({e.split("|", 1)[0] for e in adverse})
    est_states = Counter()
    for r in run.results:
        for c in r.producers.get("coverage", []):
            if c["producer_id"] == "px4:ekf2.estimator_status":
                est_states[c["state"]] += 1
    rejected = Counter(x["status"] for r in run.results for x in r.evidence["rejected"])
    ov = last.corroboration["overall"]
    return {"analysis_id": aid, "kind": k["kind"], "truth": k["truth"], "eta": k["eta"],
            "flight": k["source_flight_id"],
            "c3_motor_0": None if not loc else {"outcome": loc[0]["outcome"],
                                                "candidates": loc[0]["candidates"]},
            "adverse_producers": producers,
            "naive_count": len(adverse),
            "lineage_groups": len(ov["lineage_groups"]),
            "independent_lines_2_2": ov["independent_lines"],
            "independent_lines_ground_truth": gt_independent_lines(producers) if producers else 0,
            "estimator_coverage_states": dict(sorted(est_states.items())),
            "rejected": dict(sorted(rejected.items()))}


def main():
    t0 = time.perf_counter()
    man = json.loads((CAMPAIGN / "RAW_DATA_MANIFEST.json").read_text())
    flights = sorted((f["trial_id"], f["sha256"]) for f in man["files"] if f["kind"] == "ulog")
    out = {"label": "NON-CONFIRMATORY; estimator statements EXPLORATORY (XSYS-001 prereg. §7.4)",
           "flights": {}, "trials": {}}
    for name, sha in flights:
        ulg = C.RAW_FLIGHTS / f"{name}.ulg"
        ok = ulg.exists() and C.sha(ulg) == sha
        if not ok:
            out["flights"][name] = {"error": "missing or SHA-256 differs from the manifest"}
            continue
        out["flights"][name] = dict(flight_facts(name, ulg), sha256_ok=True)
        print(name, out["flights"][name]["transitions"], flush=True)
    key = json.loads((CAMPAIGN / "stage0/KEY.json").read_text())["trials"]
    for _oid, k in sorted(key.items(), key=lambda kv: kv[1]["analysis_id"]):
        ulg = C.RAW_FLIGHTS / f"{k['source_flight_id']}.ulg"
        out["trials"][k["analysis_id"]] = trial_result(k["analysis_id"], k, ulg)
    out["seconds"] = round(time.perf_counter() - t0, 1)
    C.write_json(OUT, out)
    print("done", out["seconds"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
