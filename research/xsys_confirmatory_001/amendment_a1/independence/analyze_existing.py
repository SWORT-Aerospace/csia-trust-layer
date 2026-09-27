#!/usr/bin/env python3
"""XSYS-001-A1 Part 2: dependence in the ORIGINAL nuisance design, from data
that already exist. Apparatus-validation and nuisance-pilot logs only; no new
flight; nominal segments only (sweep flights are used before their onset).

Usage:
  analyze_existing.py --nominal <dir> --nominal2 <dir> --sweep <dir> --pilot <dir> --out EXISTING_DATA_DEPENDENCE.json

Each directory holds decompressed .ulg files; every file is checked against
the archived SHA256SUMS before use.
"""
import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

import independence_diagnostics as ID

REPO = ID.X.parents[1]
SUMS = {
    "nominal": REPO / "research/px4_actuator_effectiveness/raw_ulog/nominal_batch1/SHA256SUMS",
    "nominal2": REPO / "research/px4_actuator_effectiveness/raw_ulog/nominal_batch2/SHA256SUMS",
    "sweep": REPO / "research/px4_actuator_effectiveness/raw_ulog/sweep/SHA256SUMS",
    "pilot": ID.X / "apparatus_pilot/SHA256SUMS",
}
ORIGINAL_OFFSETS_S = [0.5 * k for k in range(1, 11)]          # original design: onset separations 0.5 .. 5.0 s


