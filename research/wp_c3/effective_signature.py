"""WP-C3 Part 1 — the effective signature matrix S_eff.

    S_eff[f,h] = S[f,h] AND NOT (exists g in gate(f) : closes(h,g))

A feature counts as evidence for h only if h perturbs it AND h does not
silence it. The classical design-time matrix S assumes availability is fixed
at design; S_eff makes it a function of the hypothesis being diagnosed.

Theorem (immediate): Pi(S_eff) is coarser than or equal to Pi(S), always.
S_eff <= S entrywise, so equal columns in S stay equal in S_eff and pairs may
additionally merge. Verified computationally; a violation would be a bug in
this construction, not a counterexample.

Run:  PYTHONPATH=. python research/wp_c3/effective_signature.py
Out:  research/wp_c3/results/effective_signature.json
"""

import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.lattice import (                            # noqa: E402
    load_signatures, merged_pairs)
from research.wp_e1.gate_map import GATE_FEATURES               # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")

# --- closes(h, g), derived from source and the physical fault model ---------
#
# For each actuating gate, which hypotheses drive it closed? Derived from the
# gate predicate in source plus the fault model in csia/sensors/faults.py.
# Where source cannot settle it, the entry is UNKNOWN and the uncertainty is
# carried through rather than guessed.
#
#   armed_gate  online.py:491-496 — a function of vehicle arming state and
#               time since arming. NO sensor fault influences it: it reads
#               vehicle_status, not any monitored channel. Closure is
#               exogenous to every hypothesis.
#   gvalid      comparator.py:115 — GPS fix validity (fix_type >= 3 in
#               ulog_source.py:178). A GPS fault that degrades or denies the
#               fix closes it. This is the canonical endogenous gate.
#   speed_gate  comparator.py:112-113 — horizontal ground speed from GPS
#               velocity. A GPS fault corrupts the velocity the gate is
#               computed from, so it can drive the gate either way.
#   gps_warmup  comparator.py:199 — ticks > 3.0, pure elapsed time. No
#               hypothesis influences it.
#
CLOSES = {
    "nominal":             {"armed_gate": False, "gvalid": False,
                            "speed_gate": False, "gps_warmup": False},
    "gps_fault":           {"armed_gate": False, "gvalid": True,
                            "speed_gate": "UNKNOWN", "gps_warmup": False},
    "imu0_bias_drift":     {"armed_gate": False, "gvalid": False,
                            "speed_gate": False, "gps_warmup": False},
    "imu1_bias_drift":     {"armed_gate": False, "gvalid": False,
                            "speed_gate": False, "gps_warmup": False},
    "mag_interference":    {"armed_gate": False, "gvalid": False,
                            "speed_gate": False, "gps_warmup": False},
    "power_fault":         {"armed_gate": False, "gvalid": False,
                            "speed_gate": "UNKNOWN", "gps_warmup": False},
    "vibration_anomaly":   {"armed_gate": False, "gvalid": False,
                            "speed_gate": False, "gps_warmup": False},
    "unexpected_maneuver": {"armed_gate": False, "gvalid": False,
                            "speed_gate": "UNKNOWN", "gps_warmup": False},
}

RATIONALE = {
    ("gps_fault", "gvalid"): (
        "TRUE. gvalid is fix validity (comparator.py:115; fix_type >= 3 at "
        "ulog_source.py:178). Denial, jamming and many spoofing modes drop or "
        "invalidate the fix. The fault silences the gate that carries its own "
        "evidence."),
    ("gps_fault", "speed_gate"): (
        "UNKNOWN. speed_gate is computed from GPS-derived horizontal velocity "
        "(comparator.py:112-113), so a GPS fault perturbs its input — but "
        "whether it drives the gate CLOSED depends on the spoof's velocity "
        "profile, which the fault model does not fix. A spoof holding "
        "plausible velocity leaves it open; one collapsing reported velocity "
        "closes it. Not derivable from source."),
    ("power_fault", "speed_gate"): (
        "UNKNOWN. A severe power fault degrades flight and could reduce "
        "ground speed below the 2 m/s threshold, but nothing in source links "
        "battery trust to commanded velocity. Physical plausibility, not "
        "source."),
    ("unexpected_maneuver", "speed_gate"): (
        "UNKNOWN. A manoeuvre is defined by unusual kinematics; whether it "
        "crosses below the speed threshold is scenario-dependent."),
    ("*", "armed_gate"): (
        "FALSE for every hypothesis. armed_gate reads vehicle arming state "
        "and elapsed time (online.py:491-496); no monitored sensor channel "
        "feeds it. Closure is exogenous."),
    ("*", "gps_warmup"): (
        "FALSE for every hypothesis. Pure elapsed time (ticks > 3.0, "
        "comparator.py:199)."),
}


