"""The capability, product, planner, recovery and compiler semantics.

Each test pins a rule that a later convenience change would erode, and the
comment says which erosion it prevents.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_mission.capability import (                        # noqa: E402
    CapabilityContract, CapabilityReport, ContractError, DEGRADED_SUPPORTED,
    EvidenceStatus, NOT_EVALUABLE, NOT_SUPPORTED, REASON_CODES, SUPPORTED,
    UNKNOWN, build_capability_certificate, evaluate_capabilities)
from csia_mission.forge_seed import (CompileError,           # noqa: E402
                                     check_compiled, compile_contracts)
from csia_mission.planner import (                           # noqa: E402
    AUTHORIZED, DeterministicTestPlanner, MissionAction, MissionBranch,
    REJECTED, attempt_override, authorize)
from csia_mission.product import (                           # noqa: E402
    MissionProductContract, PRODUCT_DEGRADED, PRODUCT_NOT_EVALUABLE,
    PRODUCT_NOT_SUPPORTED, PRODUCT_SUPPORTED, ProductContractError,
    QualityRequirement, certificate_still_valid, evaluate_product)
from csia_mission.recovery import (RecoveryError,            # noqa: E402
                                   RecoveryState, step)
from csia_mission.xr1_contracts import (CAPABILITIES,        # noqa: E402
                                        EVIDENCE, PRODUCTS,
                                        vehicle_profile)

RESULTS = os.path.join(ROOT, "research", "mission", "results")


def _all_evidence(now=10.0, killed=(), expires_in=100.0):
    return {e: EvidenceStatus(e, e not in set(killed),
                              expires_at=now + expires_in)
            for e in EVIDENCE}


def _healthy_caps(now=10.0, killed=()):
    return evaluate_capabilities(
        CAPABILITIES, _all_evidence(now, killed), now,
        compute={"mapping": SUPPORTED, "logging": SUPPORTED},
        actuators={"elevon_left": True, "elevon_right": True})


# ----------------------------------------------------------------- capability

def test_unknown_is_never_promoted_to_supported():
    """THE RULE most likely to be eroded by a convenience change."""
    c = CapabilityContract("c", requires_all=("e",))
    ev = {"e": EvidenceStatus("e", None)}          # None means UNKNOWN
    rep = evaluate_capabilities([c], ev, now=1.0)["c"]
    assert rep.state == UNKNOWN
    assert not rep.usable
    assert "EVIDENCE_UNKNOWN" in rep.reason_codes


def test_absent_evidence_is_unknown_not_false():
    """Absence is not refutation. A missing reading is UNKNOWN."""
    c = CapabilityContract("c", requires_all=("e",))
    rep = evaluate_capabilities([c], {}, now=1.0)["c"]
    assert rep.state == UNKNOWN
    assert "EVIDENCE_ABSENT" in rep.reason_codes


def test_an_absent_compute_domain_is_unknown_not_available():
    """The erosion this prevents: 'nobody reported a problem, so it's fine'."""
    c = CapabilityContract("c", requires_compute=("mapping",))
    assert evaluate_capabilities([c], {}, now=1.0,
                                 compute={})["c"].state == UNKNOWN
    assert evaluate_capabilities([c], {}, now=1.0, compute={
        "mapping": NOT_SUPPORTED})["c"].state == NOT_SUPPORTED
    assert evaluate_capabilities([c], {}, now=1.0, compute={
        "mapping": SUPPORTED})["c"].state == SUPPORTED


def test_expiry_beats_support():
    c = CapabilityContract("c", requires_all=("e",))
    ev = {"e": EvidenceStatus("e", True, expires_at=5.0)}
    assert evaluate_capabilities([c], ev, now=4.9)["c"].state == SUPPORTED
    late = evaluate_capabilities([c], ev, now=5.1)["c"]
    assert late.state == NOT_SUPPORTED
    assert "EVIDENCE_EXPIRED" in late.reason_codes
    assert "e" in late.expired


