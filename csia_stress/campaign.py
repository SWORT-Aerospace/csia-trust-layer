"""Run many stress profiles and record what happened.

TWO MODES
---------
`catalog`  -- the named profiles in `profiles.py`, which are the cases a
              human chose and can argue about.
`random`   -- thousands of generated combinations, which is the only way to
              cover a space nobody has hand-picked. Seeded, so a run is
              reproducible and a failing variation can be replayed by id.

WHAT A RANDOM VARIATION IS ALLOWED TO BE
----------------------------------------
Only LIVE (kind, target) pairs from the measured applicability matrix, and
only windows that leave the failsafe's de-escalation dwell room to be
observed. A generator that emitted inert faults would manufacture clean
results at scale, which is worse than not running it: it would put a large
confident number behind nothing.

WHAT THE RESULT IS NOT
----------------------
This is a simulation campaign against simulated sensors. It is NOT
software-in-the-loop -- no autopilot is executed, ArduPilot is not present
in this environment -- and it is NOT hardware-in-the-loop. Those are
recorded as not-run in the report rather than approximated.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from csia.runtime.failsafe import FailsafeConfig            # noqa: E402
from csia.sensors.faults import Fault                       # noqa: E402
from csia_stress.applicability import matrix                # noqa: E402
from csia_stress.observables import (DETECTED,              # noqa: E402
                                     NOT_DETECTED, RECOVERED, run_profile)
from csia_stress.profiles import (FLIGHT_PROFILES,          # noqa: E402
                                  UNMODELLED, StressProfile, catalog)

#: Parameters used when generating a random fault of each kind. Ranges are
#: declared here, before any run, and are not adjusted after seeing results.
RANDOM_PARAMS = {
    "bias_drift": lambda r: {"axis": r.choice([0, 1, 2]),
                             "rate": round(r.uniform(0.03, 0.20), 4),
                             "channel": "accel"},
    "dropout": lambda r: {},
    "emi_spike": lambda r: {"amplitude": round(r.uniform(4.0, 18.0), 3),
                            "rate_hz": round(r.uniform(5.0, 20.0), 3)},
    "gps_spoof": lambda r: {"drift": (round(r.uniform(-4, 4), 3),
                                      round(r.uniform(-4, 4), 3), 0.0)},
    "vibration_anomaly": lambda r: {"gain": round(r.uniform(1.8, 4.5), 3)},
    "power_sag": lambda r: {"depth_v": round(r.uniform(0.6, 2.0), 3),
                            "rpm_loss": round(r.uniform(150.0, 700.0), 1)},
}

FLIGHT_DURATION = 90.0


def random_profile(rng: random.Random, index: int) -> StressProfile:
    """One reproducible variation built only from LIVE pairs."""
    live = matrix().live_pairs()
    n = rng.choice([2, 2, 3, 3, 4])          # always multi-fault: this is MSRD
    # Distinct targets, so a variation degrades several sensors rather than
    # stacking two faults on one.
    chosen, used = [], set()
    for kind, target in rng.sample(live, k=len(live)):
        if target in used:
            continue
        chosen.append((kind, target))
        used.add(target)
        if len(chosen) == n:
            break

    dwell = FailsafeConfig().dwell_down
    faults = []
    for kind, target in chosen:
        start = round(rng.uniform(15.0, 40.0), 2)
        # Leave strictly more than the dwell after the last fault clears, so
        # every generated profile can answer its own recovery question.
        max_dur = FLIGHT_DURATION - dwell - 1.0 - start
        duration = round(rng.uniform(6.0, max(7.0, min(30.0, max_dur))), 2)
        faults.append(Fault(kind, target, start, duration,
                            RANDOM_PARAMS[kind](rng)))

    return StressProfile(
        id=f"rand_{index:05d}",
        summary=f"generated variation {index}",
        faults=tuple(faults),
        flight_profile=rng.choice(FLIGHT_PROFILES),
        duration=FLIGHT_DURATION,
        classes=("generated",),
        represents="a randomly composed multi-sensor degradation",
    )


def summarise(runs: list) -> dict:
    detected = [r for r in runs if r.detection_status == DETECTED]
    missed = [r for r in runs if r.detection_status == NOT_DETECTED]
    recovered = [r for r in runs if r.recovery_status == RECOVERED]
    lat = sorted(r.detection_latency_s for r in detected)
    rec = sorted(r.recovery_time_s for r in recovered)

    def pct(values, q):
        if not values:
            return None
        return round(values[min(len(values) - 1, int(q * len(values)))], 4)

    return {
        "runs": len(runs),
        "detected": len(detected),
        "not_detected": len(missed),
        "not_detected_ids": sorted(r.profile_id for r in missed)[:50],
        "recovered": len(recovered),
        "recovery_status_counts": _counts(r.recovery_status for r in runs),
        "peak_level_counts": _counts(r.peak_level_name for r in runs),
        "detection_latency_s": {
            "min": lat[0] if lat else None, "p50": pct(lat, 0.5),
            "p95": pct(lat, 0.95), "max": lat[-1] if lat else None},
        "recovery_time_s": {
            "min": rec[0] if rec else None, "p50": pct(rec, 0.5),
            "p95": pct(rec, 0.95), "max": rec[-1] if rec else None},
        "attribution": {
            "runs_with_a_nameable_target_never_named": sum(
                1 for r in runs
                if r.attribution["targets_nameable_but_never_named"]),
            "runs_with_a_structurally_unnameable_target": sum(
                1 for r in runs
                if r.attribution["targets_structurally_unnameable"]),
        },
        "NOT_DETECTED_IS_NOT_A_PASS": (
            "a profile that injected live faults and never tripped the "
            "failsafe is a finding, not a success. It is counted here and "
            "listed by id."),
    }


def _counts(values) -> dict:
    out: dict = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


INSTRUMENT = "csia_stress.campaign"


def _controls():
    """The campaign must still detect what the frozen policy names.

    POSITIVE is a GPS dropout, which the FROZEN policy carries an explicit
    "GPS data invalid" rule for. NEGATIVE is a bias drift of rate ZERO,
    which perturbs nothing by arithmetic. A campaign that has stopped
    detecting, or that detects everything, produces a summary table that
    looks entirely normal.
    """
    from csia.sensors.faults import Fault
    from csia_stress.observables import DETECTED, run_profile
    from csia_stress.profiles import StressProfile
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _status(faults, name):
        profile = StressProfile(
            id=name, summary="instrument control", duration=90.0,
            faults=faults, represents="an instrument control, not a flight",
            does_not_represent="any degradation profile of interest")
        return run_profile(profile).detection_status

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a gps dropout is detected",
            kind=POSITIVE,
            run=lambda: _status(
                (Fault("dropout", "gps", 20.0, 40.0, {}),), "ctl-gps"),
            expect=lambda st: st == DETECTED,
            basis=("the frozen FailsafePolicy carries an explicit 'GPS data "
                   "invalid' rule; the escalation follows from that rule"),
        ),
        negative=Control(
            name="a zero-rate drift is not detected",
            kind=NEGATIVE,
            run=lambda: _status(
                (Fault("bias_drift", "imu0", 20.0, 40.0,
                       {"axis": 2, "rate": 0.0, "channel": "accel"}),),
                "ctl-null"),
            expect=lambda st: st != DETECTED,
            basis=("the fault model applies rate*elapsed; a rate of zero "
                   "perturbs nothing, by arithmetic"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=("catalog", "random"), default="catalog")
    ap.add_argument("--count", type=int, default=250,
                    help="number of generated variations (random mode)")
    ap.add_argument("--seed", type=int, default=20260907)
    ap.add_argument("--out", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    # CONTROLS FIRST, AND THEY RAISE. An instrument that cannot
    # demonstrate it still works may not emit an artifact (MX-025).
    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    _control_report = guard(INSTRUMENT)

    import logging
    if args.quiet:
        logging.disable(logging.CRITICAL)

    mtx = matrix()
    t0 = time.perf_counter()

    if args.mode == "catalog":
        profiles = list(catalog())
    else:
        rng = random.Random(args.seed)
        profiles = [random_profile(rng, i) for i in range(args.count)]

    runs, failures = [], []
    for p in profiles:
        try:
            runs.append(run_profile(p))
        except Exception as exc:                        # noqa: BLE001
            # Recorded, never swallowed: a variation that CRASHED the layer
            # is the most interesting result a campaign can produce.
            failures.append({"profile_id": p.id, "error": repr(exc)[:300],
                             "profile": p.to_dict()})

    elapsed = time.perf_counter() - t0
    report = {
        "schema": "csia.stress.campaign/1",
        "mode": args.mode,
        "seed": args.seed if args.mode == "random" else None,
        "elapsed_s": round(elapsed, 2),
        "applicability": mtx.summary(),
        "summary": summarise(runs),
        "crashes": failures,
        "runs": [r.to_dict() for r in runs],
        "profiles": [p.to_dict() for p in profiles],
        "unmodelled": [
            {"id": u.id, "why_not": u.why_not,
             "nearest_available": u.nearest_available,
             "why_the_nearest_is_not_it": u.why_the_nearest_is_not_it}
            for u in UNMODELLED],
        "what_this_is_not": {
            "software_in_the_loop": (
                "NOT RUN. No autopilot is executed. ArduPilot is not "
                "installed in the environment that produced this file and "
                "could not be fetched, so no SITL result is claimed."),
            "hardware_in_the_loop": (
                "NOT RUN. E2 is blocked on physical hardware the user must "
                "supply; see the E1 freeze manifest."),
            "why_it_still_matters": (
                "the frozen core under test is the same code either way. "
                "This campaign exercises it against simulated degradation, "
                "which bounds its behaviour without establishing anything "
                "about a real airframe."),
        },
    }

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        report = stamp(report, _control_report)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"wrote {args.out}")

    s = report["summary"]
    print(json.dumps({k: s[k] for k in (
        "runs", "detected", "not_detected", "recovery_status_counts",
        "peak_level_counts", "detection_latency_s", "recovery_time_s")},
        indent=2))
    if failures:
        print(f"\nCRASHES: {len(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
