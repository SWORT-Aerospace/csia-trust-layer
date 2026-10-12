"""Layer 2 of the shadow guard, against a REAL socket.

`tests/test_shadow_mode.py` proves layer 1 (the denied transmit surface) using
a fake connection. That is the load-bearing control, but it is the only one
those tests touch. This file exercises the transport-level belt against an
actual kernel socket, because the behaviour that matters here is the
operating system's, and a fake cannot tell us what Linux does.

It found a real defect on its first run. See `test_enotconn_still_applies`.
"""

import errno
import socket

import pytest

from csia.deploy.guard import ReadOnlyMavlinkConnection


class SocketConnection:
    """Minimal stand-in shaped like a pymavlink UDP connection.

    pymavlink exposes the socket as `.port`, which is what the guard reaches
    for. Nothing else here matters.
    """

    def __init__(self, sock):
        self.port = sock
        self.mav = object()
        self.target_system = 1
        self.target_component = 1

    def recv_match(self, **kw):
        return None

    def close(self):
        self.port.close()


def _udp_listener():
    """An unconnected UDP socket: exactly what a MAVLink listener is."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    return s


# --------------------------------------------------------------------------
# RULE A: the instrument needs a null control before any of this means
# anything. If a socket that was never shut down also cannot send, the test
# proves nothing about shutdown.

def test_null_control_socket_can_send():
    s = _udp_listener()
    try:
        s.sendto(b"x", ("127.0.0.1", 9))     # discard port
    except OSError as exc:                    # pragma: no cover
        pytest.fail(f"null control cannot send ({exc.strerror}); the "
                    f"instrument is dead and no shutdown result is readable")
    finally:
        s.close()


def test_enotconn_still_applies_the_shutdown():
    """The defect this file exists for.

    Linux applies SHUT_WR to an unconnected UDP socket and THEN returns
    ENOTCONN. Treating the exception as failure -- which the guard used to do
    -- recorded `write_half_closed: false` into every shadow flight header for
    a control that had actually worked.

    If a future kernel or a non-Linux host stops behaving this way, this test
    fails and the CLOSED_ENOTCONN mapping must be revisited rather than
    trusted.
    """
    s = _udp_listener()
    try:
        with pytest.raises(OSError) as ei:
            s.shutdown(socket.SHUT_WR)
        assert ei.value.errno == errno.ENOTCONN

        # ... and yet the write half is gone.
        with pytest.raises(OSError) as send_err:
            s.sendto(b"x", ("127.0.0.1", 9))
        assert send_err.value.errno in (errno.EPIPE, errno.ESHUTDOWN)
    finally:
        s.close()


# --------------------------------------------------------------------------
# What the guard reports

def test_guard_reports_closed_enotconn_for_a_udp_listener():
    s = _udp_listener()
    conn = ReadOnlyMavlinkConnection(SocketConnection(s))
    try:
        assert conn.write_half_state == "CLOSED_ENOTCONN"
        assert conn.write_half_closed is True, (
            "the guard under-reported a control that worked")
    finally:
        s.close()


def test_guard_reports_closed_for_a_connected_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("127.0.0.1", 9))
    conn = ReadOnlyMavlinkConnection(SocketConnection(s))
    try:
        assert conn.write_half_state == "CLOSED"
        assert conn.write_half_closed is True
    finally:
        s.close()


def test_guard_reports_no_socket_for_a_serial_or_replay_transport():
    """A serial link has no write half to shut. That is not a failure."""
    class NoSocket:
        port = None
        mav = object()

        def close(self):
            pass

    conn = ReadOnlyMavlinkConnection(NoSocket())
    assert conn.write_half_state == "NO_SOCKET"
    assert conn.write_half_closed is False


def test_the_socket_really_cannot_send_after_wrapping():
    """End to end: wrap a live socket, then try to use it as an attacker would.

    Layer 1 denies the API. This asserts the kernel denies the bytes.
    """
    s = _udp_listener()
    ReadOnlyMavlinkConnection(SocketConnection(s))
    try:
        with pytest.raises(OSError) as exc:
            s.sendto(b"\xfe\x09\x00", ("127.0.0.1", 9))
        assert exc.value.errno in (errno.EPIPE, errno.ESHUTDOWN)
    finally:
        s.close()


def test_receiving_still_works_after_the_write_half_is_shut():
    """Shutting the write half must not break the monitor's whole job."""
    listener = _udp_listener()
    addr = listener.getsockname()
    ReadOnlyMavlinkConnection(SocketConnection(listener))
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sender.sendto(b"hello", addr)
        listener.settimeout(2.0)
        data, _ = listener.recvfrom(64)
        assert data == b"hello"
    finally:
        sender.close()
        listener.close()


def test_authority_evidence_records_the_reason_not_just_a_boolean():
    from csia.deploy.guard import assert_no_command_capability
    s = _udp_listener()
    conn = ReadOnlyMavlinkConnection(SocketConnection(s))
    try:
        ev = assert_no_command_capability(conn)
        assert ev["write_half_closed"] is True
        assert ev["write_half_state"] == "CLOSED_ENOTCONN"
    finally:
        s.close()
