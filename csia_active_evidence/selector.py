"""Choose the cheapest probe that is PREDICTED to answer the question.

CLOSED FORM, NOT A SEARCH
--------------------------
`identifiability.probe_requirement` inverts the error model into three
inequalities on a probe's statistics. Selection is therefore evaluating
seven inequalities against seven probes and sorting the survivors by cost.
There is no optimiser, no simulator in the loop, no model fitting and no
learning, and there is nothing here that could be tuned to make a result
come out. If the requirement is wrong the selection is wrong, visibly, and
`tools/research/active_evidence_campaign.py` is the independent check.

COST IS DECLARED, AND IT IS NOT ONE NUMBER
-------------------------------------------
Three costs matter and they are not commensurable: charge drawn, seconds
spent, and how much the vehicle visibly moves. Collapsing them into a single
scalar would need weights, weights would need a justification, and no
justification exists that is not an invented number. `ORDER` is therefore a
declared LEXICOGRAPHIC ordering -- energy, then duration, then amplitude --
and it is stated in the artifact so a reader disagreeing with it can see
exactly what was preferred and re-sort the full ranking, which is always
returned.

THE DEFECT THAT MADE THIS FILE WRONG, AND THE CONDITION THAT FIXES IT
----------------------------------------------------------------------
An earlier revision scored probes against `probe_requirement` alone. The
pair campaign then measured that the SELECTED probe was the WORST of five
arms: it closed `effort_drift`, which is gated on a stationary operating
point, without opening `source_impedance`, which is gated on the load
varying. It paid the whole cost of probing and collected none of the
benefit.

The cause is that two independent eligibility criteria existed for the same
relation and nobody had reconciled them. `probe_requirement` is derived from
the error model and said the probe was adequate. `residuals.source_impedance`
declares `min_current_sd = 0.25` A and refused to run at a realised 0.2438.
Both are in this repository, both are defensible, and the selector was
optimising against one while the evidence obeyed the other.

    A PROBE THAT DOES NOT OPEN THE RELATION'S OWN GATE CANNOT PRODUCE
    EVIDENCE, WHATEVER THE ERROR MODEL SAYS.

`gate_threshold()` reads `min_current_sd` out of the residual's signature by
introspection rather than copying the number, so the two cannot drift apart
again. The check is applied to the PREDICTED excitation, which the
realisation measurement showed understates the realised one by 1.46x to
1.76x, so the condition is conservative in the safe direction.

WHAT IT DOES WHEN NOTHING WORKS
--------------------------------
It returns NO_PROBE_MEETS_THE_REQUIREMENT, with every probe's failing
condition. That is a RESULT, not an error: it says the question cannot be
answered by any bounded action in this library, which is exactly the thing
an abstaining diagnostic layer needs to be able to say. A selector that
returned its best failing candidate would hand back a probe that is
predicted not to work, and the caller would run it.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Tuple

import inspect

from . import probes as PR
from .identifiability import ProbeRequirement


def gate_threshold() -> float:
    """`min_current_sd` from `residuals.source_impedance`, by introspection.

    Read rather than copied. A number copied into a second file is a number
    that will disagree with the first one eventually, which is exactly the
    defect this function exists to close.
    """
    from csia_components import residuals as R
    sig = inspect.signature(R.source_impedance)
    default = sig.parameters["min_current_sd"].default
    if not isinstance(default, (int, float)):
        raise RuntimeError(
            "residuals.source_impedance no longer declares a numeric "
            "min_current_sd default; the selector cannot derive the "
            "eligibility threshold and must not guess one")
    return float(default)

SCHEMA = "csia.active_evidence.selection/1"

SELECTED = "PROBE_SELECTED"
NONE_MEET = "NO_PROBE_MEETS_THE_REQUIREMENT"
PASSIVE = "PASSIVE_DATA_ALREADY_SUFFICIENT"

#: Lexicographic, declared, and reported. Not weights.
ORDER = ("energy_cost_as", "duration_s", "vz_amplitude_m_s")


@dataclass(frozen=True)
class Selection:
    verdict: str
    probe_name: Optional[str]
    ranking: Tuple[dict, ...]
    rejected: Tuple[dict, ...]
    order: Tuple[str, ...]
    requirement: dict
    note: str
    schema: str = SCHEMA

    def to_dict(self) -> dict:
        out = asdict(self)
        out["ranking"] = list(self.ranking)
        out["rejected"] = list(self.rejected)
        out["order"] = list(self.order)
        return out


def select(requirement: ProbeRequirement, *, hz: float = PR.LOOP_HZ,
           amps_per_vz: float = PR.CURRENT_PER_AMP_OF_VZ,
           passive_stats=None, respect_relation_gate: bool = True
           ) -> Selection:
    """The cheapest probe meeting `requirement`, or a refusal.

    `passive_stats` is the excitation already present in the flight the
    vehicle is flying anyway. IT IS CHECKED FIRST. A layer that probes when
    the data it already has would answer the question is spending the
    vehicle's energy and the operator's patience to learn nothing, and the
    cheapest diagnostic action is always the one not taken.
    """
    if passive_stats is not None:
        passive = requirement.met_by(passive_stats)
        if passive["met"]:
            return Selection(
                verdict=PASSIVE, probe_name=None, ranking=(), rejected=(),
                order=ORDER, requirement=requirement.to_dict(),
                note=("the excitation already present in normal flight "
                      "meets the requirement; no probe is needed and none "
                      "is requested"))

    threshold = gate_threshold() if respect_relation_gate else 0.0
    scored = PR.meeting(requirement, hz=hz, amps_per_vz=amps_per_vz)
    for row in scored:
        std_i = PR.probe(row["probe"]).stats(hz, amps_per_vz).std_i
        row["predicted_std_i"] = std_i
        row["opens_relation_gate"] = std_i >= threshold
        if not row["opens_relation_gate"]:
            row["met"] = False
            row["failed"] = sorted(set(row["failed"]) | {"relation_gate"})
    met = [s for s in scored if s["met"]]
    rejected = [s for s in scored if not s["met"]]

    if not met:
        return Selection(
            verdict=NONE_MEET, probe_name=None, ranking=(),
            rejected=tuple(rejected), order=ORDER,
            requirement=requirement.to_dict(),
            note=("no bounded probe in this library is predicted to resolve "
                  "the requested change; the failing condition is recorded "
                  "per probe, and the correct response is to abstain rather "
                  "than to run the least-bad candidate"))

    met.sort(key=lambda s: tuple(s[k] for k in ORDER))
    return Selection(
        verdict=SELECTED, probe_name=met[0]["probe"], ranking=tuple(met),
        rejected=tuple(rejected), order=ORDER,
        requirement=requirement.to_dict(),
        note=("cheapest probe meeting every necessary condition, under the "
              "declared lexicographic ordering; the full ranking is "
              "returned so a different ordering can be applied by a reader "
              "who disagrees with this one"))
