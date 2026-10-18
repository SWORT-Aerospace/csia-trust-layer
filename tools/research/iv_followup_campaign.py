"""The follow-up campaign that breaks the paired-design cancellation.

Implements ``PREREGISTRATION_AMENDMENT_4.md`` and adds nothing to it. One
block -- the main block -- run three times over the new ``nominal_source``
factor, on the eleven deployable arms, over a partition drawn in its own
domain.

    python tools/research/iv_followup_campaign.py --partition development
    python tools/research/iv_followup_campaign.py --partition validation
    python tools/research/iv_followup_campaign.py --partition final \
        --open-the-seal

No ceiling runs here. The amendment says why, and the reason is a cost, not a
result: P7b's objective is itself computed through the arena's nominal window,
so honouring ``nominal_source`` inside it means threading the factor through
the ceiling machinery too. Regret is therefore absent from this artifact
rather than quietly carried over from the sealed one.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import statistics
import sys
import time
from typing import Dict, List, Sequence, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_independent_validation import evaluator as ev            # noqa: E402
from csia_independent_validation import followup_partitions as fp  # noqa: E402
from csia_independent_validation import partitions as pt           # noqa: E402
from csia_independent_validation import strategies as st           # noqa: E402
from csia_independent_validation.runner import (Campaign,          # noqa: E402
                                                Cell, DRIFT_STATES,
                                                MAGNITUDES,
                                                NOMINAL_SOURCES, PLANTS,
                                                REFERENCE_ACTION, frontier,
                                                resolution_area, slice_rows)

RESULTS = ROOT / "research/active_evidence/independent_validation/results"

#: Deployable arms and selectors. The three ceilings are omitted; see above.
FOLLOWUP_ARMS: Tuple[str, ...] = tuple(st.STRATEGIES) + tuple(st.SELECTORS)

#: Preregistered thresholds. Amendment 4 section 3, copied here so a reader of
#: the code sees the same numbers as a reader of the amendment.
H8_SPREAD = 0.05        # A_s spread across arms that counts as "not constant"
H9_FACTOR = 2.0         # plant-to-plant ratio in median |e_dR|
H9_CONTROL_TOLERANCE = 0.05     # paired_crn plants must agree to within this
H10_RHO = 0.7           # Spearman floor for order preservation


def _progress(message: str) -> None:
    print(message, flush=True)


def main_block(campaign: Campaign, seeds: Sequence[int]) -> List[Dict]:
    rows: List[Dict] = []
    for source in NOMINAL_SOURCES:
        for plant in PLANTS:
            for drift in DRIFT_STATES:
                _progress(f"  {source}: {plant} / {drift} drift "
                          f"({len(rows)} rows so far)")
                for seed in seeds:
                    for magnitude in MAGNITUDES:
                        cell = Cell(plant=plant, drift_state=drift,
                                    magnitude=magnitude, seed=seed,
                                    nominal_source=source)
                        for arm in FOLLOWUP_ARMS:
                            rows.append({**campaign.row(arm, cell),
                                         "block": "main"})
    return rows


# --- reductions -----------------------------------------------------------

def _median_abs_change(rows: Sequence[Dict]):
    values = [abs(r["e_delta_r"]) for r in rows if r["e_delta_r"] is not None]
    return statistics.median(values) if values else None


def _ranks(values: Sequence[float]) -> List[float]:
    """Average ranks, so ties do not invent an ordering that is not there."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = mean_rank
        i = j + 1
    return out


def spearman(a: Sequence[float], b: Sequence[float]):
    """Tie-aware Spearman. Returns ``None`` when it is undefined.

    A constant vector has no ordering to preserve, so the correlation is not
    zero and not one -- it does not exist. Returning ``None`` says that;
    returning a number would not.
    """
    if len(a) != len(b) or len(a) < 3:
        return None
    ra, rb = _ranks(a), _ranks(b)
    if len(set(ra)) == 1 or len(set(rb)) == 1:
        return None
    mean_a = statistics.fmean(ra)
    mean_b = statistics.fmean(rb)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(ra, rb))
    var_a = math.sqrt(sum((x - mean_a) ** 2 for x in ra))
    var_b = math.sqrt(sum((y - mean_b) ** 2 for y in rb))
    if var_a == 0.0 or var_b == 0.0:
        return None
    return cov / (var_a * var_b)


