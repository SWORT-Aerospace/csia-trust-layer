"""WP-E1 — the figure that keeps the two coarsening mechanisms apart.

Gate-induced coarsening (endogenous: a gate closes as a function of vehicle
state) and channel-absence coarsening (exogenous: the channel is not in the
log at all) both raise kappa. They are different mechanisms and must not be
conflated. Plotting them on one axis shows the contrast quantitatively:
gate closure alone tops out at kappa = 0.286, while the channel counts the
real corpus actually carries reach kappa = 1.000.

Run:  PYTHONPATH=. python research/wp_e1/kappa_comparison_figure.py
Out:  reports/wp_e1/kappa_mechanisms.png
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
GATE = os.path.join(ROOT, "reports", "wp_e1",
                    "structural_consequence_map.json")
CHAN = os.path.join(ROOT, "reports", "wp_a2", "e2_channel_coverage.json")
OUT = os.path.join(ROOT, "reports", "wp_e1", "kappa_mechanisms.png")


def main():
    gate = json.load(open(GATE))
    chan = json.load(open(CHAN))

    g_rows = sorted(gate["configurations"], key=lambda r: r["kappa"])
    g_labels = ["+".join(r["gates_closed"]) or "all open"
                for r in g_rows]
    g_kappa = [r["kappa"] for r in g_rows]

    c_rows = sorted(chan["configurations"], key=lambda r: r["kappa"])
    c_labels = [f"{r['n_channels']}ch ×{r['n_logs']}" for r in c_rows]
    c_kappa = [r["kappa"] for r in c_rows]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12.5, 4.6),
        gridspec_kw={"width_ratios": [len(g_rows), max(len(c_rows), 4)]})

    ax1.barh(range(len(g_kappa)), g_kappa, color="#2980b9")
    ax1.set_yticks(range(len(g_labels)))
    ax1.set_yticklabels(g_labels, fontsize=7)
    ax1.set_xlim(0, 1.05)
    ax1.set_xlabel("κ")
    ax1.axvline(max(g_kappa), ls="--", lw=1, color="#c0392b")
    ax1.set_title("ENDOGENOUS — gate closure\n"
                  f"all 16 configurations; max κ = {max(g_kappa):.3f}\n"
                  "(structural bound; NOT yet measured in flight)",
                  fontsize=9)
    ax1.grid(axis="x", alpha=0.25)

    ax2.barh(range(len(c_kappa)), c_kappa,
             color=["#c0392b" if k >= 0.99 else "#e67e22" for k in c_kappa])
    ax2.set_yticks(range(len(c_labels)))
    ax2.set_yticklabels(c_labels, fontsize=8)
    ax2.set_xlim(0, 1.05)
    ax2.set_xlabel("κ")
    ax2.axvline(max(g_kappa), ls="--", lw=1, color="#c0392b")
    ax2.set_title("EXOGENOUS — channel absent from the log\n"
                  f"measured on 26 real PX4 logs; max κ = {max(c_kappa):.3f}\n"
                  "(corpus property, not gate conditioning)", fontsize=9)
    ax2.grid(axis="x", alpha=0.25)
    ax2.text(max(g_kappa) + 0.02, 0.2, "gate-closure ceiling",
             fontsize=7, color="#c0392b", rotation=90, va="bottom")

    fig.suptitle("Two mechanisms coarsen the diagnostic partition. "
                 "Only the left one is endogenous.", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
