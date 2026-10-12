# The reality stress envelope (PRIME Track B2)

**2026-10-02. SITL BASE LOGS, OFFLINE PERTURBATION. A TOLERANCE ENVELOPE,
NOT PHYSICAL EVIDENCE.**

**Files:**
- **scripts:** `stress_envelope.py` (v2), `envelope_table.py`;
- **as run:** `STRESS_ENVELOPE.json` (v1, commit 0ead374) and
  `STRESS_ENVELOPE_V2.json` (v2);
- **reduced:** `ENVELOPE_TABLE.json`.

## 1. What was done

**Each run:**
1. takes an already-flown SITL log;
2. perturbs one signal property offline;
3. runs the **unchanged** product path on it.

The product decimates and analyses the perturbed log as it would a real
one. Nothing was tuned.

**The six bases** are a hover loss (V4), a hold loss after maneuvers
(V12), a maneuvering loss (V13), a telemetry corruption matched to V4's
local symptom on a healthy motor (CAL1 with motor_0's RPM × √0.6 from
70 s), nominal hover (CAL1) and nominal maneuvering (V5).

**The size of the sweep:**
- 15 variables, 5 levels each;
- 5 seeds for the random variables;
- 1,056 runs in v2 (906 in v1).

**v1 and v2.** v1's timestamp jitter was continuous noise, which made
sub-microsecond times that no ULog can contain. That exposed defect
D-PRIME-1 (`DEFECT_D_PRIME_1.md`). v2 keeps every v1 variable and adds
`jitter_us`, the same jitter rounded to the microsecond as a real log would
carry it. v1's file is kept as run.

## 2. The headline

**In 1,056 runs:**
- **zero false symptoms** on the nominal and telemetry-corruption bases;
- **zero symptoms on a non-injected motor;**
- **zero UNIQUE attributions;**
- **zero cases of the telemetry corruption read as a physical loss.**

**Under every perturbation the product failed safe.** What breaks is the
confirmation of a true loss: the fault is missed (reported unresolved),
never misnamed.

**That is the right direction for an assurance tool.** It also means each
limit below is a coverage limit: beyond it, the product goes quiet about
real faults.

## 3. The envelope

**Fault bases:** 1 run per level for deterministic variables, 5 for random
ones, A_hover and A_hold together. "None" means not reached in the range
tested.

| variable | range tested | first degradation | ambiguity (true loss unconfirmed) | false symptom | wrong attribution | real reference measured so far |
|---|---|---|---|---|---|---|
| timestamp jitter, µs grid (std, % of interval) | 2-40 % | 40 % | **40 %** (4 of 10) | none | none | FMUv5 boat: interval std 2.4 % (actuator_motors), 9.6 % (angular velocity); RB0 reduced-profile CubeOrange about 15 % |
| independent sample loss | 2-40 % | 2 % | **2 %** (1 of 10); 10 %: 7 of 10 | none | none | real ULogs lose samples in logger dropouts (RB0: 1-4 per log, 10-119 ms), not independently |
| propulsion logging interval (× 547e2ca default) | 1.5-5 × | 2 × (refusals on maneuvering) | **2.5 ×**, an effective 300 ms interval for the 10 Hz topics (the 3 × gap rule) | none | none | newer PX4 logs `esc_status` at 248 ms (RB0, SITL 1.14): **inside, by 52 ms**; `failure_detector_status` at 2 Hz (FMUv5) |
| ESC telemetry latency | 50-1000 ms | none | none | none | none | unmeasured (RR-08) |
| producer restart (ESC topic silent inside the event) | 0.5-10 s | 0.5 s (refused windows) | **10 s** | none | none | — |
| RPM quantization (hover ≈ 7000 rpm) | 10-250 rpm | none | none | none | none | DShot telemetry ≈ 14 rpm per step (14-pole motor), typical |
| RPM noise (std, % of mean) | 0.5-10 % | 2 % (extra events) | **5 %** (10 of 10) | none | none | **unmeasured: RB2-0's first measurement** |
| static per-motor RPM gain mismatch | 1-20 % | none | none | none | none | — |
| ESC response lag (first order) | 20-500 ms | none | none | none | none | — |
| gyro bias, each axis | 0.005-0.1 rad/s | 0.05 | **0.05 rad/s** (compensation refused as NOT_STEADY) | none | none | **CubeOrange at rest: 0.067 rad/s yaw (RB0): inside the ambiguity zone** |
| gyro noise (std) | 0.002-0.05 rad/s | 0.02 | **0.02 rad/s** (1 of 10); 0.05: 10 of 10 | none | none | quiet boards at rest: 0.0014-0.0075 rad/s; in flight with propellers: unmeasured |
| vibration (aliased 13 Hz tone, amplitude) | 0.005-0.1 rad/s | 0.1 | **0.1 rad/s** | none | none | in flight: unmeasured |
| supply sag, common mode, over the flight | 2-25 % | none | none | none | none | the boat: 15.9 → 13.4 V in 294 s (16 %) |
| one healthy motor drifting (temperature proxy) | 1-20 % | none | none | none | none | — |
| timestamp jitter, off-grid (v1 variable) | 2-40 % | 2 % | 2 % | none | none | **not a real-log condition:** these losses are D-PRIME-1, not degradation |

## 4. What it means for a customer's vehicle

**Within the envelope, the stock evidence behaves on these SITL bases as it
did unperturbed:**
- propulsion topics logged at **≥ 5 Hz** with no gap over 300 ms;
- residual gyro bias **< 0.05 rad/s;**
- gyro noise at the logged rate **< 0.02 rad/s;**
- ESC RPM noise **< 2 %.**

**Outside it, the product refuses or stays silent about real losses, and
says why** (NOT_STEADY_FLIGHT, log gaps, producer health). These limits go
into the support matrix (`SUPPORT_MATRIX.json`) as conditions to check per
log.

**Two real measurements already sit at or past an edge:**
- **gyro bias:** a real CubeOrange at rest carried 0.067 rad/s of yaw bias
  in `vehicle_angular_velocity`. On such a vehicle the compensation would
  be refused everywhere, and real losses unconfirmed. This is RB-001's
  RR-06, now with a threshold.
- **logging rate:** newer PX4 versions log `esc_status` at 248 ms. That is
  inside the gap rule by 52 ms, so any jitter or dropout tips it over.
  This is RB-001's RR-05, now with its margin.

## 5. What this does not establish

**These are SITL bases:**
- the real noise floor of the statistics is unknown;
- the curves say how far each property can move from SIH's values, not
  where a real vehicle starts.

**Not perturbable offline:** mass, CG, wind, maneuver regime and
temperature act through the closed loop or the physics. Editing signals
would be a fiction.
- wind (0-5 m/s) and maneuver patterns are covered only by flights already
  flown;
- temperature only by the single-motor drift proxy;
- configuration changes are not read in flight by the stock path, by design.

**One variable at a time.** Interactions are not tested. Real vehicles
combine bias, noise, jitter and vibration.
