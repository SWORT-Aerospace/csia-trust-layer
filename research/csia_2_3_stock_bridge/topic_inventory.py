#!/usr/bin/env python3
"""Phase 1: what the 66 XSYS-001 flight logs actually contain. RESEARCH ONLY.

    .venv/bin/python research/csia_2_3_stock_bridge/topic_inventory.py [--workers N]

For every topic instance in every log:
- message count;
- first and last time;
- median and 99th-percentile interval;
- gaps longer than 3 x the median interval (dropouts);
- fields, and per numeric field whether it varies, is constant, is all
  zero, or has NaN.

Also:
- the logger's own dropouts;
- the PX4 log messages (level, module);
- selected parameters.

**Stock or custom?** Each topic is compared with PX4 547e2ca's default
logging (`src/modules/logger/logged_topics.cpp`, `add_default_topics`;
non-SITL interval) and with the XSYS-001 custom list
(`research/px4_actuator_effectiveness/config/logger_topics.txt`), so a claim
that needs a rate only the custom list gives is visible.

Writes TOPIC_INVENTORY.json, TOPIC_COVERAGE_MATRIX.csv, and per-flight
details to /home/user/csia_2_3_raw/inventory/ (not in git).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import common_23 as C

#: PX4 547e2ca add_default_topics() logging interval in ms (0 = every
#: publication), for a real board. None: not in the default profile.
STOCK_INTERVAL_MS = {
    "esc_status": 100, "actuator_motors": 100, "actuator_outputs": 100,
    "control_allocator_status": 200, "rate_ctrl_status": 200, "battery_status": 200,
    "estimator_status": 200, "estimator_status_flags": 10, "estimator_event_flags": 10,
    "estimator_innovation_test_ratios": 500, "estimator_innovations": 500,
    "estimator_sensor_bias": 1000, "estimator_fusion_control": 1000,
    "vehicle_local_position": 100, "vehicle_global_position": 200, "vehicle_attitude": 50,
    "vehicle_angular_velocity": 20, "vehicle_acceleration": 50, "vehicle_status": 0,
    "vehicle_control_mode": 0, "failure_detector_status": 100, "cpuload": 0,
    "sensor_selection": 0, "sensor_gps": 1000, "vehicle_gps_position": 100,
    "vehicle_air_data": 200, "vehicle_magnetometer": 200, "telemetry_status": 1000,
    "system_power": 500, "logger_status": 200, "failsafe_flags": 0, "sensor_combined": 0,
    "vehicle_torque_setpoint": 20, "vehicle_thrust_setpoint": 20, "vehicle_rates_setpoint": 20,
    "vehicle_attitude_setpoint": 50, "hover_thrust_estimate": 100, "vehicle_land_detected": 0,
    "sensors_status_imu": 200, "vehicle_imu_status": 1000, "vehicle_imu": 500,
    "event": 0, "actuator_armed": 0, "vehicle_command": 0, "parameter_update": 0,
    "sensor_accel": 1000, "sensor_gyro": 1000, "sensor_mag": 1000, "sensor_baro": 1000,
    "manual_control_setpoint": 200, "trajectory_setpoint": 200, "position_setpoint_triplet": 200,
    "vehicle_local_position_setpoint": 100, "home_position": 0, "navigator_status": 0,
    "mission_result": 0, "takeoff_status": 1000, "yaw_estimator_status": 1000,
}
#: Topics that exist only in simulation; never evidence.
SIM_ONLY = {"vehicle_angular_velocity_groundtruth", "vehicle_attitude_groundtruth",
            "vehicle_local_position_groundtruth", "vehicle_global_position_groundtruth",
            "actuator_outputs_sim"}
#: Topics the brief names (Phase 1).
BRIEF = ["esc_status", "actuator_motors", "actuator_outputs", "control_allocator_status",
         "battery_status", "estimator_status", "estimator_status_flags", "vehicle_local_position",
         "vehicle_global_position", "vehicle_attitude", "vehicle_angular_velocity",
         "vehicle_acceleration", "vehicle_status", "vehicle_control_mode",
         "failure_detector_status", "cpuload", "sensor_selection", "sensor_gps",
         "vehicle_air_data", "vehicle_magnetometer", "telemetry_status"]
PARAMS = ["SENS_IMU_MODE", "SYS_HITL", "SDLOG_PROFILE", "CA_ROTOR_COUNT", "SIH_MOT_EFF1",
          "BAT1_SOURCE", "BAT1_N_CELLS", "BAT_LOW_THR", "BAT_CRIT_THR", "FD_FAIL_P",
          "FD_FAIL_R", "FD_ACT_EN", "FD_ACT_MOT_THR", "FD_ACT_MOT_C2T", "FD_ACT_MOT_TOUT",
          "FD_EXT_ATS_EN", "COM_ACT_FAIL_ACT", "EKF2_MULTI_IMU", "EKF2_MULTI_MAG",
          "SIH_VEHICLE_TYPE", "CA_AIRFRAME", "MC_AIRMODE"]


def _field_class(v: np.ndarray) -> str:
    if v.size == 0:
        return "empty"
    if v.dtype.kind == "f":
        nan = np.isnan(v)
        if nan.all():
            return "all_nan"
        w = v[~nan]
        cls = "all_zero" if np.all(w == 0) else ("constant" if np.all(w == w[0]) else "varies")
        return cls + ("+nan" if nan.any() else "")
    if v.dtype.kind in "iub":
        return "all_zero" if np.all(v == 0) else ("constant" if np.all(v == v[0]) else "varies")
    return "other"


def one(path: str) -> dict:
    from pyulog import ULog
    u = ULog(path)
    t0 = u.start_timestamp
    out = {"flight": Path(path).stem, "duration_s": round((u.last_timestamp - t0) * 1e-6, 3),
           "logger_dropouts": {"count": len(u.dropouts),
                               "total_ms": int(sum(d.duration for d in u.dropouts))},
           "messages": [{"t": round((m.timestamp - t0) * 1e-6, 3), "level": m.log_level_str(),
                         "text": m.message.strip()} for m in u.logged_messages],
           "params": {p: u.initial_parameters.get(p) for p in PARAMS},
           "topics": {}}
    for d in u.data_list:
        ts = d.data["timestamp"].astype(np.int64)
        dt = np.diff(ts) * 1e-6 if ts.size > 1 else np.array([])
        med = float(np.median(dt)) if dt.size else None
        gaps = dt[dt > 3 * med] if med else np.array([])
        fields = {}
        for f in d.field_data:
            n = f.field_name
            if n == "timestamp" or n.startswith("_padding"):
                continue
            fields[n] = _field_class(d.data[n])
        out["topics"][f"{d.name}#{d.multi_id}"] = {
            "n": int(ts.size), "first_s": round((int(ts[0]) - t0) * 1e-6, 3) if ts.size else None,
            "last_s": round((int(ts[-1]) - t0) * 1e-6, 3) if ts.size else None,
            "median_dt_s": round(med, 6) if med else None,
            "p99_dt_s": round(float(np.percentile(dt, 99)), 6) if dt.size else None,
            "gaps_over_3x": int(gaps.size), "max_gap_s": round(float(dt.max()), 4) if dt.size else None,
            "fields": fields}
    return out


def aggregate(flights: list) -> dict:
    topics: dict = {}
    for f in flights:
        for key, t in f["topics"].items():
            name, inst = key.rsplit("#", 1)
            a = topics.setdefault(name, {"flights": set(), "instances": set(), "rates_hz": [],
                                         "gaps": 0, "max_gap_s": 0.0, "fields": {}})
            a["flights"].add(f["flight"])
            a["instances"].add(int(inst))
            if t["median_dt_s"]:
                a["rates_hz"].append(1.0 / t["median_dt_s"])
            a["gaps"] += t["gaps_over_3x"]
            a["max_gap_s"] = max(a["max_gap_s"], t["max_gap_s"] or 0.0)
            for fn, cls in t["fields"].items():
                a["fields"].setdefault(fn, {}).setdefault(cls, 0)
                a["fields"][fn][cls] += 1
    out = {}
    n = len(flights)
    for name, a in sorted(topics.items()):
        r = sorted(a["rates_hz"])
        stock = STOCK_INTERVAL_MS.get(name)
        out[name] = {
            "present_in": len(a["flights"]), "of": n, "instances": sorted(a["instances"]),
            "rate_hz_median": round(float(np.median(r)), 2) if r else None,
            "rate_hz_range": [round(r[0], 2), round(r[-1], 2)] if r else None,
            "dropouts_over_3x_total": a["gaps"], "max_gap_s": round(a["max_gap_s"], 4),
            "stock_interval_ms": stock,
            "stock_rate_hz_max": (None if stock is None else ("every publication" if stock == 0
                                                              else round(1000.0 / stock, 2))),
            "sim_only": name in SIM_ONLY,
            "fields": {fn: dict(sorted(c.items())) for fn, c in sorted(a["fields"].items())}}
    for b in BRIEF:
        out.setdefault(b, {"present_in": 0, "of": n, "sim_only": False,
                           "stock_interval_ms": STOCK_INTERVAL_MS.get(b)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    paths = sorted(str(p) for p in C.RAW_FLIGHTS.glob("*.ulg"))
    with ProcessPoolExecutor(a.workers) as ex:
        flights = list(ex.map(one, paths))
    raw = C.OUT_RAW / "inventory"
    raw.mkdir(parents=True, exist_ok=True)
    for f in flights:
        (raw / f"{f['flight']}.json").write_text(json.dumps(f, indent=1, sort_keys=True))
    agg = aggregate(flights)
    msgs: dict = {}
    for f in flights:
        for m in f["messages"]:
            mod = m["text"].split("]", 1)[0].lstrip("[") if m["text"].startswith("[") else "?"
            k = f"{m['level']}|{mod}"
            msgs[k] = msgs.get(k, 0) + 1
    params: dict = {}
    for f in flights:
        for p, v in f["params"].items():
            params.setdefault(p, set()).add(v)
    out = {"label": "Phase 1 topic inventory; 66 XSYS-001 SITL logs (PX4 547e2ca, SIH)",
           "flights": len(flights),
           "logger_dropouts": {"flights_with_any": sum(1 for f in flights if f["logger_dropouts"]["count"]),
                               "total_ms": sum(f["logger_dropouts"]["total_ms"] for f in flights)},
           "duration_s": {"min": min(f["duration_s"] for f in flights),
                          "max": max(f["duration_s"] for f in flights),
                          "total": round(sum(f["duration_s"] for f in flights), 1)},
           "log_messages_by_level_and_module": dict(sorted(msgs.items())),
           "params": {p: sorted(map(str, v)) for p, v in sorted(params.items())},
           "brief_topics": BRIEF,
           "topics": agg}
    C.write_json(C.HERE / "TOPIC_INVENTORY.json", out)
    names = sorted(agg)
    with open(C.HERE / "TOPIC_COVERAGE_MATRIX.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["topic", "in_brief", "sim_only", "stock_interval_ms"] + [f["flight"] for f in flights])
        for nm in names:
            row = [nm, nm in BRIEF, agg[nm]["sim_only"], agg[nm].get("stock_interval_ms")]
            for f in flights:
                rates = [1.0 / t["median_dt_s"] for k, t in f["topics"].items()
                         if k.rsplit("#", 1)[0] == nm and t["median_dt_s"]]
                row.append(round(max(rates), 1) if rates else 0)
            w.writerow(row)
    print(json.dumps({k: out[k] for k in ("flights", "logger_dropouts", "duration_s")}, indent=1))
    for b in BRIEF:
        t = agg[b]
        print(b, t["present_in"], t.get("rate_hz_median"), t.get("stock_interval_ms"))


if __name__ == "__main__":
    main()
