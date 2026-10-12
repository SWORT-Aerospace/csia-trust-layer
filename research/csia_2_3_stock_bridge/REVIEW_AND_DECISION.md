# CSIA 2.3: review and decision

**2026-10-02. NON-CONFIRMATORY. Offboard only.**

## 1. Decision

**`CSIA_2_3_STOCK_BRIDGE_DEMONSTRATED_NARROW`**

The brief's text ends after Phase 26 and names no decision tokens. These
are the ones this review chose between, in the pilot's form:

| token | meaning | chosen? |
|---|---|---|
| `CSIA_2_3_READY_FOR_HARDWARE_LOG_TRIAL` | the analyzer is ready to be pointed at real flight logs, with known limits | no: event discovery under maneuvering is not ready, and no non-SIH data has been seen |
| `CSIA_2_3_STOCK_BRIDGE_DEMONSTRATED_NARROW` | on ordinary PX4 SITL logs, the analyzer builds a correct, honest propulsion assurance analysis with no research inputs, within stated limits | **yes** |
| `CSIA_2_3_NO_VALUE_ON_STOCK_LOGS` | stock evidence too thin to say anything | no |
| `CSIA_2_3_SEMANTIC_CORE_DEFECT_STOP` | a defect in Semantic Core 2.1.1 | no: every defect found was in the bridge, fixed outside the core |
| `CSIA_2_3_GOVERNANCE_BLOCK` | a governance rule could not be kept | no |

## 2. The product test, answered

**The test.** `python -m csia_evidence_assurance analyze flight.ulg`: no
onset, no XSYS stage-1 features, no sealed labels, no witness files. It
now runs the stock path by default.

