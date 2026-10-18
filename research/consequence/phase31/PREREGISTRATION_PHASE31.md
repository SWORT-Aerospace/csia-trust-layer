# Phase 3.1 — actionability-precondition study (preregistered amendment)

**Written and committed before the Phase-3.1 `locked` partition is opened.**
Everything below — reachability inventory, scenarios, criteria, thresholds,
seed count, statistical test, confidence interval, stopping rule and pooling
rule — is frozen at this commit and may not change after locked results are
inspected.

**Phase 3 is not reopened and not re-analysed.** Its locked result stands as
recorded: H2 NOT SUPPORTED, H3 not testable, all three policies identical,
`3/24` versus `1/24` at exact McNemar **p = 0.625**. That number does not move.

**Scope: deterministic simulation only.** No hardware, no RF, no armed
physical vehicle, no real actuator, no flight, no SITL execution. Evidence
level `MODEL_BASED_ACTION_CONSEQUENCE`, exactly as in Phase 3.

---

## 1. Measured starting state

| item | value |
|---|---|
| HEAD | `4cc60ebc396f7176550c154ac3ce7956e7850d54` |
| Phase-3 design freeze | `d2a5ee9a62978be35e91380bf036a6aea3020155` |
| working tree | clean |
| frozen core | 12 of 12 match `docs/v1/FROZEN_BASELINE.json`, 0 mismatches |

### Frozen inputs, hashed

| artifact | sha256 |
|---|---|
| `research/consequence/results/GATE_INVENTORY.json` | `fa09d82c321b31e3766e93534380de1d72bdc96a0bb426bc7633bc7254a85059` |
| `research/consequence/results/INDEPENDENT_GATE_EVALUATION.json` | `9dc8eb2e84d48aae30fc9e189ac889282149f1ac3185e3205f904d9328e9740c` |
| `research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json` | `d1e911ba6d770d5afa5ab542d1fe037be8a538a9a29f0a5589a77551c27dd3e3` |
| `research/consequence/phase3/results/PHASE3_TRACES_LOCKED.json` | `78d132988a38ad9fb16c5b85ff7f91e51df78c31b27d596469a49cfdfa238b57` |
| `research/consequence/phase3/results/PHASE3_EVALUATION_LOCKED.json` | `021959060591e91e0a68f4101ffdc5c13b17126c1475d434979314d8c34b1918` |
| `research/consequence/phase3/PREREGISTRATION_PHASE3.md` | `d3fd5dc4d8a20b0f383407e91e9c55d3f6bd737fc48352cd85206a08a142b5be` |

**The eight Phase-2 candidates are frozen and are not replaced.** Phase 3.1
adds no candidate and removes none. It asks a different question about the
same architecture.

## 2. The pooling rule, stated before execution

**Phase-3.1 results are NOT pooled with Phase-3 results.** They use disjoint
seed partitions, different fault families, a different question and a
different unit of analysis. No combined count, rate, p-value or confidence
interval over both campaigns may be computed or reported. Where both are
mentioned, they are reported side by side with their partitions named.

## 3. Task 1 — inventory of fault families and policy transitions

### Fault families the frozen injector supports

`csia/sensors/faults.py` `KNOWN_KINDS`: `bias_drift`, `dropout`,
`emi_spike`, `gps_spoof`, `vibration_anomaly`, `power_sag`. Nothing is added;
adding a kind would be a change to shared sensor code and is out of scope.

### Policy transitions the frozen failsafe can make

Read from `csia/runtime/failsafe.py` `_conditions`, not restated from memory:

| condition | level | trigger | actions |
|---|---|---|---|
| `imu_isolated` | `CAUTION` | gap > 0.12 **and** min(T) < 0.85 **and** selection would change | `SELECT_IMU` |
| `nav_degraded` | `CAUTION` | `T[gps] < 0.75` fresh, or GPS stale after being monitored | `SWITCH_NAV_INERTIAL`, `INHIBIT_GPS_MODES` |
| `heading_degraded` | `CAUTION` | `T[mag] < 0.60` fresh | `HEADING_HOLD_GYRO` |
| `attitude_degraded` | `CRITICAL` | max(T[imu0], T[imu1]) < 0.82 | `PREPARE_LANDING`, `LIMIT_MANEUVERS` |
| `power_fault` | `CRITICAL` | `T[battery] < 0.70` fresh | `REDUCE_POWER`, `LAND_NOW` |
| `structural` | `CRITICAL` | `T[vibration] < 0.60` fresh | `LIMIT_THROTTLE`, `LAND_SOON` |
| `attitude_lost` | `EMERGENCY` | max(T[imu0], T[imu1]) < 0.70 | `STABILIZE`, `CONTROLLED_DESCENT`, `BROADCAST_MAYDAY` |

