"""E2M acquisition: protocol, logging, replay, identity, ancestry, faults.

Hardware-dependent tests SKIP with an explicit reason. A skip is not a pass and
is reported separately; nothing here is evidence that hardware was exercised.
"""
from __future__ import annotations

import hashlib
import json
import re
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

from csia_e2m import ancestry, faults, identity                    # noqa: E402
from csia_e2m.fake_controller import (FakeController, FakeSensor,  # noqa: E402
                                      default_bench)
from csia_e2m.logging import RunExists, RunLogger, verify_run      # noqa: E402
from csia_e2m.protocol import (OK, READBACK_NOT_TAKEN, ProtocolError,  # noqa: E402
                               Record, crc16_ccitt, decode)
from csia_e2m.replay import (ReplayError, check_no_future_leakage,  # noqa: E402
                             replay)


def _clock():
    """Deterministic monotonic clock, 1 ms per tick."""
    state = {"t": 1_000_000_000}

    def tick() -> int:
        state["t"] += 1_000_000
        return state["t"]
    return tick


def _record(**kw) -> Record:
    base = dict(seq=1, sweep=0, commanded_channel=0,
                readback_channel=0, sensor="s0", status=OK, milli=25000,
                unit="milliC", controller_us=1000, i2c_error=0, retries=0)
    base.update(kw)
    return Record(**base)


# --- protocol -------------------------------------------------------------

def test_a_frame_round_trips():
    r = _record()
    assert decode(r.encode()) == r


def test_crc_is_ccitt_false():
    """Pinned against the standard check vector so the firmware's copy of
    these eight lines can be compared against something."""
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_a_single_flipped_character_is_rejected():
    line = _record().encode()
    corrupt = line[:10] + ("9" if line[10] != "9" else "8") + line[11:]
    with pytest.raises(ProtocolError, match="CRC mismatch"):
        decode(corrupt)


def test_a_truncated_frame_does_not_parse_into_a_plausible_reading():
    """A reset mid-write must not produce a record. This is the transport-layer
    form of the evidence-semantics findings."""
    line = _record().encode()
    for cut in (5, 12, len(line) - 3, len(line) - 1):
        with pytest.raises(ProtocolError):
            decode(line[:cut])


def test_readback_not_taken_differs_from_readback_mismatch():
    """Two different facts. Merging them loses the one that matters."""
    not_taken = _record(readback_channel=READBACK_NOT_TAKEN)
    assert not_taken.readback_taken is False
    mismatch = _record(commanded_channel=1, readback_channel=3)
    assert mismatch.readback_taken is True


def test_an_impossible_channel_is_refused():
    with pytest.raises(ProtocolError, match="outside 0..7"):
        _record(commanded_channel=9)
    with pytest.raises(ProtocolError, match="neither 0..7"):
        _record(readback_channel=-7)


def test_a_non_ok_status_carries_no_measurement():
    assert _record(status="ERR_SENSOR_NACK").has_measurement is False
    assert _record(status=OK).has_measurement is True


def test_an_unknown_status_is_not_mapped_onto_a_known_one():
    with pytest.raises(ProtocolError, match="unknown status"):
        _record(status="PROBABLY_FINE")


def test_a_wrong_field_count_is_refused():
    body = "E2M1,1,0,0,0,s0,OK,1,u,1,0"          # eleven fields
    line = f"{body}*{crc16_ccitt(body.encode()):04X}"
    with pytest.raises(ProtocolError, match="fields, expected"):
        decode(line)


# --- logging --------------------------------------------------------------

def test_a_run_is_never_overwritten(tmp_path):
    path = tmp_path / "r.jsonl"
    RunLogger(path=path, run_id="a", device="FAKE", baud=0,
              clock=_clock()).open()
    with pytest.raises(RunExists):
        RunLogger(path=path, run_id="a", device="FAKE", baud=0,
                  clock=_clock()).open()


def test_malformed_frames_are_kept_not_dropped(tmp_path):
    logger = RunLogger(path=tmp_path / "r.jsonl", run_id="a", device="FAKE",
                       baud=0, clock=_clock())
    logger.open()
    assert logger.ingest(_record(seq=1).encode()) is not None
    assert logger.ingest("E2M1,garbage*0000") is None
    manifest = logger.close()
    assert manifest["records"] == 1
    assert manifest["malformed_frames"] == 1
    body = (tmp_path / "r.jsonl").read_text()
    assert "garbage" in body, "the raw bytes of a bad frame must be preserved"


