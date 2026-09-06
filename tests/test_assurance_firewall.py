"""The assurance firewall: the one rule, and the eleven ways it fails closed.

The firewall exists to answer a question the score cannot: does the evidence
actually support the attribution? These tests are organised around the two
things that make it worth having.

  1. **A large score shall not force support.** The headline case is the
     E1 self-occlusion mechanism itself: the leader is `nominal` with weight
     0.9999 and the GNSS gate has collapsed, so no active discriminator
     separates `nominal` from `gps_fault`. Refusing support there is the whole
     point, and `test_the_brief_example` is that case.

  2. **Nothing produces SUPPORTED_UNIQUE by accident.** Every fail-closed
     condition gets its own case, and a negative control asserts the clean
     record still passes -- without it, a firewall that refused everything
     would satisfy every other test here.
"""

from __future__ import annotations

import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_assurance import (AMBIGUOUS, FAIL_CLOSED_REASONS,   # noqa: E402
                            NON_IDENTIFIABLE, NOT_EVALUABLE,
                            SUPPORTED_UNIQUE, UNKNOWN,
                            SEMANTICS_VERSION, build_certificate, qualify)
from csia_assurance.firewall import SCHEMA                     # noqa: E402
from csia_assurance.witness import (STATUS,                    # noqa: E402
                                    certificate_is_current)


def clean(**over):
    """A record with nothing wrong with it: three hypotheses, both gates open."""
    rec = {
        "schema": SCHEMA,
        "timestamp": 100.0,
        "config_hash": "cfg-1",
        "software_hash": "sw-1",
        "evidence_hash": "ev-1",
        "canonical_sample_present": True,
        "leader": "nominal",
        "signatures": {
            "nominal": [],
            "gps_fault": ["velocity_gps_doppler_0"],
            "imu_bias": ["redundant_imu"],
        },
        "gates": {"velocity_gps_doppler_0": 1.0, "redundant_imu": 1.0},
        "evidence_states": {"velocity_gps_doppler_0": "ACTIVE",
                            "redundant_imu": "ACTIVE"},
        "evidence_sources": {"velocity_gps_doppler_0": "gps",
                             "redundant_imu": "imu1"},
    }
    rec.update(over)
    return rec


# --- the negative control, first ------------------------------------------

def test_a_clean_record_is_supported_unique():
    """Without this, a firewall that refused everything would pass the rest."""
    v = qualify(clean())
    assert v.state == SUPPORTED_UNIQUE
    assert v.supported
    assert not v.competitors_without_witness


# --- the one rule ----------------------------------------------------------

def test_the_brief_example_a_large_score_does_not_force_support():
    """leader=nominal, weight 0.9999, GNSS gate collapsed -> not supported.

    This is the E1 self-occlusion mechanism, seen by the layer that is
    supposed to see it. The firewall never reads the weight at all, which is
    why the weight is in this record: to show it changes nothing.
    """
    rec = clean(leader_weight=0.9999,
                gates={"velocity_gps_doppler_0": 0.0, "redundant_imu": 1.0})
    v = qualify(rec)
    assert v.state == AMBIGUOUS
    assert v.competitors_without_witness == ("gps_fault",)
    assert not v.supported


def test_no_active_evidence_at_all_is_non_identifiable():
    v = qualify(clean(gates={"velocity_gps_doppler_0": 0.0,
                             "redundant_imu": 0.0}))
    assert v.state == NON_IDENTIFIABLE
    assert set(v.competitors_without_witness) == {"gps_fault", "imu_bias"}


def test_a_gate_with_weight_but_stale_evidence_is_not_active():
    """Weight alone is not activity.

    A gate carrying 1.0 whose evidence is STALE must not license support.
    Treating weight as sufficient is the exact shape of the defect this
    programme is about.
    """
    v = qualify(clean(evidence_states={"velocity_gps_doppler_0": "STALE",
                                       "redundant_imu": "ACTIVE"}))
    assert v.state == AMBIGUOUS
    assert v.competitors_without_witness == ("gps_fault",)


@pytest.mark.parametrize("state", ["INACTIVE", "INAPPLICABLE", "STALE",
                                   "ABSENT"])
