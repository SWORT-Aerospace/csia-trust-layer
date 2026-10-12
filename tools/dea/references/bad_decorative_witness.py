"""Computes support correctly and then emits a witness that proves nothing.

The subtlest of the eight, and the reason DEA-8 specifies the witness CONTENT
rather than its presence. This layer only attributes when genuinely supported,
so DEA-6 holds -- but its witness lists every evidence item it happened to
hold, with no mapping from competitor to separator. An auditor reading it
cannot check the attribution, which is the only thing a witness is for.

VIOLATES: DEA-8
"""

from __future__ import annotations

HYPOTHESES = ["NOMINAL", "PUMP_WEAK", "FILTER_CLOGGED", "LINE_LEAK"]

MODEL = {
    "NOMINAL":        {"dP": "NORMAL", "flow": "NORMAL", "level": "NORMAL"},
    "PUMP_WEAK":      {"dP": "LOW",    "flow": "LOW",    "level": "NORMAL"},
    "FILTER_CLOGGED": {"dP": "HIGH",   "flow": "LOW",    "level": "NORMAL"},
    "LINE_LEAK":      {"dP": "LOW",    "flow": "NORMAL", "level": "FALLING"},
}

NAME = "bad_decorative_witness"
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

    def _seps(self, state, a, c):
        out = []
        for e, obs in state.items():
            if not (obs.get("fresh") and obs.get("applicable")):
                continue
            pa, pc = MODEL[a].get(e), MODEL[c].get(e)
            if pa is None or pc is None or pa == pc:
                continue
            if obs.get("outcome") == pa and obs.get("outcome") != pc:
                out.append(e)
        return out

    def output(self, t):
        state = self.evidence_state(t)
        for h in HYPOTHESES:
            if all(self._seps(state, h, c) for c in HYPOTHESES if c != h):
                return {
                    "attribution": h, "unassessable": False,
                    # The violation: a flat list of everything held, with no
                    # per-competitor separation. It looks like a witness.
                    "witness": {"schema": "dea.support_witness/1", "t": t,
                                "asserted": h,
                                "hypothesis_set_size": len(HYPOTHESES),
                                "evidence_considered": sorted(state)},
                    "health": {"pressure_delivery":
                               "HEALTHY" if h == "NOMINAL" else "FAULTY"}}
        return {"attribution": None, "unassessable": True, "witness": None,
                "health": {"pressure_delivery": "UNASSESSABLE"}}
