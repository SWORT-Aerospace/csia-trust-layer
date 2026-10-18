"""CSIA Semantic Core 2.1.0: the successor's contract.

`csia_semantic_core` is the owner-approved successor to the frozen v2
reasoning semantics (2.0.0). The corrections are C1, F2, C2, C3, C4 and C6,
plus C5 labels and C7 trace, which change no decision. Frozen v2 stays the
historical implementation and the default.

WHAT IS CHECKED
---------------
1. **Nothing historical moved.**
   - The frozen reasoning files are byte-identical to the Phase A lock.
   - Nothing in `csia/` imports the successor, and the frozen engine is still
     the default.
2. **Identity.** With every correction off, the 2.0.0 view equals frozen v2
   on all 2,640 shipped ticks. This is what makes C5 and C7
   behaviour-neutral, and it lets each changed decision be attributed to one
   rule.
3. **The shipped effect is exactly the measured one:**
   - 664 localization ticks and 362 attribution ticks change;
   - no UNIQUE and no SUPPORTED is created;
   - attribution only ever goes from UNIQUE to AMBIGUOUS.
4. **The Phase A defects.** R1, R6, R7, R8B, R8E, R8G, R9, R17 are fixed.
   R9B's fault is now observable; withholding its verdict is governance
   option G5, which is deferred.
5. **The outcomes the brief requires are distinguishable.** They are: no
   consistent hypothesis, one survivor without confirmation, predicate
   evaluation failed, and evidence unavailable.
6. **The audit's properties P1-P15 and P19**, on the shipped corpus, plus
   bounded, derandomized property-based tests. P16, P17, P18 and P20 are
   deferred and pinned as such, so a regression is visible.
7. **Successor twins of T01-T05.** The frozen 2.0.0 tests stay unchanged
   (`research/csia_semantic_core_2_1/TEST_MIGRATION.csv`).

`research/csia_semantic_core_2_1/semantic_core_2_1_differential.py`
produces the numbers the package documents cite. It also runs the heavier
comparisons: the audit's full probe with 2.1 in the successor slot, the
Phase C records, and XSYS-001. Those results are pinned below.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "research", "csia_semantic_core_2_1")
AUDIT = os.path.join(ROOT, "research", "csia_semantic_correctness")
for _p in (ROOT, AUDIT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import semantic_probe as P  # noqa: E402  (read-only: record builders)

from csia.v2 import localization as L  # noqa: E402
from csia.v2 import signatures as SIG  # noqa: E402
from csia.v2.attribution import AMBIGUOUS as A_AMBIGUOUS  # noqa: E402
from csia.v2.attribution import UNIQUE, CrossDomainRelation, attribute  # noqa: E402
from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia.v2.localization import (AMBIGUOUS, SUPPORTED, UNSUPPORTED,  # noqa: E402
                                  Hypothesis, Predicate, SymptomSpec)
from csia.v2.profiles import SCENARIOS  # noqa: E402

import csia_semantic_core as C  # noqa: E402
from csia_semantic_core import (Corrections, SemanticCore21,  # noqa: E402
                                attribute_2_1)
from csia_semantic_core.localization import localize as successor_localize  # noqa: E402

AIR = P.AIR
rec = P.rec
FAST = settings(derandomize=True, deadline=None, max_examples=60,
                suppress_health_check=list(HealthCheck))


def _json(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def corpus():
    """Every shipped scenario, 60 ticks, frozen v2 (the audit's corpus)."""
    out = {}
    for name in sorted(SCENARIOS):
        engine, res = P.run_scenario(SCENARIOS[name])
        out[name] = (engine, res)
    return out


@pytest.fixture(scope="module")
def finals(corpus):
    return [(n, e, tuple(res[-1].records)) for n, (e, res) in sorted(corpus.items())]


def core(cfg=AIR, corrections=Corrections(), trace=True):
    return SemanticCore21(cfg.symptoms, cfg.predicates, cfg.relations,
                          corrections, trace=trace)


def dec(tr):
    return ({x.key: P.lproj(x.v2) for x in tr.localizations},
            P.aproj(tr.attribution.v2))


# =================================================================== guards
def test_the_frozen_reasoning_files_are_byte_identical_to_the_phase_a_lock():
    lock = _json("PHASE_A_CHARACTERIZATION_LOCK.json")
    files = lock["frozen_reasoning_file_sha256"]
    assert set(files) >= {"csia/v2/attribution.py", "csia/v2/localization.py",
                          "csia/v2/signatures.py", "csia/v2/evidence.py"}
    for path, want in files.items():
        with open(os.path.join(ROOT, path), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == want, path


def test_nothing_in_csia_imports_the_successor():
    hits = []
    for base, _dirs, names in os.walk(os.path.join(ROOT, "csia")):
        for n in names:
            if n.endswith(".py"):
                with open(os.path.join(base, n), encoding="utf-8") as fh:
                    if "csia_semantic_core" in fh.read():
                        hits.append(os.path.join(base, n))
    assert not hits, hits


def test_the_frozen_engine_is_still_the_default_runtime():
    """A fresh interpreter evaluates a shipped scenario the ordinary way. The
    successor is never imported and the outputs are frozen v2 types."""
    code = (
        "import sys\n"
        "from csia.v2 import scenarios as SC\n"
        "from csia.v2.profiles import SCENARIOS, build_engine_for\n"
        "from csia.v2.localization import Localization\n"
        "from csia.v2.attribution import Attribution\n"
        "sc = SCENARIOS['REGULATOR_FAILURE']\n"
        "a = SC.run(build_engine_for(sc), sc, ticks=5)[-1]\n"
        "assert type(a.attribution) is Attribution\n"
        "assert all(type(x) is Localization for x in a.localizations)\n"
        "print(sorted(m for m in sys.modules if m.startswith('csia_semantic_core')))\n")
    got = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    assert got.returncode == 0, got.stderr[-2000:]
    assert got.stdout.strip() == "[]"


def test_the_versions_are_declared_and_2_0_0_is_the_historical_one():
    assert C.SEMANTICS_VERSION == "2.1.0"
    assert C.SCHEMA == "csia.semantic_core/2.1.0"
    assert C.HISTORICAL_SEMANTICS_VERSION == "2.0.0"
    assert Corrections().ids() == ("C1", "F2", "C2", "C3", "C4", "C6")
    assert Corrections.none().ids() == ()


def test_the_successor_reuses_the_frozen_elimination_rule():
    """P14 rests on this: 2.1 calls the frozen localize(), not a copy."""
    assert successor_localize is L.localize


# ================================================================= identity
def test_with_every_correction_off_the_2_0_view_is_frozen_v2_on_every_tick(corpus):
    ticks = mismatches = 0
    for _name, (engine, res) in corpus.items():
        c = SemanticCore21.from_engine(engine, Corrections.none())
        for t in res:
            ticks += 1
            view = c.reason(t.records).to_v2_0_view()
            ref = t.to_dict()
            mismatches += int(view["attribution"] != ref["attribution"]
                              or view["localization"] != ref["localization"])
    assert ticks == 2640
    assert mismatches == 0


def test_a_historical_tick_is_evaluated_without_being_modified(corpus):
    engine, res = corpus["MS_B5_RESPONSE_SENSOR"]
    t = res[-1]
    doc = t.to_dict()
    before = json.dumps(doc, sort_keys=True, default=str)
    c = SemanticCore21.from_engine(engine)
    a = C.reason_historical_tick(t, c)
    b = C.reason_historical_tick(doc, c)
    assert json.dumps(doc, sort_keys=True, default=str) == before
    assert a.to_dict() == b.to_dict()
    assert t.attribution.verdict == UNIQUE          # the record still says so
    assert a.attribution.verdict == A_AMBIGUOUS     # 2.1 disagrees


# ======================================================== measured effect
def test_the_shipped_effect_is_exactly_the_measured_one(corpus):
    loc_ticks = attr_ticks = 0
    for _name, (engine, res) in corpus.items():
        c = SemanticCore21.from_engine(engine, trace=False)
        for t in res:
            old = ({f"{x.symptom}|{x.subject}": P.lproj(x) for x in t.localizations},
                   P.aproj(t.attribution))
            new = dec(c.reason(t.records))
            loc_ticks += int(old[0] != new[0])
            if old[1] != new[1]:
                attr_ticks += 1
                assert old[1]["verdict"] == UNIQUE
                assert new[1]["verdict"] == A_AMBIGUOUS
                assert old[1]["candidates"] == new[1]["candidates"]
            assert not (new[1]["verdict"] == UNIQUE and old[1]["verdict"] != UNIQUE)
            for k, v in new[0].items():
                if v["verdict"] == SUPPORTED:
                    assert old[0].get(k) == v, (k, "a SUPPORTED the frozen v2 did not give")
    assert (loc_ticks, attr_ticks) == (664, 362)


# ========================================================= Phase A defects
def test_R1_an_unrelated_nominal_record_no_longer_licenses_unique():
    rail = rec("POWER", "rail_5v", "power.rail_tolerance", OS.VIOLATED)
    cpu = rec("COMPUTE", "cpu", "compute.resource_headroom")
    assert attribute([rail, cpu]).verdict == UNIQUE                 # 2.0.0
    a = core().reason([rail, cpu]).attribution
    assert a.verdict == A_AMBIGUOUS
    # the aircraft relation table declares alternatives for a POWER
    # candidate; none of them was observed NOMINAL
    assert a.withheld_unique_because == ("DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL",)
    assert a.trace["other_nominal"] == {
        "COMPUTE/cpu:compute.resource_headroom": "NOT_A_DECLARED_ALTERNATIVE"}


def test_R4_control_unique_stands_when_every_declared_alternative_is_nominal():
    gps = rec("SENSOR", "source.gps", "v1_1.source_health", OS.VIOLATED,
              deps=("POWER/rail_5v", "COMMUNICATION/gnss_serial"))
    a = core().reason([gps, rec("COMMUNICATION", "gnss_serial", "comm.link_state"),
                       rec("POWER", "rail_5v", "power.rail_tolerance")]).attribution
    assert a.verdict == UNIQUE
    assert a.trace["relevant_discriminators"] == [
        "COMMUNICATION/gnss_serial:comm.link_state", "POWER/rail_5v:power.rail_tolerance"]


def test_R2_R3_R8G_an_alternative_that_did_not_look_blocks_unique():
    gps = rec("SENSOR", "source.gps", "v1_1.source_health", OS.VIOLATED,
              deps=("POWER/rail_5v", "COMMUNICATION/gnss_serial"))
    motor = rec("ACTUATION", "motor_0", "actuation.command_path")
    link_u = rec("COMMUNICATION", "gnss_serial", "comm.link_state", OS.UNAVAILABLE)
    rail_u = rec("POWER", "rail_5v", "power.rail_tolerance", OS.UNAVAILABLE)
    for records in ([gps, motor], [gps, link_u, rail_u, motor]):
        a = core().reason(records).attribution
        assert a.verdict == A_AMBIGUOUS
        assert a.withheld_unique_because == ("DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL",)
    m = rec("ACTUATION", "motor_0", "actuation.electrical_response", OS.VIOLATED,
            codes=("ACT_NO_ELECTRICAL_RESPONSE",),
            deps=("POWER/battery", "COMMUNICATION/esc_can"))
    bat_u = rec("POWER", "battery", "power.source_health", OS.UNAVAILABLE)
    cpu = rec("COMPUTE", "cpu", "compute.resource_headroom")
    assert attribute([m, bat_u, cpu]).verdict == UNIQUE             # 2.0.0
    assert core().reason([m, bat_u, cpu]).attribution.verdict == A_AMBIGUOUS


def _stale_base():
    return [rec("TIMING", "nav_solution", "timing.end_to_end", OS.VIOLATED,
                deps=("COMPUTE/state_estimator", "COMMUNICATION/gnss_serial")),
            rec("TIMING", "nav_solution.sensor_slow", "timing.rate"),
            rec("TIMING", "nav_solution.transport_delay", "timing.segment_budget"),
            rec("TIMING", "nav_solution.processing_delay", "timing.segment_budget"),
            rec("COMMUNICATION", "gnss_serial", "comm.link_state"),
            rec("COMPUTE", "state_estimator", "compute.process_alive"),
            rec("COMPUTE", "state_estimator", "compute.process_producing")]


def test_R6_two_disagreeing_records_answer_neither_in_any_order():
    ok = rec("TIMING", "nav_solution", "timing.clock_consistency")
    bad = rec("TIMING", "nav_solution", "timing.clock_consistency", OS.VIOLATED)
    f_a = P.frozen(_stale_base() + [ok, bad], AIR)[0][0]
    f_b = P.frozen(_stale_base() + [bad, ok], AIR)[0][0]
    assert f_a.verdict != f_b.verdict                               # 2.0.0
    a = core().reason(_stale_base() + [ok, bad])
    b = core().reason(_stale_base() + [bad, ok])
    assert dec(a) == dec(b)
    assert a.conflicting_keys == ("nav_solution:timing.clock_consistency",)
    loc = a.localizations[0]
    assert "nav_solution:timing.clock_consistency" in loc.trace["conflicts_not_read"]


def test_R7_an_exact_duplicate_counts_once():
    src = rec("SENSOR", "source.gps", "v1_1.source_health", OS.VIOLATED,
              deps=("POWER/rail_5v",))
    rail = rec("POWER", "rail_5v", "power.rail_tolerance", OS.VIOLATED)
    one, two = core().reason([src, rail]), core().reason([src, src, rail])
    assert dec(one) == dec(two)
    assert "MULTIPLE_SENSORS_DEGRADED|sources" not in [x.key for x in two.localizations]
    assert two.duplicates_collapsed == {"SENSOR/source.gps:v1_1.source_health": 1}


def test_R8B_a_link_that_could_not_look_no_longer_refutes_the_true_cause():
    recs = [r for r in _stale_base() if r.relation != "comm.link_state"
            and r.component != "nav_solution.transport_delay"]
    recs += [rec("TIMING", "nav_solution", "timing.clock_consistency"),
             rec("TIMING", "nav_solution.transport_delay", "timing.segment_budget", OS.VIOLATED),
             rec("COMMUNICATION", "gnss_serial", "comm.link_state", OS.UNAVAILABLE)]
    frozen = P.frozen(recs, AIR)[0][0]
    assert "COMMUNICATION/transport_delay" in dict(frozen.rejected)  # 2.0.0
    loc = core().reason(recs).localizations[0]
    assert "COMMUNICATION/transport_delay" not in dict(loc.v2.rejected)
    assert "CHANNEL_LINK_NOMINAL" in loc.evidence_unavailable


def test_R8E_missing_process_telemetry_no_longer_supports_processing_delay():
    recs = [rec("TIMING", "nav_solution", "timing.end_to_end", OS.VIOLATED,
                deps=("COMPUTE/state_estimator", "COMMUNICATION/gnss_serial")),
            rec("TIMING", "nav_solution", "timing.clock_consistency"),
            rec("TIMING", "nav_solution.sensor_slow", "timing.rate"),
            rec("TIMING", "nav_solution.transport_delay", "timing.segment_budget"),
            rec("TIMING", "nav_solution.processing_delay", "timing.segment_budget", OS.VIOLATED),
            rec("COMMUNICATION", "gnss_serial", "comm.link_state"),
            rec("COMPUTE", "state_estimator", "compute.process_alive", OS.UNAVAILABLE)]
    frozen = P.frozen(recs, AIR)[0][0]
    assert frozen.supported == ("COMPUTE/processing_delay",)          # 2.0.0
    loc = core().reason(recs).localizations[0]
    assert loc.outcome == AMBIGUOUS
    assert set(loc.unresolved) >= {"COMPUTE/process_stall"}


def test_R17_unreported_shared_nodes_no_longer_support_independent_faults():
    shared = ("POWER/rail_3v3", "COMMUNICATION/bus_a", "COMPUTE/proc_a", "TIMING/clk_a")
    s1 = rec("SENSOR", "source.imu0", "v1_1.source_health", OS.VIOLATED, deps=shared)
    s2 = rec("SENSOR", "source.mag", "v1_1.source_health", OS.VIOLATED, deps=shared)
    assert P.frozen([s1, s2], AIR)[0][0].supported == ("SENSOR/independent_faults",)
    loc = core().reason([s1, s2]).localizations[0]
    assert "SENSOR/independent_faults" not in loc.supported


def _synthetic(q, r):
    spec = SymptomSpec("S", "synthetic", detect=lambda ix: ("x",), hypotheses=(
        Hypothesis("D1/h1", "D1", "m", confirmed_by=("P",), refuted_by=("Q",)),
        Hypothesis("D2/h2", "D2", "m", confirmed_by=("P",), refuted_by=("R",))))
    table = {"P": Predicate("P", "", "D", lambda i, s: True),
             "Q": Predicate("Q", "", "D", q), "R": Predicate("R", "", "D", r)}
    return SemanticCore21((spec,), table).reason([]).localizations[0]


def _boom(i, s):
    raise KeyError("defect")


def test_R9_a_raising_predicate_is_reported_not_silently_unmeasurable():
    loc = _synthetic(_boom, lambda i, s: False)
    assert loc.evaluation == C.PREDICATE_FAULT
    assert [e.to_dict() for e in loc.predicate_errors] == [{
        "predicate": "Q", "evaluated_as": ["Q"], "subject": "x",
        "error_class": "RAISED:KeyError",
        "context": {"symptom": "S", "hypotheses": ["D1/h1"]}}]
    assert loc.evidence_unavailable == ()
    assert "Q" in loc.v2.unmeasurable        # 2.0.0 view unchanged


def test_R10_a_non_bool_return_is_reported_and_is_not_a_measured_false():
    import numpy as np
    loc = _synthetic(lambda i, s: np.True_, lambda i, s: False)
    assert loc.evaluation == C.PREDICATE_FAULT
    assert loc.predicate_errors[0].error_class == "NON_BOOL:numpy.bool"
    assert loc.v2.detail["predicate_values"]["Q"] is None


def test_R9B_the_fault_is_observable_and_the_elimination_rule_is_unchanged():
    """G5 (withholding SUPPORTED over a faulted refuter) is NOT approved. The
    verdict therefore stays what 2.0.0 gives, but it can no longer be taken
    for a clean one."""
    loc = _synthetic(_boom, lambda i, s: True)
    assert loc.outcome == SUPPORTED and loc.supported == ("D1/h1",)
    assert loc.evaluation == C.PREDICATE_FAULT
    assert loc.predicate_errors[0].hypotheses == ("D1/h1",)


def test_a_fault_in_x_cannot_reappear_as_a_measured_false_in_x_false():
    """The negation is rebuilt over the checked X. This is the path that let
    NO_TIMING_SEGMENT_OVER_BUDGET's guard vanish silently (P5)."""
    spec = SymptomSpec("S", "", detect=lambda ix: ("x",), hypotheses=(
        Hypothesis("D1/h1", "D1", "m", confirmed_by=("P",), refuted_by=("Q_FALSE",)),))
    base = Predicate("Q", "q", "D", _boom)
    table = {"P": Predicate("P", "", "D", lambda i, s: True), "Q": base,
             "Q_FALSE": SIG._negate(base)}
    loc = SemanticCore21((spec,), table).reason([]).localizations[0]
    assert loc.evaluation == C.PREDICATE_FAULT
    assert loc.predicate_errors[0].evaluated_as == ("Q_FALSE",)


def test_a_missing_predicate_id_is_a_configuration_error_before_any_tick():
    spec = SymptomSpec("S", "", detect=lambda ix: (), hypotheses=(
        Hypothesis("D1/h1", "D1", "m", confirmed_by=("NOT_THERE",)),))
    with pytest.raises(C.PredicateTableError, match="NOT_THERE"):
        SemanticCore21((spec,), {})


# ======================================================== outcome semantics
def test_the_four_outcome_states_the_brief_requires_are_distinguishable():
    true, false, none = (lambda i, s: True), (lambda i, s: False), (lambda i, s: None)
    everything_rejected = _synthetic(true, true)
    assert everything_rejected.outcome == C.NO_CONSISTENT_HYPOTHESIS
    assert everything_rejected.v2.verdict == UNSUPPORTED     # 2.0.0 label
    fault = _synthetic(_boom, false)
    assert fault.evaluation == C.PREDICATE_FAULT
    unavailable = _synthetic(none, false)
    assert unavailable.evaluation == C.EVIDENCE_UNAVAILABLE
    assert unavailable.evidence_unavailable == ("Q",) and not unavailable.predicate_errors
    spec = SymptomSpec("S", "", detect=lambda ix: ("x",), hypotheses=(
        Hypothesis("D1/h1", "D1", "m", confirmed_by=("P",), refuted_by=("R",)),
        Hypothesis("D2/h2", "D2", "m", confirmed_by=("P",)),
        Hypothesis("D3/h3", "D3", "m", unmodelled=True)))
    tbl = {"P": Predicate("P", "", "D", none), "R": Predicate("R", "", "D", true)}
    lone = SemanticCore21((spec,), tbl).reason([]).localizations[0]
    assert lone.v2.verdict == AMBIGUOUS             # two survive: h2 and h3
    spec2 = replace(spec, hypotheses=spec.hypotheses[:2])
    lone = SemanticCore21((spec2,), tbl).reason([]).localizations[0]
    assert (lone.outcome, lone.outcome_reason) == (C.INSUFFICIENT_EVIDENCE,
                                                   "UNCONFIRMED_SURVIVOR")
    assert lone.v2.verdict == UNSUPPORTED
    spec3 = replace(spec, hypotheses=(spec.hypotheses[0], spec.hypotheses[2]))
    lone = SemanticCore21((spec3,), tbl).reason([]).localizations[0]
    assert (lone.outcome, lone.outcome_reason) == (C.INSUFFICIENT_EVIDENCE, "UNMODELLED")
    assert {everything_rejected.outcome, lone.outcome} <= set(C.OUTCOMES)


# ============================================================== properties
AUX = P.AUX
STATES = P.STATES


def test_P1_P7_irrelevant_addition_changes_no_other_result(finals):
    """Exhaustive over the 44 final ticks x 6 unconnected components x 5
    states (1,320 cases, the audit's P1)."""
    bad = []
    for name, engine, records in finals:
        c = SemanticCore21.from_engine(engine, trace=False)
        base = dec(c.reason(records))
        for (d, comp, rel), s in ((a, s) for a in AUX for s in STATES):
            got = dec(c.reason(records + (rec(d, comp, rel, s, fns=("AUX_FUNCTION",)),)))
            skip = {comp, "sources"} if rel == "v1_1.source_health" else {comp}
            for k in set(base[0]) | set(got[0]):
                if k.split("|", 1)[1] not in skip and base[0].get(k) != got[0].get(k):
                    bad.append((name, rel, s.value, k))
            ab, aa = base[1], got[1]
            if s is OS.NOMINAL and ab != aa:
                bad.append((name, rel, s.value, "ATTR changed on NOMINAL"))
            # the audit's definition: an AMBIGUOUS attribution becoming UNIQUE.
            # NO_EVIDENCE -> UNIQUE names the added adverse component itself.
            if ab["verdict"] == A_AMBIGUOUS and aa["verdict"] == UNIQUE:
                bad.append((name, rel, s.value, "ATTR more certain"))
            if (ab["verdict"] == UNIQUE and aa["verdict"] == UNIQUE
                    and ab["candidates"] != aa["candidates"]):
                bad.append((name, rel, s.value, "UNIQUE moved to another component"))
            if not set(ab["candidates"]) <= set(aa["candidates"]):
                bad.append((name, rel, s.value, "candidate lost (P7)"))
    assert not bad, bad[:10]


def _scope_components(records, subject):
    idx = C.SuccessorIndex(records, tracing=False)
    comps = set(C.declared_scope(idx, subject)) | {f"v1_1.{subject}"}
    return comps | {r.component for r in records
                    if r.component.split(".", 1)[0] in comps}


@FAST
@given(data=st.data())
def test_P2_removing_an_out_of_scope_record_changes_no_localization(finals, data):
    name, engine, records = data.draw(st.sampled_from(finals))
    i = data.draw(st.integers(0, len(records) - 1))
    c = SemanticCore21.from_engine(engine, trace=False)
    base = dec(c.reason(records))
    got = dec(c.reason(records[:i] + records[i + 1:]))
    gone = records[i]
    for k, v in base[0].items():
        subject = k.split("|", 1)[1]
        if subject == "sources":
            continue
        if gone.component not in _scope_components(records, subject):
            assert got[0].get(k) == v, (name, P.rid(gone), k)


@FAST
@given(data=st.data())
def test_P3_container_order_changes_nothing(finals, data):
    name, engine, records = data.draw(st.sampled_from(finals))
    seed = data.draw(st.integers(0, 2**16))
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    c = SemanticCore21.from_engine(engine, trace=True)
    a, b = c.reason(records), c.reason(tuple(reversed(shuffled)))
    assert dec(a) == dec(b)
    for x, y in zip(a.localizations, b.localizations):
        assert x.trace == y.trace


@FAST
@given(data=st.data())
def test_P4_P15_an_exact_duplicate_changes_no_decision_and_no_trace(finals, data):
    name, engine, records = data.draw(st.sampled_from(finals))
    i = data.draw(st.integers(0, len(records) - 1))
    c = SemanticCore21.from_engine(engine, trace=True)
    a = c.reason(records)
    b = c.reason(records + (records[i],))
    assert dec(a) == dec(b)
    assert [x.trace for x in a.localizations] == [x.trace for x in b.localizations]
    assert a.attribution.trace == b.attribution.trace
    whole = c.reason(records + records)
    assert dec(whole) == dec(a)


def test_P5_every_injected_fault_is_reported_where_it_is_evaluated(finals):
    """C4: a fault is recorded in every localization that evaluates the
    predicate, and it decides nothing a None return would not decide."""
    pids = sorted(p for p in SIG.PREDICATES if not p.endswith("_FALSE"))
    evaluated = reported = 0
    for pid in pids:
        for name, engine, records in finals:
            preds = dict(engine.predicates)
            preds[pid] = Predicate(pid, "", "X", _boom)
            as_none = dict(engine.predicates)
            as_none[pid] = Predicate(pid, "", "X", lambda i, s: None)
            cfg_f = P.Cfg(engine.symptoms, preds, engine.relations)
            cfg_n = P.Cfg(engine.symptoms, as_none, engine.relations)
            tf = core(cfg_f, trace=False).reason(records)
            tn = core(cfg_n, trace=False).reason(records)
            assert dec(tf) == dec(tn), (pid, name)
            for x in tf.localizations:
                vals = x.v2.detail["predicate_values"]
                if pid in vals or pid + "_FALSE" in vals:
                    evaluated += 1
                    ok = (x.evaluation == C.PREDICATE_FAULT
                          and pid in {e.predicate for e in x.predicate_errors})
                    reported += int(ok)
    assert evaluated > 0 and reported == evaluated


@settings(derandomize=True, deadline=None, max_examples=120,
          suppress_health_check=list(HealthCheck))
@given(data=st.data())
def test_P6_P12_unknown_evidence_decides_nothing_a_completion_would_not(finals, data):
    """Kleene: with one record UNAVAILABLE, every measured predicate value
    must be the value BOTH completions give, and UNIQUE must not stand while
    an unknown record is a declared alternative."""
    name, engine, records = data.draw(st.sampled_from(finals))
    i = data.draw(st.integers(0, len(records) - 1))
    r = records[i]
    if r.observation_state in (OS.UNAVAILABLE, OS.NOT_APPLICABLE):
        return
    swap = lambda x: records[:i] + (x,) + records[i + 1:]  # noqa: E731
    c = SemanticCore21.from_engine(engine, trace=False)
    tu = c.reason(swap(P.twin(r, OS.UNAVAILABLE)))
    tn, tv = (c.reason(swap(x)) for x in P.completions(r))
    comp = [{x.key: x for x in t.localizations} for t in (tn, tv)]
    for x in tu.localizations:
        for pid, val in x.v2.detail["predicate_values"].items():
            if val is None:
                continue
            for other in comp:
                y = other.get(x.key)
                if y is not None:
                    assert y.v2.detail["predicate_values"].get(pid) == val, (name, x.key, pid)
    if tu.attribution.verdict == UNIQUE:
        only = tu.attribution.v2.candidates[0].id
        alts = C.declared_alternatives(only, tu_records := swap(P.twin(r, OS.UNAVAILABLE)),
                                       engine.relations)
        assert f"{r.domain}/{r.component}" not in alts, (name, P.rid(r))
        assert tu_records


def test_P8_replay_is_deterministic(finals):
    for name, engine, records in finals[::7]:
        c = SemanticCore21.from_engine(engine)
        assert c.reason(records).to_dict() == c.reason(records).to_dict(), name


def test_P9_unique_never_contradicts_its_own_ticks_localization(corpus):
    uniques = 0
    for _name, (engine, res) in corpus.items():
        c = SemanticCore21.from_engine(engine, trace=False)
        for t in res:
            tr = c.reason(t.records)
            if tr.attribution.verdict != UNIQUE:
                continue
            uniques += 1
            only = tr.attribution.v2.candidates[0]
            for x in tr.localizations:
                if x.subject == only.component:
                    assert all(h.split("/", 1)[0] == only.domain
                               for h in x.supported + x.unresolved)
    assert uniques == 889 - 362


def test_P10_P11_P13_trace_and_labels_are_consistent(finals):
    for name, engine, records in finals:
        tr = SemanticCore21.from_engine(engine).reason(records)
        for x in tr.localizations:
            vals = x.v2.detail["predicate_values"]
            assert list(x.v2.evidence) == sorted(p for p, v in vals.items() if v is True)
            assert list(x.v2.unmeasurable) == sorted(p for p, v in vals.items() if v is None)
            faulted = {i for e in x.predicate_errors for i in e.evaluated_as}
            assert set(x.evidence_unavailable) | faulted == set(x.v2.unmeasurable)
            assert x.outcome in C.OUTCOMES and x.outcome != UNSUPPORTED     # P11
            spec = next(s for s in SIG.SYMPTOMS if s.symptom_id == x.symptom)
            silent = [h for h, _ in x.v2.rejected
                      if any(vals.get(p) is True for p in
                             next(y for y in spec.hypotheses if y.hypothesis_id == h).confirmed_by)]
            assert sorted(c["hypothesis"] for c in x.trace["confirmed_and_refuted"]) \
                == sorted(silent)                                            # P13
        a = tr.attribution
        parts = [c for k in ("implicated_nominal", "implicated_unavailable",
                             "implicated_unobserved", "implicated_other")
                 for c in a.implicated[k]]
        assert sorted(parts) == sorted(a.v2.unsupported), name              # P11


def test_P19_every_unique_has_every_declared_alternative_affirmatively_nominal(corpus):
    for _name, (engine, res) in corpus.items():
        c = SemanticCore21.from_engine(engine, trace=False)
        for t in res[::5]:
            a = c.reason(t.records).attribution
            if a.verdict == UNIQUE:
                assert a.trace["declared_alternatives"]
                assert a.trace["unexcluded_alternatives"] == []
                only = a.v2.candidates[0]
                assert any(not d.startswith(only.domain + "/")
                           for d in a.trace["relevant_discriminators"])


# ======================================== heavier results, pinned from the run
def test_the_audits_full_probe_reproduces_with_2_1_in_the_successor_slot():
    got = _json("SEMANTIC_CORE_2_1_RESULTS.json")["AUDIT"]["comparison_with_audit_shadow"]
    for sec in ("E", "N", "P", "SH", "X"):
        assert got[sec]["identical_to_audit"], (sec, got[sec]["differing_paths"])
    # R11A records one extra field per fault (evaluated_as); same faults.
    assert got["R"]["differing_paths"] == ["/R11A/shadow_predicate_errors[0]",
                                           "/R11A/shadow_predicate_errors[1]"]


def test_phase_d_classification_has_no_defect_still_present():
    d = _json("SEMANTIC_CORE_2_1_RESULTS.json")["D"]
    assert "STILL_PRESENT" not in d["classification_counts"]
    deferred = {r["id"] for r in d["measures"] + d["not_measured_here"]
                if r["classification"] == "INTENTIONALLY_DEFERRED"}
    assert deferred == {"P16", "P17", "P18", "P20", "R9B"}
    p16 = next(r for r in d["measures"] if r["id"] == "P16")
    assert (p16["frozen_v2"], p16["semantic_core_2_1"]) == (838, 168)


def test_phase_e_every_change_is_expected_and_none_is_more_certain():
    e = _json("SEMANTIC_CORE_2_1_RESULTS.json")["E"]
    assert e["totals"]["ticks_changed"] == 945
    assert e["totals"]["unexpected_units"] == 0
    assert e["totals"]["more_certain_units"] == 0
    assert e["units_by_rule"] == {"C3": 913, "C3+F2": 81, "F2": 281}


def test_phase_e_receipts_never_claim_a_historical_result_was_modified():
    n = 0
    with open(os.path.join(PKG, "PHASE_E_CHANGE_RECEIPTS.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            assert r["HISTORICAL_RESULT_MODIFIED"] == "NO"
            n += 1
    assert n == 945


def test_phase_f_the_xsys_hard_gate_passes():
    f = _json("SEMANTIC_CORE_2_1_RESULTS.json")["F"]
    assert f["XSYS_HARD_GATE"] == "PASS"
    assert f["slots"] == 3872
    assert f["decision_differences_2_1_vs_sealed"] == 0
    assert f["outcome_differences_2_1_vs_recorded_results"] == 0
    p = f["primary_recomputed_under_2_1"]
    assert (p["n_pairs"], p["n_success"], p["wrong_A_B"], p["H_PRIMARY"]) == \
        (55, 55, 0, "SUPPORTED")
    assert p["lower95"] == f["primary_record"]["ONE_SIDED_95_LB"]


def test_phase_g_the_phase_c_gate_headline_is_unchanged():
    g = _json("SEMANTIC_CORE_2_1_RESULTS.json")["G"]
    assert g["gate_frozen_recomputed_matches_record"]
    assert g["gate_verdict"] == {"recorded": "CROSS_DOMAIN_ASSURANCE_FUNCTIONAL",
                                 "semantic_core_2_1": "CROSS_DOMAIN_ASSURANCE_FUNCTIONAL"}
    assert g["gate_qualifying_answers_unchanged"]
    assert g["wrong_unique_corrected"] == ["MS_B5_RESPONSE_SENSOR",
                                           "MS_TS_B5_RESPONSE_SENSOR"]


def test_no_protected_file_changed_during_the_differential_run():
    got = _json("SEMANTIC_CORE_2_1_RESULTS.json")["PROTECTED_FILES"]
    assert got["unchanged_by_this_run"]
    for path, want in got["sha256"].items():
        with open(os.path.join(ROOT, path), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == want, path


# ============================================ successor twins of T01-T05
def _frec(**kw):
    from csia.v2.evidence import Applicability, EvidenceRecord
    base = dict(domain="POWER", component="battery", relation="power.x",
                source="power", observation_state=OS.NOMINAL,
                applicability=Applicability.APPLICABLE)
    base.update(kw)
    return EvidenceRecord(**base)


def test_T01_twin_unique_needs_a_relevant_exclusion_not_any_nominal_record():
    adverse = _frec(observation_state=OS.VIOLATED)
    elsewhere = _frec(domain="COMPUTE", component="cpu",
                      relation="compute.resource_headroom")
    a = attribute_2_1([adverse, elsewhere], ())
    assert a.verdict == A_AMBIGUOUS
    assert a.withheld_unique_because == ("NO_DECLARED_ALTERNATIVE_WAS_EXCLUDED",)
    # declare the alternative and show it NOMINAL: UNIQUE, and it is named
    adverse = _frec(observation_state=OS.VIOLATED,
                    dependencies=("COMMUNICATION/bus",))
    bus = _frec(domain="COMMUNICATION", component="bus", relation="comm.link_state")
    a = attribute_2_1([adverse, elsewhere, bus], ())
    assert a.verdict == UNIQUE
    assert a.trace["relevant_discriminators"] == ["COMMUNICATION/bus:comm.link_state"]
    assert "COMPUTE/cpu:compute.resource_headroom" in a.trace["other_nominal"]


def test_T02_twin_both_verdicts_report_what_was_ruled_out_the_same_way():
    one = _frec(observation_state=OS.VIOLATED, dependencies=("COMPUTE/cpu",))
    elsewhere = _frec(domain="COMPUTE", component="cpu")
    unique = attribute_2_1([one, elsewhere], ())
    assert unique.verdict == UNIQUE
    assert unique.v2.detail["domains_excluded"] == ["COMPUTE"]
    two = _frec(domain="TIMING", component="nav", observation_state=OS.VIOLATED)
    ambiguous = attribute_2_1([one, two, elsewhere], ())
    assert ambiguous.verdict == A_AMBIGUOUS
    assert ambiguous.v2.detail["domains_excluded"] == ["COMPUTE"]


def test_T03_twin_a_stalled_process_is_the_only_candidate_but_not_unique(corpus):
    """The profile declares no input link for the estimator (gap G-2), so
    OUTPUT_MISSING keeps COMMUNICATION/input_starvation open, and F2 then
    withholds UNIQUE. The candidate is still the right component."""
    engine, res = corpus["PROCESS_STALL"]
    a = SemanticCore21.from_engine(engine).reason(res[-1].records).attribution
    assert a.candidates == ("COMPUTE/state_estimator",)
    assert a.verdict == A_AMBIGUOUS
    assert a.withheld_unique_because == ("SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN",)
    assert {"symptom": "OUTPUT_MISSING", "retains": ["COMMUNICATION/input_starvation"]} \
        in a.trace["localization_disagreement"]


def test_T04_twin_the_healthy_battery_is_implicated_and_affirmatively_nominal(corpus):
    engine, res = corpus["REGULATOR_FAILURE"]
    a = SemanticCore21.from_engine(engine).reason(res[-1].records).attribution
    assert "POWER/battery" in a.implicated["implicated_nominal"]
    assert "POWER/battery" in a.v2.unsupported       # the 2.0.0 field, unchanged


def test_T05_twin_a_true_lone_survivor_is_insufficient_evidence():
    spec = SIG.SYMPTOMS_BY_ID["VOLTAGE_RAIL_LOW"]
    rail = rec("POWER", "rail_5v", "power.rail_tolerance", OS.VIOLATED)
    table = dict(SIG.PREDICATES)
    table["SOURCE_WITHIN_TOLERANCE"] = Predicate(
        "SOURCE_WITHIN_TOLERANCE", "", "POWER", lambda i, s: None)
    table["SOURCE_WITHIN_TOLERANCE_FALSE"] = Predicate(
        "SOURCE_WITHIN_TOLERANCE_FALSE", "", "POWER", lambda i, s: True)
    loc = SemanticCore21((spec,), table).reason([rail]).localizations[0]
    # base None and a stand-alone negation are rebuilt by name: both None,
    # so both hypotheses survive -> AMBIGUOUS, never a lone survivor.
    assert loc.outcome == AMBIGUOUS
    lone = replace(spec, hypotheses=(spec.hypotheses[1],))
    loc = SemanticCore21((lone,), dict(SIG.PREDICATES)).reason([rail]).localizations[0]
    assert (loc.outcome, loc.outcome_reason) == (C.INSUFFICIENT_EVIDENCE,
                                                 "UNCONFIRMED_SURVIVOR")
    assert loc.v2.verdict == UNSUPPORTED


def test_a_relation_alone_still_never_promotes_a_component():
    adverse = _frec(observation_state=OS.VIOLATED)
    rel = CrossDomainRelation("r", ("POWER",), ("ACTUATION/motor_0",), "")
    a = attribute_2_1([adverse, _frec(domain="COMPUTE", component="cpu")], (rel,))
    assert "ACTUATION/motor_0" not in a.candidates
    assert a.implicated["implicated_unobserved"] == ["ACTUATION/motor_0"]


# ================================================== Phases G, K and L records
LEDGER = os.path.join(ROOT, "research", "physical_validation", "FAILURE_LEDGER.yaml")
#: The hash the Phase 3.2, 4 and 5 sealed manifests pin for the ledger.
#: Rule R8: no append without the owner's decision.
LEDGER_PINNED = "6c7e6cf3b8bde3cbac050a67b0bc9cb6fef5aeba587eabca142c823879f5b58f"


def test_phase_e_the_changes_are_assessed_not_just_counted():
    e = _json("SEMANTIC_CORE_2_1_RESULTS.json")["E"]
    assert e["units_by_assessment"] == {
        "CONSISTENT_WITH_FUNCTION_GRAPH": 189, "DECIDED_BY_PROFILE_GAP": 481,
        "RIGHT_UNIQUE_WEAKENED": 278, "WEAKENED_BY_PROFILE_GAP": 243,
        "WRONG_UNIQUE_CORRECTED": 84}


def test_the_failure_ledger_is_untouched_and_the_entries_are_proposed():
    """Phase K. The seven entries are held out of the hash-pinned ledger,
    as commit b75ad0c held FL-053, and are complete and parse."""
    with open(LEDGER, "rb") as fh:
        assert hashlib.sha256(fh.read()).hexdigest() == LEDGER_PINNED, (
            "the failure ledger changed; it is pinned by three sealed-phase "
            "manifests and rule R8 reserves appends to the owner")
    import yaml
    with open(os.path.join(PKG, "PROPOSED_LEDGER_ENTRIES.md"), encoding="utf-8") as fh:
        text = fh.read()
    block = text.split("```yaml\n", 1)[1].split("\n```", 1)[0]
    entries = yaml.safe_load("entries:\n" + block)["entries"]
    assert [e["id"] for e in entries] == [f"FL-0{k}" for k in range(54, 61)]
    for e in entries:
        assert e["verdict"] == "RECORDED", "not to be marked resolved"
        for key in ("affected_version", "found_by", "successor_correction",
                    "historical_impact", "xsys_impact", "consequence"):
            assert e.get(key), (e["id"], key)


def test_the_decision_is_exactly_one_token_and_shadow_mode_is_not_executed():
    tokens = ("SEMANTIC_2_1_READY_FOR_SHADOW", "SEMANTIC_2_1_REQUIRES_FIXES",
              "SEMANTIC_2_1_XSYS_GOVERNANCE_BLOCK",
              "SEMANTIC_2_1_PHASE_C_GOVERNANCE_BLOCK")
    with open(os.path.join(PKG, "PROMOTION_DECISION.md"), encoding="utf-8") as fh:
        text = fh.read()
    decision = text.split("## Decision", 1)[1]
    assert [t for t in tokens if t in decision] == ["SEMANTIC_2_1_READY_FOR_SHADOW"]
    with open(os.path.join(PKG, "SHADOW_MODE_PLAN.md"), encoding="utf-8") as fh:
        assert "PREPARED, NOT EXECUTED" in fh.read()


BANNED = ("no prior work exists", "we are the first", "is the first to",
          "first ever", "no one has", "never been studied", "has never been",
          "no prior art exists")


def test_the_package_documents_exist_and_keep_the_repositorys_wording_rules():
    import re
    want = {"README.md", "OWNER_AUTHORIZATION.md", "SEMANTIC_CORE_2_1.md",
            "VALIDATION_REPORT.md", "PHASE_C_GOVERNANCE_REPORT.md",
            "TEST_MIGRATION.md", "PERFORMANCE.md", "DECISION_TRACE.md",
            "SHADOW_MODE_PLAN.md", "PROMOTION_DECISION.md",
            "PROPOSED_LEDGER_ENTRIES.md"}
    have = {n for n in os.listdir(PKG) if n.endswith(".md")}
    assert have == want
    for name in sorted(want):
        with open(os.path.join(PKG, name), encoding="utf-8") as fh:
            text = fh.read().lower()
        assert not re.search(r"\bnovel\b", text), name
        for phrase in BANNED:
            assert phrase not in text, (name, phrase)


def test_the_performance_record_does_not_claim_an_embedded_result():
    b = _json("PHASE_I_BENCHMARK.json")
    assert "not an embedded measurement" in b["WARNING"]
    assert "does not implement 2.1" in b["WARNING"]
    assert b["retained_memory"]["retained_bytes_after_all_ticks"] == 0
    for stage, slope in b["scaling_padded_tick"]["loglog_slope"].items():
        assert slope < 1.3, (stage, slope)
    for case, v in b["worst_cases"].items():
        assert v["loglog_slope"] < 1.3, (case, v["loglog_slope"])
