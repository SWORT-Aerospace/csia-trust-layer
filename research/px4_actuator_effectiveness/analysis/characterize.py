#!/usr/bin/env python3
"""Characterize physical actuator-effectiveness loss on PX4 SIH, and build the
matched telemetry-fault control case offline.

Research-only apparatus characterization. It computes NO CSIA output, sets NO
threshold and makes NO detection claim. The quantities below are descriptors
of the simulated physics, fixed here before the sweep was analysed:

PHASES (per trial, t1 = first SIH step after the effectiveness change)
  PRE-FAULT                [t1 - 5 s, t1)
  ONSET TRANSIENT          [t1, t_peak]    t_peak = time of peak true body-rate
                                           norm within 3 s of t1: the step at
                                           which angular acceleration returns to
                                           zero, i.e. torque balance is regained
  COMPENSATION TRANSIENT   (t_peak, t1 + 10 s)
  POST-COMPENSATION STEADY STATE  [t1 + 10 s, end of record = t1 + 20 s)
  (revision R2: the phase boundary after the compensation transient is a FIXED
  time, not a detected settling time, because detected settling is not
  resolvable from nominal noise on this apparatus; see below.)

SETTLING (reported beside the phases, never used to cut them)
  t_settle = start of the final uninterrupted stretch, lasting at least 3 s and
  reaching the end of the record, in which the 0.5 s moving means of the true
  body-rate norm, true tilt and |altitude - pre-fault mean altitude| all stay
  inside the NOMINAL ENVELOPE. No such stretch: "not recovered".

  NOMINAL ENVELOPE (revision R1). Per signal, the largest 0.5 s moving mean
  that the eta = 1.00 control trials reach after their (no-op) onset, over the
  same post-onset window. Control trials are evaluated leave-one-out against
  the other controls, so their settle times measure the segmentation's noise
  floor. R1 replaced a first definition (1.2 x each trial's own 5 s pre-fault
  maximum) that failed its own control: a healthy eta = 1.00 hover wandered
  about 6 cm in altitude over 20 s and was classed "not recovered". R1 is
  calibrated on the control arm only; no degraded trial enters it.
  Even so, the control trials themselves "settle" anywhere between 0.5 s and
  never, so settling times are reported with that noise floor and are not used
  to define phases (R2).

FLIGHT WINDOW  every trial's analysis ends at first ground contact (altitude
  < 0.3 m), when there is one: SIH stops a falling vehicle in a single step,
  and the impact is not flight dynamics. A trial that reaches the ground before
  t1 + 10 s has no steady-state window.

CONTROL AUTHORITY (final 3 s of the flight window)
  yaw authority lost      mean |true yaw rate| > 0.5 rad/s
  altitude authority lost altitude error > 2 m, or ground contact
  attitude lost           true tilt > 30 deg at any time after t1
  motor at limit          fraction of final 3 s with motor-1 command >= 0.999

CASE B (telemetry fault, offline)
  Taken from the matched nominal flights (eta = 1.00, same schedule). From the
  same onset step, a COPY of motor 1's RPM telemetry is replaced by what a rotor
  with effectiveness eta would report for that flight's own command history:
      u_B[k] = u_B[k-1] + (dt/tau) (eta c[k] - u_B[k-1]),  rpm_B = round(1e4 sqrt(u_B))
  The true rotor record, the dynamics and the estimator are left untouched.
"""
import argparse
import json
from pathlib import Path

import numpy as np

import sihlog

ALPHA = 0.004 / 0.05          # dt / SIH_T_TAU at the 4 ms lockstep step
PRE_S, PEAK_WIN_S, SETTLE_MIN_S, MA_S, STEADY_FROM_S = 5.0, 3.0, 3.0, 0.5, 10.0
GROUND_ALT_M = 0.3
STEP_S = 0.004


def moving_mean(x, n):
    c = np.cumsum(np.insert(np.nan_to_num(x), 0, 0.0))
    out = np.full(len(x), np.nan)
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def paired_command(tr):
    """Command SIH applied at each step: the latest actuator_outputs_sim stamped
    strictly before the step (the pairing identified from the logs)."""
    ct, c = tr.raw["cmd_sim_t"], tr.raw["cmd_sim"]
    j = np.searchsorted(ct, tr.t_us, side="left") - 1
    out = np.full((len(tr.t_us), 4), np.nan)
    ok = j >= 0
    out[ok] = c[j[ok]]
    return out


