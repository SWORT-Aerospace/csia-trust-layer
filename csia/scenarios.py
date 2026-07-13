"""Canonical scenario catalog and pipeline assembly.

CSIA role: the single production entry point that wires
sensors -> prediction comparator -> trust engine -> causal diagnosis
for a scripted flight, used identically by the CLI, the dashboard
replay builder, the demo scripts, and the phase-4 test harness.
All seeds are fixed: every scenario is bit-for-bit reproducible.
"""

import logging

from .diagnosis import CausalDiagnosis
from .prediction import PredictionComparator
from .sensors import (GPS, IMU, Barometer, Battery, Fault, Magnetometer,
                      MotorESC, VibrationSensor, generate_flight)
from .trust_engine import TrustEngine
from .trust_graph import build_trust_graph

log = logging.getLogger(__name__)

DURATION = 60.0
TICK_HZ = 25.0

SCENARIOS = {
    "clean": ("Clean flight — no faults injected", []),
    "gps_spoof": ("GPS spoof 20-35 s: position walks off ~3.2 m/s, Doppler clean", [
        Fault("gps_spoof", "gps", 20.0, 15.0, {"drift": (3.0, 1.0, 0.0)})]),
    "gps_dropout": ("GPS dropout 25-33 s: no fix — trust must HOLD, not false-alarm", [
        Fault("dropout", "gps", 25.0, 8.0)]),
    "imu0_bias_drift": ("imu0 accel-z bias drift 20-40 s (0.05 m/s^2 per s)", [
        Fault("bias_drift", "imu0", 20.0, 20.0,
              {"axis": 2, "rate": 0.05, "channel": "accel"})]),
    "mag_emi": ("Magnetometer EMI bursts 25-33 s (10 uT spikes @ 12 Hz)", [
        Fault("emi_spike", "mag", 25.0, 8.0,
              {"amplitude": 10.0, "rate_hz": 12.0})]),
    "power_sag": ("Power sag 30-36 s: pack V dips 1.2 V, ESC telemetry RPM sags", [
        Fault("power_sag", "battery", 30.0, 6.0, {"depth_v": 1.2}),
        Fault("power_sag", "motor_esc", 30.0, 6.0, {"rpm_loss": 350.0})]),
    "vibration_anomaly": ("Prop damage signature 28-40 s: 3x vibration + half-order line", [
        Fault("vibration_anomaly", "vibration", 28.0, 12.0, {"gain": 3.0})]),
    "dual_imu_failure": ("Both IMUs drift (25 s / 28 s onset, opposite signs): "
                         "attitude reference integrity lost — failsafe must "
                         "command stabilize + controlled descent", [
        Fault("bias_drift", "imu0", 25.0, 30.0,
              {"axis": 2, "rate": 0.18, "channel": "accel"}),
        Fault("bias_drift", "imu1", 27.0, 28.0,
              {"axis": 2, "rate": -0.15, "channel": "accel"})]),
}


def make_sensors() -> dict:
    """The eight sensor nodes with fixed seeds (deterministic runs)."""
    return {
        "imu0": IMU("imu0", seed=1),
        "imu1": IMU("imu1", seed=2),
        "baro": Barometer(seed=3),
        "mag": Magnetometer(seed=4),
        "gps": GPS(seed=5),
        "motor_esc": MotorESC(seed=6),
        "battery": Battery(seed=7),
        "vibration": VibrationSensor(seed=8),
    }


def sample_streams(truth, faults=()) -> dict:
    known = set(make_sensors())
    for f in faults:
        if f.target not in known:
            raise ValueError(f"fault targets unknown sensor {f.target!r}; "
                             f"known: {sorted(known)}")
    return {name: s.sample(truth, faults) for name, s in make_sensors().items()}


def run_pipeline(truth=None, faults=(), duration: float = DURATION,
                 tick_hz: float = TICK_HZ):
    """Full CSIA pipeline. Returns (td, hist, diag)."""
    if truth is None:
        truth = generate_flight(duration=duration, dt=0.01)
    streams = sample_streams(truth, faults)
    td = PredictionComparator(tick_hz=tick_hz).build(streams, duration)
    hist = TrustEngine(build_trust_graph()).run(td)
    diag = CausalDiagnosis().run(td)
    log.info("pipeline complete: %d ticks, trust-core %.1f us/tick mean",
             len(td.t), float(hist.latency_us[10:].mean()))
    return td, hist, diag


def run_scenario(name: str, truth=None):
    """Run a named scenario from the catalog. Returns (title, faults, td, hist, diag)."""
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario {name!r}; available: {list(SCENARIOS)}")
    title, faults = SCENARIOS[name]
    td, hist, diag = run_pipeline(truth=truth, faults=faults)
    return title, faults, td, hist, diag
