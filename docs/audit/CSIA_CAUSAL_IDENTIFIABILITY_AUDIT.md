# CSIA Causal Identifiability Audit

**Slice:** 3E Part 1–2 · **Date:** 2026-08-03 · **Baseline:** commit `d64225e`
**Method:** measured from repository source and executed simulation. No
inference.

---

## 0. Decisive finding — read this first

**The overlapping topology proposed for slice 3E has no physical basis in the
current simulation.** Specifically:

| Proposed path | Actual coupling in `csia/sensors/` | Verdict |
|---|---|---|
| `SENSOR_REGULATOR → GNSS` | **None.** `gps.py` reads only `truth.pos`, `truth.vel`, `truth.t`. There is no voltage, rail, or supply term anywhere in the model. | **DOES NOT EXIST** |
| `SENSOR_REGULATOR → MAGNETOMETER` | One weak term: `b_body[:,1] += 0.004 * truth.batt_i` — a hard-iron offset driven by battery **current**, not by rail voltage or health. | **NOT A FAULT PATH** |
| `MAIN_POWER_PACK → PROPULSION → MOTOR_ESC` | Real: `truth.motor_rpm` / `motor_current` derive from the same thrust profile as `batt_i`/`batt_v`. | **EXISTS** |

**Quantified:** across the whole 60 s flight, `batt_i` spans 0.7–23.1 A, so
the magnetometer's power-coupled offset spans **0.0029–0.0925 µT** against a
sensor noise floor of **σ = 0.03 µT** (`NOISE_UT`). At typical current the
power-induced offset is **below the noise floor**; at peak thrust it reaches
~3σ. And it tracks *thrust demand*, not rail health — so it is a load
signature, not a fault signature.

**Consequence.** Building `H_SENSOR_5V_RAIL` would require inventing a
`rail_brownout` fault kind whose signature I would design myself. I would then
benchmark a diagnostic architecture I designed against rule baselines I
designed, on a causal structure I invented. **Whoever designs the propagation
signature determines the winner.** That is not evidence about diagnostic
capability, and the resulting numbers must not be presented as such.

This audit therefore stops before the algorithm change, exactly as Part 1
instructs: *"Do not build an algorithm that claims to distinguish hypotheses
with identical observable signatures."*

---

## 1. Actual source topology (measured)

**Nodes (8):** `imu0`, `imu1`, `baro`, `mag`, `gps`, `motor_esc`, `battery`,
`vibration`.

**Edges (11):** `imu0↔imu1`, `imu0↔motor_esc`, `imu0↔gps`, `imu0↔mag`,
`imu1↔motor_esc`, `imu1↔gps`, `baro↔gps`, `baro↔battery`, `mag↔gps`,
`motor_esc↔battery`, `motor_esc↔vibration`.

**Shared-truth couplings that genuinely exist** (all sensors sample one
`FlightTruth`, so these are physically real inside the sim):

| Coupling | Mechanism | Strength |
|---|---|---|
| thrust → `motor_rpm`, `motor_current`, `batt_i`, `batt_v` | one thrust profile drives all | **strong** |
| `batt_i` → `mag` hard-iron offset | `0.004 × batt_i` µT | **below/near noise** |
| altitude → `air_temp` | lapse rate | weak |
| attitude → every body-frame sensor | `world_to_body` | strong |

**Fault injectors available (6 kinds):** `bias_drift`, `dropout`,
`emi_spike`, `gps_spoof`, `vibration_anomaly`, `power_sag`. Only `power_sag`
is multi-source, and it is applied *per target* — the "shared cause" is a
convention of the scenario, not a modelled rail.

**Signals absent entirely:** rail voltages, per-rail current, regulator health,
bus/timing signals, estimator innovations, estimator health, vehicle-reported
sensor status.

## 2. Hypothesis → evidence signature matrix

`+` expected LOW (degraded) · `·` expected unaffected · `?` not measurable.

| Hypothesis | batt V | prop response | GNSS | mag | inertial | sync onset | prop delay | topology | unaffected evid |
|---|---|---|---|---|---|---|---|---|---|
| `H_MAIN_POWER_PACK` | + | + | · | · | · | + | · | battery+motor_esc | imu/gps intact |
| `H_MOTOR_ESC` (single) | · | + | · | · | · | n/a | · | motor_esc | battery intact |
| `H_BATTERY_SENSOR` (single) | + | · | · | · | · | n/a | · | battery | motor intact |
| `H_IMU0_BIAS` | · | · | · | · | + | n/a | · | imu0 | imu1 intact |
| `H_MULTI_INDEPENDENT` | varies | varies | varies | varies | varies | **absent** | · | none | — |
| `H_UNKNOWN` | any | any | any | any | any | any | any | none | — |
| **`H_SENSOR_5V_RAIL`** (proposed) | ? | ? | **? no path** | **? sub-noise** | ? | ? | ? | **fictional** | — |

