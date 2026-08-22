"""WP-A2 E3 — the detection floor, as a figure to replace "100% detection".

The submission's Part 3 prose states 100% detection. Its own Table 2 reports a
magnitude sweep in which the 0.1 deg decoy is never detected (0/20) and the
0.2 deg decoy is detected half the time. Both statements are true — the
campaign's nominal magnitudes (ir_decoy 6.0 deg, rf_jam 4.0 deg azimuth) sit
far above the floor — but the prose omits the floor, and a measured floor is
the stronger claim.

Reads the committed campaign artifact; runs nothing and re-seeds nothing.

Run:  PYTHONPATH=. python research/wp_a2/e3_detection_floor.py
Out:  reports/wp_a2/e3_detection_floor.json
      reports/wp_a2/e3_detection_floor.png
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SRC = os.path.join(ROOT, "deliverables", "montecarlo_results.json")
OUT = os.path.join(ROOT, "reports", "wp_a2", "e3_detection_floor.json")
PNG = os.path.join(ROOT, "reports", "wp_a2", "e3_detection_floor.png")

# csia/seeker/scenarios.py SEEKER_SCENARIOS — the campaign's nominal magnitudes
NOMINAL = {"ir_decoy": 6.0, "rf_jam_az": 4.0}
# tools/interceptor_montecarlo.py:124 — "combined bearing noise floor (~0.36 deg)"
STATED_NOISE_FLOOR_DEG = 0.36


def main() -> int:
    with open(SRC) as fh:
        mc = json.load(fh)

    rows = []
    for key, v in mc["magnitude_sweep"].items():
        rows.append({
            "offset_deg": float(key.replace("deg", "")),
            "runs": v["runs"],
            "detections": v["detections"],
            "detection_rate": v["detection_rate"],
            "mean_latency_s": v["mean_latency_s"],
        })
    rows.sort(key=lambda r: r["offset_deg"])

    below = [r for r in rows if r["detection_rate"] < 1.0]
    floor = max((r["offset_deg"] for r in below), default=None)
    first_full = min((r["offset_deg"] for r in rows
                      if r["detection_rate"] == 1.0), default=None)

    report = {
        "source": "deliverables/montecarlo_results.json (committed; not re-run)",
        "runs_per_point": rows[0]["runs"] if rows else None,
        "sweep": rows,
        "highest_offset_with_incomplete_detection_deg": floor,
        "lowest_offset_with_full_detection_deg": first_full,
        "stated_combined_bearing_noise_floor_deg": STATED_NOISE_FLOOR_DEG,
        "campaign_nominal_magnitudes_deg": NOMINAL,
        "campaign_magnitudes_are_subset_of_sweep": False,
        "probe_finding": (
            "The 150-run campaign's nominal magnitudes (ir_decoy 6.0 deg, "
            "rf_jam 4.0 deg az) are NOT members of the swept set "
            "{0.1, 0.2, 0.35, 0.6, 1.5, 4.0}; the ir_decoy nominal exceeds the "
            "largest swept point. Both nominal magnitudes sit far above the "
            "~0.36 deg noise floor, so '100% detection' is TRUE for the "
            "campaign and is not contradicted by the sweep. The defect is "
            "omission: the prose does not carry the floor its own table "
            "reports. Status TRUE_BUT_AMBIGUOUS, not FALSE."),
        "recommended_claim": (
            f"100% detection (100/100 runs) at the campaign magnitudes, with a "
            f"measured detection floor: detection falls to "
            f"{[r['detection_rate'] for r in rows if r['offset_deg'] == 0.2][0]:.2f} "
            f"at 0.2 deg and 0.00 at 0.1 deg, consistent with a combined "
            f"bearing-noise floor near {STATED_NOISE_FLOOR_DEG} deg. "
            f"Synthetic sensor models; not validated against seeker hardware."),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    _plot(rows)

    print(f"{'offset(deg)':>12s} {'det rate':>9s} {'mean lat(s)':>12s}")
    for r in rows:
        lat = "—" if r["mean_latency_s"] is None else f"{r['mean_latency_s']:.3f}"
        print(f"{r['offset_deg']:>12.2f} {r['detection_rate']:>9.2f} {lat:>12s}")
    print(f"\nfloor: full detection first reached at {first_full} deg; "
          f"highest incomplete point {floor} deg")
    return 0


def _plot(rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib unavailable; skipping figure")
        return

    x = [r["offset_deg"] for r in rows]
    rate = [r["detection_rate"] for r in rows]
    lat = [r["mean_latency_s"] for r in rows]

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(x, rate, "o-", color="#1f77b4", label="detection rate")
    ax.axvline(STATED_NOISE_FLOOR_DEG, ls="--", color="#888", lw=1)
    ax.annotate(f"combined bearing\nnoise floor ≈{STATED_NOISE_FLOOR_DEG}°",
                xy=(STATED_NOISE_FLOOR_DEG, 0.5), xytext=(0.5, 0.35),
                fontsize=8, color="#555")
    ax.set_xscale("log")
    ax.set_xlabel("IR decoy bearing offset (deg, log scale)")
    ax.set_ylabel("detection rate (20 runs/point)")
    ax.set_ylim(-0.05, 1.08)
    ax.grid(alpha=0.25)

    ax2 = ax.twinx()
    xs = [a for a, b in zip(x, lat) if b is not None]
    ys = [b for b in lat if b is not None]
    ax2.plot(xs, ys, "s--", color="#d62728", label="mean latency")
    ax2.set_ylabel("mean detection latency (s)", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")

    lines = ax.get_lines()[:1] + ax2.get_lines()[:1]
    ax.legend(lines, [ln.get_label() for ln in lines], loc="center right",
              fontsize=8)
    ax.set_title("Seeker IR-decoy detection floor (SYNTHETIC sensor models;\n"
                 "not validated against seeker hardware)", fontsize=9)
    fig.tight_layout()
    fig.savefig(PNG, dpi=150)
    print(f"wrote {PNG}")


if __name__ == "__main__":
    raise SystemExit(main())
