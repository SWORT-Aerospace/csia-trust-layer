# Configuration-transition study

**2026-09-30. Parts 13-17 and 49 of the shadow-validation brief.
NON-CONFIRMATORY.**

**Freeze first, then run.**
- **The design** (`TRANSITION_DESIGN.json`) was committed on its own in
  `e0fc81a`, before the runner existed. Its SHA-256 is `f84f8e5a…bc77c75`.
- **The runner** (`transition_study.py`) refuses to run if the design file
  changes, and records the hash in `TRANSITION_RESULTS.json`.
- **Nothing sealed was touched.** No simulator, profile or sealed file was
  changed.

## 1. Which transitions the repository can model credibly

| candidate | PX4 behaviour it corresponds to (PX4 `547e2ca`, V4) | can existing infrastructure model it? | done here |
|---|---|---|---|
| A. estimator lane / source switch | EKF2Selector changes the primary instance: it increments `instance_changed_count`, publishes the new instance's IMU device ids on `sensor_selection`, and resets every relative test ratio (`EKF2Selector.cpp` lines 111-140). Reset counters on `vehicle_local_position` (`xy_reset_counter`, `VehicleLocalPosition.msg` line 21) mark a position jump | **yes, at the evidence level.** The frozen aircraft profile has the estimator, its IMU dependency and the relations a lane switch changes (deadline, stability), and the NOMINAL run supplies every other record | **executed: experiment E1** |
| B. sensor source failover (GNSS loss and recovery with a position reset) | GNSS fusion stops (`estimator_status_flags.cs_gnss_pos`); on recovery a lateral reset increments `xy_reset_counter` | **no.** The profile has no estimator-innovation relation, so the evidence that goes stale across a reset (innovation test ratios) cannot be expressed without a new relation and an adapter from PX4 topics | **stopped at design** (§5) |
| C. controller mode change | a failsafe from position mode to altitude mode | **no.** No frozen profile models a controller mode | not attempted |
| D. control-allocation change | the allocator redistributes command after a rotor's effectiveness drops | **yes, with real data**: XSYS-001's sealed SITL flights are exactly this transition | **examined on the sealed data** (`XSYS_STATE_CONDITIONED_EXPLORATION.md`) |

## 2. E1: an IMU failure, then a lane switch

**How it is modelled.** The records are the frozen aircraft profile's NOMINAL
run, 60 ticks, edited as the frozen design specifies. The schedule:

| ticks | what is true |
|---|---|
| 0-19 | nominal |
| 20 | IMU0 fails. The estimator, still on lane 0 (IMU0), misses deadlines at ticks 20-24 and its stability degrades |
| 25 | the selector switches to lane 1 (IMU1). The estimator is healthy from here on. IMU0 is still broken |

**Two producers are modelled on real behaviour** (design §modelled_on):
- **A windowed deadline-miss counter.** It stays VIOLATED while a miss lies
  within its last 10 ticks, so it carries lane-0 content to tick 33.
- **An IMU0 health producer that publishes every 5 ticks.**

**The evidence-validity questions, answered for E1.**

| question | before the switch (20-24) | after the switch (25-59) |
|---|---|---|
| which evidence is valid | all of it | IMU0 health (it still describes IMU0, which is still broken); the estimator's current relations (lane 1) |
| which becomes stale | — | the deadline-miss counter's lane-0 content, ticks 25-33 |
| which should be recomputed | — | anything accumulated per lane: miss counters, test ratios. PX4 itself resets the relative test ratios on a switch |
| which is no longer admissible | — | estimator evidence computed on lane 0 |
| what stays admissible although old | — | IMU0 health between its publications: it is slow, not stale |

## 3. E1 results

"Stale symptom" means POSITION_UNAVAILABLE raised on a navigation function
after the switch, when nothing is unavailable.

| policy | attribution: correct UNIQUE / correct AMBIGUOUS / wrong / no evidence while a cause is present | stale symptom ticks | stale record-ticks admitted | valid record-ticks discarded | recovery tick |
|---|---|---|---|---|---|
| C: no validity management (2.1 today) | 26 / 14 / 0 / 0 | **9** | 9 | 0 | 34 (9 ticks late) |
| A: fixed age, 3 ticks | 25 / 7 / **1** / **7** | 3 | 3 | **8** | **never** |
| A: fixed age, 12 ticks | 26 / 14 / 0 / 0 | 9 | 9 | 0 | 34 |
| **B: configuration epoch** | **35 / 5 / 0 / 0** | **0** | **0** | **0** | **25 (at the switch)** |

**What 2.1 does with stale evidence** (policy C). For 9 ticks after the
switch, 2.1:
- SUPPORTS POSITION_UNAVAILABLE on POSITION_HOLD and PRECISION_NAVIGATION,
  localized to COMPUTE/estimator_stale, which is false: the estimator is
  healthy on lane 1;
