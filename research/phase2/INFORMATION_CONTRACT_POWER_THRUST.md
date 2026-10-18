# P0.5 — Information contract for the `power_thrust` relation

**Classification: `SIMULATOR_ARTIFACT`.**

**Artifacts:** `results/power_thrust_contract.json`, `results/r10_modern.json`,
`results/r10_attribution.json`, `results/information_architecture_diff.json`.
**Production code changed:** none. **Thresholds changed:** none.

---

## 1. The relation under audit

`csia/runtime/online.py:546-548`:

```python
E["power_thrust"] = self._lam_upd(
    "power_thrust", batt_i - float(esc_i.sum()) - AVIONICS_CURRENT,
    0.5), 1.0
```

| property | value |
|---|---|
| model class | **conservation** — equality of a sum, not proportionality |
| scale | 0.5 A |
| gate | hard-coded `1.0`, multiplied only by freshness (`online.py:610-611`) |
| joins | `motor_esc` ↔ `battery` (`csia/trust_graph/graph.py:50`) |
| airframe constants | **none** |

The absence of airframe constants matters. `accel_motor_current` and
`phys_motor_esc` carry CSIA's 2.0 kg reference-quad values
(`HOVER_RPM = 6000`, `HOVER_CURRENT_PER_MOTOR = 4.0`), which do not describe
the SITL vehicle. `power_thrust` does not, so it is testable on any airframe
and a failure cannot be blamed on the reference vehicle.

---

## 2. Per-input contract

### 2.1 `BATTERY_STATUS.current_battery` — **live and correct**

| item | finding | source |
|---|---|---|
| message / id | `BATTERY_STATUS`, 147 | `common.xml` |
| type / units | `int16_t`, **cA** | `common.xml:6431` |
| invalid sentinel | **−1**, "autopilot does not measure the current" | `common.xml:6431` |
| documented limit | "may overflow/rollover above 327.67 A" | `common.xml:6431` |
| producer | `AP_BattMonitor` via `GCS_Common.cpp`; `BATT_MONITOR = 4` on this build | measured param |
| simulator model | `battery_current = frame->get_current_amp()` | `SIM_Multicopter.cpp:102` |
| ...which is | `sum over motors of motors[i].get_current()` | `SIM_Frame.cpp:942-949` |
| sag model | `voltage_delta = current_amp * resistance_ohm`, then a low-pass on **voltage only** | `SIM_Battery.cpp:179-181` |
| instantaneous or averaged | current instantaneous; voltage filtered | `SIM_Battery.cpp:181` |
| aggregation | **pack-level aggregate, battery side** | — |
| sign | positive on discharge | — |
| update rate | 10 Hz measured | `power_thrust_contract.json` |
| CSIA normalisation | `max(msg.current_battery, 0) / 100.0` | `plugins.py:194` |
| **measured range** | **0 → 41.25 A, 375 distinct values** under load sweep | `power_thrust_contract.json` |

**Verdict: semantically correct, physically modelled, live.** Units and scale
match the specification exactly.

**Latent defect, not active here.** `max(..., 0)` maps the −1 sentinel to
`0.0 A`, indistinguishable from a genuine zero. An autopilot that does not
measure pack current is therefore ingested as a pack drawing nothing, and
`power_thrust` reads that as a 100% conservation violation. Verified
deterministically offline (`sentinel_probe` in `power_thrust_contract.json`:
`ingested_value_A = 0.0`). Not the cause on this build, because
`BATT_MONITOR = 4` and current is genuinely measured.

### 2.2 `ESC_TELEMETRY_1_TO_4.current[0..3]` — **a hard-coded constant**

