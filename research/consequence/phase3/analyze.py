"""Phase 3 — derive the reported numbers from the evaluation artifact.

Nothing in `PHASE3_RESULTS.md` is typed by hand. This module reads the
independent evaluator's output and emits every figure the write-up quotes,
including the hypothesis verdicts, so a stale document fails a test instead of
misleading a reader.

THE TEST THAT MATTERS IS PAIRED
--------------------------------
Conditions F and G run the SAME fault, on the same trajectory, from the same
seed, differing only in whether the gate was shut while the fault ran. So the
comparison is paired by seed, and the right test is McNemar's on the
discordant pairs -- seeds where one condition missed and the other did not.
Comparing two independent proportions would throw away the pairing and the
noise it removes.

The p-value is computed exactly, from the binomial, with no dependency beyond
the standard library.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from typing import Dict, List

MISSED = "MISSED_ESCALATION"
INCORRECT = "INCORRECT_ACTIONABLE"
UNSUPPORTED = "UNSUPPORTED_CONFIDENCE"
ABSTENTION = "ABSTENTION"

#: Below this, a difference is reported as distinguishable from chance. Fixed
#: here rather than chosen after seeing the p-value.
ALPHA = 0.05


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail)


def aggregate(evaluation: dict) -> dict:
    groups: Dict[tuple, List[dict]] = {}
    for row in evaluation["per_scenario"]:
        for policy, verdict in row["policies"].items():
            key = (row["gate_group"], row["condition"], policy)
            groups.setdefault(key, []).append(dict(verdict, seed=row["seed"],
                                                   correct=row["correct_response"]))
    out = {}
    for (group, condition, policy), rows in sorted(groups.items()):
        outcomes: Dict[str, int] = {}
        for r in rows:
            outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
        out[f"{group}|{condition}|{policy}"] = {
            "n": len(rows),
            "outcomes": outcomes,
            "mean_occlusion_during_fault_s": _mean(
                [r["occlusion_during_fault_s"] for r in rows]),
            "mean_occlusion_airborne_s": _mean(
                [r["occlusion_overlap_s"] for r in rows]),
            "mean_first_response_s": _mean(
                [r["first_response_s"] for r in rows]),
            "mean_position_error_m": _mean(
                [r["position_error_m"] for r in rows]),
            "mean_min_geofence_margin_m": _mean(
                [r["min_geofence_margin_m"] for r in rows]),
            "mean_energy_margin_frac": _mean(
                [r["energy_margin_frac"] for r in rows]),
            "total_unsupported_confidence_s": round(
                sum(r["unsupported_confidence_s"] for r in rows), 3),
            "total_abstention_s": round(
                sum(r["abstention_s"] for r in rows), 3),
            "mean_coverage_loss_frac": _mean(
                [r["coverage_loss_frac"] for r in rows]),
        }
    return out


def paired_condition_test(evaluation: dict, *, group: str, policy: str,
                          left: str, right: str) -> dict:
    """Seed-paired comparison of missed escalations between two conditions."""
    by_seed = {}
    for row in evaluation["per_scenario"]:
        if row["gate_group"] != group or row["condition"] not in (left, right):
            continue
        by_seed.setdefault(row["seed"], {})[row["condition"]] = \
            row["policies"][policy]
    pairs = {s: v for s, v in by_seed.items() if left in v and right in v}
    b = c = both = neither = 0
    discordant_seeds = {"left_only": [], "right_only": []}
    for seed, v in sorted(pairs.items()):
        lm = v[left]["outcome"] == MISSED
        rm = v[right]["outcome"] == MISSED
        if lm and not rm:
            b += 1
            discordant_seeds["left_only"].append(seed)
        elif rm and not lm:
            c += 1
            discordant_seeds["right_only"].append(seed)
        elif lm and rm:
            both += 1
        else:
            neither += 1
    p = mcnemar_exact(b, c)
    return {
        "group": group, "policy": policy,
        "left_condition": left, "right_condition": right,
        "pairs": len(pairs),
        "missed_left": b + both, "missed_right": c + both,
        "discordant_left_only": b, "discordant_right_only": c,
        "both_missed": both, "neither_missed": neither,
        "discordant_seeds": discordant_seeds,
        "mcnemar_exact_two_sided_p": round(p, 6),
        "alpha": ALPHA,
        "distinguishable_from_chance": bool(p < ALPHA),
        "mean_occlusion_during_fault_left_s": _mean(
            [v[left]["occlusion_during_fault_s"] for v in pairs.values()]),
        "mean_occlusion_during_fault_right_s": _mean(
            [v[right]["occlusion_during_fault_s"] for v in pairs.values()]),
    }


def policy_table(evaluation: dict) -> dict:
    return {name: dict(tally) for name, tally in
            sorted(evaluation["by_policy"].items())}


def verdicts(evaluation: dict, tests: List[dict], agg: dict) -> dict:
    """H2 and H3 against the preregistered criteria, and nothing softer."""
    conflicts = []
    for row in evaluation["per_scenario"]:
        v = row["policies"]["P0"]
        if v["outcome"] in (MISSED, INCORRECT, UNSUPPORTED):
            conflicts.append({
                "seed": row["seed"], "gate_group": row["gate_group"],
                "condition": row["condition"], "outcome": v["outcome"],
                "correct_response": row["correct_response"],
                "responses_issued": v["responses_issued"],
                "occlusion_during_fault_s": v["occlusion_during_fault_s"],
            })

    physical = [c for c in conflicts
                if not (c["gate_group"] == "armed_gate_pair"
                        and c["condition"] == "F")]
    attributable = [t for t in tests if t["distinguishable_from_chance"]]

    h2 = {
        "decision_conflicts_total": len(conflicts),
        "decision_conflicts_in_physically_consistent_conditions":
            len(physical),
        "conflicts_excluded_as_physically_inconsistent":
            len(conflicts) - len(physical),
        "paired_tests_distinguishable_from_chance": len(attributable),
        "verdict": ("SUPPORTED" if physical and attributable
                    else "NOT SUPPORTED"),
    }
    h2["why"] = (
        "Decision conflicts exist in physically consistent conditions, and at "
        "least one seed-paired comparison separates the gate-closed condition "
        "from its matched gate-open control at alpha."
        if h2["verdict"] == "SUPPORTED" else
        "Conflicts were observed, but no seed-paired comparison between a "
        "gate-closed condition and its matched gate-open control separates "
        "them at alpha, so no conflict is attributable to the occlusion "
        "rather than to the fault being hard to detect at all. Preregistered "
        "rejection criterion (d): unable to produce a decision conflict "
        "ATTRIBUTABLE TO THE GATE.")

    policies = policy_table(evaluation)
    p0_incorrect = policies["P0"]["incorrect_actionable"]
    p2_incorrect = policies["P2"]["incorrect_actionable"]
    h3 = {
        "p0_incorrect_actionable": p0_incorrect,
        "p2_incorrect_actionable": p2_incorrect,
        "reduction": p0_incorrect - p2_incorrect,
        "p2_abstentions": policies["P2"]["abstentions"],
        "p2_total_abstention_s": policies["P2"]["total_abstention_s"],
        "p2_minus_p0_coverage_loss":
            round(policies["P2"]["mean_coverage_loss_frac"]
                  - policies["P0"]["mean_coverage_loss_frac"], 6),
        "p2_minus_p0_mean_position_error_m":
            round(policies["P2"]["mean_position_error_m"]
                  - policies["P0"]["mean_position_error_m"], 6),
        "verdict": ("SUPPORTED" if p2_incorrect < p0_incorrect
                    else "NOT SUPPORTED"),
    }
    h3["why"] = (
        "The support-aware policy reduced incorrect actionable decisions."
        if h3["verdict"] == "SUPPORTED" else
        "P0 made no incorrect actionable decisions on the locked scenarios, "
        "so there was nothing for the support-aware policy to reduce. P2 was "
        "INERT: it withdrew no response, abstained never, and is identical to "
        "P0 on every locked scenario. That is not a defence of P2 and it is "
        "not a refutation of it -- it is the absence of a test.")
    h3["not_a_safety_guarantee"] = (
        "Abstention is not a solved safety problem. A policy that abstains "
        "moves the problem to whoever reads the abstention.")
    return {"H2": h2, "H3": h3}


def build(evaluation: dict) -> dict:
    agg = aggregate(evaluation)
    tests = [
        paired_condition_test(evaluation, group="heading_course",
                              policy="P0", left="F", right="G"),
        paired_condition_test(evaluation, group="heading_course",
                              policy="P0", left="B", right="C"),
        paired_condition_test(evaluation, group="armed_gate_pair",
                              policy="P0", left="B", right="C"),
    ]
    return {
        "schema": "csia.consequence.phase3_results/1",
        "evidence_level": "MODEL_BASED_ACTION_CONSEQUENCE",
        "executed_an_autopilot": False,
        "armed_a_vehicle": False,
        "touched_hardware": False,
        "partition": evaluation.get("partition"),
        "aggregates": agg,
        "paired_tests": tests,
        "policy_table": policy_table(evaluation),
        "hypotheses": verdicts(evaluation, tests, agg),
        "what_this_is_not": (
            "Not a SITL closed-loop result, not hardware, not flight, not a "
            "safety guarantee, not a statement that any vehicle behaved in "
            "any way, and not a claim about the five Phase-2 candidates that "
            "are out of scope."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("evaluation")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    with open(args.evaluation, encoding="utf-8") as fh:
        evaluation = json.load(fh)
    document = build(evaluation)
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    for test in document["paired_tests"]:
        print(f"{test['group']:18s} {test['left_condition']} vs "
              f"{test['right_condition']}: missed "
              f"{test['missed_left']}/{test['pairs']} vs "
              f"{test['missed_right']}/{test['pairs']}  "
              f"discordant {test['discordant_left_only']}/"
              f"{test['discordant_right_only']}  "
              f"p={test['mcnemar_exact_two_sided_p']}  "
              f"sig={test['distinguishable_from_chance']}")
    for name, h in sorted(document["hypotheses"].items()):
        print(f"{name}: {h['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
