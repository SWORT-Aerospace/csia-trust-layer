#!/usr/bin/env python3
"""Phases 3-7: what stock PX4 signals show around the XSYS-001 motor fault.
RESEARCH ONLY. NON-CONFIRMATORY. Evidence for the claim register, not a
producer.

    .venv/bin/python research/csia_2_3_stock_bridge/investigate_stock.py

Reads the extracts of `extract_stock.py`, decimated to PX4 547e2ca's
default logging intervals. Uses ONSET_TRUTH.json only to place the
comparison windows:
- PRE:  onset - 5 s .. onset;
- EARLY: onset + 0.5 .. + 2 s;
- LATE:  onset + 10 .. + 15 s (XSYS-001's T3);
- the same windows around the benign change in the 11 NB flights.

CANDIDATE STATISTICS
--------------------
Per motor m, with c = `actuator_motors.control`, rpm = `esc_status.esc_rpm`,
f = THR_MDL_FAC, T(c) = (1 - f) c + f c^2 (PX4's thrust model):

| name | definition | separates |
|---|---|---|
| q_m (telemetry response) | (rpm_m^2 / T(c_m)) / median over all motors of (rpm_j^2 / T(c_j)) | TELEMETRY: reported rotor response per unit commanded thrust, against the other rotors |
| kappa_m (compensation) | c_m / median over all motors of c_j | COMMAND: the allocator asking one motor for more than the others |
| unallocated torque | norm of `control_allocator_status.unallocated_torque` | ALLOCATION: demand not achieved |
| saturation | `actuator_saturation[m]` != 0 | ALLOCATION |
| integrators | roll and pitch rate integrators | CONTROLLER COMPENSATION (context) |
| body-rate response | roll and pitch rate in onset + 0..0.2 s against PRE, on the loss axis | PHYSICAL VEHICLE RESPONSE |
| power | `battery_status.voltage_v`, `current_average_a`, `warning` | POWER |
| PX4 failure detector | flags, `imbalanced_prop_metric` | PX4's own monitors |
| cpuload | `cpuload.load` | COMPUTE (SITL host) |

Writes STOCK_EVIDENCE_INVESTIGATION.json.
"""
from __future__ import annotations

import json

import numpy as np

import common_23 as C

from csia_evidence_assurance import stock_stats as SS  # noqa: E402
from csia_evidence_assurance.stock_log import StockLog  # noqa: E402

EXTRACTS = C.OUT_RAW / "extracts"
WIN = {"PRE": (-5.0, 0.0), "EARLY": (0.5, 2.0), "LATE": (10.0, 15.0), "T1": (0.0, 0.2)}


def thrust_model(c, f):
    c = np.clip(c, 0.0, 1.0)
    return (1.0 - f) * c + f * c * c


def zoh(t_src, v_src, t_dst):
    i = np.searchsorted(t_src, t_dst, side="right") - 1
    out = np.full((len(t_dst),) + v_src.shape[1:], np.nan)
    ok = i >= 0
    out[ok] = v_src[i[ok]]
    return out


def motor_series(s: StockLog):
    """The product's own definitions (stock_stats), on the stock log."""
    ms = SS.motor_series(s)
    return ms.t_esc, ms.q, ms.t_cmd, ms.kappa, None


def wmean(t, v, onset, w):
    a, b = WIN[w]
    m = (t >= onset + a) & (t < onset + b)
    if v.ndim == 1:
        x = v[m]
        x = x[np.isfinite(x)]
        return float(np.mean(x)) if x.size else float("nan")
    out = []
    for k in range(v.shape[1]):
        x = v[m, k]
        x = x[np.isfinite(x)]
        out.append(float(np.mean(x)) if x.size else float("nan"))
    return out


def auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    pos, neg = pos[np.isfinite(pos)], neg[np.isfinite(neg)]
    if not pos.size or not neg.size:
        return None
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return round(float(gt / (pos.size * neg.size)), 4)


