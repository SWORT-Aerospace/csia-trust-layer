"""The component simulator and its validation campaign, pinned.

Three classes of thing here, and the second is the one that matters:

  * the simulator produces physically sensible telemetry at all;
  * THE TWO CONFOUNDS THE CROSS-RELATION MATRIX CAUGHT stay fixed -- a
    faulted run must differ from a clean one ONLY by the fault;
  * every residual is covered, gated, and paired with a catalogue entry.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_components import RELATIONS                             # noqa: E402
from csia_components import residuals as R                        # noqa: E402
from csia_components import simulate as S                         # noqa: E402


@pytest.fixture(scope="module")
def clean():
    return S.Platform(seed=0, duration=40.0).run()


# --- the plant is physically sensible --------------------------------------

def test_a_clean_hover_is_in_the_right_physical_region(clean):
    pack = clean.array("pack_current")
    volt = clean.array("pack_voltage")
    rpm = np.asarray(clean.rpm, dtype=float)
    temp = np.asarray(clean.temperature, dtype=float)
    assert 15.0 < pack.mean() < 40.0, pack.mean()
    assert 13.5 < volt.mean() < 17.0, volt.mean()
    assert 5000 < rpm.mean() < 7000, rpm.mean()
    assert S.AMBIENT_C < temp.mean() < S.AMBIENT_C + 30.0, temp.mean()


def test_the_controller_holds_the_setpoint_on_a_clean_run(clean):
    vz = clean.array("vz")
    assert abs(vz[len(vz) // 2:].mean()) < 0.05


def test_the_controller_masks_an_efficiency_loss_in_the_output(clean):
    """The effect `catalog.py` is built around: the plant output carries no
    error while the plant degrades, and the COMMAND moves instead."""
    f = S.Fault("esc_efficiency_loss", "esc1", 20.0, 30.0, 0.30)
    bad = S.Platform(seed=0, duration=60.0).run((f,))
    t = bad.array("t")
    w = (t >= 25) & (t <= 48)
    assert abs(bad.array("vz")[w].mean()) < 0.05, "the loop failed to hold"
    duty = np.asarray(bad.duty, dtype=float)[w].mean()
    clean_duty = np.asarray(
        S.Platform(seed=0, duration=60.0).run().duty, dtype=float)[w].mean()
    assert duty > clean_duty * 1.02, "the command did not rise to compensate"


# --- the two confounds the matrix caught -----------------------------------

def test_a_bus_fault_leaves_every_unrelated_channel_bit_identical():
    """THE FIRST CONFOUND. Drawing a random number only when a drop was
    possible made a faulted run consume a different number of draws, so
    every downstream noise sample differed and `actuator_response`
    'detected' bus drops at 1.3x the clean maximum with no physics behind
    it."""
    clean = S.Platform(seed=0, duration=30.0).run()
    bad = S.Platform(seed=0, duration=30.0).run(
        (S.Fault("bus_drops", "canbus", 10.0, 10.0, 0.25),))
    for channel in ("pack_current", "pack_voltage", "vz"):
        assert np.allclose(clean.array(channel), bad.array(channel)), (
            f"{channel} moved under a link fault; the RNG streams have "
            f"diverged again and every cross-relation result is confounded")
    assert bad.array("frames_err")[-1] > 0, "the fault did not land"


def test_both_clocks_see_the_same_wall_time_under_a_scheduling_fault():
    """THE SECOND CONFOUND. `clock_a` used the NOMINAL period while the loop
    was stretched, so a scheduling fault desynchronised the two clocks and
    `clock_agreement` reported a 4e7-fold excursion on a fault with no clock
    involvement."""
    bad = S.Platform(seed=0, duration=30.0).run(
        (S.Fault("cpu_overrun", "cpu", 10.0, 10.0, 0.01),))
    a, b = bad.array("clock_a"), bad.array("clock_b")
    drift = ((b[-1] - b[0]) - (a[-1] - a[0])) / (a[-1] - a[0])
    assert abs(drift - 1.5e-6) < 1e-7, (
        f"relative clock drift is {drift}, not the specified 1.5e-6; the "
        f"clocks have desynchronised on something other than their spec")


def test_a_fault_outside_its_window_changes_nothing():
    clean = S.Platform(seed=0, duration=30.0).run()
    later = S.Platform(seed=0, duration=30.0).run(
        (S.Fault("bearing_friction", "esc0", 25.0, 5.0, 2.0),))
    w = clean.array("t") < 20.0
    assert np.allclose(np.asarray(clean.branch_current)[w],
                       np.asarray(later.branch_current)[w])


# --- residual coverage and gates -------------------------------------------

def test_every_residual_matches_a_catalogued_relation():
    keys = {r.key for r in RELATIONS}
    assert set(R.RESIDUALS) <= keys
    assert set(R.NOT_IMPLEMENTED) <= keys
    assert set(R.RESIDUALS) | set(R.NOT_IMPLEMENTED) == keys, (
        "a catalogued relation has neither a residual nor a recorded reason "
        "for not having one; coverage would be silently overstated")


def test_the_unimplemented_relations_say_why():
    for key, why in R.NOT_IMPLEMENTED.items():
        assert len(why) > 25, key


def test_gates_return_exactly_zero_outside_their_condition(clean):
    """A gate that down-weights is not a gate: an inapplicable check would
    contribute a little agreement and absence of evidence would become
    evidence of health."""
    moving = S.Platform(seed=0, duration=40.0,
                        setpoint=lambda t: 0.4 * np.sin(t)).run()
    _, gate = R.effort_drift(moving, 25.0, 38.0, reference_effort=1.0)
    assert gate == 0.0, "effort_drift ran during a manoeuvre"

    _, gate = R.source_impedance(clean, 25.0, 38.0,
                                 r_nominal=S.PACK_R_NOMINAL)
    assert gate == 0.0, "source_impedance ran at a constant load"

    _, gate = R.thermal_rise(clean, 25.0, 38.0, thermal_k=S.THERMAL_K,
                             esc_r=S.ESC_R, motor=0,
                             settle_s=S.THERMAL_TAU,
                             fault_free_change_at=20.0)
    assert gate == 0.0, "thermal_rise ran inside its settling time"

    _, gate = R.error_rate(clean, 25.0, 38.0, baseline_rate=None)
    assert gate == 0.0, "error_rate ran with no baseline"


def test_a_gate_that_IS_met_returns_one(clean):
    """Anti-vacuity: gates that refused everything would pass the test
    above and measure nothing."""
    _, gate = R.power_balance(clean, 25.0, 38.0,
                              quiescent_a=S.QUIESCENT_A)
    assert gate == 1.0
    _, gate = R.effort_drift(clean, 25.0, 38.0, reference_effort=1.0)
    assert gate == 1.0
    varying = S.Platform(seed=0, duration=40.0,
                         setpoint=lambda t: 0.6 * np.sin(0.5 * t)).run()
    _, gate = R.source_impedance(varying, 5.0, 38.0,
                                 r_nominal=S.PACK_R_NOMINAL)
    assert gate == 1.0, "source_impedance never runs, even under excitation"


# --- the campaign ----------------------------------------------------------

def test_campaign_controls_pass():
    from tools.assurance.instrument_controls import guard
    from tools.research import component_validation as V
    V._controls()
    assert guard(V.INSTRUMENT)["verdict"] == "PASS"


def test_the_effort_reference_is_a_held_out_run():
    """Taking it from the run being scored made the clean residual
    identically zero, so every fault 'detected' and the floor meant
    nothing. Same train-on-test error MX-030 fixed on the predictor side."""
    from tools.research import component_validation as V
    assert V.REFERENCE_SEED not in V.SEEDS
    src = open(os.path.join(ROOT, "tools", "research",
                            "component_validation.py"),
               encoding="utf-8").read()
    assert "_clean_reference(seed)" not in src, (
        "a call site still derives the reference from the scored seed")


def test_the_blindness_predictions_are_stated_with_reasons():
    from tools.research import component_validation as V
    assert len(V.BLINDNESS_PREDICTIONS) >= 5
    for rel, kind, why in V.BLINDNESS_PREDICTIONS:
        assert rel in R.RESIDUALS, rel
        assert kind in S.FAULT_KINDS, kind
        assert len(why) > 25


def test_the_falsified_prediction_is_recorded_in_the_catalogue():
    """MX-036 falsified `actuator_response`'s blind spot. The catalogue must
    carry the correction, not the original claim."""
    from csia_components import catalog, relation
    rel = relation("actuator_response")
    assert "MX-036" in rel.blind_to
    assert "TRACKING ERROR" in rel.blind_to
    assert "CORRECTED BY MEASUREMENT" in catalog.__doc__
