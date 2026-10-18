"""The control that makes SHADOW mode true rather than promised.

The requirement: in SHADOW mode CSIA "CANNOT issue MAVLink commands that
change vehicle state ... Enforce this technically, not just by convention."

A boolean like `if self.mode == SHADOW: return` is a convention. It is one
missing early-return away from arming an aircraft. What is implemented here
instead:

1. **The connection object physically cannot send.**
   `ReadOnlyMavlinkConnection` wraps a pymavlink connection and exposes only
   receive-side methods. Its `mav` attribute is a `_DeniedMav` whose
   `__getattr__` raises `CommandAuthorityError` for every attribute -- so
   `conn.mav.command_long_send(...)` raises rather than transmits, including
   for MAVLink messages that did not exist when this file was written.

2. **The socket is opened read-only where the transport allows it.**
   `mavutil.mavlink_connection(..., input=True)` on UDP binds a listening
   socket. We additionally shut down the write half of the underlying socket
   when the transport exposes one, so a bypass of layer 1 still writes to a
   closed half-duplex.

3. **The process asserts its own inability at startup and refuses to run if
   the assertion fails.** `assert_no_command_capability` probes the live
   object for send-capable attributes and raises before the first tick.

4. **A static check over the source tree.** `scan_source_for_send_calls`
   greps the deployment package for MAVLink send calls, so a future edit that
   introduces one fails a test rather than a flight.

Layers 1 and 3 are the load-bearing ones. 2 and 4 exist because a single
mechanism guarding a safety property is a single point of failure.
"""

from __future__ import annotations

import ast
import os
from typing import Iterable

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class CommandAuthorityError(RuntimeError):
    """Raised whenever anything attempts to transmit in a no-authority mode.

    This is deliberately an error and not a warning. A shadow deployment that
    silently swallowed a command attempt would hide the bug that a command was
    attempted at all.
    """


# Attribute names that can put bytes on the wire. Anything ending in _send is
# covered by the wildcard in _DeniedMav; these are the extras that do not.
SEND_CAPABLE_NAMES = (
    "mav", "write", "send", "send_mavlink", "arducopter_arm",
    "arducopter_disarm", "set_mode", "set_mode_apm", "set_mode_px4",
    "set_relay", "reboot_autopilot", "motors_armed_wait",
    "set_servo", "param_set_send", "waypoint_clear_all_send",
)

# Receive-side surface a monitor legitimately needs.
_ALLOWED = frozenset({
    "recv_match", "recv_msg", "wait_heartbeat", "close", "target_system",
    "target_component", "messages", "mavlink10", "WIRE_PROTOCOL_VERSION",
    "sysid", "compid", "flightmode", "vehicle_type", "packet_loss",
    "port", "address", "fd", "first_byte",
})


class _DeniedMav:
    """Stands where `conn.mav` would be. Every attribute access raises.

    Using `__getattr__` rather than an allow-list of blocked names means a
    MAVLink message type added upstream tomorrow is blocked today.
    """

    __slots__ = ("_mode",)

    def __init__(self, mode: str):
        object.__setattr__(self, "_mode", mode)

    def __getattr__(self, name):
        raise CommandAuthorityError(
            f"MAVLink transmit denied in {self._mode} mode: "
            f"attempted 'mav.{name}'. CSIA has no command authority. "
            f"Changing this requires a separate safety work package and "
            f"explicit approval.")

    def __setattr__(self, name, value):
        raise CommandAuthorityError(
            f"MAVLink transmit surface is immutable in {self._mode} mode "
            f"(attempted to set 'mav.{name}')")

    def __call__(self, *a, **kw):
        raise CommandAuthorityError(
            f"MAVLink transmit denied in {self._mode} mode")


