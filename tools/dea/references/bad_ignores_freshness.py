"""Reports no freshness at all: every observation is current forever.

This is the stale-sensor failure. The last reading before a sensor died looks
exactly like a fresh reading, and a layer built this way will hold an
attribution indefinitely on evidence that stopped arriving.

VIOLATES: DEA-3
"""

from __future__ import annotations

HYPOTHESES = ["NOMINAL", "PUMP_WEAK", "FILTER_CLOGGED", "LINE_LEAK"]

MODEL = {
    "NOMINAL":        {"dP": "NORMAL", "flow": "NORMAL", "level": "NORMAL"},
    "PUMP_WEAK":      {"dP": "LOW",    "flow": "LOW",    "level": "NORMAL"},
    "FILTER_CLOGGED": {"dP": "HIGH",   "flow": "LOW",    "level": "NORMAL"},
    "LINE_LEAK":      {"dP": "LOW",    "flow": "NORMAL", "level": "FALLING"},
}

NAME = "bad_ignores_freshness"
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
        # No "fresh" key anywhere: the violation. Applicability IS reported,
        # so this isolates DEA-3 from DEA-4.
        return {"dP": {"outcome": "HIGH", "applicable": True},
                "flow": {"outcome": "LOW", "applicable": True},
                "level": {"outcome": "NORMAL", "applicable": True}}

    def output(self, t):
        return {"attribution": None, "unassessable": True, "witness": None,
                "health": {"pressure_delivery": "UNASSESSABLE"}}
