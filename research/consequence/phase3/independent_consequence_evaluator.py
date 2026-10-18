"""Phase 3 — the independent consequence evaluator.

WHAT "INDEPENDENT" MEANS HERE, EXACTLY
---------------------------------------
This module imports the standard library and nothing else. It does not import
the CSIA diagnostic implementation, the support classifier, the policy
implementation, or the action adapter. It consumes serialized scenario traces
and ground-truth annotations and classifies outcomes from those alone. A test
asserts the import property in a fresh interpreter by inspecting `sys.modules`.

It re-declares the response vocabulary rather than importing it. That is
deliberate: if the campaign ever emits a response this module has not been
told about, the classification must FAIL rather than quietly bucket it.

**It is a second derivation, not a second party.** The same author wrote the
campaign and this. The same caveat that Phase 2 records about its gate
evaluator applies here and is not softened.

MATERIALITY IS DECIDED HERE AND NOWHERE ELSE
---------------------------------------------
H2 needs "materially different" to mean something a policy cannot define for
itself. Two responses are materially different iff they fall in different
RESPONSE CLASSES (below). `SELECT_IMU0` versus `SELECT_IMU1` is the case the
whole phase turns on, and they are in different classes: choosing the faulty
inertial unit is not a milder version of choosing the good one.

Materiality is a property of the RESPONSES, judged against ground truth. It is
not read off the consequence model's numbers, because those numbers come from
the model's own constants and using them to establish materiality would make
the argument circular.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, List

# --- the response vocabulary, re-declared on purpose ----------------------
R_NONE = "NONE"
R_CAUTION_GENERIC = "CAUTION_GENERIC"
R_SELECT_IMU0 = "SELECT_IMU0"
R_SELECT_IMU1 = "SELECT_IMU1"
R_PREPARE_LANDING = "PREPARE_LANDING"
R_CONTROLLED_DESCENT = "CONTROLLED_DESCENT"
R_ABSTAIN = "ABSTAIN"

#: response -> class. Two responses are materially different iff their
#: classes differ.
RESPONSE_CLASS = {
    R_NONE: "NO_ACTION",
    R_CAUTION_GENERIC: "CONSERVATIVE",
    R_ABSTAIN: "CONSERVATIVE",
    R_SELECT_IMU0: "ATTRIBUTION_IMU0",
    R_SELECT_IMU1: "ATTRIBUTION_IMU1",
    R_PREPARE_LANDING: "TERMINATE",
    R_CONTROLLED_DESCENT: "TERMINATE",
}

ATTRIBUTING = frozenset({R_SELECT_IMU0, R_SELECT_IMU1})
CONSERVATIVE = frozenset({R_CAUTION_GENERIC, R_ABSTAIN})

IDENTIFIABLE = "IDENTIFIABLE"

# --- outcome classes ------------------------------------------------------
CORRECT_ACTIONABLE = "CORRECT_ACTIONABLE"
INCORRECT_ACTIONABLE = "INCORRECT_ACTIONABLE"
UNSUPPORTED_CONFIDENCE = "UNSUPPORTED_CONFIDENCE"
ABSTENTION = "ABSTENTION"
SAFE_FALLBACK = "SAFE_FALLBACK"
MISSED_ESCALATION = "MISSED_ESCALATION"
FALSE_ESCALATION = "FALSE_ESCALATION"

OUTCOME_CLASSES = (CORRECT_ACTIONABLE, INCORRECT_ACTIONABLE,
                   UNSUPPORTED_CONFIDENCE, ABSTENTION, SAFE_FALLBACK,
                   MISSED_ESCALATION, FALSE_ESCALATION)


class TraceError(ValueError):
    """The trace says something this evaluator was not told how to read."""


def materially_different(a: str, b: str) -> bool:
    for response in (a, b):
        if response not in RESPONSE_CLASS:
            raise TraceError(f"unknown response {response!r}; the campaign "
                             f"emitted something this evaluator cannot class")
    return RESPONSE_CLASS[a] != RESPONSE_CLASS[b]


def _airborne_span(segments) -> float:
    return sum(s["t_end"] - s["t_start"] for s in segments if s["airborne"])


def classify(segments: List[dict], *, correct_response: str) -> dict:
    """One policy on one scenario -> an outcome class and its supporting spans.

    Order of the checks is the definition, not an implementation detail:
    an unsupported confident attribution is reported ahead of whether the
    attribution happened to be right, because the point of the class is that
    the evidence could not have told.
    """
    if correct_response not in RESPONSE_CLASS:
        raise TraceError(f"unknown correct response {correct_response!r}")
    issued = []
    unsupported_s = 0.0
    ambiguous_s = 0.0
    abstain_s = 0.0
    idle_s = 0.0
    for seg in segments:
        response = seg["response"]
        if response not in RESPONSE_CLASS:
            raise TraceError(f"unknown response {response!r} in trace")
        span = seg["t_end"] - seg["t_start"]
        if response != R_NONE:
            issued.append((seg["t_start"], response))
        if not seg["airborne"]:
            continue
        if seg["pair_support"] != IDENTIFIABLE:
            ambiguous_s += span
            if response in ATTRIBUTING:
                unsupported_s += span
        if response == R_ABSTAIN:
            abstain_s += span
        if response == R_NONE:
            idle_s += span

    kinds = {r for _t, r in issued}
    airborne = _airborne_span(segments)

    if unsupported_s > 0.0:
        outcome = UNSUPPORTED_CONFIDENCE
    elif correct_response == R_NONE:
        actionable = kinds - CONSERVATIVE
        outcome = FALSE_ESCALATION if actionable else CORRECT_ACTIONABLE
        if not actionable and kinds:
            outcome = FALSE_ESCALATION if kinds - {R_ABSTAIN} else ABSTENTION
    elif correct_response in kinds:
        outcome = CORRECT_ACTIONABLE
    elif any(materially_different(r, correct_response)
             and r in ATTRIBUTING for r in kinds):
        outcome = INCORRECT_ACTIONABLE
    elif R_ABSTAIN in kinds:
        outcome = ABSTENTION
    elif kinds & CONSERVATIVE or kinds:
        outcome = SAFE_FALLBACK
    else:
        outcome = MISSED_ESCALATION

    first = min(issued)[0] if issued else None
    correct_at = min((t for t, r in issued if r == correct_response),
                     default=None)
    return {
        "outcome": outcome,
        "responses_issued": sorted(kinds),
        "first_response_s": first,
        "correct_response_s": correct_at,
        "unsupported_confidence_s": round(unsupported_s, 3),
        "ambiguity_s": round(ambiguous_s, 3),
        "abstention_s": round(abstain_s, 3),
        "idle_while_fault_s": round(idle_s if correct_response != R_NONE
                                    else 0.0, 3),
        "airborne_s": round(airborne, 3),
        "coverage_loss_frac": round(
            ((idle_s + abstain_s) / airborne) if airborne
            and correct_response != R_NONE else 0.0, 4),
        "materially_different_from_correct": sorted(
            r for r in kinds if materially_different(r, correct_response)),
    }


def occlusion_overlap_s(segments) -> float:
    """Airborne time during which a gate under test is closed.

    This is the quantity H2 turns on. An occlusion that never overlaps the
    window in which decisions are taken cannot produce a decision conflict,
    however real it is structurally.
    """
    total = 0.0
    for seg in segments:
        if not seg["airborne"]:
            continue
        if not all(seg["gates_open"].values()):
            total += seg["t_end"] - seg["t_start"]
    return round(total, 3)


def occlusion_during_fault_s(segments, window) -> float:
    """Airborne time with a gate closed, restricted to the fault window.

    The quantity that actually bears on whether a gate closure could have
    hidden a fault. `occlusion_overlap_s` over a whole flight can be large for
    a reason that has nothing to do with the fault -- a hovering vehicle keeps
    its speed gate shut for most of the mission -- and two conditions can
    match on it while differing completely on this.
    """
    if not window:
        return 0.0
    lo, hi = float(window[0]), float(window[1])
    total = 0.0
    for seg in segments:
        if not seg["airborne"] or all(seg["gates_open"].values()):
            continue
        start = max(seg["t_start"], lo)
        end = min(seg["t_end"], hi)
        if end > start:
            total += end - start
    return round(total, 3)


def evaluate(document: dict) -> dict:
    """Whole campaign -> per-policy tallies and the H2/H3 inputs."""
    policies: Dict[str, dict] = {}
    per_scenario = []
    for scenario in document["scenarios"]:
        correct = scenario["correct_response"]
        row = {"seed": scenario["seed"], "gate_group": scenario["gate_group"],
               "condition": scenario["condition"],
               "correct_response": correct, "policies": {}}
        for name, payload in sorted(scenario["policies"].items()):
            segments = payload["segments"]
            verdict = classify(segments, correct_response=correct)
            verdict["occlusion_overlap_s"] = occlusion_overlap_s(segments)
            verdict["occlusion_during_fault_s"] = occlusion_during_fault_s(
                segments, scenario.get("fault_window_s"))
            verdict["fault_window_s"] = scenario.get("fault_window_s")
            verdict["time_to_safe_state_s"] = \
                payload["outcome"]["time_to_safe_state_s"]
            verdict["position_error_m"] = round(
                payload["outcome"]["position_error_m"], 3)
            verdict["min_geofence_margin_m"] = round(
                payload["outcome"]["min_geofence_margin_m"], 3)
            verdict["energy_margin_frac"] = round(
                payload["outcome"]["energy_margin_frac"], 4)
            row["policies"][name] = verdict
            tally = policies.setdefault(name, {
                "scenarios": 0, "by_outcome": {},
                "incorrect_actionable": 0, "correct_actionable": 0,
                "abstentions": 0, "ambiguous_outputs": 0,
                "safe_fallbacks": 0, "false_escalations": 0,
                "missed_escalations": 0,
                "unsupported_confidence_scenarios": 0,
                "total_ambiguity_s": 0.0, "total_abstention_s": 0.0,
                "total_position_error_m": 0.0,
                "coverage_loss_frac_sum": 0.0,
                "safe_state_reached": 0,
            })
            tally["scenarios"] += 1
            tally["by_outcome"][verdict["outcome"]] = \
                tally["by_outcome"].get(verdict["outcome"], 0) + 1
            tally["incorrect_actionable"] += \
                verdict["outcome"] == INCORRECT_ACTIONABLE
            tally["correct_actionable"] += \
                verdict["outcome"] == CORRECT_ACTIONABLE
            tally["abstentions"] += verdict["outcome"] == ABSTENTION
            tally["ambiguous_outputs"] += verdict["ambiguity_s"] > 0.0
            tally["safe_fallbacks"] += verdict["outcome"] == SAFE_FALLBACK
            tally["false_escalations"] += verdict["outcome"] == FALSE_ESCALATION
            tally["missed_escalations"] += \
                verdict["outcome"] == MISSED_ESCALATION
            tally["unsupported_confidence_scenarios"] += \
                verdict["unsupported_confidence_s"] > 0.0
            tally["total_ambiguity_s"] += verdict["ambiguity_s"]
            tally["total_abstention_s"] += verdict["abstention_s"]
            tally["total_position_error_m"] += verdict["position_error_m"]
            tally["coverage_loss_frac_sum"] += verdict["coverage_loss_frac"]
            tally["safe_state_reached"] += \
                verdict["time_to_safe_state_s"] is not None
        per_scenario.append(row)

    for tally in policies.values():
        n = tally["scenarios"]
        tally["mean_coverage_loss_frac"] = round(
            tally["coverage_loss_frac_sum"] / n, 4) if n else 0.0
        tally["mean_position_error_m"] = round(
            tally["total_position_error_m"] / n, 3) if n else 0.0
        tally["total_ambiguity_s"] = round(tally["total_ambiguity_s"], 3)
        tally["total_abstention_s"] = round(tally["total_abstention_s"], 3)
        tally["total_position_error_m"] = round(
            tally["total_position_error_m"], 3)
        del tally["coverage_loss_frac_sum"]

    return {"per_scenario": per_scenario, "by_policy": policies}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("traces")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    with open(args.traces, encoding="utf-8") as fh:
        document = json.load(fh)
    result = evaluate(document)
    result["schema"] = "csia.consequence.phase3_evaluation/1"
    result["source_traces"] = args.traces
    result["partition"] = document.get("partition")
    result["evidence_level"] = document.get("evidence_level")
    text = json.dumps(result, indent=1, sort_keys=True) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    for name, tally in sorted(result["by_policy"].items()):
        print(f"{name}: {tally['by_outcome']}  "
              f"incorrect={tally['incorrect_actionable']}  "
              f"abstain={tally['abstentions']}  "
              f"mean_cov_loss={tally['mean_coverage_loss_frac']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
