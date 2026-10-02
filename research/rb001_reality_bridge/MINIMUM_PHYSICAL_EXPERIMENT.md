# The minimum physical experiment (RB-001 Parts 8-14)

**2026-10-02. A DESIGN. Nothing here has been run;** nothing can be from
this environment (`HARDWARE_INVENTORY.md`). It is written so that the owner
can run it, and so that its analysis is fixed before the data exists.

## 1. The question (Part 8)

> DOES THE STOCK CSIA PROPULSION EVIDENCE REMAIN SEPARABLE UNDER REAL
> SENSOR/ACTUATOR NOISE?

**Concretely:** can the relationship between command, ESC-reported RPM,
ESC or bus current, and the physical effect still separate two cases on
real hardware with real noise?
- **A:** a motor that really lost effect;
- **B:** a healthy motor whose telemetry lies.

This is the XSYS-001 distinction (`MOTOR_VS_TELEMETRY.md` in the 2.3
package). On real hardware the physical effect is thrust, measured
independently.

## 2. The lowest-energy architecture that answers it: RB2

```
  bench supply (current-limited, e.g. 4S equivalent, limit 5 A)
        |
   [current shunt] --- logic analyzer / ADC (GROUND TRUTH: current)
        |
       ESC (telemetry: RPM, current, voltage, temperature) ---- FC (PX4, logs esc_status, actuator_outputs)
        |                                                        ^
      motor + propeller on a single-axis load-cell stand         | USB to the Linux desktop
        |          (GROUND TRUTH: thrust)                        |
   optical tachometer / IR reflective sensor --- logic analyzer  (GROUND TRUTH: rotor speed)
        |
   enclosure / prop guard; kill switch on the supply
```

**The parts:**
- **Flight controller:** PX4 on the planned FMUv6C-class board. It drives
  the ESC with DShot or PWM through PX4's actuator test or a scripted
  `MAV_CMD_ACTUATOR_TEST` sequence. It logs `actuator_outputs`,
  `esc_status` and its own sensors in a ULog.
- **CSIA reads the ULog afterwards, offline, as a product user would.** It
  commands nothing; the command script is the experimenter's.
- **One motor first.** A second, identical motor on a second stand makes
  the normalised statistic q, which needs a reference motor, testable.
  Two is the minimum for q; four is not needed at RB2.
- **No battery, no airframe, no free rotation.** The propeller is fitted
  only in stage RB2-1, inside the guard.

**Why not start at RB5 (a restrained vehicle)?** The compensation and B3/B4
statistics need a closed loop, so they can only be tested at RB5 or above.
But the separability question has two parts:
- whether RPM, current and thrust stay consistent under real noise;
- whether telemetry corruption is visible against the others.

Both are answered at RB2, with a fraction of the energy and no flight
controller in the loop.

## 3. Stages (lower energy first)

| stage | what runs | what it measures | stop if |
|---|---|---|---|
| RB2-0 | motor without propeller, supply limited to 2 A | ESC telemetry rate, latency against the logic analyzer, RPM quantization, RPM against tachometer, current against shunt, at command steps 10-60 % | anything heats, vibrates loose, or the supply hits its limit |
| RB2-1 | propeller fitted, inside guard, load-cell stand, limit 5 A, command at most 60 % | thrust per command, rpm^2 per thrust (does T ∝ rpm^2 hold, and with what THR_MDL_FAC?), nominal corpus (section 7) | load cell or mount moves; any contact with the guard |
| RB2-2 | the reversible conditions of section 6 | A against B | as above |
| RB3 | FC and its IMUs on the same bench, motor running nearby | real IMU noise and vibration at bench level; timing of every topic; producer-health states | — |
| RB4 | PX4 HIL with the FC | noise, timing, configuration transitions, multiple sensor instances, maneuvering, at no hardware risk | — |
| RB5 | restrained vehicle (tether or gimbal), props on | compensation C, B3/B4 residual, steadiness statistic, false-event rate under real vibration | any tether contact or loss of control |
| RB6 | low-risk real flight | not in RB-001's first result | — |

**Each stage needs the owner's written authorization first.** The
repository's program state currently forbids motors and ESCs
(`HARDWARE_INVENTORY.md`).

## 4. Physical observables, ranked (Part 9)