def per_arm_area(rows: Sequence[Dict], source: str, metric: str
                 ) -> Dict[str, float]:
    subset = [r for r in rows if r["nominal_source"] == source]
    return {arm: resolution_area(slice_rows(subset, arm=arm), metric=metric)
            for arm in FOLLOWUP_ARMS}


def excited_arms(rows: Sequence[Dict]) -> List[str]:
    """Arms that actually inject a probe, measured rather than named.

    ``P0_passive`` emits nothing, so it never resolves under any baseline and
    its ``A_s`` is zero at every level. Writing ``P0_passive`` into this
    function would be a hand-pick that happens to be right today; the property
    that matters is zero injected energy, and the rows carry it.
    """
    energy: Dict[str, List[float]] = collections.defaultdict(list)
    for row in rows:
        energy[row["arm"]].append(row["energy_as"])
    return [arm for arm in FOLLOWUP_ARMS
            if arm in energy and statistics.fmean(energy[arm]) > 0.0]


def _spread(areas: Dict[str, float]) -> float:
    finite = [v for v in areas.values() if not math.isnan(v)]
    return (max(finite) - min(finite)) if finite else float("nan")


def assess_h8(rows: Sequence[Dict]) -> Dict:
    """Saturation is a design artifact.

    Two statistics, and the first one does not work.

    H8 as preregistered in Amendment 4 section 3 asks whether any two
    deployable arms differ in ``A_s`` by more than 0.05. The control passes it:
    ``P0_passive`` scores zero at every level because it emits no probe, so the
    spread is ~1.0 under ``paired_crn`` too. A check the control passes
    measures nothing -- ``VACUOUS_IN_ENVELOPE`` in this phase's own taxonomy.
    It is reported anyway, next to the control's number, because deleting a
    preregistered statistic because it came out useless is how a phase stops
    being falsifiable.

    H8-prime, Amendment 5, restricts to the arms that inject a probe and makes
    the control part of the claim: flat under ``paired_crn``, not flat under
    the two broken levels. That one can fail.
    """
    excited = excited_arms(rows)
    literal: Dict[str, Dict] = {}
    restricted: Dict[str, Dict] = {}
    for source in NOMINAL_SOURCES:
        areas = per_arm_area(rows, source, "change")
        spread = _spread(areas)
        literal[source] = {
            "A_s_by_arm": areas,
            "spread": spread,
            "exceeds_threshold": (not math.isnan(spread)
                                  and spread > H8_SPREAD),
        }
        cut = {arm: areas[arm] for arm in excited}
        cut_spread = _spread(cut)
        restricted[source] = {
            "A_s_by_excited_arm": cut,
            "spread": cut_spread,
            "flat": not math.isnan(cut_spread) and cut_spread <= H8_SPREAD,
        }

    broken = [s for s in ("independent_seed", "independent_window")
              if literal[s]["exceeds_threshold"]]
    # The literal statistic is vacuous exactly when the control also fires.
    vacuous = literal["paired_crn"]["exceeds_threshold"]

    control_flat = restricted["paired_crn"]["flat"]
    broken_prime = [s for s in ("independent_seed", "independent_window")
                    if not restricted[s]["flat"]]
    if not control_flat:
        prime_verdict = "REJECTED_CONTROL_IS_NOT_FLAT"
    elif len(broken_prime) == 2:
        prime_verdict = "SUPPORTED"
    elif broken_prime:
        prime_verdict = "PARTIALLY_SUPPORTED"
    else:
        prime_verdict = "REJECTED"

    return {
        "threshold": H8_SPREAD,
        "statement": ("under independent_seed and independent_window, A_s on "
                      "the change metric is no longer constant across arms: "
                      "at least one deployable arm differs from another by "
                      "more than 0.05"),
        "by_source": literal,
        "levels_that_broke_saturation": broken,
        "verdict": ("SUPPORTED" if len(broken) == 2 else
                    "PARTIALLY_SUPPORTED" if broken else "REJECTED"),
        "vacuity": {
            "verdict": "VACUOUS_IN_ENVELOPE" if vacuous else "DISCRIMINATING",
            "control_also_exceeds_the_threshold": vacuous,
            "why": ("P0_passive injects no energy, so it resolves nowhere and "
                    "scores A_s = 0 at every level including the control. The "
                    "spread between it and any excited arm is ~1.0 by "
                    "construction, so this statistic cannot come out any "
                    "other way and its verdict above carries no information."
                    if vacuous else
                    "the control does not exceed the threshold, so the "
                    "statistic separates the levels"),
            "superseded_by": "H8_prime, PREREGISTRATION_AMENDMENT_5.md",
        },
        "falsifier": ("the change metric stays saturated, in which case the "
                      "saturation is not a design artifact"),
        "H8_prime": {
            "statement": ("restricted to arms with non-zero mean injected "
                          "energy, A_s on the change metric is constant "
                          "across arms under paired_crn (spread <= 0.05) and "
                          "is not constant under independent_seed and "
                          "independent_window (spread > 0.05)"),
            "preregistration": "PREREGISTRATION_AMENDMENT_5.md",
            "excited_arms": excited,
            "excluded_arms": [a for a in FOLLOWUP_ARMS if a not in excited],
            "excluded_because": "mean energy_as == 0 over this campaign's rows",
            "by_source": restricted,
            "control_is_flat": control_flat,
            "levels_that_broke_saturation": broken_prime,
            "verdict": prime_verdict,
            "falsifier": ("the paired_crn control is not flat over the "
                          "excited arms, in which case phase one's diagnosis "
                          "of its own saturation was incomplete; or either "
                          "broken level stays flat, in which case breaking "
                          "the pairing did not break the saturation"),
        },
    }


