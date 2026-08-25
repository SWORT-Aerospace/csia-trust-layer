"""Why did THIS clean flight escalate and that one not? Matched tick traces.

Two of four clean PX4 SIH flights raised CAUTION; two did not. Reading the S9
logs alone excluded, with evidence, every candidate that the log can see:

    the predicate value        mag trust < 0.60 in 3 of 4 flights, including
                               one that stayed quiet
    dwell                      the quiet flight held the predicate for a
                               CONTIGUOUS 290 ticks (11.6 s) against
                               dwell_up = 1.0 s
    the armed gate             armed channel 100/100 usable and true in the
                               decision window of every flight
    arm_time                   all flights had 78-93 ticks below threshold
                               AFTER t = 10 s
    channel freshness          mag.field_ut never appeared in
                               evidence_unavailable in any flight

What is left is `TrustState.fresh` -- NODE freshness, computed inside the
frozen core as `s[n].valid and s[n].seen` (online.py:603) -- which is the
second term of the failsafe predicate:

    if T["mag"] < cfg.heading_caution and fresh.get("mag"):

and which the flight log does not record. So it has to be replayed.

THE POSITIVE CONTROL IS NOT OPTIONAL. A replay that does not reproduce the
logged trust trajectory is not a trace of that flight, and any `fresh` value
read out of it would be a statement about the replay. This tool compares
replayed trust against the logged `trust_post` tick by tick and REFUSES to
report a diagnosis when they diverge.

  python tools/deploy/diagnose_escalation.py LOG_A.jsonl LOG_B.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "deploy"))

from csia.runtime.failsafe import FailsafePolicy          # noqa: E402
from csia.runtime.online import OnlineTrustLayer          # noqa: E402
from profile_core_from_log import (                       # noqa: E402
    core_samples_for_tick, load_ticks)

# How closely the replayed trust must track the log for the trace to count.
# Generous on purpose: the question is "is this the same flight", not "is it
# bit-identical". A real divergence shows up as tenths, not 1e-6.
TRUST_TOLERANCE = 0.02


def trace(path: str, field_mode: bool = True) -> dict:
    """Replay one flight log and record what the failsafe actually saw."""
    layer = OnlineTrustLayer(tick_hz=25.0, field_mode=field_mode)
    policy = FailsafePolicy()
    ticks = list(load_ticks(path))
    rows, prev = [], None
    logged = {t["t_mono"]: t for t in ticks}

    for tick in ticks:
        samples = core_samples_for_tick(tick, prev)
        prev = {k: v["value"]
                for k, v in tick["canonical"]["channels"].items()
                if v.get("usable")}
        for sensor, t, chans in samples:
            for state in layer.ingest(sensor, t, chans) or []:
                conds = policy._conditions(state)
                policy.update(state)
                rows.append({
                    "t": state.t,
                    "trust": dict(state.trust),
                    "fresh": dict(state.fresh),
                    "armed": getattr(state, "armed", None),
                    "conditions": sorted(conds),
                    "level": policy.level.name,
                })

    # POSITIVE CONTROL: does this replay reproduce the flight it claims to be?
    checked = drift = 0
    worst = 0.0
    for row in rows:
        near = min(logged, key=lambda x: abs(x - row["t"]))
        if abs(near - row["t"]) > 0.05:
            continue
        tp = (logged[near].get("trust_post") or {})
        for node, value in row["trust"].items():
            if node not in tp:
                continue
            checked += 1
            delta = abs(float(value) - float(tp[node]))
            worst = max(worst, delta)
            if delta > TRUST_TOLERANCE:
                drift += 1
    return {
        "log": os.path.basename(path),
        "rows": rows,
        "control": {
            "trust_values_compared": checked,
            "values_over_tolerance": drift,
            "worst_abs_delta": round(worst, 5),
            "tolerance": TRUST_TOLERANCE,
            "faithful": checked > 0 and drift == 0,
            "rule": "a replay that does not reproduce the logged trust is not "
                    "a trace of that flight, and its `fresh` values describe "
                    "the replay rather than the vehicle",
        },
    }


def summarise(tr: dict, lo: float, hi: float) -> dict:
    rows = [r for r in tr["rows"] if lo <= r["t"] <= hi]
    mag_low = [r for r in rows if r["trust"].get("mag", 1) < 0.60]
    both = [r for r in mag_low if r["fresh"].get("mag")]
    return {
        "log": tr["log"],
        "window": [lo, hi],
        "ticks": len(rows),
        "mag_trust_below_0.60": len(mag_low),
        "and_mag_node_FRESH": len(both),
        "mag_fresh_ticks": sum(1 for r in rows if r["fresh"].get("mag")),
        "heading_degraded_active": sum(
            1 for r in rows if "heading_degraded" in r["conditions"]),
        "levels": sorted({r["level"] for r in rows}),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--from-t", type=float, default=10.0)
    ap.add_argument("--to-t", type=float, default=15.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = {"window": [args.from_t, args.to_t], "flights": []}
    unfaithful = []
    for path in args.logs:
        tr = trace(path)
        c = tr["control"]
        print(f"=== {os.path.basename(path)}")
        print(f"    replay control: {c['trust_values_compared']} values "
              f"compared, {c['values_over_tolerance']} over tolerance, "
              f"worst delta {c['worst_abs_delta']} -> "
              f"{'FAITHFUL' if c['faithful'] else 'NOT FAITHFUL'}")
        s = summarise(tr, args.from_t, args.to_t)
        s["control"] = c
        out["flights"].append(s)
        if not c["faithful"]:
            unfaithful.append(os.path.basename(path))
            print("    *** diagnosis withheld: this replay is not this flight")
            continue
        print(f"    t in [{args.from_t}, {args.to_t}]: {s['ticks']} ticks | "
              f"mag T<0.60: {s['mag_trust_below_0.60']} | mag node fresh: "
              f"{s['mag_fresh_ticks']} | BOTH: {s['and_mag_node_FRESH']} | "
              f"heading_degraded active: {s['heading_degraded_active']} | "
              f"levels {s['levels']}")

    path = args.out or os.path.join(ROOT, "research", "v1_1", "results",
                                    "escalation_diagnosis.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(path, ROOT)}")
    # An unfaithful replay is a failed measurement, not a quiet one.
    return 1 if unfaithful else 0


if __name__ == "__main__":
    sys.exit(main())