De-escalation issues `RESUME_NORMAL` after `dwell_down = 5.0 s`.

## 4. Task 2 — which levels are reachable, measured on development seeds

Armed, airborne, physically consistent. Measured by running the frozen trust
layer and the frozen failsafe over the catalog scenarios:

| scenario | max level | first action |
|---|---|---|
| `clean`, `high_speed_dash`, `imu0_bias_drift` | `NORMAL` | none |
| `gps_spoof` | `CAUTION` | `SWITCH_NAV_INERTIAL` @ 24.24 s |
| `gps_dropout` | `CAUTION` | `SWITCH_NAV_INERTIAL` @ 26.04 s |
| `mag_emi` | `CAUTION` | `HEADING_HOLD_GYRO` @ 29.12 s |
| `power_sag` | **`CRITICAL`** | `REDUCE_POWER`, `LAND_NOW` @ 33.80 s |
| `vibration_anomaly` | **`CRITICAL`** | `LIMIT_THROTTLE`, `LAND_SOON` @ 34.20 s |
| `dual_imu_failure` | **`EMERGENCY`** | `PREPARE_LANDING` @ 34.20 s, `CONTROLLED_DESCENT` @ 49.44 s |

**Stronger-than-`CAUTION` responses are reachable.** Phase 3's inability to
exercise them was a **scenario-selection limitation of Phase 3**, not a
structural limitation of the architecture, and the Phase-3 write-up's
"removal action 1" is hereby answered: the fault families already exist.

## 5. Task 3 — minimum magnitude and duration to cross each transition

Swept on a development seed, `imu0` accel-z `bias_drift` from t = 15 s:

| duration | ESC telemetry present | ESC telemetry absent |
|---|---|---|
| 10 s | no crossing at any rate up to 0.25 | no crossing at any rate up to 0.25 |
| 20 s | `CAUTION` + `SELECT_IMU` from rate ≥ 0.05 | **`CRITICAL`** from rate ≥ 0.03 |
| 40 s | `CAUTION` + `SELECT_IMU` from rate ≥ 0.03 | **`CRITICAL`** from rate ≥ 0.03 |

Two things are recorded rather than smoothed over:

- **Duration is the binding constraint, not magnitude.** No rate up to 0.25
  crosses anything in 10 s. `dwell_up` is 1.0 s, so the limit is how long the
  trust estimate takes to move, not the dwell.
- **Crossing time is not monotone in fault rate.** Rate 0.12 crosses at
  26.96 s; rates 0.18 and 0.25 cross later, at 34.84 s and 29.88 s. A larger
  fault is not detected sooner here. That is a property of the frozen
  detector and it is reported, not explained away.

## 6. The reachable precondition for the support-aware policy

P2 can only act when an **attributing** response is issued while the pair it
discriminates is not identifiable. Phase 3 never reached that state. Phase 3.1
identifies a configuration that does, and it is physically consistent:

**ESC telemetry absent.** `csia/runtime/online.py` computes every edge as
`E[key] = (lam, gate * fresh[a] * fresh[b])`, and both `accel_motor_current`
and `accel_esc_rpm` have `motor_esc` as an endpoint. An airframe that does not
report ESC telemetry — a case the frozen core's own comments contemplate, "a
flight log without ESC telemetry" — drives **both** gates to zero while armed,
airborne and past `arm_time`. This is not the disarmed control that Phase 3
used and excluded; nothing about it is physically inconsistent, and no
disarmed-gate scenario is used as operational evidence anywhere in Phase 3.1.

Measured on development seeds: with ESC absent, `SELECT_IMU` is issued at
t ≈ 53–56 s while `decision_pair_support` reports `NON_IDENTIFIABLE` and both
gates read 0.0. **The precondition is reachable.**

### The structural reason, at `SOURCE_ANALYSIS`

`csia.diagnosis.causal.SOURCE_INDICATORS` gives `imu0: (redundant_imu,
accel_motor_current)` and `imu1: (redundant_imu, accel_esc_rpm)`. It does
**not** list `velocity_gps_doppler_0` and `velocity_gps_doppler_1`, which are
also per-IMU-asymmetric and whose gate reads 1.0 in these runs.

