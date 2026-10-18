"""Recovery and re-certification: why a sensor coming back is not enough.

THE CYCLE
---------
    LOSS -> RESTRICT -> RECONFIGURE -> RE-MEASURE -> RE-CERTIFY -> RESTORE

The interesting step is the one between RE-MEASURE and RE-CERTIFY, because
that is where a system is most tempted to skip.

WHY PRESENCE IS NOT RECOVERY
-----------------------------
A GNSS receiver that reappears on the bus is a receiver on the bus. It is not
evidence that its position solution is correct, and the two are separated by
however long it takes to establish a fix, agree with the other sensors, and
have that agreement observed for long enough to mean something.

A system that restores mission authority the instant a device answers has
implemented "the sensor is present, therefore the function works" -- which is
the same error as "no fault reported, therefore healthy", wearing a different
hat. BAD_PRODUCT_05 in the conformance suite is exactly this, and it must be
rejected.

HYSTERESIS, AND WHY IT IS ASYMMETRIC ON PURPOSE
------------------------------------------------
Loss is IMMEDIATE. Restoration requires `required_fresh_observations`
consecutive supported observations spanning at least `min_dwell_s`.

The asymmetry is deliberate and is not a tuning parameter dressed up: a
system should stop claiming a capability the moment its evidence goes, and
should resume claiming it only after the evidence has been re-established for
long enough that a flapping sensor cannot drive the claim. Making the two
symmetric would either delay a loss -- unsafe -- or make restoration
instant -- the failure above.

THESE ARE NOT CSIA THRESHOLDS. They live here, in a layer outside the frozen
core, they are declared per capability in the contract, and they touch no
gate, weight, prior or smoothing constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .capability import DEGRADED_SUPPORTED, SUPPORTED, UNKNOWN

#: The lifecycle. A transition not in TRANSITIONS is refused, so a state
#: machine cannot acquire a shortcut by accident.
PHASES = ("NOMINAL", "LOST", "RESTRICTED", "RECONFIGURED", "REMEASURING",
          "RECERTIFIED")

TRANSITIONS = {
    "NOMINAL": ("LOST",),
    "LOST": ("RESTRICTED",),
    "RESTRICTED": ("RECONFIGURED", "REMEASURING"),
    "RECONFIGURED": ("REMEASURING",),
    # RECERTIFIED is reachable ONLY from REMEASURING. There is deliberately no
    # edge from LOST or RESTRICTED: that edge would BE the shortcut.
    "REMEASURING": ("RECERTIFIED", "LOST"),
    "RECERTIFIED": ("NOMINAL", "LOST"),
}


class RecoveryError(ValueError):
    """An attempted transition the lifecycle does not permit."""


@dataclass
class RecoveryState:
    """One capability's recovery state machine."""
    capability_id: str
    phase: str = "NOMINAL"
    required_fresh_observations: int = 3
    min_dwell_s: float = 2.0
    consecutive_supported: int = 0
    first_supported_at: float | None = None
    last_transition_at: float = 0.0
    history: list = field(default_factory=list)

    # -- the machine -------------------------------------------------------

    def _to(self, phase: str, now: float, why: str) -> None:
        if phase not in TRANSITIONS.get(self.phase, ()):
            raise RecoveryError(
                f"{self.capability_id}: {self.phase} -> {phase} is not a "
                f"permitted transition. Permitted from {self.phase}: "
                f"{list(TRANSITIONS.get(self.phase, ()))}. In particular "
                f"there is no direct edge to RECERTIFIED: that edge would be "
                f"the shortcut this machine exists to prevent.")
        self.history.append({"from": self.phase, "to": phase, "at": now,
                             "why": why})
        self.phase = phase
        self.last_transition_at = now

    def observe(self, state: str, now: float) -> dict:
        """Feed one CANDIDATE capability state in. Returns what changed.

        `state` is a CapabilityReport state, not a boolean, because UNKNOWN
        must be distinguishable from NOT_SUPPORTED here too: an unknown
        observation neither counts towards recovery nor triggers a loss.

        **IT MUST BE THE CANDIDATE STATE, NOT THE PUBLISHED ONE.** This is
        MX-002, and it deadlocked the first version of the benchmark.

        The hold makes a capability UNKNOWN. If the machine is then fed that
        UNKNOWN -- the state its own hold produced -- it sees an observation
        that neither advances nor abandons recovery, resets the streak, and
        stays in RESTRICTED forever. The machine ends up deciding whether to
        lift the hold by reading the hold, which is circular and can only
        ever have one answer.

        So a caller must evaluate capabilities TWICE per tick:

            candidate = evaluate_capabilities(..., recertifying=())
            published = evaluate_capabilities(..., recertifying=held)

        feed `candidate[cid].state` to this method, and give `published` to
        products, certificates and the planner. `csia_mission.recovery.step`
        does both and is the safe way to call this.
        """
        usable = state in (SUPPORTED, DEGRADED_SUPPORTED)
        note = ""

        if state == UNKNOWN:
            # AN UNKNOWN OBSERVATION RESETS THE STREAK BUT DOES NOT LOSE.
            # It cannot count towards recovery (nothing was established) and
            # it cannot trigger a loss (nothing was refuted).
            self.consecutive_supported = 0
            self.first_supported_at = None
            return {"phase": self.phase, "changed": False,
                    "note": "UNKNOWN observation: streak reset, no transition"}

        if not usable:
            self.consecutive_supported = 0
            self.first_supported_at = None
            if self.phase == "NOMINAL":
                self._to("LOST", now, f"observed {state}")
                self._to("RESTRICTED", now, "capability withdrawn")
                note = "loss is immediate"
                return {"phase": self.phase, "changed": True, "note": note}
            if self.phase in ("REMEASURING", "RECERTIFIED"):
                self._to("LOST", now, f"observed {state} during recovery")
                self._to("RESTRICTED", now, "capability withdrawn again")
                return {"phase": self.phase, "changed": True,
                        "note": "recovery abandoned; evidence went away again"}
            return {"phase": self.phase, "changed": False, "note": ""}

        # usable observation
        if self.phase == "NOMINAL":
            return {"phase": self.phase, "changed": False, "note": ""}

        if self.phase == "RESTRICTED":
            self._to("REMEASURING", now, "supported evidence reappeared")
            self.consecutive_supported = 1
            self.first_supported_at = now
            return {"phase": self.phase, "changed": True,
                    "note": ("re-measuring. PRESENCE IS NOT RECOVERY: the "
                             "capability is NOT restored here")}

        if self.phase == "RECONFIGURED":
            self._to("REMEASURING", now, "post-reconfiguration measurement")
            self.consecutive_supported = 1
            self.first_supported_at = now
            return {"phase": self.phase, "changed": True, "note": ""}

        if self.phase == "REMEASURING":
            self.consecutive_supported += 1
            if self.first_supported_at is None:
                self.first_supported_at = now
            dwell = now - self.first_supported_at
            if (self.consecutive_supported >= self.required_fresh_observations
                    and dwell >= self.min_dwell_s):
                self._to("RECERTIFIED", now,
                         f"{self.consecutive_supported} consecutive supported "
                         f"observations over {dwell:.3f}s")
                return {"phase": self.phase, "changed": True,
                        "note": "re-certified on fresh evidence"}
            return {"phase": self.phase, "changed": False,
                    "note": (f"{self.consecutive_supported}/"
                             f"{self.required_fresh_observations} "
                             f"observations, dwell {dwell:.3f}/"
                             f"{self.min_dwell_s}s")}

        if self.phase == "RECERTIFIED":
            self._to("NOMINAL", now, "restored")
            return {"phase": self.phase, "changed": True, "note": "restored"}

        return {"phase": self.phase, "changed": False, "note": ""}

    def reconfigured(self, now: float) -> None:
        self._to("RECONFIGURED", now, "vehicle or payload reconfigured")

    @property
    def holds_capability(self) -> bool:
        """True while the capability must be HELD BACK from full restoration.

        Every phase except NOMINAL. RECERTIFIED still holds: the certificate
        exists but the restoration is one observation away, and reporting it
        as fully restored a tick early is the whole class of error here.
        """
        return self.phase != "NOMINAL"

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "phase": self.phase,
            "consecutive_supported": self.consecutive_supported,
            "required_fresh_observations": self.required_fresh_observations,
            "min_dwell_s": self.min_dwell_s,
            "holds_capability": self.holds_capability,
            "history": list(self.history),
        }


