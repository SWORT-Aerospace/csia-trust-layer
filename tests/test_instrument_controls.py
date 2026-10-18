"""The controls must catch the bugs that actually happened.

A control pair that cannot fail is precisely the disease it was built to
cure, one level up. So these tests do not merely check that the controls
pass on a healthy tree -- they REINTRODUCE the three real defects and assert
the controls refuse:

    MX-020  the quality ratchet compared a file against itself and reported
            HOLDS every night of its life
    MX-021  the detection sweep swallowed an AttributeError, read it as
            "not detected", and published a finding about the frozen core
    SR-007  the false-alarm measurement read a whole-run minimum spanning
            warm-up and reported the 0.8 prior's floor as a physical
            mechanism

Each was found by a human running a control on a hunch. None was caught by
anything structural. After this file, all three are.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.assurance.instrument_controls import (NEGATIVE,       # noqa: E402
                                                 POSITIVE, REGISTRY,
                                                 Control, ControlFailure,
                                                 ControlPair, guard, stamp)


def _ratchet():
    path = os.path.join(ROOT, "tools", "xr", "quality_ratchet.py")
    spec = importlib.util.spec_from_file_location("_qr_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# the framework's own rules
# ---------------------------------------------------------------------------

def test_a_pair_needs_one_of_each_kind():
    """Two positives cannot tell a stuck-on-yes instrument from a working
    one, and two negatives cannot tell stuck-on-no."""
    c = Control(name="x", kind=POSITIVE, run=lambda: True,
                expect=bool, basis="test")
    with pytest.raises(ValueError, match="POSITIVE and one"):
        ControlPair(instrument="i", positive=c, negative=c)


def test_an_unregistered_instrument_may_not_emit():
    """The default is refusal. An instrument with no controls is not
    trusted merely because nobody wrote any."""
    with pytest.raises(ControlFailure, match="no registered control pair"):
        guard("nothing.registered.here")


def test_an_instrument_that_raises_fails_its_control():
    """As broken as one that answers wrongly, and not to be excused."""
    def _boom():
        raise RuntimeError("apparatus on fire")

    pair = ControlPair(
        instrument="i",
        positive=Control(name="p", kind=POSITIVE, run=_boom,
                         expect=bool, basis="test"),
        negative=Control(name="n", kind=NEGATIVE, run=lambda: False,
                         expect=lambda v: v is False, basis="test"))
    report = pair.verify()
    assert report["verdict"] == "FAIL"
    assert "apparatus on fire" in report["controls"][0]["error"]


def test_the_control_evidence_travels_with_the_artifact():
    """An artifact whose controls were run somewhere else, or not at all, is
    indistinguishable from one whose instrument was broken."""
    doc = stamp({"result": 1}, {"verdict": "PASS"})
    assert doc["instrument_controls"]["verdict"] == "PASS"
    assert doc["result"] == 1


def test_no_control_is_justified_by_the_instrument_it_checks():
    """A control whose expected answer comes from the instrument under test
    proves only self-consistency -- which is exactly what MX-020 had."""
    _register_all()
    for name, pair in REGISTRY.items():
        for control in (pair.positive, pair.negative):
            assert control.basis, f"{name}/{control.name} states no basis"
            assert len(control.basis) > 30, (
                f"{name}/{control.name}: a one-word basis is not a "
                "justification")


# ---------------------------------------------------------------------------
# MX-021 reintroduced: the swallowed exception
# ---------------------------------------------------------------------------

def test_the_sweep_controls_catch_the_mx_021_defect(monkeypatch):
    """THE EXACT BUG. `.detected` does not exist; the old code caught the
    AttributeError per point and read it as a miss. Restored here, the
    positive control must refuse."""
    from csia_stress import detection_floor as df

    class _Run:
        detection_status = "DETECTED"
        min_trust = {"gps": 0.5}

        @property
        def detected(self):
            raise AttributeError("no such field")

    def _broken(kind, target, value, spec, supervised):
        run = _Run()
        try:
            return run.detected, 0.5      # the original defect, verbatim
        except Exception:                  # noqa: BLE001
            return False, 0.5              # ...swallowed into a miss

    df._controls()
    monkeypatch.setattr(df, "_run_one", _broken)
    with pytest.raises(ControlFailure, match="controls FAILED"):
        guard(df.INSTRUMENT)


def test_the_sweep_controls_catch_an_instrument_stuck_on_detected(
        monkeypatch):
    """The opposite defect. A positive control alone would pass it."""
    from csia_stress import detection_floor as df

    df._controls()
    monkeypatch.setattr(df, "_run_one",
                        lambda k, t, v, s, sup: (True, 0.5))
    with pytest.raises(ControlFailure):
        guard(df.INSTRUMENT)


# ---------------------------------------------------------------------------
# SR-007 reintroduced: the warm-up floor read as a mechanism
# ---------------------------------------------------------------------------

def test_the_false_alarm_controls_catch_the_sr_007_defect(monkeypatch):
    """THE EXACT BUG. A whole-run minimum spans warm-up from the 0.8 prior
    and returns 0.8182 whatever is faulted. The negative control requires a
    healthy baro to read above 0.9, so the constant fails it."""
    from csia_stress import low_trust_false_alarm as fa

    fa._controls()
    monkeypatch.setattr(fa, "_post_arm_min_trust",
                        lambda profile, sensor: 0.8182)
    with pytest.raises(ControlFailure, match="controls FAILED"):
        guard(fa.INSTRUMENT)


def test_the_false_alarm_controls_catch_a_measurement_stuck_on_healthy(
        monkeypatch):
    """An instrument that always returns 0.99 would report zero false
    alarms forever. The positive control is what catches it."""
    from csia_stress import low_trust_false_alarm as fa

    fa._controls()
    monkeypatch.setattr(fa, "_post_arm_min_trust",
                        lambda profile, sensor: 0.99)
    with pytest.raises(ControlFailure):
        guard(fa.INSTRUMENT)


# ---------------------------------------------------------------------------
# MX-020 reintroduced: the gate that could not fail
# ---------------------------------------------------------------------------

def test_the_ratchet_controls_catch_a_gate_that_cannot_fail(monkeypatch):
    """THE EXACT BUG. A comparison that always returns HOLDS passes every
    real run -- that is what MX-020 was -- and must fail its own control."""
    ratchet = _ratchet()
    ratchet._controls()
    monkeypatch.setattr(ratchet, "check",
                        lambda measured, floor: {"verdict": "HOLDS"})
    with pytest.raises(ControlFailure, match="controls FAILED"):
        guard(ratchet.INSTRUMENT)


def test_the_ratchet_controls_catch_a_gate_stuck_on_regression(monkeypatch):
    ratchet = _ratchet()
    ratchet._controls()
    monkeypatch.setattr(ratchet, "check",
                        lambda measured, floor: {"verdict": "REGRESSION"})
    with pytest.raises(ControlFailure):
        guard(ratchet.INSTRUMENT)


# ---------------------------------------------------------------------------
# the healthy tree
# ---------------------------------------------------------------------------

#: EVERY instrument that writes an artifact. A tool that measures something
#: and emits it, with no controls, is the gap this whole module is about.
ALL_INSTRUMENTS = {
    "tools.xr.quality_ratchet": ("tools/xr/quality_ratchet.py", "_qr"),
    "tools.xr.mutation_probe": ("tools/xr/mutation_probe.py", "_mp"),
    "tools.xr.stress_regression": ("tools/xr/stress_regression.py", "_sr"),
    "tools.deploy.preflight": ("tools/deploy/preflight.py", "_pf"),
    "tools.assurance.decision_replay":
        ("tools/assurance/decision_replay.py", "_dr"),
    "tools.assurance.attribute_replay_divergence":
        ("tools/assurance/attribute_replay_divergence.py", "_ard"),
    "csia_stress.detection_floor": ("csia_stress/detection_floor.py", "_df"),
    "csia_stress.low_trust_false_alarm":
        ("csia_stress/low_trust_false_alarm.py", "_fa"),
    "csia_stress.campaign": ("csia_stress/campaign.py", "_cp"),
    "csia_stress.falsify": ("csia_stress/falsify.py", "_fs"),
}


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, rel))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _register_all():
    for rel, name in ALL_INSTRUMENTS.values():
        _load(rel, name)._controls()


@pytest.mark.parametrize("instrument", [
    "tools.xr.quality_ratchet",
    "tools.xr.mutation_probe",
    "tools.xr.stress_regression",
    "tools.deploy.preflight",
    "tools.assurance.decision_replay",
    "tools.assurance.attribute_replay_divergence",
    "csia_stress.falsify",
])
def test_the_fast_instruments_pass_their_controls_on_this_tree(instrument):
    """The two stress instruments drive whole 90 s flights and are covered
    by their own CLI runs; every other registered instrument is checked
    here, on every suite run."""
    _register_all()
    report = guard(instrument)
    assert report["verdict"] == "PASS"
    assert {c["kind"] for c in report["controls"]} == {POSITIVE, NEGATIVE}


def test_every_registered_pair_declares_what_it_does_not_establish():
    """A control pair is a liveness and discrimination check. Presenting it
    as a calibration would be a new overclaim in the machinery built to
    stop overclaiming."""
    _register_all()
    for name, pair in REGISTRY.items():
        assert "calibration" in pair.does_not_establish, name


def test_every_artifact_writing_instrument_is_registered():
    """The rule is only a rule if it has no exceptions. An instrument that
    measures something, writes it to a results directory, and has no
    controls is exactly the gap MX-025 is about."""
    _register_all()
    missing = set(ALL_INSTRUMENTS) - set(REGISTRY)
    assert not missing, f"{sorted(missing)} emit artifacts with no controls"


def test_the_three_instruments_that_fabricated_are_registered():
    """MX-020, MX-021 and SR-007 each came from one of these."""
    _register_all()
    for instrument in ("tools.xr.quality_ratchet",
                       "csia_stress.detection_floor",
                       "csia_stress.low_trust_false_alarm"):
        assert instrument in REGISTRY, f"{instrument} has no controls"


def test_every_instrument_guards_before_it_writes():
    """A registered control pair that main() never calls is decoration.
    Checked against the source, because the alternative is running nine
    CLIs."""
    for rel, _name in ALL_INSTRUMENTS.values():
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            src = fh.read()
        assert "guard(INSTRUMENT)" in src, f"{rel} never runs its controls"
        assert "stamp(" in src, f"{rel} never attaches its control evidence"


# ---------------------------------------------------------------------------
# the falsification search: the vacuity failure it must not have
# ---------------------------------------------------------------------------

def test_a_search_over_an_empty_space_is_not_a_negative_result():
    """THE DANGEROUS FAILURE. A search that enumerates nothing reports
    NO_COUNTEREXAMPLE_IN_SEARCHED_SPACE -- the identical words a search that
    looked hard and found nothing produces. The negative control therefore
    requires combinations_run > 0, not merely the verdict."""
    from csia_stress import falsify

    falsify._controls()
    pair = REGISTRY["csia_stress.falsify"]
    verdict, ran = pair.negative.run()
    assert verdict == falsify.NOT_FOUND
    assert ran > 0, "a negative result must have run something"
    assert not pair.negative.expect((falsify.NOT_FOUND, 0)), (
        "the control must REJECT a not-found that ran nothing")


def test_the_search_recognises_a_counterexample_put_in_front_of_it():
    from csia_stress import falsify

    falsify._controls()
    pair = REGISTRY["csia_stress.falsify"]
    assert pair.positive.run() == falsify.FOUND


def test_the_search_space_is_not_empty_and_is_ordered_adversarially():
    """The enumeration must actually contain the SR-008 shape: all four of
    motor_esc's edge partners degraded at once. If the space no longer
    contains it, the search cannot rediscover the case it exists for."""
    from csia_stress import falsify

    combos = falsify._combinations("motor_esc")
    assert len(combos) == 95, f"expected 95 combinations, got {len(combos)}"
    assert len(combos[0]) == 4, "most adversarial must come first"
    assert len(combos[-1]) == 1, "least adversarial must come last"
    # the SR-008 conjunction itself
    sr008 = {"imu0": "dropout", "imu1": "dropout", "battery": "dropout",
             "vibration": "vibration_anomaly"}
    assert sr008 in combos, "the SR-008 case is no longer in the space"


def test_the_report_refuses_to_call_a_clean_search_a_proof():
    """A search that reported 'the claim holds' would sound more conclusive
    than the random campaign it replaces while establishing no more."""
    from csia_stress import falsify

    assert falsify.NOT_FOUND == "NO_COUNTEREXAMPLE_IN_SEARCHED_SPACE"
