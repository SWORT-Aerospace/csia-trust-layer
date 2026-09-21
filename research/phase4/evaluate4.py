"""Phase 4 — independent evaluation of the detector campaign.

INDEPENDENCE
------------
Standard library only. It imports no CSIA module, no detector implementation
and not the campaign. A test asserts that in a fresh interpreter. It consumes
the serialized alarm times and nothing else. A second derivation by the same
author, not a second party, and that is not softened.

WHAT IT MEASURES AND WHAT IT DOES NOT
--------------------------------------
Detector delay against false-alarm rate. **No action, no policy, no failsafe
level, no vehicle outcome.** The consequence question belongs to Phases 3,
3.1 and 3.2 and is not reopened here.

THE MATCHING RULE IS THE WHOLE COMPARISON
------------------------------------------
Thresholds are selected on DEVELOPMENT only, at declared target false-alarm
levels, and applied unchanged to LOCKED. A favourable threshold for one
detector is never compared with an unfavourable one for another, and the full
grid is reported alongside the matched points so a reader can see everything
the matching chose between.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
from typing import Dict, List, Optional

DETECTORS = ("CSIA", "CUSUM", "BINST")

#: Which direction is "more sensitive", used only to break ties in matching.
#: CSIA alarms when trust falls BELOW theta, so a higher theta is more
#: sensitive; CUSUM and the bare threshold alarm above, so lower is.
MORE_SENSITIVE_IS_HIGHER = {"CSIA": True, "CUSUM": False, "BINST": False}

TARGET_FAR = [0.00, 0.05, 0.10]
PRIMARY_TARGET = 0.00
BOOTSTRAP_B = 2000
BOOTSTRAP_SEED = 20260920
MIN_DETECTIONS_FOR_CI = 10
ALPHA = 0.05


class DocumentError(ValueError):
    pass


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


def quantile(values: List[float], q: float) -> Optional[float]:
    """Linear interpolation between order statistics, declared explicitly so
    two implementations of "the 90th percentile" cannot disagree silently."""
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
    """Percentile bootstrap, fixed seed, or None when there is too little.

    THE INPUT IS SORTED FIRST, and that is not cosmetic. Resampling draws by
    INDEX, so with a fixed seed the interval depends on which permutation of
    the delays the caller happened to pass -- and that permutation is the
    order the runs sit in the campaign file, which is arbitrary. Two files
    holding identical data in different order would then report different
    intervals. Sorting makes the interval a function of the multiset of
    delays, which is what it is supposed to be. Found by the test that
    shuffles the committed locked runs and asserts nothing moves; see
    FL-037.
    """
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


def _thresholds(document: dict, detector: str) -> List[str]:
    """Threshold keys in DECLARATION order, taken from the grid and not from
    whatever order the run dictionaries happen to iterate in."""
    return [repr(v) for v in document["grids"][detector]]


ALARM_KEYS = ("first", "after_settle", "after_onset")
REQUIRED_KEYS = ("runs", "grids", "settle_s", "horizon_s", "fault", "seeds")


def validate(document: dict) -> dict:
    """Refuse or explicitly classify a document that is not what it claims.

    REFUSED OUTRIGHT, because no honest number can be computed from them:
    a missing required key; a duplicate `(seed, gain, onset)`; a run with no
    alarms for some detector; a run missing a declared threshold; an alarm
    record missing one of the three alarm times; a nominal run that carries a
    gain or an onset; a faulted run with no onset; a gain or onset outside
    the declared grid.

    EXPLICITLY CLASSIFIED, because they are facts a reader must be told
    rather than errors: a seed that does not carry the full
    `nominal + gain x onset` cross (`incomplete_seeds`), and a declared grid
    cell with no run at all (`empty_cells`).

    NOT AN ERROR: the order of `runs`. Every figure here is computed by
    filtering, so reordering the list changes nothing, and a test asserts
    that on the real artifact rather than asserting it in prose.
    """
    for key in REQUIRED_KEYS:
        if key not in document:
            raise DocumentError(f"document is missing {key!r}")
    gains = list(document["fault"]["gain_grid"])
    onsets = list(document["fault"]["onset_grid"])
    seen = set()
    for r in document["runs"]:
        key = (r["seed"], r["gain"], r["onset_s"])
        if key in seen:
            raise DocumentError(f"duplicate run {key}")
        seen.add(key)
        if r["nominal"]:
            if r["gain"] is not None or r["onset_s"] is not None:
                raise DocumentError(
                    f"run {key} is flagged nominal but carries a fault")
        else:
            if r["onset_s"] is None:
                raise DocumentError(f"faulted run {key} has no onset")
            if r["gain"] not in gains:
                raise DocumentError(
                    f"run {key} has gain {r['gain']!r}, not in the declared "
                    f"grid {gains}")
            if r["onset_s"] not in onsets:
                raise DocumentError(
                    f"run {key} has onset {r['onset_s']!r}, not in the "
                    f"declared grid {onsets}")
        for det in DETECTORS:
            if det not in r["alarms"]:
                raise DocumentError(f"run {key} has no {det} alarms")
            missing = set(_thresholds(document, det)) - set(r["alarms"][det])
            if missing:
                raise DocumentError(
                    f"run {key} is missing {det} thresholds {sorted(missing)}")
            for thr, rec in r["alarms"][det].items():
                absent = [k for k in ALARM_KEYS if k not in rec]
                if absent:
                    raise DocumentError(
                        f"run {key} {det} {thr} is missing {absent}")

    expected = {(None, None)} | {(g, o) for g in gains for o in onsets}
    incomplete, empty = [], []
    for seed in document["seeds"]:
        have = {(g, o) for (s, g, o) in seen if s == seed}
        short = sorted(expected - have, key=repr)
        if short:
            incomplete.append({"seed": seed, "missing_cells": short})
    for cell in sorted(expected, key=repr):
        if not any((g, o) == cell for (_s, g, o) in seen):
            empty.append(list(cell))
    return {
        "runs_seen": len(seen),
        "seeds_declared": len(document["seeds"]),
        "cells_per_seed_expected": len(expected),
        "incomplete_seeds": incomplete,
        "all_seeds_complete": not incomplete,
        "empty_declared_cells": empty,
        "run_order_is_not_an_input": True,
    }


def false_alarms(document: dict, detector: str, threshold: str) -> dict:
    """Over NOMINAL runs only. A run either has a false alarm or it does not,
    so the rate is per horizon."""
    nominal = [r for r in document["runs"] if r["nominal"]]
    # `after_settle`, NOT `first`. A latched detector that crossed during
    # the settling window is still alarming inside the horizon, and counting
    # from `first` alone would score it as clean. See FL-035.
    hits = sum(1 for r in nominal
               if r["alarms"][detector][threshold]["after_settle"] is not None)
    n = len(nominal)
    return {"false_alarm_runs": hits, "nominal_runs": n,
            "false_alarms_per_horizon": round(hits / n, 6) if n else None,
            "ci95": clopper_pearson(hits, n)}


def detections(document: dict, detector: str, threshold: str,
               *, gain=None, onset=None) -> dict:
    faulted = [r for r in document["runs"] if not r["nominal"]
               and (gain is None or r["gain"] == gain)
               and (onset is None or r["onset_s"] == onset)]
    delays, misses, pre_onset = [], 0, 0
    for r in faulted:
        a = r["alarms"][detector][threshold]
        if (a["after_settle"] is not None
                and a["after_settle"] < r["onset_s"]):
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
        "p90_delay_ci95": bootstrap_ci(delays, 0.90),
        "ci_omitted_too_few_detections": len(delays) < MIN_DETECTIONS_FOR_CI,
        "delays_s": delays,
    }


def full_grid(document: dict) -> dict:
    out = {}
    for det in DETECTORS:
        for thr in _thresholds(document, det):
            out[f"{det}|{thr}"] = {
                "detector": det, "threshold": float(thr),
                **false_alarms(document, det, thr),
                **{k: v for k, v in detections(document, det, thr).items()
                   if k != "delays_s"},
            }
    return out


def match_operating_points(dev: dict, targets=TARGET_FAR) -> dict:
    """Select thresholds on DEVELOPMENT only."""
    chosen = {}
    for target in targets:
        for det in DETECTORS:
            eligible = []
            for thr in _thresholds(dev, det):
                far = false_alarms(dev, det, thr)["false_alarms_per_horizon"]
                if far is not None and far <= target + 1e-12:
                    eligible.append((far, float(thr), thr))
            key = f"{target:.2f}|{det}"
            if not eligible:
                chosen[key] = {"target_far": target, "detector": det,
                               "threshold": None,
                               "status": "NO_THRESHOLD_MEETS_TARGET"}
                continue
            best_far = max(f for f, _v, _k in eligible)
            tied = [(v, k) for f, v, k in eligible if f == best_far]
            value, thr = (max(tied) if MORE_SENSITIVE_IS_HIGHER[det]
                          else min(tied))
            chosen[key] = {"target_far": target, "detector": det,
                           "threshold": value, "threshold_key": thr,
                           "development_far": best_far, "status": "SELECTED"}
    return chosen


def build(dev: dict, locked: dict) -> dict:
    intake = {"development": validate(dev), "locked": validate(locked)}
    chosen = match_operating_points(dev)

    matched = {}
    for key, pick in sorted(chosen.items()):
        if pick["status"] != "SELECTED":
            matched[key] = pick
            continue
        det, thr = pick["detector"], pick["threshold_key"]
        row = dict(pick)
        row.update(false_alarms(locked, det, thr))
        row.update({k: v for k, v in detections(locked, det, thr).items()
                    if k != "delays_s"})
        row["locked_far_exceeds_development_far"] = bool(
            (row["false_alarms_per_horizon"] or 0.0) > pick["development_far"])
        row["by_gain"] = {
            str(g): {k: v for k, v in
                     detections(locked, det, thr, gain=g).items()
                     if k != "delays_s"}
            for g in locked["fault"]["gain_grid"]}
        row["by_onset"] = {
            str(o): {k: v for k, v in
                     detections(locked, det, thr, onset=o).items()
                     if k != "delays_s"}
            for o in locked["fault"]["onset_grid"]}
        matched[key] = row

    ticks = sum(r["ticks"] for r in locked["runs"])
    cost = {}
    for field, label in (("ns_series_shared", "series_shared_by_all_three"),
                         ("ns_csia", "CSIA"), ("ns_cusum", "CUSUM"),
                         ("ns_binst", "BINST"), ("ns_total", "total")):
        xs = [r[field] for r in locked["runs"] if field in r]
        if not xs:
            continue
        n_thr = len(locked["grids"].get(label, [])) or None
        cost[label] = {
            "mean_ns_per_run": round(sum(xs) / len(xs), 1),
            "mean_ns_per_tick": round(sum(xs) / ticks, 1),
            "mean_ns_per_tick_per_threshold":
                round(sum(xs) / ticks / n_thr, 1) if n_thr else None,
            "thresholds_in_grid": n_thr,
        }
    ns = [r["ns_total"] for r in locked["runs"]]
    return {
        "schema": "csia.phase4.detector_results/1",
        "phase": "4 -- detector performance",
        "measures": "detector delay and false alarms only",
        "evidence_level": "DETERMINISTIC_SIMULATION",
        "executed_an_autopilot": False, "armed_a_vehicle": False,
        "touched_hardware": False,
        "pooled_with_consequence_phases": False,
        "development_partition": dev.get("partition"),
        "locked_partition": locked.get("partition"),
        "intake": intake,
        "primary_target_far": PRIMARY_TARGET,
        "target_far_levels": TARGET_FAR,
        "operating_points": matched,
        "full_grid_development": full_grid(dev),
        "full_grid_locked": full_grid(locked),
        "quantile_method": "linear interpolation between order statistics",
        "bootstrap": {"resamples": BOOTSTRAP_B, "seed": BOOTSTRAP_SEED,
                      "min_detections_for_ci": MIN_DETECTIONS_FOR_CI},
        "computational_cost": {
            "total_runs": len(ns), "total_ticks": ticks,
            "mean_ns_per_run": round(sum(ns) / len(ns), 1) if ns else None,
            "mean_ns_per_tick": round(sum(ns) / ticks, 1) if ticks else None,
            "per_detector": cost,
            "note": ("wall clock on this container: ENVIRONMENT-SPECIFIC and "
                     "not a portable figure. Each detector's figure covers "
                     "its FULL declared threshold grid, so the per-threshold "
                     "column is the one to compare. The series build is "
                     "shared by all three and is reported on its own line "
                     "rather than charged to any one of them; it dominates "
                     "every detector by orders of magnitude, which is the "
                     "honest headline of this row."),
        },
        "what_this_is_not": (
            "not a consequence measurement, not hardware, not flight, not "
            "autopilot execution, not pooled with any consequence phase, and "
            "not a novelty claim -- CUSUM is Page (1954) and is used as the "
            "prior-art baseline it is."),
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
    print(f"matched operating points (primary target FAR = "
          f"{PRIMARY_TARGET:.2f}):")
    for key, row in sorted(result["operating_points"].items()):
        if not key.startswith(f"{PRIMARY_TARGET:.2f}"):
            continue
        if row["status"] != "SELECTED":
            print(f"  {row['detector']:6s} {row['status']}")
            continue
        print(f"  {row['detector']:6s} thr={row['threshold']:<8} "
              f"dev_far={row['development_far']:.3f} "
              f"locked_far={row['false_alarms_per_horizon']:.3f} "
              f"miss={row['miss_rate']:.3f} "
              f"median={row['median_delay_s']} p90={row['p90_delay_s']} "
              f"p99={row['p99_delay_s']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