def test_a_non_primary_alternative_path_is_reported_as_degraded():
    c = CapabilityContract("c", requires_one_of=(("primary", "backup"),))
    ev = {"primary": EvidenceStatus("primary", False),
          "backup": EvidenceStatus("backup", True)}
    rep = evaluate_capabilities([c], ev, now=1.0)["c"]
    assert rep.state == DEGRADED_SUPPORTED
    assert rep.alternative_path_selected == "backup"
    assert "ALTERNATIVE_PATH_IN_USE" in rep.reason_codes


def test_a_capability_is_never_better_than_its_worst_dependency():
    caps = [CapabilityContract("low", requires_all=("e",)),
            CapabilityContract("high", requires_capabilities=("low",))]
    ev = {"e": EvidenceStatus("e", False)}
    out = evaluate_capabilities(caps, ev, now=1.0)
    assert out["low"].state == NOT_SUPPORTED
    assert out["high"].state == NOT_SUPPORTED


def test_a_dependency_cycle_fails_closed():
    caps = [CapabilityContract("a", requires_capabilities=("b",)),
            CapabilityContract("b", requires_capabilities=("a",))]
    out = evaluate_capabilities(caps, {}, now=1.0)
    for cid in ("a", "b"):
        assert out[cid].state == NOT_EVALUABLE
        assert "DEPENDENCY_CYCLE" in out[cid].reason_codes


def test_evaluation_is_order_independent():
    ev = _all_evidence()
    forward = evaluate_capabilities(CAPABILITIES, ev, 10.0)
    backward = evaluate_capabilities(list(reversed(CAPABILITIES)), ev, 10.0)
    assert {k: v.state for k, v in forward.items()} == \
           {k: v.state for k, v in backward.items()}


def test_a_contract_contradicting_its_own_independence_is_rejected():
    c = CapabilityContract("c", requires_all=("gnss",),
                           does_not_require=("gnss",))
    with pytest.raises(ContractError, match="does_not_require"):
        c.validate()


def test_restore_on_presence_is_refused_as_a_recovery_policy():
    """The policy name is ACCEPTED so it fails loudly, not silently."""
    c = CapabilityContract("c", recovery_policy="IMMEDIATE_ON_PRESENCE")
    with pytest.raises(ContractError, match="Presence of a sensor"):
        c.validate()


def test_every_reason_code_emitted_is_in_the_declared_vocabulary():
    seen = set()
    for killed in ([], ["gnss.position.supported"], list(EVIDENCE)):
        for rep in _healthy_caps(killed=killed).values():
            seen |= set(rep.reason_codes)
    unknown = seen - set(REASON_CODES)
    assert not unknown, f"undeclared reason codes emitted: {sorted(unknown)}"


def test_there_is_no_ranking_parameter():
    """Structural. A ranking may inform diagnosis; it may not certify."""
    import inspect
    for fn in (evaluate_capabilities, evaluate_product):
        params = {p.lower() for p in inspect.signature(fn).parameters}
        for banned in ("ranking", "score", "posterior", "likelihood",
                       "confidence"):
            assert banned not in params, (
                f"{fn.__name__} now accepts {banned!r}. A ranking may inform "
                f"the diagnosis inside the frozen core; it may never "
                f"establish that a capability or product is supported.")


# -------------------------------------------------------------- certificates

def test_a_certificate_with_no_expiry_is_not_valid_forever():
    rep = CapabilityReport("c", SUPPORTED, ("ALL_REQUIREMENTS_MET",))
    cert = build_capability_certificate(
        rep, {}, issued_at=100.0, vehicle_configuration_hash="v",
        payload_configuration_hash="p", software_hashes={}, expires_at=None)
    assert cert.valid_at(100.0)
    assert not cert.valid_at(100.001), (
        "'previous certificate remains valid forever' is a forbidden "
        "transition; a certificate with no declared lifetime cannot be "
        "asserted at a later time")