def test_every_non_active_evidence_state_withdraws_the_witness(state):
    v = qualify(clean(evidence_states={"velocity_gps_doppler_0": state,
                                       "redundant_imu": "ACTIVE"}))
    assert v.state == AMBIGUOUS, f"{state} still licensed support"


def test_no_leader_is_unknown_not_a_failure():
    """UNKNOWN and NOT_EVALUABLE are different answers and both are legal."""
    v = qualify(clean(leader=None))
    assert v.state == UNKNOWN
    assert v.reason == "NO_LEADER_ASSERTED"


def test_a_single_hypothesis_model_is_not_evaluable():
    """A one-hypothesis model trivially identifies its only member, and
    reporting that as supported is how a degenerate configuration reads as a
    healthy one."""
    v = qualify(clean(signatures={"nominal": []}, leader="nominal"))
    assert v.state == NOT_EVALUABLE
    assert v.reason == "SINGLE_HYPOTHESIS_MODEL"


# --- fail-closed: one case per named reason --------------------------------

FAIL_CASES = {
    "UNSUPPORTED_SCHEMA_VERSION": (clean(schema="csia.assurance.input/99"),
                                   None),
    "MISSING_CANONICAL_SAMPLE": (clean(canonical_sample_present=False), None),
    "UNKNOWN_CONFIGURATION": (clean(config_hash=None), None),
    "INVALID_GATE_STATE": (clean(gates={"velocity_gps_doppler_0": 1.5,
                                        "redundant_imu": 1.0}), None),
    "UNKNOWN_EVIDENCE_STATE": (
        clean(evidence_states={"velocity_gps_doppler_0": "PROBABLY_FINE",
                               "redundant_imu": "ACTIVE"}), None),
    "CONFIG_HASH_MISMATCH": (clean(), {"config_hash": "cfg-2",
                                       "software_hash": "sw-1"}),
    "TIMESTAMP_REGRESSION": (clean(timestamp=50.0),
                             {"config_hash": "cfg-1", "software_hash": "sw-1",
                              "timestamp": 90.0}),
    "HYPOTHESIS_SET_CHANGED": (
        clean(), {"config_hash": "cfg-1", "software_hash": "sw-1",
                  "hypothesis_set": ["nominal", "gps_fault"]}),
    "EVIDENCE_TOPOLOGY_CHANGED": (
        clean(), {"config_hash": "cfg-1", "software_hash": "sw-1",
                  "evidence_topology": ["velocity_gps_doppler_0"]}),
    "STALE_SUPPORT_CERTIFICATE": (
        clean(timestamp=500.0), {"config_hash": "cfg-1",
                                 "software_hash": "sw-1",
                                 "timestamp": 100.0, "valid_until": 200.0}),
}


@pytest.mark.parametrize("reason", sorted(FAIL_CASES))
def test_each_fail_closed_condition_yields_not_evaluable(reason):
    record, prior = FAIL_CASES[reason]
    v = qualify(record, prior)
    assert v.state == NOT_EVALUABLE, (
        f"{reason} produced {v.state}, not NOT_EVALUABLE")
    assert v.reason == reason, f"expected reason {reason}, got {v.reason}"
    assert not v.supported


def test_an_internal_exception_is_not_evaluable_and_never_the_leader():
    """The eleventh reason. A record whose signatures explode on iteration.

    The two shapes this forbids each have a name in the module docstring:
    exception -> nominal, and exception -> the previous certificate stands.
    """
    class Exploding(dict):
        def items(self):
            raise RuntimeError("boom")

    rec = clean()
    rec["signatures"] = Exploding(rec["signatures"])
    v = qualify(rec)
    assert v.state == NOT_EVALUABLE
    assert v.reason.startswith("FIREWALL_INTERNAL_EXCEPTION")
    assert "RuntimeError" in v.reason
    assert v.leader is None, "an exception must not carry the leader forward"


def test_every_named_fail_closed_reason_is_demonstrated():
    """The list in the module and the cases here may not drift apart."""
    demonstrated = set(FAIL_CASES) | {"FIREWALL_INTERNAL_EXCEPTION"}
    missing = sorted(set(FAIL_CLOSED_REASONS) - demonstrated)
    assert not missing, f"named but never demonstrated: {missing}"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"),
                                 float("-inf"), -0.5, "1.0", True, None])
