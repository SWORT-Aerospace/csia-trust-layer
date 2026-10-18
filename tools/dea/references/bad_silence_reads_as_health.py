"""Emits health with a two-valued vocabulary: HEALTHY or FAULTY.

Nothing means "not assessed", so a consumer downstream cannot distinguish a
function that was checked and found good from one that was never checked. Even
if this layer internally knew the difference, its output destroys it -- which
makes DEA-9 unenforceable at the interface no matter what the layer computes.

VIOLATES: DEA-9, DEA-10
"""

from __future__ import annotations

HYPOTHESES = ["NOMINAL", "PUMP_WEAK", "FILTER_CLOGGED", "LINE_LEAK"]

MODEL = {
    "NOMINAL":        {"dP": "NORMAL", "flow": "NORMAL", "level": "NORMAL"},
    "PUMP_WEAK":      {"dP": "LOW",    "flow": "LOW",    "level": "NORMAL"},
    "FILTER_CLOGGED": {"dP": "HIGH",   "flow": "LOW",    "level": "NORMAL"},
    "LINE_LEAK":      {"dP": "LOW",    "flow": "NORMAL", "level": "FALLING"},
}

NAME = "bad_silence_reads_as_health"
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
        return self.script.get(t, {}).get("state", {})

    def output(self, t):
        state = self.evidence_state(t)
        active = [e for e, o in state.items()
                  if o.get("fresh") and o.get("applicable")]
        # The violation: with no active evidence it still says HEALTHY, and
        # the vocabulary offers no third value to say otherwise.
        return {"attribution": None, "unassessable": False, "witness": None,
                "health": {"pressure_delivery":
                           "HEALTHY" if not active else "HEALTHY"}}