def test_a_certificate_is_emitted_for_a_refusal_too():
    rep = CapabilityReport("c", NOT_SUPPORTED, ("EVIDENCE_NOT_SUPPORTED",))
    cert = build_capability_certificate(
        rep, {}, issued_at=1.0, vehicle_configuration_hash="v",
        payload_configuration_hash="p", software_hashes={})
    assert cert.support_status == NOT_SUPPORTED
    assert cert.reason_codes == ("EVIDENCE_NOT_SUPPORTED",)
    assert cert.certificate_hash


def test_certificates_never_claim_to_be_certified():
    rep = CapabilityReport("c", SUPPORTED, ("ALL_REQUIREMENTS_MET",))
    cert = build_capability_certificate(
        rep, {}, 1.0, "v", "p", {})
    assert cert.status.startswith("EXPERIMENTAL_")
    blob = json.dumps(cert.to_dict()).lower()
    for overclaim in ("certification-grade", "airworthy", "certified safe"):
        assert overclaim not in blob


def test_a_configuration_change_invalidates_a_product_certificate():
    class _C:
        vehicle_configuration_hash = "A"
        evidence_manifest_hash = "E"
    assert certificate_still_valid(_C(), "A", "E")[0] is True
    assert certificate_still_valid(_C(), "B", "E")[0] is False
    assert certificate_still_valid(_C(), "A", "F")[0] is False


# ------------------------------------------------------------------- product

def test_losing_gnss_removes_only_the_absolute_qualification():
    """THE ROW THE WHOLE ARCHITECTURE EXISTS TO PRODUCE."""
    now = 10.0
    killed = ("gnss.position.supported", "gnss.velocity.supported")
    caps = _healthy_caps(now, killed)
    res = evaluate_product(
        next(p for p in PRODUCTS if p.product_id == "bridge_rgb_inspection"),
        _all_evidence(now, killed), caps, now)
    assert res.state == PRODUCT_DEGRADED
    assert res.property_states["imagery_quality"] == SUPPORTED
    assert res.property_states["relative_geometry"] == SUPPORTED
    assert res.property_states["absolute_geolocation"] == NOT_SUPPORTED
    assert "visual_damage_assessment" in res.permitted_uses
    assert "survey_grade_absolute_measurement" in res.prohibited_uses


def test_losing_rgb_does_not_invalidate_thermal():
    now = 10.0
    killed = ("camera.rgb.available", "camera.rgb.calibration_valid")
    caps = _healthy_caps(now, killed)
    ev = _all_evidence(now, killed)
    thermal = evaluate_product(
        next(p for p in PRODUCTS
             if p.product_id == "bridge_thermal_inspection"), ev, caps, now)
    assert thermal.state == PRODUCT_SUPPORTED


def test_losing_comms_invalidates_nothing():
    now = 10.0
    killed = ("comms.telemetry_link.supported",)
    caps = _healthy_caps(now, killed)
    ev = _all_evidence(now, killed)
    for p in PRODUCTS:
        assert evaluate_product(p, ev, caps, now).state == PRODUCT_SUPPORTED


def test_raw_evidence_survives_every_single_evidence_loss():
    """Raw evidence is archived before reduction. A product layer that could
    invalidate the archive would contradict the programme's own rule."""
    raw = next(p for p in PRODUCTS if p.product_id == "raw_evidence_package")
    now = 10.0
    for killed in ([e] for e in EVIDENCE):
        if killed == ["timebase.supported"]:
            continue        # the one dependency it declares
        caps = _healthy_caps(now, killed)
        res = evaluate_product(raw, _all_evidence(now, killed), caps, now)
        assert res.state == PRODUCT_SUPPORTED, (killed, res.state)


def test_a_prohibited_use_wins_over_a_permitted_one():
    contract = MissionProductContract(
        "p", "probe",
        qualities=(
            QualityRequirement("imagery_quality", requires_all=("a",),
                               permits=("shared_use",),
                               prohibits_without=("x",)),
            QualityRequirement("relative_geometry", requires_all=("b",),
                               permits=("y",),
                               prohibits_without=("shared_use",)),
        ))
    ev = {"a": EvidenceStatus("a", True), "b": EvidenceStatus("b", False)}
    res = evaluate_product(contract, ev, {}, now=1.0)
    assert "shared_use" in res.prohibited_uses
    assert "shared_use" not in res.permitted_uses


