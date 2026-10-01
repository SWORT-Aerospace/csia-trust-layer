# Historical replay and difference receipts (Phases 28 and 29)

**2026-10-01. NON-CONFIRMATORY.**

**Harness:** `replay_2_2.py`. **Results:** `REPLAY_2_2_RESULTS.json`.
**Receipts:** `DIFFERENCE_RECEIPTS.json`.

**The rule.** 2.2 may change a 2.1.1 decision only by correctly rejecting
evidence. Every changed decision gets a receipt.

**The comparator** at every slot is 2.1.1 itself (`Corrections.revised()`),
on the same records 2.2 started from:
- r2 for the aircraft;
- the frozen profile for the test stand and pump skid;
- the XSYS-001 specification for XSYS.

## 1. Results

| corpus | slots | rejected by 2.2 | decisions changed | receipts |
|---|---|---|---|---|
| the 44 frozen v2 scenarios (30 aircraft, 8 test stand, 6 pump skid; every gate ACCEPTED) | 2,640 ticks | 0 | **0** | — |
| XSYS-001: 121 trials × 8 checkpoint-variants × 4 motors | 3,872 | 484 (all V4_INVALID_WINDOW at C3, all REGIME_INVALID) | **110** (all V4_INVALID_WINDOW at C3) | 110, all EXPECTED |
| E1 | 60 ticks | 9 (CONFIGURATION_MISMATCH, decided by R-3) | **0** against the revision's REVISED_2_1_1_R2 | — |

**Why 484 rejections but 110 changes.** 484 = 121 trials × 4 motors: every
V4 slot's W_DYN output is refused. Only motor_0 of an A or B trial has a
symptom to localize (110 slots). Elsewhere the refused record changes
nothing.

## 2. The XSYS-001 confirmatory result is unchanged

The primary result (C3 / V3_TEMPORAL) was recomputed from 2.2's decisions
with stage 2's own scoring functions:

| quantity | from 2.1.1 | from 2.2 | sealed record |
|---|---|---|---|
| matched pairs | 55 | 55 | 55 |
| resolved pairs | 55 | 55 | 55 |
| one-sided 95 % lower bound | 0.7616 | 0.7616 | 0.7616 |
| wrong (A and B) | 0 | 0 | 0 |

Outcomes changed outside C3/V4_INVALID_WINDOW: **0**. No XSYS-001 file was
written.

## 3. The receipts

All 110 have the same form. One, verbatim in substance
(`XS1A1-C07-A-E095|C3/V4_INVALID_WINDOW|motor_0`):

| field | value |
|---|---|
| OLD ADMITTED EVIDENCE | ACTUATION/motor_0 `xsys.rpm_response` = VIOLATED (window T3); NAVIGATION/motor_0 `xsys.dynamics_T1` = NOMINAL (window "T3 (INVALID: outside its window)") |
| NEW REJECTED EVIDENCE | `xsys:w_dyn|DYN_RESPONSE|NAVIGATION/motor_0:xsys.dynamics_T1|15.000000` |
| REJECTION REASON | REGIME_INVALID: CONTENT_OUTSIDE_VALIDATED_WINDOW: xsys.onset+[0.0, 0.2] s |
| OLD VERDICT | SUPPORTED SENSOR/response_sensor (ACTUATION/mechanical rejected by DYN_T1_NOMINAL) |
| NEW VERDICT | AMBIGUOUS: ACTUATION/mechanical, SENSOR/response_sensor |
| truth | PHYSICAL_ACTUATOR_DEGRADATION |
| EXPECTED? | YES |
| WHY | W_DYN was validated in T1 only (0-200 ms after onset). V4 feeds the same statistic computed over T3 (10-15 s), which the frozen harness itself labels "INVALID: outside its window". The contract states the validated window, so the output is REGIME_INVALID and reaches 2.1.1 as UNAVAILABLE. The verdict is then what the remaining valid evidence supports |

**Outcome transitions** (stage 2's grader, against truth):

| transition | count | trials |
|---|---|---|
| WRONG → AMBIGUOUS_CORRECT | 55 | every A trial: the invalid-window dynamics looked nominal and refuted the true cause |
| UNIQUE_CORRECT → AMBIGUOUS_CORRECT | 55 | every B trial: right, but only through evidence outside its validated window |

**Reading.** V4_INVALID_WINDOW was XSYS-001's own negative control: it
showed that a witness used outside its window gives wrong answers. Under 2.2
that evidence never reaches the reasoner:
- the 55 wrong answers become AMBIGUOUS;
- the 55 answers that were right by chance become AMBIGUOUS too.

Both are what a reasoner without that evidence must say.

## 4. What was not replayed

- **The frozen v2.0 decisions themselves.** The comparator is 2.1.1, the
  approved baseline. 2.1.1 against v2.0 is the revision's own record
  (273 fixes, 197 withholds, 0 regressions).
- **XSYS-001 flight logs other than the E055 pair.** The replay uses the
  sealed features, which cover every trial.
