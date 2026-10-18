"""Consequence, support and cross-architecture validation.

STATUS: SIMULATION / SOURCE-ANALYSIS ONLY.
------------------------------------------
Nothing in this package has run an autopilot, flown a vehicle, or touched
hardware. `gates.py` is a hand-read inventory of source expressions in
`csia/runtime/online.py`, cross-checked by an independent evaluator that
imports no CSIA module (`research/consequence/independent_gate_evaluator.py`).
`support.py` is a structural classifier over hypothesis LOW-sets. Neither
produces a measurement.

The preregistration that fixes what this phase may and may not conclude is
`research/consequence/PREREGISTRATION.md`, written before the analysis ran.

WHY SUPPORT IS NOT CONFIDENCE
-----------------------------
A normalized posterior over a hypothesis set always sums to one, so it reports
a winner even when nothing in the evidence could tell the candidates apart.
Two hypotheses are separable only by features in the symmetric difference of
their LOW-sets: a feature in both, or in neither, contributes the same term to
both log-likelihoods and cancels exactly. `support.py` answers the prior
question -- IDENTIFIABLE / AMBIGUOUS / NON_IDENTIFIABLE -- from active
structural support alone, and never from a normalized number.

AUTHORITY
---------
Read-only analysis. This package issues no command, holds no actuator
authority, and decides nothing about capability.
"""
from __future__ import annotations

from . import gates, partitions, support

# NOT re-exported here, on purpose: `action_adapter`, `consequence_model` and
# `phase3_partitions` are the Phase-3 measurement layer, and the first two
# import the frozen core (`csia.runtime.failsafe`, `csia.diagnosis.causal`).
# Pulling them in at package import would make `import csia_consequence` --
# which Phase 2 uses for pure source analysis -- depend on the runtime. Import
# them by name when you want them.

#: Analysis only. Nothing here commands anything.
LAYER = "analysis"
HAS_ACTUATOR_AUTHORITY = False
HARDWARE_VALIDATED = False
EVIDENCE_LEVEL = "SOURCE_ANALYSIS"

__all__ = ["gates", "partitions", "support", "LAYER",
           "HAS_ACTUATOR_AUTHORITY", "HARDWARE_VALIDATED", "EVIDENCE_LEVEL"]
