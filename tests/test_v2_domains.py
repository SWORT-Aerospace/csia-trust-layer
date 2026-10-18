"""CSIA v2 — the five built domains: power, compute, timing, communication,
actuation.

Each domain is tested on what it is FOR, not on whether its arithmetic runs.
The arithmetic is Ohm's law and subtraction; the engineering content is which
comparison is made, what is declared rather than assumed, and what the result
is allowed to conclude.
"""

import pytest

from csia.v2.domain import Snapshot
from csia.v2.domains.actuation import (ACT_NO_ELECTRICAL_RESPONSE, ACT_STALLED,
                                       ActuationAssuranceDomain, ActuatorSpec)
from csia.v2.domains.communication import (COMM_BUS_OFF, COMM_PACKET_LOSS,
                                           COMM_RATE_LOW,
                                           CommunicationAssuranceDomain,
                                           LinkSpec)
from csia.v2.domains.compute import (COMPUTE_CPU_SATURATED,
                                     COMPUTE_DEADLINE_MISSED,
                                     COMPUTE_HEARTBEAT_STALE,
                                     COMPUTE_PROCESS_DEAD,
                                     ComputeAssuranceDomain, ProcessSpec,
                                     ResourceSpec)
from csia.v2.domains.power import (POWER_DISTRIBUTION_SUSPECT,
                                   POWER_RAIL_OUT_OF_TOLERANCE,
                                   POWER_TELEMETRY_MISSING, BatterySpec,
                                   LoadSpec, PowerAssuranceDomain, RailSpec)
from csia.v2.domains.timing import (SENSOR_SLOW, TIMING_CLOCK_INCONSISTENT,
                                    TIMING_DEADLINE_MISSED,
                                    TRANSPORT_DELAY, ChannelSpec,
                                    TimingAssuranceDomain)
from csia.v2.evidence import ObservationState


def snap(signals, t=1.0):
    return Snapshot(t=t, signals=signals)


def by_relation(result, relation, component=None):
    rows = [r for r in result.records if r.relation == relation
            and (component is None or r.component == component)]
    assert rows, f"no {relation} record for {component}"
    return rows[0]


# ============================================================ POWER (§4)
def _power(**kw):
    kw.setdefault("rails", (RailSpec("rail_5v", 5.0,
                                     depends_on=("POWER/battery",)),))
    kw.setdefault("battery", BatterySpec())
    kw.setdefault("affected_functions", ("F",))
    return PowerAssuranceDomain(**kw)


def test_power_emits_an_affirmative_healthy_source_reading():
    """§28-B turns on this. Silence cannot exonerate a battery: to move
    suspicion downstream the source has to say something."""
    r = _power().evaluate(snap({"POWER": {
        "battery": {"voltage_v": 22.2, "current_a": 15.0},
        "rail_5v": {"voltage_v": 5.0}}}))
    src = by_relation(r, "power.source_health")
    assert src.observation_state is ObservationState.NOMINAL


def test_a_healthy_battery_with_a_failing_rail_implicates_the_distribution():
    """§28 SCENARIO B, the relation the domain exists for."""
    r = _power().evaluate(snap({"POWER": {
        "battery": {"voltage_v": 22.2, "current_a": 15.0},
        "rail_5v": {"voltage_v": 4.3}}}))
    rail = by_relation(r, "power.rail_tolerance", "rail_5v")
    assert rail.observation_state is ObservationState.VIOLATED
    assert POWER_RAIL_OUT_OF_TOLERANCE in rail.reason_codes
    assert POWER_DISTRIBUTION_SUSPECT in rail.reason_codes
    assert rail.detail["source_exonerated"] == "battery"
    # And the battery itself is NOT adverse -- that is the whole finding.
    assert not by_relation(r, "power.source_health").is_adverse


