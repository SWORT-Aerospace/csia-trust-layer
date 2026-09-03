"""MECHANISM B (brief B4): history changes threshold-crossing behaviour.

    Reproduce: clean, slow ramp, fast ramp, appropriate existing fault
    scenarios. Report: instantaneous residual, smoothed history, threshold,
    crossing time, CUSUM crossing time.
    Do not claim CUSUM novelty.

NO CUSUM NOVELTY IS CLAIMED. The detector is Page's one-sided CUSUM, already
labelled as known prior art inside `csia/v1_1/sequential.py` itself. The
established cumulative-innovations / sequential-monitoring literature this
sits in is listed in `research/systems-paper/MECHANISM_B.md` §5.

NOTHING FROZEN IS TOUCHED. `csia/scenarios.py` and `csia/diagnosis/` are
frozen paths. The ramp arms are built by calling the frozen `run_pipeline`
with `Fault` objects constructed here, which is the same interface the frozen
catalogue uses. No core file is imported for anything but reading.

THE THREE QUANTITIES, AND WHY THE FIRST ONE HAD TO BE RECOVERED
---------------------------------------------------------------
`td.physics["gps"]` is ALREADY smoothed: the comparator computes
`lam = ew_smooth(chi2, alpha=0.15)`. There is no unsmoothed lambda anywhere in
the pipeline's output, so "instantaneous vs smoothed" cannot be read off
directly. `ew_smooth` is a first-order IIR,

    y_t = (1 - a) y_{t-1} + a x_t      =>      x_t = (y_t - (1 - a) y_{t-1}) / a

so the instantaneous chi-square is recovered exactly by inverting it. The
inversion is checked by re-smoothing and asserting agreement to 1e-9; if it
ever fails, the run aborts rather than reporting a reconstructed series as a
measurement.

    python research/systems-paper/mechanism_b.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.prediction.predictors import ew_smooth              # noqa: E402
from csia.runtime.failsafe import FailsafeConfig              # noqa: E402
from csia.scenarios import Fault, run_pipeline                # noqa: E402
from csia.sensors.truth import generate_flight                # noqa: E402
from csia.trust_engine.engine import consistency              # noqa: E402
from csia.v1_1.sequential import (CUSUM_H, CUSUM_K,           # noqa: E402
                                  GATE_EPS, IN_CONTROL, CusumBank)

#: The comparator's own outer smoothing constant, read from its source rather
#: than restated: `lam()` in csia/prediction/comparator.py.
LAM_ALPHA = 0.15
NODE = "gps"
ONSET_S = 20.0
DURATION_S = 15.0

#: Drift rates in m/s along +x. The catalogue's own `gps_spoof` is 3.0; the
#: slow and fast arms bracket it. These are the only new numbers in this file
#: and they are scenario parameters, not thresholds.
ARMS = {
    "clean":      None,
    "slow_ramp":  1.0,
    "spoof_3ms":  3.0,        # the catalogue's existing fault scenario
    "fast_ramp":  6.0,
}

OUT = os.path.join(_HERE, "results", "mechanism_b.json")


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _instantaneous(lam_smoothed: np.ndarray, alpha: float) -> np.ndarray:
    """Invert the comparator's outer EW smoother. Exact, not approximate."""
    y = np.asarray(lam_smoothed, dtype=float)
    x = np.empty_like(y)
    # ew_smooth seeds acc = x[0] then immediately applies the recursion, so
    # y[0] = (1-a)x[0] + a x[0] = x[0].
    x[0] = y[0]
    x[1:] = (y[1:] - (1.0 - alpha) * y[:-1]) / alpha
    return x


def _first_crossing(t, series, threshold, above=True, after=None):
    """First time `series` crosses `threshold`, or None."""
    s = np.asarray(series, dtype=float)
    mask = (s > threshold) if above else (s < threshold)
    if after is not None:
        mask = mask & (np.asarray(t) >= after)
    idx = np.nonzero(mask)[0]
    return (float(t[idx[0]]), int(idx[0])) if len(idx) else (None, None)


