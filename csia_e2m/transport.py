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
from typing import Iterator, List, Optional, Protocol


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
    """A real USB serial port. Opens nothing until :meth:`open` is called."""

    device: str
    baud: int = 115200
    timeout_s: float = 2.0
    _port: Optional[object] = field(default=None, init=False, repr=False)

    def open(self) -> None:
        try:
            import serial           # noqa: PLC0415  -- lazy on purpose
        except ImportError as error:        # pragma: no cover
            raise RuntimeError(
                "pyserial is not installed. `pip install pyserial`, or use "
                "the fake transport for E2M-0") from error
        self._port = serial.Serial(self.device, self.baud,
                                   timeout=self.timeout_s)

    def close(self) -> None:
        if self._port is not None:
            self._port.close()      # type: ignore[attr-defined]
            self._port = None

    def lines(self) -> Iterator[str]:
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
