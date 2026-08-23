"""WP-C7 figures: the satellite ladder, false-healthy exposure by arm, and
the abstaining-policy comparison.

Run:  PYTHONPATH=. python research/wp_c7/figures.py
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

ARM_ORDER = ("nominal", "glitch", "degraded", "denial", "denial_recovered")


def _load(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    return None if d.get("status") == "SITL_UNAVAILABLE" else d


def satellite_ladder():
    d = _load("campaign_expanded.json")
    if not d:
        return None
    rungs = [r for r in d["satellite_ladder"]["rungs"]
             if r["q_gvalid"] is not None]
    if not rungs:
        return None
    x = [r["numsats"] for r in rungs]
    y = [r["q_gvalid"] for r in rungs]
    obs = [r["observed_satellites"] for r in rungs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.2))
    ax1.plot(x, y, "o-", color="#c0392b", ms=6)
    ax1.set_xlabel("SIM_GPS_NUMSATS commanded at injection")
    ax1.set_ylabel("$q_{gvalid}$ over the conditioning window")
    ax1.set_ylim(-0.05, 1.05)
    ax1.invert_xaxis()
    ax1.grid(alpha=0.25)
    flip = d["satellite_ladder"].get("flip")
    if flip:
        lo, hi = flip["boundary_between"]
        ax1.axvspan(lo, hi, color="#f39c12", alpha=0.18)
        ax1.annotate(f"gate flips between\n{lo} and {hi} satellites",
                     xy=((lo + hi) / 2, 0.5), xytext=((lo + hi) / 2, 0.62),
                     ha="center", fontsize=8, color="#b9770e")
    ax1.set_title("Where the gate actually flips", fontsize=10)

    ax2.plot(x, obs, "s-", color="#2980b9", ms=5)
    ax2.plot(x, x, "--", color="#7f8c8d", lw=1, label="commanded")
    ax2.set_xlabel("SIM_GPS_NUMSATS commanded")
    ax2.set_ylabel("satellites reported after injection")
    ax2.invert_xaxis()
    ax2.grid(alpha=0.25)
    ax2.legend(fontsize=8)
    ax2.set_title("Injection-effect control: what the receiver reported",
                  fontsize=10)

    fig.suptitle("Satellite ladder: the boundary between self-occluding and "
                 "detectable GNSS faults", fontsize=11)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c7_satellite_ladder.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def false_healthy():
    d = _load("false_healthy.json")
    if not d:
        return None
    per = d["per_arm"]
    arms = [a for a in ARM_ORDER if a in per]
    attr = [per[a].get("T_FH_attribution_only_s") or 0.0 for a in arms]
    dep = [per[a]["T_FH_deployed_s"] or 0.0 for a in arms]
    abst = [per[a]["T_FH_abstaining_s"] or 0.0 for a in arms]
    x = np.arange(len(arms))
    w = 0.27

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.3),
                                   gridspec_kw={"width_ratios": [1.15, 1]})
    ax1.bar(x - w, attr, w, label="attribution channel (diagnosis alone)",
            color="#c0392b")
    ax1.bar(x, dep, w, label="reported status (with freshness disjunct)",
            color="#e67e22")
    ax1.bar(x + w, abst, w, label="abstaining policy (research only)",
            color="#27ae60")
    ax1.set_xticks(x)
    ax1.set_xticklabels(arms, fontsize=8)
    ax1.set_ylabel("$T_{FH}$ (s) in the 25 s window")
    ax1.legend(fontsize=7.5)
    ax1.grid(alpha=0.25, axis="y")
    ax1.set_title("False-healthy exposure: time asserting health\n"
                  "with no applicable evidence", fontsize=10)
    for off, vals in ((-w, attr), (0.0, dep), (w, abst)):
        for xi, v in zip(x + off, vals):
            ax1.text(xi, v + 0.4, f"{v:.2f}", ha="center", fontsize=6.5)

    onset_d = [per[a]["onset_to_status_change_deployed_s"] for a in arms]
    onset_a = [per[a]["onset_to_status_change_abstaining_s"] for a in arms]
    ok = [i for i, (a, b) in enumerate(zip(onset_d, onset_a))
          if a is not None or b is not None]
    ax2.bar([i - w / 2 for i in ok], [onset_d[i] or 0.0 for i in ok], w,
            label="deployed", color="#c0392b")
    ax2.bar([i + w / 2 for i in ok], [onset_a[i] or 0.0 for i in ok], w,
            label="abstaining", color="#27ae60")
    ax2.set_xticks(x)
    ax2.set_xticklabels(arms, fontsize=8)
    ax2.set_ylabel("seconds from injection")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25, axis="y")
    ax2.set_title("Onset to first non-healthy status", fontsize=10)

    fig.suptitle("The cost of having no NOT_APPLICABLE state, and the cost of "
                 "adding one", fontsize=11)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c7_false_healthy.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def glitch():
    d = _load("glitch_mechanism.json")
    if not d:
        return None
    sweep = d["magnitude_sweep"]
    x = [r["magnitude_m"] for r in sweep]
    trust = [r["min_trust"] for r in sweep]
    phys = [r["min_phys"] for r in sweep]
    floor = [r["floor_ticks"] for r in sweep]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.2))
    ax1.semilogx(x, trust, "o-", color="#c0392b", ms=6,
                 label="min GPS trust")
    ax1.semilogx(x, phys, "s-", color="#2980b9", ms=5,
                 label="min phys component")
    ax1.axhline(d["nav_caution_threshold"], ls="--", color="#7f8c8d", lw=1.2)
    ax1.annotate("nav_caution = 0.75", xy=(x[0], d["nav_caution_threshold"]),
                 xytext=(x[0], d["nav_caution_threshold"] + 0.06), fontsize=8,
                 color="#7f8c8d")
    ax1.set_xlabel("injected position error (m, log scale)")
    ax1.set_ylabel("minimum value after injection")
    ax1.set_ylim(-0.05, 1.08)
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.25, which="both")
    ax1.set_title("The detector floors; the trust coefficient does not move",
                  fontsize=10)

    ax2.semilogx(x, floor, "o-", color="#8e44ad", ms=6)
    ax2.set_xlabel("injected position error (m, log scale)")
    ax2.set_ylabel("ticks with phys component below 0.10")
    ax2.grid(alpha=0.25, which="both")
    ax2.set_title("How long the detector stayed at the floor", fontsize=10)

    fig.suptitle("The glitch non-alarm: detection happened, escalation did "
                 "not", fontsize=11)
    fig.tight_layout()
    out = os.path.join(FIG, "wp_c7_glitch_mechanism.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def main() -> int:
    os.makedirs(FIG, exist_ok=True)
    for fn in (satellite_ladder, false_healthy, glitch):
        out = fn()
        print("wrote " + os.path.relpath(out, ROOT) if out
              else f"{fn.__name__}: skipped (no results yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
