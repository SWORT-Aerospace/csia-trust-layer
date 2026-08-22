"""WP-C1 Parts 1.4 and 2 — Delta_guaranteed, the exposure set, and D_critical.

Delta_guaranteed(A) = hypothesis pairs distinguishable in EVERY configuration
in an admissible set A. The exposure set is its complement, each member
reported with the MINIMAL configuration that breaks it.

D_critical = hypothesis pairs requiring DIFFERENT safe responses, read out of
the failsafe automaton's condition/action table (csia/runtime/failsafe.py:96-176)
INCLUDING action parameters. `imu0_bias_drift` and `imu1_bias_drift` both raise
`imu_isolated`, but SELECT_IMU carries {"use": best_imu}, so the commanded
response differs and the pair IS critical.

The distinction this part exists to draw: failing to NAME a cause is not
automatically a safety property. Failing to CHOOSE THE RESPONSE is.

METHOD NOTE — not novel; see NOVELTY_ATTACK.md. "Isolate only to the
granularity reconfiguration requires" is a standing FTC principle
(Blanke et al. 2003).

Run:  PYTHONPATH=. python research/wp_c1/certificate.py
Out:  research/wp_c1/results/certificate.json
"""

import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.lattice import (                          # noqa: E402
    CHANNELS, GATES, RESULTS, corpus_channel_sets, enumerate_reach,
    load_signatures, merged_pairs, observable, partition)

# --- D_critical: hypothesis -> commanded response ---------------------------
# Read from csia/runtime/failsafe.py:96-176. The value is the action set the
# condition issues, with parameters, since a parameterised action that differs
# is a different response.
RESPONSE = {
    "nominal": (),
    "unexpected_maneuver": (),          # benign explanation; commands nothing
    "gps_fault": ("SWITCH_NAV_INERTIAL", "INHIBIT_GPS_MODES"),
    "imu0_bias_drift": ("SELECT_IMU(use=imu1)",),
    "imu1_bias_drift": ("SELECT_IMU(use=imu0)",),
    "mag_interference": ("HEADING_HOLD_GYRO",),
    "power_fault": ("REDUCE_POWER", "LAND_NOW"),
    "vibration_anomaly": ("LIMIT_THROTTLE", "LAND_SOON"),
}


def d_critical(hypotheses):
    """Pairs whose commanded responses differ."""
    crit, benign = set(), set()
    for a, b in itertools.combinations(sorted(hypotheses), 2):
        if set(RESPONSE[a]) != set(RESPONSE[b]):
            crit.add((a, b))
        else:
            benign.add((a, b))
    return crit, benign


def guaranteed(reach_values, all_pairs):
    """Pairs never merged anywhere in the admissible set."""
    exposed = set()
    for row in reach_values:
        exposed |= row["merged_pairs"]
    return all_pairs - exposed, exposed


def minimal_breaker(reach, pair):
    """Smallest configuration (fewest gates closed, then most channels
    present) in which `pair` is indistinguishable."""
    hits = [r for r in reach.values() if pair in r["merged_pairs"]]
    if not hits:
        return None
    return min(hits, key=lambda r: (len(r["gates_closed"]),
                                    -r["n_channels"]))


def _transitive_closure(pairs, elements):
    """Merging is an EQUIVALENCE relation. The union of two merge relations is
    not one, and its transitive closure adds pairs that no mechanism created.
    A test for interaction that ignores this over-detects."""
    parent = {e: e for e in elements}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    out = set()
    for a, b in itertools.combinations(sorted(elements), 2):
        if find(a) == find(b):
            out.add((a, b))
    return out


