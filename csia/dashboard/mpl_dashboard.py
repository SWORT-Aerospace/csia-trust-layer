"""Static matplotlib dashboard: trust curves + diagnosis posterior + graph
snapshot at the worst tick. Companion to the interactive web replay."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from ..trust_engine.engine import consistency


def render_static_dashboard(td, hist, diag, graph, faults, path, title):
    fig = plt.figure(figsize=(15, 10))
    gs = fig.add_gridspec(2, 2, height_ratios=(1, 1.15))
    fig.suptitle(title, fontsize=13)

    ax = fig.add_subplot(gs[0, :])
    for n in hist.names:
        ax.plot(hist.t, hist.trust[:, hist.col(n)], lw=1.1, label=n)
    for f in faults:
        ax.axvspan(f.start, f.start + f.duration, alpha=0.08, color="red")
    ax.set_ylabel("Trust Coefficient")
    ax.set_ylim(0.4, 1.02)
    ax.legend(fontsize=7, ncol=8, loc="lower left")

    ax = fig.add_subplot(gs[1, 0])
    ax.stackplot(diag.t, diag.posterior.T, labels=diag.causes, alpha=0.85)
    for f in faults:
        ax.axvspan(f.start, f.start + f.duration, alpha=0.1, color="red")
    ax.set_ylabel("P(cause | signature)")
    ax.set_xlabel("t [s]")
    ax.set_ylim(0, 1)
    ax.legend(fontsize=6.5, ncol=2, loc="center left")

    # graph snapshot at the tick with the lowest single-sensor trust
    k = int(np.argmin(hist.trust.min(axis=1)))
    ax = fig.add_subplot(gs[1, 1])
    pos = nx.spring_layout(graph, seed=7, k=1.6)
    tvals = {n: hist.trust[k, hist.col(n)] for n in hist.names}
    ecols, ewid = [], []
    for key, (a, b, lam_e, gate_e) in td.edges.items():
        c = float(consistency(lam_e[k]))
        g = float((np.asarray(gate_e, dtype=float) * np.ones(len(lam_e)))[k])
        ecols.append(plt.cm.RdYlGn(c) if g > 0.05 else (0.6, 0.6, 0.6, 0.25))
        ewid.append(0.8 + 2.4 * g)
        nx.draw_networkx_edges(graph, pos, edgelist=[(a, b)], ax=ax,
                               edge_color=[ecols[-1]], width=ewid[-1])
    nx.draw_networkx_nodes(
        graph, pos, ax=ax,
        node_color=[plt.cm.RdYlGn(tvals[n]) for n in graph.nodes],
        node_size=1400, edgecolors="black", linewidths=1.0)
    nx.draw_networkx_labels(graph, pos, {n: n for n in graph.nodes},
                            ax=ax, font_size=7)
    ax.set_title(f"trust graph @ t={hist.t[k]:.1f} s — {diag.callout(k)}",
                 fontsize=9)
    ax.axis("off")

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=130)
    plt.close(fig)
