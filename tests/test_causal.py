"""Ratio-invariant causal shared-cause reasoning (slice 3C).

The regression these prevent: re-encoding one voltage-to-RPM amplitude
relationship into the shared-cause statistic.
"""
import json
import os

import pytest

from csia.diagnosis import IsolationOutcome, run_shadow
from csia.diagnosis.causal import (RESOURCE_TOPOLOGY, SOURCE_INDICATORS,
                                   CausalSharedCauseModel, normalize_severity,
                                   temporal_coherence)
from csia.sensors import Fault, generate_flight

RESOURCE = "MAIN_POWER_PACK"
TRUTH = ("battery", "motor_esc")
ROOT = os.path.join(os.path.dirname(__file__), "..")


def sp(depth=1.2, rpm=350.0, onset=30.0, dur=6.0, delay=0.0):
    f = []
    if depth > 0:
        f.append(Fault("power_sag", "battery", onset, dur, {"depth_v": depth}))
    if rpm > 0:
        f.append(Fault("power_sag", "motor_esc", onset + delay, dur,
                       {"rpm_loss": rpm}))
    return f


@pytest.fixture(scope="module")
def truth():
    return generate_flight()


# --- severity normalization ---------------------------------------------------

def test_severity_is_monotonic_and_bounded():
    vals = [normalize_severity(c) for c in (0.0, 0.2, 0.5, 0.7, 0.9, 1.0)]
    assert all(0.0 <= v <= 1.0 for v in vals)
    assert vals == sorted(vals, reverse=True)


def test_temporal_coherence_is_monotonic_not_a_step():
    a, b, c = (temporal_coherence([0.0, 0.5]), temporal_coherence([0.0, 5.0]),
               temporal_coherence([0.0, 20.0]))
    assert a == 1.0 and c == 0.0 and 0.0 < b < 1.0
    # one extra sample of skew must not flip the answer
    assert abs(temporal_coherence([0.0, 5.0]) -
               temporal_coherence([0.0, 5.04])) < 0.02


def test_temporal_needs_two_onsets():
    assert temporal_coherence([1.0]) == 0.0 and temporal_coherence([]) == 0.0


# --- ratio invariance (the point of the slice) --------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("depth,rpm", [
    (1.2, 350.0),    # development ratio
    (0.75, 200.0),   # historical failure
    (1.5, 500.0),
    (0.5, 620.0),    # inverse: weak battery, strong motor
    (2.1, 260.0),    # strong battery, moderate motor
])
def test_shared_power_is_ratio_invariant(truth, depth, rpm):
    r = run_shadow(sp(depth, rpm), truth=truth)
    assert r.isolation(TRUTH, shared_resource=RESOURCE) \
        == IsolationOutcome.CORRECT_COMMON_CAUSE.value


@pytest.mark.slow
def test_extreme_ratios_do_not_produce_false_common_cause(truth):
    """Below the motor observability floor the layer must NOT claim a shared
    cause -- reporting less is correct, blaming wrongly is not."""
    r = run_shadow(sp(1.2, 100.0), truth=truth)
    assert r.isolation(TRUTH, shared_resource=RESOURCE) \
        != IsolationOutcome.INCORRECT_ISOLATION.value


# --- negatives ----------------------------------------------------------------

@pytest.mark.slow
def test_battery_only_is_not_common_cause(truth):
    r = run_shadow(sp(1.4, 0.0), truth=truth)
    assert not (r.first_root == "H_SHARED_POWER_DEGRADATION")


@pytest.mark.slow
def test_motor_only_is_not_common_cause(truth):
    r = run_shadow(sp(0.0, 400.0), truth=truth)
    assert r.peak_confidence["H_SHARED_POWER_DEGRADATION"] < 0.60


@pytest.mark.slow
def test_clean_flight_never_activates_shared_cause(truth):
    r = run_shadow([], truth=truth)
    assert r.peak_confidence["H_SHARED_POWER_DEGRADATION"] == 0.0


# --- topology is load-bearing --------------------------------------------------