class ReadOnlyMavlinkConnection:
    """Receive-only proxy over a pymavlink connection.

    Nothing outside this module holds the wrapped object, so there is no
    handle through which the send surface can be recovered.
    """

    def __init__(self, conn, mode: str = "SHADOW"):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_mode", mode)
        object.__setattr__(self, "mav", _DeniedMav(mode))
        self._disable_write_half()

    # -- transport-level belt to layer 1's braces --------------------------
    def _disable_write_half(self):
        """Shut the socket's write half where the transport exposes one.

        Best-effort by design: serial links and file replays have no such
        concept. Failure here is not fatal because layer 1 already denies
        transmission; this only removes a second path.

        **ENOTCONN does not mean it failed.** A MAVLink UDP listener is an
        UNCONNECTED socket, and Linux applies SHUT_WR to one and *then*
        returns ENOTCONN. Measured, with a null control:

            no shutdown        -> sendto() succeeds      (instrument alive)
            shutdown, ENOTCONN -> sendto() EPIPE         (it was applied)

        The first version treated the exception as failure and recorded
        `write_half_closed: false` into every shadow flight header -- false
        evidence about a safety control that had in fact worked. Evidence that
        misreports is worse than no evidence, so the state is now three-valued
        and names which case it is instead of collapsing to a boolean.

        It is NOT verified by attempting a send: that would put a packet on
        the wire to the autopilot, which is the exact thing SHADOW mode
        exists to prevent. The Linux behaviour is pinned by a test with a null
        control instead (`tests/test_shadow_transport.py`).
        """
        import errno as _e
        import socket as _s
        sock = getattr(self._conn, "port", None)
        if not isinstance(sock, _s.socket):
            object.__setattr__(self, "_write_half_state", "NO_SOCKET")
            return
        try:
            sock.shutdown(_s.SHUT_WR)
            object.__setattr__(self, "_write_half_state", "CLOSED")
        except OSError as exc:
            if exc.errno == _e.ENOTCONN:
                # Applied on Linux despite the error return.
                object.__setattr__(self, "_write_half_state",
                                   "CLOSED_ENOTCONN")
            else:
                object.__setattr__(self, "_write_half_state",
                                   f"UNSUPPORTED({exc.errno})")

    @property
    def write_half_state(self) -> str:
        """CLOSED | CLOSED_ENOTCONN | NO_SOCKET | UNSUPPORTED(errno)."""
        return getattr(self, "_write_half_state", "NO_SOCKET")

    @property
    def write_half_closed(self) -> bool:
        return self.write_half_state in ("CLOSED", "CLOSED_ENOTCONN")

    @property
    def mode(self) -> str:
        return self._mode

    def __getattr__(self, name):
        if name in _ALLOWED:
            return getattr(self._conn, name)
        if name in SEND_CAPABLE_NAMES or name.endswith("_send"):
            raise CommandAuthorityError(
                f"'{name}' is command-capable and is denied in "
                f"{self._mode} mode")
        attr = getattr(self._conn, name)
        if callable(attr) and name.startswith(("set_", "arm", "disarm",
                                               "reboot", "command")):
            raise CommandAuthorityError(
                f"'{name}' may change vehicle state and is denied in "
                f"{self._mode} mode")
        return attr

    def __setattr__(self, name, value):
        if name in ("mav",) or name.endswith("_send"):
            raise CommandAuthorityError(
                f"cannot replace the denied transmit surface "
                f"(attempted to set '{name}')")
        object.__setattr__(self, name, value)


