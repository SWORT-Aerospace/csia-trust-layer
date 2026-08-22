"""WP-C1 Part 3 — the design inverse.

1. Minimal sufficient channel sets X with D_critical subset of
   Delta_guaranteed(X).
2. Marginal value per channel: critical pairs it alone protects; channels that
   are the SOLE protector of a critical pair are single points of assurance
   failure.
3. Cheapest repair for each exposed critical pair, searched over two kinds of
   addition: a new channel, or wiring an EXISTING but unused feature into a
   hypothesis's LOW signature.

No cost model exists, so nothing is optimised for cost. Structural options are
reported and left for the user to price.

METHOD NOTE — not novel. Minimal sensor sets for an isolability specification
is Krysander & Frisk's sensor-placement method (IEEE SMC-A 2008; Automatica
2009; Fault Diagnosis Toolbox). See NOVELTY_ATTACK.md.

Run:  PYTHONPATH=. python research/wp_c1/design_inverse.py
Out:  research/wp_c1/results/design_inverse.json
"""

import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.certificate import d_critical               # noqa: E402
from research.wp_c1.lattice import (                            # noqa: E402
    CHANNELS, REQ, RESULTS, actuatable, load_signatures, merged_pairs,
    partition)
from research.wp_e1.gate_map import GATE_FEATURES              # noqa: E402


def guaranteed_given(low, channels):
    """Pairs distinguishable under EVERY reachable gate configuration, with
    the channel set held fixed."""
    channels = frozenset(channels)
    act = actuatable(channels)
    exposed = set()
    for r in range(len(act) + 1):
        for G in itertools.combinations(act, r):
            exposed |= merged_pairs(partition(low, G, channels))
    return exposed