def healthy_rotor_rpm(tr, k0, cmd, u0):
    """RPM a healthy rotor (eta = 1) would report for this command history."""
    n = len(tr.t_us)
    u = np.full(n, np.nan)
    u[k0 - 1] = u0
    for k in range(k0, n):
        u[k] = u[k - 1] + ALPHA * (cmd[k] - u[k - 1])
    return 1e4 * np.sqrt(np.clip(u, 0, 1))


def eta_identified(tr, cmd, m=0):
    """Physical effectiveness recovered from the rotor record alone, per step."""
    u = tr.s["u_rotor"][:, m]
    tgt = u[:-1] + (u[1:] - u[:-1]) / ALPHA
    c = cmd[1:, m]
    with np.errstate(divide="ignore", invalid="ignore"):
        e = np.where(c > 0.05, tgt / c, np.nan)
    return np.concatenate([[np.nan], e])


def onset_step(tr, meta):
    ch = sihlog.eta_change(tr)
    if ch is not None:
        return sihlog.first_step_after(tr, ch[0]), ch[0], "parameter_update"
    # an unchanged value (eta = 1.00) publishes no parameter_update: use the
    # driver's send time, which is when the no-op PARAM_SET reached PX4
    t_send_us = int(meta["events_ms"]["eta_set"][0]) * 1000
    return sihlog.first_step_after(tr, t_send_us), t_send_us, "driver_send_time"


def end_step(tr):
    arm = sihlog.arm_time_us(tr)
    st, tt = tr.raw["arming_state"], tr.raw["status_t"]
    dis = np.nonzero((tt > arm) & (st != 2))[0]
    t_end = tt[dis[0]] if len(dis) else tr.t_us[-1]
    return int(np.searchsorted(tr.t_us, t_end - 100_000))


