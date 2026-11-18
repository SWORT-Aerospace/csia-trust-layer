#!/usr/bin/env python3
"""Deliverable 3, figure and table: latency ECDFs per UAV fault class, one
panel per class, three named stages per panel.

    python publication/evidence_v2/fig_d3_latency_ecdf.py

Reads data/d3_mc_runs.json (run_d3_mc_latency.py). Stages and their names are
docs/validation/METRIC_DEFINITIONS.md section 3; "detection latency" is a term
that document retires, so no curve carries it:

- time_to_trust_threshold_0_85: ANALYSIS ONLY (section 3.2); no alert follows from it
- time_to_alert_event: first operator-facing alert event (section 3.3)
- time_to_correct_isolation: leading cause names the faulted source at
  confidence 0.90 (section 3.6)

Each ECDF's denominator is every faulted run of that class, so a curve that
stops below 1 shows the runs that never reached the stage. Medians and p95 are
order statistics over the runs that reached it (numpy `method="inverted_cdf"`);
the table also gives p50/p95 the way campaigns/monte_carlo.json computes them
(`sorted[n // 2]`, `sorted[int(0.95 * (n - 1))]`), because the two definitions
differ at these sample sizes.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import numpy as np  # noqa: E402

DATA = os.path.join(C.DATA, "d3_mc_runs.json")
FIG = os.path.join(C.FIGURES, "d3_latency_ecdf.png")
TAB = os.path.join(C.TABLES, "d3_latency_stages.csv")
CLASSES = ("gps_spoof", "mag_emi", "power_sag", "vibration", "imu_bias")
STAGES = (("time_to_trust_threshold_s", "trust < 0.85 (analysis only)"),
          ("time_to_alert_event_s", "alert event (operator-facing)"),
          ("time_to_correct_isolation_s", "correct isolation (conf 0.90)"))
NAME = {"time_to_trust_threshold_s": "time_to_trust_threshold_0_85",
        "time_to_alert_event_s": "time_to_alert_event",
        "time_to_correct_isolation_s": "time_to_correct_isolation"}
DEFS = [{"metric": "time_to_trust_threshold_0_85", "source": "docs/validation/METRIC_DEFINITIONS.md", "section": "3.2"},
        {"metric": "time_to_alert_event", "source": "docs/validation/METRIC_DEFINITIONS.md", "section": "3.3"},
        {"metric": "time_to_correct_isolation", "source": "docs/validation/METRIC_DEFINITIONS.md", "section": "3.6"}]


def q(v, p):
    return float(np.quantile(np.asarray(v), p, method="inverted_cdf"))


def main() -> int:
    d = json.load(open(DATA, encoding="utf-8"))
    runs = d["faulted_runs"]
    rows = []
    plt = C.style()
    from matplotlib.lines import Line2D
    fig, axes = plt.subplots(1, len(CLASSES), figsize=(13.0, 3.9), sharey=True)
    for ax, cls in zip(axes, CLASSES):
        rs = [r for r in runs if r["fault_class"] == cls]
        n = len(rs)
        texts = []
        for (key, label), color in zip(STAGES, C.SERIES):
            v = sorted(r[key] for r in rs if r[key] is not None)
            mc_p50 = v[len(v) // 2] if v else None
            mc_p95 = v[int(0.95 * (len(v) - 1))] if v else None
            rows.append((cls, NAME[key], n, len(v),
                         round(q(v, 0.5), 3) if v else "", round(q(v, 0.95), 3) if v else "",
                         round(v[0], 3) if v else "", round(v[-1], 3) if v else "",
                         round(mc_p50, 2) if v else "", round(mc_p95, 2) if v else ""))
            if v:
                y = np.arange(1, len(v) + 1) / n
                ax.step([0.0] + v, [0.0] + list(y), where="post", color=color, label=label)
                texts.append(f"{len(v)}/{n}: med {q(v, 0.5):.2f}, p95 {q(v, 0.95):.2f} s")
            else:
                texts.append(f"0/{n}: never reached")
        ax.set_title(cls, fontsize=9, color=C.TEXT)
        ax.set_xlim(0, 16)
        ax.set_ylim(0, 1.02)
        ax.set_xlabel("seconds after configured onset")
        for i, (t, color) in enumerate(zip(texts, C.SERIES)):
            y = -0.27 - 0.085 * i
            ax.plot([0.02], [y + 0.03], marker="s", markersize=5, color=color,
                    transform=ax.transAxes, clip_on=False)
            ax.text(0.07, y, t, transform=ax.transAxes, ha="left", va="bottom",
                    fontsize=7.5, color=C.TEXT_2)
    axes[0].set_ylabel("fraction of faulted runs")
    handles = [Line2D([0], [0], color=c, lw=1.6) for c in C.SERIES]
    fig.legend(handles, [lab for _, lab in STAGES], loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 1.08))
    fig.suptitle("UAV fault-harness Monte Carlo (150 runs, seed 0, field_mode): latency by named stage",
                 y=1.15, fontsize=10, color=C.TEXT)
    C.savefig(fig, FIG)
    C.write_csv(TAB, ("fault_class", "stage", "runs", "runs_reaching_stage", "median_s", "p95_s",
                      "min_s", "max_s", "mc_style_p50_s", "mc_style_p95_s"), rows)
    common = dict(inputs=(DATA,), definitions=DEFS,
                  datasets={"dataset_id": "synthetic UAV fault harness, campaigns/monte_carlo.json replay"},
                  seeds={"numpy_default_rng": 0, "sensor_seeds": "1-8 fixed (csia/scenarios.make_sensors)"},
                  notes=["one trajectory and one noise realization for all runs; amplitude, onset and class vary",
                         "median/p95: numpy quantile method inverted_cdf over runs reaching the stage",
                         "GPS dropout has no harness class: see data/d3_mc_runs.json catalogue_gps_dropout_single_run"])
    C.stamp(FIG, __file__, **common)
    C.stamp(TAB, __file__, **common)
    return 0


if __name__ == "__main__":
    C.main_guard(main)
