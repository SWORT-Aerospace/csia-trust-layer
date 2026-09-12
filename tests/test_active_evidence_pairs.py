"""The model bank, the signature bank, and the campaign that rejected H2.

The load-bearing tests here are the ones that keep a NEGATIVE result
negative. It would be very easy for a later change to make active probing
look good again by widening an envelope, dropping a scale, or quietly
letting an ineligible relation contribute.
"""

from __future__ import annotations

import inspect
import json
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import hypotheses as HY                # noqa: E402
from csia_active_evidence import identifiability as ID           # noqa: E402
from csia_active_evidence import probes as PR                    # noqa: E402
from csia_active_evidence import selector as SE                  # noqa: E402
from csia_active_evidence import signatures as SG                # noqa: E402
from csia_components import residuals as R                       # noqa: E402
from csia_components import simulate as S                        # noqa: E402

ARTIFACT = os.path.join(ROOT, "research", "active_evidence", "results",
                        "AEA_PAIR_CAMPAIGN.json")


@pytest.fixture(scope="module")
def doc():
    with open(ARTIFACT, encoding="utf-8") as fh:
        return json.load(fh)


# --- the bank ---------------------------------------------------------------

def test_every_bank_entry_is_producible_by_this_simulator():
    for h in HY.BANK:
        if h.kind == HY.NOMINAL:
            continue
        assert h.kind in S.FAULT_KINDS, h.name
        assert h.kind in S.APPLICABLE[h.target], (h.name, h.target)


def test_a_bank_entry_the_plant_cannot_produce_is_refused():
    with pytest.raises(ValueError, match="applicability matrix"):
        HY.FaultHypothesis(name="x", kind="pack_impedance_rise",
                           target="cpu", magnitudes=(0.1,), units="ohm",
                           basis="impossible")
    with pytest.raises(ValueError, match="not a fault kind"):
        HY.FaultHypothesis(name="x", kind="gremlins", target="pack",
                           magnitudes=(0.1,), units="-", basis="impossible")


def test_the_sentinel_is_not_a_member_of_the_bank():
    """It must never be selectable, scoreable or separable."""
    assert HY.UNKNOWN not in HY.BY_NAME
    assert all(h.name != HY.UNKNOWN for h in HY.BANK)
    assert all(HY.UNKNOWN not in pair for pair in HY.pairs())
    with pytest.raises(KeyError):
        HY.hypothesis(HY.UNKNOWN)


def test_the_pair_denominator_is_fixed_before_measurement(doc):
    n = len(HY.BANK)
    assert len(HY.pairs()) == n * (n - 1) // 2
    assert doc["pairs_total"] == len(HY.pairs())


def test_the_unmodelled_fault_is_genuinely_outside_the_bank():
    faults = HY.unmodelled_fault(1.0, 10.0)
    assert len(faults) == 1
    f = faults[0]
    assert not any(h.kind == f.kind and h.target == f.target
                   for h in HY.BANK), "the open-set control is inside the bank"


# --- lineage and scales -----------------------------------------------------

def test_every_residual_has_a_channel_map_and_a_scale():
    assert set(SG.CHANNELS) == set(R.RESIDUALS)
    assert set(SG.SCALES) == set(SG.CHANNELS)
    for name, (scale, basis) in SG.SCALES.items():
        assert scale > 0.0, f"{name} has a zero scale; any difference at all "\
                            f"would then count as a separation"
        assert len(basis) > 25, name


def test_residuals_sharing_a_raw_channel_are_one_family():
    fams = SG.independent_families(["power_balance", "source_impedance",
                                    "charge_accounting", "error_rate"])
    joined = [f for f in fams if len(f) > 1]
    assert joined and set(joined[0]) == {"charge_accounting",
                                         "power_balance", "source_impedance"}
    assert ("error_rate",) in fams


def test_a_zero_width_envelope_cannot_separate_on_a_hairline():
    """THE DEFECT THE FIRST PILOT RAN INTO. Two deterministic residuals
    differing by 1e-17 must not count as separated."""
    a = {"effort_drift": SG.Envelope(0.0, 0.0, 5, True)}
    b = {"effort_drift": SG.Envelope(1e-17, 1e-17, 5, True)}
    assert SG.separating_residuals(a, b) == ()
    big = {"effort_drift": SG.Envelope(0.5, 0.5, 5, True)}
    assert SG.separating_residuals(a, big) == ("effort_drift",)


def test_an_ineligible_relation_cannot_contribute_a_separation():
    """Control 8 of the twelve, enforced in the code rather than audited."""
    a = {"effort_drift": SG.Envelope(0.0, 0.0, 5, True)}
    b = {"effort_drift": SG.Envelope(0.5, 0.5, 5, False)}
    assert SG.separating_residuals(a, b) == ()


def test_a_raising_residual_is_recorded_as_gated_shut_not_as_zero():
    """MX-021 was a swallowed exception that read as 'not detected'."""
    src = inspect.getsource(SG.signature)
    assert 'values[name] = float("nan")' in src
    assert "gates[name] = 0.0" in src
    assert '__error' in src, "the exception is discarded rather than recorded"


# --- the selector defect the campaign found ---------------------------------

def test_the_selector_reads_the_gate_threshold_from_the_residual():
    """Read, never copied. A copied number drifts from its source."""
    assert SE.gate_threshold() == inspect.signature(
        R.source_impedance).parameters["min_current_sd"].default


