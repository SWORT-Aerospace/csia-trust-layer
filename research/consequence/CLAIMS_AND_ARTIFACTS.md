# Phase 8 — what may be said, and the artifact that backs it

One row per claim. If a claim is not in this table, this phase does not
support it. If a row has no artifact, the claim is not made.

**The evidence ladder, unchanged from the preregistration:**
`SOURCE_ANALYSIS` · `DETERMINISTIC_SIMULATION` · `REPLAY` · `SITL` · `HIL` ·
`BENCH_HARDWARE` · `FLIGHT`. **Nothing in this phase reaches above
`DETERMINISTIC_SIMULATION`**, and the consequence rows sit on
`MODEL_BASED_ACTION_CONSEQUENCE`, which is a model of a response and not a
rung of that ladder.

---

## Claims this phase supports

| # | claim | level | artifact |
|---|---|---|---|
| C1 | Eighteen evidence terms in `csia/runtime/online.py` carry a gate expression, recorded verbatim | `SOURCE_ANALYSIS` | `results/GATE_INVENTORY.json` |
| C2 | Seven of them close while their data is fresh and no independent freshness path reacts; an eighth, `hist_vr_withdrawal`, is a boundary case counted separately | `SOURCE_ANALYSIS` | `results/GATE_INVENTORY.json`, `PHASE2_GATE_FINDINGS.md` |
| C3 | A second derivation that imports no CSIA module reaches the same set | `SOURCE_ANALYSIS` | `results/INDEPENDENT_GATE_EVALUATION.json`, `independent_gate_evaluator.py` |
| C4 | A structural support classifier distinguishes `IDENTIFIABLE` / `AMBIGUOUS` / `NON_IDENTIFIABLE` from active evidence alone, never from a normalized number | `DETERMINISTIC_SIMULATION` | `csia_consequence/support.py`, `tests/test_consequence_support.py` |
| C5 | Twelve hand-read paths in PX4 `547e2caa` and ArduPilot `01a504b4` show the same structure, in one subsystem family | `SOURCE_ANALYSIS` | `CROSSARCH_AUDIT.md`, `results/CROSSARCH_AUDIT.json` |
| C6 | ArduPilot states the feedback-loss mechanism in its own source comment | `SOURCE_ANALYSIS` | `results/CROSSARCH_AUDIT.json`, finding `AP-COMMENT` |
| C7 | A standard-library reimplementation reproduces both mechanisms without importing CSIA, by a different derivation | `DETERMINISTIC_SIMULATION` | `CSIA_LITE.md`, `results/CSIA_LITE_DEMO.json` |
| C8 | Occlusion changes the support state only where the closing relation is the sole separator of two candidates | `DETERMINISTIC_SIMULATION` | `results/CSIA_LITE_DEMO.json`, `redundancy_note` |
| C9 | For `accel_motor_current` and `accel_esc_rpm` on this airframe, the occlusion window has **zero** overlap with airborne flight: 0.00 s of fault-window occlusion over 48 locked scenarios | `MODEL_BASED_ACTION_CONSEQUENCE` | `phase3/results/PHASE3_RESULTS_LOCKED.json` |
| C10 | Conditions B and C for those gates give identical first-response times and position errors to three decimal places | `MODEL_BASED_ACTION_CONSEQUENCE` | same |
| C11 | For `heading_course`, the gate is shut for 3.992 s of a 4.0 s fault in a physically consistent regime, and the fault is still detected in 21 of 24 seeds | `MODEL_BASED_ACTION_CONSEQUENCE` | same |
| C12 | The seed-paired gate-shut versus gate-open difference is 3/24 vs 1/24, exact McNemar p = 0.625, not distinguishable from chance at α = 0.05 | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `paired_tests` |
| C13 | P0, P1 and P2 are identical on all 216 locked scenarios | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `policy_table` |
| C14 | The campaign replays byte-identically (two full locked runs) | measured | `phase3/REPRODUCE.md`, `SHA256_MANIFEST.json` |
| C15 | An actionable consequence **is** reachable under the current model, in a physically consistent configuration and with no disarmed-gate scenario | `MODEL_BASED_ACTION_CONSEQUENCE` | `phase31/results/PHASE31_RESULTS_LOCKED.json` |
| C16 | `structural/EG` gives 40/40 action conflicts against 0/40 in its matched control, exact McNemar p = 1.82 × 10⁻¹² | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `tests` |
| C17 | A confident attribution is issued while its separating evidence is entirely gated off in 40/360 scenarios, CI [0.0806, 0.1482] — and is correct in all 40 | `MODEL_BASED_ACTION_CONSEQUENCE` | same |
| C18 | P2's activation precondition is reachable: 40/40 eligible, CI [0.911903, 1.0] | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `actionability_precondition` |
| C19 | P2 produced 40 false refusals, prevented 0 incorrect actionable decisions, and doubled action conflicts 40 → 80 | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `by_policy` |
| C20 | `SOURCE_INDICATORS` omits the per-IMU doppler edges from the IMU indicator sets | `SOURCE_ANALYSIS` | `phase31/PHASE31_RESULTS.md`, FL-029 |
| C21 | Stronger-than-`CAUTION` transitions are reachable: `CRITICAL` by two routes, `EMERGENCY` by one | `MODEL_BASED_ACTION_CONSEQUENCE` | `phase31/PREREGISTRATION_PHASE31.md` §4 |
| C22 | At the Phase-3.2 preregistered confirmatory point, evidence gating produces an action conflict in 40/40 paired seeds against 0/40 matched controls: exact McNemar p = 1.82 × 10⁻¹², RD = 1.0, exact conditional 95 % CI [0.823806, 1.0], 0 exclusions, 0 false escalations in the nominal control | `MODEL_BASED_ACTION_CONSEQUENCE` | `phase32/results/PHASE32_RESULTS_LOCKED.json` |
| C23 | With ESC telemetry the fault reaches `CRITICAL` at 34.220 s and safe state at 54.380 s; without it, no failsafe level and no safe state | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `summary` |
| C24 | The effect holds at every gain in the declared grid, 1.5 through 4.0 | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `tests` |
| C25 | Crossing time and conflict rate are both non-monotone in fault rate on the secondary arm (40, 40, 31, 0, 0) | `MODEL_BASED_ACTION_CONSEQUENCE` | same, FL-031 |
| C26 | 0 invalid runs over 880 locked scenarios; the campaign replays byte-identically | measured | `phase32/REPRODUCE32.md`, `SHA256_MANIFEST32.json` |
| C27 | At the matched operating point on the `vibration` node — **zero false alarms observed** for all three — CSIA trust persistence has median detection delay 2.52 s against 0.08 s for both CUSUM (h = 200) and a bare threshold (μ₀+10σ₀); observed FAR 0/40 nominal runs, CI [0.0, 0.0881], 0 pre-onset alarms on 800 faulted runs, 800/800 detections. **A tradeoff result, not a superiority result** | `DETERMINISTIC_SIMULATION` | `research/phase4/results/PHASE4_RESULTS_LOCKED.json` |
| C28 | The matching selected CSIA's **fastest** grid threshold: all twelve θ have development FAR 0.000, so the comparison is not an artefact of an unfavourable CSIA operating point | `DETERMINISTIC_SIMULATION` | same, `full_grid_development` |
| C29 | CSIA's **observed** locked false-alarm rate is 0/40 at **12 of 12** declared thresholds; CUSUM's at 5 of 10 and the bare threshold's at 1 of 8. This is threshold robustness, not detection performance | `DETERMINISTIC_SIMULATION` | same, `full_grid_locked` |
| C30 | CSIA's detection delay is **non-monotone in fault magnitude** — fastest at the weakest gain (2.26 s at 1.5, 2.60 s at 4.0) — and monotone in onset time (2.36 s → 2.76 s) | `DETERMINISTIC_SIMULATION` | same, `by_gain`, `by_onset` |
| C31 | Two of CSIA's twelve thresholds cannot detect this fault reliably: θ = 0.30 misses 25.4 %, θ = 0.20 misses 99.9 % | `DETERMINISTIC_SIMULATION` | same |
| C32 | At `TARGET_FAR = 0.10` the bare threshold's locked FAR (0.125) exceeds the development FAR it was selected on (0.083); it is reported and **not** re-selected | `DETERMINISTIC_SIMULATION` | same, `operating_points` |
| C33 | **Three** independent locked passes agree pairwise on every measured quantity over 840 runs | measured | `phase4/REPRODUCE4.md`, `replay_check4.py` |
| C34 | Phase-4 mutation: **17 evaluated, 17 killed, 0 survived**, on a green unmutated baseline with a killed canary, every kill attributed to a distinct behavioural test node and none to a bare file | measured | `phase4/results/PHASE4_MUTATION_RESULTS.json` |