- keeps the attribution AMBIGUOUS {state_estimator, source.imu0}. No wrong
  UNIQUE.

**Frozen v2.0 does exactly the same**, with COARSE_NAVIGATION as well
(checked tick by tick, 18-35). This is a limitation both share, not a 2.1
regression: neither has an admissibility layer.

**It is still a confidently wrong localization** that lasts as long as the
producer's memory. The promotion review counts it against criterion 12.

**The fixed-age rule fails both ways.**
- **Short (3 ticks):**
  - it drops the slow but valid IMU0 record for 1 tick in every 5;
  - so the attribution loses the true cause intermittently: 7 ticks of "no
    evidence" while IMU0 is broken, and 1 AMBIGUOUS without IMU0;
  - and it never settles.
- **Long (12 ticks):** it behaves exactly like no rule. The latched content is
  never older than 12 ticks.
- **No single age suits both producers.** It has to be tuned per producer and
  then fails whenever a producer's latency changes.

**The epoch rule is right here by construction.** Its result says something
real, though: it needs every configuration-derived record to carry the epoch
it was computed under. Section 4 names that field.

## 4. Time rule vs state rule: what the two experiments say together

**The question** (Part 17): can state-conditioned validity keep correct
evidence longer where appropriate, and drop it earlier where necessary?

| | E1 (modelled lane switch) | XSYS-001 (real SITL allocator transition, exploratory) |
|---|---|---|
| state signal | a discrete configuration epoch (the lane id) | a continuous, thresholded estimate: the compensation witness |
| does the state rule invalidate earlier where necessary? | yes, at the switch | yes: compensation is seen in the first 0.2 s window of all 55 genuine-loss trials, before the dynamics evidence turns misleading (0.4-1.9 s) |
| does it keep correct evidence longer? | yes: it keeps the slow IMU0 record that a short fixed window drops | **no**: in no-loss trials the short-window compensation estimate crosses its threshold spuriously and closes validity early, losing 64 % of correct UNIQUE trial-times. Used as evidence too, it produces wrong UNIQUE in 10 of 55 sensor-fault trials |
| fixed time rule | fails both ways for mixed-rate producers | works on this apparatus: 0 wrong, every correct UNIQUE kept |

**Conclusion (engineering, not a claim).**
- **When a state rule helps.** State-conditioned validity helps when the state
  is a **discrete, reported configuration fact**: a lane id, a reset counter,
  a selected-sensor id, a mode. PX4 publishes these directly.
- **When it hurts.** It harms when the state is itself an **estimated, noisy
  signal**, used outside the regime its threshold was calibrated for. The
  state estimate is evidence too, with its own validity, and it can be the
  same evidence as the thing it gates (XSYS: the allocator output both gates
  the dynamics and refutes the sensor hypothesis). That is loophole L12.
- **The fixed 200 ms window is not the answer to hard-code.** In XSYS the
  dynamics evidence stayed informative for 0.4-1.9 s, so 0.2 s was
  conservative. It worked because the apparatus's compensation onset is
  consistent, not because 200 ms is a law.

**Recommended form for the future admissibility layer.** Validity conditions
are declared per producer. There are two kinds:
- **invalidating events**, for discrete configuration facts (epoch changes,
  resets, mode changes);
- **maximum content age**, for plain staleness.

A condition based on an estimated state is allowed only when that state's own
producer declares the regime its estimate is valid in.

## 5. B (GNSS loss and recovery): the design, stopped before any data

**Why it stops here.** Executing it needs two new pieces of infrastructure, so
per Part 49 it stops at design:
- an estimator-innovation relation in a successor profile;
- an adapter from PX4 topics (`estimator_status.pos_test_ratio`,
  `estimator_status_flags.cs_gnss_pos`, `vehicle_local_position.xy_reset_counter`)
  to evidence records.

**The design.**
- **Apparatus:** PX4 SITL at `547e2ca` with its built-in failure injection
  (`SYS_FAILURE_EN`, `failure gps off` / `failure gps ok`). The simulator
  itself is unmodified.
- **Transition:** GNSS off at t0, on at t1; EKF2 stops GNSS fusion, then
  resets the lateral position on recovery.
- **Evidence:**
  - GNSS source freshness (`vehicle_gps_position` age);
  - innovation-test-ratio records (`estimator_status.pos_test_ratio`; low-pass
    filtered, so it carries pre-reset content);
  - position-validity flags.
- **Truth:** GNSS unavailable over [t0, t1). After the reset, no position
  fault.
- **Policies:** C none; A fixed age at two widths; B epoch = `xy_reset_counter`
  together with `cs_gnss_pos`.
- **Metrics:** as E1, plus the delay between the reset and the last stale
  innovation evidence admitted.
- **Status:** NOT RUN. It needs owner authorization, and its own frozen design
  file, before any flight.