| item | finding | source |
|---|---|---|
| message / id | `ESC_TELEMETRY_1_TO_4`, 11030 | `ardupilotmega.xml:1921` |
| type / units | `uint16_t[4]`, **cA** | `ardupilotmega.xml:1925` |
| invalid sentinel | **none defined** | `ardupilotmega.xml:1925` |
| encoder | `s.current[j] = constrain_float(telemdata.current * 100.0f, 0, UINT16_MAX)` | `AP_ESC_Telem.cpp:451` |
| **simulator implementation** | **`.current = 0.8f`, hard-coded** | `AP_ESC_Telem_SITL.cpp:72` |
| the source comment | *"some fake values so that `is_telemetry_active()` returns true"* | `AP_ESC_Telem_SITL.cpp:68` |
| sign | non-negative by construction (`uint16`, clamped ≥ 0) | `AP_ESC_Telem.cpp:451` |
| aggregation | **per-ESC, motor side** | — |
| missing-value behaviour | struct is zero-initialised; a missing ESC reads `0`, indistinguishable from an ESC drawing 0 A | `AP_ESC_Telem.cpp:439` |
| CSIA normalisation | `cur / 100.0  # cA -> A` | `plugins.py:207` |
| **measured** | **exactly one distinct raw value, `80` cA, in 3659 samples across two flights** | `power_thrust_contract.json` |

**Verdict: a liveness stub carrying zero information.** The scaling on both
sides is correct; `4 × 0.8 = 3.20 A` is exactly what CSIA ingests.

### 2.3 `AVIONICS_CURRENT` — **a compiled-in constant with no counterpart**

`csia/sensors/truth.py:25`, `0.6 A`, commented "FC + Pi 5 companion". It is
not telemetry. SITL's `battery_current` is purely the motor-current sum with
**no avionics term at all**, so even a perfect ESC channel would leave a fixed
`−0.6 A` residual against a `0.5 A` scale — **1.2σ, permanently**. Small, but
it means the relation could never be exactly satisfied on this plant.

### 2.4 `ESC_TELEMETRY_1_TO_4.rpm` — the failed null control, and a finding

RPM was chosen as the null control for the decode path: same message, same
decoder, same tick. **It failed — rpm is also identically 0**, so it cannot
certify anything. Per RULE A the control was replaced (§3) rather than the
conclusion being drawn anyway.

Why it is zero is itself a contract finding:

```
AP_ESC_Telem_SITL.cpp:66   update_rpm(motor, MAX(min_rpm, sitl->state.rpm[motor]))
                           min_rpm = SIM_ESC_ARM_RPM, measured 0.0
SIM_Frame.cpp:901          rpm[i] = motors[i].get_command() * AP::sitl()->vibe_motor * 60.0f
SITL.cpp:512               AP_GROUPINFO("VIB_MOT_MAX", 61, SIM, vibe_motor, 0.0f)
```

SITL's motor "RPM" is **the vibration model's amplitude term**, scaled by
`SIM_VIB_MOT_MAX`, which defaults to `0.0`. It is not a motor-speed model that
happens to be switched off. It is not a motor-speed model. Anything consuming
it as RPM — `accel_esc_rpm`, `vibration_prop_freq`, `phys_motor_esc` — is
reading a quantity whose meaning it does not share.

**This is exactly the failure mode rule 3 names: names never establish
semantics.**

---

## 3. Controls

**RULE A — null control.** The intended control (rpm, same message) failed:
constant. It is kept in the artifact, not deleted. The substituted control is
`BATTERY_STATUS.current_battery`, logged by the same loop on the same ticks
through the same `recv_match` path, which sweeps **0 → 41.25 A across 375
distinct values**. The harness is proven live. What is constant is the content
of `ESC_TELEMETRY_1_TO_4`, in **both** audited fields.

**Verdict: `HARNESS_LIVE_BOTH_ESC_FIELDS_CONSTANT`.**

**Interventions.** A commanded ±2.5 m/s climb/descent sweep swings motor load
across the whole flight envelope. Pack current responds over a 41.25 A range;
ESC current does not move by one centiamp.

**Arithmetic closure.** The stub accounts for the residual exactly:

| arm | pack mean − stub − avionics | observed residual mid |
|---|---|---|
| nominal_hover | 15.84 A | **15.84 A** |
| load_sweep | 16.82 A | **16.83 A** |

Nothing is left over for a second cause.

**RULE B — intervention on the attributed channel.** `r10_attribution.py`
drops `ESC_TELEMETRY_1_TO_4` at ingestion, restoring the legacy information
architecture, with `BATTERY_STATUS`-dropped as the discriminating arm. Results
in `results/r10_attribution.json`.

