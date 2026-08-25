"""Combine the Mechanism A and Mechanism B results into one artifact.

Both mechanisms were characterised only in the 2015 ArduCopter 3.3 campaign.
This assembles what the current stack -- ArduPilot 4.8 and PX4 SIH -- actually
did, from the per-platform result files, so the published numbers are generated
rather than transcribed.

The combined Mechanism B verdict follows mechanically from the two platform
verdicts. PLATFORMS ARE NOT POOLED: each is classified on its own arms, and the
combination is a naming of the pair, not a statistic over them.

  python tools/simulation/current_stack_replication.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS = os.path.join(ROOT, "research", "v1_1", "results")
PLATFORMS = ("ardupilot", "px4")


def _load(name):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def combine_b(per_platform: dict) -> dict:
    v = {p: (per_platform[p] or {}).get("verdict", {}).get("verdict")
         for p in PLATFORMS}
    ap, px = v["ardupilot"], v["px4"]
    if ap == "REPLICATES" and px == "REPLICATES":
        token = "MECHANISM_B_REPLICATES_BOTH"
    elif ap == "REPLICATES" and px != "REPLICATES":
        token = "MECHANISM_B_REPLICATES_ARDUPILOT_ONLY"
    elif px == "REPLICATES" and ap != "REPLICATES":
        token = "MECHANISM_B_REPLICATES_PX4_ONLY"
    elif ap == "DOES_NOT_REPLICATE" and px == "DOES_NOT_REPLICATE":
        token = "MECHANISM_B_DOES_NOT_REPLICATE"
    else:
        token = "INCONCLUSIVE"
    return {"combined": token, "per_platform": v,
            "rule": "platforms are classified independently and never pooled; "
                    "the combined token names the pair"}


def arm_table(res: dict) -> list:
    rows = []
    for a in res.get("arms", []):
        d = a.get("downstream_observable") or {}
        e1 = a.get("E1_recursion_fidelity") or {}
        cr = a.get("crossing") or {}
        e2 = a.get("E2_closed_form") or {}
        rows.append({
            "arm": a.get("arm"),
            "u_ut": a.get("u_ut"),
            "field_shift_expected_ut": d.get("expected_ut"),
            "field_shift_observed_ut": d.get("observed_ut"),
            "valid": a.get("valid"),
            "invalid_reason": a.get("invalid_reason"),
            "E1_max_abs_delta": e1.get("max_abs_delta"),
            "E1_pass": e1.get("pass"),
            "T_at_injection": cr.get("T_at_injection"),
            "T_min_after_injection": cr.get("T_min_after_injection"),
            "crossed": cr.get("crossed"),
            "N_obs_ticks": cr.get("N_obs_ticks"),
            "e_f": e2.get("e_f"),
            "rho_f": e2.get("rho_f"),
            "S0": e2.get("S0"),
            "N_predicted_ceil": e2.get("N_predicted_ceil"),
            "E2_error_ticks": e2.get("error_ticks"),
            "E2_note": e2.get("note"),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(
        RESULTS, "current_stack_replication.json"))
    args = ap.parse_args()

    a_res = {p: _load(f"mechanism_a_{p}.json") for p in PLATFORMS}
    b_res = {p: _load(f"mechanism_b_{p}.json") for p in PLATFORMS}
    missing = [p for p in PLATFORMS if b_res[p] is None]
    if missing:
        print(f"!!! missing Mechanism B results for: {', '.join(missing)}")
        return 2

    out = {
        "generated_from": {
            "mechanism_a": [f"research/v1_1/results/mechanism_a_{p}.json"
                            for p in PLATFORMS],
            "mechanism_b": [f"research/v1_1/results/mechanism_b_{p}.json"
                            for p in PLATFORMS],
        },
        "preregistration_b":
            "research/v1_1/MECHANISM_B_PREREGISTRATION.md",
        "mechanism_a": {
            "claim": "W-1: SOI(gps_fault) = 1.0 -- fix loss removes the "
                     "evidence required to attribute gps_fault",
            "per_platform": {
                p: {"trial_valid": (a_res[p] or {}).get("trial_valid"),
                    "replicates": bool((a_res[p] or {}).get("trial_valid")),
                    "document": "docs/v1_1/MECHANISM_A_MODERN_REPLICATION.md"}
                for p in PLATFORMS},
        },
        "mechanism_b": {
            "claim": "W-4: banked evidence S delays a trust node's threshold "
                     "crossing, and the recursion predicts by how much",
            "intervention": "mag_emi -- constant hard-iron magnetometer "
                            "offset, evidence-preserving",
            "threshold": 0.60,
            "threshold_source": "csia/runtime/failsafe.py heading_caution",
            "endpoint": "threshold crossing, NOT escalation",
            "per_platform": {
                p: {"verdict": (b_res[p] or {}).get("verdict"),
                    "arms": arm_table(b_res[p] or {})}
                for p in PLATFORMS},
            "verdict": combine_b(b_res),
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)

    print("=== current-stack replication")
    for p in PLATFORMS:
        print(f"  {p:10s} Mechanism A: "
              f"{'REPLICATES' if (a_res[p] or {}).get('trial_valid') else 'not established'}"
              f"   Mechanism B: "
              f"{(b_res[p] or {}).get('verdict', {}).get('verdict')}")
    print(f"  -> {out['mechanism_b']['verdict']['combined']}")
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
