# Wrong-UNIQUE corrections: stability and regression tests

**2026-09-30. Part 9 of the shadow-validation brief.** Sources:
`UNIQUE_REVIEW.json` (`unique_review.py`), `SHADOW_RESULTS.json`, and
`tests/test_semantic_core_2_1_shadow.py`.

## 1. The corrections

2.1 corrects two wrong-cause UNIQUE verdicts, both by F2.

| scenario | injected cause | frozen v2.0 | 2.1 |
|---|---|---|---|
| MS_B5_RESPONSE_SENSOR (multirotor) | the RPM response sensor | UNIQUE ACTUATION/motor_0 on 42 of 60 ticks | never UNIQUE. The localization keeps SENSOR/response_sensor; the reason is SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN |
| MS_TS_B5_RESPONSE_SENSOR (test stand) | the response sensor | UNIQUE ACTUATION/dyno_motor on 42 of 60 ticks | never UNIQUE. The localization SUPPORTS SENSOR/response_sensor, because the bench torque channel refutes the mechanical hypothesis |

No other wrong UNIQUE differs between v2.0 and 2.1 in dataset A (probe W1 in
`WORSE_ANSWER_SEARCH.json`).

## 2. Stability under every profile variant

These are wrong-UNIQUE ticks (UNIQUE naming a domain other than SENSOR) over
all 60 ticks of each scenario.

| profile | MS_B5 | MS_TS_B5 |
|---|---|---|
| frozen v2.0 | 42 | 42 |
| 2.1, no successor | 0 | 0 |
| **2.1, successor r1 (accepted)** | **0** | **0** |
| 2.1, r1 + R5 (rejected) | 0 | 0 |
| 2.1, r1 + R5a (deferred) | 0 | 0 |
| 2.1, R1 to R5 | 0 | 0 |
| 2.1, R1 to R5 + R-BAD | 0 | 0 |

**The corrections cannot be undone by profile data.**
- **What they rest on:** a localization on the motor's own subject that keeps
  a SENSOR hypothesis, plus F2.
- **What the profile can change:** only scope (C3) and alternatives (C1).
  Neither enters COMMAND_NO_RESPONSE or HIGH_CURRENT_LOW_RPM on a motor.
- **So** no G-1 or G-2 declaration, accepted or rejected, can reach them. The
  test below also runs each candidate on its own (R1, R2, R3, R4, R5, R5a,
  R5b, R6 and R-BAD).

**MS_B5 and its matched twin MS_B4 (true cause: mechanical) carry identical
evidence** on all 60 ticks. A reasoner that restored UNIQUE on either would
restore it on both, and be wrong on MS_B5. That is the strongest available
argument that the correction is not a matter of taste
(`WEAKENED_UNIQUE_REVIEW.md` §3).

## 3. Equivalent cases searched for

- **Dataset A, every tick.**
  - **2.1:** 3 wrong UNIQUE ticks, TS_CPU_OVERLOAD 26-28.
  - **v2.0:** gives the same 3.
  - **Why they are wrong:** the evidence shows the effect before the cause. At
    onset the encoder timing segment crosses its limit while the CPU load and
    the controller runtime are still inside theirs, so every declared
    alternative is affirmatively NOMINAL.
  - **What that makes them:** a shared limitation (loophole L16), not a
    correction and not a regression.
- **Under the adversarial profile mutations** (`ADVERSARIAL_PROFILE_RESULTS.json`),
  2.1 produced 0 overconfident results in 10 mutations.
- **Frozen v2.0 on mutation M4b** (the GNSS link's records mislabelled as
  SENSOR) gained 81 overconfident unit-ticks. 2.1 did not.

## 4. The permanent regression tests

All are in `tests/test_semantic_core_2_1_shadow.py`.

| test | pins |
|---|---|
| `test_the_wrong_cause_unique_is_never_restored` | 24 cases: {MS_B5, MS_TS_B5} x {none, successor r1, R1, R2, R3, R4, R5, R5a, R5b, R6, R-BAD, all together}. Frozen v2.0 is wrong on 42 ticks, and 2.1 on 0 ticks in every variant |
| `test_ms_b4_and_ms_b5_carry_identical_evidence_so_no_unique_can_be_right` | the twin evidence identity, and 2.1 not UNIQUE on either |
| `test_g2_the_rejected_repairs_restore_the_wrong_process_stall` | the related G-2 case: R5, R5a and R5b restore a wrong SUPPORTED in the IMU pacing-loss counterfactual. This is the reason they stay out of the successor profile |
| `test_g2_without_a_link_input_2_1_keeps_starvation_open_when_the_imu_dies` | 2.1, with and without successor r1, keeps the right ambiguity there |

**What any future successor profile or semantic revision must do.** The
tests exercise every candidate, not only the accepted one. A change that
restored the actuator UNIQUE in MS_B5 would therefore fail here, whichever
way it arrived.
