"""Synthetic scenarios for the multirotor profile — §§27, 28.

Platform knowledge lives here, not in `csia/v2/scenarios.py`: these are one
machine's nominal signal values and one machine's faults. The harness that
runs them knows none of it.

EVERY NUMBER BELOW IS A CHOSEN VALUE, NOT A MEASUREMENT. They were chosen to
sit inside the profile's declared thresholds (nominal) or to cross them
(faults), and they support no claim about how any real battery, regulator,
radio or ESC behaves. The profile's thresholds were declared first and are not
adjusted afterwards to make a scenario come out a particular way.

THE FAULTS ARE INJECTED AT THEIR SOURCE
---------------------------------------
`_cpu_overload` raises `cpu_load` and lets the runtime, the latency and the
missed deadline follow from it. It does not set `deadline_misses` by hand. A
scenario that wrote down its own expected answer would be testing nothing.
"""

from __future__ import annotations

from dataclasses import replace

from ..scenarios import Scenario, ramp

#: Nominal signal values for the aircraft profile. Chosen to sit inside every
#: declared threshold with room to spare, so a scenario's effect is the only
#: thing moving.
AIRCRAFT_NOMINAL = {
    "POWER": {
        "battery": {"voltage_v": 22.2, "current_a": 15.0, "power_w": 333.0,
                    "voltage_reference_v": 22.5,
                    "cell_voltages": [3.70, 3.70, 3.71, 3.70, 3.70, 3.69],
                    "temperature_c": 32.0},
        "rail_5v": {"voltage_v": 5.02},
        "rail_3v3": {"voltage_v": 3.30},
    },
    "COMPUTE": {
        "state_estimator": {"alive": True, "heartbeat_age_s": 0.01,
                            "output_age_s": 0.02, "runtime_s": 0.008,
                            "deadline_misses": 0, "queue_depth": 1,
                            "restart_count": 0},
        "csia": {"alive": True, "heartbeat_age_s": 0.02,
                 "output_age_s": 0.05, "runtime_s": 0.004,
                 "deadline_misses": 0, "queue_depth": 0, "restart_count": 0},
        "logger": {"alive": True, "heartbeat_age_s": 0.2,
                   "output_age_s": 0.5, "runtime_s": 0.020,
                   "deadline_misses": 0, "queue_depth": 2,
                   "restart_count": 0},
        "cpu": {"cpu_load": 0.42, "memory_used_frac": 0.55,
                "throttled": False, "reset_reason": "POWER_ON"},
    },
    "TIMING": {
        # Stamps are expressed as offsets from the tick time by the builder.
        "nav_solution": {"transport_s": 0.004, "processing_s": 0.006,
                         "decision_s": 0.002, "interval_s": 0.020,
                         "jitter_s": 0.002},
        "telemetry_downlink": {"transport_s": 0.120, "processing_s": 0.020,
                               "decision_s": 0.0, "interval_s": 0.200,
                               "jitter_s": 0.030},
    },
    "COMMUNICATION": {
        "gnss_serial": {"link_up": True, "observed_rate_hz": 5.0,
                        "loss_frac": 0.0, "crc_errors": 0, "duplicates": 0,
                        "reordered": 0, "queue_delay_s": 0.01,
                        "bus_off": False, "reconnects": 0},
        "telemetry_radio": {"link_up": True, "observed_rate_hz": 10.0,
                            "loss_frac": 0.01, "crc_errors": 0,
                            "duplicates": 0, "reordered": 0,
                            "queue_delay_s": 0.05, "bus_off": False,
                            "reconnects": 0},
        "esc_can": {"link_up": True, "observed_rate_hz": 50.0,
                    "loss_frac": 0.0, "crc_errors": 0, "duplicates": 0,
                    "reordered": 0, "bus_off": False, "reconnects": 0},
    },
    "ACTUATION": {
        "motor_0": {"command": 0.55, "command_transmitted": 0.55,
                    "current_a": 16.5, "rpm": 4950.0},
    },
}


def _power_sag(sig, frac, t):
    # The source itself is failing: internal resistance has risen, so the
    # terminal voltage collapses under an unchanged load. The rails follow,
    # because they are downstream -- that is physics, not an extra injection.
    droop = ramp(frac, 0.30, 0.0, 2.2)
    sig["POWER"]["battery"]["voltage_v"] = 22.2 - droop
    sig["POWER"]["battery"]["power_w"] = (
        sig["POWER"]["battery"]["voltage_v"]
        * sig["POWER"]["battery"]["current_a"])
    if droop > 1.2:
        sig["POWER"]["rail_5v"]["voltage_v"] = 5.02 - (droop - 1.2) * 0.45
        sig["POWER"]["rail_3v3"]["voltage_v"] = 3.30 - (droop - 1.2) * 0.30


def _regulator_failure(sig, frac, t):
    # §28 SCENARIO B. The battery is untouched -- deliberately, because the
    # finding under test is that a healthy source EXONERATES itself and moves
    # suspicion downstream.
    sig["POWER"]["rail_5v"]["voltage_v"] = ramp(frac, 0.30, 5.02, 4.30)


