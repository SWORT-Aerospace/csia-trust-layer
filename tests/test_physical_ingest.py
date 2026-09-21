"""The additive physical-ingestion layer.

`csia_e2m` already carries 158 tests for acquisition, replay, CRC and
identity. These test only what `csia_physical` adds: the annotation sidecar,
the CSIA input adapter, the evidence schema and the support/capability
schema -- plus the five behavioural properties the brief names, checked
against the layer as assembled.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

import csia_physical                                        # noqa: E402
from csia.aircraft.sample import Quality                     # noqa: E402
from csia_e2m.protocol import (ERR_READBACK_MISMATCH,        # noqa: E402
                               ERR_TIMEOUT, OK, STATUSES)
from csia_e2m.replay import Observation                      # noqa: E402
from csia_physical import annotations as ann                 # noqa: E402
from csia_physical import csia_adapter as ad                 # noqa: E402
from csia_physical import evidence_schema as ev              # noqa: E402
from csia_physical import support_schema as sup              # noqa: E402


class _Identity:
    state = "ASSUMED"


def _obs(record_id=1, host_ns=1000, status=OK, value=1234, sensor="s0",
         commanded=3, readback=3, latency_ns=900, unit="mA"):
    return Observation(record_id=record_id, host_monotonic_ns=host_ns,
                       controller_us=50, sweep=0, sensor=sensor,
                       commanded_channel=commanded, readback_channel=readback,
                       status=status,
                       value_milli=(value if status == OK else None),
                       unit=(unit if status == OK else None),
                       identity=_Identity(), latency_ns=latency_ns)


# --- the package's claims about itself ------------------------------------

def test_no_hardware_was_operated():
    """The single most important flag in the package."""
    assert csia_physical.HARDWARE_OPERATED is False
    assert csia_physical.IS_EXPERIMENTAL is True
    assert csia_physical.REIMPLEMENTS_E2M is False


def test_the_frozen_core_is_untouched():
    import hashlib
    baseline = json.loads((ROOT / "docs/v1/FROZEN_BASELINE.json")
                          .read_text(encoding="utf-8"))
    bad = []
    for rel, want in baseline["files"].items():
        want = want if isinstance(want, str) else want["sha256"]
        if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != want:
            bad.append(rel)
    assert bad == []


def test_no_hardware_interface_reaches_the_frozen_research_packages():
    """`csia_consequence` and `csia_hybrid` must not import serial or i2c."""
    code = (
        "import sys, csia_consequence, csia_hybrid; "
        "print([m for m in sys.modules if m in "
        "('serial','smbus','smbus2','periphery') "
        "or m.startswith('csia_e2m') or m.startswith('csia_physical')])")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", out.stdout


def test_no_forge_code_exists():
    offenders = [p for p in (ROOT / "forge").rglob("*")
                 if p.is_file() and p.suffix != ".md"]
    assert offenders == []
    assert sup.FORGE_COMPATIBILITY_VERIFIED is False


# --- MISSINGNESS NEVER BECOMES ZERO ---------------------------------------

@pytest.mark.parametrize("status",
                         [s for s in STATUSES if s != OK] + ["SOMETHING_NEW"])
def test_missingness_never_becomes_zero(status):
    """The easiest and most damaging mistake an adapter can make.

    On record in `research/evidence_semantics/`: a `-1` sentinel was served
    as `5.00 A`. A missing measurement delivered as `0` is worse than one
    that never arrives, because a relation will consume a zero happily.
    """
    got = ad.adapt(_obs(status=status), channel_name="bench.s0")
    assert got.channel.value is None
    assert got.channel.value != 0
    assert got.channel.missing is not None
    assert got.channel.usable is False


def test_every_protocol_status_has_a_declared_reason():
    """A status the protocol can emit but this adapter has no reason for
    would silently become NOT_QUALIFIED -- a different claim from the one the
    controller made. The first draft of the table guessed status names the
    protocol does not use ("TIMEOUT", "NACK"); this makes that class of
    mistake fail loudly."""
    assert ad.unmapped_statuses() == ()


def test_a_readback_mismatch_is_not_reported_as_not_received():
    """Bytes DID arrive; nobody can say which device sent them. Collapsing
    that into NOT_RECEIVED loses the distinction the mux identity work
    exists to preserve."""
    got = ad.adapt(_obs(status=ERR_READBACK_MISMATCH), channel_name="c")
    assert got.channel.missing is not None
    assert got.channel.missing.value == "NOT_QUALIFIED"


def test_an_unknown_status_is_not_silently_absorbed():
    got = ad.adapt(_obs(status="WHAT_IS_THIS"), channel_name="bench.s0")
    assert got.channel.missing is ad.UNKNOWN_STATUS_REASON


def test_ok_without_a_measurement_is_refused_rather_than_defaulted():
    bad = Observation(record_id=1, host_monotonic_ns=1, controller_us=1,
                      sweep=0, sensor="s0", commanded_channel=0,
                      readback_channel=0, status=OK, value_milli=None,
                      unit="mA", identity=_Identity())
    with pytest.raises(ad.AdapterError, match="refusing to invent"):
        ad.adapt(bad, channel_name="bench.s0")


def test_the_contract_itself_refuses_a_half_populated_channel():
    """The rule is enforced by `ChannelValue`, not reimplemented here."""
    from csia.aircraft.sample import ChannelValue, MissingReason
    with pytest.raises(ValueError, match="exactly one of value/missing"):
        ChannelValue(channel="c", value=0, missing=MissingReason.NOT_RECEIVED)


# --- IDENTITY MISATTRIBUTION ----------------------------------------------

def test_an_undeclared_sensor_is_refused_rather_than_guessed():
    """Inventing a channel name for an unknown device IS misattribution."""
    with pytest.raises(ad.AdapterError, match="refusing to guess"):
        ad.adapt_stream([_obs(sensor="mystery")], naming={"s0": "bench.s0"})


def test_the_commanded_and_readback_channel_are_both_carried():
    """A read is attributable only if both are recorded and can disagree."""
    got = ad.adapt(_obs(commanded=3, readback=5), channel_name="bench.s0")
    assert got.commanded_channel == 3
    assert got.readback_channel == 5
    rec = got.as_record()
    assert rec["commanded_channel"] != rec["readback_channel"]


def test_identity_state_travels_with_the_measurement():
    got = ad.adapt(_obs(), channel_name="bench.s0")
    assert got.identity_state == "ASSUMED"
    assert got.as_record()["identity_state"] == "ASSUMED"


# --- LATENCY AND TIMESTAMPS -----------------------------------------------

def test_latency_is_carried_and_is_not_invented_when_absent():
    assert ad.adapt(_obs(latency_ns=900),
                    channel_name="c").latency_ns == 900
    assert ad.adapt(_obs(latency_ns=None),
                    channel_name="c").latency_ns is None


def test_no_per_record_wall_timestamp_is_ever_emitted():
    """Wall time is a RUN-level fact; the record clock stays monotonic.

    `csia_e2m.logging` uses `time.monotonic_ns` because the wall clock can
    step backwards under NTP mid-run. This layer does not reverse that.
    """
    rec = ad.adapt(_obs(host_ns=12345), channel_name="c").as_record()
    assert rec["host_monotonic_ns"] == 12345
    assert not [k for k in rec if "wall" in k.lower() or "utc" in k.lower()]


def test_wall_time_is_recorded_once_per_run_in_the_sidecar():
    a = ann.RunAnnotation(run_id="r", experiment="E2M-0",
                          wall_start_utc="2026-09-21T13:00:00Z",
                          operator="owner")
    doc = a.as_dict()
    assert doc["wall_start_utc"] == "2026-09-21T13:00:00Z"
    assert doc["wall_time_is_run_level_only"] is True


# --- SEQUENCE GAPS --------------------------------------------------------

def test_a_sequence_gap_is_visible_in_the_raw_record_ids():
    """Gap detection lives in `csia_e2m.logging`; this asserts the adapter
    does not paper over one by renumbering."""
    stream = [_obs(record_id=1), _obs(record_id=2), _obs(record_id=7)]
    got = ad.adapt_stream(stream, naming={"s0": "bench.s0"})
    ids = [g.record_id for g in got]
    assert ids == [1, 2, 7], "record ids must survive adaptation unrenumbered"
    assert ids != list(range(1, 4))


def test_the_e2m_logger_reports_gaps_rather_than_hiding_them(tmp_path):
    from csia_e2m.logging import RunLogger
    from csia_e2m.protocol import Record
    ticks = iter(range(1, 10_000))
    log = RunLogger(path=tmp_path / "r.jsonl", run_id="r", device="fake",
                    baud=115200, clock=lambda: next(ticks) * 1000)
    log.open()
    for seq in (1, 2, 5):
        r = Record(seq=seq, sweep=0, commanded_channel=0,
                   readback_channel=0, sensor="s0", status=OK,
                   milli=1, unit="mA", controller_us=1, i2c_error=0,
                   retries=0)
        log.ingest(r.encode())
    summary = log.close()
    assert summary["sequence_gaps"], "a 2->5 jump must be reported"


# --- ANNOTATIONS ARE A SIDECAR, NOT THE RAW LOG ---------------------------

def test_annotations_never_enter_the_raw_log(tmp_path):
    from csia_e2m.logging import RunLogger
    from csia_e2m.protocol import Record
    ticks = iter(range(1, 10_000))
    log_path = tmp_path / "run.jsonl"
    with RunLogger(path=log_path, run_id="r", device="fake", baud=115200,
                   clock=lambda: next(ticks) * 1000) as log:
        r = Record(seq=1, sweep=0, commanded_channel=0, readback_channel=0,
                   sensor="s0", status=OK, milli=1, unit="mA",
                   controller_us=1, i2c_error=0, retries=0)
        log.ingest(r.encode())
    before = log_path.read_bytes()

    a = ann.RunAnnotation(run_id="r", experiment="E2M-0",
                          wall_start_utc="2026-09-21T13:00:00Z",
                          operator="owner",
                          faults=[ann.FaultAnnotation(
                              label="f", start_host_ns=0, end_host_ns=None,
                              target="ch0", method="pulled the lead",
                              injected_by="owner")])
    side = a.write(ann.annotation_path(log_path))

    assert log_path.read_bytes() == before, "the raw log must be untouched"
    assert side != log_path
    assert "annotations" in side.name
    assert ann.load(side)["is_operator_claim_not_controller_output"] is True


def test_an_annotation_is_not_overwritten(tmp_path):
    a = ann.RunAnnotation(run_id="r", experiment="E2M-0",
                          wall_start_utc="t", operator="o")
    p = tmp_path / "a.json"
    a.write(p)
    with pytest.raises(ann.AnnotationError, match="not overwritten"):
        a.write(p)


def test_ground_truth_must_say_how_it_is_known():
    with pytest.raises(ann.AnnotationError, match="unknown ground-truth"):
        ann.GroundTruth(statement="ch3 is faulty", basis="BECAUSE_I_SAID_SO")


def test_ground_truth_inferred_from_the_data_under_test_is_flagged():
    """Inferring the answer from the data being evaluated is circular, and
    the record says so rather than leaving a reader to notice."""
    honest = ann.GroundTruth(statement="s", basis=ann.BASIS_OPERATOR_ACTION)
    circular = ann.GroundTruth(statement="s", basis=ann.BASIS_INFERRED)
    assert honest.is_independent is True
    assert circular.is_independent is False
    run = ann.RunAnnotation(run_id="r", experiment="e", wall_start_utc="t",
                            operator="o", ground_truth=[honest, circular])
    assert run.as_dict()["ground_truth_all_independent"] is False


def test_a_fault_annotation_needs_a_method():
    with pytest.raises(ann.AnnotationError, match="`method` is required"):
        ann.FaultAnnotation(label="f", start_host_ns=0, end_host_ns=None,
                            target="t", method="", injected_by="o")


def test_the_fault_label_is_joined_by_host_time_not_assumed():
    run = ann.RunAnnotation(
        run_id="r", experiment="e", wall_start_utc="t", operator="o",
        faults=[ann.FaultAnnotation(label="drop", start_host_ns=1000,
                                    end_host_ns=2000, target="ch0",
                                    method="lead pulled", injected_by="o")])
    inside = ad.adapt_stream([_obs(host_ns=1500)],
                             naming={"s0": "c"}, annotation=run)[0]
    outside = ad.adapt_stream([_obs(host_ns=5000)],
                              naming={"s0": "c"}, annotation=run)[0]
    assert inside.fault_label == "drop"
    assert outside.fault_label is None


# --- THE GATES STAY SHUT --------------------------------------------------

def test_qualification_is_blocked_while_the_hardware_gates_are_open():
    with pytest.raises(ad.QualificationBlocked, match="BLOCKED"):
        ad.qualify()


def test_no_channel_may_be_marked_informative():
    with pytest.raises(ad.QualificationBlocked):
        ad.adapt(_obs(), channel_name="c", quality=Quality.INFORMATIVE)


def test_an_adapted_channel_is_never_usable_while_gated():
    got = ad.adapt(_obs(), channel_name="c")
    assert got.channel.quality is ad.MAX_QUALITY_WHILE_GATED
    assert got.channel.usable is False


def test_the_datasheet_gate_still_raises():
    from csia_bus_provenance import datasheet as ds
    assert ds.DATASHEET_STATUS == "NOT_RETRIEVED"
    with pytest.raises(Exception):
        ds.require_verified_datasheet("wire the bus")


def test_the_inventory_declares_no_guessed_device():
    import yaml
    doc = yaml.safe_load((ROOT / "hardware/inventory/e2m_sensors.yaml")
                         .read_text(encoding="utf-8"))
    assert (doc.get("sensors") or []) == [], (
        "gate 2 is open; a populated inventory here would be invented")
    assert doc["mux_address"] is None


# --- RAW AND DERIVED STAY SEPARATE ----------------------------------------

def test_evidence_with_no_derived_from_is_refused():
    with pytest.raises(ev.EvidenceError, match="not a derivation"):
        ev.EvidenceRecord(relation="r", outcome=ev.AGREE,
                          host_monotonic_ns=1, derived_from=(),
                          inputs_admissible=True)


def test_a_conclusion_cannot_be_drawn_from_inadmissible_inputs():
    for outcome in (ev.AGREE, ev.DISAGREE):
        with pytest.raises(ev.EvidenceError, match="INDETERMINATE"):
            ev.EvidenceRecord(relation="r", outcome=outcome,
                              host_monotonic_ns=1, derived_from=(1,),
                              inputs_admissible=False)
    assert ev.indeterminate("r", 1, (1,), "gated").outcome == ev.INDETERMINATE


def test_an_evidence_document_says_it_is_derived_not_observed():
    doc = ev.document([ev.indeterminate("r", 1, (1,), "gated")],
                      run_id="r", experiment="E2M-0")
    assert doc["raw_observations_are_in_a_separate_file"] is True
    assert doc["records"][0]["is_derived_not_observed"] is True
    assert doc["any_admissible"] is False


# --- SUPPORT AND CAPABILITY ------------------------------------------------

def test_support_is_non_identifiable_while_inputs_are_inadmissible():
    adapted = [ad.adapt(_obs(record_id=i), channel_name=f"c{i}")
               for i in (1, 2)]
    s = sup.gated_support(100, ("a", "b"), adapted, run_id="r")
    assert s.status == sup.NON_IDENTIFIABLE
    assert s.reason == sup.R_INPUTS_NOT_ADMISSIBLE
    assert s.active_channels == ()
    assert len(s.inadmissible_channels) == 2
    assert s.as_record()["supports_confident_attribution"] is False


def test_identifiable_cannot_be_claimed_with_an_inadmissible_channel():
    with pytest.raises(sup.SupportError, match="cannot separate"):
        sup.PhysicalSupportState(
            host_monotonic_ns=1, hypotheses=("a", "b"),
            status=sup.IDENTIFIABLE, reason=sup.R_SEPARATED,
            active_channels=("c1",), inadmissible_channels=("c2",),
            derived_from=(1,), run_id="r")


def test_unsupported_capability_is_unknown_not_ineligible():
    s = sup.gated_support(1, ("a", "b"), [], run_id="r")
    cap = sup.capability_from(s, ("nav", "attitude"))
    assert set(cap.states.values()) == {sup.UNKNOWN}
    assert sup.INELIGIBLE not in cap.states.values()


def test_the_capability_record_claims_no_forge_integration():
    s = sup.gated_support(1, ("a",), [], run_id="r")
    rec = sup.capability_from(s, ("nav",)).as_record()
    assert rec["forge_compatibility_verified"] is False
    assert rec["no_forge_code_exists_in_this_repository"] is True
    assert rec["has_actuator_authority"] is False


def test_the_physical_schemas_are_distinct_from_the_simulation_ones():
    """A physical document must not be mistaken for a simulation one."""
    from csia_hybrid.support_view import SupportView
    assert sup.SUPPORT_SCHEMA == "csia.physical.support_state/1"
    assert sup.SUPPORT_SCHEMA != "csia.hybrid.support_view/1"
    assert sup.CAPABILITY_SCHEMA != "csia.hybrid.capability/1"


# --- DETERMINISTIC REPLAY --------------------------------------------------

def test_adaptation_is_deterministic_over_a_replayed_stream():
    stream = [_obs(record_id=i, host_ns=i * 100,
                   status=(OK if i % 3 else ERR_TIMEOUT), value=i)
              for i in range(1, 30)]
    naming = {"s0": "bench.s0"}
    first = [a.as_record() for a in ad.adapt_stream(stream, naming=naming)]
    second = [a.as_record() for a in ad.adapt_stream(stream, naming=naming)]
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second,
                                                           sort_keys=True)


def test_replay_of_a_real_log_is_byte_identical_twice(tmp_path):
    from csia_e2m.logging import RunLogger
    from csia_e2m.protocol import Record
    from csia_e2m.replay import replay
    ticks = iter(range(1, 10_000))
    path = tmp_path / "r.jsonl"
    with RunLogger(path=path, run_id="r", device="fake", baud=115200,
                   clock=lambda: next(ticks) * 1000) as log:
        for seq in range(1, 12):
            r = Record(seq=seq, sweep=0, commanded_channel=seq % 8,
                       readback_channel=seq % 8, sensor="s0",
                       status=(OK if seq % 4 else ERR_TIMEOUT),
                       milli=seq, unit="mA", controller_us=seq,
                       i2c_error=0, retries=0)
            log.ingest(r.encode())
    a = [o.record_id for o in replay(path)]
    b = [o.record_id for o in replay(path)]
    assert a == b and a


# --- SCHEMA VALIDATION ----------------------------------------------------
#
# Every document this layer emits carries a schema identifier, and a consumer
# keys off it. An unpinned schema string can be renamed silently and every
# document becomes unidentifiable while every behavioural test still passes --
# which is exactly what happened: the mutation canary renamed
# `ADAPTER_SCHEMA` and SURVIVED, so the runner aborted rather than reporting
# a score. These tests are why it now dies.

EXPECTED_SCHEMAS = {
    "adapter": (ad.ADAPTER_SCHEMA, "csia.physical.csia_input/1"),
    "annotation": (ann.ANNOTATION_SCHEMA, "csia.physical.run_annotation/1"),
    "evidence": (ev.EVIDENCE_SCHEMA, "csia.physical.evidence/1"),
    "support": (sup.SUPPORT_SCHEMA, "csia.physical.support_state/1"),
    "capability": (sup.CAPABILITY_SCHEMA, "csia.physical.capability/1"),
}


@pytest.mark.parametrize("name", sorted(EXPECTED_SCHEMAS))
def test_every_schema_identifier_is_pinned(name):
    got, want = EXPECTED_SCHEMAS[name]
    assert got == want, (
        f"{name} schema is {got!r}, expected {want!r}. A consumer keys off "
        "this string; renaming it is a breaking change and must be a "
        "deliberate edit here too.")


def test_every_emitted_document_carries_its_schema():
    a = ad.adapt(_obs(), channel_name="c").as_record()
    assert a["schema"] == ad.ADAPTER_SCHEMA

    run = ann.RunAnnotation(run_id="r", experiment="e", wall_start_utc="t",
                            operator="o")
    assert run.as_dict()["schema"] == ann.ANNOTATION_SCHEMA

    e = ev.indeterminate("r", 1, (1,), "gated").as_record()
    assert e["schema"] == ev.EVIDENCE_SCHEMA

    s = sup.gated_support(1, ("a",), [], run_id="r")
    assert s.as_record()["schema"] == sup.SUPPORT_SCHEMA
    assert sup.capability_from(s, ("nav",)).as_record()["schema"] == \
        sup.CAPABILITY_SCHEMA


def test_the_physical_schemas_are_namespaced_apart_from_e2m():
    """`csia_physical` documents must not be mistaken for `csia_e2m` ones."""
    from csia_e2m.logging import LOG_SCHEMA, MANIFEST_SCHEMA
    from csia_e2m.replay import OBSERVATION_SCHEMA
    theirs = {LOG_SCHEMA, MANIFEST_SCHEMA, OBSERVATION_SCHEMA}
    ours = {got for got, _want in EXPECTED_SCHEMAS.values()}
    assert ours.isdisjoint(theirs)
    assert all(s.startswith("csia.physical.") for s in ours)


def test_every_emitted_document_declares_the_hardware_claim():
    """`hardware_operated` is the flag that stops a replay result being read
    as a live-hardware one. Every document carries it."""
    docs = [
        ad.adapt(_obs(), channel_name="c").as_record(),
        ev.indeterminate("r", 1, (1,), "gated").as_record(),
        sup.gated_support(1, ("a",), [], run_id="r").as_record(),
        sup.capability_from(sup.gated_support(1, ("a",), [], run_id="r"),
                            ("nav",)).as_record(),
    ]
    for d in docs:
        assert d["hardware_operated"] is False, d["schema"]
        assert d["is_experimental"] is True, d["schema"]
