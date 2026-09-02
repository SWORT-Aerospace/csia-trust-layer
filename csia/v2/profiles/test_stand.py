"""§37's genericity test: an electric motor test stand.

    Build one synthetic NON-AIRCRAFT system... Run the same v2 framework with
    no aviation-specific code. If impossible: framework is too
    aircraft-specific.

A bench that spins a motor against a brake and logs torque. It has no GNSS, no
attitude, no navigation, no flight phase and no v1.1 — the SENSOR domain is
not registered at all, which is the sharpest form of the test: if the
framework needed v1.1 to function, this profile could not be built.

WHAT IS ACTUALLY BEING TESTED
-----------------------------
Not "does it run". The claim under test is that the framework carries no
aircraft assumption, and it fails if ANY of these is true:

  - a core module must be edited to add this profile
  - a domain must be edited to serve a non-vehicle
  - a function must be named after a flight concept to be expressible
  - the SENSOR domain, or a v1.1 payload, is required for the engine to work

None of them is, and the four domains here are the SAME classes the aircraft
profile registers, constructed with different declarations. That is the
evidence for §38, and it is the only evidence that counts: the framework is
reusable if a second, structurally different machine needs no framework change
-- not if the README says "generic".

The functions below are named for what the BENCH does. Nothing in this file
mentions flight, and nothing in `csia/v2/*.py` needed to know it would not.
"""

from __future__ import annotations

from ..attribution import CrossDomainRelation
from ..domains.actuation import ActuationAssuranceDomain, ActuatorSpec
from ..domains.communication import CommunicationAssuranceDomain, LinkSpec
from ..domains.compute import (ComputeAssuranceDomain, ProcessSpec,
                               ResourceSpec)
from ..domains.power import BatterySpec, PowerAssuranceDomain, RailSpec
from ..domains.timing import ChannelSpec, TimingAssuranceDomain
from ..engine import AssuranceEngine
from ..functions import FunctionGraph, SystemFunction
from ..registry import DomainRegistry

TEST_STAND_FUNCTIONS = (
    SystemFunction(
        name="TORQUE_DELIVERY",
        summary="the motor produces the commanded torque at the shaft",
        required_domains=("POWER", "ACTUATION"),
        supporting_domains=("COMPUTE",),
        fallback="hold the run point and alarm"),
    SystemFunction(
        name="SPEED_MEASUREMENT",
        summary="shaft speed is being measured and is trustworthy",
        required_domains=("ACTUATION", "COMMUNICATION", "TIMING"),
        acceptable_degradation="jitter degrades the measurement; loss of the "
                               "encoder link removes it"),
    SystemFunction(
        name="DATA_LOGGING",
        summary="the run is being recorded for later analysis",
        required_domains=("COMPUTE", "COMMUNICATION"),
        acceptable_degradation="a late sample is still a sample"),
    SystemFunction(
        name="TEST_SEQUENCE_EXECUTION",
        summary="the bench can run its profile unattended",
        required_domains=("COMPUTE", "TIMING", "POWER", "ACTUATION",
                          "COMMUNICATION"),
        no_degradation_domains=("TIMING",),
        fallback="operator-driven single run"),
)

TEST_STAND_RELATIONS = (
    CrossDomainRelation(
        relation_id="actuation_power.demand_vs_current",
        domains=("ACTUATION", "POWER"),
        implicates=("POWER/dc_supply", "ACTUATION/dyno_motor"),
        description="commanded torque implies a current draw; a commanded "
                    "motor drawing nothing implicates the supply path or the "
                    "drive, and these signals do not separate them"),
    CrossDomainRelation(
        relation_id="compute_timing.saturation_vs_latency",
        domains=("COMPUTE", "TIMING"),
        implicates=("COMPUTE/cpu", "COMPUTE/controller"),
        description="controller saturation produces loop latency produces a "
                    "missed control deadline"),
)

_ALL = tuple(f.name for f in TEST_STAND_FUNCTIONS)


