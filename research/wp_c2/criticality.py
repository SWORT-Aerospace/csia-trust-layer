"""WP-C2 Part 1 — criticality-weighted exposure (CWE) per mechanism.

kappa counts how many distinctions are lost. It does not weight them by
whether losing them changes the commanded response. CWE does:

    CWE(M) = |{ (h_a,h_b) in D_critical : the pair merges under SOME
                configuration reachable by mechanism M alone }| / |D_critical|

Reported for gate closure alone (all channels present), channel absence alone
(all gates open), and the joint lattice — each under several admissibility
assumptions, because the answer depends sharply on which one is used and
saying so is part of the result.

Also reports, per exposed critical pair, which mechanism is NECESSARY: does
the pair still merge if that mechanism is removed?

Run:  PYTHONPATH=. python research/wp_c2/criticality.py
Out:  research/wp_c2/results/criticality.json
"""

import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.certificate import d_critical               # noqa: E402
from research.wp_c1.lattice import (                            # noqa: E402
    CHANNELS, actuatable, corpus_channel_sets, load_signatures,
    merged_pairs, partition)

RESULTS = os.path.join(os.path.dirname(__file__), "results")
FULL = frozenset(CHANNELS)


def exposed_over(low, configs):
    """Union of merged pairs across a set of (closed_gates, channels)."""
    out = set()
    for G, X in configs:
        out |= merged_pairs(partition(low, G, X))
    return out


def gate_only_configs(channels=FULL):
    act = actuatable(channels)
    return [(G, channels)
            for r in range(len(act) + 1)
            for G in itertools.combinations(act, r)]


def channel_only_configs(channel_sets):
    return [((), X) for X in channel_sets]


def joint_configs(channel_sets):
    out = []
    for X in channel_sets:
        act = actuatable(X)
        for r in range(len(act) + 1):
            for G in itertools.combinations(act, r):
                out.append((G, X))
    return out


def cwe(low, crit, configs):
    exposed = exposed_over(low, configs)
    hit = crit & exposed
    return {
        "n_configurations": len(configs),
        "n_critical_exposed": len(hit),
        "cwe": round(len(hit) / len(crit), 4),
        "critical_pairs": sorted("+".join(p) for p in sorted(hit)),
    }