def assess_h9(rows: Sequence[Dict]) -> Dict:
    """The change metric recovers plant structure once the pairing is gone."""
    by_source: Dict[str, Dict] = {}
    for source in NOMINAL_SOURCES:
        subset = [r for r in rows if r["nominal_source"] == source]
        medians = {plant: _median_abs_change(slice_rows(subset, plant=plant))
                   for plant in PLANTS}
        finite = [v for v in medians.values() if v]
        ratio = (max(finite) / min(finite)) if len(finite) == len(PLANTS) \
            else None
        by_source[source] = {"median_abs_e_delta_r": medians, "ratio": ratio}

    control = by_source["paired_crn"]["ratio"]
    control_holds = control is not None and \
        abs(control - 1.0) <= H9_CONTROL_TOLERANCE
    window = by_source["independent_window"]["ratio"]
    recovered = window is not None and window >= H9_FACTOR
    return {
        "factor_threshold": H9_FACTOR,
        "control_tolerance": H9_CONTROL_TOLERANCE,
        "statement": ("under independent_window, median |e_dR| differs across "
                      "Q0, Q1 and Q2 by at least a factor of two, where under "
                      "paired_crn all three are equal to within 5%"),
        "by_source": by_source,
        "control_precondition_holds": control_holds,
        "verdict": ("SUPPORTED" if control_holds and recovered else
                    "REJECTED" if control_holds else
                    "PRECONDITION_FAILED"),
        "falsifier": ("breaking the cancellation does not recover plant "
                      "structure"),
    }


