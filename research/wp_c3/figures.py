"""WP-C3 figures: Pi(S) vs Pi(S_eff), SOI ranking, Birnbaum ranking.

Run:  PYTHONPATH=. python research/wp_c3/figures.py
Out:  figures/wp_c3_effective_signature.png
      figures/wp_c3_birnbaum_ranking.png
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt        # noqa: E402
import numpy as np                     # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RES = os.path.join(os.path.dirname(__file__), "results")
FIG = os.path.join(ROOT, "figures")


def effective_and_soi():
    d = json.load(open(os.path.join(RES, "effective_signature.json")))
    r = d["results"]["unknown_as_open"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.4),
                                   gridspec_kw={"width_ratios": [1, 1.5]})

    bars = ax1.bar(["κ(S)\ndesign-time", "κ(S_eff)\neffective"],
                   [r["kappa_S"], r["kappa_S_eff"]],
                   color=["#95a5a6", "#c0392b"])
    ax1.set_ylim(0, 0.22)
    ax1.set_ylabel("κ  (coarsening index)")
    for b, v in zip(bars, [r["kappa_S"], r["kappa_S_eff"]]):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.006, f"{v:.4f}",
                 ha="center", fontsize=10, fontweight="bold")
    ax1.annotate("", xy=(1, r["kappa_S_eff"]), xytext=(1, r["kappa_S"]),
                 arrowprops=dict(arrowstyle="<->", color="#c0392b", lw=1.4))
    ax1.text(1.08, r["kappa_S_eff"] / 2,
             f"gap = {r['gap']:.4f}\n= 1 of 7 distinctions\noverstated by "
             f"design-time\nanalysis", fontsize=8, color="#c0392b", va="center")
    ax1.set_title("Design-time analysis says fully isolable.\n"
                  "It is not.", fontsize=9.5)
    ax1.grid(axis="y", alpha=0.25)

    soi = r["soi"]
    hyps = sorted((v["soi"], h) for h, v in soi.items()
                  if v["soi"] is not None)
    vals = [v for v, _ in hyps]
    names = [h for _, h in hyps]
    ax2.barh(names, vals,
             color=["#c0392b" if v > 0.5 else "#95a5a6" for v in vals])
    ax2.axvline(0.5, ls="--", color="#666", lw=1)
    ax2.text(0.51, 0.2, "self-shielding threshold", fontsize=7.5,
             color="#666", rotation=90)
    ax2.set_xlim(0, 1.1)
    ax2.set_xlabel("SOI — fraction of a fault's own evidence it destroys")
    ax2.tick_params(axis="y", labelsize=8)
    for i, v in enumerate(vals):
        ax2.text(v + 0.02, i, f"{v:.2f}", va="center", fontsize=8)
    ax2.set_title("Self-occlusion index. Exactly one hypothesis is "
                  "completely\nself-shielding, and it is the one with no "
                  "repair.", fontsize=9.5)
    ax2.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    out = os.path.join(FIG, "wp_c3_effective_signature.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


def birnbaum():
    d = json.load(open(os.path.join(RES, "reliability_structure.json")))
    agg = d["aggregate_birnbaum_importance"]
    sole = {"imu0": 4, "imu1": 4, "mag": 2, "vibration": 2, "gps": 1,
            "baro": 0, "battery": 0, "motor_esc": 0}

    names = list(agg)
    vals = [agg[c] for c in names]
    colours = ["#2980b9" if not c.startswith("channel:") else "#16a085"
               for c in names]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.8, 4.6),
                                  gridspec_kw={"width_ratios": [1.35, 1]})
    ax.barh(range(len(names)), vals, color=colours)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("aggregate Birnbaum importance (diagnostic)")
    ax.grid(axis="x", alpha=0.25)
    for i, v in enumerate(vals):
        ax.text(v + 0.003, i, f"{v:.3f}", va="center", fontsize=7.5)
    ax.set_title("Components ranked by diagnostic criticality.\n"
                 "Green = channel, blue = gate. gvalid ranks 10 of 12.",
                 fontsize=9.5)

    ch = [c for c in names if c.startswith("channel:")]
    x = [agg[c] for c in ch]
    y = [sole[c.split(":")[1]] for c in ch]
    ax2.scatter(x, y, s=60, color="#16a085")
    for c, xi, yi in zip(ch, x, y):
        ax2.annotate(c.split(":")[1], (xi, yi), fontsize=8,
                     xytext=(4, 4), textcoords="offset points")
    ax2.set_xlabel("Birnbaum importance (how often it matters)")
    ax2.set_ylabel("WP-C1 sole-protector count\n(how often it is the only one)")
    ax2.grid(alpha=0.25)
    ax2.set_title("The two rankings disagree.\n"
                  "motor_esc and battery matter often, uniquely never —\n"
                  "that is redundancy, not irrelevance.", fontsize=9.5)

    fig.tight_layout()
    out = os.path.join(FIG, "wp_c3_birnbaum_ranking.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    effective_and_soi()
    birnbaum()
