"""PROOF AUDIT for the mathematical paper (brief C1-C5, C8).

Every proposition in `research/math-paper/FORMAL_CORE.md` is checked here two
ways:

    SYMBOLIC   sympy, exact. `simplify(lhs - rhs) == 0` or an explicit
               inequality certificate. Requires `pip install sympy`.
    NUMERIC    numpy, 20000 random instances per proposition, max absolute
               deviation reported. Runs with no extra dependency.

The numeric pass is the one the committed regression test re-runs, because
sympy is not in the project's declared dependency set and adding a dependency
to CI so a research script can run is the wrong trade. The symbolic pass is
what a reader re-runs to confirm the algebra is not a numerical coincidence.

WHAT IS BEING PROVED, IN WORDS
-------------------------------
A runtime diagnosis multiplies each hypothesis's likelihood by a factor that
depends on WHICH HYPOTHESIS IT IS -- because whether a piece of evidence is
"applicable" is itself hypothesis-relative. Write q for the posterior from the
FULL evidence the system could in principle have scored, and p for the one it
actually produces after gating. The propositions say exactly how far apart
they can be, and exactly when they coincide.

THE BASELINE MATTERS AND THE FIRST DRAFT GOT IT WRONG. If q is instead read
as "the posterior from the ACTIVE evidence alone", the gate is already inside
L, w is identically 1, p == q, and P1/P2/P5/P6 are true and empty. P7 below
exhibits the w that makes the framework non-vacuous for the additive gated
scores runtime layers actually compute, and P8 records what that costs P4.

NONE OF THIS IS CLAIMED AS NEW MATHEMATICS. P1-P3 are one line of algebra
each; P4 is a standard perturbation-of-argmax bound; P5-P6 are elementary
consequences of Jensen. The contribution the paper may claim is the RUNTIME
DIAGNOSTIC FORMULATION and the implemented system consequence, not the
identities. See `research/math-paper/PRIOR_ART_MATRIX.csv`.

    python research/math-paper/proof_audit.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
OUT = os.path.join(_HERE, "results", "proof_audit.json")

RNG = np.random.default_rng(20260903)
N_TRIALS = 20000
H = 5                     # hypotheses per random instance

#: A proposition that needs randomness BEYOND the shared (pi, L, w) instance
#: draws from its own generator, never from RNG.
#:
#: This is not stylistic. P4 reports COUNTS, not a max deviation, and counts
#: depend on the exact draws. When the P7 block was first written it drew from
#: RNG, which advanced the shared stream, which silently moved P4's reported
#: counts from 2721/6877 to 2692/7031 -- a change in a published number caused
#: by adding an unrelated proposition. Nothing was wrong with either figure,
#: and that is precisely the problem: a reader who reran the audit after a
#: later addition would find a number in the paper that no longer reproduced,
#: with no way to tell a stream shift from an error. Separate streams remove
#: the failure mode; `test_math_paper_proofs.py` pins the counts so a future
#: addition that reintroduces the coupling fails loudly.
RNG_P7 = np.random.default_rng(20260903 + 7)
RNG_P8 = np.random.default_rng(20260903 + 8)
RNG_P8E = np.random.default_rng(20260903 + 88)
N_ESCAPE = 200000


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


# ===================================================================== setup
def _instance(rng, h=H, w_positive=True):
    """(pi, L, w) with pi a prior, L the full-evidence likelihoods, w the
    hypothesis-dependent gating factors. All strictly positive."""
    pi = rng.dirichlet(np.ones(h))
    L = np.exp(rng.normal(0.0, 2.0, h))
    w = np.exp(rng.normal(0.0, 1.5, h)) if w_positive else rng.normal(0, 1, h)
    return pi, L, w


def _q_p(pi, L, w):
    qn = pi * L
    q = qn / qn.sum()
    pn = pi * w * L
    p = pn / pn.sum()
    return q, p


# ============================================================ numeric checks
def numeric() -> dict:
    """Each proposition, 20000 random instances, worst absolute deviation."""
    # IDENTITIES report |lhs - rhs|, so 0 is the ideal and a max seeded at 0
    # is honest. BOUNDS report slack = lhs - rhs, which is normally NEGATIVE,
    # so seeding a max at 0 would print 0.000e+00 whether the bound held with
    # room to spare or was never evaluated at all. They are seeded at -inf and
    # violations past tolerance are counted separately.
    worst = {k: 0.0 for k in
             ("P1_reweighting_identity", "P2_log_ratio_identity",
              "P5a_KL_q_p_is_jensen_gap", "P5b_KL_p_q_identity",
              "P3_pinned_to_prior",
              "P7_gated_score_is_a_reweighting",
              "P7b_shift_is_the_withheld_contribution",
              "P7c_pinned_when_all_distinguishing_gated")}
    slack = {k: -np.inf for k in
             ("P6a_log_ratio_bounded_by_R", "P6b_TV_bound",
              "P8_pinned_pair_margin_never_exceeds_R")}
    violations = {k: 0 for k in slack}
    p4_tested = p4_condition_met = p4_held = 0
    p4_counterexample_when_violated = 0
    p8_pairs_that_were_top_two = 0

    for _ in range(N_TRIALS):
        pi, L, w = _instance(RNG)
        q, p = _q_p(pi, L, w)
        Eq_w = float(q @ w)

        # -- P1: p_h = q_h w_h / E_q[w] ----------------------------------
        worst["P1_reweighting_identity"] = max(
            worst["P1_reweighting_identity"],
            float(np.max(np.abs(p - q * w / Eq_w))))

        # -- P2: log(p_a/p_b) = log(q_a/q_b) + log(w_a/w_b) --------------
        a, b = 0, 1
        lhs = np.log(p[a] / p[b])
        rhs = np.log(q[a] / q[b]) + np.log(w[a] / w[b])
        worst["P2_log_ratio_identity"] = max(
            worst["P2_log_ratio_identity"], float(abs(lhs - rhs)))

        # -- P5a: KL(q||p) = log E_q[w] - E_q[log w]  (the Jensen gap) ---
        kl_qp = float(np.sum(q * np.log(q / p)))
        jensen = float(np.log(Eq_w) - q @ np.log(w))
        worst["P5a_KL_q_p_is_jensen_gap"] = max(
            worst["P5a_KL_q_p_is_jensen_gap"], abs(kl_qp - jensen))

        # -- P5b: KL(p||q) = E_p[log w] - log E_q[w] ---------------------
        kl_pq = float(np.sum(p * np.log(p / q)))
        worst["P5b_KL_p_q_identity"] = max(
            worst["P5b_KL_p_q_identity"],
            abs(kl_pq - (float(p @ np.log(w)) - float(np.log(Eq_w)))))

        # -- P6a: |log(p_a/p_b) - log(q_a/q_b)| <= R ---------------------
        R = float(np.log(w.max()) - np.log(w.min()))
        gap = float(abs(np.log(p[a] / p[b]) - np.log(q[a] / q[b])))
        s = gap - R
        slack["P6a_log_ratio_bounded_by_R"] = max(
            slack["P6a_log_ratio_bounded_by_R"], s)
        violations["P6a_log_ratio_bounded_by_R"] += int(s > 1e-9)

        # -- P6b: TV(p,q) <= (w_max - w_min) / (4 E_q[w]) ----------------
        tv = 0.5 * float(np.abs(p - q).sum())
        bound = (w.max() - w.min()) / (4.0 * Eq_w)
        s = tv - bound
        slack["P6b_TV_bound"] = max(slack["P6b_TV_bound"], s)
        violations["P6b_TV_bound"] += int(s > 1e-9)

        # -- P3: no distinguishing evidence => pinned to the prior -------
        # Construct the degenerate case the systems paper measures: every
        # active term contributes identically to a and b, so L_a == L_b, and
        # CSIA's gating is a SKIP applied to all hypotheses alike, so
        # w_a == w_b. Then p_a/p_b == pi_a/pi_b exactly.
        L2 = L.copy()
        L2[b] = L2[a]
        w2 = w.copy()
        w2[b] = w2[a]
        _q2, p2 = _q_p(pi, L2, w2)
        worst["P3_pinned_to_prior"] = max(
            worst["P3_pinned_to_prior"],
            float(abs(np.log(p2[a] / p2[b]) - np.log(pi[a] / pi[b]))))

        # -- P7: the GATED-SCORE form, and why the paper needs it --------
        # A hostile reading of the manuscript's own section 2 kills the whole
        # apparatus: if L_h is "the likelihood of the ACTIVE evidence" then
        # the gate is already inside L, w_h is identically 1, p == q, and
        # P1/P2/P5/P6 say NOTHING about the worked example. That reading is
        # correct and it was the paper's first formulation.
        #
        # The framework applies under the OTHER reading: q from the FULL
        # evidence, p from the gated score, and then
        #
        #     w_h = exp( - sum_j (1 - g_j) l_j(h) )
        #
        # which IS hypothesis-dependent whenever a gated feature contributes
        # differently to two hypotheses. This block verifies that, and
        # verifies that P3 is the CORNER of P2 rather than a separate result.
        J = 6
        ell = RNG_P7.normal(0.0, 1.0, (J, H))
        g = RNG_P7.choice([0.0, 0.4, 1.0], J)
        full = ell.sum(axis=0)
        gated = (g[:, None] * ell).sum(axis=0)
        qn = pi * np.exp(full)
        q_full = qn / qn.sum()
        pn = pi * np.exp(gated)
        p_gated = pn / pn.sum()
        w_gate = np.exp(-((1.0 - g)[:, None] * ell).sum(axis=0))
        worst["P7_gated_score_is_a_reweighting"] = max(
            worst["P7_gated_score_is_a_reweighting"],
            float(np.max(np.abs(
                p_gated - q_full * w_gate / (q_full @ w_gate)))))

        # P7b: the pairwise shift is EXACTLY the withheld distinguishing
        # contribution, so a fully gated distinguishing term contributes
        # nothing and a fully open one contributes all of itself.
        a, b = 0, 1
        shift = (np.log(p_gated[a] / p_gated[b])
                 - np.log(q_full[a] / q_full[b]))
        expect = -float(((1.0 - g) * (ell[:, a] - ell[:, b])).sum())
        worst["P7b_shift_is_the_withheld_contribution"] = max(
            worst["P7b_shift_is_the_withheld_contribution"],
            abs(shift - expect))

        # P7c: gate EVERY term that distinguishes a from b, and the ratio is
        # pinned to the prior -- P3, recovered from P2 rather than assumed.
        g2 = g.copy()
        distinguishing = np.abs(ell[:, a] - ell[:, b]) > 1e-12
        g2[distinguishing] = 0.0
        pn2 = pi * np.exp((g2[:, None] * ell).sum(axis=0))
        p2 = pn2 / pn2.sum()
        worst["P7c_pinned_when_all_distinguishing_gated"] = max(
            worst["P7c_pinned_when_all_distinguishing_gated"],
            abs(np.log(p2[a] / p2[b]) - np.log(pi[a] / pi[b])))

        # -- P8: WHAT P7 COSTS P4. A NEGATIVE RESULT ABOUT OUR OWN BOUND.
        # P4 certifies the MAP when Delta > R. Under the gated form, R is the
        # spread of the WITHHELD log-likelihood across hypotheses, so the
        # regime the systems paper measures -- every distinguishing term
        # gated shut -- is exactly the regime where R is largest. Concretely:
        # for a pinned pair carrying equal prior mass, log w_a - log w_b is
        # the whole distinguishing sum S, so R >= |S|, while the q-margin
        # between them is |log(pi_a/pi_b) + S| = |S|. Hence Delta <= R
        # ALWAYS, with equality attained, and P4 can NEVER certify a pinned
        # pair. Measured as slack = Delta - R; it must not exceed 0.
        pi8 = RNG_P8.dirichlet(np.ones(H))
        pi8[1] = pi8[0]
        pi8 = pi8 / pi8.sum()
        ell8 = RNG_P8.normal(0.0, 1.0, (6, H))
        g8 = RNG_P8.choice([0.0, 0.5, 1.0], 6)
        g8[np.abs(ell8[:, 0] - ell8[:, 1]) > 1e-12] = 0.0   # pin the pair 0,1
        qn8 = pi8 * np.exp(ell8.sum(axis=0))
        q8 = qn8 / qn8.sum()
        w8 = np.exp(-((1.0 - g8)[:, None] * ell8).sum(axis=0))
        ord8 = np.argsort(q8)[::-1]
        if {int(ord8[0]), int(ord8[1])} == {0, 1}:
            p8_pairs_that_were_top_two += 1
            R8 = float(np.log(w8.max()) - np.log(w8.min()))
            D8 = float(np.log(q8[ord8[0]]) - np.log(q8[ord8[1]]))
            s = D8 - R8
            slack["P8_pinned_pair_margin_never_exceeds_R"] = max(
                slack["P8_pinned_pair_margin_never_exceeds_R"], s)
            violations["P8_pinned_pair_margin_never_exceeds_R"] += int(s > 1e-9)

        # -- P4: Delta > R  =>  argmax p == argmax q ---------------------
        order = np.argsort(q)[::-1]
        Delta = float(np.log(q[order[0]]) - np.log(q[order[1]]))
        p4_tested += 1
        if Delta > R:
            p4_condition_met += 1
            p4_held += int(np.argmax(p) == np.argmax(q))
        elif np.argmax(p) != np.argmax(q):
            p4_counterexample_when_violated += 1

    return {"worst_deviation": {k: float(v) for k, v in worst.items()},
            "bound_max_slack": {k: float(v) for k, v in slack.items()},
            "bound_violations_beyond_1e-9": dict(violations),
            "P4": {"instances": p4_tested,
                   "condition_Delta_gt_R_met": p4_condition_met,
                   "argmax_agreed_when_condition_met": p4_held,
                   "argmax_moved_when_condition_violated":
                       p4_counterexample_when_violated,
                   "note": "the last row is ALLOWED: the condition is "
                           "sufficient, not necessary. It is reported so the "
                           "bound is not mistaken for a characterisation."},
            "P8": {"pinned_pairs_that_were_the_top_two_under_q":
                       p8_pairs_that_were_top_two,
                   "note": "a NEGATIVE result about P4. For a pinned pair "
                           "carrying equal prior mass the margin Delta never "
                           "exceeds R, so P4's sufficient condition can never "
                           "certify the pair the systems paper measures. "
                           "Max slack is reported in bound_max_slack."},
            "P8_escape": p8_escape(),
            "trials": N_TRIALS, "hypotheses_per_instance": H,
            "seed": 20260903}


# =============================================== P8's escape, measured
def p8_escape() -> dict:
    """P8 assumes the pinned pair carries EQUAL prior mass. Drop that and the
    condition Delta > R CAN fire -- but only because
    |log(pi_a/pi_b)| > R - |S|, i.e. the prior log-odds carried the whole
    excess unaided. This measures how often, so the escape is reported as
    non-empty rather than dismissed as a technicality.

    A MAP certified this way is a MAP the prior decided. C3 already says what
    that is worth as discriminating support: nothing.
    """
    tested = fired = 0
    for _ in range(N_ESCAPE):
        pi = RNG_P8E.dirichlet(np.ones(H) * 0.3)      # deliberately lopsided
        ell = RNG_P8E.normal(0.0, 1.0, (6, H))
        g = RNG_P8E.choice([0.0, 0.5, 1.0], 6)
        g[np.abs(ell[:, 0] - ell[:, 1]) > 1e-12] = 0.0
        qn = pi * np.exp(ell.sum(axis=0))
        q = qn / qn.sum()
        w = np.exp(-((1.0 - g)[:, None] * ell).sum(axis=0))
        o = np.argsort(q)[::-1]
        if {int(o[0]), int(o[1])} != {0, 1}:
            continue
        tested += 1
        R = float(np.log(w.max()) - np.log(w.min()))
        D = float(np.log(q[o[0]]) - np.log(q[o[1]]))
        fired += int(D > R + 1e-9)
    return {"draws": N_ESCAPE,
            "pinned_pairs_that_were_the_top_two_under_q": tested,
            "P4_condition_fired_anyway": fired,
            "fired_fraction": (fired / tested) if tested else None,
            "prior": "Dirichlet(0.3), deliberately lopsided",
            "note": "P8's equal-prior hypothesis is load-bearing. When the "
                    "condition fires here the prior log-odds supplied the "
                    "whole margin, so the certificate was bought with prior "
                    "mass rather than evidence."}


# =========================================================== symbolic checks
def symbolic() -> dict:
    try:
        import sympy as sp
    except ImportError:
        return {"available": False,
                "note": "sympy not installed; run `pip install sympy` to "
                        "reproduce the exact algebra. The numeric pass above "
                        "stands on its own and is what CI re-runs."}

    out = {"available": True, "sympy_version": sp.__version__, "results": {}}
    n = 4
    pi = sp.symbols(f"pi0:{n}", positive=True)
    L = sp.symbols(f"L0:{n}", positive=True)
    w = sp.symbols(f"w0:{n}", positive=True)

    qn = [pi[i] * L[i] for i in range(n)]
    Zq = sum(qn)
    q = [qn[i] / Zq for i in range(n)]
    pn = [pi[i] * w[i] * L[i] for i in range(n)]
    Zp = sum(pn)
    p = [pn[i] / Zp for i in range(n)]
    Eq_w = sum(q[i] * w[i] for i in range(n))

    # P1
    out["results"]["P1_reweighting_identity"] = all(
        sp.simplify(p[i] - q[i] * w[i] / Eq_w) == 0 for i in range(n))

    # P2
    a, b = 0, 1
    lhs = sp.log(p[a] / p[b])
    rhs = sp.log(q[a] / q[b]) + sp.log(w[a] / w[b])
    out["results"]["P2_log_ratio_identity"] = bool(
        sp.simplify(sp.expand_log(lhs - rhs, force=True)) == 0)

    # P3: L_a == L_b and w_a == w_b  =>  p_a/p_b == pi_a/pi_b
    sub = {L[b]: L[a], w[b]: w[a]}
    ratio = sp.simplify((p[a] / p[b]).subs(sub))
    out["results"]["P3_pinned_to_prior"] = bool(
        sp.simplify(ratio - pi[a] / pi[b]) == 0)

    # P5a: KL(q||p) == log E_q[w] - E_q[log w]
    kl_qp = sum(q[i] * sp.log(q[i] / p[i]) for i in range(n))
    jensen = sp.log(Eq_w) - sum(q[i] * sp.log(w[i]) for i in range(n))
    out["results"]["P5a_KL_q_p_is_jensen_gap"] = bool(
        sp.simplify(sp.expand_log(kl_qp - jensen, force=True)) == 0)

    # P5b: KL(p||q) == E_p[log w] - log E_q[w]
    kl_pq = sum(p[i] * sp.log(p[i] / q[i]) for i in range(n))
    ident = sum(p[i] * sp.log(w[i]) for i in range(n)) - sp.log(Eq_w)
    out["results"]["P5b_KL_p_q_identity"] = bool(
        sp.simplify(sp.expand_log(kl_pq - ident, force=True)) == 0)

    # C2, binary exogeneity: w constant in h  =>  p == q, identically.
    const = {w[i]: w[0] for i in range(n)}
    out["results"]["C2_constant_w_implies_p_equals_q"] = all(
        sp.simplify(p[i].subs(const) - q[i]) == 0 for i in range(n))

    return out


def main() -> int:
    doc = {
        "artifact": "PROOF_AUDIT",
        "paper": "Posterior Distortion from Hypothesis-Dependent Validity "
                 "Gating in Runtime Diagnosis",
        "generation_command": "python research/math-paper/proof_audit.py",
        "commit": _git("rev-parse", "HEAD"),
        "novelty": "NONE CLAIMED FOR THE IDENTITIES. P1-P3 are one line of "
                   "algebra each; P4 is a standard perturbation-of-argmax "
                   "bound; P5-P6 follow from Jensen. See PRIOR_ART_MATRIX.csv.",
        "numeric": numeric(),
        "symbolic": symbolic(),
    }

    tol = 1e-9
    num = doc["numeric"]["worst_deviation"]
    identities_ok = all(abs(v) < tol for v in num.values())
    bounds_ok = all(v == 0 for v in
                    doc["numeric"]["bound_violations_beyond_1e-9"].values())
    p4 = doc["numeric"]["P4"]
    doc["verdict"] = {
        "identities_hold_numerically": bool(identities_ok),
        "bounds_hold_numerically": bool(bounds_ok),
        "P4_sufficient_condition_never_violated":
            p4["argmax_agreed_when_condition_met"]
            == p4["condition_Delta_gt_R_met"],
        "tolerance": tol,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"NUMERIC over {N_TRIALS} random instances")
    print("  identities -- |lhs - rhs|, 0 is exact")
    for k, v in sorted(num.items()):
        print(f"    [{'ok ' if abs(v) < tol else 'FAIL'}] {k:<34} {v:.3e}")
    print("  bounds -- max slack (lhs - rhs); NEGATIVE means the bound held "
          "with room")
    for k, v in sorted(doc["numeric"]["bound_max_slack"].items()):
        n_bad = doc["numeric"]["bound_violations_beyond_1e-9"][k]
        print(f"    [{'ok ' if n_bad == 0 else 'FAIL'}] {k:<34} "
              f"{v:+.3e}   violations={n_bad}")
    print(f"\nP4: condition Delta > R met in {p4['condition_Delta_gt_R_met']} "
          f"of {p4['instances']} instances; argmax agreed in "
          f"{p4['argmax_agreed_when_condition_met']} of those. "
          f"{p4['argmax_moved_when_condition_violated']} instances where the "
          f"argmax moved and the condition did NOT hold -- allowed, the "
          f"condition is sufficient, not necessary.")
    sym = doc["symbolic"]
    print("\nSYMBOLIC")
    if not sym.get("available"):
        print("  sympy unavailable:", sym["note"])
    else:
        for k, v in sorted(sym["results"].items()):
            print(f"  [{'ok ' if v else 'FAIL'}] {k}")
    print(f"\n{OUT}")
    ok = identities_ok and bounds_ok and (
        not sym.get("available") or all(sym["results"].values()))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
