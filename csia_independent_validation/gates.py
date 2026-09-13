"""The two-gate assurance contract, and the 2x2 table that tests it.

``PREREGISTRATION_AMENDMENT_3.md`` §3-§4 fix both gates and the claim before
either was computed. This module implements them and adds nothing.

``GATE_PRE``   proposed action is predicted safe over the declared lag interval
               AND the nominal/target output sets are **strictly disjoint** at
               some sample time. Predicted, from the command and the declared
               envelope. Reads no truth.

``GATE_POST``  the realized-telemetry certificate returned
               ``CERTIFIED_IN_MODEL``. Reads no truth either -- it reads
               measurements.

Neither gate implies the other, and the claim under test is whether requiring
both rejects wrong inferences that neither alone rejects, and at what cost.

A negative result is an acceptable outcome and is named in the amendment: if
the post gate rejects nothing the pre gate did not already reject, RCEC is
redundant in this envelope, and this module will say so.

THE SAFETY SUB-GATE IS VACUOUS OVER THIS ACTION SPACE, AND THAT IS MEASURED
---------------------------------------------------------------------------
Every admissible action has a peak excess of at most 14 A on a 20 A hover
draw, so the worst predicted current is 34 A against a limit of 56 A. **No
admissible action can fail the safety check.** It fails only for an
abstention, where there is no action to check.

That is a property of the action space -- ``PEAK_EXCESS_LIMIT_A`` is 16 A and
was frozen before any of this -- not a property of the check, and the check
itself works: a 45 A hold fails it. Both facts are pinned by tests.

It is stated here rather than left for a reader to notice because a gate that
cannot fail measures nothing, and this phase's first finding was a check of
exactly that shape. The consequence is concrete and travels with every result:
**all of the pre-action gate's discriminating power comes from the separation
sub-gate.**
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from . import discrimination as disc
from . import strategies as st
from .actions import Action, by_name
from .plants import SYNTHETIC_LOOP

LAYER = "B"
TRUTH_BEARING = True
SCHEMA = "csia.independent_validation.gates/1"

#: Declared safety margin on the current limit, in amps. An engineering
#: declaration, fixed with the gate.
CLIP_MARGIN_A = 4.0

#: The declared lag interval the safety check is taken over. The plant's lag is
#: 0.25 s; the gate does not get to know that, so it works over a factor of two
#: either side, which is what the lag-error ablation sweeps.
LAG_INTERVAL_S = (0.125, 0.500)

#: Policies compared in the table.
POLICIES = ("accept_always", "accept_if_pre", "accept_if_post",
            "accept_if_both")


@dataclass(frozen=True)
class PreGate:
    """Why the pre-action gate passed or failed. Predicted, never measured."""

    safe: bool
    separates: bool
    peak_current_a: float
    separation_margin_v: float
    overlap_volume_v: float
    touching: bool

    @property
    def passes(self) -> bool:
        return self.safe and self.separates

    def to_dict(self) -> Dict:
        return {"safe": self.safe, "separates": self.separates,
                "peak_current_a": self.peak_current_a,
                "separation_margin_v": self.separation_margin_v,
                "overlap_volume_v": self.overlap_volume_v,
                "touching": self.touching, "passes": self.passes}


def predicted_safe(action: Action) -> tuple:
    """Worst predicted current over the declared lag interval, against the limit.

    The realized current is a convex combination of past demand, so its
    supremum is bounded by the supremum of the demand whatever the lag. Taking
    the worst case over the declared interval is therefore the demand peak
    itself, and the check is exact rather than conservative-by-guesswork.
    """
    peak = SYNTHETIC_LOOP["base_current"] + action.peak_excess_a
    limit = SYNTHETIC_LOOP["saturation_a"] - CLIP_MARGIN_A
    return peak <= limit, peak


def pre_gate(action_name: Optional[str], magnitude: float, *,
             plant: str = "Q1", seed: int = 0,
             duration_default: float = 8.0) -> PreGate:
    """Evaluate ``GATE_PRE`` for a proposed action at a target magnitude.

    An abstention -- no action proposed -- fails the gate: there is nothing to
    certify as safe and nothing to separate. That is a pass-through of the
    selector's own answer, not a judgement added here.
    """
    if action_name is None:
        return PreGate(safe=False, separates=False, peak_current_a=0.0,
                       separation_margin_v=float("nan"),
                       overlap_volume_v=float("nan"), touching=False)
    action = by_name(action_name)
    safe, peak = predicted_safe(action)
    outcome = disc.nominal_versus(
        action.command(), magnitude=magnitude, plant=plant,
        duration=action.duration_s or duration_default, seed=seed)
    return PreGate(safe=safe, separates=outcome.empty_intersection,
                   peak_current_a=peak,
                   separation_margin_v=outcome.separation_margin,
                   overlap_volume_v=outcome.overlap_volume,
                   touching=outcome.touching)


def post_gate(state: Optional[str]) -> bool:
    return state == "CERTIFIED_IN_MODEL"


def accepted(policy: str, pre: bool, post: bool) -> bool:
    if policy == "accept_always":
        return True
    if policy == "accept_if_pre":
        return pre
    if policy == "accept_if_post":
        return post
    if policy == "accept_if_both":
        return pre and post
    raise ValueError(f"unknown policy {policy!r}")


def gate_table(rows: Sequence[Dict]) -> Dict:
    """The full 2x2 table plus the four policy summaries.

    ``rows`` carry ``pre_pass``, ``post_pass``, ``resolved_point``,
    ``energy_as`` and ``duration_s``. A row whose independent outcome is
    unknown -- an abstention, or a cell with no estimate -- counts as **not
    resolved**, because a policy that accepts an inference nobody can score is
    accepting a wrong inference for the purposes of this table.
    """
    cells: Dict[str, Dict] = {}
    for pre in (True, False):
        for post in (True, False):
            subset = [r for r in rows
                      if r["pre_pass"] == pre and r["post_pass"] == post]
            resolved = [r for r in subset if r["resolved_point"]]
            cells[f"pre={pre}/post={post}"] = {
                "n": len(subset),
                "resolved": len(resolved),
                "wrong": len(subset) - len(resolved),
                "resolved_fraction": (len(resolved) / len(subset)
                                      if subset else None),
            }

    policies: Dict[str, Dict] = {}
    total = len(rows)
    for policy in POLICIES:
        taken = [r for r in rows
                 if accepted(policy, r["pre_pass"], r["post_pass"])]
        wrong = [r for r in taken if not r["resolved_point"]]
        policies[policy] = {
            "accepted": len(taken),
            "coverage": len(taken) / total if total else None,
            "false_accepted": len(wrong),
            "false_accept_rate": (len(wrong) / len(taken)
                                  if taken else None),
            "false_accepted_per_1000_cells": (1000.0 * len(wrong) / total
                                              if total else None),
            "mean_energy_as_of_accepted": (
                statistics.mean(r["energy_as"] for r in taken)
                if taken else None),
            "mean_duration_s_of_accepted": (
                statistics.mean(r["duration_s"] for r in taken)
                if taken else None),
        }

    both = policies["accept_if_both"]
    pre_only = policies["accept_if_pre"]
    post_only = policies["accept_if_post"]
    verdict = {
        "combined_beats_pre_alone":
            both["false_accepted"] < pre_only["false_accepted"],
        "combined_beats_post_alone":
            both["false_accepted"] < post_only["false_accepted"],
        "post_gate_redundant":
            both["false_accepted"] == pre_only["false_accepted"],
        "pre_gate_redundant":
            both["false_accepted"] == post_only["false_accepted"],
        "coverage_cost_against_pre_alone":
            (pre_only["coverage"] - both["coverage"])
            if both["coverage"] is not None else None,
        "coverage_cost_against_post_alone":
            (post_only["coverage"] - both["coverage"])
            if both["coverage"] is not None else None,
    }
    return {"cells": cells, "policies": policies, "verdict": verdict,
            "n_rows": total,
            "note": ("a row with no scoreable outcome counts as not resolved; "
                     "accepting an inference nobody can score is accepting a "
                     "wrong one for this table")}
