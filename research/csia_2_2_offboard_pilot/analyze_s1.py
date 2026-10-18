#!/usr/bin/env python3
"""Run S1 analysis: the frozen expectations of SITL_SELECTOR_RUN_DESIGN.md
against the log, and the Analyzer on it. NON-CONFIRMATORY. RESEARCH ONLY.

    .venv/bin/python research/csia_2_2_offboard_pilot/analyze_s1.py [--raw DIR]

With the raw ULog (default /home/user/csia_2_2_pilot_raw/S1): reads the
facts the design names from the log, and writes the extract
`data/S1_estimator_extract.npz` (what the PX4 adapter reads). Without it:
re-runs the Analyzer from the committed extract only.

Writes S1_RESULTS.json and reports/S1/report.{json,txt}.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

import common_pilot as C

from csia_evidence_assurance import report as R  # noqa: E402
from csia_evidence_assurance import runs  # noqa: E402
from csia_evidence_assurance.adapters import px4_estimator as PX  # noqa: E402

EXTRACT = C.HERE / "data/S1_estimator_extract.npz"
OUT = C.HERE / "S1_RESULTS.json"
ONSET_S, MAG_BITS = 75.0, (4, 5)


def log_facts(ulg: Path) -> dict:
    """What the design's X1-X5 name, read from the raw log."""
    from pyulog import ULog
    u = ULog(str(ulg), ["estimator_selector_status", "estimator_status", "sensor_selection",
                        "vehicle_magnetometer", "estimator_status_flags"])
    t0 = u.start_timestamp
    sec = lambda us: (np.asarray(us, dtype=np.int64) - t0) * 1e-6  # noqa: E731
    out = {"topics": sorted({f"{d.name}#{d.multi_id}" for d in u.data_list}),
           "SENS_IMU_MODE": u.initial_parameters.get("SENS_IMU_MODE"),
           "EKF2_MULTI_IMU": u.initial_parameters.get("EKF2_MULTI_IMU"),
           "ver_sw": u.msg_info_dict.get("ver_sw")}
    d = u.get_dataset("estimator_selector_status").data
    cnt = d["instance_changed_count"].astype(int)
    ch = np.flatnonzero(np.diff(cnt)) + 1
    out["selector"] = {
        "messages": int(len(cnt)),
        "instances_available": sorted({int(x) for x in d["instances_available"]}),
        "primary_instance": sorted({int(x) for x in d["primary_instance"]}),
        "instance_changed_count_first_last": [int(cnt[0]), int(cnt[-1])],
        "count_changes_at_s": [round(float(sec(d["timestamp"][i])), 3) for i in ch],
        "first_message_s": round(float(sec(d["timestamp"][0])), 3),
        "gyro_fault_detected_ever": bool(np.any(d["gyro_fault_detected"])),
        "accel_fault_detected_ever": bool(np.any(d["accel_fault_detected"]))}
    es = [x for x in u.data_list if x.name == "estimator_status"]
    out["estimator_status_instances"] = sorted(x.multi_id for x in es)
    e = es[0].data
    t = sec(e["timestamp"])
    cm = e["control_mode_flags"].astype(np.uint64)
    mag = np.zeros(len(cm), bool)
    for b in MAG_BITS:
        mag |= ((cm >> np.uint64(b)) & np.uint64(1)).astype(bool)
    after = t >= ONSET_S
    off = np.flatnonzero(after & ~mag)
    out["mag_fusion"] = {
        "fused_at_onset": bool(mag[np.searchsorted(t, ONSET_S)]),
        "first_unfused_after_onset_s": round(float(t[off[0]]), 3) if len(off) else None,
        "refused_after_unfusing": bool(len(off) and np.any(mag[off[0]:])),
        "hdg_test_ratio_nan_after_unfusing": (bool(np.all(np.isnan(e["hdg_test_ratio"][off[0]:])))
                                              if len(off) else None)}
    yaw_bits = {22: "gnss_yaw", 13: "ev_yaw", 46: "yaw_manual"}
    out["other_yaw_sources_after_onset"] = sorted(
        n for b, n in yaw_bits.items()
        if np.any(((cm[after] >> np.uint64(b)) & np.uint64(1)).astype(bool)))
    ff = e["filter_fault_flags"].astype(np.int64) & PX.FAULT_MASK
    out["filter_fault_flags_0_15_ever"] = bool(np.any(ff))
    vm = u.get_dataset("vehicle_magnetometer").data
    out["vehicle_magnetometer_last_s"] = round(float(sec(vm["timestamp"][-1])), 3)
    ss = u.get_dataset("sensor_selection").data
    out["sensor_selection"] = {"messages": int(len(ss["timestamp"])),
                               "gyro_device_ids": sorted({int(x) for x in ss["gyro_device_id"]})}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="/home/user/csia_2_2_pilot_raw/S1")
    a = ap.parse_args()
    raw = Path(a.raw)
    res = {"label": "NON-CONFIRMATORY; run S1, SITL_SELECTOR_RUN_DESIGN.md frozen at e58eaed"}
    ulg = raw / "S1.ulg"
    if ulg.exists():
        rec = json.loads((raw / "S1.json").read_text())
        res["run"] = {k: rec[k] for k in ("params", "schedule_s", "events_ms", "acks",
                                          "px4_sha256", "logger_topics_sha256", "ulog_sha256",
                                          "ulog_bytes", "wall_s")}
        res["facts"] = log_facts(ulg)
        log = PX.EstimatorLog.from_ulog(ulg)
        EXTRACT.parent.mkdir(exist_ok=True)
        log.to_npz(EXTRACT)
    else:
        prev = json.loads(OUT.read_text())
        res.update({k: prev[k] for k in ("run", "facts")})
    res["extract_sha256"] = C.sha(EXTRACT)
    run = runs.estimator_log(PX.EstimatorLog.from_npz(EXTRACT), tick_s=0.1)
    m = R.machine_report(run.results, run.inputs, run.gate, run.contracts)
    d = C.HERE / "reports/S1"
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.json").write_bytes(R.dumps(m))
    (d / "report.txt").write_text(R.human_report(m))
    rej, mism, stamps, hdg = {}, 0, set(), []
    for r in run.results:
        for x in r.evidence["rejected"]:
            k = f"{x['status']}:{x['reasons'][0].split(':')[0]}"
            rej[k] = rej.get(k, 0) + 1
            mism += x["status"] == "CONFIGURATION_MISMATCH"
    for e in run.analyzer.store.values():
        stamps.add(json.dumps(e.config_epoch, sort_keys=True))
    est = runs.PX.EstimatorProducer(PX.EstimatorLog.from_npz(EXTRACT))
    for i in est._stream:
        if i["ts"] - est.log.t0_us >= (ONSET_S - 1) * 1e6:
            hdg.append(((i["ts"] - est.log.t0_us) * 1e-6, bool(np.isnan(float(i["row"]["hdg_test_ratio"])))))
    first_na = next((round(t, 3) for t, nan in hdg if t >= ONSET_S and nan), None)
    cfg_changes = [{"from": iv["from"], "changed": iv["changed"]} for iv in m["timeline"]
                   if "epochs" in iv["changed"]]
    res["analyzer"] = {"lane_mode": est._lane_mode, "ticks": m["ticks"], "intervals": m["intervals"],
                       "rejected": dict(sorted(rej.items())), "configuration_mismatch": mism,
                       "final_stamps": sorted(stamps),
                       "first_hdg_not_applicable_after_onset_s": first_na,
                       "configuration_change_intervals": cfg_changes,
                       "report_sha256": C.sha(d / "report.json")}
    f, an = res["facts"], res["analyzer"]
    sel = f["selector"]
    res["expectations"] = {
        "X1": sel["instances_available"] == [1] and sel["primary_instance"] == [0],
        "X2": len(sel["count_changes_at_s"]) <= 1 and sel["instance_changed_count_first_last"][1] == 1,
        "X3": f["estimator_status_instances"] == [0],
        "X4": (f["mag_fusion"]["first_unfused_after_onset_s"] is not None
               and f["mag_fusion"]["first_unfused_after_onset_s"] - ONSET_S <= 5.0),
        "X5": not f["filter_fault_flags_0_15_ever"],
        "A1": an["lane_mode"] == "SELECTOR",
        "A2": an["configuration_mismatch"] == 0,
        "A3": first_na is not None,
        "M2_lane_epoch_changes_after_initial": max(0, len(sel["count_changes_at_s"]) - 1),
    }
    C.write_json(OUT, res)
    print(json.dumps({k: res[k] for k in ("facts", "analyzer", "expectations")}, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
