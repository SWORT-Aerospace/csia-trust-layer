# Phase C governance report (Phase G)

**2026-09-30.** How Semantic Core 2.1 replays the recorded v2 Phase C
results.

**Nothing recorded was edited.** Every figure is measured by
`semantic_core_2_1_differential.py`, sections E and G. The comparison uses
the frozen Phase C gate function (`engineering/v2/run_phase_c.py`
`decision_gate`, imported unchanged).

**The baseline is sound.** Before comparing, each recorded artifact was
regenerated from frozen v2 at its own tick count. All four reproduce
exactly:
- `V2_SCENARIO_RESULTS.json`;
- `LOCALIZATION_RESULTS.csv`;
- `EVIDENCE_SUBSET_RESULTS.csv`;
- `V2_PHASEC_GATE.json`.

## 1. The numbers the brief asks for

| | 44 scenarios x 60 ticks (the audit's corpus) | the recorded Phase C artifacts |
|---|---|---|
| total changed ticks | 945 of 2,640 | `V2_SCENARIO_RESULTS.json` (19 scenarios x 200 ticks): 626 attribution ticks, in 5 scenarios |
| changed localization ticks | 664 (audit expectation: 664) | `LOCALIZATION_RESULTS.csv`: 4 of 27 rows; `EVIDENCE_SUBSET_RESULTS.csv`: 4 of 27 rows |
| changed attribution ticks | 362: 281 by F2, 81 by C3 and F2 together (audit expectation for F2: 281) | 626, as above |
| changed final scenario outcomes | 23 of 44 scenarios | 4 of 19 recorded finals: ACTUATOR_NO_RESPONSE, CLOCK_DRIFT, STALLED_ACTUATOR and PROCESS_STALL go from UNIQUE to AMBIGUOUS |
| changed gate-qualifying outcomes | — | **0**. Verdict `CROSS_DOMAIN_ASSURANCE_FUNCTIONAL`, qualifying sets A_STALE_OUTPUT and B_ACTUATOR_RESPONSE_BENCH, and every qualifying answer are identical |
| wrong UNIQUE corrected | 2 scenarios, 84 ticks: MS_B5_RESPONSE_SENSOR and MS_TS_B5_RESPONSE_SENSOR | 0. Neither scenario's attribution is recorded in any Phase C artifact |
| right UNIQUE weakened | 7 scenarios at the final tick, 278 ticks | 4 finals (the row above), plus 23 TS_STALLED ticks whose final stays UNIQUE |
| localization weakened by a profile gap | 243 units in 5 scenarios | the MS_D1 row |
| symptoms no longer raised, raised only by unrelated components (a real fix) | 189 units: MS_B1 and NETWORK_LATENCY | — |
| symptoms no longer raised, decided by a missing profile declaration (G-1) | 481 units in 12 scenarios | the MS_D2, MS_D3 and MS_D4 rows |
| profile gaps exposed | G-1, G-2 and G-3 (§4) | G-1 behind the D-set rows |

**Two consistency checks on these counts:**
- **Recorded attribution ticks.** 626 = 112 + 129 + 129 + 110 + 23. These are
  ACTUATOR_NO_RESPONSE, CLOCK_DRIFT, PROCESS_STALL, STALLED_ACTUATOR and
  TS_STALLED at 200 ticks. Each goes from UNIQUE to AMBIGUOUS with the same
  candidate.
- **The D set.** It was non-qualifying ("two members reduced to the SAME
  hypothesis"). It stays non-qualifying, now because "not every member
  reduced to a supported hypothesis".

## 2. Erratum to the semantic correctness audit

The audit's `IMPLEMENTATION_GATE.md` (section 3 and row G3) said:

> F2 turns 7 recorded UNIQUE final verdicts into AMBIGUOUS. They are in
> `V2_SCENARIO_RESULTS.json` and the review-report tables, and include two
> where the recorded UNIQUE names the wrong cause.

**The measurement does not support where that sentence locates them.**

- The 7 are final ticks of the audit's own 60-tick replay of all 44
  scenarios:
  - ACTUATOR_NO_RESPONSE, CLOCK_DRIFT and STALLED_ACTUATOR;
  - MS_B3, MS_B4, MS_B5 and MS_TS_B5.

  All 7 change under F2 here too.
- `V2_SCENARIO_RESULTS.json` covers 19 non-matched scenarios. It contains
  only the first three of those seven.
- MS_B3, MS_B4, MS_B5 and MS_TS_B5 are matched scenarios. **No Phase C
  artifact records their attribution** (`LOCALIZATION_RESULTS.csv` records
  only their localization).
- **So both wrong-cause UNIQUE verdicts exist only in replay, never in a
  record.**
- Of the recorded UNIQUE finals, the ones that change are 3 by F2 plus
  PROCESS_STALL by C3 and F2 together.

The audit file is a previous semantic audit result and is not edited. This
report governs where the two disagree, and the error is recorded as
proposed ledger entry FL-060 (`PROPOSED_LEDGER_ENTRIES.md`).

**What it changes for governance: nothing in kind.** Every recorded change
is UNIQUE to AMBIGUOUS, keeping the same candidate, by a rule the owner
approved. The approval named F2 and C3 and accepted disagreement with
recorded UNIQUE verdicts (G3). What it corrects is the *number* of recorded
verdicts that differ, and *where* the wrong-cause cases live.

## 3. Is each change logically justified?

This section avoids one argument: that 2.1 is better because it is more
conservative. For each class of change the question is what the evidence and
the declared model actually support.

| class | units | justified? | why |
|---|---|---|---|
| F2, MS_B5 and MS_TS_B5 | 84 | **yes; corrects a wrong answer** | the true cause is the response sensor. The same tick's localizations on the motor retain SENSOR/response_sensor. On the bench it is SUPPORTED, because the torque channel exists. 2.0.0 named the actuator UNIQUE regardless, excluding SENSOR by NOMINAL navigation records that say nothing about an RPM channel |
| F2, MS_B4 and STALLED_ACTUATOR | final-tick subset of 197 | **yes** | on the multirotor nothing independent observes the shaft. The localization's own model therefore cannot exclude the response sensor. MS_B4's written expectation is AMBIGUOUS with both supported, and MS_B5's is "the SAME ambiguous result as B4". The 2.0.0 UNIQUE contradicted the scenarios' own stated expectations |
| F2, ACTUATOR_NO_RESPONSE and MS_B3 | part of 197 | **yes, by the declared model** | COMMAND_NO_RESPONSE keeps SENSOR/response_sensor unresolved, because only an independent physical channel can refute it, and the multirotor has none. ACTUATOR_NO_RESPONSE's written expectation is "ESC, power path and wiring named as inseparable candidates", which AMBIGUOUS matches and UNIQUE did not. Whether the response-sensor hypothesis should apply to a no-current symptom at all is a signature-matrix question, and is not changed here |
| F2, CLOCK_DRIFT | part of 197 | **yes, but it weakens a right answer** | the candidate TIMING/nav_solution is the right domain. OUTPUT_STALE on nav_solution keeps COMPUTE/processing_delay and SENSOR/source_slow unresolved: with an inconsistent timebase, the stage latencies that would refute them are not measurable. 2.1 declines to call it unique on evidence that does not exclude the others |
| F2, TS_STALLED (23 ticks, final unchanged) | part of 197 | **yes** | during the ticks before the torque channel settles, the localization still retains the response sensor. The final tick, with torque evidence, stays UNIQUE |
| C3+F2, PROCESS_STALL and MS_D2 | 81 | **justified by the rule; caused by a profile gap** | the candidate COMPUTE/state_estimator is right. OUTPUT_MISSING on the estimator keeps COMMUNICATION/input_starvation open because the profile declares no input link for it (G-2). 2.0.0 refuted starvation with FUNCTION_LINKS_NOMINAL over *every* link in the tick, including links that do not feed the estimator. The 2.0.0 answer was right, but not for a reason the model declares |
| C3, POSITION_UNAVAILABLE raised by unrelated components, no longer raised | 189 | **yes; corrects a false symptom** | MS_B1 (the ESC CAN link, on all three navigation functions) and NETWORK_LATENCY (the telemetry downlink). Neither component serves any navigation or position function, and the frozen function graph calls each function ELIGIBLE. This is SC-05 as the audit found it |
| C3, POSITION_UNAVAILABLE on COARSE_NAVIGATION, no longer raised | 481 | **consistent, but decided by a missing declaration, not by evidence** | 12 scenarios, including the D-set rows of MS_D2, MS_D3 and MS_D4. The responsible components (nav_solution, state_estimator, gnss_serial) are declared to serve the SIBLING navigation functions. Nothing is declared to serve COARSE_NAVIGATION (G-1). The frozen function graph calls COARSE_NAVIGATION ELIGIBLE in every one of these ticks, so 2.1 agrees with it. But if the owner declares that COARSE_NAVIGATION depends on the estimator or the navigation channel, these symptoms return. **They are not counted as corrections** |
| C3, weakened by a profile gap | 243 | **justified by the rule; a real loss** | OUTPUT_MISSING (123 units: MS_A4, MS_D2, PROCESS_STALL) and COARSE_NAVIGATION in MS_D1 and SHARED_RAIL (120 units). The frozen SUPPORTED answers were right; they rested on evidence the profile never connects to the subject. 2.1 reports the gap (NO_DECLARED_LINK, NO_DECLARED_PROCESS, NO_DECLARED_TIMING_CHANNEL) instead of borrowing evidence from unrelated components |

**The balance, stated plainly:**
- **Corrections: 2** wrong-cause UNIQUE verdicts withheld (84 ticks), and
  **189** units of a false navigation symptom raised by unrelated components
  no longer raised.
- **Decided by profile gaps, not by evidence:** **481** units no longer
  raised on COARSE_NAVIGATION, and **243** units weakened: 724 in all.
- **Right answers weakened:** 7 attribution scenarios (278 ticks) where the
  declared model does not exclude another domain. Two of those (PROCESS_STALL
  and MS_D2) are again due to gap G-2.
- **Counting:** 2.1 corrects fewer results than it changes. Most of the
  localization change is the profile's missing declarations showing through.
  That is the honest cost of scoping predicates to what the model declares,
  and it is why G-1 and G-2 are the first owner decision after shadow mode.

**It creates no certainty:** 0 units became more certain, no UNIQUE and no
SUPPORTED was created, and no candidate was added, removed or renamed.

## 4. Profile and configuration gaps exposed

| gap | what is undeclared | effect under 2.1 | fix (an owner decision; profiles are frozen with v2) |
|---|---|---|---|
| G-1 | nothing declares it serves COARSE_NAVIGATION: no timing channel, process or link names it in `affected_functions` | scoped predicates on it are None; POSITION_UNAVAILABLE is raised on it only by v1.1's own eligibility record | declare its serving components in `csia/v2/profiles/aircraft.py` |
| G-2 | `state_estimator` declares no COMMUNICATION input link | OUTPUT_MISSING cannot refute input_starvation; this is where PROCESS_STALL's and MS_D2's UNIQUE is lost | declare the estimator's input link |
| G-3 | `gnss_serial` records do not name the navigation functions, although `nav_solution` depends on it | the P16 residual: 168 localizations on functions the graph calls ELIGIBLE | align `affected_functions` with the dependency graph |

`csia_semantic_core.scope_report()` lists these gaps from one tick of
records.

## 5. Governance conclusion

- The Phase C headline gate is intact: same verdict, same qualifying sets,
  same answers.
- Every change is expected, attributed to an approved rule (C3 913, F2 281,
  C3+F2 81 units) and receipted.
- The recorded artifacts that 2.1 disagrees with are enumerated above. The
  count is smaller than the audit's sentence implied, and the kind is the
  approved one.

**There is no Phase C governance block.** The owner decision that remains
open is profile data G-1 to G-3. It is not a condition for shadow mode.
