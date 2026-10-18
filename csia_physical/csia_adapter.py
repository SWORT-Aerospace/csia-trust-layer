"""Observations -> CSIA-shaped input. Missing never becomes zero.

WHY THIS DOES NOT IMPLEMENT THE MISSING/ZERO RULE ITSELF
----------------------------------------------------------
`csia.aircraft.sample.ChannelValue` already enforces it structurally: exactly
one of `value` and `missing` may be set, and a missing value may not carry an
admissible quality. A second implementation of the same rule would be a
second thing to keep in sync, so this adapter CONSTRUCTS `ChannelValue` and
lets the contract refuse anything malformed. The test that matters therefore
asserts the contract raises, not that this file remembered to check.

The failure this prevents is on record in `research/evidence_semantics/`: a
`-1` sentinel was served as `5.00 A`. A missing measurement that arrives as
`0` is worse than one that never arrives, because a zero is a number a
relation will happily consume.

WHY QUALITY IS NEVER `INFORMATIVE` HERE
-----------------------------------------
`Quality.INFORMATIVE` is the only admissible rung and it means the channel's
semantics have been ESTABLISHED. For a bench sensor read over a TCA9548A
that requires the datasheet (gate 1) and the inventory (gate 2), and both are
open. Every channel this adapter emits is therefore capped at
`AVAILABLE_UNVALIDATED`, and `qualify()` raises rather than promoting one
while the gates are open.

That cap is not a formality. It means nothing produced by this adapter may be
consumed as diagnostic evidence yet, and the trust layer will treat it as
unusable -- which is the correct behaviour for a sensor nobody has verified.

NO HARDWARE CONSTANTS
---------------------
This module contains no register address, no voltage, no timing and no
datasheet value. It maps a record that already exists to a contract that
already exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from csia.aircraft.sample import ChannelValue, MissingReason, Quality

from csia_e2m.protocol import (ERR_MUX_READBACK, ERR_MUX_WRITE,
                               ERR_NO_DRIVER, ERR_READBACK_MISMATCH,
                               ERR_SENSOR_NACK, ERR_TIMEOUT, OK, SAFE_IDLE,
                               STATUSES)

ADAPTER_SCHEMA = "csia.physical.csia_input/1"

#: The ceiling this adapter may assign while the hardware gates are open.
#: `INFORMATIVE` is the only admissible rung and it asserts that the
#: channel's semantics are established. They are not.
MAX_QUALITY_WHILE_GATED = Quality.AVAILABLE_UNVALIDATED

#: Status -> why the channel carries no value. The keys are taken FROM
#: `csia_e2m.protocol.STATUSES` and are not invented here; a first draft of
#: this table guessed names like "TIMEOUT" and "NACK" that the protocol does
#: not use, and the tests caught it immediately.
#:
#: A readback MISMATCH is deliberately `NOT_QUALIFIED` rather than
#: `NOT_RECEIVED`: bytes did arrive, and the problem is that nobody can say
#: which device sent them. Calling that "not received" would lose exactly the
#: distinction the mux identity work exists to preserve.
STATUS_TO_MISSING: Dict[str, MissingReason] = {
    ERR_MUX_WRITE: MissingReason.NOT_RECEIVED,
    ERR_MUX_READBACK: MissingReason.NOT_RECEIVED,
    ERR_READBACK_MISMATCH: MissingReason.NOT_QUALIFIED,
    ERR_SENSOR_NACK: MissingReason.NOT_RECEIVED,
    ERR_TIMEOUT: MissingReason.NOT_RECEIVED,
    ERR_NO_DRIVER: MissingReason.FIELD_ABSENT,
    SAFE_IDLE: MissingReason.FIELD_ABSENT,
}

#: Used when a status is not in the table. Deliberately NOT a default
#: argument on a .get() call: an unknown status is a change in the protocol
#: and the adapter says so rather than absorbing it.
UNKNOWN_STATUS_REASON = MissingReason.NOT_QUALIFIED


class AdapterError(ValueError):
    """The observation cannot be adapted as written."""


class QualificationBlocked(RuntimeError):
    """Refusing to promote a channel while the hardware gates are open."""


@dataclass(frozen=True)
class AdaptedChannel:
    """One CSIA channel plus the provenance of the read behind it."""

    channel: ChannelValue
    record_id: int
    host_monotonic_ns: int
    commanded_channel: int
    readback_channel: Optional[int]
    identity_state: str
    latency_ns: Optional[int]
    fault_label: Optional[str]

    def as_record(self) -> dict:
        c = self.channel
        return {
            "schema": ADAPTER_SCHEMA,
            "channel": c.channel,
            "value": c.value,
            "unit": c.unit,
            "quality": c.quality.value,
            "missing": None if c.missing is None else c.missing.value,
            "usable": c.usable,
            "record_id": self.record_id,
            "host_monotonic_ns": self.host_monotonic_ns,
            "commanded_channel": self.commanded_channel,
            "readback_channel": self.readback_channel,
            "identity_state": self.identity_state,
            "latency_ns": self.latency_ns,
            "fault_label": self.fault_label,
            "is_experimental": True,
            "hardware_operated": False,
        }


def missing_reason_for(status: str) -> MissingReason:
    if status == OK:
        raise AdapterError("OK carries a measurement; it is not missing")
    return STATUS_TO_MISSING.get(status, UNKNOWN_STATUS_REASON)


def unmapped_statuses() -> Tuple[str, ...]:
    """Protocol statuses this adapter has no reason for. Should be empty.

    A status the protocol can emit and the adapter has no mapping for would
    silently become `NOT_QUALIFIED`, which is a different claim from the one
    the controller made. A test asserts this is empty, so adding a status to
    the protocol without adding a reason here fails loudly.
    """
    return tuple(s for s in STATUSES
                 if s != OK and s not in STATUS_TO_MISSING)


def adapt(observation, *, channel_name: str,
          fault_label: Optional[str] = None,
          quality: Quality = MAX_QUALITY_WHILE_GATED) -> AdaptedChannel:
    """One observation -> one `ChannelValue`, with its provenance.

    `quality` may not exceed the gated ceiling. A caller that wants
    `INFORMATIVE` must clear the hardware gates first and go through
    `qualify()`, which refuses while they are open.
    """
    if quality is Quality.INFORMATIVE:
        raise QualificationBlocked(
            "refusing to mark a bench channel INFORMATIVE: that asserts the "
            "channel's semantics are established, and gates 1 and 2 of "
            "research/bus_provenance/E2M_GATE_STATUS.md are open")

    status = observation.status
    if status == OK:
        if observation.value_milli is None:
            raise AdapterError(
                f"record {observation.record_id}: status is OK but there is "
                "no measurement; refusing to invent one")
        value = observation.value_milli
        cv = ChannelValue(channel=channel_name, value=value,
                          unit=observation.unit or "", quality=quality,
                          note="milli-units as reported by the controller")
    else:
        cv = ChannelValue.absent(channel_name, missing_reason_for(status),
                                 quality=Quality.UNAVAILABLE)

    return AdaptedChannel(
        channel=cv,
        record_id=observation.record_id,
        host_monotonic_ns=observation.host_monotonic_ns,
        commanded_channel=observation.commanded_channel,
        readback_channel=observation.readback_channel,
        identity_state=getattr(observation.identity, "state",
                               str(observation.identity)),
        latency_ns=observation.latency_ns,
        fault_label=fault_label)


def adapt_stream(observations, *, naming, annotation=None
                 ) -> List[AdaptedChannel]:
    """Adapt a replayed stream, joining the annotation sidecar by host time.

    `naming` maps a sensor id to the CSIA channel name. It is injected rather
    than guessed: the mapping from "whatever the operator called the device"
    to "the channel CSIA reasons about" is a configuration fact, and
    inventing one here would be the identity misattribution this layer exists
    to prevent.
    """
    out = []
    for obs in observations:
        if obs.sensor not in naming:
            raise AdapterError(
                f"no CSIA channel declared for sensor {obs.sensor!r}; "
                "refusing to guess one")
        label = None
        if annotation is not None:
            hit = annotation.fault_at(obs.host_monotonic_ns)
            label = None if hit is None else hit.label
        out.append(adapt(obs, channel_name=naming[obs.sensor],
                         fault_label=label))
    return out


def qualify(*_args, **_kwargs):
    """Promote a channel to `INFORMATIVE`. Refuses while the gates are open."""
    raise QualificationBlocked(
        "channel qualification requires the TCA9548A datasheet (gate 1) and "
        "the sensor inventory (gate 2); both are OPEN. See "
        "research/bus_provenance/E2M_GATE_STATUS.md. BLOCKED.")
