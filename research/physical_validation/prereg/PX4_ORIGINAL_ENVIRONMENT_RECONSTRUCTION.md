# PX4 original environment — reconstruction from committed evidence

**Purpose.** A repeated PX4 campaign must run the environment the original n=1
trial ran, not a new one assembled from memory. This file recovers that
environment field by field from committed artifacts and frozen source, and
**classifies the strength of each recovery**.

**The PX4 preregistration may not freeze until this file is committed.**

Classification vocabulary:

| class | meaning |
|---|---|
| `VERIFIED_FROM_ARTIFACT` | a committed result file records it |
| `VERIFIED_FROM_SOURCE` | a frozen or committed source file determines it |
| `DERIVED` | not stated anywhere, but forced by two or more recovered facts |
| `UNRECOVERABLE` | not recorded, and not derivable. **Named, never guessed** |

---

## 1. Autopilot build

| field | value | class |
|---|---|---|
| repository | `https://github.com/PX4/PX4-Autopilot` | `VERIFIED_FROM_ARTIFACT` |
| commit | `547e2caa9883bc1609325f02b4914b4e2482fe62` | `VERIFIED_FROM_ARTIFACT` |
| short form used in prose | `PX4-Autopilot@547e2ca` | `VERIFIED_FROM_ARTIFACT` |
| build target | `px4_sitl_default` | `VERIFIED_FROM_SOURCE` |
| checkout root at the time | `/home/user/px4` | `VERIFIED_FROM_ARTIFACT` |

Sources: `research/v1_1/results/PROVENANCE_BACKFILL.json`
(`autopilot_builds.px4`), `research/v1_1/PX4_LINK_RATE_FINDING.md:93`,
`research/v1_1/results/PX4_LINK_RATE_PROBE.json`,
`csia/simulation/rigs.py:94`.

### 1.1 A qualification the backfill states about itself

`PROVENANCE_BACKFILL.json` records the strength of its own PX4 entry as:

> `"INFERRED_FROM_ENVIRONMENT, not recorded per trial"`
> `"evidence": "read from the simulator checkout these commits ran against;`
> `the artifacts do not record it, which is the gap this file exists to close"`

So the commit is **not** stamped into each PX4 trial artifact. It was read off
the checkout afterwards. That is materially weaker than a per-trial stamp: it
assumes the checkout was not moved between the trials and the backfill.

**Carried forward, not resolved.** The repeated campaign stamps the build into
every trial manifest, which closes the gap going forward and cannot close it
retroactively. This is the same shape as FL-011/FL-013 on the ArduPilot side.

## 2. Simulator configuration

| field | value | class |
|---|---|---|
| simulator | **SIH** — Simulation In Hardware, PX4's own rigid-body model inside the PX4 process | `VERIFIED_FROM_SOURCE` |
| `PX4_SYS_AUTOSTART` | `10040` (sihsim_quadx) | `VERIFIED_FROM_SOURCE` + `VERIFIED_FROM_ARTIFACT` |
| `PX4_SIM_MODEL` | `sihsim_quadx` | `VERIFIED_FROM_SOURCE` |
| external frontend | **none** — no Gazebo, no jMAVSim | `VERIFIED_FROM_SOURCE` |
| speedup | **1.0x, real time.** SIH runs lockstep; a requested speedup is ignored and the launcher says so loudly | `VERIFIED_FROM_SOURCE` |
| startup | `px4 -d -s <etc>/init.d-posix/rcS <etc>` | `VERIFIED_FROM_SOURCE` |

Source: `csia/simulation/rigs.py:93-130`.

**A recorded dead end worth carrying:** `PX4_SIM_MODEL=none_iris` was tried
first and PX4 never emitted a heartbeat — with no simulator attached,
`simulator_mavlink` blocks on TCP 4560 and the rest of the system never boots.
SIH was chosen because it has real dynamics, so the motion positive control can
fire. Repeating that dead end would waste a campaign.

**Consequence for the repeat:** PX4 cannot use `--speedup 5`. Where the
ArduPilot campaign ran 40 trials in ~30 minutes, PX4's 40 trials run in real
time — roughly 40 × (30 s + boot + arm + climb). This is a schedule fact, not a
scientific one, and it is stated before the preregistration rather than
discovered during it.

## 3. Link and telemetry

