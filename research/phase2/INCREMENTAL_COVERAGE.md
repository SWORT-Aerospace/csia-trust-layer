# Incremental coverage — CSIA's own fault families on the modern rig

**Artifacts:** `results/fault_suite_lambda_spec0.json`,
`results/fault_suite_validation_spec3.json`,
`results/fault_suite_validation_spec4.json`,
`results/baseline_comparison*.json`.
**Rig:** LEGACY_COMPAT_CONTROL. **Production code changed:** none.

---

## 0. Terminology, fixed

Let **A** = validated conditions where the native autopilot produces the
declared safety-relevant response, **C** = validated conditions where CSIA (or
a candidate) does.

| set | name used here |
|---|---|
| A ∩ C | BOTH |
| A \ C | AUTOPILOT_ONLY |
| **C \ A** | **INCREMENTAL CSIA COVERAGE** (equivalently COMPLEMENTARY) |
| Θ_sig \ (A ∪ C) | JOINT_MISS |

`C \ A` is **not** statistical independence and is never called that.
Architectural independence and incremental coverage are different things: two
monitors can be architecturally independent and still cover the same set.

---

## 1. Why this test exists

E1's grid was built entirely around GNSS slew behaviour. `CSIA_ONLY = 0/8`
there is a statement about that grid, not about the architecture. This runs
the frozen catalogue in `csia/scenarios.py` — unchanged, no new fault modes —
against ArduCopter 4.8.

**Six fault mechanisms across seven scenarios** (`gps_spoof`, `dropout`,
`bias_drift`, `emi_spike`, `power_sag`, `vibration_anomaly`; `bias_drift`
appears both singly and as the dual-IMU compound). All seven were injected and
**all seven passed their per-family validity contract** at all three flight
specs.

One family is reproduced only in part, and it is recorded rather than glossed:
**`power_sag`'s second half cannot exist on this build.** The bench scenario
injects a 1.2 V pack dip *and* a 350 rpm ESC sag; SITL's ESC rpm is a
vibration-model term pinned at 0 (P0.5), so only the voltage half is real
here.

---

## 2. Two ledgers, and why both are mandatory

**A — SAFETY-RESPONSE.** Did the system produce the declared escalation?

**B — CORRECT-DIAGNOSTIC.** Did it escalate *for* the injected fault, rather
than because an unrelated subsystem alarmed?

The two diverge immediately, and the divergence is the finding.

**`gps_spoof`, spec 0.** 49.01 m of injected offset against the project's own
48 m anchor. CSIA escalated — with
`magnetometer untrusted (mag 0.56)` and action `HEADING_HOLD_GYRO`. It named
the wrong subsystem. The mechanism is visible: the spoof corrupts GPS
course-over-ground, that breaks the `heading_course` edge which joins mag↔gps,
and the magnetometer takes the blame. Meanwhile the autopilot got it right —
`pos_horiz_variance = 12.84` and a `GPS Glitch or Compass error` STATUSTEXT.

Ledger A scores that cell BOTH. Ledger B scores it AUTOPILOT_ONLY. **A
candidate must not receive credit for detecting a GNSS fault because the
magnetometer alarmed.**

---

## 3. B1, the frozen layer, on its own fault families

| spec | R10 | Ledger A (BOTH/AUTO/**CSIA_ONLY**/MISS) | Ledger B | wrong isolation |
|---|---|---|---|---|
| 0 development | 0 | 4 / 1 / **1** / 1 | 2 / 3 / **0** / 2 | 3 |
| 3 held-out | 0 | 3 / 2 / **1** / 1 | 2 / 3 / **0** / 2 | 2 |
| 4 held-out | 0 | 4 / 1 / **1** / 1 | 3 / 2 / **0** / 2 | 2 |

B0 native responds on **5 of 7** at every spec.

### 3.1 The F4 kill test

