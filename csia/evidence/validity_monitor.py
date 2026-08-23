"""Validity-domain monitor for the anytime evidence process (Part 16).

The T-1 guarantee holds only inside a declared dependence/context domain.
This monitor decides, per evidence stream, whether the domain assumptions are
currently supported — and FAILS CLOSED: anything other than
VALIDITY_SUPPORTED suspends the anytime guarantee and prohibits
evidence-authorized action. Causal diagnosis may continue in research mode.

Estimated lag-one correlation ALONE does not establish validity (directive):
the monitor combines several indicators and treats disagreement as
uncertainty, not support.
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum


class Validity(str, Enum):
    SUPPORTED = "VALIDITY_SUPPORTED"
    UNCERTAIN = "VALIDITY_UNCERTAIN"
    VIOLATED = "VALIDITY_VIOLATED"


@dataclass(frozen=True)
class ValidityConfig:
    #: declared dependence domain from T-1 (block L=50 was validated for
    #: rho <= 0.94 EMPIRICALLY; this is the runtime enforcement of that domain)
    rho_max: float = 0.94
    #: above this, immediately VIOLATED (matches the measured counterexample)
    rho_hard: float = 0.97
    window: int = 400
    #: variance-ratio band vs calibration; outside -> distribution shift
    var_lo: float = 0.5
    var_hi: float = 2.0
    #: |kurtosis excess| beyond this suggests tails the calibration lacked
    kurt_max: float = 4.0
    #: restarts within one window beyond this -> UNCERTAIN (T-2 pending)
    max_restarts: int = 1


class ValidityMonitor:
    """Streaming monitor; bounded memory (one deque of `window` floats)."""

    def __init__(self, cfg: ValidityConfig | None = None,
                 calibration_var: float = 1.0):
        self.cfg = cfg or ValidityConfig()
        self.cal_var = calibration_var
        self._buf = deque(maxlen=self.cfg.window)
        self._restarts = 0
        self._context = None
        self._context_changed = False
        self.reasons: list = []

    def note_restart(self):
        self._restarts += 1

    def note_context(self, context: str):
        if self._context is not None and context != self._context:
            self._context_changed = True
            self._buf.clear()          # nominal model changed; re-estimate
        self._context = context

    def update(self, residual: float) -> Validity:
        self._buf.append(float(residual))
        return self.state()

    # -- indicators -------------------------------------------------------

    def _lag1(self):
        b = list(self._buf)
        n = len(b)
        if n < 30:
            return None
        m = sum(b) / n
        num = sum((b[i] - m) * (b[i + 1] - m) for i in range(n - 1))
        den = sum((v - m) ** 2 for v in b)
        return num / den if den > 0 else None

    def _var_ratio(self):
        b = list(self._buf)
        n = len(b)
        if n < 30 or self.cal_var <= 0:
            return None
        m = sum(b) / n
        return (sum((v - m) ** 2 for v in b) / (n - 1)) / self.cal_var

    def _kurt_excess(self):
        b = list(self._buf)
        n = len(b)
        if n < 60:
            return None
        m = sum(b) / n
        s2 = sum((v - m) ** 2 for v in b) / n
        if s2 <= 0:
            return None
        return sum((v - m) ** 4 for v in b) / n / (s2 * s2) - 3.0

    # -- decision ---------------------------------------------------------

    def state(self) -> Validity:
        cfg = self.cfg
        self.reasons = []
        if len(self._buf) < 30:
            self.reasons.append("INSUFFICIENT_SAMPLES_FOR_DOMAIN_CHECK")
            return Validity.UNCERTAIN
        rho = self._lag1()
        vr = self._var_ratio()
        ku = self._kurt_excess()

        if rho is not None and rho > cfg.rho_hard:
            self.reasons.append(f"DEPENDENCE_EXCEEDS_HARD_LIMIT rho~{rho:.2f}")
            return Validity.VIOLATED
        uncertain = False
        if rho is not None and rho > cfg.rho_max:
            self.reasons.append(f"DEPENDENCE_ABOVE_DECLARED_DOMAIN rho~{rho:.2f}")
            uncertain = True
        if vr is not None and not (cfg.var_lo <= vr <= cfg.var_hi):
            self.reasons.append(f"VARIANCE_SHIFT_VS_CALIBRATION ratio~{vr:.2f}")
            uncertain = True
        if ku is not None and abs(ku) > cfg.kurt_max:
            self.reasons.append(f"TAIL_BEHAVIOUR_OUTSIDE_CALIBRATION ku~{ku:.1f}")
            uncertain = True
        if self._restarts > cfg.max_restarts:
            self.reasons.append("RESTART_ACCOUNTING_PENDING_T2")
            uncertain = True
        if self._context_changed:
            self.reasons.append("CONTEXT_TRANSITION_REQUIRES_RECALIBRATION")
            uncertain = True
        if uncertain:
            return Validity.UNCERTAIN
        self.reasons.append("ALL_DOMAIN_INDICATORS_WITHIN_DECLARED_RANGE")
        return Validity.SUPPORTED

    def authorization(self) -> dict:
        """Fail-closed authorization record for the Assurance Ledger."""
        st = self.state()
        return {
            "validity": st.value,
            "anytime_guarantee_active": st is Validity.SUPPORTED,
            "evidence_authorized_action_permitted": False,   # slice: shadow only
            "causal_diagnosis_mode": ("NORMAL" if st is Validity.SUPPORTED
                                      else "RESEARCH_ONLY"),
            "reasons": list(self.reasons),
        }
