"""S9 flight log: complete provenance, non-fatal failure, honest disagreement.

The log is the entire deliverable of a shadow flight. If it is incomplete, the
flight produced nothing; if writing it can stall the runtime, it is a hazard
rather than a record.
"""

import glob
import json
import os

import numpy as np

from csia.aircraft.adapters import get_adapter
from csia.aircraft.sample import (AircraftSample, ChannelValue, MissingReason,
                                  Quality, SensorFrame)
from csia.deploy.flight_log import FlightLog, make_header
from csia.deploy.shadow import Mode, ShadowConfig, ShadowRunner


def a_sample():
    s = AircraftSample(t_mono=1.0, flight_mode="LOITER")
    s.imu["imu0.accel"] = ChannelValue(
        channel="imu0.accel", value=np.array([0.0, 0.0, 9.81]),
        unit="m/s^2", quality=Quality.INFORMATIVE,
        frame=SensorFrame.BODY_Z_UP, age_s=0.01)
    s.esc["esc.current"] = ChannelValue.absent(
        "esc.current", MissingReason.STUB,
        quality=Quality.STUB_OR_NONINFORMATIVE,
        note="AP_ESC_Telem_SITL.cpp:72 hard-coded 0.8 A")
    s.gnss["gnss.position"] = ChannelValue.absent(
        "gnss.position", MissingReason.NO_3D_FIX)
    return s


def a_log(tmp_path, **kw):
    ad = get_adapter("ardupilot")
    header = make_header(
        adapter=ad, mode="SHADOW", autopilot_version="4.8.0-dev@01a504b",
        command_authority={"result": "NO_COMMAND_PATH_REACHABLE"},
        sensor_availability={}, profile="FIELD_DERIVED_NOISE",
        vehicle_config={"id": "TEST-01"})
    return FlightLog(str(tmp_path), header, **kw)


def write_tick(fl, **over):
    kw = dict(t_mono=1.0, sample=a_sample(), trust_pre={}, trust_post={},
              residuals={}, gates={}, evidence={},
              diagnosis={"top": "nominal", "posterior": {"nominal": 0.99}},
              ambiguity=0.9,
              recommendation={"level": "NORMAL", "actions": [],
                              "authority": "NONE"},
              autopilot={"flight_mode": "LOITER", "failsafe_active": False},
              latency_us=300.0)
    kw.update(over)
    fl.tick(**kw)


def read_rows(tmp_path):
    rows = []
    for p in sorted(glob.glob(os.path.join(str(tmp_path), "*.jsonl"))):
        with open(p, encoding="utf-8") as fh:
            rows += [json.loads(line) for line in fh if line.strip()]
    return rows


# --------------------------------------------------------------------------
# Provenance

def test_header_carries_every_required_field(tmp_path):
    fl = a_log(tmp_path)
    fl.close()
    header = read_rows(tmp_path)[0]
    for key in ("flight_id", "csia_version", "csia_commit", "frozen_core_tag",
                "adapter_platform", "adapter_version", "contract_version",
                "autopilot_version", "vehicle_config_hash", "mode",
                "command_authority", "sensor_availability", "profile",
                "t_start_unix", "host"):
        assert key in header, f"header missing {key}"


def test_header_records_the_command_authority_check(tmp_path):
    """Every flight carries evidence the no-command check ran and passed."""
    fl = a_log(tmp_path)
    fl.close()
    header = read_rows(tmp_path)[0]
    assert header["command_authority"]["result"] == \
        "NO_COMMAND_PATH_REACHABLE"
    assert header["mode"] == "SHADOW"


def test_vehicle_config_hash_changes_with_the_config(tmp_path):
    ad = get_adapter("ardupilot")
    common = dict(adapter=ad, mode="SHADOW", autopilot_version="x",
                  command_authority={}, sensor_availability={},
                  profile="IDEAL_SIM")
    h1 = make_header(vehicle_config={"id": "A"}, **common)
    h2 = make_header(vehicle_config={"id": "B"}, **common)
    assert h1.vehicle_config_hash != h2.vehicle_config_hash


# --------------------------------------------------------------------------
# The six questions the log must answer

def test_tick_records_what_csia_knew_and_what_was_unavailable(tmp_path):
    fl = a_log(tmp_path)
    write_tick(fl)
    fl.close()
    tick = [r for r in read_rows(tmp_path) if r["record"] == "tick"][0]
    chans = tick["canonical"]["channels"]
    assert chans["imu0.accel"]["usable"] is True
    assert chans["imu0.accel"]["value"] == [0.0, 0.0, 9.81]
    assert chans["gnss.position"]["missing"] == "NO_3D_FIX"
    blocked = {b["channel"] for b in tick["evidence_unavailable"]}
    assert "esc.current" in blocked