def assess_h10(rows: Sequence[Dict]) -> Dict:
    """Order preservation between the two readings of the same campaign."""
    change_window = per_arm_area(rows, "independent_window", "change")
    point_paired = per_arm_area(rows, "paired_crn", "point")
    arms = [a for a in FOLLOWUP_ARMS
            if not math.isnan(change_window[a])
            and not math.isnan(point_paired[a])]
    rho = spearman([change_window[a] for a in arms],
                   [point_paired[a] for a in arms])
    return {
        "rho_threshold": H10_RHO,
        "statement": ("the ranking of deployable arms by A_s under "
                      "independent_window on the change metric agrees with "
                      "the ranking under paired_crn on the point metric at "
                      "Spearman rho >= 0.7"),
        "arms": arms,
        "A_s_change_independent_window": {a: change_window[a] for a in arms},
        "A_s_point_paired_crn": {a: point_paired[a] for a in arms},
        "spearman_rho": rho,
        "verdict": ("UNDEFINED_ONE_SIDE_IS_CONSTANT" if rho is None else
                    "SUPPORTED" if rho >= H10_RHO else "REJECTED"),
        "if_rejected": ("the point-metric conclusions in RESULTS.md are "
                        "conditional on the metric and must be reported as "
                        "such"),
        "falsifier": "the orderings disagree",
    }


def point_metric_invariance(rows: Sequence[Dict]) -> Dict:
    """``nominal_source`` must move the change metric and nothing else.

    ``AE_R`` scores the fault window alone and never reads the baseline, so
    the three levels must agree on it exactly for every matched row. If they
    do not, the factor is contaminating something it was not supposed to
    touch, and every H8/H9/H10 reading below is worthless.
    """
    keyed: Dict[Tuple, Dict[str, float]] = collections.defaultdict(dict)
    for row in rows:
        if row["ae_r"] is None:
            continue
        key = (row["arm"], row["plant"], row["drift_state"], row["magnitude"],
               row["seed"])
        keyed[key][row["nominal_source"]] = row["ae_r"]
    worst = 0.0
    compared = 0
    offenders: List[Dict] = []
    for key, values in keyed.items():
        if len(values) < 2:
            continue
        compared += 1
        spread = max(values.values()) - min(values.values())
        if spread > worst:
            worst = spread
        if spread != 0.0 and len(offenders) < 5:
            offenders.append({"cell": list(key), "ae_r": values})
    return {
        "matched_groups_compared": compared,
        "max_ae_r_spread_across_levels": worst,
        "identical_everywhere": worst == 0.0,
        "first_offenders": offenders,
    }


def resolution_without_excitation(rows: Sequence[Dict]) -> Dict:
    """Rows the outcome metric calls resolved where nothing was injected.

    `P0_passive` emits no probe, so its resistance estimate is a fit to noise.
    Under `paired_crn` both windows are the same noise draw, the difference is
    exactly zero and `|e_dR| = d` never clears `tau_R = 0.5d`. Under
    `independent_seed` the two draws differ, the difference is a random
    quantity, and it lands inside the tolerance often enough to score.

    That is the change metric reporting a resolution with no signal behind it.
    It is worth a number because the certificate is what catches it: every one
    of these rows is `INSUFFICIENT_EXCITATION`, so none becomes a false
    certificate. A reader is entitled to see both halves of that.
    """
    out: Dict[str, Dict] = {}
    for source in NOMINAL_SOURCES:
        cut = [r for r in rows if r["nominal_source"] == source
               and r["energy_as"] == 0.0]
        lucky = [r for r in cut if r["resolved"]]
        certified = [r for r in lucky if r["state"] == "CERTIFIED_IN_MODEL"]
        out[source] = {
            "zero_energy_rows": len(cut),
            "resolved_anyway": len(lucky),
            "rate": (len(lucky) / len(cut)) if cut else None,
            "of_those_certified": len(certified),
            "states": dict(collections.Counter(r["state"] for r in lucky)),
        }
    return {
        "by_source": out,
        "what_it_shows": (
            "the outcome metric can score a resolution where no probe was "
            "injected at all; the certificate refuses every one of them, "
            "which is why none of these rows is a false certificate"),
    }