---

## 4. Source-to-runtime chain, measured

One tick from the load sweep, `t = 45.2 s`:

| stage | quantity | value |
|---|---|---|
| simulator truth, battery side | `Frame::get_current_amp()` = Σ motor currents | 33.91 A |
| simulator truth, motor side | *never published* | — |
| MAVLink encode | `current_battery` | `3391` cA |
| MAVLink encode | `esc.current[0..3]` | `[80, 80, 80, 80]` cA |
| CSIA ingestion | `battery.current` | 33.91 A |
| CSIA ingestion | `motor_esc.current` sum | 3.20 A |
| relation | `33.91 − 3.20 − 0.6` | **30.11 A** |
| in scale units | `/ 0.5 A` | **60.2 σ** |
| edge consistency | `E["power_thrust"]` after field-mode normalisation and EW smoothing | **3.06e-03** |
| node evidence | `battery.nbr` | trough **0.171** |
| node trust | `trust["battery"]` | trough **0.464** |
| failsafe test | `T["battery"] < power_critical (0.70) and fresh["battery"]` | true |
| **CSIA verdict** | `FailsafeLevel` | **NORMAL → CRITICAL** |
| recommended actions | `failsafe.py:157-159` | `REDUCE_POWER`, `LAND_NOW` |
| **diagnosis, same tick** | naive-Bayes posterior | **`nominal p=0.98`** |

The last two rows are worth stating plainly: **CSIA recommends landing while
its own diagnosis reports the vehicle nominal at p = 0.98.** The failsafe
reads trust; the diagnosis reads the signature matrix and finds no cause that
matches. They disagree, and nothing in the layer notices.

---

## 5. Assumption validity: SITL versus a real aircraft

| assumption | valid in SITL? | valid on a real aircraft? |
|---|---|---|
| pack current is measured and published | **yes** | usually, with a current sensor; `-1` otherwise, which CSIA mis-ingests as 0 A |
| ESC telemetry current is measured and published | **no — hard-coded stub** | depends on the ESC protocol; BLHeli32/KISS/DShot commonly report ESC input current |
| Σ ESC current ≈ pack current − avionics | **untestable, one side is a constant** | **plausible but unverified.** Some protocols report phase current, not DC input current, in which case the sum does not equal pack current at all |
| 0.5 A is the right scale | untested | untested. At ~29 A hover, 0.5 A is a 1.7% tolerance on a cross-source current balance, which is tight for independent shunts |
| `AVIONICS_CURRENT = 0.6 A` | **no counterpart in the plant** | airframe-specific; a compiled-in constant for a specific companion computer |

---

## 6. Was the relation ever validated, or merely unreachable?

**Merely unreachable, then tautological, then fed a stub. It has never once
been tested against data that could have falsified it.**

| stack | state of `power_thrust` | why |
|---|---|---|
| ArduCopter 3.3 (all of Phase I) | **never evaluated** | neither `BATTERY_STATUS` nor `ESC_TELEMETRY_1_TO_4` is emitted; `online.py:613` gated both nodes to zero availability |
| bench simulator (`csia bench`, the 482 tests, `campaigns/bench.json`) | **tautologically satisfied** | `csia/sensors/truth.py:140` defines `batt_i = motor_current.sum(axis=1) + AVIONICS_CURRENT` — the monitor and the plant are the same equation, so the residual is identically zero by construction |
| ArduCopter 4.8 (now) | **fails on every flight** | one side is a hard-coded constant |

Corroborated by committed Phase-I evidence: across **101 run records** in
`research/wp_c*/results/*.json`, there are **zero** power-integrity alarms,
zero structural alarms and zero magnetometer alarms. Every Phase-I alarm is a
GPS alarm. On 4.8 a power-integrity alarm occurs in **12 of 12** flights.

The distinction the brief asks for therefore resolves cleanly: this is not a
regression, and it is not a relation that used to work. **R10's zero-false-
alert evidence never covered this path**, because the path was unreachable
where the requirement was verified in flight and self-satisfying where it was
verified on the bench.

---

## 7. Classification

