"""WP-C3 Part 2 — diagnostic failure as a coherent-system structure function.

For a critical pair (h_a, h_b) define phi_ab(c) = 1 if the pair merges under
configuration c. Components are the 4 actuating gates and the 8 channels, each
binary: 1 = "failed" (gate closed / channel absent). phi is MONOTONE — once a
pair merges, more failures cannot unmerge it — which is exactly the structure
function of a coherent system, so reliability machinery applies.

Computes:
  * monotonicity verification (a violation is a bug here, not a discovery)
  * minimal cut sets per critical pair, with the size distribution; size-one
    cut sets are single points of diagnostic failure and are named
  * Birnbaum importance per component: the fraction of configurations in which
    toggling that component alone flips phi
  * structural importance of gvalid specifically
  * the symbolic bridge to P(diagnostic failure). The per-component failure
    probabilities DO NOT EXIST in this repository; the expression is left
    symbolic and the missing measurement is named.

Run:  PYTHONPATH=. python research/wp_c3/reliability_structure.py
Out:  research/wp_c3/results/reliability_structure.json
"""

import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.certificate import d_critical               # noqa: E402
from research.wp_c1.lattice import (                            # noqa: E402
    CHANNELS, load_signatures, merged_pairs, partition)
from research.wp_e1.gate_map import GATE_FEATURES               # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
GATES = tuple(sorted(GATE_FEATURES))
COMPONENTS = tuple(list(GATES) + [f"channel:{c}" for c in CHANNELS])
FULL = frozenset(CHANNELS)


def decode(state):
    """A frozenset of failed components -> (closed_gates, present_channels)."""
    closed = tuple(g for g in GATES if g in state)
    absent = {c for c in CHANNELS if f"channel:{c}" in state}
    return closed, frozenset(CHANNELS) - absent


def phi(low, pair, state):
    closed, present = decode(state)
    return 1 if pair in merged_pairs(partition(low, closed, present)) else 0


def all_states():
    for r in range(len(COMPONENTS) + 1):
        for combo in itertools.combinations(COMPONENTS, r):
            yield frozenset(combo)


def analyse_pair(low, pair, states):
    values = {s: phi(low, pair, s) for s in states}

    # monotonicity: s subset of t implies phi(s) <= phi(t). Checked on
    # single-component extensions, which is equivalent for a set function.
    violations = []
    for s, v in values.items():
        if v != 1:
            continue
        for c in s:
            if values[s - {c}] > v:
                violations.append((sorted(s), c))

    failing = [s for s, v in values.items() if v == 1]
    minimal = []
    for s in failing:
        if not any(t < s for t in failing):
            minimal.append(sorted(s))
    minimal.sort(key=lambda x: (len(x), x))

    sizes = {}
    for m in minimal:
        sizes[len(m)] = sizes.get(len(m), 0) + 1

    # Birnbaum importance: fraction of the 2^(n-1) environments in which
    # toggling component x alone flips phi.
    birnbaum = {}
    others = len(COMPONENTS) - 1
    for c in COMPONENTS:
        flips = 0
        for s in states:
            if c in s:
                continue
            if values[s | {c}] != values[s]:
                flips += 1
        birnbaum[c] = round(flips / (2 ** others), 6)

    return {
        "pair": "+".join(pair),
        "monotone": not violations,
        "monotonicity_violations": violations[:5],
        "n_failing_configurations": len(failing),
        "minimal_cut_sets": minimal,
        "n_minimal_cut_sets": len(minimal),
        "cut_set_size_distribution": dict(sorted(sizes.items())),
        "order_one_cut_sets": [m[0] for m in minimal if len(m) == 1],
        "birnbaum_importance": dict(sorted(birnbaum.items(),
                                           key=lambda kv: -kv[1])),
    }


