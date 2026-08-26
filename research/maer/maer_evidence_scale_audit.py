"""Would the receiver-health contribution dwarf every existing feature?

THE HAZARD THIS EXISTS TO CATCH. `h_acc` is reported in millimetres and spans
three decades under jamming (300 -> ~300000). Any transform that carries that
dynamic range straight into the evidence score would let the research arm win
on unit choice rather than information, and the Stage 0.5 draft came close to
exactly that: it proposed dividing by `max(MAD_clean, 1e-3)` on a clean series
whose MAD is zero, which is an arbitrary 1000x gain wearing a robust-statistics
costume. That form is withdrawn.

THE REPLACEMENT REUSES THE EXISTING CONVENTION INSTEAD OF INVENTING ONE.
`OnlineTrustLayer._lam_upd` (csia/runtime/online.py:426) is:

    lam = EWMA_0.15( (resid / sigma)^2 / df )

Every relation in the layer is expressed that way, so supplying a `resid` and a
`sigma` in the same form makes scale compatibility STRUCTURAL rather than
tuned. Both constants below are declared from configuration and stated before
any fault trace is scored:

    h0    = SIM_GPS1_ACC * 1000 = 300 mm
            the DECLARED nominal receiver accuracy of the configuration under
            test, read from the simulator parameter, not from a fault trace

    resid = log(1 + max(0, h_acc - h0) / h0)
            one-sided: accuracy better than nominal is not a fault. Zero at
            nominal, and logarithmic so three decades of millimetres become a
            bounded, dimensionless quantity

    sigma = log(2) = 0.6931
            ONE DOUBLING OF EXCESS ERROR OVER NOMINAL IS ONE SIGMA. This is an
            engineering statement about what counts as a meaningful
            degradation, fixed in advance; it is not fitted, and no fault
            separation was consulted to choose it

This audit compares the resulting magnitude against the evidence magnitudes the
layer actually produces on committed flights, clean and faulted. It scores no
hypothesis and tunes nothing.

  python research/maer/maer_evidence_scale_audit.py
"""

from __future__ import annotations

import glob
import json
import math
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MAER = os.path.join(ROOT, "research", "maer")

# ---- the frozen transform constants, declared here -----------------------
H0_MM = 300.0                 # SIM_GPS1_ACC (0.3 m) * 1000
SIGMA = math.log(2.0)         # one doubling of excess error = 1 sigma
EW_ALPHA = 0.15               # the same smoother _lam_upd uses


def residual(h_acc_mm):
    """One-sided log excess over declared nominal accuracy."""
    return math.log(1.0 + max(0.0, float(h_acc_mm) - H0_MM) / H0_MM)


def lam_series(h_acc_values):
    """EWMA((resid/sigma)^2), matching _lam_upd with df=1 and no adaptation."""
    out, ew = [], None
    for v in h_acc_values:
        raw = (residual(v) / SIGMA) ** 2
        ew = raw if ew is None else ew + EW_ALPHA * (raw - ew)
        out.append(ew)
    return out


def consistency(lam):
    """The layer's own lam -> (0,1] map, csia/trust_engine/engine.py.

    This is why a millimetre-valued input cannot dominate the score by unit
    choice: whatever lam is, the downstream quantity is bounded in (0,1] and
    saturates. Comparing in THIS space is apples to apples; comparing raw lam
    against logged consistency scores would not be.
    """
    return math.exp(-0.5 * max(0.0, lam - 1.0))


