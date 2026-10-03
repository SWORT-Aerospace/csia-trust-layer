# External pilot package and engineering task test (PRIME E1-E2)

**2026-10-03. PREPARED, NOT RUN. No user study was run with the people who
built CSIA.** OFFBOARD, ZERO CONTROL authority, NO FORGE.

**Files:**
- **builder:** `build_pilot_bundle.py`;
- **build record (no truth):** `PILOT_BUNDLE.json`;
- **participant documents:** `pilot_package/`;
- **experimenter documents:** `pilot_package_experimenter/`.

## 1. E1: the package, item by item

| brief item | where | measured |
|---|---|---|
| installer | `install/csia_trust_layer-0.8.0-py3-none-any.whl` in the bundle (`pip wheel`) | the wheel carries the support matrix and the `csia-assure` entry point, and **no** `research/`, `tests/` or truth file. A fresh-environment install was measured by PRIME-A |
| sample ULogs | `logs/P01.ulg` … `logs/P12.ulg`: 10 SITL, 2 REAL | each blinded (section 3); SHA-256 of every member in `PILOT_BUNDLE.json` |
| one-command analyzer | `csia-assure P01.ulg --out P01_report` | exit 0 on all 12; **under 5 s per log** on the build machine (0.6-3.2 s in the recorded build) |
| quick start | `QUICKSTART.md` | — |
| report explanation | `REPORT_GUIDE.md` | — |
| supported / unsupported matrix | `SUPPORT_MATRIX.json` (the shipped file) | — |
| ground truth stored separately | `experimenter/GROUND_TRUTH.json`, written **only** into the experimenter folder, never into the zip; the repository record holds no truth | — |
| diagnostic questions | `DIAGNOSTIC_QUESTIONS.md` | — |
| feedback form | `FEEDBACK_FORM.md` | — |
| data notice | `DATA_NOTICE.txt`: SITL vs REAL, the licences (pyulog BSD-3, PX4 docs CC-BY-4.0), not for redistribution | — |

**Built outside git** (`/home/user/prime_raw/pilot_bundle/`). The zip is
about 100 MB. **The raw logs are not committed.** Distributing the bundle is
an owner decision (section 6).

## 2. The twelve cases (by name; the P-numbers are in the experimenter key)

| case | source | data | why it is in the set |
|---|---|---|---|
| nominal maneuvering | RB-001 CAL2 | SITL | false-alarm control during maneuvers |
| motor loss, hover | 2.3 V1 (motor_1) | SITL | motor degradation |
| **matched pair A:** motor loss, hover | 2.3 V4 (motor_0) | SITL | physical loss with a 0.40 RPM-telemetry deficit |
| **matched pair B:** RPM corruption, healthy motor | RB-001 CAL1, motor_0's RPM × √0.6 from 70 s (the demo's construction, written into the ULog) | SITL + offline corruption | the same local symptom, the opposite cause |
| RPM × 10 report, healthy motor | 2.3 V10 | SITL | telemetry corruption (excess) |
| ESC telemetry offline, healthy motor | 2.3 V9 | SITL | sensor loss |
| GPS loss | 2.3 V7 | SITL | navigation loss, failsafe |
| magnetometer loss | 2.2 pilot S1 | SITL | configuration change (EKF2 aiding) |
| motor loss in a hold after maneuvers | 2.3 V12 | SITL | ambiguous propulsion event |
| motor loss mid-maneuver | 2.3 V13 | SITL | maneuvering: a loss that cannot be confirmed |
| real logger dropouts | pyulog `sample.ulg` (AUAV X2.1) | REAL | log dropouts, missing propulsion evidence |
| real boat | PX4 docs sample log (FMUv5) | REAL | unsupported vehicle |

**Participants are told only SITL or REAL per log.** Matched pair B is
listed as SITL.

## 3. Blinding, as measured

**The SITL logs gave their answers away.** Found while building:
- **4 motor-loss logs** record the in-flight change of `SIH_MOT_EFFn`;
- **4 logs** carry PX4's `[failure_injection_manager] Injected: …` message.

**Either is visible in Flight Review, and the message also appears in
CSIA's own alert list.** It would have answered Q1-Q3 in both conditions.
An unblinded test would have measured reading, not diagnosis.

**The builder removes exactly those two record kinds** (pyulog's writer;
nothing else edited).

