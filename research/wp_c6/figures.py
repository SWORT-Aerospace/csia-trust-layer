"""WP-C6 figures: the gap surface over rho, the field-set universe, and the
SITL q_gvalid campaign.

Run:  PYTHONPATH=. python research/wp_c6/figures.py
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


def gap_surface():
    """The interior between full and zero containment. The point of the figure
    is that there is no interior: the transition is a step at rho = 1."""
    d = json.load(open(os.path.join(RES, "partial_containment_sweep.json")))
    grid = d["grid"]
    densities = sorted({r["density"] for r in grid})

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.2))
    cmap = plt.get_cmap("viridis")
    for i, dn in enumerate(densities):
        rows = sorted((r for r in grid if r["density"] == dn),
                      key=lambda r: r["rho_fraction_inside_C"])
        x = [r["rho_fraction_inside_C"] for r in rows]
        col = cmap(i / max(1, len(densities) - 1))
        ax1.plot(x, [r["mean_gap"] for r in rows], "o-", ms=3.5,
                 color=col, label=f"density {dn}")
        ax2.plot(x, [r["frac_star_absorbed_into_nominal"] for r in rows],
                 "o-", ms=3.5, color=col)

    for ax, ttl, yl in ((ax1, "Mean gap $\\kappa(S_{eff})-\\kappa(S)$", "gap"),
                        (ax2, "P(hypothesis absorbed into nominal)",
                         "probability")):
        ax.set_xlabel(r"$\rho$ = fraction of the hypothesis's features "
                      r"inside $C_h$")
        ax.set_ylabel(yl)
        ax.set_title(ttl, fontsize=10)
        ax.grid(alpha=0.25)
        ax.axvline(1.0, ls="--", lw=1, color="#c0392b")
    ax1.legend(fontsize=7, ncol=2)
    ax2.annotate("one feature outside $C_h$\nremoves absorption entirely",
                 xy=(0.88, 0.02), xytext=(0.30, 0.45), fontsize=8,
                 color="#c0392b",
                 arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1))
    fig.suptitle("Partial containment is a threshold at "
                 r"$\rho=1$, not a slope", fontsize=11)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c6_gap_surface.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def field_set():
    """Every GPS-spanning relation the ingestion path can currently build,
    split by whether gvalid controls it."""
    d = json.load(open(os.path.join(RES, "field_set_universe.json")))
    rel = d["gps_spanning_relations"]["relations"]
    inside = set(d["inside_C_gps_fault"])
    names = sorted(rel, key=lambda r: (r not in inside, r))
    vals = [1 if n in inside else 0 for n in names]
    inf = d["informativeness_of_the_one_escape"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.0),
                                   gridspec_kw={"width_ratios": [1.35, 1]})
    colors = ["#c0392b" if v else "#27ae60" for v in vals]
    ax1.barh(range(len(names)), [1] * len(names), color=colors, height=0.62)
    ax1.set_yticks(range(len(names)))
    ax1.set_yticklabels([n.replace("_", r"\_") if False else n
                         for n in names], fontsize=8, family="monospace")
    ax1.set_xticks([])
    ax1.invert_yaxis()
    for i, n in enumerate(names):
        ax1.text(0.5, i, "inside $C_{gps\\_fault}$" if vals[i]
                 else "OUTSIDE $C_{gps\\_fault}$", ha="center", va="center",
                 color="white", fontsize=8, weight="bold")
    ax1.set_title(f"GPS-spanning relations over the ingested field set "
                  f"({d['n_inside']} inside, {d['n_outside']} outside)",
                  fontsize=10)

    tr = inf["traces"]
    labels = ["mean", "min", "max"]
    x = np.arange(len(labels))
    w = 0.36
    ax2.bar(x - w / 2, [tr["clean"][k] for k in labels], w, label="clean",
            color="#2980b9")
    ax2.bar(x + w / 2, [tr["denial"][k] for k in labels], w, label="denial",
            color="#e67e22")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.set_ylim(0, 1.15)
    ax2.set_ylabel("consistency over the fault window")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25, axis="y")
    ax2.set_title("temp_gps: the one relation outside $C_h$\n"
                  "is bit-identical clean vs denial", fontsize=10)
    for xi, k in zip(x, labels):
        ax2.text(xi, max(tr["clean"][k], tr["denial"][k]) + 0.04,
                 f"{tr['clean'][k]:.6f}", ha="center", fontsize=7)

    fig.suptitle("Effective containment is complete over the ingested field "
                 "set; formal containment is not", fontsize=11)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c6_field_set_universe.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def campaign():
    """The SITL q_gvalid campaign: per-flight closure rate by arm."""
    path = os.path.join(RES, "q_gvalid_campaign.json")
    d = json.load(open(path))
    if d.get("status") != "MEASURED":
        return None
    cells = d["cell_counts"]
    arms = [a for a in ("nominal", "glitch", "degraded", "denial")
            if a in cells]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.2),
                                   gridspec_kw={"width_ratios": [1, 1.1]})
    for i, arm in enumerate(arms):
        ps = cells[arm]["per_flight_p"]
        ax1.plot([i] * len(ps), ps, "o", ms=7, alpha=0.55, color="#2980b9")
        if ps:
            ax1.plot([i - 0.2, i + 0.2], [np.mean(ps)] * 2, "-",
                     lw=2.4, color="#c0392b")
    ax1.set_xticks(range(len(arms)))
    ax1.set_xticklabels(arms)
    ax1.set_ylim(-0.05, 1.05)
    ax1.set_ylabel("$q_{gvalid}$ per flight")
    ax1.grid(alpha=0.25, axis="y")
    ax1.set_title("Gate closure rate in the conditioning window\n"
                  "(red bar: arm mean; one point per flight)", fontsize=10)

    eff = [r["injection_effect"] for r in d["per_flight"]]
    by = {}
    for r, e in zip(d["per_flight"], eff):
        by.setdefault(r["arm"], []).append(e)
    x = np.arange(len(arms))
    step = [np.mean([e["max_position_step_m_post"] for e in by[a]])
            for a in arms]
    sats = [np.mean([e["mean_satellites_post"] or 0 for e in by[a]])
            for a in arms]
    ax2.bar(x - 0.2, step, 0.38, label="max position step after "
            "injection (m)", color="#8e44ad")
    ax2.bar(x + 0.2, sats, 0.38, label="mean satellites after injection",
            color="#16a085")
    ax2.set_xticks(x)
    ax2.set_xticklabels(arms)
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25, axis="y")
    ax2.set_title("Injection effect controls: every arm's injection\n"
                  "reached the receiver", fontsize=10)

    fig.suptitle("SITL controlled-injection campaign: denial and degradation "
                 "close the gate, a position glitch does not", fontsize=11)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c6_q_gvalid_campaign.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def main() -> int:
    os.makedirs(FIG, exist_ok=True)
    for fn in (gap_surface, field_set, campaign):
        out = fn()
        print("wrote", os.path.relpath(out, ROOT) if out
              else f"{fn.__name__}: skipped (campaign not measured)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
