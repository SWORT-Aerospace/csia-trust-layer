"""The only place a serial port is opened. Nothing else imports pyserial.

The owner's decision authorizes "importing a serial-port library in the host
acquisition tool" and requires that `csia_bus_provenance` stay free of any
hardware interface. This module is the boundary: the import is **lazy**, inside
:meth:`SerialTransport.open`, so merely importing :mod:`csia_e2m` -- which the
test suite does -- pulls in no hardware library and needs no port to exist.

`FakeTransport` implements the same protocol from a list of strings, which is
what E2M-0 runs on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator, List, Optional, Protocol


class Transport(Protocol):
    """A line source. Two implementations: a serial port and a list."""

    device: str
    baud: int

    def lines(self) -> Iterator[str]:
        ...


@dataclass
class FakeTransport:
    """Replays prepared lines. Never physical evidence; `device` says so."""

    prepared: List[str]
    device: str = "FAKE"
    baud: int = 0

    def lines(self) -> Iterator[str]:
        for line in self.prepared:
            yield line


@dataclass
class SerialTransport:
    """A real USB serial port. Opens nothing until :meth:`open` is called.

    ``factory`` exists so the read loop can be tested without hardware. It
    defaults to ``None``, which means pyserial; a test supplies a callable
    returning an object with ``readline()`` and ``close()``. The injection
    point is deliberately narrow -- it replaces the PORT, not the loop -- so
    what the tests exercise is the same framing, decoding and shutdown code
    that will run against a real board.

    This is not a fake that lets a test claim hardware was exercised. A run
    driven through an injected factory still reports whatever ``device`` it
    was given, and `test_e2m_transport.py` asserts the distinction.
    """

    device: str
    baud: int = 115200
    timeout_s: float = 2.0
    factory: Optional[Callable[[], object]] = None
    _port: Optional[object] = field(default=None, init=False, repr=False)

    def open(self) -> None:
        if self.factory is not None:
            self._port = self.factory()
            return
        try:
            import serial           # noqa: PLC0415  -- lazy on purpose
        except ImportError as error:        # pragma: no cover
            raise RuntimeError(
                "pyserial is not installed. `pip install pyserial`, or use "
                "the fake transport for E2M-0") from error
        self._port = serial.Serial(self.device, self.baud,
                                   timeout=self.timeout_s)

    def close(self) -> None:
        """Idempotent. Closing twice is not an error; leaking a port is."""
        if self._port is not None:
            self._port.close()      # type: ignore[attr-defined]
            self._port = None

    @property
    def is_open(self) -> bool:
        return self._port is not None

    def reopen(self) -> None:
        """Close and open again, for a board that reset mid-run.

        The sequence number does NOT restart from the host's point of view --
        the controller's does, and that discontinuity is what
        :class:`~csia_e2m.logging.RunLogger` records as a sequence gap. Hiding
        the reconnection would erase the evidence that one happened.
        """
        self.close()
        self.open()

    def lines(self) -> Iterator[str]:
        """Yield decoded lines until the port returns nothing.

        An empty read is how pyserial reports a timeout, and it ends the
        stream rather than spinning. A partial line -- no trailing newline --
        is yielded as it arrived; the protocol layer rejects it on CRC, which
        is where that decision belongs.
        """
        if self._port is None:
            raise RuntimeError("call open() first")
        while True:
            raw = self._port.readline()     # type: ignore[attr-defined]
            if not raw:
                return
            yield raw.decode("ascii", errors="replace")


def available_ports() -> List[str]:
    """Best-effort enumeration, for the runbook's device-identification step.

    Returns an empty list rather than raising when pyserial is absent, because
    "no port" and "no library" are both answers the operator can act on and
    neither is an error in this tool.
    """
    try:
        from serial.tools import list_ports      # noqa: PLC0415
    except ImportError:                          # pragma: no cover
        return []
    return [port.device for port in list_ports.comports()]
