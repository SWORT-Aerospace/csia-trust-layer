# Claim-evidence matrix (PRIME)

**2026-10-02. Every public statement about CSIA Flight Assurance must be a
row here with PUBLIC-SAFE = YES, worded as in the row, qualifiers included.**
A claim without evidence is not published. A claim marked NO stays
internal, whatever its engineering interest.

**Versions:**
- analyzer 2.2.1;
- Semantic Core 2.1.1;
- profile multirotor-quad r1;
- view prime-view-1;
- support matrix prime-1;
- full analysis tested on PX4 547e2ca (SITL).

**"SITL"** means PX4 software-in-the-loop with the SIH quadrotor. It is not
physical evidence.

## 1. Product-behaviour claims (properties of the software)

| # | public claim | experiment | dataset | result | limitations | version | public-safe? |
|---|---|---|---|---|---|---|---|
| P1 | "One command analyses an ordinary PX4 ULog. No onset time, labels or configuration files are needed." | PRIME-A gate (`prime_a_gate.py`) | 39 logs: 31 SITL flights, the pilot run, 6 pyulog logs (4 real boards), the real boat | 39/39 analysed without a crash; installable from a fresh environment | full analysis of propulsion evidence needs the 547e2ca-era topics | analyzer 2.2.1, view prime-view-1 | **YES** |
| P2 | "The same log and version always give byte-identical outputs." | PRIME-A determinism check | 3 logs (SITL, real boat, pilot) × 2 runs, all 8 output files | identical | three logs; one machine | as P1 | **YES** |
| P3 | "Evidence that was not observed is never reported as healthy." | the coverage-class invariant (permanent tests in `tests/test_csia_prime.py`) | the 11 sample reports, plus constructed states | no unavailable, stale, faulted, unknown or uncovered state maps to NO_ANOMALY | a property of the classification, not a validation of any monitor. **An event-relative NO_ANOMALY means "no change at this event"**: with a late event, a corrupted signal compared with itself reads NO_ANOMALY (D-PRIME-2) | prime-view-1 | **YES**, worded as "not observed is never reported as healthy" only |
| P4 | "No probability or confidence percentage is reported; conclusions carry semantic states (UNIQUE, AMBIGUOUS, ...)." | the text test on the first page | all sample reports | no "%" and no probability wording | — | prime-view-1 | **YES** |
| P5 | "Every conclusion carries a receipt: the admitted, refuting and rejected evidence, rejection reasons, lineage, producer health, configuration and versions." | Track A receipt tests | sample reports | receipts present per symptom, attribution and unconfirmed output | lineage is at topic-channel level (see L2) | prime-view-1 | **YES** |
| P6 | "Each log is checked against a published support matrix. Unsupported vehicles and partial logs are stated, not silently analysed." | support check (`support.py`) | **real:** FMUv5 boat (UNSUPPORTED), CubeOrange VTOL (UNSUPPORTED), AUAV X2.1 (PARTIAL) | all three stated correctly | three real logs; the matrix is SITL-derived | support matrix prime-1 | **YES** |
| P7 | "Re-raised identical PX4 warnings are grouped into one alert." | alert grouping; C3's merge rule | **real:** FMUv5 boat | 12 events in 294 s armed → 4 alerts, each a distinct real condition | one real log | prime-view-1 | **YES**, citing one real log |
| P8 | "CSIA has no flight-control authority: it is an offboard analysis tool." | design; `csia_evidence_assurance` has no output path to a vehicle | — | — | — | all | **YES** |

## 2. Diagnostic claims (SITL only)

