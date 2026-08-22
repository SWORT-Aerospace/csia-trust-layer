"""WP-A2 E1 — measure what the five constant-gate edges actually contribute.

Five of the eleven production edges carry a gate that never varies with
vehicle state:

    redundant_imu, attitude_gravity_mag, power_thrust, vibration_prop_freq
        gate = ones          (always fully open)
    temp_bias_drift
        gate = 0.2 * ones    (permanently half-open, never opens, never closes)

The submitted white paper says "every edge carries a validity gate". That is
literally true and operationally misleading: only six gates actuate. This
script measures whether the five constant-gate edges are load-bearing, by
ablating them from the tick stream and re-running the unchanged trust engine
and diagnosis over the same scenarios.

Ablation is post-hoc on ``TickData``: no production file is modified. The
engine rebuilds its incident map from ``td.edges``, so deleting a key removes
the edge exactly as if it had never been computed.

Run:  PYTHONPATH=. python research/wp_a2/e1_inert_gates.py
Out:  reports/wp_a2/e1_inert_gates.json
"""

import copy
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from csia.diagnosis import CausalDiagnosis                      # noqa: E402
from csia.scenarios import SCENARIOS, run_scenario              # noqa: E402
from csia.trust_engine import TrustEngine                       # noqa: E402
from csia.trust_graph import build_trust_graph                  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "..",
                   "reports", "wp_a2", "e1_inert_gates.json")

CONSTANT_GATE_EDGES = [
    "redundant_imu",          # ones
    "attitude_gravity_mag",   # ones
    "power_thrust",           # ones
    "vibration_prop_freq",    # ones
    "temp_bias_drift",        # 0.2 * ones
]

# scenario -> (faulted node, expected cause, fault onset s)
CASES = {
    "gps_spoof": ("gps", "gps_fault", 20.0),
    "imu0_bias_drift": ("imu0", "imu0_bias_drift", 20.0),
    "mag_emi": ("mag", "mag_interference", 25.0),
    "power_sag": ("battery", "power_fault", 30.0),
    "vibration_anomaly": ("vibration", "vibration_anomaly", 28.0),
}

DETECT_TRUST = 0.85


def _rerun(td):
    """Re-run engine + diagnosis over a (possibly ablated) tick stream."""
    hist = TrustEngine(build_trust_graph()).run(td)
    diag = CausalDiagnosis().run(td)
    return hist, diag


def _metrics(td, hist, diag, node, cause, onset):
    trust = hist.trust[:, hist.col(node)]
    t = np.asarray(td.t)

    below = np.where((t >= onset) & (trust < DETECT_TRUST))[0]
    latency = float(t[below[0]] - onset) if below.size else None

    post = diag.posterior[:, diag.causes.index(cause)] \
        if cause in diag.causes else None
    peak = float(post.max()) if post is not None else None

    after = t >= onset
    return {
        "detect_latency_s": latency,
        "min_trust_faulted": float(trust[after].min()),
        "peak_posterior_correct_cause": peak,
        "mean_trust_all_nodes": float(hist.trust[after].mean()),
    }


def _ablate(td, drop):
    """Copy the tick stream with `drop` edges removed."""
    out = copy.copy(td)
    out.edges = {k: v for k, v in td.edges.items() if k not in drop}
    return out


def _delta(a, b):
    """b - a, tolerating None (no detection)."""
    if a is None or b is None:
        return None
    return round(b - a, 6)


def main() -> int:
    report = {
        "purpose": "measure the operational contribution of the five "
                   "constant-gate edges",
        "method": "post-hoc ablation of TickData.edges; engine, diagnosis, "
                  "graph, thresholds and seeds unchanged",
        "detect_trust_threshold": DETECT_TRUST,
        "constant_gate_edges": CONSTANT_GATE_EDGES,
        "scenarios": {},
    }

    for name, (node, cause, onset) in CASES.items():
        _, _, td, hist, diag = run_scenario(name)
        base = _metrics(td, hist, diag, node, cause, onset)

        td_abl = _ablate(td, set(CONSTANT_GATE_EDGES))
        h2, d2 = _rerun(td_abl)
        abl = _metrics(td_abl, h2, d2, node, cause, onset)

        # per-edge, to see whether any single one carries the whole effect
        per_edge = {}
        for edge in CONSTANT_GATE_EDGES:
            h3, d3 = _rerun(_ablate(td, {edge}))
            m = _metrics(td, h3, d3, node, cause, onset)
            per_edge[edge] = {
                "d_latency_s": _delta(base["detect_latency_s"],
                                      m["detect_latency_s"]),
                "d_min_trust": _delta(base["min_trust_faulted"],
                                      m["min_trust_faulted"]),
                "d_peak_posterior": _delta(
                    base["peak_posterior_correct_cause"],
                    m["peak_posterior_correct_cause"]),
            }

        report["scenarios"][name] = {
            "faulted_node": node,
            "expected_cause": cause,
            "onset_s": onset,
            "baseline": base,
            "all_five_removed": abl,
            "delta": {
                "d_latency_s": _delta(base["detect_latency_s"],
                                      abl["detect_latency_s"]),
                "d_min_trust": _delta(base["min_trust_faulted"],
                                      abl["min_trust_faulted"]),
                "d_peak_posterior": _delta(
                    base["peak_posterior_correct_cause"],
                    abl["peak_posterior_correct_cause"]),
            },
            "per_edge_removed": per_edge,
        }

    # --- temp_bias_drift: what does a permanent 0.2 weight cost? -------------
    # It touches baro and battery. Compare steady-state trust with the edge
    # present (gate 0.2) against absent, on the clean scenario.
    _, _, td_c, hist_c, _ = run_scenario("clean")
    settled = np.asarray(td_c.t) > 20.0
    h_no, _ = _rerun(_ablate(td_c, {"temp_bias_drift"}))

    tbd = {"edge": "temp_bias_drift", "gate": "0.2 * ones (constant)",
           "touches": ["baro", "battery"], "scenario": "clean",
           "window": "t > 20 s (settled)", "nodes": {}}
    for node in ("baro", "battery"):
        with_e = float(hist_c.trust[settled, hist_c.col(node)].mean())
        without_e = float(h_no.trust[settled, h_no.col(node)].mean())
        tbd["nodes"][node] = {
            "mean_trust_with_edge": round(with_e, 6),
            "mean_trust_without_edge": round(without_e, 6),
            "steady_state_offset": round(without_e - with_e, 6),
        }
    report["temp_bias_drift_constant"] = tbd

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