def test_sequence_gaps_are_recorded(tmp_path):
    logger = RunLogger(path=tmp_path / "r.jsonl", run_id="a", device="FAKE",
                       baud=0, clock=_clock())
    logger.open()
    logger.ingest(_record(seq=1).encode())
    logger.ingest(_record(seq=5).encode())
    manifest = logger.close()
    assert manifest["sequence_gaps"][0]["missing"] == 3


def test_the_two_clocks_are_never_merged(tmp_path):
    logger = RunLogger(path=tmp_path / "r.jsonl", run_id="a", device="FAKE",
                       baud=0, clock=_clock())
    logger.open()
    logger.ingest(_record(controller_us=4242).encode())
    logger.close()
    row = [json.loads(x) for x in
           (tmp_path / "r.jsonl").read_text().splitlines()
           if json.loads(x)["type"] == "record"][0]
    assert row["controller_us"] == 4242
    assert row["host_monotonic_ns"] != 4242
    assert isinstance(row["host_monotonic_ns"], int)


def test_an_interrupted_run_is_marked_incomplete(tmp_path):
    logger = RunLogger(path=tmp_path / "r.jsonl", run_id="a", device="FAKE",
                       baud=0, clock=_clock())
    logger.open()
    logger.ingest(_record().encode())
    manifest = logger.close(interrupted=True)
    assert manifest["complete"] is False
    assert manifest["status"] == "INTERRUPTED"


def test_tampering_with_a_closed_raw_log_is_detected(tmp_path):
    path = tmp_path / "r.jsonl"
    logger = RunLogger(path=path, run_id="a", device="FAKE", baud=0,
                       clock=_clock())
    logger.open()
    logger.ingest(_record().encode())
    logger.close()
    assert verify_run(logger.manifest_path)["ok"] is True
    path.write_text(path.read_text().replace("25000", "99999"))
    report = verify_run(logger.manifest_path)
    assert report["ok"] is False
    assert "does not match" in report["reason"]


# --- replay ---------------------------------------------------------------

def _run(tmp_path, controller, sweeps=3, name="r"):
    logger = RunLogger(path=tmp_path / f"{name}.jsonl", run_id=name,
                       device="FAKE", baud=0, clock=_clock())
    logger.open()
    for line in controller.frames(sweeps):
        logger.ingest(line)
    manifest = logger.close()
    return tmp_path / f"{name}.jsonl", manifest


def test_replay_is_deterministic(tmp_path):
    path, _ = _run(tmp_path, FakeController(sensors=default_bench(3)))
    first = [o.as_dict() for o in replay(path)]
    second = [o.as_dict() for o in replay(path)]
    assert first == second
    assert len(first) == 9


def test_missing_is_never_zero(tmp_path):
    """Evidence-semantics finding 2, at the adapter boundary."""
    controller = FakeController(sensors=default_bench(3), silent=("fake_1",))
    path, _ = _run(tmp_path, controller)
    silent = [o for o in replay(path) if o.sensor == "fake_1"]
    assert silent
    for o in silent:
        assert o.observed is False
        assert o.value_milli is None
        assert o.value_milli != 0


def test_replay_refuses_a_backwards_timestamp(tmp_path):
    path = tmp_path / "bad.jsonl"
    rows = [
        {"type": "record", "host_monotonic_ns": 500, "controller_us": 1,
         "seq": 1, "sweep": 0, "commanded_channel": 0, "readback_channel": 0,
         "sensor": "a", "status": OK, "milli": 1, "unit": "u",
         "i2c_error": 0, "retries": 0},
        {"type": "record", "host_monotonic_ns": 100, "controller_us": 2,
         "seq": 2, "sweep": 0, "commanded_channel": 0, "readback_channel": 0,
         "sensor": "a", "status": OK, "milli": 1, "unit": "u",
         "i2c_error": 0, "retries": 0},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ReplayError, match="backwards in host time"):
        list(replay(path))