def reduce_rows(rows: List[Dict]) -> Dict:
    per_source: Dict[str, Dict] = {}
    for source in NOMINAL_SOURCES:
        subset = [r for r in rows if r["nominal_source"] == source]
        stats: Dict[str, Dict] = {}
        for arm in FOLLOWUP_ARMS:
            for drift in DRIFT_STATES:
                cut = slice_rows(subset, arm=arm, drift_state=drift)
                if not cut:
                    continue
                margins = [r["m_r_out"] for r in cut
                           if r["m_r_out"] is not None]
                errors = [r["ae_r"] for r in cut if r["ae_r"] is not None]
                stats[f"{arm}/{drift}"] = {
                    "n": len(cut),
                    "A_s_change": resolution_area(cut, metric="change"),
                    "A_s_point": resolution_area(cut, metric="point"),
                    "frontier_change": frontier(cut, metric="change"),
                    "frontier_point": frontier(cut, metric="point"),
                    "median_m_r_out": (statistics.median(margins)
                                       if margins else None),
                    "median_ae_r": (statistics.median(errors)
                                    if errors else None),
                    "median_abs_e_delta_r": _median_abs_change(cut),
                    "abstentions": sum(1 for r in cut
                                       if r["abstention"] is not None),
                }
        resolved = sum(1 for r in subset if r["resolved"])
        false_change = [
            {k: r[k] for k in ("arm", "plant", "drift_state", "magnitude",
                               "seed", "action", "baseline_action",
                               "baseline_seed", "m_r_out", "e_delta_r")}
            for r in subset
            if r["state"] == "CERTIFIED_IN_MODEL" and not r["resolved"]]
        false_point = [
            {k: r[k] for k in ("arm", "plant", "drift_state", "magnitude",
                               "seed", "action", "ae_r")}
            for r in subset
            if r["state"] == "CERTIFIED_IN_MODEL" and r["ae_r"] is not None
            and r["ae_r"] >= ev.TAU_R_RELATIVE * r["magnitude"]]
        per_source[source] = {
            "n": len(subset),
            "resolved_fraction_change": (resolved / len(subset)
                                         if subset else None),
            "median_abs_e_delta_r": _median_abs_change(subset),
            "by_arm_and_drift": stats,
            "false_certificates_change_metric": false_change,
            "false_certificates_point_metric": false_point,
            "state_counts": dict(collections.Counter(
                r["state"] for r in subset if r["state"] is not None)),
        }

    return {
        "resolve_predicates": {
            "change": "M_R_out > 0 with tau_R = 0.5 * |target change|",
            "point": "AE_R < 0.5 * |target change|"},
        "point_metric_invariance": point_metric_invariance(rows),
        "resolution_without_excitation": resolution_without_excitation(rows),
        "by_nominal_source": per_source,
        "H8_saturation_is_a_design_artifact": assess_h8(rows),
        "H9_change_metric_recovers_plant_structure": assess_h9(rows),
        "H10_ordering_is_preserved": assess_h10(rows),
        "regret": ("not computed. Amendment 4 section 4: the ceilings are "
                   "omitted from this campaign, so no regret figure exists "
                   "here and none may be borrowed from the sealed one."),
    }


def rereduce(partition: str) -> int:
    """Recompute the reduction over rows that are already on disk.

    The rows are the measurement; the reduction is arithmetic over them. When
    the arithmetic is corrected -- as Amendment 5 corrects H8 -- re-running ten
    thousand plant simulations to get the identical rows back would waste an
    hour and prove nothing. The artifact records which reductions it has been
    through so the two are never confused.
    """
    path = RESULTS / f"FOLLOWUP_{partition.upper()}.json"
    document = json.loads(path.read_text())
    rows = document["rows"]
    history = document.setdefault("reduction_history", [])
    history.append({
        "replaced_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                         time.gmtime()),
        "reason": ("H8 restated per PREREGISTRATION_AMENDMENT_5.md; the rows "
                   "are untouched and were not re-simulated"),
    })
    document["reduction"] = reduce_rows(rows)
    path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    _report(document, path)
    return 0


