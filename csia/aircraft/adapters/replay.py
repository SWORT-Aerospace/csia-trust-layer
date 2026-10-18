"""Replay adapter: a committed trace back through the same canonical shape.

The point of a replay path in a validation program is not convenience. It is
that a reviewer with the trace and no vehicle can re-derive every number the
paper states. So this adapter has one hard obligation and one hard
prohibition:

  OBLIGATION   the same trace must produce the same canonical samples, byte
               for byte, on any host, forever.
  PROHIBITION  it must never invent a value. A channel that was MISSING in
               the recording is MISSING on replay, with the same reason.

WHY IT RECONSTRUCTS CANONICAL SAMPLES RATHER THAN REPLAYING MAVLINK
-------------------------------------------------------------------
Replaying raw MAVLink would re-run the platform decoder, which means a replay
result depends on the decoder version and a decoder change silently rewrites
history. Replaying the CANONICAL record instead makes the trace the evidence:
the decoder's output was recorded at the time, under a named contract
version, and replay reproduces exactly that.

The cost is stated rather than hidden: replay cannot re-test the decoder. A
decoder defect present at recording time is present in the trace and this
adapter will faithfully reproduce it. Decoder correctness is the
qualification harness's job, not replay's.

WHAT IS LOST IN THE ROUND TRIP, AND WHY IT IS NOT PAPERED OVER
---------------------------------------------------------------
`AircraftSample.to_log_dict()` does not persist per-channel `t_source`. On
replay those come back as None rather than as a guess. `fidelity()` reports
every field that could not be restored, so a consumer can decide rather than
discover. Filling them by interpolation would be fabrication of exactly the
kind the canonical record exists to prevent.
"""

from __future__ import annotations

import enum
import hashlib
import json
import os
import time
from typing import Iterator, Optional

from ..sample import (AircraftSample, ChannelValue, MissingReason, Quality,
                      SensorFrame)
from .base import GROUP_OF, PlatformAdapter


class TimeSource(enum.Enum):
    """How replay assigns `t_mono`.

    RECORDED is the only one that reproduces the original timing exactly and
    is therefore the only one admissible for evidence. The other two exist
    for interactive inspection and are marked in the sample metadata so a
    trace produced under them cannot be mistaken for a faithful replay.
    """

    RECORDED = "RECORDED"        # t_mono straight from the record
    MONOTONIC = "MONOTONIC"      # wall-clock paced, real time
    ACCELERATED = "ACCELERATED"  # wall-clock paced, scaled

    @property
    def faithful(self) -> bool:
        return self is TimeSource.RECORDED


class ReplayError(ValueError):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def _decode_channel(name: str, d: dict) -> ChannelValue:
    """Rebuild one ChannelValue. Raises rather than guessing."""
    missing = d.get("missing")
    value = d.get("value")
    if (value is None) == (missing is None):
        raise ReplayError(
            f"{name}: the record has value={value!r} and missing={missing!r}. "
            f"Exactly one must be set -- a half-populated channel is the "
            f"defect ChannelValue exists to prevent, and replay will not "
            f"invent the other half.")
    return ChannelValue(
        channel=name,
        value=value,
        unit=d.get("unit", ""),
        quality=Quality(d["quality"]),
        frame=SensorFrame(d.get("frame", "NONE")),
        missing=MissingReason(missing) if missing else None,
        t_source=None,          # not persisted; see module docstring
        age_s=d.get("age_s"),
        note=d.get("note", ""),
    )


def sample_from_log_dict(d: dict) -> AircraftSample:
    """The exact inverse of `AircraftSample.to_log_dict()`.

    Unknown channel names raise. A channel the group map does not know would
    otherwise be silently dropped, and a silently dropped channel on replay is
    indistinguishable from a channel the vehicle never sent.
    """
    s = AircraftSample(t_mono=d["t_mono"], t_source=d.get("t_source"),
                       flight_mode=d.get("flight_mode"))
    for name, cd in (d.get("channels") or {}).items():
        group = GROUP_OF.get(name)
        if group is None:
            raise ReplayError(
                f"channel {name!r} in the trace has no group in "
                f"adapters.base.GROUP_OF. Replay will not drop it silently: a "
                f"dropped channel is indistinguishable from one the vehicle "
                f"never sent.")
        getattr(s, group)[name] = _decode_channel(name, cd)
    s.metadata = dict(d.get("metadata") or {})
    return s