def test_replay_refuses_a_measurement_with_no_unit(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(
        {"type": "record", "host_monotonic_ns": 1, "controller_us": 1,
         "seq": 1, "sweep": 0, "commanded_channel": 0, "readback_channel": 0,
         "sensor": "a", "status": OK, "milli": 5, "unit": "",
         "i2c_error": 0, "retries": 0}))
    with pytest.raises(ReplayError, match="no unit"):
        list(replay(path))


def test_replay_refuses_an_impossible_channel(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(
        {"type": "record", "host_monotonic_ns": 1, "controller_us": 1,
         "seq": 1, "sweep": 0, "commanded_channel": 12, "readback_channel": 0,
         "sensor": "a", "status": OK, "milli": 5, "unit": "u",
         "i2c_error": 0, "retries": 0}))
    with pytest.raises(ReplayError, match="cannot exist on a TCA9548A"):
        list(replay(path))


def test_no_future_leakage(tmp_path):
    path, _ = _run(tmp_path, FakeController(sensors=default_bench(2)))
    report = check_no_future_leakage(replay(path))
    assert report["ok"] is True
    assert report["observations"] > 0


def test_the_leakage_check_can_fail():
    """Positive control. A check that cannot fail measures nothing (IV-25)."""
    from csia_e2m.replay import Observation
    from csia_e2m.identity import IdentityAssessment, UNOBSERVED
    ident = IdentityAssessment(UNOBSERVED)
    out_of_order = [
        Observation(0, 900, 1, 0, "a", 0, 0, OK, 1, "u", ident),
        Observation(1, 100, 2, 0, "a", 0, 0, OK, 1, "u", ident),
    ]
    report = check_no_future_leakage(out_of_order)
    assert report["ok"] is False
    assert report["violations"]


# --- identity -------------------------------------------------------------

def test_readback_confirmed_does_not_establish_attribution():
    """The owner's §11: a readback bounds the mux control state only."""
    a = identity.assess(commanded_channel=2, readback_channel=2,
                        declared_sensor="baro")
    assert a.state == identity.READBACK_CONFIRMED
    assert a.establishes_attribution is False


def test_assumed_does_not_establish_attribution():
    a = identity.assess(commanded_channel=2, readback_channel=None,
                        declared_sensor=None)
    assert a.state == identity.ASSUMED
    assert a.establishes_attribution is False


def test_only_physical_verification_establishes_attribution():
    assert identity.ESTABLISHES_ATTRIBUTION == frozenset(
        {identity.PHYSICALLY_VERIFIED})
    a = identity.assess(commanded_channel=2, readback_channel=2,
                        declared_sensor="baro",
                        operator_attestation="baro")
    assert a.state == identity.PHYSICALLY_VERIFIED
    assert a.establishes_attribution is True


def test_a_register_disagreement_is_misattribution():
    a = identity.assess(commanded_channel=1, readback_channel=3,
                        declared_sensor="imu_b")
    assert a.state == identity.MISATTRIBUTED
    assert a.contradicted is True


def test_a_native_identity_disagreement_outranks_a_matching_register():
    """The register can be perfect while the wrong part is on the channel."""
    a = identity.assess(commanded_channel=1, readback_channel=1,
                        declared_sensor="imu_b",
                        native_identity="0x19", expected_native_identity="0x68")
    assert a.state == identity.MISATTRIBUTED


def test_operator_and_device_disagreement_is_conflicted_not_resolved():
    a = identity.assess(commanded_channel=1, readback_channel=1,
                        declared_sensor="imu_b", native_identity="0x19",
                        operator_attestation="imu_b")
    assert a.state == identity.CONFLICTED
    assert a.establishes_attribution is False


def test_bus_binding_maps_down_never_up():
    """`VERIFIED` on the bus is not physical verification."""
    state, _ = identity.from_bus_binding("VERIFIED")
    assert state == identity.READBACK_CONFIRMED
    assert state != identity.PHYSICALLY_VERIFIED
    assert identity.from_bus_binding("MISATTRIBUTED")[0] == \
        identity.MISATTRIBUTED
    with pytest.raises(ValueError):
        identity.from_bus_binding("SOMETHING_ELSE")


