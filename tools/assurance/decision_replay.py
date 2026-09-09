"""Decision-level replay: re-derive a flight's decisions without the autopilot.

THE FOUR OUTCOMES, REPORTED SEPARATELY
---------------------------------------
    BIT_IDENTICAL                    every compared value equal exactly
    NUMERICALLY_EQUIVALENT           within the declared tolerance
    SEMANTICALLY_EQUIVALENT          categorical decisions agree; continuous
                                     values do not
    DIVERGENT                        a categorical decision differs

**Bit identity is not demanded where the platform does not guarantee it.**
`docs/SEMANTIC_PORTABILITY_CONTRACT.md` separates the levels precisely so that
a numerical difference is not reported as a decision failure -- and so that a
decision failure is never excused as a rounding artifact.

WHAT IS REPLAYED, AND THE FIDELITY LIMIT THAT MATTERS
------------------------------------------------------
The replay reconstructs the core hand-offs from the logged canonical channels,
using the same reconstruction as `tools/deploy/profile_core_from_log.py`. That
reconstruction detects a hand-off by a CHANGED channel value, so two identical
consecutive readings look like no new reading.

**This bites differently per platform, and it is already a recorded finding
(FL-019):** the reconstruction reproduces PX4's measured trust to ~0.003 and
does NOT reproduce ArduPilot's. So replay fidelity is a PER-PLATFORM property,
this tool reports it as one, and an ArduPilot divergence here is expected and
attributable rather than a new defect.

    python tools/assurance/decision_replay.py --log <flight log> \
        --platform px4 --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

BIT_IDENTICAL = "BIT_IDENTICAL"
NUMERICALLY_EQUIVALENT = "NUMERICALLY_EQUIVALENT_WITHIN_TOLERANCE"
SEMANTICALLY_EQUIVALENT = "SEMANTICALLY_EQUIVALENT"
DIVERGENT = "DIVERGENT"

#: Level 3 of the portability contract.
TOLERANCE = 1e-12


def _rel(a, b):
    if a == b:
        return 0.0
    scale = max(abs(a), abs(b), 1e-30)
    return abs(a - b) / scale


def replay(log_path: str, platform: str, node: str = "gps",
           gate: str = "arrival") -> dict:
    """Re-drive the frozen core from a committed log and compare per tick.

    `gate` selects how the hand-off sequence is reconstructed. "arrival"
    reproduces the live adapter, which keys on channel ARRIVAL TIME;
    "value" is the older approximation that compared values and missed
    58.8% of hand-offs on a committed log. See HF-010.
    """
    from csia.runtime.online import OnlineTrustLayer
    from csia.v1_1.staleness import build_runtime_stale_timeouts
    from tools.deploy.profile_core_from_log import (HandoffReconstructor,
                                                    load_ticks)

    ticks = list(load_ticks(log_path))
    if not ticks:
        return {"error": "no ticks in log"}

    layer = OnlineTrustLayer(
        tick_hz=25.0, field_mode=True,
        stale_timeout_s=build_runtime_stale_timeouts(platform))

    reconstructor = HandoffReconstructor(gate=gate)
    replayed = []
    for tick in ticks:
        states = []
        for sensor, t, chans in reconstructor.samples_for_tick(tick):
            states.extend(layer.ingest(sensor, t, chans))
        for s in states:
            replayed.append((round(s.t, 6), s.trust.get(node),
                             dict(s.edges or {})))

    # The recorded run, from the same log.
    t0 = ticks[0]["t_mono"]
    recorded = [(round(x["t_mono"] - t0, 6),
                 (x.get("trust_post") or {}).get(node),
                 dict(x.get("gates") or {}))
                for x in ticks]

    # ALIGNMENT: the replayed states carry the LAYER's internal tick clock
    # (0.0, 0.04, 0.08, ... by construction), while the log carries the
    # ACTUAL arrival times. An exact timestamp join produced zero matches on
    # both platforms -- a silent "NOT_COMPARABLE" that looked like a result.
    # So each replayed state is matched to the nearest recorded tick within
    # half a tick period, and unmatched states are counted rather than
    # dropped.
    half_tick = 0.02
    rec_sorted = sorted(recorded, key=lambda r: r[0])
    rec_times = [r[0] for r in rec_sorted]

    def nearest(t):
        import bisect
        i = bisect.bisect_left(rec_times, t)
        best = None
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(rec_sorted):
                d = abs(rec_times[j] - t)
                if best is None or d < best[0]:
                    best = (d, rec_sorted[j])
        return best[1] if best and best[0] <= half_tick else None

    unmatched = 0
    compared = bit = numeric = semantic = divergent = 0
    worst = 0.0
    examples = []

    for t, v, edges in replayed:
        match = nearest(t)
        if match is None or v is None:
            unmatched += 1
            continue
        _, rv, rg = match
        if rv is None:
            unmatched += 1
            continue
        compared += 1

        # Categorical: which gate weights are non-zero. This is what a
        # DECISION rests on, and it is compared exactly.
        def live(d):
            return frozenset(
                k for k, val in d.items()
                if isinstance(val, (list, tuple)) and len(val) >= 2
                and val[1] > 0)
        cat_same = live(edges) == live(rg)

        if not cat_same:
            divergent += 1
            if len(examples) < 5:
                examples.append({"t": t, "replay_live": sorted(live(edges)),
                                 "recorded_live": sorted(live(rg))})
            continue
        if v == rv:
            bit += 1
        else:
            d = _rel(v, rv)
            worst = max(worst, d)
            if d <= TOLERANCE:
                numeric += 1
            else:
                semantic += 1

    if compared == 0:
        verdict = "NOT_COMPARABLE"
    elif divergent:
        verdict = DIVERGENT
    elif semantic:
        verdict = SEMANTICALLY_EQUIVALENT
    elif numeric:
        verdict = NUMERICALLY_EQUIVALENT
    else:
        verdict = BIT_IDENTICAL

    return {
        "log": os.path.relpath(log_path, ROOT),
        "platform": platform,
        "node": node,
        "ticks_in_log": len(ticks),
        "decisions_compared": compared,
        "replayed_states_unmatched": unmatched,
        "bit_identical": bit,
        "numerically_equivalent": numeric,
        "semantically_equivalent_only": semantic,
        "divergent": divergent,
        "worst_relative_difference": worst,
        "tolerance": TOLERANCE,
        "verdict": verdict,
        "divergence_examples": examples,
        "reconstruction_gate": gate,
        "fidelity_note": (
            "The hand-off reconstruction now keys on channel ARRIVAL TIME, "
            "which is what the live adapter's freshness gate does. The "
            "earlier reconstruction compared VALUES and so missed 58.8% of "
            "hand-offs on a committed log, because two identical consecutive "
            "readings looked like no new reading (HF-010). That removed most "
            "of the ArduPilot divergence -- 511 categorical differences fell "
            "to 13 -- and left PX4 unchanged at 144, so what remains on PX4 "
            "has a DIFFERENT cause. HF-014 has now attributed the MECHANISM "
            "and not the root cause: all 144 are the replay seeing MORE live "
            "edges than the recording (never fewer), 122 of them exactly "
            "`altitude_baro`, and every affected edge is one whose weight is "
            "a product of per-sensor FRESHNESS terms while the residual "
            "values agree. A single differing staleness timeout was tested "
            "as the explanation and RULED OUT. Why the live side differed "
            "cannot be settled from these logs, which never recorded the "
            "layer's own `fresh` map; logs written after HF-014 do. "
            "THE VERDICT IS STILL DIVERGENT ON BOTH PLATFORMS: decision "
            "replay does not yet serve as a verification instrument, and the "
            "software-hardening gate must not count it as PASS."),
    }


INSTRUMENT = "tools.assurance.decision_replay"


def _controls():
    """The four-outcome verdict rests on `_rel` separating equal from not.

    A comparator that returned 0.0 for everything would report
    BIT_IDENTICAL on a divergent replay -- and this is the one instrument
    whose green result would be read as "the system is verified".
    """
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a real numeric difference exceeds the tolerance",
            kind=POSITIVE,
            run=lambda: _rel(1.0, 2.0),
            expect=lambda d: d > TOLERANCE,
            basis=("a relative difference of 0.5 against a tolerance of "
                   f"{TOLERANCE} is arithmetic"),
        ),
        negative=Control(
            name="identical values differ by zero",
            kind=NEGATIVE,
            run=lambda: _rel(1.0, 1.0),
            expect=lambda d: d == 0.0,
            basis="a value equals itself; zero follows by arithmetic",
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", action="append", default=None)
    ap.add_argument("--platform", action="append", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    # CONTROLS FIRST, AND THEY RAISE. An instrument that cannot
    # demonstrate it still works may not emit an artifact (MX-025).
    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    _control_report = guard(INSTRUMENT)

    if not args.log:
        # Default: one committed log per platform.
        args.log = [
            "logs/shadow-sitl-ardupilot/20260825T005244Z-8c32ffe5.part000.jsonl",
            "logs/shadow-sitl-px4/20260825T005931Z-1b4add14.part000.jsonl",
        ]
        args.platform = ["ardupilot", "px4"]

    runs = []
    for log, plat in zip(args.log, args.platform or []):
        path = os.path.join(ROOT, log) if not os.path.isabs(log) else log
        if not os.path.exists(path):
            runs.append({"log": log, "verdict": "LOG_ABSENT"})
            continue
        runs.append(replay(path, plat))

    doc = {
        "schema": "csia.assurance.decision_replay/1",
        "outcomes": [BIT_IDENTICAL, NUMERICALLY_EQUIVALENT,
                     SEMANTICALLY_EQUIVALENT, DIVERGENT],
        "runs": runs,
        "note": ("Bit identity is NOT demanded where the platform contract "
                 "does not guarantee it. The four outcomes are reported "
                 "separately so a numerical difference is never read as a "
                 "decision failure, and a decision failure is never excused "
                 "as rounding."),
    }
    doc = stamp(doc, _control_report)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
