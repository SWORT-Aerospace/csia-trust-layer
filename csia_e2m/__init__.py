"""E2M host-side acquisition: the external hardware-facing layer.

STATUS: `AUTHORIZED_NOT_RUN`. NO HARDWARE HAS BEEN OPERATED.
------------------------------------------------------------
Owner authorization exists and is recorded verbatim in
`research/bus_provenance/OWNER_DECISION_E2M_2026-09-16.md`
(`APPROVED_WITH_CONDITIONS`, 16 September 2026). Permission is not a gate pass:
the datasheet, sensor-inventory, electrical-compatibility and
execution-environment gates are assessed in `E2M_GATE_STATUS.md` and **all four
are open**. No frame in this repository came from a bus.

WHY THIS IS A SEPARATE PACKAGE FROM `csia_bus_provenance`
----------------------------------------------------------
The owner's decision §4 requires that `csia_bus_provenance` keep its AST
boundary -- it imports no hardware interface -- and that all physical I²C and
serial access live in an external acquisition layer. This is that layer.

The split is enforced in both directions by test:
`csia_bus_provenance` imports nothing hardware-facing, and this package does
not import `csia_bus_provenance` for anything that would let a hardware concern
leak back into it.

LAYERING
--------
    firmware (Arduino)  ->  protocol  ->  transport  ->  logging
                                                            |
                                        replay  <-  immutable raw log
                                          |
                              identity + ancestry  ->  CSIA-facing observation

`faults` derives new streams from a replayed log and never writes the raw log.
"""
from __future__ import annotations

from . import ancestry, faults, identity, logging, protocol, replay, transport

#: This package may open a serial port. It has no actuator authority, issues no
#: command to any vehicle, and imports no autopilot library.
LAYER = "acquisition"
HAS_ACTUATOR_AUTHORITY = False
HARDWARE_VALIDATED = False
CAMPAIGN_STATE = "AUTHORIZED_NOT_RUN"

__all__ = ["ancestry", "faults", "identity", "logging", "protocol", "replay",
           "transport", "LAYER", "HAS_ACTUATOR_AUTHORITY",
           "HARDWARE_VALIDATED", "CAMPAIGN_STATE"]
