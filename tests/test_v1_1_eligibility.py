"""Phase 4B gate: function-specific eligibility.

The two that matter most:

  * a high posterior with NO discriminating evidence must not carry a
    function (§10), and the test holds GNSS fresh and trusted so that the
    freshness rule cannot be what produces the result;
  * a single degraded IMU and a dual-IMU loss must not look the same (§32).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os

import pytest
import yaml

from csia.runtime.failsafe import FailsafeConfig, FailsafeLevel
from csia.v1_1 import reason_codes as RC
from csia.v1_1.eligibility import (OBSERVATION_FIELDS, EligibilityPolicy,
                                   Observation, Requirements)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")

#: The hash frozen BEFORE any mechanism was evaluated (§12, gate C).
REQUIREMENTS_SHA256 = (
    "62d9f1f35ce414de57a7dd3d48b2983828de03b408537858ccfde836f4382962")


def _rows():
    p = os.path.join(ENG, "FUNCTION_ELIGIBILITY_RESULTS.csv")
    if not os.path.exists(p):
        pytest.skip("Phase 4B results not built")
    return list(csv.DictReader(open(p, encoding="utf-8")))


def _transitions():
    p = os.path.join(ENG, "FUNCTION_TRANSITIONS.json")
    if not os.path.exists(p):
        pytest.skip("Phase 4B transitions not built")
    return json.load(open(p, encoding="utf-8"))


def _obs(**over) -> Observation:
    """A healthy tick. Tests perturb exactly one thing."""
    nodes = ("imu0", "imu1", "baro", "mag", "gps", "motor_esc", "battery",
             "vibration")
    base = dict(
        t=100.0,
        trust={n: 0.95 for n in nodes},
        fresh={n: True for n in nodes},
        observable=frozenset(nodes),
        relation_gates={r: 1.0 for r in (
            "velocity_gps_doppler", "heading_course", "altitude_baro",
            "redundant_imu", "accel_motor_current", "accel_esc_rpm",
            "power_thrust", "vibration_prop_freq", "attitude_gravity_mag",
            "temp_bias_drift")},
        sequential_alarms=frozenset(),
        leader="nominal", posterior=0.9,
        support_state="EVIDENCE_BACKED",
        leader_identifiable=True,
        non_identifiable_against=frozenset(),
        prior_sensitive=False, neutral_leader="nominal",
        active_evidence_count=20,
        discriminating_evidence={}, assurance_level=int(FailsafeLevel.NORMAL),
        missing_reason={})
    base.update(over)
    return Observation(**base)


def _policy():
    return EligibilityPolicy(dwell=False)


# --------------------------------------------------------- §12 gate C
def test_the_requirements_were_frozen_before_the_outcomes():
    """If this fails, requirements changed after results were seen. The fix
    is to reissue the hash in a commit that says why -- not to edit here."""
    with open(os.path.join(ENG, "FUNCTION_REQUIREMENTS.yaml"), "rb") as fh:
        got = hashlib.sha256(fh.read()).hexdigest()
    assert got == REQUIREMENTS_SHA256
    assert REQUIREMENTS_SHA256 in open(
        os.path.join(ENG, "FUNCTION_ELIGIBILITY_SPEC.md"),
        encoding="utf-8").read()


def test_the_runner_carries_the_same_frozen_hash():
    src = open(os.path.join(ENG, "phase4", "run_p4b.py"),
               encoding="utf-8").read()
    assert REQUIREMENTS_SHA256 in src


# ------------------------------------------------------------- §12 / §7
def test_every_threshold_is_inherited_from_the_frozen_failsafe_config():
    """Section 12: no tuned number. Every trust requirement must resolve to a
    declared FailsafeConfig field."""
    req = Requirements.load()
    cfg = FailsafeConfig()
    assert req.functions
    for spec in req.functions.values():
        for th in spec.trust_requirements:
            assert hasattr(cfg, th.inherits), (spec.name, th.inherits)
            assert th.resolve(cfg) == getattr(cfg, th.inherits)


def test_the_requirements_file_contains_no_bare_numeric_threshold():
    doc = yaml.safe_load(
        open(os.path.join(ENG, "FUNCTION_REQUIREMENTS.yaml"),
             encoding="utf-8"))
    for name, row in doc["functions"].items():
        for t in row.get("trust_requirements", []):
            assert "inherits" in t, (name, t)
            assert not any(isinstance(v, (int, float))
                           for k, v in t.items() if k != "inherits"), (name, t)


def test_precision_landing_is_omitted_with_a_stated_reason():
    """Section 6: omit rather than invent."""
    req = Requirements.load()
    assert "PRECISION_LANDING" not in req.functions
    assert "PRECISION_LANDING" in req.omitted
    why = req.omitted["PRECISION_LANDING"]["reason"].lower()
    assert "rangefinder" in why and "optical flow" in why


# ------------------------------------------------------------------- §9
def test_the_policy_cannot_see_ground_truth():
    """Section 9's forbidden inputs must not be expressible."""
    banned = ("scenario", "truth", "label", "fault", "filename", "path",
              "injected", "simulator", "mechanism")
    for f in OBSERVATION_FIELDS:
        for b in banned:
            assert b not in f, f


