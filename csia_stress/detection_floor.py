"""At what magnitude does each fault become detectable? Sweep and publish it.

WHY THIS EXISTS
---------------
The supervision measurement left 31 misses out of 1000 variations, and every
one is a sub-threshold `bias_drift`. There are two ways to make that number
go away:

  1. lower the frozen thresholds until the misses detect -- which is
     retuning a frozen core to rescue a result, and is not done here;
  2. find out WHERE the boundary actually is and publish it.

This module does the second. A miss below a stated detection floor is not a
failure of the system; it is the system operating outside the envelope it
declares. A miss with NO stated floor is just a failure. The difference is
entirely whether somebody measured the boundary, and that is what converts
31 unexplained misses into a capability limit an XR-1 mission planner can
actually use.

WHAT IS SWEPT
-------------
One fault at a time, at rising magnitude, on a clean flight otherwise. Single
faults, deliberately: a floor measured under simultaneous degradation would
confound "too small to see" with "masked by something else", and the whole
point is a number that means one thing.

WHAT THE FLOOR IS, PRECISELY
-----------------------------
The smallest swept magnitude at which the run escalates above NORMAL, with
every larger swept magnitude also escalating. That last clause matters: a
lone detection surrounded by misses is noise, not a boundary, and is reported
as `NON_MONOTONIC` rather than quietly taken as the floor.

    UNDETECTED_AT_EVERY_MAGNITUDE  the sweep never escalated -- the floor is
                                   above the swept range, and is NOT reported
                                   as a number
    NON_MONOTONIC                  detection is not a step function over
                                   magnitude; no single floor is meaningful
    <a number>                     the boundary, in the fault's own units

**NOTHING IS TUNED BY THIS MODULE.** It measures the frozen core as it
stands. The sweep ranges are declared here, before any run, and a range that
turns out to bracket nothing is reported as such rather than widened until it
produces a pleasing answer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from csia.sensors.faults import Fault                     # noqa: E402
from csia_stress.applicability import matrix              # noqa: E402
from csia_stress.observables import (DETECTED,               # noqa: E402
                                     NOT_DETECTED, run_profile)
from csia_stress.profiles import StressProfile            # noqa: E402

UNDETECTED = "UNDETECTED_AT_EVERY_MAGNITUDE"
NON_MONOTONIC = "NON_MONOTONIC"
#: The failsafe never escalated, but the TRUST LAYER responded clearly.
#: The fault was seen; no failsafe rule names that sensor. This is the
#: SR-001 family, not a sensing limit, and the two must never be reported
#: as the same thing.
TRUST_RESPONDS_NO_RULE = "TRUST_RESPONDS_BUT_NO_FAILSAFE_RULE"

#: DECLARED BEFORE THE RUN. The campaign draws bias_drift rates from
#: [0.03, 0.20]; the sweep starts below that and runs above it, so a floor
#: inside the campaign's own range is bracketed rather than assumed.
SWEEP: dict = {
    "bias_drift": {
        "param": "rate",
        "values": (0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.16, 0.20,
                   0.30, 0.45, 0.70, 1.00),
        "unit": "sensor units per second",
        "fixed": {"axis": 2, "channel": "accel"},
    },
    # DECLARED BEFORE THE RUN, same rule as above. The campaign draws
    # rpm_loss from [150, 700]; the grid starts well below and runs well
    # above, so a floor inside the campaign's range is bracketed rather
    # than assumed. depth_v is held at the campaign's midpoint so the swept
    # parameter is the motor-side magnitude alone.
    "power_sag": {
        "param": "rpm_loss",
        "values": (25.0, 50.0, 100.0, 150.0, 250.0, 350.0, 500.0, 700.0,
                   1000.0, 1500.0, 2200.0, 3000.0),
        "unit": "rpm lost",
        "fixed": {"depth_v": 1.3},
    },
}

#: Fault onset and length inside the flight. Long enough that the failsafe's
#: 1 s escalation dwell cannot be the thing that decides the answer.
ONSET = 20.0
DURATION = 40.0
FLIGHT = 90.0


class SweepInstrumentError(RuntimeError):
    """The sweep could not measure a point.

    RAISED, NEVER RECORDED AS A MISS. The first version of this module
    caught every exception per point and stored it as a point with no
    verdict; those points then read as "not detected", and the sweep
    reported UNDETECTED_AT_EVERY_MAGNITUDE for all four pairs. The cause
    was an AttributeError on the wrong field name -- an instrument bug
    presented as a finding about the frozen core. A sweep that cannot
    measure must stop, not produce a tidy column of zeroes.
    """


def _run_one(kind: str, target: str, value, spec, supervised: bool) -> tuple:
    params = dict(spec.get("fixed", {}))
    params[spec["param"]] = value
    profile = StressProfile(
        id=f"floor-{kind}-{target}-{value}",
        summary=f"single {kind} on {target} at {spec['param']}={value}",
        faults=(Fault(kind, target, ONSET, DURATION, params),),
        duration=FLIGHT,
        represents="a magnitude sweep point, not a flight scenario",
        does_not_represent="any real degradation profile; it is one fault "
                           "held at one magnitude to locate a boundary",
    )
    run = run_profile(profile, supervised=supervised)
    # `detection_status`, not a boolean `detected` -- there is no such
    # attribute, and asking for one is what produced the false negative
    # sweep. Compared against the declared constant rather than a string
    # literal so a rename cannot silently make everything "not detected".
    if run.detection_status not in (DETECTED, NOT_DETECTED):
        raise SweepInstrumentError(
            f"unexpected detection_status {run.detection_status!r}")
    # THE TARGET'S TRUST, not just the failsafe level. "the layer did not
    # see it" and "the layer saw it and no rule names that sensor" are
    # completely different findings, and a boolean cannot tell them apart.
    trust = run.min_trust.get(target)
    if trust is None:
        raise SweepInstrumentError(
            f"{target} has no trust value in the run; the sweep cannot say "
            "whether the layer responded")
    return run.detection_status == DETECTED, float(trust)


def sweep_one(kind: str, target: str, supervised: bool = False) -> dict:
    """Sweep one (kind, target) pair and locate its floor."""
    spec = SWEEP[kind]
    points = []
    for value in spec["values"]:
        # NO try/except HERE, DELIBERATELY. An error must reach the caller
        # and stop the sweep; swallowing it turns a broken instrument into
        # a published "undetected".
        detected, min_trust = _run_one(kind, target, value, spec, supervised)
        points.append({"value": value, "detected": bool(detected),
                       "min_trust": round(min_trust, 4)})

    seen = [p for p in points if "detected" in p]
    if len(seen) != len(spec["values"]):            # pragma: no cover
        raise SweepInstrumentError(
            f"{kind}@{target}: {len(seen)} of {len(spec['values'])} points "
            "produced a verdict; a partial sweep cannot locate a floor")
    detected_values = [p["value"] for p in seen if p["detected"]]

    # Did the TRUST LAYER respond, whatever the failsafe did? The prior is
    # 0.8, so a fall well below it is a response by any reading.
    trusts = [p["min_trust"] for p in seen]
    responded = min(trusts) < 0.6

    if not detected_values:
        floor = None
        # THE DISTINCTION THAT MATTERS. If trust collapsed and the level
        # never moved, the layer saw the fault perfectly well and no
        # failsafe rule names that sensor. Reporting that as "undetected"
        # would blame the wrong component and hide a real, fixable gap.
        shape = TRUST_RESPONDS_NO_RULE if responded else UNDETECTED
    else:
        first = min(detected_values)
        # MONOTONIC means: once it detects, it keeps detecting. A single
        # detection with misses above it is not a boundary.
        above = [p for p in seen if p["value"] >= first]
        shape = "MONOTONIC" if all(p["detected"] for p in above) \
            else NON_MONOTONIC
        floor = first if shape == "MONOTONIC" else None

    return {
        "kind": kind,
        "target": target,
        "param": spec["param"],
        "unit": spec["unit"],
        "supervised": supervised,
        "detection_floor": floor,
        "shape": shape,
        "swept": list(spec["values"]),
        "points": points,
        "floor_means": (
            "the smallest SWEPT magnitude that escalated, with every larger "
            "swept magnitude also escalating. It is bounded by the sweep "
            "grid: the true boundary lies between this value and the one "
            "below it, and no interpolation is done."),
    }


#: What the 1000-variation campaign actually draws from, taken from
#: csia_stress.campaign.RANDOM_PARAMS rather than restated here.
def _campaign_range(kind: str, param: str):
    from csia_stress.campaign import RANDOM_PARAMS
    import random
    fn = RANDOM_PARAMS.get(kind)
    if fn is None:
        return None
    rng = random.Random(20260907)
    drawn = [fn(rng).get(param) for _ in range(2000)]
    drawn = [d for d in drawn if isinstance(d, (int, float))]
    return (min(drawn), max(drawn)) if drawn else None


def _campaign_comparison(results) -> dict:
    """Does the campaign ever draw a magnitude the core could detect?

    A pair whose whole sampling range sits BELOW its floor can never be
    detected in that campaign, and its misses are the envelope being
    reported honestly rather than a failure.

    NOT A PER-RUN ATTRIBUTION. Campaign variations carry 2-4 simultaneous
    faults, so the recorded per-target miss counts are TARGETS INVOLVED in a
    missed run, not causes of it -- they sum to more than the number of
    missed runs. This block says which pairs are structurally out of reach,
    which is a weaker and defensible claim.
    """
    out = {}
    for r in results:
        rng = _campaign_range(r["kind"], r["param"])
        if rng is None:
            continue
        lo, hi = rng
        floor = r["detection_floor"]
        if floor is None:
            reach = ("NEVER_ESCALATES" if r["shape"] == TRUST_RESPONDS_NO_RULE
                     else "FLOOR_ABOVE_SWEPT_RANGE")
        elif hi < floor:
            reach = "ENTIRE_CAMPAIGN_RANGE_BELOW_FLOOR"
        elif lo >= floor:
            reach = "ENTIRE_CAMPAIGN_RANGE_AT_OR_ABOVE_FLOOR"
        else:
            reach = "CAMPAIGN_RANGE_STRADDLES_FLOOR"
        out[f"{r['kind']}@{r['target']}"] = {
            "campaign_draws": [lo, hi], "floor": floor, "reach": reach,
            "shape": r["shape"]}
    return out


def run(supervised: bool = False) -> dict:
    """Sweep every live (kind, target) pair the sweep declares parameters for.

    Only LIVE pairs: a pair that does not perturb the sampled stream has no
    detection floor to find, and sweeping it would produce a tidy row of
    misses that reads exactly like a real insensitivity.
    """
    live = [(k, t) for k, t in matrix().live_pairs() if k in SWEEP]
    results = [sweep_one(k, t, supervised) for k, t in sorted(live)]

    floors = {f"{r['kind']}@{r['target']}": r["detection_floor"]
              for r in results}
    undetected = sorted(k for k, v in floors.items() if v is None)

    return {
        "schema": "csia.stress.detection_floor/1",
        "supervised": supervised,
        "onset_s": ONSET, "fault_duration_s": DURATION,
        "flight_duration_s": FLIGHT,
        "pairs_swept": [f"{k}@{t}" for k, t in sorted(live)],
        "pairs_not_swept": sorted(
            f"{k}@{t}" for k, t in matrix().live_pairs() if k not in SWEEP),
        "detection_floors": floors,
        "no_floor_found": undetected,
        "campaign_range_vs_floor": _campaign_comparison(results),
        "shape_by_pair": {f"{r['kind']}@{r['target']}": r["shape"]
                          for r in results},
        "trust_responded_but_no_rule": sorted(
            f"{r['kind']}@{r['target']}" for r in results
            if r["shape"] == TRUST_RESPONDS_NO_RULE),
        "results": results,
        "nothing_was_tuned": (
            "this measures the frozen core as it stands. No threshold, "
            "weight, prior or dwell was changed to produce these numbers, "
            "and the sweep grid was declared before the first run."),
        "how_to_read_a_miss": (
            "a miss BELOW a published floor is the system operating outside "
            "its declared envelope, which is a limit. A miss ABOVE one is a "
            "defect. Without a published floor every miss looks like the "
            "second, which is why these were measured."),
        "single_fault_only": (
            "each point is ONE fault on a clean flight. A floor measured "
            "under simultaneous degradation would confound 'too small to "
            "detect' with 'masked by another fault'."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--supervised", action="store_true",
                    help="measure with the data-loss overlay on top")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    rep = run(supervised=args.supervised)
    if args.out:
        path = os.path.join(ROOT, args.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")

    print(f"detection floors (supervised={rep['supervised']}):")
    for r in rep["results"]:
        floor = r["detection_floor"]
        shown = f"{floor:g} {r['unit']}" if floor is not None else r["shape"]
        worst = min(p["min_trust"] for p in r["points"])
        print(f"  {r['kind']}@{r['target']:8s} {r['param']:>6s}  {shown}"
              f"   (worst trust {worst:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
