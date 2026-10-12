"""Deployment layer: shadow mode, transport guard, flight logging.

Separation of concerns, enforced by module boundaries rather than by comment:

    csia.aircraft.adapters   transport -> canonical state
    csia.runtime.online      FROZEN v1 diagnostic core
    csia.deploy.shadow       orchestration, with zero command authority
    csia.deploy.flight_log   deterministic S9 record
    csia.deploy.guard        the thing that makes "cannot command" true

`guard` is imported by `shadow` before any connection is opened, and it
monkey-patches nothing: it wraps the MAVLink connection in a proxy whose
`mav` attribute raises on every `*_send` method. There is no flag to flip and
no code path that skips it, because a mode you can disable by setting a
variable is a convention, not a control.
"""

from .guard import (CommandAuthorityError, ReadOnlyMavlinkConnection,
                    assert_no_command_capability)
from .flight_log import FlightLog, FlightLogHeader
from .shadow import ShadowRunner, ShadowConfig, Mode

__all__ = ["CommandAuthorityError", "ReadOnlyMavlinkConnection",
           "assert_no_command_capability", "FlightLog", "FlightLogHeader",
           "ShadowRunner", "ShadowConfig", "Mode"]
