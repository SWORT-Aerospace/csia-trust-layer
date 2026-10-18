"""The multirotor profile — the platform v1.1 already serves.

Spec: `engineering/v2/FUNCTION_DEPENDENCY_SPEC.md`.

HOW §36 AND §17 ARE BOTH SATISFIED
----------------------------------
They look contradictory. §36 says the plugin layer may not alter v1.1's
function eligibility; §17's worked example shows `PRECISION_NAVIGATION`
INELIGIBLE because of a COMPUTE/TIMING violation, which is an alteration if
the two `PRECISION_NAVIGATION`s are the same statement.

They are not the same statement, and the profile keeps them distinguishable:

    domain_states["SENSOR"]   IS the v1.1 verdict, transcribed, unaltered.
                              A bijection maps it back exactly, and a test
                              checks the round trip on every payload.

    the v2 function state     is the roll-up over EVERY required domain,
                              of which SENSOR is one.

So v1.1's answer is always visible, always intact, and never the only input.
Two structural properties make that checkable rather than promised:

  1. **Exactness.** With only the SENSOR domain registered
     (`build_v1_1_baseline_engine`), every v2 function state equals the v1.1
     state exactly. That is §36's baseline test.

  2. **Monotonicity.** Adding domains can only hold or restrict a function,
     never relax it — because the roll-up takes the worst state and every
     `_MAP` entry is order-preserving. v2 can never call something eligible
     that v1.1 called ineligible.

For those two to hold, the six v1.1-named functions must list SENSOR as a
REQUIRED domain and must NOT list it in `no_degradation_domains`. Required,
because a supporting domain's INELIGIBLE is softened to DEGRADED, which would
relax a v1.1 verdict; not no-degradation, because that would harden one. A
test asserts both, so the guarantee cannot be lost by editing this table.
"""

from __future__ import annotations

from ..attribution import CrossDomainRelation
from ..domains.actuation import ActuationAssuranceDomain, ActuatorSpec
from ..domains.communication import (CommunicationAssuranceDomain, LinkSpec)
from ..domains.compute import (ComputeAssuranceDomain, ProcessSpec,
                               ResourceSpec)
from ..domains.navigation import NavigationAssuranceDomain
from ..domains.power import BatterySpec, PowerAssuranceDomain, RailSpec
from ..domains.timing import ChannelSpec, TimingAssuranceDomain
from ..engine import AssuranceEngine
from ..functions import FunctionGraph, SystemFunction
from ..registry import DomainRegistry

#: The five function names v1.1 owns. Same names, deliberately: a v2 consumer
#: asking about PRECISION_NAVIGATION is asking about the same capability, and
#: renaming it would hide the relationship rather than clarify it.
#:
#: PRECISION_LANDING IS ABSENT, AND THAT IS INHERITED, NOT AN OVERSIGHT.
#: `engineering/v1_1/FUNCTION_REQUIREMENTS.yaml` omits it under Phase 4 §6
#: ("if a function cannot be specified honestly: omit it") because no landing
#: reference — rangefinder, optical flow, beacon — exists in the node set. v2
#: adds power, compute, timing, communication and actuation evidence; it adds
#: no landing reference. Nothing about the omission has changed, so listing it
#: here would either report a permanent UNKNOWN or quietly reinstate a
#: function v1.1 declined to specify. It stays omitted until such a source
#: exists.
V1_1_FUNCTIONS = ("COARSE_NAVIGATION", "GEOFENCE_SUPPORT",
                  "INERTIAL_CONTINUATION", "POSITION_HOLD",
                  "PRECISION_NAVIGATION")

_NAV_SET = ("PRECISION_NAVIGATION", "POSITION_HOLD", "AUTONOMOUS_MISSION")

