"""Regression for the mathematical paper's formal core (brief C1-C8).

The identities are re-derived here in numpy rather than read out of the
committed artifact, so a broken proposition fails in CI even if nobody
regenerated `proof_audit.json`. sympy is NOT imported: it is not a declared
project dependency and `tests/test_ci_env.py` would rightly fail an
undeclared import. The exact symbolic pass lives in
`research/math-paper/proof_audit.py` for a human to re-run.

The novelty audit is enforced too. A paper whose forbidden-phrase list lives
only in a markdown file will acquire one of those phrases the first time
somebody is writing an abstract at speed.
"""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MP = os.path.join(ROOT, "research", "math-paper")
TOL = 1e-9


def _instance(rng, h=5):
    pi = rng.dirichlet(np.ones(h))
    L = np.exp(rng.normal(0.0, 2.0, h))
    w = np.exp(rng.normal(0.0, 1.5, h))
    return pi, L, w


def _q_p(pi, L, w):
    qn = pi * L
    pn = pi * w * L
    return qn / qn.sum(), pn / pn.sum()


@pytest.fixture(scope="module")
def instances():
    rng = np.random.default_rng(4242)
    return [_instance(rng) for _ in range(2000)]


def test_P1_reweighting_identity(instances):
    """p_h = q_h w_h / E_q[w]."""
    for pi, L, w in instances:
        q, p = _q_p(pi, L, w)
        assert np.max(np.abs(p - q * w / (q @ w))) < TOL


def test_P2_log_ratio_decomposition(instances):
    """log(p_a/p_b) = log(q_a/q_b) + log(w_a/w_b).

    The gating contributes an ADDITIVE, EVIDENCE-INDEPENDENT offset to every
    pairwise log-posterior ratio. It does not shrink as evidence accumulates.
    """
    for pi, L, w in instances:
        q, p = _q_p(pi, L, w)
        for a, b in ((0, 1), (2, 3), (1, 4)):
            lhs = np.log(p[a] / p[b])
            rhs = np.log(q[a] / q[b]) + np.log(w[a] / w[b])
            assert abs(lhs - rhs) < TOL


def test_P3_no_distinguishing_evidence_pins_the_ratio_to_the_prior(instances):
    """THE PROPOSITION THE SYSTEMS PAPER MEASURES."""
    for pi, L, w in instances:
        a, b = 0, 1
        L2, w2 = L.copy(), w.copy()
        L2[b], w2[b] = L2[a], w2[a]        # identical likelihood AND factor
        _q, p = _q_p(pi, L2, w2)
        assert abs(np.log(p[a] / p[b]) - np.log(pi[a] / pi[b])) < TOL


def test_C2_constant_validity_factor_leaves_the_posterior_alone(instances):
    for pi, L, w in instances:
        q, p = _q_p(pi, L, np.full_like(w, float(w[0])))
        assert np.max(np.abs(p - q)) < TOL


def test_P5a_KL_q_p_is_exactly_the_jensen_gap(instances):
    """And is therefore >= 0, and = 0 exactly when w is constant (C2)."""
    for pi, L, w in instances:
        q, p = _q_p(pi, L, w)
        kl = float(np.sum(q * np.log(q / p)))
        jensen = float(np.log(q @ w) - q @ np.log(w))
        assert abs(kl - jensen) < TOL
        assert kl >= -TOL


def test_P5b_KL_p_q_identity(instances):
    for pi, L, w in instances:
        q, p = _q_p(pi, L, w)
        kl = float(np.sum(p * np.log(p / q)))
        assert abs(kl - (float(p @ np.log(w)) - float(np.log(q @ w)))) < TOL


def test_P6a_log_ratio_shift_is_bounded_by_the_log_range(instances):
    for pi, L, w in instances:
        q, p = _q_p(pi, L, w)
        R = float(np.log(w.max()) - np.log(w.min()))
        for a, b in ((0, 1), (2, 3)):
            gap = abs(np.log(p[a] / p[b]) - np.log(q[a] / q[b]))
            assert gap <= R + TOL


def test_P6b_total_variation_bound(instances):
    for pi, L, w in instances:
        q, p = _q_p(pi, L, w)
        tv = 0.5 * float(np.abs(p - q).sum())
        assert tv <= (w.max() - w.min()) / (4.0 * (q @ w)) + TOL


def test_P4_is_sufficient_and_is_not_claimed_to_be_necessary(instances):
    """Delta > R implies the argmax is unchanged. The converse is FALSE and
    the test asserts the counterexamples exist, so nobody later reads the
    proposition as a characterisation."""
    held = met = moved_without_condition = 0
    for pi, L, w in instances:
        q, p = _q_p(pi, L, w)
        R = float(np.log(w.max()) - np.log(w.min()))
        s = np.sort(np.log(q))[::-1]
        Delta = float(s[0] - s[1])
        if Delta > R:
            met += 1
            held += int(np.argmax(p) == np.argmax(q))
        elif np.argmax(p) != np.argmax(q):
            moved_without_condition += 1
    assert met > 0 and held == met, (held, met)
    assert moved_without_condition > 0, (
        "no counterexample to the converse was generated; the test can no "
        "longer distinguish 'sufficient' from 'necessary'")