def run_arm(name: str, drift) -> dict:
    faults = ([] if drift is None else
              [Fault("gps_spoof", "gps", ONSET_S, DURATION_S,
                     {"drift": (float(drift), 1.0, 0.0)})])
    truth = generate_flight(profile="hover_circle")
    td, hist, _diag = run_pipeline(truth=truth, faults=faults)

    t = np.asarray(td.t, dtype=float)
    lam_smoothed, gate = td.physics[NODE]
    lam_smoothed = np.asarray(lam_smoothed, dtype=float)
    gate = np.asarray(gate, dtype=float) * np.ones(len(t))

    lam_inst = _instantaneous(lam_smoothed, LAM_ALPHA)
    # The inversion is only usable if re-smoothing reproduces the original.
    recon = ew_smooth(lam_inst, LAM_ALPHA)
    err = float(np.max(np.abs(recon - lam_smoothed)))
    if err > 1e-9:
        raise RuntimeError(
            f"{name}: EW inversion did not round-trip (max err {err:g}). "
            f"Refusing to report a reconstructed series as a measurement.")

    # -- thresholds, all inherited, none invented -----------------------
    cfg = FailsafeConfig()
    trust_threshold = float(cfg.nav_caution)          # 0.75, gps
    trust = np.asarray(hist.trust[:, hist.col(NODE)], dtype=float)

    # A lambda threshold stated in the SAME units as both series, derived from
    # the frozen in-control statistics rather than chosen: mu0 + 3*sigma0.
    mu0, sigma0 = IN_CONTROL[NODE]
    lam_threshold = mu0 + 3.0 * sigma0

    t_trust, k_trust = _first_crossing(t, trust, trust_threshold, above=False,
                                       after=ONSET_S)
    t_inst, k_inst = _first_crossing(t, lam_inst, lam_threshold, above=True,
                                     after=ONSET_S)
    t_smooth, k_smooth = _first_crossing(t, lam_smoothed, lam_threshold,
                                         above=True, after=ONSET_S)

    # -- CUSUM, frozen constants, frozen implementation -----------------
    bank = CusumBank()
    S, alarm_t, alarm_k = [], None, None
    for k in range(len(t)):
        active = gate[k] > GATE_EPS
        fired = bank.update(NODE, float(lam_smoothed[k]), bool(active))
        S.append(bank.S[NODE])
        if fired and alarm_t is None and t[k] >= ONSET_S:
            alarm_t, alarm_k = float(t[k]), k
    S = np.asarray(S)

    def _lat(x):
        return None if x is None else round(x - ONSET_S, 4)

    return {
        "arm": name,
        "drift_m_per_s": drift,
        "ground_truth_faulted": drift is not None,
        # On an unfaulted arm every crossing is a FALSE ALARM. The latency
        # fields are still emitted, because suppressing them would hide that
        # the bare lambda threshold fires in clean flight, but they must not
        # be read as detection latencies.
        "crossings_are_false_alarms": drift is None,
        "onset_s": ONSET_S, "duration_s": DURATION_S,
        "ticks": len(t),
        "ew_inversion_max_error": err,
        "thresholds": {
            "trust_nav_caution": trust_threshold,
            "trust_threshold_source":
                "csia/runtime/failsafe.py FailsafeConfig.nav_caution",
            "lambda_mu0_plus_3sigma0": round(lam_threshold, 6),
            "lambda_threshold_source":
                "csia/v1_1/sequential.py IN_CONTROL['gps'], mu0 + 3*sigma0",
            "cusum_k": CUSUM_K, "cusum_h": CUSUM_H,
        },
        "series_summary": {
            "lambda_instantaneous_max_after_onset":
                round(float(lam_inst[t >= ONSET_S].max()), 6),
            "lambda_smoothed_max_after_onset":
                round(float(lam_smoothed[t >= ONSET_S].max()), 6),
            "lambda_instantaneous_mean_clean_window":
                round(float(lam_inst[(t > 5.0) & (t < ONSET_S)].mean()), 6),
            "lambda_smoothed_mean_clean_window":
                round(float(lam_smoothed[(t > 5.0) & (t < ONSET_S)].mean()), 6),
            "consistency_min_after_onset":
                round(float(consistency(lam_smoothed)[t >= ONSET_S].min()), 6),
            "trust_min_after_onset": round(float(trust[t >= ONSET_S].min()), 6),
            "cusum_max_after_onset": round(float(S[t >= ONSET_S].max()), 4),
        },
        # The bare lambda threshold is reported WITH its false-alarm count,
        # because reporting its crossing latency alone would flatter it: on
        # the clean arm it crosses too, and a detector that fires in clean
        # flight has no usable latency.
        "false_alarms_in_clean_window": {
            "window": [5.0, ONSET_S],
            "ticks_in_window": int(((t > 5.0) & (t < ONSET_S)).sum()),
            "instantaneous_lambda_over_threshold": int(
                ((lam_inst > lam_threshold) & (t > 5.0)
                 & (t < ONSET_S)).sum()),
            "smoothed_lambda_over_threshold": int(
                ((lam_smoothed > lam_threshold) & (t > 5.0)
                 & (t < ONSET_S)).sum()),
            "trust_below_threshold": int(
                ((trust < trust_threshold) & (t > 5.0) & (t < ONSET_S)).sum()),
            "cusum_alarming": int(((S > CUSUM_H) & (t > 5.0)
                                   & (t < ONSET_S)).sum()),
        },
        "crossing": {
            "instantaneous_lambda_t_s": t_inst,
            "instantaneous_lambda_latency_s": _lat(t_inst),
            "instantaneous_lambda_tick": k_inst,
            "smoothed_lambda_t_s": t_smooth,
            "smoothed_lambda_latency_s": _lat(t_smooth),
            "smoothed_lambda_tick": k_smooth,
            "trust_t_s": t_trust,
            "trust_latency_s": _lat(t_trust),
            "trust_tick": k_trust,
            "cusum_t_s": alarm_t,
            "cusum_latency_s": _lat(alarm_t),
            "cusum_tick": alarm_k,
        },
    }


