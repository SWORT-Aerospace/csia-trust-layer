# Information-architecture diff — ArduCopter 3.3 versus 4.8

**Derived, not transcribed:** `information_architecture_diff.py` reads the
relation list from `csia/trust_graph/graph.py` and `csia/runtime/online.py`,
the sensor-to-message mapping from `csia/runtime/plugins.py`, and modern
message availability from this session's own probe.
**Artifact:** `results/information_architecture_diff.json`.

---

## 0. The question, answered

> Did additional telemetry increase the information available to CSIA while
> simultaneously activating diagnostic relationships whose validity domain had
> never been established?

**Yes for the activation. Partly no for the information.**

- **Two nodes** moved from unavailable to available: `battery`, `motor_esc`.
- **Seven relations** began evaluating that had never evaluated on any stack.
- **Seven of those seven have no validation evidence.**
- **One of the two new nodes carries no information at all.** Both
  `ESC_TELEMETRY_1_TO_4` fields are constants on this build: `current` is a
  hard-coded 0.8 A liveness stub, `rpm` is identically 0.

So the honest statement is sharper than "more telemetry activated unvalidated
relations". It is:

> The modern stack added a channel that is present, fresh, well-formed,
> correctly scaled, and empty. CSIA has no gate that distinguishes *present*
> from *informative*, so four relations began scoring a constant as evidence,
> and one of them escalated to a `LAND_NOW` recommendation on every flight.

This is measured. It is not called novel and no claim of priority is made.

---

## 1. Classification

```
ACTIVE_BOTH   11        MODERN_ONLY   7        LEGACY_ONLY   0
SEMANTICALLY_CHANGED 0  UNREACHABLE_BOTH 0     UNKNOWN       0
```

| relation | class | nodes | validation evidence |
|---|---|---|---|
| `redundant_imu` | ACTIVE_BOTH | imu0, imu1 | Phase-I campaigns |
| `altitude_baro` | ACTIVE_BOTH | baro, gps | Phase-I, incl. the gate work in WP-C6 |
| `velocity_gps_doppler` | ACTIVE_BOTH | imu0/imu1, gps | Phase-I spoof campaigns |
| `attitude_gravity_mag` | ACTIVE_BOTH | imu0, mag | Phase-I, incl. the WP-C3 signature repair |
| `heading_course` | ACTIVE_BOTH | mag, gps | Phase-I |
| `phys_imu0` / `phys_imu1` | ACTIVE_BOTH | imu0 / imu1 | Phase-I |
| `phys_baro` | ACTIVE_BOTH | baro | Phase-I |
| `phys_mag` | ACTIVE_BOTH | mag | Phase-I |
| `phys_gps` | ACTIVE_BOTH | gps | Phase-I, extensively |
| `phys_vibration` | ACTIVE_BOTH | vibration | Phase-I |
| **`power_thrust`** | **MODERN_ONLY** | motor_esc, battery | **NONE** |
| **`accel_motor_current`** | **MODERN_ONLY** | imu0, motor_esc | **NONE** |
| **`accel_esc_rpm`** | **MODERN_ONLY** | imu1, motor_esc | **NONE** |
| **`vibration_prop_freq`** | **MODERN_ONLY** | vibration, motor_esc | **NONE** |
| **`temp_bias_drift`** | **MODERN_ONLY** | battery, baro | **NONE** |
| **`phys_motor_esc`** | **MODERN_ONLY** | motor_esc | **NONE** |
| **`phys_battery`** | **MODERN_ONLY** | battery | **NONE** |

`temp_bias_drift` deserves a note: `baro` was available throughout Phase I, but
the edge joins `battery`↔`baro` and `online.py:610-611` gates every edge on
**both** endpoints being fresh. A present sensor was gated off by an absent
one. Adding `BATTERY_STATUS` activated a thermal relation that has nothing to
do with batteries.

---

## 2. What each newly active relation is actually being fed

| relation | input quality on 4.8 | source |
|---|---|---|
| `power_thrust` | pack current **live** (0 → 41.25 A); ESC current a **hard-coded 0.8 A** | `AP_ESC_Telem_SITL.cpp:72` |
| `phys_motor_esc` | both inputs stubs: `abs(0.8 − 0)` = 0.8 A against a 0.2 A scale — a fixed 4σ residual independent of the vehicle | `AP_ESC_Telem_SITL.cpp:72`, `SIM_Frame.cpp:901` |
| `accel_esc_rpm` | rpm identically 0 | `SIM_Frame.cpp:901`, `SITL.cpp:512` |
| `accel_motor_current` | same 0.8 A constant, plus CSIA's 2.0 kg reference-airframe constants which do not describe the SITL quad | `truth.py:18-23` |
| `vibration_prop_freq` | rpm 0 collapses the predicted rms to its 0.08 floor term; the relation degenerates to a constant test | `online.py:549-552` |
| `phys_battery` | **genuine** — SITL models sag from its own pack resistance | `SIM_Battery.cpp:179-181` |
| `temp_bias_drift` | baro temperature, genuine; gated on battery freshness | `online.py:557-559` |

