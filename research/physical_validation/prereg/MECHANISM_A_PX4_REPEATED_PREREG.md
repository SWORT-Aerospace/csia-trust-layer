# Mechanism A, PX4 SIH — repeated campaign (CAMPAIGN P1)

**Committed BEFORE the first trial of this campaign.**

**Prerequisite satisfied:** `PX4_ORIGINAL_ENVIRONMENT_RECONSTRUCTION.md` is
committed. Every field this preregistration specifies was recovered at
`VERIFIED_FROM_ARTIFACT` or `VERIFIED_FROM_SOURCE` strength, and the four
`UNRECOVERABLE` fields are named there.

**Nothing in the frozen v1 core is modified.**

---

## 1. Scope

The PX4 Mechanism A result is **n = 1** fault trial plus one matched
fix-preserving control. This campaign runs **20 + 20** on the reconstructed
environment.

**Trust is captured from the first trial.** The ArduPilot instrumentation
omission (FL-014, `--trust-trace` not passed) is not repeated here.

## 2. The environment, reconstructed and pinned

| item | value |
|---|---|
| PX4 commit | `547e2caa9883bc1609325f02b4914b4e2482fe62` |
| build target | `px4_sitl_default` |
| simulator | **SIH** — PX4's own rigid-body model, in-process. No Gazebo, no jMAVSim |
| `PX4_SYS_AUTOSTART` | `10040` (sihsim_quadx) |
| `PX4_SIM_MODEL` | `sihsim_quadx` |
| speedup | **1.0x, real time.** SIH is lockstep; a requested speedup is ignored |
| rig command link | `udp:127.0.0.1:14550` (Normal instance) |
| CSIA passive link | `udpin:127.0.0.1:14540` (Onboard instance) |
| tee | **none** |
| frozen core | `csia-v1.0-research-final` |

The build was reproduced from source in this environment and verified to run
the full CSIA stack (501 ticks, 8474 messages, command authority denied).

**Consequence of real-time lockstep:** where the ArduPilot campaign ran 40
trials in ~30 minutes at `--speedup 5`, PX4's 40 trials run in real time. This
is stated before the campaign as a schedule fact, not discovered during it.

## 3. Intervention and control

| | |
|---|---|
| parameter | `SIM_GPS_USED` |
| **type** | **`INT32`** |
| value | `0` |
| sent by | the rig, on 14550 |
| onset | `t + 12.0 s` |
| confirmation | parameter **readback** |
| control | identical flight, fix preserved, **no parameter written** |

### 3.1 The INT32 trap is preregistered, not rediscovered

The first PX4 arm ever run sent `SIM_GPS_USED` as `REAL32`. PX4 stores it as
`INT32`, so the write landed as `1.401298464324817e-44` — the float32
reinterpretation of the integer 1 — and **the intervention did not happen while
the write reported success**.

That is COMMAND ISSUED ≠ FAULT INJECTED in its purest form. A trial whose
readback does not equal the written value is `INVALID_SCENARIO`
(`INJECTOR_READBACK_MISMATCH` in the invalid-trial matrix), never a detector
miss.

## 4. THE QUALIFICATION THIS CAMPAIGN RETAINS

**The original PX4 positive trial was narrowed because only 1 of 4 GNSS-gated
relations was live before the fault.** This campaign runs the **same passive-link
configuration** and therefore inherits it.

| relation | pre-fault | reason |
|---|---|---|
| `velocity_gps_doppler_0` | **LIVE** | the one relation carrying evidence |
| `heading_course` | `DARK_BY_GATE` | speed gate; PX4 corpus max horizontal speed 0.13 m/s against `GATE_SPEED_LO = 2.0` |
| `velocity_gps_doppler_1` | `DARK_STRUCTURAL` | PX4 SIH publishes no `SCALED_IMU2`; `imu1` does not exist |
| `altitude_baro` | `STARVED_BY_TRANSPORT` | baro at 0.993 Hz against 10.0 declared on the passive link |

**`gps_gate_weight_sum` on the control arm is expected to be 1.0, not 3.0.**

