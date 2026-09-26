#!/usr/bin/env python3
"""XSYS-001 STAGE 0 — custodian: extract, check, construct case B, blind.

The ONLY stage that sees labels, ground truth and raw ULogs. It writes:

  <blind>/<opaque_id>.npz   ON-BOARD signals only, analysis span [-5, 15) s
  <blind>/INDEX.json        the opaque ids, sorted; nothing else
  <key>                     opaque id -> analysis trial, labels, pair, level,
                            nuisance condition (read ONLY by stage 2)
  <qc>                      every logging and manipulation check, per flight
                            and per analysis trial, with the decision

CASE B (telemetry corruption), constructed here and nowhere else:
  source    the nominal flight NB of the same nuisance condition (benign
            onset event, physics untouched)
  channel   motor 0's RPM telemetry only (SIH Motor1 = CSIA motor_0)
  rule      rpm_B(k) = round( rpm_expB(k) * rho_A(k) )  for t_rel >= 0,
            where rho_A is the matched fault flight's RPM ratio and rpm_expB
            is the healthy-rotor RPM for B's OWN command (xsys_features). The
            ratio, hence the local symptom L_W, is identical to A's by
            construction.
  alignment step index relative to each flight's own t0 (both on the 4 ms
            grid). A missing step in A is held from the previous step
            (zero-order hold); no other interpolation. Before t0, nothing is
            changed.
  noise     SIH RPM telemetry has none beyond integer rounding; the corrupted
            value is rounded to an integer like the original.
  truth     B's true RPM stays in the QC record; only the analysis copy is
            modified. Every other B channel is byte-identical to its source.

NO INTERIM LOOK. In confirmatory mode stage 0 refuses to run until every flight
of the frozen matrix has been attempted: it has a ULog, or EXECUTION_LOG.jsonl
records its two failed attempts. A campaign that cannot be completed is
analysed only through --declare-campaign-terminated "<reason>", which records
the reason and excludes every unflown flight with it.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import xsys_extract as X  # noqa: E402
import xsys_features as F  # noqa: E402
import xsys_freeze_check as FC  # noqa: E402

ONBOARD_KEYS = ("t_rel", "rpm_obs", "cmd_sim", "cmd_alloc", "gyro", "accel",
                "ekf_test_ratio_max", "hte_test_ratio", "rotor_px", "rotor_py")
TRUTH_LABEL = {"A": "PHYSICAL_ACTUATOR_DEGRADATION", "B": "RPM_TELEMETRY_CORRUPTION", "N": "NOMINAL"}

# ---- frozen check tolerances (preregistration section "Manipulation checks")
TOL = {
    "max_dropouts": 0,
    "max_gap_steps": 2,
    "max_missing_frac": 0.005,
    "max_onset_uncertainty_us": 8000,
    "eta_abs_tol": 0.01,
    "eta_nominal_tol": 0.002,
    "rotor_eq_rms_max": 1e-3,
    "min_alt_m": 5.0,
    "max_tilt_deg_A": 30.0,
    "max_tilt_deg_N": 5.0,
    "max_alt_dev_m_N": 1.0,
    "max_mean_abs_yaw_rate_T3": 0.5,
    "b_ratio_match_max": 5e-4,
    "max_heading_error_deg": 5.0,
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _json_scalar(o):
    """numpy scalars in the QC record: booleans stay booleans."""
    return bool(o) if isinstance(o, np.bool_) else float(o)


def eta_identified(rpm, cmd):
    """Per-step physical effectiveness from the rotor equation (apparatus §D)."""
    u = (rpm / F.RPM_MAX) ** 2
    tgt = u[:-1] + (u[1:] - u[:-1]) / F.ALPHA
    with np.errstate(divide="ignore", invalid="ignore"):
        e = np.where(cmd[1:] > 0.05, tgt / cmd[1:], np.nan)
    return np.concatenate([[np.nan], e]), u


def flight_checks(row, meta, res, run_json, frozen):
    """Logging, integrity and manipulation checks for one flown flight."""
    c = {}
    c["Q_log_readable"] = res is not None
    if res is None:
        return c, False
    ob, tr = res["onboard"], res["truth"]
    t = ob["t_rel"]
    n_expected = int(round((F.ANALYSIS_SPAN[1] - F.ANALYSIS_SPAN[0]) / F.STEP_S))
    c["Q_dropouts"] = meta["dropouts"] <= TOL["max_dropouts"]
    c["Q_span_covered"] = meta["span_covered"]
    c["Q_max_gap"] = meta["max_gap_steps"] <= TOL["max_gap_steps"]
    c["Q_missing_frac"] = (1 - meta["n_steps"] / n_expected) <= TOL["max_missing_frac"]
    c["Q_onset_uncertainty"] = (meta["t0_us"] - meta["t_param_update_us"]) <= TOL["max_onset_uncertainty_us"]
    if frozen is not None:
        # one verified binary for the whole campaign (run_confirmatory.py CAMPAIGN.json)
        c["Q_build_hash"] = (run_json.get("px4_sha256") == frozen["campaign_px4_sha256"]
                             and frozen["campaign_source_verified"] is True)
        c["Q_logger_config_hash"] = run_json.get("logger_topics_sha256") == frozen["logger_topics_sha256"]
        c["Q_manifest"] = run_json.get("extra", {}).get("freeze_manifest_sha256") == frozen["manifest_sha256"]
        c["Q_heading"] = abs(run_json.get("heading_deg", -999) - float(row["heading_deg"])) < 1e-6
        c["Q_onset_value"] = abs(run_json.get("onset_value", -999) - float(row["onset_value"])) < 1e-9
    eh, u = eta_identified(ob["rpm_obs"][:, 0], ob["cmd_sim"][:, 0])
    pre = F.window_mask(t, "T0")
    post = (t >= 0.2) & (t < F.ANALYSIS_SPAN[1])
    c["eta_hat_T0"] = float(np.nanmedian(eh[pre]))
    c["eta_hat_post"] = float(np.nanmedian(eh[post]))
    alt0 = float(np.nanmean(tr["alt"][pre]))
    after = t >= 0
    c["min_alt_after_onset"] = float(np.nanmin(tr["alt"][after]))
    c["max_tilt_deg_after_onset"] = float(np.degrees(np.nanmax(tr["tilt"][after])))
    c["mean_abs_yaw_rate_T3"] = float(np.nanmean(np.abs(tr["w_true"][F.window_mask(t, "T3"), 2])))
    c["MC_eta_nominal_before_onset"] = abs(c["eta_hat_T0"] - 1.0) <= TOL["eta_nominal_tol"]
    # the nuisance was applied: true heading over T0 (circular mean) vs the frozen heading
    yaw0 = np.degrees(np.angle(np.nanmean(np.exp(1j * tr["yaw"][pre]))))
    c["true_heading_T0_deg"] = float(yaw0)
    if row.get("heading_deg") not in (None, ""):
        err = (yaw0 - float(row["heading_deg"]) + 180.0) % 360.0 - 180.0
        c["heading_error_deg"] = float(err)
        c["MC_heading_applied"] = abs(err) <= TOL["max_heading_error_deg"]
    if row["condition"] == "A":
        eta = float(row["eta"])
        c["MC_onset_event"] = (meta["onset_param"] == "SIH_MOT_EFF1"
                               and abs(meta["onset_value"] - eta) < 1e-6)
        c["MC_eta_reached"] = abs(c["eta_hat_post"] - eta) <= TOL["eta_abs_tol"]
        # the rotor followed the LOGGED command scaled by eta: the command SIH
        # received is the command the controller sent, untouched by the injection
        k = np.arange(1, len(u))
        e = np.where(t[k] >= 0, eta, 1.0)
        resid = u[k] - (u[k - 1] + F.ALPHA * (e * ob["cmd_sim"][k, 0] - u[k - 1]))
        c["rotor_equation_rms"] = float(np.sqrt(np.nanmean(resid[t[k] >= -5] ** 2)))
        c["MC_command_independent"] = c["rotor_equation_rms"] <= TOL["rotor_eq_rms_max"]
        c["MC_controllable"] = (c["min_alt_after_onset"] >= TOL["min_alt_m"]
                                and c["max_tilt_deg_after_onset"] <= TOL["max_tilt_deg_A"]
                                and c["mean_abs_yaw_rate_T3"] <= TOL["max_mean_abs_yaw_rate_T3"])
    else:
        c["MC_onset_event"] = meta["onset_param"] == "SDLOG_DIRS_MAX"
        c["MC_rotor_nominal"] = abs(c["eta_hat_post"] - 1.0) <= TOL["eta_nominal_tol"]
        c["MC_dynamics_nominal"] = (c["max_tilt_deg_after_onset"] <= TOL["max_tilt_deg_N"]
                                    and abs(c["min_alt_after_onset"] - alt0) <= TOL["max_alt_dev_m_N"]
                                    and c["min_alt_after_onset"] >= TOL["min_alt_m"])
    ok = all(v for k, v in c.items() if k.startswith(("Q_", "MC_")))
    return c, ok


def build_b(nb, a):
    """Telemetry-corruption copy of nominal flight nb, matched to fault flight a."""
    rho_a, _ = F.rpm_ratio(a["rpm_obs"][:, 0], a["cmd_sim"][:, 0])
    _, rpm_exp_b = F.rpm_ratio(nb["rpm_obs"][:, 0], nb["cmd_sim"][:, 0])
    ka = np.round(a["t_rel"] / F.STEP_S).astype(int)
    kb = np.round(nb["t_rel"] / F.STEP_S).astype(int)
    idx = np.searchsorted(ka, kb, side="right") - 1          # zero-order hold on A's steps
    ok = idx >= 0
    rho_on_b = np.full(len(kb), np.nan)
    rho_on_b[ok] = rho_a[idx[ok]]
    b = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in nb.items()}
    post = nb["t_rel"] >= 0
    b["rpm_obs"][post, 0] = np.round(rpm_exp_b[post] * rho_on_b[post])
    rho_b, _ = F.rpm_ratio(b["rpm_obs"][:, 0], b["cmd_sim"][:, 0])
    span = post & np.isfinite(rho_b) & np.isfinite(rho_on_b)
    match = float(np.max(np.abs(rho_b[span] - rho_on_b[span]))) if span.any() else float("inf")
    unchanged = all(np.array_equal(b[k], nb[k], equal_nan=True) for k in ONBOARD_KEYS if k != "rpm_obs")
    unchanged = unchanged and np.array_equal(b["rpm_obs"][:, 1:], nb["rpm_obs"][:, 1:])
    return b, {"MC_B_ratio_matched": match <= TOL["b_ratio_match_max"], "ratio_match_max_abs": match,
               "MC_B_only_motor0_rpm_changed": bool(unchanged)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flight-matrix", required=True)
    ap.add_argument("--analysis-matrix", required=True)
    ap.add_argument("--flights", required=True, help="directory of flown <flight_id>.ulg / .json")
    ap.add_argument("--blind", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--qc", required=True)
    ap.add_argument("--freeze-manifest", help="required in confirmatory mode")
    ap.add_argument("--mode", choices=("confirmatory", "dry-run"), required=True)
    ap.add_argument("--declare-campaign-terminated", metavar="REASON",
                    help="analyse an incomplete campaign; the reason is recorded for every unflown flight")
    a = ap.parse_args()

    frozen = None
    if a.mode == "confirmatory":
        if not a.freeze_manifest:
            raise SystemExit("confirmatory mode needs --freeze-manifest")
        man, man_sha = FC.verify_frozen(a.freeze_manifest, same_as=(
            (a.flight_matrix, "research/xsys_confirmatory_001/prereg/FLIGHT_MATRIX.csv"),
            (a.analysis_matrix, "research/xsys_confirmatory_001/prereg/ANALYSIS_MATRIX.csv")))
        camp = json.loads((Path(a.flights) / "CAMPAIGN.json").read_text())
        if camp["freeze_manifest_sha256"] != man_sha:
            raise SystemExit("CAMPAIGN.json was produced under another freeze manifest")
        frozen = {"logger_topics_sha256": man["frozen_files"][man["logger_config_file"]],
                  "campaign_px4_sha256": camp["px4_sha256"], "campaign_source_verified": camp["source_verified"],
                  "manifest_sha256": man_sha}

    flights = {r["flight_id"]: r for r in csv.DictReader(open(a.flight_matrix))}
    analysis = list(csv.DictReader(open(a.analysis_matrix)))
    fdir = Path(a.flights)
    failed = {}
    if a.mode == "confirmatory":
        log = fdir / "EXECUTION_LOG.jsonl"
        for line in (log.read_text().splitlines() if log.exists() else []):
            e = json.loads(line)
            if not e["ok"]:
                failed[e["flight_id"]] = failed.get(e["flight_id"], 0) + 1
        pending = [f for f in flights if not (fdir / f"{f}.ulg").exists() and failed.get(f, 0) < 2]
        if pending and not a.declare_campaign_terminated:
            raise SystemExit(f"campaign incomplete: {len(pending)} flights not yet attempted twice "
                             f"(first: {pending[0]}); no interim analysis")
    extracted, fqc = {}, {}
    for fid, row in flights.items():
        ulg, js = fdir / f"{fid}.ulg", fdir / f"{fid}.json"
        if not ulg.exists():
            reason = ("technical failure: two failed attempts (EXECUTION_LOG.jsonl)" if failed.get(fid, 0) >= 2
                      else "campaign terminated: " + a.declare_campaign_terminated
                      if a.declare_campaign_terminated else "not flown / no ULog")
            fqc[fid] = {"decision": "EXCLUDED", "reason": reason, "checks": {}}
            continue
        run_json = json.loads(js.read_text()) if js.exists() else {}
        onset_param = "SIH_MOT_EFF1" if row["condition"] == "A" else "SDLOG_DIRS_MAX"
        try:
            res, meta = X.extract(ulg, onset_param)
        except Exception as e:                                 # an unreadable log is a finding
            res, meta = None, {"error": repr(e)}
        if res is None and a.mode == "dry-run" and row.get("dry_run_t0_from_driver_ms"):
            # DRY RUN ONLY: apparatus eta=1.00 flights set an unchanged value, which
            # publishes no parameter_update; take t0 as the step after the driver's send.
            u, params, ob, tr = X.load_full(ulg)
            t_send = int(row["dry_run_t0_from_driver_ms"]) * 1000
            g = ob["t_abs_us"]
            t0 = int(g[np.searchsorted(g, t_send, side="right")])
            o, trc, gg = X.cut(ob, tr, t0)
            res = {"onboard": o, "truth": trc}
            meta = {"t0_us": t0, "t_param_update_us": t_send, "onset_param": "SDLOG_DIRS_MAX",
                    "onset_value": None, "n_steps": int(len(gg)), "dropouts": len(u.dropouts),
                    "grid_gaps": int(np.sum(np.diff(gg) != 4000)),
                    "max_gap_steps": int(np.max(np.diff(gg)) // 4000),
                    "span_covered": bool(o["t_rel"][0] <= -4.99 and o["t_rel"][-1] >= 14.98),
                    "dry_run_t0_source": "driver send time"}
        checks, ok = flight_checks(row, meta, res, run_json, frozen)
        fqc[fid] = {"decision": "INCLUDED" if ok else "EXCLUDED",
                    "reason": "" if ok else "failed: " + ", ".join(k for k, v in checks.items()
                                                                    if k.startswith(("Q_", "MC_")) and not v),
                    "checks": checks, "meta": {k: v for k, v in meta.items() if k != "params"},
                    "ulog_sha256": sha256(ulg)}
        if res is not None:
            extracted[fid] = res

    blind = Path(a.blind)
    blind.mkdir(parents=True, exist_ok=True)
    salt = os.urandom(16).hex()
    key, aqc = {}, {}
    for row in analysis:
        aid, kind = row["analysis_id"], row["kind"]
        src = row["source_flight_id"]
        deps = [src] + ([row["matched_a_flight_id"]] if kind == "B" else [])
        bad = [d for d in deps if fqc.get(d, {}).get("decision") != "INCLUDED"]
        rec = {"decision": "INCLUDED", "reason": "", "checks": {}}
        if bad:
            rec = {"decision": "EXCLUDED", "reason": "depends on excluded flight(s): " + ", ".join(bad),
                   "checks": {}}
        else:
            ob = extracted[src]["onboard"]
            if kind == "B":
                ob, bchk = build_b(ob, extracted[row["matched_a_flight_id"]]["onboard"])
                rec["checks"] = bchk
                rec["b_true_rpm_motor0_T3_mean"] = float(np.nanmean(
                    extracted[src]["onboard"]["rpm_obs"][F.window_mask(ob["t_rel"], "T3"), 0]))
                if not all(v for k, v in bchk.items() if k.startswith("MC_")):
                    rec["decision"], rec["reason"] = "EXCLUDED", "case-B construction check failed"
            if rec["decision"] == "INCLUDED":
                oid = hashlib.sha256((salt + aid).encode()).hexdigest()[:16]
                np.savez_compressed(blind / f"{oid}.npz", **{k: ob[k] for k in ONBOARD_KEYS})
                key[oid] = {"analysis_id": aid, "kind": kind, "truth": TRUTH_LABEL[kind],
                            "pair_id": row["pair_id"], "eta": row["eta"], "nuisance_id": row["nuisance_id"],
                            "source_flight_id": src, "matched_a_flight_id": row["matched_a_flight_id"]}
        aqc[aid] = rec
    (blind / "INDEX.json").write_text(json.dumps(sorted(key), indent=0))
    man_sha = frozen["manifest_sha256"] if frozen else None
    Path(a.key).write_text(json.dumps({"salt": salt, "mode": a.mode, "freeze_manifest_sha256": man_sha,
                                       "trials": key}, indent=1))
    Path(a.qc).write_text(json.dumps({"mode": a.mode, "freeze_manifest_sha256": man_sha,
                                      "campaign_terminated": a.declare_campaign_terminated,
                                      "tolerances": TOL, "flights": fqc,
                                      "analysis_trials": aqc}, indent=1, default=_json_scalar))
    n_ex_f = sum(v["decision"] == "EXCLUDED" for v in fqc.values())
    n_ex_a = sum(v["decision"] == "EXCLUDED" for v in aqc.values())
    print(json.dumps({"mode": a.mode, "flights": len(fqc), "flights_excluded": n_ex_f,
                      "analysis_trials": len(aqc), "analysis_excluded": n_ex_a,
                      "blinded_inputs": len(key)}))


if __name__ == "__main__":
    main()