def test_a_failing_battery_is_not_exonerated_by_its_own_failing_rail():
    """The exoneration must be conditional on the source being healthy, or
    it is not a finding, it is a rule that always fires."""
    d = _power(battery=BatterySpec(esr_ohm=0.02, droop_warn_v=0.3,
                                   droop_fail_v=0.6))
    r = d.evaluate(snap({"POWER": {
        "battery": {"voltage_v": 20.0, "current_a": 15.0,
                    "voltage_reference_v": 22.5},
        "rail_5v": {"voltage_v": 4.3}}}))
    assert by_relation(r, "power.droop_vs_current").is_adverse
    rail = by_relation(r, "power.rail_tolerance", "rail_5v")
    assert POWER_DISTRIBUTION_SUSPECT not in rail.reason_codes


def test_missing_source_telemetry_is_unavailable_not_healthy():
    r = _power().evaluate(snap({"POWER": {"battery": {"voltage_v": 22.2},
                                          "rail_5v": {"voltage_v": 5.0}}}))
    src = by_relation(r, "power.source_health")
    assert src.observation_state is ObservationState.UNAVAILABLE
    assert POWER_TELEMETRY_MISSING in src.reason_codes


def test_a_relation_without_its_declared_inputs_is_reported_not_skipped():
    """A domain that silently skips a relation looks identical to one that
    found it healthy."""
    r = _power().evaluate(snap({"POWER": {
        "battery": {"voltage_v": 22.2, "current_a": 15.0},
        "rail_5v": {"voltage_v": 5.0}}}))
    assert "battery.droop" in r.unevaluated
    assert "battery.cells" in r.unevaluated
    assert "battery.power_w" in r.unevaluated
    assert not any(x.relation == "power.droop_vs_current" for x in r.records)


def test_p_equals_vi_is_checked_only_when_p_is_measured_independently():
    d = _power(battery=BatterySpec(power_tolerance_frac=0.05))
    ok = d.evaluate(snap({"POWER": {
        "battery": {"voltage_v": 20.0, "current_a": 10.0, "power_w": 200.0},
        "rail_5v": {"voltage_v": 5.0}}}))
    assert not by_relation(ok, "power.p_equals_vi").is_adverse
    bad = d.evaluate(snap({"POWER": {
        "battery": {"voltage_v": 20.0, "current_a": 10.0, "power_w": 140.0},
        "rail_5v": {"voltage_v": 5.0}}}))
    assert by_relation(bad, "power.p_equals_vi").is_adverse


def test_the_load_relation_is_one_sided_and_says_so():
    """Over-current at a given demand is a mechanical finding, and claiming
    it in POWER would count it against the wrong domain."""
    d = _power(loads=(LoadSpec("bus", full_load_current_a=40.0),))
    sig = {"POWER": {"battery": {"voltage_v": 22.0, "current_a": 30.0},
                     "rail_5v": {"voltage_v": 5.0},
                     "bus": {"demand_frac": 0.5, "current_a": 5.0}}}
    low = d.evaluate(snap(sig))
    assert by_relation(low, "power.load_current_response").is_adverse
    sig["POWER"]["bus"]["current_a"] = 34.0        # well over 0.5 * 40
    high = d.evaluate(snap(sig))
    assert not by_relation(high, "power.load_current_response").is_adverse


def test_a_rail_carries_its_declared_dependency_into_the_evidence():
    r = _power().evaluate(snap({"POWER": {
        "battery": {"voltage_v": 22.2, "current_a": 15.0},
        "rail_5v": {"voltage_v": 4.3}}}))
    assert by_relation(r, "power.rail_tolerance").dependencies == \
        ("POWER/battery",)


# ========================================================== COMPUTE (§5)
def _compute(**kw):
    kw.setdefault("processes", (ProcessSpec(
        "est", affected_functions=("F",), heartbeat_limit_s=0.1,
        output_age_limit_s=0.1, deadline_s=0.02, queue_depth_limit=8),))
    kw.setdefault("resource", ResourceSpec(affected_functions=("F",)))
    kw.setdefault("affected_functions", ("F",))
    return ComputeAssuranceDomain(**kw)


