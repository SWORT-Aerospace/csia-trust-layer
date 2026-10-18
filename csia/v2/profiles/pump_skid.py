"""§30's SECOND genericity profile: a two-stage industrial pump skid.

Spec: `engineering/v2/SECOND_GENERIC_PROFILE_SPEC.md`.

    In addition to motor test stand, add ONE small structurally different
    synthetic profile... Goal: prove domain/function/localization framework
    survives another topology.

WHY A PUMP SKID AND NOT A SECOND MOTOR
---------------------------------------
The motor test stand and the multirotor share a topology: one command, one
actuator, one response. A second profile shaped the same way would prove
almost nothing. This one is structurally different in three ways that each
exercise something the first two never did:

  1. **REDUNDANT ACTUATION.** Two pumps in parallel, either of which can hold
     the duty. Losing one is DEGRADED, not INELIGIBLE — which is §11's
     one-of-N and which neither existing profile uses.

  2. **A FALLBACK REQUIREMENT SET.** Pressure regulation normally runs closed
     loop on the transmitter; if the transmitter is gone it can run open loop
     on commanded speed, at reduced capability. That is §11's alternate
     requirement set, and again neither existing profile uses it.

  3. **NO SENSOR DOMAIN AND NO ACTUATION-SIDE POSITION.** The bench measures
     torque; the skid measures a downstream *process variable* (discharge
     pressure) which is affected by both pumps at once. The physical response
     is shared rather than per-actuator.

**Nothing in `csia/v2/` was changed to add this profile.** That is the claim
under test, and if it had needed a core change §30 would have failed.

NO PROCESS ENGINEERING IS CLAIMED
----------------------------------
Every value here is configuration chosen to exercise a declared threshold.
No pump has been characterised, no curve has been measured, and the numbers
support no statement about real pumps.
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
from ..scenarios import Scenario, ramp

PUMP_SKID_FUNCTIONS = (
    SystemFunction(
        name="FLOW_DELIVERY",
        summary="the skid delivers its duty flow",
        required_domains=("POWER",),
        # §11 ONE-OF-N over COMPONENTS: either pump holds the duty alone.
        redundant_groups=(("ACTUATION/pump_a", "ACTUATION/pump_b"),),
        supporting_domains=("COMPUTE",),
        acceptable_degradation="one pump down is reduced margin, not lost "
                               "flow"),
    SystemFunction(
        name="PRESSURE_REGULATION",
        summary="discharge pressure is held at setpoint",
        required_domains=("COMPUTE", "TIMING", "COMMUNICATION"),
        # §11 FALLBACK: without the transmitter it can run open loop on
        # commanded speed, which is a real capability at reduced quality.
        fallback_requirements=(("OPEN_LOOP_ON_SPEED", ("COMPUTE", "POWER")),),
        fallback="open-loop speed control at reduced accuracy",
        no_degradation_domains=("TIMING",)),
    SystemFunction(
        name="CONDITION_MONITORING",
        summary="the skid is recording enough to diagnose itself later",
        required_domains=("COMPUTE",),
        optional_domains=("TIMING",),
        acceptable_degradation="late samples still diagnose"),
    SystemFunction(
        name="UNATTENDED_OPERATION",
        summary="the skid can run a duty cycle without an operator",
        required_domains=("POWER", "COMPUTE", "TIMING", "COMMUNICATION"),
        redundant_groups=(("ACTUATION/pump_a", "ACTUATION/pump_b"),),
        no_degradation_domains=("TIMING",),
        fallback="operator-attended running"),
)

PUMP_SKID_RELATIONS = (
    CrossDomainRelation(
        relation_id="actuation_power.demand_vs_current",
        domains=("ACTUATION", "POWER"),
        implicates=("POWER/mains_dc", "ACTUATION/pump_a", "ACTUATION/pump_b"),
        description="commanded speed implies a current draw at each pump; a "
                    "commanded pump drawing nothing implicates the supply "
                    "path or the drive"),
    CrossDomainRelation(
        relation_id="compute_timing.saturation_vs_latency",
        domains=("COMPUTE", "TIMING"),
        implicates=("COMPUTE/cpu", "COMPUTE/regulator"),
        description="controller saturation produces loop latency produces a "
                    "missed regulation deadline"),
)

_ALL = tuple(f.name for f in PUMP_SKID_FUNCTIONS)


def build_pump_skid_engine() -> AssuranceEngine:
    """Five domains, two redundant actuators, one fallback requirement set."""
    from ..signatures import PREDICATES, SYMPTOMS
    reg = DomainRegistry()
    reg.register(PowerAssuranceDomain(
        rails=(RailSpec("rail_24v", 24.0, depends_on=("POWER/mains_dc",),
                        affected_functions=("PRESSURE_REGULATION",
                                            "CONDITION_MONITORING",
                                            "UNATTENDED_OPERATION")),),
        battery=BatterySpec(name="mains_dc", esr_ohm=0.005,
                            droop_warn_v=2.0, droop_fail_v=6.0,
                            affected_functions=_ALL),
        affected_functions=_ALL))
    reg.register(ComputeAssuranceDomain(
        processes=(
            ProcessSpec("regulator",
                        affected_functions=("PRESSURE_REGULATION",
                                            "UNATTENDED_OPERATION"),
                        heartbeat_limit_s=0.20, output_age_limit_s=0.20,
                        deadline_s=0.020, queue_depth_limit=4,
                        depends_on=("COMPUTE/cpu",
                                    "COMMUNICATION/fieldbus")),
            ProcessSpec("historian",
                        affected_functions=("CONDITION_MONITORING",),
                        heartbeat_limit_s=2.0, output_age_limit_s=5.0,
                        deadline_s=0.200, depends_on=("COMPUTE/cpu",)),
        ),
        resource=ResourceSpec(name="cpu", affected_functions=(
            "PRESSURE_REGULATION", "CONDITION_MONITORING",
            "UNATTENDED_OPERATION", "FLOW_DELIVERY")),
        affected_functions=("UNATTENDED_OPERATION",)))
    reg.register(TimingAssuranceDomain(channels=(
        ChannelSpec("pressure_loop",
                    affected_functions=("PRESSURE_REGULATION",
                                        "UNATTENDED_OPERATION"),
                    transport_budget_s=0.010, processing_budget_s=0.020,
                    decision_budget_s=0.005,
                    end_to_end_deadline_s=0.035,
                    expected_period_s=0.020, jitter_limit_s=0.005,
                    depends_on=("COMPUTE/regulator", "COMPUTE/cpu",
                                "COMMUNICATION/fieldbus")),
    ), affected_functions=("UNATTENDED_OPERATION",)))
    reg.register(CommunicationAssuranceDomain(links=(
        LinkSpec("fieldbus", transport="Modbus-RTU",
                 carries=("discharge_pressure", "pump_speed"),
                 affected_functions=("PRESSURE_REGULATION",
                                     "UNATTENDED_OPERATION"),
                 expected_rate_hz=50.0, loss_warn=0.01, loss_fail=0.05,
                 crc_error_limit=0, queue_delay_warn_s=0.02,
                 queue_delay_fail_s=0.10, depends_on=("POWER/rail_24v",)),
    ), affected_functions=("PRESSURE_REGULATION",)))
    reg.register(ActuationAssuranceDomain(actuators=(
        # Two pumps in parallel. Either holds the duty; the FUNCTION graph
        # expresses that as a one-of-N group, and the DOMAIN does not need to
        # know about redundancy at all.
        ActuatorSpec("pump_a",
                     affected_functions=("FLOW_DELIVERY",
                                         "UNATTENDED_OPERATION"),
                     full_current_a=40.0, full_rpm=2900.0,
                     physical_signal="discharge_bar", full_physical=6.0,
                     depends_on=("POWER/mains_dc",
                                 "COMMUNICATION/fieldbus")),
        ActuatorSpec("pump_b",
                     affected_functions=("FLOW_DELIVERY",
                                         "UNATTENDED_OPERATION"),
                     full_current_a=40.0, full_rpm=2900.0,
                     physical_signal="discharge_bar", full_physical=6.0,
                     depends_on=("POWER/mains_dc",
                                 "COMMUNICATION/fieldbus")),
    ), affected_functions=("FLOW_DELIVERY",)))
    return AssuranceEngine(reg, FunctionGraph(PUMP_SKID_FUNCTIONS),
                           PUMP_SKID_RELATIONS,
                           symptoms=SYMPTOMS, predicates=PREDICATES)


# ------------------------------------------------------------- signals
PUMP_SKID_NOMINAL = {
    "POWER": {
        "mains_dc": {"voltage_v": 48.0, "current_a": 62.0, "power_w": 2976.0,
                     "voltage_reference_v": 48.3},
        "rail_24v": {"voltage_v": 24.05},
    },
    "COMPUTE": {
        "regulator": {"alive": True, "heartbeat_age_s": 0.02,
                      "output_age_s": 0.04, "runtime_s": 0.008,
                      "deadline_misses": 0, "queue_depth": 1,
                      "restart_count": 0},
        "historian": {"alive": True, "heartbeat_age_s": 0.5,
                      "output_age_s": 1.0, "runtime_s": 0.050,
                      "deadline_misses": 0, "queue_depth": 2,
                      "restart_count": 0},
        "cpu": {"cpu_load": 0.38, "memory_used_frac": 0.45,
                "throttled": False, "reset_reason": "POWER_ON"},
    },
    "TIMING": {
        "pressure_loop": {"transport_s": 0.004, "processing_s": 0.008,
                          "decision_s": 0.002, "interval_s": 0.020,
                          "jitter_s": 0.001},
    },
    "COMMUNICATION": {
        "fieldbus": {"link_up": True, "observed_rate_hz": 50.0,
                     "loss_frac": 0.0, "crc_errors": 0, "duplicates": 0,
                     "reordered": 0, "queue_delay_s": 0.004,
                     "bus_off": False, "reconnects": 0},
    },
    "ACTUATION": {
        "pump_a": {"command": 0.70, "command_transmitted": 0.70,
                   "current_a": 28.0, "rpm": 2030.0, "discharge_bar": 4.2},
        "pump_b": {"command": 0.70, "command_transmitted": 0.70,
                   "current_a": 28.0, "rpm": 2030.0, "discharge_bar": 4.2},
    },
}


def _one_pump_down(sig, frac, t):
    """§11's one-of-N, exercised: pump B loses its drive entirely."""
    if frac < 0.30:
        return
    sig["ACTUATION"]["pump_b"]["current_a"] = 0.3
    sig["ACTUATION"]["pump_b"]["rpm"] = 0.0
    sig["ACTUATION"]["pump_b"]["discharge_bar"] = 0.1


