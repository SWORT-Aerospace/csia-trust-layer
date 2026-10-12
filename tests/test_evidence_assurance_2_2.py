"""CSIA 2.2 Evidence Assurance and the Flight Assurance Analyzer.

research/csia_2_2_evidence_assurance/ has the design and the evidence. These
tests pin:
- the contract-failure taxonomy;
- every admissibility status;
- the three-monitor IMU regression;
- that rejected evidence cannot reach 2.1.1;
- the E1 regression;
- the CUSUM, PX4 estimator and XSYS witness adapters;
- the profile gate;
- byte-stable reports;
- the governance boundaries.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState as OS
from csia_evidence_assurance import (ADMISSIBLE, CONFIGURATION_MISMATCH, CONTRACT_INVALID,
                                     DUPLICATE, PRODUCER_INVALID, PROFILE_MISMATCH,
                                     REGIME_INVALID, STALE, AnalysisContext, ContractError,
                                     EvidenceEnvelope, FlightAssuranceAnalyzer, Lineage,
                                     LineageError, ProducerContract, ProducerHealth, assess,
                                     independence_groups, independent_lines, load_contracts)
from csia_evidence_assurance import dependence as D
from csia_evidence_assurance import profile_gate as PG
from csia_evidence_assurance import report as R
from csia_evidence_assurance import runs
from csia_evidence_assurance.adapters import cusum as CU
from csia_evidence_assurance.adapters import px4_estimator as PX
from csia_evidence_assurance.adapters import v2_domains as V2
from csia_evidence_assurance.adapters import xsys_witness as XW
from csia_semantic_core.admission import EpochContext

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "csia_evidence_assurance"
RESEARCH = REPO / "research/csia_2_2_evidence_assurance"
AIRCRAFT = V2.AIRCRAFT_BASE
REL = "test.imu_alarm"


# ------------------------------------------------------------------ helpers
def contract(pid="p:test", version="1", cver="c1", relation=REL, domain="SENSOR",
             lineage="PER_OUTPUT", mode="SNAPSHOT", age=None, window=None,
             health="REPORTED", profiles=(AIRCRAFT,), dep=(), attributable=False):
    d = {"schema": "csia.evidence_contract/1", "producer_id": pid,
         "producer_version": version, "contract_version": cver,
         "claims": {"ALARM": {"meaning": "test", "domain": domain, "relation": relation,
                              "attributable": attributable,
                              "config_dependency": list(dep)}},
         "lineage": lineage, "update": {"mode": mode, "period_s": None},
         "validity": {}, "health_reporting": health,
         "profile_compatibility": list(profiles)}
    if age is not None:
        d["validity"]["max_content_age_s"] = age
    if window is not None:
        d["validity"].update({"event_window_s": list(window[1:]), "relative_to": window[0]})
    return ProducerContract.from_dict(d)


def rec(component="source.imu1", state=OS.DEGRADED, relation=REL, domain="SENSOR",
        attributable=False):
    return EvidenceRecord(domain=domain, component=component, relation=relation,
                          source="test", observation_state=state,
                          applicability=Applicability.APPLICABLE, attributable=attributable)


def env(pid="p:test", record=None, lineage=("sensor:imu1",), ct=1.0, pt=1.0,
        health=ProducerHealth.VALID, version="1", cver="c1", claim="ALARM", epoch=None):
    return EvidenceEnvelope(
        producer_id=pid, producer_version=version, contract_version=cver, claim=claim,
        record=record if record is not None else rec(),
        lineage=Lineage.of(*lineage) if isinstance(lineage, tuple) else lineage,
        content_time=ct, producer_health=health, produced_time=pt, config_epoch=epoch)


def status_of(envs, contracts, t=1.0, epochs=None, events=None, base=AIRCRAFT):
    a = assess(envs, contracts, AnalysisContext(t, base, epochs, events or {}))
    return {x.evidence_id: x for x in a.admissions}, a


def one(envelope, c, **kw):
    got, _a = status_of([envelope], {c.producer_id: c}, **kw)
    return next(iter(got.values()))


@pytest.fixture(scope="module")
def aircraft():
    return runs.aircraft_setup()


# ------------------------------------------------------------------ lineage
def test_lineage_is_small_sorted_and_validated():
    a = Lineage.of("sensor:imu1", "model:ekf2", "sensor:imu1")
    assert a.roots == ("model:ekf2", "sensor:imu1")
    assert hash(a) == hash(Lineage.of("model:ekf2", "sensor:imu1"))
    for bad in ((), ("imu1",), ("thing:imu1",), ("sensor:",),
                tuple(f"sensor:s{i}" for i in range(17))):
        with pytest.raises(LineageError):
            Lineage.of(*bad)


def test_independence_is_the_largest_disjoint_set_and_groups_are_components():
    items = [("cusum", Lineage.of("sensor:imu1")), ("kalman", Lineage.of("sensor:imu1")),
             ("threshold", Lineage.of("sensor:imu1")), ("other", Lineage.of("sensor:imu2"))]
    assert independent_lines(items) == (2, True)
    assert independence_groups(items) == [["cusum", "kalman", "threshold"], ["other"]]
    # W_DYN and W_RPM share nothing; W_CTRL joins both: one group, two lines
    chain = [("dyn", XW.lineage("dyn", "motor_0")), ("rpm", XW.lineage("rpm", "motor_0")),
             ("ctrl", XW.lineage("ctrl", "motor_0"))]
    assert len(independence_groups(chain)) == 1
    assert independent_lines(chain) == (2, True)


# ------------------------------------------------------------------ contracts
def test_a_malformed_contract_is_refused_at_load():
    with pytest.raises(ContractError):
        ProducerContract.from_dict({"schema": "other"})
    with pytest.raises(ContractError):
        contract(profiles=())
    with pytest.raises(ContractError):
        contract(mode="SOMETIMES")
    for name in ("cusum_v1_1_sequential", "px4_ekf2_estimator_status", *XW.CONTRACT_FILES):
        assert ProducerContract.load(name).digest()


@pytest.mark.parametrize("case,expect,reason", [
    ("wrong producer version", CONTRACT_INVALID, "PRODUCER_VERSION_MISMATCH"),
    ("wrong contract version", CONTRACT_INVALID, "CONTRACT_VERSION_MISMATCH"),
    ("missing lineage", CONTRACT_INVALID, "MISSING_OR_INVALID_LINEAGE"),
    ("unknown claim", CONTRACT_INVALID, "UNKNOWN_CLAIM"),
    ("claim mapped to another record", CONTRACT_INVALID, "CLAIM_RECORD_MISMATCH"),
    ("profile mismatch", PROFILE_MISMATCH, "NOT_DECLARED_FOR_PROFILE"),
    ("lineage not as declared", CONTRACT_INVALID, "LINEAGE_NOT_AS_DECLARED"),
    ("missing epoch", CONTRACT_INVALID, "MISSING_EPOCH"),
    ("undeclared epoch key", CONTRACT_INVALID, "UNDECLARED_EPOCH_KEY"),
    ("malformed timestamp", CONTRACT_INVALID, "MALFORMED_CONTENT_TIME"),
    ("healthy with impossible metadata", PRODUCER_INVALID, "IMPOSSIBLE_METADATA"),
    ("health not reported", PRODUCER_INVALID, "PRODUCER_HEALTH_NOT_REPORTED"),
    ("producer faulted", PRODUCER_INVALID, "PRODUCER_FAULTED"),
    ("producer unavailable", PRODUCER_INVALID, "PRODUCER_UNAVAILABLE"),
])
def test_contract_failure_taxonomy(case, expect, reason):
    c = contract()
    e = env()
    if case == "wrong producer version":
        e = replace(e, producer_version="2")
    elif case == "wrong contract version":
        e = replace(e, contract_version="c2")
    elif case == "missing lineage":
        e = replace(e, lineage=None)
    elif case == "unknown claim":
        e = replace(e, claim="SOMETHING_ELSE")
    elif case == "claim mapped to another record":
        e = replace(e, record=rec(relation="other.relation"))
    elif case == "profile mismatch":
        c = contract(profiles=("csia/v2/profiles/pump_skid.py",))
    elif case == "lineage not as declared":
        c = contract(lineage=["sensor:imu2"])
    elif case == "missing epoch":
        c = contract(dep=("k",))
    elif case == "undeclared epoch key":
        e = replace(e, config_epoch={"k": 1})
    elif case == "malformed timestamp":
        e = replace(e, content_time=float("nan"))
    elif case == "healthy with impossible metadata":
        e = replace(e, content_time=1.0, produced_time=0.5)
    elif case == "health not reported":
        e = replace(e, producer_health=ProducerHealth.UNKNOWN)
    elif case == "producer faulted":
        e = replace(e, producer_health=ProducerHealth.FAULTED)
    elif case == "producer unavailable":
        e = replace(e, producer_health=ProducerHealth.UNAVAILABLE)
    got = one(e, c)
    assert got.status == expect
    assert any(reason in r for r in got.reasons), got.reasons


def test_degraded_producer_is_admitted_with_a_warning():
    got = one(env(health=ProducerHealth.DEGRADED), contract())
    assert got.status == ADMISSIBLE and got.warnings == ("PRODUCER_DEGRADED",)


def test_impossible_metadata_faults_the_producer_for_the_whole_tick_only():
    c = contract()
    bad = env(record=rec("source.imu1"), ct=1.0, pt=0.5)
    good_same_producer = env(record=rec("source.imu2"), lineage=("sensor:imu2",))
    other = env(pid="p:other", record=rec("source.mag"), lineage=("sensor:mag",))
    got, a = status_of([bad, good_same_producer, other],
                       {"p:test": c, "p:other": contract(pid="p:other")})
    assert got[good_same_producer.evidence_id].status == PRODUCER_INVALID
    assert "PRODUCER_FAULTED_THIS_TICK" in got[good_same_producer.evidence_id].reasons
    assert got[other.evidence_id].status == ADMISSIBLE      # one bad producer, not a failed tick
    assert list(a.producer_faults) == ["p:test"]


def test_in_process_producer_must_be_valid():
    got = one(env(health=ProducerHealth.DEGRADED), contract(health="IN_PROCESS"))
    assert got.status == PRODUCER_INVALID


# ------------------------------------------------------------------ admissibility
def test_stale_regime_duplicate_and_configuration_statuses():
    c = contract(age=0.5)
    assert one(env(ct=0.4, pt=0.4), c).status == STALE
    assert one(env(ct=0.6, pt=0.6), c).status == ADMISSIBLE
    w = contract(window=("onset", 0.0, 0.2))
    assert one(env(ct=0.2), w, t=15.0, events={"onset": 0.0}).status == ADMISSIBLE
    assert one(env(ct=15.0, pt=15.0), w, t=15.0, events={"onset": 0.0}).status == REGIME_INVALID
    assert "VALIDITY_EVENT_UNKNOWN:onset" in one(env(ct=0.2), w, t=15.0).reasons
    # the same output republished under another producer identity
    a, b = env(), env(pid="p:relay")
    got, _ = status_of([a, b], {"p:test": contract(), "p:relay": contract(pid="p:relay")})
    assert sorted(x.status for x in got.values()) == [ADMISSIBLE, DUPLICATE]
    # configuration: 2.1.1's own R-3 decides
    ce = contract(dep=("lane",))
    e = env(epoch={"lane": 0})
    assert one(e, ce, epochs={"lane": 0}).status == ADMISSIBLE
    got = one(e, ce, epochs={"lane": 1})
    assert got.status == CONFIGURATION_MISMATCH and got.reasons[0].startswith("R3:")


def test_withheld_evidence_is_unavailable_or_dropped_never_its_content():
    c = {"p:test": contract(), "p:other": contract(pid="p:other")}
    lone = env(record=rec(state=OS.NOMINAL), health=ProducerHealth.FAULTED)
    _got, a = status_of([lone], c)
    (r,) = a.records
    assert r.observation_state is OS.UNAVAILABLE and r.measured_value is None
    assert r.reason_codes == ("EVIDENCE_INADMISSIBLE_PRODUCER_INVALID",)
    # an admitted record answers the same question: the rejected one is dropped
    ok = env(pid="p:other", record=rec(state=OS.DEGRADED))
    _got, a = status_of([lone, ok], c)
    assert [x.observation_state for x in a.records] == [OS.DEGRADED]


# ------------------------------------------------------------------ three monitors
def test_three_monitor_imu_regression():
    """Phase 14, pinned permanently."""
    cs = {p: contract(pid=p, age=0.5) for p in
          ("thr", "cusum", "kalman", "mon2", "witness", "relay", "ekfa", "ekfb")}
    imu1 = ("sensor:imu1",)
    thr = env("thr", lineage=imu1)
    cus = env("cusum", lineage=imu1 + ("model:cusum",))
    kal = env("kalman", lineage=imu1 + ("model:ekf2",))
    # 1. shared source: three monitors of IMU1 are one line
    _g, a = status_of([thr, cus, kal], cs)
    admitted = [thr, cus, kal]
    assert all(x.status == ADMISSIBLE for x in a.admissions)
    (comp,) = D.corroboration(admitted)
    assert comp["independent_lines"] == 1 and len(comp["producers"]) == 3
    # 2. monitor(IMU1), monitor(IMU2), an independent physical witness: three lines
    m2 = env("mon2", record=rec(), lineage=("sensor:imu2",))
    wit = env("witness", record=rec(), lineage=("sensor:gyro_truth", "model:rigid_body"))
    assert D.corroboration([thr, m2, wit])[0]["independent_lines"] == 3
    # 3. shared model: two IMUs through one estimator are one line
    ea = env("ekfa", lineage=("sensor:imu1", "model:ekf2"))
    eb = env("ekfb", lineage=("sensor:imu2", "model:ekf2"))
    assert D.corroboration([ea, eb])[0]["independent_lines"] == 1
    # 4. duplicate producer: a relay of the threshold's output
    relay = env("relay", lineage=imu1)
    got, a = status_of([thr, relay], cs)
    assert sorted(x.status for x in got.values()) == [ADMISSIBLE, DUPLICATE]
    assert len(a.records) == 1          # the core receives one copy
    # 5. stale producer
    assert one(env("thr", ct=0.2, pt=0.2, lineage=imu1), cs["thr"]).status == STALE
    # 6. faulted producer: its output never reads as healthy
    got, a = status_of([env("thr", record=rec(state=OS.NOMINAL), lineage=imu1,
                            health=ProducerHealth.FAULTED)], cs)
    assert a.records[0].observation_state is OS.UNAVAILABLE
    # 7. different content times: separate ids, each judged on its own age
    early, late = env("thr", ct=0.4, pt=0.4, lineage=imu1), env("thr", ct=0.9, lineage=imu1)
    got, _ = status_of([early, late], cs)
    assert early.evidence_id != late.evidence_id
    assert (got[early.evidence_id].status, got[late.evidence_id].status) == (STALE, ADMISSIBLE)


def test_dependence_never_strengthens_a_verdict(aircraft):
    """Three alarms on one source reach 2.1.1 like one: 2.1.1 never counts."""
    _e, core, gate, _ov = aircraft
    cs = {p: contract(pid=p) for p in ("a", "b", "c")}
    one_alarm = FlightAssuranceAnalyzer(core, cs, gate, AIRCRAFT).step(
        1.0, [env("a", lineage=("sensor:imu1",))])
    three = FlightAssuranceAnalyzer(core, cs, gate, AIRCRAFT).step(
        1.0, [env(p, lineage=("sensor:imu1", f"model:{p}")) for p in "abc"])
    assert one_alarm.attribution == three.attribution
    assert one_alarm.localizations == three.localizations
    assert three.corroboration["overall"]["independent_lines"] == 1


# ------------------------------------------------------------------ Phase 22
def _decision(r):
    return (r.attribution["verdict"], tuple(r.attribution["candidates"]),
            tuple((x["key"], x["outcome"], tuple(x["supported"]), tuple(x["unresolved"]),
                   tuple(e["hypothesis"] for e in x["eliminated"])) for x in r.localizations))


@pytest.mark.parametrize("scenario", ["PROCESS_STALL", "MS_B5_RESPONSE_SENSOR", "SHARED_SOURCE"])
@pytest.mark.parametrize("kind", ["STALE", "FAULTED", "CONTRACT", "PROFILE"])
def test_rejected_evidence_cannot_affect_2_1_1(scenario, kind):
    """Every admitted record gets an inverted twin from a rejected producer.
    The decision must be exactly the decision without the twins."""
    from csia.v2 import scenarios as SC
    from csia.v2.profiles import SCENARIOS, build_engine_for
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed
    from csia_semantic_core import Corrections, SemanticCore21
    from csia_semantic_core.profile_overlay import load_successor
    sc = SCENARIOS[scenario]
    engine = build_engine_for(sc)
    res = SC.run(engine, sc, ticks=40, payload_for=example_payload_feed("clean"))
    ov = load_successor("aircraft_successor_r2")
    core = SemanticCore21.from_engine(engine, Corrections.revised(), pacing=ov.pacing_map())
    gate = PG.gate(ov, res[0].records, engine.functions)
    contracts = V2.legacy_contracts(engine, AIRCRAFT)
    sa = res[-1]
    base = V2.envelopes(ov.apply(sa.records), sa.t, contracts)
    flip = {OS.NOMINAL: OS.VIOLATED, OS.VIOLATED: OS.NOMINAL, OS.DEGRADED: OS.NOMINAL}
    twins, tc = [], {}
    for e in base:
        st = flip.get(e.record.observation_state)
        if st is None:
            continue
        pid = "rogue:" + e.producer_id
        if pid not in tc:
            c = contracts[e.producer_id].raw
            d = dict(c, producer_id=pid, health_reporting="REPORTED",
                     validity={"max_content_age_s": 0.01} if kind == "STALE" else {},
                     profile_compatibility=(["other/profile.py"] if kind == "PROFILE"
                                            else c["profile_compatibility"]))
            tc[pid] = ProducerContract.from_dict(d)
        twins.append(replace(e, producer_id=pid, record=replace(e.record, observation_state=st),
                             content_time=e.content_time - (1.0 if kind == "STALE" else 0.0),
                             producer_health=(ProducerHealth.FAULTED if kind == "FAULTED"
                                              else ProducerHealth.VALID),
                             contract_version=("bogus" if kind == "CONTRACT"
                                               else e.contract_version)))
    assert twins
    clean = FlightAssuranceAnalyzer(core, contracts, gate, AIRCRAFT).step(sa.t, base)
    dirty = FlightAssuranceAnalyzer(core, {**contracts, **tc}, gate, AIRCRAFT).step(
        sa.t, base + twins)
    assert _decision(dirty) == _decision(clean)
    assert len(dirty.evidence["rejected"]) == len(twins)
    assert dirty.evidence["used"] == clean.evidence["used"]
    # alone, rejected evidence still cannot speak: with the originals removed,
    # the twins' content (inverted or not) makes no difference
    twinned = {(e.record.relation, e.record.component) for e in twins}
    rest = [e for e in base if (e.record.relation, e.record.component) not in twinned]
    same = [replace(t, record=replace(t.record, observation_state=o.record.observation_state))
            for t, o in zip(twins, [e for e in base if flip.get(e.record.observation_state)])]
    inverted = FlightAssuranceAnalyzer(core, {**contracts, **tc}, gate, AIRCRAFT).step(
        sa.t, rest + twins)
    original = FlightAssuranceAnalyzer(core, {**contracts, **tc}, gate, AIRCRAFT).step(
        sa.t, rest + same)
    assert _decision(inverted) == _decision(original)


def test_the_corpus_reaches_2_1_1_unchanged_through_2_2():
    """Phase 28 on a sample of every system: 2.2 rejects nothing in the
    frozen corpus and its decisions are 2.1.1's (the full 44-scenario replay
    is in the research package)."""
    from csia.v2 import scenarios as SC
    from csia.v2.profiles import SCENARIOS, build_engine_for
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed
    from csia_semantic_core import Corrections, SemanticCore21
    from csia_semantic_core.profile_overlay import load_successor
    for name in ("NOMINAL", "PROCESS_STALL", "MS_B4_MECHANICAL", "CLOCK_DRIFT",
                 "PS_SUPPLY_SAG", "TS_STALLED"):
        sc = SCENARIOS[name]
        engine = build_engine_for(sc)
        feed = example_payload_feed("clean") if sc.system == "aircraft" else None
        res = SC.run(engine, sc, ticks=30, payload_for=feed)
        ov = load_successor(V2.SUCCESSOR[sc.system]) if sc.system in V2.SUCCESSOR else None
        base = V2.PROFILE_BASE[sc.system]
        contracts = V2.legacy_contracts(engine, base)
        core = SemanticCore21.from_engine(engine, Corrections.revised(),
                                          pacing=ov.pacing_map() if ov else None)
        an = FlightAssuranceAnalyzer(core, contracts, PG.gate(ov, res[0].records,
                                                              engine.functions), base)
        for sa in res:
            recs = ov.apply(sa.records) if ov else sa.records
            r = an.step(float(sa.t), V2.envelopes(recs, sa.t, contracts))
            d = core.reason(recs)
            assert not r.evidence["rejected"], name
            assert (r.attribution["verdict"], tuple(r.attribution["candidates"])) == \
                (d.attribution.verdict, tuple(d.attribution.candidates)), name
            assert [(x["key"], x["outcome"], x["supported"], x["unresolved"])
                    for x in r.localizations] == \
                [(x.key, x.outcome, list(x.supported), list(x.unresolved))
                 for x in d.localizations], name


# ------------------------------------------------------------------ E1
def test_e1_through_2_2_is_a_permanent_regression():
    sys.path.insert(0, str(RESEARCH))
    import e1_2_2
    r = e1_2_2.run()["result"]
    assert r["stale_position_symptom_ticks"] == 0
    assert r["missed_position_symptom_ticks"] == 0
    assert r["recovery_tick"] == 25
    assert r["per_tick_equal_to_revision_REVISED_2_1_1_R2"] is True
    assert r["pre_2_1_0_stale_position_symptom_ticks"] == 9
    assert r["config_mismatch_ticks"] == 9
    assert r["other_rejections"] == 0      # nothing valid is refused


# ------------------------------------------------------------------ CUSUM
def test_cusum_adapter_wraps_the_frozen_bank_and_states_coverage():
    from csia.v1_1 import sequential as SEQ
    assert CU.frozen_version() == ProducerContract.load("cusum_v1_1_sequential").producer_version
    cov = {c["source"] for c in CU.coverage_notices()}
    assert cov == {"source.imu0", "source.imu1", "source.baro"}
    p = CU.CusumProducer()
    out = p.step(0.0, {"battery": (1.0, 1.0), "gps": (1.0, 0.0)}, {"battery": True, "gps": True})
    by = {e.record.component: e for e in out}
    assert set(by) == {"source.battery", "source.gps"}
    assert by["source.gps"].producer_health is ProducerHealth.UNAVAILABLE   # gated out
    assert not any(e.record.component == "source.imu0" for e in out)
    assert all(e.record.attributable is False for e in out)
    (e,) = [e for e in p.step(0.1, {"battery": (float("inf"), 1.0)}, {"battery": True})]
    assert e.producer_health is ProducerHealth.FAULTED
    # a payload computed with other constants is not the frozen detector
    (other,) = CU.from_v1_1_payload({"sequential": {"k": 0.25, "h": SEQ.CUSUM_H,
                                                    "covered_nodes": ["battery"]},
                                     "evidence": {"fresh": {"battery": True}}})
    assert one(other, load_contracts("cusum_v1_1_sequential")[CU.PRODUCER_ID]).status == \
        CONTRACT_INVALID


def test_cusum_alarms_that_share_a_source_are_one_line():
    lins = {n: CU.node_lineage(n) for n in ("battery", "motor_esc", "vibration")}
    assert all("sensor:motor_esc" in lin.roots for lin in lins.values())
    assert independent_lines(list(lins.items())) == (1, True)


# ------------------------------------------------------------------ PX4 estimator
def _two_lane_log(switch_us=1_005_000, end_us=2_000_000):
    flags = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 9) | (1 << 44)
    status = {}
    for inst, gyro in ((0, 111), (1, 222)):
        ts = np.arange(0, end_us + 1, 10_000, dtype=np.int64)
        n = len(ts)
        d = {k: np.zeros(n) for k in PX.STATUS_FIELDS}
        d.update(timestamp=ts, timestamp_sample=ts - 150_000,
                 control_mode_flags=np.full(n, flags, dtype=np.uint64),
                 gyro_device_id=np.full(n, gyro), accel_device_id=np.full(n, gyro),
                 baro_device_id=np.full(n, 7), mag_device_id=np.full(n, 9),
                 pos_test_ratio=np.full(n, 0.1), vel_test_ratio=np.full(n, 0.1),
                 hgt_test_ratio=np.full(n, 0.1), hdg_test_ratio=np.full(n, np.nan))
        status[inst] = d
    sel = {"timestamp": np.array([0, switch_us], dtype=np.int64),
           "primary_instance": np.array([0, 1]), "instance_changed_count": np.array([1, 2])}
    return PX.EstimatorLog(status, sel, {"SENS_IMU_MODE": 0}, "547e2caa98", 0)


def test_estimator_lane_switch_epoch_pin(aircraft):
    """Phase 19: old-lane evidence becomes stale, new-lane evidence is
    admissible, unrelated evidence survives."""
    _e, core, gate, _ov = aircraft
    est = PX.EstimatorProducer(_two_lane_log())
    cs = load_contracts("px4_ekf2_estimator_status", "cusum_v1_1_sequential")
    an = FlightAssuranceAnalyzer(core, cs, gate, AIRCRAFT)
    cusum = CU.CusumProducer()

    def tick(t):
        envs = est.step(t) + cusum.step(t, {"battery": (1.0, 1.0)}, {"battery": True})
        cur, ev = est.context(t)
        return an.step(t, envs, epochs=EpochContext(cur, ev))

    before = tick(1.0)
    assert {x["producer_id"] for x in before.evidence["rejected"]} == set()
    during = tick(1.007)            # the selector has switched; lane 1 has not published
    stale = [x for x in during.evidence["rejected"] if x["producer_id"] == PX.PRODUCER_ID]
    assert len(stale) == 4 and all(x["status"] == CONFIGURATION_MISMATCH for x in stale)
    assert any(e.startswith(CU.PRODUCER_ID) for e in during.evidence["used"])  # unrelated
    assert during.configuration["epochs"][PX.LANE_KEY] in ([2], 2)
    after = tick(1.02)
    used = [e for e in after.evidence["used"] if e.startswith(PX.PRODUCER_ID)]
    assert len(used) == 4 and not after.evidence["rejected"]
    held = an.store[(PX.PRODUCER_ID, "INNOVATION_POS",
                     "COMPUTE/state_estimator:estimator.innovation.pos")]
    assert held.record.detail["instance"] == 1 and "sensor:imu.222" in held.lineage.roots


def test_estimator_claims_health_and_missing_selector():
    log = _two_lane_log()
    log.status[0]["filter_fault_flags"][50:] = 1 << 12
    est = PX.EstimatorProducer(log)
    out = {e.claim: e for e in est.step(0.3)}
    assert out["INNOVATION_POS"].record.observation_state is OS.NOMINAL
    assert out["INNOVATION_HDG"].record.observation_state is OS.NOT_APPLICABLE
    assert out["INNOVATION_POS"].content_time == pytest.approx(0.15)
    assert out["INNOVATION_POS"].produced_time == pytest.approx(0.3)
    assert "sensor:gnss" in out["INNOVATION_POS"].lineage.roots
    assert "sensor:baro.7" in out["INNOVATION_HGT"].lineage.roots
    assert all(e.producer_health is ProducerHealth.FAULTED for e in est.step(0.6))
    # over the gate
    log = _two_lane_log()
    log.status[0]["vel_test_ratio"][:] = 1.5
    (v,) = [e for e in PX.EstimatorProducer(log).step(0.3) if e.claim == "INNOVATION_VEL"]
    assert v.record.observation_state is OS.VIOLATED and v.record.attributable is False
    # the selector should run but is not logged: refused, with a notice
    log = _two_lane_log()
    log.selector = None
    est = PX.EstimatorProducer(log)
    assert est.coverage_notices()
    c = load_contracts("px4_ekf2_estimator_status")
    got, _ = status_of(est.step(0.3), c, t=0.3)
    assert {x.status for x in got.values()} == {CONTRACT_INVALID}
    assert all(any("MISSING_EPOCH" in r for r in x.reasons) for x in got.values())
    # single instance (SENS_IMU_MODE=1): the lane is 0 by construction
    log = _two_lane_log()
    log.params = {"SENS_IMU_MODE": 1}
    log.status.pop(1)
    log.selector = None
    est = PX.EstimatorProducer(log)
    envs = est.step(0.3)
    cur, _ev = est.context(0.3)
    got, _ = status_of(envs, c, t=0.3, epochs=cur)
    assert {x.status for x in got.values()} == {ADMISSIBLE} and cur[PX.LANE_KEY] == 0


def test_uint8_reset_counters_are_unwrapped_as_context():
    log = _two_lane_log()
    log.params = {"SENS_IMU_MODE": 1}
    log.status.pop(1)
    log.selector = None
    log.status[0]["reset_count_pos_ne"] = (np.arange(len(log.status[0]["timestamp"])) % 256)
    est = PX.EstimatorProducer(log)
    cur, _ = est.context(2.0)
    assert cur["ekf2.reset.reset_count_pos_ne"] == 200      # 0..200, no wrap lost
    log.status[0]["reset_count_pos_ne"] = np.where(np.arange(201) < 100, 254, 1)
    cur, _ = PX.EstimatorProducer(log).context(2.0)
    assert cur["ekf2.reset.reset_count_pos_ne"] == 3         # 254 -> 1 across the wrap


# ------------------------------------------------------------------ XSYS witnesses
def _xsys_a_trial():
    key = runs.xsys_key()["trials"]
    data = json.loads((XW.CAMPAIGN / "stage1/STAGE1.json").read_text())
    oid = next(o for o, k in sorted(key.items()) if k["kind"] == "A"
               and data["trials"][o]["features"]["motor_0"]["dyn_T3_invalid"] is not None
               and data["trials"][o]["features"]["motor_0"]["dyn_T1"] is not None)
    return data["trials"][oid]["features"]["motor_0"]


def test_xsys_witness_validity_is_the_validated_window():
    f = _xsys_a_trial()
    cs = load_contracts(*XW.CONTRACT_FILES)
    ev, base = {XW.ONSET: 0.0}, "research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py"
    v3 = {e.producer_id: e for e in XW.envelopes("motor_0", f, "V3_TEMPORAL", "C3")}
    got, _ = status_of(list(v3.values()), cs, t=15.0, events=ev, base=base)
    assert {x.status for x in got.values()} == {ADMISSIBLE}
    assert v3["xsys:w_dyn"].content_time == pytest.approx(0.2)   # T1, 14.8 s old, valid
    v4 = {e.producer_id: e for e in XW.envelopes("motor_0", f, "V4_INVALID_WINDOW", "C3")}
    got, a = status_of(list(v4.values()), cs, t=15.0, events=ev, base=base)
    assert got[v4["xsys:w_dyn"].evidence_id].status == REGIME_INVALID
    assert got[v4["xsys:w_rpm"].evidence_id].status == ADMISSIBLE
    dyn = [r for r in a.records if r.relation == "xsys.dynamics_T1"]
    assert dyn[0].observation_state is OS.UNAVAILABLE


def test_xsys_witness_records_are_the_frozen_adapters():
    S1, XA, _XF = XW.pipeline()
    f = _xsys_a_trial()
    rpm, dyn, ctrl, w = S1.plan("V3_TEMPORAL", "C3", f)
    want = XA.records_for("motor_0", rpm, dyn, ctrl,
                          {"L": f["L_T3"], "D": f["D_T1"], "C": f["C_T3"]}, w)
    got = [e.record for e in XW.envelopes("motor_0", f, "V3_TEMPORAL", "C3")]
    assert sorted(got, key=lambda r: r.relation) == sorted(want, key=lambda r: r.relation)


# ------------------------------------------------------------------ profile gate
def test_profile_gate(aircraft, tmp_path):
    from csia_semantic_core.profile_overlay import load_successor
    _e, core, gate, ov = aircraft
    assert gate.status == "ACCEPTED" and gate.warnings()
    assert {f[1] for f in gate.findings} >= {"PV2_DEAD_SUPPORTING_DOMAIN"}
    # approval condition 1: a pacing declaration without a citation is an ERROR
    empty = tmp_path / "c.json"
    empty.write_text(json.dumps({"schema": "csia.pacing_citations/1", "profiles": {}}))
    assert PG.pacing_citation_findings(load_successor("aircraft_successor_r2"), empty)[0][1] \
        == "PG1_PACING_WITHOUT_CITATION"
    refused = PG.GateResult("REFUSED", gate.profile, (("ERROR", "PG1_PACING_WITHOUT_CITATION",
                                                       "state_estimator", ""),))
    r = FlightAssuranceAnalyzer(core, {}, refused, AIRCRAFT).step(1.0, [env()])
    assert r.state["attribution"] == "PROFILE_REFUSED" and r.localizations == ()
    na = PG.not_applicable("spec", "x.py", "no function table")
    assert na.accepted and na.findings[0][0] == "INFO"


# ------------------------------------------------------------------ reports
def test_reports_are_byte_stable_and_carry_no_probabilities():
    a = runs.v2_scenario("PROCESS_STALL", ticks=30)
    b = runs.v2_scenario("PROCESS_STALL", ticks=30)
    ma = R.machine_report(a.results, a.inputs, a.gate, a.contracts)
    mb = R.machine_report(b.results, b.inputs, b.gate, b.contracts)
    assert R.dumps(ma) == R.dumps(mb)
    assert ma["intervals"] < ma["ticks"]
    assert [iv["changed"] for iv in ma["timeline"]][0] == ["start"]
    text = R.human_report(ma)
    assert "%" not in text and not re.search(r"\b(probab|confiden|likel)", text, re.I)
    assert "OUTPUT_MISSING" in text and "UNIQUE" in text
    assert R.dumps({"x": 0.1 + 0.2, "y": [3, 1]}) == b'{\n "x": 0.3,\n "y": [\n  3,\n  1\n ]\n}\n'


def test_timeline_collapses_stable_intervals():
    run = runs.v2_scenario("NOMINAL", ticks=20)
    tl = R.timeline(run.results)
    assert len(tl) == 1 and tl[0]["ticks"] == 20


# ------------------------------------------------------------------ governance
def test_nothing_in_csia_imports_2_2_and_2_2_never_attributes_unsupported():
    for p in (REPO / "csia").rglob("*.py"):
        assert "csia_evidence_assurance" not in p.read_text(), p
    for p in PKG.rglob("*.py"):
        assert "attribute_unsupported" not in p.read_text(), p


def test_no_frozen_artifact_changed_since_the_2_1_1_baseline():
    sys.path.insert(0, str(RESEARCH))
    import common_2_2 as C
    out = subprocess.run(["git", "diff", "--name-only", C.REVISION_HEAD, "--",
                          "csia", "csia_semantic_core", "research/csia_semantic_core_2_1",
                          "research/csia_semantic_core_2_1_shadow",
                          "research/csia_semantic_core_2_1_revision",
                          "research/csia_semantic_correctness",
                          "research/xsys_confirmatory_001", "research/xsys_001_confirmatory_campaign",
                          "engineering/v2"],
                         cwd=REPO, capture_output=True, text=True).stdout.split()
    assert out == []
    assert C.sha(REPO / "research/physical_validation/FAILURE_LEDGER.yaml") == C.LEDGER_PINNED


def test_contracts_on_disk_are_what_the_adapters_declare():
    for name, d in XW.contracts_dict().items():
        on_disk = json.loads((PKG / f"contracts/xsys_w_{name}.json").read_text())
        assert on_disk == json.loads(json.dumps(d))
    px = json.loads((PKG / "contracts/px4_ekf2_estimator_status.json").read_text())
    assert set(px["claims"]) == set(PX.CLAIMS)
    for c, spec in px["claims"].items():
        assert spec["relation"] == PX.relation(c)
        assert tuple(spec["config_dependency"]) == PX.claim_keys(c)
    assert math.isclose(px["validity"]["max_content_age_s"], 0.4)