**It then checks:**
- **no leak string or SIH parameter change remains:** 12/12 clean;
- **the product's conclusions on each blinded copy equal those on its
  source:**
  - **11/12 equal.** Of these, 7 reports are byte-identical except the
    input name;
  - 3 differ only in their event lists (the message no longer opens an
    event): GPS, magnetometer, ESC offline;
  - matched pair B is compared with the demo's in-memory result, and is
    equal.
- **1/12 changed: the RPM × 10 log.** Without the injection message the
  excess is never discovered, and the first page reads "nothing adverse was
  observed". **This is defect D-PRIME-2** (`DEFECT_D_PRIME_2.md`), reported
  and not patched.

**The log stays in the bundle as it is.** The test measures the product as
it is, including this gap. Whether analyzer users are then lulled into
"nothing abnormal" is exactly what the test should show. The experimenter
knows (the rubric's case table); the participant does not.

## 4. E2: the engineering task test (protocol; not run)

**This builds on 2.2's `EXTERNAL_USER_TEST_PLAN.md`,** with the PRIME bundle
and the brief's questions.

**The question.** Does an engineer who did not build CSIA answer the
following more correctly with the analyzer than with ordinary manual PX4
analysis?
- what happened, when, which component;
- which alternatives remain;
- which evidence is trustworthy;
- which evidence shares a source;
- which measurement would resolve the ambiguity.

The analyzer must also produce **fewer unsupported claims and no more wrong
attributions.**

| element | protocol |
|---|---|
| participants | 6-10 flight-test, controls, autopilot-integration or autonomy engineers who have debugged PX4 logs. None has seen CSIA code, documents or this repository |
| design | crossover: each participant does 6 logs manually and 6 with the analyzer. Form X uses the analyzer on odd P-numbers and form Y on even ones; forms alternate by participant; each participant's order is rotated (`experimenter/ASSIGNMENT.json`). The matched pair falls in opposite conditions within each form |
| manual condition | the ULog, plus PX4 Flight Review (local), PlotJuggler, pyulog, the participant's own scripts, and the PX4 documentation |
| analyzer condition | the same tools, plus the analyzer's outputs and `REPORT_GUIDE.md` |
| per log | one `DIAGNOSTIC_QUESTIONS.md` sheet; 20 minutes maximum (proposed); the experimenter answers tool-operation questions only |
| after the session | `FEEDBACK_FORM.md`, including the two-minute comprehension item (A6) |
| scoring | `pilot_package_experimenter/SCORING_RUBRIC.md`: two blind raters, a third to resolve |
| primary measures | **wrong attribution** (the safety measure), correctness, unsupported certainty |
| success criteria | the rubric's section 4, all three, fixed now |

**Frozen before the first participant:**
- the product commit;
- the bundle's member hashes (`PILOT_BUNDLE.json`);
- the rubric;
- the assignment.

**Any change means a new bundle version and a restart,** never a mid-study
edit.

**Threats and controls:**

| threat | control |
|---|---|
| truth leaking from the log | the two record kinds removed and checked (section 3); file names replaced by P-numbers in a seeded order |
| SITL logs identifiable as SITL | participants are told SITL or REAL per log; the diagnosis is still theirs to make |
| the analyzer's wording leads | outputs frozen with the commit; the guide does not mention cases |
| learning across logs | crossover; rotated order |
| experimenter coaching | written protocol; no interpretation help |
| rubric fitted afterwards | the rubric is committed before any session |
| a known product gap (D-PRIME-2) | stated in the rubric; any wrong or empty answer copied from the analyzer is reported individually |

**What this test cannot show:**
- real-hardware validity, because 10 of 12 logs are SITL;
- performance on faults outside the set.

It measures whether the product helps an engineer reason correctly about
what a log does and does not support.

## 5. What it costs to run

- **No new flights and no hardware.**
- **People:** 6-10 participants for about 4 hours each; two raters; one
  experimenter.

## 6. Owner decisions needed

1. **Distribution of the bundle** to named external engineers:
   - the logs are this program's SITL output, plus two third-party logs
     whose licences allow it with the notices included;
   - the wheel is proprietary code.
2. **Recruitment, consent and compensation.**
3. **Whether to fix D-PRIME-2 first**, in a versioned discovery mode, and
   rebuild the bundle, or to test the product as it is. **Testing as it is
   is valid.** The result then includes the gap.
