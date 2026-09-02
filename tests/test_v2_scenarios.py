"""§§27, 28, 37 — the synthetic scenarios, and what each must demonstrate.

Every scenario writes its expectation into the table BEFORE the run
(`Scenario.expectation`). These tests assert the specific, checkable part of
that expectation. Where a scenario's behaviour drifts, one of these fails
rather than the prose being quietly reinterpreted.

The five §28 cases carry a `scenario_x` tag, and a test at the bottom asserts
all five are present — so a case cannot be dropped by deleting its test.
"""

import pytest

import os

from csia.v2 import scenarios as SC
from csia.v2.profiles import SCENARIOS, build_engine_for
from csia.v2.profiles.aircraft_scenarios import example_payload_feed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKS = 40


def run(name):
    sc = SCENARIOS[name]
    feed = (example_payload_feed(sc.v1_1_variant)
            if sc.system == "aircraft" else None)
    return SC.run(build_engine_for(sc), sc, ticks=TICKS, payload_for=feed)


def final(name):
    return run(name)[-1]


def codes(assurance, domain=None):
    return {c for r in assurance.records
            if (domain is None or r.domain == domain)
            for c in r.reason_codes}


# ------------------------------------------------------------- baselines
@pytest.mark.parametrize("name", ["NOMINAL", "TS_NOMINAL"])
def test_a_nominal_run_is_normal_with_nothing_adverse(name):
    a = final(name)
    assert a.system == "NORMAL"
    assert a.attribution.verdict == "NO_EVIDENCE"
    assert a.limiting_domains == ()
    assert all(v.state == "ELIGIBLE" for v in a.functions.values())


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_every_scenario_replays_bit_for_bit(name):
    """No RNG, no clock. A scenario that could not be replayed could not be
    the basis of a ledger."""
    a = [r.to_dict() for r in run(name)]
    b = [r.to_dict() for r in run(name)]
    assert a == b


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_no_function_is_ever_left_undetermined_by_a_wiring_gap(name):
    """UNKNOWN is a real state meaning "the policy could not determine
    eligibility". It must not also be what a profile produces when it forgot
    to attach a domain to a function -- that would make a configuration
    mistake indistinguishable from a genuine finding."""
    for a in run(name):
        for fname, v in a.functions.items():
            if v.state != "UNKNOWN":
                continue
            missing = [d for d, s in v.domain_states.items()
                       if s == "UNAVAILABLE"]
            assert any(c for r in a.records
                       for c in r.reason_codes
                       if r.domain in missing), (
                f"{name}: {fname} is UNKNOWN because {missing} said nothing "
                f"at all -- that is a profile wiring gap, not a finding")


# -------------------------------------------------- §28 SCENARIO A
def test_scenario_a_a_delayed_network_does_not_become_a_sensor_fault():
    """sensor healthy + network delayed -> communication/timing degrade,
    sensor domain remains source-valid."""
    a = final("NETWORK_LATENCY")
    assert a.domains["SENSOR"] == "NOMINAL"
    assert a.domains["COMMUNICATION"] in ("DEGRADED", "VIOLATED")
    assert a.domains["TIMING"] in ("DEGRADED", "VIOLATED")
    assert a.functions["TELEMETRY"].state != "ELIGIBLE"
    assert a.functions["TELEMETRY"].limiting_domain in ("COMMUNICATION",
                                                        "TIMING")
    # And navigation, which does not ride the delayed link, is untouched.
    assert a.functions["PRECISION_NAVIGATION"].state == "ELIGIBLE"
    assert not any(c.domain == "SENSOR" for c in a.attribution.candidates)