> **`CSIA_ONLY = 1 > 0` on the safety-response ledger, at all three flight
> specs.** The cell is `vibration_anomaly`: vibration rms rose 478×, the
> autopilot did not respond (velocity variance 0.67 against 0.8), and CSIA
> escalated to CRITICAL with `PREPARE_LANDING`, `LIMIT_MANEUVERS`.

So **`F4-ZERO-COVERAGE: REFUTED_AS_GENERAL_CLAIM`.** The E1 result remains
valid locally and is unchanged; it does not generalise.

### 3.2 The immediate qualification

On the **correct-diagnostic ledger, `CSIA_ONLY = 0` at all three specs.** The
one incremental cell is misattributed: CSIA blamed the magnetometer at
t = 65.1 s, then the IMUs at t = 76.7 s, and never the vibration node.

There is a structural reason, and it is a direct consequence of the rig
control. `online.py:617-618` gates `P["vibration"]` by `fresh["motor_esc"]`.
LEGACY_COMPAT_CONTROL suppresses ESC telemetry, so `motor_esc` is not fresh,
so **the vibration physics term is gated off entirely** — measured:
`components["vibration"]["phys"]` is `None` on every tick of every arm. CSIA
cannot attribute a vibration fault on this rig even in principle.

That cuts both ways and both are recorded: on FULL_MODERN the ESC stub makes
`power_thrust` fire falsely; on LEGACY_COMPAT it makes `phys_vibration`
unavailable. There is no configuration of this simulator in which the
`motor_esc`-dependent relations are both live and informative.

### 3.3 A second qualification: `gps_dropout`

Classified as a **negative control** before flying, because the bench scenario
says *"trust must HOLD, not false-alarm"*. CSIA escalated
(`GPS data invalid`, `SWITCH_NAV_INERTIAL`, `INHIBIT_GPS_MODES`), so under
that classification it scores as a false alarm.

**That classification is questionable and the alternative is stated rather
than silently adopted.** The modern injection is *total* GNSS denial —
`fix_type < 3` for 100% of the hold — and ArduPilot's own response was
`EKF variance: position lost` → `EKF Failsafe: changed to Land Mode`. When the
autopilot lands the aircraft, calling CSIA's matching GPS-named escalation a
false alarm is hard to defend. Read as a positive fault, CSIA is correct here
and B1's ledger-B row becomes 3/2/0/2 at spec 0.

Both readings are reported. Neither changes `CSIA_ONLY`, which is 0 on ledger
B either way.

---

## 4. B0–B4 side by side

Development spec 0, 7 valid fault families, R10 measured on the clean arm.

| candidate | R10 | Ledger A | Ledger B | wrong iso | µs/tick | new inputs |
|---|---|---|---|---|---|---|
| **B0** native | n/a | responds 5/7 | — | — | 0 | 0 |
| **B1** CSIA v1 | **0** | 4/1/**1**/1 | 2/3/**0**/2 | 3 | 85.5 (measured baseline) | 0 |
| **B2** k=5 | **0** | 2/3/**0**/2 | 1/4/**0**/2 | 0 | 0.18 | 0 |
| **B3** ρ=0.99 (S=100) | **2 ✗** | 4/1/2/0 | 0/5/0/2 | 6 | 85.5 | 0 |
| **B3** ρ=0.98 (S=50) | **4 ✗** | 5/0/2/0 | 1/4/0/2 | 6 | 85.5 | 0 |
| **B3** ρ=0.96 (S=25) | **4 ✗** | 5/0/2/0 | 1/4/0/2 | 6 | 85.5 | 0 |
| **B4** CUSUM h=500 | **0** | 2/3/**2**/**0** | 2/3/**2**/**0** | 0 | 0.62 | 0 |

Held-out replication of the frozen parameters:

| candidate | spec 0 ledger B | spec 3 ledger B | spec 4 ledger B |
|---|---|---|---|
| B1 | 2/3/0/2 | 2/3/0/2 | 3/2/0/2 |
| B2 k=5 | 1/4/0/2 | 1/4/0/2 | 1/4/0/2 |
| **B4 h=500** | **2/3/2/0** | **1/4/2/0** | **1/4/2/0** |