def _both_pumps_down(sig, frac, t):
    if frac < 0.30:
        return
    for pump in ("pump_a", "pump_b"):
        sig["ACTUATION"][pump]["current_a"] = 0.3
        sig["ACTUATION"][pump]["rpm"] = 0.0
        sig["ACTUATION"][pump]["discharge_bar"] = 0.1


def _transmitter_lost(sig, frac, t):
    """§11's fallback set, exercised: the fieldbus carrying the pressure
    transmitter goes down, and regulation drops to open loop."""
    if frac < 0.30:
        return
    sig["COMMUNICATION"]["fieldbus"]["link_up"] = False


def _loop_saturated(sig, frac, t):
    if frac < 0.30:
        return
    load = ramp(frac, 0.30, 0.38, 0.99)
    sig["COMPUTE"]["cpu"]["cpu_load"] = load
    sig["COMPUTE"]["regulator"]["runtime_s"] = 0.030
    sig["TIMING"]["pressure_loop"]["processing_s"] = 0.030


def _supply_sag(sig, frac, t):
    if frac < 0.30:
        return
    v = ramp(frac, 0.30, 48.0, 40.0)
    sig["POWER"]["mains_dc"]["voltage_v"] = v
    sig["POWER"]["mains_dc"]["power_w"] = v * 62.0


