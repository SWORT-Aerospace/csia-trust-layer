"""WP-C8 figures: the two-detector coverage map, the duration-magnitude
escalation boundary, and the four quantities by arm.

Run:  PYTHONPATH=. python research/wp_c8/figures.py
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt      # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
import numpy as np                   # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RES = os.path.join(os.path.dirname(__file__), "results")
FIG = os.path.join(ROOT, "figures")

COVER_COLOR = {"both": "#27ae60", "ekf_only": "#2980b9",
               "layer_only": "#f39c12", "neither": "#c0392b"}
COVER_LABEL = {"both": "both detect", "ekf_only": "estimator only",
               "layer_only": "diagnostic layer only", "neither": "NEITHER"}


def _load(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    return None if d.get("status") == "SITL_UNAVAILABLE" else d


def coverage_map():
    d = _load("response_surface.json")
    if not d:
        return None
    rows = [r for r in d["per_run"]["grid"] if "error" not in r]
    amps = sorted({r["amplitude_m"] for r in rows})
    slews = sorted({r["slew_s"] for r in rows})

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.6))
    for ax, key, title in (
            (axes[0], "coverage", "By DETECTION"),
            (axes[1], "coverage_by_escalation", "By ESCALATION")):
        for r in rows:
            xi = slews.index(r["slew_s"])
            yi = amps.index(r["amplitude_m"])
            ax.add_patch(plt.Rectangle((xi - 0.5, yi - 0.5), 1, 1,
                                       facecolor=COVER_COLOR[r[key]],
                                       edgecolor="white", lw=1.5))
        ax.set_xlim(-0.5, len(slews) - 0.5)
        ax.set_ylim(-0.5, len(amps) - 0.5)
        ax.set_xticks(range(len(slews)))
        ax.set_xticklabels(["step" if s == 0 else f"{s} s ramp"
                            for s in slews])
        ax.set_yticks(range(len(amps)))
        ax.set_yticklabels([f"{a:g}" for a in amps])
        ax.set_xlabel("slew (time to reach full amplitude)")
        ax.set_ylabel("injected position error (m)")
        ax.set_title(title, fontsize=10)
    axes[0].legend(handles=[Patch(facecolor=COVER_COLOR[k], label=COVER_LABEL[k])
                            for k in ("both", "ekf_only", "layer_only",
                                      "neither")],
                   fontsize=7.5, loc="lower left", framealpha=0.9)
    fig.suptitle("Two-detector coverage. The red region is covered by neither, "
                 "and it widens as the error slows.", fontsize=11)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c8_coverage_map.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def escalation_boundary():
    d = _load("response_surface.json")
    if not d:
        return None
    eb = d["escalation_boundary"]
    rows = eb["grid_classification"]
    bound = eb["boundary_ticks"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))
    esc = [r for r in rows if r["measured_escalates"]]
    non = [r for r in rows if not r["measured_escalates"]]
    ax1.scatter([r["phys_floor_ticks"] for r in non],
                [r["min_trust"] for r in non], s=55, marker="o",
                facecolor="none", edgecolor="#c0392b", label="no escalation")
    ax1.scatter([r["phys_floor_ticks"] for r in esc],
                [r["min_trust"] for r in esc], s=60, marker="^",
                color="#27ae60", label="escalated")
    ax1.axvline(bound, ls="--", color="#2c3e50", lw=1.4)
    ax1.annotate(f"N* + dwell = {bound:.0f} ticks",
                 xy=(bound, 0.96), xytext=(bound + 14, 0.96), fontsize=8)
    ax1.axhline(0.75, ls=":", color="#7f8c8d", lw=1.2)
    ax1.annotate("nav_caution 0.75", xy=(5, 0.755), fontsize=7.5,
                 color="#7f8c8d")
    ax1.set_xlabel("ticks with the physics residual saturated")
    ax1.set_ylabel("minimum GPS trust")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.25)
    ax1.set_title("The escalation boundary is a DURATION, not a magnitude",
                  fontsize=10)

    rs = [r for r in d["per_run"]["grid"] if "error" not in r]
    amps = [r["amplitude_m"] for r in rs]
    floors = [r["layer"]["phys_floor_ticks"] for r in rs]
    marks = {0: "o", 4: "s", 20: "^"}
    for slew in sorted({r["slew_s"] for r in rs}):
        sel = [(a, f) for a, f, r in zip(amps, floors, rs)
               if r["slew_s"] == slew]
        ax2.semilogx([a for a, _ in sel], [f for _, f in sel],
                     marker=marks.get(slew, "o"), ms=6,
                     label="step" if slew == 0 else f"{slew} s ramp")
    ax2.axhline(bound, ls="--", color="#2c3e50", lw=1.4)
    ax2.set_xlabel("injected position error (m, log scale)")
    ax2.set_ylabel("ticks at the floor")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25, which="both")
    ax2.set_title("Magnitude buys logarithmic time; slew buys linear time",
                  fontsize=10)

    fig.suptitle("Escalation requires the residual to stay saturated past "
                 "N* + dwell", fontsize=11)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c8_escalation_boundary.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def four_quantities():
    d = _load("four_quantity_metrics.json")
    if not d:
        return None
    per = d["per_arm"]
    arms = [a for a in ("nominal", "glitch", "link_loss", "denial",
                        "denial_recovered") if a in per]
    x = np.arange(len(arms))
    w = 0.2

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.5),
                                   gridspec_kw={"width_ratios": [1.2, 1]})
    na = [per[a]["T_NA_s"] or 0.0 for a in arms]
    uh = [per[a]["channels"]["attribution"]["T_UH_s"] or 0.0 for a in arms]
    fh = [per[a]["channels"]["attribution"]["T_FH_s"] or 0.0 for a in arms]
    so = [per[a]["channels"]["attribution"]["T_SOFH_s"] or 0.0 for a in arms]
    for off, vals, lbl, col in (
            (-1.5 * w, na, "$T_{NA}$ inapplicable", "#7f8c8d"),
            (-0.5 * w, uh, "$T_{UH}$ unsupported healthy", "#f39c12"),
            (0.5 * w, fh, "$T_{FH}$ false healthy", "#c0392b"),
            (1.5 * w, so, "$T_{SOFH}$ self-occluded", "#8e44ad")):
        ax1.bar(x + off, vals, w, label=lbl, color=col)
    ax1.set_xticks(x)
    ax1.set_xticklabels(arms, fontsize=8)
    ax1.set_ylabel("seconds in a 25 s window")
    ax1.legend(fontsize=7.5)
    ax1.grid(alpha=0.25, axis="y")
    ax1.set_title("Four quantities, attribution channel", fontsize=10)
    gi = arms.index("glitch") if "glitch" in arms else None
    if gi is not None:
        ax1.annotate("$T_{SOFH}=0$:\n$A_h=1$ throughout",
                     xy=(gi + 1.5 * w, 0.4), xytext=(gi - 0.35, 9.0),
                     fontsize=7.5, color="#8e44ad",
                     arrowprops=dict(arrowstyle="->", color="#8e44ad", lw=1))

    for off, chan, lbl, col in (
            (-w, "attribution", "attribution", "#c0392b"),
            (0.0, "status", "reported status", "#e67e22"),
            (w, "abstaining", "abstaining (research)", "#27ae60")):
        ax2.bar(x + off, [per[a]["channels"][chan]["T_FH_s"] or 0.0
                          for a in arms], w, label=lbl, color=col)
    ax2.set_xticks(x)
    ax2.set_xticklabels(arms, fontsize=8)
    ax2.set_ylabel("$T_{FH}$ (s)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25, axis="y")
    ax2.set_title("$T_{FH}$ by channel", fontsize=10)

    fig.suptitle("Exposure decomposed: an unsupported verdict is not the same "
                 "as a false one", fontsize=11)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c8_four_quantities.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def main() -> int:
    os.makedirs(FIG, exist_ok=True)
    for fn in (coverage_map, escalation_boundary, four_quantities):
        out = fn()
        print("wrote " + os.path.relpath(out, ROOT) if out
              else f"{fn.__name__}: skipped (no results yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