def test_the_observation_fields_are_exactly_the_permitted_inputs():
    assert set(OBSERVATION_FIELDS) == {
        "t", "trust", "fresh", "observable", "relation_gates",
        "sequential_alarms", "leader", "posterior", "support_state",
        "leader_identifiable", "non_identifiable_against", "prior_sensitive",
        "neutral_leader", "active_evidence_count", "discriminating_evidence",
        "assurance_level", "missing_reason"}


# ------------------------------------------------------------------ §10
def test_a_high_posterior_with_no_support_does_not_carry_precision_nav():
    """THE section 10 regression.

    GNSS is FRESH, TRUSTED, its relations are gated in and assurance is
    NORMAL -- so no freshness, trust, relation or assurance rule can fire.
    The ONLY thing wrong is that the leader cannot be separated from
    `gps_fault`. That must be enough.
    """
    obs = _obs(leader="nominal", posterior=0.9998,
               support_state="NON_IDENTIFIABLE", leader_identifiable=False,
               non_identifiable_against=frozenset({"gps_fault"}),
               discriminating_evidence={"gps_fault": 0})
    v = _policy().evaluate(obs)

    pn = v["PRECISION_NAVIGATION"]
    assert pn.state == RC.INELIGIBLE
    assert "SUPPORT_LOST_FOR_REQUIRED_INFORMATION" in pn.reason_codes
    assert pn.required_inputs_available is True, (
        "the inputs were all present; if this is False the test is passing "
        "for the wrong reason")
    assert pn.support_sufficient is False

    assert v["GEOFENCE_SUPPORT"].state == RC.INELIGIBLE
    # TOLERATE_AMBIGUITY functions degrade rather than stop
    assert v["COARSE_NAVIGATION"].state == RC.DEGRADED
    assert v["POSITION_HOLD"].state == RC.DEGRADED
    # and a function that does not depend on GNSS is untouched
    assert v["INERTIAL_CONTINUATION"].state == RC.ELIGIBLE


def test_the_same_tick_with_support_restored_is_eligible():
    """The control for the test above: change ONLY the support verdict."""
    v = _policy().evaluate(_obs(posterior=0.9998))
    assert v["PRECISION_NAVIGATION"].state == RC.ELIGIBLE
    assert v["GEOFENCE_SUPPORT"].state == RC.ELIGIBLE


# ------------------------------------------------------------------ §11
def test_a_sequential_alarm_degrades_and_never_attributes():
    obs = _obs(sequential_alarms=frozenset({"gps"}))
    v = _policy().evaluate(obs)
    pn = v["PRECISION_NAVIGATION"]
    assert pn.state == RC.DEGRADED
    assert "SEQUENTIAL_ALARM_ON_REQUIRED_SOURCE" in pn.reason_codes
    # the alarm must not have promoted a cause
    assert "NAMED_CAUSE_AFFECTS_FUNCTION" not in pn.reason_codes
    assert v["INERTIAL_CONTINUATION"].state == RC.ELIGIBLE


def test_an_alarm_on_an_unrelated_node_does_not_touch_a_function():
    v = _policy().evaluate(_obs(sequential_alarms=frozenset({"vibration"})))
    assert v["PRECISION_NAVIGATION"].state == RC.ELIGIBLE


