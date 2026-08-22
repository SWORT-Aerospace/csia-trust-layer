"""WP-C1 figures: certificate curve, guaranteed-vs-exposed pairs, channel value.

Reads the committed results JSON; computes nothing new.

Run:  PYTHONPATH=. python research/wp_c1/figures.py
Out:  figures/wp_c1_certificate_curve.png
      figures/wp_c1_pair_matrix.png
      figures/wp_c1_channel_value.png
"""

import itertools
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                    # noqa: E402
import numpy as np                                 # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.certificate import d_critical  # noqa: E402
from research.wp_c1.design_inverse import guaranteed_given  # noqa: E402
from research.wp_c1.lattice import CHANNELS, load_signatures  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RES = os.path.join(os.path.dirname(__file__), "results")
FIG = os.path.join(ROOT, "figures")


def certificate_curve():
    c = json.load(open(os.path.join(RES, "certificate.json")))
    lat = json.load(open(os.path.join(RES, "joint_lattice.json")))
    rows = c["certificate_curve_min_channels"]
    k = [r["min_channels"] for r in rows]
    guar = [r["n_guaranteed_pairs"] for r in rows]
    kmax = [lat["kappa_max_by_min_channels"][str(x)]["kappa_max"] for x in k]
    n_crit = c["d_critical"]["n_critical_pairs"]

    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.plot(k, guar, "o-", color="#2980b9", label="|Δ_guaranteed|")
    ax.axhline(n_crit, ls="--", color="#c0392b", lw=1.2)
    ax.text(1.1, n_crit + 0.5, f"|D_critical| = {n_crit} — never reached",
            color="#c0392b", fontsize=8)
    ax.set_xlabel("admissibility: at least k of 8 channels present")
    ax.set_ylabel("hypothesis pairs guaranteed distinguishable")
    ax.set_ylim(-1, 29)
    ax.grid(alpha=0.25)

    ax2 = ax.twinx()
    ax2.plot(k, kmax, "s--", color="#e67e22", label="κ_max")
    ax2.set_ylabel("κ_max over the admissible set", color="#e67e22")
    ax2.tick_params(axis="y", labelcolor="#e67e22")

    lines = ax.get_lines()[:1] + ax2.get_lines()[:1]
    ax.legend(lines, [ln.get_label() for ln in lines], loc="upper left",
              fontsize=8)
    ax.set_title("The certificate never covers the decision-relevant set.\n"
                 "Even with all 8 channels, 2 critical pairs stay exposed.",
                 fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c1_certificate_curve.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


def pair_matrix():
    low = load_signatures()
    hyps = sorted(low)
    crit, _ = d_critical(hyps)
    exposed = guaranteed_given(low, frozenset(CHANNELS))

    n = len(hyps)
    m = np.full((n, n), np.nan)
    for i, j in itertools.combinations(range(n), 2):
        pair = (hyps[i], hyps[j])
        if pair in exposed:
            v = 2.0 if pair in crit else 1.0      # exposed critical / benign
        else:
            v = 0.0 if pair in crit else 0.5      # guaranteed
        m[i, j] = m[j, i] = v

    fig, ax = plt.subplots(figsize=(7.4, 6.2))
    cmap = matplotlib.colors.ListedColormap(
        ["#27ae60", "#95a5a6", "#f39c12", "#c0392b"])
    ax.imshow(m, cmap=cmap, vmin=0, vmax=2)
    ax.set_xticks(range(n)); ax.set_xticklabels(hyps, rotation=45,
                                                ha="right", fontsize=8)
    ax.set_yticks(range(n)); ax.set_yticklabels(hyps, fontsize=8)
    for i, j in itertools.combinations(range(n), 2):
        if m[i, j] == 2.0:
            for (a, b) in ((i, j), (j, i)):
                ax.text(b, a, "×", ha="center", va="center",
                        color="white", fontsize=13, fontweight="bold")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in
               ("#27ae60", "#95a5a6", "#c0392b")]
    ax.legend(handles,
              ["guaranteed & decision-relevant",
               "response-equivalent (need not distinguish)",
               "EXPOSED & decision-relevant"],
              fontsize=7, loc="upper left", bbox_to_anchor=(0, -0.22))
    ax.set_title("Δ_guaranteed at full channel availability, over all "
                 "gate configurations", fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c1_pair_matrix.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print("wrote", out)


def channel_value():
    d = json.load(open(os.path.join(RES, "design_inverse.json")))
    mv = d["marginal_channel_value"]
    chans = sorted(mv, key=lambda c: -mv[c]["n_critical_lost"])
    vals = [mv[c]["n_critical_lost"] for c in chans]

    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    ax.bar(chans, vals, color=["#c0392b" if v > 0 else "#95a5a6"
                               for v in vals])
    ax.set_ylabel("critical pairs lost if this\nchannel is removed")
    ax.set_title("Marginal channel value. Zero does not mean useless — it "
                 "means covered by redundancy,\nso the channel is not a "
                 "single point of assurance failure.", fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.08, str(v), ha="center", fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c1_channel_value.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    certificate_curve()
    pair_matrix()
    channel_value()