R10 = 0 for B1, B2 and B4 at every spec.

### 4.1 Each baseline against the brief's taxonomy

- **B2 — (A) duplicates, and covers less.** Zero incremental coverage on
  either ledger, at every spec. It fires only on `gps`, and strictly later
  than the trust recursion. It prices the smoothing and finds it is not the
  bottleneck.
- **B3 — (D) unacceptable false alerts, and (E) attribution damage.** Every
  mass cap tried breaks R10 (2–4 clean-flight transitions) and simultaneously
  raises wrong isolation from 3 to 6 and collapses correct-diagnostic BOTH
  from 2 to 0–1. It buys ledger-A coverage with exactly the currency the hard
  constraint forbids. **B3 is refuted.**
- **B4 — (B) genuine incremental coverage, and (C) converts joint misses.**
  Two correctly-attributed CSIA_ONLY cells at every spec, zero joint misses at
  every spec, zero wrong isolation, R10 = 0, 0.62 µs/tick against a 2 ms
  budget, no new sensor inputs, one float and one counter of state per node.

### 4.2 What B4 actually catches, and what it does not

Spec 0, per family:

| family | B4 alarms on | correct | delay |
|---|---|---|---|
| gps_spoof | `gps` | yes | 2.20 s |
| mag_emi | `mag` | yes | 0.12 s |
| power_sag | `battery` | yes | 0.32 s |
| vibration_anomaly | `battery`, `vibration` | yes | 0.40 s |
| gps_dropout | — | (negative control) | — |
| imu0_bias_drift | — | **no** | — |
| dual_imu_failure | — | **no** | — |

B4 is blind on both IMU families, because the layer publishes no per-IMU
physics residual — `components["imu0"]["phys"]` does not exist. Those are
precisely the two families B1 handles best, and handles with correct
attribution (`imu0_bias_drift p=0.96`, and an EMERGENCY with
`STABILIZE`/`CONTROLLED_DESCENT`/`BROADCAST_MAYDAY` on the dual failure).

**B1 and B4 are complementary, not ordered.** B4 dominates on the
correct-diagnostic ledger as scored, but the union of the two covers strictly
more than either. That is a result about this suite, not a design proposal.

### 4.3 The persistent joint miss under B1: `power_sag`

A verified 1.24 V pack sag. The autopilot does not respond. B1 does not
respond. On FULL_MODERN the same battery node produces a spurious CRITICAL
every flight from the ESC stub; on LEGACY_COMPAT it produces nothing at all
for a real power fault. B4 catches it in 0.32 s with correct attribution.

---

## 5. Threats to these numbers

- **n = 1 flight per family per spec.** Rule 3 stands: these are seven
  families at three sites, not a distribution. Three specs agreeing is
  replication across sites, not across repeats.
- **R10 is measured on one clean flight per spec.** `h = 500` was selected by
  a zero-alarm constraint on a single 110 s nominal arm and then reproduced on
  two more. That is three clean flights total, which is a weak qualification
  set for a zero-false-alert requirement.
- **`h = 500` is far from the textbook `h = 5`.** The textbook pair is
  retained as a committed negative result: at k = 0.5, h = 5.0 gives an
  in-control ARL of about 465 samples, and the layer ticks at ~25 Hz, so it
  predicts about five false alarms per flight and measured four. The
  mis-specification was the analyst's, not the method's; the corrected rule
  reads the clean arm only.
- **Three instrument defects were found and repaired inside this work package**
  (validity windows, saturated residual input, wrong GPS stream). All are
  recorded in `METHODOLOGY.md` and in the artifacts. The rate at which
  instruments in this programme turn out to be wrong is itself a reason to
  treat single-run results with suspicion.
- **B4 has NOT been evaluated on the E1 slow-slew regime.** No per-tick
  streams exist for those cells. Everything above concerns the fault-family
  suite only.
