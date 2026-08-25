"""Why is each evidence relation live or dark on this platform? One ledger.

THE RECURRING COST THIS EXISTS TO END. Three times now the declared rate of a
channel has failed to describe what arrived, and each time it silently starved
evidence rather than failing:

    esc.current   declared 10 Hz, measured 0.97
    mag.field_ut  declared 50 Hz, measured 13.9
    baro.altitude declared 10 Hz, measured 1.00   <- found by this line of work

Whenever the declaration is FASTER than the arrivals, the derived `max_age`
(MAX_AGE_MARGIN / rate) is shorter than the real inter-arrival, so the channel
spends part of every period STALE, the NODE stops being fresh, and every
relation with that node as an endpoint quietly stops carrying weight. The layer
does not complain: absence of evidence is handled correctly, so nothing looks
broken. The consequence only appears if someone thinks to measure which
relations were actually live -- which has, until now, happened by hand and
after the fact.

The baro case is the sharpest, and it is NOT a wrong number in the contract.
Declared 10 Hz gives max_age 0.50 s against a measured 1.00 s inter-arrival, so
`baro.altitude` was STALE on 505 of 1001 ticks, the baro node was fresh on
8.2 %, and `altitude_baro` -- the only baro/GNSS cross-check -- carried weight
on 8.1 % of PX4 ticks against 99.9 % on ArduPilot.

The declaration and the flight logs are BOTH correct, because on PX4 the rate
is a property of the LINK rather than of the platform: it is set by whoever
last transmitted SET_MESSAGE_INTERVAL on that link. `qualification_px4.json`
measured 9.825 Hz on a link that requested 10 Hz; CSIA binds a passive
companion link and may not transmit, so nothing ever raises its rates and the
same channel arrives at 1.00 Hz. Measured three ways in one simulator run by
`tools/simulation/px4_link_rate_probe.py`; see
`research/v1_1/results/PX4_LINK_RATE_PROBE.json`.

So a flagged rate here means "the declaration does not describe the link CSIA
bound", which is a real defect with real starvation downstream -- but the fix
is to drive that link, not to edit the number. Editing the number was tried
first and was wrong: it would have replaced one link-conditional constant with
another and broken the qualification probe, which measures the other link.

WHAT THIS JOINS, in one table per platform, per relation:

  gate expression   extracted from the FROZEN source, so "why is it dark" is a
                    lookup instead of a source-reading exercise
  endpoints         which nodes the relation needs alive
  declared rate     what the contract says each endpoint's channel publishes at
  measured rate     what it actually published, counted from flight logs
  channel usable    share of ticks the channel was usable
  node fresh        share of ticks the node was fresh
  relation live     share of ticks the relation carried non-zero gate weight
  verdict           LIVE / DARK_STRUCTURAL / DARK_STARVED / RATE_MISDECLARED

DARK_STRUCTURAL and DARK_STARVED are different findings and must not be
confused. Structural means the platform cannot produce the evidence at all --
PX4 has no second IMU, so `redundant_imu` can never be live, and that is a
declared platform fact. Starved means the platform DOES produce it and the
harness threw it away, which is a defect. Only measurement separates them.

Reads committed artifacts and frozen source. Runs nothing, changes nothing.

  python tools/simulation/evidence_coverage_ledger.py
"""

from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.aircraft.adapters.base import MAX_AGE_MARGIN        # noqa: E402
from csia.runtime.online import STALE_TIMEOUT_S               # noqa: E402

