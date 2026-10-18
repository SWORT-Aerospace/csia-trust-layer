#!/usr/bin/env python3
"""Three monitors on one IMU: the correlated-evidence preview (Parts 29, 37,
38). SYNTHETIC, SHADOW ONLY, RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/imu_dependency_preview.py

Monitor A  threshold detector on IMU1 rate         lineage {imu1}
Monitor B  CUSUM on IMU1 rate                      lineage {imu1}
Monitor C  estimator innovation (IMU1-driven       lineage {imu1, gps, model:ekf}
           prediction against GNSS)
Monitor D  threshold detector on IMU2 (control     lineage {imu2}
           case only)

The question is how many INDEPENDENT confirmations an alarm pattern carries,
and whether each policy counts that number, more, or fewer:

    NAIVE          one confirmation per alarming record
    CURRENT_2_1    2.1 does not count; the independence notion it has is
                   "another domain" (C1's cross-domain discriminator), so the
                   column is the number of distinct domains among alarms. The
                   2.1 attribution of each case is also run, with and without
                   the estimator's declared dependency on IMU1, to show how
                   2.1 represents the monitors today.
    DEP_AWARE      the minimal dependency model: records with the same
                   producer and claim collapse (duplicates), and support is
                   the largest set of alarming records whose source lineages
                   are pairwise disjoint
    DEP_AWARE+VAL  the same, after dropping records whose content is older
                   than the producer's declared validity (the stale case)

`true_independent` is fixed by construction for each case. Writes
IMU_DEPENDENCY_PREVIEW.json only.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from csia.v2.evidence import Applicability, EvidenceRecord  # noqa: E402
from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia_semantic_core import attribute_2_1  # noqa: E402

OUT = HERE / "IMU_DEPENDENCY_PREVIEW.json"

MONITORS = {
    "A": dict(domain="SENSOR", component="imu1", relation="monitor.rate_threshold",
              producer="threshold@imu1", lineage={"imu1"}),
    "B": dict(domain="SENSOR", component="imu1", relation="monitor.cusum_mean_shift",
              producer="cusum@imu1", lineage={"imu1"}),
    "C": dict(domain="COMPUTE", component="state_estimator", relation="monitor.innovation",
              producer="ekf_innovation@lane0", lineage={"imu1", "gps", "model:ekf"}),
    "D": dict(domain="SENSOR", component="imu2", relation="monitor.rate_threshold",
              producer="threshold@imu2", lineage={"imu2"}),
}

#: case -> (alarming monitors, nominal monitors, extras, true independent
#: confirmations of the alarm, what is actually true)
CASES = {
    "1_all_three_agree": (["A", "B", "C"], [], {}, 1,
                          "one source (IMU1) is anomalous; nothing independent corroborates it"),
    "2_AB_agree_C_differs": (["A", "B"], ["C"], {}, 1,
                             "IMU1 shows a rate the GNSS-aided estimator agrees with: real motion, one source"),
    "3_imu1_biased": (["A", "B", "C"], [], {}, 1,
                      "IMU1 bias; every alarm descends from it"),
    "4_estimator_model_wrong": (["C"], ["A", "B"], {}, 1,
                                "the estimator's model is wrong; IMU1 is fine"),
    "5_duplicated_output": (["A", "B", "C"], [], {"duplicate_of": "A"}, 1,
                            "as case 3, with A republished under a new identity"),
    "6_one_monitor_stale": (["B"], ["A", "C"], {"stale": "B"}, 0,
                            "the anomaly ended; B's CUSUM output is latched from before"),
    "7_control_two_imus": (["A", "D"], ["B"], {}, 2,
                           "two independent IMUs both see the rate: genuine corroboration"),
}


def record(key, alarm, dep_declared, identity=None):
    m = MONITORS[key]
    deps = ()
    if key == "C" and dep_declared:
        deps = ("SENSOR/imu1",)
    return EvidenceRecord(
        domain=m["domain"], component=m["component"], relation=m["relation"],
        source=identity or m["producer"],
        observation_state=OS.VIOLATED if alarm else OS.NOMINAL,
        applicability=Applicability.APPLICABLE,
        reason_codes=("MONITOR_ALARM",) if alarm else (),
        provenance={"producer": m["producer"], "claim": m["relation"],
                    "lineage": sorted(m["lineage"])},
        dependencies=deps)


def max_disjoint(lineages):
    best = 0
    for n in range(len(lineages), 0, -1):
        for combo in itertools.combinations(lineages, n):
            if all(a.isdisjoint(b) for a, b in itertools.combinations(combo, 2)):
                return n
    return best


def main():
    out = {"harness": "semantic_core_2_1_imu_dependency_preview", "cases": {}}
    totals = {p: {"over_count": 0, "false_corroboration": 0, "lost_corroboration": 0}
              for p in ("NAIVE", "CURRENT_2_1", "DEP_AWARE", "DEP_AWARE+VAL")}
    for case, (alarms, nominal, extra, truth_n, what) in CASES.items():
        alarm_recs = [(k, record(k, True, True)) for k in alarms]
        if extra.get("duplicate_of"):
            alarm_recs.append((extra["duplicate_of"],
                               record(extra["duplicate_of"], True, True,
                                      identity="bridge@republished")))
        naive = len(alarm_recs)
        domains = len({r.domain for _k, r in alarm_recs})
        seen, dedup = set(), []
        for k, r in alarm_recs:
            key = (r.provenance["producer"], r.provenance["claim"])
            if key not in seen:
                seen.add(key)
                dedup.append((k, r))
        dep = max_disjoint([set(r.provenance["lineage"]) for _k, r in dedup])
        dep_val = max_disjoint([set(r.provenance["lineage"]) for k, r in dedup
                                if k != extra.get("stale")])
        counts = {"NAIVE": naive, "CURRENT_2_1": domains, "DEP_AWARE": dep,
                  "DEP_AWARE+VAL": dep_val}
        attrib = {}
        for declared in (True, False):
            recs = [record(k, True, declared) for k in alarms] + \
                   [record(k, False, declared) for k in nominal]
            a = attribute_2_1(recs, ())
            attrib["C_depends_on_imu1_declared" if declared else "C_dependency_undeclared"] = {
                "verdict": a.verdict, "candidates": list(a.candidates),
                "common_cause": a.v2.common_cause,
                "withheld_because": list(a.withheld_unique_because)}
        for p, n in counts.items():
            totals[p]["over_count"] += max(0, n - truth_n)
            totals[p]["false_corroboration"] += int(n >= 2 and truth_n < 2)
            totals[p]["lost_corroboration"] += int(truth_n >= 2 and n < 2)
        out["cases"][case] = {"what_is_true": what, "true_independent": truth_n,
                              "alarms": alarms, "nominal": nominal, "extra": extra,
                              "support_count": counts, "attribution_2_1": attrib}
    out["totals"] = totals
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
    for c, v in out["cases"].items():
        print(c, v["true_independent"], v["support_count"],
              {k: (x["verdict"], x["candidates"]) for k, x in v["attribution_2_1"].items()})
    print(json.dumps(totals, indent=1))


if __name__ == "__main__":
    main()
