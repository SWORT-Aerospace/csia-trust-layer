# The supervision layer — a loss-of-data rule the frozen core does not have

**What it fixes:** SR-001. The frozen failsafe alarms when a sensor's *trust*
falls, and for seven of eight sensors says nothing when the sensor stops
delivering at all.

**What it never does:** modify the frozen core, or lower a level the frozen
core raised.

---

## 1. The gap, counted from the frozen source

| sensor | references in `FailsafePolicy._conditions` | loss-of-data rule before |
|---|---|---|
| gps | 5 | **yes** — "GPS data invalid" |
| imu0 | 4 | no |
| imu1 | 3 | no |
| mag | 2 | no |
| battery | 2 | no |
| vibration | 2 | no |
| **baro** | **0** | no — *no rule of any kind* |
| **motor_esc** | **0** | no — *no rule of any kind* |

Every non-GPS rule is gated on `fresh.get(<sensor>)`, so a sensor that stops
delivering is *removed from supervision* rather than alarmed on. The sharpest
case is attitude:

```python
imus = [n for n in ("imu0", "imu1") if fresh.get(n)]
att  = max((T[n] for n in imus), default=1.0)      # <- both lost => 1.0
```

With neither IMU fresh, attitude confidence reads **1.000** and both attitude
rules become unreachable. Measured: both IMUs dropped for 40 s of a 90 s
flight, freshness correctly false for both, **frozen failsafe peak NORMAL for
the whole flight**.

## 2. Why an overlay and not an edit

`csia/runtime/failsafe.py` is inside `FROZEN_PATHS`. Editing it would break
the E1 freeze manifest, byte-equivalence to `csia-v1.0-research-final`, and
every claim descending from them. So the rule lives *above* the core, in the
same direction as `csia_assurance` and `csia_mission`. A test asserts the
frozen file still matches the tag.

## 3. The levels are derived, not chosen

Inventing a severity per sensor would be the retuning that must not happen.
Each level is read off the severity the **frozen config** already assigns:

| sensor | frozen rule it is derived from | loss level | provenance |
|---|---|---|---|
| mag | `heading_caution` → CAUTION | CAUTION | ANCHORED |
| battery | `power_critical` → CRITICAL | CRITICAL | ANCHORED |
| vibration | `struct_critical` → CRITICAL | CRITICAL | ANCHORED |
| imu0 / imu1 (one) | `imu_isolation` → CAUTION | CAUTION | ANCHORED |
| **imu0 + imu1 (both)** | `att_emergency` → EMERGENCY | **EMERGENCY** | ANCHORED |
| baro | *none exists* | CAUTION | **UNANCHORED — a choice** |
| motor_esc | *none exists* | CAUTION | **UNANCHORED — a choice** |
| gps | — | *deferred to the frozen rule* | — |

`baro` and `motor_esc` have no threshold in `FailsafeConfig`, so there is
nothing to derive from. **Those two levels are the only judgement in the
table**, and `DERIVED_FROM` labels them `UNANCHORED_THIS_IS_A_CHOICE` so a
reader can see which two numbers are mine. Timing is not invented either:
`dwell_up`, `arm_time` and the disarmed behaviour all come from the frozen
config, and freshness is whatever the frozen online layer already computed.

## 4. Measured effect

| case (40 s loss in a 90 s flight) | frozen | supervised |
|---|---|---|
| **both IMUs** | NORMAL | **EMERGENCY** |
| one IMU | NORMAL | CAUTION |
| battery + baro | NORMAL | CRITICAL |
| mag | NORMAL | CAUTION |
| motor_esc | NORMAL | CAUTION |
| GPS | CAUTION | CAUTION *(unchanged — not double-reported)* |
| **clean flight** | NORMAL | **NORMAL** |
| vibration *anomaly* (bad data) | CRITICAL | CRITICAL *(unchanged)* |

The clean-flight row is the one that decides whether this is an improvement or
a nuisance: **a loss-of-data rule that alarms on healthy flight would be worse
than the gap it fills.**

### Across 1000 generated variations

Each of the seeded multi-sensor variations run twice — frozen policy, then
frozen + overlay:

| | frozen | supervised |
|---|---|---|
| detected | 783 / 1000 | **969 / 1000** |
| still undetected | 217 | **31** |
| newly detected | — | 186 |
| **detections lost** | — | **0** |
| peak level raised | — | 255 runs |

**The zero is the one that matters.** The overlay computes
`max(frozen, supervisor)`, so it can only add urgency; a non-zero value there
would mean it had removed a detection the frozen core made, which the
composition forbids.

**What remains is a different class of miss.** Every one of the 186 newly
detected runs involved a `dropout` — exactly the absence-of-data mechanism
SR-001 named. The 31 still undetected are dominated by `bias_drift`:
degradation too weak to cross a frozen *trust* threshold. That is a threshold
question **inside** the frozen core, not a supervision gap, and it is not
retuned here.

## 5. Three safety properties, each with its own test

1. **It escalates where the frozen policy was silent** — SR-001 closed.
2. **It can only raise, never lower.** `effective = max(frozen, supervisor)`.
   A layer above the core must not be able to de-escalate a frozen safety
   decision.
3. **It does not fire when it should not** — clean flight, a sensor never
   fitted, before `arm_time`, while known-disarmed, or for a gap shorter than
   `dwell_up`.

## 6. One rule cannot be exercised here

`dropout` on the **vibration** node is live in the sampled stream and inert
after transport (SR-002): `SimulatedFlightSource` emits the 10 Hz RMS envelope
with a hardcoded `valid=True`, so `fresh["vibration"]` never goes false. The
rule exists and its level is anchored; what is missing is a way to *deliver*
the stimulus. That is a property of the simulator, not of this layer, and the
test says so rather than asserting an outcome the rig cannot produce.

## 7. Test sensitivity

Mutation score on `csia_supervision/dataloss.py`, same targets, seed and 16
sites throughout — only tests added:

| | score | killed |
|---|---|---|
| first pass | 0.6875 | 11 / 16 |
| after five boundary tests | 0.9375 | 15 / 16 |
| after the exact-subset test | **1.000** | **16 / 16** |

The survivors were all boundaries — `<` vs `<=` at `arm_time`, at `dwell_up`,
the `fresh.get` default, proper-vs-improper subset on `ever_fresh`, and
once-per-condition action issuing. The last needed a vehicle whose *only*
ever-fresh nodes are the two IMUs, which is the only case where subset and
proper subset differ.

## 8. What this does not change

CSIA remains **advisory, with no command authority**. This changes what the
trust layer would *raise*, not what any vehicle would do. The frozen core is
byte-identical to `csia-v1.0-research-final`, and the recorded stress baseline
still describes the frozen policy alone — `run_profile(supervised=True)` is an
explicit request to measure a different system.