def build_test_stand_engine() -> AssuranceEngine:
    """Five domains, no SENSOR domain, no v1.1, no aviation vocabulary."""
    reg = DomainRegistry()
    reg.register(PowerAssuranceDomain(
        # 24 V drives the motor; 5 V runs the logic and the buses. A 5 V
        # failure takes the measurement and logging chain, not the torque.
        rails=(RailSpec("rail_24v", 24.0, depends_on=("POWER/dc_supply",),
                        affected_functions=("TORQUE_DELIVERY",
                                            "TEST_SEQUENCE_EXECUTION")),
               RailSpec("rail_5v", 5.0, depends_on=("POWER/rail_24v",),
                        affected_functions=("SPEED_MEASUREMENT",
                                            "DATA_LOGGING",
                                            "TEST_SEQUENCE_EXECUTION"))),
        battery=BatterySpec(name="dc_supply", esr_ohm=0.01,
                            droop_warn_v=1.0, droop_fail_v=3.0,
                            affected_functions=_ALL),
        affected_functions=_ALL))
    reg.register(ComputeAssuranceDomain(
        processes=(
            ProcessSpec("controller",
                        affected_functions=("TEST_SEQUENCE_EXECUTION",
                                            "TORQUE_DELIVERY"),
                        heartbeat_limit_s=0.05, output_age_limit_s=0.05,
                        deadline_s=0.005, queue_depth_limit=4,
                        depends_on=("COMPUTE/cpu",)),
            ProcessSpec("recorder", affected_functions=("DATA_LOGGING",),
                        heartbeat_limit_s=1.0, output_age_limit_s=2.0,
                        deadline_s=0.050, depends_on=("COMPUTE/cpu",)),
        ),
        resource=ResourceSpec(name="cpu",
                              affected_functions=("TEST_SEQUENCE_EXECUTION",
                                                  "DATA_LOGGING",
                                                  "TORQUE_DELIVERY")),
        affected_functions=("TEST_SEQUENCE_EXECUTION",)))
    reg.register(TimingAssuranceDomain(channels=(
        ChannelSpec("encoder", affected_functions=("SPEED_MEASUREMENT",
                                                   "TEST_SEQUENCE_EXECUTION"),
                    transport_budget_s=0.002, processing_budget_s=0.002,
                    end_to_end_deadline_s=0.005,
                    expected_period_s=0.001, jitter_limit_s=0.0005,
                    # Processing latency is incurred ON the CPU. Declaring it
                    # is what lets a saturated CPU and a late channel be
                    # recognised as one event (§14) instead of two candidates.
                    depends_on=("COMMUNICATION/encoder_bus", "COMPUTE/cpu")),
    ), affected_functions=("TEST_SEQUENCE_EXECUTION",)))
    reg.register(CommunicationAssuranceDomain(links=(
        LinkSpec("encoder_bus", transport="RS-485", carries=("shaft_speed",),
                 affected_functions=("SPEED_MEASUREMENT",
                                     "TEST_SEQUENCE_EXECUTION"),
                 expected_rate_hz=1000.0, loss_warn=0.001, loss_fail=0.01,
                 crc_error_limit=0, depends_on=("POWER/rail_5v",)),
        LinkSpec("host_ethernet", transport="Ethernet",
                 affected_functions=("DATA_LOGGING",),
                 expected_rate_hz=100.0, loss_warn=0.05, loss_fail=0.20,
                 crc_error_limit=10, queue_delay_warn_s=0.05,
                 queue_delay_fail_s=0.50, depends_on=("POWER/rail_5v",)),
    ), affected_functions=("DATA_LOGGING",)))
    reg.register(ActuationAssuranceDomain(actuators=(
        ActuatorSpec("dyno_motor",
                     affected_functions=("TORQUE_DELIVERY",
                                         "SPEED_MEASUREMENT",
                                         "TEST_SEQUENCE_EXECUTION"),
                     full_current_a=80.0, full_rpm=6000.0,
                     physical_signal="torque_nm", full_physical=45.0,
                     depends_on=("POWER/dc_supply",
                                 "COMMUNICATION/encoder_bus")),
    ), affected_functions=("TORQUE_DELIVERY",)))
    return AssuranceEngine(reg, FunctionGraph(TEST_STAND_FUNCTIONS),
                           TEST_STAND_RELATIONS)