def test_evidence_unavailable_distinguishes_blocked_from_absent(tmp_path):
    """W-1 needs 'had nothing to see with', not just 'saw nothing'."""
    fl = a_log(tmp_path)
    write_tick(fl)
    fl.close()
    tick = [r for r in read_rows(tmp_path) if r["record"] == "tick"][0]
    blocked = {b["channel"] for b in tick["evidence_unavailable"]}
    assert "esc.current" in blocked      # refused as evidence
    assert "gnss.position" not in blocked  # simply not present


def test_disagreement_is_computed_per_tick(tmp_path):
    fl = a_log(tmp_path)
    write_tick(fl)                                            # both quiet
    write_tick(fl, diagnosis={"top": "gps_fault", "posterior": {}},
               recommendation={"level": "CAUTION", "actions": ["X"]},
               autopilot={"flight_mode": "LOITER",
                          "failsafe_active": False})          # csia only
    write_tick(fl, autopilot={"flight_mode": "LAND",
                              "failsafe_active": True})       # autopilot only
    write_tick(fl, diagnosis={"top": "gps_fault", "posterior": {}},
               recommendation={"level": "CRITICAL", "actions": ["Y"]},
               autopilot={"flight_mode": "LAND",
                          "failsafe_active": True})           # both
    fl.close()
    states = [r["disagreement"]["state"]
              for r in read_rows(tmp_path) if r["record"] == "tick"]
    assert states == ["BOTH_QUIET", "CSIA_ONLY", "AUTOPILOT_ONLY",
                      "BOTH_REACTED"]


def test_both_quiet_is_recorded_not_skipped(tmp_path):
    """A quiet tick is a data point; a rate cannot be computed without it."""
    fl = a_log(tmp_path)
    for _ in range(5):
        write_tick(fl)
    fl.close()
    ticks = [r for r in read_rows(tmp_path) if r["record"] == "tick"]
    assert len(ticks) == 5
    assert all(t["disagreement"]["state"] == "BOTH_QUIET" for t in ticks)


def test_sequence_numbers_are_monotonic(tmp_path):
    fl = a_log(tmp_path)
    for _ in range(20):
        write_tick(fl)
    fl.close()
    seqs = [r["seq"] for r in read_rows(tmp_path) if r["record"] == "tick"]
    assert seqs == sorted(seqs) == list(range(20))


# --------------------------------------------------------------------------
# Failure posture

def test_write_failure_is_counted_not_raised(tmp_path):
    fl = a_log(tmp_path)
    fl._fh = None                       # simulate a closed/failed handle
    write_tick(fl)                      # must not raise
    assert fl.write_errors >= 1


def test_unserializable_extra_does_not_raise(tmp_path):
    fl = a_log(tmp_path)
    write_tick(fl, extra={"obj": object()})   # default=str handles it
    fl.close()
    assert any(r["record"] == "tick" for r in read_rows(tmp_path))


def test_rotation_keeps_the_log_bounded(tmp_path):
    fl = a_log(tmp_path, max_bytes=4096, compress=False, keep=3)
    for _ in range(400):
        write_tick(fl)
    fl.close()
    parts = glob.glob(os.path.join(str(tmp_path), "*.part*"))
    assert len(parts) <= 4        # keep + the open one
    assert fl.part >= 1, "rotation never triggered"


def test_footer_records_the_run(tmp_path):
    fl = a_log(tmp_path)
    write_tick(fl)
    fl.close({"stats": {"ticks": 1}})
    footer = [r for r in read_rows(tmp_path) if r["record"] == "footer"][0]
    assert footer["ticks"] == 1
    assert "write_errors" in footer


# --------------------------------------------------------------------------
# End to end through the runner

def test_shadow_run_produces_a_readable_log(tmp_path):
    from tests.test_shadow_mode import FakeConnection
    cfg = ShadowConfig(log_dir=str(tmp_path), mode=Mode.SHADOW, tick_hz=100.0)
    r = ShadowRunner(cfg, connection_factory=FakeConnection)
    msgs = [{"mavpackettype": "SCALED_IMU2", "time_boot_ms": i,
             "xacc": i % 7, "yacc": 0, "zacc": -1000,
             "xgyro": 0, "ygyro": 0, "zgyro": 0} for i in range(30)]
    r.connect()
    r.run(message_iter=iter(msgs))
    rows = read_rows(tmp_path)
    assert rows[0]["record"] == "header"
    assert rows[0]["command_authority"]["result"] == \
        "NO_COMMAND_PATH_REACHABLE"
    ticks = [x for x in rows if x["record"] == "tick"]
    assert ticks, "no ticks were logged"
    assert all(t["recommendation"]["authority"] == "NONE" for t in ticks)
    assert all(t["latency_us"] >= 0 for t in ticks)
