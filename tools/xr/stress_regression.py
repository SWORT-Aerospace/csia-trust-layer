"""An EXACT regression gate on stress behaviour, including recovery time.

WHY THIS NEEDS NO TOLERANCE
---------------------------
The stress campaign is bit-for-bit deterministic: fixed sensor seeds, a
seeded profile generator, and a frozen core. Running it twice at the same
seed and count produces byte-identical summaries, runs and profiles --
verified, not assumed (`test_the_campaign_is_bit_for_bit_deterministic`).

So this gate does not need a tolerance band, and it does not have one. Any
difference in any run's outcome is reported. That is a much stronger check
than "the p95 recovery time did not move more than X", because a tolerance
band is exactly where a real behavioural change hides.

WHAT COUNTS AS A CHANGE
-----------------------
Per profile: whether it escalated, the peak failsafe level, the detection
latency, the recovery status, the recovery time, and which targets the
diagnosis named. A change in any of them is listed with its before and
after. Nothing is aggregated away -- an aggregate that stays still while
two runs swap outcomes is the failure mode this avoids.

NOT COMPARABLE IS NOT PASS
--------------------------
A baseline recorded at a different seed, count, or applicability matrix is
not a baseline for this run. The gate says so and exits non-zero rather
than comparing two different experiments -- the same rule the quality
ratchet learned in MX-015.

    python tools/xr/stress_regression.py --check
    python tools/xr/stress_regression.py --update    # re-baseline, deliberately
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

BASELINE = os.path.join(ROOT, "research", "stress", "results",
                        "STRESS_BASELINE.json")

#: Fixed so the gate is reproducible. Changing either makes the stored
#: baseline NOT COMPARABLE, which is reported rather than absorbed.
SEED = 20260907
COUNT = 200

#: The per-run fields compared. Recovery time is in here, which is what
#: makes this a recovery-time regression gate.
COMPARED = ("escalated", "peak_failsafe_level_name", "detection_latency_s",
            "recovery_status", "recovery_time_s", "targets_named",
            "targets_nameable_but_never_named")


def run_campaign(count: int = COUNT, seed: int = SEED) -> dict:
    import logging
    logging.disable(logging.CRITICAL)
    import random

    from csia_stress.applicability import matrix
    from csia_stress.campaign import random_profile
    from csia_stress.observables import run_profile

    rng = random.Random(seed)
    profiles = [random_profile(rng, i) for i in range(count)]
    out = {}
    for profile in profiles:
        run = run_profile(profile)
        out[profile.id] = {
            "escalated": run.escalated,
            "peak_failsafe_level_name": run.peak_level_name,
            "detection_latency_s": run.detection_latency_s,
            "recovery_status": run.recovery_status,
            "recovery_time_s": run.recovery_time_s,
            "targets_named": run.attribution["targets_named"],
            "targets_nameable_but_never_named":
                run.attribution["targets_nameable_but_never_named"],
        }
    return {
        "schema": "csia.stress.baseline/1",
        "seed": seed,
        "count": count,
        "applicability_fingerprint": _applicability_fingerprint(matrix()),
        "runs": out,
    }


def _applicability_fingerprint(mtx) -> str:
    import hashlib
    payload = json.dumps({"live": [list(p) for p in mtx.live_pairs()],
                          "lost": [list(p) for p in mtx.lost_in_transport()]},
                         sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compare(measured: dict, baseline: dict) -> dict:
    not_comparable = []
    for field in ("seed", "count", "applicability_fingerprint"):
        if measured.get(field) != baseline.get(field):
            not_comparable.append({
                "field": field,
                "baseline": baseline.get(field),
                "measured": measured.get(field),
                "why": ("the baseline was recorded under a different "
                        "experiment; comparing them would measure the "
                        "difference between the experiments, not a change "
                        "in behaviour")})

    changes, appeared, vanished = [], [], []
    if not not_comparable:
        base_runs, now_runs = baseline["runs"], measured["runs"]
        appeared = sorted(set(now_runs) - set(base_runs))
        vanished = sorted(set(base_runs) - set(now_runs))
        for pid in sorted(set(base_runs) & set(now_runs)):
            for field in COMPARED:
                before, after = base_runs[pid].get(field), now_runs[pid].get(field)
                if before != after:
                    changes.append({"profile_id": pid, "field": field,
                                    "baseline": before, "measured": after})

    if not_comparable:
        verdict = "NOT_COMPARABLE"
    elif changes or appeared or vanished:
        verdict = "CHANGED"
    else:
        verdict = "UNCHANGED"

    return {
        "schema": "csia.stress.regression/1",
        "verdict": verdict,
        "not_comparable": not_comparable,
        "profiles_appeared": appeared,
        "profiles_vanished": vanished,
        "changes": changes,
        "change_count": len(changes),
        "no_tolerance_band": (
            "the campaign is bit-for-bit deterministic, so any difference "
            "is a real difference. A tolerance band here would be a place "
            "for a behavioural change to hide."),
        "changed_is_not_automatically_bad": (
            "a CHANGED verdict means stress behaviour moved. That may be an "
            "improvement, a harness change, or a regression -- read the "
            "listed differences and re-baseline deliberately if the new "
            "behaviour is the intended one."),
    }


INSTRUMENT = "tools.xr.stress_regression"


def _controls():
    """The exact-comparison gate must still be able to say CHANGED.

    This gate compares detection latency, recovery, escalation and
    attribution with NO tolerance band. A comparator stuck on UNCHANGED
    would report a clean nightly forever -- the MX-020 failure in a
    different gate. Both expectations follow from the definition of the
    comparison, not from any previous run of this tool.
    """
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _doc(latency):
        return {"seed": 1, "count": 1, "applicability_fingerprint": "f",
                "runs": {"p0": {f: latency for f in COMPARED}}}

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="an injected behavioural difference is reported",
            kind=POSITIVE,
            run=lambda: compare(_doc(2.0), _doc(1.0))["verdict"],
            expect=lambda v: v == "CHANGED",
            basis=("every compared field differs; CHANGED follows from the "
                   "exact-comparison rule this gate is defined by"),
        ),
        negative=Control(
            name="identical campaigns are not reported as changed",
            kind=NEGATIVE,
            run=lambda: compare(_doc(1.0), _doc(1.0))["verdict"],
            expect=lambda v: v == "UNCHANGED",
            basis=("identical inputs cannot differ; UNCHANGED follows from "
                   "the same definition"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--count", type=int, default=COUNT)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--max-listed", type=int, default=25)
    args = ap.parse_args(argv)

    # CONTROLS FIRST, AND THEY RAISE. An instrument that cannot
    # demonstrate it still works may not emit an artifact (MX-025).
    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    _control_report = guard(INSTRUMENT)

    measured = run_campaign(count=args.count, seed=args.seed)

    if args.update:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        measured = stamp(measured, _control_report)
        with open(BASELINE, "w", encoding="utf-8") as fh:
            json.dump(measured, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"stress baseline written: {BASELINE}")
        print(f"  seed={measured['seed']} count={measured['count']} "
              f"applicability={measured['applicability_fingerprint']}")
        return 0

    if not os.path.exists(BASELINE):
        print("no stress baseline recorded; run --update", file=sys.stderr)
        return 2
    with open(BASELINE, encoding="utf-8") as fh:
        baseline = json.load(fh)

    report = compare(measured, baseline)
    shown = dict(report)
    shown["changes"] = report["changes"][:args.max_listed]
    if len(report["changes"]) > args.max_listed:
        shown["changes_note"] = (
            f"{len(report['changes'])} changes; first {args.max_listed} shown")
    print(json.dumps(shown, indent=2, sort_keys=True, default=str))

    if report["verdict"] == "NOT_COMPARABLE":
        print("\nSTRESS REGRESSION: NOT COMPARABLE -- nothing was compared. "
              "This is NOT a pass.", file=sys.stderr)
        return 2
    if report["verdict"] == "CHANGED":
        print(f"\nSTRESS REGRESSION: {report['change_count']} behavioural "
              f"change(s)", file=sys.stderr)
        return 1
    print("\nSTRESS REGRESSION: UNCHANGED", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
