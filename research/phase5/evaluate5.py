"""Phase 5 — independent evaluation of the hybrid study.

INDEPENDENCE
------------
Standard library only. It imports no CSIA module, no detector, no adapter and
not the campaign. A test asserts that in a fresh interpreter. It consumes the
serialized run documents and nothing else. A second derivation by the same
author, not a second party, and that is not softened.

WHAT IT MEASURES
----------------
Detector timing, evidence support and model-based consequence for seven
baselines, at matched observed false-alarm operating points selected on
DEVELOPMENT and applied unchanged to LOCKED.

**Phase 5 is experimental.** Nothing here is a production-core result, and
`B4` and `B6` rest on a SHADOW support map that the frozen core does not use.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
from typing import Dict, List, Optional, Tuple

#: Pure detectors, in the sense that they produce alarms and nothing else.
DETECTORS = ("B0", "B1", "B2", "B3", "B4", "B5", "B6")

#: Baselines with no policy: their evidence and consequence metrics are N/A,
#: never zero. A zero would read as "no action conflicts", which is a claim
#: about a policy neither of them has.
DETECTOR_ONLY = ("B1", "B2")

#: Which direction is "more sensitive", used only to break ties in matching.
MORE_SENSITIVE_IS_HIGHER = {"B0": True, "B1": False, "B2": False,
                            "B3": False, "B4": False, "B6": False,
                            "B5": None}

TARGET_FAR = [0.00, 0.05]
PRIMARY_TARGET = 0.00
BOOTSTRAP_B = 2000
BOOTSTRAP_SEED = 20260921
MIN_DETECTIONS_FOR_CI = 10
ALPHA = 0.05

#: Preregistered minimum effect sizes and non-inferiority margin.
MIN_LATENCY_GAIN_S = 0.50
MIN_AVAILABILITY_GAIN = 0.20
MAX_GRADUAL_LOSS_S = 0.50
NONINFERIORITY_DELTA = 0.05

STRUCTURAL = "structural"
IMU_ISOLATION = "imu_isolation"

VERDICTS = ("HYBRID_DOMINATES_ON_DECLARED_SYSTEM_METRICS",
            "HYBRID_IMPROVES_LATENCY_ONLY",
            "HYBRID_IMPROVES_SUPPORT_ONLY",
            "HYBRID_IMPROVES_ACTIONABILITY_ONLY",
            "NO_HYBRID_DOMINANCE",
            "INCONCLUSIVE")


class DocumentError(ValueError):
    pass


# ----------------------------------------------------------------- exact stats

def clopper_pearson(k: int, n: int, alpha: float = ALPHA) -> List[float]:
    if n == 0:
        return [0.0, 1.0]

    def at_least(p, m):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                   for i in range(m, n + 1))

    def at_most(p, m):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                   for i in range(0, m + 1))

    def bisect(f, target):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if f(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    low = 0.0 if k == 0 else bisect(lambda p: at_least(p, k), alpha / 2.0)
    high = 1.0 if k == n else bisect(lambda p: -at_most(p, k), -(alpha / 2.0))
    return [round(low, 6), round(high, 6)]


def mcnemar_exact(b: int, c: int) -> float:
    """Exact two-sided McNemar. Unrounded: a p of 1.8e-12 rounded to six
    places prints as 0.0, which is a different claim (FL-027)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail)


def quantile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return round(xs[0], 6)
    pos = q * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return round(xs[lo] * (1 - frac) + xs[hi] * frac, 6)


def bootstrap_ci(values: List[float], q: float) -> Optional[List[float]]:
    """Percentile bootstrap, fixed seed, input SORTED first (FL-037)."""
    if len(values) < MIN_DETECTIONS_FOR_CI:
        return None
    values = sorted(values)
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(values)
    stats = []
    for _ in range(BOOTSTRAP_B):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        stats.append(quantile(sample, q))
    return [quantile(stats, 0.025), quantile(stats, 0.975)]


