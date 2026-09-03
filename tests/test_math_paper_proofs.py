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


# ============================================ the gated-score form (P7, P8)
#
# THE PROPOSITIONS THAT MAKE THE FRAMEWORK NON-VACUOUS, AND THE ONE THAT SAYS
# WHAT THAT COSTS. See research/math-paper/FORMAL_CORE.md 1.1 and 9a. If L_h
# is read as the ACTIVE-evidence likelihood, w is identically 1 and every test
# above passes while saying nothing about the system. These tests use the
# full-evidence baseline and therefore have content.


def _gated(rng, h=5, j=6, gates=(0.0, 0.4, 1.0)):
    """(pi, ell, g): a prior, per-feature log-likelihood contributions, and
    gates in [0,1]. Built here rather than imported, like everything else in
    this file."""
    pi = rng.dirichlet(np.ones(h))
    ell = rng.normal(0.0, 1.0, (j, h))
    g = rng.choice(np.asarray(gates), j)
    return pi, ell, g


def _post(pi, logL):
    n = pi * np.exp(logL)
    return n / n.sum()


@pytest.fixture(scope="module")
def gated_instances():
    rng = np.random.default_rng(70707)
    return [_gated(rng) for _ in range(2000)]


def test_P7_the_gated_score_is_a_reweighting_of_the_full_evidence_posterior():
    """w_h = exp(-sum_j (1-g_j) l_j(h)), and it is NOT identically 1."""
    rng = np.random.default_rng(70707)
    varied = 0
    for _ in range(2000):
        pi, ell, g = _gated(rng)
        q = _post(pi, ell.sum(axis=0))
        p = _post(pi, (g[:, None] * ell).sum(axis=0))
        w = np.exp(-((1.0 - g)[:, None] * ell).sum(axis=0))
        assert np.max(np.abs(p - q * w / (q @ w))) < TOL
        varied += int(w.max() / w.min() > 1.0 + 1e-9)
    assert varied > 1500, (
        f"w varied across hypotheses in only {varied}/2000 instances. If it "
        f"stops varying, the framework has collapsed back to Reading A and "
        f"P1-P6 are describing a reweighting by the constant 1.")


def test_P7b_the_shift_is_exactly_the_withheld_distinguishing_contribution(
        gated_instances):
    for pi, ell, g in gated_instances:
        q = _post(pi, ell.sum(axis=0))
        p = _post(pi, (g[:, None] * ell).sum(axis=0))
        for a, b in ((0, 1), (2, 3), (1, 4)):
            shift = np.log(p[a] / p[b]) - np.log(q[a] / q[b])
            withheld = -float(((1.0 - g) * (ell[:, a] - ell[:, b])).sum())
            assert abs(shift - withheld) < TOL


def test_P7c_gating_every_distinguishing_feature_pins_the_ratio(
        gated_instances):
    """THE STATEMENT THE SYSTEMS PAPER ACTUALLY MEASURES -- P3's conclusion
    reached without P3's hypotheses, which do NOT hold in the implemented
    case under the full-evidence baseline."""
    for pi, ell, g in gated_instances:
        a, b = 0, 1
        g2 = g.copy()
        g2[np.abs(ell[:, a] - ell[:, b]) > 1e-12] = 0.0
        p = _post(pi, (g2[:, None] * ell).sum(axis=0))
        assert abs(np.log(p[a] / p[b]) - np.log(pi[a] / pi[b])) < TOL


def test_P7c_case_has_L_a_neq_L_b_and_w_a_neq_w_b():
    """The point of P7c. FORMAL_CORE.md once claimed the skip made w_a = w_b
    'by construction'; it does not, and this test is why that claim cannot
    come back. Both P3 hypotheses FAIL and the ratio is pinned anyway."""
    rng = np.random.default_rng(70708)
    both_fail = 0
    for _ in range(2000):
        pi, ell, g = _gated(rng)
        a, b = 0, 1
        dist = np.abs(ell[:, a] - ell[:, b]) > 1e-12
        if not dist.any():
            continue
        g2 = g.copy()
        g2[dist] = 0.0
        logL = ell.sum(axis=0)                       # full evidence
        w = np.exp(-((1.0 - g2)[:, None] * ell).sum(axis=0))
        both_fail += int(abs(logL[a] - logL[b]) > 1e-9
                         and abs(np.log(w[a]) - np.log(w[b])) > 1e-9)
    assert both_fail > 1900, (
        f"only {both_fail}/2000 pinned instances had BOTH L_a != L_b and "
        f"w_a != w_b; if this drops, the reading has silently reverted")


def test_P8_the_MAP_condition_can_never_certify_a_pinned_pair():
    """A NEGATIVE RESULT ABOUT OUR OWN PROPOSITION P4, asserted rather than
    hoped for. Delta <= R always, so 'Delta > R' cannot fire on the pair the
    systems paper measures."""
    rng = np.random.default_rng(70709)
    tested = 0
    worst = -np.inf
    for _ in range(4000):
        pi, ell, g = _gated(rng, gates=(0.0, 0.5, 1.0))
        a, b = 0, 1
        g = g.copy()
        g[np.abs(ell[:, a] - ell[:, b]) > 1e-12] = 0.0
        pi = pi.copy()
        pi[b] = pi[a]
        pi = pi / pi.sum()
        q = _post(pi, ell.sum(axis=0))
        w = np.exp(-((1.0 - g)[:, None] * ell).sum(axis=0))
        order = np.argsort(q)[::-1]
        if {int(order[0]), int(order[1])} != {a, b}:
            continue
        tested += 1
        R = float(np.log(w.max()) - np.log(w.min()))
        Delta = float(np.log(q[order[0]]) - np.log(q[order[1]]))
        worst = max(worst, Delta - R)
    assert tested > 100, tested
    assert worst <= TOL, (
        f"found a pinned pair with Delta > R by {worst:.3e}; either P8's "
        f"proof is wrong or the construction no longer pins the pair")


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


