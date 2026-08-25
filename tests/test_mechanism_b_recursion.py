"""The Mechanism B reconstruction and closed form, tested against the source.

A reconstruction tool that is wrong produces a confident, plausible, wrong
answer -- and Mechanism B's whole claim rests on the reconstruction being an
independent re-derivation rather than a paraphrase of the runtime. So the two
pieces of arithmetic get their own positive controls:

  * `reconstruct()` is run against the FROZEN `TrustCore` itself, driven with
    synthetic inputs, and must reproduce its trust trajectory. Nothing here
    mocks the engine: the engine is the oracle.
  * `closed_form_N()` is checked against a direct numerical iteration of the
    same constant-coefficient recursion, and against the W-4 figure published
    in the verdict document.
"""

import math
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "simulation"))

from csia.trust_engine.engine import EngineConfig, TrustCore   # noqa: E402
from mechanism_b_report import (                               # noqa: E402
    THRESHOLD, closed_form_N, median, reconstruct, rho_of)

CFG = EngineConfig()
CFG_DICT = {"w_nbr": CFG.w_nbr, "w_phys": CFG.w_phys, "w_temp": CFG.w_temp,
            "w_stat": CFG.w_stat, "rho_max": CFG.rho_max,
            "rho_min": CFG.rho_min, "alpha0": CFG.alpha0,
            "beta0": CFG.beta0}


def _steps_from_core(lams, node="mag", fresh_pattern=None):
    """Drive the real TrustCore and emit trace rows in the runner's format."""
    core = TrustCore([node], CFG)
    steps = []
    for k, (lam_p, lam_t) in enumerate(lams):
        fresh = {node: True if fresh_pattern is None else fresh_pattern[k]}
        res = core.step(edges={}, phys={node: (lam_p, 1.0)},
                        hist={node: lam_t}, var_ratio={node: 1.0},
                        fresh=fresh)
        r = res[node]
        steps.append({
            "record": "step", "t": round(0.04 * k, 6),
            "trust": {node: r["trust"]},
            "evidence": {node: r["evidence"]},
            "components": {node: {c: r[c] for c in
                                  ("nbr", "phys", "temp", "stat")}},
            "fresh": {node: fresh[node]},
            "S": {node: core.alpha[node] + core.beta[node]},
        })
    return steps


class TestReconstructionAgainstTheEngine:
    """The engine is the oracle; the reconstruction must reproduce it."""

    def test_reproduces_a_healthy_trajectory(self):
        steps = _steps_from_core([(1.0, 1.0)] * 200)
        rows = reconstruct(steps, "mag", CFG_DICT)
        assert len(rows) == 200
        worst = max(abs(r["T_hat"] - r["T_runtime"]) for r in rows)
        assert worst < 1e-12, worst

    def test_reproduces_a_step_collapse(self):
        """The Mechanism B shape: healthy, then evidence collapses."""
        steps = _steps_from_core([(1.0, 1.0)] * 100 + [(60.0, 1.0)] * 300)
        rows = reconstruct(steps, "mag", CFG_DICT)
        worst = max(abs(r["T_hat"] - r["T_runtime"]) for r in rows)
        assert worst < 1e-12, worst
        # and the trajectory must actually be the one the mechanism describes
        assert rows[99]["T_runtime"] > 0.9
        assert rows[-1]["T_runtime"] < 0.6

    def test_S_is_reproduced_too(self):
        steps = _steps_from_core([(1.0, 1.0)] * 50 + [(40.0, 1.0)] * 150)
        rows = reconstruct(steps, "mag", CFG_DICT)
        worst = max(abs(r["S_hat"] - r["S_runtime"]) for r in rows)
        assert worst < 1e-9, worst

    # The dropout is placed in the MIDDLE OF THE DESCENT on purpose. Put it
    # after the trajectory has already reached its asymptote and the gate
    # costs 0.0097 -- under E1's tolerance -- so the test would pass whether
    # or not the tool honoured the gate. It has to bite where the trust is
    # still moving, which is exactly where PX4's intermittent mag freshness
    # bites in PX4_CLEAN_ESCALATION_DIAGNOSIS.md.
    _LAMS = [(1.0, 1.0)] * 100 + [(60.0, 1.0)] * 200
    _PATTERN = [True] * 120 + [False] * 50 + [True] * 130

    def test_honours_the_update_gate(self):
        """A non-fresh node does not update, and the reconstruction knows."""
        steps = _steps_from_core(self._LAMS, fresh_pattern=self._PATTERN)
        rows = reconstruct(steps, "mag", CFG_DICT)
        worst = max(abs(r["T_hat"] - r["T_runtime"]) for r in rows)
        assert worst < 1e-12, worst
        # trust is frozen across the non-fresh stretch
        assert rows[125]["T_runtime"] == pytest.approx(rows[165]["T_runtime"])
        assert not any(r["updated"] for r in rows[120:170])

    def test_ignoring_the_gate_would_be_detected(self):
        """The gate matters: a reconstruction that skipped it fails E1.

        Without this the previous test could pass for the wrong reason -- a
        stretch where the gate happens not to change anything.
        """
        steps = _steps_from_core(self._LAMS, fresh_pattern=self._PATTERN)
        rows = reconstruct(steps, "mag", CFG_DICT)
        for st in steps:                       # pretend everything was fresh
            st["fresh"]["mag"] = True
        naive = reconstruct(steps, "mag", CFG_DICT)
        worst = max(abs(a["T_hat"] - b["T_runtime"])
                    for a, b in zip(naive, rows))
        assert worst > 0.02, worst


