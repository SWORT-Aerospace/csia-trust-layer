"""Unit tests: sensor simulation layer (phase 1)."""

import numpy as np
import pytest

from csia.prediction.attitude import calibrate_imu_stream
from csia.scenarios import make_sensors, sample_streams
from csia.sensors import Fault
from csia.sensors.barometer import altitude_to_pressure, pressure_to_altitude
from csia.sensors.truth import G, world_to_body


def test_rotation_is_orthonormal():
    rng = np.random.default_rng(0)
    att = rng.uniform(-0.5, 0.5, (100, 3))
    v = rng.normal(size=(100, 3))
    out = world_to_body(v, att)
    np.testing.assert_allclose(np.linalg.norm(out, axis=1),
                               np.linalg.norm(v, axis=1), rtol=1e-12)


def test_coordinated_turn_reads_load_factor(truth):
    """Body-z specific force must equal |a - g| — the attitude/thrust sign
    conventions that phase 2 debugging fixed must never regress."""
    f_w = truth.acc + np.array([0.0, 0.0, G])
    f_b = world_to_body(f_w, truth.att)
    # peak of the banked turn: |f| well above 1 g, and body z carries it
    k = np.argmax(np.linalg.norm(f_w, axis=1))
    assert np.linalg.norm(f_w[k]) > 1.15 * G
    np.testing.assert_allclose(f_b[k, 2], np.linalg.norm(f_w[k]), rtol=0.02)


def test_isa_round_trip():
    alt = np.linspace(0, 3000, 50)
    np.testing.assert_allclose(
        pressure_to_altitude(altitude_to_pressure(alt)), alt, atol=1e-6)


def test_imu_calibration_removes_turn_on_bias(truth):
    imu = make_sensors()["imu0"].sample(truth)
    cal = calibrate_imu_stream(imu)
    mask = cal["t"] < 2.0
    np.testing.assert_allclose(cal["accel"][mask].mean(axis=0),
                               [0.0, 0.0, G], atol=5e-3)
    np.testing.assert_allclose(cal["gyro"][mask].mean(axis=0), 0.0, atol=5e-4)


def test_fault_validation():
    with pytest.raises(ValueError, match="unknown fault kind"):
        Fault("gps_spooof", "gps", 20.0, 15.0)
    with pytest.raises(ValueError, match="window invalid"):
        Fault("dropout", "gps", 20.0, 0.0)


def test_unknown_fault_target_rejected(truth):
    with pytest.raises(ValueError, match="unknown sensor"):
        sample_streams(truth, [Fault("dropout", "lidar", 10.0, 5.0)])


def test_spoof_confined_to_window(truth):
    clean = make_sensors()["gps"].sample(truth)
    spoofed = make_sensors()["gps"].sample(truth, [
        Fault("gps_spoof", "gps", 20.0, 15.0, {"drift": (3.0, 1.0, 0.0)})])
    t = clean["t"]
    before = t < 20.0
    inside = (t > 25.0) & (t < 35.0)
    np.testing.assert_array_equal(clean["pos"][before], spoofed["pos"][before])
    assert np.abs(spoofed["pos"][inside] - clean["pos"][inside]).max() > 5.0
    # Doppler untouched — the whole point of the spoof signature
    np.testing.assert_array_equal(clean["vel"], spoofed["vel"])


def test_dropout_marks_invalid_only_in_window(truth):
    d = make_sensors()["gps"].sample(truth, [Fault("dropout", "gps", 25.0, 8.0)])
    t = d["t"]
    assert not d["valid"][(t >= 25.0) & (t < 33.0)].any()
    assert d["valid"][t < 25.0].all() and d["valid"][t >= 33.0].all()


def test_streams_are_deterministic(truth):
    a = sample_streams(truth)
    b = sample_streams(truth)
    for name in a:
        for key in a[name]:
            np.testing.assert_array_equal(a[name][key], b[name][key])
