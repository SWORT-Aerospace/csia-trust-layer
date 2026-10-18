"""SHADOW mode must be unable to command. Proved, not asserted.

These tests are the safety case for putting CSIA on an aircraft. They are
adversarial on purpose: each one plays the part of code that is *trying* to
transmit, and asserts that it cannot. A test that only checks the happy path
would pass against a guard that does nothing.
"""

import pytest

from csia.deploy.guard import (CommandAuthorityError,
                               ReadOnlyMavlinkConnection,
                               assert_no_command_capability,
                               scan_source_for_send_calls)
from csia.deploy.shadow import Mode, ShadowConfig, ShadowRunner, env_mode


class FakeMav:
    """A fully command-capable MAVLink interface, as pymavlink would give us."""

    def __init__(self):
        self.sent = []

    def command_long_send(self, *a, **kw):
        self.sent.append(("command_long", a, kw))

    def set_mode_send(self, *a, **kw):
        self.sent.append(("set_mode", a, kw))

    def rc_channels_override_send(self, *a, **kw):
        self.sent.append(("rc_override", a, kw))

    def set_actuator_control_target_send(self, *a, **kw):
        self.sent.append(("actuator", a, kw))

    def manual_control_send(self, *a, **kw):
        self.sent.append(("manual", a, kw))

    def param_set_send(self, *a, **kw):
        self.sent.append(("param_set", a, kw))

    def heartbeat_send(self, *a, **kw):
        self.sent.append(("heartbeat", a, kw))


class FakeConnection:
    def __init__(self, messages=()):
        self.mav = FakeMav()
        self.target_system = 1
        self.target_component = 1
        self._messages = list(messages)
        self.closed = False

    def recv_match(self, **kw):
        return self._messages.pop(0) if self._messages else None

    def wait_heartbeat(self, **kw):
        return True

    def close(self):
        self.closed = True

    # command-capable helpers pymavlink really does expose
    def arducopter_arm(self):
        self.mav.command_long_send(1, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0)

    def arducopter_disarm(self):
        self.mav.command_long_send(1, 1, 400, 0, 0, 0, 0, 0, 0, 0, 0)

    def set_mode(self, *a, **kw):
        self.mav.set_mode_send(*a, **kw)

    def write(self, data):
        raise AssertionError("raw write reached the transport")


# --------------------------------------------------------------------------
# The four things the work package says shadow mode CANNOT do.

def test_cannot_issue_mavlink_commands():
    conn = ReadOnlyMavlinkConnection(FakeConnection())
    with pytest.raises(CommandAuthorityError):
        conn.mav.command_long_send(1, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0)


def test_cannot_change_flight_mode():
    conn = ReadOnlyMavlinkConnection(FakeConnection())
    with pytest.raises(CommandAuthorityError):
        conn.mav.set_mode_send(1, 1, 4)
    with pytest.raises(CommandAuthorityError):
        conn.set_mode("GUIDED")


def test_cannot_actuate_motors_or_servos():
    conn = ReadOnlyMavlinkConnection(FakeConnection())
    for call in ("set_actuator_control_target_send",
                 "rc_channels_override_send", "manual_control_send"):
        with pytest.raises(CommandAuthorityError):
            getattr(conn.mav, call)(0, 0, 0)


def test_cannot_arm_or_disarm():
    conn = ReadOnlyMavlinkConnection(FakeConnection())
    for call in ("arducopter_arm", "arducopter_disarm"):
        with pytest.raises(CommandAuthorityError):
            getattr(conn, call)()


def test_cannot_override_via_param_set():
    conn = ReadOnlyMavlinkConnection(FakeConnection())
    with pytest.raises(CommandAuthorityError):
        conn.mav.param_set_send(1, 1, b"SIM_GPS1_GLITCH_X", 5.0, 9)


# --------------------------------------------------------------------------
# Generality: the guard must block things it has never heard of.

def test_blocks_unknown_future_send_methods():
    """A MAVLink message added upstream tomorrow must be blocked today."""
    conn = ReadOnlyMavlinkConnection(FakeConnection())
    with pytest.raises(CommandAuthorityError):
        conn.mav.some_message_invented_in_2027_send(1, 2, 3)


def test_transmit_surface_cannot_be_replaced():
    """The obvious bypass -- swap .mav for the real one -- must fail."""
    raw = FakeConnection()
    conn = ReadOnlyMavlinkConnection(raw)
    with pytest.raises(CommandAuthorityError):
        conn.mav = raw.mav
    with pytest.raises(CommandAuthorityError):
        conn.mav.heartbeat_send(1, 2, 3, 4, 5)