def main() -> int:
    doc = {
        "artifact": "MECHANISM_B",
        "purpose": "history/persistence materially changes threshold-crossing "
                   "behaviour; the exact effect depends on threshold and "
                   "scenario",
        "novelty": "NONE CLAIMED. The sequential detector is Page's one-sided "
                   "CUSUM (1954), labelled as prior art in "
                   "csia/v1_1/sequential.py. See MECHANISM_B.md section 5 for "
                   "the cumulative-innovations literature it sits in.",
        "generation_command": "python research/systems-paper/mechanism_b.py",
        "commit": _git("rev-parse", "HEAD"),
        "node": NODE, "lam_alpha": LAM_ALPHA,
        "frozen_inputs": {
            "scenarios": "csia/scenarios.py (FROZEN) run_pipeline",
            "comparator": "csia/prediction/comparator.py",
            "cusum": "csia/v1_1/sequential.py CusumBank, k=%s h=%s"
                     % (CUSUM_K, CUSUM_H),
        },
        "arms": {},
    }
    for name, drift in ARMS.items():
        row = run_arm(name, drift)
        doc["arms"][name] = row
        c = row["crossing"]
        print(f"  {name:<12} drift={str(drift):>4}  "
              f"inst={str(c['instantaneous_lambda_latency_s']):>7}  "
              f"smooth={str(c['smoothed_lambda_latency_s']):>7}  "
              f"trust={str(c['trust_latency_s']):>7}  "
              f"cusum={str(c['cusum_latency_s']):>7}   (s after onset)")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n{OUT}\n  sha256 {_sha(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
