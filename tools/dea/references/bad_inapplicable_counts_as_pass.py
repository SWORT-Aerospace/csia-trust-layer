"""Treats an inapplicable comparison as a passed one.

THE CENTRAL FAILURE THIS PROFILE EXISTS FOR. Differential pressure across a
filter says nothing while the pump is off. This implementation reads it as
NORMAL anyway, concludes NOMINAL, and reports the function healthy -- health
asserted from a comparison that was never performed.

VIOLATES: DEA-4, DEA-9
"""

from __future__ import annotations

HYPOTHESES = ["NOMINAL", "PUMP_WEAK", "FILTER_CLOGGED", "LINE_LEAK"]

MODEL = {
    "NOMINAL":        {"dP": "NORMAL", "flow": "NORMAL", "level": "NORMAL"},
    "PUMP_WEAK":      {"dP": "LOW",    "flow": "LOW",    "level": "NORMAL"},
    "FILTER_CLOGGED": {"dP": "HIGH",   "flow": "LOW",    "level": "NORMAL"},
    "LINE_LEAK":      {"dP": "LOW",    "flow": "NORMAL", "level": "FALLING"},
}

NAME = "bad_inapplicable_counts_as_pass"
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
        # Never reports applicability, and substitutes NORMAL for the
        # unperformed comparison rather than marking it unassessable.
        return {"dP": {"outcome": "NORMAL", "fresh": True},
                "flow": {"outcome": "NORMAL", "fresh": True},
                "level": {"outcome": "NORMAL", "fresh": True}}

    def output(self, t):
        return {"attribution": None, "unassessable": False, "witness": None,
                "health": {"pressure_delivery": "HEALTHY"}}
