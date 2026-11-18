#!/usr/bin/env python3
"""Deliverable 6, figure and table: CSIA's trust detector against a flat
per-sensor threshold monitor on identical injections, from the LOCKED Phase 5
results. Nothing is re-run; the locked file is verified against its sealed
SHA-256 first.

    python publication/evidence_v2/fig_d6_flat_monitor.py

Mapping. The brief calls the comparison "B3 flat-monitor". In this repository
`B3` is "fast + current CSIA", a hybrid. The flat per-sensor threshold monitor
is `B2`, "bare threshold: instantaneous lambda > tau, no persistence"; CSIA is
`B0`, "trust below theta for DWELL_TICKS consecutive active ticks"
(research/phase5/PREREGISTRATION_PHASE5.md sections 3 and 4).

Definitions are the preregistration's section 11: a false alarm is any alarm in
[SETTLE_S, 60] s on a nominal run; a detection is the first alarm at or after
onset on a faulted run; delay is t_alarm - onset over detections only. Rates
carry exact Clopper-Pearson intervals; delay quantiles use linear interpolation
with a seeded bootstrap (B = 2000, seed 20260921), all as locked.

Scope, as preregistered: one node (`vibration`), conditions EA/EG,
ABRUPT/GRADUAL shapes, three gains, two onsets, 40 seeds. The locked faulted
denominator (1280) also contains the 320 IMU-isolation-arm runs of amendment
section 18, whose fault is on imu0 and which neither vibration-node detector
can see; the per-family split is not in the locked file, so detection rate is
reported pooled, as locked.

Attribution accuracy is not compared: B2 has no attribution by preregistration
(section 3, "B1 and B2 have no attribution"), and B0 is a detector, not a
diagnosis.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

LOCKED = os.path.join(C.ROOT, "research", "phase5", "results", "PHASE5_RESULTS_LOCKED.json")
MANIFEST = os.path.join(C.ROOT, "research", "phase5", "SHA256_MANIFEST5.json")
PREREG = os.path.join(C.ROOT, "research", "phase5", "PREREGISTRATION_PHASE5.md")
FIG = os.path.join(C.FIGURES, "d6_flat_monitor.png")
TAB = os.path.join(C.TABLES, "d6_flat_monitor_locked.csv")
DETECTORS = (("B0", "B0 CSIA trust persistence"), ("B2", "B2 flat threshold (bare)"))


def main() -> int:
    pinned = json.load(open(MANIFEST, encoding="utf-8"))
    want = next(v for k, v in pinned["files"].items() if k.endswith("PHASE5_RESULTS_LOCKED.json"))
    if C.sha256_file(LOCKED) != want:
        print("REFUSED: PHASE5_RESULTS_LOCKED.json does not match its sealed SHA-256")
        return 1
    d = json.load(open(LOCKED, encoding="utf-8"))
    grid = d["full_grid_locked"]
    ops = d["operating_points"]

    rows, series = [], {}
    for det, _ in DETECTORS:
        pts = [v for v in grid.values() if v["detector"] == det]      # declaration order kept
        series[det] = pts
        for v in pts:
            sel = [k.split("|")[0] for k, o in ops.items() if o["detector"] == det and o["threshold"] == v["threshold"]]
            rows.append((det, v["threshold"], v["faulted_runs"], v["detections"],
                         round(v["detections"] / v["faulted_runs"], 4), v["miss_rate_ci95"][0], v["miss_rate_ci95"][1],
                         v["nominal_runs"], v["false_alarm_runs"], v["observed_far"], v["ci95"][0], v["ci95"][1],
                         v["median_delay_s"], (v["median_delay_ci95"] or ["", ""])[0], (v["median_delay_ci95"] or ["", ""])[1],
                         v["p90_delay_s"], v["pre_onset_alarms_on_faulted_runs"],
                         ";".join(f"selected_on_development_for_target_far_{t}" for t in sel)))

    plt = C.style()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.0, 3.8))
    for (det, label), color in zip(DETECTORS, C.SERIES):
        pts = series[det]
        far = [p["observed_far"] for p in pts]
        ring = det == "B0"
        a1.plot(far, [p["detections"] / p["faulted_runs"] for p in pts], marker="o",
                markersize=11 if ring else 5, markerfacecolor="none" if ring else color,
                markeredgewidth=1.6 if ring else 0.0, color=color, label=label, linestyle="none")
        a2.plot(far, [p["median_delay_s"] for p in pts], marker="o", markersize=5, color=color,
                label=label, linestyle="none")
        for p in pts:
            lo, hi = p["median_delay_ci95"] or (None, None)
            if lo is not None:
                a2.plot([p["observed_far"]] * 2, [lo, hi], color=color, linewidth=1.0)
    a1.set_xlabel("false-alarm runs / nominal runs (locked, 80 nominal)")
    a1.set_ylabel("detections / faulted runs (pooled, 1280)")
    a1.set_ylim(0.70, 1.0)
    a1.axhline(0.75, color=C.TEXT_2, linewidth=0.8, linestyle=(0, (2, 2)))
    a1.text(0.98, 0.746, "960/1280 = every vibration-family run;\nthe 320 IMU-arm runs are invisible to both",
            ha="right", va="top", fontsize=7, color=C.TEXT_2, transform=a1.get_yaxis_transform())
    a1.annotate("B0: all 9 thresholds here", (0.0, 0.75), xytext=(0.08, 0.80), fontsize=7.5,
                color=C.TEXT_2, arrowprops={"arrowstyle": "-", "color": C.TEXT_2, "lw": 0.6})
    a2.set_yscale("log")
    a2.set_xlabel("false-alarm runs / nominal runs (locked, 80 nominal)")
    a2.set_ylabel("median delay, s (log; bars: bootstrap 95)")
    b0 = next(p for p in series["B0"] if p["threshold"] == "0.9")
    b2 = next(p for p in series["B2"] if p["observed_far"] == 0.0)
    a2.annotate(f"B0 theta 0.9: {b0['median_delay_s']} s", (0.0, b0["median_delay_s"]), xytext=(0.12, 3.5),
                fontsize=7.5, color=C.TEXT_2, arrowprops={"arrowstyle": "-", "color": C.TEXT_2, "lw": 0.6})
    a2.annotate(f"B2 tau {float(b2['threshold']):.4f}: {b2['median_delay_s']} s", (0.0, b2["median_delay_s"]),
                xytext=(0.12, 0.25), fontsize=7.5, color=C.TEXT_2,
                arrowprops={"arrowstyle": "-", "color": C.TEXT_2, "lw": 0.6})
    a1.legend(frameon=False, loc="upper left", fontsize=7.5)
    fig.suptitle("Phase 5 locked partition (40 seeds, vibration node, identical injections): every preregistered "
                 "threshold", fontsize=10, color=C.TEXT, y=1.03)
    C.savefig(fig, FIG)
    C.write_csv(TAB, ("detector", "threshold", "faulted_runs", "detections", "detection_rate_pooled",
                      "miss_rate_ci95_lo", "miss_rate_ci95_hi", "nominal_runs", "false_alarm_runs",
                      "observed_far", "far_ci95_lo", "far_ci95_hi", "median_delay_s", "median_delay_ci95_lo",
                      "median_delay_ci95_hi", "p90_delay_s", "pre_onset_alarms_on_faulted_runs",
                      "development_selection"), rows)
    common = dict(inputs=(LOCKED, MANIFEST), configs=((PREREG, "preregistration: detectors, grids, definitions"),),
                  datasets={"dataset_id": "Phase 5 locked partition (synthetic, deterministic simulation)",
                            "seeds_locked": 40, "runs_seen": d["intake"]["locked"]["runs_seen"],
                            "sealed_sha256": want},
                  seeds={"bootstrap_seed": d["bootstrap"]["seed"], "bootstrap_resamples": d["bootstrap"]["resamples"],
                         "scenario_seeds": "40 locked seeds, research/phase5 campaign5.py"},
                  definitions=[{"metric": "false alarm, detection, delay, observed FAR",
                                "source": "research/phase5/PREREGISTRATION_PHASE5.md", "section": "11"},
                               {"metric": "B0 and B2 alarms", "source": "research/phase5/PREREGISTRATION_PHASE5.md",
                                "section": "3, 4"}],
                  notes=["brief's 'B3 flat monitor' is this repository's B2; B3 is a hybrid",
                         "attribution accuracy not compared: B2 has none by preregistration",
                         "single node (vibration); not the six UAV fault modes"])
    C.stamp(FIG, __file__, **common)
    C.stamp(TAB, __file__, **common)
    print(f"B0 theta 0.9: {b0['median_delay_s']} s, FA {b0['false_alarm_runs']}/{b0['nominal_runs']}; "
          f"B2 tau {b2['threshold']}: {b2['median_delay_s']} s, FA {b2['false_alarm_runs']}/{b2['nominal_runs']}")
    return 0


if __name__ == "__main__":
    C.main_guard(main)
