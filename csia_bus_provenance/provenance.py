"""Whether a reading can be attributed to the device it is claimed to be from.

THE DEFECT FAMILY THIS BELONGS TO
---------------------------------
`research/evidence_semantics/README.md` records three findings, and all three
are one shape: **an absence collapsing into a usable value.** A GNSS receiver
with no fix is indistinguishable from a receiver that sent nothing; a battery
sentinel of ``-1`` is served as ``5.00 A`` for half a second; an all-zero
magnetometer triple is ingested as a field.

`CANONICAL_STATE_MODEL.md` §3 gives those a coordinate -- where the value came
from, independent of whether ``q`` still claims ``OBSERVED_VALID``:

    REAL       the value the producer sent
    RETAINED   a real value the producer has since disowned
    IMPUTED    a value the decoder invented

A multiplexer adds a member that the existing coordinate cannot express:

    MISATTRIBUTED   a REAL value, from a REAL producer -- the WRONG one

This is strictly worse than the three recorded findings, and worth being
precise about why. In every one of those, the bad value is *locally* explicable
-- a sentinel, a zero, a stale retained sample -- and a sufficiently careful
reader of the wire could catch it. A misattributed mux reading is a healthy
device reporting a true measurement of itself. Nothing in the value is wrong.
What is wrong is the *name attached to it*, and no amount of inspecting the
bytes recovers that, because the information was never on the bus.

It is the same species as the defect the independent-validation phase spent a
campaign on (`COUNTEREXAMPLE_LOG.md` IV-26): an assumption that was
load-bearing, undeclared, and invisible in the output it supported.

WHAT THIS MODULE REFUSES TO DO
------------------------------
It does not guess. When two devices could have answered, the verdict is
``AMBIGUOUS`` and both candidates are carried. Program objective 3 is to
preserve unresolved ambiguity rather than hide it, and picking the likelier
device would be hiding it behind a plausible name.

It also does not decide what a consumer should do about any verdict. It has no
threshold, no score, and no notion of "good enough". It reports what the bus
can and cannot establish; deciding whether that supports a capability is
FORGE's job, downstream, and not this package's.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .datasheet import channels_in
from .topology import Device, Mux


class Binding(str):
    """How well a reading is tied to a named device. A string for logging."""


VERIFIED = Binding("VERIFIED")
"""Readback confirmed the register, and exactly one device could answer."""

ASSUMED = Binding("ASSUMED")
"""The register was written and not read back. The binding rests on the write
having landed, which is an assumption about a bus that can NACK."""

AMBIGUOUS = Binding("AMBIGUOUS")
"""More than one enabled device shares the address. The value is real and its
source is not determinable from the bus. Carried, never resolved."""

MISATTRIBUTED = Binding("MISATTRIBUTED")
"""Readback proves the register was not what the caller believed, and the
device that answered is not the device the caller named."""

NO_RESPONDER = Binding("NO_RESPONDER")
"""Under the register actually in force, no device holds that address. A value
purporting to come from one is unexplainable."""

UNBOUND = Binding("UNBOUND")
"""No selection record covers this read. The address alone names nothing."""

ALL_BINDINGS = (VERIFIED, ASSUMED, AMBIGUOUS, MISATTRIBUTED, NO_RESPONDER,
                UNBOUND)

#: The only binding under which identity was ESTABLISHED rather than assumed.
#:
#: ASSUMED is deliberately NOT in here, and an earlier draft of this module had
#: it the other way. That draft's own counterexample test showed why it was
#: wrong: under a write that silently failed, a read of a stale channel returns
#: a real measurement from the wrong device, and the verdict is ASSUMED. Had
#: ASSUMED counted as established, the default path would have laundered an
#: unverified assumption into an identity -- which is the exact defect family
#: this package was written to expose (`research/evidence_semantics/`
#: findings 1-3), reproduced inside the tool meant to catch it.
#:
#: A caller may still choose to accept ASSUMED. It has to say so, at the call
#: site, through :func:`accepts`.
ESTABLISHED = frozenset({VERIFIED})

#: Bindings that establish nothing, whatever a caller chooses to accept.
NOT_ATTRIBUTABLE = frozenset({AMBIGUOUS, MISATTRIBUTED, NO_RESPONDER, UNBOUND})


def accepts(binding: Binding, *, allow_assumed: bool = False) -> bool:
    """Whether ``binding`` clears the bar, with the bar named at the call site.

    ``allow_assumed=True`` is a real choice with a real cost: it accepts reads
    whose channel was commanded but never confirmed, and those are the reads a
    silently-failed register write misattributes. It is spelled out rather than
    defaulted so the cost appears in the caller's source, not in this file's.
    """
    if binding in ESTABLISHED:
        return True
    if binding == ASSUMED:
        return allow_assumed
    return False


@dataclass(frozen=True)
class Selection:
    """One attempt to put the mux on a channel, and what was checked after.

    ``readback`` is ``None`` when the caller did not read the control register
    back. That is the common case in field code and it is exactly why
    :data:`ASSUMED` exists as a distinct verdict rather than being folded into
    :data:`VERIFIED`.

    ``writes_since`` counts bus operations that could have changed the register
    between this selection and the read being judged -- another task touching
    the mux, a recovery routine, a shared-bus driver. A non-zero count
    invalidates an earlier readback, because the readback described the
    register at readback time and not at read time.
    """

    mux_address: int
    commanded_mask: int
    at_s: float
    readback: Optional[int] = None
    readback_at_s: Optional[float] = None
    writes_since: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.commanded_mask <= 0xFF:
            raise ValueError("commanded_mask is one byte")
        if self.readback is not None and not 0 <= self.readback <= 0xFF:
            raise ValueError("readback is one byte")
        if self.readback is not None and self.readback_at_s is None:
            raise ValueError(
                "a readback without a timestamp cannot be ordered against the "
                "read it is supposed to justify")

    @property
    def effective_mask(self) -> int:
        """What the register actually held, so far as anything knows.

        The readback when there is one, because a measurement of the register
        beats an intention about it. The commanded value otherwise -- and the
        verdict that results is downgraded to reflect that.
        """
        return self.commanded_mask if self.readback is None else self.readback

    @property
    def write_landed(self) -> Optional[bool]:
        """``None`` when nobody looked."""
        if self.readback is None:
            return None
        return self.readback == self.commanded_mask


@dataclass(frozen=True)
class Attribution:
    """The verdict, its reason, and every device that could have answered."""

    binding: Binding
    address: int
    candidates: Tuple[Device, ...]
    effective_mask: int
    expected: Optional[Device] = None
    why: str = ""

    @property
    def identity_established(self) -> bool:
        """True only when the register was measured, not merely written."""
        return self.binding in ESTABLISHED

    @property
    def establishes_nothing(self) -> bool:
        """True when no choice by the caller could rescue this read."""
        return self.binding in NOT_ATTRIBUTABLE

    def accepted_by(self, *, allow_assumed: bool = False) -> bool:
        return accepts(self.binding, allow_assumed=allow_assumed)

    @property
    def device(self) -> Optional[Device]:
        """The single source, or ``None`` when there is not exactly one.

        Deliberately ``None`` for :data:`AMBIGUOUS` rather than the first
        candidate. A caller that wants a name under ambiguity has to reach for
        ``candidates`` and decide in the open.
        """
        return self.candidates[0] if len(self.candidates) == 1 else None

    def as_dict(self) -> dict:
        return {
            "binding": str(self.binding),
            "address": self.address,
            "effective_mask": self.effective_mask,
            "enabled_channels": list(channels_in(self.effective_mask)),
            "candidates": [
                {"name": d.name, "address": d.address, "channel": d.channel}
                for d in self.candidates],
            "expected": None if self.expected is None else self.expected.name,
            "identity_established": self.identity_established,
            "establishes_nothing": self.establishes_nothing,
            "why": self.why,
        }


def attribute(mux: Mux, address: int,
              selection: Optional[Selection],
              *, expected: Optional[Device] = None,
              read_at_s: Optional[float] = None,
              max_binding_age_s: Optional[float] = None) -> Attribution:
    """Judge a read of ``address`` against the selection that preceded it.

    Order of decision, and each step exists because skipping it is how the
    wrong answer gets produced:

    1. no selection at all -> UNBOUND, because an address behind a mux names
       nothing on its own;
    2. the selection is for a different mux -> UNBOUND;
    3. the register was written and never read back -> at best ASSUMED;
    4. someone else wrote the register since the readback -> the readback no
       longer describes read time, so back to ASSUMED;
    5. the binding is older than ``max_binding_age_s`` -> ASSUMED;
    6. under the register actually in force: none can answer -> NO_RESPONDER;
       more than one can -> AMBIGUOUS; exactly one -> attributed, and if that
       one is not ``expected`` -> MISATTRIBUTED.

    Ambiguity outranks staleness. A read that two devices could have answered
    is not made attributable by having been taken promptly.
    """
    if selection is None:
        return Attribution(UNBOUND, address, (), 0, expected,
                           "no selection record covers this read")
    if selection.mux_address != mux.address:
        return Attribution(
            UNBOUND, address, (), 0, expected,
            f"selection was for mux {selection.mux_address:#04x}, read was "
            f"behind {mux.address:#04x}")

    mask = selection.effective_mask
    candidates = mux.responders(mask, address)

    downgrades = []
    if selection.readback is None:
        downgrades.append("the control register was never read back")
    elif selection.writes_since:
        downgrades.append(
            f"{selection.writes_since} bus write(s) since the readback, which "
            f"described the register then and not now")
    if (max_binding_age_s is not None and read_at_s is not None
            and read_at_s - selection.at_s > max_binding_age_s):
        downgrades.append(
            f"selection was {read_at_s - selection.at_s:.3f} s before the "
            f"read, over the {max_binding_age_s:.3f} s limit")

    if not candidates:
        return Attribution(
            NO_RESPONDER, address, (), mask, expected,
            f"no device at {address:#04x} on channels "
            f"{list(channels_in(mask))}"
            + (f"; also, {'; '.join(downgrades)}" if downgrades else ""))

    if len(candidates) > 1:
        names = ", ".join(d.name for d in candidates)
        return Attribution(
            AMBIGUOUS, address, candidates, mask, expected,
            f"{len(candidates)} devices share {address:#04x} under this "
            f"register ({names}); the bus cannot say which answered")

    only = candidates[0]
    if expected is not None and only != expected:
        return Attribution(
            MISATTRIBUTED, address, candidates, mask, expected,
            f"expected {expected.name} on channel {expected.channel}, but "
            f"under register {mask:#04x} the responder is {only.name} on "
            f"channel {only.channel}")

    if downgrades:
        return Attribution(ASSUMED, address, candidates, mask, expected,
                           "; ".join(downgrades))
    return Attribution(
        VERIFIED, address, candidates, mask, expected,
        f"readback confirmed register {mask:#04x}; {only.name} is the only "
        f"device at {address:#04x} on an enabled channel")