AIRCRAFT_FUNCTIONS = (
    # -- the six v1.1 names, extended across domains -------------------
    SystemFunction(
        name="PRECISION_NAVIGATION",
        summary="metre-class positioning for guided flight",
        required_domains=("SENSOR", "COMPUTE", "TIMING", "POWER"),
        no_degradation_domains=("TIMING",),
        fallback="COARSE_NAVIGATION",
        acceptable_degradation="none: a late position is a wrong position "
                               "at speed"),
    SystemFunction(
        name="COARSE_NAVIGATION",
        summary="position good enough to hold a corridor",
        required_domains=("SENSOR", "POWER"),
        supporting_domains=("COMPUTE", "TIMING"),
        fallback="INERTIAL_CONTINUATION",
        acceptable_degradation="latency and compute pressure degrade but do "
                               "not remove it"),
    SystemFunction(
        name="POSITION_HOLD",
        summary="station keeping against drift",
        required_domains=("SENSOR", "COMPUTE", "TIMING", "POWER"),
        no_degradation_domains=("TIMING",),
        fallback="attitude hold"),
    # PRECISION_LANDING would sit here. It does not, for the reason recorded
    # on V1_1_FUNCTIONS above: v1.1 omitted it for want of a landing
    # reference and v2 adds none.
    SystemFunction(
        name="GEOFENCE_SUPPORT",
        summary="boundary enforcement",
        required_domains=("SENSOR", "POWER"),
        supporting_domains=("COMPUTE",)),
    SystemFunction(
        name="INERTIAL_CONTINUATION",
        summary="dead reckoning through an outage",
        required_domains=("SENSOR", "POWER")),

    # -- v2-only functions, which v1.1 could not express ---------------
    SystemFunction(
        name="SENSING",
        summary="sources are being received and are usable at all",
        required_domains=("SENSOR", "POWER", "COMMUNICATION"),
        supporting_domains=("COMPUTE",),
        acceptable_degradation="a degraded source set still senses"),
    SystemFunction(
        name="TELEMETRY",
        summary="the ground station is being kept informed",
        required_domains=("COMMUNICATION", "POWER"),
        supporting_domains=("COMPUTE", "TIMING"),
        fallback="onboard log only",
        acceptable_degradation="latency and loss degrade telemetry; they do "
                               "not stop it"),
    SystemFunction(
        name="LOGGING",
        summary="an assurance record is being written",
        required_domains=("COMPUTE", "POWER"),
        # Deliberately NOT no_degradation on TIMING. The contrast with
        # PRECISION_NAVIGATION is the point of §15: the same late value is
        # fatal to one function and irrelevant to another, and the difference
        # is a declared requirement rather than a global rule.
        acceptable_degradation="a late log entry is still a log entry"),
    SystemFunction(
        name="PROPULSION",
        summary="commanded thrust is being produced",
        required_domains=("POWER", "ACTUATION"),
        supporting_domains=("COMPUTE",)),
    SystemFunction(
        name="AUTONOMOUS_MISSION",
        summary="the vehicle can execute a mission without an operator",
        required_domains=("SENSOR", "COMPUTE", "TIMING", "POWER",
                          "ACTUATION"),
        supporting_domains=("COMMUNICATION",),
        no_degradation_domains=("TIMING",),
        fallback="operator-supervised flight"),
)

#: §14. Declared, listed in the API, and reviewable. A relation names the
#: components it can point at; a component named here but carrying no adverse
#: evidence of its own comes out UNSUPPORTED (§29), never promoted.
AIRCRAFT_RELATIONS = (
    CrossDomainRelation(
        relation_id="actuation_power.demand_vs_current",
        domains=("ACTUATION", "POWER"),
        implicates=("POWER/battery", "ACTUATION/motor_0"),
        description="actuator demand implies an expected current draw; a "
                    "commanded actuator drawing nothing implicates the power "
                    "path OR the actuator, and these signals do not separate "
                    "them"),
    CrossDomainRelation(
        relation_id="compute_timing.saturation_vs_latency",
        domains=("COMPUTE", "TIMING"),
        implicates=("COMPUTE/cpu", "COMPUTE/state_estimator"),
        description="CPU saturation produces processing latency produces a "
                    "missed output deadline; the timing finding and the "
                    "compute finding are one event seen twice"),
    CrossDomainRelation(
        relation_id="comm_sensor.link_vs_source",
        domains=("COMMUNICATION", "SENSOR"),
        implicates=("COMMUNICATION/gnss_serial",),
        description="a source that has gone quiet behind a failing link is a "
                    "communication candidate, not a sensor fault"),
    CrossDomainRelation(
        relation_id="power_sensor.shared_rail",
        domains=("POWER", "SENSOR"),
        implicates=("POWER/rail_5v",),
        description="sources sharing a rail degrade together when the rail "
                    "sags; the rail is retained as a common-cause "
                    "alternative rather than replacing the sensor "
                    "explanation"),
)

