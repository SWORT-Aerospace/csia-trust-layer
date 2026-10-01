# Wrong-answer search on real pilot data (Phase 18)

**2026-10-01. NON-CONFIRMATORY.** **Harness:** `wrong_answer_search.py`.
**Results:** `WRONG_ANSWER_SEARCH.json`.

**Every probe starts from real outputs:**
- run S1's estimator outputs;
- every XSYS-001 trial's witness outputs;
- the full campaign replay with each flight's estimator.

## 1. Results after the two fixes below

| probe | wrong answer looked for | over | found |
|---|---|---|---|
| P1 | wrong UNIQUE or wrong SUPPORTED | 3,872 XSYS-001 slots (121 trials × 8 checkpoint-variants × 4 motors) through the Analyzer | 0 |
| P2 | true hypothesis removed | the same | 0 |
| P3 | valid evidence rejected | witnesses: every slot (only V4's out-of-window W_DYN is refused, correctly); estimator: 121 trials with their flight logs | 0 |
| P4 | invalid evidence admitted | 14 single mutations of real envelopes: producer version, contract version, unknown claim, claim on another record, attributability, missing lineage, NaN content time, content after production, content in the future, stale content, missing epoch, another lane's epoch, profile mismatch, witness outside its window | 0 missed (each refused with the expected status) |
| P5 | dependent evidence treated as independent | 121 trials, 2.2's independent lines against the ground-truth source analysis | 0 mismatches |
| P6 | no coverage treated as nominal | CUSUM on imu0_bias_drift; run S1; the 66 flight logs analysed alone | 0 at the record level; **one at the report level (WA-3)** |
| P7 | producer fault treated as vehicle fault | 242 injections: every witness output of every trial duplicated by a FAULTED or UNAVAILABLE producer saying the opposite | 0 decisions changed; 0 faulted outputs among the adverse evidence |
| P8 | configuration reset mishandled | run S1: every raw reset increment in the log against the reported changes; refusals for resets | reported = real for all five counters (after WA-2); 0 refusals |
| P9 | timeline order wrong; content-time error | run S1 report; every admitted output | monotonic; 0 admitted outputs with content after their tick |

## 2. Findings, each with a minimal reproduction

### WA-1: one IMU chip named as two independent sources (fixed)

| | |
|---|---|
| **found by** | P5's ground-truth tracing (an IMU's gyro and accelerometer share device id 1310988) |
| **defect** | the PX4 adapter's lineage named `sensor:gyro.<id>` and `sensor:accel.<id>` as separate roots. A gyro-only monitor and an accelerometer-only monitor of one chip would count as two independent lines, while one chip fault corrupts both |
| **observed on the campaign?** | no: every producer here that read the IMU used the gyro name. Latent |
| **reproduction** | `Lineage.of("sensor:gyro.1310988")` and `Lineage.of("sensor:accel.1310988")`: `independent_lines` gave 2 (ground truth 1) |
| **fix** | roots are `sensor:imu.<device id>` in the PX4 and XSYS adapters (commit 62aa012) |
| **pinned** | `test_wa1_one_imu_chip_is_one_root` |

### WA-2: resets before the first lane selection missing from the timeline (fixed)

| | |
|---|---|
| **found by** | P8 on run S1 |
| **defect** | in selector mode the adapter followed a lane only once the selector had named it primary (0.516 s in S1). EKF2's position and height resets at 0.428 s fell before any observed state, and never appeared as configuration changes |
| **admissibility affected?** | no: no estimator evidence may be emitted before a lane is primary, and none was |
| **reproduction** | S1 extract: raw `reset_count_pos_ne` increments 4, reported 3; `reset_count_pod_d` 1, reported 0 |
| **fix** | before the selector's first message the lowest instance is kept as PROVISIONAL context: it carries resets and aiding changes into the context, and is never emitted as evidence |
| **pinned** | `test_wa2_every_real_reset_is_reported_even_before_the_first_selection` |

### WA-3: "no symptom" without its scope (fixed)

| | |
|---|---|
| **found by** | reading the batch reports of the 66 flight logs (`SCALE.md`), after the probes above had passed |
| **defect** | a flight log analysed alone gives one producer, EKF2, whose claims are outside the profile. For XS1A1-C00-A-E055 (motor 0 at 55 % thrust) the report said "no symptom detected" and "nothing abnormal at any tick", and nothing in it said that no producer observed the motors. Every record-level state was right; the report omitted what had no record at all |
| **observed on the campaign?** | yes: all 66 flight-level reports, including the 55 with a degraded motor |
| **reproduction** | `python -m csia_evidence_assurance analyze XS1A1-C00-A-E055.ulg` at commit a44202f |
| **fix** | report schema 3: `profile_coverage`, the PROFILE COVERAGE section, and a "scope" line beside the final state (`ANALYZER_MVP.md` §5) |
| **pinned** | `test_wa3_a_verdict_names_the_profile_records_nothing_observed` |
| **why the probes missed it** | P6 checked the states of records that exist. A record that no producer emits has no state to check |

## 3. Report-quality defects found while reading the reports (fixed)

These are not wrong answers. They are places where a correct answer was not
visible to an engineer (`ENGINEER_USEFULNESS.md`).

| defect | fix |
|---|---|
| an eliminated hypothesis named only the first refuter 2.1.1 lists; the second refuter's evidence was invisible | every refuter that held, and its evidence |
| two refutations resting on the same IMU were not flagged | "the refuting evidence shares sensor:imu.1310988: it is not independent corroboration" |
| a lineage group did not say what ties it together | first "not independent because they share: …"; then, after FV-1 (`FALSE_VALUE_SEARCH.md`), each shared source with the members that hold it |
| configuration changes read as counters ("ekf2.aiding.hdg 2 -> 3") | PX4 terms ("hdg aiding fused: 3-axis magnetometer -> none") |
| attribution NO_EVIDENCE beside a SUPPORTED localization, unexplained | 2.1.1's reason, and a note that the localization is the diagnosis |

## 4. Semantic Core

**No 2.1.1 defect was found.** Every wrong answer looked for was absent at
the semantic level:
- WA-1 and WA-2 were in 2.2's adapters;
- WA-3 was in 2.2's report.

The stop rule for a semantic-core defect was not triggered.