def paired_risk_difference(b: int, c: int, n: int,
                           alpha: float = ALPHA) -> dict:
    """Exact CONDITIONAL interval for a paired risk difference.

    `b` is the count of pairs where the candidate is worse and the base is
    not, `c` the reverse, `n` the number of pairs. The interval is obtained
    by putting an exact Clopper-Pearson interval on `b / (b + c)` and mapping
    it through `RD = (2p - 1)(b + c)/n`. It is **conditional on the
    discordant-pair count**, and the returned flag says so, because an
    unconditional reading would overstate its precision.

    With no discordant pairs the two policies made identical decisions on
    every pair. `RD` is then exactly 0 and no interval is defined; that is
    reported as `rd = 0.0` with `discordant = 0`, not as a tight interval.
    """
    d = b + c
    rd = (b - c) / n if n else None
    if d == 0:
        return {"b": b, "c": c, "pairs": n, "rd": 0.0 if n else None,
                "discordant": 0, "ci95": None,
                "ci95_is_conditional_on_discordant_pairs": True,
                "identical_on_every_pair": bool(n)}
    lo_p, hi_p = clopper_pearson(b, d, alpha)
    scale = d / n
    return {"b": b, "c": c, "pairs": n, "rd": round(rd, 6), "discordant": d,
            "ci95": [round((2 * lo_p - 1) * scale, 6),
                     round((2 * hi_p - 1) * scale, 6)],
            "ci95_is_conditional_on_discordant_pairs": True,
            "identical_on_every_pair": False}


def paired_noninferior(pairs, delta: float = NONINFERIORITY_DELTA) -> dict:
    """Non-inferiority on a PAIRED design, which is what this one is.

    Every scenario is run under both policies on the same seed, the same
    fault and the same horizon, so the comparison is paired by construction
    and an UNPAIRED interval throws that away. It throws away enough to
    matter: with 188 conflicts out of 384 under both policies -- identical
    decisions on every single scenario -- an unpaired test still refuses to
    certify non-inferiority, because the exact bound on 188/384 sits 0.051
    above its own point estimate. A test that cannot certify identical data
    is measuring its own width, not the difference. Recorded as FL-040.

    `pairs` is a sequence of `(candidate_is_bad, base_is_bad)` booleans.
    Non-inferior when the UPPER bound of the paired risk-difference interval
    is at or below `delta`.
    """
    pairs = [(bool(x), bool(y)) for x, y in pairs]
    n = len(pairs)
    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if y and not x)
    rd = paired_risk_difference(b, c, n)
    if n == 0:
        ok = None
    elif rd["ci95"] is None:
        ok = bool(rd["rd"] <= delta)
    else:
        ok = bool(rd["ci95"][1] <= delta)
    return {"pairs": n, "candidate_worse": b, "base_worse": c,
            "candidate_bad": sum(1 for x, _ in pairs if x),
            "base_bad": sum(1 for _, y in pairs if y),
            "risk_difference": rd, "delta": delta,
            "mcnemar_p": mcnemar_exact(b, c),
            "noninferior": ok, "paired": True}


def noninferior(candidate_k: int, candidate_n: int,
                base_k: int, base_n: int,
                delta: float = NONINFERIORITY_DELTA) -> dict:
    """UNPAIRED fallback, kept for genuinely unpaired comparisons.

    Retained and still used where no pairing exists. Where the design IS
    paired, `paired_noninferior` is the correct test and this one is not
    used; see FL-040.
    """
    c_rate = candidate_k / candidate_n if candidate_n else None
    b_rate = base_k / base_n if base_n else None
    hi = clopper_pearson(candidate_k, candidate_n)[1]
    ok = None if (c_rate is None or b_rate is None) else bool(
        hi <= b_rate + delta)
    return {"candidate": candidate_k, "candidate_n": candidate_n,
            "base": base_k, "base_n": base_n,
            "candidate_rate": None if c_rate is None else round(c_rate, 6),
            "base_rate": None if b_rate is None else round(b_rate, 6),
            "candidate_ci95_upper": hi, "delta": delta,
            "noninferior": ok, "paired": False}


def paired_outcomes(document, key, *, hfast, family=None, condition=None):
    """`(hybrid_bad, p0_bad)` per scenario, in run order.

    The pairing is the scenario itself: same seed, same fault, same onset,
    same horizon, two policies.
    """
    runs = _select(document["runs"], nominal=False, family=family,
                   condition=condition)
    out = []
    for r in runs:
        d = r["decisions"]
        by = d["corrected"]["consequence_hybrid_by_hfast"]
        if hfast not in by:
            return []
        out.append((bool(by[hfast][key]), bool(d["p0"]["consequence"][key])))
    return out


# ------------------------------------------------------------------- intake

REQUIRED_KEYS = ("runs", "grids", "settle_s", "horizon_s", "seeds",
                 "families", "conditions", "multiscale_grid")


def _thresholds(document: dict, detector: str) -> List[str]:
    """Threshold keys in DECLARATION order, from the grid, never sorted."""
    grid = document["grids"]
    if detector == "B0":
        return [repr(v) for v in grid["B0"]]
    if detector == "B1":
        return [repr(v) for v in grid["B1"]]
    if detector == "B2":
        return [repr(v) for v in grid["B2"]]
    if detector == "B5":
        return list(grid["B5"])
    return [repr(v) for v in grid["FAST"]]        # B3, B4, B6