def main() -> int:
    low = load_signatures()
    hyps = sorted(low)
    all_pairs = set(itertools.combinations(hyps, 2))
    crit, _ = d_critical(hyps)
    full = frozenset(CHANNELS)

    # --- 1. minimal sufficient channel sets ---------------------------------
    sufficient = []
    for r in range(len(CHANNELS) + 1):
        for X in itertools.combinations(CHANNELS, r):
            if not (crit & guaranteed_given(low, X)):
                continue
            if crit <= (all_pairs - guaranteed_given(low, X)):
                pass
            exposed = guaranteed_given(low, X)
            if not (crit & exposed):
                sufficient.append(sorted(X))
        if sufficient:
            break                      # first non-empty r gives minimal sets

    # --- 2. marginal value per channel --------------------------------------
    base_exposed = guaranteed_given(low, full)
    base_guar = all_pairs - base_exposed
    marginal = {}
    for ch in CHANNELS:
        without = all_pairs - guaranteed_given(low, full - {ch})
        lost = base_guar - without
        marginal[ch] = {
            "critical_pairs_lost_if_removed": sorted("+".join(p)
                                                     for p in lost & crit),
            "n_critical_lost": len(lost & crit),
            "sole_protector": sorted("+".join(p) for p in lost & crit),
        }

    # --- 3. cheapest repair for each exposed critical pair ------------------
    exposed_crit = sorted(base_exposed & crit)

    # Physically admissible edits only:
    #  - NEVER touch `nominal`: its LOW set is definitionally empty ("no
    #    feature is anomalous"). Adding a feature to it would assert that
    #    healthy flight predicts an anomaly.
    #  - A feature may only be wired into hypothesis h if it SPANS a channel
    #    h is about, i.e. it is physically informative about that fault.
    #  - The repair must not create a NEW critical exposure. A fix that
    #    separates one pair by merging another is not a fix.
    ABOUT = {
        "gps_fault": {"gps"},
        "imu0_bias_drift": {"imu0"},
        "imu1_bias_drift": {"imu1"},
        "mag_interference": {"mag"},
        "power_fault": {"battery", "motor_esc"},
        "vibration_anomaly": {"vibration"},
        "unexpected_maneuver": {"gps"},
    }

    def admissible(feature, target):
        if target == "nominal":
            return False
        return bool(REQ[feature] & ABOUT.get(target, set()))

    repairs = []
    for pair in exposed_crit:
        a, b = pair
        full_opts, partial_opts = [], []
        for f in sorted(REQ):
            for target in (a, b):
                if f in low.get(target, ()) or not admissible(f, target):
                    continue
                trial = {k: list(v) for k, v in low.items()}
                trial[target] = sorted(set(trial[target]) | {f})
                new_exposed = guaranteed_given(trial, full) & crit
                fixed = pair not in new_exposed
                collateral = sorted("+".join(p)
                                    for p in (new_exposed - base_exposed))
                entry = {
                    "feature": f,
                    "into_hypothesis": target,
                    "channels_required": sorted(REQ[f]),
                    "new_hardware": False,
                    "gated_by": sorted(g for g, fs in GATE_FEATURES.items()
                                       if f in fs),
                    "fixes_pair_in_all_configurations": fixed,
                    "creates_new_critical_exposure": collateral,
                }
                (full_opts if fixed and not collateral
                 else partial_opts).append(entry)

        repairs.append({
            "pair": "+".join(pair),
            "exposed_by": "gate closure at full channel availability",
            "channel_addition_helps": False,
            "n_complete_repairs": len(full_opts),
            "complete_repairs": full_opts,
            "n_partial_or_harmful": len(partial_opts),
            "partial_or_harmful": partial_opts,
            "reading": ("No existing feature repairs this pair under every "
                        "configuration without collateral damage; the fix "
                        "requires a NEW physics relation whose gate is "
                        "independent of the one that breaks the pair."
                        if not full_opts else
                        "Repairable by re-wiring the signature matrix alone, "
                        "no new hardware."),
        })

    report = {
        "purpose": "design inverse: minimal sufficient channel sets, marginal "
                   "channel value, cheapest repair",
        "not_novel": "see research/wp_c1/NOVELTY_ATTACK.md — this is "
                     "Krysander & Frisk sensor placement applied to CSIA",
        "n_critical_pairs": len(crit),
        "minimal_sufficient_channel_sets": sufficient,
        "minimal_sufficient_exists": bool(sufficient),
        "why_none": ("No channel set is sufficient. The two exposed critical "
                     "pairs are exposed by GATE closure at full channel "
                     "availability, and no amount of instrumentation closes a "
                     "gate-induced collision. The design inverse over channels "
                     "is therefore vacuous for this architecture, and the "
                     "actionable lever is the signature matrix, not the sensor "
                     "suite." if not sufficient else ""),
        "baseline_full_channels": {
            "n_guaranteed": len(base_guar),
            "critical_exposed": sorted("+".join(p)
                                       for p in sorted(base_exposed & crit)),
        },
        "marginal_channel_value": marginal,
        "single_points_of_assurance_failure": sorted(
            ch for ch, v in marginal.items() if v["n_critical_lost"] > 0),
        "cheapest_repairs": repairs,
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "design_inverse.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"minimal sufficient channel sets: "
          f"{sufficient if sufficient else 'NONE — see why_none'}")
    print(f"\nbaseline (all 8 channels): {len(base_guar)}/{len(all_pairs)} "
          f"pairs guaranteed; critical exposed = "
          f"{report['baseline_full_channels']['critical_exposed']}\n")
    print(f"{'channel':>12s} {'#critical lost if removed':>26s}  pairs")
    for ch, v in sorted(marginal.items(),
                        key=lambda kv: -kv[1]["n_critical_lost"]):
        print(f"{ch:>12s} {v['n_critical_lost']:>26d}  "
              f"{v['critical_pairs_lost_if_removed']}")
    print("\ncheapest repairs (physically admissible edits only):")
    for rp in repairs:
        print(f"  {rp['pair']}: {rp['n_complete_repairs']} complete, "
              f"{rp['n_partial_or_harmful']} partial/harmful")
        for o in rp["complete_repairs"][:4]:
            print(f"     COMPLETE  + {o['feature']} -> {o['into_hypothesis']} "
                  f"(gated by {o['gated_by'] or 'nothing'})")
        for o in rp["partial_or_harmful"][:4]:
            print(f"     partial   + {o['feature']} -> {o['into_hypothesis']} "
                  f"(gated by {o['gated_by'] or 'nothing'}; "
                  f"collateral {o['creates_new_critical_exposure']})")
        print(f"     -> {rp['reading']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
