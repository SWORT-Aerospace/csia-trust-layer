"""Mechanism A — fix-loss self-occlusion, measured on the current stack.

THE PHASE-I CLAIM UNDER TEST. `docs/v1/V1_FINAL_RESEARCH_VERDICT.md` W-1:

    SOI(gps_fault) = 1.0. Every feature that would name a GPS fault is gated
    by a gate a GPS fault closes.

That was demonstrated only in the ArduCopter 3.3 campaign. This is a small
confirmatory replication on **current ArduPilot 4.8 and PX4 SIH**, not a new
characterisation programme: two arms per platform, one intervention.

    CONTROL   fix preserved   (the null control -- RULE A)
    FAULT     fix removed mid-flight from the RIG's link

The intervention was read out of the simulator source before use:
ArduPilot `SIM_GPS1_ENABLE` (SIM_GPS.cpp:42); PX4 `SIM_GPS_USED` driven to 0,
because `SensorGpsSim.cpp:155-167` sets `fix_type = 3` only when
`_sim_gps_used >= 4` and `SENS_EN_GPSSIM` is `reboot_required` and therefore
useless in flight.

RULE B -- no mechanism attribution without the intermediate quantity. The
parameter write is not the measurement. `gnss.position` going MISSING with
`NO_3D_FIX` is, and a FAULT arm that never shows it is a failed trial rather
than a result.

Reports, per arm, exactly the quantities the question turns on:
gate state; support/applicability; GPS trust; gps_fault probability and rank;
nominal probability and rank; freshness; assurance level; recommendation.

  python tools/simulation/mechanism_a_report.py \\
      --control research/v1_1/results/mechanism_a/ap_CONTROL.json \\
      --fault   research/v1_1/results/mechanism_a/ap_FAULT.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

GPS_GATES = ("velocity_gps_doppler_0", "velocity_gps_doppler_1",
             "altitude_baro", "heading_course")


def _ticks(path: str):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("record") == "tick":
                out.append(rec)
    return out


def _rank(posterior: dict, name: str):
    """1-based rank of a hypothesis, and its probability."""
    if not posterior:
        return None, None
    order = sorted(posterior.items(), key=lambda kv: -float(kv[1]))
    for i, (k, v) in enumerate(order, start=1):
        if k == name:
            return i, float(v)
    return None, None


def snapshot(tick: dict) -> dict:
    chans = (tick.get("canonical") or {}).get("channels") or {}
    pos = chans.get("gnss.position") or {}
    diag = tick.get("diagnosis") or {}
    post = diag.get("posterior") or {}
    gps_rank, gps_p = _rank(post, "gps_fault")
    nom_rank, nom_p = _rank(post, "nominal")
    gates = tick.get("gates") or {}
    return {
        "t": tick.get("t_mono"),
        # the INTERMEDIATE QUANTITY (RULE B)
        "gnss_position_usable": bool(pos.get("usable")),
        "gnss_position_missing": pos.get("missing"),
        # gate state and applicability: [lambda, weight] per gate
        "gps_gates": {g: gates.get(g) for g in GPS_GATES if g in gates},
        "gps_gate_weight_sum": round(sum(
            float((gates.get(g) or [0, 0])[1]) for g in GPS_GATES
            if g in gates), 4),
        "trust_gps": (tick.get("trust_post") or {}).get("gps"),
        "gps_fault_rank": gps_rank,
        "gps_fault_p": None if gps_p is None else round(gps_p, 4),
        "nominal_rank": nom_rank,
        "nominal_p": None if nom_p is None else round(nom_p, 4),
        "diagnosis_top": diag.get("top"),
        "ambiguity": tick.get("ambiguity"),
        "level": (tick.get("recommendation") or {}).get("level"),
        "actions": [a.get("kind") if isinstance(a, dict) else a
                    for a in ((tick.get("recommendation") or {})
                              .get("actions") or [])],
        "disagreement": (tick.get("disagreement") or {}).get("state"),
    }


def arm(result_path: str, label: str) -> dict:
    with open(result_path, encoding="utf-8") as fh:
        res = json.load(fh)
    log_dir = os.path.join(ROOT, res.get("log_dir", ""))
    fid = res.get("flight_id", "")
    files = [p for p in sorted(glob.glob(os.path.join(log_dir, "*.jsonl")))
             if fid and fid in os.path.basename(p)]
    ticks = []
    for p in files:
        ticks += _ticks(p)
    inj = res.get("injection") or {}
    at = inj.get("at_s")

    # RULE B: did the intervention reach the vehicle?
    lost = [t for t in ticks
            if ((t.get("canonical") or {}).get("channels", {})
                .get("gnss.position", {}) or {}).get("missing") == "NO_3D_FIX"]
    out = {
        "arm": label,
        "result_file": os.path.relpath(result_path, ROOT),
        "flight_id": fid,
        "ticks": len(ticks),
        "injection": inj,
        "intermediate_quantity": {
            "name": "gnss.position MISSING with NO_3D_FIX",
            "ticks_observed": len(lost),
            "first_t": lost[0]["t_mono"] if lost else None,
            "rule": "RULE B -- the parameter write is not the measurement",
        },
        "levels_seen": sorted({(t.get("recommendation") or {}).get("level")
                               for t in ticks if t.get("recommendation")}),
    }
    if inj.get("kind"):
        out["intervention_effective"] = bool(lost)
    else:
        # In the CONTROL arm the intermediate quantity must NOT appear.
        out["control_clean"] = not lost

    # Snapshots: before the injection instant and after it (or the same
    # instants in the CONTROL arm, so the two are comparable).
    marks = {}
    for name, target in (("pre", (at or 12.0) - 2.0),
                         ("at", at or 12.0),
                         ("post", (at or 12.0) + 2.0),
                         ("late", (at or 12.0) + 10.0)):
        near = [t for t in ticks if t.get("t_mono") is not None]
        if not near:
            continue
        marks[name] = snapshot(min(near, key=lambda t: abs(t["t_mono"] - target)))
    out["snapshots"] = marks
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--control", required=True)
    ap.add_argument("--fault", required=True)
    ap.add_argument("--platform", default="")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    control = arm(args.control, "CONTROL (fix preserved)")
    fault = arm(args.fault, "FAULT (fix lost)")

    print(f"=== Mechanism A, {args.platform or 'platform'}")
    for a in (control, fault):
        iq = a["intermediate_quantity"]
        print(f"  {a['arm']:26s} ticks={a['ticks']:4d}  "
              f"NO_3D_FIX ticks={iq['ticks_observed']:4d} "
              f"(first t={iq['first_t']})  levels={a['levels_seen']}")

    valid = fault.get("intervention_effective") and control.get("control_clean")
    print(f"  trial validity: intervention effective="
          f"{fault.get('intervention_effective')}, control clean="
          f"{control.get('control_clean')} -> "
          f"{'VALID' if valid else 'INVALID'}")

    if valid:
        f = fault["snapshots"]
        print(f"\n  {'quantity':26s} {'pre':>12s} {'post':>12s} {'late':>12s}")
        for key, label in (("gnss_position_usable", "gnss.position usable"),
                           ("gps_gate_weight_sum", "GPS gate weight sum"),
                           ("trust_gps", "GPS trust"),
                           ("gps_fault_p", "P(gps_fault)"),
                           ("gps_fault_rank", "rank(gps_fault)"),
                           ("nominal_p", "P(nominal)"),
                           ("nominal_rank", "rank(nominal)"),
                           ("level", "recommendation")):
            row = [f.get(m, {}).get(key) for m in ("pre", "post", "late")]
            print(f"  {label:26s} " + " ".join(f"{str(v):>12s}" for v in row))

    out = {"platform": args.platform, "control": control, "fault": fault,
           "trial_valid": bool(valid),
           "claim_under_test": "W-1: SOI(gps_fault) = 1.0 -- fix loss removes "
                               "the evidence required to attribute gps_fault"}
    path = args.out or os.path.join(
        ROOT, "research", "v1_1", "results",
        f"mechanism_a_{args.platform or 'platform'}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(path, ROOT)}")
    return 0 if valid else 2


if __name__ == "__main__":
    sys.exit(main())
