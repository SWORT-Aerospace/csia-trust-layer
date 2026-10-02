# Known against discovered onset, and the blind-onset XSYS replay (Phases 15-16)

**2026-10-02.**

- **Script:** `blind_onset_replay.py`.
- **Output:** `BLIND_ONSET_REPLAY.json`.
- **Label:** EXPLORATORY product benchmark. It is NOT the XSYS-001
  confirmatory result.

## 1. What was replayed

**The cases.** The 121 XSYS-001 analysis cases, from the sealed key:
- 55 motor losses (A, eta 0.55-0.95, all on motor 0);
- 55 telemetry-only deficits (B, built by XSYS-001's frozen case-B rule
  over the whole flight);
- 11 benign-onset flights (N).

**XSYS-001's sealed data, code and results are read, never written.**
The replay rebuilds:
- the stock logs, at default rates;
- XSYS-001's research witnesses, from its frozen code. They match the
  sealed stage-1 features exactly.

**The configurations:**

| configuration | evidence | onset |
|---|---|---|
| A | stock producers only (`px4_monitors=False`) | discovered |
| B | stock producers and PX4's monitors (the product default) | discovered |
| B_known | as B | the true onset, given (benchmark hook) |
| C_known | XSYS-001's research witnesses, frozen | the true onset |
| C_disc | XSYS-001's research witnesses, frozen | configuration B's discovered event |

## 2. Event discovery on 121 cases

| | A trials | B trials | N flights |
|---|---|---|---|
| matched (an event within 2 s of the injection) | 55/55 | 55/55 | — |
| events per case | exactly 1 | exactly 1 | 0 |
| false events | 0 | 0 | 0 |

**Timing error** (discovered t0 minus the true onset), over 110 cases:
- median -0.032 s;
- range -0.096 to +0.140 s;
- |error| <= 0.05 s in 62 cases, <= 0.1 s in 106.

The CUSUM onset estimate (the last S = 0) usually lands one or two samples
early. At eta = 0.95 it is late (median +0.084 s): a 5 % change takes
longer to accumulate.

**How the cases were found.**
- **A trials:** by the compensation and telemetry CUSUMs together.
- **B trials:** by the telemetry CUSUM alone. The command did not change,
  so the compensation detector stayed silent, as it should.

## 3. Decisions: known against discovered (Phase 15)

| question | answer |
|---|---|
| decision differences, B against B_known | **0 / 121** |
| decision differences, C_disc against C_known | **0 / 121** |
| wrong attribution | 0 in every configuration |
| ambiguity | unchanged: identical candidate sets |
| outcome, A trials (configs A, B) | `COMMAND_NO_RESPONSE|motor_0` AMBIGUOUS among drive_no_current, mechanical, command_not_delivered, path_unavailable; response_sensor eliminated |
| outcome, B trials (configs A, B) | no symptom; motor_0's telemetry deficit reported as context, not confirmed by the vehicle |
| outcome, configs C_known and C_disc | UNIQUE and correct, 110/110 (XSYS-001's result reproduced, onset discovered or given) |

**Window validity.**
- The compensation (W_CTRL) and telemetry (W_RPM) windows start 10 s after
  t0.
- An onset error of 0.1 s moves them by 1 % of their offset. It cannot
  change their content.

## 4. W_DYN at a discovered onset: not stretched, and fragile

**The brief: "Do not stretch W_DYN's validity window."** It was not
stretched. The rate-transient window is still [t0, t0 + 0.2) s, now with
the discovered t0.

**What the replay shows is how little room that window leaves:**

| eta | median D_T1, true onset (rad/s) | median D_T1, discovered onset | median onset error |
|---|---|---|---|
| 0.55 | 0.463 | 0.230 | -0.068 s |
| 0.65 | 0.346 | 0.267 | -0.032 s |
| 0.75 | 0.240 | 0.179 | -0.032 s |
| 0.85 | 0.135 | 0.102 | -0.028 s |
| 0.95 | 0.043 | 0.046 | +0.084 s |

- **The magnitude shrinks.** A discovered t0 that is early moves part of
  the 0.2 s window before the fault. The magnitude falls to a median 0.79
  of its known-onset value (minimum 0.31).
- **The decisions held.** XSYS-001's dynamics witness gave the same
  boolean in every A trial. In 3 B trials it became unevaluable (None) at
  the discovered onset. No decision changed, because 2.1.1's decision
  rests on the control and RPM witnesses.
- **The stock product carries the transient as context only.** It is read
  by no symptom, for this reason. In configuration B its state was ANOMALY
  in 55/55 A trials, known or discovered.
- **Four cases had an onset error above half the window (0.1 s)**, all at
  eta = 0.95. A detector with more delay, or a noisier vehicle, would put
  t0 outside the transient altogether.

**Conclusion.** Evidence with a 0.2 s validity window needs an onset
accurate to a fraction of 0.2 s. The product must not promote it to
profile evidence on a discovered onset. It does not.

## 5. Not established by this replay

- **Every case has one fault, on motor 0, in a hover.** Other motors are
  in `LOCALIZATION.md`, maneuvering in `FALSE_POSITIVES.md`.
- **The noise.** SIH is nearly noise-free, so timing on hardware will be
  worse. By how much is not known.
- **What it is not.** The replay is a benchmark of the product path. It
  does not change, extend or re-score XSYS-001.