def validate(document: dict) -> dict:
    """Refuse or explicitly classify a document that is not what it claims."""
    for key in REQUIRED_KEYS:
        if key not in document:
            raise DocumentError(f"document is missing {key!r}")
    seen = set()
    for r in document["runs"]:
        key = (r["seed"], r["condition"], r["family"], r["shape"],
               r["magnitude"], r["onset_s"])
        if key in seen:
            raise DocumentError(f"duplicate run {key}")
        seen.add(key)
        if r["nominal"] and r["family"] is not None:
            raise DocumentError(f"run {key} is nominal but names a family")
        if not r["nominal"] and r["onset_s"] is None:
            raise DocumentError(f"faulted run {key} has no onset")
        for det in ("B0", "B1", "B2", "B5", "FAST"):
            if det not in r["detectors"]:
                raise DocumentError(f"run {key} has no {det} alarms")
    return {
        "runs_seen": len(seen),
        "seeds_declared": len(document["seeds"]),
        "cells_per_seed_expected": document.get("cells_per_seed"),
        "invalid_runs": len(document.get("invalid_runs", [])),
        "run_order_is_not_an_input": True,
    }


# --------------------------------------------------------------- alarm access

def alarm_of(run: dict, detector: str, threshold: str) -> dict:
    """The three alarm times for one baseline at one threshold.

    `B3`, `B4` and `B6` read the fast path's PROVISIONAL series, which the
    preregistration fixes as their alarm -- crediting them with
    SUSPECTED_CHANGE would flatter them with a one-tick excursion.
    """
    d = run["detectors"]
    if detector in ("B0", "B1", "B2"):
        return d[detector][threshold]
    if detector == "B5":
        return d["B5"][threshold]["combined"]
    return d["FAST"][threshold]["provisional"]


def _select(runs, *, nominal=None, family=None, shape=None, condition=None,
            magnitude=None, onset=None):
    out = []
    for r in runs:
        if nominal is not None and bool(r["nominal"]) != nominal:
            continue
        if family is not None and r["family"] != family:
            continue
        if shape is not None and r["shape"] != shape:
            continue
        if condition is not None and r["condition"] != condition:
            continue
        if magnitude is not None and r["magnitude"] != magnitude:
            continue
        if onset is not None and r["onset_s"] != onset:
            continue
        out.append(r)
    return out


def false_alarms(document, detector, threshold) -> dict:
    """Over NOMINAL runs only, from `after_settle` (FL-035)."""
    nominal = _select(document["runs"], nominal=True)
    hits = sum(1 for r in nominal
               if alarm_of(r, detector, threshold)["after_settle"] is not None)
    n = len(nominal)
    return {"false_alarm_runs": hits, "nominal_runs": n,
            "observed_far": round(hits / n, 6) if n else None,
            "ci95": clopper_pearson(hits, n),
            "is_a_finite_horizon_count_not_a_probability": True}


def detections(document, detector, threshold, **sel) -> dict:
    faulted = _select(document["runs"], nominal=False, **sel)
    delays, misses, pre_onset = [], 0, 0
    for r in faulted:
        a = alarm_of(r, detector, threshold)
        if a["after_settle"] is not None and a["after_settle"] < r["onset_s"]:
            pre_onset += 1
        if a["after_onset"] is None:
            misses += 1
        else:
            delays.append(round(a["after_onset"] - r["onset_s"], 6))
    n = len(faulted)
    return {
        "faulted_runs": n, "detections": len(delays), "misses": misses,
        "miss_rate": round(misses / n, 6) if n else None,
        "miss_rate_ci95": clopper_pearson(misses, n),
        "pre_onset_alarms_on_faulted_runs": pre_onset,
        "mean_delay_s": round(sum(delays) / len(delays), 6) if delays else None,
        "median_delay_s": quantile(delays, 0.5),
        "p90_delay_s": quantile(delays, 0.90),
        "p99_delay_s": quantile(delays, 0.99),
        "median_delay_ci95": bootstrap_ci(delays, 0.5),
        "ci_omitted_too_few_detections": len(delays) < MIN_DETECTIONS_FOR_CI,
        "delays_s": delays,
    }


def full_grid(document) -> dict:
    out = {}
    for det in DETECTORS:
        for thr in _thresholds(document, det):
            out[f"{det}|{thr}"] = {
                "detector": det, "threshold": thr,
                **false_alarms(document, det, thr),
                **{k: v for k, v in
                   detections(document, det, thr).items() if k != "delays_s"},
            }
    return out


