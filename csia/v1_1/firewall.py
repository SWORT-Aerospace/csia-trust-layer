"""Output firewall — Phase 4 §25.

The read-only interface a later HIL or shadow flight uses. It permits
telemetry reads and logging, and denies every write and control operation.

**DEFAULT-DENY.** `request()` permits only what is explicitly allow-listed and
raises on everything else, so a MAVLink command added upstream tomorrow is
denied today. An allow-list of *permitted* operations is the correct shape
here; a deny-list of *forbidden* ones would be one missing entry away from
arming an aircraft.

WHAT ALREADY EXISTED, AND WHAT THIS ADDS
----------------------------------------
`csia/deploy/guard.py` already denies the MAVLink **transmit surface**:
`ReadOnlyMavlinkConnection` replaces `conn.mav` with an object whose every
attribute access raises, shuts the socket's write half where the transport
has one, asserts its own inability at startup, and is backed by a static scan
of the deployment package. That is the transport layer and it is not
duplicated here.

This module adds the layer above it: an **operation-level** policy, so the
question "may CSIA change the flight mode?" has an answer that does not depend
on which pymavlink method name someone happens to call. The two compose —
`attach()` returns a firewalled connection built on the existing guard — and a
bypass of either still meets the other.

Nothing in this module transmits anything. It raises or it returns a
read-only object.
"""

from __future__ import annotations

from ..deploy.guard import CommandAuthorityError, ReadOnlyMavlinkConnection

#: Operations a monitor legitimately needs. Everything else is denied.
PERMITTED = frozenset({
    "READ_TELEMETRY",       # receive and decode vehicle messages
    "READ_PARAMETERS",      # read-only parameter inspection
    "WRITE_LOG",            # append to the flight log / ledger
    "READ_LOG",
    "EMIT_OUTPUT",          # produce a csia_output_v1_1 payload
    "EMIT_RECOMMENDATION",  # advisory strings; no transport
})

#: Named for the error message and for the test matrix. Membership here is
#: NOT what denies them -- absence from PERMITTED is. Listing them separately
#: means a test can assert each one by name, which is what §25 asks for.
DENIED = {
    "WRITE_PARAMETER": "parameter write",
    "SET_FLIGHT_MODE": "flight mode change",
    "WRITE_MISSION": "mission write",
    "CLEAR_MISSION": "mission write",
    "ACTUATOR_COMMAND": "actuator command",
    "SET_SERVO": "actuator command",
    "ARM": "arm/disarm",
    "DISARM": "arm/disarm",
    "RTL": "return-to-launch",
    "LAND": "land",
    "TAKEOFF": "takeoff",
    "REBOOT_AUTOPILOT": "autopilot reboot",
    "SET_HOME": "home position write",
    "CALIBRATE": "calibration command",
}


class OutputFirewall:
    """Operation-level read-only policy. Default-deny."""

    def __init__(self, mode: str = "SHADOW"):
        self.mode = mode
        self.denied_attempts: list = []

    def permits(self, operation: str) -> bool:
        return operation in PERMITTED

    def request(self, operation: str):
        """Return the operation name if permitted; raise otherwise.

        The denial is recorded before raising. A shadow deployment that
        silently swallowed a command attempt would hide the fact that one was
        attempted, which is the more important half of the event.
        """
        if operation in PERMITTED:
            return operation
        self.denied_attempts.append(operation)
        what = DENIED.get(operation, "unrecognised operation")
        raise CommandAuthorityError(
            f"{operation} ({what}) is denied in {self.mode} mode. CSIA has "
            f"no command authority: it reports and logs. Granting one is a "
            f"separate safety work package, not a configuration change.")

    def attach(self, conn):
        """Wrap a live connection with the transport-level guard beneath."""
        return ReadOnlyMavlinkConnection(conn, mode=self.mode)

    def evidence(self) -> dict:
        """Goes into the flight-log header, so a flight carries a record of
        the control having been in place rather than an assurance that it
        exists."""
        return {"mode": self.mode,
                "policy": "DEFAULT_DENY",
                "permitted_operations": sorted(PERMITTED),
                "denied_attempts": list(self.denied_attempts),
                "transport_guard": "csia.deploy.guard.ReadOnlyMavlinkConnection"}