# --- shared ancestry ------------------------------------------------------

def _lineage(name, channel, **overrides):
    deps = {k: "shared" for k in ancestry.DEPENDENCY_KINDS}
    deps.update(overrides)
    return ancestry.Lineage(sensor=name, channel=channel, dependencies=deps)


def test_three_sensors_on_one_mux_are_one_lineage_not_three():
    report = ancestry.analyse([_lineage("a", 0), _lineage("b", 1),
                               _lineage("c", 2)])
    assert len(report.sensors) == 3
    assert report.independent_lineages == 1
    assert ancestry.corroboration_is_independent(report) is False


def test_two_sensors_sharing_power_keep_a_common_mode_dependency():
    report = ancestry.analyse([
        _lineage("a", 0, controller="uno_a", multiplexer="mux_a"),
        _lineage("b", 1, controller="uno_b", multiplexer="mux_b"),
    ])
    assert ancestry.common_mode_channels(report, "power_rail") is True
    assert ancestry.corroboration_is_independent(report) is False


def test_channel_isolation_does_not_imply_independence():
    """Different channels, everything else shared."""
    report = ancestry.analyse([_lineage("a", 0), _lineage("b", 7)])
    assert report.pairwise[("a", "b")] == frozenset(
        ancestry.DEPENDENCY_KINDS)


def test_fully_separate_benches_are_independent():
    """Positive control: the check can come out the other way."""
    report = ancestry.analyse([
        ancestry.Lineage("a", 0, {k: f"A_{k}" for k in
                                  ancestry.DEPENDENCY_KINDS}),
        ancestry.Lineage("b", 0, {k: f"B_{k}" for k in
                                  ancestry.DEPENDENCY_KINDS}),
    ])
    assert report.shared_by_all == frozenset()
    assert report.independent_lineages == 2
    assert ancestry.corroboration_is_independent(report) is True


def test_a_lineage_may_not_omit_a_dependency_kind():
    with pytest.raises(ValueError, match="omits"):
        ancestry.Lineage("a", 0, {"multiplexer": "m"})


def test_majority_voting_over_one_mux_cannot_confirm_anything():
    """The correlated-fault case, stated as a test rather than a warning."""
    report = ancestry.analyse([_lineage(n, i) for i, n in
                               enumerate("abc")])
    assert ancestry.corroboration_is_independent(report) is False
    assert report.as_dict()["independent_lineages"] == 1
    assert report.as_dict()["sensor_count"] == 3


# --- derived faults -------------------------------------------------------

def test_derived_faults_never_touch_the_raw_log(tmp_path):
    path, manifest = _run(tmp_path, FakeController(sensors=default_bench(3)))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    observations = list(replay(path))
    for name, fn in faults.REGISTRY.items():
        kwargs = {
            "constant_bias": dict(milli=10), "gradual_drift":
                dict(milli_per_sweep=2),
            "freeze": dict(sensor="fake_0", from_sweep=1),
            "dropout": dict(sensor="fake_0", from_sweep=1),
            "delay": dict(ns=1000), "jitter": dict(amplitude_ns=10, seed=1),
            "correlated_bias": dict(milli=5),
            "correlated_drift": dict(milli_per_sweep=1),
        }[name]
        fn(observations, **kwargs)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert after == before == manifest["raw_log_sha256"]


def test_a_derived_dropout_produces_none_not_zero(tmp_path):
    path, _ = _run(tmp_path, FakeController(sensors=default_bench(2)))
    out = faults.dropout(list(replay(path)), sensor="fake_0", from_sweep=1)
    dropped = [o for o in out if o.sensor == "fake_0" and o.sweep >= 1]
    assert dropped
    for o in dropped:
        assert o.value_milli is None and o.observed is False


def test_jitter_is_deterministic_given_a_seed(tmp_path):
    path, _ = _run(tmp_path, FakeController(sensors=default_bench(2)))
    base = list(replay(path))
    a = [o.host_monotonic_ns for o in faults.jitter(base, amplitude_ns=500,
                                                    seed=7)]
    b = [o.host_monotonic_ns for o in faults.jitter(base, amplitude_ns=500,
                                                    seed=7)]
    assert a == b


