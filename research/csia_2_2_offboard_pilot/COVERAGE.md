# Coverage: what was observed, and what was not (Phases 9 and 23)

**2026-10-01. NON-CONFIRMATORY.**

**The rule:** an unobserved source is never reported as healthy. A
detector that stayed silent is never reported as an observation of health.

## 1. Coverage states, each on real or frozen data (Phase 9)

| state | meaning | where it occurs | count |
|---|---|---|---|
| NOMINAL | admitted; a check with the power to see the condition passed | EKF2 innovations on 66 flights; W_RPM on motors 1-3 | estimator: 76,797 output-ticks over 121 trials |
| NO_ANOMALY | admitted; a detector stayed silent, which is not health (the contract's `nominal_means`) | frozen CUSUM, every node it can see | U6: battery 1,500 ticks; GPS 1,424 |
| ANOMALY | admitted and adverse | W_RPM, W_DYN, W_CTRL on motor 0 in the A trials; CUSUM battery and motor_esc in power_sag | 55/55 A trials, all three witnesses |
| NOT_APPLICABLE | admitted; nothing to look at in this configuration | EKF2 heading claim after magnetometer loss (S1, 75.5 s on); W_DYN and W_CTRL on motors 1-3 | S1: 252 ticks; campaign: 1,127 output-ticks |
| UNAVAILABLE | the producer could not look | EKF2 before alignment (S1: 0.6-2.6 s); CUSUM GPS during its 76-tick gap | S1: 21 ticks per claim |
| FAULTED | the producer failed | injected only: 242 faulted or unavailable producers (`WRONG_ANSWER_SEARCH.json` P7) | 0 in real data |
| REJECTED:\<status\> | not admitted for another reason | W_DYN outside its validated window (U3, REGIME_INVALID); the 14 mutations | 0 in real data under V3 |
| NO_COVERAGE | the producer says it cannot observe this source | CUSUM: imu0, imu1 (no per-IMU physics chi-square), baro (degenerate clean-arm sigma) | U6: 1,500 ticks each |
| NO PRODUCER (profile) | a record the profile defines that nothing observed in the run (WA-3) | every PX4 log analysed alone: 68 of 68 | 66 flights + S1 |

**The canonical case: CUSUM on an IMU fault** (v1 `imu0_bias_drift`, U6).
- The fault is on imu0.
- The CUSUM has no residual for imu0 and says so (NO_COVERAGE).
- Every node it can see stays silent (NO_ANOMALY, never NOMINAL).
- The final state is "no symptom", with "scope: the run observed 0 of the
  profile's 68 records".
- No line of the report presents imu0 as healthy.
- **Pinned:** `test_a_silent_detector_is_no_anomaly_and_an_unseen_source_is_no_coverage`,
  `test_wa3_a_verdict_names_the_profile_records_nothing_observed`.

**Before the pilot:**
- CUSUM silence was reported NOMINAL;
- an unobserved profile record was not mentioned at all.

## 2. The coverage matrix, from evidence only (Phase 23)

**Cells:**
- **COVERED:** observed, with the right answer, on the data named;
- **PARTIAL:** observed, but only as context, or only part of the event;
- **NO_COVERAGE:** tested, and the producer cannot see it;
- **NOT_TESTED:** no data in this repository puts this producer on this
  event.

**Real** means PX4 547e2ca SITL logs. **Synthetic** means the frozen v1
simulation or the v2 scenario corpus. A synthetic COVERED means:
- the plugins emit records for the injected fault;
- the 2.2 replay reproduces 2.1.1's decision on every tick
  (`REPLAY_2_2_RESULTS.json`: 0 decision differences);
- the correctness of those 2.1.1 answers is the Phase C record, not this
  pilot's.

| event class | W_RPM | W_DYN | W_CTRL | PX4 EKF2 status | frozen CUSUM | v2 domain plugins | evidence |
|---|---|---|---|---|---|---|---|
| motor thrust loss (actuator degradation) | COVERED (real, 55/55 adverse) | COVERED (real, 55/55) | COVERED (real, 55/55, at T3) | NO_COVERAGE (real: 0 over-gate, AUC 0.43-0.55) | NOT_TESTED | COVERED (synthetic: MS_B4_MECHANICAL, STALLED_ACTUATOR) | `CAMPAIGN_XSYS.json`; 2.2 scenario replay |
| RPM telemetry corruption | COVERED (real, 55/55 adverse) | COVERED as refuter (real, nominal 55/55) | COVERED as refuter (real, 55/55) | NO_COVERAGE (does not read ESC telemetry) | NOT_TESTED | COVERED (synthetic: MS_B5_RESPONSE_SENSOR) | same |
| nominal flight with a benign onset | COVERED (real, 11/11 silent) | COVERED (real) | COVERED (real) | COVERED (real, NOMINAL) | NOT_TESTED | COVERED (synthetic: NOMINAL) | same |
| magnetometer loss | NOT_TESTED | NOT_TESTED | NOT_TESTED | PARTIAL (real, S1: the aiding change is named and the heading claim turns NOT_APPLICABLE; no claim says "magnetometer failed") | NOT_TESTED (no magnetometer fault in the v1 scenarios used) | NOT_TESTED | `SITL_SELECTOR_RUN.md` |
| EKF2 resets and aiding changes | — | — | — | COVERED (real: 66 flights + S1; every reset reported after WA-2) | — | — | `CAMPAIGN_REPLAY.md` §2 |
| EKF2 lane switch | — | — | — | NOT_TESTED on real data (S1 ran the selector with one lane); synthetic log only | — | COVERED (synthetic: E1) | `LANE_SWITCH_EXPERIMENT_DESIGN.md` |
| IMU bias drift | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NO_COVERAGE (synthetic: U6) | COVERED (synthetic: E1, imu0) | U6, U7 |
| battery and ESC power sag | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | COVERED (synthetic: battery 30.20 s, motor_esc 30.12 s) | COVERED (synthetic: POWER_SAG, MS_B2_POWER_PATH) | U5 |
| shared supply rail | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | COVERED (synthetic: SHARED_RAIL, MS_C2_SHARED_POWER) | 2.2 scenario replay |
| process stall, compute deadline | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED (EM-1 not built) | NOT_TESTED | COVERED (synthetic: PROCESS_STALL, MS_A4, MS_D4) | same |
| sensor or transport delay | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | COVERED (synthetic: MS_A1, MS_A2; U8 with a failed predicate) | U8 |
| communication link loss | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | COVERED (synthetic: PACKET_LOSS, MS_C3) | 2.2 scenario replay |
| GNSS source failure | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED (no GNSS fault in any real log) | NOT_TESTED | COVERED (synthetic: MS_D1_NAV_SOURCE) | same |

**Reading the matrix:**
1. **On real data,** only one event class is seen by more than one
   producer: motor thrust loss, through the three XSYS-001 witnesses.
2. **The PX4 estimator,** the only producer that reads a stock PX4 log, is
   COVERED for its own configuration history and NO_COVERAGE for the
   fault class the campaign injected.
3. **Every power, compute, timing and communication class** is covered on
   synthetic data only. On a real PX4 log, those records have no producer
   (§3).

## 3. The batch coverage matrix (66 real flight logs)

**`analyze-many` over the 66 XSYS-001 logs, each analysed alone**
(`batch/coverage_matrix.txt`; `SCALE.md` has the run):

| producer, claim | states seen across the 66 flights |
|---|---|
| EKF2 INNOVATION_POS, VEL | 57 flights: NOMINAL, UNAVAILABLE, NOT_APPLICABLE. 9 flights: NOMINAL, UNAVAILABLE |
| EKF2 INNOVATION_HGT | 66 flights: NOMINAL, UNAVAILABLE |
| EKF2 INNOVATION_HDG | 62 flights: NOMINAL, UNAVAILABLE, NOT_APPLICABLE. 4 flights: NOMINAL, UNAVAILABLE |
| any profile record | **none: 0 of 68 observed in all 66 flights** |

**Where each state comes from:**
- **UNAVAILABLE:** before alignment.
- **NOT_APPLICABLE:**
  - mostly one tick, between alignment and the start of GNSS and heading
    aiding (E055: aligned at 2.5 s, aiding from 2.6 s);
  - the flights where they fall in the same tick have none;
  - for heading, also the two flights whose heading aiding stopped.
- **Height:** aided from 0.7 s, before alignment, so it is never
  NOT_APPLICABLE.

**This is the gap that matters most for the product.**
- A stock PX4 log gives 2.2 nothing it can diagnose with.
- The motor-degradation flights look exactly like the nominal flights when
  analysed alone.
- The report now says so (WA-3).
