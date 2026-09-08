"""Does the SR-006 baro rule fire when baro is fine? Measure it, don't hope.

WHY THIS IS THE DECIDING MEASUREMENT
-------------------------------------
The low-trust threshold was chosen against the CLEAN-flight minimum baro
trust of 0.9930, giving an apparently comfortable margin of 0.243 below the
0.75 threshold. That margin is misleading, and a single control run showed
why: on a flight where **GPS** drops out and baro is untouched, baro trust
falls to **0.8182**. Baro's only trust-graph edge is `altitude_baro`,
spanning (baro, gps) -- so losing GPS costs baro its only source of
corroboration and its trust decays toward the prior through no fault of the
barometer.

Margin against a clean flight: 0.243. Margin against another sensor's
failure: **0.068**. The second number is the one that decides whether this
rule is safe to ship, and it is not obtainable from a clean flight.

So this measures the thing that actually matters: across the campaign's
multi-sensor degradations, **in runs where baro carries no fault at all**,
how often would the baro low-trust rule fire?

    A FALSE ALARM HERE IS WORSE THAN THE GAP IT FILLS. An advisory layer
    that cries wolf on a healthy barometer trains an operator to ignore it,
    and SR-006's gap is at least honest about itself.

The threshold is NOT adjusted by this module whatever the answer is. If the
false-alarm rate is unacceptable the finding is reported and the rule is
withdrawn or re-scoped -- tuning a number until a result looks acceptable is
the failure mode the whole programme is built to avoid.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from csia_stress.campaign import random_profile                 # noqa: E402
from csia_stress.observables import run_profile                 # noqa: E402


def run(count: int = 300, seed: int = 20260907) -> dict:
    from csia_supervision.lowtrust import RULES

    rule = RULES["baro"]
    rows, without_baro_fault = [], 0
    would_fire, fired_names = 0, []
    worst_margin = None

    for i in range(count):
        profile = random_profile(random.Random(seed + i), i)
        targets = {f.target for f in profile.faults}
        if "baro" in targets:
            continue                    # baro IS faulted; not a false alarm
        without_baro_fault += 1

        result = run_profile(profile, supervised=True)
        baro_min = result.min_trust.get("baro")
        if baro_min is None:
            continue
        margin = baro_min - rule.threshold
        worst_margin = margin if worst_margin is None \
            else min(worst_margin, margin)
        if baro_min < rule.threshold:
            would_fire += 1
            fired_names.append({
                "profile": profile.id,
                "faulted_targets": sorted(targets),
                "fault_kinds": sorted({f.kind for f in profile.faults}),
                "baro_min_trust": round(baro_min, 4)})
        rows.append(round(baro_min, 4))

    rows.sort()

    def pct(p):
        if not rows:
            return None
        return rows[max(0, min(len(rows) - 1, int(p * len(rows))))]

    rate = (would_fire / without_baro_fault) if without_baro_fault else None
    return {
        "schema": "csia.stress.low_trust_false_alarm/1",
        "count_requested": count,
        "runs_without_a_baro_fault": without_baro_fault,
        "threshold": rule.threshold,
        "threshold_borrowed_from": rule.borrowed_from,
        "clean_flight_min_trust": rule.clean_flight_min_trust,
        "would_fire": would_fire,
        "false_alarm_rate": rate,
        "worst_margin_above_threshold": (round(worst_margin, 4)
                                         if worst_margin is not None else None),
        "baro_min_trust_percentiles": {
            "p00": pct(0.0), "p01": pct(0.01), "p05": pct(0.05),
            "p50": pct(0.5), "p95": pct(0.95)},
        "examples": fired_names[:10],
        "why_a_clean_flight_is_not_enough": (
            "baro's only trust-graph edge is `altitude_baro`, spanning "
            "(baro, gps). Losing GPS removes baro's only corroboration and "
            "its trust decays toward the prior with nothing wrong with the "
            "barometer. Clean-flight margin 0.243; margin under another "
            "sensor's failure was measured at 0.068 in a single control "
            "run, which is what prompted this campaign."),
        "nothing_is_tuned_by_this_module": (
            "whatever the rate, the threshold is not adjusted here. An "
            "unacceptable rate is reported and the rule withdrawn or "
            "re-scoped; moving the number until the answer looks right is "
            "the failure mode this programme exists to avoid."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--count", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260907)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    rep = run(args.count, args.seed)
    if args.out:
        path = os.path.join(ROOT, args.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")

    print(f"runs without a baro fault: {rep['runs_without_a_baro_fault']}")
    print(f"would fire (FALSE ALARMS): {rep['would_fire']}"
          f"  rate={rep['false_alarm_rate']}")
    print(f"worst margin above {rep['threshold']}: "
          f"{rep['worst_margin_above_threshold']}")
    print(f"baro min-trust percentiles: {rep['baro_min_trust_percentiles']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