| field | value | class |
|---|---|---|
| rig command link | `udp:127.0.0.1:14550` (Normal instance, the GCS link) | `VERIFIED_FROM_SOURCE` |
| CSIA passive link | `udpin:127.0.0.1:14540` (Onboard instance, the companion port) | `VERIFIED_FROM_SOURCE` |
| tee | **not used** — `NEEDS_TEE = {"ardupilot": True, "px4": False}` | `VERIFIED_FROM_SOURCE` |
| link mode | **passive on 14540** — CSIA requests no streams | `VERIFIED_FROM_ARTIFACT` |

Sources: `tools/deploy/shadow_sitl_check.py:112-119`,
`research/v1_1/PX4_LINK_RATE_FINDING.md:82`.

### 3.1 The passive-link starvation, measured

This is the single most important qualification on the PX4 result and it must
be carried into the repeat unchanged.

PX4 runs several mavlink instances with **per-link runtime state**. On the
passive Onboard link CSIA binds, rates are far below the declared contract:

| message | passive/14540 | request/14550 |
|---|---|---|
| `BATTERY_STATUS` | 0.500 Hz | 9.750 Hz |

Measured `baro.altitude`: **0.993 Hz delivered against 10.0 Hz declared**,
giving `channel_usable_share = 0.4943`.

Source: `research/v1_1/PX4_LINK_RATE_FINDING.md:93-123`,
`research/v1_1/results/PX4_LINK_RATE_PROBE.json`.

## 4. Intervention

| field | value | class |
|---|---|---|
| parameter | `SIM_GPS_USED` | `VERIFIED_FROM_ARTIFACT` |
| type | **`INT32`** | `VERIFIED_FROM_ARTIFACT` |
| value | `0` | `VERIFIED_FROM_ARTIFACT` |
| sent by | the **rig**, on 14550 | `VERIFIED_FROM_ARTIFACT` |
| onset | `t + 12.0 s` | `VERIFIED_FROM_ARTIFACT` |
| confirmation | parameter **readback**, `readback = 0.0`, `confirmed: true` | `VERIFIED_FROM_ARTIFACT` |

Source: `research/v1_1/results/mechanism_a_px4.json` (`fault.injection`).

### 4.1 The INT32 trap, recorded so it is not re-encountered

`tools/deploy/shadow_sitl_check.py:145-149` records that the **first PX4 arm
sent `SIM_GPS_USED` as `REAL32`**. PX4 stores it as `INT32`, so the write
landed as `SIM_GPS_USED = 1.401298464324817e-44` — the float32
reinterpretation of the integer 1 — and the intervention did not happen while
the write reported success.

**This is the COMMAND ISSUED ≠ FAULT INJECTED failure in its purest form**, and
it is why readback confirmation is mandatory rather than advisory. The repeat
sends `INT32` and confirms by readback.

## 5. Trial structure

| field | value | class |
|---|---|---|
| duration | 30.0 s of shadow run | `VERIFIED_FROM_ARTIFACT` |
| ticks | 751 | `VERIFIED_FROM_ARTIFACT` |
| tick rate | 25 Hz | `VERIFIED_FROM_ARTIFACT` |
| flight | arm and climb (`--fly`), rig authority | `VERIFIED_FROM_ARTIFACT` |
| FAULT flight id | `20260825T005931Z-1b4add14` | `VERIFIED_FROM_ARTIFACT` |
| CONTROL flight id | `20260825T005523Z-559772e6` | `VERIFIED_FROM_ARTIFACT` |
| control semantics | fix preserved, no parameter written, `control_clean: true` | `VERIFIED_FROM_ARTIFACT` |

## 6. Downstream confirmation and the original result

| quantity | value | class |
|---|---|---|
| intermediate quantity | `gnss.position` MISSING with `NO_3D_FIX` | `VERIFIED_FROM_ARTIFACT` |
| `first_t`, FAULT | **12.121585 s** | `VERIFIED_FROM_ARTIFACT` |
| ticks observed, FAULT | **448** | `VERIFIED_FROM_ARTIFACT` |
| `first_t`, CONTROL | `null` | `VERIFIED_FROM_ARTIFACT` |
| ticks observed, CONTROL | 0 | `VERIFIED_FROM_ARTIFACT` |
| `gps_gate_weight_sum` control | **1.0** | `VERIFIED_FROM_ARTIFACT` |
| `gps_gate_weight_sum` post-fault | **0.0** | `VERIFIED_FROM_ARTIFACT` |
| trust | 0.9856 → 0.9875 | `VERIFIED_FROM_ARTIFACT` |
| `intervention_effective` | `true` | `VERIFIED_FROM_ARTIFACT` |