def _skid(name, desc, expect, inject=None, tags=()):
    return Scenario(name=name, system="pump_skid", section="30",
                    description=desc, expectation=expect, inject=inject,
                    tags=("second_profile",) + tags,
                    nominal=PUMP_SKID_NOMINAL)


PUMP_SKID_SCENARIOS = (
    _skid("PS_NOMINAL", "skid at duty", "SYSTEM NORMAL"),
    _skid("PS_ONE_PUMP_DOWN",
          "pump B loses its drive; pump A carries the duty",
          "FLOW_DELIVERY stays ELIGIBLE -- the one-of-N group is not "
          "exhausted. This is the case neither existing profile could "
          "express",
          _one_pump_down, tags=("redundancy",)),
    _skid("PS_BOTH_PUMPS_DOWN",
          "both pumps lose their drive",
          "FLOW_DELIVERY is limited by ACTUATION: the group IS exhausted",
          _both_pumps_down, tags=("redundancy",)),
    _skid("PS_TRANSMITTER_LOST",
          "the fieldbus carrying the pressure transmitter goes down",
          "PRESSURE_REGULATION drops to DEGRADED on its declared "
          "OPEN_LOOP_ON_SPEED fallback rather than to INELIGIBLE",
          _transmitter_lost, tags=("fallback",)),
    _skid("PS_LOOP_SATURATED",
          "the controller saturates and the loop misses its deadline",
          "COMPUTE and TIMING limit regulation; localization separates the "
          "processing delay from a stall",
          _loop_saturated, tags=("compute", "timing")),
    _skid("PS_SUPPLY_SAG", "the DC supply droops under load",
          "POWER limits everything downstream of the supply",
          _supply_sag, tags=("power",)),
)

__all__ = ["PUMP_SKID_FUNCTIONS", "PUMP_SKID_RELATIONS", "PUMP_SKID_NOMINAL",
           "PUMP_SKID_SCENARIOS", "build_pump_skid_engine"]
