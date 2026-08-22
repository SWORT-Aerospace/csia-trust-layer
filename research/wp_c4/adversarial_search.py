"""WP-C4 Part 2.1 — adversarial input search against the unmodified system.

No parameter edits, no code changes. Inputs only.

  1. CHATTER RESONANCE. Theory predicts the label flip rate peaks when gate
     closure duration is near the smoothing time constant 1/alpha_s ~ 16.7
     frames at alpha_s = 0.06. Swept against the real DiagnosisCore. This is a
     direct empirical test of a theoretical prediction and has never been run
     against the code.
  2. TRUST FLOOR AND RECOVERY. Drive trust to its floor with sustained
     inconsistency, release, and measure recovery against the geometric bound
     implied by rho.
  3. MINIMUM UNDETECTED FAULT. Per fault mode, the largest magnitude that
     never crosses the detection line, bisected.

Run:  PYTHONPATH=. python research/wp_c4/adversarial_search.py
Out:  research/wp_c4/results/adversarial_search.json
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from csia.diagnosis.bayes import CAUSES, SMOOTH_ALPHA, DiagnosisCore  # noqa
from csia.scenarios import run_pipeline                          # noqa: E402
from csia.sensors.faults import Fault                            # noqa: E402
from csia.sensors.truth import generate_flight                   # noqa: E402
from csia.trust_engine.engine import EngineConfig, TrustCore     # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
DETECT_LINE = 0.85
SEED = 20260822


def chatter_resonance():
    """Toggle a gate with period 2*d frames and count top-label flips.

    The evidence pattern is held FIXED; only availability toggles, so every
    flip is caused by gating alone.
    """
    # The gated feature must be DECISIVE, or there is nothing to flip. Only
    # phys_gps is anomalous; everything else is healthy. With gvalid open the
    # leader is gps_fault, with it closed the evidence vanishes and nominal
    # leads. A first version made every feature anomalous, which let a
    # multi-feature hypothesis win in both states and produced 0 flips at
    # every duration — a null result caused by the probe, not the system.
    HEALTHY, ANOMALOUS = 0.98, 0.02
    feats_open = {f: (HEALTHY, 1.0) for f in
                  ("redundant_imu", "accel_motor_current", "accel_esc_rpm",
                   "attitude_gravity_mag", "phys_mag", "temp_mag",
                   "phys_battery", "temp_battery", "phys_motor_esc",
                   "phys_vibration", "temp_vibration", "vibration_prop_freq",
                   "temp_gps", "heading_course")}
    feats_open["phys_gps"] = (ANOMALOUS, 1.0)
    rows = []
    n = 2000
    for d in list(range(1, 41)) + [50, 60, 80, 100]:
        core = DiagnosisCore()
        last, flips = None, 0
        for k in range(n):
            closed = (k // d) % 2 == 1
            feats = {f: (c, 0.0 if (closed and f == "phys_gps") else g)
                     for f, (c, g) in feats_open.items()}
            post = core.step(feats)
            top = max(post.items(), key=lambda kv: kv[1])[0]
            if last is not None and top != last:
                flips += 1
            last = top
        rows.append({"closure_duration_frames": d,
                     "flips": flips,
                     "flip_rate_per_1000_frames": round(1000 * flips / n, 3)})
    peak = max(rows, key=lambda r: r["flips"])
    predicted = round(1.0 / SMOOTH_ALPHA, 2)
    return {
        "alpha_s": SMOOTH_ALPHA,
        "predicted_resonance_frames": predicted,
        "observed_peak_frames": peak["closure_duration_frames"],
        "observed_peak_flips": peak["flips"],
        "n_frames_per_sweep_point": n,
        "prediction_confirmed": abs(peak["closure_duration_frames"]
                                    - predicted) <= 5,
        "sweep": rows,
    }


def trust_floor_recovery():
    cfg = EngineConfig()
    names = ["a", "b"]
    core = TrustCore(names, cfg)
    edges = {"e": ("a", "b", 0.0, 1.0)}

    def tick(consistency):
        # NOTE: engine.step takes `phys`, and its edge tuples carry LAMBDA
        # (a chi-square-normalised residual), not a consistency score — the
        # kernel maps lam -> c internally. Passing a consistency here would
        # silently measure the wrong thing.
        lam = 0.0 if consistency >= 1.0 else 40.0
        return core.step(
            edges={"e": ("a", "b", lam, 1.0)},
            phys={"a": (lam, 1.0), "b": (lam, 1.0)},
            hist={}, var_ratio={}, fresh={"a": True, "b": True})

    # core.step returns {node: {trust, evidence, rho, nbr, phys, temp, stat}}
    floor_traj = [float(tick(0.0)["a"]["trust"]) for _ in range(600)]
    floor = min(floor_traj)
    rec, above = [], None
    for i in range(4000):
        v = float(tick(1.0)["a"]["trust"])
        rec.append(v)
        if above is None and v >= 0.85:
            above = i + 1
    # geometric bound: alpha,beta decay by rho each tick with unit input
    return {
        "floor_reached": round(float(floor), 6),
        "ticks_to_floor": int(np.argmin(floor_traj)) + 1,
        "recovery_ticks_to_0.85": above,
        "trust_after_600_clean_ticks": round(float(rec[599]), 6),
        "final_trust_after_4000_clean_ticks": round(float(rec[-1]), 6),
        "geometric_bound_ticks_to_0.85":
            round(float(np.log(0.15) / np.log(cfg.rho_max)), 1),
        "rho_max": cfg.rho_max,
        "implied_concentration_cap_alpha_plus_beta": round(
            1.0 / (1.0 - cfg.rho_max), 1),
        "note": "recovery is geometric with ratio rho_max. The 0.538 fused-"
                "evidence floor pinned by test_formalization_lock does NOT "
                "apply here: it holds when ONE sub-score collapses and another "
                "survives, whereas this probe collapses every available "
                "sub-score, so fused evidence goes to ~0 and trust follows.",
    }


def min_undetected(kind, target, params_fn, lo, hi, tol=1e-3):
    """Largest magnitude whose target trust never crosses the detection line."""
    truth = generate_flight(profile="hover_circle")

    def detected(mag):
        # Detection must be measured AFTER onset and AFTER prior convergence.
        # A first version scanned the whole run and reported every magnitude
        # as "detected" because it was seeing the warm-up dip, not the fault.
        f = [Fault(kind, target, 20.0, 20.0, params_fn(mag))]
        td, hist, _ = run_pipeline(truth=truth, faults=f)
        t = np.asarray(td.t)
        win = (t >= 20.0) & (t <= 40.0)
        return bool((hist.trust[win, hist.col(target)] < DETECT_LINE).any())

    if detected(lo):
        return {"largest_undetected": None,
                "note": f"even the smallest probed magnitude {lo} is detected"}
    if not detected(hi):
        return {"largest_undetected": f">= {hi}",
                "note": "even the largest probed magnitude is NOT detected"}
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if detected(mid):
            hi = mid
        else:
            lo = mid
    return {"largest_undetected": round(lo, 5),
            "smallest_detected": round(hi, 5)}


def main() -> int:
    np.random.seed(SEED)
    report = {
        "purpose": "worst inputs found against the unmodified system",
        "seed": SEED,
        "detection_line": DETECT_LINE,
        "chatter_resonance": chatter_resonance(),
        "trust_floor_recovery": trust_floor_recovery(),
        "minimum_undetected_fault": {
            "imu0_bias_drift_m_s2_per_s": min_undetected(
                "bias_drift", "imu0", lambda m: {"rate": m},
                0.0005, 0.5),
            "mag_emi_uT": min_undetected(
                "emi_spike", "mag", lambda m: {"amplitude": m}, 0.05, 60.0),
        },
    }
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "adversarial_search.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    c = report["chatter_resonance"]
    print(f"CHATTER: predicted resonance {c['predicted_resonance_frames']} "
          f"frames; observed peak {c['observed_peak_frames']} frames "
          f"({c['observed_peak_flips']} flips) -> "
          f"confirmed={c['prediction_confirmed']}")
    print("  sweep (frames: flips):", ", ".join(
        f"{r['closure_duration_frames']}:{r['flips']}"
        for r in c["sweep"][:20]))
    t = report["trust_floor_recovery"]
    print(f"\nFLOOR: {t['floor_reached']} after {t['ticks_to_floor']} ticks; "
          f"recovery to 0.85 in {t['recovery_ticks_to_0.85']} ticks")
    print(f"\nMIN UNDETECTED: "
          f"{json.dumps(report['minimum_undetected_fault'], indent=1)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