class TestRhoRederivation:
    """rho is re-derived from components, never read from the runtime."""

    def test_matches_the_source_formula(self):
        comps = {"nbr": 0.9, "phys": 0.2, "temp": None, "stat": 0.5}
        rho, n = rho_of(comps, CFG.rho_max, CFG.rho_min)
        d = 0.9 - 0.2
        assert n == 3
        assert rho == pytest.approx(
            CFG.rho_max - (CFG.rho_max - CFG.rho_min) * d)

    def test_single_component_has_zero_spread(self):
        rho, n = rho_of({"nbr": None, "phys": 0.3, "temp": None,
                         "stat": None}, CFG.rho_max, CFG.rho_min)
        assert n == 1 and rho == pytest.approx(CFG.rho_max)

    def test_no_evidence_reports_zero_available(self):
        rho, n = rho_of({c: None for c in ("nbr", "phys", "temp", "stat")},
                        CFG.rho_max, CFG.rho_min)
        assert n == 0


class TestClosedForm:
    """W-4's closed form, against a direct iteration of the same recursion."""

    @staticmethod
    def _iterate(S0, T0, e_f, rho, thr=THRESHOLD, limit=100000):
        S, T = S0, T0
        for n in range(1, limit + 1):
            S_prev, T_prev = S, T
            S = rho * S_prev + 1.0
            T = (rho * S_prev * T_prev + e_f) / S
            if T <= thr:
                return n
        return None

    @pytest.mark.parametrize("S0,T0,e_f,rho", [
        (500.0, 0.97, 0.35, 0.95),
        (10.0, 0.80, 0.10, 0.99),
        (250.0, 0.92, 0.50, 0.98),
        (60.0, 0.99, 0.05, 0.96),
    ])
    def test_agrees_with_direct_iteration(self, S0, T0, e_f, rho):
        N, note = closed_form_N(S0, T0, e_f, rho)
        assert N is not None, note
        assert self._iterate(S0, T0, e_f, rho) == pytest.approx(
            math.ceil(N), abs=1)

    def test_no_crossing_when_evidence_stays_above_threshold(self):
        N, note = closed_form_N(500.0, 0.97, 0.70, 0.95)
        assert N is None and "no crossing is predicted" in note
        assert self._iterate(500.0, 0.97, 0.70, 0.95, limit=5000) is None

    def test_already_below_threshold_is_zero_not_none(self):
        N, note = closed_form_N(500.0, 0.55, 0.20, 0.95)
        assert N == 0.0 and "already" in note

    def test_banked_evidence_delays_the_crossing(self):
        """This IS W-4: a larger S0 means a later crossing, all else equal.

        The verdict document quotes `N* = 93.31` but not the S0/T0/e_f/rho
        that produced it, so that number cannot be re-derived here and this
        test does not pretend to. What it checks is the property the number
        was evidence FOR -- that the delay is set by banked evidence.
        """
        args = dict(T0=0.95, e_f=0.20, rho=0.99)
        ns = [closed_form_N(S0=s, **args)[0] for s in (10, 50, 100, 300, 800)]
        assert all(n is not None for n in ns)
        assert ns == sorted(ns), ns
        # and the effect is large, not a rounding artefact
        assert ns[-1] > 3 * ns[0]
        # every one of them agrees with a direct iteration of the recursion
        for S0, n in zip((10, 50, 100, 300, 800), ns):
            assert self._iterate(S0, 0.95, 0.20, 0.99) == pytest.approx(
                math.ceil(n), abs=1)

    def test_a_93_tick_crossing_is_reproducible_arithmetic(self):
        """A crossing on W-4's stated ~93-tick scale, checked both ways."""
        S0, T0, rho = 100.0, 0.95, 0.99
        lo, hi = 0.0, THRESHOLD - 1e-9      # N increases with e_f
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            N, _note = closed_form_N(S0, T0, mid, rho)
            if N is None or N > 93.31:
                hi = mid
            else:
                lo = mid
        N, _ = closed_form_N(S0, T0, lo, rho)
        assert N == pytest.approx(93.31, abs=0.05)
        assert self._iterate(S0, T0, lo, rho) == pytest.approx(94, abs=1)


