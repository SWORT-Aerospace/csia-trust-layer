"""A deterministic stand-in for the acquisition controller. NOT HARDWARE.

Every frame this produces is synthetic. It exists so E2M-0 -- software-only
protocol validation -- can be executed today, with no Arduino, no mux and no
sensors, and so the logger and replay path are exercised before anybody wires
anything.

**A run driven by this module is never physical evidence.** The manifest it
produces carries ``device`` = ``"FAKE"``; a test asserts that a fake run cannot
be reported as a bench run, and the runbook keeps the two commands separate.

It is deterministic by construction: no RNG without an explicit seed, no clock.
Two runs with the same parameters produce byte-identical frames.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence

from .protocol import (ERR_MUX_WRITE, ERR_READBACK_MISMATCH, ERR_SENSOR_NACK,
                       OK, READBACK_NOT_TAKEN, Record)

FAKE_DEVICE = "FAKE"


@dataclass
class FakeSensor:
    """A synthetic device with a flat baseline and a per-sweep ramp."""

    name: str
    channel: int
    unit: str = "milliC"
    baseline_milli: int = 25000
    per_sweep_milli: int = 3

    def value(self, sweep: int) -> int:
        return self.baseline_milli + self.per_sweep_milli * sweep


@dataclass
class FakeController:
    """Emits frames the way the firmware is specified to.

    ``verify_readback`` mirrors the firmware's compile-time option. With it
    off, `readback_channel` is `READBACK_NOT_TAKEN` -- which is a different
    fact from a readback that disagreed, and the protocol keeps them apart.
    """

    sensors: Sequence[FakeSensor]
    verify_readback: bool = True
    #: channel -> the channel the mux actually lands on, for E2M-2 rehearsal
    stuck_channel: Dict[int, int] = field(default_factory=dict)
    #: sensors that do not answer, for E2M-3 rehearsal
    silent: Sequence[str] = ()
    #: channels whose register write is not acknowledged
    write_fails: Sequence[int] = ()
    us_per_read: int = 2500
    seed: Optional[int] = None

    def frames(self, sweeps: int) -> Iterator[str]:
        for record in self.records(sweeps):
            yield record.encode()

    def records(self, sweeps: int) -> Iterator[Record]:
        rng = random.Random(self.seed) if self.seed is not None else None
        seq = 0
        micros = 0
        for sweep in range(sweeps):
            for sensor in self.sensors:
                seq += 1
                micros += self.us_per_read
                jitter = rng.randint(-50, 50) if rng is not None else 0
                yield self._one(sensor, sweep, seq, micros + jitter)

    def _one(self, sensor: FakeSensor, sweep: int, seq: int,
             micros: int) -> Record:
        commanded = sensor.channel

        if commanded in self.write_fails:
            return Record(seq=seq, sweep=sweep, commanded_channel=commanded,
                          readback_channel=READBACK_NOT_TAKEN,
                          sensor=sensor.name, status=ERR_MUX_WRITE, milli=0,
                          unit="", controller_us=micros, i2c_error=2,
                          retries=3)

        landed = self.stuck_channel.get(commanded, commanded)
        readback = landed if self.verify_readback else READBACK_NOT_TAKEN

        if self.verify_readback and landed != commanded:
            return Record(seq=seq, sweep=sweep, commanded_channel=commanded,
                          readback_channel=readback, sensor=sensor.name,
                          status=ERR_READBACK_MISMATCH, milli=0, unit="",
                          controller_us=micros, i2c_error=0, retries=0)

        if sensor.name in self.silent:
            return Record(seq=seq, sweep=sweep, commanded_channel=commanded,
                          readback_channel=readback, sensor=sensor.name,
                          status=ERR_SENSOR_NACK, milli=0, unit="",
                          controller_us=micros, i2c_error=2, retries=3)

        # The E2M-2 case: the mux landed elsewhere, readback is not taken, and
        # whatever is on the channel it DID land on answers. The value is real
        # and the label is wrong, and nothing in the frame reveals it.
        source = sensor
        if landed != commanded:
            for other in self.sensors:
                if other.channel == landed:
                    source = other
                    break

        return Record(seq=seq, sweep=sweep, commanded_channel=commanded,
                      readback_channel=readback, sensor=sensor.name,
                      status=OK, milli=source.value(sweep), unit=source.unit,
                      controller_us=micros, i2c_error=0, retries=0)


def default_bench(count: int = 3) -> List[FakeSensor]:
    """Three synthetic sensors on distinct channels, distinguishable values."""
    return [FakeSensor(name=f"fake_{i}", channel=i,
                       baseline_milli=25000 + 1000 * i, per_sweep_milli=3 + i)
            for i in range(count)]