# -------------------------------------------------- §28 SCENARIO B
def test_scenario_b_a_healthy_battery_is_exonerated_and_says_so():
    """battery healthy + 5V rail failing -> power DISTRIBUTION issue, not a
    battery fault."""
    a = final("REGULATOR_FAILURE")
    assert a.domains["POWER"] == "VIOLATED"
    ids = [c.id for c in a.attribution.candidates]
    assert "POWER/rail_5v" in ids
    assert "POWER/battery" not in ids, "the source must not be a candidate"
    assert "POWER/battery" in a.attribution.unsupported
    assert "POWER_DISTRIBUTION_SUSPECT" in codes(a, "POWER")
    rail = [r for r in a.records if r.component == "rail_5v"][0]
    assert rail.detail["source_exonerated"] == "battery"


def test_scenario_b_does_not_report_the_whole_vehicle_as_lost():
    """The 5 V rail carries the GNSS and the radio. The IMUs are on 3V3 and
    the motors are on the battery, so dead reckoning, logging and propulsion
    survive -- and a monitor that said otherwise would be reporting a
    vehicle that cannot fly home when in fact it can."""
    a = final("REGULATOR_FAILURE")
    assert a.system == "RESTRICTED"
    assert a.functions["INERTIAL_CONTINUATION"].state == "ELIGIBLE"
    assert a.functions["LOGGING"].state == "ELIGIBLE"
    assert a.functions["PROPULSION"].state == "ELIGIBLE"
    assert a.functions["PRECISION_NAVIGATION"].state == "INELIGIBLE"


def test_a_failing_source_by_contrast_does_take_everything():
    """The contrast that makes the exoneration meaningful: when the SOURCE
    is what is failing, nothing is exonerated and nothing survives."""
    a = final("POWER_SAG")
    assert a.system == "UNAVAILABLE"
    assert "POWER/battery" in [c.id for c in a.attribution.candidates]
    assert a.attribution.common_cause == "POWER/battery"


# -------------------------------------------------- §28 SCENARIO C
def test_scenario_c_current_rises_and_rpm_does_not():
    """command sent, ESC receives, current rises, RPM does not ->
    actuation/mechanical domain issue."""
    a = final("STALLED_ACTUATOR")
    assert a.domains["ACTUATION"] == "VIOLATED"
    assert "ACT_STALLED" in codes(a, "ACTUATION")
    assert "ACT_NO_ELECTRICAL_RESPONSE" not in codes(a, "ACTUATION")
    assert "ACT_COMMAND_NOT_TRANSMITTED" not in codes(a, "ACTUATION")
    assert a.functions["PROPULSION"].limiting_domain == "ACTUATION"
    # The other domains are affirmatively fine, which is what makes this a
    # mechanical finding rather than a shrug.
    assert a.domains["POWER"] == "NOMINAL"
    assert a.domains["COMMUNICATION"] == "NOMINAL"


def test_the_opposite_electrical_signature_is_a_different_finding():
    a = final("ACTUATOR_NO_RESPONSE")
    assert "ACT_NO_ELECTRICAL_RESPONSE" in codes(a, "ACTUATION")
    assert "ACT_STALLED" not in codes(a, "ACTUATION")


# -------------------------------------------------- §28 SCENARIO D
def test_scenario_d_a_late_estimator_is_not_a_sensor_failure():
    """sensor fresh + estimator process late -> compute/timing limitation,
    not sensor failure."""
    a = final("ESTIMATOR_LATE")
    assert a.domains["SENSOR"] == "NOMINAL"
    assert a.domains["COMPUTE"] == "VIOLATED"
    assert a.functions["PRECISION_NAVIGATION"].limiting_domain in ("COMPUTE",
                                                                   "TIMING")
    assert "COMPUTE_DEADLINE_MISSED" in codes(a, "COMPUTE")
    assert not any(c.domain == "SENSOR" for c in a.attribution.candidates)