def held_capabilities(states: Mapping[str, RecoveryState]) -> tuple:
    """The `recertifying=` argument for `evaluate_capabilities`."""
    return tuple(sorted(cid for cid, s in states.items()
                        if s.holds_capability))


def step(contracts, evidence, now: float,
         recovery_states: Mapping[str, RecoveryState],
         **evaluate_kwargs) -> dict:
    """One tick, done correctly. Use this rather than wiring it by hand.

    The two evaluations and the order they happen in are the whole content of
    MX-002, so they live in a function rather than in a docstring anyone can
    skip:

        1. CANDIDATE  -- what the evidence says right now, hold ignored.
                         This is what the recovery machines observe.
        2. advance the machines on the candidate states.
        3. PUBLISHED  -- the same evaluation WITH the resulting holds applied.
                         This is what products, certificates and the planner
                         consume.

    Step 3 uses the holds computed in step 2, so a machine that reaches
    RECERTIFIED on this tick stops holding on this tick -- there is no
    one-tick lag between re-certification and restoration, and equally no way
    for a capability to be published as supported before its machine says so.
    """
    from .capability import evaluate_capabilities

    candidate = evaluate_capabilities(contracts, evidence, now,
                                      recertifying=(), **evaluate_kwargs)
    transitions = {}
    for cid, machine in sorted(recovery_states.items()):
        rep = candidate.get(cid)
        if rep is not None:
            transitions[cid] = machine.observe(rep.state, now)

    held = held_capabilities(recovery_states)
    published = evaluate_capabilities(contracts, evidence, now,
                                      recertifying=held, **evaluate_kwargs)
    return {"candidate": candidate, "published": published,
            "held": held, "transitions": transitions}
