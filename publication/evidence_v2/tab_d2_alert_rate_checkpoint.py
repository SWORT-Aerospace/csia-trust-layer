#!/usr/bin/env python3
"""Deliverable 2, checkpoint: the 3.859 alert episodes per monitored hour on
the 26 UNANNOTATED PX4 logs, and its exact (Garwood) Poisson 95 interval,
recomputed from the committed counts.

    python publication/evidence_v2/tab_d2_alert_rate_checkpoint.py

Definitions used, all repo-normative (docs/validation/METRIC_DEFINITIONS.md):
alert episode (section 1.1), rate per hour with an exact Garwood interval
(section 2). Exposure is monitored hours: per-log duration minus `arm_time_s`
(datasets/reports/exposure_v2.json, `exposure_basis: monitored`).

This is NOT a false-alarm rate. The corpus is UNANNOTATED (verified-healthy
exposure 0.0 h), so no episode can be scored as false
(publication/system_paper_i/evidence_export/08_REAL_LOG_RESULTS.md section 4).

The operating curve against an alarm threshold is not produced: see
EVIDENCE_V2_REPORT.md, blocked items.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

from scipy.stats import chi2  # noqa: E402

EXPOSURE = os.path.join(C.ROOT, "datasets", "reports", "exposure_v2.json")
FLIGHTS = os.path.join(C.ROOT, "data", "real_logs_report.json")
OUT = os.path.join(C.TABLES, "d2_alert_episode_rate_checkpoint.csv")


def garwood(k: int, t: float) -> tuple[float, float]:
    lo = 0.0 if k == 0 else chi2.ppf(0.025, 2 * k) / 2.0 / t
    hi = chi2.ppf(0.975, 2 * k + 2) / 2.0 / t
    return lo, hi


def main() -> int:
    exp = json.load(open(EXPOSURE, encoding="utf-8"))
    pay = exp["payload"]
    cat = pay["rates_by_health_category"]["UNANNOTATED"]
    k, t_mon = cat["alert_episodes"], cat["exposure_hours"]
    arm = pay["arm_time_s"]

    flights = json.load(open(FLIGHTS, encoding="utf-8"))["flights"]
    raw_h = sum(f["duration_s"] for f in flights) / 3600.0
    mon_h = sum(max(0.0, f["duration_s"] - arm) for f in flights) / 3600.0
    short = [f["log"] for f in flights if f["duration_s"] < arm]

    rate = k / t_mon
    lo, hi = garwood(k, t_mon)
    rate_raw = k / raw_h
    lo_raw, hi_raw = garwood(k, raw_h)

    rows = [
        ("logs", len(flights), cat["logs"], "", "data/real_logs_report.json flights; exposure_v2 logs"),
        ("alert_episodes", k, k, "", "exposure_v2 UNANNOTATED.alert_episodes (input, not recomputed)"),
        ("raw_hours", round(raw_h, 4), pay["exposure"]["total_raw_hours"], "", "sum of duration_s / 3600"),
        ("monitored_hours", round(mon_h, 4), t_mon, "", f"sum of max(0, duration_s - {arm}) / 3600"),
        ("rate_per_monitored_hour", round(rate, 3), cat["rate_per_hour"], 3.859, "k / monitored hours"),
        ("garwood_95_lower", round(lo, 3), cat["ci95_per_hour"][0], 0.467, "chi2.ppf(0.025, 2k) / 2T"),
        ("garwood_95_upper", round(hi, 3), cat["ci95_per_hour"][1], 13.939, "chi2.ppf(0.975, 2k + 2) / 2T"),
        ("rate_per_raw_hour", round(rate_raw, 3), "", "", "k / raw hours; the basis METRIC_DEFINITIONS.md 1.2 still quotes"),
        ("garwood_95_lower_raw_basis", round(lo_raw, 3), "", "", "raw-hours basis"),
        ("garwood_95_upper_raw_basis", round(hi_raw, 3), "", "", "raw-hours basis"),
    ]
    C.write_csv(OUT, ("quantity", "recomputed", "artifact_value", "checkpoint_value", "how"), rows)

    match = (round(rate, 3) == 3.859 and round(lo, 3) == 0.467 and round(hi, 3) == 13.939
             and round(mon_h, 4) == t_mon and len(flights) == cat["logs"] == 26)
    ids = sorted(f["log"].replace("fr_", "").replace(".ulg", "") for f in flights)
    C.stamp(OUT, __file__, inputs=(EXPOSURE, FLIGHTS),
            datasets={"dataset_id": pay["dataset_id"],
                      "dataset_aggregate_hash": pay["dataset_aggregate_hash"],
                      "health_category": "UNANNOTATED",
                      "log_uuids": ids,
                      "raw_log_sha256": "not recorded in the artifact (input_logs sha256 null); "
                                        "raw logs are not in the repository",
                      "artifact_config_hashes": {
                          "csia_config_hash": exp["experiment_manifest"]["csia_config_hash"],
                          "failsafe_config_hash": exp["experiment_manifest"]["failsafe_config_hash"]}},
            seeds={"note": "none: deterministic replay counts and closed-form intervals"},
            definitions=[
                {"metric": "alert episode", "source": "docs/validation/METRIC_DEFINITIONS.md", "section": "1.1"},
                {"metric": "rate with exact Garwood 95 interval", "source": "docs/validation/METRIC_DEFINITIONS.md", "section": "2"},
                {"metric": "monitored exposure", "source": "datasets/reports/exposure_v2.json", "section": "exposure_basis"}],
            notes=[f"checkpoint {'REPRODUCED' if match else 'NOT REPRODUCED'}",
                   f"logs shorter than arm_time_s: {len(short)}",
                   "not a false-alarm rate: the corpus is UNANNOTATED"])
    print(f"rate {rate:.3f}/h, Garwood 95 [{lo:.3f}, {hi:.3f}] on {t_mon} h: "
          f"{'REPRODUCED' if match else 'NOT REPRODUCED'}")
    return 0 if match else 1


if __name__ == "__main__":
    C.main_guard(main)
