"""Zero-event bounds, with the denominator that is actually defensible.

"Zero false certificates" is not a rate claim. For zero observed failures in
``N`` independent relevant trials the one-sided 95% upper bound is
approximately ``3/N``, so the number that matters is ``N`` -- and ``N`` is
smaller than the row count, for a reason worth being explicit about.

Several arms choose the **same action** in the **same cell**. When they do,
they are not independent trials: they are one simulation counted several times.
Up to seven arms share a single experiment in the validation campaign. Counting
rows would inflate the denominator by roughly a factor of two and tighten the
bound by the same factor, for free, which is exactly the sort of free tightening
that should not be available.

Three denominators are reported and the most conservative is named as such:

``rows``
    certified rows. Inflated. Reported only so the inflation is visible.
``experiments``
    distinct ``(action, plant, magnitude, seed, drift)`` combinations. The
    honest count of distinct simulations.
``seeds``
    distinct seeds. The most conservative reading, treating everything sharing
    a seed as one observation.

The truth is between the last two and this tool does not pretend to know where.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from typing import Dict, List

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "research/active_evidence/independent_validation/results"

#: From the downstream roadmap: trials needed for a 95% zero-event bound below
#: 1e-4. Recorded so the shortfall is a number rather than an impression.
TRIALS_FOR_1E4 = 29956


def rule_of_three(n: int) -> float:
    """One-sided 95% upper bound for zero events in ``n`` independent trials."""
    return 3.0 / n if n > 0 else float("inf")


def analyse(campaign: Dict, *, state: str = "CERTIFIED_IN_MODEL") -> Dict:
    main = [r for r in campaign["rows"] if r["block"] == "main"]
    accepted = [r for r in main if r["state"] == state]

    def resolved(row: Dict) -> bool:
        if row["ae_r"] is None:
            return False
        return row["ae_r"] < 0.5 * row["magnitude"]

    failures = [r for r in accepted if not resolved(r)]

    experiments = {(r["action"], r["plant"], r["magnitude"], r["seed"],
                    r["drift_state"]) for r in accepted}
    sharing = collections.Counter(
        (r["action"], r["plant"], r["magnitude"], r["seed"], r["drift_state"])
        for r in accepted)

    denominators = {
        "rows": len(accepted),
        "experiments": len(experiments),
        "seeds": len({r["seed"] for r in accepted}),
    }
    return {
        "state": state,
        "observed_failures": len(failures),
        "failures": failures[:20],
        "denominators": denominators,
        "rule_of_three_95_upper_bound": {
            name: rule_of_three(n) for name, n in denominators.items()},
        "max_arms_sharing_one_experiment": (max(sharing.values())
                                            if sharing else 0),
        "trials_needed_for_1e4_bound": TRIALS_FOR_1E4,
        "shortfall_factor_against_1e4": (
            TRIALS_FOR_1E4 / denominators["experiments"]
            if denominators["experiments"] else None),
        "honest_denominator": "experiments",
        "most_conservative_denominator": "seeds",
        "caveat": (
            "zero observed failures is not a rate of zero. The experiments "
            "denominator assumes distinct simulations are independent, which "
            "they are not: they share seeds, a plant family, one command "
            "library and one declared envelope. The true effective count lies "
            "between 'experiments' and 'seeds' and this tool does not claim "
            "to know where."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", default="validation")
    args = parser.parse_args()
    path = RESULTS / f"CAMPAIGN_{args.partition.upper()}.json"
    if not path.is_file():
        print(f"no campaign artifact at {path.relative_to(ROOT)}")
        return 1
    campaign = json.loads(path.read_text())
    document = {
        "schema": "csia.independent_validation.zero_event_bound/1",
        "source_campaign": str(path.relative_to(ROOT)),
        "partition": campaign["partition"],
        "certified": analyse(campaign),
    }
    out = RESULTS / f"ZERO_EVENT_BOUND_{args.partition.upper()}.json"
    out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    block = document["certified"]
    print(f"observed failures: {block['observed_failures']}")
    for name, n in block["denominators"].items():
        bound = block["rule_of_three_95_upper_bound"][name]
        mark = ""
        if name == block["honest_denominator"]:
            mark = "   <- honest denominator"
        if name == block["most_conservative_denominator"]:
            mark = "   <- most conservative"
        print(f"  n({name:12s}) = {n:6d}   95% upper bound {bound:.3e}{mark}")
    print(f"up to {block['max_arms_sharing_one_experiment']} arms share a "
          "single experiment")
    print(f"short of a 1e-4 bound by a factor of "
          f"{block['shortfall_factor_against_1e4']:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