def test_scenario_d_matches_the_shape_of_the_worked_example_in_section_17():
    """§17's example: SENSOR eligible, COMMUNICATION eligible, COMPUTE
    degraded, TIMING ineligible, PRECISION_NAVIGATION ineligible,
    COARSE_NAVIGATION eligible; sensor and transport failure unsupported,
    compute deadline violation supported.

    Every column matches except one, and the difference is reported rather
    than tuned away: **COMPUTE reads VIOLATED here, not DEGRADED**, because
    at the end of this run the estimator's runtime is past its deadline
    outright rather than inside the marginal band. Making it come out
    DEGRADED would mean choosing a ramp endpoint to match an illustrative
    example, which is not a reason to choose anything.
    """
    a = final("ESTIMATOR_LATE")
    assert a.domains["SENSOR"] == "NOMINAL"
    assert a.domains["COMMUNICATION"] == "NOMINAL"
    assert a.domains["TIMING"] == "VIOLATED"
    assert a.functions["PRECISION_NAVIGATION"].state == "INELIGIBLE"
    assert a.functions["COARSE_NAVIGATION"].state == "ELIGIBLE"
    supported = {c.domain for c in a.attribution.candidates}
    assert "SENSOR" not in supported and "COMMUNICATION" not in supported
    assert "COMPUTE" in supported


# -------------------------------------------------- §28 SCENARIO E
def test_scenario_e_a_shared_rail_is_retained_as_an_alternative():
    """shared rail fault affects two dependants -> common power-domain cause
    RETAINED as an alternative explanation, never adopted as the answer."""
    a = final("SHARED_RAIL")
    assert a.attribution.verdict == "AMBIGUOUS", (
        "a common cause is an alternative explanation, not a diagnosis: a "
        "rail fault and coincident faults downstream of it produce the same "
        "evidence here")
    assert a.attribution.common_cause == "POWER/rail_5v"
    ids = [c.id for c in a.attribution.candidates]
    downstream = [i for i in ids if not i.startswith("POWER/")]
    assert len(downstream) >= 2, (
        f"the case needs several dependants of the rail to be adverse; "
        f"got {ids}")
    assert "POWER/rail_5v" in ids


def test_scenario_e_finds_the_rail_through_the_declared_chain():
    """The GNSS source declares POWER/rail_5v and the telemetry radio
    declares it too, but the 3V3 rail reaches it only via rail_5v. Direct
    dependency counting would miss the shared node."""
    a = final("SHARED_RAIL")
    deps = {r.component: r.dependencies for r in a.records}
    assert deps["rail_3v3"] == ("POWER/rail_5v",)
    assert "POWER/rail_5v" in deps["source.gps"]


# ------------------------------------------------------ §27's other cases
def test_cpu_saturation_and_the_latency_it_causes_are_one_event():
    """§14: CPU saturation -> processing latency -> missed output deadline.
    Three candidates for one event is not three faults."""
    a = final("CPU_OVERLOAD")
    assert a.attribution.common_cause == "COMPUTE/cpu"
    assert "COMPUTE_CPU_SATURATED" in codes(a, "COMPUTE")
    assert a.domains["TIMING"] == "VIOLATED"


def test_a_stalled_process_is_attributed_to_the_process():
    a = final("PROCESS_STALL")
    assert a.attribution.verdict == "UNIQUE"
    assert [c.id for c in a.attribution.candidates] == \
        ["COMPUTE/state_estimator"]
    assert a.domains["SENSOR"] == "NOMINAL"


def test_packet_loss_is_a_link_finding_not_a_source_finding():
    a = final("PACKET_LOSS")
    assert a.attribution.verdict == "UNIQUE"
    assert [c.id for c in a.attribution.candidates] == \
        ["COMMUNICATION/gnss_serial"]
    assert a.domains["SENSOR"] == "NOMINAL", (
        "the v1.1 payload is the clean one; a link fault must not be "
        "reported as a sensor fault")


def test_clock_drift_is_reported_as_a_timebase_fault():
    a = final("CLOCK_DRIFT")
    assert "TIMING_CLOCK_INCONSISTENT" in codes(a, "TIMING")
    assert a.domains["TIMING"] == "VIOLATED"
    # No latency numbers are published from stamps shown to be inconsistent.
    assert not any(r.relation == "timing.segment_budget"
                   and r.component.startswith("nav_solution")
                   for r in a.records)