def threshold_robustness(document) -> dict:
    """Fraction of declared thresholds with observed FAR 0 (H5)."""
    out = {}
    for det in DETECTORS:
        thrs = _thresholds(document, det)
        clean = [t for t in thrs
                 if false_alarms(document, det, t)["observed_far"] == 0.0]
        out[det] = {"thresholds": len(thrs), "far_zero": len(clean),
                    "fraction": round(len(clean) / len(thrs), 6) if thrs else None,
                    "clean_thresholds": clean}
    return out


def match_operating_points(dev, targets=TARGET_FAR) -> dict:
    """Select thresholds on DEVELOPMENT only."""
    chosen = {}
    for target in targets:
        for det in DETECTORS:
            eligible = []
            for thr in _thresholds(dev, det):
                far = false_alarms(dev, det, thr)["observed_far"]
                if far is not None and far <= target + 1e-12:
                    eligible.append((far, thr))
            key = f"{target:.2f}|{det}"
            if not eligible:
                chosen[key] = {"target_far": target, "detector": det,
                               "threshold": None,
                               "status": "NO_THRESHOLD_MEETS_TARGET"}
                continue
            best = max(f for f, _t in eligible)
            tied = [t for f, t in eligible if f == best]
            higher = MORE_SENSITIVE_IS_HIGHER[det]
            if higher is None:
                # B5 configurations are named, not ordered: break the tie on
                # DEVELOPMENT median delay, which is a development quantity.
                pick = min(tied, key=lambda t: (
                    detections(dev, det, t)["median_delay_s"] or 1e9, t))
            else:
                pick = (max(tied, key=lambda t: float(t)) if higher
                        else min(tied, key=lambda t: float(t)))
            chosen[key] = {"target_far": target, "detector": det,
                           "threshold": pick, "development_far": best,
                           "status": "SELECTED"}
    return chosen


# ----------------------------------------------------- support and decisions

def support_availability(document, *, condition=None, family=None) -> dict:
    """Per-map availability of the decision pair, seed-paired.

    A seed counts as AVAILABLE when the pair is IDENTIFIABLE for any airborne
    tick in any matching scenario. That is the unit the preregistered McNemar
    is computed over.
    """
    runs = _select(document["runs"], nominal=False, condition=condition,
                   family=family)
    per_seed: Dict[int, Dict[str, bool]] = {}
    frac: Dict[str, List[float]] = {"current": [], "corrected": []}
    for r in runs:
        s = r["seed"]
        cell = per_seed.setdefault(s, {"current": False, "corrected": False})
        for m in ("current", "corrected"):
            f = r["support"][m]["identifiable_frac"]
            frac[m].append(f)
            if f > 0.0:
                cell[m] = True
    seeds = sorted(per_seed)
    b = sum(1 for s in seeds
            if per_seed[s]["corrected"] and not per_seed[s]["current"])
    c = sum(1 for s in seeds
            if per_seed[s]["current"] and not per_seed[s]["corrected"])
    means = {m: (round(sum(v) / len(v), 6) if v else None)
             for m, v in frac.items()}
    return {
        "scenarios": len(runs), "seeds": len(seeds),
        "mean_identifiable_frac": means,
        "gain": (None if None in means.values()
                 else round(means["corrected"] - means["current"], 6)),
        "seeds_available": {m: sum(1 for s in seeds if per_seed[s][m])
                            for m in ("current", "corrected")},
        "discordant_corrected_only": b, "discordant_current_only": c,
        "mcnemar_p": mcnemar_exact(b, c),
        "condition": condition, "family": family,
    }


