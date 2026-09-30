"""Ground truth for the 44 shipped scenarios, as the scenarios state it.

SOURCE: each scenario's own `description` and `expectation` in
`csia/v2/profiles/` (read-only). The reasoner never sees this table; it is
used only to grade differences between 2.0 and 2.1.

`domain` / `component`
    the injected cause, for grading attribution.

`hypotheses`
    per symptom, the hypothesis id that is true. `None` means no declared
    hypothesis is true: the matrix has no mechanism for it, so
    NO_CONSISTENT_HYPOTHESIS is the correct answer. `UNSPECIFIED` means the
    scenario does not determine it; such units are graded UNKNOWN, never
    guessed.

`navigation_affected`
    the navigation / position functions the injected cause actually makes
    "not fully available", for grading POSITION_UNAVAILABLE presence. This
    is the physical reading of `G1_COARSE_NAVIGATION_AUDIT.md` §5: on a
    PX4-class multirotor every position output, coarse or precise, is the
    estimator's output and every one of them carries the GNSS solution.
    Where that audit says the relation is CONDITIONAL (latency degrades
    rather than removes), "not fully available" is still true.
"""

UNSPECIFIED = "UNSPECIFIED"
NAV = ("COARSE_NAVIGATION", "POSITION_HOLD", "PRECISION_NAVIGATION")
GNSS_FUNCS = NAV + ("GEOFENCE_SUPPORT",)

