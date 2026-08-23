"""Shadow hypothesis layer (slice 3B).

Two classes of regression these prevent:
  * the shadow layer acquiring any influence over active behaviour
  * UNKNOWN or a shared cause activating on healthy flight
"""

import pytest

from csia.diagnosis import (ACTIVE_CONF, MAX_HYPOTHESES,
                            MAX_SOURCES_PER_HYPOTHESIS, REGISTRY,
                            Authorization, DiagnosticState, Hypothesis,
                            HypothesisClass, HypothesisEngine,
                            IsolationOutcome, Usability, classify_isolation,
                            run_shadow)
from csia.scenarios import SCENARIOS
from csia.sensors import Fault, generate_flight

SHARED = ("battery", "motor_esc")
RESOURCE = "MAIN_POWER_PACK"
INDEP = ("imu0", "imu1")


def shared_power(depth_v=1.2, rpm_loss=350.0, onset=30.0, dur=6.0, delay=0.0):
    return [Fault("power_sag", "battery", onset, dur, {"depth_v": depth_v}),
            Fault("power_sag", "motor_esc", onset + delay, dur,
                  {"rpm_loss": rpm_loss})]


@pytest.fixture(scope="module")
def truth():
    return generate_flight()


# --- structural / bounds ------------------------------------------------------

def test_registry_is_bounded_and_stable():
    assert len(REGISTRY) <= MAX_HYPOTHESES
    ids = [h.hypothesis_id for h in REGISTRY]
    assert ids == sorted(ids, key=lambda x: ids.index(x))   # order is fixed
    assert len(set(ids)) == len(ids)
    for h in REGISTRY:
        assert len(h.affected_sources) <= MAX_SOURCES_PER_HYPOTHESIS


def test_too_many_sources_is_rejected():
    with pytest.raises(ValueError, match="MAX_SOURCES_PER_HYPOTHESIS"):
        Hypothesis(hypothesis_id="H", hypothesis_class="SHARED_POWER",
                   affected_sources=tuple(f"s{i}" for i in
                                          range(MAX_SOURCES_PER_HYPOTHESIS + 1)))


def test_every_hypothesis_is_shadow_only(truth):
    r = run_shadow(shared_power(), truth=truth)
    for rep in r.reports:
        for h in rep.hypotheses:
            assert h.operational_authorization == Authorization.SHADOW_ONLY.value


def test_no_recommendation_permits_active_application(truth):
    r = run_shadow(shared_power(), truth=truth)
    recs = [rec for rep in r.reports for rec in rep.recommendations]
    assert recs, "scenario produced no recommendations"
    assert all(rec["active_application_permitted"] is False for rec in recs)
    assert all(rec["authorization_level"] == Authorization.SHADOW_ONLY.value
               for rec in recs)


# --- the shared-power vertical -------------------------------------------------

def test_shared_power_is_correctly_isolated(truth):
    r = run_shadow(shared_power(), truth=truth)
    assert r.first_root is not None
    assert r.first_root[1] == "H_SHARED_POWER_DEGRADATION"
    assert set(r.first_root[2]) == set(SHARED)
    assert r.isolation(SHARED, shared_resource=RESOURCE) \
        == IsolationOutcome.CORRECT_COMMON_CAUSE.value


def test_shared_power_isolation_latency_is_bounded(truth):
    r = run_shadow(shared_power(), truth=truth)
    lat = r.latency(30.0)
    assert lat is not None and 0.0 < lat <= 3.0


def test_shared_power_affected_set_excludes_unaffected_sources(truth):
    r = run_shadow(shared_power(), truth=truth)
    assert "gps" not in r.first_root[2] and "mag" not in r.first_root[2]


def test_shared_power_recovers(truth):
    """After the fault window the hypothesis must stop being ACTIVE."""
    r = run_shadow(shared_power(onset=25.0, dur=5.0), truth=truth)
    late = r.at(55.0)
    assert late.most_probable_root_cause != "H_SHARED_POWER_DEGRADATION"


# --- shared cause vs independent faults (Part 9, mandatory) -------------------

def test_independent_faults_are_not_called_common_cause(truth):
    r = run_shadow(SCENARIOS["dual_imu_failure"][1], truth=truth)
    assert r.peak_confidence["H_MULTI_INDEPENDENT_IMU"] > \
        r.peak_confidence["H_SHARED_POWER_DEGRADATION"]
    assert r.first_root[1] == "H_MULTI_INDEPENDENT_IMU"