| # | public claim | experiment | dataset | result | limitations | version | public-safe? |
|---|---|---|---|---|---|---|---|
| S1 | "In PX4 simulation, a motor's loss of effect in hover or a hold was attributed to the right motor, with the remaining causes listed (AMBIGUOUS among 4)." | 2.3 validation flights | 2.3 V1-V4, V12 (SITL) | 5/5 right motor; no other motor at any time | SITL, one airframe, 40 % loss; cause within the propulsion path not separable (no ESC or battery current) | 2.3 / analyzer 2.2.1 | **YES, only with "in PX4 simulation"** |
| S2 | "In PX4 simulation, a telemetry fault with the same local RPM symptom as a motor loss was not reported as a motor failure." | 2.3 V9, V10; PRIME demo; the stress envelope's matched base | SITL; 1,056 perturbed runs | 0 telemetry cases read as a physical loss | SITL; offline corruption for the matched case; one airframe. **Says nothing about reporting the telemetry fault itself:** an RPM excess is never discovered (D-PRIME-2) | as S1; stress v2 | **YES, only with "in PX4 simulation"** |
| S3 | "Under offline timing, noise, bias and rate perturbations of simulated logs, CSIA produced no false symptom and no wrong attribution; it reported real losses as unconfirmed beyond its envelope." | stress envelope v2 | 6 SITL bases, 15 variables, 1,056 runs | 0 false symptoms, 0 wrong-motor, 0 UNIQUE; losses unconfirmed at the stated edges | one variable at a time; SITL bases; **D-PRIME-1 shows off-grid time breaks it** (not a ULog condition) | stress v2 | **YES, with all three qualifiers** |
| S4 | "Losses during continuous maneuvering are reported as unconfirmed, with the reason, rather than attributed." | 2.3 V13; RB-001 evaluation; event-discovery evaluation | SITL | 1/7 losses confirmed (the hover one); 0 wrong attributions | this is a **limitation** claim | 2.3; PRIME C3 | **YES**, as a limitation |
| S5 | "CSIA counts corroboration by shared source, not by the number of monitors that fired." | 2.2 lineage; PRIME demo case A | SITL V4 | 3 adverse outputs → 2 independent lines | lineage roots at topic channels, not hardware | 2.2 | **YES** as a software behaviour; **NO** as "matches your hardware topology" (L2) |

## 3. Claims that are NOT public-safe

| # | claim | why not | what would make it safe |
|---|---|---|---|
| N1 | "Distinguishes real motor degradation from telemetry corruption on hardware" | **no physical data** | B4 matched A/B on the bench, evaluated once under `B4_MATCHED_AB_PROTOCOL.md` |
| N2 | "Validated on real flights" / "works on real propulsion faults" | no real propulsion event has been analysed against truth | the first real propulsion logs with truth (pilot customers, RflyMAD if reachable, the bench) |
| N3 | "Diagnoses maneuvering faults" | 1/7 confirmed in SITL; B3 not product-approved; B3 has a CG-change confound | B3 on HIL or a restrained vehicle, with a validity condition (PRIME-D) |
| N4 | "Low alert burden" | the product's event discovery raised 310 false candidate events per nominal SITL hour while maneuvering; the 0 per hour candidates (E2, E3, E5) are SITL-only and not in the product | E2 on a real nominal corpus, as a versioned discovery mode |
| N5 | "Reduces analysis time" / any ROI | no user study has been run (E2 protocol prepared, not run) | the E2 test or pilot metrics (`COMMERCIAL_PILOT.md` section 6) |
| N6 | "Generic PX4 support" | the support matrix covers quad X and 547e2ca-era topics; pre-allocation PX4 is PARTIAL | — (do not claim) |
| N7 | "Detects motor failures" / "AI diagnostics" | crowded categories (`DEFENSIBILITY_AND_IP.md` §2.4); not the value shown | — (do not claim) |
| N8 | "First" or "unique" evidence assurance | aircraft vehicle-level reasoners and model-based diagnosis provide every function (`COMPETITOR_FUNCTION_MATRIX.md`) | — (do not claim) |
| N9 | "Unlike Flight Review / FlightMD / Auterion / ..., CSIA ..." | competitor functions are read from search summaries (V0), not product documentation | a documented comparison against each product's current documentation |
| N10 | "Lineage reflects hardware dependencies" | lineage roots are topic channels; S4 of the B4 protocol predicts this fails on hardware | a customer wiring map in the producer contracts; tested on the bench |
| N11 | "Patented" / "patent pending" | nothing filed; the combination with the most interest (MNC-1) faces a HIGH prior-art concern | attorney review (`DEFENSIBILITY_AND_IP.md`) |
| N12 | "Reports ESC telemetry corruption" (unqualified) | a telemetry **excess** opens no event and vanishes from the report; 2.3 V10's correct-looking result relied on PX4's simulation-only injection message (`DEFECT_D_PRIME_2.md`) | a two-sided telemetry trigger and a level-validity condition, in a versioned discovery mode; then "reports telemetry deficits and excesses" |

## 4. Rules for using this matrix

- **Quote rows, not summaries.** The qualifier is part of the claim: "in PX4
  simulation", "one real log", "SITL bases".
- **A new claim needs a new row** with its experiment and dataset before it
  is used.
- **A row's result changes only by a new experiment.** It is never
  re-worded upward.
- **Physical results, when they exist, are added as new rows.** SITL rows
  stay as they are.
