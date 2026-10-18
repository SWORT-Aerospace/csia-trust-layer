"""Deterministic replay of an immutable raw log into CSIA-shaped observations.

WHAT REPLAY MUST NOT DO
-----------------------
**It must not leak the future.** An observation at event time *t* may be built
only from records whose host receive time is <= *t*. A replay that hands a
consumer the whole file and lets it index freely is not a replay; it is a
lookahead, and every timing conclusion drawn from it is invalid.
:func:`replay` is a generator for that reason -- it cannot hand out what it has
not yet reached, and :func:`check_no_future_leakage` verifies the property
holds over an emitted sequence.

**It must not convert missing into zero.** A record whose status is not ``OK``
carries no measurement. `value_milli` is ``None`` there, and a test asserts it
is not ``0``. This is finding 2 of `research/evidence_semantics/` -- a `-1`
sentinel served as `5.00 A` -- and it is the single easiest mistake to make in
an adapter.

**It must not repair.** Malformed frames stay malformed and are emitted as
their own kind of event.

**Derived streams never touch the raw log.** :mod:`csia_e2m.faults` writes new
files; this module only reads.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional

from .identity import IdentityAssessment, assess
from .protocol import OK

OBSERVATION_SCHEMA = "csia.e2m.observation/1"


class ReplayError(ValueError):
    """The log cannot be replayed as written."""


@dataclass(frozen=True)
class Observation:
    """One CSIA-facing observation, linked to the raw record it came from."""

    record_id: int
    host_monotonic_ns: int
    controller_us: int
    sweep: int
    sensor: str
    commanded_channel: int
    readback_channel: Optional[int]
    status: str
    value_milli: Optional[int]
    unit: Optional[str]
    identity: IdentityAssessment
    latency_ns: Optional[int] = None

    @property
    def observed(self) -> bool:
        """Whether a measurement exists. Missing is not zero."""
        return self.value_milli is not None

    def as_dict(self) -> dict:
        return {
            "schema": OBSERVATION_SCHEMA,
            "record_id": self.record_id,
            "host_monotonic_ns": self.host_monotonic_ns,
            "controller_us": self.controller_us,
            "sweep": self.sweep,
            "sensor": self.sensor,
            "commanded_channel": self.commanded_channel,
            "readback_channel": self.readback_channel,
            "status": self.status,
            "observed": self.observed,
            "value_milli": self.value_milli,
            "unit": self.unit,
            "latency_ns": self.latency_ns,
            "identity": self.identity.as_dict(),
        }


def _load(path: pathlib.Path) -> List[Dict]:
    rows = []
    for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ReplayError(f"{path.name}:{number} is not JSON: {error}") \
                from error
    return rows


def replay(path: pathlib.Path, *,
           declared: Optional[Dict[int, str]] = None,
           native_identities: Optional[Dict[str, str]] = None
           ) -> Iterator[Observation]:
    """Yield observations in recorded order, one at a time.

    ``declared`` maps channel -> the sensor configuration says is there.
    ``native_identities`` maps sensor -> the identity it should report, when
    the part has an identity register. Both are declarations, and the identity
    assessment treats them as such rather than as facts.
    """
    declared = declared or {}
    native_identities = native_identities or {}
    previous_host_ns: Optional[int] = None

    for index, row in enumerate(_load(path)):
        if row.get("type") != "record":
            continue
        host_ns = int(row["host_monotonic_ns"])
        if previous_host_ns is not None and host_ns < previous_host_ns:
            raise ReplayError(
                f"record {index} goes backwards in host time "
                f"({host_ns} after {previous_host_ns}); the log is not "
                f"replayable in event order and is not silently re-sorted")
        previous_host_ns = host_ns

        channel = int(row["commanded_channel"])
        if not 0 <= channel <= 7:
            raise ReplayError(
                f"record {index} names channel {channel}, which cannot exist "
                f"on a TCA9548A")
        readback = row.get("readback_channel")
        readback = None if readback in (None, -1) else int(readback)

        status = row["status"]
        sensor = row["sensor"]
        has_value = status == OK
        unit = row.get("unit") or None
        if has_value and not unit:
            raise ReplayError(
                f"record {index} reports a measurement with no unit; a "
                f"number without a unit is not a measurement")

        identity = assess(
            commanded_channel=channel,
            readback_channel=readback,
            declared_sensor=declared.get(channel),
            write_acknowledged=status != "ERR_MUX_WRITE",
            expected_native_identity=native_identities.get(
                declared.get(channel, "")),
        )

        yield Observation(
            record_id=index,
            host_monotonic_ns=host_ns,
            controller_us=int(row["controller_us"]),
            sweep=int(row["sweep"]),
            sensor=sensor,
            commanded_channel=channel,
            readback_channel=readback,
            status=status,
            value_milli=int(row["milli"]) if has_value else None,
            unit=unit if has_value else None,
            identity=identity,
        )


def check_no_future_leakage(observations: Iterable[Observation]) -> Dict:
    """Verify emitted observations are non-decreasing in host time."""
    last: Optional[int] = None
    violations: List[Dict] = []
    count = 0
    for observation in observations:
        count += 1
        if last is not None and observation.host_monotonic_ns < last:
            violations.append({"record_id": observation.record_id,
                               "host_monotonic_ns":
                                   observation.host_monotonic_ns,
                               "previous": last})
        last = observation.host_monotonic_ns
    return {"observations": count, "violations": violations,
            "ok": not violations}
