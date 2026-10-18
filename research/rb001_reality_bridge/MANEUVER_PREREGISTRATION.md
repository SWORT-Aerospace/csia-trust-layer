# Maneuver study: preregistration (RB-001 Part 6)

**2026-10-02. Committed after calibration and BEFORE any evaluation flight
(EN1-EN4, EF1-EF6, EH1, ET1, ET2) is flown.** Nothing below changes after
this commit. Any later change is a new, separately labelled analysis.

## 1. What is frozen

| item | frozen as |
|---|---|
| statistics and decisions | `maneuver.py`, SHA-256 `9c585800d8e21c797ca8524247baf6bc5096378a0eed63013159dfe7657a6244` |
| scoring | `evaluate_maneuver.py`, SHA-256 `192baa0349e47d12093ba8af01cc4d965b09137210507b805b9440cbd4f3ec0a` |
| calibration and model | `MANEUVER_CALIBRATION.json`, SHA-256 `3c2c0f76364114765c5cf379965d8a186e009a73485435ee6e05967eb72c1429` |
| calibration set | CAL1-CAL5 only (hashes in the calibration file): 1,020 nominal pseudo-onsets |
| evaluation flights | EN1-EN4, EF1-EF6, EH1, ET1, ET2 exactly as in `MANEUVER_FLIGHTS_DESIGN.md` (committed in f2a491a) |
| development data | 2.3 V1-V13 only; used for formulation choices (lag constant 0.05 s, roll-pitch for B3, B4's argmax among loss estimates); **no threshold** |

## 2. The candidates and their thresholds

**Common rules:**
- Every candidate is evaluated at the product's own discovered events, at
  the AFTER checkpoint.
- Every candidate refuses (UNAVAILABLE) when the allocator reports
  saturation over most of the AFTER window.

| id | VIOLATED on motor m when | validity regime | threshold (from CAL1-CAL5 unless stated) |
|---|---|---|---|
| B0 | C_m >= theta_ctrl | refused when R > theta_steady | theta_ctrl = 0.00688, theta_steady = 0.0989 rad/s (2.3 r3, as shipped) |
| B1 | C_m >= theta_ctrl | refused when R > theta_steady_B1 | theta_ctrl = 0.00688 (r3); theta_steady_B1 = 2.876 rad/s (2 x the CAL max of R) |
| B2 | C_m >= theta_C(R bin) | a bin with fewer than 20 CAL pseudo-onsets is not calibrated: refused | R bins [0, 0.1, 0.3, 0.6, 1.2, inf) rad/s: thresholds 0.00614, **not calibrated** (6 pseudo-onsets), 0.0568, 0.320, 0.352 |
| B3 | delta_m is the largest of the four and >= theta_delta | none | theta_delta = 0.0183 (null max 0.0092) |
| B4 | GLR_m >= h_glr, for the motor with the largest GLR among those whose estimate is a loss | none (the noise model depends on the body rate) | h_glr = 126.6 (null max 63.3) |

**The rule** is 2.3's: threshold = 2 x the largest null value. Nothing was
chosen by looking at a fault.

## 3. Development reference (already seen; not evidence)

With these frozen thresholds on 2.3's V1-V13 (`MANEUVER_RESULTS_DEV.json`):

| | B0 | B1 | B2 | B3 | B4 |
|---|---|---|---|---|---|
| false VIOLATED (each one a false COMMAND_NO_RESPONSE) | 0 | **42** | 0 | 0 | 0 |
| faults detected (V1-V4, V12, V13) | 5/6 (misses V13) | 6/6 | 6/6 | 6/6 | 6/6 |
| wrong motor | 0 | 0 | 0 | 0 | 0 |

B0 here equals the shipped product's any-time result on every flight (V13
missed, nothing else raised).

## 4. Success and failure criteria (per candidate, applied once)

**S1, no false symptoms:** zero VIOLATED on any motor at any scored event
of:
- EN1-EN4;
- ET1 and ET2 (a telemetry fault on a healthy motor);
- the PRE events of EF1-EF6 and EH1 (AFTER window entirely before the
  injection).

**S2, detection:**
- the injected motor is VIOLATED at at least one POST or STRADDLE event in
  **at least 5 of the 6** EF flights;
- and in EH1.

**S3, no wrong motor:** zero VIOLATED on a non-injected motor at any POST or
STRADDLE event of EF1-EF6 and EH1.

**What PASS and FAIL mean:**
- A candidate **PASSES** if S1, S2 and S3 all hold.
- A candidate that fails S1 **FAILS**, whatever it detects, and does not
  move to hardware (the brief, Part 5).
- A candidate that passes S1 and S3 but fails S2 does not close the hole.

**What passing gives and does not give:**
- Every passing candidate goes forward to the bench designs as a candidate.
- None replaces the product's evidence. The product does not change on
  SITL results.
- The brief's rule: physical data decides any architecture change.

**Also reported, not pass/fail:**
- detection margin (statistic over threshold);
- refusals (UNAVAILABLE) per candidate;
- the product's own any-time result per flight.

## 5. What is kept apart

**As-run:**
- `MANEUVER_RESULTS_EVAL.json`, produced once by `evaluate_maneuver.py --set eval`;
- the criteria above, applied to it.

A flight that fails to fly is reported as such and not re-flown.

**Post-hoc:** anything else is labelled POST-HOC in `MANEUVER_STUDY.md`. That
includes different windows, thresholds, regimes, continuous monitoring or
other flights. None of it rewrites the as-run result.