def test_all_unknown_properties_give_not_evaluable_not_not_supported():
    """'We cannot tell' is a different answer from 'we can tell it is
    unusable', and four product states exist to keep them apart."""
    contract = MissionProductContract(
        "p", "probe",
        qualities=(QualityRequirement("imagery_quality",
                                      requires_capabilities=("c",),
                                      permits=("u",),
                                      prohibits_without=("u",)),))
    caps = {"c": CapabilityReport("c", UNKNOWN, ("EVIDENCE_UNKNOWN",))}
    assert evaluate_product(contract, {}, caps, 1.0).state == \
        PRODUCT_NOT_EVALUABLE
    caps = {"c": CapabilityReport("c", NOT_SUPPORTED, ())}
    assert evaluate_product(contract, {}, caps, 1.0).state == \
        PRODUCT_NOT_SUPPORTED


def test_a_product_with_no_qualities_is_rejected():
    with pytest.raises(ProductContractError, match="no quality properties"):
        MissionProductContract("p", "t", qualities=()).validate()


def test_an_undeclared_quality_name_is_rejected():
    with pytest.raises(ProductContractError, match="not a declared quality"):
        QualityRequirement("made_up_property").validate()


# ------------------------------------------------------------------- planner

def test_the_gate_rejects_unknown_as_well_as_not_supported():
    action = MissionAction("a", requires_capabilities=("c",))
    for state, expect in ((SUPPORTED, AUTHORIZED),
                          (DEGRADED_SUPPORTED, AUTHORIZED),
                          (NOT_SUPPORTED, REJECTED),
                          (UNKNOWN, REJECTED),
                          (NOT_EVALUABLE, REJECTED)):
        caps = {"c": CapabilityReport("c", state, ())}
        assert authorize(action, caps).decision == expect, state


def test_the_gate_has_no_override_parameter():
    import inspect
    params = set(inspect.signature(authorize).parameters)
    for banned in ("override", "force", "advisory", "allow_unsupported"):
        assert banned not in params
    with pytest.raises(PermissionError, match="no override"):
        attempt_override()


def test_the_planner_falls_back_rather_than_proceeding_partially():
    actions = (MissionAction("big", requires_capabilities=("hard",)),
               MissionAction("small", requires_capabilities=("easy",)))
    branches = (MissionBranch("ambitious", ("big",), priority=10),
                MissionBranch("fallback", ("small",), priority=5))
    caps = {"hard": CapabilityReport("hard", NOT_SUPPORTED, ()),
            "easy": CapabilityReport("easy", SUPPORTED, ())}
    assert DeterministicTestPlanner(branches, actions).choose(
        caps)["chosen"] == "fallback"

    caps["easy"] = CapabilityReport("easy", UNKNOWN, ())
    out = DeterministicTestPlanner(branches, actions).choose(caps)
    assert out["chosen"] is None
    assert "NO BRANCH AUTHORIZED" in out["note"]


# ------------------------------------------------------------------ recovery

def test_presence_alone_does_not_restore_a_capability():
    m = RecoveryState("c", required_fresh_observations=3, min_dwell_s=1.0)
    m.observe(NOT_SUPPORTED, 0.0)
    assert m.phase == "RESTRICTED"
    m.observe(SUPPORTED, 0.1)
    assert m.phase == "REMEASURING"
    assert m.holds_capability, "one observation must not restore"


def test_recovery_requires_both_a_count_and_a_dwell():
    m = RecoveryState("c", required_fresh_observations=3, min_dwell_s=5.0)
    m.observe(NOT_SUPPORTED, 0.0)
    for t in (0.1, 0.2, 0.3, 0.4):
        m.observe(SUPPORTED, t)
    assert m.phase == "REMEASURING", "count met, dwell not met"
    m.observe(SUPPORTED, 6.0)
    assert m.phase == "RECERTIFIED"


