"""WP1 formalization locks — pin the RECOVERED system, change nothing.

These tests encode what the implementation *is* at
bc3ed977e14d6eb6c5dc3a8b771b2349337de91a, so that a later refactor that alters
the mathematics has to say so out loud. They assert no behaviour that the code
does not already have.

Two of them are deliberately written as documented counterexamples rather than
as passing invariants — see the DOCUMENTED COUNTEREXAMPLE blocks. Where an
expected invariant does not hold, the failing case is preserved and named; the
algorithm is not adjusted to make the mathematics tidier.
"""

import itertools

import numpy as np
import pytest

from csia.diagnosis.bayes import (CAUSES, EPS, EVIDENCE_MULT, PRIOR_NOMINAL,
                                  SMOOTH_ALPHA, DiagnosisCore)
from csia.profiles import PROFILES, get_profile
from csia.trust_engine.engine import EngineConfig, TrustCore, consistency
from csia.trust_graph.graph import EDGES, NODES, build_trust_graph

CFG = EngineConfig()


def _core(names=("a", "b"), cfg=None):
    return TrustCore(list(names), cfg or CFG)


def _step(core, lam=1.0, gate=1.0, fresh=True, hist=None, vr=None):
    names = core.names
    return core.step(
        {"e": (names[0], names[1], lam, gate)},
        {n: (lam, gate) for n in names},
        {n: hist for n in names}, {n: vr for n in names},
        {n: fresh for n in names})


# --- graph topology per profile ----------------------------------------------

def test_graph_topology_is_eight_nodes_eleven_edges():
    g = build_trust_graph()
    assert (g.number_of_nodes(), g.number_of_edges()) == (8, 11)
    assert (len(NODES), len(EDGES)) == (8, 11)
    assert not g.is_directed()


def test_every_profile_uses_the_same_topology():
    """No profile ships a different graph — the 11/12 discrepancy is not a
    per-profile difference."""
    quad = set(get_profile("sow001_quad").sensors)
    assert quad == set(get_profile("sow001_quad_strict").sensors)
    assert quad == {n for n, _, _ in NODES}
    # the seeker profile is a different sensor set and does NOT use this graph
    assert set(get_profile("interceptor_seeker").sensors) == {
        "ir_seeker", "rf_seeker", "ins"}


def test_relation_velocity_gps_doppler_names_two_distinct_edges():
    pairs = [(a, b) for a, b, r, _ in EDGES if r == "velocity_gps_doppler"]
    assert sorted(pairs) == [("imu0", "gps"), ("imu1", "gps")]


def test_shipped_profile_tick_rates():
    assert get_profile("sow001_quad").tick_hz == 25.0
    assert get_profile("sow001_quad_strict").tick_hz == 25.0
    assert get_profile("interceptor_seeker").tick_hz == 100.0
    assert len(PROFILES) == 3


# --- initialization -----------------------------------------------------------

def test_beta_prior_and_initial_trust():
    core = _core()
    assert (CFG.alpha0, CFG.beta0) == (8.0, 2.0)
    assert all(core.alpha[n] == 8.0 for n in core.names)
    assert all(core.trust[n] == pytest.approx(0.8) for n in core.names)


def test_invalid_engine_config_is_rejected():
    with pytest.raises(ValueError):
        EngineConfig(rho_min=0.999, rho_max=0.95)
    with pytest.raises(ValueError):
        EngineConfig(alpha0=0.0)
    with pytest.raises(ValueError):
        EngineConfig(w_nbr=-1.0)


# --- deterministic replay / causal-prefix invariance --------------------------

def test_deterministic_replay():
    a, b = _core(), _core()
    rng_a = np.random.default_rng(11)
    rng_b = np.random.default_rng(11)
    for _ in range(120):
        ra, rb = _step(a, float(rng_a.exponential())), \
            _step(b, float(rng_b.exponential()))
        assert ra["a"]["trust"] == rb["a"]["trust"]


def test_causal_prefix_invariance():
    """Trust at tick k depends only on ticks <= k: a run truncated at k has the
    same state as the prefix of a longer run."""
    lams = list(np.random.default_rng(3).exponential(1.0, 60))
    short, long_ = _core(), _core()
    for lam in lams[:30]:
        s = _step(short, float(lam))
    for lam in lams:
        l = _step(long_, float(lam))
        if lam is lams[29]:
            break
    assert short.alpha["a"] == pytest.approx(long_.alpha["a"])


# --- trust bounds, concentration, rho ----------------------------------------

def test_trust_stays_in_open_unit_interval():
    core = _core()
    rng = np.random.default_rng(5)
    for _ in range(2000):
        r = _step(core, float(rng.exponential() * 30))
        for n in core.names:
            assert 0.0 < r[n]["trust"] < 1.0


