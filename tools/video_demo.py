"""One-command live demo of the interceptor_seeker trust layer (SYNTHETIC).

For screen recording. Plays a clean closing engagement at 100 Hz in
wall-clock time with a big, readable terminal view of the three channel
Trust Coefficients, the diagnosis, and the engagement-confidence level.

Interactive (a TTY): press ENTER to INJECT the fault live into the running
engagement; press ENTER again to CLEAR it (recovery/de-escalation on screen).
Non-interactive / `--auto`: scripted timed injection with a visible
countdown (same visual result, deterministic).

Live keypress injection is achieved WITHOUT modifying the runtime core: the
engagement is deterministic and seeded, so a run regenerated with the fault
onset set to the keypress time is bit-identical before that instant — the
tool seamlessly switches to the faulted timeline at the moment you press.

  python tools/video_demo.py                    # ir_decoy, interactive
  python tools/video_demo.py --scenario rf_jam  # second take
  python tools/video_demo.py --auto             # scripted (for CI / piped)
"""

import argparse
import os
import select
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csia.seeker import run_seeker
from csia.seeker.runtime import DETECT_TRUST, SeekerConfig

CHANNELS = ("ir_seeker", "rf_seeker", "ins")
FAULTED = {"ir_decoy": "ir_seeker", "rf_jam": "rf_seeker"}
FAULT_PARAMS = {
    "ir_decoy": {"kind": "ir_decoy", "offset_deg": 6.0, "ramp_s": 1.5},
    "rf_jam": {"kind": "rf_jam", "az_bias_deg": 4.0, "rrate_bias": 40.0,
               "var_mult": 4.0, "ramp_s": 2.0},
}
WARMUP = SeekerConfig().arm_time


def _bar(v, width=40):
    n = int(round(max(0.0, min(1.0, v)) * width))
    block = "#" * n + "-" * (width - n)
    tag = "OK " if v >= 0.85 else ("LOW" if v >= 0.55 else "!!!")
    return f"[{block}] {v:0.2f} {tag}"


def _render(scenario, t, trust, top_cause, top_p, level, phase_msg):
    os.system("clear" if os.name != "nt" else "cls")
    print("=" * 62)
    print(f"  CSIA interceptor_seeker  —  LIVE DEMO  [SYNTHETIC]")
    print(f"  scenario: {scenario:12s}   t = {t:5.2f} s")
    print("=" * 62)
    for ch in CHANNELS:
        print(f"  {ch:10s} {_bar(trust[ch])}")
    print("-" * 62)
    print(f"  DIAGNOSIS : {top_cause}  ({100*top_p:.0f}%)")
    print(f"  CONFIDENCE: {level}")
    print("-" * 62)
    print(f"  {phase_msg}")
    print("=" * 62, flush=True)


def _key_pressed():
    if not sys.stdin.isatty():
        return False
    r, _, _ = select.select([sys.stdin], [], [], 0)
    return bool(r) and bool(sys.stdin.readline())


def _top_cause(res, k):
    best_c, best_p = "nominal", res.diag["nominal"][k]
    for c in res.causes:
        if c != "nominal" and res.diag[c][k] > best_p:
            best_c, best_p = c, res.diag[c][k]
    # report the leading non-nominal cause once it is meaningful
    nn = [(c, res.diag[c][k]) for c in res.causes if c != "nominal"]
    c2, p2 = max(nn, key=lambda x: x[1])
    if p2 > 0.5:
        return c2, p2
    return "nominal", res.diag["nominal"][k]


def _level_at(res, t):
    lvl = "NORMAL"
    for tr in res.transitions:
        if tr["t"] <= t:
            lvl = tr["to"]
    return lvl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=("ir_decoy", "rf_jam"),
                    default="ir_decoy")
    ap.add_argument("--auto", action="store_true",
                    help="scripted timed injection (no keypress)")
    ap.add_argument("--inject-after", type=float, default=5.0,
                    help="[auto] seconds after warmup to inject")
    ap.add_argument("--clear-after", type=float, default=5.0,
                    help="[auto] seconds after injection to clear")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--speed", type=float, default=1.0,
                    help="playback speed multiplier")
    args = ap.parse_args()
    interactive = sys.stdin.isatty() and not args.auto

    eng, clean = run_seeker([], tick_hz=100.0, seed=args.seed)
    dt = eng.dt / max(args.speed, 1e-6)
    tarr = clean.t
    faulted_ch = FAULTED[args.scenario]

    active = clean            # current timeline being played
    inject_t = None; clear_t = None
    detected = False
    auto_inject_t = WARMUP + args.inject_after
    print("Starting clean engagement… "
          + ("press ENTER to inject the fault." if interactive
             else f"[auto] injecting at t={auto_inject_t:.1f}s"))
    time.sleep(1.0)

    k = 0
    n = len(tarr)
    last_level = "NORMAL"
    while k < n:
        t = tarr[k]
        # --- injection trigger ------------------------------------------
        if inject_t is None:
            fire = (_key_pressed() if interactive else t >= auto_inject_t)
            if fire and t > WARMUP:
                inject_t = t
                fp = dict(FAULT_PARAMS[args.scenario]); fp["start"] = inject_t
                eng, active = run_seeker([fp], tick_hz=100.0, seed=args.seed)
        # --- clear trigger ----------------------------------------------
        elif clear_t is None:
            fire = (_key_pressed() if interactive
                    else t >= inject_t + args.clear_after)
            if fire:
                clear_t = t
                fp = dict(FAULT_PARAMS[args.scenario])
                fp["start"] = inject_t; fp["end"] = clear_t
                eng, active = run_seeker([fp], tick_hz=100.0, seed=args.seed)

        trust = {ch: active.trust[ch][k] for ch in CHANNELS}
        top_c, top_p = _top_cause(active, k)
        level = _level_at(active, t)
        if level != last_level:
            print(f"\a>>> ENGAGEMENT-CONFIDENCE: {last_level} -> {level} "
                  f"@ t={t:.2f}s", flush=True)
            last_level = level
            time.sleep(0.4)
        if inject_t and not detected and t > inject_t \
                and trust[faulted_ch] < DETECT_TRUST:
            detected = True

        if inject_t is None:
            phase = "CLEAN — all channels trusted. " + (
                "PRESS ENTER TO INJECT." if interactive else
                f"auto-inject in {max(0, auto_inject_t - t):3.1f}s")
        elif clear_t is None:
            phase = (f">>> FAULT ACTIVE ({args.scenario}) since t={inject_t:.1f}s"
                     + ("  — DETECTED!" if detected else "  — detecting…")
                     + ("  press ENTER to clear." if interactive else ""))
        else:
            phase = f"FAULT CLEARED at t={clear_t:.1f}s — watch recovery."

        if k % 4 == 0:      # ~25 fps redraw
            _render(args.scenario, t, trust, top_c, top_p, level, phase)
        time.sleep(dt * 4 if k % 4 == 0 else 0)
        k += 4              # advance 4 ticks per rendered frame

    print("\nEngagement complete.")
    if inject_t:
        print(f"  fault injected t={inject_t:.2f}s, "
              f"{'detected' if detected else 'NOT detected'}"
              + (f", cleared t={clear_t:.2f}s" if clear_t else ""))
        print(f"  min trust on {faulted_ch}: "
              f"{active.trust[faulted_ch][tarr > (inject_t or 0)].min():.2f}")


if __name__ == "__main__":
    main()