def subadditivity(low, all_pairs):
    """Do gate closure and channel absence interact super-additively?

    Tested at TWO levels, because the naive pair-level test is wrong.

    1. FEATURE level — the mechanism level. A feature is destroyed by
       (channel absent) OR (gate closed), so joint feature loss is exactly the
       union of the marginals. Any excess here would be genuine interaction.

    2. PARTITION level — merge pairs, compared against the TRANSITIVE CLOSURE
       of the union of the marginal merge relations. Comparing against the raw
       union (as a first version of this function did) reports spurious
       interaction: if gate closure gives A == B and channel absence gives
       B == C, then A == C holds jointly by transitivity alone, with no
       higher-order structure involved.
    """
    full = frozenset(CHANNELS)
    hyps = sorted(low)
    feature_excess, pair_excess_raw, pair_excess_closed = [], [], []

    for r in range(len(CHANNELS) + 1):
        for X in itertools.combinations(CHANNELS, r):
            X = frozenset(X)
            chan_only_f = observable((), full) - observable((), X)
            chan_only_p = merged_pairs(partition(low, (), X))
            for gr in range(len(GATES) + 1):
                for G in itertools.combinations(GATES, gr):
                    gate_only_f = observable((), full) - observable(G, full)
                    gate_only_p = merged_pairs(partition(low, G, full))
                    joint_f = observable((), full) - observable(G, X)
                    joint_p = merged_pairs(partition(low, G, X))

                    fx = joint_f - gate_only_f - chan_only_f
                    if fx:
                        feature_excess.append(
                            {"gates_closed": sorted(G),
                             "channels": sorted(X),
                             "features": sorted(fx)})

                    raw = joint_p - gate_only_p - chan_only_p
                    if raw:
                        pair_excess_raw.append(
                            {"gates_closed": sorted(G),
                             "channels": sorted(X),
                             "novel_merges": sorted("+".join(p)
                                                    for p in raw)})

                    closure = _transitive_closure(
                        gate_only_p | chan_only_p, hyps)
                    beyond = joint_p - closure
                    if beyond:
                        pair_excess_closed.append(
                            {"gates_closed": sorted(G),
                             "channels": sorted(X),
                             "novel_merges": sorted("+".join(p)
                                                    for p in beyond)})

    return {
        "feature_level": {
            "superadditive_configurations": len(feature_excess),
            "examples": feature_excess[:5],
            "verdict": "ADDITIVE BY CONSTRUCTION — a feature dies if its "
                       "channel is absent OR a controlling gate is closed, so "
                       "joint feature loss is exactly the union of the "
                       "marginals. No configuration can exceed it."
                       if not feature_excess else "SUPER-ADDITIVE",
        },
        "pair_level_raw_union": {
            "superadditive_configurations": len(pair_excess_raw),
            "examples": pair_excess_raw[:3],
            "caveat": "THIS TEST IS WRONG and is retained only to document "
                      "the error. It compares joint merges against the raw "
                      "union of marginal merges, ignoring that merging is an "
                      "equivalence relation. It reports interaction wherever "
                      "transitivity alone links two classes.",
        },
        "pair_level_transitive_closure": {
            "superadditive_configurations": len(pair_excess_closed),
            "examples": pair_excess_closed[:5],
            "verdict": "SUB-ADDITIVE — no configuration merges a pair beyond "
                       "the transitive closure of the two marginal merge "
                       "relations. Gate closure and channel absence destroy "
                       "OVERLAPPING feature sets; their effects compose by "
                       "union and transitivity, not by interaction."
                       if not pair_excess_closed else
                       "SUPER-ADDITIVE — genuine higher-order structure; see "
                       "examples.",
        },
    }


