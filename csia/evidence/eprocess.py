"""Anytime-valid evidence processes (CSIA-ACEG, theorem T-1).

Research implementation — NOT flight software, NOT part of the v1 runtime.

Three constructions are implemented so the falsification suite can compare a
known-invalid one against two candidate-valid ones on identical inputs:

  NaivePerTickEProcess   the slice-ACEG-0 proposal applied per tick. KNOWN
                         INVALID under autocorrelated residuals (measured 9x
                         boundary violation); retained deliberately so the
                         test suite proves it can falsify a bad construction.

  BlockwiseEProcess      T-1 candidate. One e-value per block of length L,
                         computed from a block-level statistic. Valid GIVEN
                         block-level conditional super-uniformity (assumption
                         A3 in docs/math/T1_BLOCKWISE_EPROCESS.md) — which for
                         mixing processes holds approximately as L exceeds the
                         decorrelation time. Status: PROVISIONAL.

  LikelihoodRatioEProcess  exact conditional likelihood ratio against a
                         parametric null. E[e_t | F_{t-1}] = 1 identically
                         when the null conditional density is correct, so the
                         product is a nonnegative martingale and Ville's
                         inequality holds EXACTLY. Status: PROVED under
                         correct null specification; REFUTED (by measured
                         counterexample) under misspecification.

Design constraints honoured for an eventual embedded port: bounded memory
(one block buffer / one lag state), no allocation growth with time,
deterministic arithmetic order.
"""

import math
from dataclasses import dataclass, field

#: Default calibrator exponent, pre-registered in the ACEG critique.
DEFAULT_KAPPA = 0.5
#: Clamp for the p -> e calibrator. kappa*p^(kappa-1) diverges as p -> 0 for
#: kappa < 1; clamping p at P_MIN keeps arithmetic finite. Because the
#: calibrator is decreasing in p and clamping only RAISES p, the clamped
#: calibrator is dominated by the exact one, so it remains an e-value
#: (conservative). Proof: Lemma 1 in T1_BLOCKWISE_EPROCESS.md.
P_MIN = 1e-8
#: Cap on the running product to keep floats finite. Capping only LOWERS
#: evidence, so it cannot create a false alert; it can only delay a true one.
E_MAX = 1e12


def calibrate(p: float, kappa: float = DEFAULT_KAPPA,
              p_min: float = P_MIN) -> float:
    """Admissible p-to-e calibrator  e = kappa * p**(kappa-1),  0 < kappa < 1.

    integral_0^1 kappa p^(kappa-1) dp = 1 exactly, so for any super-uniform p,
    E[e] <= 1 (Vovk & Wang 2021). The clamp at p_min is conservative.
    """
    if not (0.0 < kappa < 1.0):
        raise ValueError("kappa must be in (0, 1)")
    p = min(max(p, p_min), 1.0)
    return kappa * p ** (kappa - 1.0)


@dataclass
class EProcessState:
    """Common running state. E is valid at every time (anytime property)."""
    log_e: float = 0.0
    n_updates: int = 0
    ever_crossed: dict = field(default_factory=dict)   # threshold -> bool

    @property
    def e(self) -> float:
        return min(math.exp(self.log_e), E_MAX)

    def _accumulate(self, e_value: float, thresholds=(20.0,)):
        # e_value must be > 0; log-domain product avoids overflow/underflow.
        self.log_e += math.log(max(e_value, 1e-300))
        self.log_e = min(self.log_e, math.log(E_MAX))
        self.n_updates += 1
        for thr in thresholds:
            if self.e >= thr:
                self.ever_crossed[thr] = True


class NaivePerTickEProcess(EProcessState):
    """The original proposal, per tick. RETAINED AS A KNOWN-INVALID CONTROL.

    Multiplying per-tick calibrated e-values requires each p_t to be
    super-uniform CONDITIONALLY on F_{t-1}. Marginal uniformity is not
    enough: under AR(1)-like dependence (rho ~ 0.94, CSIA's smoothed
    residual regime) the measured boundary-crossing rate was 0.454 against
    an advertised bound of 0.05. Do not deploy. The falsification suite
    asserts that this construction VIOLATES the bound — if that test ever
    fails, the suite has lost its power to detect invalid implementations.
    """

    def __init__(self, kappa: float = DEFAULT_KAPPA):
        super().__init__()
        self.kappa = kappa

    def update(self, p_tick: float, thresholds=(20.0,)) -> float:
        self._accumulate(calibrate(p_tick, self.kappa), thresholds)
        return self.e


