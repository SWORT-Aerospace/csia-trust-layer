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

WHAT IS REPLAYED
----------------
The replay reconstructs the core hand-offs from the logged canonical channels,
using the same reconstruction as `tools/deploy/profile_core_from_log.py`, and
re-drives the frozen core with them. The default gate keys on channel ARRIVAL
TIME, which is what the live adapter's freshness gate does. An older gate
compared VALUES and missed 58.8% of hand-offs (HF-010); it is kept selectable
so the two can be compared rather than one silently replacing the other.

TWO WAYS THIS TOOL HAS PRODUCED A WRONG ANSWER, BOTH FIXED, BOTH WORTH
KNOWING BEFORE TRUSTING A NUMBER FROM IT
-----------------------------------------------------------------------
**It compared the wrong ticks (HF-017).** Replayed states carry the layer's
exact tick grid; recorded rows carry wall time. Pairing them by nearest wall
time is off by however far the log's first row sits from the grid, and at a
staleness boundary that flips a freshness bit. It produced 119 PX4
"divergences" that were entirely an artifact of the pairing. A log carrying
`tick_tau` is now joined on the tick index instead, which is exact.

**It replayed logs it could not replay.** A log whose header carries no
`stale_timeout_s` was replayed against timeouts derived TODAY, and the
difference reported as a decision divergence. Such a log is now
NOT_COMPARABLE and yields no divergence count at all.

Replay fidelity remains a PER-PLATFORM property and this tool reports it as
one.

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


def _live_edges(gates: dict) -> frozenset:
    """Which edges carry weight. THIS is what decides DIVERGENT.

    At module scope rather than nested inside `replay` so its control can
    reach it. The verdict a reader treats as "the replay verified the run"
    rests on this one set comparison, and a version of it that returned a
    constant would report agreement on every log.
    """
    return frozenset(
        k for k, val in gates.items()
        if isinstance(val, (list, tuple)) and len(val) >= 2 and val[1] > 0)


def _header_field(log_path: str, field: str):
    """Read one field from the log's header record (line 0)."""
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record") == "header":
                return rec.get(field)
            if rec.get("record") == "tick":
                return None      # header must precede the ticks
    return None


