"""The wire record between the acquisition controller and the host.

WHY A TEXT LINE WITH A CRC
--------------------------
The controller is an Arduino Uno class board: 2 KB of RAM and no floating-point
unit worth using. A binary struct would be smaller and a JSON object would be
friendlier, and both are worse here. A delimited ASCII line can be read by a
human with a serial monitor during bring-up -- which is the whole first hour of
any bench session -- and it survives being truncated by a reset mid-write,
because the CRC fails and the frame is recorded as malformed rather than parsed
into a plausible reading.

That last property is the point. `research/evidence_semantics/` records three
findings in which a bad value was served as a good one. A truncated frame that
parses is the same defect at the transport layer, so the frame carries a CRC
and a short-field check, and anything that fails either becomes a
:class:`MalformedFrame` that is *kept*, not dropped.

NO FLOATS ON THE WIRE
---------------------
Measurements cross as integers in milli-units with the unit named separately.
`float` formatting on an 8-bit AVR costs code space and introduces a rounding
step whose behaviour differs from the host's. An integer and a unit string
cannot disagree between the two ends.

THE FRAME
---------
    E2M1,<seq>,<sweep>,<cmd_ch>,<rb_ch>,<sensor>,<status>,<milli>,<unit>,
         <ctrl_us>,<i2c_err>,<retries>*<crc16_hex>

`rb_ch` is ``-1`` when the control register was not read back, which is a
different fact from reading it back and getting a different channel. Both occur
and they are not merged.

The CRC is CRC-16/CCITT-FALSE over the payload bytes before the ``*``.
"""
from __future__ import annotations

from dataclasses import dataclass


MAGIC = "E2M1"
FIELD_COUNT = 12

#: Status words the controller may emit. Anything else is a protocol error and
#: is not silently mapped onto one of these.
OK = "OK"
ERR_MUX_WRITE = "ERR_MUX_WRITE"
ERR_MUX_READBACK = "ERR_MUX_READBACK"
ERR_READBACK_MISMATCH = "ERR_READBACK_MISMATCH"
ERR_SENSOR_NACK = "ERR_SENSOR_NACK"
ERR_TIMEOUT = "ERR_TIMEOUT"
ERR_NO_DRIVER = "ERR_NO_DRIVER"
SAFE_IDLE = "SAFE_IDLE"

STATUSES = (OK, ERR_MUX_WRITE, ERR_MUX_READBACK, ERR_READBACK_MISMATCH,
            ERR_SENSOR_NACK, ERR_TIMEOUT, ERR_NO_DRIVER, SAFE_IDLE)

#: Statuses that carry no measurement. A consumer must not read `milli` here.
NO_MEASUREMENT = frozenset(STATUSES) - {OK}

#: `rb_ch` value meaning "the control register was not read back at all".
READBACK_NOT_TAKEN = -1


class ProtocolError(ValueError):
    """A frame that cannot be trusted to mean anything."""


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE. Init 0xFFFF, poly 0x1021, no reflection, no xorout.

    Written out rather than imported so the firmware can carry the identical
    eight lines and the two ends cannot drift apart through a library version.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 \
                else (crc << 1) & 0xFFFF
    return crc