def _cpu_overload(sig, frac, t):
    load = ramp(frac, 0.30, 0.42, 0.995)
    sig["COMPUTE"]["cpu"]["cpu_load"] = load
    # Runtime follows load; the deadline miss is a CONSEQUENCE, not injected.
    sig["COMPUTE"]["state_estimator"]["runtime_s"] = 0.008 * (
        1.0 + 4.0 * max(0.0, load - 0.42) / 0.58)
    sig["TIMING"]["nav_solution"]["processing_s"] = 0.006 * (
        1.0 + 5.0 * max(0.0, load - 0.42) / 0.58)


def _process_stall(sig, frac, t):
    if frac < 0.30:
        return
    age = ramp(frac, 0.30, 0.01, 1.20)
    sig["COMPUTE"]["state_estimator"]["heartbeat_age_s"] = age
    sig["COMPUTE"]["state_estimator"]["output_age_s"] = age
    sig["COMPUTE"]["state_estimator"]["queue_depth"] = int(
        ramp(frac, 0.30, 1, 40))


def _network_latency(sig, frac, t):
    # §28 SCENARIO A. Only the transport is touched. The sensor's own
    # sampling interval is untouched, which is what lets TIMING attribute the
    # delay to TRANSPORT rather than to SENSOR_SLOW.
    delay = ramp(frac, 0.30, 0.120, 1.400)
    sig["TIMING"]["telemetry_downlink"]["transport_s"] = delay
    sig["COMMUNICATION"]["telemetry_radio"]["queue_delay_s"] = ramp(
        frac, 0.30, 0.05, 1.40)


def _packet_loss(sig, frac, t):
    loss = ramp(frac, 0.30, 0.0, 0.35)
    sig["COMMUNICATION"]["gnss_serial"]["loss_frac"] = loss
    sig["COMMUNICATION"]["gnss_serial"]["observed_rate_hz"] = 5.0 * (
        1.0 - loss)


def _clock_drift(sig, frac, t):
    # §27 CLOCK_DRIFT. The validity stamp runs AHEAD of arrival, which cannot
    # happen physically. The point is that this is reported as a timebase
    # fault, not silently averaged in as negative latency.
    sig["TIMING"]["nav_solution"]["transport_s"] = ramp(
        frac, 0.30, 0.004, -0.050)


def _actuator_no_response(sig, frac, t):
    # Commanded, transmitted, and drawing nothing.
    if frac < 0.30:
        return
    sig["ACTUATION"]["motor_0"]["current_a"] = ramp(frac, 0.30, 16.5, 0.4)
    sig["ACTUATION"]["motor_0"]["rpm"] = ramp(frac, 0.30, 4950.0, 0.0)


def _stalled_actuator(sig, frac, t):
    # §28 SCENARIO C: command sent, ESC receives it, CURRENT RISES, RPM does
    # not. The opposite electrical signature to ACTUATOR_NO_RESPONSE, and the
    # pair is what makes the mechanical finding meaningful.
    if frac < 0.30:
        return
    sig["ACTUATION"]["motor_0"]["current_a"] = ramp(frac, 0.30, 16.5, 26.0)
    sig["ACTUATION"]["motor_0"]["rpm"] = ramp(frac, 0.30, 4950.0, 300.0)


def _estimator_late(sig, frac, t):
    # §28 SCENARIO D: the sources are fresh (the v1.1 payload is the clean
    # one, untouched); the estimator process is late. The expected finding is
    # a compute/timing limitation, NOT a sensor failure.
    if frac < 0.30:
        return
    over = ramp(frac, 0.30, 0.008, 0.045)
    sig["COMPUTE"]["state_estimator"]["runtime_s"] = over
    sig["TIMING"]["nav_solution"]["processing_s"] = over


def _shared_rail(sig, frac, t):
    # §28 SCENARIO E. One rail out of tolerance, with several things declared
    # downstream of it. Nothing downstream is injected -- their own evidence
    # comes from the real v1.1 payload and from the rail's own dependants.
    sig["POWER"]["rail_5v"]["voltage_v"] = ramp(frac, 0.30, 5.02, 4.55)
    sig["POWER"]["rail_3v3"]["voltage_v"] = ramp(frac, 0.30, 3.30, 3.05)
    sig["COMMUNICATION"]["telemetry_radio"]["observed_rate_hz"] = ramp(
        frac, 0.30, 10.0, 3.0)
    sig["COMMUNICATION"]["gnss_serial"]["observed_rate_hz"] = ramp(
        frac, 0.30, 5.0, 1.5)