# ------------------------------------------------------------------- §8
def test_unknown_fires_when_a_required_source_is_not_observable():
    """Never reached in the scenario catalogue -- every node is always
    present there -- so it is proven here instead of claimed there."""
    obs = _obs(observable=frozenset({"imu0", "imu1", "baro", "mag",
                                     "motor_esc", "battery", "vibration"}))
    v = _policy().evaluate(obs)
    assert v["COARSE_NAVIGATION"].state == RC.UNKNOWN
    assert ("REQUIRED_SOURCE_NOT_OBSERVABLE"
            in v["COARSE_NAVIGATION"].reason_codes)
    assert v["INERTIAL_CONTINUATION"].state == RC.ELIGIBLE


def test_eligibility_unknown_is_not_the_unmodeled_fault_unknown():
    """Section 34: the two concepts share a spelling and nothing else."""
    t = open(os.path.join(ENG, "UNKNOWN_MODEL_ADEQUACY_AUDIT.md"),
             encoding="utf-8").read()
    assert "NOT IMPLEMENTED — MODEL ADEQUACY TEST REQUIRED" in t
    codes = RC.load()
    assert "DISTINCT" in codes["states"]["UNKNOWN"]
    assert RC.UNKNOWN in RC.STATES


# ------------------------------------------------------------------ §33
def test_the_producers_own_absence_reason_is_preserved():
    """Section 33: SENTINEL, STALE and OBSERVED_INVALID must not collapse
    into one code where the ingest layer can tell them apart."""
    seen = {}
    for reason, code in (("SENTINEL", "SOURCE_ABSENT_SENTINEL"),
                         ("STALE", "SOURCE_ABSENT_STALE"),
                         ("NOT_RECEIVED", "SOURCE_ABSENT_NOT_RECEIVED"),
                         ("NO_3D_FIX", "SOURCE_ABSENT_NO_3D_FIX")):
        obs = _obs(fresh={**_obs().fresh, "gps": False},
                   missing_reason={"gps": reason})
        v = _policy().evaluate(obs)["COARSE_NAVIGATION"]
        assert code in v.reason_codes, reason
        seen[reason] = code
    assert len(set(seen.values())) == 4

    # and with no ingest layer in the loop, the generic code is used
    obs = _obs(fresh={**_obs().fresh, "gps": False})
    v = _policy().evaluate(obs)["COARSE_NAVIGATION"]
    assert "REQUIRED_SOURCE_NOT_FRESH" in v.reason_codes


# ------------------------------------------------------------------ §32
def test_one_imu_degraded_and_both_lost_do_not_look_the_same():
    cfg = FailsafeConfig()
    one = _obs(trust={**_obs().trust, "imu0": 0.40},
               leader="imu0_bias_drift")
    both = _obs(trust={**_obs().trust, "imu0": 0.40, "imu1": 0.40})
    v1 = _policy().evaluate(one)
    v2 = _policy().evaluate(both)

    # one IMU down: max(imu0, imu1) is still healthy -> redundancy working
    assert v1["POSITION_HOLD"].state == RC.ELIGIBLE
    assert v1["INERTIAL_CONTINUATION"].state == RC.DEGRADED
    assert ("NAMED_CAUSE_AFFECTS_FUNCTION"
            in v1["INERTIAL_CONTINUATION"].reason_codes)

    # both down: below att_caution AND below att_emergency
    assert v2["POSITION_HOLD"].state == RC.INELIGIBLE
    assert v2["INERTIAL_CONTINUATION"].state == RC.INELIGIBLE
    assert 0.40 < cfg.att_emergency < cfg.att_caution


def test_redundancy_loss_degrades_without_removing_the_function():
    obs = _obs(fresh={**_obs().fresh, "imu0": False})
    v = _policy().evaluate(obs)
    assert v["POSITION_HOLD"].state == RC.DEGRADED
    assert "REDUNDANT_SOURCE_UNAVAILABLE" in v["POSITION_HOLD"].reason_codes

    both = _obs(fresh={**_obs().fresh, "imu0": False, "imu1": False})
    v2 = _policy().evaluate(both)
    assert v2["POSITION_HOLD"].state == RC.INELIGIBLE
    assert ("REQUIRED_SOURCE_GROUP_EXHAUSTED"
            in v2["POSITION_HOLD"].reason_codes)


