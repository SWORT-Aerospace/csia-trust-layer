# Claim register: claim before adapter (Phases 2-7)

**2026-10-02.** The register is `CLAIMS.json`, written and committed
(67bc92f) before any producer existed.

## 1. The rule

For every candidate piece of stock evidence, the register fixes:
- source topics and fields;
- what the evidence means;
- what it can support and what it can refute;
- what it CANNOT establish;
- assumptions;
- lineage (the sources it depends on);
- content time;
- configuration dependencies;
- failure modes;
- what the 66 XSYS-001 logs show.

Then comes the decision:
- IMPLEMENT as profile evidence;
- CONTEXT: reported, read by no symptom;
- TRIGGER: event discovery only;
- NOT_IMPLEMENTED: with the reason.

The producers were written from the register, not the reverse.

## 2. Decisions

| claim | decision | why (short) |
|---|---|---|
| ESC_TELEMETRY_RESPONSE | CONTEXT | finding SB-1 (section 3) |
| ESC_ELECTRICAL_RESPONSE | NOT_IMPLEMENTED | ESC current is zero in SIH |
| ALLOCATOR_COMPENSATION | IMPLEMENT, `actuation.physical_response` | XSYS-001's validated control witness (W_CTRL), from stock topics |
| VEHICLE_RATE_TRANSIENT | CONTEXT | valid only within 0.2 s of a precisely known onset |
| ALLOCATION_STATUS | CONTEXT | never fired in XSYS-001; the profile has no relation for it |
| RATE_INTEGRATOR | CONTEXT | an axis, not a motor |
| BATTERY_SOURCE_STATUS | IMPLEMENT, `power.source_health` | stock battery telemetry; UNAVAILABLE when current is not measured |
| PX4_FAILURE_DETECTOR | TRIGGER | PX4's own judgement; says nothing about cause |
| ESTIMATOR_STATUS | CONTEXT | the 2.2 adapter, kept to navigation integrity, not forced into the propulsion diagnosis (Phase 6) |
| OUTPUT_STAGE | NOT_IMPLEMENTED | `actuator_outputs` is what the FMU computed; it cannot show that the ESC received it |
| CPU_LOAD | CONTEXT | load alone is not a missed deadline; in SITL it measures the host (Phase 7) |
| LOG_COMPLETENESS | IMPLEMENT, producer health | a log gap makes outputs over it UNAVAILABLE |
| VEHICLE_MODE_AND_FAILSAFE | TRIGGER | commander's failsafe; not a cause |
| TELEMETRY_LINK, SENSOR_TOPICS | NOT_IMPLEMENTED | not propulsion; the v1.1 trust engine is not run on PX4 logs |

## 3. ESC and motor: four stages kept apart (Phase 3)

| stage | stock source | stock statistic |
|---|---|---|
| COMMAND | `actuator_motors.control[m]` | input to the others |
| TELEMETRY RESPONSE | `esc_status.esc[m].esc_rpm` | q_m: RPM squared per commanded thrust, against the median motor |
| CONTROLLER COMPENSATION | `actuator_motors` after the event against before | C_m: the change in c_m / median c |
| PHYSICAL VEHICLE RESPONSE | `vehicle_angular_velocity` | D_m: body-rate transient on motor m's loss axis in [0, 0.2] s |

**No thrust is inferred from RPM.** Thrust per RPM depends on the
propeller and air density, which no stock topic reports. q compares
motors with each other through PX4's own thrust model (`THR_MDL_FAC`,
0 in SIH). It does not estimate a thrust.

**On the 66 logs (`STOCK_EVIDENCE_INVESTIGATION.json`, at default rates):**
- q_0 after the event equals eta to 0.003 at every eta, 0.55-0.95.
- kappa_0 equals 1/eta to 0.004.
- Benign-onset flights change neither by more than 0.0016.
- Both statistics separate fault from benign onset with AUC 1.0.
- Both localize motor 0 in 55/55.

**Finding SB-1.** The telemetry claim is CONTEXT, not
`actuation.mechanical_response`:
- 2.1.1's STALL_SIGNATURE predicate reads that relation, and takes the
  absence of the code ACT_STALLED as "stall checked and absent".
- An RPM-only deficit there would refute ACTUATION/mechanical, although
  without ESC current no stall check was possible.
- `test_sb1_an_rpm_only_deficit_on_mechanical_response_would_eliminate_mechanical`
  reproduces this.

Placing the claim where 2.1.1 would misread it would have been a wrong
answer created by the bridge.

## 4. Power, allocation, estimator, compute (Phases 4-7)

**Power (Phase 4).**
- Battery voltage is present; current is -1 in every flight.
- Battery source health is therefore UNAVAILABLE, the v2 semantics: voltage
  and current must both be present.
- No electrochemistry and no state-of-charge reasoning were added.
- PX4's battery warning is context and a trigger.

**Allocation (Phase 5).**
- PX4's allocator reported every setpoint achieved and no saturation in all
  66 flights, including eta = 0.55.
- The vehicle had authority to spare, so allocation status never
  discriminates here.
- It is reused as PX4 computes it, as context and a trigger.

**Estimator (Phase 6).** The 2.2 PX4 estimator producer is kept as it was,
for navigation integrity. Its test ratios and resets are not read as
propulsion evidence.

**Compute (Phase 7).**
- `cpuload` ranged 0.12-1.18 in SITL (the host).
- A high load is not a missed deadline, and no stock topic pairs the two.
- It is context only, and no fault is raised from load.

## 5. Amendment after the register

The register's q and kappa definitions normalise by the mean of the OTHER
motors (calibration revision 1). They were changed to the median of ALL
motors (revision 2, `CALIBRATION_2_3.json` `revision_history`).

With the mean of the others, one motor's deficit appeared as an excess on
every other motor. The fix was found on one development run, before any
systematic evaluation. `csia_evidence_assurance/stock_stats.py` is the
authoritative definition. The register is left as written, with this
amendment recorded here.