def main() -> int:
    low = load_signatures()
    hyps = sorted(low)
    all_pairs = set(itertools.combinations(hyps, 2))
    crit, benign = d_critical(hyps)

    reach = enumerate_reach(low)
    counts, n_logs = corpus_channel_sets()
    corpus_reach = enumerate_reach(low, list(counts))

    # Certificate curve: admissible set = "at least k channels present".
    curve = []
    for k in range(1, len(CHANNELS) + 1):
        subset = [r for r in reach.values() if r["n_channels"] >= k]
        g, _ = guaranteed(subset, all_pairs)
        curve.append({
            "min_channels": k,
            "n_configurations": len(subset),
            "n_guaranteed_pairs": len(g),
            "n_critical_guaranteed": len(crit & g),
            "d_critical_subset_of_guaranteed": crit <= g,
            "critical_pairs_exposed": sorted("+".join(p)
                                             for p in sorted(crit - g)),
        })

    g_corpus, exposed_corpus = guaranteed(corpus_reach.values(), all_pairs)

    exposure_detail = []
    for pair in sorted(crit - g_corpus):
        br = minimal_breaker(corpus_reach, pair)
        exposure_detail.append({
            "pair": "+".join(pair),
            "critical": True,
            "minimal_breaking_configuration": None if br is None else {
                "gates_closed": br["gates_closed"],
                "channels": br["channels"],
                "n_channels": br["n_channels"],
                "kappa": br["kappa"],
            },
            "corpus_logs_in_that_channel_config":
                counts.get(frozenset(br["channels"]), 0) if br else 0,
        })

    subadd = subadditivity(low, all_pairs)

    report = {
        "purpose": "Delta_guaranteed, the exposure set, and the safety "
                   "projection D_critical",
        "not_novel": "see research/wp_c1/NOVELTY_ATTACK.md",
        "n_hypotheses": len(hyps),
        "n_pairs_total": len(all_pairs),
        "d_critical": {
            "source": "csia/runtime/failsafe.py:96-176, action sets WITH "
                      "parameters",
            "response_map": {k: list(v) for k, v in RESPONSE.items()},
            "n_critical_pairs": len(crit),
            "n_response_equivalent_pairs": len(benign),
            "response_equivalent_pairs": sorted("+".join(p) for p in benign),
            "note": "nominal and unexpected_maneuver command the identical "
                    "(empty) response, so they need never be distinguished. "
                    "imu0/imu1 bias drift raise the same CONDITION but "
                    "SELECT_IMU carries {'use': best_imu}, so the responses "
                    "differ and the pair is critical.",
        },
        "certificate_curve_min_channels": curve,
        "corpus_admissible_set": {
            "n_logs": n_logs,
            "n_configurations": len(corpus_reach),
            "n_guaranteed_pairs": len(g_corpus),
            "guaranteed_pairs": sorted("+".join(p) for p in sorted(g_corpus)),
            "d_critical_subset_of_guaranteed": crit <= g_corpus,
            "n_critical_exposed": len(crit - g_corpus),
        },
        "exposure_set_critical_pairs": exposure_detail,
        "subadditivity": subadd,
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "certificate.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"pairs total {len(all_pairs)}; D_critical {len(crit)}; "
          f"response-equivalent {len(benign)} "
          f"({sorted('+'.join(p) for p in benign)})\n")
    print(f"{'min ch':>7s} {'#cfg':>6s} {'|guaranteed|':>13s} "
          f"{'crit guaranteed':>16s}  D_crit subset?")
    for row in curve:
        print(f"{row['min_channels']:>7d} {row['n_configurations']:>6d} "
              f"{row['n_guaranteed_pairs']:>13d} "
              f"{row['n_critical_guaranteed']:>16d}  "
              f"{row['d_critical_subset_of_guaranteed']}")
    print(f"\ncorpus admissible set: |Delta_guaranteed| = {len(g_corpus)}, "
          f"D_critical subset = {crit <= g_corpus}, "
          f"critical exposed = {len(crit - g_corpus)}")
    print("\nsub-additivity:")
    print(f"  feature level      : "
          f"{subadd['feature_level']['superadditive_configurations']} "
          f"superadditive configs")
    print(f"  pair, raw union    : "
          f"{subadd['pair_level_raw_union']['superadditive_configurations']} "
          f"(WRONG TEST — ignores transitivity)")
    print(f"  pair, trans-closure: "
          f"{subadd['pair_level_transitive_closure']['superadditive_configurations']}"
          f" -> {subadd['pair_level_transitive_closure']['verdict'][:48]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