def test_topology_is_actually_consulted():
    """Slice 3B's topology was data with no reader. It must now be read."""
    assert RESOURCE in RESOURCE_TOPOLOGY
    assert set(RESOURCE_TOPOLOGY[RESOURCE]) >= {"battery", "motor_esc"}
    m = CausalSharedCauseModel()
    assert m.topology is RESOURCE_TOPOLOGY or m.topology == RESOURCE_TOPOLOGY


@pytest.mark.slow
def test_disabling_topology_changes_the_result(truth):
    full = run_shadow(sp(), truth=truth)
    off = run_shadow(sp(), truth=truth, enable_topology_evidence=False)
    assert (full.peak_confidence["H_SHARED_POWER_DEGRADATION"]
            != off.peak_confidence["H_SHARED_POWER_DEGRADATION"])


@pytest.mark.slow
def test_healthy_strongly_coupled_member_contradicts(truth):
    """battery-only: motor_esc is strongly coupled and healthy -> contradiction."""
    m = CausalSharedCauseModel()
    from csia.diagnosis.shadow import features_over_time
    from csia.prediction import PredictionComparator
    from csia.scenarios import sample_streams
    td = PredictionComparator(tick_hz=25.0).build(
        sample_streams(truth, sp(1.4, 0.0)), 60.0)
    fe = features_over_time(td)
    seen = False
    for k in range(len(td.t)):
        tick = {n: (float(c[k]), float(g[k])) for n, (c, g) in fe.items()}
        a = m.assess(float(td.t[k]), tick, RESOURCE)
        if a.healthy_strong_members:
            seen = True
    assert seen


def test_non_diagnostic_indicator_excluded_from_support():
    """accel_motor_current measured 0.000 in every case (audit D-2)."""
    from csia.diagnosis.causal import NON_DIAGNOSTIC_FOR_POWER
    assert "accel_motor_current" in NON_DIAGNOSTIC_FOR_POWER


def test_per_source_indicators_do_not_mix_sources():
    """The root cause of the overfit: a statistic spanning two sources."""
    assert set(SOURCE_INDICATORS["battery"]).isdisjoint(
        SOURCE_INDICATORS["motor_esc"])


# --- determinism ---------------------------------------------------------------

@pytest.mark.slow
def test_repeated_execution_is_deterministic(truth):
    a = run_shadow(sp(), truth=truth)
    b = run_shadow(sp(), truth=truth)
    assert a.peak_confidence == b.peak_confidence
    assert a.first_root == b.first_root


# --- campaign integrity --------------------------------------------------------

CAMPAIGN = os.path.join(ROOT, "campaigns", "shared_power_generalization_v1.json")


@pytest.mark.skipif(not os.path.exists(CAMPAIGN), reason="campaign absent")
class TestCampaign:
    def load(self):
        with open(CAMPAIGN) as fh:
            return json.load(fh)

    def test_partition_assignment_is_deterministic(self):
        import hashlib
        c = self.load()
        for r in c["scenarios"]:
            h = hashlib.sha256(
                f"{c['campaign_seed']}:{r['scenario_id']}".encode()).hexdigest()
            assert h == r["scenario_sha256"]

    def test_no_parameter_tuple_crosses_partitions(self):
        seen = {}
        for r in self.load()["scenarios"]:
            key = (r["family"], json.dumps(r["params"], sort_keys=True))
            assert seen.setdefault(key, r["dataset_partition"]) \
                == r["dataset_partition"]

    def test_every_partition_has_positives_and_negatives(self):
        c = self.load()
        for part in ("DEVELOPMENT", "VALIDATION", "BLIND_SYNTHETIC"):
            fams = {r["family"] for r in c["scenarios"]
                    if r["dataset_partition"] == part}
            assert "POSITIVE_SHARED_POWER" in fams
            assert any(f.startswith("NEGATIVE") for f in fams)

    def test_blind_access_is_logged(self):
        p = os.path.join(ROOT, "datasets", "reports",
                         "blind_evaluation_access.json")
        if not os.path.exists(p):
            pytest.skip("blind not yet accessed")
        with open(p) as fh:
            log = json.load(fh)
        assert log["accesses"]
        for a in log["accesses"]:
            assert a["reason"] and a["git_commit"]
            assert a["campaign_aggregate_hash"] \
                == self.load()["campaign_aggregate_hash"]