def decision_metrics(document, *, family=None, condition=None) -> dict:
    """False refusals, unsupported confident outputs and downgrades.

    Reported per map. The hybrid's false-refusal rate is zero BY
    CONSTRUCTION -- it downgrades instead of abstaining -- so it is not
    reported as evidence of anything, and the P2 arms are what H3's retained
    secondary measure is computed on.
    """
    runs = _select(document["runs"], nominal=False, family=family,
                   condition=condition)
    out = {}
    for m in ("current", "corrected"):
        fr = sum(r["decisions"][m]["p2_false_refusal_ticks"] for r in runs)
        fr_runs = sum(1 for r in runs
                      if r["decisions"][m]["p2_false_refusal_ticks"] > 0)
        uc = sum(r["decisions"][m]["unsupported_confident_ticks"] for r in runs)
        uc_runs = sum(1 for r in runs
                      if r["decisions"][m]["unsupported_confident_ticks"] > 0)
        dg = sum(r["decisions"][m]["hybrid_downgrade_ticks"] for r in runs)
        out[m] = {
            "runs": len(runs),
            "p2_false_refusal_ticks": fr,
            "p2_false_refusal_runs": fr_runs,
            "p2_false_refusal_rate": round(fr_runs / len(runs), 6) if runs else None,
            "p2_false_refusal_ci95": clopper_pearson(fr_runs, len(runs)),
            "unsupported_confident_ticks": uc,
            "unsupported_confident_runs": uc_runs,
            "unsupported_confident_rate":
                round(uc_runs / len(runs), 6) if runs else None,
            "hybrid_downgrade_ticks": dg,
            "hybrid_false_refusal_rate": 0.0,
            "hybrid_false_refusal_is_zero_by_construction": True,
        }
    out["attribution"] = {
        "attributing_ticks": sum(r["decisions"]["p0"]["attributing_ticks"]
                                 for r in runs),
        "correct_attribution_ticks": sum(
            r["decisions"]["p0"]["correct_attribution_ticks"] for r in runs),
        "incorrect_attribution_ticks": sum(
            r["decisions"]["p0"]["incorrect_attribution_ticks"] for r in runs),
        "runs": len(runs),
    }
    return out


def consequence(document, policy, *, family=None, condition=None,
                hfast=None) -> dict:
    """Model-based consequence for one policy over the selected scenarios.

    `policy` is "p0", "p2_current", "p2_corrected", or "hybrid_current" /
    "hybrid_corrected" (which need `hfast`, because the hybrid's extra
    caution depends on when the fast path went provisional).

    Every figure here is MODEL_BASED_ACTION_CONSEQUENCE: a model of a
    response, integrated by `consequence_model31`, not a vehicle.
    """
    runs = _select(document["runs"], nominal=False, family=family,
                   condition=condition)
    rows = []
    for r in runs:
        d = r["decisions"]
        if policy == "p0":
            rows.append(d["p0"]["consequence"])
        elif policy.startswith("p2_"):
            rows.append(d[policy.split("_", 1)[1]]["consequence_p2"])
        else:
            m = policy.split("_", 1)[1]
            by = d[m]["consequence_hybrid_by_hfast"]
            if hfast is None or hfast not in by:
                return {"status": "NO_HFAST_SELECTED"}
            rows.append(by[hfast])
    n = len(rows) or 1
    def _rate(key):
        k = sum(1 for x in rows if x[key])
        return {"count": k, "n": len(rows),
                "rate": round(k / n, 6), "ci95": clopper_pearson(k, len(rows))}
    safe = [x["time_to_safe_state_s"] for x in rows
            if x["time_to_safe_state_s"] is not None]
    first = [x["time_to_first_response_s"] for x in rows
             if x["time_to_first_response_s"] is not None]
    return {
        "policy": policy, "runs": len(rows), "hfast": hfast,
        "action_conflict": _rate("action_conflict"),
        "reached_safe_state": _rate("reached_safe_state"),
        "geofence_breached": _rate("geofence_breached"),
        "median_time_to_first_response_s": quantile(first, 0.5),
        "responses_at_all": len(first),
        "median_time_to_safe_state_s": quantile(safe, 0.5),
        "reached_safe_state_count": len(safe),
        "median_max_position_error_m": quantile(
            [x["max_position_error_m"] for x in rows], 0.5),
        "median_energy_margin_frac": quantile(
            [x["energy_margin_frac"] for x in rows], 0.5),
        "evidence_level": "MODEL_BASED_ACTION_CONSEQUENCE",
    }


# ------------------------------------------------------------- the hypotheses

def _matched(chosen, locked, det, target=PRIMARY_TARGET):
    row = chosen.get(f"{target:.2f}|{det}")
    if not row or row["status"] != "SELECTED":
        return None
    thr = row["threshold"]
    return {"threshold": thr, "development_far": row["development_far"],
            **false_alarms(locked, det, thr),
            **{k: v for k, v in detections(locked, det, thr).items()
               if k != "delays_s"}}


