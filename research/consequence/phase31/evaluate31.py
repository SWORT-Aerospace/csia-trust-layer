"""Phase 3.1 — independent evaluation and analysis.

INDEPENDENCE
------------
Standard library only. It imports no CSIA module, no policy, no support
classifier and no consequence model, and a test asserts that in a fresh
interpreter. It consumes serialized traces and ground-truth annotations.

It reuses Phase 3's `RESPONSE_CLASS` materiality rule -- restated here, not
imported, so that a campaign emitting an unknown response FAILS rather than
being silently bucketed.

WHAT IT DOES DIFFERENTLY FROM PHASE 3'S EVALUATOR, AND WHY
-----------------------------------------------------------
Durations are `ticks / TICK_HZ`, not `t_end - t_start`. The frozen failsafe
issues each action exactly once, so an attributing response is the response
label for a single tick; under Phase 3's span rule that is a duration of
zero, and any threshold on it would measure the logging format instead of the
decision. The rule is declared in §7.1 of the Phase-3.1 amendment, before the
locked run.

Phase 3's own numbers are NOT recomputed here. Its campaign and evaluator are
untouched and its result stands as recorded.

STATISTICS
----------
Exact two-sided McNemar on seed-paired discordant counts, and exact
Clopper-Pearson 95 % intervals on rates, both from the standard library. The
Clopper-Pearson bound is what lets a zero count say something: zero conflicts
over 40 paired seeds bounds the rate at 0.0881, where zero over 24 bounds it
only at 0.1425.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from typing import Dict, List

TICK_HZ = 25.0
MIN_STATE_S = 1.0
ALPHA = 0.05

R_NONE = "NONE"
R_ABSTAIN = "ABSTAIN"
RESPONSE_CLASS = {
    "NONE": "NO_ACTION",
    "CAUTION_GENERIC": "CONSERVATIVE",
    "ABSTAIN": "CONSERVATIVE",
    "SELECT_IMU0": "ATTRIBUTION_IMU0",
    "SELECT_IMU1": "ATTRIBUTION_IMU1",
    "PREPARE_LANDING": "TERMINATE",
    "CONTROLLED_DESCENT": "TERMINATE",
}
ATTRIBUTING = frozenset({"SELECT_IMU0", "SELECT_IMU1"})
IDENTIFIABLE = "IDENTIFIABLE"


class TraceError(ValueError):
    pass


def span_s(segment: dict) -> float:
    """A segment's duration. See the module docstring for why it is `ticks`."""
    return float(segment["ticks"]) / TICK_HZ


def materially_different(a: str, b: str) -> bool:
    for r in (a, b):
        if r not in RESPONSE_CLASS:
            raise TraceError(f"unknown response {r!r}")
    return RESPONSE_CLASS[a] != RESPONSE_CLASS[b]


def clopper_pearson(k: int, n: int, alpha: float = ALPHA):
    """Exact two-sided binomial interval, from the standard library.

    Inverted from the binomial CDF by bisection rather than pulled from a
    beta quantile, so this module keeps its no-dependency property.
    """
    # A LIST, not a tuple: the results artifact is JSON, and a tuple comes
    # back as a list, so a test that rebuilds the artifact and compares it
    # would fail on the type alone and say nothing about the numbers.
    if n == 0:
        return [0.0, 1.0]

    def cdf_at_least(p, m):        # P(X >= m) for X ~ Bin(n, p)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                   for i in range(m, n + 1))

    def cdf_at_most(p, m):         # P(X <= m)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                   for i in range(0, m + 1))

    def bisect(f, target):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if f(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    low = 0.0 if k == 0 else bisect(lambda p: cdf_at_least(p, k), alpha / 2.0)
    high = 1.0 if k == n else bisect(
        lambda p: -cdf_at_most(p, k), -(alpha / 2.0))
    return [round(low, 6), round(high, 6)]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail)