def test_a_probe_that_cannot_open_the_relation_gate_is_rejected():
    """THE DEFECT: the selected probe was once the WORST arm of five,
    because it closed effort_drift without opening source_impedance."""
    noise = ID.NoiseModel(sigma_v=0.0200, sigma_i=0.0786,
                          ocv_drift_v_per_s=0.0046)
    req = ID.probe_requirement(0.020, noise, S.PACK_R_NOMINAL)
    soft = PR.probe("triangle_soft")
    assert req.met_by(soft.stats())["met"] is True, (
        "the error model no longer accepts triangle_soft, so this test no "
        "longer exercises the disagreement it was written for")
    assert soft.stats().std_i < SE.gate_threshold()

    sel = SE.select(req)
    assert sel.probe_name != "triangle_soft"
    rejected = {r["probe"]: r["failed"] for r in sel.rejected}
    assert "relation_gate" in rejected["triangle_soft"]


def test_the_gate_condition_can_be_switched_off_and_changes_the_answer():
    """Anti-vacuity: if it made no difference it would not be a condition."""
    noise = ID.NoiseModel(sigma_v=0.0200, sigma_i=0.0786,
                          ocv_drift_v_per_s=0.0046)
    req = ID.probe_requirement(0.020, noise, S.PACK_R_NOMINAL)
    with_gate = SE.select(req).probe_name
    without = SE.select(req, respect_relation_gate=False).probe_name
    assert with_gate != without, (with_gate, without)


# --- the negative result, pinned --------------------------------------------

def test_the_campaign_controls_pass():
    from tools.assurance.instrument_controls import guard
    from tools.research import aea_pair_campaign as V
    V._controls()
    assert guard(V.INSTRUMENT)["verdict"] == "PASS"


def test_a_steady_hover_never_separates_nominal_from_pack_impedance(doc):
    """H1, the anchor. It must hold at EVERY magnitude in the bracket, or
    the premise of the whole package is wrong."""
    passive = doc["results"]["passive"]["by_magnitude"]
    for mi, row in passive.items():
        assert "nominal|pack_impedance" in row["unresolved"], mi


def test_every_active_arm_resolves_that_pair_at_the_top_of_the_bracket(doc):
    """The other half of H1: the pair is not inseparable in principle, only
    inseparable at a constant load."""
    for arm in doc["arms"]:
        if arm == "passive":
            continue
        top = doc["results"][arm]["by_magnitude"]["2"]["unresolved"]
        assert "nominal|pack_impedance" not in top, arm


def test_probing_costs_a_relation_and_the_artifact_says_which(doc):
    """THE MECHANISM. Every active arm trades effort_drift for
    source_impedance, exactly."""
    for arm, c in doc["comparison_against_passive"].items():
        assert c["relations_the_action_made_INELIGIBLE"] == ["effort_drift"], arm
        assert c["relations_the_action_made_eligible"] == ["source_impedance"], arm


def test_active_probing_is_a_net_loss_over_the_bracket(doc):
    """H2 REJECTED. If this ever passes, the result changed and RESULTS.md
    must be rewritten rather than this test relaxed."""
    assert doc["verdict"] == "ACTIVE_PROBING_NOT_SUPPORTED_ON_THIS_GRID"
    for arm, c in doc["comparison_against_passive"].items():
        assert c["pairs_resolved_over_passive_across_bracket"] < 0, arm
        assert c["worse_than_passive_at_some_magnitude"] is True, arm


def test_a_free_mission_manoeuvre_matches_the_selected_probe(doc):
    """H5 REJECTED, and the falsifier the preregistration named."""
    assert doc["falsifiers"][
        "a_free_mission_manoeuvre_matches_the_selected_probe"] is True
    opp = doc["results"]["opportunistic"]
    sel = doc["results"]["selected"]
    assert opp["incremental_energy_as"] == 0.0
    assert sel["incremental_energy_as"] > 0.0
    assert opp["total_unresolved_over_bracket"] <= sel[
        "total_unresolved_over_bracket"]


def test_the_sophisticated_selector_beats_neither_fixed_nor_random(doc):
    for arm in ("fixed", "random_safe"):
        assert doc["falsifiers"][f"selected_does_not_beat_{arm}"] is True


def test_every_active_arm_has_the_same_effect_at_very_different_cost(doc):
    """The sharpest single number in the campaign: identical outcomes,
    costs spanning zero to several amp-seconds."""
    active = [a for a in doc["arms"] if a != "passive"]
    totals = {doc["results"][a]["total_unresolved_over_bracket"]
              for a in active}
    assert len(totals) == 1, totals
    costs = [doc["results"][a]["incremental_energy_as"] for a in active]
    assert min(costs) == 0.0 and max(costs) > 3.0, costs


def test_no_arm_forced_an_unmodelled_fault_into_a_label(doc):
    """H4 SUPPORTED. Abstention integrity is the one thing that held."""
    assert doc["falsifiers"][
        "any_arm_falsely_attributed_an_unmodelled_fault"] is False
    for arm in doc["arms"]:
        o = doc["results"][arm]["open_set"]
        assert o["false_attribution"] is False, arm
        assert len(o["hypotheses_still_consistent"]) >= 2, arm


def test_the_artifact_says_its_envelope_is_not_a_confidence_interval(doc):
    assert "OPTIMISTIC" in doc["the_envelope_is_not_a_confidence_interval"]
    assert "not a bound" in doc["the_envelope_is_not_a_confidence_interval"]
    assert "E0" in doc["what_this_is_not"]