def test_an_unknown_observation_neither_recovers_nor_loses():
    m = RecoveryState("c")
    m.observe(NOT_SUPPORTED, 0.0)
    m.observe(SUPPORTED, 1.0)
    before = m.phase
    out = m.observe(UNKNOWN, 2.0)
    assert m.phase == before and not out["changed"]
    assert m.consecutive_supported == 0


def test_there_is_no_direct_edge_to_recertified():
    m = RecoveryState("c")
    m.observe(NOT_SUPPORTED, 0.0)
    assert m.phase == "RESTRICTED"
    with pytest.raises(RecoveryError, match="not a permitted transition"):
        m._to("RECERTIFIED", 1.0, "shortcut")


def test_the_recovery_step_helper_does_not_deadlock():
    """MX-002. Feeding the machine its own held output stuck it in
    RESTRICTED forever."""
    caps = [CapabilityContract("c", requires_all=("e",))]
    machines = {"c": RecoveryState("c", required_fresh_observations=2,
                                   min_dwell_s=0.5)}
    step(caps, {"e": EvidenceStatus("e", False)}, 0.0, machines)
    assert machines["c"].phase == "RESTRICTED"

    ev = {"e": EvidenceStatus("e", True)}
    for t in (0.5, 1.0, 1.5, 2.0):
        out = step(caps, ev, t, machines)
    assert machines["c"].phase == "NOMINAL", machines["c"].to_dict()
    assert out["published"]["c"].state == SUPPORTED


def test_the_hold_is_unknown_and_therefore_does_not_authorize():
    """MX-001. The hold was DEGRADED_SUPPORTED, which authorizes, so it
    changed the label and nothing downstream."""
    caps = [CapabilityContract("c", requires_all=("e",))]
    ev = {"e": EvidenceStatus("e", True)}
    held = evaluate_capabilities(caps, ev, 1.0, recertifying=("c",))["c"]
    assert held.state == UNKNOWN
    assert not held.usable
    assert "AWAITING_RECERTIFICATION" in held.reason_codes
    action = MissionAction("a", requires_capabilities=("c",))
    assert authorize(action, {"c": held}).decision == REJECTED


# --------------------------------------------------------------- forge-seed

def test_the_compiler_is_deterministic():
    hashes = {compile_contracts(CAPABILITIES, PRODUCTS,
                                vehicle_profile()).output_hash
              for _ in range(5)}
    assert len(hashes) == 1


def test_the_compiler_output_does_not_depend_on_input_order():
    a = compile_contracts(CAPABILITIES, PRODUCTS, vehicle_profile())
    b = compile_contracts(list(reversed(CAPABILITIES)),
                          list(reversed(PRODUCTS)), vehicle_profile())
    assert a.output_hash == b.output_hash


def test_the_independent_checker_agrees_with_the_compiler():
    tables = compile_contracts(CAPABILITIES, PRODUCTS, vehicle_profile())
    check = check_compiled(tables, CAPABILITIES, PRODUCTS)
    assert check["agrees"], check["problems"][:3]
    assert "closure by repeated expansion" in check["method"]


def test_a_cycle_is_a_compile_error():
    caps = [CapabilityContract("a", requires_capabilities=("b",)),
            CapabilityContract("b", requires_capabilities=("a",))]
    with pytest.raises(CompileError, match="dependency cycle"):
        compile_contracts(caps, [], {})


def test_an_unprovided_dependency_is_a_compile_error():
    caps = [CapabilityContract("a", requires_all=("nobody_provides_this",))]
    with pytest.raises(CompileError, match="no declared provider"):
        compile_contracts(caps, [], {"provides_evidence": ["something_else"]})


def test_an_undeclared_subordinate_capability_is_a_compile_error():
    caps = [CapabilityContract("a", requires_capabilities=("ghost",))]
    with pytest.raises(CompileError, match="requires capability"):
        compile_contracts(caps, [], {})