def load_group(g, d, sums):
    want = dict(reversed(l.split()) for l in Path(sums).read_text().splitlines() if l.endswith(".ulg"))
    out = []
    for name in sorted(want):
        p = Path(d) / name
        f = ID.Flight(p)
        if f.sha256 != want[name]:
            raise SystemExit(f"{p} does not match {sums}")
        f.name = f"{g}/{f.name}"                            # the two nominal batches reuse file names
        out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    for g in SUMS:
        ap.add_argument(f"--{g}", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    groups = {g: load_group(g, getattr(a, g), SUMS[g]) for g in SUMS}
    flights = [f for g in groups.values() for f in g]
    group_of = {f.name: g for g, fs in groups.items() for f in fs}
    res = {"label": "XSYS-001-A1 PART 2 - EXISTING NOMINAL DATA - NOT CONFIRMATORY",
           "diagnostic_spec_sha256": ID.sha256(ID.HERE / "DIAGNOSTIC_SPEC.json"),
           "inputs": {f.name: f.sha256 for f in flights}}

    # ---- A. residual model (sensor noise)
    pooled = np.concatenate([f.r[(f.t > 25e6) & (f.t < 30e6)] for f in flights])
    lag1 = [float(np.corrcoef(pooled[:-1, k], pooled[1:, k])[0, 1]) for k in range(3)]
    res["A_residual_model"] = {
        "std_rad_s": pooled.std(0).round(6).tolist(), "lag1_autocorrelation": np.round(lag1, 3).tolist(),
        "interpretation": "trapezoidal IMU integral of two consecutive SIH draws: std 0.01/sqrt(2), lag-1 0.5",
        "chance_coincidence_per_step_pair": float((2 * ID.TOL / (0.01 * np.sqrt(2 * np.pi))) ** 3)}

    # ---- E. families (DX5): every pair, 1 s bins, whole flight
    pairs = {}
    region_pre = (25.0, 30.0)                               # hover before any onset, every group
    for fa, fb in combinations(flights, 2):
        edges, fr = ID.family_bins(fa, fb, 0.0, 45.0)
        e = np.array(edges)
        pre = [x for x, t in zip(fr, e) if region_pre[0] <= t < region_pre[1] and x is not None]
        post = [x for x, t in zip(fr, e) if 30.0 <= t < 44.0 and x is not None]
        pairs[f"{fa.name}|{fb.name}"] = {
            "groups": [group_of[fa.name], group_of[fb.name]],
            "same_fraction_25_30s": float(np.mean(pre)) if pre else None,
            "same_fraction_30_44s": float(np.mean(post)) if post else None,
            "prearm_1_9s": float(np.mean([x for x, t in zip(fr, e) if 1 <= t < 9 and x is not None])),
            "branch_time_s": ID.branch_time(edges, fr)}
    cls = {k: ID.classify(v["same_fraction_25_30s"]) for k, v in pairs.items()}
    # connected components of the 'same' relation over 25-30 s
    parent = {f.name: f.name for f in flights}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for k, c in cls.items():
        if c == "same":
            x, y = k.split("|")
            parent[find(x)] = find(y)
    fam = {}
    for f in flights:
        fam.setdefault(find(f.name), []).append(f.name)
    families = sorted(fam.values(), key=len, reverse=True)

    def rate(sel):
        ks = [k for k in pairs if sel(pairs[k])]
        n_same = sum(cls[k] == "same" for k in ks)
        return {"pairs": len(ks), "same_family_25_30s": n_same,
                "fraction": n_same / len(ks) if ks else None,
                "mixed": sum(cls[k] == "mixed" for k in ks)}
    same_config = lambda p: p["groups"][0] == p["groups"][1]  # noqa: E731
    # pairs of identically configured launches that stay together through 44 s
    persist = [k for k in pairs if cls[k] == "same" and pairs[k]["same_fraction_30_44s"] is not None
               and pairs[k]["groups"][0] in ("nominal", "nominal2", "pilot")
               and pairs[k]["groups"][1] in ("nominal", "nominal2", "pilot")]
    res["E_families"] = {
        "families_25_30s": [{"size": len(v), "members": sorted(v)} for v in families],
        "n_families": len(families), "n_flights": len(flights),
        "same_family_rate_all_pairs": rate(lambda p: True),
        "same_family_rate_same_group": rate(same_config),
        "same_family_rate_pilot_pairs": rate(lambda p: p["groups"] == ["pilot", "pilot"]),
        "same_family_pairs_still_identical_30_44s": {
            "pairs": len(persist),
            "median_same_fraction": float(np.median([pairs[k]["same_fraction_30_44s"] for k in persist])) if persist else None,
            "min_same_fraction": float(np.min([pairs[k]["same_fraction_30_44s"] for k in persist])) if persist else None},
        "branch_times_s_of_pairs_that_branch": sorted({round(v["branch_time_s"], 1) for v in pairs.values()
                                                       if v["branch_time_s"] not in (None, 0.0)})[:40],
    }
    res["E_pairs"] = pairs

    # ---- E2. identity of every pair at the same simulated time (+-40 steps), 25-44 s
    ident = {}
    for fa, fb in combinations(flights, 2):
        hi = 44.0 if all(group_of[f.name] != "sweep" for f in (fa, fb)) else 30.0
        byl = ID.identity_by_lag(fa, fb, 25.0, hi, 40)
        best = max(byl, key=lambda L: byl[L] or 0)
        ident[f"{fa.name}|{fb.name}"] = {"zero_lag": byl[0], "best_lag_steps": best, "best": byl[best],
                                        "window_s": [25.0, hi]}
    best = np.array([v["best"] for v in ident.values()])
    res["E2_identity_all_pairs"] = {
        "construction": "fraction of coincident draws at the best lag within +-40 steps (0.16 s), 25-44 s "
                        "(25-30 s when a sweep flight is involved, before its onset)",
        "pairs": len(best),
        "fraction_of_pairs_with_best_identity_ge": {str(t): float((best >= t).mean())
                                                   for t in (0.99, 0.9, 0.5, 0.1, 0.01, 0.001)},
        "median_best_identity": float(np.median(best)), "min_best_identity": float(best.min()),
        "best_lag_steps_histogram": {str(k): int(v) for k, v in zip(*np.unique(
            [x["best_lag_steps"] for x in ident.values()], return_counts=True))},
        "pairs_detail": ident}

    # ---- D. original design: two conditions t0 apart by delta, same family
    same_pairs = [k.split("|") for k in pairs if cls[k] == "same"
                  and pairs[k]["groups"][0] in ("nominal", "nominal2") and pairs[k]["groups"][1] in ("nominal", "nominal2")]
    by = {f.name: f for f in flights}
    rng = np.random.default_rng(20260927)
    sample = [same_pairs[i] for i in rng.choice(len(same_pairs), size=min(12, len(same_pairs)), replace=False)]
    t0a = 25_000_000
    emu = []
    for x, y in sample:
        fa, fb = by[x], by[y]
        for d in (0.5, 2.5, 5.0):
            t0b = t0a + int(d * 1e6)
            idn = ID.identity_global(fa, fa.span_mask(t0a), fb, fb.span_mask(t0b))
            emu.append({"a": x, "b": y, "onset_separation_s": d, **idn})
    res["D_original_design_emulation"] = {
        "construction": "two same-family launches treated as two conditions with onsets 25 s and 25 s + delta "
                        "(the original design's separations are 0.5 .. 5 s); DX1 over their spans",
        "cases": emu,
        "I_min": float(min(e["I"] for e in emu)) if emu else None,
        "C1_would_hold": all(e["I"] <= 0.001 for e in emu) if emu else None}

    # ---- B/C. frozen-statistic lag correlation at the original separations (one stream per flight)
    hover = [f for f in flights if group_of[f.name] in ("nominal", "nominal2", "pilot")
             or f.name.startswith("sweep/sweep_eta100")]
    series = {}
    for f in hover:
        end_s = (f.t_disarm_us or f.t[-1]) * 1e-6 - 0.3
        grid, s = ID.pseudo_onset_series(f, 27.0, end_s - 0.2, 0.1, need_T3=False)
        grid3, s3 = ID.pseudo_onset_series(f, 27.0, end_s - 15.0, 0.1, need_T3=True) if end_s - 15.0 > 27.2 else (None, None)
        series[f.name] = (s, s3)
    lagcorr = {}
    for d in ORIGINAL_OFFSETS_S:
        lag = int(round(d / 0.1))
        row = {}
        for key in ("D_T1_m0", "L_T1_m0", "D_T1_m1", "D_T1_m2", "D_T1_m3"):
            xs, ys = [], []
            for s, _ in series.values():
                v = s[key]
                if lag < len(v):
                    xs.append(v[:len(v) - lag]); ys.append(v[lag:])
            x, y = np.concatenate(xs), np.concatenate(ys)
            ok = np.isfinite(x) & np.isfinite(y)
            row[key] = float(np.corrcoef(x[ok], y[ok])[0, 1])
        for key in ("C_T3_m0", "L_T3_m0", "C_T3_m1"):
            xs, ys = [], []
            for _, s3 in series.values():
                if s3 is None:
                    continue
                v = s3[key]
                if lag < len(v):
                    xs.append(v[:len(v) - lag]); ys.append(v[lag:])
            if xs:
                x, y = np.concatenate(xs), np.concatenate(ys)
                ok = np.isfinite(x) & np.isfinite(y)
                row[key] = float(np.corrcoef(x[ok], y[ok])[0, 1]) if ok.sum() > 20 else None
                row[key + "_n"] = int(ok.sum())
        lagcorr[f"{d:.1f}"] = row
    res["BC_statistic_lag_correlation_original_separations"] = {
        "meaning": "correlation of a frozen null statistic between two onsets delta apart in ONE noise stream = "
                   "between two same-family conditions of the original design",
        "by_separation_s": lagcorr}

    # ---- D. same family, different heading: trajectories and statistics at the same simulated time
    pil = {f.name: f for f in groups["pilot"]}
    fam_pil = []
    for x, y in combinations(sorted(pil), 2):
        k = f"{x}|{y}" if f"{x}|{y}" in pairs else f"{y}|{x}"
        if cls.get(k) != "same":
            continue
        fa, fb = pil[x], pil[y]
        c, i, j = np.intersect1d(fa.t, fb.t, return_indices=True)
        m = (c >= 25e6) & (c < 44e6)
        wc = [float(np.corrcoef(fa.w_true[i][m, q], fb.w_true[j][m, q])[0, 1]) for q in range(2)]
        sa, _ = series[x]; sb, _ = series[y]
        n = min(len(sa["D_T1_m0"]), len(sb["D_T1_m0"]))
        dc = float(np.corrcoef(sa["D_T1_m0"][:n], sb["D_T1_m0"][:n])[0, 1])
        fam_pil.append({"a": x, "b": y, "true_roll_rate_corr_25_44s": wc[0], "true_pitch_rate_corr_25_44s": wc[1],
                        "D_T1_m0_series_corr_same_time": dc})
    res["D_same_family_different_heading"] = fam_pil

    # ---- replays at nonzero lags (DX1 global) between different-family launches
    reps = []
    names = [fs[0] for fs in families]
    for x, y in combinations(names, 2):
        fa, fb = by[x], by[y]
        ma = (fa.t >= 25e6) & (fa.t < 44e6)
        mb = (fb.t >= 12e6) & (fb.t < 44e6)
        reps.append({"a": x, "b": y, **ID.identity_global(fa, ma, fb, mb)})
    res["replay_at_other_lags"] = {
        "construction": "one representative per family; span [25, 44) s of a against [12, 44) s of b, every lag",
        "pairs": len(reps), "max_I": float(max(r["I"] for r in reps)) if reps else None,
        "cases": reps}

    Path(a.out).write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({"A": res["A_residual_model"], "families": [len(v) for v in families],
                      "same_group_rate": res["E_families"]["same_family_rate_same_group"],
                      "pilot_rate": res["E_families"]["same_family_rate_pilot_pairs"],
                      "persist": res["E_families"]["same_family_pairs_still_identical_30_44s"],
                      "emulation_I_min": res["D_original_design_emulation"]["I_min"],
                      "lagcorr_0.5": lagcorr["0.5"], "lagcorr_5.0": lagcorr["5.0"],
                      "same_family_diff_heading": fam_pil,
                      "replay_max_I": res["replay_at_other_lags"]["max_I"],
                      "E2": {k: v for k, v in res["E2_identity_all_pairs"].items() if k != "pairs_detail"}}, indent=1, default=float))


if __name__ == "__main__":
    main()