def per_flight(name, truth):
    s = StockLog.from_npz(EXTRACTS / f"{name}.npz").decimate()
    on = truth["onset_s"]
    t, q, kt, kappa, c_at = motor_series(s)
    fl = s.in_flight(t)
    qf = np.where(fl[:, None], q, np.nan)
    flk = s.in_flight(kt)
    kf = np.where(flk[:, None], kappa, np.nan)
    out = {"flight": name, "condition": truth["condition"], "eta": truth["eta"], "onset_s": on,
           "rates_hz": {k: round(1.0 / float(np.median(np.diff(v["t"]))), 2)
                        for k, v in s.topics.items() if len(v["t"]) > 2},
           "airborne_s": round(float(fl.sum() * np.median(np.diff(t))), 2)}
    for w in ("PRE", "EARLY", "LATE"):
        out[f"q_{w}"] = wmean(t, qf, on, w)
        out[f"kappa_{w}"] = wmean(kt, kf, on, w)
    # allocation
    ca = s.topics["control_allocator_status"]
    ut = np.sqrt(sum(ca[f"unallocated_torque[{i}]"] ** 2 for i in range(3)))
    sat = np.stack([ca[f"actuator_saturation[{m}]"] for m in range(s.n_motors)], 1)
    for w in ("PRE", "EARLY", "LATE"):
        out[f"unalloc_torque_{w}"] = wmean(ca["t"], ut, on, w)
        out[f"sat_any_{w}"] = wmean(ca["t"], (sat != 0).any(axis=1).astype(float), on, w)
        out[f"torque_achieved_{w}"] = wmean(ca["t"], ca["torque_setpoint_achieved"], on, w)
    out["sat_values"] = sorted({int(v) for v in np.unique(sat)})
    # controller integrators
    rc = s.topics["rate_ctrl_status"]
    for w in ("PRE", "LATE"):
        out[f"integ_{w}"] = [wmean(rc["t"], rc[k], on, w) for k in ("rollspeed_integ",
                                                                       "pitchspeed_integ")]
    # physical response on motor 0's loss axis (rotor geometry from parameters)
    px, py = s.params["CA_ROTOR0_PX"], s.params["CA_ROTOR0_PY"]
    axis = np.array([py, -px], float)
    axis /= np.linalg.norm(axis)
    av = s.topics["vehicle_angular_velocity"]
    g = np.stack([av["xyz[0]"], av["xyz[1]"]], 1)
    base = wmean(av["t"], g, on, "PRE")
    m1 = (av["t"] >= on) & (av["t"] < on + 0.2)
    out["dyn_T1_samples"] = int(m1.sum())
    out["dyn_T1"] = float(((g[m1] - base) @ axis).mean()) if m1.any() else float("nan")
    # power
    b = s.topics["battery_status"]
    out["battery"] = {"voltage_range": [float(b["voltage_v"].min()), float(b["voltage_v"].max())],
                      "current_average_range": [float(b["current_average_a"].min()),
                                                float(b["current_average_a"].max())],
                      "current_a_unique": sorted({float(x) for x in np.unique(b["current_a"])})[:5],
                      "warning_nonzero": int((b["warning"] != 0).sum()),
                      "v_PRE": wmean(b["t"], b["voltage_v"], on, "PRE"),
                      "v_LATE": wmean(b["t"], b["voltage_v"], on, "LATE"),
                      "i_PRE": wmean(b["t"], b["current_average_a"], on, "PRE"),
                      "i_LATE": wmean(b["t"], b["current_average_a"], on, "LATE")}
    fd = s.topics["failure_detector_status"]
    out["failure_detector"] = {k: int((fd[k] != 0).sum()) for k in fd if k not in ("t", "imbalanced_prop_metric")}
    out["imbalanced_prop_metric"] = {"PRE": wmean(fd["t"], fd["imbalanced_prop_metric"], on, "PRE"),
                                     "LATE": wmean(fd["t"], fd["imbalanced_prop_metric"], on, "LATE"),
                                     "max": float(np.nanmax(fd["imbalanced_prop_metric"])),
                                     "threshold_FD_IMB_PROP_THR": s.params.get("FD_IMB_PROP_THR")}
    cl = s.topics["cpuload"]
    out["cpuload"] = {"min": float(cl["load"].min()), "max": float(cl["load"].max())}
    out["esc_current_nonzero"] = int(sum((s.topics["esc_status"][f"esc[{m}].esc_current"] != 0).sum()
                                         for m in range(s.n_motors)))
    out["warnings"] = [m[2] for m in s.messages]
    return out