def classify(segments: List[dict], *, correct_response: str) -> dict:
    if correct_response not in RESPONSE_CLASS:
        raise TraceError(f"unknown correct response {correct_response!r}")
    issued, unsupported_s, ambiguous_s, abstain_s, idle_s = [], 0.0, 0.0, 0.0, 0.0
    airborne_s = 0.0
    for seg in segments:
        response = seg["response"]
        if response not in RESPONSE_CLASS:
            raise TraceError(f"unknown response {response!r} in trace")
        d = span_s(seg)
        if response != R_NONE:
            issued.append((seg["t_start"], response))
        if not seg["airborne"]:
            continue
        airborne_s += d
        if seg["pair_support"] != IDENTIFIABLE:
            ambiguous_s += d
            if response in ATTRIBUTING:
                unsupported_s += d
        if response == R_ABSTAIN:
            abstain_s += d
        if response == R_NONE:
            idle_s += d

    kinds = {r for _t, r in issued}
    classes = {RESPONSE_CLASS[r] for r in kinds}
    conflict = bool(kinds) and RESPONSE_CLASS[correct_response] not in classes
    if not kinds and correct_response != R_NONE:
        conflict = True

    if unsupported_s > 0.0:
        outcome = "UNSUPPORTED_CONFIDENCE"
    elif correct_response == R_NONE:
        outcome = ("FALSE_ESCALATION" if kinds - {R_ABSTAIN}
                   else ("ABSTENTION" if kinds else "CORRECT_ACTIONABLE"))
    elif correct_response in kinds:
        outcome = "CORRECT_ACTIONABLE"
    elif any(r in ATTRIBUTING and materially_different(r, correct_response)
             for r in kinds):
        outcome = "INCORRECT_ACTIONABLE"
    elif R_ABSTAIN in kinds:
        outcome = "ABSTENTION"
    elif kinds:
        outcome = "SAFE_FALLBACK"
    else:
        outcome = "MISSED_ESCALATION"

    return {
        "outcome": outcome,
        "responses_issued": sorted(kinds),
        "response_classes_issued": sorted(classes),
        "correct_response_class": RESPONSE_CLASS[correct_response],
        "action_conflict": conflict,
        "first_response_s": min(issued)[0] if issued else None,
        "correct_response_s": min((t for t, r in issued
                                   if r == correct_response), default=None),
        "unsupported_confidence_s": round(unsupported_s, 3),
        "ambiguity_s": round(ambiguous_s, 3),
        "abstention_s": round(abstain_s, 3),
        "ambiguity_exceeds_min_state": ambiguous_s >= MIN_STATE_S,
        "abstention_exceeds_min_state": abstain_s >= MIN_STATE_S,
        "airborne_s": round(airborne_s, 3),
        "coverage_loss_frac": round(
            ((idle_s + abstain_s) / airborne_s) if airborne_s
            and correct_response != R_NONE else 0.0, 4),
    }


def occlusion_during_fault_s(segments, window) -> float:
    if not window:
        return 0.0
    lo, hi = float(window[0]), float(window[1])
    total = 0.0
    for seg in segments:
        if not seg["airborne"] or all(seg["gates_open"].values()):
            continue
        start, end = max(seg["t_start"], lo), min(seg["t_end"], hi)
        if end > start:
            total += end - start
    return round(total, 3)


def evaluate(document: dict) -> dict:
    per_scenario, policies = [], {}
    for scenario in document["scenarios"]:
        correct = scenario["correct_response"]
        row = {"seed": scenario["seed"], "family": scenario["gate_group"],
               "condition": scenario["condition"],
               "correct_response": correct,
               "fault_family": scenario["fault_family"],
               "meaningful_consequence_fields":
                   scenario.get("meaningful_consequence_fields", []),
               "policies": {}}
        for name, payload in sorted(scenario["policies"].items()):
            segments = payload["segments"]
            v = classify(segments, correct_response=correct)
            v["occlusion_during_fault_s"] = occlusion_during_fault_s(
                segments, scenario.get("fault_window_s"))
            out = payload["outcome"]
            v["time_to_safe_state_s"] = out["time_to_safe_state_s"]
            v["position_error_m"] = round(out["position_error_m"], 3)
            v["altitude_error_m"] = round(out["altitude_error_m"], 3)
            v["min_geofence_margin_m"] = round(out["min_geofence_margin_m"], 3)
            v["energy_margin_frac"] = round(out["energy_margin_frac"], 4)
            row["policies"][name] = v
            t = policies.setdefault(name, {
                "scenarios": 0, "by_outcome": {}, "action_conflicts": 0,
                "incorrect_actionable": 0, "correct_actionable": 0,
                "abstentions": 0, "missed_escalations": 0,
                "false_escalations": 0, "safe_fallbacks": 0,
                "unsupported_confidence_scenarios": 0,
                "total_ambiguity_s": 0.0, "total_abstention_s": 0.0,
                "safe_state_reached": 0, "coverage_loss_sum": 0.0})
            t["scenarios"] += 1
            t["by_outcome"][v["outcome"]] = t["by_outcome"].get(
                v["outcome"], 0) + 1
            t["action_conflicts"] += v["action_conflict"]
            t["incorrect_actionable"] += v["outcome"] == "INCORRECT_ACTIONABLE"
            t["correct_actionable"] += v["outcome"] == "CORRECT_ACTIONABLE"
            t["abstentions"] += v["outcome"] == "ABSTENTION"
            t["missed_escalations"] += v["outcome"] == "MISSED_ESCALATION"
            t["false_escalations"] += v["outcome"] == "FALSE_ESCALATION"
            t["safe_fallbacks"] += v["outcome"] == "SAFE_FALLBACK"
            t["unsupported_confidence_scenarios"] += \
                v["unsupported_confidence_s"] > 0.0
            t["total_ambiguity_s"] += v["ambiguity_s"]
            t["total_abstention_s"] += v["abstention_s"]
            t["safe_state_reached"] += v["time_to_safe_state_s"] is not None
            t["coverage_loss_sum"] += v["coverage_loss_frac"]
        per_scenario.append(row)
    for t in policies.values():
        n = t["scenarios"]
        t["mean_coverage_loss_frac"] = round(t["coverage_loss_sum"] / n, 4)
        t["total_ambiguity_s"] = round(t["total_ambiguity_s"], 3)
        t["total_abstention_s"] = round(t["total_abstention_s"], 3)
        del t["coverage_loss_sum"]
    return {"per_scenario": per_scenario, "by_policy": policies}