def _describe(vals):
    if not vals:
        return None
    s = sorted(vals)
    return {
        "n": len(s), "min": round(s[0], 4),
        "p50": round(s[len(s) // 2], 4),
        "p95": round(s[int(0.95 * (len(s) - 1))], 4),
        "max": round(s[-1], 4),
        "mean": round(statistics.fmean(s), 4),
    }


def existing_evidence():
    """Per-node evidence scores the layer actually produced, from logs.

    `hypothesis_evidence` is {node: score in (0,1]} -- the post-consistency
    quantity, which is what the proposed contribution must be compared with.
    """
    clean, fault = [], []
    for pat, bucket in (
            ("research/v1_1/results/shadow_flights/*.json", clean),
            ("research/v1_1/results/mechanism_a/*.json", None)):
        for path in sorted(glob.glob(os.path.join(ROOT, pat))):
            if os.path.basename(path).startswith("campaign_"):
                continue
            with open(path, encoding="utf-8") as fh:
                res = json.load(fh)
            fid, ld = res.get("flight_id"), res.get("log_dir")
            if not fid or not ld:
                continue
            target = bucket
            if target is None:
                target = fault if "FAULT" in os.path.basename(path) else clean
            for lp in sorted(glob.glob(os.path.join(ROOT, ld, "*.jsonl"))):
                if fid not in os.path.basename(lp):
                    continue
                with open(lp, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            rec = json.loads(line)
                        except ValueError:
                            continue
                        if rec.get("record") != "tick":
                            continue
                        for v in (rec.get("hypothesis_evidence")
                                  or {}).values():
                            if isinstance(v, (int, float)):
                                target.append(float(v))
    return clean, fault


def proposed_evidence():
    """The candidate's magnitude on the committed jamming captures."""
    clean_vals, invalid_vals, valid_vals = [], [], []
    for path in sorted(glob.glob(os.path.join(
            MAER, "MAER_ARDUPILOT_JAM_RAW", "*.json"))):
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        rows = d.get("rows") or []
        seq = [r["h_acc"] for r in rows if r.get("h_acc") is not None]
        lam = lam_series(seq)
        for r, L in zip([r for r in rows if r.get("h_acc") is not None], lam):
            c = consistency(L)
            if r["phase"] == "clean":
                clean_vals.append(c)
            elif (r.get("fix_type") or 0) < 3:
                invalid_vals.append(c)
            else:
                valid_vals.append(c)
    return clean_vals, valid_vals, invalid_vals


def main() -> int:
    ex_clean, ex_fault = existing_evidence()
    pr_clean, pr_valid, pr_invalid = proposed_evidence()

    out = {
        "why": "a contribution reported in millimetres must not dominate the "
               "score by unit choice; the Stage 0.5 MAD-floor form is "
               "withdrawn",
        "withdrawn_transform": {
            "form": "z = (log(h_acc+1) - median_clean) / max(MAD_clean, 1e-3)",
            "defect": "clean SITL h_acc is constant so MAD is 0; the floor is "
                      "an arbitrary 1000x gain and would let the research arm "
                      "win on scaling rather than information",
        },
        "frozen_transform": {
            "h0_mm": H0_MM,
            "h0_source": "SIM_GPS1_ACC (0.3 m) * 1000 -- the DECLARED nominal "
                         "receiver accuracy of the configuration under test",
            "residual": "log(1 + max(0, h_acc - h0) / h0)",
            "residual_rationale": "one-sided because better-than-nominal "
                                  "accuracy is not a fault; logarithmic "
                                  "because h_acc spans three decades",
            "sigma": round(SIGMA, 6),
            "sigma_rationale": "one DOUBLING of excess error over nominal is "
                               "one sigma -- an engineering statement fixed "
                               "in advance, not fitted, and chosen without "
                               "consulting fault separation",
            "lam": "EWMA_0.15((resid/sigma)^2), identical in form to "
                   "OnlineTrustLayer._lam_upd(df=1) so the units match every "
                   "existing relation by construction",
            "downstream_map": "consistency(lam) = exp(-0.5*max(0, lam-1)), "
                              "csia/trust_engine/engine.py -- bounded in "
                              "(0,1], so the contribution CANNOT dominate the "
                              "score by unit choice regardless of lam's "
                              "magnitude. This is a structural guarantee, not "
                              "a tuned one",
            "saturation_note": "consistency falls below 0.01 at lam ~ 10.2, "
                               "i.e. h_acc ~ 2.8x nominal; beyond that the "
                               "evidence is saturated and further degradation "
                               "changes nothing downstream",
            "worked_points": {
                "h_acc=300 (nominal)": round((residual(300) / SIGMA) ** 2, 4),
                "h_acc=600 (2x nominal)": round((residual(600) / SIGMA) ** 2, 4),
                "h_acc=3000": round((residual(3000) / SIGMA) ** 2, 4),
                "h_acc=300000": round((residual(300000) / SIGMA) ** 2, 4),
            },
        },
        "existing_evidence_magnitude": {
            "clean_flights": _describe(ex_clean),
            "fault_flights": _describe(ex_fault),
        },
        "proposed_h_acc_evidence_magnitude": {
            "clean_phase": _describe(pr_clean),
            "jam_fix_valid": _describe(pr_valid),
            "jam_fix_invalid": _describe(pr_invalid),
        },
    }

    out["units"] = ("all four distributions below are consistency scores in "
                    "(0,1]; higher means MORE consistent, so a fault drives "
                    "the score DOWN")
    ex_c = out["existing_evidence_magnitude"]["clean_flights"]
    pr_c = out["proposed_h_acc_evidence_magnitude"]["clean_phase"]
    pr_i = out["proposed_h_acc_evidence_magnitude"]["jam_fix_invalid"]
    if ex_c and pr_c and pr_i:
        out["clean_quiet"] = pr_c["p50"] >= 0.99
        out["fault_separates"] = pr_i["p50"] <= 0.5
        out["in_same_bounded_space_as_existing"] = (
            0.0 <= pr_i["min"] <= 1.0 and 0.0 <= pr_c["max"] <= 1.0)
        out["comparable_criterion"] = (
            "proposed contribution lives in the same bounded (0,1] space as "
            "every existing relation, is quiet on clean data, and moves on "
            "fault -- checked without consulting any scored outcome")

    dest = os.path.join(MAER, "MAER_EVIDENCE_SCALE_AUDIT.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)

    print("=== evidence scale audit")
    print("  frozen transform worked points (lam, pre-EWMA):")
    for k, v in out["frozen_transform"]["worked_points"].items():
        print(f"    {k:26s} {v}")
    print("\n  existing layer evidence:")
    for k, v in out["existing_evidence_magnitude"].items():
        print(f"    {k:16s} {v}")
    print("\n  proposed h_acc evidence:")
    for k, v in out["proposed_h_acc_evidence_magnitude"].items():
        print(f"    {k:16s} {v}")
    if "p95_ratio_proposed_over_existing_fault" in out:
        print(f"\n  p95 ratio proposed/existing-fault : "
              f"{out['p95_ratio_proposed_over_existing_fault']}")
        print(f"  comparable (within 10x)           : {out['comparable']}")
    print(f"-> {os.path.relpath(dest, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