def test_correlated_faults_move_every_sensor(tmp_path):
    path, _ = _run(tmp_path, FakeController(sensors=default_bench(3)))
    base = list(replay(path))
    out = faults.correlated_bias(base, milli=100)
    moved = {o.sensor for o, b in zip(out, base)
             if o.observed and o.value_milli != b.value_milli}
    assert moved == {"fake_0", "fake_1", "fake_2"}


def test_a_derived_stream_is_tagged_as_not_a_measurement():
    tag = faults.provenance("constant_bias", "abc", {"milli": 1})
    assert tag["is_physical_measurement"] is False
    with pytest.raises(ValueError, match="unknown transform"):
        faults.provenance("wishful_thinking", "abc", {})


# --- the misattribution counterexample, rehearsed in software -------------

def test_a_stuck_channel_yields_a_plausible_value_under_the_wrong_name(
        tmp_path):
    """E2M-2 rehearsed. With no readback the frame looks perfect: status OK,
    a plausible temperature, the expected sensor name -- and the value is the
    neighbour's. This is what the physical arm must reproduce."""
    sensors = [FakeSensor("hot", 0, baseline_milli=80000),
               FakeSensor("cold", 1, baseline_milli=5000)]
    controller = FakeController(sensors=sensors, verify_readback=False,
                                stuck_channel={1: 0})
    path, _ = _run(tmp_path, controller, sweeps=1, name="stuck")
    by_name = {o.sensor: o for o in replay(path)}
    assert by_name["cold"].status == OK
    assert by_name["cold"].value_milli == 80000      # the neighbour's value
    # COMMAND_CONFIRMED, not ASSUMED: the channel write WAS acknowledged --
    # the mux accepted an instruction. That is the trap. The strongest true
    # statement available is about the write, and it says nothing about which
    # part answered.
    assert by_name["cold"].identity.state == identity.COMMAND_CONFIRMED
    assert by_name["cold"].identity.establishes_attribution is False


def test_with_readback_the_same_stuck_channel_is_named(tmp_path):
    sensors = [FakeSensor("hot", 0, baseline_milli=80000),
               FakeSensor("cold", 1, baseline_milli=5000)]
    controller = FakeController(sensors=sensors, verify_readback=True,
                                stuck_channel={1: 0})
    path, _ = _run(tmp_path, controller, sweeps=1, name="stuck2")
    cold = [o for o in replay(path) if o.sensor == "cold"][0]
    assert cold.status == "ERR_READBACK_MISMATCH"
    assert cold.observed is False
    assert cold.identity.state == identity.MISATTRIBUTED


# --- boundaries -----------------------------------------------------------

