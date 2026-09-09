"""S9 flight log: what the aircraft knew, what CSIA knew, and where they differ.

One JSONL file per flight. Line 0 is the header (provenance); every subsequent
line is one tick. JSONL rather than a binary format because a log that cannot
be read with `head` after a bad landing is not evidence.

The log must answer these six questions after the fact, and the field set is
chosen so that each one is answerable without re-running anything:

    What did the aircraft know?        autopilot.*
    What did CSIA know?                canonical.channels[*].value
    What evidence was unavailable?     canonical.channels[*].missing + blocked
    What did CSIA conclude?            diagnosis, trust_post, recommendation
    What did the autopilot conclude?   autopilot.estimator, autopilot.mode
    Did they disagree?                 disagreement, computed per tick

`disagreement` is computed at write time rather than left to a later script,
because "did they disagree" is the question the whole shadow programme exists
to answer and it must not depend on someone choosing the right comparison
later.

Rotation is by size, with monotonic sequence numbers. Loss of the log must
never stall the runtime: write errors are counted and dropped, never raised.
"""

from __future__ import annotations

import glob
import gzip
import json
import os
import platform
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


def _git(*args) -> Optional[str]:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        r = subprocess.run(["git", "-C", root, *args],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


@dataclass
class FlightLogHeader:
    """Provenance. Every field here is required to interpret the ticks."""

    flight_id: str
    csia_version: str
    csia_commit: Optional[str]
    frozen_core_tag: Optional[str]
    adapter_platform: str
    adapter_version: str
    contract_version: Optional[int]
    autopilot_version: str
    vehicle_config_hash: str
    mode: str
    command_authority: dict
    sensor_availability: dict
    calibration_manifest: dict
    profile: str
    host: dict
    t_start_unix: float
    t_start_mono: float
    t_end_unix: Optional[float] = None
    #: Which failsafe was in force. "FROZEN_ONLY" is the frozen policy alone;
    #: "FROZEN_PLUS_DATA_LOSS_SUPERVISION" adds the SR-003 overlay, which can
    #: only RAISE the level. A log that does not say which describes a system
    #: the reader cannot identify, and logs from the two are NOT comparable.
    failsafe_policy: str = "FROZEN_ONLY"
    #: The per-sensor staleness timeouts THIS RUN used, in seconds.
    #:
    #: Without it a log cannot be replayed faithfully. HF-014 is the cost of
    #: the omission: the PX4 decision-replay divergence was traced to a
    #: freshness disagreement, and the obvious explanation -- that the run
    #: used different timeouts from the ones the replay applies today --
    #: could be neither confirmed nor ruled out, because the run's
    #: configuration was not written down anywhere in the log.
    stale_timeout_s: dict = field(default_factory=dict)
    schema: str = "csia.flight_log/1"
    notes: dict = field(default_factory=dict)


class FlightLog:
    """Append-only JSONL writer with rotation and non-fatal failure."""

    def __init__(self, directory: str, header: FlightLogHeader,
                 max_bytes: int = 64 * 1024 * 1024, compress: bool = True,
                 keep: int = 20):
        self.dir = directory
        self.header = header
        self.max_bytes = max_bytes
        self.compress = compress
        self.keep = keep
        self.seq = 0
        self.part = 0
        self.write_errors = 0
        self.ticks_written = 0
        os.makedirs(directory, exist_ok=True)
        self._fh = None
        self._open_part()

    # -- file management ---------------------------------------------------

    def _path(self, part: int) -> str:
        return os.path.join(
            self.dir, f"{self.header.flight_id}.part{part:03d}.jsonl")

    def _open_part(self):
        self._close_fh()
        path = self._path(self.part)
        try:
            self._fh = open(path, "a", encoding="utf-8")
            self._raw({"record": "header", **asdict(self.header),
                       "part": self.part})
        except OSError:
            self.write_errors += 1
            self._fh = None

    def _close_fh(self):
        if self._fh is not None:
            try:
                self._fh.flush()
                os.fsync(self._fh.fileno())
                self._fh.close()
            except OSError:
                self.write_errors += 1
            self._fh = None

    def _rotate(self):
        finished = self._path(self.part)
        self._close_fh()
        if self.compress and os.path.exists(finished):
            try:
                with open(finished, "rb") as src, \
                        gzip.open(finished + ".gz", "wb") as dst:
                    dst.writelines(src)
                os.remove(finished)
            except OSError:
                self.write_errors += 1
        self.part += 1
        self._open_part()
        self._prune()

    def _prune(self):
        files = sorted(glob.glob(os.path.join(
            self.dir, f"{self.header.flight_id}.part*")))
        for old in files[:-self.keep] if len(files) > self.keep else []:
            try:
                os.remove(old)
            except OSError:
                self.write_errors += 1

    # -- writing -----------------------------------------------------------

    def _raw(self, obj: dict):
        if self._fh is None:
            self.write_errors += 1
            return
        try:
            self._fh.write(json.dumps(obj, separators=(",", ":"),
                                      default=str) + "\n")
        except (OSError, TypeError, ValueError):
            self.write_errors += 1

    def tick(self, *, t_mono: float, sample, trust_pre: dict, trust_post: dict,
             residuals: dict, gates: dict, evidence: dict, diagnosis: dict,
             ambiguity: Optional[float], recommendation: dict,
             autopilot: dict, latency_us: float, extra: Optional[dict] = None,
             fresh: Optional[dict] = None, tick_tau: Optional[float] = None):
        """Record one tick. Never raises."""
        blocked = [{"channel": cv.channel,
                    "quality": cv.quality.value,
                    "missing": cv.missing.value if cv.missing else None,
                    "note": cv.note[:200]}
                   for cv in sample.blocked_channels()]

        row = {
            "record": "tick",
            "seq": self.seq,
            "t_mono": round(t_mono, 6),
            "t_unix": round(time.time(), 6),
            "canonical": sample.to_log_dict(),
            "evidence_unavailable": blocked,
            "residuals": residuals,
            "gates": gates,
            "trust_pre": trust_pre,
            "trust_post": trust_post,
            "hypothesis_evidence": evidence,
            "diagnosis": diagnosis,
            "ambiguity": ambiguity,
            "recommendation": recommendation,
            "autopilot": autopilot,
            "latency_us": round(latency_us, 3),
            "disagreement": self._disagreement(diagnosis, recommendation,
                                               autopilot),
            # THE LAYER'S OWN per-sensor freshness verdict, which is NOT
            # recoverable from anything else in the row. `canonical` carries
            # the ADAPTER's per-channel age; the gate weights carry products
            # of freshness terms that cannot be factored back apart. HF-014
            # got stuck exactly here -- the divergence was localised to
            # freshness and could go no further, because the one map that
            # would settle it was never written down.
            "fresh": ({k: bool(v) for k, v in fresh.items()}
                      if fresh else None),
            # THE LAYER'S OWN TICK BOUNDARY, which is a different clock from
            # `t_mono`. The live run ticks on a wall clock; a replay driven
            # from hand-offs builds its own grid and the two drift by a
            # fraction of a tick. HF-016 measured the cost: 119 PX4
            # divergences with a perfectly symmetric signature -- 59 ticks
            # leading, 59 lagging at baro's staleness boundary -- which is
            # what a phase offset looks like and what no log could confirm,
            # because this number was never written down.
            "tick_tau": (round(float(tick_tau), 6)
                         if tick_tau is not None else None),
        }
        if extra:
            row["extra"] = extra
        self._raw(row)
        self.seq += 1
        self.ticks_written += 1
        if self.seq % 50 == 0:
            self._maybe_rotate()

    def _maybe_rotate(self):
        if self._fh is None:
            self._open_part()
            return
        try:
            self._fh.flush()
            if os.path.getsize(self._path(self.part)) >= self.max_bytes:
                self._rotate()
        except OSError:
            self.write_errors += 1

    @staticmethod
    def _disagreement(diagnosis: dict, recommendation: dict,
                      autopilot: dict) -> dict:
        """Classify CSIA vs autopilot at this tick.

        Four outcomes, deliberately including the two "silent" ones. A tick
        where both are quiet is as much a data point as a tick where they
        differ, and a rate cannot be computed later without it.
        """
        csia_fault = bool(diagnosis and diagnosis.get("top") not in
                          (None, "nominal"))
        csia_escalated = bool(recommendation and
                              recommendation.get("level", "NORMAL") != "NORMAL")
        ap_failsafe = bool(autopilot.get("failsafe_active"))
        ap_mode = autopilot.get("flight_mode")
        ap_reactive = ap_failsafe or (ap_mode in ("LAND", "RTL", "AUTO.LAND",
                                                  "AUTO.RTL"))
        csia_active = csia_fault or csia_escalated
        if csia_active and ap_reactive:
            state = "BOTH_REACTED"
        elif csia_active:
            state = "CSIA_ONLY"
        elif ap_reactive:
            state = "AUTOPILOT_ONLY"
        else:
            state = "BOTH_QUIET"
        return {
            "state": state,
            "csia_top": (diagnosis or {}).get("top"),
            "csia_level": (recommendation or {}).get("level"),
            "autopilot_mode": ap_mode,
            "autopilot_failsafe": ap_failsafe,
        }

    def close(self, note: Optional[dict] = None):
        self.header.t_end_unix = time.time()
        self._raw({"record": "footer",
                   "ticks": self.ticks_written,
                   "write_errors": self.write_errors,
                   "t_end_unix": self.header.t_end_unix,
                   "note": note or {}})
        self._close_fh()


def make_header(*, adapter, mode: str, autopilot_version: str,
                command_authority: dict, sensor_availability: dict,
                profile: str, vehicle_config: dict,
                calibration_manifest: Optional[dict] = None,
                flight_id: Optional[str] = None,
                failsafe_policy: str = "FROZEN_ONLY",
                stale_timeout_s: Optional[dict] = None) -> FlightLogHeader:
    from .. import __version__ as csia_version
    cfg_blob = json.dumps(vehicle_config, sort_keys=True).encode()
    import hashlib
    return FlightLogHeader(
        flight_id=flight_id or f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
                               f"-{uuid.uuid4().hex[:8]}",
        csia_version=csia_version,
        csia_commit=_git("rev-parse", "HEAD"),
        frozen_core_tag=_git("describe", "--tags", "--match",
                             "csia-v1.0-*", "--abbrev=0"),
        adapter_platform=adapter.platform,
        adapter_version=adapter.adapter_version,
        contract_version=adapter.contract.version,
        autopilot_version=autopilot_version,
        vehicle_config_hash=hashlib.sha256(cfg_blob).hexdigest()[:16],
        mode=mode,
        failsafe_policy=failsafe_policy,
        stale_timeout_s=dict(sorted((stale_timeout_s or {}).items())),
        command_authority=command_authority,
        sensor_availability=sensor_availability,
        calibration_manifest=calibration_manifest or {},
        profile=profile,
        host={"python": platform.python_version(),
              "system": platform.system(),
              "machine": platform.machine()},
        t_start_unix=time.time(),
        t_start_mono=time.monotonic(),
    )