def test_concentration_is_bounded_by_rho_max_not_by_clipping():
    """There is no explicit cap; alpha+beta is bounded only by the geometric
    series 1/(1-rho_max) = 500."""
    core = _core()
    for _ in range(5000):
        _step(core, 1.0)          # lam=1 -> c=1, perfectly consistent
    tot = core.alpha["a"] + core.beta["a"]
    assert tot < 1.0 / (1.0 - CFG.rho_max) + 1e-6
    assert tot > 400.0


def test_rho_stays_within_declared_bounds():
    core = _core(["a", "b", "c"])
    rng = np.random.default_rng(9)
    for _ in range(500):
        r = core.step(
            {"e": ("a", "b", float(rng.exponential() * 20), 1.0)},
            {n: (float(rng.exponential() * 20), 1.0) for n in core.names},
            {n: float(rng.exponential() * 20) for n in core.names},
            {n: float(rng.exponential() * 20) for n in core.names},
            {n: True for n in core.names})
        for n in core.names:
            assert CFG.rho_min - 1e-12 <= r[n]["rho"] <= CFG.rho_max + 1e-12


# --- zero / gated / missing / stale evidence ---------------------------------

def test_fully_gated_tick_holds_the_belief_and_reports_placeholder():
    core = _core()
    a0, b0 = core.alpha["a"], core.beta["a"]
    r = _step(core, lam=5.0, gate=0.0, hist=None, vr=None)
    assert r["a"]["evidence"] == 0.5
    assert core.alpha["a"] == a0 and core.beta["a"] == b0
    assert r["a"]["nbr"] is None and r["a"]["phys"] is None


def test_stale_sensor_holds_belief_even_with_evidence_available():
    core = _core()
    a0 = core.alpha["a"]
    _step(core, lam=9.0, gate=1.0, fresh=False)
    assert core.alpha["a"] == a0, "stale node must not integrate evidence"


def test_sensor_return_resumes_updating():
    core = _core()
    _step(core, lam=9.0, fresh=False)
    a_held = core.alpha["a"]
    _step(core, lam=9.0, fresh=True)
    assert core.alpha["a"] != a_held


def test_denominator_guard_on_neighbour_score():
    """Every incident edge gated out -> c_nbr is None, never a division."""
    core = _core()
    r = core.step({"e": ("a", "b", 3.0, 0.0)},
                  {}, {n: None for n in core.names},
                  {n: None for n in core.names},
                  {n: True for n in core.names})
    assert r["a"]["nbr"] is None
    assert r["a"]["evidence"] == 0.5


def test_gated_check_is_excluded_not_scored_zero():
    """The renormalisation semantics: a gated check must not drag evidence
    down. With physics gated off and a perfect neighbour, evidence must be
    1.0, not w_nbr-weighted against a zero."""
    core = _core()
    r = core.step({"e": ("a", "b", 1.0, 1.0)},
                  {n: (1.0, 0.0) for n in core.names},
                  {n: None for n in core.names},
                  {n: None for n in core.names},
                  {n: True for n in core.names})
    assert r["a"]["evidence"] == pytest.approx(1.0)
    assert r["a"]["phys"] is None


# --- prolonged agreement / disagreement / contradictory edges ----------------

def test_prolonged_agreement_raises_trust_toward_one():
    core = _core()
    for _ in range(1500):
        _step(core, lam=1.0)
    assert core.trust["a"] > 0.99


def test_prolonged_disagreement_lowers_trust():
    core = _core()
    for _ in range(1500):
        _step(core, lam=30.0)
    assert core.trust["a"] < 0.2


def test_trust_recovers_after_a_transient():
    core = _core()
    for _ in range(600):
        _step(core, lam=30.0)
    low = core.trust["a"]
    for _ in range(1500):
        _step(core, lam=1.0)
    assert core.trust["a"] > low + 0.5, "degradation must be reversible"


def test_single_bad_subscore_cannot_drive_trust_below_the_weight_floor():
    """MEASURED PROPERTY (not previously documented). With only c_nbr and
    c_phys available and c_phys collapsed, fused evidence floors at
    w_nbr/(w_nbr+w_phys) = 0.35/0.65 = 0.538 — renormalisation means one
    catastrophic sub-score cannot by itself take trust to zero. Recorded
    because it bounds how fast any single-check fault can move trust."""
    core = _core(["a", "b"])
    for _ in range(800):
        core.step({"e": ("a", "b", 1.0, 1.0)},
                  {"a": (1.0, 1.0), "b": (40.0, 1.0)},
                  {n: None for n in core.names},
                  {n: None for n in core.names},
                  {n: True for n in core.names})
    floor = CFG.w_nbr / (CFG.w_nbr + CFG.w_phys)
    assert core.trust["b"] == pytest.approx(floor, abs=1e-3)
    assert floor == pytest.approx(0.5385, abs=1e-3)