def replay(log_path: str, platform: str, node: str = "gps",
           gate: str = "arrival", align: str = "auto") -> dict:
    """Re-drive the frozen core from a committed log and compare per tick.

    `gate` selects how the hand-off sequence is reconstructed. "arrival"
    reproduces the live adapter, which keys on channel ARRIVAL TIME;
    "value" is the older approximation that compared values and missed
    58.8% of hand-offs on a committed log. See HF-010.

    `align` selects how a replayed state is paired with a recorded tick.
    "auto" uses the exact layer-tick join when the log carries `tick_tau`
    and the wall-clock approximation otherwise. "wall" FORCES the
    approximation, which is what makes the two a controlled comparison on
    one log rather than two results from two runs.
    """
    from csia.runtime.online import OnlineTrustLayer
    from csia.v1_1.staleness import build_runtime_stale_timeouts
    from tools.deploy.profile_core_from_log import (HandoffReconstructor,
                                                    load_ticks)

    ticks = list(load_ticks(log_path))
    if not ticks:
        return {"error": "no ticks in log"}

    # THE RUN'S OWN STALENESS CONFIGURATION, OR NO COMPARISON AT ALL.
    #
    # The replay applies timeouts derived from the platform TODAY. If the log
    # does not say which timeouts the RUN used, the two may differ and there
    # is no way to tell -- so a freshness difference cannot be attributed to
    # the system rather than to the instrument. Reporting DIVERGENT in that
    # state manufactures a finding out of a gap in the log, which is the same
    # defect as MX-021: an instrument that turns "I cannot measure this" into
    # a measurement.
    #
    # Measured cost of the old behaviour: the 2026-08-25 PX4 log carries
    # `stale_timeout_s: None` and was reported DIVERGENT on 144 of 750
    # decisions for months. That number was never evidence of a semantic
    # disagreement, and it was never evidence of agreement either.
    #
    # NOT_COMPARABLE IS NEVER PASS.
    derived_timeouts = build_runtime_stale_timeouts(platform)
    recorded_timeouts = _header_field(log_path, "stale_timeout_s")
    if not recorded_timeouts:
        return {
            "log": os.path.relpath(log_path, ROOT),
            "platform": platform,
            "ticks_in_log": len(ticks),
            "verdict": "NOT_COMPARABLE",
            "reason": "NO_STALENESS_CONFIG_IN_LOG",
            "detail": ("the log's header carries no `stale_timeout_s`, so the "
                       "timeouts this run used are unknown and a freshness "
                       "difference cannot be attributed to the system rather "
                       "than to the replay's own configuration"),
            "derived_timeouts_that_would_have_been_applied": derived_timeouts,
        }
    if dict(recorded_timeouts) != dict(derived_timeouts):
        return {
            "log": os.path.relpath(log_path, ROOT),
            "platform": platform,
            "ticks_in_log": len(ticks),
            "verdict": "NOT_COMPARABLE",
            "reason": "STALENESS_CONFIG_CHANGED_SINCE_THE_RUN",
            "recorded_timeouts": dict(recorded_timeouts),
            "derived_timeouts": dict(derived_timeouts),
        }

    layer = OnlineTrustLayer(
        tick_hz=25.0, field_mode=True, stale_timeout_s=derived_timeouts)

    reconstructor = HandoffReconstructor(gate=gate)
    replayed = []
    for tick in ticks:
        states = []
        for sensor, t, chans in reconstructor.samples_for_tick(tick):
            states.extend(layer.ingest(sensor, t, chans))
        for s in states:
            replayed.append((round(s.t, 6), s.trust.get(node),
                             dict(s.edges or {})))

    # ALIGNMENT. Two joins are available and they are NOT interchangeable.
    #
    # EXACT_LAYER_TICK_INDEX is used whenever the log carries `tick_tau`, the
    # live layer's own tick boundary. Both sides are then on the same grid --
    # `next_tick` starts at 0.0 and advances by `dt_tick` in the live run and
    # in the replay alike -- so the join is an integer equality on the tick
    # index and a compared pair is guaranteed to be the SAME tick.
    #
    # NEAREST_WALL_CLOCK_WITHIN_HALF_TICK is the fallback for logs written
    # before `tick_tau` existed, and it is an approximation with a measurable
    # cost. The recorded rows are stamped with wall time, which advances at
    # ~0.0407 s per tick against the layer's exact 0.0400 s, so "the recorded
    # row nearest in wall time" is not in general the same tick as the
    # replayed one. At a staleness boundary that mismatch flips a freshness
    # bit, which is what HF-016 measured on PX4: 119 divergences, 59 with the
    # replay's `altitude_baro` live and 59 with the recording's live. A
    # symmetric signature is what an alignment artifact looks like, not what a
    # semantic disagreement looks like.
    #
    # The two are reported under different `alignment` values and results
    # obtained under them MUST NOT be compared to each other.
    dt_tick = layer.dt_tick
    tau_rows = [x for x in ticks if x.get("tick_tau") is not None]
    if align not in ("auto", "exact", "wall"):
        raise ValueError(f"unknown alignment {align!r}")
    if align == "exact" and not tau_rows:
        return {"log": os.path.relpath(log_path, ROOT), "platform": platform,
                "verdict": "NOT_COMPARABLE",
                "reason": "alignment 'exact' requested and no tick carries "
                          "tick_tau; this log predates the field"}
    exact = bool(tau_rows) and align != "wall"

    if exact:
        alignment = "EXACT_LAYER_TICK_INDEX"
        by_index = {}
        for x in tau_rows:
            by_index[int(round(float(x["tick_tau"]) / dt_tick))] = (
                (x.get("trust_post") or {}).get(node),
                dict(x.get("gates") or {}))

        def nearest(t):
            hit = by_index.get(int(round(t / dt_tick)))
            return (t, hit[0], hit[1]) if hit is not None else None
    else:
        alignment = "NEAREST_WALL_CLOCK_WITHIN_HALF_TICK"
        t0 = ticks[0]["t_mono"]
        recorded = [(round(x["t_mono"] - t0, 6),
                     (x.get("trust_post") or {}).get(node),
                     dict(x.get("gates") or {}))
                    for x in ticks]
        half_tick = dt_tick / 2.0
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
        if _live_edges(edges) != _live_edges(rg):
            divergent += 1
            if len(examples) < 5:
                examples.append({"t": t,
                                 "replay_live": sorted(_live_edges(edges)),
                                 "recorded_live": sorted(_live_edges(rg))})
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
        # WHICH RUN THIS NUMBER CAME FROM. `logs/` is gitignored, so a path
        # alone does not identify a flight to anyone but the machine holding
        # it.
        "flight_id": _header_field(log_path, "flight_id"),
        "log_csia_commit": _header_field(log_path, "csia_commit"),
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
        "alignment": alignment,
        "ticks_carrying_tick_tau": len(tau_rows),
        "alignment_note": (
            "EXACT_LAYER_TICK_INDEX joins on the live layer's own tick "
            "boundary, so a compared pair is the same tick by construction. "
            "NEAREST_WALL_CLOCK_WITHIN_HALF_TICK matches on wall time, which "
            "advances at ~0.0407 s per tick against the layer's 0.0400 s, so "
            "the pair need not be the same tick. Results obtained under the "
            "two alignments are NOT comparable."),
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
            "as the explanation and RULED OUT. "
            "HF-017 THEN FOUND THE CAUSE, AND IT WAS THIS TOOL. The "
            "divergence was an artifact of pairing a replayed state with the "
            "recorded row NEAREST IN WALL TIME: the replay carries the "
            "layer's exact tick grid, the recording was shifted by its first "
            "row's t_mono, and on the log in question that shift was 0.59 of "
            "a tick. Joining on the layer's own tick index instead gives 0 "
            "divergent and 2250 of 2250 bit-identical on the same log, with "
            "ArduPilot unchanged at 0. "
            "HF-004 WAS CLOSED ON THAT EVIDENCE (HF-018), by an explicit "
            "decision of the program owner rather than by this instrument. "
            "WHAT THE CLOSURE DOES NOT MEAN. It promotes no gate. It covers "
            "two 90-second clean SITL flights, not hardware, not a fault "
            "campaign, not any other platform. The hand-offs HF-004 asked to "
            "have LOGGED at run time are still RECONSTRUCTED, so this is the "
            "weaker of the two available results. And the VALUES are still "
            "not reproduced on either platform: ArduPilot has 22 "
            "bit-identical decisions of 2248 and ZERO within the declared "
            "1e-12 tolerance, worst 1.80e-05; PX4 has 51 and 980 of 2242, "
            "worst 6.74e-10. The tolerance has not been changed."),
    }


