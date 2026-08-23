"""WP-C3 Part 3 — audit the signature matrix against the design rule.

    RULE: a feature intended to discriminate hypothesis h must not be gated by
          any gate that h closes.

This is what the WP-C2 GPS control demonstrated: the identical relation
repairs the pair when ungated and repairs nothing when gated by `gvalid`. The
rule generalises it into a checkable constraint on the signature matrix.

Run:  PYTHONPATH=. python research/wp_c3/design_rule_audit.py
Out:  research/wp_c3/results/design_rule_audit.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.lattice import load_signatures              # noqa: E402
from research.wp_c3.effective_signature import (                # noqa: E402
    CLOSES, gate_of)

RESULTS = os.path.join(os.path.dirname(__file__), "results")


def audit(low):
    """Every (f, h) with S[f,h]=1, classified against the rule."""
    violations, at_risk, clean = [], [], 0
    for h, feats in low.items():
        for f in feats:
            gates = gate_of(f)
            bad = [g for g in gates if CLOSES[h].get(g) is True]
            unk = [g for g in gates if CLOSES[h].get(g) == "UNKNOWN"]
            row = {"hypothesis": h, "feature": f, "gated_by": gates,
                   "closed_by_this_hypothesis": bad,
                   "unknown_for_this_hypothesis": unk,
                   "is_sole_feature": len(feats) == 1}
            if bad:
                violations.append(row)
            elif unk:
                at_risk.append(row)
            else:
                clean += 1
    return violations, at_risk, clean


def main() -> int:
    low = load_signatures()
    violations, at_risk, clean = audit(low)
    total = sum(len(v) for v in low.values())

    report = {
        "rule": "a feature intended to discriminate hypothesis h must not be "
                "gated by any gate that h closes",
        "provenance": "generalised from the WP-C2 Part 3 control: the same "
                      "GPS relation repairs gps_fault+nominal when ungated "
                      "and repairs nothing when gated by gvalid",
        "baseline": "post-promotion signature matrix (attitude_gravity_mag "
                    "already in imu0_bias_drift)",
        "n_signature_entries": total,
        "n_clean": clean,
        "n_violations": len(violations),
        "n_at_risk_unknown": len(at_risk),
        "violations": violations,
        "at_risk_unknown": at_risk,
        "severity_note": (
            "A violation is fatal to the hypothesis exactly when the violating "
            "feature is its SOLE feature: the hypothesis then has an empty "
            "effective signature and is absorbed into nominal. A violation on "
            "one of several features merely weakens the hypothesis."),
        "fatal_violations": [v for v in violations if v["is_sole_feature"]],
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "design_rule_audit.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"signature entries: {total}   clean: {clean}   "
          f"violations: {len(violations)}   at-risk (UNKNOWN): {len(at_risk)}")
    print("\nVIOLATIONS:")
    for v in violations:
        tag = "FATAL — sole feature" if v["is_sole_feature"] else "weakening"
        print(f"  {v['hypothesis']:<22s} {v['feature']:<22s} "
              f"closed by {v['closed_by_this_hypothesis']}  [{tag}]")
    print("\nAT RISK (gate closure UNKNOWN for this hypothesis):")
    for v in at_risk or []:
        print(f"  {v['hypothesis']:<22s} {v['feature']:<22s} "
              f"unknown for {v['unknown_for_this_hypothesis']}")
    if not at_risk:
        print("  none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
