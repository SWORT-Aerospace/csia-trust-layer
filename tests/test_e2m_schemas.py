"""E2M artifacts validated against the schemas that claim to describe them.

`schemas/e2m/` was committed with nothing validating against it, which makes a
schema documentation wearing a contract's clothes. These tests make it a
contract: real artifacts produced by the real logger and the real replay path
are validated, and deliberately-broken ones must be rejected.

WHERE A SCHEMA LOOKS WRONG, IT IS REPORTED AND NOT QUIETLY WIDENED.
Every rejection case below fails against the schema as committed. Nothing in
this file edits a schema to make an example pass -- if one needed that, the
correction would be proposed separately, because a schema edited to accept its
own counterexample tests nothing.
"""
from __future__ import annotations

import copy
import json
import pathlib

import jsonschema
import pytest

from csia_e2m.fake_controller import FakeController, default_bench
from csia_e2m.logging import RunLogger
from csia_e2m.replay import replay

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas/e2m"


def _schema(name):
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text())


RAW = _schema("raw_bus_observation")
MANIFEST = _schema("run_manifest")
FAULT = _schema("fault_event")


def _clock():
    state = {"t": 1_000_000_000}

    def tick():
        state["t"] += 1_000_000
        return state["t"]
    return tick


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("schema")
    logger = RunLogger(path=tmp / "r.jsonl", run_id="schema-1", device="FAKE",
                       baud=0, clock=_clock())
    logger.open()
    for line in FakeController(sensors=default_bench(3)).frames(3):
        logger.ingest(line)
    manifest = logger.close()
    return tmp / "r.jsonl", manifest


# --- the schemas themselves ----------------------------------------------

def test_every_schema_is_itself_a_valid_json_schema():
    for name in ("raw_bus_observation", "run_manifest", "fault_event"):
        jsonschema.Draft202012Validator.check_schema(_schema(name))


# --- real artifacts validate ---------------------------------------------

def test_every_recorded_observation_validates(run):
    path, _ = run
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln]
    records = [r for r in rows if r.get("type") == "record"]
    assert records, "the fixture produced no records to validate"
    for record in records:
        jsonschema.validate(record, RAW)


def test_the_manifest_validates(run):
    _, manifest = run
    jsonschema.validate(manifest, MANIFEST)


def test_replay_output_carries_the_fields_downstream_needs(run):
    path, _ = run
    for observation in replay(path):
        payload = observation.as_dict()
        for field in ("record_id", "host_monotonic_ns", "sensor", "status",
                      "observed", "value_milli", "identity"):
            assert field in payload
        assert payload["identity"]["state"] in (
            "UNOBSERVED", "ASSUMED", "COMMAND_CONFIRMED", "READBACK_CONFIRMED",
            "TOPOLOGY_DECLARED", "PHYSICALLY_VERIFIED", "MISATTRIBUTED",
            "CONFLICTED")


# --- rejections: each must fail against the schema AS COMMITTED -----------

def _a_record(**overrides):
    base = {"type": "record", "host_monotonic_ns": 1000, "controller_us": 5,
            "seq": 1, "sweep": 0, "commanded_channel": 3,
            "readback_channel": 3, "readback_taken": True, "sensor": "s0",
            "status": "OK", "has_measurement": True, "milli": 25000,
            "unit": "milliC", "i2c_error": 0, "retries": 0,
            "raw": "E2M1,...*ABCD"}
    base.update(overrides)
    return base


def test_the_baseline_record_is_actually_valid():
    """Positive control. If this failed, every rejection below would pass
    for the wrong reason."""
    jsonschema.validate(_a_record(), RAW)


@pytest.mark.parametrize("field", ["type", "host_monotonic_ns",
                                   "controller_us", "seq", "sweep",
                                   "commanded_channel", "readback_channel",
                                   "readback_taken", "sensor", "status",
                                   "has_measurement", "raw"])
def test_a_missing_required_field_is_rejected(field):
    record = _a_record()
    del record[field]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, RAW)


@pytest.mark.parametrize("field,bad", [
    ("host_monotonic_ns", "not-an-int"),
    ("controller_us", 1.5),
    ("seq", "1"),
    ("sweep", None),
    ("commanded_channel", "3"),
    ("has_measurement", "true"),
    ("raw", 42),
    ("sensor", 7),
])
def test_a_wrong_type_is_rejected(field, bad):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_a_record(**{field: bad}), RAW)