ONLINE = os.path.join(ROOT, "csia", "runtime", "online.py")
CONTRACT = os.path.join(ROOT, "docs", "simulation", "CHANNEL_SEMANTICS.yaml")
CAMPAIGNS = (
    "research/v1_1/results/mechanism_b_gps/*.json",
    "research/v1_1/results/mechanism_b/*.json",
    "research/v1_1/results/shadow_flights/*.json",
)
LIVE = 1e-6
# THE ARRIVAL COUNTER CANNOT SEE FASTER THAN THE TICK RATE.
#
# Arrivals are detected as `age_s` resets, and the log has one sample per
# shadow tick, so at most ONE arrival per tick is observable. With random
# phase between the channel and the tick clock the count saturates near HALF
# the tick rate, which is exactly what the data shows: on ArduPilot imu0,
# imu1, baro, gps, mag, battery and vibration all "measure" 12.5 Hz against
# declared rates of 5 to 25. They are not all 12.5 Hz; they are all aliased.
#
# An earlier version of this file reported nine RATE_MISDECLARED findings on
# that basis. Every one above the ceiling was an artifact of the instrument.
# Rates at or above the ceiling are now UNMEASURABLE_AT_TICK_RATE and are
# never called misdeclared -- a measurement that cannot resolve a quantity
# must not testify about it.
TICK_HZ = 25.0
MEASURABLE_CEILING_HZ = 0.8 * (TICK_HZ / 2.0)      # 10 Hz
# Which node each relation needs alive. Read off the edge construction in
# online.py; the extractor below verifies each name still appears there, so a
# renamed relation fails loudly instead of silently dropping out of the table.
ENDPOINTS = {
    "altitude_baro": ("baro", "gps"),
    "velocity_gps_doppler_0": ("gps", "imu0"),
    "velocity_gps_doppler_1": ("gps", "imu1"),
    "heading_course": ("mag", "gps"),
    "attitude_gravity_mag": ("mag", "imu0"),
    "redundant_imu": ("imu0", "imu1"),
    "accel_motor_current": ("imu0", "motor_esc"),
    "accel_esc_rpm": ("imu1", "motor_esc"),
    "power_thrust": ("battery", "motor_esc"),
    "vibration_prop_freq": ("vibration", "motor_esc"),
    "temp_bias_drift": ("baro", "imu0"),
}
NODE_CHANNEL = {
    "baro": "baro.altitude", "gps": "gnss.position", "imu0": "imu0.accel",
    "imu1": "imu1.accel", "mag": "mag.field_ut", "battery": "battery.voltage",
    "motor_esc": "esc.rpm", "vibration": "vibration.rms",
}


# ------------------------------------------------------- gate expressions
def _loop_bindings(node):
    """`name -> [value, ...]` for a `for` over a literal tuple of literals.

    Only string constants at a fixed position are resolved. Anything else
    yields nothing, so an unrecognised loop shape drops out rather than
    guessing a key.
    """
    out = {}
    it = node.iter
    if not isinstance(it, (ast.Tuple, ast.List)) or not it.elts:
        return out
    rows, tgt = it.elts, node.target
    if isinstance(tgt, ast.Name):                    # for key in ("a", "b")
        vals = [r.value for r in rows
                if isinstance(r, ast.Constant) and isinstance(r.value, str)]
        if len(vals) == len(rows):
            out[tgt.id] = vals
    elif isinstance(tgt, ast.Tuple):                 # for a, b, key in ((...),)
        if not all(isinstance(r, (ast.Tuple, ast.List)) for r in rows):
            return out
        for i, name in enumerate(tgt.elts):
            if not isinstance(name, ast.Name):
                continue
            vals = [r.elts[i].value for r in rows
                    if i < len(r.elts) and isinstance(r.elts[i], ast.Constant)
                    and isinstance(r.elts[i].value, str)]
            if len(vals) == len(rows):
                out[name.id] = vals
    return out


def _resolve_key(name, assign):
    """Values a loop variable can take, from the NEAREST enclosing `for`."""
    node = assign
    while node is not None:
        if isinstance(node, ast.For):
            bound = _loop_bindings(node)
            if name in bound:
                return bound[name]
        node = getattr(node, "_parent", None)
    return None


def gate_expressions():
    """`relation -> the gate expression as written in the frozen source`.

    Parsed rather than transcribed, so it cannot drift from the code. Every
    `E["name"] = (..., <gate>)` assignment is picked up and the gate half is
    rendered back to source text.

    LOOP-CONSTRUCTED RELATIONS ARE NOT OPTIONAL. The dual doppler edges are
    written `E[key] = ..., gvalid` inside a `for` over a literal tuple, so the
    subscript is a Name and `literal_eval` cannot read it. An earlier version
    skipped those two silently, and they showed as "NOT FOUND" in the gate
    column -- for `velocity_gps_doppler_0`, the relation that carries the
    flagship GNSS check. A tool whose whole point is "why is this dark" must
    not be blank on the relation most likely to be asked about.
    """
    src = open(ONLINE, encoding="utf-8").read()
    tree = ast.parse(src)
    for parent in ast.walk(tree):                    # parent links, for scoping
        for child in ast.iter_child_nodes(parent):
            child._parent = parent
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        tgt = node.targets[0]
        if not (isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name)
                and tgt.value.id in ("E", "P")):
            continue
        if isinstance(tgt.slice, ast.Name):
            keys = _resolve_key(tgt.slice.id, node)
            if not keys:
                continue
        else:
            try:
                keys = [ast.literal_eval(tgt.slice)]
            except (ValueError, TypeError):
                continue
        val = node.value
        if isinstance(val, ast.Tuple) and len(val.elts) == 2:
            gate = val.elts[1]
            try:
                text = ast.unparse(gate)
            except AttributeError:               # pragma: no cover
                continue
            for key in keys:
                out[key if tgt.value.id == "E" else f"phys_{key}"] = text
    return out