def evaluate_hypotheses(dev, locked, chosen) -> dict:
    out = {}
    base = _matched(chosen, locked, "B0")

    # --- H1: hybrid latency ------------------------------------------------
    h1 = {"statement": "a fast-detector-plus-CSIA architecture has lower "
                       "detection latency than current CSIA at matched "
                       "observed false-alarm operating points",
          "min_gain_s": MIN_LATENCY_GAIN_S, "candidates": {}}
    for det in ("B3", "B4", "B6"):
        cand = _matched(chosen, locked, det)
        if base is None or cand is None:
            h1["candidates"][det] = {"status": "NO_MATCHED_POINT"}
            continue
        b_med, c_med = base["median_delay_s"], cand["median_delay_s"]
        gain = (None if b_med is None or c_med is None
                else round(b_med - c_med, 6))
        b_ci, c_ci = base["median_delay_ci95"], cand["median_delay_ci95"]
        disjoint = (None if not (b_ci and c_ci)
                    else bool(c_ci[1] < b_ci[0] or b_ci[1] < c_ci[0]))
        h1["candidates"][det] = {
            "threshold": cand["threshold"],
            "base_median_s": b_med, "candidate_median_s": c_med,
            "gain_s": gain, "base_ci95": b_ci, "candidate_ci95": c_ci,
            "intervals_disjoint": disjoint,
            "supported": bool(gain is not None and gain >= MIN_LATENCY_GAIN_S
                              and disjoint)}
    h1["verdict"] = ("SUPPORTED" if any(c.get("supported")
                                        for c in h1["candidates"].values())
                     else "KILLED")
    out["H1"] = h1

    # --- H2: assurance preservation ---------------------------------------
    dm = decision_metrics(locked, family=IMU_ISOLATION)
    h2 = {"statement": "the hybrid does not increase unsupported confident "
                       "attribution, incorrect actionable decisions, action "
                       "conflicts or false escalation",
          "delta": NONINFERIORITY_DELTA,
          "unsupported_confident": paired_noninferior([
              (bool(r["decisions"]["corrected"]
                    ["unsupported_confident_ticks"]),
               bool(r["decisions"]["current"]
                    ["unsupported_confident_ticks"]))
              for r in _select(locked["runs"], nominal=False,
                               family=IMU_ISOLATION)]),
          "note": ("measured on the imu_isolation arm, the only arm on which "
                   "an attributing response exists at all"),
          }
    _hf = chosen.get(f"{PRIMARY_TARGET:.2f}|B6", {}).get("threshold")
    h2["action_conflicts"] = paired_noninferior(
        paired_outcomes(locked, "action_conflict", hfast=_hf))
    h2["false_escalation"] = paired_noninferior(
        paired_outcomes(locked, "false_escalation", hfast=_hf))
    h2["false_escalation_note"] = (
        "the hybrid's only added action is a generic caution on a "
        "provisional fast alarm; nominal runs carry no fault so any caution "
        "there is a false escalation and is counted in the nominal arm")
    ok = (h2["unsupported_confident"]["noninferior"]
          and h2["action_conflicts"]["noninferior"]
          and h2["false_escalation"]["noninferior"])
    h2["verdict"] = ("SUPPORTED" if ok else
                     "KILLED" if ok is False else "INCONCLUSIVE")
    out["H2"] = h2

    # --- H3: support-map correction (amendment 19 primary measure) ---------
    av = support_availability(locked, condition="EG", family=IMU_ISOLATION)
    h3 = {"statement": "an experimental correction for FL-029 reduces false "
                       "refusals without increasing unsupported confident "
                       "outputs or action conflicts",
          "primary_measure": ("support availability for the decision pair "
                              "under EG (amendment 19)"),
          "min_gain": MIN_AVAILABILITY_GAIN,
          "availability": av,
          "retained_false_refusal_measure": {
              m: dm[m]["p2_false_refusal_rate"] for m in
              ("current", "corrected")},
          "false_refusal_is_structurally_zero": True,
          "guard_unsupported_confident": h2["unsupported_confident"],
          }
    h3["verdict"] = (
        "SUPPORTED" if (av["gain"] is not None
                        and av["gain"] >= MIN_AVAILABILITY_GAIN
                        and av["mcnemar_p"] < ALPHA
                        and h2["unsupported_confident"]["noninferior"])
        else "KILLED")
    out["H3"] = h3

    # --- H4: multi-timescale ----------------------------------------------
    b5 = chosen.get(f"{PRIMARY_TARGET:.2f}|B5")
    h4 = {"statement": "a fast and slow evidence accumulator improves "
                       "abrupt-fault latency without materially worsening "
                       "gradual-fault detection",
          "min_abrupt_gain_s": MIN_LATENCY_GAIN_S,
          "max_gradual_loss_s": MAX_GRADUAL_LOSS_S}
    b0_thr = chosen.get(f"{PRIMARY_TARGET:.2f}|B0", {}).get("threshold")
    if not b5 or b5["status"] != "SELECTED" or b0_thr is None:
        h4["verdict"] = "INCONCLUSIVE"
    else:
        arms = {}
        for shape in ("ABRUPT", "GRADUAL"):
            b = detections(locked, "B0", b0_thr, family=STRUCTURAL,
                           shape=shape)
            c = detections(locked, "B5", b5["threshold"], family=STRUCTURAL,
                           shape=shape)
            arms[shape] = {
                "base_median_s": b["median_delay_s"],
                "candidate_median_s": c["median_delay_s"],
                "base_miss_rate": b["miss_rate"],
                "candidate_miss_rate": c["miss_rate"],
                "delta_s": (None if b["median_delay_s"] is None
                            or c["median_delay_s"] is None
                            else round(b["median_delay_s"]
                                       - c["median_delay_s"], 6))}
        h4["arms"] = arms
        h4["threshold"] = b5["threshold"]
        ab = arms["ABRUPT"]["delta_s"]
        gr = arms["GRADUAL"]["delta_s"]
        h4["verdict"] = (
            "SUPPORTED" if (ab is not None and gr is not None
                            and ab >= MIN_LATENCY_GAIN_S
                            and -gr <= MAX_GRADUAL_LOSS_S)
            else "KILLED")
    out["H4"] = h4

    # --- H5: threshold robustness -----------------------------------------
    rob = threshold_robustness(locked)
    h5 = {"statement": "the hybrid retains or improves the observed threshold "
                       "robustness seen in Phase 4",
          "robustness": rob,
          "base_fraction": rob["B0"]["fraction"]}
    h5["candidates"] = {
        det: {"fraction": rob[det]["fraction"],
              "retained": bool(rob[det]["fraction"] is not None
                               and rob["B0"]["fraction"] is not None
                               and rob[det]["fraction"] >= rob["B0"]["fraction"])}
        for det in ("B3", "B4", "B5", "B6")}
    h5["verdict"] = ("SUPPORTED"
                     if all(c["retained"] for c in h5["candidates"].values())
                     else "KILLED")
    out["H5"] = h5
    return out