So the trust engine can isolate an IMU on evidence the attribution model does
not know it has. The support classifier takes its LOW-sets verbatim from
`SOURCE_INDICATORS`, so it reports `NON_IDENTIFIABLE` in a state where the
system does in fact identify. **This is a finding about the frozen core's
attribution model and it is not fixed here** — the core is frozen, and
changing `SOURCE_INDICATORS` would invalidate Phase 2 and Phase 3.

## 6.1 Seed partitions

`csia_consequence/phase31_partitions.py`, domain
`csia/actionability_precondition_phase31/2026-09-20`, disjoint by construction
from the phase-one, follow-up (including companions), Phase-2 and **Phase-3**
partitions. Disjointness from Phase 3 is what keeps the two campaigns
independent and makes the pooling rule in §2 enforceable rather than
aspirational.

| partition | seeds |
|---|---|
| `development` | 12 |
| `validation` | 16 |
| `locked` | **40** (sealed; the call site must say it is opening it) |

Manifest hash: `713abd66227760d954435859a7fb71d352eb1dc03b444e0fc25e0b2e252433bf`

### Constants added by Phase 3.1

Phase 3's constants are imported unchanged and are not re-tuned. Two are new,
and both are declared as zero so that no drift number is invented for a fault
that does not move the vehicle:

| constant | value | meaning |
|---|---|---|
| `DRIFT_POWER_MPS` | 0.0 | a sagging pack causes no attitude error, so no horizontal drift |
| `DRIFT_STRUCT_MPS` | 0.0 | a rotor-vibration anomaly likewise |
| `MIN_CONSEQUENCE_M` | 5.0 | see §7; the minimum modelled position-error difference that counts as a consequence |

## 7. Hypotheses and predeclared criteria

### A1 — the actionability precondition

> There exists a physically consistent, reachable scenario in which an
> attributing response is issued while the pair it discriminates is reported
> not identifiable.

**Killed if:** no locked scenario issues `SELECT_IMU` with
`pair_support != IDENTIFIABLE` while airborne.

### A2 — direction of the support-aware policy's effect

> Where A1's precondition holds, withdrawing the attribution either prevents
> an incorrect actionable decision (P2 helps) or withdraws a correct one
> (P2 causes a false refusal).

**Both directions are predeclared.** The development sweep found `SELECT_IMU`
choosing `imu1` — the good unit — in every ESC-absent case inspected, which
points at **false refusal**. The locked run tests that on unseen seeds, and a
result in the other direction is reported as readily.

**A2 is not a hypothesis about safety.** A false refusal is a capability cost,
not a hazard, and a prevented incorrect attribution is not a safety guarantee.

### Predeclared thresholds

| quantity | value | why this value |
|---|---|---|
| minimum action-conflict criterion | the set of **issued response classes** differs from the correct response's class (`RESPONSE_CLASS` in the Phase-3 independent evaluator, unchanged) | class difference is the Phase-3 materiality rule; reusing it keeps the two campaigns commensurable even though they are not pooled |
| `MIN_STATE_S` | 1.0 s | applies to **state-like** measures only — ambiguity and abstention time — not to issued actions. See §7.1 |
| minimum scenario duration | 60.0 s flight, fault duration ≥ 20.0 s | §5: no rate up to 0.25 crosses any transition in 10 s |
| minimum consequence magnitude | `MIN_CONSEQUENCE_M = 5.0 m` of modelled position-error difference between the compared policies | below this the difference is smaller than the geofence margin's own resolution in this model and is not called a consequence |
| required paired seeds | **40** locked, paired by seed across conditions | a zero count over 40 gives a Clopper–Pearson 95 % upper bound of 0.0881; over Phase 3's 24 it would be 0.1425 |
| statistical test | exact two-sided McNemar on discordant pairs, α = 0.05 | same test as Phase 3, so the two are readable side by side |
| confidence interval | Clopper–Pearson 95 %, two-sided, on the per-scenario conflict rate | exact; does not degenerate at a zero count, which is the outcome this study most has to be able to report |
| stopping rule | run all 40 locked seeds, once. **No interim looks, no extension, no seed added after any result is seen.** | |

### 7.1 The span rule, declared because a development run showed it matters

A run-length segment records `t_start`, `t_end` and `ticks`. Phase 3 measured a
segment's duration as `t_end - t_start`, which is **one tick short** and is
exactly **zero** for a single-tick segment. 1212 of Phase 3's 4200 locked
segments are single-tick.

That matters here in a way it did not in Phase 3, because the frozen failsafe
issues each action **once**: `SELECT_IMU` appears as the response label for a
single tick and then the label reverts. Any duration threshold applied to the
response label would discard every attributing action in the study.

