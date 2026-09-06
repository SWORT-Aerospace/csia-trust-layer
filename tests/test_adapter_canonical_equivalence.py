"""Four adapters, one canonical record, no core edit.

Program section P2. The pluggable claim has two halves and the first one --
"a new vehicle needs only a profile" -- is already covered by
tests/test_vehicle_profile_no_core_change.py. This is the second half: every
adapter, live or recorded or constructed, hands the frozen core the SAME
SHAPE, so the core cannot tell which one it is talking to.

If that ever stops being true, the cross-platform argument collapses in a
specific way worth naming: a replay result and a live result would no longer
be comparable, and the paper's replay-based reproducibility story would be
reproducing something else.
"""

from __future__ import annotations

import json

import pytest

from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
from csia.aircraft.adapters.base import GROUP_OF, PlatformAdapter
from csia.aircraft.adapters.px4 import PX4Adapter
from csia.aircraft.adapters.replay import (ReplayAdapter, ReplayError,
                                           TimeSource, sample_from_log_dict)
from csia.aircraft.adapters.synthetic import SyntheticAdapter
from csia.aircraft.sample import (AircraftSample, MissingReason, Quality,
                                  SensorFrame)

LIVE = (ArduPilotAdapter, PX4Adapter)
ALL = LIVE + (SyntheticAdapter,)


def _populated_synthetic() -> SyntheticAdapter:
    """A state with every kind of channel outcome in it at once.

    Deliberately mixed: usable values, an explicitly missing channel, a stale
    one, and a cleared one. A round-trip test over only-usable channels would
    pass while silently losing every absence reason -- which is the half that
    matters.
    """
    a = SyntheticAdapter(label="equivalence-fixture")
    a.set_channel("imu0.accel", [0.1, -0.2, 9.79], frame=SensorFrame.BODY_Z_UP)
    a.set_channel("imu0.gyro", [0.0, 0.0, 0.01], frame=SensorFrame.BODY_Z_UP)
    a.set_channel("imu1.accel", [0.11, -0.19, 9.80], frame=SensorFrame.BODY_Z_UP)
    a.set_channel("imu1.gyro", [0.0, 0.0, 0.011], frame=SensorFrame.BODY_Z_UP)
    a.set_channel("mag.field_ut", [20.0, 1.0, 43.0], frame=SensorFrame.BODY_Z_UP)
    a.set_channel("baro.altitude", 12.5)
    a.set_channel("battery.voltage", 15.8)
    a.set_channel("battery.current", 11.2)
    # The interesting half:
    a.set_missing("gnss.position", MissingReason.NO_3D_FIX)
    a.set_missing("gnss.velocity", MissingReason.STALE)
    a.set_missing("esc.rpm", MissingReason.STUB,
                  quality=Quality.STUB_OR_NONINFORMATIVE)
    a.clear("vibration.rms")           # the vehicle never sent it
    a.set_flight_mode("LOITER")
    return a


@pytest.mark.parametrize("cls", ALL, ids=lambda c: c.platform)
def test_every_adapter_produces_the_same_canonical_type(cls):
    adapter = cls()
    assert isinstance(adapter, PlatformAdapter)
    s = adapter.sample()
    assert isinstance(s, AircraftSample)
    assert set(s.GROUPS) == set(AircraftSample.GROUPS)


@pytest.mark.parametrize("cls", ALL, ids=lambda c: c.platform)
def test_every_adapter_bridges_to_the_frozen_core_the_same_way(cls):
    """`to_core_samples` is the only shape the frozen core consumes.

    Inherited from the base class, so this asserts no adapter has overridden
    it into a platform-specific dialect -- which is the exact drift that would
    put vehicle knowledge back inside the core's input.
    """
    assert cls.to_core_samples is PlatformAdapter.to_core_samples, (
        f"{cls.__name__} overrides to_core_samples. The bridge to the frozen "
        f"core must be identical for every adapter, or the core is being "
        f"handed a platform-specific shape.")


def test_a_canonical_sample_survives_the_round_trip_exactly(tmp_path):
    """Synthetic -> JSONL -> replay -> identical dict.

    Equality is checked on the serialised form, which is what a reviewer
    actually has. Comparing live objects would pass even if serialisation
    dropped a field.
    """
    original = _populated_synthetic().sample()
    d = original.to_log_dict()

    path = tmp_path / "trace.jsonl"
    path.write_text(json.dumps(d) + "\n", encoding="utf-8")

    replay = ReplayAdapter(str(path))
    got = list(replay.samples())
    assert len(got) == 1
    back = got[0].to_log_dict()

    # Replay legitimately adds its own provenance block; everything else must
    # match exactly, absence reasons included.
    back_meta = back.pop("metadata")
    d.pop("metadata")
    assert back == d, "the canonical record did not survive the round trip"
    assert back_meta["replay"]["source_sha256"] == replay.source_sha256


