"""Refuses to declare what hypotheses it admits.

The commonest real-world shape of this: a layer that emits a fault code from a
lookup table and has no explicit notion of "the other things this could have
been". Separation is defined relative to the admitted set, so a layer that will
not state the set cannot be assessed at all -- and must not be recorded as
passing by default.

VIOLATES: DEA-1
"""

from __future__ import annotations

HYPOTHESES = ["NOMINAL", "PUMP_WEAK", "FILTER_CLOGGED", "LINE_LEAK"]

MODEL = {
    "NOMINAL":        {"dP": "NORMAL", "flow": "NORMAL", "level": "NORMAL"},
    "PUMP_WEAK":      {"dP": "LOW",    "flow": "LOW",    "level": "NORMAL"},
    "FILTER_CLOGGED": {"dP": "HIGH",   "flow": "LOW",    "level": "NORMAL"},
    "LINE_LEAK":      {"dP": "LOW",    "flow": "NORMAL", "level": "FALLING"},
}

NAME = "bad_no_hypothesis_set"
SHARES_CODE_WITH_CSIA = False


class Impl:
    NAME = NAME
    SHARES_CODE_WITH_CSIA = False

    def __init__(self, script=None):
        self.script = script or {}

    def hypotheses(self):
        return []                       # the violation

    def evidence_model(self):
        return {h: dict(v) for h, v in MODEL.items()}

    def evidence_state(self, t):
        return {"dP": {"outcome": "HIGH", "fresh": True, "applicable": True}}

    def output(self, t):
        return {"attribution": "FILTER_CLOGGED", "unassessable": False,
                "witness": None, "health": {"pressure_delivery": "FAULTY"}}
