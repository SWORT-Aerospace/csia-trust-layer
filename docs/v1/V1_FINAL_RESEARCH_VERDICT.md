# CSIA v1 — final research verdict and freeze

**This document closes the v1 research line.** Everything after it is
engineering work under a new version. The v1 algorithm is frozen: no
threshold, relation, gate or fusion weight in `csia/trust_engine/`,
`csia/diagnosis/`, `csia/runtime/online.py` or `csia/runtime/failsafe.py`
changes in service of deployment.

**The purpose of freezing is not celebration.** It is so that when v1.1
engineering changes behaviour, we can prove which change did it.

---

## 1. Identity of the frozen baseline

| item | value |
|---|---|
| package version | `0.8.0` |
| freeze commit | `ec5acd1` (see `git tag csia-v1.0-research-final`) |
| Phase-I scientific reference | `848f556` |
| tag | `csia-v1.0-research-final` |
| trust graph | 8 nodes, 11 relations |
| tick rate | 25 Hz nominal |
| production diff across all Phase-II work | **empty** — `git diff 848f556..ec5acd1 -- csia/` |

The last line is the important one. Every Phase-II result, every publication
artifact and every audit in this repository was produced against an
**unmodified** v1. Nothing was tuned to make a result look better.

---

## 2. Benchmarks as measured at freeze

Measured on this commit, in the development container. **Python runtime,
desktop-class CPU.** These are not embedded numbers and must not be quoted as
such.

| measurement | value |
|---|---|
| trust core, replay build | 69–75 µs/tick |
| trust core + failsafe, live runtime | 297–356 µs/tick |
| requirement R13 | ≤ 2 ms/tick |
| headroom against R13 | ~6x at the runtime figure |
| native C core, host benchmark | 247 ns trust kernel + 427 ns diagnosis |
| native C core on STM32H743 | **NOT MEASURED.** The 7–15 µs figure in older docs is an estimate. The C core is on no execution path. |

### 2.1 Detection summary at freeze (`csia report`)

| scenario | target | min trust | t<0.85 [s] | peak diagnosis |
|---|---|---|---|---|
| clean | — | 0.92 | — | 98% nominal |
| gps_spoof | gps | 0.59 | 2.2 | 89% `gps_fault` |
| gps_dropout | gps | 0.89 | — | 98% **nominal** |
| imu0_bias_drift | imu0 | 0.77 | 13.0 | 92% `imu0_bias_drift` |
| mag_emi | mag | 0.28 | 1.5 | 100% `mag_interference` |
| power_sag | battery | 0.40 | 1.6 | 100% `power_fault` |
| vibration_anomaly | vibration | 0.17 | 2.6 | 100% `vibration_anomaly` |
| dual_imu_failure | imu0 | 0.44 | 6.4 | 100% **`imu1_bias_drift`** |
| high_speed_dash | — | 0.92 | — | 98% nominal |

### 2.2 Sim vs field truth table (`campaigns/bench.json`)

| fault | config | detected | latency [s] | min trust |
|---|---|---|---|---|
| gps_spoof | sim | yes | 2.16 | 0.591 |
| gps_spoof | field | yes | 3.16 | 0.735 |
| imu_bias | sim | yes | 13.00 | 0.766 |
| imu_bias | field | **no** | — | 0.99 |
| mag_emi | sim | yes | 1.5 | 0.17 |
| mag_emi | field | yes | 2.1 | 0.67 |
| power_sag | sim | yes | 1.4 | 0.40 |
| power_sag | field | yes | 2.0 | 0.70 |
| vibration | sim | yes | 2.2 | 0.16 |
| vibration | field | yes | 2.0 | 0.42 |
| clean | sim | 0 false alarms | | |
| clean | field | 0 false alarms | | |

---

## 3. Known failures — carried forward, not fixed

Each has a regression test under `tests/test_v1_known_weaknesses.py`. **Those
tests assert the weakness still behaves as recorded.** If one starts passing
"better", that is a behaviour change to investigate, not a win to bank.

### W-1 GNSS fix-loss self-occlusion

`SOI(gps_fault) = 1.0`. Every feature that would name a GPS fault is gated by
a gate a GPS fault closes. Visible directly in `gps_dropout`: the vehicle
escalates to CAUTION on an independent freshness path, GPS trust never leaves
0.96, and the diagnosis says `nominal p=0.99` for the whole window.

**Deployment consequence.** In shadow mode this shows up as an escalation with
no cause. The log format therefore records `evidence_unavailable` explicitly
per hypothesis, so a post-flight reader can distinguish "CSIA saw nothing" from
"CSIA had nothing to see with".

### W-2 Incorrect and misleading attribution

`dual_imu_failure` attributes 100% to `imu1_bias_drift` when `imu0` is the
injected target. On the Phase-II modern rig a 49 m GNSS spoof was attributed to
the magnetometer (`mag 0.56`, action `HEADING_HOLD_GYRO`) because the spoof
corrupts course-over-ground, which breaks the `heading_course` edge joining
mag↔gps. Wrong isolation: 3 of 7 families at flight spec 0.

**Deployment consequence.** Advisory output must present the cause as a ranked
hypothesis with its evidence, never as a verdict. Shadow mode has no authority
precisely because this failure mode is live.