## 3. Pairwise identifiability

| Pair | Class | Basis |
|---|---|---|
| `MAIN_POWER_PACK` vs `MOTOR_ESC` | **IDENTIFIABLE** | battery-side evidence present vs absent |
| `MAIN_POWER_PACK` vs `BATTERY_SENSOR` | **IDENTIFIABLE** | propulsion response present vs absent |
| `MAIN_POWER_PACK` vs `MULTI_INDEPENDENT` | **IDENTIFIABLE_ONLY_TEMPORALLY** | the *only* discriminator is onset coherence; with simultaneous independent battery+motor faults the signatures are identical |
| `MOTOR_ESC` vs `BATTERY_SENSOR` | **IDENTIFIABLE** | disjoint indicator sets |
| `IMU0_BIAS` vs `IMU1_BIAS` | **PARTIALLY_IDENTIFIABLE** | `redundant_imu` drops for both; the motor edge that accompanies it names the unit |
| **`MAIN_POWER_PACK` vs `SENSOR_5V_RAIL`** | **INDISTINGUISHABLE_WITH_CURRENT_SIGNALS** | no GNSS power path exists; mag path is sub-noise. Both would have to be *authored*. |
| **`SENSOR_5V_RAIL` vs concurrent GNSS+mag faults** | **INDISTINGUISHABLE_WITH_CURRENT_SIGNALS** | identical observables by construction |
| `H_ESTIMATOR_DIVERGENCE` vs anything | **IDENTIFIABLE_ONLY_WITH_ADDITIONAL_SIGNAL** | no estimator output, innovations or health exist |
| `H_UNKNOWN` vs weak single-source | **PARTIALLY_IDENTIFIABLE** | separated only by the ≥2-relationship cross-sensor rule |

**Two of the structures slice 3E is built on are structurally
indistinguishable with current signals, and one requires signals that do not
exist.**

## 4. Minimum additional signals for the proposed topology

| Needed | PX4 / ArduPilot source | Present in repo? |
|---|---|---|
| Per-rail voltage (5 V / 3.3 V sensor rail) | `system_power` (PX4) / `POWR` (ArduPilot) | **No** |
| Regulator/servo rail current | `system_power.voltage5v_v`, `scaled_v3v` | **No** |
| GNSS receiver supply status | GNSS module status word | **No** |
| Estimator innovations / health | `estimator_innovations`, `estimator_status_flags` | **No** |
| Sensor status per instrument | `sensor_*_status` | **No** |

All five are **available in real PX4 logs** and none is currently parsed by
`csia/runtime/ulog_source.py`. That is the concrete path to making this
benchmark meaningful, and it is a data-ingest task, not an algorithm task.

## 5. What can honestly be claimed today

| Question | Answerable? |
|---|---|
| Upstream vs downstream within the power branch | **Yes** — `MAIN_POWER_PACK` vs `MOTOR_ESC` vs `BATTERY_SENSOR` are identifiable |
| Two-level propagation through *two* branches | **No** — the second branch does not exist |
| Shared cause vs concurrent independent faults | **Temporally only** — and simultaneous independent faults are indistinguishable |
| Estimator-level causes | **No** — no signals |
| Concurrent shared + independent (power + IMU) | **Yes, partially** — these use disjoint indicator sets, so it is a genuine and buildable test |

## 6. Recommendation

**Do not build Families A/B/C on an invented sensor rail.** Two buildable
directions rest on couplings that already exist:

1. **Concurrent shared + independent** (`MAIN_POWER_PACK` + `IMU0_BIAS`) —
   disjoint indicators, genuinely identifiable, directly tests multi-cause
   representation, which is the one capability a single-output rule cannot
   express. This is the strongest available test of the general architecture.
2. **Upstream vs downstream within the power branch**
   (`MAIN_POWER_PACK` vs `MOTOR_ESC` vs `BATTERY_SENSOR`) — real coupling,
   real discrimination, no fiction.

Both are worth running. Neither requires inventing physics. The overlapping
two-branch topology should wait until `system_power` and
`estimator_innovations` are ingested from real logs.
