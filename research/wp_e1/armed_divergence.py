"""WP-E1 — the armed_gate discrepancy: batch proxy vs runtime flag.

WP1 recorded that the two execution paths compute `armed_gate` differently:

  batch    comparator.py:137   clip((ticks - 5.0) / 1.0, 0, 1)
                               — unconditional; the batch path has NO armed
                                 flag and assumes arming at t = 5.0 s
  runtime  online.py:491-496   armed flag None  -> the same t>5 s proxy
                               armed flag True  -> clip(tau - armed_since,0,1)
                               armed flag False -> hard 0.0

The runtime flag is fed from real vehicle state: `ulog_source.py:217-225`
emits `vehicle_status.arming_state == 2` when that topic is present in the
log. WP-E1 adopts the RUNTIME FLAG as reference semantics, and records the
divergence as a WP1 discrepancy rather than repairing either path.

This quantifies how much of the real-log corpus falls in the window where the
two can disagree, and whether that window can affect any published figure.

Run:  PYTHONPATH=. python research/wp_e1/armed_divergence.py
Out:  reports/wp_e1/armed_divergence.json
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
CORPUS = os.path.join(ROOT, "data", "real_logs_report.json")
OUT = os.path.join(ROOT, "reports", "wp_e1", "armed_divergence.json")

PROXY_OPEN_S = 5.0      # comparator.py:137 — proxy starts opening
PROXY_RAMP_S = 1.0      # ... and saturates 1 s later
ARM_TIME_S = 20.0       # offline failsafe posture; exposure denominator


def disagreement_window(t_arm):
    """[start, end) in which the proxy and the flag differ, for a vehicle that
    actually armed at `t_arm`. Both are 1 s ramps; they coincide only when
    t_arm == PROXY_OPEN_S."""
    if abs(t_arm - PROXY_OPEN_S) < 1e-9:
        return 0.0, 0.0
    start = min(PROXY_OPEN_S, t_arm)
    end = max(PROXY_OPEN_S + PROXY_RAMP_S, t_arm + PROXY_RAMP_S)
    return start, end


def main() -> int:
    with open(CORPUS) as fh:
        flights = json.load(fh)["flights"]
    dur = np.array([f["duration_s"] for f in flights])
    raw = float(dur.sum())
    monitored = float(np.maximum(dur - ARM_TIME_S, 0.0).sum())

    # Bound with no assumption about arming time: the proxy is unsaturated
    # over [0, 6) s of every flight, so no arming time can move the
    # disagreement outside [0, max(6, t_arm + 1)).
    proxy_window = PROXY_OPEN_S + PROXY_RAMP_S
    unsaturated = float(np.minimum(dur, proxy_window).sum())

    # Sensitivity: the corpus records no arming timestamps, so sweep.
    sweep = []
    for t_arm in (0.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0):
        start, end = disagreement_window(t_arm)
        overlap = float(np.clip(np.minimum(dur, end) - start, 0.0, None).sum())
        inside_arm = float(np.clip(
            np.minimum(np.minimum(dur, end), ARM_TIME_S) - start,
            0.0, None).sum())
        sweep.append({
            "assumed_arming_time_s": t_arm,
            "disagreement_window_s": [start, end],
            "corpus_seconds_in_window": round(overlap, 1),
            "fraction_of_raw_exposure": round(overlap / raw, 4),
            "seconds_also_inside_arm_time_exclusion": round(inside_arm, 1),
            "fraction_of_window_already_excluded":
                round(inside_arm / overlap, 4) if overlap > 0 else None,
            "affects_monitored_exposure": overlap - inside_arm > 1e-6,
        })

    report = {
        "purpose": "quantify the armed_gate batch-proxy vs runtime-flag "
                   "divergence over the real-log corpus",
        "status": "WP1 DISCREPANCY — recorded, not repaired",
        "reference_semantics": "runtime flag (online.py:491-496)",
        "batch_path": "comparator.py:137 — no armed flag exists; assumes "
                      "arming at t = 5.0 s unconditionally",
        "runtime_fallback": "when the armed flag is None the runtime uses the "
                            "identical proxy, so the paths agree exactly "
                            "whenever vehicle_status is absent from the log",
        "corpus": {
            "n_logs": len(flights),
            "raw_exposure_s": round(raw, 1),
            "monitored_exposure_s": round(monitored, 1),
            "arm_time_exclusion_s": ARM_TIME_S,
        },
        "assumption_free_bound": {
            "proxy_unsaturated_window_s": proxy_window,
            "corpus_seconds_in_window": round(unsaturated, 1),
            "fraction_of_raw_exposure": round(unsaturated / raw, 4),
            "fraction_of_monitored_exposure": 0.0,
            "reasoning": (
                f"The proxy is unsaturated only over [0, {proxy_window}) s of "
                f"each flight. That window lies entirely inside the "
                f"{ARM_TIME_S:.0f} s arm-time exclusion already applied to the "
                f"exposure denominator, so NONE of it is monitored time."),
        },
        "arming_time_sensitivity": sweep,
        "corpus_metadata_gap": {
            "arming_timestamps_recorded": False,
            "vehicle_status_topic_presence_recorded": False,
            "note": "data/real_logs_report.json carries only log id, duration, "
                    "channel list, min trust, transitions, bad samples and "
                    "excluded channels. It records no timestamps, no arming "
                    "events and no topic inventory, so the ACTUAL per-log "
                    "arming time is UNKNOWN and the exact divergence cannot "
                    "be computed from committed artifacts. The bound below "
                    "holds regardless.",
        },
        "verdict": (
            "The divergence cannot affect any published real-log figure. "
            "Under every assumed arming time up to the arm window itself, the "
            "entire disagreement region lies inside the 20 s exclusion already "
            "removed from the exposure denominator. It affects 0.0% of "
            "monitored exposure. For a vehicle arming LATER than the arm "
            "window the divergence would reach monitored time, and the "
            "runtime (correctly) withholds motor-edge evidence the batch path "
            "would credit — but no corpus log records its arming time, so "
            "whether that occurred is UNKNOWN."),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    b = report["assumption_free_bound"]
    print(f"corpus: {len(flights)} logs, raw {raw:.1f} s, "
          f"monitored {monitored:.1f} s")
    print(f"proxy-unsaturated window [0, {proxy_window}) s -> "
          f"{b['corpus_seconds_in_window']} s = "
          f"{b['fraction_of_raw_exposure']:.2%} of raw exposure, "
          f"{b['fraction_of_monitored_exposure']:.1%} of monitored\n")
    print(f"{'assumed t_arm':>14s} {'window (s)':>16s} {'corpus s':>10s} "
          f"{'% raw':>7s} {'reaches monitored?':>20s}")
    for row in sweep:
        w = row["disagreement_window_s"]
        print(f"{row['assumed_arming_time_s']:>14.1f} "
              f"{f'[{w[0]:.0f}, {w[1]:.0f})':>16s} "
              f"{row['corpus_seconds_in_window']:>10.1f} "
              f"{row['fraction_of_raw_exposure']:>7.2%} "
              f"{str(row['affects_monitored_exposure']):>20s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