def _report(document: Dict, path: pathlib.Path) -> None:
    reduction = document["reduction"]
    print(f"wrote {path.relative_to(ROOT)}")
    print(f"{document['n_rows']} rows, {document['plant_simulations']} plant "
          f"runs, {document['elapsed_s']:.1f} s")
    invariance = reduction["point_metric_invariance"]
    print(f"point metric identical across levels: "
          f"{invariance['identical_everywhere']} "
          f"(worst spread {invariance['max_ae_r_spread_across_levels']:.3e} "
          f"over {invariance['matched_groups_compared']} groups)")
    for source in NOMINAL_SOURCES:
        block = reduction["by_nominal_source"][source]
        print(f"  {source:20s} median |e_dR| "
              f"{block['median_abs_e_delta_r']:.4e}  "
              f"resolved {block['resolved_fraction_change']:.4f}  "
              f"false certs (change) "
              f"{len(block['false_certificates_change_metric'])}")
    lucky = reduction["resolution_without_excitation"]["by_source"]
    print("  resolved with zero injected energy (certificate refuses all):")
    for source in NOMINAL_SOURCES:
        block = lucky[source]
        print(f"        {source:20s} {block['resolved_anyway']:3d}"
              f"/{block['zero_energy_rows']:<4d} certified "
              f"{block['of_those_certified']}")
    h8 = reduction["H8_saturation_is_a_design_artifact"]
    print(f"  H8  as preregistered: {h8['verdict']}  "
          f"[{h8['vacuity']['verdict']}]")
    print(f"  H8' excited arms only: {h8['H8_prime']['verdict']}  "
          f"(control flat: {h8['H8_prime']['control_is_flat']})")
    for source in NOMINAL_SOURCES:
        print(f"        {source:20s} spread "
              f"{h8['H8_prime']['by_source'][source]['spread']:.4f}")
    for name in ("H9_change_metric_recovers_plant_structure",
                 "H10_ordering_is_preserved"):
        print(f"  {name}: {reduction[name]['verdict']}")


def run(partition: str, *, open_the_seal: bool) -> int:
    seeds = fp.seeds(partition,
                     i_am_opening_the_sealed_partition=open_the_seal)
    campaign = Campaign()
    started = time.time()

    _progress(f"follow-up partition {partition}: {len(seeds)} seeds, "
              f"{len(FOLLOWUP_ARMS)} arms, "
              f"{len(NOMINAL_SOURCES)} nominal sources")
    rows = main_block(campaign, seeds)
    elapsed = time.time() - started
    _progress(f"  main block done: {len(rows)} rows, "
              f"{campaign.simulations} plant runs, {elapsed:.0f} s")

    document = {
        "schema": "csia.independent_validation.followup_campaign/1",
        "partition": partition,
        "seeds": list(seeds),
        "partition_manifest_sha256": fp.manifest_hash(),
        "phase_one_partition_manifest_sha256": pt.manifest_hash(),
        "preregistration": ("PREREGISTRATION.md + "
                            "PREREGISTRATION_AMENDMENT_4.md + "
                            "PREREGISTRATION_AMENDMENT_5.md"),
        "nominal_sources": list(NOMINAL_SOURCES),
        "reference_action": REFERENCE_ACTION,
        "arms": list(FOLLOWUP_ARMS),
        "arms_omitted": ["P7a_benchmark", "P7b_oracle", "P7b_point_oracle",
                         "P7c_robust"],
        "plants": list(PLANTS),
        "magnitudes": list(MAGNITUDES),
        "drift_states": dict(DRIFT_STATES),
        "n_rows": len(rows),
        "plant_simulations": campaign.simulations,
        "elapsed_s": elapsed,
        "what_this_is_not": (
            "Simulator only. Synthetic pack, no chemistry, no hardware "
            "representativeness. Not a certified safety artifact. Nothing "
            "here promotes anything, and nothing here edits the sealed "
            "campaign."),
        "reduction": reduce_rows(rows),
        "rows": rows,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"FOLLOWUP_{partition.upper()}.json"
    out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")

    _report(document, out)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", required=True,
                        choices=tuple(fp.SIZES))
    parser.add_argument("--open-the-seal", action="store_true",
                        help="required for the sealed final partition")
    parser.add_argument("--reduce-only", action="store_true",
                        help="recompute the reduction over rows already on "
                             "disk; simulates nothing")
    args = parser.parse_args()
    if args.reduce_only:
        raise SystemExit(rereduce(args.partition))
    raise SystemExit(run(args.partition, open_the_seal=args.open_the_seal))
