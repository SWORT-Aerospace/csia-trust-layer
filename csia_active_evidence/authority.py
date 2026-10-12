"""An independent authorizer for a requested probe. ALLOW, CLIP or DENY.

WHAT THIS IS AND WHAT IT IS NOT
--------------------------------
THIS IS NOT FORGE, NOT SACA AND NOT ZETH. `forge/README_FUTURE.md` states
that no Forge production code exists in this repository and none may be
written, and `tests/test_program_state.py` holds `forge/` code-free. This
file is a much smaller thing: a DETERMINISTIC MOCK of the authorization
decision that a vehicle's own flight-envelope owner would make, written so
that the rest of `csia_active_evidence` has something that can refuse it.

It is the same shape as `csia_mission/planner.py::authorize`, deliberately.
That file gates a proposed mission action on capability state and has no
`override`, no `force` and no `advisory` mode. The absence is the mechanism.

WHY THIS EXISTS AS A SEPARATE FILE
-----------------------------------
A diagnostic layer that could authorise its own diagnostic actions has
exactly the authority it is built not to have. `csia/deploy/guard.py`
enforces at four layers that CSIA reaches no transmit path, and
`csia/contracts/validate.py` refuses any trust contract whose
`authorization.active_action_prohibited` is not literally True. Active
evidence acquisition does not change either fact and must not look like it
does:

    CSIA PRODUCES A REQUEST. SOMETHING ELSE DECIDES. NOTHING HERE TRANSMITS.

The request is a dataclass. The decision is a dataclass. No function in this
package opens a socket, and the `Authorization` object contains no callable
the requester could invoke to make the probe happen.

THE THIRD VERDICT, AND THE TRAP IN IT
--------------------------------------
`csia_mission/planner.py` has two verdicts. This has three, and CLIP is the
one that needs an argument, because a bounded partial authorization is
exactly how a safety gate turns into a rubber stamp: the authorizer feels
it has been accommodating, the requester runs something smaller, and nobody
checks whether the smaller thing can still answer the question.

    A CLIPPED PROBE IS A DIFFERENT PROBE AND ITS IDENTIFIABILITY MUST BE
    RECOMPUTED FROM THE CLIPPED WAVEFORM.

`Authorization.clipped_probe` returns the reduced probe, and every caller in
this package re-runs `ProbeRequirement.met_by` on it. `updater.py` abstains
when the clipped probe no longer meets the requirement rather than running
it and reporting a weaker answer as if it were the answer.
`tests/test_authority.py::test_a_clip_that_destroys_identifiability_is_not_
silently_accepted` is what holds that.

THE LIMITS ARE A MOCK
---------------------
`EnvelopeLimits` carries plausible numbers for a 1.5 kg quadrotor. THEY ARE
NOT MEASURED AND NOT A CERTIFICATION. A real deployment replaces this object
with its own flight-envelope authority, and the only thing this package
relies on is the interface: something that takes a request and returns one
of three verdicts without the requester being able to influence which.
"""

from __future__ import annotations

from dataclasses import dataclass, replace, asdict, field
from typing import Optional, Tuple

SCHEMA = "csia.active_evidence.authorization/1"

ALLOW = "ALLOW"
CLIP = "CLIP"
DENY = "DENY"
VERDICTS = (ALLOW, CLIP, DENY)

#: Every reason a probe can be refused or reduced. A verdict must name one.
REASONS = (
    "WITHIN_ENVELOPE",
    "ALTITUDE_HEADROOM_INSUFFICIENT",
    "ALTITUDE_FLOOR_INSUFFICIENT",
    "AMPLITUDE_ABOVE_ENVELOPE",
    "DURATION_ABOVE_ENVELOPE",
    "ENERGY_BUDGET_INSUFFICIENT",
    "VEHICLE_STATE_FORBIDS_PERTURBATION",
    "PROXIMITY_FORBIDS_PERTURBATION",
    "OPERATOR_INHIBIT",
    "NO_ENVELOPE_DECLARED",
)

#: Vehicle states in which a perturbation may be considered at all. Anything
#: not on this list is refused, so a state added upstream tomorrow is denied
#: today rather than silently permitted.
PERTURBABLE_STATES = ("CRUISE", "LOITER", "HOVER")


