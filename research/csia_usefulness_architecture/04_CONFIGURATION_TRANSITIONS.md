# Configuration transitions, context model and invalidation (Phases 5, 27, 28)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`. The full per-transition table is `TRANSITION_MATRIX.csv`
(28 transitions).

## 1. Phase 5: which autonomy interventions change evidence semantics

For each of 28 transitions across controller, estimator, sensor, power,
planner and compute, `TRANSITION_MATRIX.csv` answers:

- which evidence remains valid;
- which becomes stale;
- which becomes invalid;
- which needs recomputation;
- which assumption changed;
- where the transition is observable;
- which context dimension carries it.

**What the table shows.**

1. **Most transitions invalidate a narrow slice of evidence.** An EKF lane
   switch invalidates estimator-derived accumulations and evidence tied to
   the old lane's IMU. It leaves raw power, compute and actuator-telemetry
   evidence intact.

   A global flush on every transition would throw away most admissible
   evidence, which widens ambiguity for no reason. That is the case for
   **targeted** invalidation. It is also the hypothesis that
   `14_FIRST_EXPERIMENT.md` has to test, because a global flush is the
   obvious simple baseline.
2. **Several transitions are observable from messages fielded autopilots
   already publish** (V4):
   - PX4 reset counters and deltas, sensor-selection device ids, estimator
     aiding flags, `solution_status_flags` (S055, S056);
   - PX4 allocator motor-failure handling (S034);
   - ArduPilot lane-switch reset data (S057).

   CSIA does not need to infer them.
3. **Some are not observable on standard telemetry** (UNCLEAR in the table):
   - gain-set changes;
   - anti-windup state;
   - covariance-only resets;
   - calibration changes;
   - thermal limiting;
   - load shedding;
   - ArduPilot's first-usable-accelerometer switch behind `VIBRATION` (S025).

   For these, the honest behaviour is `UNKNOWN` admissibility for evidence
   whose contract depends on them. Assuming "unchanged" is not acceptable.
4. **A reduced-demand trajectory invalidates nothing** but lowers
   diagnosability. That is an **information-need** matter, and it is
   delegated to active diagnosis (`11_TARGET_ROLE_AND_NON_GOALS.md` §3),
   not handled by invalidation.

## 2. Phase 27: the minimum runtime context

A context field is kept only if some contract can name it in `requires` or
`invalidated_by`. The autopilot's state is **not mirrored**: CSIA reads each
field from a published message and estimates none of them.

| context dimension | type | read from (PX4) | read from (ArduPilot) | used by |
|---|---|---|---|---|
| `t` | vehicle time (µs) | `timestamp_sample` (S055) | message time | windows, age |
| `armed`, `airborne` | bool | vehicle status; `CS_IN_AIR` (S055) | HEARTBEAT; land-detector state | enable conditions |
| `flight_mode` | enum id | nav state | custom mode | enable conditions; mode-dependent witnesses |
| `controller_config_hash` | hash | parameter set hash (host-computed at load) | same | response-envelope witnesses (FM-17) |
| `allocation_epoch` | counter | increments on `handled_motor_failure_mask` or effectiveness update (S034) | motor-mask change (UNCLEAR on telemetry) | command-side witnesses |
| `controller_degraded_flags` | bitset | allocator saturation | vibration compensation (log only; UNCLEAR on MAVLink) | FM-11 |
| `estimator_instance` | small int | `EKF2Selector` selected instance (S056) | EKF3 primary lane (S057) | estimator-derived evidence |
| `estimator_reset_counters` | small ints | xy, z, vxy, vz, heading, quaternion (S055, S056) | yaw and position reset counts (S057) | accumulated statistics |
| `aiding_sources` | bitset | `control_mode_flags` (S055) | EKF status flags | estimator-derived evidence |
| `attitude_solution_valid` | bool | `solution_status_flags` (S055) | EKF status | enable conditions |
| `imu_selection` | device ids | `accel_device_id`, `gyro_device_id` (S055) | UNKNOWN for the `VIBRATION` path (S025) | source identity (FM-29) |
| `sensor_presence_health` | three bitmaps | MAVLink SYS_STATUS present, enabled, health (S054) | same | producer health (FM-15) |
| `power_limit_active` | bool | UNCLEAR | throttle-ceiling state (G02 package, V4; S035) | actuation evidence |
| `compensation_active` | bool | **derived by a CSIA producer** from the command-side witness (W_CTRL-type), declared with its own contract | same | the XSYS-001 lesson (FM-11) |
| `config_version` | hash | deployment configuration hash (S017) | same | FM-17 |
| `contract_set_hash` | hash | host-computed at load | same | FM-27 |