def _proc(**kw):
    base = {"alive": True, "heartbeat_age_s": 0.01, "output_age_s": 0.02,
            "runtime_s": 0.008, "deadline_misses": 0, "queue_depth": 1,
            "restart_count": 0}
    base.update(kw)
    return {"COMPUTE": {"est": base,
                        "cpu": {"cpu_load": 0.4, "memory_used_frac": 0.5}}}


def test_the_four_compute_questions_are_four_separate_answers():
    """§5. Alive, producing, on time and resourced fail separately and mean
    different things; one health number would destroy the distinction."""
    r = _compute().evaluate(snap(_proc()))
    got = {x.relation for x in r.records}
    assert {"compute.process_alive", "compute.process_producing",
            "compute.deadline_met", "compute.resource_headroom",
            "compute.stability"} <= got


def test_a_stale_heartbeat_beats_a_cheerful_alive_flag():
    """The flag is a claim; the heartbeat is evidence."""
    r = _compute().evaluate(snap(_proc(alive=True, heartbeat_age_s=5.0)))
    alive = by_relation(r, "compute.process_alive")
    assert alive.observation_state is ObservationState.VIOLATED
    assert COMPUTE_HEARTBEAT_STALE in alive.reason_codes


def test_a_dead_process_is_violated():
    r = _compute().evaluate(snap(_proc(alive=False)))
    assert COMPUTE_PROCESS_DEAD in \
        by_relation(r, "compute.process_alive").reason_codes


def test_a_late_value_is_not_automatically_equivalent_to_an_on_time_one():
    """§5's sentence, tested. The domain reports the deadline as missed; what
    that COSTS is the function graph's decision, not this module's."""
    r = _compute().evaluate(snap(_proc(runtime_s=0.030)))
    d = by_relation(r, "compute.deadline_met")
    assert d.observation_state is ObservationState.VIOLATED
    assert COMPUTE_DEADLINE_MISSED in d.reason_codes
    assert d.detail["deadline_slack_s"] == pytest.approx(-0.010)


def test_a_reported_miss_counts_even_when_this_tick_looked_fine():
    """The platform observed something we did not."""
    r = _compute().evaluate(snap(_proc(runtime_s=0.001, deadline_misses=3)))
    assert by_relation(r, "compute.deadline_met").observation_state \
        is ObservationState.VIOLATED


def test_resource_exhaustion_is_reported_separately_from_process_health():
    sig = _proc()
    sig["COMPUTE"]["cpu"]["cpu_load"] = 0.99
    r = _compute().evaluate(snap(sig))
    res = by_relation(r, "compute.resource_headroom")
    assert res.observation_state is ObservationState.VIOLATED
    assert COMPUTE_CPU_SATURATED in res.reason_codes
    assert not by_relation(r, "compute.process_alive").is_adverse


def test_a_process_with_no_declared_deadline_is_not_judged_on_one():
    d = ComputeAssuranceDomain(
        processes=(ProcessSpec("est", affected_functions=("F",)),),
        resource=ResourceSpec(affected_functions=("F",)),
        affected_functions=("F",))
    r = d.evaluate(snap(_proc(runtime_s=99.0)))
    assert "est.deadline" in r.unevaluated
    assert not any(x.relation == "compute.deadline_met" for x in r.records)


# =========================================================== TIMING (§6)
def _timing(**kw):
    kw.setdefault("channels", (ChannelSpec(
        "nav", affected_functions=("F",), transport_budget_s=0.02,
        processing_budget_s=0.02, decision_budget_s=0.01,
        end_to_end_deadline_s=0.05, expected_period_s=0.02,
        jitter_limit_s=0.01),))
    return TimingAssuranceDomain(**kw)


def _stamps(transport=0.004, processing=0.006, decision=0.002,
            interval=0.02, jitter=0.002, t=1.0):
    v = t - interval
    return {"TIMING": {"nav": {
        "t_validity": v, "t_arrival": v + transport,
        "t_processed": v + transport + processing,
        "t_decision": v + transport + processing + decision,
        "interval_s": interval, "jitter_s": jitter}}}


