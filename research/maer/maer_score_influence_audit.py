"""How far can ONE added relation move the hypothesis ranking?

THE CLAIM THIS RETRACTS. The Stage 1 report said: "consistency is bounded in
(0,1], therefore the new relation cannot dominate diagnosis by unit choice."
That is too strong and it is withdrawn. Bounded relation consistency bounds the
INPUT to the likelihood mapping; it says nothing on its own about the resulting
pairwise log-score correction, which is what decides ranking.

This traces the whole path analytically, from the frozen source:

    h_acc -> u = max(0, log(h_acc/h0)) / kappa_h
          -> lam = EWMA_0.15(u^2)
          -> c = consistency(lam) = exp(-0.5 max(0, lam-1))
          -> per-tick log-likelihood (csia/diagnosis/bayes.py DiagnosisCore.step)
                 in  the cause's low-set: ll += gate * log(1 - c + EPS)
                 not in the low-set     : ll += gate * log(c + EPS)
          -> EWMA smoothing (SMOOTH_ALPHA)
          -> tempering (EVIDENCE_MULT)
          -> softmax against log-prior

and asks the only question that matters for scoring integrity: can one
saturated h_acc relation, by itself, put gps_fault above nominal?

Every constant is imported from the frozen core rather than transcribed.

  python research/maer/maer_score_influence_audit.py
"""

from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.diagnosis.bayes import (CAUSES, EPS, EVIDENCE_MULT,  # noqa: E402
                                  PRIOR_NOMINAL, SMOOTH_ALPHA)

H0_MM = 300.0
KAPPA_H = math.log(2.0)
TARGET = "gps_fault"


def u(h_acc_mm):
    """Normalized degradation units above declared nominal accuracy."""
    return max(0.0, math.log(float(h_acc_mm) / H0_MM)) / KAPPA_H


def consistency(lam):
    return math.exp(-0.5 * max(0.0, lam - 1.0))


