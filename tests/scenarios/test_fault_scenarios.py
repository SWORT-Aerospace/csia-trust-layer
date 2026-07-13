"""Phase 4 fault-scenario harness.

For every scripted fault the CSIA pipeline must, with fixed thresholds set
below measured performance (so regressions fail loudly):

  detect    — target sensor's Trust Coefficient falls below its detection
              threshold within a bounded time of fault onset
  attribute — the diagnosis posterior names the correct cause with high
              probability at its peak
  isolate   — non-implicated sensors keep their trust (graceful degradation,
              not cascade); for the dual-IMU case the healthy unit must stay
              measurably above the faulty one
  recover   — trust returns after the fault clears (no latched flags)

Latency is measured per tick and asserted against a loose desktop budget —
logged, not spun: this is desktop Python, not embedded (STM32H7) timing.
"""

import numpy as np
import pytest

# scenario -> expectations. Measured performance (2026-07, seeds fixed):
#   gps_spoof:  min 0.59, detect 2.2 s, P=0.89
#   imu0_bias:  min 0.77, detect 13.0 s (slow ramp), P=0.99, imu1 min 0.86
#   mag_emi:    min 0.28, detect 1.5 s, P=1.00
#   power_sag:  min 0.40, detect 1.6 s, P=1.00
#   vibration:  min 0.17, detect 2.6 s, P=1.00
CASES = {
    "gps_spoof": dict(target="gps", cause="gps_fault", drop_below=0.72,
                      detect_within=5.0, p_cause=0.75, others_floor=0.85,
                      exempt={"gps"}),
    "imu0_bias_drift": dict(target="imu0", cause="imu0_bias_drift",
                            drop_below=0.85, detect_within=16.0, p_cause=0.85,
                            others_floor=0.80, exempt={"imu0", "imu1"}),
    "mag_emi": dict(target="mag", cause="mag_interference", drop_below=0.50,
                    detect_within=4.0, p_cause=0.90, others_floor=0.80,
                    exempt={"mag"}),
    "power_sag": dict(target="battery", cause="power_fault", drop_below=0.60,
                      detect_within=4.0, p_cause=0.90, others_floor=0.75,
                      exempt={"battery", "motor_esc"}),  # both telemetry faulted
    "vibration_anomaly": dict(target="vibration", cause="vibration_anomaly",
                              drop_below=0.45, detect_within=5.0, p_cause=0.90,
                              others_floor=0.75, exempt={"vibration", "motor_esc"}),
}


@pytest.mark.parametrize("name", list(CASES))
def test_fault_detected_attributed_isolated(name, scenario_cache):
    exp = CASES[name]
    title, faults, td, hist, diag = scenario_cache(name)
    onset = min(f.start for f in faults)
    end = max(f.start + f.duration for f in faults)
    c = hist.col(exp["target"])
    trust = hist.trust[:, c]
    t = hist.t

    # --- detect ---------------------------------------------------------------
    assert trust.min() < exp["drop_below"], \
        f"{name}: target trust never dropped below {exp['drop_below']}"
    below = np.where((t > onset) & (trust < 0.85))[0]
    assert len(below), f"{name}: trust never crossed the 0.85 detection line"
    detect_latency = t[below[0]] - onset
    print(f"\n{name}: detection latency {detect_latency:.1f} s, "
          f"min trust {trust.min():.2f}")
    assert detect_latency < exp["detect_within"]

    # --- attribute --------------------------------------------------------------
    ci = diag.causes.index(exp["cause"])
    peak_p = diag.posterior[:, ci].max()
    k_peak = int(np.argmax(diag.posterior[:, ci]))
    top_cause, top_p = diag.top(k_peak)[0]
    print(f"{name}: peak P({exp['cause']}) = {peak_p:.2f} at t={t[k_peak]:.1f}s")
    assert peak_p > exp["p_cause"]
    assert top_cause == exp["cause"], \
        f"{name}: top cause at peak was {top_cause}, not {exp['cause']}"

    # --- isolate ---------------------------------------------------------------
    for n in hist.names:
        if n in exp["exempt"]:
            continue
        floor = hist.trust[250:, hist.col(n)].min()
        assert floor > exp["others_floor"], \
            f"{name}: healthy sensor {n} dragged to {floor:.2f} (cascade)"

    # --- recover ---------------------------------------------------------------
    tail = trust[t > max(end + 10.0, t[-1] - 3.0)]
    assert tail.mean() > 0.85, \
        f"{name}: no recovery after fault cleared (tail {tail.mean():.2f})"

    # --- latency (informational budget) -----------------------------------------
    assert float(hist.latency_us[10:].mean()) < 2000.0


def test_dual_imu_isolation(scenario_cache):
    """The dual-IMU edge is symmetric evidence; trust-weighting must still
    separate faulty imu0 from healthy imu1."""
    _, faults, td, hist, diag = scenario_cache("imu0_bias_drift")
    m0 = hist.trust[250:, hist.col("imu0")].min()
    m1 = hist.trust[250:, hist.col("imu1")].min()
    print(f"\nimu0 min {m0:.2f} vs imu1 min {m1:.2f}")
    assert m1 - m0 > 0.05, "healthy IMU not separated from faulty one"
    ci = diag.causes.index("imu1_bias_drift")
    assert diag.posterior[:, ci].max() < 0.10, \
        "diagnosis wrongly implicates the healthy IMU"


def test_gps_dropout_holds_trust(scenario_cache):
    """Dropout is ABSENCE of data, not evidence of fault: trust must hold
    (frozen Beta state), no diagnosis alarm, and edges must gate out."""
    _, faults, td, hist, diag = scenario_cache("gps_dropout")
    t = hist.t
    c = hist.col("gps")
    window = (t > 25.5) & (t < 33.0)
    drift = np.abs(np.diff(hist.trust[window, c])).sum()
    assert drift < 0.05, f"gps trust moved {drift:.3f} during dropout"
    assert hist.trust[250:, c].min() > 0.85
    nominal = diag.causes.index("nominal")
    assert diag.posterior[window, nominal].min() > 0.85, \
        "dropout misdiagnosed as a fault"


def test_spoof_beats_maneuver_hypothesis(scenario_cache):
    """The discriminator the CSIA description promises: a spoof must NOT be
    explainable as an unexpected maneuver (both IMUs + Doppler agree the
    vehicle didn't move that way)."""
    _, faults, td, hist, diag = scenario_cache("gps_spoof")
    t = diag.t
    window = (t > 24.0) & (t < 35.0)
    gi = diag.causes.index("gps_fault")
    mi = diag.causes.index("unexpected_maneuver")
    assert diag.posterior[window, gi].mean() > 0.6
    assert diag.posterior[window, mi].max() < 0.10