## 7. THE QUALIFICATION THAT MUST BE RETAINED

**Verdict: `PARTIALLY_AFFECTED`.** Only **1 of 4** GNSS-gated relations was
live before the fault. The other three were already dark, **for three different
reasons**:

| relation | pre-fault state | reason |
|---|---|---|
| `heading_course` | `DARK_BY_GATE` | speed gate; the corpus max horizontal speed is 0.13 m/s on PX4 against `GATE_SPEED_LO = 2.0` |
| `velocity_gps_doppler_1` | `DARK_STRUCTURAL` | PX4 SIH publishes no `SCALED_IMU2`, so `imu1` does not exist |
| `altitude_baro` | `STARVED_BY_TRANSPORT` | baro delivered at 0.993 Hz against 10.0 declared on the passive link; `live_share = 0.0812` |
| `velocity_gps_doppler_0` | **LIVE** | the one relation carrying evidence |

Source: `research/v1_1/results/MECHANISM_A_LINK_CONFOUND_AUDIT.json`.

The audit's own conclusion, quoted rather than paraphrased:

> *"`altitude_baro` is dark from TRANSPORT starvation on this consumer's link,
> so the demonstration is narrower than the platform allows — which is a
> statement about the link configuration, not about PX4. It does not change the
> post-fault state: every relation feeding `gps_fault` is gated on `gvalid`, so
> fix loss drives all of them to zero whether or not they were starved."*

### 7.1 The repeat does NOT fix this

**The repeated campaign runs the same passive-link configuration**, and the
`gps_gate_weight_sum` control value stays **1.0**, not 3.0.

Demanding a cleaner link would improve the number and **would not be a repeat**.
A configuration that removes the starvation is a **separate experiment** with
its own preregistration, and its result would not be comparable to the original.
Silently adopting it would be tuning the environment after seeing the result.

## 8. Sentinel handling

| field | value | class |
|---|---|---|
| `BATTERY_STATUS.current_battery` | `-1` on PX4 SIH — an implemented stream with no sensor behind it | `VERIFIED_FROM_ARTIFACT` |
| observed | 387 sentinel frames in 40 s, confirmed 2026-08-24 | `VERIFIED_FROM_ARTIFACT` |
| treatment | rejected as a sentinel, counted in `adapter_counters.rejected_sentinel` | `VERIFIED_FROM_SOURCE` |

Source: `docs/v1/V1_FINAL_RESEARCH_VERDICT.md:404-405`.

## 9. `UNRECOVERABLE` fields

Named rather than guessed.

| field | why |
|---|---|
| host CPU, core count, load during the original trials | never recorded. PX4 SIH is lockstep so this matters less than it would for a wall-clock measurement, but latency figures from the original PX4 trial are not comparable to a repeat on different hardware |
| the exact toolchain (gcc version, cmake version) used to build `547e2ca` | not recorded. A different toolchain produces a different binary from the same source; no evidence says whether that matters here |
| PX4 parameter set beyond the two named | only `PX4_SYS_AUTOSTART`, `PX4_SIM_MODEL` and the injection parameter are recorded. Any other non-default parameter, if one was set, is lost |
| wind / environment settings in SIH | not recorded; assumed default, and **assumed is not verified** |

**None of these blocks the repeat.** They bound what a difference between the
original and the repeat could be attributed to, and that boundary is stated
here rather than discovered in the discussion section.

## 10. Verdict

**Reconstruction: PASS, with two carried qualifications.**

1. The build commit is `VERIFIED_FROM_ARTIFACT` but was **inferred from the
   environment, not stamped per trial** (§1.1).
2. Four fields are `UNRECOVERABLE` (§9), all of them about the host and
   toolchain rather than about the experiment.

Every field the preregistration needs to specify an intervention, a control, a
downstream confirmation and a validity criterion is recovered at
`VERIFIED_FROM_ARTIFACT` or `VERIFIED_FROM_SOURCE` strength.

The PX4 preregistration may freeze.
