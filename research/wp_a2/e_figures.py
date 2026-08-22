"""WP-A2 — figures for the report: channel coverage (E2) and gate ablation (E1).

Reads the committed JSON produced by e1/e2; computes nothing new.

Run:  PYTHONPATH=. python research/wp_a2/e_figures.py
Out:  reports/wp_a2/e2_channel_coverage.png
      reports/wp_a2/e1_inert_gates.png
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt              # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RPT = os.path.join(ROOT, "reports", "wp_a2")


def channel_coverage():
    r = json.load(open(os.path.join(RPT, "e2_channel_coverage.json")))
    rows = sorted(r["configurations"], key=lambda c: (c["n_channels"],
                                                      -c["n_logs"]))
    labels = [f"{c['n_channels']}ch ×{c['n_logs']}" for c in rows]
    kappa = [c["kappa"] for c in rows]
    absorbed = [len(c["nominal_absorbs"]) for c in rows]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.0))

    bars = ax.bar(labels, kappa, color=["#c0392b" if k >= 0.99 else "#e67e22"
                                        if k >= 0.7 else "#f1c40f"
                                        for k in kappa])
    ax.set_ylabel("coarsening index κ")
    ax.set_ylim(0, 1.08)
    ax.axhline(1.0, ls="--", lw=1, color="#666")
    ax.set_title("Diagnostic coarsening by observed channel configuration\n"
                 "κ = (H−P)/(H−1);  1.0 = all 8 hypotheses collapse to one",
                 fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    for b, k in zip(bars, kappa):
        ax.text(b.get_x() + b.get_width() / 2, k + 0.02, f"{k:.2f}",
                ha="center", fontsize=8)

    ax2.bar(labels, absorbed, color="#8e44ad")
    ax2.set_ylabel("fault hypotheses absorbed into `nominal`")
    ax2.set_ylim(0, 7.6)
    ax2.set_title(f"Faults structurally indistinguishable from healthy\n"
                  f"{r['fraction_of_corpus_nominal_absorbed']:.0%} of the "
                  f"corpus has at least one", fontsize=9)
    ax2.tick_params(axis="x", labelsize=8)
    for i, a in enumerate(absorbed):
        ax2.text(i, a + 0.12, str(a), ha="center", fontsize=8)

    fig.tight_layout()
    out = os.path.join(RPT, "e2_channel_coverage.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


def gate_ablation():
    r = json.load(open(os.path.join(RPT, "e1_inert_gates.json")))
    edges = r["constant_gate_edges"]
    scenarios = list(r["scenarios"])

    fig, ax = plt.subplots(figsize=(8.6, 4.0))
    width = 0.15
    for i, edge in enumerate(edges):
        vals = []
        for s in scenarios:
            d = r["scenarios"][s]["per_edge_removed"][edge]["d_min_trust"]
            vals.append(abs(d) if d is not None else 0.0)
        ax.bar([x + i * width for x in range(len(scenarios))], vals,
               width, label=edge)

    ax.set_xticks([x + 2 * width for x in range(len(scenarios))])
    ax.set_xticklabels(scenarios, fontsize=8)
    ax.set_ylabel("|Δ min-trust| when the edge is removed")
    ax.set_title("Constant-gate edges: a constant gate is not a dead edge.\n"
                 "Only temp_bias_drift is inert (0.0 everywhere); "
                 "redundant_imu removal also destroys imu0 detection entirely",
                 fontsize=9)
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    out = os.path.join(RPT, "e1_inert_gates.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)


if __name__ == "__main__":
    channel_coverage()
    gate_ablation()
