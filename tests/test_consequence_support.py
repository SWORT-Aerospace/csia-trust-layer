"""The support classifier: structure, not confidence.

Phase 5 of the consequence preregistration. Evidence level:
DETERMINISTIC_SIMULATION over constructed inputs. Nothing here is a runtime
measurement and nothing here is hardware evidence.
"""
from __future__ import annotations

import pytest

from csia_consequence import support as sup

# A small signature matrix. `nominal` predicts nothing low; each fault
# predicts its own features low. Constructed, not taken from production.
LOW = {
    "nominal": frozenset(),
    "gps_fault": frozenset({"phys_gps", "velocity_gps_doppler_0"}),
    "mag_fault": frozenset({"phys_mag", "heading_course"}),
    "baro_fault": frozenset({"phys_baro", "altitude_baro"}),
}
ALL_FEATURES = sorted(set().union(*LOW.values()))


def _gates(active=(), attenuated=()):
    g = {f: 0.0 for f in ALL_FEATURES}
    for f in active:
        g[f] = 1.0
    for f in attenuated:
        g[f] = 0.2
    return g


def _classify(hyps, gates, **kw):
    return sup.classify(hypotheses=hyps, low_sets=LOW, gates=gates,
                        timestamp_s=1.0, provenance="unit-test", **kw)


# --- the three states -----------------------------------------------------

def test_active_evidence_separating_every_pair_is_identifiable():
    report = _classify(("nominal", "gps_fault", "mag_fault"),
                       _gates(active=("phys_gps", "phys_mag")))
    assert report.status == sup.IDENTIFIABLE
    assert report.reason == sup.R_ALL_PAIRS_SEPARATED
    assert report.unseparated_pairs == ()
    assert report.supports_confident_attribution is True


def test_all_separating_evidence_gated_is_non_identifiable():
    """Self-occlusion: the features that would have separated the pair are
    exactly the ones switched off."""
    report = _classify(("nominal", "gps_fault"), _gates(active=("phys_mag",)))
    assert report.status == sup.NON_IDENTIFIABLE
    assert report.reason == sup.R_ALL_SEPARATING_EVIDENCE_GATED
    assert report.supports_confident_attribution is False


def test_no_active_evidence_at_all_is_its_own_reason():
    """Distinct from self-occlusion: nothing is on, rather than the wrong
    things being off."""
    report = _classify(("nominal", "gps_fault"), _gates())
    assert report.status == sup.NON_IDENTIFIABLE
    assert report.reason == sup.R_NO_ACTIVE_EVIDENCE


def test_partial_separation_is_ambiguous_not_identifiable():
    report = _classify(("nominal", "gps_fault", "mag_fault"),
                       _gates(active=("phys_gps",)))
    assert report.status == sup.AMBIGUOUS
    assert report.reason == sup.R_SOME_PAIRS_UNSEPARATED
    assert report.separated_pairs and report.unseparated_pairs
    assert report.supports_confident_attribution is False


# --- the case the module exists for --------------------------------------

def test_high_confidence_with_no_support_is_non_identifiable():
    """SC-20's shape. Confidence is never consulted; a leader could hold any
    weight and the verdict would not move, because weight is not an input."""
    report = _classify(("nominal", "gps_fault"), _gates(active=("phys_mag",)))
    assert report.status == sup.NON_IDENTIFIABLE
    payload = report.as_dict()
    assert "confidence" not in payload
    assert "weight" not in payload
    assert "posterior" not in payload


def test_a_feature_in_both_low_sets_cannot_separate_them():
    """It contributes an identical term to both log-likelihoods and cancels
    exactly, for every value it can take."""
    low = {"a": frozenset({"shared"}), "b": frozenset({"shared"})}
    assert sup.separating_features(low, "a", "b") == frozenset()
    report = sup.classify(hypotheses=("a", "b"), low_sets=low,
                          gates={"shared": 1.0}, timestamp_s=0.0,
                          provenance="t")
    assert report.status == sup.NON_IDENTIFIABLE


def test_an_attenuated_gate_still_counts_as_active():
    """temp_bias_drift sits at a constant 0.2. Calling that absent would
    overstate ambiguity; the conservative reading is that it contributes."""
    low = {"a": frozenset({"temp_bias_drift"}), "b": frozenset()}
    report = sup.classify(hypotheses=("a", "b"), low_sets=low,
                          gates={"temp_bias_drift": 0.2}, timestamp_s=0.0,
                          provenance="t")
    assert report.status == sup.IDENTIFIABLE
    assert "temp_bias_drift" in report.active_evidence