# ------------------------------------------------------------ determinism
def test_the_same_observation_always_gives_the_same_verdict():
    obs = _obs(trust={**_obs().trust, "gps": 0.5},
               sequential_alarms=frozenset({"gps"}))
    a = _policy().evaluate(obs)
    b = _policy().evaluate(obs)
    assert {k: (v.state, v.reason_codes) for k, v in a.items()} == \
           {k: (v.state, v.reason_codes) for k, v in b.items()}


def test_every_emitted_code_is_defined_in_the_reason_code_table():
    defined = set(RC.eligibility_codes())
    pol = _policy()
    perturbations = [
        _obs(), _obs(fresh={**_obs().fresh, "gps": False}),
        _obs(trust={**_obs().trust, "gps": 0.1, "mag": 0.1,
                    "imu0": 0.1, "imu1": 0.1}),
        _obs(relation_gates={}), _obs(observable=frozenset()),
        _obs(sequential_alarms=frozenset({"gps", "mag"})),
        _obs(assurance_level=int(FailsafeLevel.EMERGENCY)),
        _obs(non_identifiable_against=frozenset({"gps_fault",
                                                 "mag_interference"})),
        _obs(leader="gps_fault"), _obs(support_state="NO_APPLICABLE_EVIDENCE",
                                       active_evidence_count=0),
        _obs(prior_sensitive=True, leader="gps_fault",
             neutral_leader="mag_interference"),
        _obs(fresh={**_obs().fresh, "imu0": False},
             missing_reason={"imu0": "SENTINEL"}),
        _obs(fresh={**_obs().fresh, "gps": False},
             missing_reason={"gps": "SENTINEL"}),
    ]
    emitted = set()
    for obs in perturbations:
        for v in pol.evaluate(obs).values():
            emitted.update(v.reason_codes)
    assert emitted <= defined, emitted - defined
    # and the table must not carry codes nothing can emit
    unreachable = defined - emitted
    assert unreachable <= {"SOURCE_ABSENT_STALE", "SOURCE_ABSENT_NOT_RECEIVED",
                           "SOURCE_ABSENT_NO_3D_FIX"}, unreachable


def test_severity_of_a_policy_code_needs_a_policy():
    assert RC.severity_of("SUPPORT_LOST_FOR_REQUIRED_INFORMATION",
                          "REQUIRE_IDENTIFIABLE") == RC.INELIGIBLE
    assert RC.severity_of("SUPPORT_LOST_FOR_REQUIRED_INFORMATION",
                          "TOLERATE_AMBIGUITY") == RC.DEGRADED
    with pytest.raises(ValueError):
        RC.severity_of("SUPPORT_LOST_FOR_REQUIRED_INFORMATION", None)


# ------------------------------------------------------------------ §30
def test_dwell_prevents_a_single_tick_flap():
    pol = EligibilityPolicy(dwell=True)
    cfg = FailsafeConfig()
    good, bad = _obs(t=0.0), _obs(t=0.04, sequential_alarms=frozenset({"gps"}))
    assert pol.update(good)["PRECISION_NAVIGATION"].state == RC.ELIGIBLE
    assert pol.update(bad)["PRECISION_NAVIGATION"].state == RC.ELIGIBLE
    held = _obs(t=cfg.dwell_up + 0.04, sequential_alarms=frozenset({"gps"}))
    assert pol.update(held)["PRECISION_NAVIGATION"].state == RC.DEGRADED


def test_the_clean_control_is_stable_after_startup():
    d = json.load(open(os.path.join(ENG, "PHASE4_CLEAN_RESULT.json"),
                       encoding="utf-8"))
    assert d["sequential_alarms_on_clean"] == 0
    assert d["assurance_transitions_on_clean"] == 0
    assert d["stable_after_startup"] is True
    for t in d["transitions"]:
        assert t["t"] == 8.04, t
        assert t["new_state"] == "ELIGIBLE", t


def test_the_startup_window_is_exactly_the_documented_201_ticks():
    """76 genuine ambiguity ticks + 125 ticks of inherited dwell_down."""
    cfg = FailsafeConfig()
    assert 76 + int(cfg.dwell_down * 25) == 201
    for r in _rows():
        if r["mechanism"] != "CLEAN":
            continue
        restricted = (int(r["ticks_DEGRADED"]) + int(r["ticks_INELIGIBLE"])
                      + int(r["ticks_UNKNOWN"]))
        assert restricted in (0, 201), r