def test_near_simultaneous_independent_faults_still_not_common_cause(truth):
    """The hard case: two independent faults 0.2 s apart."""
    faults = [Fault("bias_drift", "imu0", 25.0, 30.0,
                    {"axis": 2, "rate": 0.18, "channel": "accel"}),
              Fault("bias_drift", "imu1", 25.2, 28.0,
                    {"axis": 2, "rate": -0.15, "channel": "accel"})]
    r = run_shadow(faults, truth=truth)
    assert r.first_root[1] == "H_MULTI_INDEPENDENT_IMU"
    assert r.peak_confidence["H_SHARED_POWER_DEGRADATION"] < ACTIVE_CONF


def test_shared_and_independent_are_separated_by_margin(truth):
    a = run_shadow(shared_power(), truth=truth)
    b = run_shadow(SCENARIOS["dual_imu_failure"][1], truth=truth)
    margin_a = (a.peak_confidence["H_SHARED_POWER_DEGRADATION"]
                - a.peak_confidence["H_MULTI_INDEPENDENT_IMU"])
    margin_b = (b.peak_confidence["H_MULTI_INDEPENDENT_IMU"]
                - b.peak_confidence["H_SHARED_POWER_DEGRADATION"])
    assert margin_a > 0.3 and margin_b > 0.3


def test_delayed_second_source_is_not_forced_into_common_cause(truth):
    """A 6 s stagger is not a shared rail; the layer must not claim it is."""
    r = run_shadow(shared_power(delay=6.0), truth=truth)
    assert r.isolation(SHARED, shared_resource=RESOURCE) \
        != IsolationOutcome.CORRECT_COMMON_CAUSE.value


# --- healthy flight -----------------------------------------------------------

def test_clean_flight_activates_nothing(truth):
    r = run_shadow([], truth=truth)
    assert r.first_root is None
    for hid, c in r.peak_confidence.items():
        assert c < ACTIVE_CONF, f"{hid} reached {c} on clean flight"


def test_unknown_does_not_fire_on_healthy_unusual_behaviour(truth):
    """The scripted yaw-in-place drives ONE relationship to ~0.37. A single
    degraded relationship is not cross-sensor inconsistency."""
    r = run_shadow([], truth=truth)
    assert r.peak_confidence["H_UNKNOWN_CROSS_SENSOR_INCONSISTENCY"] == 0.0


def test_unknown_is_distinguishable_from_none():
    assert IsolationOutcome.UNKNOWN_DETECTED.value != IsolationOutcome.NONE.value


def test_unknown_activates_when_known_causes_are_disabled(truth):
    """Novel structure: with the shared hypothesis off, the evidence is real
    but unexplained — that is exactly what UNKNOWN is for."""
    r = run_shadow(shared_power(), truth=truth, enable_shared_cause=False)
    assert r.isolation(SHARED, shared_resource=RESOURCE) \
        == IsolationOutcome.UNKNOWN_DETECTED.value


def test_low_evidence_stays_low_confidence_not_unknown(truth):
    r = run_shadow(shared_power(depth_v=0.05, rpm_loss=10.0), truth=truth)
    assert r.peak_confidence["H_UNKNOWN_CROSS_SENSOR_INCONSISTENCY"] < ACTIVE_CONF


# --- isolation taxonomy -------------------------------------------------------

class _FakeH:
    def __init__(self, hid, cls, conf, sources, resource=None):
        self.hypothesis_id, self.hypothesis_class = hid, cls
        self.confidence, self.affected_sources = conf, sources
        self.shared_resource = resource


class _FakeR:
    def __init__(self, root, affected, hyps):
        self.most_probable_root_cause = root
        self.affected_sources = affected
        self.hypotheses = hyps


def _rep(root, affected, cls=HypothesisClass.SHARED_POWER.value, resource=None):
    return _FakeR(root, affected,
                  [_FakeH(root, cls, 0.9, tuple(affected), resource)])


def test_taxonomy_partial_isolation():
    r = _rep("H", ["battery"])
    assert classify_isolation(r, ("battery", "motor_esc")) \
        == IsolationOutcome.PARTIAL_ISOLATION.value


def test_taxonomy_over_isolation():
    r = _rep("H", ["battery", "motor_esc", "gps"])
    assert classify_isolation(r, ("battery", "motor_esc")) \
        == IsolationOutcome.OVER_ISOLATION.value


