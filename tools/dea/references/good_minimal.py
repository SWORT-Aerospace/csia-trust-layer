"""A conforming DEA implementation that is NOT CSIA and shares no code with it.

WHY THIS FILE EXISTS
--------------------
A profile validated only against its author's own system is a description of
that system wearing a standard's clothes. This implementation imports nothing
from `csia`, uses no trust coefficient, no Bayesian update, no graph, no
smoothing and no thresholds. It is a lookup table and a set comparison.

It conforms. That is the claim being tested: DEA-CORE is satisfiable by
something that resembles CSIA in no respect except honesty about what its
evidence entitles it to say.

THE DOMAIN IS DELIBERATELY NOT AVIONICS
----------------------------------------
A small hydraulic loop: a pump, a filter and a line. Three faults, three
observations. If the profile were secretly avionics-shaped, it would show up
here as a requirement that cannot be met without a flight concept.

  hypotheses      NOMINAL, PUMP_WEAK, FILTER_CLOGGED, LINE_LEAK
  evidence        dP_across_filter, flow_vs_command, reservoir_level_trend

Each evidence item predicts HIGH / LOW / NORMAL per hypothesis. Support is the
definition applied literally: h is supported when, for every other admitted
hypothesis, some ACTIVE item's observed outcome matches h's prediction and not
the competitor's.
"""

from __future__ import annotations

NAME = "hydraulic_loop_minimal"
VERSION = "0.1"
SHARES_CODE_WITH_CSIA = False

HYPOTHESES = ["NOMINAL", "PUMP_WEAK", "FILTER_CLOGGED", "LINE_LEAK"]

#: The declared evidence model (DEA-2). One table, no mathematics.
MODEL = {
    "NOMINAL":         {"dP_across_filter": "NORMAL",
                        "flow_vs_command": "NORMAL",
                        "reservoir_level_trend": "NORMAL"},
    "PUMP_WEAK":       {"dP_across_filter": "LOW",
                        "flow_vs_command": "LOW",
                        "reservoir_level_trend": "NORMAL"},
    "FILTER_CLOGGED":  {"dP_across_filter": "HIGH",
                        "flow_vs_command": "LOW",
                        "reservoir_level_trend": "NORMAL"},
    "LINE_LEAK":       {"dP_across_filter": "LOW",
                        "flow_vs_command": "NORMAL",
                        "reservoir_level_trend": "FALLING"},
}

FRESHNESS_LIMIT_S = {"dP_across_filter": 2.0, "flow_vs_command": 2.0,
                     "reservoir_level_trend": 30.0}

#: Applicability: differential pressure across a filter says nothing while the
#: pump is off, and reading it then as NORMAL is exactly the DEA-4 failure.
def _applicable(evidence_id: str, pump_running: bool) -> bool:
    if evidence_id in ("dP_across_filter", "flow_vs_command"):
        return pump_running
    return True


class HydraulicLoop:
    """Scripted observations, so a conformance run is deterministic."""

    NAME = NAME
    VERSION = VERSION
    SHARES_CODE_WITH_CSIA = SHARES_CODE_WITH_CSIA

    def __init__(self, script: dict):
        """script: t -> {"pump_running": bool, "obs": {id: (outcome, age_s)}}"""
        self.script = script

    # ------------------------------------------------------------- DEA-1, 2
    def hypotheses(self) -> list:
        return list(HYPOTHESES)

    def evidence_model(self) -> dict:
        return {h: dict(v) for h, v in MODEL.items()}

    # ------------------------------------------------------------- DEA-3, 4
    def evidence_state(self, t) -> dict:
        frame = self.script.get(t, {})
        pump = frame.get("pump_running", True)
        out = {}
        for evidence_id, (outcome, age) in (frame.get("obs") or {}).items():
            out[evidence_id] = {
                "outcome": outcome,
                "fresh": age <= FRESHNESS_LIMIT_S[evidence_id],
                "applicable": _applicable(evidence_id, pump),
                "age_s": age,
                "freshness_limit_s": FRESHNESS_LIMIT_S[evidence_id],
            }
        return out

    # -------------------------------------------------------- support, DEA-5
    def _separators(self, state, asserted, competitor) -> list:
        out = []
        for evidence_id, obs in state.items():
            if not (obs["fresh"] and obs["applicable"]):
                continue
            pa = MODEL[asserted].get(evidence_id)
            pc = MODEL[competitor].get(evidence_id)
            if pa is None or pc is None or pa == pc:
                continue
            # Directional: the observation must match the ASSERTED
            # hypothesis and not the competitor. Evidence against you is not
            # evidence for you.
            if obs["outcome"] == pa and obs["outcome"] != pc:
                out.append({
                    "evidence_id": evidence_id,
                    "observed": obs["outcome"],
                    "predicted_for_asserted": pa,
                    "predicted_for_competitor": pc,
                    "active_because": {
                        "fresh": obs["fresh"], "applicable": obs["applicable"],
                        "age_s": obs["age_s"],
                        "freshness_limit_s": obs["freshness_limit_s"]},
                })
        return out

    def _support(self, state, asserted):
        seps = {c: self._separators(state, asserted, c)
                for c in HYPOTHESES if c != asserted}
        return all(seps.values()), seps

    # ------------------------------------------------ DEA-6..DEA-10 output
    def output(self, t) -> dict:
        state = self.evidence_state(t)

        supported = [h for h in HYPOTHESES if self._support(state, h)[0]]
        # More than one supported hypothesis means the evidence does not pick
        # one, and asserting the "best" of them is the failure DEA-6 forbids.
        if len(supported) != 1:
            return {
                "attribution": None,
                "unassessable": True,
                "witness": None,
                "health": {fn: "UNASSESSABLE" for fn in ("pressure_delivery",)},
                "note": (f"{len(supported)} hypotheses are supported; the "
                         f"evidence does not separate one"),
            }

        asserted = supported[0]
        _ok, seps = self._support(state, asserted)
        witness = {
            "schema": "dea.support_witness/1",
            "t": t,
            "asserted": asserted,
            "hypothesis_set_size": len(HYPOTHESES),
            "separations": [{"competitor": c, "separated_by": v}
                            for c, v in sorted(seps.items())],
        }
        # DEA-9/DEA-10: health is asserted only from ACTIVE evidence, and the
        # vocabulary has a value that means "not assessed".
        active = [e for e, o in state.items()
                  if o["fresh"] and o["applicable"]]
        health = {"pressure_delivery":
                  ("HEALTHY" if asserted == "NOMINAL" and active
                   else "UNASSESSABLE" if not active else "FAULTY")}
        return {"attribution": asserted, "unassessable": False,
                "witness": witness, "health": health}