| the brief asks it to say | on ordinary logs it says |
|---|---|
| what it observed and did not | the adverse outputs, with magnitudes, units, thresholds and windows; the unobserved profile records with their meaning (4 of 29 observed in a SIH hover: no ESC current, no battery current, no command-delivery topic) |
| what events it detected and which producers fired | every discovered event with every trigger, its motor, onset, alarm and magnitude |
| which evidence was independent | lineage groups and independent lines (V1: the two adverse outputs share the four motor commands, so 1 line, not 2) |
| which hypotheses remain, which evidence was missing | the remaining explanations, each eliminated one with the predicate and the value that eliminated it, and the records that would eliminate the rest (structural diagnosability on 2.1.1's own tables) |
| whether attribution is justified | "no" in every flight: the stock floor in SIH is three explanations |
| "If the ULog does not contain enough information: CSIA must say so" | coverage notices, NOT_STEADY_FLIGHT, ESC_TELEMETRY_OFFLINE, log gaps and missing topics are named. Nothing unobserved is called healthy (Phase 19 tests). |

## 3. What the evidence shows

**On 121 XSYS-001 cases** (the blind-onset replay, stock evidence at
default rates, no onset given):
- 110/110 injections discovered, with onset error -0.096 to +0.140 s;
- 0 events on 11 benign-onset flights;
- 0 decision differences between discovered and known onset, both on the
  stock path and with XSYS-001's own witnesses;
- motor loss separated from a telemetry-only deficit 110/110;
- never a wrong attribution.

**On 13 ordinary-log SITL flights** (two designs, each committed before
flying):
- the right motor in 5/5 hover or hold losses (motors 0-3);
- a telemetry fault never blamed on its motor (V9, V10);
- power and navigation anomalies kept out of the propulsion diagnosis;
- after the fixes, no false symptom at any time in any flight.

**Two misses, both stated in advance or found and reported:**
- a loss during continuous maneuvering is not confirmed (V13, stated in
  advance);
- V9's expectation is not met as written.

**Scale.** The reasoning is linear in the motor count. Only the offline
diagnosability probe grows faster, about N^2.7: 67 ms at 4 motors.

## 4. What went wrong, and was found

| finding | where | consequence | status |
|---|---|---|---|
| SB-1 | an RPM-only deficit placed on `mechanical_response` would make 2.1.1 eliminate mechanical with no stall check | avoided by design: telemetry is context | test |
| D-1 | 2.1.1 reads a NOMINAL state even when applicability is NOT_APPLICABLE | stock producers never emit that pair | test; the core unchanged |
| maneuvering | the compensation claim's register assumption "near-steady flight" was not implemented; V5 and V6 raised a transient false `COMMAND_NO_RESPONSE` on a healthy motor pair 11 times each | **a wrong answer on a nominal flight, hidden by the end-of-log result** | fixed (NOT_STEADY_FLIGHT, calibration r3 from apparatus data); summary now names every symptom ever raised; blind re-test V11-V13 as expected |
| ESC offline | an offline ESC's zero RPM read as a measured deficit; the power gate's division guard | V9 partly unmet | fixed; tests |
| log completeness | the register said IMPLEMENT; the code had not | none on these logs | implemented; tests |
| W_DYN fragility | a discovered onset shrinks the 0.2 s transient's magnitude to 0.31-1.3 of its known-onset value | none: the transient is context only | documented |
| one-sided telemetry detector | an RPM excess (V10) is not caught at onset without PX4's own warning | configuration A misses it | documented; not changed |
| noisy discovery under maneuvering | about 287 false events per in-flight hour on nominal maneuvering flights, all dismissed | the event list buries the answer | **open** |

**The pattern.** The claim register was right every time. The code fell
short of it three times, and only flight data showed where. Each fix is
pinned by a test. The one that mattered most, the steadiness check, was
re-tested on flights designed after it.

## 5. Governance

**Unchanged, verified (`FINAL_STATE_2_3.json`):**
- Semantic Core 2.1.1;
- frozen v2.0;
- the historical Phase C;
- XSYS-001, XSYS-A1/A2 and the confirmatory result (hard gate PASS, 3,872
  slots, 0 decision differences; H_PRIMARY 55/55, LB 0.7616);
- the 2.2 historical replay outputs and receipts;
- the pinned pilot reports;
- the 66-flight batch, byte for byte;
- the sealed manifests;
- the failure ledger (pinned SHA, no append).

**What 2.3 adds:** code outside the core (`csia_evidence_assurance/`),
new versioned contracts, a new versioned profile, and a separate schema
for stock reports. The historical aircraft profile is not modified.

**Offboard, zero control authority.** Nothing here runs on a vehicle,
commands one, or recovers anything. No FORGE.

**Validation discipline:**
- both flight designs were committed before flying;
- expectations were never revised;
- as-flown results are kept beside the final ones;
- calibration came from apparatus data only;
- the XSYS-001 replay is labelled an exploratory product benchmark,
  reported apart from the confirmatory result.

## 6. Phase by phase

| phase | result | document |
|---|---|---|
| P0 | baseline locked at 5eb7f02: core, gates, tests 51 + 22, replays, 66-flight batch identical, provenance | `BASELINE_2_3.json` |
| P1 | 90 topics, 66 flights; ESC current/voltage and battery current never measured; PX4 monitors silent | `TOPIC_INVENTORY.md` |
| P2-P7 | 15 claims, decided before any adapter; ESC chain in four stages; no thrust from RPM; power, allocation, estimator, compute bounded | `CLAIM_REGISTER.md` |
| P8-P9 | five stock producers ranked; contracts; the 2.2 model not weakened | `STOCK_PRODUCERS.md` |
| P10 | multirotor quad r1, 29 records, gate ACCEPTED; historical profile untouched | `MULTIROTOR_PROFILE.md` |
| P11 | linear reasoning, 1-16 motors; the probe ~N^2.7 | `SCALE.md` |
| P12, P14 | CUSUM and PX4-monitor triggers, 3 s clustering; "something may have started", never "this failed" | `EVENT_DISCOVERY.md` |
| P13 | frozen CUSUM on its own coverage: 4 of 5 covered onsets, 0 false, duplicates absorbed; no coverage on PX4 | `CUSUM_TRIGGER.md` |
| P15-P16 | 0 decision differences known vs discovered; W_DYN not stretched, shown fragile | `UNKNOWN_ONSET.md` |
| P17 | all four motors localized on ordinary logs | `LOCALIZATION.md` |
| P18 | configurations A, B, C compared | `MOTOR_VS_TELEMETRY.md` |
| P19 | the five discipline rules, plus log gaps, D-1, steadiness, ESC offline: permanent tests | `DISCIPLINE.md` |
| P20 | `analyze flight.ulg` is the stock path; reproducible byte for byte | `ORDINARY_ULOG.md` |
| P21-P24 | the summary first; magnitudes with units and thresholds, no invented confidence; coverage with meaning; structural diagnosability | `REPORT_PRODUCT.md` |
| P25 | 15 classes; compute/timing not diagnosable on a stock log | `VALIDATION_SET.md` |
| P26 | 0 false events in hover; 287/h maneuvering, all dismissed after the fix; transient false symptoms as first frozen | `FALSE_POSITIVES.md` |

## 7. What would move the decision

**Real flight logs.** Hardware logs with ESC telemetry (RPM, current) and
a power module would test:
- whether the statistics survive noise;
- whether ESC current shrinks the ambiguity, as the diagnosability probe
  predicts (to {command_not_delivered}).

**Maneuver-aware event discovery.** Reading the commanded setpoints would
keep a commanded change in the command split from becoming a candidate
event. Its null must come from flights that are not this validation set.

**A two-sided telemetry detector,** for RPM excess, with its own
calibration.

**Hardware nulls.** Every threshold here is SIH's and must be
re-calibrated on the target vehicle, by the same rule.
