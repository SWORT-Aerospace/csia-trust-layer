"""Declares hypotheses but not what any of them predicts.

Without predictions, "separating evidence" has no meaning, and any claim that
evidence separated two hypotheses is unfalsifiable.

VIOLATES: DEA-2
"""

from __future__ import annotations

HYPOTHESES = ["NOMINAL", "PUMP_WEAK", "FILTER_CLOGGED", "LINE_LEAK"]

MODEL = {
    "NOMINAL":        {"dP": "NORMAL", "flow": "NORMAL", "level": "NORMAL"},
    "PUMP_WEAK":      {"dP": "LOW",    "flow": "LOW",    "level": "NORMAL"},
    "FILTER_CLOGGED": {"dP": "HIGH",   "flow": "LOW",    "level": "NORMAL"},
    "LINE_LEAK":      {"dP": "LOW",    "flow": "NORMAL", "level": "FALLING"},
}

NAME = "bad_no_evidence_model"
SHARES_CODE_WITH_CSIA = False


class Impl:
    NAME = NAME
    SHARES_CODE_WITH_CSIA = False

    def __init__(self, script=None):
        self.script = script or {}

    def hypotheses(self):
        return list(HYPOTHESES)

    def evidence_model(self):
        return {}                       # the violation

    def evidence_state(self, t):
        return {"dP": {"outcome": "HIGH", "fresh": True, "applicable": True}}

    def output(self, t):
        return {"attribution": "FILTER_CLOGGED", "unassessable": False,
                "witness": None, "health": {"pressure_delivery": "FAULTY"}}
