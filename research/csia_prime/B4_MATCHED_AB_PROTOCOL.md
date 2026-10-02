# The matched physical A/B experiment: frozen protocol (PRIME Tracks B3-B5)

**2026-10-02. FROZEN BEFORE ANY HARDWARE EXISTS.**

**Hold point:** the first fault run needs, in this order:
1. the owner's written authorization of each RB2 stage;
2. the nominal corpus (section 6), recorded and frozen;
3. the bench producer adapter, built from the contract in
   `contracts_draft/bench_loadcell_thrust_response.json` and committed with
   its test;
4. this protocol's hash recorded in the run log before run 1.

Nothing below changes after the first fault run. Any change is a new,
separately labelled protocol.

## 1. The question

**CAN CSIA DISTINGUISH PHYSICAL ACTUATOR DEGRADATION (A) FROM TELEMETRY
CORRUPTION ON A PHYSICALLY HEALTHY ACTUATOR (B), USING INDEPENDENT
CROSS-SYSTEM EVIDENCE?**

AMBIGUOUS or "unresolved" is a correct answer where the evidence is
insufficient. UNIQUE is not forced.

## 2. Why this bench needs one producer that does not exist yet

**On an open-loop bench the stock product has no independent witness**
(`PRIME_EXECUTION_PLAN.md`, section 2):
- the allocator compensation needs a closed loop;
- ESC current shares the ESC MCU with ESC RPM.

**So the load cell enters as a 2.2 external witness producer,** exactly as
XSYS-001's witnesses do:
- its own contract;
- its own lineage root (`sensor:loadcell.0`);
- one existing record, `ACTUATION/motor_m:actuation.physical_response`.

**No 2.1.1 semantics change.** The record and its predicates are already in
the multirotor-quad r1 profile. Only the producer is new, and it is built
when bench data exists (reality-first rule 5).

## 3. Channels: evidence versus ground truth

| channel | instrument | role | lineage root |
|---|---|---|---|
| motor command | PX4 `actuator_motors` (and the DShot frame on the logic analyzer) | evidence input | `channel:motor_command.motor_m` |
| ESC RPM | ESC telemetry, `esc_status` | **evidence** (the claim under test) | `sensor:esc.<n>` (the ESC MCU) |
| ESC current | ESC telemetry | evidence; **not independent of ESC RPM** (same MCU) | `sensor:esc.<n>` |
| bus voltage and current | PX4 power module, `battery_status` | context (presence semantics today) | `sensor:power_module.0` |
| thrust | load cell (single axis) | **evidence**, through the bench producer | `sensor:loadcell.0` |
| rotor speed | optical tachometer on the logic analyzer | **ground truth only** | — |
| bus current | shunt on the logic analyzer | **ground truth only** | — |
| condition | the experimenter's run sheet | **ground truth only** | — |
| vibration | the FC's IMU on the stand | recorded; not used in the decision | `sensor:imu.<id>` |

**The rule:** no channel is both evidence and ground truth. The tachometer
confirms whether the motor really changed. The run sheet says what was done.

## 4. Apparatus

The RB-001 design (`MINIMUM_PHYSICAL_EXPERIMENT.md`), with **two**
identical motor/ESC pairs:
- **motor_0** is the test motor, on the load-cell stand;
- **motor_1** is the reference, on a fixed mount.

Two are needed because the telemetry producer's statistic is normalised by
the other motors.
- **Power:** a current-limited bench supply (≤ 5 A per stage RB2-1), no
  battery.
- **Drive:** PX4's actuator test from a scripted sequence. The FC is
  configured as a quad, with outputs 3-4 unconnected and their telemetry
  offline (UNAVAILABLE, not healthy).
- **Safety:** a propeller only inside the guard. Commands at most 60 %. A kill
  switch on the supply.

## 5. Conditions (all reversible)

| id | condition | how | ground-truth signature | levels |
|---|---|---|---|---|
| N | nominal | — | tachometer and thrust as the nominal corpus | — |
| **A** | physical degradation | PX4 output scaling on motor_0 (PWM maximum, or the DShot output limit), set between runs | **tachometer RPM falls, thrust falls** at the same `actuator_motors` command | effectiveness η = 0.85, 0.75, 0.60, set from the nominal thrust-per-command curve |
| **B-phys** | telemetry corruption, physically healthy | **the ESC telemetry's motor pole count set wrong** between runs (PX4's DShot telemetry pole-count parameter; its name is checked on the board's firmware before run 1). Reported RPM scales by true/configured poles | **tachometer and thrust unchanged;** only the reported RPM moves | configured pole counts nearest to RPM ratios 0.922, 0.866, 0.775 (√η of the A levels); for a 14-pole motor: 15 → 0.933, 16 → 0.875, 18 → 0.778 |
| B-syn | telemetry corruption, offline | the logged RPM of a nominal run scaled by √η after the run | as N | the A levels exactly; labelled **REAL DATA WITH SYNTHETIC CORRUPTION**, secondary analysis only |