Only **two of seven** newly active relations are fed real data
(`phys_battery`, `temp_bias_drift`). The remaining five all depend on
`motor_esc`, which is a stub in both of its fields.

`phys_battery`, the one genuinely new and genuinely fed relation, is exercised
for the first time here and sits **just inside** tolerance: the plant's pack
resistance regresses to 0.0100 Ω against a compiled-in 0.0120, giving a
0.058 V residual against a 0.06 V scale. It does not fire only because
field-mode normalisation maps sub-unity chi-squares to consistency 1.0.

---

## 3. Evidence provenance for the legacy column

The ArduCopter 3.3 binary **could not be re-measured in this container**.
Phase I used a `dronekit-assets` prebuilt tarball; GitHub reads here are
scoped to this session's repository allowlist, `dronekit/assets` is outside
it, and `add_repo` refuses cross-owner adds. Every row therefore carries its
provenance rather than being presented uniformly as measurement.

| provenance | meaning | rows |
|---|---|---|
| `MEASURED_MODERN` | probed on 4.8 in this session | all modern columns |
| `MEASURED_LEGACY` | a committed Phase-I artifact measured it on 3.3 | `GPS_RAW_INT`, `RAW_IMU`, `SCALED_IMU` absent, `EKF_STATUS_REPORT` |
| `INFERRED_LEGACY` | inferred from committed Phase-I behaviour | `SCALED_PRESSURE` |
| `ASSERTED_LEGACY` | recorded in `modern_replication.json` but not measured by any artifact available here | `BATTERY_STATUS`, `ESC_TELEMETRY_1_TO_4`, `SCALED_IMU2`, `VIBRATION`, `GLOBAL_POSITION_INT`, `SIMSTATE` |

**Corroboration for the two rows that carry the argument.** The two
`ASSERTED_LEGACY` rows that matter are `BATTERY_STATUS` and
`ESC_TELEMETRY_1_TO_4`. Independent committed evidence:

> Every `alarms` list in `research/wp_c*/results/*.json` was scanned:
> **101 run records** on ArduCopter 3.3. Power-integrity alarms: **0**.
> Structural: **0**. Magnetometer: **0**. GPS: **37**.
> On 4.8, a power-integrity alarm occurs in **12 of 12** flights.

This shows the path did not *fire* on 3.3. It does not by itself prove the
message was absent rather than present and consistent. Combined with the stub
finding it is sufficient for the architecture claim, and it is reported as
**inferred, not measured**.

---

## 4. The consequence, measured by intervention

`results/r10_attribution.json` drops one message at ingestion and changes
nothing else:

| arm | suppressed | failsafe transitions | R10 | `trust_battery` trough |
|---|---|---|---|---|
| A baseline | — | **1** | fail | 0.463 |
| B | `ESC_TELEMETRY_1_TO_4` | **0** | **pass** | **0.997** |
| C | `BATTERY_STATUS` | **0** | pass | 0.800 (prior held, node absent) |

Arm B restores the legacy information architecture: `motor_esc` returns to
unavailable, exactly as on 3.3. Both B and C silence the alarm, as they must —
`power_thrust` needs both endpoints fresh — so the discriminator is
`trust_battery`. In **B it recovers to 0.997**, meaning the battery channel is
live and healthy once the stub is removed. In **C it sits at the 0.8 prior**,
meaning the node simply is not there and nothing was learned about it.

**The battery telemetry is good. The ESC telemetry is the fault.**

---

## 5. What this changes about how the programme reads its own history

Two Phase-I claims are re-scoped rather than withdrawn.

1. **"Two of the eight graph nodes that were dead throughout Phase I are live
   here"** (`modern_replication.json`) is now precise: one of the two is live
   and informative (`battery`), one is live and empty (`motor_esc`).

2. **"e_f, which the algebra derives from which components are AVAILABLE, is
   expected to differ"** is confirmed, but the direction was mis-anticipated.
   The extra availability does not add evidence; it adds a channel that votes
   *against* the vehicle from a constant. The Phase-I algebra's `e_f` term
   assumes an available component contributes information. That assumption is
   now measurably false on this rig.

Nothing in the Phase-I result set is invalidated by this: every Phase-I number
was measured on a stack where these seven relations were gated off, and the
freshness gate handled their absence correctly.
