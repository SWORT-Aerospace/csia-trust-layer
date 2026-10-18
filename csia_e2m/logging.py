"""Append-only acquisition log, and a manifest that closes over it.

RULES, AND WHY EACH ONE
-----------------------
**Every valid record is kept.** Malformed frames are kept too, separately, with
the raw bytes and the reason. Nothing is dropped and nothing is repaired: a
repaired frame is a fabricated measurement, and `research/evidence_semantics/`
already records three ways a fabricated value gets served as a real one.

**Two clocks, never merged.** The controller's microsecond counter and the
host's monotonic nanosecond receive time are different quantities measured by
different oscillators, and their difference is the acquisition latency the
owner asked to record. Collapsing them into one field would destroy exactly the
thing worth measuring.

**Runs are never overwritten.** Opening a log that exists raises. An
interrupted run stays marked incomplete rather than being silently closed,
because "the manifest closed" is a claim that the run finished.

**Host time is integer nanoseconds from `time.monotonic_ns`.** Not the wall
clock, which can step backwards under NTP mid-run, and not a float, which loses
resolution as the process ages.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .protocol import MalformedFrame, ProtocolError, Record, decode

LOG_SCHEMA = "csia.e2m.raw_log/1"
MANIFEST_SCHEMA = "csia.e2m.run_manifest/1"


class RunExists(FileExistsError):
    """Refusing to overwrite a previous run."""


@dataclass
class RunLogger:
    """Writes one run's append-only JSONL log and closes a manifest over it.

    ``clock`` is injectable so tests are deterministic. Nothing in the class
    reads the wall clock for anything that lands in a record.
    """

    path: pathlib.Path
    run_id: str
    device: str
    baud: int
    experiment: str = "E2M-0"
    clock: Callable[[], int] = time.monotonic_ns
    notes: str = ""

    records: int = field(default=0, init=False)
    malformed: int = field(default=0, init=False)
    sequence_gaps: List[Dict] = field(default_factory=list, init=False)
    _last_seq: Optional[int] = field(default=None, init=False)
    _handle: Optional[object] = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)
    _first_host_ns: Optional[int] = field(default=None, init=False)
    _last_host_ns: Optional[int] = field(default=None, init=False)

    def __enter__(self) -> "RunLogger":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close(interrupted=exc_type is not None)

    def open(self) -> None:
        if self.path.exists():
            raise RunExists(
                f"{self.path} exists. A run is never overwritten; choose a new "
                f"run id or move the old log")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("x", encoding="utf-8")
        self._write({"type": "run_start", "schema": LOG_SCHEMA,
                     "run_id": self.run_id, "experiment": self.experiment,
                     "device": self.device, "baud": self.baud,
                     "notes": self.notes,
                     "host_monotonic_ns": self.clock()})

    def ingest(self, line: str) -> Optional[Record]:
        """Take one raw line. Returns the record, or ``None`` if malformed."""
        host_ns = self.clock()
        if self._first_host_ns is None:
            self._first_host_ns = host_ns
        self._last_host_ns = host_ns
        try:
            record = decode(line)
        except ProtocolError as error:
            self.malformed += 1
            frame = MalformedFrame(raw=line.rstrip("\n"), reason=str(error))
            self._write({"type": "malformed", "host_monotonic_ns": host_ns,
                         "raw": frame.raw, "reason": frame.reason})
            return None

        if self._last_seq is not None and record.seq != self._last_seq + 1:
            gap = {"after_seq": self._last_seq, "next_seq": record.seq,
                   "missing": record.seq - self._last_seq - 1,
                   "host_monotonic_ns": host_ns}
            self.sequence_gaps.append(gap)
            self._write({"type": "sequence_gap", **gap})
        self._last_seq = record.seq
        self.records += 1

        self._write({
            "type": "record",
            "host_monotonic_ns": host_ns,
            "controller_us": record.controller_us,
            "seq": record.seq, "sweep": record.sweep,
            "commanded_channel": record.commanded_channel,
            "readback_channel": record.readback_channel,
            "readback_taken": record.readback_taken,
            "sensor": record.sensor, "status": record.status,
            "has_measurement": record.has_measurement,
            "milli": record.milli, "unit": record.unit,
            "i2c_error": record.i2c_error, "retries": record.retries,
            "raw": line.rstrip("\n"),
        })
        return record

    def close(self, *, interrupted: bool = False) -> Dict:
        if self._closed:
            raise RuntimeError("already closed")
        self._write({"type": "run_end", "interrupted": interrupted,
                     "host_monotonic_ns": self.clock()})
        self._handle.close()          # type: ignore[union-attr]
        self._closed = True

        digest = sha256_file(self.path)
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "run_id": self.run_id,
            "experiment": self.experiment,
            "complete": not interrupted,
            "status": "INTERRUPTED" if interrupted else "CLOSED",
            "raw_log": self.path.name,
            "raw_log_sha256": digest,
            "raw_log_bytes": self.path.stat().st_size,
            "device": self.device,
            "baud": self.baud,
            "records": self.records,
            "malformed_frames": self.malformed,
            "sequence_gaps": self.sequence_gaps,
            "host_span_ns": (None if self._first_host_ns is None
                             else self._last_host_ns - self._first_host_ns),
            "notes": self.notes,
            "what_this_is_not": (
                "not evidence that any measurement is correct, and not "
                "evidence that hardware was present. It records what arrived "
                "on a serial port and what did not parse."),
        }
        self.manifest_path.write_text(
            json.dumps(manifest, indent=1, sort_keys=True) + "\n",
            encoding="utf-8")
        return manifest

    @property
    def manifest_path(self) -> pathlib.Path:
        return self.path.with_suffix(".manifest.json")

    def _write(self, payload: Dict) -> None:
        if self._handle is None:
            raise RuntimeError("logger is not open")
        self._handle.write(json.dumps(payload, sort_keys=True) + "\n")
        self._handle.flush()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_run(manifest_path: pathlib.Path) -> Dict:
    """Re-hash the raw log and compare. Detects tampering after the fact."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = manifest_path.parent / manifest["raw_log"]
    if not raw.is_file():
        return {"ok": False, "reason": f"raw log {raw.name} is missing"}
    actual = sha256_file(raw)
    ok = actual == manifest["raw_log_sha256"]
    return {
        "ok": ok,
        "recorded_sha256": manifest["raw_log_sha256"],
        "actual_sha256": actual,
        "complete": manifest["complete"],
        "reason": "" if ok else "raw log does not match its recorded digest",
    }
