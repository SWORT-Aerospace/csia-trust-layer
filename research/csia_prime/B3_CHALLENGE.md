# B3's physical challenge, as far as it can go without hardware (PRIME Track C2)

**2026-10-02. SITL BASES (development and calibration flights only),
OFFLINE MISMATCH. NOT PHYSICAL EVIDENCE. B3 IS NOT PRODUCT-APPROVED.**

**Files:**
- **script:** `b3_challenge.py`;
- **output:** `B3_CHALLENGE.json`.

**What stays fixed:**
- B3's code (RB-001 `maneuver.py`, SHA-256 `9c585800…`);
- its SIH model and its threshold θ_δ = 0.0183 (`MANEUVER_CALIBRATION.json`).

**Data:** the 2.3 development flights V1-V13 and RB-001's calibration
flights CAL1-CAL5. **The RB-001 evaluation flights were not used.**

## 1. Method

**The plant is made to disagree with the model, one mismatch at a time,**
and B3 is scored at the product's own events with its frozen rule:
- false VIOLATED at nominal events;
- detection of the six development losses (V1-V4, V12, V13);
- VIOLATED on a wrong motor.

**The two step variables also get an event at the step** (t_s − 0.5 s) on
every nominal flight, as if event discovery had found it. A CG change does
move the compensation, so it would be.

## 2. Results

**Unperturbed:** 0 false, 6/6 detected, 0 wrong.

| mismatch (stands for) | range | false VIOLATED | wrong motor | detection |
|---|---|---|---|---|
| response latency beyond the model's 0.05 s (ESC/motor lag) | 5-100 ms | 0 | 0 | 6/6 |
| effectiveness error, the model's g wrong (inertia, motor constant) | −30 % to +30 % | 0 | 0 | 6/6 |
| effectiveness drift over the flight (battery sag) | 2-20 % | 0 | 0 | 6/6 |
| static motor asymmetry (motor_1 at 1 ± a) | ±5-20 % | 0 | 0 | 6/6 |
| mass change without CG change (collective thrust step) | 0.02-0.2 | 0 | 0 | 6/6 |
| **angular-acceleration noise** (vibration on the differentiated gyro; white, at the 100 Hz grid) | 0.5-20 rad/s² | **17 at 5; 51 at 10; 75 at 20** | **2 at 10; 3 at 20** | 6/6 |
| **CG step mid-flight** (a payload shift: the controller needs extra roll torque Δ; the rotation does not change) | Δ = 0.005-0.1 of normalised roll torque | **at Δ ≥ 0.01: a false loss at the step event on all 8 nominal flights**; 17-42 in total | 0 | 6/6 |
| gyro bias | — | — | — | **structurally none:** B3 reads only the derivative of the rate |

**Δ = 0.01 is small.** In SIH a normalised roll torque of 1 is about 2.6
N·m (g ≈ 104 rad/s², I_xx = 0.025 kg·m²). So 0.01 is about 0.026 N·m:
about 27 g of payload moving 10 cm, or a battery sliding 1 cm.

## 3. What the results mean

**B3's model form is robust to parameter error.** The AFTER-minus-BEFORE
difference cancels static mismatches. A model 30 % off in effectiveness,
100 ms late, or with a 20 % motor asymmetry still raised nothing false in
these flights. So identifying the model on a real vehicle should be a
recalibration, not a redesign.

**B3 has a structural confound: a CG or payload change.** To the residual,
a mid-flight CG shift is the same signature as a loss of effect on the
motors on the other side. The controller needs more torque for the same
rotation. **No threshold separates them:**
- the false loss appeared at the smallest step tested above 0.005;
- it appeared on every nominal flight.

**What could separate them, as a matter of evidence:**
- **ESC telemetry:** after a CG shift the motors' RPM still follows their
  commands, so telemetry stays NOMINAL. After a real loss it shows a
  deficit (except when the loss is in the propeller and RPM is
  unaffected).
- **What that requires of the product:** B3 needs a validity condition, or
  a corroboration rule with the telemetry witness, before it could raise
  a symptom. Today the product treats telemetry as context only (SB-1), so
  that is a profile question.

**Real angular-acceleration noise is the second open edge:**

| source | std (rad/s², per axis) |
|---|---|
| SIH | 0.5 |
| real CubeOrange at rest (RB0 log, 404 Hz) | 0.08-0.09 |
| real FMUv5 on a boat, motor running (50 Hz; motion plus noise) | **1.7-4.8** |
| a real multirotor in flight | **unmeasured** |

**B3's false-VIOLATED edge is at 5 rad/s² white noise.** A real multirotor's
vibration on the differentiated gyro is likely at or above the boat's
level. That is a real risk, measurable only on real flight data.

## 4. Transfer classification (predicted; the brief's classes)

**`REQUIRES_VALIDITY_CONDITION`.** Three reasons:
- B3 must not raise a loss across a payload or CG change. The confound is
  structural, so calibration cannot remove it.
- It also needs its noise floor recalibrated on real flights. Parameter
  error, latency and asymmetry did not break the form.
- So: not REQUIRES_MODEL_CHANGE; not TRANSFERS_DIRECTLY.

**This is a prediction from SITL perturbation.** Gate PRIME-D needs real or
HIL maneuvering data. The first physical test stays RB-001's:
1. identify g, c and the mixing on a restrained vehicle's nominal runs;
2. measure δ's null distribution there;
3. only then, a reversible loss.

**Add to that test:** a deliberate, reversible CG change (a known clip-on
mass moved between runs), to measure the confound on real hardware.

## 5. Stop conditions

**Stop condition 4** (B3 producing wrong-motor attribution on hardware)
**cannot be tested:** there is no hardware.

**In SITL B3 named a wrong motor only under heavy angular-acceleration
noise:** 2 states at 10 rad/s², 3 at 20.