def main() -> int:
    low = load_signatures()
    hyps = sorted(low)
    crit, _ = d_critical(hyps)
    states = list(all_states())

    per_pair = [analyse_pair(low, p, states) for p in sorted(crit)]

    # aggregate Birnbaum across all critical pairs
    agg = {c: 0.0 for c in COMPONENTS}
    for row in per_pair:
        for c, v in row["birnbaum_importance"].items():
            agg[c] += v
    agg = {c: round(v / len(per_pair), 6) for c, v in agg.items()}
    ranked = sorted(agg.items(), key=lambda kv: -kv[1])

    order_one = {row["pair"]: row["order_one_cut_sets"]
                 for row in per_pair if row["order_one_cut_sets"]}

    gvalid_rank = [i for i, (c, _) in enumerate(ranked, 1)
                   if c == "gvalid"][0]

    report = {
        "purpose": "diagnostic failure as a coherent-system structure "
                   "function: cut sets, Birnbaum importance, symbolic risk",
        "components": list(COMPONENTS),
        "n_components": len(COMPONENTS),
        "n_states": len(states),
        "convention": "component = 1 means FAILED (gate closed / channel "
                      "absent); phi = 1 means the pair is indistinguishable",
        "all_pairs_monotone": all(r["monotone"] for r in per_pair),
        "per_critical_pair": per_pair,
        "aggregate_birnbaum_importance": dict(ranked),
        "birnbaum_ranking": [c for c, _ in ranked],
        "gvalid": {
            "aggregate_birnbaum": agg["gvalid"],
            "rank_among_components": gvalid_rank,
            "of_total_components": len(COMPONENTS),
            "order_one_cut_set_for": [p for p, cs in order_one.items()
                                      if "gvalid" in cs],
        },
        "order_one_cut_sets_by_pair": order_one,
        "probability_bridge": {
            "expression": "P(phi_ab = 1) = sum over states s of "
                          "[ prod_{c in s} q_c * prod_{c not in s} (1 - q_c) "
                          "* phi_ab(s) ]",
            "equivalently": "for a coherent system, P(phi=1) = 1 - prod over "
                            "minimal PATH sets of (1 - prod of component "
                            "availabilities); the cut-set form above is used "
                            "here because the cut sets are enumerated",
            "conditional_form": "the operationally meaningful quantity is "
                                "P(phi_ab = 1 | h_a true), because gate "
                                "closure probabilities are hypothesis-"
                                "dependent: q_gvalid differs under GNSS "
                                "degradation and under nominal flight",
            "q_c_required": [f"q_{c}" for c in COMPONENTS],
            "STATUS": "NOT COMPUTABLE. No per-gate closure probability and no "
                      "per-channel unavailability probability exists anywhere "
                      "in this repository. No emission table, no reliability "
                      "block, no measured rates.",
            "single_measurement_that_unlocks_it": (
                "q_gvalid conditioned on hypothesis — i.e. P(gvalid closed | "
                "gps_fault) versus P(gvalid closed | nominal), measured from "
                "per-tick gate traces on real flight logs. This is the same "
                "measurement WP-E2 needs, and it converts every structural "
                "result in WP-C1 through WP-C3 into a risk statement."),
            "externally_supplied_figure": (
                "The ~45:1 ratio quoted by the user (P(Z=0|GNSS_DEG) ~ 0.90 "
                "vs P(Z=0|nominal) ~ 0.02) is EXTERNAL to this codebase and "
                "is not used in any computation here."),
        },
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "reliability_structure.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"components: {len(COMPONENTS)}   states: {len(states)}   "
          f"all pairs monotone: {report['all_pairs_monotone']}\n")
    print("order-1 cut sets (single points of diagnostic failure):")
    for p, cs in sorted(order_one.items()):
        print(f"  {p:<42s} {cs}")
    print(f"\naggregate Birnbaum importance ranking:")
    for c, v in ranked:
        print(f"  {c:<22s} {v:.6f}")
    print(f"\ngvalid: rank {gvalid_rank}/{len(COMPONENTS)}, "
          f"aggregate {agg['gvalid']:.6f}, order-1 cut set for "
          f"{report['gvalid']['order_one_cut_set_for']}")
    print("\ncut-set size distribution per pair (first 6):")
    for row in per_pair[:6]:
        print(f"  {row['pair']:<42s} {row['cut_set_size_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
