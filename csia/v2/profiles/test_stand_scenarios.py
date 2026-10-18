"""Synthetic scenarios for §37's electric motor test stand.

The same harness, a different machine. Nothing in this module mentions flight,
and nothing in `csia/v2/` needed to know that it would not.

As with the aircraft scenarios, every value here is chosen to exercise a
declared threshold and none is a measurement of any real bench.
"""

from __future__ import annotations

from dataclasses import replace

from ..scenarios import Scenario, ramp

#: Nominal for §37's motor test stand. Nothing aviation-shaped.
TEST_STAND_NOMINAL = {
    "POWER": {
        "dc_supply": {"voltage_v": 48.0, "current_a": 40.0, "power_w": 1920.0,
                      "voltage_reference_v": 48.4},
        "rail_24v": {"voltage_v": 24.1},
        "rail_5v": {"voltage_v": 5.01},
    },
    "COMPUTE": {
        "controller": {"alive": True, "heartbeat_age_s": 0.002,
                       "output_age_s": 0.004, "runtime_s": 0.002,
                       "deadline_misses": 0, "queue_depth": 0,
                       "restart_count": 0},
        "recorder": {"alive": True, "heartbeat_age_s": 0.2,
                     "output_age_s": 0.4, "runtime_s": 0.010,
                     "deadline_misses": 0, "queue_depth": 1,
                     "restart_count": 0},
        "cpu": {"cpu_load": 0.35, "memory_used_frac": 0.40,
                "throttled": False, "reset_reason": "POWER_ON"},
    },
    "TIMING": {
        "encoder": {"transport_s": 0.0008, "processing_s": 0.0009,
                    "decision_s": 0.0, "interval_s": 0.001,
                    "jitter_s": 0.0002},
    },
    "COMMUNICATION": {
        "encoder_bus": {"link_up": True, "observed_rate_hz": 1000.0,
                        "loss_frac": 0.0, "crc_errors": 0, "duplicates": 0,
                        "reordered": 0, "bus_off": False, "reconnects": 0},
        "host_ethernet": {"link_up": True, "observed_rate_hz": 100.0,
                          "loss_frac": 0.0, "crc_errors": 0, "duplicates": 0,
                          "reordered": 0, "queue_delay_s": 0.01,
                          "bus_off": False, "reconnects": 0},
    },
    "ACTUATION": {
        "dyno_motor": {"command": 0.60, "command_transmitted": 0.60,
                       "current_a": 48.0, "rpm": 3600.0,
                       "torque_nm": 27.0},
    },
}



# -- test-stand injections (§37): same framework, different machine -------
def _ts_supply_sag(sig, frac, t):
    sig["POWER"]["dc_supply"]["voltage_v"] = ramp(frac, 0.30, 48.0, 43.0)
    sig["POWER"]["dc_supply"]["power_w"] = (
        sig["POWER"]["dc_supply"]["voltage_v"]
        * sig["POWER"]["dc_supply"]["current_a"])


def _ts_regulator_failure(sig, frac, t):
    sig["POWER"]["rail_5v"]["voltage_v"] = ramp(frac, 0.30, 5.01, 4.20)


def _ts_stalled(sig, frac, t):
    if frac < 0.30:
        return
    sig["ACTUATION"]["dyno_motor"]["current_a"] = ramp(
        frac, 0.30, 48.0, 76.0)
    sig["ACTUATION"]["dyno_motor"]["rpm"] = ramp(frac, 0.30, 3600.0, 200.0)
    sig["ACTUATION"]["dyno_motor"]["torque_nm"] = ramp(
        frac, 0.30, 27.0, 2.0)


def _ts_encoder_loss(sig, frac, t):
    loss = ramp(frac, 0.30, 0.0, 0.08)
    sig["COMMUNICATION"]["encoder_bus"]["loss_frac"] = loss
    sig["COMMUNICATION"]["encoder_bus"]["observed_rate_hz"] = 1000.0 * (
        1.0 - loss)


def _ts_cpu_overload(sig, frac, t):
    load = ramp(frac, 0.30, 0.35, 0.99)
    sig["COMPUTE"]["cpu"]["cpu_load"] = load
    sig["COMPUTE"]["controller"]["runtime_s"] = 0.002 * (
        1.0 + 4.0 * max(0.0, load - 0.35) / 0.64)
    sig["TIMING"]["encoder"]["processing_s"] = 0.0009 * (
        1.0 + 4.0 * max(0.0, load - 0.35) / 0.64)




# ------------------------------------------------------------- the table
TEST_STAND_SCENARIOS = (
        Scenario("TS_NOMINAL", "test_stand", "37",
                 "bench at its run point", "SYSTEM NORMAL"),
        Scenario("TS_SUPPLY_SAG", "test_stand", "37",
                 "DC supply droops under load",
                 "POWER limits TORQUE_DELIVERY and the sequence function",
                 inject=_ts_supply_sag, tags=("power",)),
        Scenario("TS_REGULATOR_FAILURE", "test_stand", "37",
                 "5 V logic rail fails; supply healthy",
                 "same exoneration as the aircraft profile, with no aviation "
                 "code involved",
                 inject=_ts_regulator_failure, tags=("power",)),
        Scenario("TS_STALLED", "test_stand", "37",
                 "drive current rises, shaft does not turn, torque falls",
                 "ACT_STALLED plus a physical-response finding",
                 inject=_ts_stalled, tags=("actuation",)),
        Scenario("TS_ENCODER_LOSS", "test_stand", "37",
                 "encoder bus loses messages",
                 "SPEED_MEASUREMENT limited by COMMUNICATION",
                 inject=_ts_encoder_loss, tags=("comm",)),
        Scenario("TS_CPU_OVERLOAD", "test_stand", "37",
                 "controller loop saturates",
                 "COMPUTE and TIMING limit TEST_SEQUENCE_EXECUTION",
                 inject=_ts_cpu_overload, tags=("compute", "timing")),
)


TEST_STAND_SCENARIOS = tuple(replace(s, nominal=TEST_STAND_NOMINAL)
                             for s in TEST_STAND_SCENARIOS)