INSTRUMENT = "tools.assurance.decision_replay"


def _default_logs():
    """The newest log per platform that CAN be replayed, not a fixed path.

    The old default named two 2026-08-25 files directly. Both problems with
    that were real:

      * `logs/` is gitignored in its entirety, so those paths are not in the
        repository and resolve to LOG_ABSENT on any checkout but the machine
        that produced them. A default that only works on one machine is not a
        default.
      * Neither carries `stale_timeout_s`, so neither is replayable at all
        under the provenance rule above. The PX4 one is the source of the
        long-standing "144 divergent" figure.

    Selecting the newest QUALIFYING log makes the artifact machine-dependent,
    which is why every run records the flight_id and csia_commit of the log it
    read. A reader can tell which run a number came from; they could not
    before.
    """
    import glob
    logs, plats = [], []
    for plat in ("ardupilot", "px4"):
        best = None
        pattern = os.path.join(ROOT, "logs", f"shadow-sitl-{plat}", "*.jsonl")
        for path in sorted(glob.glob(pattern)):
            if _header_field(path, "stale_timeout_s"):
                best = path
        if best is not None:
            logs.append(os.path.relpath(best, ROOT))
            plats.append(plat)
    return logs, plats


#: Two gate maps that differ ONLY in whether `altitude_baro` carries weight.
#: That is the exact shape of every PX4 divergence ever recorded here, so a
#: comparator blind to it would have reported agreement on all of them.
_GATES_BARO_LIVE = {"altitude_baro": [0.4, 0.9], "attitude_gravity_mag": [0.1, 0.8]}
_GATES_BARO_DEAD = {"altitude_baro": [0.4, 0.0], "attitude_gravity_mag": [0.1, 0.8]}


def _controls():
    """Both comparators, because the verdict rests on both.

    `_rel` decides BIT_IDENTICAL vs NUMERICALLY_EQUIVALENT; `_live_edges`
    decides DIVERGENT, and DIVERGENT is the outcome a reader treats as "the
    replay failed" -- so a `_live_edges` stuck at a constant would turn every
    divergent replay green. Each control exercises both, because a pair can
    hold one positive and one negative and both comparators need covering.
    """
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a numeric difference exceeds tolerance AND a dead edge "
                 "reads as a different decision",
            kind=POSITIVE,
            run=lambda: {
                "rel": _rel(1.0, 2.0),
                "cat_differs": (_live_edges(_GATES_BARO_LIVE)
                                != _live_edges(_GATES_BARO_DEAD)),
            },
            expect=lambda d: d["rel"] > TOLERANCE and d["cat_differs"] is True,
            basis=("a relative difference of 0.5 against a tolerance of "
                   f"{TOLERANCE} is arithmetic; and an edge whose weight is "
                   "0.0 is not carrying weight, which is the definition the "
                   "gate semantics give, not one this tool supplies"),
        ),
        negative=Control(
            name="identical values differ by zero AND identical gate maps "
                 "read as the same decision",
            kind=NEGATIVE,
            run=lambda: {
                "rel": _rel(1.0, 1.0),
                "cat_differs": (_live_edges(_GATES_BARO_LIVE)
                                != _live_edges(dict(_GATES_BARO_LIVE))),
            },
            expect=lambda d: d["rel"] == 0.0 and d["cat_differs"] is False,
            basis=("a value equals itself and a set equals itself; both "
                   "follow from the definitions of equality, not from this "
                   "tool"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", action="append", default=None)
    ap.add_argument("--platform", action="append", default=None)
    ap.add_argument("--align", choices=("auto", "exact", "wall"),
                    default="auto",
                    help="how a replayed state is paired with a recorded "
                         "tick; 'wall' forces the pre-tick_tau approximation "
                         "so the two can be compared on one log")
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    # CONTROLS FIRST, AND THEY RAISE. An instrument that cannot
    # demonstrate it still works may not emit an artifact (MX-025).
    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    _control_report = guard(INSTRUMENT)

    if not args.log:
        args.log, args.platform = _default_logs()

    runs = []
    for log, plat in zip(args.log, args.platform or []):
        path = os.path.join(ROOT, log) if not os.path.isabs(log) else log
        if not os.path.exists(path):
            runs.append({"log": log, "verdict": "LOG_ABSENT"})
            continue
        runs.append(replay(path, plat, align=args.align))

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
