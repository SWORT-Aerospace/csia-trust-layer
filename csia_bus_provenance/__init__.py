"""Device identity on a shared I2C bus behind a TCA9548A multiplexer.

STATUS: SIMULATOR-ONLY MODEL. NO HARDWARE HAS BEEN OPERATED.
------------------------------------------------------------
Nothing in this package has touched a real TCA9548A, a real sensor or a real
bus. No hardware exists in this environment, the TCA9548A datasheet could not
be retrieved (`datasheet.py`), and no module here imports any hardware
interface. Every number a consumer produces today comes from
:mod:`csia_bus_provenance.simulator`.

It is a model and a vocabulary, built before hardware deliberately, on the
precedent already set by `research/physical_validation/prereg/
E2_HARDWARE_BOUNDARY_PREREG.md` -- which fixes its design "before any hardware
is purchased, so that no design decision can be made after seeing a
measurement."

WHY IT EXISTS
-------------
A multiplexer is bought because two sensors share an address. From that moment
the address stops identifying the device, and what identifies it is the address
*plus the channel selected at the moment of the read*. The second half of that
pair lives in a register the host wrote earlier and typically never checks.

`research/evidence_semantics/` records three findings, all of the form "an
absence collapses into a usable value". A mux permits a worse member of the
same family: a real, healthy device reporting a true measurement of itself,
under the wrong name. Nothing in the bytes is wrong, so no inspection of the
value recovers it.

AUTHORITY
---------
Read-only. This package models sensor acquisition and says what the bus can
and cannot establish about identity. It issues no command, holds no actuator
authority, and takes no decision about whether a capability is supported --
that is FORGE's, downstream, on evidence this layer hands it.
"""
from __future__ import annotations

from .datasheet import (CHANNEL_COUNT, DATASHEET_STATUS, DatasheetNotVerified,
                        channel_mask, channels_in, require_verified_datasheet)
from .provenance import (ALL_BINDINGS, AMBIGUOUS, ASSUMED, ESTABLISHED,
                         MISATTRIBUTED, NO_RESPONDER, NOT_ATTRIBUTABLE,
                         UNBOUND, VERIFIED, Attribution, Selection,
                         accepts, attribute)
from .simulator import FAULTS, BusError, MuxSimulator
from .topology import Device, Mux, Topology

#: This package is acquisition-side. It never decides and never commands.
LAYER = "acquisition"
HAS_ACTUATOR_AUTHORITY = False
HARDWARE_VALIDATED = False

__all__ = [
    "CHANNEL_COUNT", "DATASHEET_STATUS", "DatasheetNotVerified",
    "channel_mask", "channels_in", "require_verified_datasheet",
    "ALL_BINDINGS", "AMBIGUOUS", "ASSUMED", "ESTABLISHED", "MISATTRIBUTED",
    "NO_RESPONDER", "NOT_ATTRIBUTABLE", "UNBOUND", "VERIFIED",
    "Attribution", "Selection", "accepts", "attribute",
    "FAULTS", "BusError", "MuxSimulator", "Device", "Mux",
    "Topology", "LAYER", "HAS_ACTUATOR_AUTHORITY", "HARDWARE_VALIDATED",
]
