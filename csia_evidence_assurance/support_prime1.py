"""Is this log inside what CSIA Flight Assurance PRIME-1 supports? OFFBOARD ONLY.

The answer is about the ANALYZER's competence on this log, never about the
vehicle's health. It is decided BEFORE any diagnostic interpretation, from the
log's header, parameters and topics (`support_contract_prime1.json`):

| state | meaning | what the Analyzer does |
|---|---|---|
| SUPPORTED | vehicle, PX4 version, schema, topics and logging inside a supported configuration | full analysis |
| PARTIAL | analysis runs; some evidence missing, refused or untested here | full analysis, every reason listed |
| UNKNOWN_VERSION | the log does not say which PX4 produced it | full analysis, every conclusion qualified |
| UNSUPPORTED_SCHEMA | not a readable PX4 ULog, or without the topics any analysis needs | log integrity only |
| UNSUPPORTED_VEHICLE_CONFIGURATION | the vehicle is outside every profile | generic analysis only; no diagnostic interpretation |

An unsupported vehicle is NOT a broken log: the report says what was
detected, which profile would have been applied, which vehicle classes are
supported, and what generic analysis remains safe.

PRIME's `support.py` (and its matrix) stay as they were for `assure
--release prime`.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

CONTRACT_PATH = Path(__file__).with_name("support_contract_prime1.json")
VEHICLE_TYPES = {0: "unknown", 1: "rotary wing", 2: "fixed wing", 3: "rover or boat", 4: "airship"}
TESTED_FULL_GIT = ("547e2ca",)
REQUESTED_PROFILE = "multirotor-quad r1"
#: Without these, no analysis of any kind is possible (generic analysis only reads them).
MINIMUM_TOPICS = ("vehicle_status",)
PROPULSION_TOPICS = ("actuator_motors", "esc_status", "control_allocator_status", "vehicle_angular_velocity",
                     "vehicle_status", "vehicle_land_detected")
MAX_GAP_MS = {"actuator_motors": 300, "esc_status": 300, "control_allocator_status": 600,
              "vehicle_angular_velocity": 60}
GYRO_BIAS_MAX = 0.05
STATE_ORDER = ("UNSUPPORTED_VEHICLE_CONFIGURATION", "UNSUPPORTED_SCHEMA", "UNKNOWN_VERSION", "PARTIAL", "SUPPORTED")


def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text())


def decode_release(v) -> str | None:
    """PX4's ver_sw_release (major<<24 | minor<<16 | patch<<8 | type) as text, or None."""
    if not v:
        return None
    v = int(v)
    major, minor, patch, typ = (v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255
    if major == 0 and minor == 0 and patch == 0:
        return None
    kind = {255: "", 0: "-dev", 64: "-alpha", 128: "-beta", 192: "-rc"}.get(typ, f"-type{typ}")
    return f"v{major}.{minor}.{patch}{kind}"


def inspect(path) -> dict:
    """What the log says about itself. Never raises for a bad log: an unreadable file is
    reported as such (UNSUPPORTED_SCHEMA)."""
    path = Path(path)
    out = {"file": path.name, "readable": False}
    try:
        from pyulog import ULog
        want = ["vehicle_status", "vehicle_land_detected", "vehicle_angular_velocity", "actuator_motors",
                "esc_status", "control_allocator_status", "battery_status", "actuator_outputs",
                "actuator_controls_0", "estimator_status", "failure_detector_status"]
        u = ULog(str(path), want, False)
    except Exception as exc:  # noqa: BLE001 - any parse failure is the answer itself
        out["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return out
    info, params = u.msg_info_dict, u.initial_parameters
    D = {d.name: d.data for d in u.data_list if d.multi_id == 0}
    vt, is_vtol = None, None
    vs = D.get("vehicle_status")
    if vs is not None and len(vs["timestamp"]):
        if "vehicle_type" in vs:
            vt = int(np.bincount(np.asarray(vs["vehicle_type"], int)).argmax())
        if "is_vtol" in vs:
            is_vtol = bool(np.any(vs["is_vtol"]))
    gaps = {}
    for name in MAX_GAP_MS:
        d = D.get(name)
        if d is not None and len(d["timestamp"]) > 2:
            dt = np.diff(d["timestamp"].astype(np.int64)) * 1e-3
            gaps[name] = {"median_ms": round(float(np.median(dt)), 2), "max_ms": round(float(dt.max()), 2)}
    esc_rpm = None
    es = D.get("esc_status")
    if es is not None:
        keys = [k for k in es if k.endswith(".esc_rpm")]
        esc_rpm = bool(keys) and any(np.any(np.asarray(es[k]) != 0) for k in keys)
    bias = None
    av, ld = D.get("vehicle_angular_velocity"), D.get("vehicle_land_detected")
    if av is not None and ld is not None and len(ld["timestamp"]) and "landed" in ld:
        ta = av["timestamp"].astype(np.int64)
        landed = np.interp(ta, ld["timestamp"].astype(np.int64), np.asarray(ld["landed"], float)) > 0.5
        if landed.sum() > 50:
            bias = [round(float(np.mean(np.asarray(av[f"xyz[{i}]"], float)[landed])), 4) for i in range(3)]
    git = str(info.get("ver_sw", ""))
    out.update({"readable": True, "hardware": info.get("ver_hw", ""), "px4_git": git[:12],
                "px4_release": decode_release(info.get("ver_sw_release")),
                "sys_autostart": params.get("SYS_AUTOSTART"), "ca_rotor_count": params.get("CA_ROTOR_COUNT"),
                "vehicle_type": vt, "is_vtol": is_vtol, "topics": sorted(D), "intervals": gaps,
                "esc_rpm_present": esc_rpm, "dropouts": len(u.dropouts),
                "gyro_mean_while_landed_rad_s": bias})
    return out


def _vehicle(info) -> dict:
    autostart = int(info["sys_autostart"]) if info.get("sys_autostart") is not None else None
    vt, rc = info.get("vehicle_type"), info.get("ca_rotor_count")
    detected = VEHICLE_TYPES.get(vt, "unknown") if vt is not None else "unknown (no vehicle_status.vehicle_type)"
    why = None
    if info.get("is_vtol") or (autostart is not None and 13000 <= autostart < 14000):
        why, detected = "VTOL", "VTOL"
    elif vt is not None and vt != 1:
        why = detected
    elif vt is None and autostart is not None and 50000 <= autostart < 60000:
        why, detected = "rover or boat airframe", "rover or boat"
    elif rc is not None and int(rc) != 4:
        why, detected = f"{int(rc)}-rotor multirotor", f"multirotor with {int(rc)} rotors"
    return {"detected": detected, "sys_autostart": autostart, "ca_rotor_count": rc,
            "requested_profile": REQUESTED_PROFILE,
            "supported_vehicle_classes": ["multirotor quadrotor, X configuration (CA_ROTOR_COUNT 4, not VTOL)"],
            "state": "UNSUPPORTED_VEHICLE_CONFIGURATION" if why else "SUPPORTED_VEHICLE", "why": why}


def check(info: dict, report: dict | None = None) -> dict:
    """The support decision. `report` (optional) adds the analysis's own schema notices."""
    c = contract()
    reasons, conditions = [], []
    dims = {}
    if not info.get("readable"):
        dims["schema"] = "UNSUPPORTED_SCHEMA"
        reasons.append(f"not a readable PX4 ULog ({info.get('error', 'unknown error')})")
        return _result("UNSUPPORTED_SCHEMA", dims, reasons, conditions, info, None, c)
    veh = _vehicle(info)
    dims["vehicle"] = veh["state"]
    if veh["state"] != "SUPPORTED_VEHICLE":
        reasons.append(f"vehicle: {veh['why']}; the only profile is {REQUESTED_PROFILE}")
    topics = set(info["topics"])
    missing_min = [t for t in MINIMUM_TOPICS if t not in topics]
    if missing_min:
        dims["schema"] = "UNSUPPORTED_SCHEMA"
        reasons.append("missing for any analysis: " + ", ".join(missing_min))
    else:
        missing = [t for t in PROPULSION_TOPICS if t not in topics]
        if info.get("ca_rotor_count") is None or ("actuator_motors" not in topics and "actuator_controls_0" in topics):
            dims["schema"] = "PARTIAL"
            reasons.append("PX4 before control allocation (no CA_ROTOR_COUNT or actuator_motors): "
                           "no propulsion evidence")
        elif missing:
            dims["schema"] = "PARTIAL"
            reasons.append("missing for propulsion evidence: " + ", ".join(missing))
        elif info.get("esc_rpm_present") is False:
            dims["schema"] = "PARTIAL"
            reasons.append("esc_status carries no RPM: no telemetry evidence and no propulsion event discovery")
        else:
            dims["schema"] = "SUPPORTED"
    git, rel = info.get("px4_git") or "", info.get("px4_release")
    if any(git.startswith(g) for g in TESTED_FULL_GIT):
        dims["version"] = "TESTED"
    elif rel:
        dims["version"] = "UNTESTED_VERSION"
        reasons.append(f"PX4 {rel} ({git[:8]}): not among the versions tested for full analysis "
                       f"({', '.join(TESTED_FULL_GIT)}, SITL); no validation exists for this version")
    else:
        dims["version"] = "UNKNOWN_VERSION"
        reasons.append("the log does not record a PX4 release version (ver_sw_release); git "
                       f"{git[:8] or 'unknown'} is not a tested build")
    log_ok = True
    for topic, lim in MAX_GAP_MS.items():
        g = info["intervals"].get(topic)
        if g is None:
            continue
        ok = g["max_ms"] <= lim
        conditions.append({"condition": f"{topic} largest gap", "value_ms": g["max_ms"], "limit_ms": lim, "ok": ok})
        if not ok:
            log_ok = False
            reasons.append(f"{topic} has a {g['max_ms']:.0f} ms gap (> {lim} ms): its evidence is refused there")
    b = info.get("gyro_mean_while_landed_rad_s")
    if b is not None:
        worst = max(abs(x) for x in b)
        ok = worst < GYRO_BIAS_MAX
        conditions.append({"condition": "gyro bias at rest (largest axis)", "value_rad_s": worst,
                           "limit_rad_s": GYRO_BIAS_MAX, "ok": ok})
        if not ok:
            log_ok = False
            reasons.append(f"gyro bias at rest {worst:.3f} rad/s (>= {GYRO_BIAS_MAX}): the compensation "
                           "witness will be refused as not steady")
    if info.get("dropouts"):
        log_ok = False
        conditions.append({"condition": "logger dropouts", "value": info["dropouts"], "ok": False})
        reasons.append(f"{info['dropouts']} logger dropout(s): evidence over them is refused")
    dims["logging"] = "OK" if log_ok else "PARTIAL"
    if report is not None:
        for n in report.get("coverage_report", {}).get("coverage_notices", []):
            if "schema" in n.get("why", ""):
                reasons.append(n["why"])
                if dims.get("schema") == "SUPPORTED":
                    dims["schema"] = "PARTIAL"
    if dims["vehicle"] != "SUPPORTED_VEHICLE":
        state = "UNSUPPORTED_VEHICLE_CONFIGURATION"
    elif dims["schema"] == "UNSUPPORTED_SCHEMA":
        state = "UNSUPPORTED_SCHEMA"
    elif dims["version"] == "UNKNOWN_VERSION":
        state = "UNKNOWN_VERSION"
    elif dims["schema"] == "PARTIAL" or dims["logging"] == "PARTIAL" or dims["version"] == "UNTESTED_VERSION":
        state = "PARTIAL"
    else:
        state = "SUPPORTED"
    return _result(state, dims, reasons, conditions, info, veh, c)


def _result(state, dims, reasons, conditions, info, veh, c) -> dict:
    withheld = state in ("UNSUPPORTED_VEHICLE_CONFIGURATION", "UNSUPPORTED_SCHEMA")
    config = {"UNSUPPORTED_SCHEMA": "not-ulog"}.get(state)
    if config is None and veh is not None:
        if veh["state"] != "SUPPORTED_VEHICLE":
            d = veh["detected"]
            config = ("vtol" if d == "VTOL" else "rover-boat" if "rover" in d else "fixed-wing" if "fixed" in d
                      else "other-multirotor")
        elif dims.get("schema") == "PARTIAL" and "before control allocation" in " ".join(reasons):
            config = "quadx-pre-allocation"
        elif dims.get("schema") == "PARTIAL" and "no RPM" in " ".join(reasons):
            config = "quadx-no-esc-telemetry"
        else:
            config = "quadx-allocation-esc"
    level = next((x["validation_level"] for x in c["configurations"] if x["id"] == config), None)
    return {"status": state, "dimensions": dims, "reasons": reasons, "conditions": conditions,
            "configuration": config, "validation_level": level,
            "interpretation": "WITHHELD" if withheld else "FULL",
            "generic_analysis_safe": c["generic_analysis_when_withheld"] if withheld else None,
            "vehicle": veh, "px4": {"release": info.get("px4_release"), "git": info.get("px4_git"),
                                    "hardware": info.get("hardware")},
            "contract_version": c["contract_version"]}
