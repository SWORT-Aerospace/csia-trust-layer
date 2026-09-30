# The seven weakened UNIQUE scenarios

**2026-09-30. Parts 8 and 46 of the shadow-validation brief.** Source:
`UNIQUE_REVIEW.json`, written by `unique_review.py`.

**What was examined.** Each case was judged from the decision traces, not
from the ground-truth label: which gate withheld the UNIQUE; what the
same-tick localization kept, and why; and what v2.0's UNIQUE had rested on.

**The seven scenarios** are those whose final tick changed from a correct
UNIQUE to AMBIGUOUS (Phase C governance report, §1). TS_STALLED is reviewed as
well, because its UNIQUE is withheld during onset, although its final tick is
unchanged.

## 1. Two facts that hold for all of them

**Every withhold is F2, never C1.** On every one of the 278 weakened ticks
(plus TS_STALLED's 7), the reason is SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN.
C1 passes in each case: the candidate's declared alternatives are all
affirmatively NOMINAL.
- **What is disputed is therefore never the other components.** It is a
  hypothesis about the candidate itself that its own localization cannot
  rule out.

**v2.0 was not right "for the right reason" in any of them (category A).**
- **The discriminators v2.0's UNIQUE rested on were mostly irrelevant.** 57 of
  them in the actuator scenarios, of which 48 are about components that are
  not declared alternatives of the motor (the GNSS link, the telemetry radio,
  navigation timing). In the estimator scenarios, 40 of 47.
- **Even where relevant evidence existed, v2.0 never tested the retained
  hypothesis.** The relevant evidence excluded the other components (the ESC
  CAN bus and the battery for the motor).
- **So each is category B:** correctly certain for a reason that does not
  exclude the alternative that remains.

## 2. Each case

**Abstention labels (Part 46):**
- **NECESSARY:** the evidence genuinely cannot distinguish.
- **TEMPORARY:** the discriminating evidence exists but has not arrived yet.
- **ARTIFICIAL:** the declared model (profile or signature) cannot use
  evidence that is present.
- **REGRESSION:** 2.1 ignores relevant evidence that v2.0 used. **None of the
  eight is a REGRESSION.**

| scenario | weakened ticks | what the localization keeps, and why | v2.0 category | 2.1 category | abstention |
|---|---|---|---|---|---|
| MS_B4_MECHANICAL | 42 (18-59) | SENSOR/response_sensor, **confirmed** (STALL_SIGNATURE True); its refuter PHYSICAL_RESPONSE_NOMINAL_FALSE is unmeasurable, because the multirotor has no independent shaft observation | **B**. The same evidence gives the same UNIQUE in MS_B5, where it is wrong (§3) | correct | **NECESSARY** |
| STALLED_ACTUATOR | 33 (27-59) | as MS_B4 | B | correct | **NECESSARY** |
| ACTUATOR_NO_RESPONSE | 34 (26-59) | SENSOR/response_sensor, **unresolved**: not confirmed (STALL_SIGNATURE False), and its only refuter is unmeasurable | B: the response-sensor hypothesis was never tested | **C via D**: physically, an RPM sensor that lies about a motor drawing no current is refuted by the absent current under a single fault, but COMMAND_NO_RESPONSE's signature does not list CURRENT_PRESENT_FALSE as a refuter. Also **E**: the scenario's own expectation is "ESC, power path and wiring named as inseparable candidates", so it asks for ambiguity, just not over this alternative | **ARTIFICIAL** (signature) |
| MS_B3_DRIVE_NO_CURRENT | 42 (18-59) | as ACTUATOR_NO_RESPONSE | B | C via D | **ARTIFICIAL** (signature) |
| CLOCK_DRIFT | 39 (21-59) | COMPUTE/processing_delay and SENSOR/source_slow, both unresolved; their refuters (segment latencies) are unmeasurable because the clock is inconsistent | B: the SENSOR alternative was excluded only through the IMU's record, which says nothing about the GPS interval | **C via D**: the estimator's own deadline record (NOMINAL) and the v1.1 GPS freshness record bear on the two survivors. The signature reads neither, and the profile does not declare source.gps for nav_solution | **ARTIFICIAL** (signature and profile) |
| PROCESS_STALL | 39 (21-59) | COMMUNICATION/input_starvation for OUTPUT_MISSING, unresolved: no link is declared for the estimator (G-2) | B: v2.0 refuted starvation using the ESC CAN bus and the telemetry radio | **D** | **ARTIFICIAL** (G-2; see `G2_ESTIMATOR_INPUT_AUDIT.md`) |
| MS_D2_ESTIMATOR_STALE | 42 (18-59) | as PROCESS_STALL | B | D | **ARTIFICIAL** (G-2) |
| TS_STALLED (not final) | 7 (27-33) | SENSOR/response_sensor, **SUPPORTED**: during the stall's onset the bench torque channel still reads nominal (PHYSICAL_RESPONSE_NOMINAL True), so the localization supports the wrong hypothesis | B: the UNIQUE is right, but contradicted by its own tick's localization | correct: the two stages disagree | **TEMPORARY**: from tick 34 the torque drops and UNIQUE returns |

**None of the seven is restored by the accepted successor profile r1.**
- **Why:** none of them is a G-1 case.
- **Where they are restored:** PROCESS_STALL and MS_D2 come back under R5,
  R5a and every superset. Those are the configurations
  `G2_ESTIMATOR_INPUT_AUDIT.md` shows to restore v2.0's wrong reason.
- **In numbers:** 39 and 42 ticks restored under successor r1 + R5 and under
  successor r1 + R5a; 0 under r1.

## 3. MS_B4 and MS_B5: why the abstention is necessary

**The multirotor matched pair is observationally identical.**
- **Their evidence matches on every tick.** MS_B4_MECHANICAL (true cause:
  mechanical) and MS_B5_RESPONSE_SENSOR (true cause: the response sensor)
  produce identical evidence on all 60 ticks, down to every record's domain,
  component, relation, observation state and reason codes.
- **So any rule gives both the same answer.** v2.0 gives both UNIQUE
  ACTUATION/motor_0, and is wrong on MS_B5 on 42 ticks.
- **2.1 is right on both.** It withholds both, with the reason, and its
  localization keeps both hypotheses.
- **The scenario authors said the same.** MS_B4's written expectation is
  AMBIGUOUS with both supported, and MS_B5's is "the SAME ambiguous result as
  B4".

**The bench pair differs.** MS_TS_B4 and MS_TS_B5 are identical until tick
17. From tick 18 the torque channel separates them
(`actuation.physical_response` VIOLATED in B4, NOMINAL in B5).
- **v2.0 ignores that evidence.** It gives the same actuator UNIQUE in both on
  all 60 ticks.
- **2.1 uses it.** Its localization supports SENSOR/response_sensor in
  MS_TS_B5, which is what makes the Phase C bench set qualify, and F2
  withholds the wrong actuator UNIQUE.

## 4. What this settles

- **All seven are explained, and so is TS_STALLED.**
  - Two are NECESSARY abstentions where v2.0's certainty was luck.
  - Five are ARTIFICIAL:
    - two are the G-2 profile gap (PROCESS_STALL, MS_D2);
    - two are a missing refuter in the signature matrix
      (ACTUATOR_NO_RESPONSE, MS_B3);
    - one comes from both the signature and the profile (CLOCK_DRIFT).
  - TS_STALLED is TEMPORARY.
- **None is a REGRESSION.** In none of them does 2.1 ignore relevant evidence
  that v2.0 used.
- **Four signature-level repairs would lift the ARTIFICIAL cases.** They are
  owner decisions on the signature matrix, not profile data:
  - CURRENT_PRESENT_FALSE as a refuter of the response-sensor hypothesis
    under COMMAND_NO_RESPONSE;
  - the producer's own deadline record as a refuter of processing_delay;
  - GPS source freshness as a refuter of source_slow;
  - the estimator's pacing-input health as the refuter of input_starvation.

  None is made here. Each would need the same shadow treatment as the profile
  candidates, including a counterfactual that looks for a wrong answer it
  might restore.
