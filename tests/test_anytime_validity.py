"""T-1 falsification suite (CSIA-ACEG).

Purpose: these tests must be able to FALSIFY an invalid evidence
construction. Two of them assert that known-invalid constructions VIOLATE the
bound — if those ever pass in the "safe" direction, the suite has lost its
falsification power and must be treated as broken.
"""

import json
import math
import os

import numpy as np
import pytest
from scipy import stats

from csia.evidence import (BlockwiseEProcess, LikelihoodRatioEProcess,
                           NaivePerTickEProcess, ar1_block_mean_p, calibrate)

ROOT = os.path.join(os.path.dirname(__file__), "..")
RESULT = os.path.join(ROOT, "experiments", "results",
                      "anytime_validity_v1.json")
THR, ALPHA = 20.0, 0.05


def ar1(rng, n, t, rho):
    x = np.empty((n, t))
    s = rng.standard_normal(n)
    c = math.sqrt(1 - rho * rho)
    for k in range(t):
        s = rho * s + c * rng.standard_normal(n)
        x[:, k] = s
    return x


def crossing_rate(paths_fn, n=400, t=1000, seed=7):
    rng = np.random.default_rng(seed)
    crossed = 0
    for x in paths_fn(rng, n, t):
        crossed += bool(x)
    return crossed / n


# --- calibrator ---------------------------------------------------------------

def test_calibrator_is_admissible_in_expectation():
    rng = np.random.default_rng(0)
    p = rng.random(2_000_000)
    e = np.array([calibrate(v) for v in p[:20000]])       # class path
    assert e.mean() < 1.05                                 # ~1, sampling noise
    # vectorized closed form on the big sample
    ev = 0.5 * np.power(np.clip(p, 1e-8, 1.0), -0.5)
    assert ev.mean() == pytest.approx(1.0, abs=0.01)


def test_clamp_is_conservative_never_anticonservative():
    assert calibrate(0.0) == calibrate(1e-8)      # finite
    assert calibrate(1e-12) <= 0.5 * (1e-8) ** (-0.5) + 1e-9
    with pytest.raises(ValueError):
        calibrate(0.5, kappa=1.5)


# --- known-invalid control: the suite MUST detect the violation ---------------

def test_FALSIFICATION_POWER_naive_ar1_violates():
    """If this test fails, the suite can no longer detect invalid
    constructions — treat that as a broken suite, not a fixed process."""
    rng = np.random.default_rng(11)
    x = ar1(rng, 400, 1000, 0.94)
    crossed = 0
    for i in range(x.shape[0]):
        ep = NaivePerTickEProcess()
        for v in x[i]:
            ep.update(float(stats.norm.sf(v)), thresholds=(THR,))
        crossed += ep.ever_crossed.get(THR, False)
    rate = crossed / x.shape[0]
    assert rate > 0.20, f"naive construction no longer violates ({rate})"


def test_iid_null_respects_ville():
    rng = np.random.default_rng(12)
    x = rng.standard_normal((400, 1000))
    crossed = 0
    for i in range(x.shape[0]):
        ep = NaivePerTickEProcess()
        for v in x[i]:
            ep.update(float(stats.norm.sf(v)), thresholds=(THR,))
        crossed += ep.ever_crossed.get(THR, False)
    rate = crossed / 400
    se = math.sqrt(ALPHA * (1 - ALPHA) / 400)
    assert rate <= ALPHA + 3 * se


# --- blockwise restores the bound in the declared domain ----------------------

def test_blockwise_L50_restores_bound_at_rho094():
    rng = np.random.default_rng(13)
    x = ar1(rng, 400, 1500, 0.94)
    crossed = 0
    for i in range(x.shape[0]):
        ep = BlockwiseEProcess(50, lambda b: ar1_block_mean_p(b, 0.94))
        for v in x[i]:
            ep.update(v, thresholds=(THR,))
        crossed += ep.ever_crossed.get(THR, False)
    rate = crossed / 400
    se = math.sqrt(max(rate * (1 - rate), 1e-6) / 400)
    assert rate <= ALPHA + 3 * max(se, 0.011)


def test_blockwise_evidence_constant_within_block():
    ep = BlockwiseEProcess(10, lambda b: 0.5)
    vals = [ep.update(0.0) for _ in range(9)]
    assert all(v == 1.0 for v in vals)          # no block closed yet
    assert ep.update(0.0) != 1.0                # block closes on the 10th


