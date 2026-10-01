# Multi-producer events in the existing data (Phases 2 and 3)

**2026-10-01.**

**Rule:** existing data first, no monitor invented to raise a producer
count.

**Producers:** those 2.2 already wraps:
- the frozen CUSUM;
- PX4 EKF2 status;
- the XSYS-001 witnesses W_RPM, W_DYN, W_CTRL;
- the frozen v2 domain plugins.

**Not wrapped:** control-allocation status and battery/power status exist
only as v2 plugin records on synthetic scenarios. No adapter reads them from
a PX4 log, and none was written for the pilot.

## 1. What each data source can supply

| source | real producers that can read it | ≥ 2 on one vehicle event? |
|---|---|---|
| **66 XSYS-001 flight logs + sealed stage-1 features** (SITL, PX4 547e2ca) | W_RPM, W_DYN, W_CTRL (from the sealed features); PX4 EKF2 status (from the log) | **yes**: the motor degradation of the 55 A flights (`campaign_xsys.py`) |
| apparatus logs (`research/px4_actuator_effectiveness/raw_ulog`, compressed in git) | PX4 EKF2 status only; the witnesses exist only as the campaign's blinded stage-1 features | no |
| run S1 (this pilot, SITL) | PX4 EKF2 status only (no magnetometer-health adapter) | no |
| v1 scenarios (`csia/scenarios.py`, simulated) | the frozen CUSUM; the frozen v1 trust engine is not wrapped | CUSUM only. power_sag gives several CUSUM outputs from one producer and shared relations: the dependence case, not multiple producers |
| v2 scenario corpus / Phase C (synthetic) | the six frozen v2 domain plugins | yes, synthetically: e.g. SHARED_RAIL, MS_C2_SHARED_POWER (power and sensor plugins on one injected cause) |
| E1 (synthetic transition) | v2 plugins with configuration epochs | a transition, not a multi-producer event |

**CUSUM and the PX4 estimator never observe the same event.** The frozen
CUSUM consumes the v1 simulation's physics chi-square, which no PX4 log
contains. Pairing them would need a new monitor, which the brief excludes.

## 2. The event matrix

| event | ground truth | producer A | producer B | producer C | producer D | shared lineage | independent lineage | expected 2.2 value | data source |
|---|---|---|---|---|---|---|---|---|---|
| motor 0 thrust loss, eta 0.55-0.95 (55 flights) | physical actuator degradation (SIH_MOT_EFF1 at onset) | W_RPM: RPM below command (ESC telemetry) | W_DYN: body rates respond in T1 (IMU) | W_CTRL: controller compensates in T3 (allocator) | PX4 EKF2: innovations | W_CTRL shares the motor command with W_RPM and the IMU with W_DYN; EKF2 shares the IMU with W_DYN and W_CTRL | W_RPM and W_DYN: different sensors | show that 3 adverse outputs are 2 independent lines; that the exclusion of the telemetry hypothesis rests twice on the IMU; that the estimator is silent and why that is not evidence against the fault | XSYS-001 A trials |
| RPM telemetry corruption (55 trials) | the RPM channel lies; the rotor is healthy | W_RPM: deficit (corrupted channel) | W_DYN: no response (nominal) | W_CTRL: no compensation (nominal) | PX4 EKF2: innovations | as above | as above | show that the one adverse output rests on the telemetry channel only, and that two IMU-based witnesses (one line) contradict it | XSYS-001 B trials (NB flights) |
| nominal flight with a benign onset (11) | nothing | W_RPM, W_DYN, W_CTRL: nominal | PX4 EKF2: nominal | — | — | as above | — | no symptom; NO_ANOMALY / NOMINAL kept distinct | XSYS-001 N trials |
| power sag, battery and motor_esc (v1, simulated) | power sag on battery and ESC | CUSUM(battery) | CUSUM(motor_esc) | CUSUM(vibration), 35.4-39.6 s | — | all share `sensor:motor_esc` (one v1 relation set) | none | 3 alarms reported as 1 line | `csia/scenarios.py` power_sag |
| shared 5 V rail sag (v2, synthetic) | the rail | v2 power plugin | v2 sensor plugin (sources on the rail) | v2 communication plugin | — | declared rail dependency (record `dependencies`) | each plugin's own channel | attribution keeps the rail as a common-cause candidate (2.1.1) | v2 SHARED_RAIL, MS_C2_SHARED_POWER |

**The real multi-producer case for Phases 6-8 is the first row.**

**Why the first row, and not "because it makes CSIA look good":**
- it is the only real (SITL-flown, PX4 547e2ca) event in the repository that
  two or more wrapped producers observe;
- it has 55 repetitions;
- its ground truth is the injected parameter.

Its B-trial counterpart (row 2) is analysed with it, and is where a naive
reading could go wrong in the other direction.