### W-3 IMU-bias detection disappears under field noise

`imu_bias` detects in the `sim` configuration and **not at all** in `field`
(min trust 0.99). The detection is a property of the noise model, not of the
fault.

**Deployment consequence.** Every simulated result must name its noise profile
(S4). A result from `IDEAL_SIM` is not evidence about a real aircraft.

### W-4 History / banked-evidence escalation delay

Escalation is duration-limited by the trust recursion's banked mass. Closed
form: `N* = 93.31` ticks; the shipping code crosses at tick 94; `T_N = (x·S₀·T₀
+ (1−x)·M·e_f)/(x·S₀ + (1−x)·M)` with `x = ρ^N`, `M = 1/(1−ρ)`. At 25 Hz that
is ~3.7 s of accumulated evidence before a slow fault can move the verdict.

**Deployment consequence.** A slow fault is structurally invisible for several
seconds. Advisory latency budgets must assume this, not the 1.5 s figures from
the fast-fault scenarios.

### W-5 ESC telemetry stub in SITL

`AP_ESC_Telem_SITL.cpp:72` sets `.current = 0.8f` under a comment saying it is
a fake value so `is_telemetry_active()` returns true. `SIM_Frame.cpp:901`
derives `rpm` from `vibe_motor`, whose `VIB_MOT_MAX` defaults to 0.

Consequence measured both ways, and neither configuration is usable:

- **FULL_MODERN** — the constant current makes `power_thrust` fire a false
  CRITICAL on every clean flight (this is the P0.5 `SIMULATOR_ARTIFACT`).
- **LEGACY_COMPAT** — suppressing ESC telemetry makes `phys_vibration`
  unavailable entirely (`components["vibration"]["phys"]` is `None` on every
  tick), so CSIA cannot attribute a vibration fault even in principle.

**Deployment consequence.** This is the motivating case for the whole S2
semantic-qualification layer: a field being *present and fresh* is not
evidence that it *means anything*. Retained as
`tests/test_channel_semantics.py::test_esc_sitl_stub_is_not_informative`.

### W-6 Response is not attribution

Two ledgers, and they diverge:

| ledger | question | CSIA-only cells, all three flight specs |
|---|---|---|
| A safety response | did it escalate when the autopilot did not? | **1 of 7** |
| B correct diagnostic | did it escalate *for the injected fault*? | **0 of 7** |

A textbook CUSUM (B4, 0.62 µs/tick, no new sensors) scored 2 correctly
attributed CSIA-only cells with zero joint misses and zero wrong isolation.
It is blind on both IMU families where v1 is strongest, so the two are
complementary rather than ordered — but no new detector is justified by the
completed B0–B4 branch.

**Deployment consequence.** v1.1 is a qualification and integration programme,
not a detector programme. That is a deliberate decision, recorded here.

---

## 4. Known simulator artifacts

| artifact | status |
|---|---|
| ESC current/rpm stub (W-5) | confirmed by source read; regression test |
| `SIM_WIND_SPD` applies no force in ArduCopter 3.3 | confirmed; the Phase-I campaign varied one axis, not two |
| `SIM_GPS_*` renamed `SIM_GPS1_*` on 4.x | confirmed; Phase-I scripts do not run unmodified on 4.8 |
| SITL vibration amplitude comes from `SIM_ACC*_RND`, not `SIM_VIB_MOT_MAX` alone | confirmed after two failed probes |
| `gpsDriftNE` monitor exists in ArduPilot but is gated `&& onGround` | confirmed by source read |

---

## 5. What v1 is, in one paragraph

A cross-sensor trust and attribution layer that consumes eight sensor nodes,
evaluates eleven declared physical relations, maintains a per-node trust
recursion with banked evidence, produces a ranked cause hypothesis with an
ambiguity measure, and emits typed advisory actions. It has been measured in a
bench simulator, in ArduCopter 3.3 SITL, in ArduCopter 4.8 SITL, and on 26
unannotated public flight logs. **It has never flown in the loop and is not
certified flight software.** Its measured incremental detection coverage over a
modern autopilot, on its own fault families, is one cell on safety response and
zero on correct diagnosis. Its distinguishing property is cause attribution
over a declared, enumerable structure — which is also what makes its failure
modes enumerable, and section 3 is that enumeration.

---

## 6. What is explicitly NOT concluded

- No claim that v1 detects faults a modern autopilot misses, in general.
- No claim of novelty. The word is forbidden by `papers/csia_systems/check.py`.
- No claim about embedded timing. Nothing has run on an STM32.
- No claim that the 26-log corpus is healthy, validated, or annotated.
- No fault-conditioned quantity estimated from unlabelled logs, ever.

---

## 7. Freeze conditions for v1.1

Engineering work may:

- add adapters, qualification, logging, deployment modes, tests, docs;
- refuse to feed a relation an input whose semantics are unqualified;
- change how CSIA is *fed* and how its output is *carried*.

Engineering work may **not**:

- change a threshold, weight, gate or relation in the diagnostic core;
- delete or weaken a scenario because it fails;
- retune around any weakness in section 3.

A change that alters `csia report` output on the frozen scenarios is a v1
algorithm change and requires re-freezing the baseline explicitly, with the
before/after recorded in this document.
