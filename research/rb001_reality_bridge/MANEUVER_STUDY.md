# Maneuver study: can degradation be detected during maneuvering without restoring false symptoms? (RB-001 Parts 3-6)

**2026-10-02. SITL only (SIH). Nothing here is physical evidence.**

## 1. The problem and the rule

**The hole.** CSIA 2.3 refuses its compensation evidence when the vehicle
is not near-steady (NOT_STEADY_FLIGHT, peak body rate above
θ_steady = 0.0989 rad/s). That removed the false `COMMAND_NO_RESPONSE`
that maneuvers raised (2.3 V5, V6). But a motor losing effectiveness
during continuous maneuvering is then not confirmed (2.3 V13).

**The brief's rule:** do not loosen the steadiness threshold. Compare
baselines; SITL before hardware; and a candidate that brings back false
`COMMAND_NO_RESPONSE` does not move to hardware.

## 2. The five candidates (`maneuver.py`)

| id | what it is | statistic | validity regime |
|---|---|---|---|
| B0 | the 2.3 product as shipped | compensation C_m (change in motor m's command share) ≥ θ_ctrl | refused above θ_steady |
| B1 | the gate loosened (the brief's "looser threshold" baseline, run to show what it costs) | C_m ≥ θ_ctrl | refused above 2 × the calibration maximum of the peak rate |
| B2 | regime-conditioned thresholds | C_m ≥ θ_C(bin of the peak rate) | a bin with fewer than 20 calibration pseudo-onsets is refused |
| B3 | control-conditioned residual | the per-motor loss estimate δ_m from the torque residual: demanded torque (low-passed) minus the torque implied by measured angular acceleration, projected on each motor's signature, AFTER minus BEFORE | none |
| B4 | an established model-based test | Willsky-Jones GLR on the same residual, motor signatures u_m·b_m, heteroscedastic noise model | none |

**B3 and B4 are textbook forms** (parity-space residual and GLR; see
`LITERATURE.md`). They are what an engineer would try first. Neither is
offered as a new method.

**The model** (g, c, the allocator mixing, the noise) was fitted on the
calibration flights only: g ≈ [104.3, 104.6, 6.3] (rad/s² per unit
torque setpoint, roll, pitch, yaw).

## 3. Data separation

| set | flights | used for |
|---|---|---|
| development | 2.3 V1-V13 (already seen) | formulation choices only: the lag constant, roll-pitch for B3, B4's argmax among loss estimates; no threshold |
| calibration | CAL1-CAL5, nominal: 1,020 pseudo-onsets | every threshold, by one rule: 2 × the largest null value |
| evaluation | EN1-EN4, EF1-EF6, EH1, ET1, ET2 | flown after the preregistration was committed (9375920); scored once |

**Thresholds** (`MANEUVER_CALIBRATION.json`):
- θ_steady_B1 = 2.876 rad/s;
- θ_C by bin: 0.0061, not calibrated, 0.057, 0.320, 0.352;
- θ_δ = 0.0183 (null maximum 0.0092);
- h_GLR = 126.6 (null maximum 63.3).

**Development reference** (seen before the preregistration, not evidence):
B1 raised 42 false VIOLATED on V1-V13. B0 missed V13. B2, B3 and B4 raised
none and detected 6/6.

## 4. AS-RUN: the evaluation flights

**All 13 were flown,** once each, after the preregistration was committed:
- EN1-EN4, EF1-EF6, EH1, ET1, ET2;
- every arm, injection and disarm acknowledged;
- none re-flown.

**One deviation from the design, found after flying, and kept:**
- **What the design says:** ET2 (ESC 1 OFF during the EN2 pattern) with
  an east wind of 5 m/s.
- **What was flown:** the runner, `sitl_maneuver_runs.py`, committed with
  the design in f2a491a, gave ET2 no wind parameter, so ET2 flew in still
  air.
- **What was done about it:** it was not re-flown.
- **What it affects:** ET2 still tests what it was in the set for, a
  telemetry fault on a healthy motor during maneuvering. It does so with
  less disturbance than designed, so it is a weaker nominal case than
  intended.

**Scored once:**
- `evaluate_maneuver.py --set eval`, hashes as in the preregistration →
  `MANEUVER_RESULTS_EVAL.json`;
- the criteria applied by `as_run_verdict.py` (committed in 8c2eb29, before
  the results existed) → `MANEUVER_VERDICT_EVAL.json`.

**Scope of the scoring:**
- 152 product events were scored at their AFTER checkpoint; 9 more had
  their checkpoint beyond the end of the log;
- 3 events of EF3 were refused by every candidate because the allocator
  was saturated (motor_2 at 60 % in a 4 m/s wind on 70 m legs).

| | B0 (product) | B1 (loosened gate) | B2 (regime thresholds) | B3 (control-conditioned residual) | B4 (GLR) |
|---|---|---|---|---|---|
| false VIOLATED at nominal events (each one a false `COMMAND_NO_RESPONSE`) | 0 | **163**, on 12 of 13 flights | 0 | 0 | 0 |
| injected motor detected, EF1-EF6 | **0 / 6** | 6 / 6 | 4 / 6 (missed EF4, EF5) | **6 / 6** | 6 / 6 |
| injected motor detected, EH1 (hover) | yes | yes | yes | yes | yes |
| VIOLATED on a non-injected motor after the onset | 0 | 52 | 0 | 0 | **6** |
| motor states refused | 576 of 608 (564 NOT_STEADY) | 12 (saturated) | 32 (20 bin not calibrated) | 12 | 12 |
| S1 / S2 / S3 | pass / **fail** / pass | **fail** / pass / fail | pass / **fail** / pass | pass / pass / pass | pass / pass / **fail** |
| **as-run verdict** | FAIL: the hole stays | **FAIL on S1: does not move to hardware** | FAIL | **PASS** | FAIL |

**The product as shipped (B0), any time, on its own:**
- `COMMAND_NO_RESPONSE|motor_0` on EH1 (hover), correct;
- nothing on any other flight: no false symptom, and none of the six
  maneuvering losses confirmed;
- this is 2.3's V13 behaviour, reproduced on six new flights.

**What the as-run result says:**
- **Loosening the gate (B1) brings the false symptoms back,** 163 of them,
  and blames healthy motors 52 times. The brief's rule, "do not loosen the
  steadiness threshold", is confirmed on new flights.
- **Regime-conditioned thresholds (B2) are safe but blind** to smaller
  losses while maneuvering.
- **The GLR (B4) detects everything but names a wrong motor six times.**
- **The control-conditioned residual (B3) is the one candidate that closes
  the hole in SITL** without a false or wrong symptom.

## 5. POST-HOC analysis (chosen after the result was seen; re-scores nothing)

Script: `posthoc_maneuver.py` → `MANEUVER_POSTHOC.json`.

**B3's estimate is the lost fraction.** At the first clean POST event of
each fault flight, δ against 1 − η:

| flight | 1 − η | δ |
|---|---|---|
| EF1 | 0.40 | 0.396 |
| EF2 | 0.25 | 0.249 |
| EF4 | 0.25 | 0.250 |
| EF5 | 0.15 | 0.148 |
| EF6 | 0.40 | 0.398 |
| EH1 | 0.20 | 0.199 |

EF3 is not in the table: its STRADDLE event gave 0.285, and its first POST
event (0.399) was refused as saturated.

**B3's margins:**
- the largest estimate at any nominal event was 0.0061; on a healthy motor
  after an onset, 0.0067. Against θ_δ = 0.0183 that is a margin of about
  3x;
- the smallest detection was EF5's STRADDLE event at 0.048, then 0.148 at
  its POST events.

**Why B3 looks this good in SITL, and will not on hardware.** In SIH the
model is the plant:
- rigid body;
- linear mixing;
- no aerodynamic torques;
- no vibration on the differentiated gyro;
- the inertia is constant and known.

Every one of those is a reality-gap threat in `REALITY_GAP_AUDIT.md`. Its
transfer class is REQUIRES_NEW_MODEL (`TRANSFER_CLASSIFICATION.md`). Its
noise floor on a real vehicle is unknown until RB5.

**B3 is a change statistic.** At later events, after the loss is already in
the BEFORE window, δ on the degraded motor is about 0 and B3 says
NOT_VIOLATED. That means "no new change", not "healthy". Any report that
used it would have to keep the symptom raised at the onset, as 2.3's
"symptoms raised at any time" already does.

**B4's six wrong motors are all at later events,** none at an onset:

| flight | event | injected | named | GLR (injected, named) | estimate for the named motor |
|---|---|---|---|---|---|
| EF2 | 145.1 s | 1 | 0 | 423, 410 | 0.032 |
| EF3 | 121.8 s | 2 | 3 | 4143, 4098 | 0.093 |
| EF3 | 130.3 s | 2 | 3 | 7870, 7851 | 0.133 |
| EF4 | 82.0 s | 3 | 2 | 171, 161 | 0.018 |
| EF4 | 102.0 s | 3 | 2 | 204, 188 | 0.019 |
| EF4 | 142.0 s | 3 | 2 | 583, 558 | 0.035 |

**In each case:**
- the named motor is the injected motor's **diagonal partner**, whose
  roll-pitch signature is nearly the negative of the injected one, so
  their GLRs are nearly equal;
- B3's estimate on the injected motor at the same events was below 0.0016,
  so nothing changed.

**The likely mechanism.** B4 compares the AFTER samples with the BEFORE
mean. A loss already present in both windows leaves a residual that varies
with the motor command as it maneuvers, and B4 reads that as a change. The
development fix (choose among positive estimates) cannot help when the
estimates are close to zero. This is an explanation, not a tested claim.

**B2's misses are a detectability floor, not noise:**
- EF4 (η = 0.75): C = 0.273 at R = 1.28 rad/s, against that bin's
  threshold of 0.352;
- EF5 (η = 0.85): C = 0.095 at R = 0.96 rad/s, against 0.320.

Maneuvers move the command split as much as a 25 % loss does, so a
threshold set on maneuvering nulls hides losses of that size.

**The product's event rate on the new nominal and telemetry flights**
(Part 16, in SITL):
- 78 events in 0.230 in-flight hours, **339 per hour**;
- 2.3 measured 287 per hour on its own maneuvering flights;
- the Part 15 budget is 6 per hour;
- all were dismissed (no product symptom on any of them).

## 6. What follows, under the preregistration

**B3 goes forward as a candidate for the RB5 design. Nothing else changes:**
- it does not enter the product, and the product does not change on SITL
  results;
- it needs a closed loop, so it cannot be tested on the RB2 motor bench.

**Its first physical test is the model:**
- identify g, c and the mixing on the restrained vehicle's nominal runs;
- measure δ's null distribution there;
- only then a reversible loss (`MINIMUM_PHYSICAL_EXPERIMENT.md` section 6,
  `HARDWARE_EVIDENCE_PLANS.md`).

**Lineage.** B3 shares the IMU and the rate loop with the compensation, so
it would corroborate it only partly (`PHYSICAL_EVIDENCE_CASES.md`).

**B1 does not move to hardware** (failed S1). **B2 and B4 do not move
either** in their frozen form. A B4 that also required B3's estimate to
exceed θ_δ would be a new candidate, needing new flights.