@pytest.mark.parametrize("channel", [-1, 8, 9, 255])
def test_an_invalid_commanded_channel_is_rejected(channel):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_a_record(commanded_channel=channel), RAW)


@pytest.mark.parametrize("channel", [-2, 8, 99])
def test_an_invalid_readback_channel_is_rejected(channel):
    """-1 is legal and means 'not read back'. -2 and 8 are not."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_a_record(readback_channel=channel), RAW)


def test_minus_one_readback_is_accepted_because_it_means_not_taken():
    jsonschema.validate(_a_record(readback_channel=-1, readback_taken=False),
                        RAW)


def test_a_negative_sequence_number_is_rejected():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_a_record(seq=-1), RAW)


def test_an_unknown_status_is_rejected():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_a_record(status="PROBABLY_FINE"), RAW)


# --- manifest rejections --------------------------------------------------

def _a_manifest(**overrides):
    base = {"schema": "csia.e2m.run_manifest/1", "run_id": "r",
            "experiment": "E2M-0", "complete": True, "status": "CLOSED",
            "raw_log": "r.jsonl", "raw_log_sha256": "a" * 64,
            "device": "FAKE", "baud": 0, "records": 1,
            "malformed_frames": 0, "sequence_gaps": []}
    base.update(overrides)
    return base


def test_the_baseline_manifest_is_valid():
    jsonschema.validate(_a_manifest(), MANIFEST)


@pytest.mark.parametrize("digest", ["", "abc", "A" * 64, "z" * 64,
                                    "a" * 63, "a" * 65])
def test_a_malformed_digest_is_rejected(digest):
    """Upper-case hex is rejected too: the manifest is compared byte-for-byte
    against `sha256_file` output, which is lower-case."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_a_manifest(raw_log_sha256=digest), MANIFEST)


def test_an_unknown_run_status_is_rejected():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_a_manifest(status="PROBABLY_DONE"), MANIFEST)


@pytest.mark.parametrize("field", ["schema", "run_id", "complete", "status",
                                   "raw_log_sha256", "device", "records"])
def test_a_manifest_missing_a_required_field_is_rejected(field):
    manifest = _a_manifest()
    del manifest[field]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(manifest, MANIFEST)


# --- fault annotations ----------------------------------------------------

def test_a_derived_fault_annotation_validates():
    jsonschema.validate({"schema": "csia.e2m.derived_stream/1",
                         "kind": "derived", "transform": "constant_bias",
                         "parameters": {"milli": 10},
                         "derived_from_raw_log_sha256": "b" * 64,
                         "is_physical_measurement": False}, FAULT)


def test_a_physical_fault_without_an_operator_annotation_is_rejected():
    """The conditional requirement in the schema: a PHYSICAL fault event has
    to say what the operator actually did, or it is unreconstructable."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"schema": "csia.e2m.derived_stream/1",
                             "kind": "physical",
                             "is_physical_measurement": True}, FAULT)


def test_a_physical_fault_with_an_annotation_validates():
    jsonschema.validate({"schema": "csia.e2m.derived_stream/1",
                         "kind": "physical", "is_physical_measurement": True,
                         "operator_annotation":
                             "disconnected SDA on channel 1"}, FAULT)


def test_an_unknown_transform_is_rejected():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"schema": "csia.e2m.derived_stream/1",
                             "kind": "derived",
                             "transform": "wishful_thinking",
                             "is_physical_measurement": False}, FAULT)


def test_an_unknown_kind_is_rejected():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"schema": "csia.e2m.derived_stream/1",
                             "kind": "imaginary",
                             "is_physical_measurement": False}, FAULT)


def test_every_registered_transform_is_permitted_by_the_schema():
    """The code and the schema must agree on the transform vocabulary, or one
    of them is describing software that does not exist."""
    from csia_e2m import faults
    allowed = set(FAULT["properties"]["transform"]["enum"])
    assert set(faults.TRANSFORMS) == allowed
    assert set(faults.REGISTRY) == allowed


def test_mutating_a_valid_artifact_field_by_field_is_caught(run):
    """Broad sweep: for each field in a real record, a type-violating value
    must be rejected. Guards against a schema that validates only the fields
    somebody remembered to test."""
    path, _ = run
    record = next(json.loads(ln) for ln in path.read_text().splitlines()
                  if ln and json.loads(ln).get("type") == "record")
    jsonschema.validate(record, RAW)
    for field, value in record.items():
        if not isinstance(value, (int, bool, str)):
            continue
        broken = copy.deepcopy(record)
        broken[field] = {"unexpected": "object"}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(broken, RAW)