| observable | diagnostic value | cost | safety | rate | integration | independence from the evidence |
|---|---|---|---|---|---|---|
| command (actuator_outputs / DShot frame) | the input; needed for everything | free | none | 10 Hz logged by default; the bus can be captured at full rate by the logic analyzer | none | the FC's own value: evidence |
| ESC RPM (esc_status) | **high**: the telemetry claim itself | comes with the ESC | none | 10 Hz default (4 Hz in newer PX4, RB0) | ESC setup | **this is the evidence under test** |
| ESC current (esc_status) | **high**: the stall check (2.1.1's STALL_SIGNATURE) and PX4's own motor-failure check | comes with the ESC | none | as RPM | ESC setup | shares the ESC MCU with RPM: **not independent of it** |
| bus current (shunt or power module) | high: independent of the ESC MCU | low | none | logic analyzer or ADC at kHz; power module at 5 Hz in the ULog | low | **independent** of ESC telemetry |
| thrust (load cell) | **highest**: the physical effect itself | moderate | needs the stand | 80-1000 Hz | moderate | **independent ground truth** |
| tachometer RPM | high: ground truth for the RPM claim | low | none | per revolution | low | **independent ground truth** |
| torque (reaction load cell) | medium: yaw-moment checks | moderate | needs a torque stand | as thrust | higher | independent |
| IMU vibration (accelerometer at full rate) | medium at RB2; high at RB5 (propeller faults: Ghalamchi et al.) | free (FC) | none | 1 kHz if logged | logger profile change | independent of the ESC; shares the FC |
| angular response | not observable at RB2 (no vehicle) | — | — | — | — | — |
| temperature (ESC report; thermocouple on the motor) | low for the question; needed to record warm-up as a covariate | low | observe natural warm-up only | 1 Hz | low | ESC report shares the MCU; thermocouple independent |

## 5. Independent ground truth (Part 10)

**The rule.** A signal under test is never its own ground truth:

| evidence under test | ground truth |
|---|---|
| ESC RPM | optical tachometer (logic-analyzer timestamped) |
| ESC current | bus shunt, or a clamp meter where the shunt cannot go |
| "the motor lost effect" | load cell thrust at the same command |
| "the telemetry is wrong" | the configuration protocol: the experimenter's run sheet records exactly what was changed and when, and the tachometer and load cell show the motor unchanged |
| timing (content time) | the logic analyzer, one timebase for command pulses, tachometer pulses and a sync pulse the FC toggles on a GPIO |

## 6. Physical fault classes: reversible, low risk (Part 11)

| class | how | A or B | reversible |
|---|---|---|---|
| reduced commanded effectiveness, in software | the FC scales the motor's output range (for PWM, the output's maximum; for DShot, the output limit), so the same normalised command produces less | **A**: the drive delivers less, and RPM, current and thrust all fall | yes, a parameter |
| added known load | a clip-on drag disc or a heavier propeller of known inertia; the experimenter's sheet records which | **A** (more power for the same RPM, or less RPM) | yes |
| telemetry corruption, injected | PX4 failure injection on the ESC topic, if the board's driver supports it (to be checked, not assumed) | **B** | yes |
| telemetry corruption, offline | the logged RPM scaled by sqrt(eta) in replay, so that the local telemetry symptom matches A's exactly: XSYS-001's case-B construction on real data | **B** (labelled REAL DATA WITH SYNTHETIC CORRUPTION) | n/a |
| sensor disconnection | the ESC telemetry wire unplugged, motor stopped, between runs | B (telemetry absent) | yes |
| controlled power limitation | the supply's current limit lowered | A-like (common to all motors) | yes |
| configuration change | a parameter change between runs, recorded | neither: a configuration epoch | yes |

**Never:**
- damaging a propeller;
- overheating anything on purpose;
- any battery fault;
- free flight;
- a fault while a vehicle is airborne.

## 7. Real motor against telemetry (Part 12)

**The design:**
- the same motor, the same command profile (steps 20/40/60 % and a slow
  ramp), 10 runs each;
- conditions: nominal, then A at three loss levels, then B matched to each
  A level offline.

**What is compared:** the local telemetry symptom L (RPM deficit) is made
equal by construction. The question is whether current and thrust separate
A from B, and with what margin.

**Thresholds** are recalibrated on the nominal runs only. **The SITL
thresholds are not used; SIH's do not transfer** (STOCK_PRODUCERS.md in
2.3).

**Success, fixed now:**
- every B run classified "telemetry not confirmed by the physical
  evidence";
- every A run at a loss level above the nominal-derived resolution
  classified "loss confirmed";
- **zero A classified as B or B as A.**

## 8. Nominal corpus before any fault (Part 13)

**Frozen before the first fault run.** Matrix:

| factor | levels |
|---|---|
| hardware temperature | cold start; warm (after 10 min at 40 %) |
| supply voltage | three settings within the ESC's rating (e.g. 14.8, 15.6, 16.4 V) |
| command level | 20, 40, 60 % steps, and a 20-60 % ramp |
| duration | 60 s and 5 min holds |
| remount | the motor removed and remounted between blocks (mounting variation) |
| repeats | 5 per cell at RB2-1 |

**Purpose:** the null distribution of each statistic, over:
- run to run;
- temperature;
- supply;
- command level.

**Not purpose:** finding the threshold that best detects the planned fault.

## 9. Hardware calibration (Part 14)

**Recorded per statistic, from the nominal corpus:**
- distribution (quantiles, not only the maximum);
- sensitivity to temperature and supply (regression slope);
- run-to-run spread;
- sensor noise floor;
- false-alarm count at the candidate threshold.

**The rule stays 2.3's:** threshold = 2 x the largest null value. The
99.9th percentile is also reported, so the rule's conservatism is visible.

**A statistic whose null depends strongly on temperature or supply gets a
validity condition,** not a looser threshold.

## 10. What a result would and would not mean

**An RB2 result would say** whether the telemetry, current and thrust
relationships CSIA relies on survive real motors, ESCs and sensors.

**It would not say anything about** the closed-loop statistics:
- compensation;
- B3/B4;
- steadiness.

Those need RB5. It would not say anything about flight either.

**The first purchase decision** follows from the owner's confirmation of
what they hold. The minimum set is listed in `HARDWARE_INVENTORY.md`: one
ESC with telemetry, one motor, a current-limited supply, a single-axis stand,
a tachometer sensor and a logic analyzer.