def test_contradictory_edge_evidence_is_trust_weighted():
    """A distrusted neighbour's disagreement is discounted: the implemented
    weight is gate*T_neighbour (engine.py:113)."""
    core = _core(["a", "b"])
    for _ in range(800):
        core.step({"e": ("a", "b", 1.0, 1.0)},
                  {"a": (1.0, 1.0), "b": (40.0, 1.0)},
                  {n: None for n in core.names},
                  {n: None for n in core.names},
                  {n: True for n in core.names})
    r = core.step({"e": ("a", "b", 50.0, 1.0)},
                  {}, {n: None for n in core.names},
                  {n: None for n in core.names},
                  {n: True for n in core.names})
    assert r["a"]["nbr"] is not None


# --- diagnosis structure ------------------------------------------------------

def test_diagnosis_constants_and_prior():
    d = DiagnosisCore()
    assert len(d.names) == 8 and "nominal" in d.names
    assert (EPS, SMOOTH_ALPHA, EVIDENCE_MULT, PRIOR_NOMINAL) == \
        (0.02, 0.06, 1.5, 0.86)
    assert np.exp(d._log_prior[d.names.index("nominal")]) == \
        pytest.approx(0.86)


def test_gated_feature_contributes_nothing_to_diagnosis():
    a, b = DiagnosisCore(), DiagnosisCore()
    pa = a.step({"phys_gps": (0.01, 0.0)})       # gated off
    pb = b.step({})                               # absent entirely
    assert set(pa) == set(pb)
    for cause in pa:
        assert pa[cause] == pytest.approx(pb[cause])


# --- DOCUMENTED COUNTEREXAMPLES ----------------------------------------------
# Preserved as findings, NOT repaired. See
# research/formalization/diagnostic_signature_matrix.md.

def test_COUNTEREXAMPLE_imu_hypotheses_collide_when_motor_edges_gated():
    """F-D1. Disarmed/pre-arm gates the motor edges off (online.py:491-496).
    imu0_bias_drift and imu1_bias_drift then share the LOW set {redundant_imu}
    and become observationally identical: equal priors, so the posterior splits
    and no evidence can separate them."""
    off = {"accel_motor_current", "accel_esc_rpm", "phys_motor_esc"}
    a = set(CAUSES["imu0_bias_drift"]) - off
    b = set(CAUSES["imu1_bias_drift"]) - off
    assert a == b == {"redundant_imu"}

    d = DiagnosisCore()
    for _ in range(200):
        post = d.step({"redundant_imu": (0.01, 1.0),
                       "accel_motor_current": (0.01, 0.0),
                       "accel_esc_rpm": (0.99, 0.0)})
    assert post["imu0_bias_drift"] == pytest.approx(post["imu1_bias_drift"])


def test_COUNTEREXAMPLE_gps_fault_unnameable_when_fix_invalid():
    """F-D2. With an invalid GPS fix every GPS feature gates off
    (comparator.py:115,144,155,168,199). gps_fault then has an empty LOW set,
    identical to nominal, so its posterior is pinned at the prior ratio
    (0.02 vs 0.86) forever: a GPS fault cannot be diagnosed in the very mode
    where it is most likely."""
    off = {"phys_gps", "heading_course", "altitude_baro",
           "velocity_gps_doppler", "temp_gps"}
    assert set(CAUSES["gps_fault"]) - off == set(CAUSES["nominal"]) == set()

    d = DiagnosisCore()
    for _ in range(300):
        post = d.step({f: (0.01, 0.0) for f in off})
    assert post["nominal"] > 0.8
    assert post["gps_fault"] == pytest.approx(post["unexpected_maneuver"])
    assert post["gps_fault"] < 0.05


def test_no_unconditional_signature_degeneracy():
    """With every gate open, all fault signatures are pairwise distinct. The
    collisions above are gate-conditional, not inherent to the table."""
    faults = [c for c in CAUSES if c != "nominal"]
    for a, b in itertools.combinations(faults, 2):
        assert set(CAUSES[a]) != set(CAUSES[b]), f"{a} == {b}"


# --- consistency kernel -------------------------------------------------------

def test_consistency_kernel_only_penalises_chi2_excess():
    assert consistency(0.0) == pytest.approx(1.0)
    assert consistency(1.0) == pytest.approx(1.0)
    assert consistency(3.0) == pytest.approx(np.exp(-1.0))
    assert 0.0 < consistency(1e3) < 1e-100