## Hypotheses

| | status | why |
|---|---|---|
| H1 | **consistent at `SOURCE_ANALYSIS`, not tested** | H1 also requires that no independent freshness path forces an equivalent warning. That clause is established from source structure only, which is not a test of it. |
| H2 (Phase 3) | **NOT SUPPORTED** | 28 conflicts; 24 in a physically inconsistent control and excluded; the remaining 4 are not separated from their matched control (p = 0.625). Rejection criteria (a) and (d). Unchanged. |
| H2 (Phase 3.2) | **SUPPORTED** | on its own disjoint locked partition, preregistered before the run: 40/40 vs 0/40 at the confirmatory point, p = 1.82 × 10⁻¹², RD = 1.0, 0 exclusions. **Not pooled with Phase 3.** |
| H3 | **NOT SUPPORTED**, and in Phase 3.1 **rejected in the harmful direction** | Phase 3: P0 made 0 incorrect actionable decisions and P2 was inert — the absence of a test. Phase 3.1, separate partition, no pooling: P2 fired in 40/40 eligible scenarios, produced 40 false refusals, prevented 0, and doubled action conflicts. |
| A1 (Phase 3.1) | **SUPPORTED** | the actionability precondition is reachable; P2 activated in 40/40 eligible scenarios |
| A2 (Phase 3.1) | **false-refusal direction** | 40 false refusals, 0 prevented incorrect actionable decisions |
| H4 | **SUPPORTED**, direction unfavourable to the mechanism on delay | a matched operating point exists at FAR = 0 for all three detectors and the curves are far from indistinguishable, so neither kill condition fires. CSIA is ~31× slower than both comparators there. **No claim that CUSUM is inferior is made**; on this fault it is not. |
| H5 | **not killed** | twelve paths classified; H5 predicts nothing, so classification is the whole test |
| H6 | **not killed** | both mechanisms reproduce, fresh-interpreter import check clean |

