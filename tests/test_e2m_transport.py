"""The serial read loop, exercised without a serial device.

`transport.py` was the least-covered module in the acquisition layer (55%),
and the uncovered half was the part that will actually face hardware. These
tests inject a fake port object -- `readline()` and `close()`, the only two
methods the loop uses -- so the framing, decoding, timeout and shutdown paths
run for real.

WHAT THIS IS NOT
----------------
Not evidence that any serial device works. A fake port returns bytes a test
wrote; it has no UART, no timing, no electrical behaviour and no board on the
other end. `test_a_fake_port_run_is_not_a_hardware_run` pins that distinction
so a green file here cannot be read as a bench result.

No real device is opened anywhere in this file: every `SerialTransport` is
constructed with `factory=`, and a test asserts that pyserial is never
imported as a side effect.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from csia_e2m.logging import RunLogger
from csia_e2m.protocol import OK, Record
from csia_e2m.transport import FakeTransport, SerialTransport


class FakePort:
    """Returns prepared chunks from readline(), then b'' forever.

    b'' is how pyserial reports a timeout, so a test that wants a timeout
    simply runs out of chunks.
    """

    def __init__(self, chunks, *, fail_on_close=False):
        self.chunks = list(chunks)
        self.closed = 0
        self.reads = 0
        self._fail_on_close = fail_on_close

    def readline(self):
        self.reads += 1
        return self.chunks.pop(0) if self.chunks else b""

    def close(self):
        self.closed += 1
        if self._fail_on_close:
            raise OSError("device went away")


def _frame(seq=1, channel=0, status=OK, milli=25000):
    return Record(seq=seq, sweep=0, commanded_channel=channel,
                  readback_channel=channel, sensor=f"ch{channel}",
                  status=status, milli=milli,
                  unit="milliC" if status == OK else "",
                  controller_us=1000 * seq, i2c_error=0,
                  retries=0).encode()


def _transport(chunks, **kw):
    port = FakePort(chunks)
    transport = SerialTransport("/dev/fake", 115200, factory=lambda: port, **kw)
    return transport, port


def _clock():
    state = {"t": 1_000_000_000}

    def tick():
        state["t"] += 1_000_000
        return state["t"]
    return tick


# --- the read loop --------------------------------------------------------

def test_a_complete_frame_is_delivered():
    transport, _ = _transport([(_frame(1) + "\n").encode()])
    transport.open()
    assert list(transport.lines()) == [_frame(1) + "\n"]


def test_several_frames_arrive_in_order():
    chunks = [(_frame(n) + "\n").encode() for n in (1, 2, 3)]
    transport, port = _transport(chunks)
    transport.open()
    lines = list(transport.lines())
    assert len(lines) == 3
    assert [line.strip() for line in lines] == [_frame(n) for n in (1, 2, 3)]
    assert port.reads == 4          # three frames plus the terminating empty


def test_multiple_frames_in_one_read_are_not_silently_merged():
    """A readline() that returns two frames is a framing violation. The loop
    does not split it -- it hands the blob to the protocol layer, which fails
    the CRC. Losing a frame silently would be worse than rejecting both."""
    blob = (_frame(1) + "\n" + _frame(2) + "\n").encode()
    transport, _ = _transport([blob])
    transport.open()
    lines = list(transport.lines())
    assert len(lines) == 1
    logger_lines = [ln for ln in lines[0].splitlines() if ln]
    assert len(logger_lines) == 2       # the data is there, unparsed
    from csia_e2m.protocol import ProtocolError, decode
    with pytest.raises(ProtocolError):
        decode(lines[0])


def test_a_partial_read_is_yielded_and_then_rejected_downstream():
    """A truncated line reaches the protocol layer, which refuses it. The
    transport does not guess at the missing bytes."""
    partial = _frame(1)[:20].encode()
    transport, _ = _transport([partial])
    transport.open()
    lines = list(transport.lines())
    assert lines == [_frame(1)[:20]]
    from csia_e2m.protocol import ProtocolError, decode
    with pytest.raises(ProtocolError):
        decode(lines[0])


def test_a_timeout_ends_the_stream_rather_than_spinning():
    transport, port = _transport([])
    transport.open()
    assert list(transport.lines()) == []
    assert port.reads == 1


def test_a_timeout_midway_ends_the_stream_there():
    transport, _ = _transport([(_frame(1) + "\n").encode(), b"",
                               (_frame(2) + "\n").encode()])
    transport.open()
    lines = list(transport.lines())
    assert len(lines) == 1, "an empty read must terminate, not be skipped"


def test_non_ascii_bytes_do_not_raise():
    """A noisy line must not take the acquisition down. It is decoded with
    replacement and rejected by the CRC."""
    transport, _ = _transport([b"\xff\xfe garbage \x00\n"])
    transport.open()
    lines = list(transport.lines())
    assert len(lines) == 1
    from csia_e2m.protocol import ProtocolError, decode
    with pytest.raises(ProtocolError):
        decode(lines[0])


def test_reading_before_open_is_an_error():
    transport = SerialTransport("/dev/fake", factory=lambda: FakePort([]))
    with pytest.raises(RuntimeError, match="call open"):
        list(transport.lines())


# --- lifecycle ------------------------------------------------------------

def test_clean_shutdown_closes_the_port_once():
    transport, port = _transport([(_frame(1) + "\n").encode()])
    transport.open()
    list(transport.lines())
    transport.close()
    assert port.closed == 1
    assert transport.is_open is False


def test_close_is_idempotent():
    """Closing twice must not raise. Leaking a port is the real failure."""
    transport, port = _transport([])
    transport.open()
    transport.close()
    transport.close()
    assert port.closed == 1


def test_reopen_replaces_the_port():
    ports = []

    def factory():
        port = FakePort([(_frame(len(ports) + 1) + "\n").encode()])
        ports.append(port)
        return port

    transport = SerialTransport("/dev/fake", factory=factory)
    transport.open()
    list(transport.lines())
    transport.reopen()
    list(transport.lines())
    assert len(ports) == 2
    assert ports[0].closed == 1
    assert transport.is_open is True


# --- what the logger makes of a reset -------------------------------------

def test_a_board_reset_shows_up_as_a_sequence_gap(tmp_path):
    """The controller restarts its sequence after a reset. That discontinuity
    is recorded, not smoothed: a run with a hidden reset would look like an
    unbroken acquisition."""
    chunks = [(_frame(n) + "\n").encode() for n in (1, 2, 3)]
    chunks += [(_frame(n) + "\n").encode() for n in (1, 2)]   # after reset
    transport, _ = _transport(chunks)
    transport.open()
    logger = RunLogger(path=tmp_path / "r.jsonl", run_id="reset", device="FAKE",
                       baud=0, clock=_clock())
    logger.open()
    for line in transport.lines():
        logger.ingest(line)
    manifest = logger.close()
    assert manifest["records"] == 5
    assert manifest["sequence_gaps"], "the reset was absorbed silently"


def test_a_crc_failure_is_counted_as_malformed_not_dropped(tmp_path):
    good = _frame(1)
    bad = good[:-1] + ("0" if good[-1] != "0" else "1")
    transport, _ = _transport([(good + "\n").encode(), (bad + "\n").encode()])
    transport.open()
    logger = RunLogger(path=tmp_path / "r.jsonl", run_id="crc", device="FAKE",
                       baud=0, clock=_clock())
    logger.open()
    for line in transport.lines():
        logger.ingest(line)
    manifest = logger.close()
    assert manifest["records"] == 1
    assert manifest["malformed_frames"] == 1
    assert bad in (tmp_path / "r.jsonl").read_text()


# --- boundaries -----------------------------------------------------------

def test_a_fake_port_run_is_not_a_hardware_run():
    """A green transport suite is software evidence. Nothing here touched a
    UART, and the campaign state is unchanged by it."""
    import csia_e2m
    assert csia_e2m.HARDWARE_VALIDATED is False
    assert csia_e2m.CAMPAIGN_STATE == "AUTHORIZED_NOT_RUN"


def test_the_fake_transport_declares_itself_fake():
    assert FakeTransport([]).device == "FAKE"


def test_no_real_serial_device_is_opened_by_this_module():
    """Every SerialTransport here is constructed with `factory=`. Importing
    the module must still not pull in pyserial."""
    code = ("import sys, csia_e2m.transport as t; "
            "print('serial' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, check=True,
                         cwd=str(__import__("pathlib").Path(__file__)
                                 .resolve().parents[1]))
    assert out.stdout.strip() == "False"


def test_available_ports_does_not_raise_without_hardware():
    from csia_e2m.transport import available_ports
    assert isinstance(available_ports(), list)
