"""Substitutes rank for support: the highest-scoring hypothesis is asserted.

Named in the program brief as BAD_HIGH_SCORE_IS_SUPPORT, and it is the shape
most real implementations actually have. It computes a score, sorts, takes the
top, and calls the result a diagnosis -- with no check that any evidence
distinguishes the winner from the runner-up. When the evidence is silent the
scores are equal and it still picks one.

VIOLATES: DEA-5, DEA-6, DEA-8
"""

from __future__ import annotations

HYPOTHESES = ["NOMINAL", "PUMP_WEAK", "FILTER_CLOGGED", "LINE_LEAK"]

MODEL = {
    "NOMINAL":        {"dP": "NORMAL", "flow": "NORMAL", "level": "NORMAL"},
    "PUMP_WEAK":      {"dP": "LOW",    "flow": "LOW",    "level": "NORMAL"},
    "FILTER_CLOGGED": {"dP": "HIGH",   "flow": "LOW",    "level": "NORMAL"},
    "LINE_LEAK":      {"dP": "LOW",    "flow": "NORMAL", "level": "FALLING"},
}

NAME = "bad_high_score_is_support"
SHARES_CODE_WITH_CSIA = False


class Impl:
    NAME = NAME
    SHARES_CODE_WITH_CSIA = False

    def __init__(self, script=None):
        self.script = script or {}

    def hypotheses(self):
        return list(HYPOTHESES)

    def evidence_model(self):
        return {h: dict(v) for h, v in MODEL.items()}

    def evidence_state(self, t):
        frame = self.script.get(t, {})
        return frame.get("state", {})

    def _scores(self, state):
        out = {}
        for h, pred in MODEL.items():
            out[h] = sum(1 for e, o in state.items()
                         if o.get("outcome") == pred.get(e))
        return out

    def output(self, t):
        state = self.evidence_state(t)
        scores = self._scores(state)
        # Sort and take the top. No separation check anywhere: the violation.
        best = max(sorted(scores), key=lambda h: scores[h])
        witness = {"schema": "dea.support_witness/1", "t": t,
                   "asserted": best, "hypothesis_set_size": len(HYPOTHESES),
                   "separations": [{"competitor": c, "separated_by": []}
                                   for c in HYPOTHESES if c != best]}
        return {"attribution": best, "unassessable": False,
                "witness": witness,
                "health": {"pressure_delivery":
                           "HEALTHY" if best == "NOMINAL" else "FAULTY"}}
