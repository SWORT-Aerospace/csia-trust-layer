"""POST-HOC model sensitivity: what does the banked state S0 actually buy?

THIS WAS NOT PREREGISTERED. `research/v1_1/CURRENT_STACK_REPLICATION.md` fixed
the campaign, the endpoints and the classification rule before the first trial;
this analysis was written afterwards, against traces that were already on disk.
It is reported as POST-HOC MECHANISTIC SUPPORT and nothing stronger. No trial
was re-run, no threshold moved, no parameter fitted.

THE QUESTION. The completed campaign shows a persistence contrast: a 50 m step
does not cross T* = 0.75 and a 20 s ramp to the same endpoint does, 5/5. That
establishes the contrast. It does NOT by itself establish that the *banked
history* is what sets the crossing time -- the phrase "history-dominated" is a
Phase-I analytical result for a Phase-I parameter set, and the modern campaign
did not test it.

WHAT CAN BE ASKED OF THE EXISTING TRACES. The recursion

    S(k) = rho(k)*S(k-1) + 1
    T(k) = ( rho(k)*S(k-1)*T(k-1) + e(k) ) / S(k)

takes the measured evidence stream e(k) and the measured forgetting factor
rho(k) as inputs. Holding BOTH of those streams exactly as recorded and
changing ONLY the initial banked state isolates the contribution of S0:

    alpha0 = S0*T0,  beta0 = S0*(1 - T0)

S0 = 0 is mathematically valid and is the clean limiting case: S(1) = 1 and
T(1) = e(1), i.e. a node with no history simply adopts the incoming evidence.

If the crossing tick moves monotonically and materially with S0, the banked
state is doing the work, on this platform, for this fault. That is a mechanism
statement supported by measurement rather than an assumed carry-over from 2015.

  python tools/simulation/s0_sensitivity_posthoc.py
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "simulation"))

from mechanism_b_report import read_trace                  # noqa: E402
from current_stack_replication import (                    # noqa: E402
    THRESHOLD, first_index_at_or_after, prepare)

# Declared fractions of the measured S0. Fixed here, in the tool, so the set
# cannot be quietly widened until one of them looks good.
FRACTIONS = (0.0, 0.25, 0.5, 1.0)


def roll(rows, i0, S0, T0):
    """Step the recursion from a SUPPLIED banked state.

    e(k) and rho(k) come from the recorded trace and are never altered. Only
    the initial condition changes.
    """
    S, T = float(S0), float(T0)
    if S <= 0.0:
        # No banked history. S(1) = rho*0 + 1 = 1 and T(1) = e(1): the node
        # adopts the incoming evidence outright. Well defined, not a hack.
        S, T = 0.0, float(T0)
    out = []
    for i in range(i0, len(rows)):
        r = rows[i]
        if i > i0 and r["updated"]:
            S_prev, T_prev = S, T
            S = r["rho"] * S_prev + 1.0
            T = (r["rho"] * S_prev * T_prev + r["e"]) / S
        out.append((r["t"], S, T))
    return out


def crossing(traj):
    for k, (_t, _S, T) in enumerate(traj):
        if T <= THRESHOLD:
            return k
    return None


def analyse(result_path):
    with open(result_path, encoding="utf-8") as fh:
        res = json.load(fh)
    trace = os.path.join(ROOT, res.get("trust_trace") or "")
    if not os.path.exists(trace):
        return None
    header, steps = read_trace(trace)
    rows = prepare(steps, header["engine_config"])
    inj = res.get("injection") or {}
    i0 = first_index_at_or_after(
        rows, float(inj.get("wrote_at_rel_s") or inj.get("at_s") or 0.0))
    if i0 is None:
        return None
    S0 = rows[i0]["S_runtime"]
    T0 = rows[i0]["T_runtime"]

    out = {"trial": os.path.basename(result_path).replace(".json", ""),
           "S0_measured": S0, "T0_measured": T0, "onset_tick": i0,
           "variants": []}
    for f in FRACTIONS:
        traj = roll(rows, i0, S0 * f, T0)
        k = crossing(traj)
        out["variants"].append({
            "S0_fraction": f,
            "S0_used": round(S0 * f, 4),
            "crossing_tick": k,
            "crossed": k is not None,
            "T_min": round(min(T for _, _, T in traj), 6),
        })
    # positive control: fraction 1.0 must reproduce the runtime crossing
    base = next(v for v in out["variants"] if v["S0_fraction"] == 1.0)
    runtime_cross = crossing([(r["t"], 0, r["T_runtime"]) for r in rows[i0:]])
    out["positive_control"] = {
        "runtime_crossing_tick": runtime_cross,
        "reconstruction_at_S0_measured": base["crossing_tick"],
        "agree": runtime_cross == base["crossing_tick"],
        "rule": "fraction 1.0 is the unmodified reconstruction; if it does "
                "not reproduce the runtime crossing the sensitivity below is "
                "describing something other than this flight",
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", default=os.path.join(
        ROOT, "research", "v1_1", "results", "mechanism_b_gps"))
    ap.add_argument("--condition", default="RAMP_20S")
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results", "s0_sensitivity_posthoc.json"))
    args = ap.parse_args()

    trials = []
    for p in sorted(glob.glob(os.path.join(
            args.results, f"ardupilot_{args.condition}_*.json"))):
        r = analyse(p)
        if r:
            trials.append(r)
    if not trials:
        print("no trials found")
        return 2

    print(f"=== POST-HOC S0 sensitivity, {args.condition} "
          f"(NOT preregistered)")
    print(f"  crossing tick at T* = {THRESHOLD}, by initial banked state\n")
    hdr = "  " + f"{'trial':22s}" + "".join(
        f"{'S0x' + str(f):>10s}" for f in FRACTIONS) + f"{'control':>9s}"
    print(hdr)
    for t in trials:
        cells = "".join(
            f"{(str(v['crossing_tick']) if v['crossed'] else 'none'):>10s}"
            for v in t["variants"])
        print(f"  {t['trial']:22s}{cells}"
              f"{('ok' if t['positive_control']['agree'] else 'MISMATCH'):>9s}")

    # aggregate, per fraction
    print()
    for f in FRACTIONS:
        ks = [v["crossing_tick"] for t in trials
              for v in t["variants"] if v["S0_fraction"] == f]
        got = [k for k in ks if k is not None]
        S0s = [v["S0_used"] for t in trials
               for v in t["variants"] if v["S0_fraction"] == f]
        if got:
            print(f"  S0 x {f:<5} (S0 = {min(S0s):.1f}-{max(S0s):.1f}): "
                  f"crossing ticks {min(got)}-{max(got)}, "
                  f"{len(got)}/{len(ks)} crossed")
        else:
            print(f"  S0 x {f:<5}: no crossing in {len(ks)} trials")

    out = {
        "status": "POST-HOC MECHANISTIC SUPPORT -- NOT PREREGISTERED",
        "what_was_held_fixed": "the recorded per-tick e(k) and rho(k) streams",
        "what_was_varied": "only the initial banked state, via "
                           "alpha0 = S0*T0 and beta0 = S0*(1-T0)",
        "fractions": list(FRACTIONS),
        "threshold": THRESHOLD,
        "condition": args.condition,
        "trials": trials,
        "caveats": [
            "not preregistered; written after the campaign, against traces "
            "already on disk",
            "no trial was re-run, no threshold moved, no parameter fitted",
            "this does not define a 'dominance threshold' and none is claimed",
            "one platform, one fault family, n=5",
        ],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"\n-> {os.path.relpath(args.out, ROOT)}")
    return 0 if all(t["positive_control"]["agree"] for t in trials) else 1


if __name__ == "__main__":
    sys.exit(main())
