"""TCA9548A device constants, and an honest statement of where they came from.

PROVENANCE OF EVERY CONSTANT IN THIS FILE
-----------------------------------------
**The datasheet was NOT retrieved in this environment.** Outbound HTTPS to
`ti.com` and to a datasheet mirror both returned `403` at the agent proxy on
2026-09-15, which is the same egress condition already recorded against this
repository's bibliography work (`docs/CURRENT_PROGRAM_STATE.md`, blocker 1).

So every value below is written from general engineering knowledge of the
part, **not** from a hashed primary source. That is exactly the situation this
repository refuses to paper over elsewhere, and it is not treated differently
here because the source happens to be a datasheet rather than a paper.

Consequence, enforced rather than advised: :data:`DATASHEET_STATUS` is
``NOT_RETRIEVED``, and :func:`require_verified_datasheet` raises. Any code path
that would drive real silicon must call it first, so the constants cannot reach
hardware while their provenance is unverified. Simulation is unaffected --
a simulator that is wrong in the same way as the model is still a sound test of
the *logic*, and is not evidence about the *device*.

To clear this: retrieve the datasheet, record its SHA-256 and revision in
:data:`DATASHEET_STATUS`, check each constant below against it, and flip the
status. Do not flip it because the constants look right.

WHAT THE PART IS
----------------
An 8-channel bidirectional I2C switch. One 8-bit control register; bit *n*
connects upstream SDA/SCL to downstream channel *n*. Any number of bits may be
set at once, including none and all -- which is the root of the identity
hazard this package exists to make visible, because two enabled channels can
host two devices at the SAME address.
"""
from __future__ import annotations

from typing import Dict, Optional

#: Set to a dict with ``sha256``, ``revision`` and ``retrieved_utc`` once the
#: datasheet has actually been fetched and hashed. ``None`` means it has not.
DATASHEET_SHA256: Optional[str] = None

DATASHEET_STATUS = "NOT_RETRIEVED"

DATASHEET_ACCESS_RECORD: Dict[str, str] = {
    "attempted_utc": "2026-09-15",
    "ti.com/lit/ds/symlink/tca9548a.pdf": "CONNECT tunnel failed, 403",
    "cdn-shop.adafruit.com/datasheets/tca9548a.pdf": "CONNECT tunnel failed, 403",
    "conclusion": "PRIMARY_SOURCE_NOT_RETRIEVED",
}

#: Channel count. Bit *n* of the control register enables channel *n*.
CHANNEL_COUNT = 8

#: Valid 7-bit addresses, set by the A0/A1/A2 pins.
ADDRESS_MIN = 0x70
ADDRESS_MAX = 0x77
VALID_ADDRESSES = tuple(range(ADDRESS_MIN, ADDRESS_MAX + 1))

#: The control register value after power-on reset: every channel disconnected.
#: This matters more than it looks. A brownout that resets the mux but not the
#: host leaves the host believing a channel is selected when none is, and the
#: next read is addressed into a disconnected bus.
POR_CONTROL_REGISTER = 0x00

#: The whole device state is one readable byte. That readability is the only
#: reason :class:`~csia_bus_provenance.provenance.Binding` can ever be
#: VERIFIED rather than ASSUMED, so it is load-bearing, not a detail.
CONTROL_REGISTER_IS_READABLE = True

#: Reserved I2C addresses that a downstream device must not claim. General
#: I2C, not TCA9548A-specific.
RESERVED_ADDRESSES = frozenset(
    list(range(0x00, 0x08)) + list(range(0x78, 0x80)))


class DatasheetNotVerified(RuntimeError):
    """Raised when unverified constants would have reached real hardware."""


def require_verified_datasheet(action: str) -> None:
    """Gate any hardware-touching action on verified device constants.

    Simulation does not call this. Driving silicon must.
    """
    if DATASHEET_STATUS != "VERIFIED" or DATASHEET_SHA256 is None:
        raise DatasheetNotVerified(
            f"refusing to {action}: the TCA9548A datasheet has not been "
            f"retrieved or hashed in this environment "
            f"(status={DATASHEET_STATUS!r}), so the register semantics in "
            f"csia_bus_provenance/datasheet.py are unverified general "
            f"knowledge. Retrieve it, hash it, check each constant, then set "
            f"DATASHEET_STATUS='VERIFIED'. Do not set it because the "
            f"constants look right.")


def channel_mask(*channels: int) -> int:
    """The control-register value that enables exactly ``channels``."""
    mask = 0
    for channel in channels:
        if not 0 <= channel < CHANNEL_COUNT:
            raise ValueError(
                f"channel {channel} outside 0..{CHANNEL_COUNT - 1}")
        mask |= 1 << channel
    return mask


def channels_in(mask: int) -> tuple:
    """Which channels a control-register value enables, ascending."""
    if not 0 <= mask <= 0xFF:
        raise ValueError(f"control register is one byte; got {mask}")
    return tuple(c for c in range(CHANNEL_COUNT) if mask & (1 << c))