class TestMedian:
    def test_odd_and_even(self):
        assert median([3, 1, 2]) == 2
        assert median([4, 1, 3, 2]) == 2.5

    def test_empty_is_nan_not_a_crash(self):
        assert math.isnan(median([]))


# ---------------------------------------------------------------------------
# The GPS-glitch campaign reconstructs from the MEASURED S0/T0 at onset rather
# than from the Beta prior at t=0, because preregistration section 5 says to.
# That is a different function with a different failure mode -- it can be
# handed an S0 that is not the runtime's -- so it gets its own control.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(ROOT, "tools", "simulation"))
from current_stack_replication import (                     # noqa: E402
    lambda_from_c, prepare, reconstruct_from)


class TestReconstructFromMeasuredState:

    def test_tracks_the_engine_from_a_mid_flight_start(self):
        steps = _steps_from_core([(1.0, 1.0)] * 300 + [(40.0, 1.0)] * 400,
                                 node="gps")
        rows = prepare(steps, CFG_DICT)
        rec = reconstruct_from(rows, 300, CFG_DICT)
        worst = max(abs(r["T_hat"] - r["T_runtime"]) for r in rec)
        # the preregistered tolerance is 1e-6; the arithmetic is far inside it
        assert worst < 1e-9, worst
        assert rec[0]["T_hat"] == rows[300]["T_runtime"]

    def test_a_wrong_S0_is_detected(self):
        """Guards the guard: if S0 were mis-read the error must exceed 1e-6."""
        steps = _steps_from_core([(1.0, 1.0)] * 300 + [(40.0, 1.0)] * 400,
                                 node="gps")
        rows = prepare(steps, CFG_DICT)
        rows[300] = dict(rows[300], S_runtime=rows[300]["S_runtime"] * 0.5)
        rec = reconstruct_from(rows, 300, CFG_DICT)
        worst = max(abs(r["T_hat"] - r["T_runtime"]) for r in rec)
        assert worst > 1e-6, worst

    def test_carries_S_forward_when_a_step_has_none(self):
        steps = _steps_from_core([(1.0, 1.0)] * 20, node="gps")
        steps[5]["S"] = None
        rows = prepare(steps, CFG_DICT)
        assert rows[5]["S_runtime"] == pytest.approx(rows[4]["S_runtime"])


class TestLambdaInversion:

    def test_inverts_the_source_consistency_map(self):
        for lam in (1.5, 3.0, 12.0, 40.0):
            c = math.exp(-0.5 * max(0.0, lam - 1.0))
            assert lambda_from_c(c) == pytest.approx(lam, rel=1e-9)

    def test_saturation_returns_none_rather_than_a_made_up_number(self):
        # c == 1 for EVERY lam <= 1, so no single lam can be recovered
        assert lambda_from_c(1.0) is None
        assert lambda_from_c(None) is None
