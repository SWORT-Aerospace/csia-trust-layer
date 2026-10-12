"""Has no way to say "I do not know".

Correct support computation, and then a fallback that picks NOMINAL whenever
nothing is supported. A layer with no unassessable state will emit something
else, and "nothing is wrong" is the most dangerous available default.

VIOLATES: DEA-6, DEA-7, DEA-8, DEA-9
"""

from __future__ import annotations

HYPOTHESES = ["NOMINAL", "PUMP_WEAK", "FILTER_CLOGGED", "LINE_LEAK"]

MODEL = {
    "NOMINAL":        {"dP": "NORMAL", "flow": "NORMAL", "level": "NORMAL"},
    "PUMP_WEAK":      {"dP": "LOW",    "flow": "LOW",    "level": "NORMAL"},
    "FILTER_CLOGGED": {"dP": "HIGH",   "flow": "LOW",    "level": "NORMAL"},
    "LINE_LEAK":      {"dP": "LOW",    "flow": "NORMAL", "level": "FALLING"},
}

NAME = "bad_never_unassessable"
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
                out.append({"evidence_id": e, "observed": obs.get("outcome"),
                            "predicted_for_asserted": pa,
                            "predicted_for_competitor": pc})
        return out

    def output(self, t):
        state = self.evidence_state(t)
        for h in HYPOTHESES:
            seps = {c: self._seps(state, h, c)
                    for c in HYPOTHESES if c != h}
            if all(seps.values()):
                return {"attribution": h, "unassessable": False,
                        "witness": {"schema": "dea.support_witness/1", "t": t,
                                    "asserted": h,
                                    "hypothesis_set_size": len(HYPOTHESES),
                                    "separations": [
                                        {"competitor": c, "separated_by": v}
                                        for c, v in sorted(seps.items())]},
                        "health": {"pressure_delivery":
                                   "HEALTHY" if h == "NOMINAL" else "FAULTY"}}
        # The violation: no unassessable state, so it falls back to NOMINAL.
        return {"attribution": "NOMINAL", "unassessable": False,
                "witness": {"schema": "dea.support_witness/1", "t": t,
                            "asserted": "NOMINAL",
                            "hypothesis_set_size": len(HYPOTHESES),
                            "separations": [{"competitor": c,
                                             "separated_by": []}
                                            for c in HYPOTHESES
                                            if c != "NOMINAL"]},
                "health": {"pressure_delivery": "HEALTHY"}}