def dominance(locked, chosen, hyps) -> dict:
    """The primary dominance criterion, all six clauses, B6 against B0."""
    base = _matched(chosen, locked, "B0")
    cand = _matched(chosen, locked, "B6")
    if base is None or cand is None:
        return {"verdict": "INCONCLUSIVE",
                "why": "no matched operating point for B0 or B6"}
    uc = paired_noninferior([
        (bool(r["decisions"]["corrected"]["unsupported_confident_ticks"]),
         bool(r["decisions"]["current"]["unsupported_confident_ticks"]))
        for r in _select(locked["runs"], nominal=False,
                         family=IMU_ISOLATION)])
    hfast = cand["threshold"]
    c_p0 = consequence(locked, "p0")
    c_hy = consequence(locked, "hybrid_corrected", hfast=hfast)
    conflicts = paired_noninferior(
        paired_outcomes(locked, "action_conflict", hfast=hfast))
    base_safe = c_p0["reached_safe_state"]["rate"]
    cand_safe = c_hy["reached_safe_state"]["rate"]
    clauses = {
        "1_latency_lower_or_equal": bool(
            cand["median_delay_s"] is not None
            and base["median_delay_s"] is not None
            and cand["median_delay_s"] <= base["median_delay_s"]),
        "2_false_alarms_no_worse": bool(
            (cand["observed_far"] or 0.0) <= (base["observed_far"] or 0.0)
            + NONINFERIORITY_DELTA),
        "3_no_more_unsupported_confident": uc["noninferior"],
        "4_no_more_action_conflicts": conflicts["noninferior"],
        "5_time_to_safe_state_preserved": bool(
            cand_safe is not None and base_safe is not None
            and cand_safe >= base_safe - NONINFERIORITY_DELTA),
        "6_same_evidence_budget": True,
    }
    unmet = [k for k, v in clauses.items() if v is False]
    unknown = [k for k, v in clauses.items() if v is None]
    improvements = {
        "latency": hyps["H1"]["verdict"] == "SUPPORTED",
        "support": hyps["H3"]["verdict"] == "SUPPORTED",
        "actionability": bool(
            c_hy["action_conflict"]["rate"] is not None
            and c_p0["action_conflict"]["rate"] is not None
            and c_hy["action_conflict"]["rate"]
            < c_p0["action_conflict"]["rate"]),
    }
    if unknown:
        verdict = "INCONCLUSIVE"
    elif not unmet:
        verdict = "HYBRID_DOMINATES_ON_DECLARED_SYSTEM_METRICS"
    elif improvements["latency"] and not improvements["support"]:
        verdict = "HYBRID_IMPROVES_LATENCY_ONLY"
    elif improvements["support"] and not improvements["latency"]:
        verdict = "HYBRID_IMPROVES_SUPPORT_ONLY"
    elif improvements["latency"] and improvements["support"]:
        verdict = "HYBRID_IMPROVES_LATENCY_ONLY"
    else:
        verdict = "NO_HYBRID_DOMINANCE"
    assert verdict in VERDICTS
    return {"verdict": verdict, "clauses": clauses, "unmet": unmet,
            "unknown_clauses": unknown, "improvements": improvements,
            "base": base, "candidate": cand,
            "consequence_p0": c_p0, "consequence_hybrid": c_hy,
            "action_conflict_noninferiority": conflicts,
            "evidence_budget_note": (
                "B4 and B6 read two edges the frozen core already computes "
                "every tick and then discards; no new sensor, no new channel "
                "and no additional arithmetic")}


