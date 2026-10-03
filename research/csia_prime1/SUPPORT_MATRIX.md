# CSIA Flight Assurance PRIME-1: support matrix

**Support contract prime1-r1** (machine-readable: `support_contract_prime1.json` inside the installed package). No entry is PHYSICAL_VALIDATED: no physical evidence exists yet.

| configuration | state | vehicle | validation level |
|---|---|---|---|
| quadx-allocation-esc | SUPPORTED | multirotor quadrotor, X configuration (vehicle_status.vehicle_type 1, CA_ROTOR_COUNT 4, not VTOL) | SIMULATION |
| quadx-no-esc-telemetry | PARTIAL | as quadx-allocation-esc, without ESC RPM telemetry | SIMULATION |
| quadx-pre-allocation | PARTIAL | quad X on PX4 before control allocation (actuator_controls_0 / actuator_outputs only) | REAL_LOG_CONTEXT_ONLY |
| other-multirotor | UNSUPPORTED_VEHICLE_CONFIGURATION | hexa-, octo-, tri- or coaxial multirotor (CA_ROTOR_COUNT != 4) | SIMULATION |
| fixed-wing | UNSUPPORTED_VEHICLE_CONFIGURATION | fixed wing (vehicle_type 2) | REAL_LOG_CONTEXT_ONLY |
| vtol | UNSUPPORTED_VEHICLE_CONFIGURATION | VTOL (is_vtol, airframes 13000-13999) | REAL_LOG_CONTEXT_ONLY |
| rover-boat | UNSUPPORTED_VEHICLE_CONFIGURATION | rover or boat (vehicle_type 3; airframes 50000-59999) | REAL_LOG_CONTEXT_ONLY |
| not-ulog | UNSUPPORTED_SCHEMA | any log that is not a PX4 ULog (e.g. ArduPilot .bin, .tlog) | REAL_LOG_CONTEXT_ONLY |

## Validation levels

- **SIMULATION**: shown in PX4 software-in-the-loop simulation (SIH quadrotor) only
- **HIL**: shown in hardware-in-the-loop simulation (none yet)
- **REAL_LOG_CONTEXT_ONLY**: real logs are read and their coverage stated; no diagnostic conclusion has been checked against real truth
- **PHYSICAL_VALIDATED**: a diagnostic conclusion checked against independent physical truth (none yet)

## Telemetry classes

| class | what the Analyzer does | validation level |
|---|---|---|
| rpm_shortfall | discovered (RPM_DEFICIT_EVENT) and reported as telemetry evidence; never a motor fault on its own | SIMULATION |
| rpm_excess | discovered (RPM_EXCESS_EVENT) and reported as telemetry evidence (PRIME-1; D-PRIME-2) | SIMULATION |
| esc_offline | discovered (ESC_OFFLINE_EVENT); telemetry UNAVAILABLE, never read as a deficit | SIMULATION |
| log_dropout | evidence over the gap refused; support PARTIAL | SIMULATION |
| stuck_value | NOT discovered in steady hover (no change to see); see the telemetry matrix | SIMULATION |
| static_offset_or_slow_drift | NOT discovered as a change; a gross static inconsistency with the other rotors is stated as a coverage notice | SIMULATION |
| matched_physical_vs_telemetry_discrimination | in simulation only; physical test designed, not run | SIMULATION |

## Known blind spots

- losses during continuous maneuvering are discovered but not confirmed (the compensation witness needs steady flight)
- ESC current not logged by stock PX4: drive-without-current and stall cannot be separated
- battery current often not logged: the power path cannot be eliminated
- a propeller loss that leaves RPM unchanged has only the compensation witness
- compute and timing faults, command-delivery faults
- a compensation change between two steady holds at different headings is not an event, but its evidence is not yet refused (candidate validity condition)
- every threshold is SITL-calibrated (SIH has almost no noise); real vehicles need their own nominal calibration

## Known defects (fixed in prime1)

- D-PRIME-1: sub-microsecond time representation changed admissibility decisions
- D-PRIME-2: an RPM excess opened no event; a late event read a corrupted reference as NOMINAL
- D-PRIME-3: the wheel omitted stock_calibration.json: an installed csia-assure crashed on every analysable log