**H2 was rejected in Phase 3 and supported in Phase 3.2 on a separate
partition; H3 was rejected in the harmful direction.** H1 and H5 remain at
`SOURCE_ANALYSIS`; H6's test is about code, not about aircraft. **H4 has now
been tested at `DETERMINISTIC_SIMULATION` and is supported, with the direction
against the mechanism on delay.**

## Claims this phase does NOT support, listed so they cannot be borrowed

- **Prevalence.** Twelve hand-picked paths are not a sample, and every one of
  them classified `STRUCTURALLY_PRESENT` *because* they were picked as
  candidates.
- **Universality.** Forbidden by the preregistration at any number of audited
  paths.
- **Novelty.** C6 is a counterexample to it, in one of the audited projects'
  own words.
- **That an autopilot executed anything.** No autopilot path ran. No SITL ran.
  `RUNTIME_REPRODUCED` and `RUNTIME_NOT_REPRODUCED` appear nowhere in the
  results.
- **That CUSUM is inferior.** Phase 4 has now run at matched false-alarm
  operating points over the preregistered grid, and CUSUM was **thirty times
  faster** than CSIA at the same false-alarm rate on this fault. The
  preregistration forbade claiming CUSUM inferior; the measurement would not
  have supported it in any case.
- **That CSIA is a better detector.** It is not, on this fault, on this node,
  on delay. What it is measurably better at is tolerating a badly chosen
  threshold, which is a different property.
- **That any of this generalises to other faults.** Phase 4 tested one node,
  one fault family, and a large abrupt sustained step — the easy case for the
  memoryless comparators. No drift, incipient, intermittent or multi-node
  fault was tested.