def paired(per_scenario, *, family, policy, left, right, field):
    by_seed = {}
    for row in per_scenario:
        if row["family"] != family or row["condition"] not in (left, right):
            continue
        by_seed.setdefault(row["seed"], {})[row["condition"]] = \
            row["policies"][policy]
    pairs = {s: v for s, v in by_seed.items() if left in v and right in v}
    b = c = both = neither = 0
    for v in pairs.values():
        lv, rv = bool(v[left][field]), bool(v[right][field])
        if lv and not rv:
            b += 1
        elif rv and not lv:
            c += 1
        elif lv:
            both += 1
        else:
            neither += 1
    p = mcnemar_exact(b, c)
    k_left, k_right = b + both, c + both
    n = len(pairs)
    return {"family": family, "policy": policy, "field": field,
            "left": left, "right": right, "pairs": n,
            "count_left": k_left, "count_right": k_right,
            "rate_left": round(k_left / n, 4) if n else None,
            "rate_right": round(k_right / n, 4) if n else None,
            "ci95_left": clopper_pearson(k_left, n),
            "ci95_right": clopper_pearson(k_right, n),
            "discordant_left_only": b, "discordant_right_only": c,
            "both": both, "neither": neither,
            # NOT rounded to six places. With 40 discordant pairs the exact
            # p is 1.8e-12, and `round(p, 6)` prints it as 0.0 -- a p-value
            # of exactly zero, which is impossible and which would be a
            # false statement in the write-up. Found after the locked run;
            # this changes how a number is DISPLAYED, not any criterion, and
            # the significance verdict is identical either way.
            "mcnemar_exact_two_sided_p": p, "alpha": ALPHA,
            "distinguishable_from_chance": bool(p < ALPHA)}


def cross_policy(per_scenario, *, family, condition, left, right, field):
    """P0 versus P2 on the SAME scenarios -- paired by seed by construction."""
    b = c = both = neither = 0
    n = 0
    for row in per_scenario:
        if row["family"] != family or row["condition"] != condition:
            continue
        n += 1
        lv = bool(row["policies"][left][field])
        rv = bool(row["policies"][right][field])
        if lv and not rv:
            b += 1
        elif rv and not lv:
            c += 1
        elif lv:
            both += 1
        else:
            neither += 1
    p = mcnemar_exact(b, c)
    return {"family": family, "condition": condition, "field": field,
            "left_policy": left, "right_policy": right, "pairs": n,
            "count_left": b + both, "count_right": c + both,
            "ci95_left": clopper_pearson(b + both, n),
            "ci95_right": clopper_pearson(c + both, n),
            "discordant_left_only": b, "discordant_right_only": c,
            "mcnemar_exact_two_sided_p": p, "alpha": ALPHA,
            "distinguishable_from_chance": bool(p < ALPHA)}


