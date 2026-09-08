"""Does the SR-006 baro rule fire when baro is fine? Measure it, don't hope.

WHY THIS IS THE DECIDING MEASUREMENT
-------------------------------------
The low-trust threshold was chosen against the CLEAN-flight minimum baro
trust of 0.9930. A clean flight is the easy case; the question that decides
whether the rule is safe to enable is what happens to baro when a DIFFERENT
sensor fails. Baro's only trust-graph edge is `altitude_baro`, spanning
(baro, gps), so it is not obvious that baro's trust survives a GPS failure
with nothing wrong with the barometer.

So this measures the thing that actually matters: across the campaign's
multi-sensor degradations, **in runs where baro carries no fault at all**,
how often would the baro low-trust rule fire?

A CORRECTION THIS MODULE EXISTS TO RECORD
------------------------------------------
The first version of this measurement read `StressRun.min_trust`, which is
the minimum over the WHOLE run including warm-up from the 0.8 Beta prior. It
reported 0.8182 and that was taken as evidence of exactly the feared
mechanism -- GPS loss starving baro of corroboration, leaving a margin of
only 0.068 above the threshold.

**That was a misreading.** 0.8182 is 9/11 to four decimals and appears in
EVERY campaign run whatever is faulted: runs degrading only battery and
imu1, GPS entirely healthy, report the identical value. It is the warm-up
floor as trust climbs off the prior, and it says nothing about fault
response at all. The rule cannot fire before `arm_time` anyway, so it was
also the wrong window.

Measured over the armed window instead, baro's minimum in runs without a
baro fault is **0.993** -- the clean-flight figure. Another sensor's failure
does not degrade baro. Margin 0.243, not 0.068.

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


def _post_arm_min_trust(profile, sensor: str):
    """Minimum trust AFTER `arm_time`, which is the only window that matters.

    `StressRun.min_trust` is the minimum over the WHOLE run, warm-up
    included. Trust starts at the 0.8 Beta prior and climbs, so that
    minimum is an early-flight artifact -- measured at exactly 0.8182
    (9/11) in every campaign run regardless of which sensors are faulted.

    THIS CORRECTS A MISREADING. That constant was first taken as evidence
    that losing GPS starves baro of its only corroborating edge and drags
    its trust down. It is nothing of the kind: runs faulting only battery
    and imu1, with GPS perfectly healthy, report the same 0.8182. The
    number is the warm-up floor and says nothing about fault response.

    The rule cannot fire before `arm_time`, so the margin that decides the
    false-alarm question is the minimum over the ARMED window alone.
    """
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.online import OnlineTrustLayer
    from csia_stress.source import StressFlightSource

    arm = FailsafeConfig().arm_time
    source = StressFlightSource(faults=profile.faults, truth=None,
                                flight_profile=profile.flight_profile,
                                duration=profile.duration)
    layer = OnlineTrustLayer()
    worst, last = None, 0.0
    for name, t, channels in source.samples():
        for state in layer.ingest(name, t, channels):
            if float(state.t) < arm:
                continue
            value = state.trust.get(sensor)
            if value is not None:
                worst = float(value) if worst is None \
                    else min(worst, float(value))
        last = t
    for state in layer.flush(last):
        if float(state.t) >= arm:
            value = state.trust.get(sensor)
            if value is not None:
                worst = float(value) if worst is None \
                    else min(worst, float(value))
    return worst


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

        baro_min = _post_arm_min_trust(profile, "baro")
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
        "measurement_window": (
            "minimum baro trust AFTER arm_time, which is the only window "
            "the rule can fire in. StressRun.min_trust spans the whole run "
            "including warm-up from the 0.8 prior, and that whole-run "
            "minimum is 0.8182 (9/11) in EVERY campaign run whatever is "
            "faulted -- an early-flight artifact, not a fault response. "
            "Reading it as GPS starving baro of its only corroborating edge "
            "was a misreading, corrected here: runs faulting only battery "
            "and imu1, GPS healthy, report the identical 0.8182."),
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