# ---------------------------------------------------------------- §37
def test_the_test_stand_runs_the_same_framework_with_no_sensor_domain():
    """§37's genericity test. No SENSOR domain, no v1.1 payload, no aviation
    vocabulary -- and no framework change."""
    sc = SCENARIOS["TS_NOMINAL"]
    engine = build_engine_for(sc)
    assert "SENSOR" not in engine.registry
    assert len(engine.registry) == 5
    results = SC.run(engine, sc, ticks=5, payload_for=None)
    assert results[-1].system == "NORMAL"


def test_the_test_stand_reproduces_the_exoneration_with_no_aviation_code():
    a = final("TS_REGULATOR_FAILURE")
    ids = [c.id for c in a.attribution.candidates]
    assert "POWER/rail_5v" in ids
    assert "POWER/dc_supply" not in ids
    assert "POWER/dc_supply" in a.attribution.unsupported


def test_the_test_stand_functions_are_named_for_what_the_bench_does():
    names = set(SCENARIOS["TS_NOMINAL"].nominal)
    assert "SENSOR" not in names
    engine = build_engine_for(SCENARIOS["TS_NOMINAL"])
    for fn in engine.functions.names():
        for aviation in ("NAVIGATION", "FLIGHT", "GEOFENCE", "INERTIAL",
                         "LANDING", "MISSION"):
            assert aviation not in fn


# ------------------------------------------------------------ completeness
def test_every_scenario_named_in_section_27_exists():
    required = {"POWER_SAG", "REGULATOR_FAILURE", "CPU_OVERLOAD",
                "PROCESS_STALL", "NETWORK_LATENCY", "PACKET_LOSS",
                "CLOCK_DRIFT", "ACTUATOR_NO_RESPONSE"}
    assert required <= set(SCENARIOS)


def test_all_five_cross_domain_cases_from_section_28_exist():
    tags = {t for s in SCENARIOS.values() for t in s.tags}
    for letter in "abcde":
        assert f"scenario_{letter}" in tags, f"§28 case {letter.upper()} is "\
            f"not represented by any scenario"


def test_every_scenario_states_its_expectation_before_it_is_run():
    for name, s in SCENARIOS.items():
        assert s.expectation.strip(), name
        assert s.description.strip(), name
        assert s.section.strip(), name


def test_the_test_stand_needs_neither_v1_1_nor_the_aircraft_profile_loaded():
    """§37's strongest form, run in a fresh interpreter.

    If the framework carried an aircraft assumption, building a bench would
    drag one in. This imports ONLY the test-stand profile, runs a full
    scenario, and asserts that no `csia.v1_1` module and no aircraft profile
    module was ever loaded -- which the in-process tests cannot check,
    because by then the whole package is imported.
    """
    import subprocess
    import sys
    import textwrap
    script = textwrap.dedent("""
        import sys
        from csia.v2.profiles.test_stand import build_test_stand_engine
        from csia.v2.profiles.test_stand_scenarios import TEST_STAND_SCENARIOS
        from csia.v2 import scenarios as SC
        engine = build_test_stand_engine()
        by_name = {s.name: s for s in TEST_STAND_SCENARIOS}
        res = SC.run(engine, by_name["TS_STALLED"], ticks=20)
        assert res[-1].system == "RESTRICTED", res[-1].system
        assert res[-1].functions["TORQUE_DELIVERY"].state == "INELIGIBLE"
        leaked = sorted(m for m in sys.modules
                        if m.startswith("csia.v1_1")
                        or "aircraft" in m
                        or m.startswith("csia.trust_engine")
                        or m.startswith("csia.diagnosis"))
        assert not leaked, leaked
        print("OK")
    """)
    out = subprocess.run([sys.executable, "-c", script],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout
