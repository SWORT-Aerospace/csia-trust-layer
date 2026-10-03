# Scoring rubric for the engineering task test (EXPERIMENTER ONLY)

**2026-10-02. Frozen before any participant. Never shown to a participant.**
The truth per log is in the bundle's `experimenter/GROUND_TRUTH.json`,
written by `build_pilot_bundle.py`. This rubric refers to cases by name,
never by P-number.

## 1. Scoring each answer sheet

**Two raters score every sheet independently, blind to the condition
(manual or analyzer-assisted).** The condition box is masked before rating.
A third rater resolves disagreements. Each question is scored 0 or 1, and
some are flagged.

| question | 1 point when | flag |
|---|---|---|
| Q1 what happened | the category matches the truth (nothing / fault / cannot tell / outside scope). "Cannot tell" scores 1 only where the truth is not separable from the log (below) | **FALSE_FAULT** if a fault is named on a nominal or out-of-scope log |
| Q2 when | within 5 s of the truth's onset; "not applicable" on nominal and out-of-scope logs | — |
| Q3 which component | the named component matches the truth at the stated precision | **WRONG_ATTRIBUTION** if a different component is named as the cause (the primary safety measure) |
| Q4 alternatives | every alternative the truth leaves open is listed, or the answer correctly says none remain | **OVERCLAIM** if a single cause is given where the truth is not separable |
| Q5 trust | at least one signal correctly relied on; any signal rejected is rejected for a correct reason | **TRUSTED_INVALID** if a signal the truth makes invalid is relied on (e.g. a corrupted RPM report) |
| Q6 shared source | a real shared source is named, or "none found" where none matters | — |
| Q7 resolving measurement | names a measurement that would separate the remaining causes (ESC current, battery current, an independent RPM or thrust witness, command-delivery evidence) | — |
| Q8 certainty | "establishes" only where the log establishes it; "supports" or "guessing" otherwise | **UNSUPPORTED_CERTAINTY** if "establishes" is ticked for a non-separable or wrong answer |
| Q9 reproducibility | scored by rater 2: could they reach the same answer from the notes | — |

## 2. What "not separable from the log" means, per case

**Fixed now, from the truth and the log contents.** This is not from the
analyzer's output.

| case | separable from the log? | open alternatives a fully correct answer keeps |
|---|---|---|
| motor loss in hover or hold (motors 0, 1, 2) | the motor and the physical loss: **yes**. The cause within the propulsion path: **no** (no ESC current, no battery current) | mechanical, drive without current, command not delivered, power path |
| matched B (RPM corruption on motor 0) | **yes**: the vehicle's response is nominal, so a motor failure is not supported | — |
| RPM ×10 on motor 2 | **yes**, as for matched B | — |
| ESC telemetry offline, motor 1 | the telemetry loss: yes. The motor's health from ESC data: **no**. The vehicle's response is nominal | — |
| motor loss mid-maneuver (motor 2) | the RPM deficit: yes. The physical loss, confirmed: **no** while the vehicle maneuvers | physical loss vs telemetry |
| GPS loss | yes | — |
| magnetometer loss | yes | — |
| nominal maneuvering | yes | — |
| real logger dropouts | no fault known; parts of the evidence missing | — |
| real boat | **outside scope** for a multirotor analysis | — |

## 3. Primary and secondary measures

| measure | definition | primary |
|---|---|---|
| **wrong attribution** | count of WRONG_ATTRIBUTION flags | **yes: the safety measure** |
| correctness | Q1 + Q3 + Q4 points | yes |
| unsupported certainty | count of OVERCLAIM, TRUSTED_INVALID, UNSUPPORTED_CERTAINTY and FALSE_FAULT flags | yes |
| two-minute comprehension | feedback form section 2, on the first analyzer-assisted log | secondary |
| dependence recognised | Q6 points | secondary |
| resolving measurement | Q7 points | secondary |
| time to answer | minutes per sheet | secondary; **never a success criterion alone** |
| reproducibility | Q9 points | secondary |

## 4. Success criteria (fixed now)

**The analyzer is judged useful only if all three hold:**
1. **wrong attribution:** analyzer-assisted is not higher than manual, in
   total and on every case;
2. **correctness:** analyzer-assisted is higher by at least one point per
   participant on average;
3. **unsupported certainty:** analyzer-assisted is lower by at least one
   flag per participant on average.

**Any wrong attribution that a participant copied from the analyzer's page
is reported individually**, with the page text, whatever the totals.

**Failure is a result:** if the criteria fail, the report says so and
names the sections that misled or did not help.

## 5. What is not scored

- whether the participant liked the tool (that is the feedback form);
- speed alone;
- agreement with the analyzer. The truth is the reference, not the tool.
