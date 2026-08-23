"""WP-C6 Part 2.2 — the minimum repair for gps_fault, measured. Implements nothing.

Given the knife-edge result, the question is not "how much evidence" but
"which one relation". This quantifies, for each candidate whose telemetry the
corpus plausibly carries, the certificate delta it would produce, and confirms
it survives the full 1232-configuration lattice without creating a collision.

Candidates are restricted to relations buildable from fields present in the
PX4 `vehicle_gps_position` message. Fields not currently read by
`ulog_source.py` are marked as requiring plumbing.

Run:  PYTHONPATH=. python research/wp_c6/minimum_repair.py
Out:  research/wp_c6/results/minimum_repair.json
"""

import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import research.wp_c1.lattice as L                              # noqa: E402
from research.wp_c1.certificate import d_critical               # noqa: E402
from research.wp_e1.gate_map import GATE_FEATURES               # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")

# candidate -> (channels spanned, gates controlling it, telemetry status)
CANDIDATES = {
    "gps_cn0_stats": ({"gps"}, [], "needs plumbing: noise_per_ms"),
    "gps_sat_geometry": ({"gps"}, [], "needs plumbing: satellites_used, hdop"),
    "gps_jamming_flag": ({"gps"}, [], "needs plumbing: jamming_indicator"),
    "gps_accuracy_report": ({"gps"}, [], "needs plumbing: eph, epv, "
                                         "s_variance_m_s"),
    "phys_gps_inertial": ({"gps", "imu0"}, [],
                          "no new fields: position derivative vs inertial"),
    "CONTROL_gated_cn0": ({"gps"}, ["gvalid"],
                          "control: same relation, gated by gvalid"),
}


def exposure(low, min_channels):
    reach = L.enumerate_reach(low)
    exposed = set()
    kmax = 0.0
    for r in reach.values():
        if r["n_channels"] >= min_channels:
            exposed |= r["merged_pairs"]
            kmax = max(kmax, r["kappa"])
    return exposed, kmax, len(reach)


def main() -> int:
    base = L.load_signatures()
    hyps = sorted(base)
    crit, _ = d_critical(hyps)
    target = ("gps_fault", "nominal")

    base_exp8, base_k8, n_reach = exposure(base, 8)
    base_exp7, _, _ = exposure(base, 7)

    rows = []
    for name, (chans, gates, telemetry) in CANDIDATES.items():
        L.REQ[name] = set(chans)
        for g in gates:
            GATE_FEATURES[g] = tuple(list(GATE_FEATURES[g]) + [name])
        try:
            trial = {h: list(v) for h, v in base.items()}
            trial["gps_fault"] = sorted(set(trial["gps_fault"]) | {name})
            exp8, k8, _ = exposure(trial, 8)
            exp7, _, _ = exposure(trial, 7)
            rows.append({
                "candidate": name,
                "channels": sorted(chans),
                "gated_by": list(gates),
                "telemetry": telemetry,
                "repairs_target_at_k8": target not in exp8,
                "critical_exposed_k8_before": len(crit & base_exp8),
                "critical_exposed_k8_after": len(crit & exp8),
                "critical_exposed_k7_before": len(crit & base_exp7),
                "critical_exposed_k7_after": len(crit & exp7),
                "kappa_max_k8_before": round(base_k8, 6),
                "kappa_max_k8_after": round(k8, 6),
                "new_collisions_anywhere": sorted(
                    "+".join(p) for p in sorted(exp8 - base_exp8)),
            })
        finally:
            L.REQ.pop(name, None)
            for g in gates:
                GATE_FEATURES[g] = tuple(f for f in GATE_FEATURES[g]
                                         if f != name)

    minimal = [r for r in rows if r["repairs_target_at_k8"]
               and not r["new_collisions_anywhere"]]
    best = min(minimal, key=lambda r: r["critical_exposed_k7_after"]) \
        if minimal else None

    report = {
        "purpose": "smallest addition to E_gps_fault that leaves effective "
                   "undetectability, quantified over the full lattice",
        "implements_nothing": True,
        "n_reachable_configurations": n_reach,
        "minimum_addition_size": 1 if minimal else None,
        "why_size_one": ("The partial-containment sweep shows a knife edge: a "
                         "single feature outside C_h removes absorption "
                         "entirely at every density. So the minimum repair is "
                         "one relation, and the question is only which."),
        "candidates": rows,
        "candidates_that_repair_cleanly": [r["candidate"] for r in minimal],
        "recommended": best["candidate"] if best else None,
        "recommendation_basis": (
            "repairs the target at full instrumentation, creates no new "
            "collision anywhere in the lattice, and leaves the fewest critical "
            "pairs exposed at k=7 (one channel already lost)"),
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "minimum_repair.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"lattice: {n_reach} reachable configurations; "
          f"minimum addition size: {report['minimum_addition_size']}\n")
    print(f"{'candidate':<22s} {'repairs':>8s} {'crit@8':>10s} {'crit@7':>10s} "
          f"{'kmax@8':>9s}  new collisions")
    for r in rows:
        print(f"{r['candidate']:<22s} {str(r['repairs_target_at_k8']):>8s} "
              f"{r['critical_exposed_k8_before']}->"
              f"{r['critical_exposed_k8_after']:<7d} "
              f"{r['critical_exposed_k7_before']}->"
              f"{r['critical_exposed_k7_after']:<7d} "
              f"{r['kappa_max_k8_after']:>9.4f}  "
              f"{r['new_collisions_anywhere'] or 'none'}")
    print(f"\nrecommended: {report['recommended']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