@dataclass(frozen=True)
class EnvelopeLimits:
    """What the vehicle's own envelope owner permits. A MOCK, see above."""

    max_vz_amplitude_m_s: float = 0.50
    max_duration_s: float = 10.0
    min_altitude_agl_m: float = 15.0
    min_headroom_m: float = 10.0
    max_energy_as: float = 30.0
    min_clearance_m: float = 8.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class VehicleState:
    """The inputs the authorizer reads. It reads nothing else.

    NOTE WHAT IS ABSENT: there is no field by which a requester states that
    a probe is important, urgent, or diagnostically necessary. The
    authorizer cannot be argued with, only measured against.
    """

    mode: str
    altitude_agl_m: float
    ceiling_agl_m: float
    clearance_m: float
    energy_margin_as: float
    operator_inhibit: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ProbeRequest:
    """What CSIA asks for. A value, not a command.

    `justification` is carried so a human reviewing a flight log can see why
    the probe was asked for. IT IS NOT READ BY `authorize`, on purpose.
    """

    probe_name: str
    vz_amplitude_m_s: float
    duration_s: float
    energy_cost_as: float
    justification: str
    schema: str = SCHEMA

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Authorization:
    """The decision. There is no override field and no force parameter."""

    verdict: str
    reasons: Tuple[str, ...]
    granted_vz_amplitude_m_s: float
    granted_duration_s: float
    request: ProbeRequest
    limits: EnvelopeLimits
    schema: str = SCHEMA

    def __post_init__(self):
        if self.verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")
        for r in self.reasons:
            if r not in REASONS:
                raise ValueError(f"unknown reason {r!r}; every refusal names "
                                 f"one of {REASONS}")
        if self.verdict == DENY and (self.granted_vz_amplitude_m_s != 0.0
                                     or self.granted_duration_s != 0.0):
            raise ValueError("a DENY may not grant a non-zero probe")

    @property
    def runnable(self) -> bool:
        return self.verdict in (ALLOW, CLIP)

    def clipped_probe(self, original):
        """The probe as AUTHORIZED, which may not be the one requested.

        Returns None on DENY. On CLIP the returned probe carries the granted
        amplitude and duration and a name that says it was clipped, so it
        cannot be confused with the library entry in an artifact.
        """
        if self.verdict == DENY:
            return None
        if self.verdict == ALLOW:
            return original
        return replace(original,
                       name=f"{original.name}@clipped",
                       vz_amplitude=self.granted_vz_amplitude_m_s,
                       duration_s=self.granted_duration_s)

    def to_dict(self) -> dict:
        return {"schema": self.schema, "verdict": self.verdict,
                "reasons": list(self.reasons),
                "granted_vz_amplitude_m_s": self.granted_vz_amplitude_m_s,
                "granted_duration_s": self.granted_duration_s,
                "request": self.request.to_dict(),
                "limits": self.limits.to_dict()}


def authorize(request: ProbeRequest, state: VehicleState,
              limits: Optional[EnvelopeLimits] = None) -> Authorization:
    """Decide. NOTE THE SIGNATURE.

    There is no `override`, no `force`, no `advisory` and no `urgency`. A
    requester that wanted a different answer would have to modify this file,
    which is a visible diff and a review. That is the enforcement mechanism,
    not a convention -- the same argument `csia_mission/planner.py` makes.

    DENY beats CLIP. A condition that no reduction can fix -- the wrong
    vehicle state, an operator inhibit, insufficient clearance or altitude
    -- refuses the probe outright, because clipping amplitude does not make
    a vehicle that is 3 m from an obstacle a safe place to perturb.
    """
    if limits is None:
        return Authorization(verdict=DENY, reasons=("NO_ENVELOPE_DECLARED",),
                             granted_vz_amplitude_m_s=0.0,
                             granted_duration_s=0.0, request=request,
                             limits=EnvelopeLimits())

    hard = []
    if state.operator_inhibit:
        hard.append("OPERATOR_INHIBIT")
    if state.mode not in PERTURBABLE_STATES:
        hard.append("VEHICLE_STATE_FORBIDS_PERTURBATION")
    if state.clearance_m < limits.min_clearance_m:
        hard.append("PROXIMITY_FORBIDS_PERTURBATION")
    if state.altitude_agl_m < limits.min_altitude_agl_m:
        hard.append("ALTITUDE_FLOOR_INSUFFICIENT")
    if state.ceiling_agl_m - state.altitude_agl_m < limits.min_headroom_m:
        hard.append("ALTITUDE_HEADROOM_INSUFFICIENT")
    if state.energy_margin_as < request.energy_cost_as:
        hard.append("ENERGY_BUDGET_INSUFFICIENT")
    if hard:
        return Authorization(verdict=DENY, reasons=tuple(hard),
                             granted_vz_amplitude_m_s=0.0,
                             granted_duration_s=0.0, request=request,
                             limits=limits)

    clip_reasons = []
    amplitude = request.vz_amplitude_m_s
    duration = request.duration_s
    if amplitude > limits.max_vz_amplitude_m_s:
        amplitude = limits.max_vz_amplitude_m_s
        clip_reasons.append("AMPLITUDE_ABOVE_ENVELOPE")
    if duration > limits.max_duration_s:
        duration = limits.max_duration_s
        clip_reasons.append("DURATION_ABOVE_ENVELOPE")
    # The energy a probe costs scales with both, so a clip on either is
    # re-checked against the budget rather than assumed to have helped.
    scaled = request.energy_cost_as
    if request.vz_amplitude_m_s > 0 and request.duration_s > 0:
        scaled = (request.energy_cost_as
                  * (amplitude / request.vz_amplitude_m_s)
                  * (duration / request.duration_s))
    if scaled > limits.max_energy_as:
        return Authorization(verdict=DENY,
                             reasons=tuple(clip_reasons
                                           + ["ENERGY_BUDGET_INSUFFICIENT"]),
                             granted_vz_amplitude_m_s=0.0,
                             granted_duration_s=0.0, request=request,
                             limits=limits)

    if clip_reasons:
        return Authorization(verdict=CLIP, reasons=tuple(clip_reasons),
                             granted_vz_amplitude_m_s=amplitude,
                             granted_duration_s=duration, request=request,
                             limits=limits)
    return Authorization(verdict=ALLOW, reasons=("WITHIN_ENVELOPE",),
                         granted_vz_amplitude_m_s=amplitude,
                         granted_duration_s=duration, request=request,
                         limits=limits)


def attempt_override(*_args, **_kwargs):
    """Exists so that its absence is greppable. Always raises.

    Copied in spirit from `csia_mission/planner.py::attempt_override`: a
    reader looking for a way to force a probe finds this, and a test asserts
    it raises.
    """
    raise PermissionError(
        "there is no override. An authorizer that can be overridden is not "
        "an authorizer; if a probe must run, the envelope limits are the "
        "thing to change, in a visible diff, by whoever owns them")