# ------------------------------------------------------------------ artifacts

def _load(name):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not generated")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_the_benchmark_matched_every_declared_expectation():
    doc = _load("DISASTER_CORRIDOR.json")
    assert doc["verdict"] == "ALL_TRANSITIONS_AS_EXPECTED", \
        doc["scenarios_mismatched"]
    assert doc["metrics"]["false_product_certification_count"] == 0
    assert doc["provenance"]["all_intact"] is True


def test_the_benchmark_records_how_its_expectations_were_derived():
    doc = _load("DISASTER_CORRIDOR.json")
    assert "NEVER probed" in doc["how_expectations_were_derived"]
    assert doc["expectations_corrected_after_the_run"], (
        "the record of the one expectation corrected after the run has been "
        "removed; that record is the thing that makes the rest credible")


def test_recovery_latency_is_not_zero():
    """A latency near zero is the signature of restoring on presence."""
    doc = _load("DISASTER_CORRIDOR.json")
    lat = doc["metrics"]["capability_recovery_latency_s"]
    assert lat, "no recovery latency recorded"
    for cid, seconds in lat.items():
        assert seconds > 0.0, (
            f"{cid} recovered in {seconds}s. A recovery latency of zero means "
            f"the capability was restored on presence rather than on "
            f"re-established evidence -- BAD_PRODUCT_05.")


def test_no_bounded_property_passes_vacuously():
    """MX-004. Zero cases reported NO_COUNTEREXAMPLE."""
    doc = _load("MISSION_BOUNDED_VERIFICATION.json")
    assert doc["summary"]["vacuous_zero_cases"] == 0
    for p in doc["properties"]:
        assert p["cases_checked"] > 0, p["property"]
        assert p["verdict"] != "VACUOUS_NO_CASES_CHECKED", p["property"]


def test_bounded_verification_never_claims_a_theorem():
    doc = _load("MISSION_BOUNDED_VERIFICATION.json")
    assert doc["what_unsat_licenses"] == (
        "No counterexample exists within the verified bounded domain.")
    assert "NO NOVELTY IS CLAIMED" in doc["what_unsat_does_not_license"]
    assert doc["verdict"] == "NO_COUNTEREXAMPLE_IN_ANY_PROPERTY"


def test_the_conformance_suite_judges_every_reference_correctly():
    doc = _load("MISSION_CONFORMANCE.json")
    assert doc["suite_correct"], doc["misjudged"]
    assert len(doc["rows"]) == 9


def test_the_conformance_suite_does_not_judge_on_names():
    """The control is a CORRECT implementation named like a bad one."""
    doc = _load("MISSION_CONFORMANCE.json")
    control = [r for r in doc["rows"]
               if r["label"] == "BAD_PRODUCT_08_actually_fine"]
    assert control, "the name-trap control is gone"
    assert control[0]["rejected"] is False, (
        "a correct implementation was rejected because of its NAME; the "
        "suite is checking labels rather than behaviour")


def test_the_reconfiguration_analysis_discriminates():
    """It must flag self-occlusion and must NOT flag every reduction."""
    doc = _load("RECONFIGURATION_ANALYSIS.json")
    rows = {(r["transition"], r["intended_capability"]): r
            for r in doc["rows"]}
    stow_rel = rows[("FULL_PAYLOAD -> CAMERA_STOWED", "relative_navigation")]
    stow_map = rows[("FULL_PAYLOAD -> CAMERA_STOWED", "local_mapping")]
    assert stow_rel["self_occluding"] is False, (
        "the reference-IMU path survives the stow, so relative navigation is "
        "not self-occluded; flagging it would make the term mean nothing")
    assert stow_map["self_occluding"] is True, (
        "MX-005: local_mapping's requirements are entirely subordinate "
        "capabilities, and satisfiability must follow the chain")
    assert doc["novelty"] == "NOVELTY_NOT_ESTABLISHED"