def test_the_delay_is_partitioned_into_segments_that_have_owners():
    """§6. One age field is the sum of four segments and identifies none."""
    r = _timing().evaluate(snap(_stamps()))
    e2e = by_relation(r, "timing.end_to_end")
    segs = e2e.detail["segments_s"]
    assert set(segs) >= {TRANSPORT_DELAY, "PROCESSING_DELAY",
                         "DECISION_DELAY", SENSOR_SLOW}
    assert segs[TRANSPORT_DELAY] == pytest.approx(0.004)


def test_only_a_segment_over_its_own_budget_is_named():
    """The biggest share of an acceptable total is not a finding, and
    reporting it as one trains an operator to ignore the domain."""
    ok = _timing().evaluate(snap(_stamps(transport=0.019)))
    assert by_relation(ok, "timing.end_to_end").detail[
        "segments_over_budget"] == []
    bad = _timing().evaluate(snap(_stamps(transport=0.030)))
    over = by_relation(bad, "timing.end_to_end").detail
    assert over["segments_over_budget"] == [TRANSPORT_DELAY]
    assert over["classification"] == TRANSPORT_DELAY


def test_a_slow_source_is_classified_as_the_source_not_the_transport():
    r = _timing().evaluate(snap(_stamps(interval=0.20)))
    assert by_relation(r, "timing.end_to_end").detail["classification"] \
        == SENSOR_SLOW


def test_an_impossible_stamp_order_is_a_timebase_fault_not_a_negative_latency():
    """§27 CLOCK_DRIFT. A negative latency gets averaged into fake headroom;
    an inconsistent clock is a finding in its own right."""
    r = _timing().evaluate(snap(_stamps(transport=-0.05)))
    clock = by_relation(r, "timing.clock_consistency")
    assert clock.observation_state is ObservationState.VIOLATED
    assert TIMING_CLOCK_INCONSISTENT in clock.reason_codes
    # And nothing downstream publishes arithmetic on stamps just shown bad.
    assert not any(x.relation == "timing.segment_budget" for x in r.records)
    assert "nav" in r.unevaluated


def test_the_end_to_end_deadline_can_fail_with_every_segment_inside_budget():
    """A channel whose segment budgets sum to more than its end-to-end
    deadline is a real misconfiguration, and the honest report is that the
    TOTAL failed with no segment to blame. Naming one anyway would send an
    operator to the wrong place.

    (The aircraft profile's `nav_solution` is deliberately not like this: its
    three budgets sum to exactly its deadline, so the two cannot disagree.)
    """
    d = TimingAssuranceDomain(channels=(ChannelSpec(
        "nav", affected_functions=("F",), transport_budget_s=0.02,
        processing_budget_s=0.02, decision_budget_s=0.01,
        end_to_end_deadline_s=0.04, expected_period_s=0.02),))
    r = d.evaluate(snap(_stamps(transport=0.019, processing=0.019,
                                decision=0.009)))
    e2e = by_relation(r, "timing.end_to_end")
    assert e2e.observation_state is ObservationState.VIOLATED
    assert TIMING_DEADLINE_MISSED in e2e.reason_codes
    assert e2e.detail["segments_over_budget"] == []
    assert e2e.detail["classification"] is None


def test_a_channel_with_no_declared_budget_is_measured_but_not_judged():
    d = TimingAssuranceDomain(channels=(ChannelSpec(
        "nav", affected_functions=("F",)),))
    r = d.evaluate(snap(_stamps()))
    seg = by_relation(r, "timing.segment_budget")
    assert seg.observation_state is ObservationState.NOT_APPLICABLE
    assert seg.measured_value is not None, "measured, just not judged"


# ==================================================== COMMUNICATION (§7)
def _comm(**kw):
    kw.setdefault("links", (LinkSpec(
        "radio", transport="MAVLink", affected_functions=("F",),
        expected_rate_hz=10.0, loss_warn=0.05, loss_fail=0.25,
        crc_error_limit=5, carries=("gps",)),))
    return CommunicationAssuranceDomain(**kw)


