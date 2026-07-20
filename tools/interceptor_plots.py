"""Plots for the interceptor_seeker white paper (SYNTHETIC data).

Clean matplotlib defaults, all axes labeled. Every plotted value comes from
an actual run. Reads the magnitude sweep from deliverables/montecarlo_results.json.

Run:  .venv/bin/python tools/interceptor_plots.py
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from csia.seeker import run_seeker
from csia.seeker.runtime import DETECT_TRUST
from csia.seeker.scenarios import scenario_faults

OUT = os.path.join(os.path.dirname(__file__), "..", "deliverables")
ONSET = 8.0
COLORS = {"ir_seeker": "tab:red", "rf_seeker": "tab:blue", "ins": "tab:green"}


def _trust_plot(scenario, path, title):
    eng, r = run_seeker(scenario_faults(scenario), tick_hz=100.0, seed=0)
    t = r.t
    fig, ax = plt.subplots(figsize=(9, 5))
    for n in ("ir_seeker", "rf_seeker", "ins"):
        ax.plot(t, r.trust[n], color=COLORS[n], lw=1.5, label=n)
    ax.axvline(ONSET, color="k", ls="--", lw=1, label="fault onset")
    ax.axhline(DETECT_TRUST, color="gray", ls=":", lw=1,
               label=f"actionable threshold ({DETECT_TRUST})")
    # escalation transitions along the top
    for tr in r.transitions:
        if tr["to"] != "NORMAL":
            ax.axvline(tr["t"], color="orange", ls="-", lw=0.6, alpha=0.6)
            ax.text(tr["t"], 1.02, tr["to"][:4], rotation=90, fontsize=7,
                    color="darkorange", va="bottom")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("Trust Coefficient")
    ax.set_ylim(0, 1.08)
    ax.set_title(title + "  [SYNTHETIC]")
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"wrote {path}")


def _latency_plot(path):
    rep = json.load(open(os.path.join(OUT, "montecarlo_results.json")))
    sweep = rep["magnitude_sweep"]
    mags = [float(k.replace("deg", "")) for k in sweep]
    rate = [sweep[k]["detection_rate"] for k in sweep]
    lat = [sweep[k]["mean_latency_s"] for k in sweep]
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.set_xlabel("IR decoy bearing offset (deg)")
    ax1.set_ylabel("mean detection latency (s)", color="tab:blue")
    lm = [(m, l) for m, l in zip(mags, lat) if l is not None]
    if lm:
        ax1.plot([m for m, _ in lm], [l for _, l in lm], "o-",
                 color="tab:blue", label="mean latency")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax2 = ax1.twinx()
    ax2.set_ylabel("detection rate", color="tab:red")
    ax2.plot(mags, rate, "s--", color="tab:red", label="detection rate")
    ax2.set_ylim(-0.05, 1.05)
    ax2.tick_params(axis="y", labelcolor="tab:red")
    ax1.axvline(0.36, color="gray", ls=":", lw=1)
    ax1.text(0.36, ax1.get_ylim()[1] * 0.9, " bearing noise floor ~0.36 deg",
             fontsize=8, color="gray")
    ax1.set_title("ir_decoy: detection latency & rate vs decoy magnitude  "
                  "[SYNTHETIC, 20 runs/pt]")
    ax1.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"wrote {path}")


def main():
    os.makedirs(OUT, exist_ok=True)
    _trust_plot("ir_decoy", os.path.join(OUT, "plot_trust_vs_time_ir_decoy.png"),
                "interceptor_seeker — IR decoy engagement (100 Hz)")
    _latency_plot(os.path.join(OUT, "plot_latency_vs_magnitude.png"))
    _trust_plot("rf_jam", os.path.join(OUT, "plot_trust_vs_time_rf_jam.png"),
                "interceptor_seeker — RF jam engagement (100 Hz)")


if __name__ == "__main__":
    main()