- **That any detector has a zero false-alarm PROBABILITY.** Zero was
  *observed*, over 16 000 s of simulated flight; the 95 % upper bound is
  0.0881 per horizon for each of the three. A zero count is not a zero rate.
- **That threshold robustness compensates for CSIA's latency penalty.**
  Phase 4 measured both and converts between neither.
- **That the occlusion is harmless in general.** Phase 3 tested 3 of 8
  candidates, one airframe profile, one trajectory family, two fault families.
- **That the support-aware policy is safe or unsafe.** Phase 3.1 shows it
  withdrew a correct attribution in 40/40 activations; that is a capability
  cost, not a hazard, and no safety conclusion follows in either direction.
- **That freshness logic covers the occlusion.** P1 never fired in either
  phase; that is untested, not confirmed.
- **That H2 is supported by Phase 3 or Phase 3.1.** It is not. Phase 3
  rejected it on its own partition and Phase 3.1 did not preregister it.
  Phase 3.2 preregistered and supported it on a third, disjoint partition,
  and the three are never pooled.
- **That the Phase-3.2 result generalises to airframes that do report ESC
  telemetry.** It is precisely a statement about one that does not.
- **That abstention is a solved safety problem.** `AMBIGUOUS` is a report that
  a question cannot be answered. Reporting it is not the same as handling it,
  and the tradeoff curve phase 3 would produce does not exist yet.
- **That RAIM proves the mechanism.** RAIM may be cited as a design analogy for
  availability/integrity reporting. It is not evidence, and RAIM and CSIA are
  not claimed to solve the same problem.
- **Anything about hardware, RF, arming, flight, airworthiness or
  certification.** The E2M hardware campaign remains `AUTHORIZED_NOT_RUN` and
  this phase did not touch it.
- **An independent party's replication.** CSIA-Lite is independent of the code
  and not of the author, and `CSIA_LITE.md` says so before it reports anything.

## Corrections this phase made to itself

| what | where |
|---|---|
| Phase 6 was recorded `BLOCKED_BY_SOURCE_ACCESS` on a `find` that searched the repository and concluded about the environment. Both source trees were present. | `PHASE_STATUS.md`, `CROSSARCH_AUDIT.md` |
| The independent gate evaluator disagreed with the hand inventory on four terms and missed the `P[...]` family entirely. The parse defects were fixed **after** the disagreement was seen, which weakens the independence and is recorded as such. | `PHASE2_GATE_FINDINGS.md` |
| The first CSIA-Lite demonstration showed no occlusion, because the two airspeed hypotheses were also separated by a second feature. | `CSIA_LITE.md`, `csia_lite/demo.py` |
| A mutation run reported 24/24 killed. Every kill was a collection error caused by a module the sandbox never received, so the score was meaningless. A baseline check now refuses to report unless the unmutated selection passes. | `tools/mutation/run_e2m_mutations.py` |
| `decode()` accepted a frame with one bit flipped in the CRC field, because `int(x, 16)` is case-insensitive. Found by a property test that had been failing about one run in three. | `csia_e2m/protocol.py`, `tests/test_e2m_properties.py` |
| Phase 4 scored a pre-onset alarm as a detection with negative delay, and scored a latched detector that never stopped alarming as clean. Both were found on development data before the locked partition was opened; the second **changed the matched thresholds**. | FL-035, `phase4/PREREGISTRATION_PHASE4.md` §7 |
| The Phase-4 reproduction check was a byte-identity comparison of a document that deliberately carries a wall-clock timing field, so it could never pass. The field was kept and the check was fixed, not the other way round. | FL-036, `phase4/replay_check4.py` |

## What is still missing

Every phase the preregistration defines has now run. What is missing is
everything **above** `DETERMINISTIC_SIMULATION`: no SITL, no HIL, no bench
hardware, no flight, and no independent party's replication. The E2M hardware
campaign remains `AUTHORIZED_NOT_RUN`.

The consequence result rests on a model of the response
(`consequence_model.py`), and the detector result rests on one fault family on
one node. Neither limit is a detail; they are the reason no row above claims a
rung it did not reach.