T = {
    "ACTUATOR_NO_RESPONSE": dict(domain="ACTUATION", component="motor_0",
        hypotheses={"COMMAND_NO_RESPONSE": "ACTUATION/drive_no_current"}),
    "CLOCK_DRIFT": dict(domain="TIMING", component="nav_solution",
        hypotheses={"OUTPUT_STALE": "TIMING/clock_inconsistent",
                    "POSITION_UNAVAILABLE": UNSPECIFIED},
        navigation_affected=NAV),
    "CPU_OVERLOAD": dict(domain="COMPUTE", component="cpu",
        hypotheses={"PROCESS_OUTPUT_LATE": "COMPUTE/resource_exhaustion",
                    "POSITION_UNAVAILABLE": "COMPUTE/estimator_stale",
                    "OUTPUT_STALE": "COMPUTE/processing_delay",
                    "FUNCTION_DEADLINE_MISS": "COMPUTE/processing_delay"},
        navigation_affected=NAV),
    "ESTIMATOR_LATE": dict(domain="COMPUTE", component="state_estimator",
        hypotheses={"PROCESS_OUTPUT_LATE": None,
                    "POSITION_UNAVAILABLE": "COMPUTE/estimator_stale",
                    "OUTPUT_STALE": "COMPUTE/processing_delay",
                    "FUNCTION_DEADLINE_MISS": "COMPUTE/processing_delay"},
        navigation_affected=NAV),
    "MS_A1_SENSOR_DELAY": dict(domain="SENSOR", component="source.gps",
        hypotheses={"OUTPUT_STALE": "SENSOR/source_slow",
                    "FUNCTION_DEADLINE_MISS": "SENSOR/source_slow",
                    "POSITION_UNAVAILABLE": UNSPECIFIED},
        navigation_affected=NAV),
    "MS_A2_COMMUNICATION_DELAY": dict(domain="COMMUNICATION", component="gnss_serial",
        hypotheses={"OUTPUT_STALE": "COMMUNICATION/transport_delay",
                    "FUNCTION_DEADLINE_MISS": "COMMUNICATION/transport_delay",
                    "POSITION_UNAVAILABLE": UNSPECIFIED},
        navigation_affected=NAV),
    "MS_A3_COMPUTE_DELAY": dict(domain="COMPUTE", component="state_estimator",
        hypotheses={"OUTPUT_STALE": "COMPUTE/processing_delay",
                    "FUNCTION_DEADLINE_MISS": "COMPUTE/processing_delay",
                    "PROCESS_OUTPUT_LATE": UNSPECIFIED,
                    "POSITION_UNAVAILABLE": "COMPUTE/estimator_stale"},
        navigation_affected=NAV),
    "MS_A4_PROCESS_STALL": dict(domain="COMPUTE", component="state_estimator",
        hypotheses={"OUTPUT_STALE": "COMPUTE/process_stall",
                    "OUTPUT_MISSING": "COMPUTE/process_stall",
                    "PROCESS_OUTPUT_LATE": "COMPUTE/process_stall",
                    "FUNCTION_DEADLINE_MISS": UNSPECIFIED,
                    "POSITION_UNAVAILABLE": "COMPUTE/estimator_stale"},
        navigation_affected=NAV),
    "MS_B1_COMMAND_LOST": dict(domain="COMMUNICATION", component="esc_can",
        hypotheses={"COMMAND_NO_RESPONSE": "COMMUNICATION/command_not_delivered"},
        navigation_affected=()),
    "MS_B2_POWER_PATH": dict(domain="POWER", component="battery",
        hypotheses={"COMMAND_NO_RESPONSE": "POWER/path_unavailable"}),
    "MS_B3_DRIVE_NO_CURRENT": dict(domain="ACTUATION", component="motor_0",
        hypotheses={"COMMAND_NO_RESPONSE": "ACTUATION/drive_no_current"}),
    "MS_B4_MECHANICAL": dict(domain="ACTUATION", component="motor_0",
        hypotheses={"COMMAND_NO_RESPONSE": "ACTUATION/mechanical",
                    "HIGH_CURRENT_LOW_RPM": "ACTUATION/mechanical"}),
    "MS_B5_RESPONSE_SENSOR": dict(domain="SENSOR", component="motor_0.rpm",
        hypotheses={"COMMAND_NO_RESPONSE": "SENSOR/response_sensor",
                    "HIGH_CURRENT_LOW_RPM": "SENSOR/response_sensor"}),
    "MS_C1_INDEPENDENT": dict(domain="SENSOR", component=UNSPECIFIED,
        hypotheses={"MULTIPLE_SENSORS_DEGRADED": "SENSOR/independent_faults"}),
    "MS_C2_SHARED_POWER": dict(domain="POWER", component=UNSPECIFIED,
        hypotheses={"MULTIPLE_SENSORS_DEGRADED": "POWER/shared_node"}),
    "MS_C3_LINKS_DOWN_NOT_SHARED": dict(domain="COMMUNICATION", component=UNSPECIFIED,
        hypotheses={"MULTIPLE_SENSORS_DEGRADED": "SENSOR/independent_faults",
                    "POSITION_UNAVAILABLE": "COMMUNICATION/starvation"},
        navigation_affected=NAV),
    "MS_C4_CPU_SATURATED_NOT_SHARED": dict(domain="COMPUTE", component="cpu",
        hypotheses={"MULTIPLE_SENSORS_DEGRADED": UNSPECIFIED,
                    "POSITION_UNAVAILABLE": "COMPUTE/estimator_stale"},
        navigation_affected=NAV),
    "MS_D1_NAV_SOURCE": dict(domain="SENSOR", component="source.gps",
        hypotheses={"POSITION_UNAVAILABLE": "SENSOR/navigation_source_invalid"},
        navigation_affected=NAV),
    "MS_D2_ESTIMATOR_STALE": dict(domain="COMPUTE", component="state_estimator",
        hypotheses={"POSITION_UNAVAILABLE": "COMPUTE/estimator_stale",
                    "OUTPUT_MISSING": "COMPUTE/process_stall",
                    "OUTPUT_STALE": "COMPUTE/process_stall",
                    "PROCESS_OUTPUT_LATE": "COMPUTE/process_stall"},
        navigation_affected=NAV),
    "MS_D3_COMM_STARVATION": dict(domain="COMMUNICATION", component="gnss_serial",
        hypotheses={"POSITION_UNAVAILABLE": "COMMUNICATION/starvation"},
        navigation_affected=NAV),
    "MS_D4_COMPUTE_DEADLINE": dict(domain="COMPUTE", component="state_estimator",
        hypotheses={"POSITION_UNAVAILABLE": "COMPUTE/estimator_stale",
                    "OUTPUT_STALE": "COMPUTE/processing_delay",
                    "FUNCTION_DEADLINE_MISS": "COMPUTE/processing_delay",
                    "PROCESS_OUTPUT_LATE": UNSPECIFIED},
        navigation_affected=NAV),
    "MS_TS_B4_MECHANICAL": dict(domain="ACTUATION", component="dyno_motor",
        hypotheses={"COMMAND_NO_RESPONSE": "ACTUATION/mechanical",
                    "HIGH_CURRENT_LOW_RPM": "ACTUATION/mechanical"}),
    "MS_TS_B5_RESPONSE_SENSOR": dict(domain="SENSOR", component="dyno_motor.rpm",
        hypotheses={"COMMAND_NO_RESPONSE": "SENSOR/response_sensor",
                    "HIGH_CURRENT_LOW_RPM": "SENSOR/response_sensor"}),
    "NETWORK_LATENCY": dict(domain="COMMUNICATION", component="telemetry_radio",
        hypotheses={"OUTPUT_STALE": "COMMUNICATION/transport_delay",
                    "FUNCTION_DEADLINE_MISS": "COMMUNICATION/transport_delay"},
        navigation_affected=()),
    "NOMINAL": dict(domain=None, component=None, hypotheses={},
                    navigation_affected=()),
    "PACKET_LOSS": dict(domain="COMMUNICATION", component="gnss_serial",
        hypotheses={"POSITION_UNAVAILABLE": "COMMUNICATION/starvation"},
        navigation_affected=NAV),
    "POWER_SAG": dict(domain="POWER", component="battery",
        hypotheses={"VOLTAGE_RAIL_LOW": "POWER/source",
                    "MULTIPLE_SENSORS_DEGRADED": "POWER/shared_node"}),
    "PROCESS_STALL": dict(domain="COMPUTE", component="state_estimator",
        hypotheses={"OUTPUT_MISSING": "COMPUTE/process_stall",
                    "OUTPUT_STALE": "COMPUTE/process_stall",
                    "PROCESS_OUTPUT_LATE": "COMPUTE/process_stall",
                    "POSITION_UNAVAILABLE": "COMPUTE/estimator_stale"},
        navigation_affected=NAV),
    "PS_BOTH_PUMPS_DOWN": dict(domain="ACTUATION", component=UNSPECIFIED, hypotheses={}),
    "PS_LOOP_SATURATED": dict(domain="COMPUTE", component=UNSPECIFIED,
        hypotheses={"OUTPUT_STALE": "COMPUTE/processing_delay"}),
    "PS_NOMINAL": dict(domain=None, component=None, hypotheses={}),
    "PS_ONE_PUMP_DOWN": dict(domain="ACTUATION", component=UNSPECIFIED, hypotheses={}),
    "PS_SUPPLY_SAG": dict(domain="POWER", component=UNSPECIFIED,
        hypotheses={"VOLTAGE_RAIL_LOW": "POWER/source"}),
    "PS_TRANSMITTER_LOST": dict(domain="COMMUNICATION", component="fieldbus", hypotheses={}),
    "REGULATOR_FAILURE": dict(domain="POWER", component="rail_5v",
        hypotheses={"VOLTAGE_RAIL_LOW": "POWER/distribution",
                    "MULTIPLE_SENSORS_DEGRADED": "POWER/shared_node"}),
    "SHARED_RAIL": dict(domain="POWER", component=UNSPECIFIED,
        hypotheses={"MULTIPLE_SENSORS_DEGRADED": "POWER/shared_node",
                    "POSITION_UNAVAILABLE": "SENSOR/navigation_source_invalid"},
        navigation_affected=NAV),
    "SHARED_SOURCE": dict(domain="POWER", component="battery",
        hypotheses={"MULTIPLE_SENSORS_DEGRADED": "POWER/shared_node"}),
    "STALLED_ACTUATOR": dict(domain="ACTUATION", component="motor_0",
        hypotheses={"COMMAND_NO_RESPONSE": "ACTUATION/mechanical",
                    "HIGH_CURRENT_LOW_RPM": "ACTUATION/mechanical"}),
    "TS_CPU_OVERLOAD": dict(domain="COMPUTE", component=UNSPECIFIED, hypotheses={}),
    "TS_ENCODER_LOSS": dict(domain="COMMUNICATION", component="encoder_bus", hypotheses={}),
    "TS_NOMINAL": dict(domain=None, component=None, hypotheses={}),
    "TS_REGULATOR_FAILURE": dict(domain="POWER", component="rail_5v",
        hypotheses={"VOLTAGE_RAIL_LOW": "POWER/distribution"}),
    "TS_STALLED": dict(domain="ACTUATION", component="dyno_motor",
        hypotheses={"COMMAND_NO_RESPONSE": "ACTUATION/mechanical",
                    "HIGH_CURRENT_LOW_RPM": "ACTUATION/mechanical"}),
    "TS_SUPPLY_SAG": dict(domain="POWER", component="dc_supply",
        hypotheses={"VOLTAGE_RAIL_LOW": "POWER/source"}),
}


def truth(scenario):
    return T[scenario]


def true_hypothesis(scenario, symptom):
    """The true hypothesis id, None (no declared hypothesis is true), or
    UNSPECIFIED."""
    return T[scenario].get("hypotheses", {}).get(symptom, UNSPECIFIED)


def symptom_should_exist(scenario, symptom, subject):
    """True / False / None (not determined). Only decided for
    POSITION_UNAVAILABLE on navigation functions."""
    if symptom != "POSITION_UNAVAILABLE":
        return None
    affected = T[scenario].get("navigation_affected")
    if affected is None:
        return None
    return subject in affected
