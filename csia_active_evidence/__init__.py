"""Active evidence acquisition: ask for the smallest bounded diagnostic action.

WHAT THIS PACKAGE DOES
----------------------
When a fault cannot be localised from the data a vehicle happens to be
producing, this package works out what bounded perturbation WOULD separate
the remaining hypotheses, asks an independent authorizer for permission, and
-- if permission is granted -- says what the result does to the hypothesis
set. It never runs anything and it never decides that it may.

WHAT IT DOES NOT DO
-------------------
  * it does not touch the frozen v1 core. `csia/trust_engine`,
    `csia/diagnosis`, `csia/runtime/online.py`, `csia/runtime/failsafe.py`,
    `csia/scenarios.py` and `csia/profiles.py` are read at most, never
    imported for modification and never edited;
  * it does not transmit. `active_action_prohibited` is True in every
    episode and a test asserts no module here can reach a send path;
  * it does not promote anything. No trust value, capability state or
    support verdict is written by any function in this package;
  * it contains no neural network, no language model and no learned
    component of any kind. Every decision is a closed-form inequality.

MODULES
-------
  identifiability  the error model, inverted into a probe requirement
  probes           a library of bounded excitations, statistics COMPUTED
  authority        an independent ALLOW / CLIP / DENY mock that can refuse
  selector         cheapest probe meeting the requirement, or a refusal
  updater          set-valued hypothesis elimination, with abstention
  contract         the versioned episode record and the stopping rule

STATUS
------
RESEARCH. Simulation only. No novelty is claimed: the required prior-art
search could not be run from this host and
`research/active_evidence/PRIOR_ART_MATRIX.md` records the refusals
verbatim and marks the search INCOMPLETE.
"""

from .identifiability import (ExcitationStats, NoiseModel, ProbeRequirement,
                              Separability, attenuation, estimate_sd,
                              expected_estimate, naive_estimate_sd,
                              probe_requirement, rank_of_design,
                              resolvable_delta, separability)

__all__ = [
    "ExcitationStats", "NoiseModel", "ProbeRequirement", "Separability",
    "attenuation", "estimate_sd", "expected_estimate", "naive_estimate_sd",
    "probe_requirement", "rank_of_design", "resolvable_delta",
    "separability",
]
