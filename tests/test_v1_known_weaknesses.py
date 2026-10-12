"""v1's known weaknesses, kept visible on purpose.

`docs/v1/V1_FINAL_RESEARCH_VERDICT.md` section 3 lists six. The work package
is explicit: "The goal is not to make tests green by deleting difficult
scenarios."

So these tests ASSERT THE WEAKNESSES ARE STILL THERE. That is deliberate. If
one starts failing, v1 behaviour changed, and the correct response is to find
out why -- not to update the expectation. A weakness that quietly disappears
is indistinguishable from one someone tuned away, and the freeze exists to
make that difference visible.

W-4 (banked-evidence escalation delay) is covered by the WP-C8 escalation
artifacts rather than re-derived here.
"""

import os

import pytest

from csia.aircraft.adapters import get_adapter
from csia.aircraft.qualification import default_contract
from csia.aircraft.sample import AircraftSample, ChannelValue, MissingReason, Quality

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*parts):
    return open(os.path.join(ROOT, *parts), encoding="utf-8").read()


# --------------------------------------------------------------------------
# W-1 GNSS fix-loss self-occlusion

@pytest.mark.slow
def test_w1_gps_dropout_escalates_without_naming_a_cause():
    """The vehicle reacts; the layer cannot say why.

    This is the paper's central result and it must remain observable.
    """
    from csia.runtime.online import OnlineTrustLayer
    from csia.runtime.plugins import SimulatedFlightSource
    from csia.scenarios import SCENARIOS

    assert "gps_dropout" in SCENARIOS
    layer = OnlineTrustLayer(tick_hz=25.0)
    states = []
    for sensor, t, ch in SimulatedFlightSource("gps_dropout").samples():
        states.extend(layer.ingest(sensor, t, ch) or [])

    assert states, "scenario produced no states"
    post = [s for s in states if s.t > 25.0]
    tops = [s.top_causes(1)[0][0] for s in post]
    nominal_frac = sum(t == "nominal" for t in tops) / len(tops)
    assert nominal_frac > 0.9, (
        f"W-1 changed: gps_dropout now names a cause "
        f"{1 - nominal_frac:.0%} of the time. Investigate before updating "
        f"this expectation.")


def test_w1_the_log_can_tell_blocked_from_absent():
    """The mitigation for W-1 is legibility, not a fix."""
    s = AircraftSample(t_mono=0.0)
    s.gnss["gnss.position"] = ChannelValue.absent(
        "gnss.position", MissingReason.NO_3D_FIX)
    s.esc["esc.current"] = ChannelValue.absent(
        "esc.current", MissingReason.STUB,
        quality=Quality.STUB_OR_NONINFORMATIVE)
    assert {cv.channel for cv in s.blocked_channels()} == {"esc.current"}
    assert s.get("gnss.position").missing is MissingReason.NO_3D_FIX


# --------------------------------------------------------------------------
# W-3 IMU-bias detection depends on the noise profile

def test_w3_profiles_differ_enough_to_change_the_answer():
    """If the profiles quietly converged, W-3 would look fixed with nothing
    fixed."""
    from csia.simulation.profiles import get_profile
    ideal, field = get_profile("IDEAL_SIM"), get_profile("FIELD_DERIVED_NOISE")
    assert not ideal.sitl_params, "IDEAL_SIM should be simulator defaults"
    assert field.sitl_params["SIM_ACC1_RND"] > 1.0
    assert field.csia_field_mode and not ideal.csia_field_mode


def test_w3_no_profile_claims_representativeness():
    from csia.simulation.profiles import PROFILES
    assert all(p.representative is False for p in PROFILES.values())


# --------------------------------------------------------------------------
# W-5 the ESC SITL stub -- the regression named in the contract

def test_w5_esc_stub_is_still_blocked():
    c = default_contract()
    assert not c.channels["esc.current"].admissible
    assert not c.channels["esc.rpm"].admissible


def test_w5_esc_stub_cannot_reach_the_power_relation():
    ad = get_adapter("ardupilot")
    ad.ingest({"mavpackettype": "ESC_TELEMETRY_1_TO_4",
               "time_usec": 1_000_000,
               "rpm": [0, 0, 0, 0], "current": [80, 80, 80, 80]})
    s = ad.sample(t_mono=0.1)
    assert "motor_esc" not in {n for n, _t, _c in ad.to_core_samples(s)}


def test_w5_cites_its_source_line():
    body = _doc("docs", "simulation", "CHANNEL_SEMANTICS.yaml")
    assert "AP_ESC_Telem_SITL.cpp:72" in body
    assert "is_telemetry_active" in body


# --------------------------------------------------------------------------
# W-6 response is not attribution

def test_w6_recommendation_and_diagnosis_stay_separate():
    """Ledger A and ledger B disagreed on 1 of 7 families; the log must not
    blur what CSIA DID with what it BLAMED."""
    from csia.deploy.flight_log import FlightLog
    d = FlightLog._disagreement(
        diagnosis={"top": "mag_interference"},
        recommendation={"level": "CAUTION"},
        autopilot={"flight_mode": "LOITER", "failsafe_active": False})
    assert d["state"] == "CSIA_ONLY"
    assert d["csia_top"] == "mag_interference"     # what it blamed
    assert d["csia_level"] == "CAUTION"            # what it did


def test_w6_verdict_document_records_both_ledgers():
    body = _doc("docs", "v1", "V1_FINAL_RESEARCH_VERDICT.md")
    assert "1 of 7" in body and "0 of 7" in body, (
        "the two-ledger result was removed from the verdict document")


# --------------------------------------------------------------------------
# The freeze document itself

def test_all_six_weaknesses_are_still_documented():
    body = _doc("docs", "v1", "V1_FINAL_RESEARCH_VERDICT.md")
    for w in ("W-1", "W-2", "W-3", "W-4", "W-5", "W-6"):
        assert f"### {w}" in body, f"{w} was removed from the verdict document"


def test_verdict_document_makes_no_embedded_claim():
    body = _doc("docs", "v1", "V1_FINAL_RESEARCH_VERDICT.md")
    assert "NOT MEASURED" in body
    assert "estimate" in body.lower()