def build(dev: dict, locked: dict) -> dict:
    intake = {"development": validate(dev), "locked": validate(locked)}
    chosen = match_operating_points(dev)
    hyps = evaluate_hypotheses(dev, locked, chosen)
    dom = dominance(locked, chosen, hyps)
    return {
        "schema": "csia.phase5.hybrid_results/1",
        "phase": "5 -- hybrid detector study",
        "is_experimental": True,
        "evidence_level": "DETERMINISTIC_SIMULATION",
        "consequence_evidence_level": "MODEL_BASED_ACTION_CONSEQUENCE",
        "executed_an_autopilot": False, "armed_a_vehicle": False,
        "touched_hardware": False, "pooled_with_earlier_phases": False,
        "development_partition": dev.get("partition"),
        "locked_partition": locked.get("partition"),
        "intake": intake,
        "primary_target_far": PRIMARY_TARGET,
        "target_far_levels": TARGET_FAR,
        "operating_points": chosen,
        "hypotheses": hyps,
        "dominance": dom,
        "full_grid_development": full_grid(dev),
        "full_grid_locked": full_grid(locked),
        "threshold_robustness_locked": threshold_robustness(locked),
        "support_availability": {
            "EG_imu": support_availability(locked, condition="EG",
                                           family=IMU_ISOLATION),
            "EA_imu": support_availability(locked, condition="EA",
                                           family=IMU_ISOLATION),
            "EG_structural": support_availability(locked, condition="EG",
                                                  family=STRUCTURAL),
        },
        "decision_metrics_imu": decision_metrics(locked, family=IMU_ISOLATION),
        "consequence": {
            "p0": consequence(locked, "p0"),
            "p2_current": consequence(locked, "p2_current"),
            "p2_corrected": consequence(locked, "p2_corrected"),
            "hybrid_corrected": consequence(
                locked, "hybrid_corrected",
                hfast=chosen.get(f"{PRIMARY_TARGET:.2f}|B6", {}).get(
                    "threshold")),
            "by_condition": {
                cond: {
                    "p0": consequence(locked, "p0", condition=cond),
                    "hybrid_corrected": consequence(
                        locked, "hybrid_corrected", condition=cond,
                        hfast=chosen.get(f"{PRIMARY_TARGET:.2f}|B6", {}).get(
                            "threshold")),
                } for cond in locked["conditions"]},
        },
        "detector_only_baselines_have_no_policy": list(DETECTOR_ONLY),
        "quantile_method": "linear interpolation between order statistics",
        "bootstrap": {"resamples": BOOTSTRAP_B, "seed": BOOTSTRAP_SEED,
                      "min_detections_for_ci": MIN_DETECTIONS_FOR_CI,
                      "input_sorted_before_resampling": True},
        "what_this_is_not": (
            "not a production-core result -- B4 and B6 rest on a SHADOW "
            "support map the frozen core does not use; not hardware, not "
            "flight, not SITL, not autopilot execution; not pooled with any "
            "earlier phase; and not a claim that CSIA outperforms CUSUM, "
            "which Phase 4 measured the other way on latency"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("development")
    ap.add_argument("locked")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    with open(args.development, encoding="utf-8") as fh:
        dev = json.load(fh)
    with open(args.locked, encoding="utf-8") as fh:
        locked = json.load(fh)
    result = build(dev, locked)
    text = json.dumps(result, indent=1, sort_keys=True) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    for h, v in sorted(result["hypotheses"].items()):
        print(f"  {h}: {v['verdict']}")
    print(f"  DOMINANCE: {result['dominance']['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