#: §22: platform wiring, declared. Which rail each v1.1 source hangs off.
#: This is a fact about the harness, not an estimate.
SOURCE_DEPENDENCIES = {
    "imu0": ("POWER/rail_3v3",), "imu1": ("POWER/rail_3v3",),
    "mag": ("POWER/rail_3v3",), "baro": ("POWER/rail_3v3",),
    "gps": ("POWER/rail_5v", "COMMUNICATION/gnss_serial"),
    "vibration": ("POWER/rail_3v3",),
    "motor_esc": ("POWER/battery", "COMMUNICATION/esc_can"),
    "battery": ("POWER/battery",),
}

_ALL = tuple(f.name for f in AIRCRAFT_FUNCTIONS)


def build_aircraft_engine() -> AssuranceEngine:
    """The full six-domain profile."""
    reg = DomainRegistry()
    reg.register(NavigationAssuranceDomain(
        affected_functions=("SENSING", "AUTONOMOUS_MISSION"),
        source_dependencies=SOURCE_DEPENDENCIES))
    reg.register(PowerAssuranceDomain(
        # Each rail declares WHAT IT FEEDS. `SOURCE_DEPENDENCIES` above says
        # which source hangs off which rail; this says what that costs in
        # function terms, and the two are consistent by construction.
        #
        # 5 V carries the GNSS receiver and the telemetry radio, so it takes
        # the GNSS-dependent functions and telemetry with it. It does NOT
        # take INERTIAL_CONTINUATION, LOGGING or PROPULSION: the IMUs are on
        # 3V3 and the motors are on the battery, and a monitor that reported
        # those lost would be reporting a vehicle that cannot fly home when
        # in fact it can.
        rails=(RailSpec("rail_5v", 5.0, depends_on=("POWER/battery",),
                        affected_functions=("SENSING", "TELEMETRY",
                                            "COARSE_NAVIGATION",
                                            "POSITION_HOLD",
                                            "PRECISION_NAVIGATION",
                                            "GEOFENCE_SUPPORT",
                                            "AUTONOMOUS_MISSION")),
               # 3V3 carries the inertial set, the magnetometer and the
               # barometer, so everything that senses depends on it --
               # including dead reckoning.
               RailSpec("rail_3v3", 3.3, depends_on=("POWER/rail_5v",),
                        affected_functions=("SENSING", "COARSE_NAVIGATION",
                                            "POSITION_HOLD",
                                            "PRECISION_NAVIGATION",
                                            "GEOFENCE_SUPPORT",
                                            "INERTIAL_CONTINUATION",
                                            "AUTONOMOUS_MISSION"))),
        battery=BatterySpec(esr_ohm=0.02, droop_warn_v=0.30,
                            droop_fail_v=0.60,
                            cell_spread_warn_v=0.05,
                            cell_spread_fail_v=0.15,
                            # The source feeds everything, so here the
                            # all-functions attachment IS the wiring.
                            affected_functions=_ALL),
        affected_functions=_ALL))
    reg.register(ComputeAssuranceDomain(
        processes=(
            ProcessSpec("state_estimator", affected_functions=_NAV_SET,
                        heartbeat_limit_s=0.10, output_age_limit_s=0.10,
                        deadline_s=0.020, queue_depth_limit=8,
                        depends_on=("COMPUTE/cpu", "SENSOR/source.imu0")),
            ProcessSpec("csia", affected_functions=("SENSING",),
                        heartbeat_limit_s=0.20, output_age_limit_s=0.20,
                        deadline_s=0.010, depends_on=("COMPUTE/cpu",)),
            ProcessSpec("logger", affected_functions=("LOGGING",),
                        heartbeat_limit_s=1.0, output_age_limit_s=2.0,
                        deadline_s=0.100, depends_on=("COMPUTE/cpu",)),
        ),
        resource=ResourceSpec(
            name="cpu",
            affected_functions=_NAV_SET + ("LOGGING", "SENSING")),
        affected_functions=("SENSING",)))
    reg.register(TimingAssuranceDomain(channels=(
        ChannelSpec("nav_solution", affected_functions=_NAV_SET,
                    transport_budget_s=0.020, processing_budget_s=0.020,
                    decision_budget_s=0.010,
                    end_to_end_deadline_s=0.050,
                    expected_period_s=0.020, jitter_limit_s=0.010,
                    # The position this channel carries arrives over the
                    # GNSS link and is computed on the CPU by the estimator.
                    # Declaring the link is what lets a healthy link REFUTE
                    # the transport explanation for a late value -- without
                    # it, "the source was slow" and "the link was slow" are
                    # not separable, because both live in validity->arrival.
                    depends_on=("COMPUTE/state_estimator", "COMPUTE/cpu",
                                "COMMUNICATION/gnss_serial")),
        ChannelSpec("telemetry_downlink", affected_functions=("TELEMETRY",),
                    transport_budget_s=0.500, processing_budget_s=0.100,
                    end_to_end_deadline_s=1.000,
                    expected_period_s=0.200, jitter_limit_s=0.200,
                    depends_on=("COMMUNICATION/telemetry_radio",)),
    )))
    reg.register(CommunicationAssuranceDomain(links=(
        LinkSpec("gnss_serial", transport="UART", carries=("gps",),
                 affected_functions=("SENSING",),
                 expected_rate_hz=5.0, loss_warn=0.02, loss_fail=0.10,
                 crc_error_limit=0, queue_delay_warn_s=0.10,
                 queue_delay_fail_s=0.50,
                 depends_on=("POWER/rail_3v3",)),
        LinkSpec("telemetry_radio", transport="MAVLink",
                 affected_functions=("TELEMETRY",),
                 expected_rate_hz=10.0, loss_warn=0.05, loss_fail=0.25,
                 crc_error_limit=5, queue_delay_warn_s=0.30,
                 queue_delay_fail_s=1.00,
                 depends_on=("POWER/rail_5v",)),
        LinkSpec("esc_can", transport="CAN", carries=("motor_esc",),
                 affected_functions=("PROPULSION", "AUTONOMOUS_MISSION"),
                 expected_rate_hz=50.0, loss_warn=0.01, loss_fail=0.05,
                 crc_error_limit=0,
                 depends_on=("POWER/battery",)),
    )))
    reg.register(ActuationAssuranceDomain(actuators=(
        ActuatorSpec("motor_0",
                     affected_functions=("PROPULSION", "AUTONOMOUS_MISSION"),
                     full_current_a=30.0, full_rpm=9000.0,
                     depends_on=("POWER/battery", "COMMUNICATION/esc_can")),
    ), affected_functions=("PROPULSION",)))
    from ..signatures import PREDICATES, SYMPTOMS
    return AssuranceEngine(reg, FunctionGraph(AIRCRAFT_FUNCTIONS),
                           AIRCRAFT_RELATIONS,
                           symptoms=SYMPTOMS, predicates=PREDICATES)


def build_v1_1_baseline_engine() -> AssuranceEngine:
    """§36's baseline: the SENSOR domain alone, over the six v1.1 functions.

    With nothing else registered every function's only evidence is the v1.1
    verdict, so any difference between this engine's output and the payload's
    `function_eligibility` is an alteration by the plugin layer. There is
    nowhere else it could have come from.
    """
    reg = DomainRegistry()
    reg.register(NavigationAssuranceDomain(affected_functions=("SENSING",)))
    fns = tuple(SystemFunction(name=n, summary=f"v1.1 {n}, unmodified",
                               required_domains=("SENSOR",))
                for n in V1_1_FUNCTIONS)
    return AssuranceEngine(reg, FunctionGraph(fns), ())
