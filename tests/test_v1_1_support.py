"""Phase 2 gate: support-aware diagnosis.

The obligations, from the Phase 2/3 brief section 13:

  A. production posterior unchanged
  B. support state reproducible deterministically
  C. no label-tuned threshold
  D. the fix-loss case receives an honest support description
  E. clean nominal cases stay evidence-backed when evidence truly exists
  F. ambiguity is based on evidence structure, not score margin

Nothing here modifies `csia/diagnosis`, which is FROZEN.
"""

from __future__ import annotations

import importlib.util
import json
import os

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")
SUP = os.path.join(ENG, "support")


def _load(name, fn):
    """Load by path -- tests/test_ci_env.py scans import statements and a bare
    local import inside an engineering package looks like a missing dep."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(SUP, fn))
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mods():
    return _load("_v11_decompose", "decompose.py"), \
        _load("_v11_support", "support.py")


@pytest.fixture(scope="module")
def dropout():
    from csia.scenarios import run_scenario
    return run_scenario("gps_dropout")


@pytest.fixture(scope="module")
def clean():
    from csia.scenarios import run_scenario
    return run_scenario("clean")


# ------------------------------------------------------- A: production intact
def test_the_decomposition_reconstructs_the_production_posterior(mods, dropout):
    """The first obligation. If this fails, nothing downstream means
    anything, because the analysis would be describing a different model."""
    D, _S = mods
    _t, _f, td, _h, diag = dropout
    dec = D.decompose(td)
    err = float(np.abs(dec.posterior - diag.posterior).max())
    assert err < 1e-12, err
    # and each row is still a distribution
    assert np.allclose(dec.posterior.sum(axis=1), 1.0)


def test_the_per_term_contributions_sum_to_the_core_log_likelihood(mods, dropout):
    """Section 2 of the spec: contribution_j[h] is the exact summand."""
    D, _S = mods
    _t, _f, td, _h, _d = dropout
    dec = D.decompose(td)
    assert np.allclose(dec.contribution.sum(axis=1), dec.ll, atol=0, rtol=0)


def test_the_analysis_does_not_mutate_the_production_diagnosis(mods, dropout):
    """Obligation A. Prior-neutral scoring must not leak into production."""
    D, S = mods
    from csia.diagnosis.bayes import CausalDiagnosis
    _t, _f, td, _h, _d = dropout
    before = CausalDiagnosis().run(td).posterior.copy()
    dec, rows = S.support_series(td, stride=200)
    _ = [r.prior_sensitive for r in rows]          # forces the neutral score
    after = CausalDiagnosis().run(td).posterior
    assert np.array_equal(before, after)
    assert np.abs(dec.posterior - after).max() < 1e-12


def test_the_frozen_diagnosis_core_is_untouched():
    import subprocess
    r = subprocess.run(["git", "diff", "--stat", "csia-v1.0-research-final",
                        "--", "csia/diagnosis", "csia/trust_engine"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("frozen tag unavailable")
    assert r.stdout.strip() == "", r.stdout


# ---------------------------------------------------------- B: deterministic
def test_support_analysis_is_deterministic(mods, dropout):
    D, S = mods
    _t, _f, td, _h, _d = dropout
    a = [r.row() for r in S.support_series(td, stride=100)[1]]
    b = [r.row() for r in S.support_series(td, stride=100)[1]]
    assert a == b


# ------------------------------------------------------- C: no tuned threshold
def test_the_numerical_tolerance_is_not_a_decision_threshold(mods, dropout):
    """Spec section 4: TAU_NUM exists for float comparison. If the verdict
    moved when it moved, it would be a decision threshold instead."""
    D, S = mods
    _t, _f, td, _h, _d = dropout
    base = None
    for tau in (1e-15, 1e-12, 1e-9):
        rows = S.support_series(td, stride=50, tau=tau)[1]
        got = [(r.k, r.support_state, tuple(r.non_identifiable_against))
               for r in rows]
        if base is None:
            base = got
        assert got == base, f"verdict moved at tau={tau}"


def test_the_support_label_is_a_total_function_of_three_booleans(mods):
    """Spec section 8. No fourth input can sneak in."""
    _D, S = mods
    seen = set()
    for ev in (False, True):
        for ident in (False, True):
            for ps in (False, True):
                lab = S._label(ev, ident, ps)
                assert lab in S.SUPPORT_STATES
                seen.add(lab)
    assert seen == set(S.SUPPORT_STATES)


def test_no_tuned_constant_lives_in_the_support_modules():
    """C. The only numbers permitted are the frozen core's own and the
    declared float tolerance."""
    import re
    for fn in ("decompose.py", "support.py"):
        src = open(os.path.join(SUP, fn), encoding="utf-8").read()
        # strip comments and docstrings before looking for magic numbers
        body = re.sub(r'"""[\s\S]*?"""', "", src)
        body = re.sub(r"#.*", "", body)
        for m in re.finditer(r"[<>]=?\s*0\.\d+", body):
            raise AssertionError(f"{fn}: threshold-shaped comparison "
                                 f"{m.group(0)!r}")


# --------------------------------------------------------------- D: fix loss
def test_the_fix_loss_case_is_reported_as_unsupported(mods, dropout):
    """Obligation D, and the point of Phase 2.

    nominal and gps_fault differ on exactly ONE feature, phys_gps
    (csia/diagnosis/bayes.py CAUSES), and its gate is multiplied by
    fresh['gps'] (csia/runtime/online.py:613). When the fix goes, the pair
    must collapse -- while the posterior stays high.
    """
    _D, S = mods
    _t, _f, td, _h, _d = dropout
    _dec, rows = S.support_series(td, stride=1)
    during = [r for r in rows if 25.0 <= r.t <= 33.0]
    assert during

    bad = [r for r in during if not r.leader_identifiable]
    assert len(bad) / len(during) > 0.5, (
        "the fix-loss window is still reported as identifiable")

    worst = max(bad, key=lambda r: r.posterior)
    assert worst.leader == "nominal"
    assert worst.posterior > 0.9, worst.posterior
    assert worst.support_state == "NON_IDENTIFIABLE"
    assert worst.ambiguity == "AMBIGUOUS"
    assert "gps_fault" in worst.non_identifiable_against
    assert worst.discriminating_terms["gps_fault"] == 0


def test_phys_gps_is_the_only_discriminator_of_nominal_from_gps_fault(mods,
                                                                     clean):
    """The mechanism claim, checked against the frozen CAUSES table rather
    than asserted in prose."""
    _D, S = mods
    from csia.diagnosis.bayes import CAUSES
    diff = set(CAUSES["nominal"]) ^ set(CAUSES["gps_fault"])
    assert diff == {"phys_gps"}, diff


def test_before_the_fault_the_leader_is_identifiable(mods, dropout):
    """The control for D: the collapse must be caused by the dropout, not be
    the permanent state of the scenario."""
    _D, S = mods
    _t, _f, td, _h, _d = dropout
    _dec, rows = S.support_series(td, stride=1)
    pre = [r for r in rows if 10.0 <= r.t < 25.0]
    assert pre
    assert all(r.leader_identifiable for r in pre)


# ------------------------------------------------------------- E: clean stays
def test_clean_flight_is_predominantly_evidence_backed(mods, clean):
    """Obligation E. If clean did not stay evidence-backed, the support test
    would be measuring something other than evidence."""
    _D, S = mods
    _t, _f, td, _h, _d = clean
    _dec, rows = S.support_series(td, stride=1)
    backed = sum(r.support_state == "EVIDENCE_BACKED" for r in rows)
    assert backed / len(rows) > 0.9, backed / len(rows)
    settled = [r for r in rows if r.t > 5.0]
    assert all(r.leader == "nominal" for r in settled)


# --------------------------------------------------------- F: structural only
def test_ambiguity_does_not_track_the_score_margin(mods, dropout):
    """Obligation F, and section 10: ambiguity must be structural. If it were
    a margin rule, margin alone would predict it."""
    _D, S = mods
    _t, _f, td, _h, _d = dropout
    _dec, rows = S.support_series(td, stride=1)
    amb = [r.score_margin for r in rows if r.ambiguity == "AMBIGUOUS"]
    uni = [r.score_margin for r in rows if r.ambiguity == "UNIQUE"]
    assert amb and uni
    # the ranges must overlap: some AMBIGUOUS ticks have a LARGER margin than
    # some UNIQUE ticks, which no margin threshold could reproduce
    assert max(amb) > min(uni), (max(amb), min(uni))


def test_a_collapsed_pair_really_has_identical_contributions(mods, dropout):
    """The definition, checked directly rather than through the label."""
    D, S = mods
    _t, _f, td, _h, _d = dropout
    dec, rows = S.support_series(td, stride=1)
    hit = next(r for r in rows if r.non_identifiable_against)
    other = r_other = hit.non_identifiable_against[0]
    d = dec.delta(hit.k, hit.leader, other)
    active = dec.active_mask(hit.k)
    assert np.abs(d[active]).max() <= D.TAU_NUM, (r_other,
                                                  np.abs(d[active]).max())


# ------------------------------------------------------------ the artifacts
def test_the_phase2_artifacts_exist_and_agree_with_the_code(mods, dropout):
    p = os.path.join(ENG, "FIXLOSS_SUPPORT_ANALYSIS.json")
    if not os.path.exists(p):
        pytest.skip("Phase 2 artifacts not built")
    d = json.load(open(p, encoding="utf-8"))
    assert d["production_posterior_unchanged"] is True
    assert d["reconstruction_max_abs_error"] < 1e-12
    w = d["worst_case_unsupported_leader"]
    assert w["support_state"] == "NON_IDENTIFIABLE"
    assert w["discriminating_terms_vs_gps_fault"] == 0
    assert w["posterior"] > 0.9

    s = json.load(open(os.path.join(ENG, "PHASE2_SUMMARY.json"),
                       encoding="utf-8"))
    assert s["max_reconstruction_abs_error"] < 1e-12
    # constants must be the frozen ones, not a local copy
    from csia.diagnosis.bayes import EPS, EVIDENCE_MULT, SMOOTH_ALPHA
    assert s["frozen_constants"]["EPS"] == EPS
    assert s["frozen_constants"]["EVIDENCE_MULT"] == EVIDENCE_MULT
    assert s["frozen_constants"]["SMOOTH_ALPHA"] == SMOOTH_ALPHA


def test_unknown_is_recorded_as_not_implemented():
    """Section 11: UNKNOWN must not be shipped to complete a feature list."""
    _D = None
    t = open(os.path.join(ENG, "UNKNOWN_MODEL_ADEQUACY_AUDIT.md"),
             encoding="utf-8").read()
    assert "NOT IMPLEMENTED — MODEL ADEQUACY TEST REQUIRED" in t
    from importlib.util import spec_from_file_location
    spec = spec_from_file_location("_s", os.path.join(SUP, "support.py"))
    assert spec is not None
    src = open(os.path.join(SUP, "support.py"), encoding="utf-8").read()
    assert "UNKNOWN" not in src.replace("UNKNOWN /", ""), (
        "an UNKNOWN state has appeared in the shipped support module")


def test_design_time_indistinguishable_pairs_are_reported(mods):
    """Spec section 10: a pair with identical LOW sets would be
    non-identifiable under every configuration and must not be confused with
    a runtime collapse."""
    _D, S = mods
    pairs = S.design_time_indistinguishable()
    assert pairs == [], pairs