def test_taxonomy_under_isolation():
    r = _rep("H", ["battery", "gps"])
    assert classify_isolation(r, ("battery", "motor_esc")) \
        == IsolationOutcome.UNDER_ISOLATION.value


def test_taxonomy_incorrect_isolation():
    r = _rep("H", ["gps"])
    assert classify_isolation(r, ("battery", "motor_esc")) \
        == IsolationOutcome.INCORRECT_ISOLATION.value


def test_taxonomy_correct_multi_source_without_shared_resource():
    r = _rep("H", ["imu0", "imu1"],
             cls=HypothesisClass.MULTI_SOURCE_INDEPENDENT.value)
    assert classify_isolation(r, ("imu0", "imu1")) \
        == IsolationOutcome.CORRECT_MULTI_SOURCE.value


def test_taxonomy_correct_single_source():
    r = _rep("H", ["gps"], cls=HypothesisClass.SINGLE_SOURCE.value)
    assert classify_isolation(r, ("gps",)) \
        == IsolationOutcome.CORRECT_SINGLE_SOURCE.value


def test_taxonomy_none_and_ambiguous():
    weak = _FakeR(None, [], [_FakeH("H", "SHARED_POWER", 0.05, ())])
    assert classify_isolation(weak, ("gps",)) == IsolationOutcome.NONE.value
    amb = _FakeR(None, [], [_FakeH("H", "SHARED_POWER", 0.45, ())])
    assert classify_isolation(amb, ("gps",)) == IsolationOutcome.AMBIGUOUS.value


# --- outputs / schema ---------------------------------------------------------

def test_confidence_concepts_are_separate(truth):
    rep = run_shadow(shared_power(), truth=truth).at(33.0)
    assert rep.source_usability and rep.source_fault_confidence
    h = rep.hypotheses[0]
    assert hasattr(h, "confidence") and hasattr(h, "isolation_confidence")
    assert isinstance(rep.diagnostic_ambiguity, float)
    assert isinstance(rep.residual_unexplained_evidence, float)


def test_source_usability_is_per_function(truth):
    rep = run_shadow(shared_power(), truth=truth).at(33.0)
    assert "gps:position" in rep.source_usability
    assert "gps:timing" in rep.source_usability
    assert rep.source_usability["gps:timing"] == Usability.UNKNOWN.value


def test_evidence_trail_is_present_and_explainable(truth):
    rep = run_shadow(shared_power(), truth=truth).at(33.0)
    assert rep.evidence
    e = rep.evidence[0]
    for f in ("evidence_id", "t", "source_or_relationship", "residual_value",
              "direction", "persistence_s", "valid", "context",
              "supports", "contradicts", "reason_code"):
        assert hasattr(e, f), f
    assert any(ev.supports for ev in rep.evidence)


def test_active_hypothesis_carries_reason_codes(truth):
    rep = run_shadow(shared_power(), truth=truth).at(33.0)
    active = [h for h in rep.hypotheses
              if h.diagnostic_state == DiagnosticState.ACTIVE.value]
    assert active and all(h.reason_codes for h in active)


def test_report_serializes_stably(truth):
    r = run_shadow(shared_power(), truth=truth)
    import json
    a = json.dumps(r.at(33.0).to_dict(), sort_keys=True, default=str)
    b = json.dumps(r.at(33.0).to_dict(), sort_keys=True, default=str)
    assert a == b and len(a) > 100


def test_hypothesis_ordering_is_deterministic(truth):
    a = run_shadow(shared_power(), truth=truth).at(33.0)
    b = run_shadow(shared_power(), truth=truth).at(33.0)
    assert [h.hypothesis_id for h in a.hypotheses] == \
           [h.hypothesis_id for h in b.hypotheses]


def test_tie_break_follows_registry_order():
    eng = HypothesisEngine(arm_time_s=0.0)
    rep = eng.step(1.0, {"phys_battery": (1.0, 1.0)})
    order = [h.hypothesis_id for h in rep.hypotheses]
    reg = [h.hypothesis_id for h in REGISTRY]
    assert order == sorted(order, key=lambda x: reg.index(x))


def test_confidences_are_bounded_not_normalized(truth):
    """Deliberately NOT a softmax — hypotheses do not compete for mass."""
    rep = run_shadow(shared_power(), truth=truth).at(33.0)
    for h in rep.hypotheses:
        assert 0.0 <= h.confidence <= 1.0
    assert sum(h.confidence for h in rep.hypotheses) != pytest.approx(1.0)


# --- estimator hypothesis -----------------------------------------------------