def build(document: dict) -> dict:
    ev = evaluate(document)
    ps = ev["per_scenario"]
    families = sorted({r["family"] for r in ps})
    tests = [paired(ps, family=f, policy="P0", left="EG", right="EA",
                    field="action_conflict") for f in families]
    tests += [cross_policy(ps, family=f, condition="EG", left="P0",
                           right="P2", field="action_conflict")
              for f in families]

    # A false refusal is defined on the RESPONSES, not on P0's outcome LABEL.
    # The first version keyed on `P0 outcome == CORRECT_ACTIONABLE` and
    # reported zero false refusals on development seeds, because in exactly
    # the scenarios where P2 fires, P0's label is UNSUPPORTED_CONFIDENCE --
    # P0 issues the RIGHT unit while the pair is not identifiable. Both facts
    # are true at once, and a definition that could not hold both was wrong.
    activations = [r for r in ps
                   if r["policies"]["P2"]["outcome"] == "ABSTENTION"
                   and r["policies"]["P0"]["outcome"] != "ABSTENTION"]
    false_refusals = [
        r for r in activations
        if r["correct_response"] in r["policies"]["P0"]["responses_issued"]
        and r["correct_response"] not in r["policies"]["P2"]["responses_issued"]]
    prevented = [r for r in activations
                 if r["policies"]["P0"]["outcome"] == "INCORRECT_ACTIONABLE"
                 and r["policies"]["P2"]["outcome"] != "INCORRECT_ACTIONABLE"]
    unsupported = [r for r in ps
                   if r["policies"]["P0"]["unsupported_confidence_s"] > 0.0]
    conflicts = [r for r in ps if r["policies"]["P0"]["action_conflict"]]

    n_p2 = sum(1 for r in ps if r["family"] == "imu_isolation"
               and r["condition"] == "EG")
    return {
        "schema": "csia.consequence.phase31_results/1",
        "phase": "3.1 -- actionability precondition",
        "evidence_level": "MODEL_BASED_ACTION_CONSEQUENCE",
        "executed_an_autopilot": False,
        "armed_a_vehicle": False,
        "touched_hardware": False,
        "pooled_with_phase3": False,
        "span_rule": "ticks / TICK_HZ (amendment section 7.1)",
        "partition": document.get("partition"),
        "per_scenario": ps,
        "by_policy": ev["by_policy"],
        "tests": tests,
        "actionability_precondition": {
            "p2_activations": len(activations),
            "p2_activation_scenarios": [
                {"seed": r["seed"], "family": r["family"],
                 "condition": r["condition"]} for r in activations],
            "false_refusals": len(false_refusals),
            "prevented_incorrect_actionable": len(prevented),
            "p2_eligible_scenarios": n_p2,
            "activation_rate_ci95": clopper_pearson(len(activations), n_p2)
            if n_p2 else None,
            "reachable": bool(activations),
            "unsupported_confident_attribution_scenarios": len(unsupported),
            "unsupported_confident_attribution_ci95":
                clopper_pearson(len(unsupported), len(ps)),
            "unsupported_but_attribution_was_correct": sum(
                1 for r in unsupported
                if r["correct_response"]
                in r["policies"]["P0"]["responses_issued"]),
        },
        "action_conflicts": {
            "count": len(conflicts),
            "scenarios": [{"seed": r["seed"], "family": r["family"],
                           "condition": r["condition"],
                           "correct_class": r["correct_response_class"]
                           if "correct_response_class" in r
                           else r["policies"]["P0"]["correct_response_class"],
                           "issued_classes":
                               r["policies"]["P0"]["response_classes_issued"]}
                          for r in conflicts],
            "rate_ci95": clopper_pearson(len(conflicts), len(ps)),
        },
        "what_this_is_not": (
            "Not a safety conclusion in either direction, not pooled with "
            "Phase 3, not hardware, not SITL, not flight, and not a claim "
            "that any vehicle behaved in any way."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("traces")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    with open(args.traces, encoding="utf-8") as fh:
        document = json.load(fh)
    result = build(document)
    text = json.dumps(result, indent=1, sort_keys=True) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    ap_ = result["actionability_precondition"]
    print(f"P2 activations {ap_['p2_activations']}/{ap_['p2_eligible_scenarios']}"
          f"  false_refusals {ap_['false_refusals']}"
          f"  prevented {ap_['prevented_incorrect_actionable']}")
    for t in result["tests"]:
        label = t.get("condition", f"{t.get('left')}v{t.get('right')}")
        print(f"  {t['family']:14s} {label:10s} "
              f"{t.get('left_policy','P0')}/{t.get('right_policy','')} "
              f"{t['count_left']}vs{t['count_right']} of {t['pairs']} "
              f"p={t['mcnemar_exact_two_sided_p']} sig={t['distinguishable_from_chance']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