class BlockwiseEProcess(EProcessState):
    """T-1 candidate: one e-value per length-L block.

    The caller supplies ``block_p_fn(block_scores) -> p``, the block-level
    p-value. Validity requires (A3): p_j is super-uniform conditionally on
    all previous blocks. For phi-mixing residuals this holds approximately
    once L exceeds the decorrelation time; the approximation error is what
    the falsification sweep measures as a function of L.

    Between block boundaries E is simply held constant — holding evidence
    fixed cannot increase crossing probability, so the anytime property is
    preserved at tick resolution.

    Bounded memory: exactly one block buffer of length L.
    """

    def __init__(self, block_len: int, block_p_fn,
                 kappa: float = DEFAULT_KAPPA):
        super().__init__()
        if block_len < 1:
            raise ValueError("block_len must be >= 1")
        self.block_len = block_len
        self.block_p_fn = block_p_fn
        self.kappa = kappa
        self._buf = []

    def update(self, score: float, thresholds=(20.0,)) -> float:
        self._buf.append(float(score))
        if len(self._buf) >= self.block_len:
            p = float(self.block_p_fn(self._buf))
            self._accumulate(calibrate(p, self.kappa), thresholds)
            self._buf.clear()
        return self.e


class LikelihoodRatioEProcess(EProcessState):
    """Exact conditional likelihood-ratio e-process for a Gaussian AR(1) null.

    Null H0:  x_t | x_{t-1} ~ N(rho0 * x_{t-1}, 1 - rho0^2)   (unit marginal var)
    Alt  H1:  x_t | x_{t-1} ~ N(rho0 * x_{t-1} + delta, 1 - rho0^2)

    e_t = q1(x_t | x_{t-1}) / q0(x_t | x_{t-1}).

    When rho0 matches the data-generating process, E[e_t | F_{t-1}] = 1
    identically (the integral of a density ratio against the true conditional
    density), so E_t is a nonnegative martingale with E[E_t] = 1 and Ville's
    inequality is EXACT — no mixing or block assumption needed. When rho0 is
    misspecified this fails, and the suite measures the resulting violation.
    """

    def __init__(self, rho0: float, delta: float = 1.0):
        super().__init__()
        if not (-1.0 < rho0 < 1.0):
            raise ValueError("rho0 must be in (-1, 1)")
        self.rho0 = rho0
        self.delta = delta
        self._prev = 0.0
        self._var = 1.0 - rho0 * rho0

    def update(self, x: float, thresholds=(20.0,)) -> float:
        mu0 = self.rho0 * self._prev
        # log LR of N(mu0+delta, var) vs N(mu0, var) at x
        log_e = (self.delta * (x - mu0) - 0.5 * self.delta ** 2) / self._var
        self._prev = float(x)
        self._accumulate(math.exp(min(log_e, 700.0)), thresholds)
        return self.e


def ar1_block_mean_p(block, rho: float, sigma: float = 1.0) -> float:
    """One-sided p-value for the mean of a length-L block of a stationary
    Gaussian AR(1) process with known rho and marginal sd sigma.

    Var(mean) = sigma^2/L * (1 + 2 * sum_{k=1}^{L-1} (1 - k/L) rho^k).
    Marginally exact; the CONDITIONAL validity across successive blocks is
    the T-1 assumption under test.
    """
    L = len(block)
    m = sum(block) / L
    acc = sum((1.0 - k / L) * rho ** k for k in range(1, L))
    var = sigma * sigma / L * (1.0 + 2.0 * acc)
    z = m / math.sqrt(var)
    # one-sided upper-tail p via the complementary error function
    return 0.5 * math.erfc(z / math.sqrt(2.0))
