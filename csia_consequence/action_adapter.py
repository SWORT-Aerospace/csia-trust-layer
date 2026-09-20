"""Phase 3 — the three policies, and the one place a response is named.

STRUCTURE, AND WHY IT IS THIS SHAPE
-----------------------------------
The preregistration requires that the support-aware policy hold no actuator
authority and emit only a typed support state. That is enforced here by
module structure rather than by convention:

    p0_response / p1_response      wrap the FROZEN FailsafePolicy
    p2_support                     emits IDENTIFIABLE / AMBIGUOUS /
                                   NON_IDENTIFIABLE and nothing else
    adapt                          the ONLY function that names a response

`p2_support` returns a `SupportReport`. It cannot reach `adapt` except through
that typed value, and it has no way to express "descend" or "select imu0".

WHAT IS REAL HERE AND WHAT IS NOT
---------------------------------
Real, and not re-implemented: `csia.runtime.online.OnlineTrustLayer` produces
the `TrustState`, and `csia.runtime.failsafe.FailsafePolicy` produces P0's
level and actions. Both are in the frozen core and neither is touched.

Modelled: nothing in this module. The vehicle's response to a response lives
in `consequence_model.py`, which is where the model-based part of
`MODEL_BASED_ACTION_CONSEQUENCE` actually is.

THE GATE-WEIGHT SUBSTITUTION, STATED WHERE IT IS MADE
-----------------------------------------------------
Support needs a weight for every feature in `SOURCE_INDICATORS`. `TrustState`
exposes the `E` edge gates and does not expose the `P` node gates or the
`temp_*` gates -- they exist only inside `_tick`'s locals, and exposing them
would mean editing the frozen core. So:

    edge features     EXACT, read from `state.edges`
    phys_<n>          substituted as `1.0 * fresh[n]`
    temp_<n>          substituted as `1.0`

Both substitutions are chosen in the direction that makes IDENTIFIABLE EASIER
and therefore makes any support-based finding HARDER to obtain. For the five
node terms the Phase-2 inventory classifies `ALWAYS_OPEN` the `phys_`
substitution is exact. For `phys_gps`, `phys_mag` and `phys_vibration` it
overstates availability -- those three are out of Phase-3 scope for exactly
this reason, and overstating their availability cannot manufacture a finding.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Tuple

from csia.diagnosis.bayes import TEMP_FEATURES
from csia.diagnosis.causal import SOURCE_INDICATORS
from csia.runtime.failsafe import FailsafeLevel

from . import support as _support

#: This module decides nothing about actuators. It names a response; the
#: response is consumed by a model, never by a vehicle.
HAS_ACTUATOR_AUTHORITY = False

#: The LOW-sets attribution is decided over, taken verbatim from the frozen
#: core rather than restated.
LOW_SETS: Dict[str, FrozenSet[str]] = {
    source: frozenset(features)
    for source, features in SOURCE_INDICATORS.items()
}

#: The pair the SELECT_IMU decision discriminates. Their symmetric difference
#: is exactly the two armed-gated features, which is the whole Phase-3
#: prediction.
DECISION_PAIR: Tuple[str, str] = ("imu0", "imu1")

# --- responses ------------------------------------------------------------
R_NONE = "NONE"
R_CAUTION_GENERIC = "CAUTION_GENERIC"
R_SELECT_IMU0 = "SELECT_IMU0"
R_SELECT_IMU1 = "SELECT_IMU1"
R_PREPARE_LANDING = "PREPARE_LANDING"
R_CONTROLLED_DESCENT = "CONTROLLED_DESCENT"
R_ABSTAIN = "ABSTAIN"

RESPONSES = (R_NONE, R_CAUTION_GENERIC, R_SELECT_IMU0, R_SELECT_IMU1,
             R_PREPARE_LANDING, R_CONTROLLED_DESCENT, R_ABSTAIN)

#: A response that names a specific source. These are the ones support can
#: withdraw, because they are the ones that assert an attribution.
ATTRIBUTING = frozenset({R_SELECT_IMU0, R_SELECT_IMU1})


def feature_weights(state) -> Dict[str, float]:
    """Gate weight per feature this tick. See the module docstring."""
    weights: Dict[str, float] = {}
    for key, (_consistency, gate) in state.edges.items():
        weights[key] = float(gate)
    for sensor, ok in state.fresh.items():
        weights[f"phys_{sensor}"] = 1.0 * float(bool(ok))
    for sensor in TEMP_FEATURES:
        weights[f"temp_{sensor}"] = 1.0
    return weights


def p2_support(state, *, sources=None, provenance="phase3"):
    """P2's ENTIRE output. A typed support state and nothing else."""
    names = tuple(sorted(LOW_SETS)) if sources is None else tuple(sources)
    return _support.classify(
        hypotheses=names,
        low_sets={n: LOW_SETS[n] for n in names},
        gates=feature_weights(state),
        timestamp_s=float(state.t),
        provenance=provenance)