### Primary: `SIMULATOR_ARTIFACT`

One input to a two-input conservation relation is a hard-coded constant that
ArduPilot's own source comment describes as a liveness placeholder. The stub
accounts for the residual to within 0.01 A. Nothing is left for a second
cause.

**Ruled out, each on evidence:**

- **`UNIT_OR_SCALE_INVALID`** — ruled out. `AP_ESC_Telem.cpp:451` encodes
  `A × 100` and `plugins.py:207` decodes `/ 100`; `common.xml:6431` specifies
  cA and `plugins.py:194` decodes `/ 100`. Both correct.
- **`AGGREGATION_SEMANTICS_INVALID`** — ruled out. Per-ESC values summed
  against a pack aggregate is the correct pairing, and it is the same
  aggregation SITL itself performs on the battery side
  (`SIM_Frame.cpp:942`).
- **`INTERFACE_MAPPING_INVALID`** — ruled out *as the cause*. The message and
  field selection are right. Two real mapping defects exist (the `−1` sentinel
  collapsing to 0 A; ESC telemetry having no sentinel at all) but neither is
  active on this build.
- **`RELATION_MODEL_INVALID`** — ruled out *as the cause*, with a caveat. The
  conservation model is precisely what SITL uses on the battery side, so the
  physics is not in dispute. The `AVIONICS_CURRENT` term, however, has no
  counterpart in the plant and would leave a permanent 1.2σ offset even with a
  perfect ESC channel. That is a real model gap, an order of magnitude too
  small to explain a 50σ residual.
- **`REAL_INCONSISTENCY`** — ruled out. The simulated vehicle's power balance
  is internally consistent; only its published telemetry is not.
- **`MULTIPLE_CAUSES`** — not claimed. Two secondary defects are real and
  recorded, but neither contributes to the observed alarm.

### The architectural consequence, which is not a classification but matters more

CSIA has no gate distinguishing **"channel present"** from **"channel
informative"**. `power_thrust`'s gate is a hard-coded `1.0` multiplied by
freshness, and a 10 Hz stream of constants is maximally fresh. The freshness
watchdog (`online.py:603-613`) correctly handles a channel that *stops*; it
has no notion of a channel that never carried anything.

That is what turned a simulator placeholder into a `LAND_NOW` recommendation.

---

## 8. Standing report

**What I measured.** Every field entering `power_thrust`, at source, at the
MAVLink encoder, at CSIA ingestion, and at runtime across a 41 A load sweep;
the full residual-to-verdict chain on a single tick; and 101 committed
Phase-I run records for the legacy comparison.

**What surprised me.** That `rpm` is not a disabled motor-speed model but a
vibration-model term wearing the name RPM, and that the whole `motor_esc` node
is therefore fed by two constants.

**What I got wrong, and how I found out.** I chose `rpm` as the null control
for the ESC decode path. It was constant too, so it certified nothing, and my
first analysis pass printed `INSTRUMENT_DEAD_NOTHING_CONCLUDABLE` — correctly
refusing to conclude. The control was replaced with the battery channel on the
same ticks and the failed control kept in the artifact. Had I not built the
control in, I would have reported "ESC current is constant" on a logging path
I had no evidence was working.

**What I could not determine.** Whether real ESC telemetry sums to pack
current — the protocols differ, and some report phase rather than DC input
current. Whether `0.5 A` is a defensible scale for a cross-source current
balance on real shunts. And I could not re-measure the 3.3 message inventory:
`dronekit/assets` is outside this session's repository allowlist and
`add_repo` refuses cross-owner adds, so the legacy column is labelled by
provenance rather than presented as measurement.

**What remains open, with an owner.**

| item | owner | blocks |
|---|---|---|
| does real ESC telemetry satisfy the conservation model | not startable here, needs hardware | production validity of `power_thrust` |
| the `−1` sentinel collapsing to 0.0 A in `plugins.py:194` | this session | nothing yet; a latent interface defect |
| no "informative" gate distinct from "fresh" | this session | every relation, not just this one |
| 3.3 message inventory re-measurement | blocked, binary unobtainable | strength of the legacy column only |
