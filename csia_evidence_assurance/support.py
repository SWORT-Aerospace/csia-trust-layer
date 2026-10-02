"""Is this log inside what CSIA Flight Assurance supports? OFFBOARD ONLY.

The answer is about the ANALYZER's competence on this log, never about the
vehicle's health:
- SUPPORTED: the vehicle, PX4 schema, topics and logging are inside the
  support matrix (`support_matrix.json`), and the measurable conditions hold;
- PARTIAL: the analysis runs, but some evidence cannot be produced or will
  be refused (each reason is listed);
- UNSUPPORTED: the vehicle is outside every profile. PX4's own monitor
  events are still listed, but no propulsion conclusion is offered.

Why it exists: a real FMUv5 boat log was analysed with the multirotor-quad
profile and the report never said the vehicle was outside the supported
boundary (CSIA PRIME receipt RR-09, research/csia_prime/SIM_TO_REAL_RECEIPTS.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

MATRIX_PATH = Path(__file__).with_name("support_matrix.json")
VEHICLE_TYPES = {0: "unknown", 1: "rotary wing", 2: "fixed wing", 3: "rover or boat", 4: "airship"}


def matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text())


def inspect(path) -> dict:
    """What the log says about the vehicle and its logging (header, parameters, timing)."""
    from pyulog import ULog
    want = ["vehicle_status", "vehicle_land_detected", "vehicle_angular_velocity", "actuator_motors",
            "esc_status", "control_allocator_status", "battery_status"]
    u = ULog(str(path), want, False)
    info, params = u.msg_info_dict, u.initial_parameters
    D = {d.name: d.data for d in u.data_list if d.multi_id == 0}
    t0 = u.start_timestamp
    vt, is_vtol = None, None
    vs = D.get("vehicle_status")
    if vs is not None and len(vs["timestamp"]):
        if "vehicle_type" in vs:
            vt = int(np.bincount(np.asarray(vs["vehicle_type"], int)).argmax())
        if "is_vtol" in vs:
            is_vtol = bool(np.any(vs["is_vtol"]))
    gaps = {}
    for name in ("actuator_motors", "esc_status", "control_allocator_status", "battery_status",
                 "vehicle_angular_velocity"):
        d = D.get(name)
        if d is not None and len(d["timestamp"]) > 2:
            dt = np.diff(d["timestamp"].astype(np.int64)) * 1e-3
            gaps[name] = {"median_ms": round(float(np.median(dt)), 2), "max_ms": round(float(dt.max()), 2)}
    bias = None
    av, ld = D.get("vehicle_angular_velocity"), D.get("vehicle_land_detected")
    if av is not None and ld is not None and len(ld["timestamp"]):
        ta = av["timestamp"].astype(np.int64)
        landed = np.interp(ta, ld["timestamp"].astype(np.int64), np.asarray(ld["landed"], float)) > 0.5
        if landed.sum() > 50:
            bias = [round(float(np.mean(np.asarray(av[f"xyz[{i}]"], float)[landed])), 4) for i in range(3)]
    return {"hardware": info.get("ver_hw", ""), "px4_git": info.get("ver_sw", "")[:12],
            "sys_autostart": params.get("SYS_AUTOSTART"), "mav_type": params.get("MAV_TYPE"),
            "ca_rotor_count": params.get("CA_ROTOR_COUNT"), "vehicle_type": vt, "is_vtol": is_vtol,
            "topics": sorted(D), "intervals": gaps, "dropouts": len(u.dropouts),
            "gyro_mean_while_landed_rad_s": bias, "log_start_us": int(t0)}


def check(info: dict, report: dict | None = None) -> dict:
    mx = matrix()
    reasons, conditions = [], []
    status = "SUPPORTED"
    autostart = int(info["sys_autostart"]) if info.get("sys_autostart") is not None else None
    vt = info.get("vehicle_type")
    vtol = info.get("is_vtol") or (autostart is not None and 13000 <= autostart < 14000)
    if vtol:
        status = "UNSUPPORTED"
        reasons.append("VTOL vehicle: no VTOL profile")
    elif vt is not None and vt != 1:
        status = "UNSUPPORTED"
        reasons.append(f"vehicle type {VEHICLE_TYPES.get(vt, vt)}: outside the multirotor-quad profile")
    elif vt is None and autostart is not None and 50000 <= autostart < 60000:
        status = "UNSUPPORTED"
        reasons.append("rover or boat airframe: outside the multirotor-quad profile")
    rc = info.get("ca_rotor_count")
    if status != "UNSUPPORTED":
        if rc is None:
            status = "PARTIAL"
            reasons.append("no CA_ROTOR_COUNT: PX4 before control allocation; no propulsion evidence")
        elif int(rc) != 4:
            status = "UNSUPPORTED"
            reasons.append(f"CA_ROTOR_COUNT = {int(rc)}: the profile is a quadrotor")
    if status != "UNSUPPORTED":
        missing = [t for t in mx["topics"]["required_for_propulsion"] if t not in info["topics"]]
        if missing:
            status = "PARTIAL"
            reasons.append("missing for propulsion evidence: " + ", ".join(missing))
        for topic, lim in mx["logging"]["max_gap_ms"].items():
            g = info["intervals"].get(topic)
            if g is None:
                continue
            ok = g["max_ms"] <= lim
            conditions.append({"condition": f"{topic} largest gap", "value_ms": g["max_ms"],
                               "limit_ms": lim, "ok": ok})
            if not ok:
                status = "PARTIAL"
                reasons.append(f"{topic} has a {g['max_ms']:.0f} ms gap (> {lim} ms): its evidence is refused there")
        b = info.get("gyro_mean_while_landed_rad_s")
        lim = mx["conditions_checked_per_log"]["gyro_bias_at_rest_rad_s_max"]
        if b is not None:
            worst = max(abs(x) for x in b)
            ok = worst < lim
            conditions.append({"condition": "gyro bias at rest (largest axis)", "value_rad_s": worst,
                               "limit_rad_s": lim, "ok": ok})
            if not ok:
                status = "PARTIAL"
                reasons.append(f"gyro bias at rest {worst:.3f} rad/s (>= {lim}): the compensation "
                               "witness will be refused as not steady")
        if info.get("dropouts"):
            conditions.append({"condition": "logger dropouts", "value": info["dropouts"], "ok": False})
            reasons.append(f"{info['dropouts']} logger dropout(s): evidence over them is refused")
            status = "PARTIAL"
    if report is not None:
        for n in report.get("coverage_report", {}).get("coverage_notices", []):
            if "schema" in n.get("why", ""):
                reasons.append(n["why"])
                if status == "SUPPORTED":
                    status = "PARTIAL"
    return {"status": status, "reasons": reasons, "conditions": conditions,
            "vehicle": {"hardware": info.get("hardware"), "px4_git": info.get("px4_git"),
                        "sys_autostart": info.get("sys_autostart"),
                        "vehicle_type": VEHICLE_TYPES.get(vt, vt), "ca_rotor_count": rc},
            "matrix_version": mx["matrix_version"]}