# ------------------------------------------------------------- the table
#: §27's eight, then §28's remaining cross-domain cases. Several §28 scenarios
#: ARE a §27 scenario looked at through a cross-domain question, and where
#: that is true the table says so instead of duplicating the injection under
#: a second name.
AIRCRAFT_SCENARIOS = (
        Scenario("NOMINAL", "aircraft", "baseline",
                 "every declared signal inside every declared threshold",
                 "SYSTEM NORMAL; no adverse evidence; attribution "
                 "NO_EVIDENCE"),
        # -- §27 ------------------------------------------------------
        Scenario("POWER_SAG", "aircraft", "27",
                 "battery terminal voltage collapses under unchanged load",
                 "POWER limits functions; the BATTERY is the candidate and "
                 "the rails follow it, so the source is NOT exonerated",
                 inject=_power_sag, tags=("power",)),
        Scenario("REGULATOR_FAILURE", "aircraft", "27,28B",
                 "5 V rail leaves tolerance; battery untouched",
                 "distribution/regulator candidate; battery affirmatively "
                 "nominal and named as exonerated",
                 inject=_regulator_failure, tags=("power", "scenario_b")),
        Scenario("CPU_OVERLOAD", "aircraft", "27",
                 "CPU load rises; estimator runtime and latency follow",
                 "COMPUTE degrades then violates; TIMING follows; functions "
                 "with a no-degradation TIMING requirement stop first",
                 inject=_cpu_overload, tags=("compute", "timing")),
        Scenario("PROCESS_STALL", "aircraft", "27",
                 "estimator heartbeat and output age grow without bound",
                 "process_alive VIOLATED; the functions that need it become "
                 "INELIGIBLE; the sensor domain is untouched",
                 inject=_process_stall, tags=("compute",)),
        Scenario("NETWORK_LATENCY", "aircraft", "27,28A",
                 "telemetry transport delay and queue delay rise",
                 "COMMUNICATION and TIMING degrade; SENSOR stays "
                 "source-valid; TELEMETRY is limited, navigation is not",
                 inject=_network_latency, tags=("comm", "timing",
                                                "scenario_a")),
        Scenario("PACKET_LOSS", "aircraft", "27",
                 "GNSS serial link loses messages and falls below rate",
                 "COMMUNICATION is the candidate; the link failure is NOT "
                 "reported as a sensor failure",
                 inject=_packet_loss, tags=("comm",)),
        Scenario("CLOCK_DRIFT", "aircraft", "27",
                 "validity stamps run ahead of arrival stamps",
                 "TIMING_CLOCK_INCONSISTENT, VIOLATED; no latency is "
                 "published from stamps shown to be inconsistent",
                 inject=_clock_drift, tags=("timing",)),
        Scenario("ACTUATOR_NO_RESPONSE", "aircraft", "27",
                 "motor commanded and transmitted; current collapses",
                 "ACT_NO_ELECTRICAL_RESPONSE; ESC, power path and wiring "
                 "named as inseparable candidates",
                 inject=_actuator_no_response, tags=("actuation",)),
        # -- §28's remaining cross-domain cases ------------------------
        Scenario("STALLED_ACTUATOR", "aircraft", "28C",
                 "command sent, ESC receives, current rises, RPM does not",
                 "ACT_STALLED: a mechanical/load candidate, distinct from "
                 "the no-current signature",
                 inject=_stalled_actuator, tags=("actuation", "scenario_c")),
        Scenario("ESTIMATOR_LATE", "aircraft", "28D",
                 "sources fresh; estimator runtime exceeds its deadline",
                 "COMPUTE/TIMING limitation; SENSOR domain remains exactly "
                 "what v1.1 said it was",
                 inject=_estimator_late, tags=("compute", "timing",
                                               "scenario_d")),
        Scenario("SHARED_RAIL", "aircraft", "28E",
                 "one rail out of tolerance with several dependants",
                 "AMBIGUOUS with the rail retained as a common-cause "
                 "alternative, NOT adopted as the answer",
                 inject=_shared_rail, v1_1_variant="fixloss",
                 tags=("power", "scenario_e")),
)


#: Bound to their nominal set here rather than repeated on every entry: the
#: whole point of a profile is that one machine has one nominal state.
AIRCRAFT_SCENARIOS = tuple(replace(s, nominal=AIRCRAFT_NOMINAL)
                           for s in AIRCRAFT_SCENARIOS)


# ---------------------------------------------------- the v1.1 payload feed
#: The two committed REAL v1.1 payloads, produced by the frozen v1.1 runtime
#: (`engineering/v1_1/phase4/run_p4d.py`). §36's baseline test is only
#: meaningful against real payloads, so the harness never synthesises one.
V1_1_EXAMPLES = {
    "clean": "csia_output_example.json",
    "fixloss": "csia_output_fixloss_example.json",
}


def load_v1_1_example(variant: str = "clean") -> dict:
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    path = os.path.join(root, "engineering", "v1_1", V1_1_EXAMPLES[variant])
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def example_payload_feed(variant: str = "clean"):
    """`(k, t) -> payload`, re-stamped to the harness clock.

    ONLY `timestamp` is rewritten. Every other field is the payload exactly
    as the frozen v1.1 runtime produced it, because a payload edited to suit
    a scenario would no longer be evidence of anything v1.1 concluded.
    """
    payload = load_v1_1_example(variant)
    return lambda k, t: dict(payload, timestamp=t)