def test_a_non_numeric_or_out_of_range_gate_is_invalid(bad):
    """NaN is the case a bare range check misses, so it is tested by name."""
    v = qualify(clean(gates={"velocity_gps_doppler_0": bad,
                             "redundant_imu": 1.0}))
    assert v.state == NOT_EVALUABLE
    assert v.reason == "INVALID_GATE_STATE", (
        f"gate {bad!r} was accepted as {v.state}")


def test_negative_zero_is_a_valid_gate_and_means_inactive():
    """-0.0 is in range and is not > 0, so it is inactive, not invalid.

    Recorded because it is the one signed-zero case where 'reject it' would
    be wrong: the value is perfectly interpretable.
    """
    v = qualify(clean(gates={"velocity_gps_doppler_0": -0.0,
                             "redundant_imu": 1.0}))
    assert v.state == AMBIGUOUS
    assert v.competitors_without_witness == ("gps_fault",)


# --- certificates ----------------------------------------------------------

def test_a_certificate_says_experimental_and_cannot_lose_it():
    cert = build_certificate(qualify(clean()), clean(), SEMANTICS_VERSION)
    assert cert.status == STATUS
    assert "EXPERIMENTAL" in cert.status
    assert "EXPERIMENTAL" in str(cert.to_dict())


def test_a_certificate_is_emitted_even_when_support_is_refused():
    """An incomplete certificate records WHY support was refused.

    Emitting only on success would leave the durable record covering just the
    decisions that went well.
    """
    rec = clean(gates={"velocity_gps_doppler_0": 0.0, "redundant_imu": 1.0})
    cert = build_certificate(qualify(rec), rec, SEMANTICS_VERSION)
    assert cert.complete is False
    assert cert.competitors_without_witness == ("gps_fault",)
    assert [w.competitor_hypothesis for w in cert.witnesses] == ["imu_bias"]


def test_the_certificate_hash_covers_everything_but_itself():
    cert = build_certificate(qualify(clean()), clean(), SEMANTICS_VERSION)
    assert len(cert.certificate_hash) == 64
    other = build_certificate(qualify(clean(evidence_hash="ev-2")),
                              clean(evidence_hash="ev-2"), SEMANTICS_VERSION)
    assert cert.certificate_hash != other.certificate_hash


@pytest.mark.parametrize("mutate,expected", [
    ({"config_hash": "cfg-2"}, "CONFIG_HASH_MISMATCH"),
    ({"software_hash": "sw-2"}, "SOFTWARE_HASH_MISMATCH"),
    ({"signatures": {"nominal": [], "gps_fault": ["velocity_gps_doppler_0"]}},
     "HYPOTHESIS_SET_CHANGED"),
    ({"gates": {"velocity_gps_doppler_0": 1.0}},
     "EVIDENCE_TOPOLOGY_CHANGED"),
    ({"timestamp": 50.0}, "TIMESTAMP_REGRESSION"),
])
def test_a_certificate_goes_stale_for_each_named_reason(mutate, expected):
    rec = clean()
    cert = build_certificate(qualify(rec), rec, SEMANTICS_VERSION)
    ok, why = certificate_is_current(cert, clean(**mutate), SEMANTICS_VERSION)
    assert ok is False and why == expected


def test_a_certificate_expires():
    rec = clean()
    cert = build_certificate(qualify(rec), rec, SEMANTICS_VERSION,
                             validity_window_s=10.0)
    assert certificate_is_current(cert, clean(timestamp=105.0),
                                  SEMANTICS_VERSION)[0] is True
    ok, why = certificate_is_current(cert, clean(timestamp=200.0),
                                     SEMANTICS_VERSION)
    assert ok is False and why == "EXPIRED"


def test_a_semantics_version_change_invalidates_every_certificate():
    rec = clean()
    cert = build_certificate(qualify(rec), rec, SEMANTICS_VERSION)
    ok, why = certificate_is_current(cert, rec, "csia.assurance.semantics/99")
    assert ok is False and why == "SEMANTICS_VERSION_CHANGED"


def test_the_verdict_serialises_to_json_safe_types():
    import json
    json.dumps(qualify(clean()).to_dict())
    json.dumps(build_certificate(qualify(clean()), clean(),
                                 SEMANTICS_VERSION).to_dict())