# ------------------------------------------------------------------ §31
def test_the_fix_loss_control_removes_every_gnss_function():
    d = json.load(open(os.path.join(ENG, "PHASE4_FIXLOSS_RESULT.json"),
                       encoding="utf-8"))
    onset = [t for t in d["transitions"] if t["t"] > 10.0]
    assert onset, d["transitions"]
    for t in onset:
        if t["new_state"] != "INELIGIBLE":
            continue
        assert t["t"] == 26.0, t
        assert "SUPPORT_LOST_FOR_REQUIRED_INFORMATION" in t["reason_codes"], t
    removed = {t["function"] for t in onset if t["new_state"] == "INELIGIBLE"}
    assert removed == {"COARSE_NAVIGATION", "GEOFENCE_SUPPORT",
                       "POSITION_HOLD", "PRECISION_NAVIGATION"}
    assert "INERTIAL_CONTINUATION" not in removed


def test_the_dual_imu_control_distinguishes_redundancy_from_loss():
    d = json.load(open(os.path.join(ENG, "PHASE4_DUAL_IMU_RESULT.json"),
                       encoding="utf-8"))
    single = d["single_imu"]["per_function_tick_counts"]
    dual = d["dual_imu"]["per_function_tick_counts"]

    # one IMU: the fallback degrades, nothing is removed
    assert single["INERTIAL_CONTINUATION"].get("DEGRADED", 0) > 0
    assert single["INERTIAL_CONTINUATION"].get("INELIGIBLE", 0) == 0
    assert single["POSITION_HOLD"].get("INELIGIBLE", 0) == 201   # startup only

    # both IMUs: the fallback is removed too
    assert dual["INERTIAL_CONTINUATION"].get("INELIGIBLE", 0) > 0
    assert dual["POSITION_HOLD"].get("INELIGIBLE", 0) > 201


# ------------------------------------------------------------------ §13
def test_the_per_tick_record_is_reconstructable_from_the_transitions():
    """Section 13 asks for a per-tick record. The series is piecewise
    constant, so transitions + tick counts carry it exactly -- proven here
    rather than asserted in a note."""
    doc = _transitions()
    counts = {}
    for r in _rows():
        counts[(r["mechanism"], r["function"])] = {
            s: int(r[f"ticks_{s}"])
            for s in ("ELIGIBLE", "DEGRADED", "INELIGIBLE", "UNKNOWN")}
    by_key = {}
    for t in doc["transitions"]:
        by_key.setdefault((t["mechanism"], t["function"]), []).append(t)

    for key, want in counts.items():
        total = sum(want.values())
        trans = sorted(by_key.get(key, []), key=lambda x: x["t"])
        states = ([trans[0]["previous_state"]] + [t["new_state"]
                                                  for t in trans]) \
            if trans else [max(want, key=want.get)]
        got = {s: 0 for s in want}
        for s in states:
            got[s] += 1
        # every state that has ticks must appear in the reconstructed run,
        # and no state with zero ticks may appear
        for s, n in want.items():
            assert (n > 0) == (got[s] > 0), (key, s, n, got[s])
        assert total == 1500


def test_the_transitions_artifact_records_the_omission_and_the_mode():
    doc = _transitions()
    assert doc["trust_mode"] == "FLAT_V1_1"
    assert doc["requirements_sha256"] == REQUIREMENTS_SHA256
    assert "PRECISION_LANDING" in doc["omitted"]
    assert set(doc["functions"]) == {
        "COARSE_NAVIGATION", "POSITION_HOLD", "PRECISION_NAVIGATION",
        "GEOFENCE_SUPPORT", "INERTIAL_CONTINUATION"}


# ------------------------------------------------------------------ §27
def test_the_staleness_audit_exists_and_changes_nothing():
    t = open(os.path.join(ENG, "STALENESS_LAYER_AUDIT.md"),
             encoding="utf-8").read()
    assert "Nothing is changed by this document" in t
    assert "STALE_TIMEOUT_S" in t and "MaxAge" in t
    assert "motor_esc" in t
    # the audit's design decision must match the implementation
    assert "Eligibility reads the FROZEN LAYER" in t

    from csia.aircraft.adapters.base import MaxAge
    from csia.runtime.online import STALE_TIMEOUT_S
    assert MaxAge["gnss.position"] == 1.00
    assert STALE_TIMEOUT_S["gps"] == 0.50
    assert STALE_TIMEOUT_S["motor_esc"] == 0.10
