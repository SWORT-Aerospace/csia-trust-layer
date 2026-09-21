"""Phase 5 — the hybrid modules' invariants.

Every module in `csia_hybrid` is an ADDITIVE EXPERIMENTAL adapter. These
tests pin the properties that make that claim true: the fast path cannot
attribute, the support layer cannot report a supported attribution without
support, the shadow map does not touch the frozen core, and the capability
record does not claim a Forge integration that does not exist.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
P5 = ROOT / "research" / "phase5"
sys.path.insert(0, str(P5))

from csia_hybrid import baselines as bl                   # noqa: E402
from csia_hybrid import capability as cap                 # noqa: E402
from csia_hybrid import fl029_shadow as shadow            # noqa: E402
from csia_hybrid import multiscale as ms                  # noqa: E402
from csia_hybrid import phase5_partitions as parts5       # noqa: E402
from csia_hybrid.fast_path import (NO_CHANGE,             # noqa: E402
                                   PROVISIONAL_DEGRADATION,
                                   PROVISIONAL_TICKS, SUSPECTED_CHANGE,
                                   VERDICTS, FastAlert, FastChangeDetector)
from csia_hybrid.support_view import (IDENTIFIABLE,       # noqa: E402
                                      NON_IDENTIFIABLE, SUPPORTED,
                                      UNSUPPORTED, SupportTracker,
                                      SupportView)

PREREG = P5 / "PREREGISTRATION_PHASE5.md"


# --- the package's own claims about itself --------------------------------

def test_the_frozen_core_is_untouched():
    baseline = json.loads((ROOT / "docs/v1/FROZEN_BASELINE.json")
                          .read_text(encoding="utf-8"))
    bad = []
    for rel, want in baseline["files"].items():
        want = want if isinstance(want, str) else want["sha256"]
        got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        if got != want:
            bad.append(rel)
    assert bad == [], bad


def test_importing_the_package_pulls_in_no_simulator():
    """`import csia_hybrid` must stay cheap and runtime-free."""
    code = ("import sys, csia_hybrid; "
            "print(any(m.startswith('csia.runtime') or m == 'numpy' "
            "for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False", out.stdout


def test_no_forge_code_was_written():
    """forge/README_FUTURE.md forbids it and this study did not do it."""
    offenders = [p for p in (ROOT / "forge").rglob("*")
                 if p.is_file() and p.suffix not in (".md",)]
    assert offenders == [], offenders
    assert cap.FORGE_COMPATIBILITY_VERIFIED is False


# --- the fast path may not attribute --------------------------------------

def test_the_fast_path_vocabulary_is_closed():
    assert VERDICTS == (NO_CHANGE, SUSPECTED_CHANGE, PROVISIONAL_DEGRADATION)
    with pytest.raises(ValueError, match="vocabulary is closed"):
        FastAlert(t=0.0, detector_id="x", verdict="FAULT_IS_IMU0",
                  statistic=1.0, threshold=1.0, evidence_source="s",
                  freshness=1.0, provenance="p", detector_state="ABOVE",
                  provisional=True)


def test_the_fast_alert_has_no_field_that_could_carry_an_attribution():
    """The field set IS the contract, so a future edit that widens it fails."""
    a = FastChangeDetector(node="vibration", h_fast=5.0).update(0.0, 0.0, 1.0)
    forbidden = {"fault", "source", "hypothesis", "action", "level",
                 "authority", "attribution", "select", "land"}
    assert forbidden.isdisjoint(set(a.as_record()))
    assert a.as_record()["may_attribute"] is False
    assert a.as_record()["has_actuator_authority"] is False


def test_a_gated_tick_is_not_evidence_for_the_fast_path():
    hot = FastChangeDetector(node="vibration", h_fast=5.0)
    for k in range(200):
        hot.update(k * 0.04, 10.0, 0.0)          # gate shut throughout
    assert hot.statistic == 0.0
    live = FastChangeDetector(node="vibration", h_fast=5.0)
    for k in range(200):
        live.update(k * 0.04, 10.0, 1.0)
    assert live.statistic > 5.0


def test_provisional_requires_the_declared_dwell():
    det = FastChangeDetector(node="vibration", h_fast=1.0)
    seen = []
    for k in range(PROVISIONAL_TICKS + 3):
        seen.append(det.update(k * 0.04, 50.0, 1.0).verdict)
    assert seen.count(SUSPECTED_CHANGE) == PROVISIONAL_TICKS - 1
    assert seen[PROVISIONAL_TICKS - 1] == PROVISIONAL_DEGRADATION


def test_the_fast_path_refuses_an_uncovered_node():
    """`IN_CONTROL` covers five nodes and explicitly not the IMUs."""
    with pytest.raises(KeyError, match="imu0"):
        FastChangeDetector(node="imu0", h_fast=5.0)


# --- support may not be claimed without support ---------------------------

def test_a_confident_leader_with_no_active_separating_evidence_is_unsupported():
    """SC-20: a 0.99-weight leader whose separating edges are all shut.

    This combination is reachable and is the entire reason the support layer
    exists. If it ever reports SUPPORTED, the layer has failed at its one job.
    """
    tracker = SupportTracker(low_sets=shadow.current_map(), map_id="current")
    weights = {"redundant_imu": 1.0, "accel_motor_current": 0.0,
               "accel_esc_rpm": 0.0}
    view = tracker.observe(t=1.0, hypotheses=("imu0", "imu1"),
                           weights=weights, freshness={"redundant_imu": 1.0},
                           leader="imu0", leader_weight=0.99)
    assert view.support_status == NON_IDENTIFIABLE
    assert view.attribution_status == UNSUPPORTED
    assert view.leader_weight == 0.99
    assert view.separating_features == ()


def test_a_supported_attribution_without_identifiable_support_cannot_be_built():
    with pytest.raises(ValueError, match="exact combination"):
        SupportView(t=0.0, evidence=_empty_evidence(), hypotheses=("a", "b"),
                    support_status=NON_IDENTIFIABLE,
                    attribution_status=SUPPORTED, leader="a",
                    leader_weight=0.99, separating_features=(),
                    reason="r", provenance="p", map_id="m")


def _empty_evidence():
    from csia_hybrid.support_view import EvidenceView
    return EvidenceView((), (), (), (), ())


def test_withdrawn_evidence_needs_a_memory_and_has_one():
    tracker = SupportTracker(low_sets=shadow.current_map(), map_id="current")
    tracker.observe(t=0.0, hypotheses=("imu0", "imu1"),
                    weights={"accel_motor_current": 1.0}, freshness={})
    view = tracker.observe(t=1.0, hypotheses=("imu0", "imu1"),
                           weights={"accel_motor_current": 0.0}, freshness={})
    assert view.evidence.withdrawn == ("accel_motor_current",)
    assert tracker.evidence_loss_latency("accel_motor_current") == 1.0


def test_an_active_but_unfresh_edge_is_reported_stale_as_well_as_active():
    tracker = SupportTracker(low_sets=shadow.current_map(), map_id="current")
    view = tracker.observe(t=0.0, hypotheses=("imu0", "imu1"),
                           weights={"accel_motor_current": 1.0},
                           freshness={"accel_motor_current": 0.1})
    assert "accel_motor_current" in view.evidence.active
    assert "accel_motor_current" in view.evidence.stale


# --- the FL-029 shadow map ------------------------------------------------

def test_the_shadow_map_changes_only_the_two_imus():
    current, corrected = shadow.current_map(), shadow.corrected_map()
    assert set(current) == set(corrected)
    changed = {k for k in current if current[k] != corrected[k]}
    assert changed == {"imu0", "imu1"}
    assert shadow.MODIFIES_FROZEN_CORE is False


def test_every_added_indicator_carries_a_source_reference():
    refs = shadow.references()
    for source, features in shadow.added_features().items():
        for feature in features:
            assert feature in refs and refs[feature], (source, feature)
            assert "online.py" in refs[feature]
            assert "graph.py" in refs[feature]


def test_the_added_edges_are_ones_the_frozen_core_really_computes():
    """A support claim must rest on an edge that exists, not on a wish."""
    online = (ROOT / "csia/runtime/online.py").read_text(encoding="utf-8")
    for features in shadow.added_features().values():
        for feature in features:
            assert f'"{feature}"' in online, feature


def test_the_correction_grows_the_separating_set_for_the_decision_pair():
    current, corrected = shadow.current_map(), shadow.corrected_map()
    before = shadow.separating_features(current, "imu0", "imu1")
    after = shadow.separating_features(corrected, "imu0", "imu1")
    assert before == {"accel_motor_current", "accel_esc_rpm"}
    assert before < after
    assert after - before == {"velocity_gps_doppler_0",
                              "velocity_gps_doppler_1"}


def test_the_budget_note_says_no_new_sensing():
    note = shadow.budget_note()
    assert "no new sensor" in note and "already computes" in note


# --- multi-timescale ------------------------------------------------------

def test_every_alarm_is_recorded_not_only_the_first():
    """The FL-038 regression.

    An accumulator that fires during trust convergence and again after the
    fault must report BOTH, or the post-onset detection is invisible and the
    detector is scored as having missed everything.
    """
    det = ms.MultiScaleDetector(theta_fast=0.5, dwell_fast=2,
                                theta_medium=0.5, dwell_medium=2,
                                theta_slow=0.5, dwell_slow=2)
    for k in range(10):
        det.update(k * 0.04, 0.0, 1.0)           # early episode
    for k in range(10, 20):
        det.update(k * 0.04, 1.0, 1.0)           # recovery
    for k in range(20, 30):
        det.update(k * 0.04, 0.0, 1.0)           # late episode
    times = det.all_times()["FAST"]
    assert len(times) > 1
    assert min(times) < 0.4 < max(times)
    assert det.combined_times() == sorted(det.combined_times())


def test_the_only_reset_is_structural_loss_of_support():
    assert ms.RESET_REASONS == (ms.RESET_STRUCTURAL_LOSS,)
    acc = ms.Accumulator("x", theta=0.5, dwell=5)
    for _ in range(3):
        acc.update(0.0, 1.0)                     # partial run
    acc.update(0.0, 0.0)                         # gate shuts
    assert acc.resets == 1
    for _ in range(4):
        assert acc.update(0.0, 1.0) is False     # run did not carry across


def test_a_partial_run_below_the_dwell_is_not_an_alarm():
    acc = ms.Accumulator("x", theta=0.5, dwell=5)
    assert not any(acc.update(0.0, 1.0) for _ in range(4))
    assert acc.update(0.0, 1.0) is True


# --- capability -----------------------------------------------------------

def test_degraded_without_supported_attribution_is_unknown_not_ineligible():
    """"Something is wrong and we cannot say what" is not "we know it is bad".

    Collapsing UNKNOWN into INELIGIBLE would let an unsupported suspicion
    read as a confident restriction, which is the error this whole layer
    exists to avoid.
    """
    unsupported = cap.derive(t=1.0, support_status=NON_IDENTIFIABLE,
                             attribution_status=UNSUPPORTED,
                             degraded_sources=("imu0",), map_id="m",
                             provenance="p")
    assert unsupported.states[cap.ATTITUDE_CONTROL] == "UNKNOWN"
    supported = cap.derive(t=1.0, support_status=IDENTIFIABLE,
                           attribution_status=SUPPORTED,
                           degraded_sources=("imu0",), map_id="m",
                           provenance="p")
    assert supported.states[cap.ATTITUDE_CONTROL] == "INELIGIBLE"
    assert supported.limiting[cap.ATTITUDE_CONTROL] == "imu0"


def test_the_capability_record_commands_nothing():
    r = cap.derive(t=1.0, support_status=IDENTIFIABLE,
                   attribution_status=SUPPORTED, degraded_sources=(),
                   map_id="m", provenance="p")
    rec = r.as_record()
    assert rec["has_actuator_authority"] is False
    assert rec["is_experimental"] is True
    assert rec["forge_compatibility_verified"] is False


# --- baselines ------------------------------------------------------------

def test_the_seven_declared_baselines_are_the_ones_the_preregistration_names():
    assert bl.declared_ids() == ("B0", "B1", "B2", "B3", "B4", "B5", "B6")
    text = PREREG.read_text(encoding="utf-8")
    for bid in bl.declared_ids():
        assert f"`{bid}`" in text, bid


def test_the_detector_only_baselines_are_flagged_as_having_no_policy():
    assert bl.DETECTOR_ONLY == ("B1", "B2")
    for bid in bl.DETECTOR_ONLY:
        assert bl.BY_ID[bid].has_policy is False


def test_the_hybrid_downgrades_and_never_abstains():
    """The whole difference from P2, asserted rather than described."""
    class _S:
        t = 30.0
    out = bl.hybrid_decide(_S(), 2, (), pair_supported=False,
                           fast_provisional=False)
    assert out.response != "ABSTAIN"


# --- partitions -----------------------------------------------------------

def test_the_phase5_partition_manifest_is_pinned():
    assert parts5.manifest_hash() == (
        "4659a6a1fed28716b87a319acb01a013b796b3236fcce5dcb6868113423a2a84")


def test_the_locked_partition_refuses_casual_access():
    with pytest.raises(PermissionError, match="locked"):
        parts5.seeds("locked")
    assert len(parts5.seeds(
        "locked", i_am_opening_the_locked_partition=True)) == 40


def test_phase5_seeds_are_disjoint_from_every_earlier_phase():
    from csia_consequence import partitions as p2
    from csia_consequence import phase3_partitions as p3
    from csia_consequence import phase4_partitions as p4
    from csia_consequence import phase31_partitions as p31
    from csia_consequence import phase32_partitions as p32
    ours = {s for v in parts5.PARTITIONS.values() for s in v}
    for mod in (p2, p3, p31, p32, p4):
        theirs = {s for v in mod.PARTITIONS.values() for s in v}
        assert ours.isdisjoint(theirs), mod.__name__
    parts5.assert_disjoint()
    parts5.assert_disjoint_from_earlier_phases()