def _link(**kw):
    base = {"link_up": True, "observed_rate_hz": 10.0, "loss_frac": 0.0,
            "crc_errors": 0, "duplicates": 0, "reordered": 0,
            "bus_off": False, "reconnects": 0}
    base.update(kw)
    return {"COMMUNICATION": {"radio": base}}


def test_a_link_fault_is_reported_as_a_link_fault():
    """§7. The sensor domain cannot tell a dead receiver from a dead link;
    this domain can, and only because the link is monitored separately."""
    r = _comm().evaluate(snap(_link(bus_off=True)))
    state = by_relation(r, "comm.link_state")
    assert state.observation_state is ObservationState.VIOLATED
    assert COMM_BUS_OFF in state.reason_codes
    assert state.detail["carries"] == ["gps"]


def test_a_dead_link_is_not_also_reported_as_a_rate_failure():
    """Zero messages over a dead link is the same finding twice, and
    double-reporting makes one fault look like several."""
    r = _comm().evaluate(snap(_link(link_up=False, observed_rate_hz=0.0)))
    assert not any(x.relation == "comm.rate" for x in r.records)
    assert "radio" in r.unevaluated


def test_rate_and_loss_are_measured_independently():
    """A link can hold its rate while dropping every third message, and drop
    below rate with no loss at all."""
    r = _comm().evaluate(snap(_link(observed_rate_hz=10.0, loss_frac=0.40)))
    assert not by_relation(r, "comm.rate").is_adverse
    loss = by_relation(r, "comm.loss")
    assert loss.observation_state is ObservationState.VIOLATED
    assert COMM_PACKET_LOSS in loss.reason_codes

    r2 = _comm().evaluate(snap(_link(observed_rate_hz=3.0, loss_frac=0.0)))
    assert COMM_RATE_LOW in by_relation(r2, "comm.rate").reason_codes
    assert not by_relation(r2, "comm.loss").is_adverse


def test_loss_can_be_derived_from_sequence_gaps_when_no_rate_is_reported():
    sig = _link()
    del sig["COMMUNICATION"]["radio"]["loss_frac"]
    sig["COMMUNICATION"]["radio"].update(sequence_gaps=40,
                                         messages_expected=100)
    r = _comm().evaluate(snap(sig))
    assert by_relation(r, "comm.loss").measured_value == pytest.approx(0.40)


def test_the_transport_label_never_changes_a_verdict():
    """§§7, 25. Nothing here parses a protocol; the transport is a record
    field, and a domain that branched on it would not be transport-agnostic."""
    def verdicts(transport):
        d = CommunicationAssuranceDomain(links=(LinkSpec(
            "radio", transport=transport, affected_functions=("F",),
            expected_rate_hz=10.0, loss_warn=0.05, loss_fail=0.25,
            crc_error_limit=5),))
        res = d.evaluate(snap(_link(observed_rate_hz=4.0, loss_frac=0.3)))
        return [(x.relation, x.observation_state) for x in res.records]
    assert verdicts("CAN-FD") == verdicts("DDS") == verdicts("SPI") \
        == verdicts("unspecified")


# ========================================================= ACTUATION (§8)
def _act(**kw):
    kw.setdefault("actuators", (ActuatorSpec(
        "motor", affected_functions=("F",), full_current_a=30.0,
        full_rpm=9000.0),))
    return ActuationAssuranceDomain(**kw)


def _motor(**kw):
    base = {"command": 0.5, "command_transmitted": 0.5, "current_a": 15.0,
            "rpm": 4500.0}
    base.update(kw)
    return {"ACTUATION": {"motor": base}}


def test_no_current_and_no_rpm_is_an_electrical_finding():
    r = _act().evaluate(snap(_motor(current_a=0.3, rpm=0.0)))
    e = by_relation(r, "actuation.electrical_response")
    assert e.observation_state is ObservationState.VIOLATED
    assert ACT_NO_ELECTRICAL_RESPONSE in e.reason_codes