# =================================================== the committed artifact
def test_the_committed_audit_agrees_with_this_test():
    path = os.path.join(MP, "results", "proof_audit.json")
    if not os.path.exists(path):
        pytest.skip("proof_audit.json not generated")
    doc = json.load(open(path, encoding="utf-8"))
    assert doc["verdict"]["identities_hold_numerically"] is True
    assert doc["verdict"]["bounds_hold_numerically"] is True
    assert doc["verdict"]["P4_sufficient_condition_never_violated"] is True
    if doc["symbolic"].get("available"):
        assert all(doc["symbolic"]["results"].values())


def test_the_audit_reports_bound_slack_not_a_zero_seeded_maximum():
    """A max seeded at 0 cannot distinguish 'the bound always held' from
    'the bound was never evaluated'. This caught a real reporting defect."""
    path = os.path.join(MP, "results", "proof_audit.json")
    if not os.path.exists(path):
        pytest.skip("proof_audit.json not generated")
    doc = json.load(open(path, encoding="utf-8"))
    assert "bound_max_slack" in doc["numeric"]
    assert "bound_violations_beyond_1e-9" in doc["numeric"]
    assert doc["numeric"]["bound_max_slack"]["P6b_TV_bound"] < 0.0


def test_P4_reports_a_denominator_not_only_a_numerator():
    path = os.path.join(MP, "results", "proof_audit.json")
    if not os.path.exists(path):
        pytest.skip("proof_audit.json not generated")
    p4 = json.load(open(path, encoding="utf-8"))["numeric"]["P4"]
    assert p4["condition_Delta_gt_R_met"] > 0
    assert p4["argmax_agreed_when_condition_met"] \
        == p4["condition_Delta_gt_R_met"]
    assert p4["argmax_moved_when_condition_violated"] > 0


# ======================================================== the novelty audit
FORBIDDEN = (
    "new information theory",
    "first posterior-reweighting theorem",
    "novel kl bound",
    "new bayesian identity",
    "we prove for the first time",
)


#: A line that FORBIDS a phrase necessarily contains it. Exempting whole
#: files would blind the test to the manuscript; exempting whole lines that
#: carry a prohibition marker keeps it looking at every assertion.
#: "claim no" is the manuscript's own disclaimer form -- "We claim no new
#: information-theoretic result, no new Bayesian identity". A line that
#: DISCLAIMS a phrase necessarily contains it, and the guard exists to catch
#: the phrase being ASSERTED.
_PROHIBITION_MARKERS = ("forbidden", "must not", "may not", "never",
                        "none claimed", "do not claim", "claim no",
                        "not acceptable", "prohibit")


def _is_mention_only(line: str, phrase: str) -> bool:
    """USE versus MENTION. A register that quotes a banned phrase in order to
    ban it is mentioning it; a manuscript that writes it plain is using it.
    Every legitimate occurrence in this repository is quoted."""
    quoted = 0
    for q in ('"', "'", "`"):
        quoted += line.count(f"{q}{phrase}{q}")
    return quoted >= line.count(phrase)


def test_no_forbidden_novelty_phrase_appears():
    """C7. Every proposition in this paper is labelled KNOWN; a phrase from
    this list, used as an ASSERTION, would contradict the paper's own
    prior-art matrix.

    Matched line by line rather than file by file. The first version scanned
    whole files and failed on PRIOR_ART_MATRIX.csv, whose 'claim consequence'
    column exists precisely to forbid these phrases -- a test that fails on
    the register of prohibitions is a test that gets deleted.
    """
    roots = [MP, os.path.join(ROOT, "papers", "gate_conditioning")]
    checked = 0
    for root in roots:
        for dirpath, _d, filenames in os.walk(root):
            for f in sorted(filenames):
                if not f.endswith((".md", ".tex", ".py", ".csv")):
                    continue
                path = os.path.join(dirpath, f)
                checked += 1
                for n, line in enumerate(
                        open(path, encoding="utf-8"), start=1):
                    low = line.lower()
                    if any(m in low for m in _PROHIBITION_MARKERS):
                        continue
                    for phrase in FORBIDDEN:
                        if phrase not in low:
                            continue
                        assert _is_mention_only(low, phrase), \
                            f"{path}:{n}: {phrase!r} used, not quoted"
    assert checked > 0


def test_every_proposition_is_labelled_known():
    """If a row of the novelty table ever stops saying KNOWN, the prior-art
    matrix and the paper have diverged."""
    text = open(os.path.join(MP, "NOVELTY_AUDIT.md"), encoding="utf-8").read()
    assert "Every mathematical proposition in this paper is labelled KNOWN" \
        in text
    for pid in ("P1", "P2", "P3", "C2", "C3", "P4", "P5a", "P5b",
                "P6a", "P6b"):
        assert f"| {pid} |" in text, pid


def test_the_prior_art_matrix_records_the_unfound_reference():
    """A reference the brief named and the search could not find is an open
    hole. Silently dropping it would be the dishonest outcome."""
    import csv as _csv
    path = os.path.join(MP, "PRIOR_ART_MATRIX.csv")
    rows = list(_csv.DictReader(open(path, encoding="utf-8")))
    assert rows
    statuses = {r["status"] for r in rows}
    assert "NOT_FOUND_NEEDS_HUMAN" in statuses
    # And nothing may claim to be verified against a publisher record, because
    # every publisher route is blocked from this environment.
    assert "VERIFIED" not in statuses