That is 16 dimensions. Every one is either read from a message or derived
by a declared producer.

**`compensation_active` is the exception that proves the rule.** No
autopilot publishes it, so it is **evidence**, produced by a registered
producer with a contract, not a context fact. A contract that depends on it
therefore depends on another piece of evidence. That dependency is recorded
like any other (`05_PROVENANCE_AND_DEPENDENCE.md`).

**Context is itself evidence about the vehicle, so it gets the same
discipline:**

- **Freshness.** Each dimension has a maximum age. A dimension beyond it is
  `UNKNOWN`.
- **Plausibility.** Reset counters must be monotone modulo wrap. Device ids
  must agree with SYS_STATUS presence.
- **Stability.** Repeated flips within a hold-off make the dimension
  `CONTEXT_UNSTABLE` (FM-30). ArduPilot applies a 5 s hold-off to its own
  lane switches (S057).

## 3. Phase 28: the invalidation engine

### 3.1 Data structures

These are sized for the embedded target. Numbers are design limits to be
benchmarked, not measurements.

| structure | form | purpose |
|---|---|---|
| context vector | 16 small fields plus a per-dimension **epoch** counter | each change increments that dimension's epoch |
| evidence slot table | fixed array of N slots (design limit N ≤ 256) | live records |
| per-slot `dim_mask` | bitmask over the 16 dimensions (from the contract's `invalidated_by`) | which transitions touch this record |
| per-slot `tag_mask` | bitmask over interned dependency tags (design limit 64 or 128) | dependency invalidation and refutation independence |
| inverted index `dim -> slots` | one N-bit bitmap per dimension | the set of records a transition touches |
| inverted index `tag -> slots` | one N-bit bitmap per tag | the set of records depending on an invalidated record's output |

### 3.2 Transition processing

```
on context change of dimension d (old -> new):
    epoch[d] += 1
    hit = slots_by_dim[d]                          # N-bit AND/copy
    for each slot s in hit (lowest set bit loop):
        mark s INVALIDATED(reason = DEPENDENCY_INVALID or CONFIGURATION_MISMATCH, dim = d)
        if s produces an output tag t that others depend on:
            hit |= slots_by_tag[t] & live             # derived evidence, bounded fan-out
    reset ACCUMULATED_STATISTIC producers whose inputs are in hit
    append one ledger event: CONTEXT_TRANSITION{d, old, new, epoch, invalidated_count, invalidated_set_hash}
```

**Nothing outside `hit` is touched.** Evidence whose contract does not name
`d`, and does not depend on invalidated evidence, stays admissible.

### 3.3 Complexity

- **Per transition:**
  - O(N/w) word operations to form `hit` (w = 32 or 64);
  - O(|hit|) to mark records;
  - plus one derived-evidence pass bounded by the tag fan-out.
- **The derivation graph is acyclic by construction.** Cycles are a load
  error, as in FORGE-SEED (S042) and to prevent FM-24. The derived pass
  therefore terminates in at most D rounds, where D is the declared
  maximum derivation depth (design limit 3).
- **Worst case:** a dimension that every live record depends on invalidates
  all N slots. That is O(N) marks and one ledger event, with no allocation.

### 3.4 Audit record

Each transition appends one ledger event to the existing hash chain (S009),
containing:

- the dimension;
- the old and new values;
- the new epoch;
- the count of invalidated records;
- a hash of their ids.

The full id list goes to the debug view only. This keeps the onboard ledger
bounded while letting a post-flight tool reconstruct exactly which evidence
was dropped and why. That fixes FM-32, because replay then **reads**
admissibility decisions instead of recomputing them.

### 3.5 What invalidation must never do

1. **Invent evidence.** It only removes.
2. **Upgrade a function** (FM-33). A function whose limiting adverse evidence
   was invalidated goes to UNKNOWN, not ELIGIBLE.
3. **Flush globally** unless the contract says so. A contract may name the
   pseudo-dimension `ANY`, which is then visible and reviewable.
4. **Hide an invalidation storm** (FM-30). More than K invalidations of the
   same dimension within a hold-off window raise `CONTEXT_UNSTABLE`, and
   every dependent record becomes `UNKNOWN`. Design default: K = 3, hold-off
   5 s. These values are to be set by measurement, not asserted.