def gate_of(feature):
    return [g for g, feats in GATE_FEATURES.items() if feature in feats]


def silences(h, feature, unknown_as=False):
    """Does hypothesis h silence this feature by closing one of its gates?"""
    for g in gate_of(feature):
        v = CLOSES[h].get(g, False)
        if v == "UNKNOWN":
            if unknown_as:
                return True
        elif v:
            return True
    return False


def effective(low, unknown_as=False):
    return {h: sorted(f for f in feats
                      if not silences(h, f, unknown_as))
            for h, feats in low.items()}


def partition_of(sig):
    classes = {}
    for h, s in sig.items():
        classes.setdefault(tuple(sorted(s)), []).append(h)
    return {k: tuple(sorted(v)) for k, v in classes.items()}


def kappa_of(sig):
    h = len(sig)
    return (h - len(partition_of(sig))) / (h - 1) if h > 1 else 0.0


def soi(low, unknown_as=False):
    out = {}
    for h, feats in low.items():
        if not feats:
            out[h] = {"soi": None, "n_features": 0, "silenced": [],
                      "note": "empty LOW set; SOI undefined"}
            continue
        sil = sorted(f for f in feats if silences(h, f, unknown_as))
        out[h] = {"soi": round(len(sil) / len(feats), 4),
                  "n_features": len(feats), "silenced": sil}
    return out


def main() -> int:
    low = load_signatures()

    coverage = {"total": 0, "derived": 0, "unknown": 0, "unknown_cells": []}
    for h, gates in CLOSES.items():
        for g, v in gates.items():
            coverage["total"] += 1
            if v == "UNKNOWN":
                coverage["unknown"] += 1
                coverage["unknown_cells"].append(f"{h}/{g}")
            else:
                coverage["derived"] += 1
    coverage["fraction_derived"] = round(
        coverage["derived"] / coverage["total"], 4)

    results = {}
    for label, unknown_as in (("unknown_as_open", False),
                              ("unknown_as_closed", True)):
        eff = effective(low, unknown_as)
        pi_s, pi_eff = partition_of(low), partition_of(eff)
        k_s, k_eff = kappa_of(low), kappa_of(eff)
        merged_s = merged_pairs(pi_s)
        merged_eff = merged_pairs(pi_eff)

        # Theorem check: Pi(S_eff) coarser than or equal to Pi(S).
        violations = sorted("+".join(p) for p in (merged_s - merged_eff))

        results[label] = {
            "S_eff": eff,
            "n_classes_S": len(pi_s),
            "n_classes_S_eff": len(pi_eff),
            "kappa_S": round(k_s, 6),
            "kappa_S_eff": round(k_eff, 6),
            "gap": round(k_eff - k_s, 6),
            "pairs_merged_only_in_S_eff": sorted(
                "+".join(p) for p in (merged_eff - merged_s)),
            "theorem_violations": violations,
            "theorem_holds": not violations,
            "soi": soi(low, unknown_as),
        }

    report = {
        "purpose": "effective signature matrix: a feature is evidence for h "
                   "only if h perturbs it AND does not silence it",
        "definition": "S_eff[f,h] = S[f,h] AND NOT (exists g in gate(f): "
                      "closes(h,g))",
        "theorem": "Pi(S_eff) is coarser than or equal to Pi(S), always "
                   "(S_eff <= S entrywise)",
        "baseline_note": "computed against the POST-PROMOTION signature "
                         "matrix, i.e. with attitude_gravity_mag already in "
                         "imu0_bias_drift (WP-C3 promotion)",
        "closes_table": CLOSES,
        "closes_rationale": {f"{h} / {g}": t
                             for (h, g), t in RATIONALE.items()},
        "closes_coverage": coverage,
        "results": results,
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "effective_signature.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"closes(h,g) coverage: {coverage['derived']}/{coverage['total']} "
          f"derived from source ({coverage['fraction_derived']:.0%}); "
          f"UNKNOWN: {coverage['unknown_cells']}\n")
    for label, r in results.items():
        print(f"--- {label} ---")
        print(f"  kappa(S)     = {r['kappa_S']:.6f}   "
              f"classes {r['n_classes_S']}")
        print(f"  kappa(S_eff) = {r['kappa_S_eff']:.6f}   "
              f"classes {r['n_classes_S_eff']}")
        print(f"  GAP          = {r['gap']:.6f}")
        print(f"  merged only in S_eff: "
              f"{r['pairs_merged_only_in_S_eff'] or 'none'}")
        print(f"  theorem holds: {r['theorem_holds']}")
        ranked = sorted(((v['soi'], h) for h, v in r["soi"].items()
                         if v["soi"] is not None), reverse=True)
        print("  SOI ranking:")
        for v, h in ranked:
            print(f"     {h:<22s} {v:.4f}  "
                  f"silenced={r['soi'][h]['silenced'] or '-'}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
