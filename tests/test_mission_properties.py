"""Property-based tests for the mission layer.

WHY PROPERTIES AND NOT MORE EXAMPLES
------------------------------------
The example tests in this repository were written by the same person who
wrote the code, which means they encode the same assumptions -- including
the wrong ones. MX-004 is the recorded instance: two checks "passed" from
zero cases and nobody noticed, because the examples agreed with the
author's mental model of what would be constructed.

A property test does not ask "does this case work". It asks "is this
statement true for every input Hypothesis can find", and it is allowed to
find inputs nobody thought of.

THE PROPERTIES HERE ARE INVARIANTS, NOT RESTATEMENTS
----------------------------------------------------
A property that re-implements the function it tests proves only that two
copies of the same mistake agree. Each property below is a statement about
what the LAYER MUST NEVER DO, phrased so it could be false:

  * UNKNOWN is never promoted to SUPPORTED
  * losing evidence never improves a capability
  * expiry beats support, always
  * evaluation is deterministic and order-independent
  * a prohibited use is never also permitted

Every one of them could fail against a plausible wrong implementation,
which is the test for whether a property is worth writing.
"""

from __future__ import annotations

import os
import sys

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_mission.capability import (CAPABILITY_STATES,       # noqa: E402
                                     DEGRADED_SUPPORTED, NOT_EVALUABLE,
                                     NOT_SUPPORTED, SUPPORTED, UNKNOWN,
                                     CapabilityContract, ContractError,
                                     EvidenceStatus, _combine,
                                     _validated_k_of_n, evaluate_capabilities)

SEVERITY = {NOT_EVALUABLE: 0, NOT_SUPPORTED: 1, UNKNOWN: 2,
            DEGRADED_SUPPORTED: 3, SUPPORTED: 4}

SETTINGS = settings(max_examples=250, deadline=None,
                    suppress_health_check=[HealthCheck.too_slow])

evidence_ids = st.sampled_from(["e0", "e1", "e2", "e3", "e4"])
states = st.sampled_from(CAPABILITY_STATES)
#: None means UNKNOWN and must STAY UNKNOWN -- that is the point of the value.
supported_values = st.sampled_from([True, False, None])


@st.composite
def evidence_map(draw, ids=("e0", "e1", "e2", "e3", "e4")):
    """A world of evidence, some of it unknown, some of it expired."""
    out = {}
    for eid in ids:
        supported = draw(supported_values)
        expires = draw(st.one_of(st.none(),
                                 st.floats(min_value=0.0, max_value=200.0,
                                           allow_nan=False,
                                           allow_infinity=False)))
        out[eid] = EvidenceStatus(evidence_id=eid, supported=supported,
                                  expires_at=expires)
    return out


@st.composite
def simple_contract(draw):
    """One capability depending on evidence only -- no subordinates, so the
    property is about requirement resolution rather than graph order."""
    ids = ["e0", "e1", "e2", "e3", "e4"]
    n_all = draw(st.integers(min_value=0, max_value=3))
    requires_all = tuple(draw(st.lists(st.sampled_from(ids), min_size=n_all,
                                       max_size=n_all, unique=True)))
    groups = draw(st.lists(
        st.lists(st.sampled_from(ids), min_size=2, max_size=3, unique=True),
        min_size=0, max_size=2))
    requires_one_of = tuple(tuple(g) for g in groups)
    assume(requires_all or requires_one_of)
    return CapabilityContract(capability_id="cap",
                              requires_all=requires_all,
                              requires_one_of=requires_one_of)


def _state(contract, evidence, now=50.0):
    reports = evaluate_capabilities([contract], evidence, now=now)
    return reports["cap"].state


# ---------------------------------------------------------------------------
# the central invariant
# ---------------------------------------------------------------------------

@SETTINGS
@given(contract=simple_contract(), evidence=evidence_map())
def test_unknown_evidence_is_never_promoted_to_supported(contract, evidence):
    """IF ANY REQUIRED EVIDENCE IS UNKNOWN, THE CAPABILITY IS NOT SUPPORTED.

    This is the single property the whole layer exists to guarantee. An
    implementation that treated "nobody reported on this" as "fine" would
    pass every example test written by someone who never constructed that
    case, and would fail here.

    THE CONDITION IS READ FROM THE RAW INPUT, not from `state_at()`. An
    earlier version guarded on `state_at(...) == UNKNOWN`, which is the
    function under test: mutating `state_at` to return SUPPORTED for
    unknown evidence ALSO disabled the guard, so the property silently
    stopped asserting anything and the mutant survived. A property that
    asks the implementation whether it should check the implementation is
    not a property.
    """
    required = set(contract.requires_all)
    if not any(evidence[e].supported is None for e in required):
        return
    assert _state(contract, evidence) != SUPPORTED, (
        "a capability was fully SUPPORTED while one of its own required "
        "evidence items was UNKNOWN")


@SETTINGS
@given(contract=simple_contract(), evidence=evidence_map(),
       victim=evidence_ids)
def test_losing_evidence_never_improves_a_capability(contract, evidence,
                                                     victim):
    """MONOTONICITY. Flipping evidence from supported to unsupported can
    leave a capability unchanged -- a `requires_one_of` group may cover it --
    but it must never make the capability BETTER.
    """
    before = _state(contract, evidence)
    worse = dict(evidence)
    worse[victim] = EvidenceStatus(evidence_id=victim, supported=False,
                                   expires_at=evidence[victim].expires_at)
    after = _state(contract, worse)
    assert SEVERITY[after] <= SEVERITY[before], (
        f"losing {victim} improved the capability: {before} -> {after}")