def main() -> int:
    names = list(CAUSES)
    n = len(names)
    prior_other = (1.0 - PRIOR_NOMINAL) / (n - 1)
    log_prior_nominal = math.log(PRIOR_NOMINAL)
    log_prior_target = math.log(prior_other)
    barrier = log_prior_nominal - log_prior_target

    # ---- per-tick pairwise correction from ONE relation, at gate = 1 ------
    # in the target's low-set  -> log(1 - c + EPS)
    # not in it (e.g. nominal) -> log(c + EPS)
    def delta(c):
        return math.log(1.0 - c + EPS) - math.log(c + EPS)

    d_max = delta(0.0)        # fully degraded: maximum support for the target
    d_min = delta(1.0)        # fully healthy: maximum support against it

    # EWMA converges to its input, so steady state equals the per-tick value.
    steady_target_minus_nominal = EVIDENCE_MULT * d_max
    net = steady_target_minus_nominal - barrier

    # ---- saturation arithmetic, solved rather than asserted ---------------
    lam_001 = 1.0 + 2.0 * math.log(100.0)
    ratio_001 = 2.0 ** math.sqrt(lam_001)
    lam_050 = 1.0 + 2.0 * math.log(2.0)
    ratio_050 = 2.0 ** math.sqrt(lam_050)

    out = {
        "retracted_claim": {
            "text": "consistency is bounded in (0,1], therefore the new "
                    "relation cannot dominate diagnosis by unit choice",
            "why_wrong": "bounding the INPUT to the likelihood mapping does "
                         "not bound the pairwise log-score correction, which "
                         "is what decides ranking. The correction is bounded "
                         "by EPS, not by the consistency range",
        },
        "frozen_constants": {
            "EPS": EPS, "SMOOTH_ALPHA": SMOOTH_ALPHA,
            "EVIDENCE_MULT": EVIDENCE_MULT, "PRIOR_NOMINAL": PRIOR_NOMINAL,
            "n_causes": n,
            "prior_other": round(prior_other, 6),
        },
        "consistency_range": {"min": 0.0, "max": 1.0},
        "per_tick_pairwise_log_correction_gate_1": {
            "target_minus_nominal_at_c_0": round(d_max, 6),
            "target_minus_nominal_at_c_1": round(d_min, 6),
            "bounded_by": "EPS -- log((1+EPS)/EPS) = "
                          f"{round(math.log((1 + EPS) / EPS), 6)}",
            "note": "this bound is IDENTICAL for every existing relation; "
                    "h_acc is not privileged by its units",
        },
        "after_smoothing_and_tempering": {
            "steady_state_target_minus_nominal": round(
                steady_target_minus_nominal, 6),
            "smoothing_effect": "EWMA converges to its input, so a sustained "
                                "saturated relation reaches the full value; "
                                "SMOOTH_ALPHA sets only how fast",
            "ticks_to_90_percent": round(
                math.log(0.1) / math.log(1 - SMOOTH_ALPHA), 1),
        },
        "prior_barrier": {
            "log_prior_nominal": round(log_prior_nominal, 6),
            "log_prior_target": round(log_prior_target, 6),
            "barrier_nominal_over_target": round(barrier, 6),
        },
        "decisive_question": {
            "question": "does ONE saturated h_acc relation alone put "
                        f"{TARGET} above nominal?",
            "net_margin": round(net, 6),
            "answer": bool(net > 0),
            "reading": ("YES -- a single sustained saturated relation in a "
                        "cause's low-set overcomes the nominal prior on its "
                        "own, with no other evidence"
                        if net > 0 else
                        "NO -- the prior survives a single saturated relation"),
        },
        "saturation_arithmetic": {
            "consistency_0.01_at_lambda": round(lam_001, 8),
            "derivation": "consistency = exp(-0.5(lam-1)) = 0.01 "
                          "=> lam = 1 + 2 ln 100",
            "h_acc_over_h0_at_that_lambda": round(ratio_001, 4),
            "h_acc_mm_at_h0_300": round(300.0 * ratio_001, 1),
            "consistency_0.50_at_lambda": round(lam_050, 6),
            "h_acc_over_h0_at_half": round(ratio_050, 4),
            "CORRECTION": "an earlier report stated 2.8x nominal for the 0.01 "
                          "threshold. That was wrong: 2748 mm is the absolute "
                          "threshold and was mistakenly written as a ratio. "
                          "The ratio is 9.16x",
        },
    }

    if net > 0:
        verdict = "DETECTOR_DOMINANT_BUT_DECLARED"
        rationale = (
            "One saturated relation in a single-feature cause overcomes the "
            "nominal prior by itself. This is NOT a property of the h_acc "
            "transform: the per-relation bound log((1+EPS)/EPS) is the same "
            "for every relation in the layer, and gps_fault's evidence set "
            "already had exactly one member. It is a property of the frozen "
            "diagnosis design -- a single-feature cause plus an EPS floor -- "
            "and it is declared here rather than discovered after scoring. "
            "The consequence for the experiment is that H1's DIRECTION is "
            "close to structurally implied once the relation is live and "
            "degraded, so the informative content sits in H2's crossover and "
            "in magnitude/timing, not in the sign of H1.")
    else:
        verdict = "SCALE_COMPATIBLE"
        rationale = "the prior survives a single saturated relation"
    out["verdict"] = verdict
    out["verdict_rationale"] = rationale

    dest = os.path.join(ROOT, "research", "maer",
                        "MAER_HACC_SCORE_INFLUENCE_AUDIT.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)

    print("=== h_acc downstream score-influence audit")
    print(f"  causes                        : {n}  {names}")
    print(f"  per-tick pairwise correction  : {d_min:+.6f} .. {d_max:+.6f}")
    print(f"  bound                         : log((1+EPS)/EPS) = "
          f"{math.log((1 + EPS) / EPS):.6f}  (same for EVERY relation)")
    print(f"  x EVIDENCE_MULT at steady state: {steady_target_minus_nominal:+.6f}")
    print(f"  prior barrier nominal>target  : {barrier:+.6f}")
    print(f"  NET margin                    : {net:+.6f}")
    print(f"  one saturated relation flips rank: {net > 0}")
    print(f"\n  saturation: consistency=0.01 at lam={lam_001:.8f}, "
          f"h_acc/h0={ratio_001:.4f} ({300 * ratio_001:.0f} mm)")
    print(f"  VERDICT: {verdict}")
    print(f"-> {os.path.relpath(dest, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
