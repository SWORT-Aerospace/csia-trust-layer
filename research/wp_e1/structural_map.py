"""WP-E1 C-plus — the deterministic structural consequence map.

Enumerates every configuration of the four actuating gates and computes, for
each, the partition of the eight hypotheses into observable classes:

  * kappa  = (H - P) / (H - 1)   coarsening index, 0 = distinguishable,
                                 1 = total collapse
  * nominal absorption           which faults become indistinguishable from
                                 healthy flight
  * merged classes               which hypotheses collapse together
  * pure-interaction sets        gate sets whose JOINT closure produces a
                                 merge that no proper subset produces

No flight data is required and none is used. This is a closed-form
consequence of the signature matrix (WP1) and the gate map (source-verified),
computed under the RUNTIME armed-flag semantics.

Run:  PYTHONPATH=. python research/wp_e1/structural_map.py
Out:  reports/wp_e1/structural_consequence_map.json
"""

import itertools
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_e1.gate_map import (                       # noqa: E402
    ARMED_SEMANTICS, GATE_FEATURES, NON_ACTUATING_GATES, surviving)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MATRIX = os.path.join(ROOT, "research", "formalization",
                      "diagnostic_signature_matrix.yaml")
OUT = os.path.join(ROOT, "reports", "wp_e1",
                   "structural_consequence_map.json")

GATES = tuple(GATE_FEATURES)


def load_signatures():
    if not os.path.exists(MATRIX):
        raise SystemExit("WP1_FORMALIZATION_MISSING: "
                         f"{MATRIX} not found — refusing to proceed")
    with open(MATRIX) as fh:
        matrix = yaml.safe_load(fh)
    low = matrix.get("hypotheses")
    if not low:
        raise SystemExit("SIGNATURE_MATRIX_MISSING: no `hypotheses` block")
    return low


def partition(low, closed):
    """Observable classes under `closed` gates: hypotheses sharing a
    restricted LOW signature are indistinguishable."""
    avail = surviving(closed)
    restricted = {h: tuple(sorted(set(s) & avail)) for h, s in low.items()}
    classes = {}
    for hyp, sig in restricted.items():
        classes.setdefault(sig, []).append(hyp)
    return restricted, {sig: sorted(m) for sig, m in classes.items()}


def merge_pairs(classes):
    """Unordered pairs of hypotheses that share an observable class."""
    pairs = set()
    for members in classes.values():
        for a, b in itertools.combinations(sorted(members), 2):
            pairs.add((a, b))
    return pairs


def describe(low, closed):
    restricted, classes = partition(low, closed)
    h = len(low)
    p = len(classes)
    nominal_class = next(m for sig, m in classes.items() if "nominal" in m)
    return {
        "gates_closed": sorted(closed),
        "features_lost": sorted(set(GATE_FEATURES and
                                    [f for g in closed
                                     for f in GATE_FEATURES[g]])),
        "n_observable_classes": p,
        "kappa": round((h - p) / (h - 1), 4),
        "nominal_absorbs": sorted(x for x in nominal_class if x != "nominal"),
        "merged_classes": {", ".join(m): list(sig)
                           for sig, m in classes.items() if len(m) > 1},
        "restricted_signatures": {k: list(v) for k, v in restricted.items()},
        "_pairs": merge_pairs(classes),
    }