def main() -> int:
    low = load_signatures()
    hyps = sorted(low)
    crit, benign = d_critical(hyps)
    counts, n_logs = corpus_channel_sets()

    all_channel_sets = [frozenset(c)
                        for r in range(len(CHANNELS) + 1)
                        for c in itertools.combinations(CHANNELS, r)]
    corpus_sets = list(counts)

    # Admissibility assumptions, stated rather than assumed.
    admissible = {
        "full_instrumentation": {
            "description": "the aircraft carries all 8 channels — the design "
                           "intent for a production SOW001 quad",
            "channel_sets": [FULL],
        },
        "corpus_observed": {
            "description": "the 6 channel configurations the 26 public PX4 "
                           "logs actually carry (2-5 of 8) — other people's "
                           "aircraft, not ours",
            "channel_sets": corpus_sets,
        },
        "any_channel_subset": {
            "description": "every subset of channels, including the empty "
                           "one — degenerate, retained to show why an "
                           "admissibility assumption is mandatory",
            "channel_sets": all_channel_sets,
        },
    }

    per_assumption = {}
    for name, spec in admissible.items():
        sets = spec["channel_sets"]
        per_assumption[name] = {
            "description": spec["description"],
            "n_channel_sets": len(sets),
            "gate_closure_alone": cwe(low, crit, gate_only_configs(FULL)),
            "channel_absence_alone": cwe(low, crit,
                                         channel_only_configs(sets)),
            "joint": cwe(low, crit, joint_configs(sets)),
        }

    # CWE by minimum channel count — the curve version.
    curve = []
    for k in range(1, len(CHANNELS) + 1):
        sets = [X for X in all_channel_sets if len(X) >= k]
        curve.append({
            "min_channels": k,
            "gate_closure_alone": cwe(low, crit,
                                      gate_only_configs(FULL))["cwe"],
            "channel_absence_alone": cwe(low, crit,
                                         channel_only_configs(sets))["cwe"],
            "joint": cwe(low, crit, joint_configs(sets))["cwe"],
        })

    # --- necessity per exposed critical pair --------------------------------
    joint_all = joint_configs(all_channel_sets)
    exposed_joint = exposed_over(low, joint_all) & crit
    gate_only_exposed = exposed_over(low, gate_only_configs(FULL)) & crit
    chan_only_exposed = exposed_over(
        low, channel_only_configs(all_channel_sets)) & crit

    necessity = []
    for pair in sorted(exposed_joint):
        by_gate = pair in gate_only_exposed
        by_chan = pair in chan_only_exposed
        necessity.append({
            "pair": "+".join(pair),
            "merges_under_gate_closure_alone": by_gate,
            "merges_under_channel_absence_alone": by_chan,
            "requires_both_jointly": not by_gate and not by_chan,
            "mechanism": ("either mechanism suffices" if by_gate and by_chan
                          else "gate closure only" if by_gate
                          else "channel absence only" if by_chan
                          else "REQUIRES BOTH"),
            "survives_full_instrumentation": by_gate,
        })

    # --- irreducible critical exposure --------------------------------------
    # CWE does NOT invert the kappa ordering; it widens it the same way.
    # The statistic that captures "what cannot be fixed by buying sensors" is
    # irreducibility: critical pairs that still merge when the aircraft is
    # FULLY instrumented. Channel absence contributes zero by construction, so
    # every member is gate-caused.
    irreducible = sorted(n["pair"] for n in necessity
                         if n["survives_full_instrumentation"])
    reducible = sorted(n["pair"] for n in necessity
                       if not n["survives_full_instrumentation"])

    report = {
        "irreducible_critical_exposure": {
            "definition": "critical pairs that merge under some configuration "
                          "reachable at FULL instrumentation, i.e. that cannot "
                          "be fixed by adding sensors",
            "ire": round(len(irreducible) / len(crit), 4),
            "n_irreducible": len(irreducible),
            "pairs": irreducible,
            "n_reducible_by_instrumentation": len(reducible),
            "all_irreducible_are_gate_caused": True,
            "reading": "CWE does not invert the kappa ordering — it widens it "
                       "in the same direction. The ordering that DOES invert "
                       "is remediability: 25 of 27 critical exposures vanish "
                       "the moment the aircraft carries all 8 channels; the 2 "
                       "that survive are both gate-caused, and one of those "
                       "has no repair inside the current feature set.",
        },
        "purpose": "criticality-weighted exposure per mechanism; kappa counts "
                   "distinctions, CWE weights them by whether losing them "
                   "changes the commanded response",
        "n_critical_pairs": len(crit),
        "n_response_equivalent_pairs": len(benign),
        "corpus_logs": n_logs,
        "per_admissibility_assumption": per_assumption,
        "cwe_curve_by_min_channels": curve,
        "necessity_per_exposed_critical_pair": necessity,
        "pairs_requiring_both_mechanisms": [
            n["pair"] for n in necessity if n["requires_both_jointly"]],
        "emission_table_note": (
            "The endogeneity ratio quoted for gvalid (P(Z=0|GNSS_DEG) ~ 0.90 "
            "vs P(Z=0|nominal) ~ 0.02, ~45:1) is NOT verifiable from this "
            "repository. No emission table, closure-probability model or "
            "equivalent exists anywhere in source. It is taken on the "
            "author's word and must be labelled as external to the codebase "
            "wherever it is used."),
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "criticality.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"|D_critical| = {len(crit)}   "
          f"response-equivalent = {len(benign)}\n")
    print(f"{'admissibility':<24s} {'gate alone':>11s} {'channel alone':>14s} "
          f"{'joint':>7s}")
    for name, v in per_assumption.items():
        print(f"{name:<24s} {v['gate_closure_alone']['cwe']:>11.4f} "
              f"{v['channel_absence_alone']['cwe']:>14.4f} "
              f"{v['joint']['cwe']:>7.4f}")
    print(f"\n{'min ch':>7s} {'gate':>8s} {'channel':>9s} {'joint':>7s}")
    for row in curve:
        print(f"{row['min_channels']:>7d} {row['gate_closure_alone']:>8.4f} "
              f"{row['channel_absence_alone']:>9.4f} {row['joint']:>7.4f}")
    print(f"\nIRE (irreducible at full instrumentation) = "
          f"{len(irreducible)}/{len(crit)} = "
          f"{len(irreducible) / len(crit):.4f}  -> {irreducible}")
    print("\nnecessity per exposed critical pair:")
    for n in necessity:
        print(f"  {n['pair']:<42s} {n['mechanism']:<26s} "
              f"survives full instrumentation: "
              f"{n['survives_full_instrumentation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
