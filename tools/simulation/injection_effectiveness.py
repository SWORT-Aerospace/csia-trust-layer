"""Did every injection actually reach the vehicle? One table, one convention.

RULE B in one place. Every injection in this repository declares a downstream
observable -- the thing that must be true of the VEHICLE, not of the command,
before a trial counts:

    gps_fix_loss   gnss.position goes MISSING with NO_3D_FIX
    mag_emi        mag.field_ut shifts by u*sqrt(3) uT across the onset
    gps_glitch     reported gnss.position offsets by the commanded metres
                   while the fix is preserved

That logic currently lives in three separate report tools, written at three
different times, with three slightly different tolerance conventions and three
different ideas of what "confirmed" means. Three implementations of one rule is
how the conventions drift apart without anyone noticing, and drift in THIS rule
decides which trials count.

This reads every committed campaign and applies ONE convention to all of them.
It changes none of the existing tools and re-runs nothing; it is a cross-check
that they agree with each other and with the artifacts.

  python tools/simulation/injection_effectiveness.py
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CAMPAIGNS = (
    "research/v1_1/results/mechanism_b_gps/*.json",
    "research/v1_1/results/mechanism_b/*.json",
    "research/v1_1/results/mechanism_a/*.json",
    "research/v1_1/results/shadow_flights/*.json",
)
# ONE tolerance, applied to every injection family that declares a magnitude.
REL_TOL = 0.40


def ticks_of(result):
    fid, ld = result.get("flight_id"), result.get("log_dir")
    if not fid or not ld:
        return
    for path in sorted(glob.glob(os.path.join(ROOT, ld, "*.jsonl"))):
        if fid not in os.path.basename(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("record") == "tick":
                    yield rec


def observable(result):
    """The declared downstream observable for this trial, measured."""
    inj = result.get("injection") or {}
    kind = inj.get("kind")
    if not kind:
        return {"kind": None, "role": "control (no injection declared)"}
    onset = float(inj.get("wrote_at_rel_s") or inj.get("at_s") or 0.0)

    if kind == "gps_fix_loss":
        n = sum(1 for t in ticks_of(result)
                if ((t.get("canonical") or {}).get("channels", {})
                    .get("gnss.position", {}) or {}).get("missing")
                == "NO_3D_FIX")
        return {"kind": kind, "observable": "NO_3D_FIX ticks",
                "observed": n, "expected": "> 0",
                "effective": n > 0}

    if kind in ("mag_emi", "gps_glitch"):
        # ONE post-window per family, chosen to match what that injection
        # actually does. An earlier version of this tool OR-ed the two
        # windows together and pooled samples from 0.4-2.4 s AND 15-25 s,
        # which produced numbers that agreed with neither original tool --
        # the exact convention drift this file exists to catch, caught in
        # this file first.
        #
        # mag_emi is a STEP: the field moves at onset and holds, so the
        # shift is measured just after it. gps_glitch RAMPS for 20 s, so it
        # must be measured after the ramp completes.
        chan = "mag.field_ut" if kind == "mag_emi" else "gnss.position"
        lo, hi = ((onset + 0.4, onset + 2.4) if kind == "mag_emi"
                  else (onset + 15.0, onset + 25.0))
        pre, post = [], []
        for t in ticks_of(result):
            cv = ((t.get("canonical") or {}).get("channels") or {}).get(chan)
            if not cv or not cv.get("usable"):
                continue
            v = cv.get("value")
            tm = float(t["t_mono"])
            if onset - 2.5 <= tm < onset:
                pre.append(v)
            elif lo <= tm <= hi:
                post.append(v)
        if not pre or not post:
            return {"kind": kind, "observable": chan,
                    "observed": None, "effective": None,
                    "note": "channel not observable around onset"}
        if kind == "mag_emi":
            u = float(inj.get("micro_tesla_per_axis") or 0.0)
            want = abs(u) * math.sqrt(3.0)
            mp = [sum(v[i] for v in pre) / len(pre) for i in range(3)]
            mq = [sum(v[i] for v in post) / len(post) for i in range(3)]
            got = math.sqrt(sum((mq[i] - mp[i]) ** 2 for i in range(3)))
        else:
            want = float(inj.get("metres") or 0.0)
            got = (sum(v[0] for v in post) / len(post)
                   - sum(v[0] for v in pre) / len(pre))
        if want == 0.0:
            eff = None                      # null control: nothing to detect
        else:
            eff = (1 - REL_TOL) * want <= got <= (1 + REL_TOL) * want
        return {"kind": kind, "observable": f"{chan} shift",
                "observed": round(got, 4), "expected": round(want, 4),
                "effective": eff,
                "is_null_control": want == 0.0}
    return {"kind": kind, "observable": "unknown family", "effective": None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results", "INJECTION_EFFECTIVENESS.json"))
    args = ap.parse_args()

    rows = []
    for pat in CAMPAIGNS:
        for path in sorted(glob.glob(os.path.join(ROOT, pat))):
            if os.path.basename(path).startswith("campaign_"):
                continue
            with open(path, encoding="utf-8") as fh:
                res = json.load(fh)
            inj = res.get("injection") or {}
            obs = observable(res)
            rows.append({
                "trial": os.path.basename(path).replace(".json", ""),
                "campaign": os.path.basename(os.path.dirname(path)),
                "platform": res.get("platform"),
                "kind": obs.get("kind"),
                "readback_confirmed": inj.get("confirmed"),
                **{k: v for k, v in obs.items() if k != "kind"},
            })

    print("=== injection effectiveness, one convention for every campaign "
          f"(+/-{int(REL_TOL * 100)} %)")
    print(f"  {'trial':26s} {'kind':12s} {'readback':9s} "
          f"{'observed':>10s} {'expected':>10s}  effective")
    disagree = []
    for r in rows:
        if r["kind"] is None:
            continue
        eff = r.get("effective")
        mark = {True: "yes", False: "NO", None: "n/a (null)"}[eff]
        print(f"  {r['trial']:26s} {str(r['kind']):12s} "
              f"{str(r['readback_confirmed']):9s} "
              f"{str(r.get('observed')):>10s} {str(r.get('expected')):>10s}  "
              f"{mark}")
        # The cross-check that matters: a confirmed WRITE with an ineffective
        # downstream observable means the command landed and the vehicle did
        # not respond, which is a failed trial that readback alone calls good.
        if r["readback_confirmed"] and eff is False:
            disagree.append(r["trial"])
    if disagree:
        print("\n  !! readback CONFIRMED but the downstream observable failed:")
        for t in disagree:
            print(f"     {t}")
        print("     The command reached the vehicle and the vehicle did not "
              "respond. Readback alone would have called these valid.")

    out = {"convention": {"relative_tolerance": REL_TOL,
                          "rule": "RULE B -- the parameter write is not the "
                                  "measurement; the vehicle's response is"},
           "trials": rows,
           "readback_confirmed_but_ineffective": disagree}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    return 1 if disagree else 0


if __name__ == "__main__":
    sys.exit(main())