#: The two P4 counts PRINTED IN THE MANUSCRIPT, pinned.
#:
#: This is not a numerical claim -- both counts are artefacts of one seed and
#: carry no meaning beyond "sufficient, not necessary". It is a STABILITY
#: check. Adding the P7 block to proof_audit.py drew from the shared generator
#: and moved these from 2721/6877 to 2692/7031: a published number changed
#: because an unrelated proposition was added. The script now gives each such
#: block its own stream; this test is what makes a future regression loud
#: instead of silent. If it fails, either restore stream independence or
#: update the manuscript, FORMAL_CORE.md 7 and 10, and PROSE_NUMERIC_BINDINGS
#: PB-17/PB-18 together -- never the artifact alone.
P4_PUBLISHED = {"condition_Delta_gt_R_met": 2721,
                "argmax_moved_when_condition_violated": 6877}


def test_the_P4_counts_the_manuscript_prints_are_stream_stable():
    path = os.path.join(MP, "results", "proof_audit.json")
    if not os.path.exists(path):
        pytest.skip("proof_audit.json not generated")
    p4 = json.load(open(path, encoding="utf-8"))["numeric"]["P4"]
    got = {k: p4[k] for k in P4_PUBLISHED}
    assert got == P4_PUBLISHED, (
        f"the audit's P4 counts moved: published {P4_PUBLISHED}, artifact "
        f"{got}. A proposition added upstream of the P4 block probably drew "
        f"from the shared generator. See the note above this test.")


def test_P8_is_reported_as_a_bound_that_holds_with_no_room():
    """The negative result about P4 must be present and must not have been
    quietly softened into a bound with slack."""
    path = os.path.join(MP, "results", "proof_audit.json")
    if not os.path.exists(path):
        pytest.skip("proof_audit.json not generated")
    num = json.load(open(path, encoding="utf-8"))["numeric"]
    key = "P8_pinned_pair_margin_never_exceeds_R"
    assert num["bound_violations_beyond_1e-9"][key] == 0
    assert num["bound_max_slack"][key] < 1e-9
    assert num["P8"]["pinned_pairs_that_were_the_top_two_under_q"] > 0, (
        "P8 was never evaluated on a single instance, so its 0 violations "
        "mean nothing")


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
                "P6a", "P6b", "P7", "P7b", "P7c", "P8"):
        assert f"| {pid} |" in text, pid


#: The literature search the brief requires "at minimum". Coverage of this
#: list is checkable; VERIFICATION of the rows is not, and the two must not be
#: confused -- every row is WEB_SEARCH_ONLY and the matrix says so.
REQUIRED_PRIOR_ART_TOPICS = (
    "unreliable observations",
    "loss of observations",
    "robust diagnosability",
    "partial observations",
    "maximum-likelihood diagnosis under unreliable observations",
    "missing data / selection mechanisms",
    "likelihood reweighting",
    "bounded likelihood ratios",
    "posterior sensitivity",
    "runtime validity gating",
)


def _prior_art_rows():
    import csv as _csv
    path = os.path.join(MP, "PRIOR_ART_MATRIX.csv")
    return list(_csv.DictReader(open(path, encoding="utf-8")))


def test_every_required_search_topic_has_at_least_one_row():
    """C6 asks for a search covering these at minimum. A topic with no row is
    a topic nobody looked at, and 'I did not find it' is not the same as
    'nothing exists' -- so an EMPTY row is not an acceptable substitute
    either. Both states are failures here."""
    rows = _prior_art_rows()
    covered = {r["topic"].strip() for r in rows}
    missing = [t for t in REQUIRED_PRIOR_ART_TOPICS if t not in covered]
    assert not missing, (
        f"prior-art topics with no row: {missing}. Either search them and add "
        f"a row, or remove them from REQUIRED_PRIOR_ART_TOPICS with a reason.")


def test_every_prior_art_row_is_complete():
    for r in _prior_art_rows():
        for field in ("topic", "reference", "result", "assumptions",
                      "closest_csia_statement", "subsumes", "difference",
                      "claim_consequence", "verification_route", "status"):
            assert (r.get(field) or "").strip(), \
                f"{r.get('reference', '?')[:50]}: {field} is empty"


def test_an_unsuccessful_search_is_not_recorded_as_a_gap():
    """The one way this matrix could lie: reporting 'not found' as 'nothing
    exists'. Any row whose status says the search came up short must say so
    in its own claim_consequence rather than asserting a gap."""
    weak = {"NOT_FOUND_NEEDS_HUMAN", "TOPIC_SEARCHED_NO_CLOSE_MATCH",
            "NOT_READ_HIGH_PRIORITY"}
    for r in _prior_art_rows():
        if r["status"] not in weak:
            continue
        text = (r["claim_consequence"] + " " + r["difference"]).lower()
        assert any(w in text for w in
                   ("not established", "do not cite", "weak evidence",
                    "must not be", "has not been read", "never as establishing",
                    "before submission")), (
            f"{r['reference'][:60]}: status {r['status']} but the row does "
            f"not say what may NOT be concluded from an unsuccessful search")


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
