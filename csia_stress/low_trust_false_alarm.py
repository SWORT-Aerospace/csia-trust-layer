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


def run(count: int = 300, seed: int = 20260907,
        sensor: str = "baro", threshold: float | None = None) -> dict:
    """Measure the false-alarm rate for one sensor's low-trust rule.

    `threshold` may be given for a CANDIDATE rule that is not yet shipped --
    the whole point is to measure before enabling, not after.
    """
    from csia_supervision.lowtrust import RULES

    rule = RULES.get(sensor)
    if rule is None and threshold is None:
        raise ValueError(
            f"no shipped rule for {sensor!r} and no candidate threshold "
            "given; refusing to invent one")
    limit = float(threshold if threshold is not None else rule.threshold)
    rows, without_baro_fault = [], 0
    would_fire, fired_names = 0, []
    worst_margin, worst_run = None, None

    for i in range(count):
        profile = random_profile(random.Random(seed + i), i)
        targets = {f.target for f in profile.faults}
        if sensor in targets:
            continue           # the sensor IS faulted; not a false alarm
        without_baro_fault += 1

        baro_min = _post_arm_min_trust(profile, sensor)
        if baro_min is None:
            continue
        margin = baro_min - limit
        if worst_margin is None or margin < worst_margin:
            worst_margin = margin
            # WHICH RUN produced the worst margin. Reporting a thin margin
            # without naming the combination that caused it leaves a reader
            # unable to judge whether it is a plausible flight or a corner.
            worst_run = {"profile": profile.id,
                         "faulted_targets": sorted(targets),
                         "fault_kinds": sorted({f.kind
                                                for f in profile.faults}),
                         "min_trust": round(baro_min, 4),
                         "margin": round(margin, 4)}
        if baro_min < limit:
            would_fire += 1
            fired_names.append({
                "profile": profile.id,
                "faulted_targets": sorted(targets),
                "fault_kinds": sorted({f.kind for f in profile.faults}),
                "min_trust": round(baro_min, 4)})
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
        "sensor": sensor,
        "threshold": limit,
        "is_a_shipped_rule": rule is not None,
        "threshold_borrowed_from": (rule.borrowed_from if rule else
                                    "CANDIDATE -- not yet shipped"),
        "clean_flight_min_trust": (rule.clean_flight_min_trust
                                   if rule else None),
        "would_fire": would_fire,
        "false_alarm_rate": rate,
        "worst_margin_above_threshold": (round(worst_margin, 4)
                                         if worst_margin is not None else None),
        "min_trust_percentiles": {
            "p00": pct(0.0), "p01": pct(0.01), "p05": pct(0.05),
            "p50": pct(0.5), "p95": pct(0.95)},
        "examples": fired_names[:10],
        "worst_run": worst_run,
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


INSTRUMENT = "csia_stress.low_trust_false_alarm"


def _controls():
    """The pair this measurement must pass before it may write anything.

    THE NEGATIVE CONTROL IS THE ONE THAT MATTERS HERE, because it is exactly
    the check that would have caught SR-007's misreading on the first run.
    On a profile faulting battery and imu1 -- baro untouched, GPS healthy --
    a correct armed-window measurement returns baro's clean-flight figure,
    above 0.9. The broken version, reading a whole-run minimum that spans
    warm-up from the 0.8 prior, returned 0.8182 and would fail this control
    instead of being reported as a physical mechanism.

    The POSITIVE control drives a severe drift into baro and requires the
    measurement to see it fall below the rule's own threshold: an instrument
    that returns a healthy-looking number whatever is happening is the
    failure this pairs against.
    """
    from csia.sensors.faults import Fault
    from csia_stress.profiles import StressProfile
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _profile(faults, name):
        return StressProfile(
            id=name, summary="instrument control", duration=90.0,
            faults=faults, represents="an instrument control, not a flight",
            does_not_represent="any degradation profile of interest")

    def positive():
        return _post_arm_min_trust(_profile(
            (Fault("bias_drift", "baro", 20.0, 40.0,
                   {"axis": 2, "rate": 1.0, "channel": "accel"}),),
            "control-baro-drift"), "baro")

    def negative():
        return _post_arm_min_trust(_profile(
            (Fault("power_sag", "battery", 20.0, 40.0,
                   {"depth_v": 1.3, "rpm_loss": 350.0}),
             Fault("bias_drift", "imu1", 20.0, 40.0,
                   {"axis": 2, "rate": 0.20, "channel": "accel"})),
            "control-baro-untouched"), "baro")

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a severe baro drift is seen as low trust",
            kind=POSITIVE,
            run=positive,
            expect=lambda v: v is not None and v < 0.75,
            basis=("SR-006 measured this stimulus driving a 327 m altitude "
                   "error with baro trust at 0.231, by a separate "
                   "instrument (the magnitude sweep) -- not by this one"),
        ),
        negative=Control(
            name="an untouched baro reads healthy while others fail",
            kind=NEGATIVE,
            run=negative,
            expect=lambda v: v is not None and v > 0.9,
            basis=("baro's clean-flight minimum is 0.9930, measured "
                   "directly from the trust layer; nothing in this profile "
                   "faults baro or its gps partner. A value near 0.8182 is "
                   "the warm-up floor of the 0.8 prior, which is the "
                   "SR-007 defect"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--count", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260907)
    ap.add_argument("--sensor", default="baro")
    ap.add_argument("--threshold", type=float, default=None,
                    help="measure a CANDIDATE threshold before shipping it")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    # CONTROLS FIRST, AND THEY RAISE.
    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    control_report = guard(INSTRUMENT)
    print(f"instrument controls: {control_report['verdict']}")

    rep = stamp(run(args.count, args.seed, args.sensor, args.threshold),
                control_report)
    if args.out:
        path = os.path.join(ROOT, args.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")

    print(f"sensor: {rep['sensor']}  threshold {rep['threshold']}"
          f"  shipped={rep['is_a_shipped_rule']}")
    print(f"runs without a {rep['sensor']} fault: "
          f"{rep['runs_without_a_baro_fault']}")
    print(f"would fire (FALSE ALARMS): {rep['would_fire']}"
          f"  rate={rep['false_alarm_rate']}")
    print(f"worst margin above {rep['threshold']}: "
          f"{rep['worst_margin_above_threshold']}")
    print(f"min-trust percentiles: {rep['min_trust_percentiles']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