def derived(tr, cmd_paired):
    s = tr.s
    d = {}
    d["cmd0"] = s["cmd_alloc"][:, 0]
    d["cmd_others"] = s["cmd_alloc"][:, 1:4].mean(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        d["kappa"] = d["cmd0"] / d["cmd_others"]
    d["rate_norm"] = np.linalg.norm(s["w_true"], axis=1)
    d["yaw_rate"] = s["w_true"][:, 2]
    d["alpha_norm"] = np.linalg.norm(s["alpha_true"], axis=1)
    d["tilt"] = s["tilt_true"][:, 0]
    d["att_err"] = s["att_err"][:, 0]
    d["alt"] = -s["pos_true"][:, 2]
    d["torque_sp"] = s["torque_sp"]
    d["sf"] = s["accel_meas"]
    d["sat0"] = (s["alloc_sat"][:, 0] >= 1).astype(float)
    with np.errstate(all="ignore"):
        d["ratio_max"] = np.nanmax(np.where(np.isnan(s["innov_ratio"]), -np.inf, np.abs(s["innov_ratio"])), axis=1)
    idx = {n: i for i, n in enumerate(tr.raw["innov_fields"])}
    v = s["innov_ratio"][:, [idx["baro_vpos"], idx["gps_vpos"], idx["rng_vpos"]]]
    d["ratio_vert"] = np.max(np.where(np.isnan(v), -np.inf, np.abs(v)), axis=1)
    d["hte_ratio"] = s["hte_innov"][:, 1]
    d["hover_thrust"] = s["hover_thrust"][:, 0]
    d["thrust_total"] = s["thrust_rotor"].sum(1)
    d["cmd_paired"] = cmd_paired
    return d


def ma_signals(tr, d, k1):
    t = tr.t
    k_pre = int(np.searchsorted(t, t[k1] - PRE_S))
    n_ma = int(round(MA_S / STEP_S))
    alt_ref = np.nanmean(d["alt"][k_pre:k1])
    sig = {"rate_norm": d["rate_norm"], "tilt": d["tilt"], "alt_err": np.abs(d["alt"] - alt_ref)}
    return {k: moving_mean(v, n_ma) for k, v in sig.items()}, k_pre, alt_ref


def post_onset_maxima(tr, d, k1, kend):
    ma, _, _ = ma_signals(tr, d, k1)
    n_ma = int(round(MA_S / STEP_S))
    return {k: float(np.nanmax(v[k1 + n_ma:kend])) for k, v in ma.items()}


def phases(tr, d, k1, kend, env):
    t = tr.t
    ma, k_pre, alt_ref = ma_signals(tr, d, k1)
    k_win = int(np.searchsorted(t, t[k1] + PEAK_WIN_S))
    k_peak = k1 + int(np.nanargmax(d["rate_norm"][k1:min(k_win, kend)]))
    inside = np.all([ma[k][:kend] <= env[k] for k in ma], axis=0)
    inside[:k1] = False
    # final uninterrupted in-envelope stretch reaching the end of the record
    k_settle = None
    if inside[kend - 1]:
        j = kend - 1
        while j > k_peak and inside[j - 1]:
            j -= 1
        if t[kend - 1] - t[j] >= SETTLE_MIN_S:
            k_settle = j
    settle_each = {}
    for name in ma:
        ok = ma[name][:kend] <= env[name]
        ok[:k1] = False
        j = None
        if ok[kend - 1]:
            j = kend - 1
            while j > k_peak and ok[j - 1]:
                j -= 1
        settle_each[name] = None if j is None else float(t[j] - t[k1])
    k_steady = min(int(np.searchsorted(t, t[k1] + STEADY_FROM_S)), kend)
    return {"k_pre": k_pre, "k1": k1, "k_peak": k_peak, "k_settle": k_settle, "k_end": kend,
            "k_steady": k_steady, "settle_each_s": settle_each,
            "envelope": env, "alt_ref": alt_ref}


def seg(x, a, b):
    return x[a:b] if b > a else x[a:a]


def summarize(tr, d, ph, rpm_tel, rpm_exp):
    """Per-phase magnitudes, as differences from the pre-fault mean."""
    k_pre, k1, kp, kst, ke = ph["k_pre"], ph["k1"], ph["k_peak"], ph["k_steady"], ph["k_end"]
    spans = {"pre": (k_pre, k1), "onset": (k1, kp + 1),
             "compensation": (kp + 1, kst), "steady": (kst, ke)}
    pre = slice(k_pre, k1)
    out = {}
    base = {
        "W_CTRL.cmd0": d["cmd0"], "W_CTRL.kappa": d["kappa"],
        "W_CTRL.torque_sp_norm": np.linalg.norm(d["torque_sp"] - np.nanmean(d["torque_sp"][pre], 0), axis=1),
        "W_CTRL.sat0": d["sat0"],
        "W_RPM.residual0_rpm": rpm_tel[:, 0] - rpm_exp,
        "W_DYN.rate_norm": d["rate_norm"], "W_DYN.alpha_norm": d["alpha_norm"], "W_DYN.tilt": d["tilt"],
        "W_DYN.sf_dev_norm": np.linalg.norm(d["sf"] - np.nanmean(d["sf"][pre], 0), axis=1),
        "W_DYN.alt_err": np.abs(d["alt"] - ph["alt_ref"]),
        "W_EST.ratio_max": d["ratio_max"], "W_EST.ratio_vert": d["ratio_vert"],
        "W_EST.hover_thrust": d["hover_thrust"],
        "W_EST.hte_innov_ratio": d["hte_ratio"],
    }
    for name, x in base.items():
        mu = np.nanmean(x[pre])
        sd = np.nanstd(x[pre])
        row = {"pre_mean": float(mu), "pre_sd": float(sd)}
        for ph_name, (a, b) in spans.items():
            y = seg(x, a, b) - (0.0 if name.endswith(("norm", "sat0", "alt_err", "residual0_rpm")) else mu)
            if len(y) == 0 or np.all(np.isnan(y)):
                row[ph_name] = None
                continue
            row[ph_name] = {"mean": float(np.nanmean(y)), "max_abs": float(np.nanmax(np.abs(y))),
                            "n": int(len(y))}
        out[name] = row
    return out, spans


def authority(tr, d, ph):
    t = tr.t
    k1, ke = ph["k1"], ph["k_end"]
    k3 = int(np.searchsorted(t, t[ke - 1] - 3.0))
    ground = d.get("k_ground") is not None
    return {
        "final3s_mean_abs_yaw_rate": float(np.nanmean(np.abs(d["yaw_rate"][k3:ke]))),
        "yaw_authority_lost": bool(np.nanmean(np.abs(d["yaw_rate"][k3:ke])) > 0.5),
        "final_alt_err_m": float(abs(np.nanmean(d["alt"][k3:ke]) - ph["alt_ref"])),
        "min_alt_m": float(np.nanmin(d["alt"][k1:ke])),
        "ground_contact": ground,
        "altitude_authority_lost": bool(ground or abs(np.nanmean(d["alt"][k3:ke]) - ph["alt_ref"]) > 2.0),
        "max_tilt_deg": float(np.degrees(np.nanmax(d["tilt"][k1:ke]))),
        "attitude_lost": bool(np.degrees(np.nanmax(d["tilt"][k1:ke])) > 30.0),
        "final3s_motor1_at_limit_frac": float(np.nanmean(d["cmd0"][k3:ke] >= 0.999)),
    }


def first_exceed(x, k1, ke, pre):
    """First step at or after k1 where |x - pre mean| exceeds the pre-fault max deviation."""
    mu = np.nanmean(x[pre])
    lim = np.nanmax(np.abs(x[pre] - mu))
    hit = np.nonzero(np.abs(x[k1:ke] - mu) > lim)[0]
    return int(k1 + hit[0]) if len(hit) else None


def timing(tr, meta, k1, t_change, source, d, ph, rpm_exp):
    t_us = tr.t_us
    pre = slice(ph["k_pre"], k1)
    ke = ph["k_end"]
    r = {"onset_source": source,
         "driver_send_us": int(meta["events_ms"]["eta_set"][0]) * 1000,
         "change_timestamp_us": int(t_change), "t1_us": int(t_us[k1])}
    r["send_to_change_ms"] = (r["change_timestamp_us"] - r["driver_send_us"]) / 1000
    r["change_to_t1_ms"] = (r["t1_us"] - r["change_timestamp_us"]) / 1000
    for name, x in (("rpm0", tr.s["rpm_true"][:, 0]), ("cmd0", d["cmd0"]),
                    ("alpha_norm", d["alpha_norm"]), ("rate_norm", d["rate_norm"]),
                    ("ratio_max", d["ratio_max"]), ("hte_ratio", d["hte_ratio"]),
                    ("hover_thrust", d["hover_thrust"])):
        k = first_exceed(x, k1, ke, pre)
        r[f"first_response_{name}_ms"] = None if k is None else (int(t_us[k]) - int(t_us[k1])) / 1000
    return r


def prepare(path):
    meta = json.loads(Path(path).with_suffix(".json").read_text())
    tr = sihlog.load(path)
    cmd = paired_command(tr)
    k1, t_change, source = onset_step(tr, meta)
    ke = end_step(tr)
    d = derived(tr, cmd)
    # the flight window ends at first ground contact: SIH stops a falling
    # vehicle in one step (sih.cpp:640-660), which produces impact artefacts
    g = np.nonzero(d["alt"][k1:ke] < GROUND_ALT_M)[0]
    d["k_ground"] = int(k1 + g[0]) if len(g) else None
    if d["k_ground"] is not None:
        ke = d["k_ground"]
    return meta, tr, cmd, k1, t_change, source, ke, d


def control_envelope(prepared, exclude=None):
    maxima = [post_onset_maxima(tr, d, k1, ke) for name, (meta, tr, cmd, k1, tc, src, ke, d) in prepared.items()
              if name != exclude]
    return {k: max(m[k] for m in maxima) for k in maxima[0]}


def analyse_trial(path, env, prep=None):
    meta, tr, cmd, k1, t_change, source, ke, d = prep if prep is not None else prepare(path)
    ph = phases(tr, d, k1, ke, env)
    rpm_exp = healthy_rotor_rpm(tr, ph["k_pre"], cmd[:, 0], tr.s["u_rotor"][ph["k_pre"] - 1, 0])
    summ, spans = summarize(tr, d, ph, tr.s["rpm_telemetry"], rpm_exp)
    eh = eta_identified(tr, cmd)
    ss = slice(ph["k_steady"], ke)
    pre = slice(ph["k_pre"], k1)
    t = tr.t
    row = {
        "name": Path(path).stem, "eta_set": meta["eta"], "onset": source,
        "t1_s": float(t[k1]),
        "eta_identified_pre": float(np.nanmedian(eh[pre])),
        "eta_identified_post": float(np.nanmedian(eh[k1 + 1:ke])),
        "cmd0_pre": float(np.nanmean(d["cmd0"][pre])), "cmd0_peak": float(np.nanmax(d["cmd0"][k1:ke])),
        "cmd0_steady": float(np.nanmean(d["cmd0"][ss])),
        "cmd_others_steady": float(np.nanmean(d["cmd_others"][ss])),
        "kappa_steady": float(np.nanmean(d["kappa"][ss])),
        "rpm0_pre": float(np.nanmean(tr.s["rpm_true"][pre, 0])),
        "rpm0_steady": float(np.nanmean(tr.s["rpm_true"][ss, 0])),
        "rpm_others_steady": float(np.nanmean(tr.s["rpm_true"][ss, 1:4])),
        "rpm0_expected_from_cmd_steady": float(np.nanmean(rpm_exp[ss])),
        "thrust0_pre_N": float(np.nanmean(tr.s["thrust_rotor"][pre, 0])),
        "thrust0_steady_N": float(np.nanmean(tr.s["thrust_rotor"][ss, 0])),
        "thrust0_capacity_N": float(meta["eta"] * float(tr.params.get("SIH_T_MAX", 5.0))),
        "thrust_total_steady_N": float(np.nanmean(d["thrust_total"][ss])),
        "peak_rate_norm": float(np.nanmax(d["rate_norm"][k1:ke])),
        "peak_alpha_norm": float(np.nanmax(d["alpha_norm"][k1:ke])),
        "peak_sf_dev_norm": float(np.nanmax(np.linalg.norm(d["sf"][k1:ke] - np.nanmean(d["sf"][pre], 0), axis=1))),
        "peak_tilt_deg": float(np.degrees(np.nanmax(d["tilt"][k1:ke]))),
        "peak_att_err_deg": float(np.degrees(np.nanmax(d["att_err"][k1:ke]))),
        "pre_max_att_err_deg": float(np.degrees(np.nanmax(d["att_err"][pre]))),
        "peak_innov_ratio": float(np.nanmax(d["ratio_max"][k1:ke])),
        "pre_max_innov_ratio": float(np.nanmax(d["ratio_max"][pre])),
        "t_peak_after_t1_s": float(t[ph["k_peak"]] - t[k1]),
        "recovered": ph["k_settle"] is not None,
        "recovery_time_s": None if ph["k_settle"] is None else float(t[ph["k_settle"]] - t[k1]),
        "settle_each_s": ph["settle_each_s"],
        "nominal_envelope": env,
        "peak_hte_innov_ratio": float(np.nanmax(np.abs(d["hte_ratio"][k1:ke]))),
        "pre_max_hte_innov_ratio": float(np.nanmax(np.abs(d["hte_ratio"][pre]))),
        "authority": authority(tr, d, ph),
        "timing": timing(tr, meta, k1, t_change, source, d, ph, rpm_exp),
        "phase_s": {k: ([float(t[a] - t[k1]), float(t[min(b, ke) - 1] - t[k1])] if b > a else None)
                    for k, (a, b) in spans.items()},
        "evidence": summ,
        "dropouts": tr.dropouts,
        "ground_contact_after_t1_s": None if d["k_ground"] is None else float(t[d["k_ground"]] - t[k1]),
        "steady_flight_window": ph["k_steady"] < ke,
    }
    return row, tr, d, ph, cmd


def case_b(nominal_path, eta, phase_template):
    """Telemetry-fault copy of a matched nominal flight (eta = 1.00, same schedule)."""
    meta = json.loads(Path(nominal_path).with_suffix(".json").read_text())
    tr = sihlog.load(nominal_path)
    cmd = paired_command(tr)
    k1, t_change, source = onset_step(tr, meta)
    ke = end_step(tr)
    d = derived(tr, cmd)
    rpm_true = tr.s["rpm_true"].copy()
    u = tr.s["u_rotor"][:, 0].copy()
    uB = u.copy()
    for k in range(k1, len(u)):
        uB[k] = uB[k - 1] + ALPHA * (eta * cmd[k, 0] - uB[k - 1])
    tel = tr.s["rpm_telemetry"].copy()
    tel[:, 0] = np.round(1e4 * np.sqrt(np.clip(uB, 0, 1)))
    assert np.array_equal(tr.s["rpm_true"], rpm_true)  # the truth record is untouched
    # phase boundaries matched to case A at the same level, by time since onset
    t = tr.t

    def at(dt_s):
        return int(np.clip(np.searchsorted(t, t[k1] + dt_s), k1, ke))
    ph = {"k_pre": int(np.searchsorted(t, t[k1] - PRE_S)), "k1": k1,
          "k_peak": max(k1, at(phase_template["peak"]) - 1),
          "k_steady": at(STEADY_FROM_S),
          "k_end": ke, "alt_ref": float(np.nanmean(d["alt"][int(np.searchsorted(t, t[k1] - PRE_S)):k1]))}
    rpm_exp = healthy_rotor_rpm(tr, ph["k_pre"], cmd[:, 0], tr.s["u_rotor"][ph["k_pre"] - 1, 0])
    summ, _ = summarize(tr, d, ph, tel, rpm_exp)
    ss = slice(ph["k_steady"], ke)
    return {"name": f"B_from_{Path(nominal_path).stem}_eta{int(round(eta * 100)):03d}", "eta_telemetry": eta,
            "truth_rpm_preserved": True,
            "rpm0_true_steady": float(np.nanmean(rpm_true[ss, 0])),
            "rpm0_reported_steady": float(np.nanmean(tel[ss, 0])),
            "rpm0_expected_from_cmd_steady": float(np.nanmean(rpm_exp[ss])),
            "cmd0_steady": float(np.nanmean(d["cmd0"][ss])),
            "kappa_steady": float(np.nanmean(d["kappa"][ss])),
            "evidence": summ}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", help="directory holding sweep_etaXXX_rN.ulg")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    runs = sorted(Path(a.runs).glob("sweep_eta*_r*.ulg"))
    controls = {p.stem: prepare(p) for p in runs if p.stem.startswith("sweep_eta100_")}
    env_all = control_envelope(controls)
    rows = []
    for p in runs:
        if p.stem in controls:
            rows.append(analyse_trial(p, control_envelope(controls, exclude=p.stem), controls[p.stem])[0])
        else:
            rows.append(analyse_trial(p, env_all)[0])
    by_level = {}
    for r in rows:
        by_level.setdefault(r["eta_set"], []).append(r)
    nominal = [p for p in runs if p.stem.startswith("sweep_eta100_")]
    cases_b = []
    for eta, rs in sorted(by_level.items(), reverse=True):
        tmpl = {"peak": float(np.median([r["t_peak_after_t1_s"] for r in rs])), "steady_from": STEADY_FROM_S}
        for p in nominal:
            cases_b.append(dict(case_b(p, eta, tmpl), phase_template=tmpl))
    Path(a.out).write_text(json.dumps({"doc": __doc__, "nominal_envelope": env_all, "trials": rows,
                                       "case_b": cases_b}, indent=1, default=float))
    for r in rows:
        au = r["authority"]
        print(f"{r['name']:20s} eta_id={r['eta_identified_post']:.3f} cmd0 {r['cmd0_pre']:.3f}->{r['cmd0_steady']:.3f} "
              f"rpm0 {r['rpm0_pre']:.0f}->{r['rpm0_steady']:.0f} kappa={r['kappa_steady']:.2f} "
              f"peak|w|={r['peak_rate_norm']:.2f} tilt={r['peak_tilt_deg']:.1f} rec={r['recovered']} "
              f"t_rec={r['recovery_time_s']} yaw_lost={au['yaw_authority_lost']} alt_lost={au['altitude_authority_lost']}")


if __name__ == "__main__":
    main()
