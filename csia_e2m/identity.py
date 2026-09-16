"""Seven distinct things the owner's §11 forbids treating as one.

The decision message is explicit: a successful register readback establishes
only the mux control state permitted by the verified datasheet. It does not
prove the wiring, the sensor placement, or the configuration label.

So these are seven separate facts, and this module keeps them apart:

    commanded channel          what the host asked for
    register readback          what the mux reports its register holds
    electrically active        which channel is actually switched through
    expected installed sensor  what the topology declaration says is there
    actual physical sensor     what is really soldered to that channel
    sensor-native identity     what the device says it is, from its own ID
                               register or serial number
    logical role               the name configuration gives it

Only the first two and the last two are observable from software. "Electrically
active" needs a logic analyser. "Actual physical sensor" needs a human looking
at the bench. This module therefore cannot reach `PHYSICALLY_VERIFIED` on its
own and does not pretend to -- reaching it requires an operator attestation
carrying a run artifact.

RELATION TO `csia_bus_provenance.provenance`
--------------------------------------------
That module answers a narrower question -- can this read be attributed, given
the register and the wiring declaration -- and its vocabulary
(`VERIFIED`/`ASSUMED`/`AMBIGUOUS`/`MISATTRIBUTED`/`NO_RESPONDER`/`UNBOUND`) is
about the *bus*. The owner's §11 vocabulary is about the *chain of custody from
silicon to label*, which is longer. The two are related by
:func:`from_bus_binding` rather than merged, because merging them would lose
the distinction the owner asked to preserve.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

UNOBSERVED = "UNOBSERVED"
"""Nothing was recorded about identity for this read."""

ASSUMED = "ASSUMED"
"""Configuration says so and nothing checked it. Establishes nothing."""

COMMAND_CONFIRMED = "COMMAND_CONFIRMED"
"""The channel write was acknowledged. The mux accepted an instruction; that
is not the same as the register holding the value, nor the channel being
switched, nor the right part being on it."""

READBACK_CONFIRMED = "READBACK_CONFIRMED"
"""The register was read back and matched. Per the owner's §11 this bounds the
mux control state and nothing downstream of the switch."""

TOPOLOGY_DECLARED = "TOPOLOGY_DECLARED"
"""A human wrote down what is on this channel. Evidence about the document."""

PHYSICALLY_VERIFIED = "PHYSICALLY_VERIFIED"
"""An operator confirmed the part on the bench, or a native identity register
matched, against a recorded run. Not reachable from software alone."""

MISATTRIBUTED = "MISATTRIBUTED"
"""Evidence shows the reading came from somewhere other than the named source."""

CONFLICTED = "CONFLICTED"
"""Two sources of identity evidence disagree, and neither is discardable."""

STATES = (UNOBSERVED, ASSUMED, COMMAND_CONFIRMED, READBACK_CONFIRMED,
          TOPOLOGY_DECLARED, PHYSICALLY_VERIFIED, MISATTRIBUTED, CONFLICTED)

#: States that establish attribution. `ASSUMED` is deliberately absent -- the
#: owner's §11 says so in as many words, and `csia_bus_provenance` reached the
#: same conclusion the hard way (its own counterexample refuted the first
#: draft). `READBACK_CONFIRMED` is absent too, and that is the sharper point:
#: it bounds the control register, not the identity of the part behind it.
ESTABLISHES_ATTRIBUTION = frozenset({PHYSICALLY_VERIFIED})

#: States that are positively bad news rather than merely weak.
CONTRADICTED = frozenset({MISATTRIBUTED, CONFLICTED})


@dataclass(frozen=True)
class IdentityAssessment:
    """What is known about where one reading came from, and how."""

    state: str
    commanded_channel: Optional[int] = None
    readback_channel: Optional[int] = None
    declared_sensor: Optional[str] = None
    native_identity: Optional[str] = None
    expected_native_identity: Optional[str] = None
    operator_attestation: Optional[str] = None
    why: str = ""

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError(f"unknown identity state {self.state!r}")

    @property
    def establishes_attribution(self) -> bool:
        return self.state in ESTABLISHES_ATTRIBUTION

    @property
    def contradicted(self) -> bool:
        return self.state in CONTRADICTED

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "commanded_channel": self.commanded_channel,
            "readback_channel": self.readback_channel,
            "declared_sensor": self.declared_sensor,
            "native_identity": self.native_identity,
            "expected_native_identity": self.expected_native_identity,
            "operator_attestation": self.operator_attestation,
            "establishes_attribution": self.establishes_attribution,
            "contradicted": self.contradicted,
            "why": self.why,
        }


def assess(*, commanded_channel: Optional[int],
           readback_channel: Optional[int],
           declared_sensor: Optional[str],
           write_acknowledged: bool = False,
           native_identity: Optional[str] = None,
           expected_native_identity: Optional[str] = None,
           operator_attestation: Optional[str] = None
           ) -> IdentityAssessment:
    """Grade one reading's chain of custody, strongest supportable claim only.

    The order below is not a ranking of confidence; it is a search for
    contradictions first and evidence second. A disagreement outranks every
    positive signal, because a reading that two sources describe differently is
    not made trustworthy by one of them being emphatic.
    """
    common = dict(commanded_channel=commanded_channel,
                  readback_channel=readback_channel,
                  declared_sensor=declared_sensor,
                  native_identity=native_identity,
                  expected_native_identity=expected_native_identity,
                  operator_attestation=operator_attestation)

    # 1. Native identity disagrees with what was expected there.
    if (native_identity is not None and expected_native_identity is not None
            and native_identity != expected_native_identity):
        return IdentityAssessment(
            MISATTRIBUTED, **common,
            why=f"device reports {native_identity!r}; {declared_sensor!r} was "
                f"expected to report {expected_native_identity!r}")

    # 2. The register does not hold what was commanded.
    if (commanded_channel is not None and readback_channel is not None
            and commanded_channel != readback_channel):
        return IdentityAssessment(
            MISATTRIBUTED, **common,
            why=f"commanded channel {commanded_channel}, register reads "
                f"{readback_channel}")

    # 3. An attestation that contradicts the native identity register.
    if (operator_attestation is not None and native_identity is not None
            and operator_attestation != native_identity):
        return IdentityAssessment(
            CONFLICTED, **common,
            why=f"operator attests {operator_attestation!r}, device reports "
                f"{native_identity!r}; neither is discardable")

    # 4. Physical confirmation, the only state that establishes attribution.
    if operator_attestation is not None:
        return IdentityAssessment(
            PHYSICALLY_VERIFIED, **common,
            why=f"operator attestation {operator_attestation!r}"
                + (f", consistent with device identity {native_identity!r}"
                   if native_identity is not None else ""))
    if native_identity is not None and \
            native_identity == expected_native_identity:
        return IdentityAssessment(
            PHYSICALLY_VERIFIED, **common,
            why=f"device's own identity register reads {native_identity!r}, "
                f"matching the declaration")

    # 5. Weaker, in descending strength. None of these establishes anything.
    if commanded_channel is not None and readback_channel is not None:
        return IdentityAssessment(
            READBACK_CONFIRMED, **common,
            why=f"register reads {readback_channel} as commanded; this bounds "
                f"the mux control state only, not the part behind it")
    if write_acknowledged:
        return IdentityAssessment(
            COMMAND_CONFIRMED, **common,
            why="the channel write was acknowledged; the register was not read "
                "back")
    if declared_sensor is not None:
        return IdentityAssessment(
            TOPOLOGY_DECLARED, **common,
            why=f"configuration declares {declared_sensor!r} on channel "
                f"{commanded_channel}; nothing checked it")
    if commanded_channel is not None:
        return IdentityAssessment(
            ASSUMED, **common,
            why="a channel was commanded and nothing else is known")
    return IdentityAssessment(UNOBSERVED, **common,
                              why="no identity evidence recorded")


def from_bus_binding(binding: str) -> Tuple[str, str]:
    """Map a `csia_bus_provenance` binding onto this vocabulary.

    Returns the state and a note. The mapping is deliberately lossy in the
    safe direction: the strongest bus binding, `VERIFIED`, maps to
    `READBACK_CONFIRMED` and **not** to `PHYSICALLY_VERIFIED`, because the bus
    module reasons about a register and a declaration and never sees silicon.
    """
    table = {
        "VERIFIED": (READBACK_CONFIRMED,
                     "bus readback confirmed; says nothing about the part"),
        "ASSUMED": (ASSUMED, "no readback was taken"),
        "AMBIGUOUS": (CONFLICTED,
                      "more than one device could have answered"),
        "MISATTRIBUTED": (MISATTRIBUTED, "the responder was not the expected "
                                         "device"),
        "NO_RESPONDER": (UNOBSERVED, "nothing answered"),
        "UNBOUND": (UNOBSERVED, "no selection record covered the read"),
    }
    if binding not in table:
        raise ValueError(f"unknown bus binding {binding!r}")
    return table[binding]
