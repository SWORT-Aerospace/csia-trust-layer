# Claim-evidence matrix (PRIME-1 Phase 18)

**2026-10-03. Supersedes PRIME's matrix for the successor product; PRIME's
matrix stays as recorded.** Every public statement about CSIA Flight
Assurance PRIME-1 must be a row here with PUBLIC-SAFE = YES, worded as in
`PUBLIC_CLAIMS.md`, qualifiers included.

**Versions (all rows unless stated):**
- release prime1;
- analyzer 2.2.1;
- Semantic Core 2.1.1;
- profile multirotor-quad r1;
- view prime1-view-2;
- support contract prime1-r1;
- telemetry producer csia-prime1-stock-tel-r1.

**Validation levels:**
- **SOFTWARE** (a property of the code, true for any input);
- **SIMULATION** (PX4 SITL, SIH quadrotor, PX4 547e2ca);
- **REAL_LOG_CONTEXT_ONLY** (real logs read; no diagnostic truth);
- **PHYSICAL_VALIDATED**: no row.

## 1. Product-behaviour claims

| # | public claim | artifact | dataset | version | result | limitation | validation level | public-safe? |
|---|---|---|---|---|---|---|---|---|
| M-P1 | one command, only the log | `REAL_DATA_READY_CHECK.json`; `DEV_CHECKS.json`; PRIME-A 39-log run | 7 real logs (6 pyulog samples, the PX4 docs boat); 31 SITL; the pilot run | prime1 | every log analysed, exit 0; support state stated | full propulsion analysis needs the 547e2ca-era topics | SOFTWARE; REAL_LOG_CONTEXT_ONLY | **YES** |
| M-P2 | byte-identical outputs | `REAL_DATA_READY_CHECK.json` (twice, proxy removed); `FRESH_INSTALL_PRIME1.json`; `test_the_view_and_receipts_are_deterministic` | 7 real logs; 8 sample logs; synthetic | prime1 | identical; the installed wheel reproduces the repository's bytes | one machine type | SOFTWARE | **YES** |
| M-P3 | not observed is never reported as healthy | coverage-class invariant; first-page sections 3-4 (`test_a_page_without_admitted_evidence_justifies_nothing_about_health`) | samples; synthetic | prime1-view-2 | no unobserved state maps to NO_ANOMALY; a page with no admitted evidence claims nothing about health | an event-relative NO_ANOMALY means "no change at this event" | SOFTWARE | **YES** |
| M-P4 | no percentages, plain states | first-page test | every sample | prime1-view-2 | no "%", no probability wording | — | SOFTWARE | **YES** |
| M-P5 | a receipt per conclusion | `test_every_conclusion_has_a_complete_receipt` | synthetic; samples | prime1-view-2 | all 15 Phase 16 fields present | lineage at topic-channel level | SOFTWARE | **YES** |
| M-P6 | support decided before interpretation | `support_prime1`; `test_support_states_are_decided_before_interpretation`; samples 06-08 | real: AUAV X2.1, CubeOrange VTOL, FMUv5 boat | support contract prime1-r1 | VTOL and boat withheld (UNSUPPORTED_VEHICLE_CONFIGURATION); old PX4 stated as UNKNOWN_VERSION / PARTIAL | the contract is SITL-derived | SOFTWARE; REAL_LOG_CONTEXT_ONLY | **YES** |
| M-P7 | independent lines, not monitor count | Semantic Core lineage; sample 02 | SITL | 2.2 lineage | 3 adverse outputs = 2 lines | roots at topic channels, not hardware | SOFTWARE | **YES** as software behaviour |
| M-P8 | local, no network | `REAL_DATA_READY_CHECK.json` (no network module imported; runs with proxy variables removed) | 7 real logs | prime1 | no network import; identical offline | — | SOFTWARE | **YES** |
| M-P9 | blind engagement, sealed before reveal | `engagement.py`; `REAL_DATA_READY_CHECK.json`; `test_the_engagement_enforces_the_blind_protocol` | a real log as stand-in | prime1 | expected time refused in blind mode; no rerun after seal; reveal only after seal; tampering detected | not yet used with a customer | SOFTWARE | **YES** |

## 2. Telemetry classes (separated)

