"""A deterministic TCA9548A, so the failure modes can be exercised with no bench.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
It is a model of the *register and switching logic* -- one byte, eight gates,
and a short list of ways the byte stops meaning what the host thinks it means.
That is enough to test every path in :mod:`csia_bus_provenance.provenance`,
because those paths are decided by the register and the wiring and by nothing
electrical.

**It is not evidence about any real TCA9548A.** It shares its author with the
model it is used to test, so agreement between them demonstrates internal
consistency and not correctness -- the same limitation the repository already
states for its five-way differential (`ASSURANCE_DIFFERENTIAL.json`,
"a wrong definition agree[d] upon"). It also models nothing electrical: no
pull-up sizing, no bus capacitance, no clock stretching, no channel loading.
Those decide whether real wiring works, and this cannot speak to them.

Nothing here imports a hardware interface. There is no ``smbus``, no
``periphery``, no ``/dev/i2c-*``. That is deliberate and is how the owner
authorization's hardware prohibition is held -- by there being no path, not by
a promise (`OWNER_AUTHORIZATION.md`: "no interface to any is imported").

THE FAULTS, AND WHY EACH ONE IS IN THE LIST
-------------------------------------------
Each is a documented consequence of the part being one writable byte, not a
speculative physical mechanism. Anything requiring a claim about crosstalk,
capacitance or marginal timing is deliberately absent, because this
environment cannot support such a claim.

``WRITE_IGNORED``   the register write is not applied. The mux stays on the
                    previous channel and the host does not know. This is the
                    misattribution generator.
``POR_RESET``       the register returns to 0x00 under a brownout while the
                    host stays up, so the host believes a channel is selected
                    when none is.
``STUCK_MASK``      the register stops accepting writes entirely.
``EXTRA_CHANNEL``   a write lands with an additional bit set, enabling two
                    channels at once -- the ambiguity generator.
``MUX_SILENT``      the device stops acknowledging, so neither write nor
                    readback succeeds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .datasheet import POR_CONTROL_REGISTER, channels_in
from .provenance import Selection
from .topology import Device, Mux

WRITE_IGNORED = "WRITE_IGNORED"
POR_RESET = "POR_RESET"
STUCK_MASK = "STUCK_MASK"
EXTRA_CHANNEL = "EXTRA_CHANNEL"
MUX_SILENT = "MUX_SILENT"

FAULTS = (WRITE_IGNORED, POR_RESET, STUCK_MASK, EXTRA_CHANNEL, MUX_SILENT)


class BusError(RuntimeError):
    """The device did not acknowledge."""


@dataclass
class MuxSimulator:
    """One TCA9548A with an injectable fault. Deterministic; no clock, no RNG.

    Time is supplied by the caller. Nothing here reads the wall clock, so a
    replay produces byte-identical records -- the same property
    `research/evidence_semantics/README.md` requires of its probes.
    """

    mux: Mux
    register: int = POR_CONTROL_REGISTER
    fault: Optional[str] = None
    extra_channel: int = 0
    writes: int = 0
    log: List[Dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.fault is not None and self.fault not in FAULTS:
            raise ValueError(f"unknown fault {self.fault!r}; have {FAULTS}")

    # -- the bus ----------------------------------------------------------

    def write_register(self, mask: int, *, at_s: float) -> None:
        if not 0 <= mask <= 0xFF:
            raise ValueError("control register is one byte")
        self.writes += 1
        applied = mask
        if self.fault == MUX_SILENT:
            self._record("write", at_s, mask, self.register, "NACK")
            raise BusError(f"mux {self.mux.address:#04x} did not acknowledge")
        if self.fault in (WRITE_IGNORED, STUCK_MASK):
            self._record("write", at_s, mask, self.register, self.fault)
            return
        if self.fault == EXTRA_CHANNEL:
            applied = mask | (1 << self.extra_channel)
        self.register = applied
        self._record("write", at_s, mask, applied, self.fault or "ok")

    def read_register(self, *, at_s: float) -> int:
        if self.fault == MUX_SILENT:
            self._record("readback", at_s, None, self.register, "NACK")
            raise BusError(f"mux {self.mux.address:#04x} did not acknowledge")
        self._record("readback", at_s, None, self.register, self.fault or "ok")
        return self.register

    def brownout(self, *, at_s: float) -> None:
        """Reset the register without the host noticing."""
        self.register = POR_CONTROL_REGISTER
        self._record("brownout", at_s, None, self.register, POR_RESET)

    def responders(self, address: int) -> Tuple[Device, ...]:
        """Who would answer ``address`` right now. The simulator's ground truth.

        This is Layer-B knowledge in the sense the independent-validation
        package uses the term: it sees what the register really holds.
        :mod:`csia_bus_provenance.provenance` must never call it -- it decides
        from the host's records alone, which is the whole point.
        """
        return self.mux.responders(self.register, address)

    # -- the host's view --------------------------------------------------

    def select(self, channel: int, *, at_s: float,
               verify: bool = True) -> Selection:
        """Command a channel and build the record a later read is judged by.

        ``verify=False`` is the field-code default in most drivers, and
        produces a :data:`~csia_bus_provenance.provenance.ASSUMED` binding
        rather than a verified one. It is offered because pretending nobody
        writes such code would make the model useless for arguing against it.
        """
        mask = 1 << channel
        self.write_register(mask, at_s=at_s)
        readback = None
        readback_at = None
        if verify:
            readback = self.read_register(at_s=at_s)
            readback_at = at_s
        return Selection(mux_address=self.mux.address, commanded_mask=mask,
                         at_s=at_s, readback=readback,
                         readback_at_s=readback_at)

    def _record(self, op: str, at_s: float, requested: Optional[int],
                register: int, note: str) -> None:
        self.log.append({
            "op": op, "at_s": at_s, "requested": requested,
            "register": register,
            "enabled_channels": list(channels_in(register)),
            "note": note,
        })
