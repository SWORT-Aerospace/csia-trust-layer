"""WP-C2 figures: the CWE two-panel, and the certificate before/after.

Run:  PYTHONPATH=. python research/wp_c2/figures.py
Out:  figures/wp_c2_cwe_mechanisms.png
      figures/wp_c2_certificate_before_after.png
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RES = os.path.join(os.path.dirname(__file__), "results")
E1 = os.path.join(ROOT, "reports", "wp_e1",
                  "structural_consequence_map.json")
C1 = os.path.join(ROOT, "research", "wp_c1", "results", "joint_lattice.json")
FIG = os.path.join(ROOT, "figures")


def cwe_panels():
    c = json.load(open(os.path.join(RES, "criticality.json")))
    gate_k = json.load(open(E1))
    chan_k = json.load(open(C1))

    gate_kappa_max = max(r["kappa"] for r in gate_k["configurations"])
    chan_kappa_max = 1.0

    cwe_gate = c["per_admissibility_assumption"][
        "full_instrumentation"]["gate_closure_alone"]["cwe"]
    cwe_chan = c["per_admissibility_assumption"][
        "corpus_observed"]["channel_absence_alone"]["cwe"]
    ire = c["irreducible_critical_exposure"]["ire"]

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.3))
    labels = ["gate closure\n(endogenous)", "channel absence\n(exogenous)"]
    colours = ["#2980b9", "#c0392b"]

    for ax, vals, title, note in (
        (axes[0], [gate_kappa_max, chan_kappa_max],
         "κ_max — counts distinctions lost",
         "channel absence dominates"),
        (axes[1], [cwe_gate, cwe_chan],
         "CWE — weights by commanded response",
         "NO INVERSION: the gap widens"),
        (axes[2], [ire, 0.0],
         "IRE — survives full instrumentation",
         "THIS is what inverts"),
    ):
        bars = ax.bar(labels, vals, color=colours)
        ax.set_ylim(0, 1.12)
        ax.set_title(title, fontsize=9.5)
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", labelsize=8)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.03, f"{v:.3f}",
                    ha="center", fontsize=9, fontweight="bold")
        ax.text(0.5, 1.04, note, transform=ax.transAxes, ha="center",
                fontsize=8, style="italic", color="#444")

    fig.suptitle("Severity does not invert. Remediability does.\n"
                 "25 of 27 critical exposures vanish once the aircraft "
                 "carries all 8 channels; the 2 that survive are gate-caused.",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    out = os.path.join(FIG, "wp_c2_cwe_mechanisms.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


def before_after():
    r = json.load(open(os.path.join(RES, "repair_experiment.json")))
    d = r["certificate_diff"]
    ks = sorted(int(k) for k in d["kappa_max_by_min_channels_before"])
    kb = [d["kappa_max_by_min_channels_before"][str(k)] for k in ks]
    ka = [d["kappa_max_by_min_channels_after"][str(k)] for k in ks]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.3))

    ax.plot(ks, kb, "o-", color="#95a5a6", label="before repair")
    ax.plot(ks, ka, "s-", color="#27ae60", label="after repair")
    ax.set_xlabel("admissibility: at least k of 8 channels")
    ax.set_ylabel("κ_max")
    ax.set_ylim(-0.05, 1.08)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    ax.set_title("κ_max halves at full instrumentation\n"
                 "0.286 → 0.143; unchanged below k=8 because the repair\n"
                 "needs both imu0 and mag present", fontsize=9)

    per_k = d["diff_by_min_channels"]
    kk = sorted(int(k) for k in per_k)
    cb = [per_k[str(k)]["critical_exposed_before"] for k in kk]
    ca = [per_k[str(k)]["critical_exposed_after"] for k in kk]
    w = 0.38
    x = np.arange(len(kk))
    ax2.bar(x - w / 2, cb, w, color="#95a5a6", label="before")
    ax2.bar(x + w / 2, ca, w, color="#27ae60", label="after")
    ax2.set_xticks(x); ax2.set_xticklabels(kk)
    ax2.set_xlabel("at least k of 8 channels")
    ax2.set_ylabel("critical pairs exposed")
    ax2.legend(fontsize=8)
    ax2.grid(axis="y", alpha=0.25)
    ax2.set_title("Critical exposure, before vs after.\n"
                  "No new collision anywhere in 1232 configurations.",
                  fontsize=9)

    fig.tight_layout()
    out = os.path.join(FIG, "wp_c2_certificate_before_after.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    cwe_panels()
    before_after()
