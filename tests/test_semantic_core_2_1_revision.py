"""CSIA Semantic Core 2.1.1: the promotion-candidate revision, pinned.

Package: research/csia_semantic_core_2_1_revision/. Three owner-approved
revisions, each behind its own switch and each off by default:

- R-1 FAULT_POLICY_B: a SUPPORTED is withheld only when a failed predicate
  could have changed it; irrelevant failures leave conclusions alone and stay
  visible;
- R-2 PACING_INPUTS: OUTPUT_MISSING's starvation hypothesis reads the
  subject's declared pacing inputs, never its closure; the rejected GNSS
  repairs (R5, R5a, R5b) cannot bring the wrong answer back by any path;
- R-3 CONFIG_EPOCH: evidence stamped with a configuration epoch other than
  the current one is not admitted; unrelated evidence is untouched.

Plus: 2.1.0 is unchanged when the switches are off; the frozen E1 design
replays with 0 stale ticks; the successor profile r2 is what was reviewed,
by digest, and keeps r1's declarations unchanged.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REV = os.path.join(ROOT, "research", "csia_semantic_core_2_1_revision")
SHADOW = os.path.join(ROOT, "research", "csia_semantic_core_2_1_shadow")
AUDIT = os.path.join(ROOT, "research", "csia_semantic_correctness")
for _p in (ROOT, AUDIT, SHADOW, REV):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import semantic_probe as P  # noqa: E402

from csia.v2.evidence import Applicability, EvidenceRecord  # noqa: E402
from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia.v2.localization import (AMBIGUOUS, SUPPORTED,  # noqa: E402
                                  Hypothesis, Predicate, SymptomSpec)
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import (SEMANTICS_VERSION, Corrections,  # noqa: E402
                                EpochContext, SemanticCore21,
                                WITHHELD_PREDICATE_FAULT)
from csia_semantic_core import admission as A  # noqa: E402
from csia_semantic_core.profile_overlay import (Declaration,  # noqa: E402
                                                ProfileOverlay,
                                                load_successor)
from csia_semantic_core.profile_validator import (ERROR,  # noqa: E402
                                                  validate_profile)

SUCCESSOR_R1_DIGEST = "c7541cab7aa09c8fb6fd4ea1ae522ed1637a0b18a440e5596aeab4e882293bb0"
SUCCESSOR_R2_DIGEST = "c834b0356228da273c6d351def4916387815787ad330e6276d908d1042d7d60e"
R1 = Corrections(fault_policy_b=True)
REVISED = Corrections.revised()


@pytest.fixture(scope="module")
def runs():
    names = ("PROCESS_STALL", "MS_D2_ESTIMATOR_STALE", "MS_A1_SENSOR_DELAY",
             "MS_A2_COMMUNICATION_DELAY", "MS_B5_RESPONSE_SENSOR", "NOMINAL")
    return {n: P.run_scenario(SCENARIOS[n]) for n in names}


@pytest.fixture(scope="module")
def r2():
    return load_successor("aircraft_successor_r2")


# ============================================================ versioning
def test_the_revisions_are_off_by_default_and_2_1_0_is_unchanged():
    assert SEMANTICS_VERSION == "2.1.0"
    assert Corrections().ids() == ("C1", "F2", "C2", "C3", "C4", "C6")
    assert not Corrections().is_revised
    assert Corrections.revised().ids() == (
        "C1", "F2", "C2", "C3", "C4", "C6",
        "FAULT_POLICY_B", "PACING_INPUTS", "CONFIG_EPOCH")


def test_a_revised_result_says_it_is_2_1_1_and_a_default_one_2_1_0(runs, r2):
    engine, res = runs["PROCESS_STALL"]
    d0 = SemanticCore21.from_engine(engine).reason(res[-1].records).to_dict()
    d1 = SemanticCore21.from_engine(engine, REVISED, pacing=r2.pacing_map()).reason(
        r2.apply(res[-1].records)).to_dict()
    assert d0["semantics_version"] == "2.1.0" and d0["schema"].endswith("2.1.0")
    assert d1["semantics_version"] == "2.1.1" and d1["schema"].endswith("2.1.1")
    assert "pacing_declarations_digest" in d1
    assert "config_epoch_admission" in d1["evidence_handling"]
    assert "pacing_declarations_digest" not in d0
    assert "config_epoch_admission" not in d0["evidence_handling"]


def test_pacing_given_to_a_2_1_0_core_is_ignored(runs, r2):
    engine, res = runs["PROCESS_STALL"]
    a = SemanticCore21.from_engine(engine).reason(res[-1].records)
    b = SemanticCore21.from_engine(engine, pacing=r2.pacing_map()).reason(res[-1].records)
    assert a.to_dict() == b.to_dict()
    assert "PACING_INPUTS_NOMINAL" not in SemanticCore21.from_engine(
        engine, pacing=r2.pacing_map()).predicates


@pytest.mark.parametrize("name", ["MS_A1_SENSOR_DELAY", "MS_B5_RESPONSE_SENSOR", "NOMINAL"])
def test_r1_and_r3_change_nothing_on_a_tick_with_no_fault_and_no_epoch(runs, name):
    engine, res = runs[name]
    a = SemanticCore21.from_engine(engine)
    b = SemanticCore21.from_engine(engine, Corrections(fault_policy_b=True,
                                                       config_epoch=True))
    for sa in res:
        x, y = a.reason(sa.records), b.reason(sa.records, {"some.key": 3})
        assert x.to_v2_0_view() == y.to_v2_0_view()
        assert [l.outcome for l in x.localizations] == [l.outcome for l in y.localizations]


# ================================================================== R-1
def _rec(component="subj", state=OS.NOMINAL, **kw):
    base = dict(domain="COMPUTE", component=component, relation="x.state",
                source="test", observation_state=state,
                applicability=Applicability.APPLICABLE)
    base.update(kw)
    return EvidenceRecord(**base)


def _core(hypotheses, values, fail=(), corrections=R1, symptoms=None):
    """A synthetic table: predicate P's value is values[P]; a predicate in
    `fail` raises. X_FALSE is rebuilt from X by the successor."""
    preds = {}

    def make(pid):
        def test(_ix, _s):
            if pid in fail:
                raise RuntimeError("injected")
            return values[pid]
        return test
    for pid in values:
        preds[pid] = Predicate(pid, pid, "COMPUTE", make(pid))
        preds[pid + "_FALSE"] = Predicate(pid + "_FALSE", pid, "COMPUTE", None)
    specs = symptoms or (SymptomSpec("S", "s", lambda ix: ("subj",), hypotheses),)
    return SemanticCore21(specs, preds, (), corrections, trace=True)


def _one(core, key="S|subj"):
    return {x.key: x for x in core.reason((_rec(),)).localizations}[key]


H1 = Hypothesis("COMPUTE/h1", "COMPUTE", "h1", confirmed_by=("C1", "C2"), refuted_by=("R1",))
H2 = Hypothesis("POWER/h2", "POWER", "h2", confirmed_by=("C3",), refuted_by=("R2",))


def test_r1_a_failed_refuter_of_the_supported_hypothesis_withholds_it():
    vals = {"C1": True, "C2": False, "C3": False, "R1": False, "R2": True}
    clean = _one(_core((H1, H2), vals))
    assert clean.v2.verdict == SUPPORTED
    x = _one(_core((H1, H2), vals, fail=("R1",)))
    assert x.outcome == WITHHELD_PREDICATE_FAULT
    assert x.v2.verdict == AMBIGUOUS and x.supported == ("COMPUTE/h1",)
    assert x.evaluation == "PREDICATE_FAULT"
    e = [e for e in x.fault_impact if e["evaluated_as"] == "R1"][0]
    assert (e["predicate_fault"], e["predicate"], e["hypothesis"], e["role"],
            e["dependency"], e["action"]) == (True, "R1", "COMPUTE/h1", "REFUTER",
                                              "MATERIAL", "SUPPORTED_WITHHELD")
    a = _one(_core((H1, H2), vals, fail=("R1",), corrections=Corrections()))
    assert a.v2.verdict == SUPPORTED                       # 2.1.0 policy A


def test_r1_a_material_refuter_failure_never_creates_a_supported():
    vals = {"C1": True, "C2": False, "C3": False, "R1": True, "R2": True}
    assert _one(_core((H1, H2), vals)).outcome == "NO_CONSISTENT_HYPOTHESIS"
    a = _one(_core((H1, H2), vals, fail=("R1",), corrections=Corrections()))
    assert a.v2.verdict == SUPPORTED                       # what 2.1.0 does
    x = _one(_core((H1, H2), vals, fail=("R1",)))
    assert x.outcome == WITHHELD_PREDICATE_FAULT and x.v2.verdict != SUPPORTED


def test_r1_a_failed_confirmer_never_preserves_certainty_that_needed_it():
    vals = {"C1": True, "C2": False, "C3": False, "R1": False, "R2": True}
    only = _one(_core((H1, H2), vals, fail=("C1",)))
    assert only.v2.verdict != SUPPORTED and only.outcome == "INSUFFICIENT_EVIDENCE"
    e = [e for e in only.fault_impact if e["evaluated_as"] == "C1"][0]
    assert (e["role"], e["dependency"], e["action"]) == ("CONFIRMER", "MATERIAL", "NONE")
    both = Hypothesis("COMPUTE/h1", "COMPUTE", "h1", confirmed_by=("C1", "C2"),
                      confirm_requires_all=True, refuted_by=("R1",))
    vals_all = dict(vals, C2=True)
    assert _one(_core((both, H2), vals_all)).v2.verdict == SUPPORTED
    assert _one(_core((both, H2), vals_all, fail=("C2",))).v2.verdict != SUPPORTED


def test_r1_a_confirmer_failure_another_true_confirmer_covers_is_not_material():
    vals = {"C1": True, "C2": True, "C3": False, "R1": False, "R2": True}
    x = _one(_core((H1, H2), vals, fail=("C2",)))
    assert x.outcome == SUPPORTED and x.evaluation == "PREDICATE_FAULT"
    e = [e for e in x.fault_impact if e["evaluated_as"] == "C2"][0]
    assert (e["dependency"], e["why"]) == ("NOT_MATERIAL", "CONFIRMED_BY_ANOTHER_TRUE_CONFIRMER")


def test_r1_an_irrelevant_failure_leaves_an_unrelated_conclusion_alone_and_visible():
    other = SymptomSpec("T", "t", lambda ix: ("subj",),
                        (Hypothesis("POWER/z", "POWER", "z", confirmed_by=("Z",)),))
    main = SymptomSpec("S", "s", lambda ix: ("subj",), (H1, H2))
    vals = {"C1": True, "C2": False, "C3": False, "R1": False, "R2": True, "Z": True}
    core = _core(None, vals, fail=("Z",), symptoms=(main, other))
    got = {x.key: x for x in core.reason((_rec(),)).localizations}
    s = got["S|subj"]
    assert s.outcome == SUPPORTED and s.evaluation != "PREDICATE_FAULT"
    assert not s.fault_impact
    t = got["T|subj"]
    assert t.evaluation == "PREDICATE_FAULT" and t.predicate_errors


def test_r1_an_alternative_domain_failure_on_a_rejected_hypothesis_is_not_material():
    h2 = Hypothesis("POWER/h2", "POWER", "h2", confirmed_by=("C3",), refuted_by=("R2", "R3"))
    vals = {"C1": True, "C2": False, "C3": False, "R1": False, "R2": True, "R3": False}
    x = _one(_core((H1, h2), vals, fail=("R3",)))
    assert x.outcome == SUPPORTED
    e = [e for e in x.fault_impact if e["evaluated_as"] == "R3"][0]
    assert e["dependency"] == "NOT_MATERIAL" and e["why"].startswith("REJECTED_BY_MEASURED_REFUTER")


def test_r1_an_alternative_domain_refuter_failure_only_widens():
    vals = {"C1": True, "C2": False, "C3": False, "R1": False, "R2": True}
    x = _one(_core((H1, H2), vals, fail=("R2",)))
    assert x.v2.verdict != SUPPORTED and "POWER/h2" in x.unresolved
    e = [e for e in x.fault_impact if e["evaluated_as"] == "R2"][0]
    assert (e["dependency"], e["action"]) == ("MATERIAL", "NONE")


def test_r1_a_predicate_shared_by_two_hypotheses_gets_one_entry_per_hypothesis():
    h1 = Hypothesis("COMPUTE/h1", "COMPUTE", "h1", confirmed_by=("C1",), refuted_by=("X",))
    h2 = Hypothesis("POWER/h2", "POWER", "h2", confirmed_by=("X_FALSE",), refuted_by=("R2",))
    vals = {"C1": True, "X": False, "R2": True}
    x = _one(_core((h1, h2), vals, fail=("X",)))
    by = {(e["hypothesis"], e["evaluated_as"]): e for e in x.fault_impact}
    assert by[("COMPUTE/h1", "X")]["action"] == "SUPPORTED_WITHHELD"
    assert by[("POWER/h2", "X_FALSE")]["dependency"] == "NOT_MATERIAL"
    assert x.outcome == WITHHELD_PREDICATE_FAULT


def test_r1_multiple_simultaneous_failures_are_each_judged_and_all_visible():
    vals = {"C1": True, "C2": True, "C3": False, "R1": False, "R2": True}
    x = _one(_core((H1, H2), vals, fail=("C2", "R1")))
    assert x.outcome == WITHHELD_PREDICATE_FAULT
    assert {e.predicate for e in x.predicate_errors} == {"C2", "R1"}
    assert x.trace["withheld_because"] == [{"predicate": "R1", "evaluated_as": "R1",
                                            "hypothesis": "COMPUTE/h1", "role": "REFUTER"}]
    y = _one(_core((H1, H2), vals, fail=("C2", "C3")))
    assert y.outcome == SUPPORTED and len(y.predicate_errors) == 2


@pytest.mark.parametrize("scenario", ["MS_A1_SENSOR_DELAY", "MS_A2_COMMUNICATION_DELAY"])
def test_r1_the_168_fault_created_supported_are_withheld_on_real_ticks(runs, scenario):
    import predicate_fault_study as F
    engine, res = runs[scenario]
    for corr, want in ((Corrections(), SUPPORTED), (R1, WITHHELD_PREDICATE_FAULT)):
        core = F.faulted_core(SemanticCore21.from_engine(engine, corr),
                              "NO_TIMING_SEGMENT_OVER_BUDGET")
        x = {l.key: l for l in core.reason(res[-1].records).localizations}[
            "POSITION_UNAVAILABLE|PRECISION_NAVIGATION"]
        assert x.outcome == want
        assert list(x.supported) == ["TIMING/deadline_violation"]


def test_r1_attribution_is_never_changed_by_the_fault_policy(runs):
    import predicate_fault_study as F
    engine, res = runs["MS_B5_RESPONSE_SENSOR"]
    for base in ("PHYSICAL_RESPONSE_NOMINAL", "CURRENT_PRESENT", "STALL_SIGNATURE"):
        a = F.faulted_core(SemanticCore21.from_engine(engine), base).reason(res[-1].records)
        b = F.faulted_core(SemanticCore21.from_engine(engine, R1), base).reason(res[-1].records)
        assert a.attribution.to_dict() == b.attribution.to_dict()


# ================================================================== R-2
def _om(core, recs):
    got = [x for x in core.reason(recs).localizations
           if x.symptom == "OUTPUT_MISSING" and x.subject == "state_estimator"]
    return got[0] if got else None


def _set(recs, component, state, codes=("SOURCE_STALE",)):
    return tuple(replace(r, observation_state=state, reason_codes=codes)
                 if r.component == component else r for r in recs)


@pytest.fixture(scope="module")
def stall(runs, r2):
    engine, res = runs["PROCESS_STALL"]
    core = SemanticCore21.from_engine(engine, REVISED, pacing=r2.pacing_map())
    return core, r2.apply(res[-1].records)


def _pacing(x):
    return x.trace["predicates"]["PACING_INPUTS_NOMINAL"]


def test_r2_case_a_imu_unavailable_gnss_healthy_starvation_is_supported(stall):
    core, recs = stall
    x = _om(core, _set(recs, "source.imu0", OS.VIOLATED))
    assert "COMMUNICATION/input_starvation" in x.supported
    assert x.v2.verdict != SUPPORTED
    assert _pacing(x)["read"] == {"SENSOR/source.imu0:v1_1.source_health": "VIOLATED"}
    y = _om(core, _set(recs, "source.imu0", OS.UNAVAILABLE))
    assert "COMMUNICATION/input_starvation" in y.unresolved         # plausible, not refuted


def test_r2_case_b_gnss_unavailable_imu_healthy_no_starvation(stall):
    core, recs = stall
    bad = _set(_set(recs, "source.gps", OS.UNAVAILABLE), "gnss_serial", OS.VIOLATED,
               ("COMM_LINK_DOWN",))
    x = _om(core, bad)
    assert dict(x.v2.rejected)["COMMUNICATION/input_starvation"] == "PACING_INPUTS_NOMINAL"
    assert x.v2.verdict == SUPPORTED and x.supported == ("COMPUTE/process_stall",)


def test_r2_case_c_both_unavailable_the_pacing_input_is_the_one_named(stall):
    core, recs = stall
    both = _set(_set(recs, "source.imu0", OS.VIOLATED), "source.gps", OS.VIOLATED)
    x = _om(core, both)
    assert "COMMUNICATION/input_starvation" in x.supported
    assert set(_pacing(x)["read"]) == {"SENSOR/source.imu0:v1_1.source_health"}


@pytest.mark.parametrize("component", ["gnss_serial", "source.gps", "cpu"])
def test_r2_case_d_a_non_pacing_dependency_has_no_effect(stall, component):
    core, recs = stall
    clean = _om(core, recs)
    for state in (OS.VIOLATED, OS.UNAVAILABLE):
        x = _om(core, _set(recs, component, state, ("X",)))
        assert _pacing(x)["value"] == _pacing(clean)["value"] is True


@pytest.mark.parametrize("mode,imu0,imu1,want", [
    ("ALL", OS.NOMINAL, OS.NOMINAL, True), ("ALL", OS.NOMINAL, OS.VIOLATED, False),
    ("ALL", OS.NOMINAL, OS.UNAVAILABLE, None), ("ALL", OS.VIOLATED, OS.UNAVAILABLE, False),
    ("ANY", OS.NOMINAL, OS.VIOLATED, True), ("ANY", OS.VIOLATED, OS.VIOLATED, False),
    ("ANY", OS.VIOLATED, OS.UNAVAILABLE, None), ("ANY", OS.UNAVAILABLE, OS.NOMINAL, True)])
def test_r2_case_e_multiple_pacing_inputs_follow_the_declared_production_semantics(
        runs, r2, mode, imu0, imu1, want):
    engine, res = runs["PROCESS_STALL"]
    base = r2.apply(res[-1].records)
    imu = [r for r in base if r.component == "source.imu0"][0]
    recs = base + (replace(imu, component="source.imu1"),)
    extra = ProfileOverlay("t", "t", "t", (Declaration(
        "COMPUTE", "state_estimator", add_dependencies=("SENSOR/source.imu1",)),))
    recs = _set(_set(extra.apply(recs), "source.imu0", imu0), "source.imu1", imu1)
    core = SemanticCore21.from_engine(engine, REVISED, pacing={
        "state_estimator": (mode, ("SENSOR/source.imu0", "SENSOR/source.imu1"))})
    assert _pacing(_om(core, recs))["value"] is want


def test_r2_no_pacing_declaration_gives_no_answer_and_no_fallback_to_links(runs):
    engine, res = runs["PROCESS_STALL"]
    core = SemanticCore21.from_engine(engine, REVISED)
    x = _om(core, res[-1].records)
    assert _pacing(x)["value"] is None
    assert "NO_DECLARED_PACING_INPUT" in x.trace["scope_gaps"]
    assert "COMMUNICATION/input_starvation" in x.unresolved


def test_r2_the_closure_predicate_is_gone_from_output_missing_and_only_there(runs):
    engine, _ = runs["PROCESS_STALL"]
    core = SemanticCore21.from_engine(engine, REVISED, pacing={})
    om = [s for s in core.symptoms if s.symptom_id == "OUTPUT_MISSING"][0]
    names = {p for h in om.hypotheses for p in h.confirmed_by + h.refuted_by}
    assert not any(p.startswith("FUNCTION_LINKS_NOMINAL") for p in names)
    pu = [s for s in core.symptoms if s.symptom_id == "POSITION_UNAVAILABLE"][0]
    starv = [h for h in pu.hypotheses if h.hypothesis_id == "COMMUNICATION/starvation"][0]
    assert starv.refuted_by == ("FUNCTION_LINKS_NOMINAL",)


def _shadow_overlay(*ids):
    import json
    with open(os.path.join(SHADOW, "profile_candidates.json"), encoding="utf-8") as fh:
        c = json.load(fh)["candidates"]
    return tuple(Declaration(**{k: (tuple(v) if isinstance(v, list) else v)
                                for k, v in c[i].items()}) for i in ids)


@pytest.mark.parametrize("candidate", ["R5", "R5a", "R5b"])
def test_r2_the_rejected_gnss_repairs_cannot_restore_the_wrong_process_stall(
        runs, r2, candidate):
    """Under 2.1.1, even a profile that declares the GNSS input (the repairs
    the shadow study rejected) cannot make GNSS refute starvation."""
    engine, res = runs["PROCESS_STALL"]
    recs = _set(res[-1].records, "source.imu0", OS.VIOLATED)
    bad = ProfileOverlay("t", "r2+" + candidate, "t",
                         r2.declarations + _shadow_overlay(candidate))
    core = SemanticCore21.from_engine(engine, REVISED, pacing=bad.pacing_map())
    x = _om(core, bad.apply(recs))
    assert not (x.v2.verdict == SUPPORTED and x.supported == ("COMPUTE/process_stall",))
    assert "COMMUNICATION/input_starvation" in x.supported
    assert not any("gnss" in k or "gps" in k for k in _pacing(x)["read"])


def test_r2_gnss_cannot_be_smuggled_in_as_a_pacing_input(runs, r2):
    engine, res = runs["PROCESS_STALL"]
    recs = r2.apply(res[-1].records)
    findings = validate_profile(recs, engine.functions, pacing={
        "state_estimator": ("ALL", ("SENSOR/source.imu0", "COMMUNICATION/gnss_serial"))})
    assert ("PV9_PACING_INPUT_NOT_A_DEPENDENCY", ERROR) in {
        (f.rule, f.severity) for f in findings}
    assert not [f for f in validate_profile(recs, engine.functions, pacing=r2.pacing_map())
                if f.severity == ERROR]


def test_r2_successor_r2_is_r1_plus_one_pacing_declaration_and_no_gnss_edge(r2):
    r1 = load_successor()
    assert r1.digest() == SUCCESSOR_R1_DIGEST
    assert r2.digest() == SUCCESSOR_R2_DIGEST
    assert r2.declarations[:2] == r1.declarations
    extra = r2.declarations[2:]
    assert len(extra) == 1 and extra[0].add_pacing_inputs == ("SENSOR/source.imu0",)
    assert not extra[0].add_dependencies and not extra[0].add_affected_functions
    for d in r2.declarations:
        assert not any("gnss" in x or "gps" in x for x in d.add_dependencies)
    assert r2.pacing_map() == {"state_estimator": ("ALL", ("SENSOR/source.imu0",))}


@pytest.mark.parametrize("scenario", ["PROCESS_STALL", "MS_D2_ESTIMATOR_STALE"])
def test_r2_restores_the_process_stall_unique_for_the_right_reason(runs, r2, scenario):
    engine, res = runs[scenario]
    core = SemanticCore21.from_engine(engine, REVISED, pacing=r2.pacing_map())
    tr = core.reason(r2.apply(res[-1].records))
    x = _om(core, r2.apply(res[-1].records))
    assert x.v2.verdict == SUPPORTED and x.supported == ("COMPUTE/process_stall",)
    assert dict(x.v2.rejected)["COMMUNICATION/input_starvation"] == "PACING_INPUTS_NOMINAL"
    assert tr.attribution.verdict == "UNIQUE"
    assert tr.attribution.candidates == ("COMPUTE/state_estimator",)


def test_r2_a_malformed_pacing_declaration_is_refused_before_any_tick(runs):
    engine, _ = runs["PROCESS_STALL"]
    for bad in ({"state_estimator": ("SOME", ("SENSOR/source.imu0",))},
                {"state_estimator": ("ALL", ())},
                {"state_estimator": ("ALL", ("imu0",))}):
        with pytest.raises(ValueError):
            SemanticCore21.from_engine(engine, REVISED, pacing=bad)
    with pytest.raises(ValueError):
        Declaration("COMPUTE", "x", add_pacing_inputs=("SENSOR/a",), pacing_mode="SOME")


# ================================================================== R-3
KEY = "ekf2.selector.instance_changed_count"


def _er(component="state_estimator", relation="compute.deadline_met", epoch=None,
        state=OS.VIOLATED, codes=("COMPUTE_DEADLINE_MISSED",), key=KEY, **kw):
    prov = {} if epoch is None else {"config_epoch": {key: epoch}}
    return _rec(component=component, relation=relation, state=state,
                reason_codes=codes, provenance=prov, **kw)


def _admit(recs, current, events=None):
    return A.admit(recs, EpochContext(current, events or {}))


def test_r3_1_same_epoch_is_admitted_unchanged():
    r = _er(epoch=4)
    out, rep = _admit((r,), {KEY: 4})
    assert out == (r,) and rep["inadmissible"] == []


def test_r3_2_dependent_evidence_after_a_transition_is_not_admitted_and_is_traced():
    r = _er(epoch=4, source="ekf2_lane0")
    out, rep = _admit((r,), {KEY: 5}, {KEY: "primary EKF changed 0 -> 1"})
    assert out[0].observation_state is OS.UNAVAILABLE
    assert out[0].reason_codes == (A.INADMISSIBLE_CODE,)
    e = rep["inadmissible"][0]
    assert (e["source"], e["key"], e["evidence_epoch"], e["current_epoch"], e["reason"],
            e["transition_event"], e["action"]) == (
        "ekf2_lane0", KEY, [4], [5], A.STALE_CONFIGURATION_EPOCH,
        "primary EKF changed 0 -> 1", A.MADE_UNAVAILABLE)


def test_r3_3_unrelated_evidence_is_never_invalidated():
    plain = _er(component="source.imu0", relation="v1_1.source_health")
    other = _er(component="gps", relation="x", epoch=1, key="gps.device_id")
    out, rep = _admit((plain, other), {KEY: 9, "gps.device_id": 1})
    assert out == (plain, other) and rep["inadmissible"] == []


def test_r3_4_new_evidence_is_admitted_and_supersedes_the_old_record_of_its_key():
    old, new = _er(epoch=4), _er(epoch=5, state=OS.NOMINAL, codes=())
    out, rep = _admit((old, new), {KEY: 5})
    assert out == (new,)
    assert rep["inadmissible"][0]["action"] == A.DROPPED_SUPERSEDED


def test_r3_5_multiple_transitions_invalidate_every_older_epoch():
    recs = tuple(_er(epoch=e, relation=f"r{e}") for e in (1, 2, 3, 4))
    out, rep = _admit(recs, {KEY: 4})
    assert [r.observation_state for r in out] == [OS.UNAVAILABLE] * 3 + [OS.VIOLATED]
    assert [e["evidence_epoch"] for e in rep["inadmissible"]] == [[1], [2], [3]]


def test_r3_6_a_replayed_old_epoch_record_is_not_admitted():
    r = _er(epoch=2)
    assert _admit((r,), {KEY: 2})[0] == (r,)
    out, rep = _admit((r, r), {KEY: 3})
    assert all(x.observation_state is OS.UNAVAILABLE for x in out)
    assert {e["reason"] for e in rep["inadmissible"]} == {A.STALE_CONFIGURATION_EPOCH}


def test_r3_7_a_transition_no_record_depends_on_invalidates_nothing():
    recs = (_er(), _er(component="imu", relation="y"))
    out, rep = _admit(recs, {KEY: 7, "imu.device_id": 3}, {KEY: "switch"})
    assert out == recs and rep["inadmissible"] == []


def test_r3_switching_back_to_an_earlier_lane_does_not_readmit_its_old_evidence():
    """The key is a monotonic counter, so lane 0 -> 1 -> 0 is epoch 0 -> 1 -> 2.
    Evidence from the first lane-0 period stays inadmissible."""
    r = _er(epoch=0)
    assert _admit((r,), {KEY: 2})[1]["inadmissible"][0]["reason"] == A.STALE_CONFIGURATION_EPOCH


def test_r3_rapid_switching_admits_only_the_current_epoch():
    recs = tuple(_er(epoch=e, relation="compute.deadline_met",
                     source=f"lane{e}") for e in range(6))
    out, _ = _admit(recs, {KEY: 5})
    assert out == (recs[-1],)


def test_r3_evidence_ahead_of_the_context_holds_back_the_whole_key():
    """A missed transition event: a producer already at N+1 shows the
    context is behind, so its "current" N is not trusted for any record."""
    cur, ahead = _er(epoch=4, relation="a"), _er(epoch=5, relation="b")
    out, rep = _admit((cur, ahead), {KEY: 4})
    reasons = {e["record"].split(":")[1]: e["reason"] for e in rep["inadmissible"]}
    assert reasons == {"a": A.CONTEXT_BEHIND_PRODUCER, "b": A.EPOCH_AHEAD_OF_CONTEXT}
    assert rep["keys_with_context_behind"] == [KEY]
    assert all(r.observation_state is OS.UNAVAILABLE for r in out)


@pytest.mark.parametrize("stamp", [{KEY: -1}, {KEY: True}, {KEY: "4"}, {KEY: 4.0},
                                   {}, "4", {KEY: []}, {"": 4}, {KEY: [1, "a"]}])
def test_r3_a_malformed_epoch_is_not_admitted(stamp):
    r = _rec(component="e", relation="x", state=OS.VIOLATED,
             provenance={"config_epoch": stamp})
    out, rep = _admit((r,), {KEY: 4})
    assert out[0].observation_state is OS.UNAVAILABLE
    assert rep["inadmissible"][0]["reason"] == A.MALFORMED_EPOCH


def test_r3_a_malformed_or_missing_context_epoch_fails_closed():
    r = _er(epoch=4)
    assert _admit((r,), {KEY: "x"})[1]["inadmissible"][0]["reason"] == A.MALFORMED_CONTEXT_EPOCH
    assert _admit((r,), {})[1]["inadmissible"][0]["reason"] == A.UNKNOWN_EPOCH_KEY


def test_r3_a_producer_restart_is_handled_by_a_composite_epoch():
    """A counter alone restarts at 0 with its producer, so an old-boot record
    would match. (boot, counter) does not."""
    old_boot = _er(epoch=[7, 0])
    assert _admit((old_boot,), {KEY: [8, 0]})[1]["inadmissible"][0]["reason"] == \
        A.STALE_CONFIGURATION_EPOCH
    assert _admit((old_boot,), {KEY: 0})[1]["inadmissible"][0]["reason"] == \
        A.EPOCH_FORM_MISMATCH


def test_r3_a_counter_rollover_is_a_mismatch_not_a_match():
    r = _er(epoch=255)
    out, rep = _admit((r,), {KEY: 0})
    assert out[0].observation_state is OS.UNAVAILABLE
    assert rep["inadmissible"][0]["reason"] == A.EPOCH_AHEAD_OF_CONTEXT


def test_r3_an_unrelated_producers_transition_does_not_touch_this_key():
    r = _er(epoch=4)
    out, rep = _admit((r,), {KEY: 4, "sensor_selection.gyro_device_id": 99},
                      {"sensor_selection.gyro_device_id": "gyro changed"})
    assert out == (r,) and rep["inadmissible"] == []


def test_r3_inadmissible_content_is_invisible_to_reason_code_detectors(runs):
    """A stale deadline-missed record must not raise a symptom through its
    old reason codes."""
    engine, res = runs["NOMINAL"]
    recs = tuple(r if not (r.component == "nav_solution" and r.relation == "timing.end_to_end")
                 else replace(r, observation_state=OS.VIOLATED,
                              reason_codes=("TIMING_DEADLINE_MISSED",),
                              provenance=dict(r.provenance or {}, config_epoch={KEY: 0}))
                 for r in res[-1].records)
    core = SemanticCore21.from_engine(engine, REVISED, pacing={})
    now = {x.symptom for x in core.reason(recs, {KEY: 0}).localizations}
    later = {x.symptom for x in core.reason(recs, {KEY: 1}).localizations}
    assert "FUNCTION_DEADLINE_MISS" in now and "FUNCTION_DEADLINE_MISS" not in later


def test_r3_epochs_are_ignored_entirely_by_a_2_1_0_core(runs):
    engine, res = runs["NOMINAL"]
    recs = tuple(replace(r, provenance=dict(r.provenance or {}, config_epoch={KEY: 0}))
                 for r in res[-1].records)
    core = SemanticCore21.from_engine(engine)
    assert core.reason(recs, {KEY: 9}).to_dict() == core.reason(recs).to_dict()


def test_r3_the_frozen_e1_design_replays_with_no_stale_tick():
    import json
    with open(os.path.join(REV, "TRANSITION_REPLAY_RESULTS.json"), encoding="utf-8") as fh:
        got = json.load(fh)
    import transition_study as T
    assert got["design_sha256"] == T.FROZEN_SHA256
    rev = got["configurations"]["REVISED_2_1_1"]
    assert rev["stale_position_symptom_ticks"] == 0
    assert rev["valid_record_ticks_made_unavailable"] == 0
    assert rev["missed_position_symptom_ticks"] == 0
    for cfg in ("V2_0", "PRE_2_1_0"):
        assert got["configurations"][cfg]["stale_position_symptom_ticks"] == 9


# ======================================================= properties (Phase 1)
def test_p5_prime_a_fault_is_reported_and_never_more_certain_than_none():
    """P5 of the 2.1 suite says a fault decides exactly what a None return
    decides. R-1 deliberately separates them (a faulted refuter withholds; an
    unmeasured one does not), so P5's decision clause is replaced by P5': the
    fault is reported wherever it is evaluated, and it never decides anything
    more certain than None. Same injection as P5: every base predicate raises
    on the final tick of every shipped scenario."""
    import property_rerun as PR
    got = PR.p5_prime()
    assert got["P5_prime_holds"], got
    assert got["evaluated"] == got["reported"] > 0
    assert got["more_certain_than_none"] == 0 and got["attribution_differs"] == 0