def decision_pair_support(state, *, provenance="phase3-pair"):
    """Support for the pair the action actually discriminates.

    The global support state over all eight sources answers "can the evidence
    tell any two sources apart". The decision does not ask that. It asks
    whether THIS attribution -- imu0 versus imu1 -- is supported, and a
    policy that consulted the global state would be answering a different
    question from the one it is about to act on.
    """
    return p2_support(state, sources=DECISION_PAIR, provenance=provenance)


# --- P0 and P1: the frozen failsafe, with and without a freshness overlay --

def _from_actions(level, actions) -> str:
    """Map the frozen policy's typed actions onto the response vocabulary."""
    names = [a.name for a in actions]
    if "CONTROLLED_DESCENT" in names:
        return R_CONTROLLED_DESCENT
    if "SELECT_IMU" in names:
        use = next(a.params.get("use") for a in actions
                   if a.name == "SELECT_IMU")
        return R_SELECT_IMU0 if use == "imu0" else R_SELECT_IMU1
    if "PREPARE_LANDING" in names or "LAND_NOW" in names \
            or "LAND_SOON" in names:
        return R_PREPARE_LANDING
    if names:
        return R_CAUTION_GENERIC
    if level >= FailsafeLevel.CRITICAL:
        return R_PREPARE_LANDING
    if level >= FailsafeLevel.CAUTION:
        return R_CAUTION_GENERIC
    return R_NONE


@dataclass(frozen=True)
class Decision:
    """One policy's output at one tick, plus why."""
    response: str
    level: int
    support_state: Optional[str]
    pair_support_state: Optional[str]
    reason: str

    def __post_init__(self) -> None:
        if self.response not in RESPONSES:
            raise ValueError(f"unknown response {self.response!r}")


def p0_decide(state, level, actions) -> Decision:
    """Current CSIA behaviour: the frozen failsafe, unmodified."""
    return Decision(_from_actions(level, actions), int(level), None, None,
                    "P0: frozen FailsafePolicy output, unmodified")


def p1_decide(state, level, actions, *, monitored) -> Decision:
    """Freshness-only fallback, implemented so that it can win.

    The rule is the strongest reasonable form of "the existing freshness logic
    already covers this": ANY monitored sensor that is not fresh raises the
    response to at least a generic caution. If occlusion were in fact covered
    by freshness, this policy would catch what P0 misses and H2 would be
    rejected on criterion (c).
    """
    base = p0_decide(state, level, actions)
    stale = sorted(n for n in monitored if not state.fresh.get(n, False))
    if stale and base.response == R_NONE:
        return Decision(R_CAUTION_GENERIC, int(level), None, None,
                        f"P1: freshness fallback on stale {stale}")
    return Decision(base.response, base.level, None, None,
                    "P1: freshness rule did not fire; " + base.reason)


def adapt(state, level, actions, support_report, pair_report) -> Decision:
    """THE ONLY FUNCTION THAT NAMES A RESPONSE FOR P2.

    It takes the frozen failsafe's level and actions, and a typed support
    value. It withdraws an ATTRIBUTING response when the pair that response
    discriminates is not identifiable, and it does nothing else: it never
    escalates, never invents an action, and never touches a response that
    asserts no attribution.

    Withdrawing to ABSTAIN is a real cost and is counted as one. An abstention
    is not a correct answer; it is a refusal to give a wrong one.
    """
    base = p0_decide(state, level, actions)
    if base.response in ATTRIBUTING and \
            pair_report.status != _support.IDENTIFIABLE:
        return Decision(R_ABSTAIN, int(level), support_report.status,
                        pair_report.status,
                        f"P2: withdrew {base.response} -- "
                        f"{pair_report.status}/{pair_report.reason} for "
                        f"{DECISION_PAIR}")
    return Decision(base.response, base.level, support_report.status,
                    pair_report.status, "P2: " + base.reason)
