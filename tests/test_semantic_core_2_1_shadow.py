"""CSIA Semantic Core 2.1 shadow validation: permanent regression tests.

Package: research/csia_semantic_core_2_1_shadow/. What is pinned here:

- the shadow runner has no control authority: it returns the frozen engine's
  own output, and a failure inside the shadow cannot reach it;
- the versioned successor profile r1 is what the study accepted, by digest;
- the two wrong-cause UNIQUE verdicts 2.1 withholds (MS_B5, MS_TS_B5) stay
  withheld under the successor profile and under every candidate
  declaration, including the rejected ones (Part 9);
- the IMU pacing-loss counterfactual that rejects R5, R5a and R5b (G-2);
- G-1: successor r1 restores POSITION_UNAVAILABLE on COARSE_NAVIGATION;
- one failing profile per static-validator rule (Part 40);
- the selected predicate-fault policy B withholds the fault-created
  SUPPORTED that policy A (2.1 today) leaves standing (Part 48);
- the transition design is the frozen one;
- the package's documents exist and keep the repository's wording rules;
- the failure ledger is untouched.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import replace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "research", "csia_semantic_core_2_1_shadow")
AUDIT = os.path.join(ROOT, "research", "csia_semantic_correctness")
for _p in (ROOT, AUDIT, PKG):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import semantic_probe as P  # noqa: E402

from csia.v2.attribution import UNIQUE  # noqa: E402
from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia.v2.localization import SUPPORTED  # noqa: E402
from csia.v2.profiles import SCENARIOS, build_engine_for  # noqa: E402
from csia.v2.scenarios import SnapshotSource  # noqa: E402
from csia_semantic_core import SemanticCore21  # noqa: E402
from csia_semantic_core.profile_overlay import (Declaration,  # noqa: E402
                                                ProfileOverlay,
                                                load_successor)
from csia_semantic_core.profile_validator import (ERROR,  # noqa: E402
                                                  validate_profile)
from csia_semantic_core.shadow import ShadowRunner  # noqa: E402

SUCCESSOR_R1_DIGEST = "c7541cab7aa09c8fb6fd4ea1ae522ed1637a0b18a440e5596aeab4e882293bb0"
LEDGER_SHA256 = "6c7e6cf3b8bde3cbac050a67b0bc9cb6fef5aeba587eabca142c823879f5b58f"
TRANSITION_DESIGN_SHA256 = "f84f8e5acbf9d581632286469ef32d038081000a36001e2b9d6d510edbc77c75"


@pytest.fixture(scope="module")
def runs():
    names = ("MS_B4_MECHANICAL", "MS_B5_RESPONSE_SENSOR", "MS_TS_B4_MECHANICAL",
             "MS_TS_B5_RESPONSE_SENSOR", "PROCESS_STALL", "MS_D2_ESTIMATOR_STALE",
             "MS_A1_SENSOR_DELAY", "NOMINAL")
    return {n: P.run_scenario(SCENARIOS[n]) for n in names}


def _candidates():
    with open(os.path.join(PKG, "profile_candidates.json"), encoding="utf-8") as fh:
        return json.load(fh)["candidates"]


def overlay(*ids):
    c = _candidates()
    decls = tuple(Declaration(**{k: (tuple(v) if isinstance(v, list) else v)
                                 for k, v in c[i].items()}) for i in ids)
    return ProfileOverlay("aircraft-successor", "+".join(ids),
                          "csia/v2/profiles/aircraft.py", decls)


def _r1_plus(*ids):
    s = load_successor()
    return ProfileOverlay(s.name, "r1+" + "+".join(ids), s.base_profile,
                          s.declarations + overlay(*ids).declarations)


# ------------------------------------------------------------ shadow runner
def test_the_shadow_returns_the_frozen_engines_own_output():
    sc = SCENARIOS["MS_B5_RESPONSE_SENSOR"]
    snaps = list(SnapshotSource(sc, ticks=60, payload_for=P.feed(sc)))
    shadowed = ShadowRunner(build_engine_for(sc))
    plain = build_engine_for(sc)
    for snap in snaps:
        assert shadowed.evaluate(snap).to_dict() == plain.evaluate(snap).to_dict()
    assert len(shadowed.log) == 60
    assert not any("shadow_fault" in r for r in shadowed.log)


def test_a_failure_inside_the_shadow_cannot_reach_the_authoritative_path(runs):
    engine, res = runs["MS_B5_RESPONSE_SENSOR"]
    runner = ShadowRunner(engine)

    class Broken:
        def reason(self, records):
            raise RuntimeError("shadow bug")

    runner.core = Broken()
    rec = runner.observe(res[-1])
    assert rec["shadow_fault"] == "RuntimeError"
    assert res[-1].attribution.verdict == UNIQUE     # untouched


def test_the_shadow_log_holds_a_hash_not_the_evidence(runs):
    engine, res = runs["MS_B5_RESPONSE_SENSOR"]
    rec = ShadowRunner(engine).observe(res[-1])
    assert len(rec["input_hash"]) == 64
    assert "records" not in rec and "evidence" not in rec


# ------------------------------------------------------- successor profile
def test_successor_r1_is_the_accepted_declarations_by_digest():
    s = load_successor("aircraft_successor_r1")
    assert s.digest() == SUCCESSOR_R1_DIGEST
    assert [(d.domain, d.component, d.add_affected_functions, d.add_dependencies)
            for d in s.declarations] == [
        ("COMPUTE", "state_estimator", ("COARSE_NAVIGATION",), ()),
        ("TIMING", "nav_solution", ("COARSE_NAVIGATION",), ())]
    assert all(d.kind == "DIRECT" and d.justification and d.source
               for d in s.declarations)


def test_the_overlay_never_mutates_the_records_it_is_given(runs):
    engine, res = runs["PROCESS_STALL"]
    before = [r.to_dict() for r in res[-1].records]
    out = load_successor().apply(res[-1].records)
    assert [r.to_dict() for r in res[-1].records] == before
    est = [r for r in out if r.component == "state_estimator"]
    assert all("COARSE_NAVIGATION" in r.affected_functions for r in est)


def test_g1_successor_r1_restores_coarse_navigation_position_unavailable(runs):
    engine, res = runs["MS_D2_ESTIMATOR_STALE"]
    core = SemanticCore21.from_engine(engine, trace=False)
    rec = res[-1].records
    without = {x.subject for x in core.reason(rec).localizations
               if x.symptom == "POSITION_UNAVAILABLE"}
    with_r1 = {x.subject for x in core.reason(load_successor().apply(rec)).localizations
               if x.symptom == "POSITION_UNAVAILABLE"}
    assert "COARSE_NAVIGATION" not in without
    assert "COARSE_NAVIGATION" in with_r1


# ------------------------------------------- wrong UNIQUE stays withheld
@pytest.mark.parametrize("scenario", ["MS_B5_RESPONSE_SENSOR", "MS_TS_B5_RESPONSE_SENSOR"])
@pytest.mark.parametrize("variant", ["none", "successor_r1", "R1", "R2", "R3", "R4",
                                     "R5", "R5a", "R5b", "R6", "R-BAD", "all"])
def test_the_wrong_cause_unique_is_never_restored(runs, scenario, variant):
    engine, res = runs[scenario]
    core = SemanticCore21.from_engine(engine, trace=False)
    ov = {"none": None, "successor_r1": load_successor(),
          "all": overlay("R1", "R2", "R3", "R4", "R5", "R6", "R-BAD")}.get(variant)
    if variant not in ("none", "successor_r1", "all"):
        ov = overlay(variant)
    v20_wrong = sum(1 for sa in res if sa.attribution.verdict == UNIQUE
                    and sa.attribution.candidates[0].domain != "SENSOR")
    assert v20_wrong == 42                     # frozen v2.0 names the actuator
    for sa in res:
        a = core.reason(ov.apply(sa.records) if ov else sa.records).attribution
        assert not (a.verdict == UNIQUE and a.candidates[0].split("/", 1)[0] != "SENSOR")


def test_ms_b4_and_ms_b5_carry_identical_evidence_so_no_unique_can_be_right(runs):
    def sig(records):
        return sorted((r.domain, r.component, r.relation, r.observation_state.value,
                       tuple(r.reason_codes)) for r in records)
    b4, b5 = runs["MS_B4_MECHANICAL"][1], runs["MS_B5_RESPONSE_SENSOR"][1]
    assert all(sig(x.records) == sig(y.records) for x, y in zip(b4, b5))
    core = SemanticCore21.from_engine(runs["MS_B4_MECHANICAL"][0], trace=False)
    assert core.reason(b4[-1].records).attribution.verdict != UNIQUE
    assert core.reason(b5[-1].records).attribution.verdict != UNIQUE


# ------------------------------------------------------------------- G-2
def _imu_pacing_loss(runs):
    engine, res = runs["PROCESS_STALL"]
    recs = tuple(replace(r, observation_state=OS.VIOLATED, reason_codes=("SOURCE_STALE",))
                 if r.component == "source.imu0" else r for r in res[-1].records)
    return SemanticCore21.from_engine(engine, trace=False), recs


def _output_missing(core, recs):
    return [x for x in core.reason(recs).localizations
            if x.symptom == "OUTPUT_MISSING" and x.subject == "state_estimator"][0]


def test_g2_without_a_link_input_2_1_keeps_starvation_open_when_the_imu_dies(runs):
    core, recs = _imu_pacing_loss(runs)
    for ov in (None, load_successor()):
        x = _output_missing(core, ov.apply(recs) if ov else recs)
        assert x.v2.verdict != SUPPORTED
        assert "COMMUNICATION/input_starvation" in x.unresolved


@pytest.mark.parametrize("candidate", ["R5", "R5a", "R5b"])
def test_g2_the_rejected_repairs_restore_the_wrong_process_stall(runs, candidate):
    """Why R5, R5a and R5b are not in the successor profile: each lets the
    GNSS link (directly, or through source.gps's own dependency) refute
    input starvation, which cannot starve EKF2's IMU-paced output."""
    core, recs = _imu_pacing_loss(runs)
    x = _output_missing(core, overlay(candidate).apply(recs))
    assert x.v2.verdict == SUPPORTED
    assert list(x.supported) == ["COMPUTE/process_stall"]


# ------------------------------------------------------- profile validator
@pytest.fixture(scope="module")
def nominal(runs):
    engine, res = runs["NOMINAL"]
    return engine.functions, res[0].records


def _rules(functions, records):
    return {(f.rule, f.subject) for f in validate_profile(records, functions)}


def test_pv1_catches_g1_in_the_frozen_profile_and_r1_clears_it(nominal):
    fg, recs = nominal
    assert ("PV1_SUBJECT_WITHOUT_SERVING_COMPONENT", "COARSE_NAVIGATION") in _rules(fg, recs)
    assert not any(r == "PV1_SUBJECT_WITHOUT_SERVING_COMPONENT"
                   for r, _ in _rules(fg, load_successor().apply(recs)))


def test_pv2_catches_the_dead_supporting_domains_behind_g1(nominal):
    fg, recs = nominal
    got = _rules(fg, recs)
    assert ("PV2_DEAD_SUPPORTING_DOMAIN", "COARSE_NAVIGATION:COMPUTE") in got
    assert ("PV2_DEAD_SUPPORTING_DOMAIN", "COARSE_NAVIGATION:TIMING") in got
    after = _rules(fg, load_successor().apply(recs))
    assert ("PV2_DEAD_SUPPORTING_DOMAIN", "COARSE_NAVIGATION:COMPUTE") not in after


def test_pv3_catches_the_over_connection_that_restores_false_symptoms(nominal):
    fg, recs = nominal
    bad = overlay("R-BAD").apply(recs)
    new = _rules(fg, bad) - _rules(fg, recs)
    assert ("PV3_UNWATCHED_DECLARATION",
            "COMMUNICATION/esc_can -> PRECISION_NAVIGATION") in new


def test_pv4_catches_a_dependency_on_a_component_nobody_describes(nominal):
    fg, recs = nominal
    bad = tuple(replace(r, dependencies=tuple(r.dependencies) + ("COMPUTE/ghost",))
                if r.component == "state_estimator" else r for r in recs)
    assert any(r == "PV4_DANGLING_DEPENDENCY" for r, _ in _rules(fg, bad))


def test_pv5_catches_a_dependency_under_the_wrong_domain(nominal):
    fg, recs = nominal
    bad = tuple(replace(r, dependencies=tuple("SENSOR/cpu" if d == "COMPUTE/cpu" else d
                                              for d in r.dependencies))
                if r.component == "state_estimator" else r for r in recs)
    assert ("PV5_DEPENDENCY_DOMAIN_MISMATCH",
            "COMPUTE/state_estimator -> SENSOR/cpu") in _rules(fg, bad)


def test_pv6_catches_a_dependency_cycle(nominal):
    fg, recs = nominal
    bad = tuple(replace(r, dependencies=tuple(r.dependencies) + ("COMPUTE/state_estimator",))
                if r.component == "cpu" else r for r in recs)
    assert any(r == "PV6_DEPENDENCY_CYCLE" for r, _ in _rules(fg, bad))


def test_pv7_catches_a_misspelled_function(nominal):
    fg, recs = nominal
    bad = tuple(replace(r, affected_functions=tuple(
        "PRECISION_NAVIGATON" if f == "PRECISION_NAVIGATION" else f
        for f in r.affected_functions)) if r.component.startswith("nav_solution") else r
        for r in recs)
    assert any(r == "PV7_UNKNOWN_FUNCTION" for r, _ in _rules(fg, bad))


def test_pv8_catches_one_component_declaring_two_dependency_sets(nominal):
    fg, recs = nominal
    bad = tuple(recs) + tuple(replace(r, dependencies=()) for r in recs
                              if r.component == "state_estimator")
    assert ("PV8_INCONSISTENT_COMPONENT_DEPENDENCIES",
            "COMPUTE/state_estimator") in _rules(fg, bad)


def test_no_shipped_profile_has_a_validator_error():
    for name in ("NOMINAL", "TS_NOMINAL", "PS_NOMINAL"):
        engine, res = P.run_scenario(SCENARIOS[name], ticks=1)
        assert not [f for f in validate_profile(res[0].records, engine.functions)
                    if f.severity == ERROR], name


# ------------------------------------------------- predicate-fault policy
def test_policy_b_withholds_the_supported_a_faulted_refuter_left_standing(runs):
    import predicate_fault_study as F
    engine, res = runs["MS_A1_SENSOR_DELAY"]
    core = SemanticCore21.from_engine(engine, trace=False)
    for s in core.symptoms:
        F._SPEC_BY_SYMPTOM[s.symptom_id] = {h.hypothesis_id: h for h in s.hypotheses}
    rec = res[-1].records
    clean = core.reason(rec)
    faulted = F.faulted_core(core, "NO_TIMING_SEGMENT_OVER_BUDGET").reason(rec)
    key = "POSITION_UNAVAILABLE|PRECISION_NAVIGATION"
    c = {x.key: x for x in clean.localizations}[key]
    f = {x.key: x for x in faulted.localizations}[key]
    assert c.v2.verdict != SUPPORTED                          # correct: nothing fits
    assert f.v2.verdict == SUPPORTED                          # policy A: fault-created
    assert list(f.supported) == ["TIMING/deadline_violation"]
    assert f.evaluation == "PREDICATE_FAULT"                  # visible, as C4 promises
    locs_b, _ = F.apply_policy("B", faulted)
    assert locs_b[key] == F.WITHHELD
    locs_a, _ = F.apply_policy("A", faulted)
    assert locs_a[key] == SUPPORTED


# ------------------------------------------------------------- governance
def test_the_transition_experiment_ran_on_the_frozen_design():
    with open(os.path.join(PKG, "TRANSITION_DESIGN.json"), "rb") as fh:
        assert hashlib.sha256(fh.read()).hexdigest() == TRANSITION_DESIGN_SHA256
    import transition_study as T
    assert T.FROZEN_SHA256 == TRANSITION_DESIGN_SHA256
    with open(os.path.join(PKG, "TRANSITION_RESULTS.json"), encoding="utf-8") as fh:
        res = json.load(fh)
    assert res["design_sha256"] == TRANSITION_DESIGN_SHA256
    assert "NON-CONFIRMATORY" in res["label"]


def test_the_xsys_reanalysis_is_labelled_exploratory_and_reproduces_the_sealed_v3():
    with open(os.path.join(PKG, "XSYS_STATE_CONDITIONED_RESULTS.json"), encoding="utf-8") as fh:
        s = json.load(fh)["summary"]
    assert s["label"].startswith("EXPLORATORY")
    assert s["reproduces_sealed_V3_at_C3"] == {"checked": 110, "matches": 110}


def test_the_failure_ledger_is_untouched():
    path = os.path.join(ROOT, "research", "physical_validation", "FAILURE_LEDGER.yaml")
    with open(path, "rb") as fh:
        assert hashlib.sha256(fh.read()).hexdigest() == LEDGER_SHA256


DOCS = {"README.md", "SHADOW_VALIDATION_REPORT.md", "G1_COARSE_NAVIGATION_AUDIT.md",
        "G2_ESTIMATOR_INPUT_AUDIT.md", "PROFILE_REPAIR_PROPOSAL.md",
        "PROFILE_COUNTERFACTUAL_RESULTS.md", "WEAKENED_UNIQUE_REVIEW.md",
        "WRONG_UNIQUE_REGRESSION.md", "PREDICATE_FAULT_POLICY.md",
        "CONFIGURATION_TRANSITION_STUDY.md", "XSYS_STATE_CONDITIONED_EXPLORATION.md",
        "PROFILE_VALIDATOR_SPEC.md", "DEPENDENCY_METADATA_PREVIEW.md",
        "CUSUM_INTEGRATION_EXAMPLE.md", "ESTIMATOR_INTEGRATION_EXAMPLE.md",
        "C_RUNTIME_DELTA.md", "H743_FEASIBILITY.md", "PRODUCT_UTILITY.md",
        "METHOD_REUSE_MAP.md", "PROMOTION_REVIEW.md", "NEXT_IMPLEMENTATION_TOP5.md",
        "ANTI_ROADMAP.md", "FULLTEXT_VERIFICATION_QUEUE.md",
        "FAILURE_LEDGER_RECOMMENDATIONS.md"}
DATA = {"SHADOW_DIFFERENCES.csv", "PREDICATE_FAULT_INJECTION_RESULTS.csv",
        "LOOPHOLE_REGISTER.csv"}
BANNED = ("no prior work exists", "we are the first", "is the first to",
          "first ever", "no one has", "never been studied", "has never been",
          "no prior art exists")
TOKENS = ("SEMANTIC_2_1_KEEP_SHADOW", "SEMANTIC_2_1_READY_AS_BASELINE",
          "SEMANTIC_2_1_REQUIRES_REVISION", "SEMANTIC_2_1_GOVERNANCE_BLOCK")


def test_the_package_documents_exist_and_keep_the_repositorys_wording_rules():
    have = set(os.listdir(PKG))
    assert DOCS <= have and DATA <= have
    assert {n for n in have if n.endswith(".md")} == DOCS
    for name in sorted(DOCS):
        with open(os.path.join(PKG, name), encoding="utf-8") as fh:
            text = fh.read().lower()
        assert len(text) > 1500, name
        assert not re.search(r"\bnovel\b", text), name
        for phrase in BANNED:
            assert phrase not in text, (name, phrase)


def test_the_promotion_review_chooses_exactly_one_level_and_does_not_promote():
    with open(os.path.join(PKG, "PROMOTION_REVIEW.md"), encoding="utf-8") as fh:
        text = fh.read()
    decision = text.split("## Decision", 1)[1].split("\n## ", 1)[0]
    chosen = [t for t in TOKENS if t in decision]
    assert len(chosen) == 1
    assert chosen != ["SEMANTIC_2_1_READY_AS_BASELINE"]
    assert len(re.findall(r"^\| *\d+ *\|", text, re.M)) >= 16


def test_frozen_v2_is_still_the_default_and_imports_no_successor_code():
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "csia")):
        for f in files:
            if f.endswith(".py"):
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    assert "csia_semantic_core" not in fh.read(), f
