#!/usr/bin/env python3
"""Logging and common-clock validation for the apparatus ULogs.

For every topic that must be captured at the simulator step rate, count, over
the armed interval, how many 4 ms SIH steps it covers, how many it misses, and
whether any timestamp falls off the step grid. Also measures the estimator's
delayed fusion horizon (timestamp - timestamp_sample) and the logger dropout
count. Research-only; reads ULogs, writes JSON.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from pyulog import ULog

STEP_TOPICS = ["esc_status", "actuator_outputs_sim", "actuator_motors", "sensor_combined",
               "vehicle_angular_velocity_groundtruth", "vehicle_attitude_groundtruth",
               "vehicle_angular_velocity", "vehicle_attitude", "vehicle_torque_setpoint",
               "vehicle_thrust_setpoint", "rate_ctrl_status", "vehicle_acceleration"]
EKF_TOPICS = ["estimator_innovations", "estimator_innovation_test_ratios", "vehicle_local_position",
              "control_allocator_status", "hover_thrust_estimate"]


def check(path):
    u = ULog(str(path))
    st = u.get_dataset("vehicle_status").data
    armed = st["timestamp"][st["arming_state"] == 2]
    t0, t1 = int(armed[0]), int(armed[-1])
    grid = np.arange(((t0 // 4000) + 1) * 4000, t1, 4000)
    out = {"name": Path(path).stem, "dropouts": len(u.dropouts),
           "armed_s": [(t0) / 1e6, t1 / 1e6], "steps_in_armed_interval": int(len(grid)), "topics": {}}
    for name in STEP_TOPICS + EKF_TOPICS:
        d = u.get_dataset(name).data
        ts = d["timestamp"].astype(np.int64)
        ts = ts[(ts >= grid[0]) & (ts <= grid[-1])]
        uniq = np.unique(ts)
        rec = {"samples": int(len(ts)), "duplicates": int(len(ts) - len(uniq)),
               "off_grid": int(np.sum(uniq % 4000 != 0)),
               "median_period_ms": float(np.median(np.diff(uniq)) / 1000) if len(uniq) > 1 else None}
        if name in STEP_TOPICS:
            rec["steps_missing"] = int(len(np.setdiff1d(grid, uniq)))
        if "timestamp_sample" in d and name.startswith("estimator_innov"):
            lag = (d["timestamp"] - d["timestamp_sample"]).astype(np.int64)
            lag = lag[(d["timestamp"] >= grid[0]) & (d["timestamp"] <= grid[-1])]
            rec["delayed_horizon_ms"] = [float(np.min(lag) / 1000), float(np.median(lag) / 1000),
                                         float(np.max(lag) / 1000)]
        out["topics"][name] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ulogs", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = [check(p) for p in a.ulogs]
    agg = {}
    for name in STEP_TOPICS + EKF_TOPICS:
        recs = [r["topics"][name] for r in rows]
        agg[name] = {"samples": int(sum(x["samples"] for x in recs)),
                     "duplicates": int(sum(x["duplicates"] for x in recs)),
                     "off_grid": int(sum(x["off_grid"] for x in recs)),
                     "median_period_ms": float(np.median([x["median_period_ms"] for x in recs]))}
        if name in STEP_TOPICS:
            agg[name]["steps_missing"] = int(sum(x["steps_missing"] for x in recs))
            agg[name]["steps_expected"] = int(sum(r["steps_in_armed_interval"] for r in rows))
        if "delayed_horizon_ms" in recs[0]:
            agg[name]["delayed_horizon_ms"] = [min(x["delayed_horizon_ms"][0] for x in recs),
                                               float(np.median([x["delayed_horizon_ms"][1] for x in recs])),
                                               max(x["delayed_horizon_ms"][2] for x in recs)]
    res = {"n_logs": len(rows), "dropouts_total": int(sum(r["dropouts"] for r in rows)),
           "aggregate": agg, "per_log": rows}
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({"n_logs": res["n_logs"], "dropouts_total": res["dropouts_total"], "aggregate": agg}, indent=1))


if __name__ == "__main__":
    main()