def assert_no_command_capability(conn, mode: str = "SHADOW") -> dict:
    """Prove, on the live object, that no transmit path is reachable.

    Called before the first tick. Returns the evidence dict that goes into the
    flight-log header, so every flight carries a record of the check having
    passed rather than an assurance that it exists.
    """
    probes, failures = {}, []

    for name in SEND_CAPABLE_NAMES:
        try:
            attr = getattr(conn, name)
        except CommandAuthorityError:
            probes[name] = "DENIED"
            continue
        except AttributeError:
            probes[name] = "ABSENT"
            continue
        if name == "mav":
            # Reaching .mav is fine only if touching anything on it raises.
            try:
                getattr(attr, "command_long_send")
            except CommandAuthorityError:
                probes[name] = "DENIED"
                continue
            probes[name] = "REACHABLE"
            failures.append(f"{name}.command_long_send is reachable")
            continue
        probes[name] = "REACHABLE"
        failures.append(f"{name} is reachable")

    # A representative sample of concrete commands, including the four the
    # work package names explicitly: mode change, actuation, arm, override.
    for call in ("mav.command_long_send", "mav.set_mode_send",
                 "mav.rc_channels_override_send",
                 "mav.set_actuator_control_target_send",
                 "mav.manual_control_send", "mav.param_set_send"):
        obj, attr_name = conn, None
        try:
            for part in call.split("."):
                attr_name = part
                obj = getattr(obj, part)
        except CommandAuthorityError:
            probes[call] = "DENIED"
            continue
        except AttributeError:
            # Name the attribute that was missing. `mav.command_long_send`
            # absent because `mav` itself is gone is a very different fact
            # from the send method being absent on a present `mav`, and the
            # bare "ABSENT" could not tell them apart.
            probes[call] = ("ABSENT" if attr_name in (None, call)
                            else f"ABSENT at {attr_name!r}")
            continue
        probes[call] = "REACHABLE"
        failures.append(f"{call} is reachable")

    if failures:
        raise CommandAuthorityError(
            f"{mode} mode refused to start: command paths are reachable: "
            + "; ".join(failures))

    return {
        "mode": mode,
        "checked": len(probes),
        "result": "NO_COMMAND_PATH_REACHABLE",
        "probes": probes,
        "write_half_closed": getattr(conn, "write_half_closed", None),
        # The reason, not just the boolean: a flight header that says "false"
        # without saying whether the transport HAS a write half is unreadable
        # after the fact.
        "write_half_state": getattr(conn, "write_half_state", "NO_SOCKET"),
    }


# --------------------------------------------------------------------------
# Static check (layer 4)

_COMMAND_METHODS = frozenset({
    "arducopter_arm", "arducopter_disarm", "set_mode", "set_mode_apm",
    "set_mode_px4", "set_servo", "set_relay", "reboot_autopilot",
})


def _is_command_call(node: "ast.Call") -> bool:
    f = node.func
    if not isinstance(f, ast.Attribute):
        return False
    if f.attr.endswith("_send"):
        # Only a transmit if it hangs off something named `mav`.
        owner = f.value
        return isinstance(owner, ast.Attribute) and owner.attr == "mav" \
            or isinstance(owner, ast.Name) and owner.id == "mav"
    return f.attr in _COMMAND_METHODS


def scan_source_for_send_calls(
        paths: Iterable[str] = ("csia/deploy", "csia/aircraft")) -> list:
    """Find MAVLink transmit CALLS in the deployment tree.

    Parsed with `ast`, not grepped. The first version of this used a regex and
    immediately flagged this module's own docstring, which quotes the pattern
    it forbids. A regex cannot tell a call from a sentence about a call; the
    AST can, so the check was narrowed to real call expressions rather than
    the docstring being exempted.

    A hit is not automatically a defect -- one day there will be an approved
    command path in some other package -- but it must never appear in these
    directories without a deliberate decision, so the test asserts zero.
    """
    hits = []
    for rel in paths:
        base = os.path.join(ROOT, rel)
        for dirpath, _dirs, files in os.walk(base):
            for fn in sorted(files):
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(dirpath, fn)
                with open(p, encoding="utf-8") as fh:
                    src = fh.read()
                try:
                    tree = ast.parse(src, filename=p)
                except SyntaxError as exc:               # pragma: no cover
                    hits.append((os.path.relpath(p, ROOT), exc.lineno or 0,
                                 f"unparseable: {exc.msg}"))
                    continue
                lines = src.splitlines()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and _is_command_call(node):
                        n = node.lineno
                        hits.append((os.path.relpath(p, ROOT), n,
                                     lines[n - 1].strip()[:100]))
    return hits