def test_denied_mav_attributes_cannot_be_set():
    conn = ReadOnlyMavlinkConnection(FakeConnection())
    with pytest.raises(CommandAuthorityError):
        conn.mav.command_long_send = lambda *a, **kw: None


def test_no_command_reaches_the_underlying_transport():
    """End to end: after every attempt above, nothing was actually sent."""
    raw = FakeConnection()
    conn = ReadOnlyMavlinkConnection(raw)
    for attempt in (lambda: conn.mav.command_long_send(1, 1, 400, 0, 1),
                    lambda: conn.mav.set_mode_send(1, 1, 4),
                    lambda: conn.arducopter_arm(),
                    lambda: conn.set_mode("LAND")):
        with pytest.raises(CommandAuthorityError):
            attempt()
    assert raw.mav.sent == [], f"commands reached the transport: {raw.mav.sent}"


def test_receive_side_still_works():
    """A guard that broke reception would be useless rather than safe."""
    raw = FakeConnection(messages=["m1", "m2"])
    conn = ReadOnlyMavlinkConnection(raw)
    assert conn.recv_match() == "m1"
    assert conn.wait_heartbeat() is True
    assert conn.target_system == 1
    conn.close()
    assert raw.closed is True


# --------------------------------------------------------------------------
# Startup assertion and static scan.

def test_startup_assertion_passes_on_guarded_connection():
    conn = ReadOnlyMavlinkConnection(FakeConnection())
    ev = assert_no_command_capability(conn)
    assert ev["result"] == "NO_COMMAND_PATH_REACHABLE"
    assert ev["checked"] > 0
    assert all(v in ("DENIED", "ABSENT") for v in ev["probes"].values())


def test_startup_assertion_fails_on_unguarded_connection():
    """The assertion must be capable of failing, or it proves nothing."""
    with pytest.raises(CommandAuthorityError):
        assert_no_command_capability(FakeConnection())


def test_no_send_calls_in_deployment_source():
    hits = scan_source_for_send_calls()
    assert hits == [], f"MAVLink transmit calls in the deploy tree: {hits}"


# --------------------------------------------------------------------------
# Mode semantics.

def test_no_mode_has_command_authority():
    assert [m for m in Mode if m.may_command] == []


def test_env_mode_defaults_to_shadow(monkeypatch):
    monkeypatch.delenv("CSIA_MODE", raising=False)
    assert env_mode() is Mode.SHADOW


def test_env_mode_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("CSIA_MODE", "ACTIVE")
    with pytest.raises(ValueError):
        env_mode()


def test_runner_connects_and_records_authority_evidence(tmp_path):
    cfg = ShadowConfig(log_dir=str(tmp_path), mode=Mode.SHADOW)
    r = ShadowRunner(cfg, connection_factory=FakeConnection)
    r.connect()
    assert r.authority_evidence["result"] == "NO_COMMAND_PATH_REACHABLE"
    with pytest.raises(CommandAuthorityError):
        r.conn.mav.command_long_send(1, 1, 400, 0, 1)


def test_advisory_consumer_gets_no_connection(tmp_path):
    """The advisory hook must receive data, not a handle to the vehicle."""
    seen = []
    cfg = ShadowConfig(log_dir=str(tmp_path), mode=Mode.ADVISORY,
                       tick_hz=50.0)
    r = ShadowRunner(cfg, consumer=lambda rec, t: seen.append(rec),
                     connection_factory=FakeConnection)
    r.connect()
    r.run(message_iter=iter([None] * 5))
    for rec in seen:
        assert isinstance(rec, dict)
        assert rec["authority"] == "NONE"
        assert not any(hasattr(v, "mav") for v in rec.values())


def test_deploy_never_imports_the_simulator_rigs():
    """`csia.simulation.rigs` may command a vehicle. Deploy may not touch it.

    The rigs module exists so a qualification probe can arm and climb. Nothing
    in the deployment path has any business importing it, and the static
    send-call scan does not cover `csia/simulation`, so this is the check that
    keeps the two apart.
    """
    import ast
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    offenders = []
    for dirpath, _dirs, files in os.walk(os.path.join(root, "csia", "deploy")):
        for fn in sorted(f for f in files if f.endswith(".py")):
            path = os.path.join(dirpath, fn)
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "")] + \
                            [a.name for a in node.names]
                if any("rigs" in n for n in names):
                    offenders.append(f"{fn}:{node.lineno}")
    assert not offenders, (
        f"csia/deploy imports the simulator rigs at {offenders}: a shadow "
        f"deployment must not be able to reach command-capable code")
