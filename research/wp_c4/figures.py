"""WP-C4 figures: chatter resonance, sparsity probe, self-occlusion timeline.

Run:  PYTHONPATH=. python research/wp_c4/figures.py
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt      # noqa: E402
import numpy as np                   # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RES = os.path.join(os.path.dirname(__file__), "results")
FIG = os.path.join(ROOT, "figures")


def chatter():
    d = json.load(open(os.path.join(RES, "adversarial_search.json")))
    c = d["chatter_resonance"]
    x = [r["closure_duration_frames"] for r in c["sweep"]]
    y = [r["flips"] for r in c["sweep"]]

    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    ax.plot(x, y, "o-", color="#2980b9", ms=4)
    ax.axvline(c["predicted_resonance_frames"], ls="--", color="#c0392b")
    ax.annotate(f"predicted 1/α_s = {c['predicted_resonance_frames']}",
                xy=(c["predicted_resonance_frames"], max(y) * 0.55),
                xytext=(c["predicted_resonance_frames"] + 4, max(y) * 0.75),
                fontsize=8, color="#c0392b",
                arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1))
    ax.axvline(c["observed_peak_frames"], ls=":", color="#27ae60")
    ax.annotate(f"observed peak {c['observed_peak_frames']}",
                xy=(c["observed_peak_frames"], max(y)),
                xytext=(c["observed_peak_frames"] + 14, max(y) * 0.95),
                fontsize=8, color="#27ae60",
                arrowprops=dict(arrowstyle="->", color="#27ae60", lw=1))
    ax.set_xlabel("gate closure duration (frames)")
    ax.set_ylabel(f"top-label flips per {c['n_frames_per_sweep_point']} frames")
    ax.grid(alpha=0.25)
    ax.set_title("Label chatter resonates near the smoothing time constant.\n"
                 "Evidence held fixed; only availability toggles, so every "
                 "flip is caused by gating alone.", fontsize=9.5)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c4_chatter_resonance.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


def sparsity():
    d = json.load(open(os.path.join(RES, "sparsity_probe.json")))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.4))
    for arm, colour, marker in (("uniform", "#95a5a6", "o"),
                                ("physically_forced", "#c0392b", "s")):
        rows = d["arms"][arm]
        x = [r["density_features_per_hypothesis"] for r in rows]
        ax.plot(x, [r["mean_gap"] for r in rows], marker + "-",
                color=colour, label=arm)
        ax2.plot(x, [r["frac_gap_positive"] for r in rows], marker + "-",
                 color=colour, label=arm)
    ax.axhline(1 / 7, ls="--", color="#2980b9", lw=1)
    ax.text(4.4, 1 / 7 + 0.004, "real system = 1/7", fontsize=8,
            color="#2980b9")
    ax.set_xlabel("features per hypothesis")
    ax.set_ylabel("mean κ(S_eff) − κ(S)")
    ax.legend(fontsize=8); ax.grid(alpha=0.25)
    ax.set_title("The gap vanishes with density only when the\n"
                 "hypothesis's evidence is NOT bound to the gate.",
                 fontsize=9.5)
    ax2.set_xlabel("features per hypothesis")
    ax2.set_ylabel("P(gap > 0)")
    ax2.set_ylim(-0.03, 1.05)
    ax2.legend(fontsize=8); ax2.grid(alpha=0.25)
    ax2.set_title("Not a sparsity artifact: it is evidence–gate coincidence.",
                  fontsize=9.5)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c4_sparsity_probe.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


def occlusion():
    d = json.load(open(os.path.join(RES, "self_occlusion.json")))["results"]
    arms = list(d)
    labels = ["A spoof\n(fix valid)", "B denial\n(fix invalid)",
              "C spoof→denial"]
    gps_occ = [d[a]["top_cause_occupancy_after_onset"].get("gps_fault", 0.0)
               for a in arms]
    nom_occ = [d[a]["top_cause_occupancy_after_onset"].get("nominal", 0.0)
               for a in arms]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.3))
    x = np.arange(len(arms))
    ax.bar(x, gps_occ, 0.55, label="gps_fault on top", color="#27ae60")
    ax.bar(x, nom_occ, 0.55, bottom=gps_occ, label="nominal on top",
           color="#c0392b")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("share of post-onset ticks")
    ax.legend(fontsize=8)
    for i, (g, n) in enumerate(zip(gps_occ, nom_occ)):
        if g > 0.02:
            ax.text(i, g / 2, f"{g:.0%}", ha="center", color="white",
                    fontsize=9, fontweight="bold")
        ax.text(i, g + n / 2, f"{n:.0%}", ha="center", color="white",
                fontsize=9, fontweight="bold")
    ax.set_title("SOI(gps_fault) = 1.0, observed.\n"
                 "When the fault destroys the fix, the diagnosis never "
                 "names it.", fontsize=9.5)

    cw = [d[a]["seconds_confident_wrong_nominal_above_actionable_trust"]
          for a in arms]
    tr = [d[a]["gps_trust_min_after_onset"] for a in arms]
    ax2.bar(x, cw, 0.55, color="#8e44ad")
    ax2.set_xticks(x); ax2.set_xticklabels(labels, fontsize=8)
    ax2.set_ylabel("seconds 'nominal' on top with GPS trust ≥ 0.85")
    for i, (v, t) in enumerate(zip(cw, tr)):
        ax2.text(i, v + 0.6, f"{v:.1f} s\nmin trust {t}", ha="center",
                 fontsize=8)
    ax2.set_ylim(0, max(cw) * 1.25)
    ax2.grid(axis="y", alpha=0.25)
    ax2.set_title("Confident-wrong time. Absence of data freezes the belief,\n"
                  "so trust stays high while the fault is active.",
                  fontsize=9.5)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c4_self_occlusion.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    chatter()
    sparsity()
    occlusion()
