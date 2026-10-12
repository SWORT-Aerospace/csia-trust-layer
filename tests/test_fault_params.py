"""A fault parameter the sensor ignores must be an error, not a default.

WHAT WENT WRONG, TWICE IN ONE DAY
----------------------------------
`Fault` raises on an unknown KIND, deliberately, because a typo'd kind would
be silently ignored by every sensor. Its PARAMETERS had no such check. Each
sensor reads what it knows with `params.get(name, default)`, so

    Fault("power_sag", "battery", 20, 30, {"depth": 0.25})

is not a 0.25 V sag. It is the battery's default 1.0 V sag, applied
identically at every value the caller writes. A magnitude sweep over that
name produces a smooth, plausible, entirely meaningless curve.

MX-030 and MX-031 are the two occurrences. The predictor study named `depth`,
`amp` and `rate` where the sensors read `depth_v`, `amplitude` and `drift`;
the config sweep repeated two of them. Both reported detection results for
sweeps that never varied the fault.

The correct names were already written correctly in
`csia_stress/falsify.py`, in the same session, in a file that had been read.
Which is the point: this cannot be fixed by being more careful.

WHY THE CHECK IS BEHAVIOURAL
-----------------------------
`effective_params` asks the sensor model rather than consulting a table. A
table would be a second copy of the sensor models, free to drift; asking the
model cannot drift.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.sensors.faults import Fault                              # noqa: E402
from csia_stress import fault_params as fp                         # noqa: E402


#: The names each sensor/kind pair is BELIEVED to read, cited to the line
#: that reads it. A test below asserts the belief against the model, so this
#: table can never quietly become wrong -- it fails instead.
EXPECTED = {
    ("baro", "bias_drift"): {"rate"},                # barometer.py:42
    ("imu0", "bias_drift"): {"rate", "axis", "channel"},   # imu.py:56-58
    ("mag", "emi_spike"): {"amplitude", "rate_hz"},  # magnetometer.py:34-35
    ("battery", "power_sag"): {"depth_v"},           # battery.py:30
    ("motor_esc", "power_sag"): {"rpm_loss"},        # motor.py:32
    ("vibration", "vibration_anomaly"): {"gain"},    # vibration.py:38
    ("gps", "gps_spoof"): {"drift"},                 # gps.py:42
}


@pytest.mark.parametrize("pair,expected", sorted(EXPECTED.items()))
def test_the_documented_parameters_are_the_ones_the_sensor_reads(pair,
                                                                 expected):
    sensor, kind = pair
    assert set(fp.known_effective(sensor, kind)) == expected


def test_a_wrong_name_raises_and_names_the_right_one():
    with pytest.raises(ValueError) as excinfo:
        fp.assert_effective("battery", "power_sag", ["depth"])
    message = str(excinfo.value)
    assert "depth" in message
    assert "depth_v" in message, (
        "the error must supply the correction, or the next caller guesses "
        "again")


def test_a_correct_name_passes():
    """Anti-vacuity. A guard that rejected everything would be useless and
    would look identical in a test that only checks it raises."""
    fp.assert_effective("battery", "power_sag", ["depth_v"])
    fp.assert_effective("gps", "gps_spoof", ["drift"])
    fp.assert_effective("mag", "emi_spike", ["amplitude", "rate_hz"])


def test_the_guard_catches_every_name_that_was_actually_got_wrong():
    """The three real mistakes, pinned as regressions."""
    for sensor, kind, bad in (("battery", "power_sag", "depth"),
                              ("mag", "emi_spike", "amp"),
                              ("gps", "gps_spoof", "rate")):
        with pytest.raises(ValueError):
            fp.assert_effective(sensor, kind, [bad])


def test_assert_fault_effective_works_on_a_built_fault():
    fp.assert_fault_effective(
        Fault("power_sag", "battery", 20.0, 30.0, {"depth_v": 1.3}))
    with pytest.raises(ValueError):
        fp.assert_fault_effective(
            Fault("power_sag", "battery", 20.0, 30.0, {"depth": 1.3}))


def test_a_fault_with_no_parameters_is_not_rejected():
    """`dropout` takes none, and demanding one would break every dropout."""
    fp.assert_effective("gps", "dropout", [])
    fp.assert_fault_effective(Fault("dropout", "gps", 20.0, 30.0, {}))


def test_the_probe_uses_a_fresh_sensor_for_each_value():
    """Reusing one sensor would advance its generator between the two
    samples, so every parameter would look effective and the guard would
    pass on the very names it exists to catch."""
    src = open(os.path.join(ROOT, "csia_stress", "fault_params.py"),
               encoding="utf-8").read()
    body = src[src.index("def _differs"):src.index("def effective_params")]
    assert body.count("_make_sensor(sensor_name)") == 1
    assert "for value in" in body
    assert "A FRESH SENSOR EACH TIME" in body


def test_vector_parameters_are_probed_as_vectors():
    """`drift` is a three-vector; probing it with a scalar raises inside the
    sensor, which is a different failure from 'the sensor ignores it'."""
    assert "drift" in fp._VECTOR_PARAMS
    fp.assert_effective("gps", "gps_spoof", ["drift"])


# --- the two tools that had the bug ---------------------------------------

def test_the_config_sweep_validates_its_faults_at_import():
    from tools.research import config_sweep as cs
    for fault in cs.FAULTS.values():
        fp.assert_fault_effective(fault)
    src = open(os.path.join(ROOT, "tools", "research", "config_sweep.py"),
               encoding="utf-8").read()
    assert "_check_fault_parameters()" in src


def test_the_predictor_study_validates_its_grids_at_import():
    from tools.research import predictor_study as ps
    for (sensor, kind), (param, _values) in ps.MAGNITUDES.items():
        fp.assert_effective(sensor, kind, [param])
    src = open(os.path.join(ROOT, "tools", "research",
                            "predictor_study.py"), encoding="utf-8").read()
    assert "_check_grid_parameters()" in src


def test_every_worst_case_fault_is_actually_controllable_on_its_target():
    """WORST_PARAMS never had this bug, and this pins that it stays that way.

    THE CHECK IS `assert_any_effective`, NOT `assert_effective`, and the
    difference is not a loosening. WORST_PARAMS holds one dict PER KIND
    applied to whichever sensor is faulted, so it necessarily carries keys
    some targets do not read -- `power_sag` names `depth_v` for the battery
    and `rpm_loss` for the motor, and each ignores the other's. Demanding
    every key bite on every target would fail the table for being correctly
    written.

    What matters is that the magnitude is CONTROLLABLE on each target. A
    target where no key reaches it is being faulted at its default while the
    table calls it a worst case, and every "no counterexample" from that
    target would be about a milder fault than the one claimed.
    """
    from csia_stress.applicability import matrix
    from csia_stress.falsify import WORST_PARAMS
    live = {(kind, target) for kind, target in matrix().live_pairs()}
    checked = 0
    for kind, params in WORST_PARAMS.items():
        if not params:
            continue
        for target in sorted({t for k, t in live if k == kind}):
            fp.assert_any_effective(target, kind, list(params))
            checked += 1
    assert checked > 0, "no live pair was checked; this test proves nothing"


def test_assert_any_effective_still_rejects_an_entirely_wrong_dict():
    """Anti-vacuity for the weaker check: it must not accept anything."""
    with pytest.raises(ValueError):
        fp.assert_any_effective("battery", "power_sag",
                                ["depth", "amp", "nonsense"])


def test_the_two_strengths_differ_on_a_real_case():
    """`bias_drift` on the barometer: `rate` bites, `axis` and `channel` do
    not. The strict check must reject it and the superset check accept it,
    or the distinction is decorative."""
    params = ["rate", "axis", "channel"]
    fp.assert_any_effective("baro", "bias_drift", params)
    with pytest.raises(ValueError):
        fp.assert_effective("baro", "bias_drift", params)