def test_replay_preserves_every_absence_reason(tmp_path):
    """The half that would fail silently.

    A round trip that restored values and lost MissingReason would look
    correct on every usable channel and would erase the distinction the whole
    canonical record exists to carry.
    """
    original = _populated_synthetic().sample()
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps(original.to_log_dict()) + "\n", encoding="utf-8")
    back = next(iter(ReplayAdapter(str(path)).samples()))

    for name in ("gnss.position", "gnss.velocity", "esc.rpm"):
        a, b = original.get(name), back.get(name)
        assert b is not None, f"{name} was dropped on replay"
        assert a.missing == b.missing, f"{name}: missing reason changed"
        assert a.quality == b.quality, f"{name}: quality changed"
        assert not b.usable

    # And a cleared channel must stay absent, not reappear as missing.
    assert back.get("vibration.rms") is None, (
        "a channel the vehicle never sent came back as present-and-missing; "
        "those are different states")


def test_replay_is_deterministic_across_instances(tmp_path):
    """Same file, two adapters, identical output hash."""
    states = [_populated_synthetic().sample() for _ in range(5)]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(s.to_log_dict()) for s in states)
                    + "\n", encoding="utf-8")

    hashes = []
    for _ in range(2):
        r = ReplayAdapter(str(path))
        list(r.samples())
        hashes.append(r.provenance()["output_sha256"])
    assert hashes[0] == hashes[1], "replay is not deterministic"


def test_only_recorded_timing_is_admissible_as_evidence(tmp_path):
    """Accelerated replay is a convenience, and must not be quotable."""
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps(_populated_synthetic().sample().to_log_dict())
                    + "\n", encoding="utf-8")

    faithful = ReplayAdapter(str(path), time_source=TimeSource.RECORDED)
    list(faithful.samples())
    assert faithful.provenance()["admissible_as_evidence"] is True

    fast = ReplayAdapter(str(path), time_source=TimeSource.ACCELERATED,
                         speed=1000.0)
    list(fast.samples())
    assert fast.provenance()["admissible_as_evidence"] is False, (
        "a wall-clock-paced replay must not be marked admissible: its "
        "timing is not the recorded timing")


def test_replay_refuses_a_half_populated_channel(tmp_path):
    """A record with neither a value nor a reason is corrupt, and replay must
    say so rather than inventing the missing half."""
    bad = {"t_mono": 1.0, "channels": {
        "baro.altitude": {"value": None, "missing": None,
                          "quality": "UNAVAILABLE", "frame": "NONE"}}}
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(ReplayError, match="Exactly one must be set"):
        list(ReplayAdapter(str(path)).samples())


def test_replay_refuses_an_unknown_channel_rather_than_dropping_it(tmp_path):
    bad = {"t_mono": 1.0, "channels": {
        "lidar.range": {"value": 3.0, "missing": None,
                        "quality": "INFORMATIVE", "frame": "NONE"}}}
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(ReplayError, match="no group"):
        list(ReplayAdapter(str(path)).samples())


def test_replay_has_no_live_ingest_path(tmp_path):
    """Wiring a live stream into a replay adapter must fail loudly, not
    produce an empty plausible result."""
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps(_populated_synthetic().sample().to_log_dict())
                    + "\n", encoding="utf-8")
    with pytest.raises(ReplayError, match="no live ingest"):
        ReplayAdapter(str(path)).ingest(object())


def test_replay_reports_what_the_round_trip_could_not_restore(tmp_path):
    """Honest degradation. `to_log_dict` does not persist per-channel
    t_source, and replay says so instead of interpolating."""
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps(_populated_synthetic().sample().to_log_dict())
                    + "\n", encoding="utf-8")
    r = ReplayAdapter(str(path))
    list(r.samples())
    fid = r.fidelity()
    assert "t_source" in " ".join(fid["not_restored"])
    assert "does not re-run the platform decoder" in fid["note"]


def test_a_flight_log_shaped_trace_is_recognised(tmp_path):
    """The other accepted shape, sniffed rather than declared."""
    s = _populated_synthetic().sample()
    lines = [
        json.dumps({"record": "header", "schema": "csia.flight_log/1",
                    "flight_id": "test"}),
        json.dumps({"record": "tick", "seq": 0, "canonical": s.to_log_dict()}),
    ]
    path = tmp_path / "flight.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    r = ReplayAdapter(str(path))
    got = list(r.samples())
    assert len(got) == 1
    assert r.trace_kind == "csia.flight_log"
    assert r.header["flight_id"] == "test"


def test_channel_group_map_covers_every_channel_a_live_adapter_declares():
    """`sample_from_log_dict` raises on a channel with no group, so a live
    adapter that produced one would make its own traces unreplayable."""
    ungrouped = []
    for cls in LIVE:
        for channel in cls().contract.channels:
            if channel not in GROUP_OF:
                ungrouped.append(f"{cls.platform}: {channel}")
    assert not ungrouped, (
        f"{ungrouped} are declared by a live adapter's contract but have no "
        f"group in adapters.base.GROUP_OF, so a trace containing them could "
        f"not be replayed.")