**B-phys is the primary B.** It is a real configuration error that real
teams make. It corrupts the telemetry without touching the motor, so it is
the physical counterpart of XSYS-001's case B.

## 6. Nominal corpus first (B5; frozen before any fault run)

| factor | levels |
|---|---|
| temperature | cold start; warm (10 min at 40 %) |
| supply | 3 voltages within the ESC rating |
| command | 20, 40, 60 % steps; a 20-60 % ramp |
| duration | 60 s; 5 min |
| motors | motor_0 and motor_1, swapped between stands once |
| mounting | removed and remounted between blocks |
| repeats | 5 per cell |

**Calibration (prospective, from N runs only):**
- every statistic's distribution;
- its temperature and supply slopes;
- run-to-run spread.

**Thresholds:**
- the rule is 2.3's: 2 × the largest null value, with the 99.9th
  percentile reported beside it;
- a statistic whose null moves with temperature or supply gets a validity
  condition, not a looser threshold;
- **no SITL threshold is used.**

## 7. Matching rule

**L is the telemetry producer's local symptom:** the RPM deficit as a
fraction of the thrust it implies.

- **A B-phys run matches an A level** when its median L over the hold
  steps is within **±0.03 absolute** of the median L of that A level's
  runs.
- **B-phys runs that do not match are reported, not dropped,** and are
  excluded from the matched comparison.
- **B-syn matches by construction.**

## 8. Decision rule (per run, applied by `ab_scoring.py`; frozen)

**For motor_0, from the product's report** (the bench configuration: stock
producers plus the load-cell producer):

| class | when |
|---|---|
| **A_CONFIRMED** | `COMMAND_NO_RESPONSE|motor_0` raised at any time, with `actuation.physical_response` VIOLATED from the load-cell producer |
| **TELEMETRY_ONLY** | `esc.telemetry_response` DEGRADED, `actuation.physical_response` NOMINAL, and no symptom on motor_0 |
| **UNRESOLVED** | physical response UNAVAILABLE or NOT_APPLICABLE (the evidence is insufficient; a correct answer when it is) |
| **NO_CHANGE** | telemetry NOMINAL and no symptom |

**Errors:**
- **B_AS_A:** a B run classified A_CONFIRMED;
- **A_AS_B:** an A run classified TELEMETRY_ONLY;
- **WRONG_UNIQUE:** any UNIQUE attribution whose candidate is not the
  run sheet's cause;
- **WRONG_MOTOR:** any symptom on motor_1.

## 9. Sample count

**N:** the corpus above, 5 repeats per cell.

**A:** 10 runs per η level (30).

**B-phys:** 10 runs per matched level (30).

**Why 10 per level:**
- with zero errors in 30 runs of one class, the 95 % upper bound on that
  class's per-run error rate is 3/30 = 10 % (rule of three);
- pooled over 60 fault runs, it is 5 %.

**Order:** randomised within blocks of 6 runs (2 N, 2 A, 2 B-phys), from a
seed recorded before run 1, so that warm-up and supply drift are not
confounded with condition.

## 10. Success and failure (frozen)

| | criterion |
|---|---|
| S1 | **zero B_AS_A** over all B-phys runs (and, secondarily, B-syn) |
| S2 | every A run at an η whose expected thrust deficit exceeds the nominal-derived resolution is **A_CONFIRMED**. At most 1 in 10 per level may be UNRESOLVED, and only with a recorded cause (e.g. a load-cell dropout). **Zero A_AS_B.** |
| S3 | **zero WRONG_UNIQUE, zero WRONG_MOTOR** |
| S4 | the report counts the load cell and the ESC telemetry as **2 independent lines**, and ESC RPM with ESC current as **1** (Part 25's correlated case) |
| S5 | the local symptom is present in both A and B-phys (telemetry DEGRADED); otherwise the comparison is not matched |

**PASS** is S1-S5 all holding, giving gate PRIME-C
`MATCHED_PHYSICAL_SEPARABILITY_SUPPORTED`, within this bench's limits.

**The STOP conditions:**
- **any B_AS_A or WRONG_UNIQUE:** the product would mislead an engineer;
- **S4 failing:** stop condition 5, lineage disagreeing with the hardware.

**What a PASS would not say:**
- nothing about flight;
- nothing about the closed-loop compensation, which needs RB5;
- nothing about other ESCs or motors.