| # | public claim | artifact | dataset | version | result | limitation | validation level | public-safe? |
|---|---|---|---|---|---|---|---|---|
| M-T1 | **RPM shortfall** (reported RPM below command) is found as RPM_DEFICIT_EVENT and kept a telemetry observation | `TELEMETRY_MATRIX_DEV.json`; held-out matrix (`HELDOUT_RESULTS.json`) | SITL hover and maneuvering, x0.1 to x0.95, step down | prime1 | development 10 of 10 shortfall and step-down cases (CAL1, V5); held-out 10 of 10 (HN1, HN4): RPM_DEFICIT_EVENT, telemetry DEGRADED, no motor symptom | SITL thresholds; one airframe | SIMULATION | **YES, with "in PX4 simulation"** |
| M-T2 | **RPM excess** (reported RPM above command) is found as RPM_EXCESS_EVENT and kept a telemetry observation | as M-T1; blinded 2.3 V10; held-out HT1 | SITL x1.05 to x10, step up; PX4 ESC WRONG injection | prime1 | development and held-out matrix: 10 of 10 excess and step-up cases each, all RPM_EXCESS_EVENT; held-out HT1 (PX4 ESC WRONG, maneuvering): found at onset (0.000 s), no symptom. 2.3 missed HT1 | D-PRIME-2 is fixed only in prime1; release 2.3 still misses it | SIMULATION | **YES, with "in PX4 simulation"** |
| M-T3 | **telemetry dropout** (no ESC samples for 10 s) gives no motor symptom | telemetry matrix | SITL | prime1 | no motor symptom in any dropout case; no event required | a gap is not a measurement; nothing is concluded over it | SIMULATION | **YES**, as "a gap is never read as a fault" |
| M-T4 | **stuck** telemetry value | telemetry matrix | SITL hover | prime1 | not discovered as a change in steady hover; no motor symptom | **blind spot** | SIMULATION | **NO** as a detection claim |
| M-T5 | **offline producer** (ESC reports itself offline) is stated as UNAVAILABLE, never as a loss or as health | telemetry matrix `zero_while_offline`; held-out HT2; sample 04 | SITL | prime1 | matrix `zero_while_offline` 2 of 2 held-out; HT2: ESC_OFFLINE_EVENT at onset, telemetry UNAVAILABLE, no symptom | PX4's online flag must be logged | SIMULATION | **YES, with "in PX4 simulation"** |
| M-T6 | **matched motor-vs-telemetry discrimination**: a telemetry corruption with the same local RPM symptom as a motor loss is not read as a motor failure | PRIME demo and stress envelope (2.3); the PRIME-1 bundle's matched telemetry case (prime1) | SITL; offline corruption | 2.3 and prime1 | 0 telemetry cases read as a physical loss | offline corruption, one airframe; the physical A/B is designed, not run | SIMULATION | **YES, with "in PX4 simulation"** |
| M-T7 | static offset or slow drift | telemetry matrix | SITL | prime1 | not discovered as a change; a gross static disagreement is a coverage notice | **blind spot** | SIMULATION | **NO** as a detection claim |

## 3. Diagnostic and event-discovery claims (simulation)

| # | public claim | artifact | dataset | version | result | limitation | validation level | public-safe? |
|---|---|---|---|---|---|---|---|---|
| M-S1 | a loss in hover or a hold attributed to the right motor, causes listed | 2.3 validation; held-out HF1, HF2 | 2.3 V1-V4, V12; held-out HF1-HF2 | 2.3; prime1 | held-out HF1 (hover) and HF2 (hold): COMMAND_NO_RESPONSE on the right motor, AMBIGUOUS among 4; no other motor in any flight | AMBIGUOUS among 4 without ESC or battery current | SIMULATION | **YES, with "in PX4 simulation"** |
| M-S4 | maneuvering losses found but unconfirmed, with the reason | held-out HF3, HF4; 2.3 V13 | SITL | prime1 | held-out HF3, HF4: RPM_DEFICIT_EVENT at onset, no symptom (physical witness refused: not steady); 0 wrong attribution | a **limitation** claim | SIMULATION | **YES**, as a limitation |
| M-E1 | event discovery: alert burden, recall, onset | `HELDOUT_RESULTS.json` (preregistered, run once) | 14 prospectively flown SITL flights, blinded; jittered copies | prime1 vs 2.3 | **PROMOTE** (S1-S6 all hold): 1 nominal event in 0.298 h (PX4's own magnetometer timeout; 0 propulsion events) vs 92 for 2.3; 6 of 6 faults found (2.3: 5); median onset error 0.010 s; 0 false symptoms; 0 wrong attribution | about 0.3 nominal hours; SITL noise is far below real; EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY | SIMULATION | **YES, only with "in PX4 simulation" and the measured hours** |

## 4. Claims that are NOT public-safe

| # | claim | why not | what would make it safe |
|---|---|---|---|
| N1 | "Distinguishes real motor degradation from telemetry corruption on hardware" | no physical data | the matched A/B on a bench (PRIME `B4_MATCHED_AB_PROTOCOL.md`), evaluated once |
| N2 | "Validated on real flights" / "works on real propulsion faults" / any configuration marked PHYSICAL_VALIDATED | no real propulsion event analysed against truth | a blind pilot on real logs with truth sealed, or the bench |
| N3 | "Low false-alarm rate" (unqualified) | the held-out nominal set is a fraction of an hour of SITL with almost no noise | a real nominal corpus from a pilot customer, per vehicle |
| N4 | "Detects stuck, drifting or offset RPM telemetry" | blind spots (M-T4, M-T7) | a level-validity detector, evaluated before any claim |
| N5 | "Reduces analysis time" / any ROI | no user study or pilot run | the pilot metrics (`PILOT_METRICS.md`) |
| N6 | "Generic PX4 support" | quad X only | further profiles, each validated |
| N7 | "Diagnoses maneuvering faults" | losses in maneuvering are not confirmed | a maneuver-valid witness, validated on HIL or hardware |
| N8 | "First", "only", "unique in the market" | not established against each product's documentation | — (do not claim) |
| N9 | "Patented" | nothing filed | attorney review |
| N10 | "Lineage reflects hardware dependencies" | lineage roots are topic channels | a customer wiring map; tested on the bench |

## 5. Rules for using this matrix

- **Quote rows, not summaries.** The qualifier is part of the claim.
- **A new claim needs a new row** with its artifact and dataset first.
- **A result changes only by a new experiment.** It is never re-worded
  upward.
- **Physical results, when they exist, are new rows.** Simulation rows stay.
- **A row with validation level SIMULATION can never become PHYSICAL_VALIDATED
  by argument**, only by a physical experiment.