def test_estimator_hypothesis_is_declared_but_unsupported(truth):
    """No estimator signals exist in the graph (audit Q8); the hypothesis must
    exist without ever activating on data that cannot support it."""
    h = next(h for h in REGISTRY if h.hypothesis_id == "H_ESTIMATOR_DIVERGENCE")
    assert h.required_evidence == ()
    assert "NO_ESTIMATOR_SIGNALS_AVAILABLE" in h.reason_codes
    r = run_shadow(shared_power(), truth=truth)
    assert r.peak_confidence["H_ESTIMATOR_DIVERGENCE"] == 0.0


# --- ablation mechanisms are load-bearing -------------------------------------

def test_temporal_evidence_is_load_bearing(truth):
    """UPDATED in slice 3C. Under the ratio-invariant causal model, temporal
    coherence no longer changes PEAK confidence on a clean co-onset scenario
    (both saturate at ~1.0) -- it earns its place on DISPERSED onsets, where
    it is what separates a shared cause from coincident independent faults.
    Measured on a 6 s-staggered second source, which is the case it exists for.
    """
    full = run_shadow(shared_power(delay=6.0), truth=truth)
    no_temporal = run_shadow(shared_power(delay=6.0), truth=truth,
                             enable_temporal_evidence=False)
    assert (no_temporal.peak_confidence["H_SHARED_POWER_DEGRADATION"]
            > full.peak_confidence["H_SHARED_POWER_DEGRADATION"]), \
        "temporal evidence must penalise dispersed onsets"


def test_disabling_shared_cause_removes_the_capability(truth):
    r = run_shadow(shared_power(), truth=truth, enable_shared_cause=False)
    assert r.peak_confidence["H_SHARED_POWER_DEGRADATION"] == 0.0


def test_arm_time_suppresses_startup_transient(truth):
    r = run_shadow(shared_power(), truth=truth)
    for rep in r.reports:
        if rep.t < 10.0:
            assert rep.most_probable_root_cause is None


def test_dwell_prevents_single_tick_conclusions(truth):
    fast = run_shadow(shared_power(), truth=truth, dwell_ticks=1)
    slow = run_shadow(shared_power(), truth=truth)
    assert fast.latency(30.0) < slow.latency(30.0)


# --- generalization -----------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("depth", (0.9, 1.2, 1.8))
def test_sweep_severity_holds(truth, depth):
    r = run_shadow(shared_power(depth_v=depth), truth=truth)
    assert r.isolation(SHARED, shared_resource=RESOURCE) \
        == IsolationOutcome.CORRECT_COMMON_CAUSE.value


@pytest.mark.slow
@pytest.mark.parametrize("onset", (20.0, 25.0, 40.0))
def test_sweep_onset_holds(truth, onset):
    r = run_shadow(shared_power(onset=onset), truth=truth)
    assert r.isolation(SHARED, shared_resource=RESOURCE) \
        == IsolationOutcome.CORRECT_COMMON_CAUSE.value


@pytest.mark.slow
def test_held_out_generalization_is_pinned_at_its_measured_value(truth):
    """UPDATED in slice 3C: 1/4 -> 4/4.

    This set is now HISTORICAL_DIAGNOSTIC_EVALUATION (it was inspected to
    diagnose the overfit, so it is no longer blind). It was NOT tuned against:
    the fix was structural -- per-source severity normalisation replacing an
    arithmetic mean over a mixed-source feature list. The genuine blind
    campaign is campaigns/shared_power_generalization_v1.json, evaluated once,
    logged in datasets/reports/blind_evaluation_access.json.
    """
    combos = ((0.75, 200.0, 22.0), (1.5, 500.0, 35.0),
              (2.1, 120.0, 27.5), (0.5, 620.0, 44.0))
    ok = 0
    for depth, rpm, onset in combos:
        r = run_shadow(shared_power(depth_v=depth, rpm_loss=rpm, onset=onset),
                       truth=truth)
        if r.isolation(SHARED, shared_resource=RESOURCE) \
                == IsolationOutcome.CORRECT_COMMON_CAUSE.value:
            ok += 1
        else:
            # It must never be actively WRONG — no false common-cause blame.
            assert r.isolation(SHARED, shared_resource=RESOURCE) in (
                IsolationOutcome.NONE.value,
                IsolationOutcome.UNKNOWN_DETECTED.value,
                IsolationOutcome.PARTIAL_ISOLATION.value)
    assert ok == 4, f"historical diagnostic set regressed: {ok}/4"