def test_blockwise_detects_mean_shift():
    """Power sanity: validity must not have destroyed detection."""
    rng = np.random.default_rng(14)
    x = ar1(rng, 100, 1500, 0.94) + 1.0         # persistent 1-sigma shift
    detected = 0
    for i in range(x.shape[0]):
        ep = BlockwiseEProcess(50, lambda b: ar1_block_mean_p(b, 0.94))
        for v in x[i]:
            ep.update(v, thresholds=(THR,))
        detected += ep.ever_crossed.get(THR, False)
    assert detected / 100 > 0.95


# --- likelihood-ratio variant -------------------------------------------------

def test_lr_correct_null_is_a_martingale_and_respects_ville():
    rng = np.random.default_rng(15)
    x = ar1(rng, 400, 1000, 0.94)
    finals, crossed = [], 0
    for i in range(x.shape[0]):
        ep = LikelihoodRatioEProcess(rho0=0.94, delta=1.0)
        ep._prev = float(x[i, 0])               # condition on first obs
        for v in x[i, 1:]:
            ep.update(float(v), thresholds=(THR,))
        finals.append(min(ep.e, 50.0))
        crossed += ep.ever_crossed.get(THR, False)
    assert crossed / 400 <= ALPHA + 0.033
    assert np.mean(finals) < 2.5                # martingale mean ~<=1 (capped)


def test_FALSIFICATION_POWER_lr_misspecified_violates():
    rng = np.random.default_rng(16)
    x = ar1(rng, 300, 1000, 0.94)
    crossed = 0
    for i in range(x.shape[0]):
        ep = LikelihoodRatioEProcess(rho0=0.0, delta=1.0)   # iid assumed
        ep._prev = float(x[i, 0])
        for v in x[i, 1:]:
            ep.update(float(v), thresholds=(THR,))
        crossed += ep.ever_crossed.get(THR, False)
    assert crossed / 300 > 0.20


def test_lr_restart_counterexample_is_pinned():
    """Scoring a stationary first observation against the conditional density
    (prev=0, var 1-rho^2) is INVALID — the bug this suite caught. One update
    must show a hugely inflated e-value in expectation."""
    rng = np.random.default_rng(17)
    x0 = rng.standard_normal(4000)              # stationary start, var 1
    ep_vals = []
    for v in x0:
        ep = LikelihoodRatioEProcess(rho0=0.94, delta=1.0)  # prev=0 default
        ep_vals.append(ep.update(float(v)))
    assert np.mean(ep_vals) > 100.0             # wildly > 1: invalid restart


# --- committed results integrity ---------------------------------------------

@pytest.mark.skipif(not os.path.exists(RESULT), reason="matrix not generated")
class TestCommittedMatrix:
    def load(self):
        with open(RESULT) as fh:
            return json.load(fh)["payload"]

    def test_selection_and_evaluation_seeds_differ(self):
        p = self.load()["protocol"]
        assert p["selection_seed_base"] != p["evaluation_seed_base"]

    def test_selected_block_length_valid_in_declared_domain(self):
        d = self.load()
        L = d["selected_block_len"]
        for rho in ("0.5", "0.94"):
            cell = d["cells"][f"eval/blockwise_L{L}/ar1_{rho}"]
            assert not cell["violates"], cell

    def test_known_invalid_cells_recorded_as_violations(self):
        cells = self.load()["cells"]
        for name in ("eval/naive/ar1_0.94_KNOWN_INVALID",
                     "eval/lr_MISSPECIFIED_iid_assumed/ar1_0.94"):
            assert cells[name]["violates"], name

    def test_domain_boundary_counterexample_preserved(self):
        d = self.load()
        L = d["selected_block_len"]
        assert d["cells"][f"eval/blockwise_L{L}/ar1_0.99"]["violates"]
        assert "0.99" in d["validity_domain"]["boundary_counterexample"]

    def test_context_ignorance_counterexample_preserved(self):
        d = self.load()
        L = d["selected_block_len"]
        assert d["cells"][
            f"eval/blockwise_L{L}/regime_IGNORED_context"]["violates"]
        assert not d["cells"][
            f"eval/blockwise_L{L}/regime_oracle_context"]["violates"]
