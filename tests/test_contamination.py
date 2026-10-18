"""The decomposition must reproduce the frozen core, or it is a story.

WHAT THIS COVERS
----------------
`csia_supervision/contamination.py` takes a sensor's neighbour consistency
apart edge by edge, and re-runs the Beta recursion on a restricted partner
set. Both are reimplementations of arithmetic that lives in a FROZEN file.
A reimplementation that drifts from its original is worse than no
reimplementation at all, because every number it produces looks like a
measurement of the system.

So the tests here are mostly one test asked in several ways: does it agree
with `csia/trust_engine/engine.py`, on real runs, exactly?

THE THREE WAYS IT COULD SILENTLY BE WRONG, EACH PINNED
-------------------------------------------------------
  * Using THIS tick's trust to weight the edges instead of the previous
    tick's. The core updates `self.trust` only after every node is scored,
    so the off-by-one is invisible in the arithmetic and wrong everywhere.
  * Treating the `w <= 1e-6` cutoff as a zero-weight contribution instead of
    an absent one. That leaves the denominator unchanged and gives a
    different mean.
  * Collapsing `velocity_gps_doppler` into one edge. One relation name
    serves two edges -- imu0/gps and imu1/gps -- and a map that merges them
    attributes imu1's evidence to imu0 with no error anywhere.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_supervision import contamination as ct                  # noqa: E402


def _fly(profile_id: str, faults=None, duration=None):
    """Real states from the real frozen layer. No synthetic TrustState."""
    from csia.runtime.online import OnlineTrustLayer
    from csia_stress.profiles import by_id
    from csia_stress.source import StressFlightSource

    profile = by_id(profile_id)
    source = StressFlightSource(
        faults=faults if faults is not None else profile.faults,
        truth=None, flight_profile=profile.flight_profile,
        duration=duration or profile.duration)
    layer = OnlineTrustLayer()
    states, last = [], 0.0
    for name, t, channels in source.samples():
        states.extend(layer.ingest(name, t, channels))
        last = t
    states.extend(layer.flush(last))
    return states


@pytest.fixture(scope="module")
def flight():
    return _fly("msrd_four_class_cascade")


# --- the endpoint map ------------------------------------------------------

def test_endpoint_map_equals_the_layers_own():
    """Derived independently, then checked against the authority.

    If the frozen layer ever changes how it names or splits an edge, this
    fails loudly instead of misattributing evidence in silence.
    """
    from csia.runtime.online import OnlineTrustLayer
    layer = OnlineTrustLayer(tick_hz=25.0, field_mode=True)
    assert ct.edge_endpoints() == dict(layer._edge_meta)


def test_the_doppler_edge_is_split_not_merged():
    meta = ct.edge_endpoints()
    assert meta["velocity_gps_doppler_0"] == ("imu0", "gps")
    assert meta["velocity_gps_doppler_1"] == ("imu1", "gps")
    assert "velocity_gps_doppler" not in meta, (
        "the merged relation name would attribute imu1's evidence to imu0")


def test_prior_trust_matches_the_engine_config():
    from csia.trust_engine.engine import EngineConfig
    cfg = EngineConfig()
    assert ct.PRIOR_TRUST == cfg.alpha0 / (cfg.alpha0 + cfg.beta0)


# --- the decomposition sums back to the core's own number ------------------

def test_decomposition_is_exact_on_every_tick(flight):
    meta = ct.edge_endpoints()
    prev = {n: ct.PRIOR_TRUST for n in flight[0].trust}
    worst, disagreements, checked = 0.0, 0, 0
    for state in flight:
        report = ct.verify(state, prev, meta)
        disagreements += report["disagreements"]
        worst = max(worst, report["worst_abs_diff"])
        checked += len(report["sensors"])
        prev = dict(state.trust)
    assert checked > 5000, "too few comparisons to mean anything"
    assert disagreements == 0
    assert worst < 1e-12, f"worst reconstruction error {worst}"


def test_the_verification_is_not_vacuous(flight):
    """Every sensor must actually produce a c_nbr on most ticks.

    A `verify` that only ever compared None to None would pass while
    measuring nothing.
    """
    meta = ct.edge_endpoints()
    prev = {n: ct.PRIOR_TRUST for n in flight[0].trust}
    with_value = 0
    total = 0
    for state in flight:
        for row in ct.verify(state, prev, meta)["sensors"]:
            total += 1
            if row["core"] is not None and row["reconstructed"] is not None:
                with_value += 1
        prev = dict(state.trust)
    assert with_value / total > 0.9, (
        f"only {with_value}/{total} comparisons carried a value on both "
        f"sides; the exactness result would be about None == None")


def test_using_this_ticks_trust_instead_of_the_previous_one_disagrees(flight):
    """The off-by-one must be DETECTABLE, or the exactness proves nothing."""
    meta = ct.edge_endpoints()
    disagreements = 0
    for state in flight[:400]:
        # Deliberately wrong: weight the edges by THIS tick's trust.
        disagreements += ct.verify(state, dict(state.trust),
                                   meta)["disagreements"]
    assert disagreements > 0, (
        "weighting edges by the wrong tick's trust produced no disagreement, "
        "so the exactness test cannot distinguish right from wrong")


def test_shares_sum_to_one_where_there_is_any_evidence(flight):
    meta = ct.edge_endpoints()
    prev = {n: ct.PRIOR_TRUST for n in flight[0].trust}
    seen = 0
    for state in flight[:300]:
        for sensor in state.trust:
            d = ct.decompose(sensor, state, prev, meta)
            if d.contributions:
                seen += 1
                assert abs(sum(c.share for c in d.contributions) - 1.0) < 1e-9
        prev = dict(state.trust)
    assert seen > 100


def test_c_nbr_is_none_exactly_when_no_edge_clears_the_cutoff(flight):
    meta = ct.edge_endpoints()
    prev = {n: ct.PRIOR_TRUST for n in flight[0].trust}
    for state in flight[:300]:
        for sensor in state.trust:
            d = ct.decompose(sensor, state, prev, meta)
            assert (d.c_nbr is None) == (not d.contributions)
        prev = dict(state.trust)


# --- restriction -----------------------------------------------------------

def test_restricting_to_every_partner_changes_nothing(flight):
    meta = ct.edge_endpoints()
    prev = {n: ct.PRIOR_TRUST for n in flight[0].trust}
    for state in flight[:300]:
        for sensor in state.trust:
            d = ct.decompose(sensor, state, prev, meta)
            r = d.restricted(set(state.trust) - {sensor})
            if d.c_nbr is None:
                assert r.c_nbr is None
            else:
                assert abs(r.c_nbr - d.c_nbr) <= 4 * sys.float_info.epsilon
                assert r.coverage == pytest.approx(1.0)
        prev = dict(state.trust)


def test_restricting_to_nothing_removes_the_evidence(flight):
    meta = ct.edge_endpoints()
    prev = {n: ct.PRIOR_TRUST for n in flight[0].trust}
    for state in flight[:200]:
        for sensor in state.trust:
            r = ct.decompose(sensor, state, prev, meta).restricted(set())
            assert r.c_nbr is None
            assert r.coverage == 0.0
        prev = dict(state.trust)


def test_coverage_reports_the_share_that_survived(flight):
    """A judgement at coverage 0.15 rests on almost nothing, and a caller
    that cannot see that will not know."""
    meta = ct.edge_endpoints()
    prev = {n: ct.PRIOR_TRUST for n in flight[0].trust}
    partial_seen = False
    for state in flight[:600]:
        d = ct.decompose("motor_esc", state, prev, meta)
        if len(d.contributions) >= 2:
            keep = {d.contributions[0].partner}
            r = d.restricted(keep)
            assert 0.0 < r.coverage < 1.0
            assert r.coverage == pytest.approx(
                d.contributions[0].weight / d.weight_total)
            partial_seen = True
        prev = dict(state.trust)
    assert partial_seen, "no multi-partner tick was found to restrict"


# --- the shadow recursion --------------------------------------------------

def test_unrestricted_shadow_reproduces_the_frozen_core_exactly(flight):
    """The only reason to believe any restricted number."""
    sensors = sorted(flight[0].trust)
    shadow = ct.ShadowTrust(sensors)
    prev = {n: ct.PRIOR_TRUST for n in sensors}
    for state in flight:
        shadow.step(state, prev)
        prev = dict(state.trust)
    assert shadow.max_drift_when_unrestricted == 0.0


def test_shadow_restricted_to_all_partners_matches_within_an_ulp(flight):
    """Going through the reconstruction costs at most a few ulps, and does
    NOT accumulate through the recursion."""
    sensors = sorted(flight[0].trust)
    shadow = ct.ShadowTrust(
        sensors, admissible=lambda s, st, pt: set(st.trust) - {s})
    prev = {n: ct.PRIOR_TRUST for n in sensors}
    worst = 0.0
    for state in flight:
        shadow.step(state, prev)
        prev = dict(state.trust)
        for n in sensors:
            core = state.trust.get(n)
            if core is not None:
                worst = max(worst, abs(float(core) - shadow.trust[n]))
    assert worst <= 4 * sys.float_info.epsilon, worst


def test_shadow_restricted_to_nothing_diverges_from_the_core(flight):
    """Anti-vacuity for the two tests above: the shadow CAN differ."""
    sensors = sorted(flight[0].trust)
    shadow = ct.ShadowTrust(sensors, admissible=lambda s, st, pt: set())
    prev = {n: ct.PRIOR_TRUST for n in sensors}
    worst = 0.0
    for state in flight[:600]:
        shadow.step(state, prev)
        prev = dict(state.trust)
        for n in sensors:
            core = state.trust.get(n)
            if core is not None:
                worst = max(worst, abs(float(core) - shadow.trust[n]))
    assert worst > 0.01, (
        "removing every partner moved nothing; the restriction is inert and "
        "every result built on it is the core's own number in disguise")


def test_shadow_does_not_feed_its_own_trust_back_into_the_weights():
    """A decomposition under a counterfactual partner set, not a second
    trust engine. Letting the shadow's beliefs drive the shadow's edge
    weights would make it a different system, and comparing it to the core
    would then establish nothing."""
    src = open(os.path.join(ROOT, "csia_supervision", "contamination.py"),
               encoding="utf-8").read()
    body = src[src.index("class ShadowTrust"):]
    step = body[body.index("def step"):]
    assert "self.trust" in step
    assert "prev_trust" in step
    # the decomposition is driven by prev_trust, never by self.trust
    assert "decompose(n, state, self.trust" not in step


# --- capability support attribution ---------------------------------------

def test_evidence_support_traces_a_capability_to_its_edges(flight):
    prev = {n: ct.PRIOR_TRUST for n in flight[0].trust}
    for state in flight[:400]:
        r = ct.evidence_support("baro.altitude.supported", state, prev)
        if r["status"] == "TRACED" and r["legs"][0]["edges"]:
            leg = r["legs"][0]
            assert leg["sensor"] == "baro"
            partners = {e["partner"] for e in leg["edges"]}
            assert partners <= {"gps", "battery"}, partners
            assert abs(sum(e["share"] for e in leg["edges"]) - 1.0) < 1e-9
            return
        prev = dict(state.trust)
    pytest.fail("no traceable tick found")


def test_evidence_with_no_sensor_mapping_says_so_rather_than_guessing(flight):
    r = ct.evidence_support("nothing.at.all", flight[0],
                            {n: ct.PRIOR_TRUST for n in flight[0].trust})
    assert r["status"] == "NO_SENSOR_MAPPING"
    assert "legs" not in r


def test_requires_all_lost_evidence_traces_to_every_named_sensor(flight):
    """`attitude.supported` lives in REQUIRES_ALL_LOST, not SENSOR_EVIDENCE.
    Reporting NO_SENSOR_MAPPING for it would hide a capability that IS
    traceable."""
    r = ct.evidence_support("attitude.supported", flight[0],
                            {n: ct.PRIOR_TRUST for n in flight[0].trust})
    assert r["status"] == "TRACED"
    assert {leg["sensor"] for leg in r["legs"]} == {"imu0", "imu1"}


def test_the_two_weak_leg_questions_are_reported_separately(flight):
    """A well-corroborated partner in flat disagreement carries a LARGE
    share, so a single "weakest" field would hide it."""
    prev = {n: ct.PRIOR_TRUST for n in flight[0].trust}
    differed = False
    for state in flight:
        r = ct.evidence_support("imu.primary.supported", state, prev)
        prev = dict(state.trust)
        if r["status"] != "TRACED":
            continue
        leg = r["legs"][0]
        if not leg["edges"]:
            continue
        assert set(leg) >= {"smallest_share", "lowest_consistency"}
        if (leg["smallest_share"]["edge"]
                != leg["lowest_consistency"]["edge"]):
            differed = True
    assert differed, (
        "the smallest-share edge and the lowest-consistency edge were the "
        "same on every tick, so reporting both proves nothing here")


# --- the probe's own controls ---------------------------------------------

def test_probe_controls_pass_and_discriminate():
    from csia_stress.contamination_probe import INSTRUMENT, _controls
    from tools.assurance.instrument_controls import guard
    _controls()
    report = guard(INSTRUMENT)
    assert report["verdict"] == "PASS"
    kinds = {r["kind"] for r in report["controls"]}
    assert kinds == {"POSITIVE", "NEGATIVE"}


def test_the_probe_declares_its_kill_conditions_before_measuring():
    from csia_stress import contamination_probe
    doc = contamination_probe.__doc__
    for k in ("K1", "K2", "K3"):
        assert k in doc, f"kill condition {k} is not declared in the docstring"
    assert "DECLARED BEFORE" in doc.upper()


def test_the_probe_invents_no_threshold():
    """Step 3 of the declared procedure: an existing FailsafeConfig constant
    or nothing at all."""
    from csia.runtime.failsafe import FailsafeConfig
    from csia_stress.contamination_probe import _select_threshold
    cfg = FailsafeConfig()
    picked = _select_threshold(0.95, cfg)
    assert picked["selected"] in (
        "nav_caution", "heading_caution", "struct_critical",
        "power_critical", "att_caution", "att_emergency")
    assert picked["value"] == float(getattr(cfg, picked["selected"]))
    # and it must be capable of refusing
    refused = _select_threshold(0.10, cfg)
    assert refused["selected"] is None
    assert "K1" in refused["reason"]
