"""Qualify a live autopilot's telemetry against the semantic contract (S2/S3).

This is the instrument that turns `CHANNEL_SEMANTICS.yaml` from a document
into a measurement. It launches the real simulator, runs the real adapter over
the real stream, and asks of every channel:

    did it arrive?          -> presence
    did it move?            -> INFORMATIVENESS, the property that matters
    does the contract agree?-> contract vs observation, reported side by side

The informativeness probe is the whole point. A channel that arrives on every
tick with an identical value is a stub no matter how healthy the stream looks,
and that is exactly how the ArduPilot SITL ESC current (a hard-coded 0.8 A)
produced a spurious CRITICAL on every clean flight.

Disagreements are reported, never auto-applied. A contract row is a decision;
this tool produces the evidence for changing one, not the change.

  python tools/simulation/qualify_platform.py --platform ardupilot
  python tools/simulation/qualify_platform.py --platform px4
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import subprocess
import statistics
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.aircraft.adapters import get_adapter            # noqa: E402
from csia.aircraft.qualification import (                # noqa: E402
    default_contract, platform_rows_in_force)
from csia.aircraft.sample import Quality                  # noqa: E402
from csia.simulation.dialect import (                     # noqa: E402
    blind_channels, message_names, undecodable_frames)
from csia.simulation.rigs import (                        # noqa: E402
    LAUNCHERS, ROOTS, connect, dialect_report, effective_speedup, fly)
from csia.simulation.ulog_check import (                  # noqa: E402
    HEADING_DEPENDENT_CHANNELS, heading_provenance, newest_ulog)

# Not a Quality: it is a statement about the INSTRUMENT, not the channel.
# A channel whose producer arrived as a frame the decoder could not parse is
# unread, and "unread" must never be recorded as "absent" -- that is how the
# PX4 ESC_STATUS finding was published backwards.
UNDECODABLE = "UNDECODABLE"


# A channel is INFORMATIVE only if it varies. The floor is deliberately tiny:
# we are separating "constant" from "not constant", not judging magnitude.
CONSTANT_EPS = 1e-9

# The process exit code IS the gate: `make sim-px4` and CI read nothing else.
EXIT_CODES = {"PASS": 0, "FAIL": 1, "PARTIAL": 2,
              "INVALID_PROBE": 2, "INSTRUMENT_DEAD": 3}


def verdict_exit_code(verdict: str):
    """Derive the exit code FROM the verdict, so the two cannot diverge.

    They did diverge. The exit code was computed from its own conditions
    (`return 1 if admitted_stub else 0`), and a run whose verdict read
    "FAIL: a channel the contract admits as evidence never arrived" matched
    none of them and exited 0. The gate reported success on a failing
    qualification -- the exact thing a gate exists to prevent.

    Returns None for a token nobody mapped; the caller must treat that as a
    failure, never as a pass. A verdict string that reaches here unrecognised
    means someone added a verdict and forgot the gate, and defaulting to 0
    would hide precisely that.
    """
    return EXIT_CODES.get(verdict.split(":", 1)[0].strip())


def _scalarize(v):
    """Reduce any channel value to one finite number for variation testing.

    SINGLE EXIT, deliberately. The first version guarded only the numpy branch
    and let the dict branch return early, so a NaN inside a dict-valued
    channel went straight through. PX4's ESTIMATOR_STATUS publishes NaN ratios
    before the EKF converges (ArduPilot's EKF_STATUS_REPORT does not), which
    reached `statistics.pstdev` and crashed the whole probe with
    "'float' object has no attribute 'numerator'" -- Python 3.12's signature
    for NaN in the Fraction path.

    Guarding one branch fixes one crash; funnelling every branch through one
    check fixes the class. A NaN is not a sample, and it must never be allowed
    to decide a channel's verdict either.
    """
    out = None
    if v is None:
        return None
    elif isinstance(v, dict):
        nums = [x for x in v.values()
                if isinstance(x, (int, float)) and not isinstance(x, bool)]
        out = float(sum(nums)) if nums else None
    elif isinstance(v, bool):
        out = float(v)
    elif isinstance(v, (int, float)):
        out = float(v)
    elif isinstance(v, str):
        out = float(abs(hash(v)) % 1000)
    else:
        try:
            out = float(np.sum(np.asarray(v, dtype=float)))
        except Exception:
            out = None
    if out is None or not math.isfinite(out):
        return None
    return out


def observe(platform, duration_s, conn, adapter):
    """Collect per-channel observations from the live stream."""
    obs = {ch: [] for ch in adapter.contract.channels}
    nonfinite = {}
    # channel -> the store's receive stamp at the last time we sampled it.
    #
    # WITHOUT THIS THE PROBE COUNTS MESSAGES, NOT SAMPLES. The loop reads the
    # whole store after every message, so a 25 Hz channel was recorded ~430
    # times a second and a 40 s PX4 run reported n=17,336 for a channel that
    # published about 1,000 times. Two consequences, and the second is worse
    # than the first:
    #
    #   * the reported `n` overstated the evidence by more than 17x, and it
    #     was quoted in the docs as if it were a sample count;
    #   * `sd` was DWELL-WEIGHTED -- each value counted once per message that
    #     happened to arrive while it was current -- so a slow channel's
    #     spread was silently weighted by how long each value sat in the
    #     store rather than by how often it was measured.
    #
    # The verdicts do not change: range is over the same set of values, and
    # the stub test is `spread <= EPS`. Only the statistics become honest.
    last_stamp = {}
    t0 = time.time()
    msgs = 0
    while time.time() - t0 < duration_s:
        m = conn.recv_match(blocking=True, timeout=2.0)
        if m is None:
            continue
        msgs += 1
        adapter.ingest(m)
        # Read the adapter's own store so a BLOCKED channel is still observed:
        # deciding whether a declared stub really is constant is the evidence
        # the contract row rests on, and a blocked channel never reaches the
        # canonical sample.
        for ch, entry in adapter._latest.items():
            stamp = entry[1]
            if last_stamp.get(ch) == stamp:
                continue           # same arrival as last time: not a sample
            last_stamp[ch] = stamp
            s = _scalarize(entry[0])
            if s is not None:
                obs.setdefault(ch, []).append(s)
            elif entry[0] is not None:
                # Present but unusable as a sample: NaN, inf, or a shape the
                # probe cannot reduce. Counted rather than silently dropped --
                # a channel that publishes NaN is a finding in itself, and
                # discarding it quietly is how the PX4 crash stayed invisible
                # until it took the whole run down.
                nonfinite[ch] = nonfinite.get(ch, 0) + 1
    return obs, msgs, nonfinite


def analyse(obs, raw_present, contract, nonfinite=None, blind=None,
            sentinels=None, duration_s=None, platform=""):
    nonfinite = nonfinite or {}
    blind = blind or {}
    sentinels = sentinels or {}
    rows = []
    for ch, row in sorted(contract.channels.items()):
        vals = obs.get(ch, [])
        n = len(vals)
        bad = nonfinite.get(ch, 0)
        # Initialised per channel: the DECODE branch never assigns it, so
        # without this a latched row reported whatever spread the PREVIOUS
        # channel happened to leave behind.
        spread = None
        if n == 0 and ch in blind:
            # The producer message DID arrive -- the decoder could not read
            # it. Reporting UNAVAILABLE here would be a claim about PX4 made
            # from a fact about pymavlink's bundled common.xml, which is
            # precisely the error this branch exists to prevent.
            observed = UNDECODABLE
            b = blind[ch]
            detail = (f"{b['message']} (id {b['id']}) arrived {b['frames']} "
                      f"times and the decoder could not parse it: NO claim "
                      f"about this channel can be made from this run")
        elif n == 0:
            if bad:
                # It DID arrive. It was unusable. Those are different facts and
                # collapsing them to "never arrived" would misreport PX4's
                # pre-convergence estimator as an absent message.
                observed = Quality.AVAILABLE_UNVALIDATED
                detail = (f"arrived {bad} times, every sample non-finite "
                          f"(NaN/inf) -- present but not measurable")
            else:
                observed = Quality.UNAVAILABLE
                sent = sentinels.get(ch, 0)
                # "Never arrived" and "arrived declaring it has no sensor" are
                # different facts about a platform, and the report gave both
                # the same words. PX4's BATTERY_STATUS reaches us at ~9 Hz
                # with current_battery = -1: the stream is implemented, the
                # measurement is not. That distinction decides whether the fix
                # is wiring a message or fitting a sensor.
                detail = ("never arrived" if not sent else
                          f"producer arrived {sent} times carrying the "
                          f"documented not-measured sentinel: the stream is "
                          f"implemented, the measurement is absent")
        elif row.criterion == "DECODE":
            # A latched enum or boolean. Constancy is its normal state -- a
            # vehicle that stays armed reports the same value all flight --
            # so variation is the wrong criterion. It qualifies by decoding.
            observed = Quality.INFORMATIVE
            detail = (f"latched value {vals[-1]:.6g}, decoded over {n} "
                      f"samples (criterion DECODE, not variation)")
        else:
            spread = (max(vals) - min(vals)) if n > 1 else 0.0
            if spread <= CONSTANT_EPS:
                observed = Quality.STUB_OR_NONINFORMATIVE
                detail = f"constant at {vals[0]:.6g} over {n} samples"
            else:
                observed = Quality.INFORMATIVE
                sd = statistics.pstdev(vals) if n > 2 else spread
                detail = f"range {spread:.6g}, sd {sd:.6g}, n={n}"
        declared = row.quality
        if observed is UNDECODABLE:
            # NOT False. "Disagrees with the contract" is a finding, and a
            # run that could not read the message is entitled to neither
            # agreement nor disagreement. None says so.
            agrees = None
        else:
            agrees = (observed == declared) or (
                declared in (Quality.VALIDATED_SEMANTICS,
                             Quality.AVAILABLE_UNVALIDATED)
                and observed is Quality.INFORMATIVE)
        # Measured publish rate. The probe has always had the data and never
        # made the comparison: PX4's ESC_STATUS row claimed 10 Hz and the
        # platform delivers 0.97, which MaxAge inherited as a 0.50 s limit and
        # would have marked half of every publish period STALE.
        rate_hz = (n / duration_s) if (duration_s and n) else None
        declared_hz = (row.raw.get(f"producer_{platform}") or {}).get("rate_hz")
        rows.append({
            "measured_rate_hz": round(rate_hz, 2) if rate_hz else None,
            "declared_rate_hz": declared_hz,
            "channel": ch,
            "declared": declared.value,
            "observed": (observed if isinstance(observed, str)
                         else observed.value),
            "agrees": agrees,
            "may_use": row.may_use,
            "admissible": row.admissible,
            "criterion": row.criterion,
            "samples": n,
            "nonfinite_samples": bad,
            "spread": spread,
            "detail": detail,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=sorted(LAUNCHERS),
                    default="ardupilot")
    ap.add_argument("--seconds", type=float, default=40.0)
    ap.add_argument("--speedup", type=int, default=10)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--static", action="store_true",
                    help="skip the motion positive control (probe will be "
                         "reported INVALID_PROBE; for debugging only)")
    args = ap.parse_args()

    workdir = args.workdir or os.path.join(
        ROOT, "build", f"sitl-{args.platform}")
    proc, conn_str = LAUNCHERS[args.platform](workdir, args.speedup)
    print(f"=== {args.platform} SITL launched (pid {proc.pid}) -> {conn_str}")
    try:
        conn = connect(conn_str, args.platform)
        print("=== heartbeat received")
        adapter = get_adapter(args.platform)
        motion = {"armed": False, "climbed_m": 0.0, "alt_samples": []}
        if not args.static:
            print("=== positive control: arming and climbing")
            motion = fly(conn, args.platform)
            print(f"    armed={motion['armed']} "
                  f"climbed={motion['climbed_m']:.1f} m")
        print(f"=== observing {args.seconds:.0f}s")
        obs, msgs, nonfinite = observe(args.platform, args.seconds, conn, adapter)
        # BEFORE analysis: which channels is this decoder blind to?
        #
        # An `UNKNOWN_<id>` in the unmapped counter is not traffic we chose to
        # ignore. It is a well-framed message the parser could not read, and
        # if the contract names it as a producer then every claim about that
        # channel from this run is a claim about the parser.
        unmapped = adapter.unmapped_types()
        undecodable = undecodable_frames(unmapped)
        names = message_names(args.platform, ROOTS[args.platform])
        blind = blind_channels(adapter.contract, args.platform,
                               undecodable, names)
        rows = analyse(obs, {}, adapter.contract, nonfinite, blind,
                       adapter.sentinel_counts(), duration_s=args.seconds,
                       platform=args.platform)
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    # AFTER the autopilot has exited, so its own log is flushed and closed.
    #
    # PX4 SIH prints "Preflight Fail: no heading reference" on every boot. If
    # that were a real missing heading source, every magnetometer,
    # GNSS-course, attitude and cross-sensor row in this report would be
    # contaminated and nothing here would show it. The autopilot's ulog
    # settles the question; see csia/simulation/ulog_check.py.
    provenance = {"verdict": "NOT_APPLICABLE",
                  "notes": [f"{args.platform} does not write a ulog"]}
    if args.platform == "px4":
        provenance = heading_provenance(newest_ulog(workdir))
    heading_verified = provenance["verdict"] == "HEADING_REFERENCE_VALID"
    # LATE belongs here too: if yaw aligned only after the vehicle armed,
    # part of the observation window ran without a heading reference, and a
    # partially contaminated channel is not a usable one.
    heading_broken = provenance["verdict"] in ("NO_HEADING_REFERENCE",
                                               "HEADING_REFERENCE_LOST",
                                               "HEADING_REFERENCE_LATE")

    print(f"\n=== {msgs} messages, {adapter.counters['mapped']} mapped, "
          f"{adapter.counters['unmapped']} unmapped")
    if unmapped:
        top = sorted(unmapped.items(), key=lambda kv: -kv[1])[:8]
        print("    unmapped types: " +
              ", ".join(f"{k}x{v}" for k, v in top))

    # Every platform narrowing in force, printed on every run. A narrowing
    # nobody sees is a narrowing nobody reviews, and that is how "the platform
    # genuinely does not provide it" decays into "we stopped checking".
    narrowed = platform_rows_in_force(adapter.contract)
    if narrowed:
        print(f"=== platform contract rows in force for {args.platform}: "
              f"{len(narrowed)}")
        for ch, row in sorted(narrowed.items()):
            print(f"    {ch:22s} -> {row['qualification']:22s} "
                  f"may_use={bool(row.get('csia_may_use'))}")

    dialect = dialect_report(args.platform)
    print(f"=== decoder: {dialect.name if dialect else 'library default'} "
          f"({dialect.message_count if dialect else '?'} message types), "
          f"vehicle definitions "
          f"{'IN USE' if dialect and dialect.active else 'NOT IN USE'}")
    if undecodable:
        print("    UNDECODABLE frames "
              "(arrived, could not be parsed, NOT absent):")
        for mid, count in sorted(undecodable.items()):
            name = names.get(mid, "<not in the vehicle's XML either>")
            print(f"      id {mid:<5} {name:34s} x{count}")
    for ch, b in sorted(blind.items()):
        print(f"    *** {ch} depends on {b['message']}, which this decoder "
              f"could not read")

    if args.platform == "px4":
        print(f"=== estimator heading: {provenance['verdict']}"
              + (f", source {provenance.get('source')}, aligned at "
                 f"{provenance.get('aligned_at_s')} s"
                 if provenance.get("aligned_at_s") is not None else ""))
        gt = provenance.get("yaw_error_vs_truth_deg")
        if gt:
            print(f"    yaw vs SIH ground truth: mean |err| "
                  f"{gt['mean_abs']}deg, max {gt['max_abs']}deg, n={gt['n']}")
        if not heading_verified:
            # Loud, because "we could not check" and "it was fine" are the two
            # things this whole check exists to keep apart.
            print("    *** HEADING NOT VERIFIED -- "
                  + "; ".join(provenance.get("notes", [])))

    print(f"\n{'channel':26s} {'declared':24s} {'observed':24s} agree")
    disagreements = []
    for r in rows:
        mark = {True: "yes", False: "NO", None: "n/a"}[r["agrees"]]
        print(f"{r['channel']:26s} {r['declared']:24s} "
              f"{r['observed']:24s} {mark}")
        print(f"{'':26s}   {r['detail']}")
        # `agrees is False`, not `not agrees`: None means the run made no
        # claim, and folding that into "disagrees" would manufacture a
        # finding out of a blind spot.
        if r["agrees"] is False:
            disagreements.append(r)

    # RATE DRIFT. Only meaningful at speedup 1: with SITL accelerated, wall
    # rates are inflated by the speedup factor and comparing them against a
    # real-time declaration is a category error. ArduPilot runs at speedup 10
    # by default, so its rates are reported and NOT judged.
    # The EFFECTIVE speedup, not the requested one. PX4 SIH ignores the flag
    # and always runs real time, so keying this off args.speedup skipped the
    # check on every default PX4 run -- the guard silently guarding nothing.
    eff_speedup = effective_speedup(args.platform, args.speedup)
    rate_comparable = eff_speedup == 1
    rate_drift = []
    if rate_comparable:
        for r in rows:
            dec, meas = r["declared_rate_hz"], r["measured_rate_hz"]
            if dec and meas and not (0.5 * dec <= meas <= 2.0 * dec):
                rate_drift.append({"channel": r["channel"], "declared_hz": dec,
                                   "measured_hz": meas,
                                   "factor": round(meas / dec, 3)})
    if rate_drift:
        print(f"\n=== declared rate disagrees with measurement "
              f"({len(rate_drift)} channel(s)); MaxAge derives from the "
              f"declared rate, so this decides staleness")
        for d in rate_drift:
            print(f"    {d['channel']:22s} declared {d['declared_hz']:>5} Hz  "
                  f"measured {d['measured_hz']:>7} Hz  ({d['factor']}x)")
    elif not rate_comparable:
        print(f"\n=== rate drift NOT assessed: effective speedup "
              f"{eff_speedup} inflates wall-clock rates; re-run with "
              f"--speedup 1 to judge them")

    stub_rows = [r for r in rows
                 if r["observed"] == Quality.STUB_OR_NONINFORMATIVE.value
                 and r["samples"] > 0]
    print(f"\n=== observed stubs: {len(stub_rows)}")
    for r in stub_rows:
        flag = "declared" if not r["admissible"] else "*** ADMISSIBLE ***"
        print(f"    {r['channel']:26s} {r['detail']}  [{flag}]")

    admitted_stub = [r for r in stub_rows if r["admissible"]]

    # RULE A on the instrument itself, applied to the RIGHT claims.
    #
    # The first version of this gate voided the whole run when the airframe did
    # not move, and that threw away findings that do not depend on motion at
    # all. A PX4 run collected 18,800 samples, established that imu1.*, esc.*
    # and battery.current never arrive on SIH, and reported none of it.
    #
    # Two kinds of claim, two different validity conditions:
    #
    #   PRESENCE    "this channel never arrived" -- motion-independent. A
    #               message that is not published is not published whether or
    #               not the vehicle flew.
    #   CONSTANCY   "this channel is a stub" -- motion-DEPENDENT. On a static
    #               airframe "constant" means "nothing happened", which is a
    #               statement about the trial, not about the channel.
    #
    # So presence findings are always issued and constancy findings are gated.
    probe_valid = bool(motion["armed"] and motion["climbed_m"] >= 1.0)
    absent_rows = [r for r in rows if r["observed"] == "UNAVAILABLE"]
    absent_but_expected = [r for r in absent_rows if r["admissible"]]

    # A channel whose MEANING depends on a heading reference cannot be graded
    # on a run that had none. Same shape as the decoder guard: narrow the
    # claim to what the evidence supports instead of voiding the whole run.
    heading_voided = []
    if heading_broken:
        for r in rows:
            if r["channel"] in HEADING_DEPENDENT_CHANNELS:
                r["observed"] = "UNVERIFIED_HEADING"
                r["agrees"] = None
                r["detail"] = (f"the estimator had no valid heading reference "
                               f"({provenance['verdict']}), so this channel's "
                               f"values carry no interpretable heading and no "
                               f"claim is issued")
                heading_voided.append(r["channel"])
        disagreements = [r for r in disagreements
                         if r["channel"] not in heading_voided]
        absent_rows = [r for r in rows if r["observed"] == "UNAVAILABLE"]
        absent_but_expected = [r for r in absent_rows if r["admissible"]]

    # RULE A applied to the DECODER, and it dominates every other verdict.
    #
    # A blind spot is not a result. If the contract depends on a message this
    # parser could not read, the run cannot say whether the platform provides
    # that channel, and a PASS or a FAIL would both be assertions the evidence
    # does not support. INSTRUMENT_DEAD is the existing name for this in
    # csia/simulation/contract.py and it means the same thing here.
    if heading_broken:
        verdict = (f"INSTRUMENT_DEAD: {provenance['verdict']} -- the "
                   f"estimator had no valid heading reference, so "
                   f"{len(heading_voided)} heading-dependent channel(s) "
                   f"carry no interpretable value")
    elif blind:
        verdict = ("INSTRUMENT_DEAD: the decoder could not read "
                   + ", ".join(sorted({b["message"] for b in blind.values()}))
                   + f", which {len(blind)} contract channel(s) depend on; "
                     "no presence or constancy claim is issued for them")
    elif probe_valid:
        if admitted_stub:
            verdict = "FAIL: a stub channel is admissible as evidence"
        elif absent_but_expected:
            verdict = ("FAIL: a channel the contract admits as evidence "
                       "never arrived")
        else:
            verdict = "PASS"
    elif absent_but_expected:
        # Motion was not demonstrated, so no constancy claim is made -- but an
        # admissible channel that never arrived is a contract defect on any
        # trial, and suppressing it would hide a real integration gap.
        verdict = ("PARTIAL: no motion, so constancy is not assessed; "
                   "PRESENCE findings stand and a channel the contract "
                   "admits as evidence never arrived")
    else:
        verdict = ("INVALID_PROBE: the airframe did not move, so constancy "
                   "is uninformative; presence findings stand and show no "
                   "missing admissible channel")

    token = verdict.split(":", 1)[0].strip()
    exit_code = verdict_exit_code(verdict)

    result = {
        "platform": args.platform,
        "seconds": args.seconds,
        "messages": msgs,
        "counters": adapter.counters,
        "unmapped_types": unmapped,
        # The narrowings applied to this run, verbatim from the contract with
        # their evidence. A PASS reached by narrowing must show what it
        # narrowed, in the same file as the PASS.
        # WHICH contract this run qualified. A result that cannot name the
        # contract it was measured against cannot be compared with a later
        # one -- and the version sat at 1 through five commits that changed
        # what CSIA may consume, so "the contract" was not one thing.
        "contract_version": adapter.contract.version,
        "contract_path": os.path.relpath(adapter.contract.path, ROOT),
        "platform_contract_rows": narrowed,
        "rate_drift": rate_drift,
        "rate_drift_assessed": rate_comparable,
        "speedup_requested": args.speedup,
        "speedup_effective": eff_speedup,
        # What actually did the decoding, and what it could not read. A reader
        # asking "is this row a fact about PX4 or a fact about pymavlink?"
        # must be able to answer it from the result file without rerunning
        # anything -- that question had no answer in the previous format, and
        # a decoder limitation was published as a platform property because of
        # it.
        "decoder": {
            **(dialect.to_dict() if dialect else
               {"vehicle_dialect_active": False,
                "reason": "no dialect report; library default in use"}),
            "undecodable_frames": {
                str(mid): {"name": names.get(mid), "frames": count}
                for mid, count in sorted(undecodable.items())},
            "blind_channels": blind,
            "rule": "an undecodable producer makes the channel UNDECODABLE, "
                    "never UNAVAILABLE",
        },
        "positive_control": {
            # Everything the rig recorded, not a hand-picked subset.
            #
            # This dict used to name six keys explicitly and silently dropped
            # the rest, so takeoff_ack, arm_ack and takeoff_alt_param -- added
            # specifically to diagnose a failing climb -- never reached the
            # result file. An instrument that collects evidence and then
            # discards it is the same defect as the verdict gate that voided
            # presence findings, and this is the third time today.
            **{k: v for k, v in motion.items() if k != "alt_samples"},
            "armed": motion["armed"],
            "climbed_m": round(motion["climbed_m"], 2),
            "alt_samples": len(motion["alt_samples"]),
            "satisfied": probe_valid,
            "rule": "RULE A -- an informativeness probe needs a positive "
                    "control; motion is it",
            "gates": "CONSTANCY claims only; PRESENCE claims are "
                     "motion-independent and are always issued",
        },
        # Motion-independent findings. Reported on every run, valid or not.
        "presence_findings": {
            "never_arrived": [r["channel"] for r in absent_rows],
            "never_arrived_but_admissible": [r["channel"]
                                             for r in absent_but_expected],
            # Absent for a DIFFERENT reason: the producer arrived and said it
            # has nothing. Split out so "PX4 does not publish battery current"
            # cannot be written from a row that means "PX4 has no current
            # sensor fitted".
            "sentinel_counts": adapter.sentinel_counts(),
        },
        # FOUR flags, because there are four ways a run can be invalid and
        # collapsing them loses which one happened: the airframe did not move,
        # the decoder could not read a producer, the estimator had no heading
        # reference, or nothing went wrong. PROBE_VALID is the conjunction and
        # is what a caller should read; the others say why it is false.
        # Row-level gating still keys off the motion control alone -- a blind
        # or heading-voided channel is marked in its own row, so the remaining
        # rows stay readable instead of being voided wholesale.
        "PROBE_VALID": probe_valid and not blind and not heading_broken,
        "MOTION_CONTROL_SATISFIED": probe_valid,
        "DECODER_COMPLETE": not blind,
        # Separate from PROBE_VALID on purpose: "the heading reference was
        # checked and was good" and "we could not check it" must never read
        # the same, and only this flag distinguishes them.
        "HEADING_VERIFIED": heading_verified,
        "estimator_provenance": provenance,
        "heading_voided_channels": heading_voided,
        "undecodable_channels": sorted(blind),
        "rows": rows if probe_valid else [],
        "rows_unscored": [] if probe_valid else rows,
        "disagreements": disagreements if probe_valid else [],
        "observed_stubs": [r["channel"] for r in stub_rows] if probe_valid else [],
        "admissible_stubs": [r["channel"] for r in admitted_stub] if probe_valid else [],
        "verdict": verdict,
    }
    out = args.out or os.path.join(
        ROOT, "research", "v1_1", "results",
        f"qualification_{args.platform}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True, default=str)
    print(f"\n{result['verdict']}")
    print(f"-> {os.path.relpath(out, ROOT)}")
    if exit_code is None:
        print(f"!!! no exit code mapped for verdict token {token!r} -- "
              f"treating as failure rather than reporting success")
        return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