class ReplayAdapter(PlatformAdapter):
    """Replay a committed canonical trace.

    Accepts either shape, because both exist in this repository:

      * a CSIA flight log (`csia.flight_log/1`), whose `tick` rows carry the
        canonical sample under `"canonical"`;
      * a bare canonical-sample JSONL, one `to_log_dict()` per line.

    It sniffs rather than being told, and records which it found in
    `provenance()`, so a trace cannot be replayed under the wrong assumption.
    """

    platform = "replay"
    adapter_version = "1.0.0"

    def __init__(self, path: str, *,
                 time_source: TimeSource = TimeSource.RECORDED,
                 speed: float = 1.0,
                 profile=None,
                 contract=None,
                 clock=time.monotonic):
        # The replay path is not qualifying a live decoder, so it inherits
        # whatever contract the trace was recorded under rather than asserting
        # one. `contract` may be supplied for tooling that needs the channel
        # list; it does not re-qualify anything.
        super().__init__(contract=contract, clock=clock)
        if not os.path.exists(path):
            raise ReplayError(f"{path}: no such trace")
        if speed <= 0:
            raise ReplayError(f"speed must be positive, got {speed}")

        self.path = path
        self.time_source = time_source
        self.speed = float(speed)
        self.profile = profile
        self.source_sha256 = sha256_file(path)
        self.trace_kind = None            # set on first read
        self.header = None
        self._records_read = 0
        self._output_hash = hashlib.sha256()
        self._t0_record = None
        self._t0_wall = None
        self._last: Optional[AircraftSample] = None
        self._fidelity_losses = set()

    # -- iteration ---------------------------------------------------------

    def samples(self) -> Iterator[AircraftSample]:
        """Yield every canonical sample in the trace, in recorded order.

        Deterministic by construction: file order, no clock read in RECORDED
        mode, no dict iteration that depends on insertion by a live decoder.
        """
        with open(self.path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ReplayError(f"{self.path}:{lineno}: {exc}") from exc

                rec = row.get("record")
                if rec == "header":
                    self.header = row
                    self.trace_kind = self.trace_kind or "csia.flight_log"
                    continue
                if rec == "tick":
                    self.trace_kind = self.trace_kind or "csia.flight_log"
                    canonical = row.get("canonical")
                    if canonical is None:
                        raise ReplayError(
                            f"{self.path}:{lineno}: a tick row with no "
                            f"'canonical' block cannot be replayed")
                elif rec is None and "channels" in row:
                    self.trace_kind = self.trace_kind or "canonical_jsonl"
                    canonical = row
                else:
                    # A row we do not understand. Skipping it silently would
                    # make the replay shorter than the recording with nothing
                    # to say so.
                    continue

                sample = sample_from_log_dict(canonical)
                self._note_fidelity(canonical, sample)
                sample.metadata.setdefault("replay", {})
                sample.metadata["replay"] = {
                    "source": os.path.basename(self.path),
                    "source_sha256": self.source_sha256,
                    "time_source": self.time_source.value,
                    "faithful_timing": self.time_source.faithful,
                    "record_index": self._records_read,
                }
                self._pace(sample)
                self._records_read += 1
                self._last = sample
                self._output_hash.update(
                    json.dumps(sample.to_log_dict(), sort_keys=True,
                               separators=(",", ":")).encode("utf-8"))
                yield sample

    def _note_fidelity(self, canonical: dict, sample: AircraftSample):
        for name, cd in (canonical.get("channels") or {}).items():
            if cd.get("t_source") is not None:
                # The recorder did persist it and we still cannot place it --
                # would be a real defect, so it is recorded rather than
                # ignored.
                self._fidelity_losses.add("channel.t_source")

    def _pace(self, sample: AircraftSample):
        """Wall-clock pacing for the two non-faithful modes."""
        if self.time_source is TimeSource.RECORDED:
            return
        if self._t0_record is None:
            self._t0_record = sample.t_mono
            self._t0_wall = self._clock()
            return
        target = (sample.t_mono - self._t0_record) / self.speed
        elapsed = self._clock() - self._t0_wall
        if target > elapsed:
            time.sleep(target - elapsed)

    # -- adapter surface ---------------------------------------------------

    def ingest(self, msg) -> None:
        """Replay has no live stream. Raising is the honest answer.

        A no-op here would let a caller wire a live source into a replay
        adapter and get an empty, silent, plausible-looking result.
        """
        raise ReplayError(
            "ReplayAdapter has no live ingest path. Iterate samples() "
            "instead, or use a live platform adapter.")

    def sample(self, t_mono: Optional[float] = None) -> AircraftSample:
        if self._last is None:
            raise ReplayError("no sample has been replayed yet; call "
                              "samples() first")
        return self._last

    # -- provenance --------------------------------------------------------

    def fidelity(self) -> dict:
        """What the round trip could not restore. Reported, never filled in."""
        return {
            "exact": not self._fidelity_losses,
            "not_restored": sorted(self._fidelity_losses) or
            ["channel.t_source (never persisted by to_log_dict)"],
            "note": "replay reproduces the recorded canonical sample; it does "
                    "not re-run the platform decoder, so a decoder defect "
                    "present at recording time is faithfully reproduced",
        }

    def provenance(self) -> dict:
        """Everything needed to decide whether a replay result is evidence."""
        return {
            "adapter": self.platform,
            "adapter_version": self.adapter_version,
            "source_path": self.path,
            "source_sha256": self.source_sha256,
            "trace_kind": self.trace_kind,
            "records_read": self._records_read,
            "time_source": self.time_source.value,
            "faithful_timing": self.time_source.faithful,
            "speed": self.speed,
            "output_sha256": self._output_hash.hexdigest(),
            "profile_id": getattr(self.profile, "profile_id", None),
            "header": self.header,
            "fidelity": self.fidelity(),
            "admissible_as_evidence": self.time_source.faithful,
        }