def main():
    truth = json.loads((C.HERE / "ONSET_TRUTH.json").read_text())["flights"]
    rows = [per_flight(n, truth[n]) for n in sorted(truth)]
    A = [r for r in rows if r["condition"] == "A"]
    N = [r for r in rows if r["condition"] == "NB"]
    summ = {}
    # telemetry response and compensation on motor 0, change against PRE
    for stat in ("q", "kappa"):
        for w in ("EARLY", "LATE"):
            dA = [r[f"{stat}_{w}"][0] - r[f"{stat}_PRE"][0] for r in A]
            dN = [r[f"{stat}_{w}"][0] - r[f"{stat}_PRE"][0] for r in N]
            sign = -1 if stat == "q" else 1
            summ[f"{stat}0_change_{w}"] = {
                "A_median": round(float(np.nanmedian(dA)), 4), "NB_median": round(float(np.nanmedian(dN)), 4),
                "NB_abs_max": round(float(np.nanmax(np.abs(dN))), 4),
                "auc_A_vs_NB": auc([sign * x for x in dA], [sign * x for x in dN])}
    # implied effectiveness against the truth: q0 LATE vs eta, kappa0 LATE vs 1/eta
    summ["q0_LATE_vs_eta"] = [(r["eta"], round(r["q_LATE"][0], 3)) for r in sorted(A, key=lambda r: r["eta"])][::5]
    summ["kappa0_LATE_vs_inv_eta"] = [(round(1 / r["eta"], 3), round(r["kappa_LATE"][0], 3))
                                      for r in sorted(A, key=lambda r: r["eta"])][::5]
    # localization: the motor with the lowest q (telemetry) and highest kappa change (compensation)
    loc_q = sum(1 for r in A if int(np.nanargmin(r["q_LATE"])) == 0)
    loc_k = sum(1 for r in A if int(np.nanargmax(np.subtract(r["kappa_LATE"], r["kappa_PRE"]))) == 0)
    summ["localization_motor0"] = {"by_q_LATE_min": f"{loc_q}/{len(A)}",
                                   "by_kappa_change_LATE_max": f"{loc_k}/{len(A)}"}
    for stat in ("unalloc_torque", "sat_any", "torque_achieved"):
        summ[stat] = {w: {"A_median": round(float(np.nanmedian([r[f"{stat}_{w}"] for r in A])), 4),
                          "NB_median": round(float(np.nanmedian([r[f"{stat}_{w}"] for r in N])), 4)}
                      for w in ("PRE", "EARLY", "LATE")}
    summ["dyn_T1"] = {"samples_in_T1_at_stock_rate": sorted({r["dyn_T1_samples"] for r in rows}),
                      "auc_A_vs_NB": auc([r["dyn_T1"] for r in A], [r["dyn_T1"] for r in N])}
    summ["integrator_change_LATE"] = {
        "A_median": [round(float(np.nanmedian([r["integ_LATE"][k] - r["integ_PRE"][k] for r in A])), 4) for k in (0, 1)],
        "NB_median": [round(float(np.nanmedian([r["integ_LATE"][k] - r["integ_PRE"][k] for r in N])), 4) for k in (0, 1)]}
    summ["battery"] = {"voltage_range_all": [min(r["battery"]["voltage_range"][0] for r in rows),
                                             max(r["battery"]["voltage_range"][1] for r in rows)],
                       "current_a_unique_values": sorted({v for r in rows for v in r["battery"]["current_a_unique"]}),
                       "warnings": sum(r["battery"]["warning_nonzero"] for r in rows),
                       "current_average_change_A_median": round(float(np.nanmedian(
                           [r["battery"]["i_LATE"] - r["battery"]["i_PRE"] for r in A])), 4),
                       "current_average_change_NB_median": round(float(np.nanmedian(
                           [r["battery"]["i_LATE"] - r["battery"]["i_PRE"] for r in N])), 4)}
    summ["failure_detector_flags_nonzero"] = sum(sum(r["failure_detector"].values()) for r in rows)
    summ["imbalanced_prop_metric"] = {
        "A_LATE_median": round(float(np.nanmedian([r["imbalanced_prop_metric"]["LATE"] for r in A])), 4),
        "NB_LATE_median": round(float(np.nanmedian([r["imbalanced_prop_metric"]["LATE"] for r in N])), 4),
        "max_all": round(max(r["imbalanced_prop_metric"]["max"] for r in rows), 3),
        "threshold": rows[0]["imbalanced_prop_metric"]["threshold_FD_IMB_PROP_THR"]}
    summ["cpuload_range"] = [min(r["cpuload"]["min"] for r in rows), max(r["cpuload"]["max"] for r in rows)]
    summ["esc_current_nonzero_samples"] = sum(r["esc_current_nonzero"] for r in rows)
    summ["airborne_s"] = {"total": round(sum(r["airborne_s"] for r in rows), 1),
                          "NB_total": round(sum(r["airborne_s"] for r in N), 1)}
    summ["stock_rates_hz"] = rows[0]["rates_hz"]
    by_eta = {}
    for r in A:
        by_eta.setdefault(r["eta"], []).append(r)
    summ["by_eta"] = {str(e): {"n": len(v),
                               "q0_drop_LATE_median": round(float(np.nanmedian([x["q_PRE"][0] - x["q_LATE"][0] for x in v])), 4),
                               "kappa0_rise_LATE_median": round(float(np.nanmedian([x["kappa_LATE"][0] - x["kappa_PRE"][0] for x in v])), 4)}
                      for e, v in sorted(by_eta.items())}
    summ["NB_q_change_abs_max_any_motor"] = round(float(np.nanmax(
        [abs(r["q_LATE"][m] - r["q_PRE"][m]) for r in N for m in range(4)])), 4)
    summ["NB_kappa_change_abs_max_any_motor"] = round(float(np.nanmax(
        [abs(r["kappa_LATE"][m] - r["kappa_PRE"][m]) for r in N for m in range(4)])), 4)
    C.write_json(C.HERE / "STOCK_EVIDENCE_INVESTIGATION.json",
                 {"label": "NON-CONFIRMATORY; default-rate emulation of the 66 XSYS-001 logs",
                  "summary": summ, "flights": rows})
    print(json.dumps(summ, indent=1)[:6000])


if __name__ == "__main__":
    main()