**A cleaner link is NOT adopted to improve the number.** Doing so would make
this not a repeat. A driven-link configuration is a **separate experiment**
with its own preregistration, and its result would not be comparable to the
original. This is preregistered so that a disappointing control value cannot
later motivate a configuration change presented as a fix.

## 5. Sample size and stopping rule

* **20 valid FAULT, 20 valid CONTROL**, interleaved FAULT-first.
* Stops at 40 attempted. **No backfilling.**
* `planned = valid + invalid + not_attempted` must balance or the report raises.

### 5.1 Declared resource limitation

**Declared BEFORE the first trial, as the program requires.**

PX4 SIH runs in real time. If the full 40 trials cannot complete within this
session's remaining budget, the campaign stops at whatever count it reaches,
and **the denominator stays 40**: unrun trials are `NOT_ATTEMPTED`, counted,
and reported. The campaign is **not** re-planned to a smaller N to make the
arithmetic look complete.

## 6. Captured quantities

Per trial, from the trust trace and the flight log:

* GNSS downstream validity state (`gnss.position` MISSING with `NO_3D_FIX`)
* per-edge gate states and weights for the four GNSS-incident edges
* **pre-fault and post-fault live discriminating relation counts** — the
  quantity §4's qualification is about
* diagnostic leader, nominal rank, `gps_fault` rank
* nominal and `gps_fault` normalised hypothesis weights
* **GPS trust**, and the per-source components (`w_nbr`/`w_phys`/`w_temp`/`w_stat`)
* Beta mass `S`
* failsafe state and transitions
* fault command timestamp, downstream effect timestamp, gate-collapse
  timestamp, recovery timestamp
* rejected-sentinel counts and telemetry starvation metrics

**Raw traces are archived before any reduction**, then reduced by the same
committed deterministic extractor and the same four windows the ArduPilot A2
campaign uses (`PRE` [10,12), `AT` [12,13), `POST` [14,20), `LATE` [20,end]).

## 7. Sentinel handling

`BATTERY_STATUS.current_battery = -1` on PX4 SIH is an implemented stream with
no sensor behind it (387 sentinel frames in 40 s, measured 2026-08-24). It is
**rejected as a sentinel** and counted in `adapter_counters.rejected_sentinel`.
A trial whose sentinel count is zero on PX4 is suspicious and is reported, not
silently accepted.

## 8. Validity and exclusion

The eight-state vocabulary, plus the twelve-cause invalid-trial matrix. In
particular:

| condition | verdict |
|---|---|
| readback ≠ written value | `INVALID_SCENARIO` (`INJECTOR_READBACK_MISMATCH`) |
| a parameter written on a CONTROL flight | `INSTRUMENT_DEAD` — RULE A, campaign-wide |
| `gnss.position` never goes MISSING on a FAULT flight | `INVALID_SCENARIO` |
| build commit ≠ `547e2ca…` | `PREREG_VIOLATION` |
| tick latency over budget | **not an exclusion** (§9) |

## 9. Nuisance policy

Tick latency is **recorded and NOT adjudicated**, identically to A1 and A2. The
host is shared. **No latency or timing claim may be made from this campaign** —
and note that PX4's real-time lockstep makes its latency figures even less
comparable to ArduPilot's than the shared host alone would.

## 10. Analysis, fixed in advance

* Per arm: N, median, min, max, IQR at the **trial** level. Ticks are not
  replicates.
* **No p-values, no confidence intervals**, for the reason given in the
  ArduPilot preregistration.
* **NO POOLING WITH ARDUPILOT.** The two platforms differ structurally — PX4
  has no `imu1` at all — and pooling would average over that. They are reported
  separately, always.
* **No prevalence claim.** Nothing here says how often this occurs in the field.
* The original n=1 values (`first_t` 12.121585 s, 448 ticks,
  `gps_gate_weight_sum` 1.0 → 0.0, trust 0.9856 → 0.9875) are compared against
  the repeated distributions. **A contradiction is a result**, not a failure.

## 11. What this campaign cannot establish

* **Still E1.** Nothing about hardware, real sensors or flight.
* **Nothing about a driven-link PX4 configuration** (§4).
* **Nothing about the signature table.**
* **No timing claim** (§9).