def test_current_present_and_rpm_absent_is_a_different_finding():
    """§28 SCENARIO C. Merging this with the no-current case would discard
    the only discriminating information the domain has."""
    r = _act().evaluate(snap(_motor(current_a=22.0, rpm=300.0)))
    # The electrical side is drawing MORE than expected, not less. That is a
    # separate code and it is emphatically not the no-current signature --
    # which is the distinction the two relations exist to preserve.
    e = by_relation(r, "actuation.electrical_response")
    assert ACT_NO_ELECTRICAL_RESPONSE not in e.reason_codes
    assert e.residual > 0
    m = by_relation(r, "actuation.mechanical_response")
    assert m.observation_state is ObservationState.VIOLATED
    assert ACT_STALLED in m.reason_codes


def test_a_stall_is_not_declared_on_low_rpm_alone():
    """Otherwise a dead ESC reads as a seized motor."""
    r = _act().evaluate(snap(_motor(current_a=0.3, rpm=0.0)))
    m = by_relation(r, "actuation.mechanical_response")
    assert ACT_STALLED not in m.reason_codes


def test_the_electrical_finding_names_its_alternatives_instead_of_choosing():
    """§8: never uniquely attribute without sufficient evidence."""
    d = _act(actuators=(ActuatorSpec(
        "motor", affected_functions=("F",), full_current_a=30.0,
        full_rpm=9000.0,
        depends_on=("POWER/battery", "COMMUNICATION/esc_can")),))
    r = d.evaluate(snap(_motor(current_a=0.3, rpm=0.0)))
    e = by_relation(r, "actuation.electrical_response")
    assert set(e.detail["candidates"]) == {"POWER/battery",
                                           "COMMUNICATION/esc_can"}
    assert e.dependencies == ("POWER/battery", "COMMUNICATION/esc_can")


def test_a_command_that_was_not_transmitted_points_at_the_command_path():
    r = _act().evaluate(snap(_motor(command=0.8, command_transmitted=0.2,
                                    current_a=6.0, rpm=1800.0)))
    c = by_relation(r, "actuation.command_path")
    assert c.observation_state is ObservationState.VIOLATED
    assert c.detail["candidate"] == "COMMUNICATION or command path"


def test_below_the_declared_floor_nothing_is_concluded():
    """Near-zero command, near-zero everything: an expected response is not
    distinguishable from standing losses, and a domain that reported a fault
    there would fire on every idle tick."""
    r = _act().evaluate(snap(_motor(command=0.02, command_transmitted=0.02,
                                    current_a=0.0, rpm=0.0)))
    for rel in ("actuation.electrical_response",
                "actuation.mechanical_response"):
        assert by_relation(r, rel).observation_state \
            is ObservationState.NOT_APPLICABLE


def test_a_physical_channel_is_only_judged_when_the_host_declares_one():
    r = _act().evaluate(snap(_motor()))
    assert "motor.physical" in r.unevaluated
    d = _act(actuators=(ActuatorSpec(
        "motor", affected_functions=("F",), full_current_a=30.0,
        full_rpm=9000.0, physical_signal="thrust_n", full_physical=40.0),))
    sig = _motor()
    sig["ACTUATION"]["motor"]["thrust_n"] = 4.0        # expected ~20
    r2 = d.evaluate(snap(sig))
    assert by_relation(r2, "actuation.physical_response").is_adverse


# ================================================= determinism, all domains
@pytest.mark.parametrize("build,signals", [
    (_power, {"POWER": {"battery": {"voltage_v": 22.0, "current_a": 15.0},
                        "rail_5v": {"voltage_v": 4.4}}}),
    (_compute, _proc(runtime_s=0.03)),
    (_timing, _stamps(transport=0.03)),
    (_comm, _link(loss_frac=0.3)),
    (_act, _motor(current_a=0.2, rpm=0.0)),
])
def test_the_same_snapshot_produces_the_same_records_every_time(build,
                                                                signals):
    """§2's determinism requirement. No clock reads, no RNG, no state."""
    d = build()
    a = [r.to_dict() for r in d.evaluate(snap(signals)).records]
    b = [r.to_dict() for r in d.evaluate(snap(signals)).records]
    assert a == b
