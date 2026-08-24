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
from csia.aircraft.qualification import default_contract  # noqa: E402
from csia.aircraft.sample import Quality                  # noqa: E402
from csia.simulation.rigs import LAUNCHERS, connect, fly  # noqa: E402


# A channel is INFORMATIVE only if it varies. The floor is deliberately tiny:
# we are separating "constant" from "not constant", not judging magnitude.
CONSTANT_EPS = 1e-9


def _scalarize(v):
    """Reduce any channel value to one number for variation testing."""
    if v is None:
        return None
    if isinstance(v, dict):
        nums = [x for x in v.values() if isinstance(x, (int, float))]
        return float(sum(nums)) if nums else None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return float(abs(hash(v)) % 1000)
    try:
        out = float(np.sum(np.asarray(v, dtype=float)))
    except Exception:
        return None
    # A NaN or inf is not a sample. Letting one through crashed pstdev and,
    # worse, would have let a corrupt value decide a channel's verdict.
    return out if math.isfinite(out) else None


def observe(platform, duration_s, conn, adapter):
    """Collect per-channel observations from the live stream."""
    obs = {ch: [] for ch in adapter.contract.channels}
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
            s = _scalarize(entry[0])
            if s is not None:
                obs.setdefault(ch, []).append(s)
    return obs, msgs


def analyse(obs, raw_present, contract):
    rows = []
    for ch, row in sorted(contract.channels.items()):
        vals = obs.get(ch, [])
        n = len(vals)
        if n == 0:
            observed = Quality.UNAVAILABLE
            spread = None
            detail = "never arrived"
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
        agrees = (observed == declared) or (
            declared in (Quality.VALIDATED_SEMANTICS,
                         Quality.AVAILABLE_UNVALIDATED)
            and observed is Quality.INFORMATIVE)
        rows.append({
            "channel": ch,
            "declared": declared.value,
            "observed": observed.value,
            "agrees": agrees,
            "may_use": row.may_use,
            "admissible": row.admissible,
            "criterion": row.criterion,
            "samples": n,
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
        obs, msgs = observe(args.platform, args.seconds, conn, adapter)
        rows = analyse(obs, {}, adapter.contract)
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"\n=== {msgs} messages, {adapter.counters['mapped']} mapped, "
          f"{adapter.counters['unmapped']} unmapped")
    unmapped = adapter.unmapped_types()
    if unmapped:
        top = sorted(unmapped.items(), key=lambda kv: -kv[1])[:8]
        print("    unmapped types: " +
              ", ".join(f"{k}x{v}" for k, v in top))

    print(f"\n{'channel':26s} {'declared':24s} {'observed':24s} agree")
    disagreements = []
    for r in rows:
        mark = "yes" if r["agrees"] else "NO"
        print(f"{r['channel']:26s} {r['declared']:24s} "
              f"{r['observed']:24s} {mark}")
        print(f"{'':26s}   {r['detail']}")
        if not r["agrees"]:
            disagreements.append(r)

    stub_rows = [r for r in rows
                 if r["observed"] == Quality.STUB_OR_NONINFORMATIVE.value
                 and r["samples"] > 0]
    print(f"\n=== observed stubs: {len(stub_rows)}")
    for r in stub_rows:
        flag = "declared" if not r["admissible"] else "*** ADMISSIBLE ***"
        print(f"    {r['channel']:26s} {r['detail']}  [{flag}]")

    admitted_stub = [r for r in stub_rows if r["admissible"]]

    # RULE A on the instrument itself. Without demonstrated motion, "constant"
    # means "nothing happened", not "this channel is a stub", and no channel
    # verdict may be issued from this run.
    probe_valid = bool(motion["armed"] and motion["climbed_m"] >= 1.0)
    if probe_valid:
        verdict = ("FAIL: a stub channel is admissible as evidence"
                   if admitted_stub else "PASS")
    else:
        verdict = ("INVALID_PROBE: the airframe did not move, so constancy "
                   "is uninformative and no channel verdict is issued")

    result = {
        "platform": args.platform,
        "seconds": args.seconds,
        "messages": msgs,
        "counters": adapter.counters,
        "unmapped_types": unmapped,
        "positive_control": {
            "armed": motion["armed"],
            "climbed_m": round(motion["climbed_m"], 2),
            "alt_samples": len(motion["alt_samples"]),
            "satisfied": probe_valid,
            "rule": "RULE A -- an informativeness probe needs a positive "
                    "control; motion is it",
        },
        "PROBE_VALID": probe_valid,
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
    if not probe_valid:
        return 2
    return 1 if admitted_stub else 0


if __name__ == "__main__":
    sys.exit(main())