def main() -> int:
    low = load_signatures()
    h = len(low)

    configs = {}
    for r in range(len(GATES) + 1):
        for closed in itertools.combinations(GATES, r):
            configs[frozenset(closed)] = describe(low, closed)

    baseline_pairs = configs[frozenset()]["_pairs"]

    # --- interaction analysis -----------------------------------------------
    # A gate set S shows PURE INTERACTION if closing all of S produces a merge
    # that no PROPER SUBSET of S produces. If every merge at S already appears
    # under some singleton, the marginals over-count and must not be summed.
    interactions = []
    for closed, row in configs.items():
        if len(closed) < 2:
            continue
        subset_pairs = set()
        for r in range(1, len(closed)):
            for sub in itertools.combinations(sorted(closed), r):
                subset_pairs |= configs[frozenset(sub)]["_pairs"]
        novel = row["_pairs"] - subset_pairs - baseline_pairs
        interactions.append({
            "gates_closed": sorted(closed),
            "novel_merges": sorted("+".join(p) for p in novel),
            "pure_interaction": bool(novel),
            "kappa_joint": row["kappa"],
            "kappa_sum_of_marginals": round(sum(
                configs[frozenset([g])]["kappa"] for g in closed), 4),
        })

    any_pure = any(i["pure_interaction"] for i in interactions)

    # Sub-additivity check: joint kappa vs summed marginals.
    superadditive = [i for i in interactions
                     if i["kappa_joint"] > i["kappa_sum_of_marginals"] + 1e-9]

    singles = {g: configs[frozenset([g])] for g in GATES}
    ranked = sorted(GATES, key=lambda g: -singles[g]["kappa"])

    report = {
        "purpose": "deterministic structural consequence of gate closure on "
                   "diagnostic identifiability",
        "method": "restrict each hypothesis LOW signature to the features "
                  "surviving a gate configuration; hypotheses sharing a "
                  "restricted signature are indistinguishable "
                  "(bayes.py:99-100 SKIPS a gated feature)",
        "inputs": {
            "signature_matrix": "research/formalization/"
                                "diagnostic_signature_matrix.yaml",
            "gate_map": "research/wp_e1/gate_map.py (source-verified)",
            "flight_data_used": "none",
        },
        "armed_gate_semantics": "RUNTIME FLAG (online.py:491-496)",
        "armed_semantics_detail": ARMED_SEMANTICS,
        "non_actuating_gates": NON_ACTUATING_GATES,
        "n_hypotheses": h,
        "actuating_gates": list(GATES),
        "kappa_definition": "(H - P) / (H - 1)",
        "disjointness": {
            "gates_share_features": True,
            "shared": {
                "heading_course": ["gvalid", "speed_gate"],
                "phys_gps": ["gvalid", "gps_warmup"],
            },
            "composition": "multiplicative (product of gates), so EITHER gate "
                           "alone drives the feature to zero",
            "pure_interaction_found": any_pure,
            "superadditive_configurations": superadditive,
            "verdict": (
                "SHARED BUT SUB-ADDITIVE. Sharing is real — two features each "
                "depend on two gates — but because the composition is a "
                "product, closure is an OR: each gate alone is sufficient. No "
                "gate set produces a merge that no proper subset produces, so "
                "there is NO pure interaction in this gate map. Level-1 "
                "marginals still cannot be summed, but the reason is "
                "over-counting, not hidden interaction."
                if not any_pure else
                "PURE INTERACTION PRESENT — see novel_merges."),
        },
        "gate_severity_ranking": [
            {"gate": g, "kappa": singles[g]["kappa"],
             "nominal_absorbs": singles[g]["nominal_absorbs"],
             "merged": list(singles[g]["merged_classes"])}
            for g in ranked],
        "interactions": interactions,
        "configurations": [
            {k: v for k, v in row.items() if k != "_pairs"}
            for row in sorted(configs.values(),
                              key=lambda r: (len(r["gates_closed"]),
                                             r["gates_closed"]))],
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"hypotheses H = {h}; actuating gates = {list(GATES)}\n")
    print(f"{'gates closed':<44s} {'P':>3s} {'kappa':>7s}  absorbed by nominal")
    for row in report["configurations"]:
        label = "+".join(row["gates_closed"]) or "(none — all gates open)"
        print(f"{label:<44s} {row['n_observable_classes']:>3d} "
              f"{row['kappa']:>7.3f}  {row['nominal_absorbs']}")
    print(f"\npure interaction found: {any_pure}")
    print(f"superadditive configurations: {len(superadditive)}")
    print(f"\nverdict: {report['disjointness']['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
