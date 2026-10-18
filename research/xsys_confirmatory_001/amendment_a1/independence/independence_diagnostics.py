#!/usr/bin/env python3
"""XSYS-001-A1 nuisance-independence diagnostics (implements DIAGNOSTIC_SPEC.json).

NOMINAL DATA ONLY. Every statistic is computed with the frozen
research/xsys_confirmatory_001/pipeline/xsys_features.py; nothing here is a
new evidence definition.

  existing  Part 2: dependence in the ORIGINAL design, from apparatus and
            pilot logs already archived (families, in-span noise identity,
            frozen-statistic lag correlation, same-family trajectories,
            replays at other lags)
  memory    DX6 and DX2/DX3 from the long nominal hover Q1; fixes S
  design    C1..C5 for the candidate design from pilots Q2..Q5 (+ Q1)

Measured property of the residual used by DX1 (see EXISTING_DATA_DEPENDENCE.json):
sensor_combined.gyro_rad is PX4's trapezoidal IMU integral of two consecutive
SIH samples, so r(k) = (n_k + n_(k-1))/2 + tiny state terms: std 0.0071 rad/s,
lag-1 autocorrelation 0.5. Two INDEPENDENT residuals coincide on all three axes
within 3e-4 rad/s with probability 1.4e-5 per step pair; identical noise gives
|dr| ~ 1e-6.
"""
import argparse
import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
from pyulog import ULog

HERE = Path(__file__).resolve().parent
X = HERE.parents[1]
sys.path.insert(0, str(X / "pipeline"))
import xsys_extract as XE  # noqa: E402
import xsys_features as F  # noqa: E402