@dataclass(frozen=True)
class Record:
    """One attempted sensor read, as the controller saw it."""

    seq: int
    sweep: int
    commanded_channel: int
    readback_channel: int
    sensor: str
    status: str
    milli: int
    unit: str
    controller_us: int
    i2c_error: int
    retries: int

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ProtocolError(f"unknown status {self.status!r}")
        if not 0 <= self.commanded_channel <= 7:
            raise ProtocolError(
                f"commanded channel {self.commanded_channel} outside 0..7")
        if self.readback_channel != READBACK_NOT_TAKEN and \
                not 0 <= self.readback_channel <= 7:
            raise ProtocolError(
                f"readback channel {self.readback_channel} is neither 0..7 "
                f"nor {READBACK_NOT_TAKEN} (not taken)")
        if "," in self.sensor or "*" in self.sensor:
            raise ProtocolError("sensor id may not contain ',' or '*'")

    @property
    def readback_taken(self) -> bool:
        return self.readback_channel != READBACK_NOT_TAKEN

    @property
    def has_measurement(self) -> bool:
        """Whether `milli` means anything. Missing is not zero."""
        return self.status == OK

    def payload(self) -> str:
        return (f"{MAGIC},{self.seq},{self.sweep},{self.commanded_channel},"
                f"{self.readback_channel},{self.sensor},{self.status},"
                f"{self.milli},{self.unit},{self.controller_us},"
                f"{self.i2c_error},{self.retries}")

    def encode(self) -> str:
        body = self.payload()
        return f"{body}*{crc16_ccitt(body.encode('ascii')):04X}"


@dataclass(frozen=True)
class MalformedFrame:
    """A line that did not decode. Kept, never repaired, never dropped."""

    raw: str
    reason: str


def decode(line: str) -> Record:
    """Parse one frame, or raise. The caller decides what to keep."""
    line = line.strip()
    if not line:
        raise ProtocolError("empty line")
    if "*" not in line:
        raise ProtocolError("no CRC delimiter")
    body, _, given = line.rpartition("*")
    if len(given) != 4:
        raise ProtocolError(f"CRC field {given!r} is not four hex digits")
    # UPPERCASE IS PART OF THE GRAMMAR, AND THIS IS NOT COSMETIC.
    #
    # `int(given, 16)` is case-insensitive, so "28B9" and "28b9" parse to the
    # same value and a frame whose CRC field had one bit flipped -- 'B' 0x42
    # -> 'b' 0x62, bit 5 -- decoded as valid. That is a real hole:
    # `test_any_single_bit_corruption_is_detected` claims EVERY single-bit
    # flip is refused, and an exhaustive sweep over one frame found exactly
    # one that was not, at index 43 in the CRC field.
    #
    # It was found by the property test failing, not by inspection, and it
    # had been failing intermittently: the flip has to land on one of the CRC
    # field's A-F digits at bit 5, roughly 0.4% of examples, so a 100-example
    # run failed about a third of the time and passed the rest. Earlier green
    # full-suite runs in this repository were luck.
    #
    # The fix is to the GRAMMAR, not to the test's claim. The firmware emits
    # `Serial.println(crc, HEX)`, which is uppercase, so a lowercase CRC field
    # did not come from the firmware. Requiring the canonical form makes the
    # universal claim true: every flip inside the field now either yields a
    # different uppercase hex digit (CRC mismatch) or a character outside
    # [0-9A-F] (grammar error).
    if any(c not in "0123456789ABCDEF" for c in given):
        raise ProtocolError(
            f"CRC field {given!r} is not four UPPERCASE hex digits; the "
            f"firmware emits uppercase, so this frame is not canonical")
    given_value = int(given, 16)
    actual = crc16_ccitt(body.encode("ascii", errors="replace"))
    if actual != given_value:
        raise ProtocolError(
            f"CRC mismatch: frame says {given_value:04X}, bytes give "
            f"{actual:04X}")

    parts = body.split(",")
    if parts[0] != MAGIC:
        raise ProtocolError(f"magic {parts[0]!r} is not {MAGIC!r}")
    if len(parts) != FIELD_COUNT:
        raise ProtocolError(
            f"{len(parts)} fields, expected {FIELD_COUNT}")
    try:
        return Record(
            seq=int(parts[1]), sweep=int(parts[2]),
            commanded_channel=int(parts[3]), readback_channel=int(parts[4]),
            sensor=parts[5], status=parts[6], milli=int(parts[7]),
            unit=parts[8], controller_us=int(parts[9]),
            i2c_error=int(parts[10]), retries=int(parts[11]))
    except ProtocolError:
        raise
    except ValueError as error:
        raise ProtocolError(f"non-integer field: {error}") from error
