"""Phase 3.2 — independent evaluation and the confirmatory H2 analysis.

INDEPENDENCE
------------
Standard library only. It imports no CSIA module, no policy implementation,
no support classifier, no consequence model and not the campaign. A test
asserts that in a fresh interpreter. It is a second derivation by the same
author, not a second party, and that limit is not softened anywhere.

The response vocabulary and the materiality map are re-declared here rather
than imported, so a campaign emitting an unknown response FAILS instead of
being silently bucketed.

WHAT CARRIES THE VERDICT
------------------------
One grid point -- `structural` at gain 3.0 -- and one comparison, EG versus
EA, paired by seed. Everything else in the declared grid is run, reported in
full, and carries nothing. The grid is read in the order the campaign wrote
it; this module does not sort it, and Phase 3.1's measured non-monotonicity
in crossing time is why.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from typing import Dict, List

TICK_HZ = 25.0
ALPHA = 0.05
#: Declared in the preregistration before the locked run. A risk difference
#: below this is reported as observed and is NOT called a demonstrated
#: consequence, whatever its p-value.
MIN_RD = 0.50
#: More than this many dropped pairs at the confirmatory point and the test
#: is reported UNDERPOWERED_BY_EXCLUSIONS with no verdict drawn.
MAX_DROPPED_PAIRS = 4

R_NONE, R_ABSTAIN = "NONE", "ABSTAIN"
RESPONSE_CLASS = {
    "NONE": "NO_ACTION", "CAUTION_GENERIC": "CONSERVATIVE",
    "ABSTAIN": "CONSERVATIVE", "SELECT_IMU0": "ATTRIBUTION_IMU0",
    "SELECT_IMU1": "ATTRIBUTION_IMU1", "PREPARE_LANDING": "TERMINATE",
    "CONTROLLED_DESCENT": "TERMINATE",
}
ATTRIBUTING = frozenset({"SELECT_IMU0", "SELECT_IMU1"})
IDENTIFIABLE = "IDENTIFIABLE"


class TraceError(ValueError):
    pass


def span_s(segment: dict) -> float:
    return float(segment["ticks"]) / TICK_HZ


def clopper_pearson(k: int, n: int, alpha: float = ALPHA) -> List[float]:
    if n == 0:
        return [0.0, 1.0]

    def at_least(p, m):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                   for i in range(m, n + 1))

    def at_most(p, m):
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

    low = 0.0 if k == 0 else bisect(lambda p: at_least(p, k), alpha / 2.0)
    high = 1.0 if k == n else bisect(lambda p: -at_most(p, k), -(alpha / 2.0))
    return [round(low, 6), round(high, 6)]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail)


def paired_risk_difference(b: int, c: int, n: int) -> dict:
    """RD and its EXACT CONDITIONAL interval.

    Conditional on the number of discordant pairs d = b + c: an exact
    Clopper-Pearson interval on p = b/d, mapped through
    RD = (2p - 1) * d / n. The conditioning is stated in the output and
    wherever the interval is quoted -- it is not a marginal interval and is
    not presented as one.

    The odds ratio b/c is not finite when c = 0. In that case no point
    estimate is emitted; only the risk difference and its interval are.
    """
    d = b + c
    rd = (b - c) / n if n else 0.0
    if d == 0:
        return {"risk_difference": 0.0, "discordant_pairs": 0,
                "ci95_conditional": [0.0, 0.0],
                "ci95_is_conditional_on_discordant_pairs": True,
                "odds_ratio": None,
                "odds_ratio_note": "no discordant pairs; undefined"}
    lo, hi = clopper_pearson(b, d)
    return {
        "risk_difference": round(rd, 6),
        "discordant_pairs": d,
        "ci95_conditional": [round((2 * lo - 1) * d / n, 6),
                             round((2 * hi - 1) * d / n, 6)],
        "ci95_is_conditional_on_discordant_pairs": True,
        "odds_ratio": None if c == 0 else round(b / c, 6),
        "odds_ratio_note": ("not finite: c = 0, so no point estimate is "
                            "reported" if c == 0 else "b / c"),
    }


def classify(segments: List[dict], *, correct_response: str) -> dict:
    if correct_response not in RESPONSE_CLASS:
        raise TraceError(f"unknown correct response {correct_response!r}")
    issued, unsupported_s, ambiguous_s, abstain_s = [], 0.0, 0.0, 0.0
    airborne_s = idle_s = 0.0
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
    want = RESPONSE_CLASS[correct_response]
    conflict = (want not in classes) if kinds else (correct_response != R_NONE)
    actionable = {r for r in kinds if RESPONSE_CLASS[r] != "NO_ACTION"}

    if unsupported_s > 0.0:
        outcome = "UNSUPPORTED_CONFIDENCE"
    elif correct_response == R_NONE:
        outcome = ("FALSE_ESCALATION" if kinds - {R_ABSTAIN}
                   else ("ABSTENTION" if kinds else "CORRECT_ACTIONABLE"))
    elif correct_response in kinds:
        outcome = "CORRECT_ACTIONABLE"
    elif any(r in ATTRIBUTING and RESPONSE_CLASS[r] != want for r in kinds):
        outcome = "INCORRECT_ACTIONABLE"
    elif R_ABSTAIN in kinds:
        outcome = "ABSTENTION"
    elif kinds:
        outcome = "SAFE_FALLBACK"
    else:
        outcome = "MISSED_ESCALATION"

    return {
        "outcome": outcome, "responses_issued": sorted(kinds),
        "response_classes_issued": sorted(classes),
        "correct_response_class": want,
        "action_conflict": conflict,
        "correct_escalation": bool(correct_response != R_NONE
                                   and correct_response in kinds),
        "false_escalation": bool(correct_response == R_NONE
                                 and actionable),
        "first_response_s": min(issued)[0] if issued else None,
        "unsupported_confidence_s": round(unsupported_s, 3),
        "ambiguity_s": round(ambiguous_s, 3),
        "abstention_s": round(abstain_s, 3),
        "airborne_s": round(airborne_s, 3),
        "coverage_loss_frac": round(
            ((idle_s + abstain_s) / airborne_s) if airborne_s
            and correct_response != R_NONE else 0.0, 4),
    }


def evaluate(document: dict) -> List[dict]:
    rows = []
    for s in document["scenarios"]:
        row = {"seed": s["seed"], "family": s["gate_group"],
               "family_role": s["family_role"], "condition": s["condition"],
               "magnitude": s["magnitude"],
               "is_confirmatory": s.get("is_confirmatory", False),
               "correct_response": s["correct_response"],
               "fault_family": s["fault_family"],
               "fault_window_duration_s": s.get("fault_window_duration_s"),
               "time_to_level_s": s.get("time_to_level_s", {}),
               "meaningful_consequence_fields":
                   s.get("meaningful_consequence_fields", []),
               "policies": {}}
        for name, payload in sorted(s["policies"].items()):
            v = classify(payload["segments"],
                         correct_response=s["correct_response"])
            o = payload["outcome"]
            v["time_to_safe_state_s"] = o["time_to_safe_state_s"]
            v["position_error_m"] = round(o["position_error_m"], 3)
            v["altitude_error_m"] = round(o["altitude_error_m"], 3)
            v["min_geofence_margin_m"] = round(o["min_geofence_margin_m"], 3)
            v["energy_margin_frac"] = round(o["energy_margin_frac"], 4)
            row["policies"][name] = v
        rows.append(row)
    return rows


def paired_test(rows, invalid, *, family, magnitude, policy="P0",
                left="EG", right="EA", field="action_conflict") -> dict:
    """Seed-paired comparison with exclusions counted and explained."""
    by_seed: Dict[int, dict] = {}
    for r in rows:
        if r["family"] != family or r["magnitude"] != magnitude:
            continue
        if r["condition"] in (left, right):
            by_seed.setdefault(r["seed"], {})[r["condition"]] = \
                r["policies"][policy]
    dropped = []
    for bad in invalid:
        if bad.get("gate_group") == family and bad.get("magnitude") == magnitude:
            dropped.append({"seed": bad.get("seed"),
                            "condition": bad.get("condition"),
                            "reason": bad.get("reason")})
    pairs = {s: v for s, v in by_seed.items() if left in v and right in v}
    incomplete = sorted(set(by_seed) - set(pairs))
    for seed in incomplete:
        dropped.append({"seed": seed, "condition": "incomplete pair",
                        "reason": "one arm of the pair is missing"})

    b = c = both = neither = 0
    per_seed = []
    for seed, v in sorted(pairs.items()):
        lv, rv = bool(v[left][field]), bool(v[right][field])
        per_seed.append({"seed": seed, left: lv, right: rv})
        if lv and not rv:
            b += 1
        elif rv and not lv:
            c += 1
        elif lv:
            both += 1
        else:
            neither += 1
    n = len(pairs)
    p = mcnemar_exact(b, c)
    rd = paired_risk_difference(b, c, n) if n else {}
    k_left, k_right = b + both, c + both
    out = {
        "family": family, "magnitude": magnitude, "policy": policy,
        "left": left, "right": right, "field": field,
        "pairs_analysed": n, "pairs_dropped": len(dropped),
        "dropped_detail": dropped,
        "count_left": k_left, "count_right": k_right,
        "rate_left": round(k_left / n, 4) if n else None,
        "rate_right": round(k_right / n, 4) if n else None,
        "ci95_left": clopper_pearson(k_left, n),
        "ci95_right": clopper_pearson(k_right, n),
        "discordant_left_only": b, "discordant_right_only": c,
        "both": both, "neither": neither,
        "per_seed": per_seed,
        "mcnemar_exact_two_sided_p": p, "alpha": ALPHA,
        "significant": bool(p < ALPHA),
        "min_rd_threshold": MIN_RD,
    }
    out.update(rd)
    out["exceeds_effect_size_threshold"] = bool(
        rd.get("risk_difference", 0.0) >= MIN_RD)
    out["underpowered_by_exclusions"] = bool(len(dropped) > MAX_DROPPED_PAIRS)
    return out


def build(document: dict) -> dict:
    rows = evaluate(document)
    invalid = document.get("invalid_runs", [])
    grids = document["grids"]
    confirm = document["confirmatory_point"]

    tests = []
    for family in grids:                       # declaration order
        for magnitude in grids[family]:        # declaration order, no sort
            tests.append(paired_test(rows, invalid, family=family,
                                     magnitude=magnitude))

    primary = next(t for t in tests
                   if t["family"] == "structural"
                   and t["magnitude"] == confirm["structural"])

    if primary["underpowered_by_exclusions"]:
        verdict, why = "UNDERPOWERED_BY_EXCLUSIONS", (
            f"{primary['pairs_dropped']} pairs dropped at the confirmatory "
            f"point, above the preregistered maximum of {MAX_DROPPED_PAIRS}. "
            "No H2 verdict is drawn.")
    else:
        nominal = [r for r in rows
                   if r["condition"] == "N" and r["family"] == "structural"]
        false_esc = sum(1 for r in nominal if r["policies"]["P0"]["false_escalation"])
        ok = (primary["significant"]
              and primary["exceeds_effect_size_threshold"]
              and primary["risk_difference"] > 0
              and false_esc == 0)
        verdict = "SUPPORTED" if ok else "NOT SUPPORTED"
        why = (
            "At the confirmatory grid point the exact McNemar p is below "
            "alpha, the paired risk difference exceeds the preregistered "
            f"MIN_RD of {MIN_RD} in the direction of more conflicts under "
            "EG, and the matched nominal control shows no false escalation."
            if ok else
            "One or more of the three preregistered conditions failed: "
            f"p<alpha {primary['significant']}, RD>={MIN_RD} "
            f"{primary['exceeds_effect_size_threshold']}, "
            f"false escalations in N {false_esc}.")

    # Exploratory only. FL-029 invalidates P2's support mapping.
    p2_rows = [r for r in rows if "P2" in r["policies"]]
    p2_table = {}
    for r in p2_rows:
        key = f"{r['family']}|{r['condition']}|{r['magnitude']}"
        t = p2_table.setdefault(key, {"n": 0, "p0_conflicts": 0,
                                      "p2_conflicts": 0, "p2_abstentions": 0,
                                      "p0_correct_escalations": 0,
                                      "p2_correct_escalations": 0})
        t["n"] += 1
        t["p0_conflicts"] += r["policies"]["P0"]["action_conflict"]
        t["p2_conflicts"] += r["policies"]["P2"]["action_conflict"]
        t["p2_abstentions"] += r["policies"]["P2"]["outcome"] == "ABSTENTION"
        t["p0_correct_escalations"] += r["policies"]["P0"]["correct_escalation"]
        t["p2_correct_escalations"] += r["policies"]["P2"]["correct_escalation"]

    summary = {}
    for r in rows:
        key = f"{r['family']}|{r['condition']}|{r['magnitude']}"
        s = summary.setdefault(key, {
            "n": 0, "role": r["family_role"], "conflicts": 0,
            "unsupported": 0, "correct_escalations": 0,
            "false_escalations": 0, "outcomes": {},
            "sum_time_to_safe": 0.0, "n_safe": 0,
            "sum_position_error_m": 0.0, "sum_altitude_error_m": 0.0,
            "sum_geofence_margin_m": 0.0, "sum_energy_margin": 0.0,
            "sum_ambiguity_s": 0.0, "sum_fault_window_s": 0.0,
            "sum_t_caution": 0.0, "n_caution": 0,
            "sum_t_critical": 0.0, "n_critical": 0,
            "sum_t_emergency": 0.0, "n_emergency": 0})
        v = r["policies"]["P0"]
        s["n"] += 1
        s["conflicts"] += v["action_conflict"]
        s["unsupported"] += v["unsupported_confidence_s"] > 0.0
        s["correct_escalations"] += v["correct_escalation"]
        s["false_escalations"] += v["false_escalation"]
        s["outcomes"][v["outcome"]] = s["outcomes"].get(v["outcome"], 0) + 1
        if v["time_to_safe_state_s"] is not None:
            s["sum_time_to_safe"] += v["time_to_safe_state_s"]
            s["n_safe"] += 1
        s["sum_position_error_m"] += v["position_error_m"]
        s["sum_altitude_error_m"] += v["altitude_error_m"]
        s["sum_geofence_margin_m"] += v["min_geofence_margin_m"]
        s["sum_energy_margin"] += v["energy_margin_frac"]
        s["sum_ambiguity_s"] += v["ambiguity_s"]
        s["sum_fault_window_s"] += r["fault_window_duration_s"] or 0.0
        for lvl, field in ((1, "caution"), (2, "critical"), (3, "emergency")):
            t = r["time_to_level_s"].get(str(lvl))
            if t is not None:
                s[f"sum_t_{field}"] += t
                s[f"n_{field}"] += 1
    for s in summary.values():
        n = s["n"]
        s["conflict_rate"] = round(s["conflicts"] / n, 4)
        s["conflict_rate_ci95"] = clopper_pearson(s["conflicts"], n)
        s["mean_time_to_safe_state_s"] = (
            round(s["sum_time_to_safe"] / s["n_safe"], 3) if s["n_safe"] else None)
        for key, field in (("mean_position_error_m", "sum_position_error_m"),
                           ("mean_altitude_error_m", "sum_altitude_error_m"),
                           ("mean_geofence_margin_m", "sum_geofence_margin_m"),
                           ("mean_energy_margin_frac", "sum_energy_margin"),
                           ("mean_ambiguity_s", "sum_ambiguity_s"),
                           ("mean_fault_window_s", "sum_fault_window_s")):
            s[key] = round(s[field] / n, 4)
        for field in ("caution", "critical", "emergency"):
            s[f"mean_time_to_{field}_s"] = (
                round(s[f"sum_t_{field}"] / s[f"n_{field}"], 3)
                if s[f"n_{field}"] else None)
            s[f"reached_{field}"] = s[f"n_{field}"]

    return {
        "schema": "csia.consequence.phase32_results/1",
        "phase": "3.2 -- direct preregistered consequence test",
        "evidence_level": "MODEL_BASED_ACTION_CONSEQUENCE",
        "executed_an_autopilot": False, "armed_a_vehicle": False,
        "touched_hardware": False,
        "pooled_with_phase3": False, "pooled_with_phase31": False,
        "partition": document.get("partition"),
        "invalid_run_count": document.get("invalid_run_count", 0),
        "invalid_runs": invalid,
        "grid_order": document.get("grid_order"),
        "confirmatory_point": confirm,
        "h2_phase32": {"verdict": verdict, "why": why,
                       "confirmatory_test": primary},
        "tests": tests,
        "summary": summary,
        "P2_CURRENT_IMPLEMENTATION_EXPLORATORY": {
            "why_excluded_from_the_primary_test": (
                "FL-029: SOURCE_INDICATORS omits the per-IMU Doppler edges, "
                "so P2's NON_IDENTIFIABLE verdicts do not mean what the "
                "policy takes them to mean. Nothing here supports a claim "
                "that P2 is safe or unsafe in general."),
            "table": p2_table},
        "per_scenario": rows,
        "what_this_is_not": (
            "Not hardware, not SITL, not flight, not autopilot execution, "
            "not a general safety claim about P2, and not pooled with any "
            "earlier campaign."),
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
    h2 = result["h2_phase32"]
    t = h2["confirmatory_test"]
    print(f"H2 PHASE-3.2: {h2['verdict']}")
    print(f"  confirmatory {t['family']} gain={t['magnitude']}: "
          f"{t['count_left']}/{t['pairs_analysed']} vs "
          f"{t['count_right']}/{t['pairs_analysed']}  "
          f"p={t['mcnemar_exact_two_sided_p']:.6g}  RD={t['risk_difference']} "
          f"CI{t['ci95_conditional']}  dropped={t['pairs_dropped']}")
    for x in result["tests"]:
        print(f"  {x['family']:14s} m={x['magnitude']:<5} "
              f"{x['count_left']:2d} vs {x['count_right']:2d} of "
              f"{x['pairs_analysed']:2d}  p={x['mcnemar_exact_two_sided_p']:.4g} "
              f"RD={x.get('risk_difference')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