def test_the_epsilon_is_explicit_and_changes_the_answer():
    low = {"a": frozenset({"f"}), "b": frozenset()}
    gates = {"f": 0.2}
    assert sup.classify(hypotheses=("a", "b"), low_sets=low, gates=gates,
                        timestamp_s=0.0, provenance="t",
                        gate_epsilon=0.0).status == sup.IDENTIFIABLE
    assert sup.classify(hypotheses=("a", "b"), low_sets=low, gates=gates,
                        timestamp_s=0.0, provenance="t",
                        gate_epsilon=0.5).status == sup.NON_IDENTIFIABLE


# --- the awkward inputs ---------------------------------------------------

def test_a_single_hypothesis_is_not_an_identification():
    """A one-hypothesis set trivially 'identifies' its only member. Named as
    its own reason so it can never be counted as a success."""
    report = _classify(("nominal",), _gates(active=("phys_gps",)))
    assert report.status == sup.NON_IDENTIFIABLE
    assert report.reason == sup.R_SINGLE_HYPOTHESIS


def test_an_empty_hypothesis_set_is_refused_not_defaulted():
    report = _classify((), _gates())
    assert report.status == sup.NON_IDENTIFIABLE
    assert report.reason == sup.R_EMPTY_HYPOTHESIS_SET


def test_contradictory_evidence_is_ambiguous_and_names_the_features():
    report = _classify(("nominal", "gps_fault"),
                       _gates(active=("phys_gps",)),
                       contradictory=("phys_gps",))
    assert report.status == sup.AMBIGUOUS
    assert report.reason == sup.R_CONTRADICTORY_EVIDENCE
    assert report.detail["contradictory_features"] == ["phys_gps"]


def test_missing_evidence_is_not_zero_evidence():
    """A feature absent from `gates` entirely is not silently treated as
    active; it simply does not appear in either list."""
    report = sup.classify(hypotheses=("nominal", "gps_fault"), low_sets=LOW,
                          gates={"phys_gps": 1.0}, timestamp_s=0.0,
                          provenance="t")
    assert "velocity_gps_doppler_0" not in report.active_evidence
    assert "velocity_gps_doppler_0" not in report.gated_evidence


def test_correlated_degradation_collapses_support_for_every_affected_pair():
    """Two GPS-derived features gated together removes separation for the
    GPS pair while leaving others intact."""
    report = _classify(("nominal", "gps_fault", "mag_fault"),
                       _gates(active=("phys_mag", "heading_course")))
    assert report.status == sup.AMBIGUOUS
    unsep = {frozenset(p) for p in report.unseparated_pairs}
    assert frozenset({"nominal", "gps_fault"}) in unsep


# --- output contract ------------------------------------------------------

def test_the_report_carries_provenance_and_a_timestamp():
    report = _classify(("nominal", "gps_fault"), _gates(active=("phys_gps",)))
    payload = report.as_dict()
    assert payload["provenance"] == "unit-test"
    assert payload["timestamp_s"] == 1.0
    assert payload["schema"] == "csia.consequence.support/1"


def test_the_report_declares_no_actuator_authority():
    report = _classify(("nominal", "gps_fault"), _gates(active=("phys_gps",)))
    assert report.HAS_ACTUATOR_AUTHORITY is False
    assert report.as_dict()["has_actuator_authority"] is False


def test_a_restriction_is_advisory_and_only_present_when_support_is_absent():
    identifiable = _classify(("nominal", "gps_fault"),
                             _gates(active=("phys_gps",)))
    assert identifiable.recommended_capability_restriction is None
    occluded = _classify(("nominal", "gps_fault"),
                         _gates(active=("phys_mag",)))
    assert occluded.recommended_capability_restriction is not None
    assert "do not act" in occluded.recommended_capability_restriction


def test_unknown_status_or_reason_is_refused():
    with pytest.raises(ValueError, match="unknown support status"):
        sup.SupportReport("PROBABLY_FINE", sup.R_ALL_PAIRS_SEPARATED, (), (),
                          (), (), (), 0.0, "t")
    with pytest.raises(ValueError, match="unknown reason"):
        sup.SupportReport(sup.IDENTIFIABLE, "BECAUSE", (), (), (), (), (),
                          0.0, "t")


def test_classification_is_deterministic():
    a = _classify(("nominal", "gps_fault", "mag_fault"),
                  _gates(active=("phys_gps",))).as_dict()
    b = _classify(("nominal", "gps_fault", "mag_fault"),
                  _gates(active=("phys_gps",))).as_dict()
    assert a == b


def test_the_module_imports_no_frozen_core_module():
    import ast
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "csia_consequence/support.py").read_text())
    for node in ast.walk(tree):
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module or ""] if isinstance(node, ast.ImportFrom)
                 else [])
        for name in names:
            assert not name.startswith("csia."), f"imports frozen path {name}"
