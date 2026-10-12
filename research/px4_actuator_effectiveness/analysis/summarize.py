#!/usr/bin/env python3
"""Aggregate CHARACTERIZATION.json into per-level tables (JSON + Markdown).

Each cell is the median over repeats, with [min, max] where it varies.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def med(xs, fmt="{:.3f}"):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and np.isnan(x))]
    if not xs:
        return "—"
    m = float(np.median(xs))
    if max(xs) - min(xs) > 1e-9 and len(xs) > 1:
        return (fmt + " [" + fmt + ", " + fmt + "]").format(m, min(xs), max(xs))
    return fmt.format(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("characterization")
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    a = ap.parse_args()
    c = json.loads(Path(a.characterization).read_text())
    levels = sorted({r["eta_set"] for r in c["trials"]}, reverse=True)
    by = {e: [r for r in c["trials"] if r["eta_set"] == e] for e in levels}
    md = []

    md.append("| η set | η identified from log | motor-1 cmd pre → steady (peak) | κ steady (1/η) | motor-1 RPM steady | RPM implied by its cmd | motor-1 thrust steady / capacity (N) |")
    md.append("|---|---|---|---|---|---|---|")
    for e in levels:
        rs = by[e]
        md.append("| {:.2f} | {} | {} → {} ({}) | {} ({}) | {} | {} | {} / {:.2f} |".format(
            e, med([r["eta_identified_post"] for r in rs], "{:.4f}"),
            med([r["cmd0_pre"] for r in rs]), med([r["cmd0_steady"] for r in rs]), med([r["cmd0_peak"] for r in rs]),
            med([r["kappa_steady"] for r in rs], "{:.2f}"), "∞" if e == 0 else f"{1 / e:.2f}",
            med([r["rpm0_steady"] for r in rs], "{:.0f}"), med([r["rpm0_expected_from_cmd_steady"] for r in rs], "{:.0f}"),
            med([r["thrust0_steady_N"] for r in rs], "{:.2f}"), rs[0]["thrust0_capacity_N"]))
    md.append("")
    md.append("| η | peak ‖ω‖ rad/s | peak ‖ω̇‖ rad/s² | peak Δ specific force m/s² | peak tilt ° | peak att. error ° | peak EKF test ratio (pre max) | peak hover-thrust test ratio (pre max) | onset→peak s |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for e in levels:
        rs = by[e]
        md.append("| {:.2f} | {} | {} | {} | {} | {} | {} ({}) | {} ({}) | {} |".format(
            e, med([r["peak_rate_norm"] for r in rs]), med([r["peak_alpha_norm"] for r in rs], "{:.2f}"),
            med([r["peak_sf_dev_norm"] for r in rs], "{:.2f}"), med([r["peak_tilt_deg"] for r in rs], "{:.1f}"),
            med([r["peak_att_err_deg"] for r in rs], "{:.1f}"),
            med([r["peak_innov_ratio"] for r in rs], "{:.3f}"), med([r["pre_max_innov_ratio"] for r in rs], "{:.3f}"),
            med([r["peak_hte_innov_ratio"] for r in rs], "{:.2f}"), med([r["pre_max_hte_innov_ratio"] for r in rs], "{:.2f}"),
            med([r["t_peak_after_t1_s"] for r in rs], "{:.3f}")))
    md.append("")
    md.append("| η | ground contact after onset s | recovered (of repeats) | recovery time s | settle: rates / tilt / altitude s | yaw lost | altitude lost | attitude lost (>30°) | final \\|yaw rate\\| rad/s | motor 1 at limit, final 3 s |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    for e in levels:
        rs = by[e]
        au = [r["authority"] for r in rs]
        se = [r["settle_each_s"] for r in rs]
        md.append("| {:.2f} | {} | {}/{} | {} | {} / {} / {} | {}/{} | {}/{} | {}/{} | {} | {} |".format(
            e, med([r["ground_contact_after_t1_s"] for r in rs], "{:.2f}"),
            sum(r["recovered"] for r in rs), len(rs), med([r["recovery_time_s"] for r in rs], "{:.2f}"),
            med([s["rate_norm"] for s in se], "{:.2f}"), med([s["tilt"] for s in se], "{:.2f}"), med([s["alt_err"] for s in se], "{:.2f}"),
            sum(x["yaw_authority_lost"] for x in au), len(rs), sum(x["altitude_authority_lost"] for x in au), len(rs),
            sum(x["attitude_lost"] for x in au), len(rs),
            med([x["final3s_mean_abs_yaw_rate"] for x in au], "{:.3f}"), med([x["final3s_motor1_at_limit_frac"] for x in au], "{:.2f}")))
    md.append("")
    md.append("| η | param send → change ms | change → t1 ms | first response after t1 (ms): RPM / cmd / ‖ω̇‖ / ‖ω‖ / EKF ratio / HTE ratio / hover thrust |")
    md.append("|---|---|---|---|")
    for e in levels:
        tm = [r["timing"] for r in by[e]]
        md.append("| {:.2f} | {} | {} | {} / {} / {} / {} / {} / {} / {} |".format(
            e, med([x["send_to_change_ms"] for x in tm], "{:.0f}"), med([x["change_to_t1_ms"] for x in tm], "{:.0f}"),
            *[med([x[f"first_response_{k}_ms"] for x in tm], "{:.0f}") for k in
              ("rpm0", "cmd0", "alpha_norm", "rate_norm", "ratio_max", "hte_ratio", "hover_thrust")]))
    md.append("")

    # A vs B, per phase, per witness variable
    keys = ["W_CTRL.cmd0", "W_CTRL.kappa", "W_CTRL.torque_sp_norm", "W_CTRL.sat0", "W_RPM.residual0_rpm",
            "W_DYN.alpha_norm", "W_DYN.rate_norm", "W_DYN.tilt", "W_DYN.sf_dev_norm", "W_DYN.alt_err",
            "W_EST.ratio_max", "W_EST.hte_innov_ratio", "W_EST.hover_thrust"]
    ab = {}
    for e in levels:
        A = by[e]
        B = [b for b in c["case_b"] if abs(b["eta_telemetry"] - e) < 1e-9]
        ab[e] = {}
        for k in keys:
            ab[e][k] = {}
            for ph in ("onset", "compensation", "steady"):
                def vals(rows):
                    out = []
                    for r in rows:
                        cell = r["evidence"][k].get(ph)
                        out.append(None if cell is None else cell["mean"])
                    return out
                ab[e][k][ph] = {"A": vals(A), "B": vals(B)}
    md.append("| η | witness variable | onset A | onset B | compensation A | compensation B | steady A | steady B |")
    md.append("|---|---|---|---|---|---|---|---|")
    for e in levels:
        for k in keys:
            cells = []
            for ph in ("onset", "compensation", "steady"):
                for side in ("A", "B"):
                    cells.append(med(ab[e][k][ph][side], "{:.3g}"))
            md.append(f"| {e:.2f} | {k} | " + " | ".join(cells) + " |")
    Path(a.out_md).write_text("\n".join(md) + "\n")
    Path(a.out_json).write_text(json.dumps({"levels": levels, "a_vs_b": ab}, indent=1, default=float))
    print("\n".join(md[:60]))


if __name__ == "__main__":
    main()