Two consequences, both declared before the locked run:

1. **Phase 3.1 measures a segment's duration as `ticks / TICK_HZ`.** Phase 3's
   numbers are not recomputed; its campaign and evaluator are untouched.
2. **The action-conflict criterion is defined on issued actions, not on how
   long a response label persists.** An action issued once holds; a duration
   threshold on it would measure the logging format rather than the decision.
   `MIN_STATE_S` therefore applies only to ambiguity and abstention time.

**Phase 3's headline numbers are unaffected, and that was checked rather than
assumed.** Across all 4200 locked segments there are **zero** in which an
attributing response coincides with a non-identifiable pair while airborne,
so `unsupported_confidence_scenarios = 0` holds under either span rule. What
the defect does affect is Phase 3's reported ambiguity and abstention
*durations*, which are under-counted by one tick per segment. Phase 3's
abstention total is 0.0 s and stays 0.0 s; its ambiguity total of 1152.0 s is
a lower bound. No Phase-3 conclusion rests on it, and Phase 3 is not re-run.

## 8. Scenarios

Three fault families, chosen because §4 shows they reach three different
levels, and one gating variable per family. All armed from t = 0, airborne
from t = 5.0 s, `hover_circle`.

| family | fault | correct response under latent truth | why it is here |
|---|---|---|---|
| `imu_isolation` | `imu0` accel-z `bias_drift`, rate 0.12, 15.0–55.0 s | `SELECT_IMU1` | the only family that produces an attributing response |
| `power` | `power_sag` depth 1.2 V + 350 rpm, 30.0–50.0 s | `PREPARE_LANDING` | reaches `CRITICAL` |
| `structural` | `vibration_anomaly` gain 3.0, 28.0–48.0 s | `PREPARE_LANDING` | reaches `CRITICAL` by a different route |

Conditions, matched by seed:

| id | condition |
|---|---|
| **N** | nominal — no fault |
| **EA** | fault, **evidence applicable** — ESC telemetry present |
| **EG** | fault, **evidence gated** — ESC telemetry absent, physically consistent |
| **FP** | condition EG evaluated under P1, the freshness-path policy |
| **SA** | condition EG evaluated under P2, the support-aware policy |

FP and SA are policy readings of the EG stream, not separate streams: all
three policies consume one pass of the trust layer, as in Phase 3.

**No disarmed-gate scenario appears anywhere in Phase 3.1**, as an experimental
condition or as a control.

## 8.1 Which modelled consequences are physically meaningful, declared per family

The Phase-3 consequence model is reused unchanged. Its constants are not
re-tuned and its file is not edited — Phase 3.1's additions live in
`csia_consequence/consequence_model31.py` so that Phase 3's SHA-256 manifest
still describes the state Phase 3 was committed at.

Two of the three families here do not cause an attitude error, so a drift rate
for them would be invented, not modelled:

| family | drift rate | position error meaningful? | what IS meaningful |
|---|---|---|---|
| `imu_isolation` | `DRIFT_IMU_MPS = 1.20` (Phase 3's, unchanged) | **yes** — an undetected attitude bias does move the vehicle | position, altitude, geofence |
| `power` | **0.0** | **no** | time to safe state |
| `structural` | **0.0** | **no** | time to safe state |

**The energy margin is declared NOT physically meaningful for any family in
this model**, in advance. `ENERGY_FULL_S` is a fixed endurance and no fault in
the model consumes energy differently, so the column measures airborne time
and nothing else. A battery model that responded to a power sag would be a new
model, and inventing one after seeing which columns were empty is exactly the
retrofitting this amendment forbids. The column is still recorded, and it is
labelled.

**Time to safe state is the field Phase 3 could not populate.** Phase 3's
write-up records that as its first removal action; the `power` and
`structural` families issue `LAND_NOW` and `LAND_SOON`, which the model turns
into a descent, so Phase 3.1 populates it.

## 9. What Phase 3.1 may not conclude

No hardware, SITL, HIL or flight validation. No safety guarantee, in either
direction: neither that P2 is safe nor that withdrawing an attribution is
safe. No statement that any vehicle behaved in any way. No universal
prevalence — three fault families, one airframe profile, one trajectory. No
novelty, no certification, no airworthiness. Nothing about the five Phase-2
candidates that remain outside the frozen core's exposed interface.

**If no reachable action conflict is found, the report says
`NO_ACTIONABLE_CONSEQUENCE_REACHABLE_UNDER_CURRENT_MODEL` and that is not
proof of safety.** It is a statement about three fault families in one model.