def test_csia_bus_provenance_still_imports_no_hardware_interface():
    """The owner's §4 requires this boundary survive the change."""
    import ast
    forbidden = {"smbus", "smbus2", "periphery", "serial", "spidev", "RPi",
                 "board", "busio", "adafruit_tca9548a", "gpiozero"}
    offenders = []
    for path in sorted((ROOT / "csia_bus_provenance").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            names = ([a.name for a in node.names]
                     if isinstance(node, ast.Import)
                     else [node.module or ""]
                     if isinstance(node, ast.ImportFrom) else [])
            offenders += [f"{path.name}:{n}" for n in names
                          if n.split(".")[0] in forbidden]
    assert offenders == [], offenders


def test_importing_csia_e2m_pulls_in_no_serial_library():
    """`import serial` is lazy, inside SerialTransport.open()."""
    code = ("import sys; import csia_e2m; "
            "print('serial' in sys.modules or "
            "'serial.tools' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False", out.stdout


def test_no_actuator_or_autopilot_import_anywhere_in_e2m():
    forbidden = {"pymavlink", "mavlink", "dronekit", "px4", "ardupilot",
                 "pyulog"}
    import ast
    offenders = []
    for path in sorted((ROOT / "csia_e2m").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            names = ([a.name for a in node.names]
                     if isinstance(node, ast.Import)
                     else [node.module or ""]
                     if isinstance(node, ast.ImportFrom) else [])
            offenders += [f"{path.name}:{n}" for n in names
                          if n.split(".")[0].lower() in forbidden]
    assert offenders == [], offenders


def test_the_datasheet_gate_still_raises():
    """Permission does not satisfy the datasheet requirement."""
    from csia_bus_provenance import datasheet as ds
    assert ds.DATASHEET_STATUS == "NOT_RETRIEVED"
    with pytest.raises(ds.DatasheetNotVerified):
        ds.require_verified_datasheet("run E2M-1")


def test_the_firmware_refuses_to_build_a_real_driver_today():
    """The real-driver path is an #error, not a stub that silently works."""
    ino = (ROOT / "hardware/arduino/e2m_mux_acquisition"
           / "e2m_mux_acquisition.ino").read_text()
    assert "#  error" in ino or "#    error" in ino
    assert "E2M_MUX_ADDR must be supplied from the verified datasheet" in ino
    assert "No real sensor driver is implemented" in ino

    # Strip comments before looking for actuator code. The firmware's own
    # disclaimer names the things it does not do, and matching prose would
    # make this assertion fire on the sentence promising the opposite.
    code = re.sub(r"/\*.*?\*/", " ", ino, flags=re.S)
    code = re.sub(r"//[^\n]*", " ", code)
    for banned in ("Servo", "analogWrite", "digitalWrite", "Stepper",
                   "attachInterrupt", "tone("):
        assert banned not in code, f"firmware CODE contains {banned}"
    # And the disclaimer must still be there in the prose.
    assert "no servo, motor, ESC, PWM or actuator code" in ino


def test_the_inventory_is_empty_and_valid():
    import yaml
    sys.path.insert(0, str(ROOT / "tools" / "hardware"))
    from validate_inventory import validate
    doc = yaml.safe_load(
        (ROOT / "hardware/inventory/e2m_sensors.yaml").read_text())
    assert doc["sensors"] == []
    assert validate(doc) == []


def test_a_physical_state_cannot_be_claimed_without_a_run_artifact():
    """Positive control for the inventory validator."""
    sys.path.insert(0, str(ROOT / "tools" / "hardware"))
    from validate_inventory import validate
    doc = {"sensors": [{
        "logical_id": "s0", "manufacturer": "m", "part_number": "p",
        "datasheet_path": "d", "i2c_address": 104, "supply_voltage_v": 3.3,
        "logic_voltage_v": 3.3, "measurement_units": "C", "channel": 0,
        "state": "MEASUREMENT_VERIFIED"}]}
    problems = validate(doc)
    assert any("evidence_run is unset" in p for p in problems)


def test_a_fake_run_cannot_establish_a_physical_state(tmp_path):
    """A synthetic run is not a bench run, and the validator says so."""
    sys.path.insert(0, str(ROOT / "tools" / "hardware"))
    from validate_inventory import validate
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"complete": True, "device": "FAKE"}))
    doc = {"sensors": [{
        "logical_id": "s0", "manufacturer": "m", "part_number": "p",
        "datasheet_path": "d", "i2c_address": 104, "supply_voltage_v": 3.3,
        "logic_voltage_v": 3.3, "measurement_units": "C", "channel": 0,
        "state": "DISCOVERED_ON_BUS", "evidence_run": "m.json"}]}
    problems = validate(doc, root=tmp_path)
    assert any("FAKE run" in p for p in problems)


# --- hardware-dependent: skipped, and a skip is not a pass ----------------

def _hardware_present() -> bool:
    try:
        from serial.tools import list_ports
    except ImportError:
        return False
    return any(p.device.startswith(("/dev/ttyACM", "/dev/ttyUSB", "COM"))
               for p in list_ports.comports())


requires_hardware = pytest.mark.skipif(
    not _hardware_present(),
    reason="E2M gate 4: NO_HARDWARE_ACCESS. No /dev/ttyACM*, /dev/ttyUSB* or "
           "COM* port is present. This test is NOT evidence about hardware "
           "and a skip must not be reported as physical validation.")


@requires_hardware
def test_live_controller_emits_decodable_frames():      # pragma: no cover
    raise AssertionError(
        "unreachable in this environment; see E2M_GATE_STATUS.md gate 4")


@requires_hardware
def test_live_register_readback_matches_command():      # pragma: no cover
    raise AssertionError(
        "unreachable in this environment; see E2M_GATE_STATUS.md gate 4")