SPEC = json.loads((HERE / "DIAGNOSTIC_SPEC.json").read_text())
TOL = 3e-4
STEP_US = 4000
SPAN = (-5.0, 15.0)
STATS = ("L_T1", "D_T1", "L_T3", "C_T3")
CAL = json.loads((X / "calibration" / "CALIBRATION.json").read_text())["calibration"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ------------------------------------------------------------------ loading
class Flight:
    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.stem
        u = ULog(str(path))
        sc = u.get_dataset("sensor_combined").data
        gt = u.get_dataset("vehicle_angular_velocity_groundtruth").data
        c, i, j = np.intersect1d(sc["timestamp"], gt["timestamp"], return_indices=True)
        self.t = c.astype(np.int64)
        self.r = np.stack([sc[f"gyro_rad[{a}]"][i].astype(float) - gt[f"xyz[{a}]"][j] for a in range(3)], 1)
        self.w_true = np.stack([gt[f"xyz[{a}]"][j].astype(float) for a in range(3)], 1)
        st = u.get_dataset("vehicle_status").data
        armed = st["timestamp"][st["arming_state"] == 2]
        self.t_arm_us = int(armed[0]) if len(armed) else None
        self.t_disarm_us = int(armed[-1]) if len(armed) else None
        self._full = None
        self.sha256 = sha256(path)

    def full(self):
        if self._full is None:
            u, params, ob, tr = XE.load_full(self.path)
            self._full = (ob, tr)
        return self._full

    def span_mask(self, t0_us, back_s=0.0):
        lo = t0_us + int((SPAN[0] - back_s) * 1e6)
        hi = t0_us + int(SPAN[1] * 1e6)
        return (self.t >= lo) & (self.t < hi)


# ------------------------------------------------------------------ DX5 families
def family_bins(a, b, lo_s=0.0, hi_s=None, bin_s=1.0):
    c, i, j = np.intersect1d(a.t, b.t, return_indices=True)
    same = np.max(np.abs(a.r[i] - b.r[j]), 1) < TOL
    hi_s = hi_s if hi_s is not None else c[-1] * 1e-6
    edges = np.arange(lo_s, hi_s + 1e-9, bin_s)
    out = []
    for e0, e1 in zip(edges[:-1], edges[1:]):
        m = (c >= e0 * 1e6) & (c < e1 * 1e6)
        out.append(None if m.sum() == 0 else float(same[m].mean()))
    return edges[:-1].tolist(), out


def classify(frac):
    if frac is None:
        return None
    return "same" if frac >= 0.99 else "different" if frac <= 0.01 else "mixed"


def branch_time(edges, fracs):
    """First bin after which the pair stays 'different' to the end; None if
    never different; 0 if different from the start."""
    cls = [classify(f) for f in fracs]
    last_not_diff = max((k for k, c in enumerate(cls) if c not in ("different", None)), default=-1)
    if last_not_diff == len(cls) - 1:
        return None
    return edges[last_not_diff + 1]


# ------------------------------------------------------------------ DX1 identity
def identity_global(a, mask_a, b, mask_b):
    """I(a,b): max over all lags of coincident draws / steps in span a."""
    ra, ta = a.r[mask_a], a.t[mask_a]
    rb, tb = b.r[mask_b], b.t[mask_b]
    if len(ra) == 0 or len(rb) == 0:
        return {"I": None, "n_a": int(len(ra))}
    order = np.argsort(rb[:, 0])
    xb = rb[order, 0]
    lags = []
    for s in range(0, len(ra), 2000):
        xa = ra[s:s + 2000, 0]
        lo = np.searchsorted(xb, xa - TOL, "left")
        hi = np.searchsorted(xb, xa + TOL, "right")
        cnt = hi - lo
        ia = np.repeat(np.arange(s, s + len(xa)), cnt)
        ib = order[np.concatenate([np.arange(l, h) for l, h in zip(lo, hi)])] if cnt.sum() else np.array([], int)
        if len(ia) == 0:
            continue
        ok = np.max(np.abs(ra[ia] - rb[ib]), 1) < TOL
        lags.append(np.round((tb[ib[ok]] - ta[ia[ok]]) / STEP_US).astype(np.int64))
    lags = np.concatenate(lags) if lags else np.array([], np.int64)
    if len(lags) == 0:
        return {"I": 0.0, "n_a": int(len(ra)), "matches": 0, "best_lag_steps": None}
    vals, counts = np.unique(lags, return_counts=True)
    k = int(np.argmax(counts))
    return {"I": float(counts[k] / len(ra)), "n_a": int(len(ra)), "matches": int(len(lags)),
            "best_lag_steps": int(vals[k]), "best_lag_s": float(vals[k] * STEP_US * 1e-6),
            "second_best_count": int(np.sort(counts)[-2]) if len(counts) > 1 else 0}


def identity_by_lag(a, b, lo_s, hi_s, max_lag_steps=40):
    """Coincident-draw fraction at each lag in [-max, +max] steps over [lo, hi) s
    of a (the same-sim-time neighbourhood; DX1's global search covers all lags)."""
    k0, k1 = int(round(lo_s * 1e6 / STEP_US)), int(round(hi_s * 1e6 / STEP_US))
    n = k1 - k0 + 2 * max_lag_steps

    def grid(f, base):
        g = np.full((n, 3), np.nan)
        k = np.round(f.t / STEP_US).astype(np.int64) - base
        ok = (k >= 0) & (k < n)
        g[k[ok]] = f.r[ok]
        return g
    ga = grid(a, k0 - max_lag_steps)
    gb = grid(b, k0 - max_lag_steps)
    core = slice(max_lag_steps, max_lag_steps + (k1 - k0))
    xa = ga[core]
    out = {}
    for lag in range(-max_lag_steps, max_lag_steps + 1):
        xb = gb[max_lag_steps + lag: max_lag_steps + lag + (k1 - k0)]
        ok = np.isfinite(xa[:, 0]) & np.isfinite(xb[:, 0])
        out[lag] = float((np.max(np.abs(xa[ok] - xb[ok]), 1) < TOL).mean()) if ok.any() else None
    return out


# ------------------------------------------------------------------ frozen statistics
def stats_at(flight, t0_us):
    ob, tr = flight.full()
    o, _, _ = XE.cut(ob, tr, t0_us)
    t = o["t_rel"]
    out = {}
    for m in range(4):
        rho, _ = F.rpm_ratio(o["rpm_obs"][:, m], o["cmd_sim"][:, m])
        ax = F.loss_axis(o["rotor_px"][m], o["rotor_py"][m])
        for w in ("T1", "T3"):
            L, ok = F.local_deficit(rho, o["cmd_sim"][:, m], t, w)
            out[f"L_{w}_m{m}"] = L if ok else np.nan
        D, ok = F.dynamics_statistic(o["gyro"], t, ax, "T1")
        out[f"D_T1_m{m}"] = D if ok else np.nan
        C, ok = F.compensation_statistic(o["cmd_alloc"], t, m, "T3")
        out[f"C_T3_m{m}"] = C if ok else np.nan
    return out


def pseudo_onset_series(flight, t_from_s, t_to_s, step_s=0.2, need_T3=True):
    grid = np.arange(t_from_s, t_to_s + 1e-9, step_s)
    rows = []
    for ts in grid:
        t0 = int(round(ts * 1e6 / STEP_US)) * STEP_US
        s = stats_at(flight, t0)
        if not need_T3:
            s = {k: v for k, v in s.items() if "T3" not in k}
        rows.append(s)
    keys = sorted(rows[0])
    return grid, {k: np.array([r.get(k, np.nan) for r in rows]) for k in keys}


def lag_corr(series_a, series_b, lag_steps):
    if lag_steps >= len(series_a):
        return None
    x = series_a[:len(series_a) - lag_steps]
    y = series_b[lag_steps:]
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 20 or np.std(x[ok]) == 0 or np.std(y[ok]) == 0:
        return None
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


# ------------------------------------------------------------------ DX6 memory
def memory_signals(flight, lo_s, hi_s):
    ob, tr = flight.full()
    g = ob["t_abs_us"]
    m = (g >= lo_s * 1e6) & (g < hi_s * 1e6)
    sig = {}
    for k in range(4):
        rho, _ = F.rpm_ratio(ob["rpm_obs"][m, k], ob["cmd_sim"][m, k])
        sig[f"rho_m{k}"] = rho
        others = [j for j in range(4) if j != k]
        with np.errstate(divide="ignore", invalid="ignore"):
            sig[f"kappa_m{k}"] = ob["cmd_alloc"][m, k] / ob["cmd_alloc"][m][:, others].mean(1)
    sig["gyro_roll"] = ob["gyro"][m, 0]
    sig["gyro_pitch"] = ob["gyro"][m, 1]
    return sig


def acf(x, max_lag):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    x = x - x.mean()
    n = len(x)
    f = np.fft.rfft(x, 2 * n)
    a = np.fft.irfft(f * np.conj(f))[:max_lag + 1]
    return a / a[0]


def memory_length(ac, step_s, window_s=60.0):
    """Smallest lag L with |acf| <= 0.1 on [L, L + window_s]."""
    w = int(round(window_s / step_s))
    bad = np.abs(ac) > 0.1
    # last lag that is still bad, searching only where a full window fits
    for L in range(0, len(ac) - w):
        if not bad[L:L + w + 1].any():
            return L * step_s
    return None


# ------------------------------------------------------------------ DX4 trajectory
def span_signals(flight, t0_us):
    ob, tr = flight.full()
    o, trc, _ = XE.cut(ob, tr, t0_us)
    ax = F.loss_axis(o["rotor_px"][0], o["rotor_py"][0])
    rho, _ = F.rpm_ratio(o["rpm_obs"][:, 0], o["cmd_sim"][:, 0])
    with np.errstate(divide="ignore", invalid="ignore"):
        kappa = o["cmd_alloc"][:, 0] / o["cmd_alloc"][:, 1:].mean(1)
    k_rel = np.round(o["t_rel"] / F.STEP_S).astype(int)
    return k_rel, {"gyro_loss_axis_m0": o["gyro"][:, :2] @ ax, "kappa_m0": kappa, "rho_m0": rho,
                   "w_true_roll": trc["w_true"][:, 0], "w_true_pitch": trc["w_true"][:, 1]}


def trajectory_corr(fa, t0a, fb, t0b):
    ka, sa = span_signals(fa, t0a)
    kb, sb = span_signals(fb, t0b)
    common, ia, ib = np.intersect1d(ka, kb, return_indices=True)
    out = {}
    for k in sa:
        x, y = sa[k][ia], sb[k][ib]
        ok = np.isfinite(x) & np.isfinite(y)
        out[k] = float(np.corrcoef(x[ok], y[ok])[0, 1]) if ok.sum() > 20 else None
    return out


def hover_nulls(flight, lo_s, hi_s, step_s=0.5):
    """Frozen null statistics at hover pseudo-onsets (motor 0), as calibrated."""
    L1, D1, C3 = [], [], []
    for ts in np.arange(lo_s, hi_s - 0.2, step_s):
        t0 = int(round(ts * 1e6 / STEP_US)) * STEP_US
        s = stats_at(flight, t0)
        L1.append(abs(s["L_T1_m0"]))
        D1.append(abs(s["D_T1_m0"]))
        if ts + 15.0 <= hi_s:
            C3.append(abs(s["C_T3_m0"]))
    f = lambda v: float(np.nanmax(v)) if len(v) else None  # noqa: E731
    return {"n": len(L1), "n_C": len(C3), "max_abs_L_T1": f(L1), "max_abs_D_T1": f(D1), "max_abs_C_T3": f(C3),
            "below_thresholds": bool((f(L1) or 0) < CAL["delta_rpm"] and (f(D1) or 0) < CAL["theta_dyn"]
                                     and (not C3 or f(C3) < CAL["theta_ctrl"]))}