@SETTINGS
@given(evidence=evidence_map(),
       now=st.floats(min_value=0.0, max_value=300.0, allow_nan=False,
                     allow_infinity=False))
def test_expiry_beats_support_for_every_item(evidence, now):
    """A witness valid at t is not a witness at t + dt, whatever it claimed."""
    for status in evidence.values():
        state = status.state_at(now)
        if status.supported is None:
            assert state == UNKNOWN, "None must stay UNKNOWN"
        elif status.expires_at is not None and now > status.expires_at:
            assert state == NOT_SUPPORTED, (
                "an expired item reported something other than NOT_SUPPORTED")
        else:
            assert state == (SUPPORTED if status.supported else NOT_SUPPORTED)


@SETTINGS
@given(contract=simple_contract(), evidence=evidence_map())
def test_evaluation_is_deterministic(contract, evidence):
    """Same inputs, same answer. A layer whose verdict moves between calls
    cannot be the basis of an authorization decision."""
    assert _state(contract, evidence) == _state(contract, evidence)


@SETTINGS
@given(evidence=evidence_map(),
       order=st.permutations(["a", "b", "c"]))
def test_contract_order_cannot_change_a_verdict(evidence, order):
    """Contracts are topologically ordered before evaluation, so the
    caller's iteration order is not an input to the result."""
    contracts = [
        CapabilityContract(capability_id="a", requires_all=("e0",)),
        CapabilityContract(capability_id="b", requires_all=("e1",),
                           requires_capabilities=("a",)),
        CapabilityContract(capability_id="c", requires_all=("e2",),
                           requires_capabilities=("b",)),
    ]
    by_id = {c.capability_id: c for c in contracts}
    shuffled = [by_id[name] for name in order]
    baseline = evaluate_capabilities(contracts, evidence, now=50.0)
    reordered = evaluate_capabilities(shuffled, evidence, now=50.0)
    assert {k: v.state for k, v in baseline.items()} == \
           {k: v.state for k, v in reordered.items()}


# ---------------------------------------------------------------------------
# _combine: worst wins
# ---------------------------------------------------------------------------

@SETTINGS
@given(values=st.lists(states, min_size=1, max_size=8))
def test_combine_is_the_worst_and_never_an_average(values):
    """Worst wins. Never a mean, never a majority, never a vote."""
    result = _combine(values)
    assert result in values
    assert SEVERITY[result] == min(SEVERITY[v] for v in values)


@SETTINGS
@given(values=st.lists(states, min_size=1, max_size=8))
def test_combine_is_order_independent_and_idempotent(values):
    assert _combine(values) == _combine(list(reversed(values)))
    assert _combine([_combine(values)]) == _combine(values)


@SETTINGS
@given(a=st.lists(states, min_size=1, max_size=4),
       b=st.lists(states, min_size=1, max_size=4))
def test_combining_more_states_never_improves_the_result(a, b):
    """Adding a requirement cannot make a capability better."""
    assert SEVERITY[_combine(a + b)] <= SEVERITY[_combine(a)]


# ---------------------------------------------------------------------------
# k-of-n: the form that refuses to be guessed
# ---------------------------------------------------------------------------

@SETTINGS
@given(k=st.integers(min_value=-5, max_value=10),
       n=st.integers(min_value=1, max_value=5))
def test_k_of_n_accepts_only_k_within_range(k, n):
    """k outside [1, n] is vacuous (k <= 0) or unsatisfiable (k > n), and
    both are refused rather than clamped. Clamping would silently turn a
    typo into a requirement nobody wrote."""
    spec = {"k": k, "of": tuple(f"e{i}" for i in range(n))}
    if 1 <= k <= n:
        parsed_k, parsed_of = _validated_k_of_n(spec, "cap")
        assert parsed_k == k and len(parsed_of) == n
    else:
        with pytest.raises(ContractError, match="vacuous|unsatisfiable"):
            _validated_k_of_n(spec, "cap")


@SETTINGS
@given(items=st.lists(evidence_ids, min_size=1, max_size=4, unique=True))
def test_a_bare_list_is_never_read_as_k_of_n(items):
    """'How many must hold' is exactly what a reader guesses wrong, so a
    bare sequence is refused instead of being read as 1-of-n."""
    with pytest.raises(ContractError, match="NEVER read as 1-of-n"):
        _validated_k_of_n(tuple(items), "cap")


# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------

@SETTINGS
@given(evidence=evidence_map())
def test_a_prohibited_use_is_never_also_permitted(evidence):
    """The product layer's whole mechanism: losing a quality property moves
    the uses that needed it from permitted to prohibited. A use appearing in
    both lists would make the certificate meaningless."""
    from csia_mission.product import (MissionProductContract,
                                      QualityRequirement, evaluate_product)

    contract = MissionProductContract(
        product_id="p", product_type="inspection",
        qualities=(
            QualityRequirement(property_name="absolute_geolocation",
                               requires_capabilities=("cap",),
                               permits=("survey_grade_measurement",)),
            QualityRequirement(property_name="imagery_quality",
                               requires_capabilities=("cap2",),
                               permits=("visual_assessment",)),
        ))
    caps = evaluate_capabilities(
        [CapabilityContract(capability_id="cap", requires_all=("e0",)),
         CapabilityContract(capability_id="cap2", requires_all=("e1",))],
        evidence, now=50.0)
    result = evaluate_product(contract, evidence, caps, now=50.0)
    assert not (set(result.permitted_uses) & set(result.prohibited_uses)), (
        "a use was reported as both permitted and prohibited")