def declared_rates():
    """`channel -> {platform: declared rate}` straight from the contract."""
    out = {}
    chan = None
    for line in open(CONTRACT, encoding="utf-8"):
        m = re.match(r"- channel:\s*(\S+)", line.strip())
        if m:
            chan = m.group(1)
            continue
        m = re.match(r"producer_(\w+):\s*\{.*rate_hz:\s*([0-9.]+)",
                     line.strip())
        if m and chan:
            out.setdefault(chan, {})[m.group(1)] = float(m.group(2))
    return out


# ----------------------------------------------------------- measurement
def measure(result):
    """Per-flight: channel usability, arrival count, relation liveness."""
    fid, ld = result.get("flight_id"), result.get("log_dir")
    if not fid or not ld:
        return None
    chan_usable, chan_arrivals, prev_age = {}, {}, {}
    rel_live, ticks = {}, 0
    for path in sorted(glob.glob(os.path.join(ROOT, ld, "*.jsonl"))):
        if fid not in os.path.basename(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("record") != "tick":
                    continue
                ticks += 1
                chans = (rec.get("canonical") or {}).get("channels") or {}
                for name in set(NODE_CHANNEL.values()):
                    cv = chans.get(name) or {}
                    if cv.get("usable"):
                        chan_usable[name] = chan_usable.get(name, 0) + 1
                        a = cv.get("age_s")
                        if a is not None:
                            # a new sample is an age RESET
                            if (name in prev_age
                                    and a < prev_age[name] - 1e-9):
                                chan_arrivals[name] = \
                                    chan_arrivals.get(name, 0) + 1
                            prev_age[name] = a
                for rel, val in (rec.get("gates") or {}).items():
                    if (isinstance(val, (list, tuple)) and len(val) > 1
                            and float(val[1]) > LIVE):
                        rel_live[rel] = rel_live.get(rel, 0) + 1
    dur = None
    return {"ticks": ticks, "chan_usable": chan_usable,
            "chan_arrivals": chan_arrivals, "rel_live": rel_live,
            "duration": result.get("seconds") or dur}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results", "EVIDENCE_COVERAGE_LEDGER.json"))
    ap.add_argument("--rate-tolerance", type=float, default=0.5,
                    help="relative gap between declared and measured rate "
                         "that counts as a misdeclaration")
    args = ap.parse_args()

    gates = gate_expressions()
    missing_gate = [r for r in ENDPOINTS if r not in gates]
    declared = declared_rates()

    agg = {}
    for pat in CAMPAIGNS:
        for path in sorted(glob.glob(os.path.join(ROOT, pat))):
            if os.path.basename(path).startswith("campaign_"):
                continue
            with open(path, encoding="utf-8") as fh:
                res = json.load(fh)
            plat = res.get("platform")
            m = measure(res)
            if not plat or not m or not m["ticks"]:
                continue
            a = agg.setdefault(plat, {"ticks": 0, "dur": 0.0, "flights": 0,
                                      "chan_usable": {}, "arrivals": {},
                                      "rel_live": {}})
            a["ticks"] += m["ticks"]
            a["dur"] += float(m["duration"] or 0)
            a["flights"] += 1
            for k, v in m["chan_usable"].items():
                a["chan_usable"][k] = a["chan_usable"].get(k, 0) + v
            for k, v in m["chan_arrivals"].items():
                a["arrivals"][k] = a["arrivals"].get(k, 0) + v
            for k, v in m["rel_live"].items():
                a["rel_live"][k] = a["rel_live"].get(k, 0) + v

    if not agg:
        print("no flight logs with gate data found")
        return 2

    ledger, findings = {}, []
    for plat in sorted(agg):
        a = agg[plat]
        rows = {}
        for rel, eps in sorted(ENDPOINTS.items()):
            live = a["rel_live"].get(rel, 0)
            share = live / a["ticks"] if a["ticks"] else 0.0
            ep_info = {}
            starved, misdeclared = [], []
            for node in eps:
                ch = NODE_CHANNEL.get(node)
                dec = (declared.get(ch) or {}).get(plat)
                arr = a["arrivals"].get(ch, 0)
                meas = arr / a["dur"] if a["dur"] else None
                usable = (a["chan_usable"].get(ch, 0) / a["ticks"]
                          if a["ticks"] else 0.0)
                max_age = (MAX_AGE_MARGIN / dec) if dec else None
                aliased = bool(meas is not None
                               and meas >= MEASURABLE_CEILING_HZ)
                # ONLY OVER-DECLARATION IS A DEFECT. max_age is
                # MAX_AGE_MARGIN / declared_rate, so declaring FASTER than the
                # truth shrinks the staleness budget below the real
                # inter-arrival and starves the channel. Declaring SLOWER
                # enlarges the budget, which is merely conservative -- PX4's
                # GNSS is declared 5 Hz and measures 7.9, and flagging that as
                # a defect (three relations did) is an instrument error, not a
                # finding.
                over = (dec and meas and meas > 0 and not aliased
                        and (dec - meas) / dec > args.rate_tolerance)
                under = (dec and meas and meas > 0 and not aliased
                         and (meas - dec) / dec > args.rate_tolerance)
                bad_rate = bool(over)
                # starvation: the channel arrives less often than the derived
                # staleness budget allows, so it is stale part of every period
                if (meas and not aliased and max_age
                        and (1.0 / meas) > max_age):
                    starved.append(node)
                if bad_rate:
                    misdeclared.append(node)
                ep_info[node] = {
                    "channel": ch, "declared_hz": dec,
                    "measured_hz": None if meas is None else round(meas, 3),
                    "derived_max_age_s": (None if max_age is None
                                          else round(max_age, 4)),
                    "channel_usable_share": round(usable, 4),
                    "node_stale_timeout_s": STALE_TIMEOUT_S.get(node),
                    "rate_measurable": not aliased,
                    "rate_overdeclared": bool(over),
                    "rate_underdeclared_conservative": bool(under),
                    "rate_note": ("UNMEASURABLE_AT_TICK_RATE: arrivals are "
                                  "counted once per tick, so any rate at or "
                                  "above ~half the tick rate saturates"
                                  if aliased else "below the aliasing ceiling"),
                }
            if share > 0.5:
                verdict = "LIVE"
            elif misdeclared:
                verdict = "RATE_MISDECLARED"
            elif starved:
                verdict = "DARK_STARVED"
            elif share <= LIVE:
                verdict = "DARK_STRUCTURAL"
            else:
                verdict = "INTERMITTENT"
            rows[rel] = {"gate_expression": gates.get(rel, "NOT FOUND"),
                         "endpoints": ep_info,
                         "relation_live_share": round(share, 4),
                         "verdict": verdict}
            if verdict in ("RATE_MISDECLARED", "DARK_STARVED"):
                findings.append((plat, rel, verdict, misdeclared or starved))
        ledger[plat] = {"flights": a["flights"], "ticks": a["ticks"],
                        "relations": rows}

    print("=== evidence coverage ledger")
    if missing_gate:
        print(f"  !! relations with no gate found in source: {missing_gate}")
    for plat in sorted(ledger):
        print(f"\n  {plat}  ({ledger[plat]['flights']} flights, "
              f"{ledger[plat]['ticks']} ticks)")
        print(f"    {'relation':24s} {'live':>7s}  {'verdict':17s} gate")
        for rel, r in sorted(ledger[plat]["relations"].items()):
            print(f"    {rel:24s} {r['relation_live_share']:7.3f}  "
                  f"{r['verdict']:17s} {r['gate_expression'][:38]}")
    if findings:
        print("\n  DEFECTS (the platform produces the evidence and the "
              "harness discards it):")
        for plat, rel, verdict, nodes in findings:
            print(f"    {plat:10s} {rel:24s} {verdict:17s} via {nodes}")
    else:
        print("\n  no starved or misdeclared endpoints found")

    out = {"max_age_margin": MAX_AGE_MARGIN,
           "rate_tolerance": args.rate_tolerance,
           "measurable_ceiling_hz": MEASURABLE_CEILING_HZ,
           "tick_hz": TICK_HZ,
           "verdict_meanings": {
               "LIVE": "carried weight on most ticks",
               "INTERMITTENT": "carried weight sometimes",
               "DARK_STRUCTURAL": "never carried weight and no endpoint is "
                                  "starved: the platform does not produce it",
               "DARK_STARVED": "endpoint arrives less often than its derived "
                               "max_age allows, so it is stale part of every "
                               "period -- a DEFECT, not a platform fact",
               "RATE_MISDECLARED": "the declared rate is faster than what "
                                   "arrived, beyond tolerance. On PX4 this "
                                   "means the declaration describes a link "
                                   "that REQUESTED intervals while CSIA bound "
                                   "a passive one -- the number is not wrong, "
                                   "it describes the wrong link, and the fix "
                                   "is to drive CSIA's link rather than to "
                                   "edit the contract"},
           "rate_is_a_link_property": {
               "measured_by": "tools/simulation/px4_link_rate_probe.py",
               "artifact": "research/v1_1/results/PX4_LINK_RATE_PROBE.json",
               "summary": "on PX4, SET_MESSAGE_INTERVAL is per-link runtime "
                          "state in both directions: requesting on 14550 "
                          "leaves 14540 untouched and vice versa, so a rate "
                          "declared per (channel, platform) cannot describe "
                          "both links at once"},
           "ledger": ledger,
           "findings": [{"platform": p, "relation": r, "verdict": v,
                         "nodes": n} for p, r, v, n in findings]}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
