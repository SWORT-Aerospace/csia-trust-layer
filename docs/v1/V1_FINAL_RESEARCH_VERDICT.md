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
| headroom against R13 | **~1.9x measured on the full graph — see W-8.** The ~6x once stated here came from a sub-measurement taken on a graph missing two nodes |
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

**PX4 update, 2026-08-24 — the same two channels, the opposite result.**
Measured on PX4 SIH with the airframe flying: `esc.rpm` varies over a 5,540
RPM range (sd 1,323, n=17,167) and `esc.current` is constant at 0. ArduPilot
SITL, re-measured the same day, is the mirror image: current constant at 3.2 A,
rpm constant at 0. The contract row declares both `STUB_OR_NONINFORMATIVE`,
which is right for ArduPilot and **wrong for PX4** — the row was written
against one simulator. Neither backend supplies a complete set and they fail
in opposite places, which is more useful than either alone: a relation that
survives both has not been validated against one simulator's quirks.

**Resolved the same day by a per-platform mechanism, not by editing the base
row.** `platform_qualification:` narrows a row for one platform, carrying the
measurement that justifies it. On PX4 `esc.rpm` is now
`AVAILABLE_UNVALIDATED` and `esc.current` keeps `STUB_OR_NONINFORMATIVE` with
its own reason, since the ArduPilot source citation does not apply there.
**Neither becomes admissible**, and `esc.rpm` stays refused deliberately:
INFORMATIVE needs `VALIDATED_SEMANTICS` *and* variation, and nobody has read
the PX4 source for that field's units or indexing. Admitting it because it
moves would be this weakness with the sign reversed. A platform row can only
narrow — effective admissibility is the AND of base and platform, enforced in
`ChannelContract` and held by `tests/test_platform_contract.py`, because
otherwise the mechanism would be the easiest possible way to re-admit a stub.
Details: `docs/simulation/PX4_CURRENT.md` §2.5.

**How that PX4 measurement was nearly missed.** The first PX4 run reported
both ESC channels as "never arrived" and it was published. PX4 had been
sending `ESC_STATUS` all along; the pymavlink installed here carries a reduced
`common.xml` with no message 291, so every frame was counted as `UNKNOWN_291`
and binned with traffic we ignore on purpose. The instrument could not read
the message and reported the platform as not sending it — the same error as
calling a channel a stub because the aircraft never moved. Fixed twice over:
the rigs now decode with the vehicle's own message definitions
(`csia/simulation/dialect.py`), and any undecodable frame whose id names a
contract producer marks that channel `UNDECODABLE`, never `UNAVAILABLE`, and
voids the run as `INSTRUMENT_DEAD`.

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

### W-8 The published tick figure is a sub-measurement

**Found after the freeze.** Narrower than first recorded here — see the
correction at the end of this entry, which is part of the finding.

`TrustState.latency_us` — the number `csia run` prints and the source of the
297–356 µs/tick in section 2 — starts its timer at `online.py:461`, inside
`_tick()`, and stops at `online.py:645`. **It excludes `ingest()` and
`_apply()`**: the per-sensor work of accepting a sample, updating the Holt
filters and computing residuals, without which `_tick()` cannot run.

Confirmed by profile on real logged flight data: `ingest` cumulative 0.882 s
against `_tick` cumulative 0.655 s — a ratio of **1.35×**.

**The full drive cost, measured on real data.** Logged ticks from a live
ArduCopter 4.8 shadow run, replayed into a fresh core, timed with
`perf_counter` and no profiler
(`tools/deploy/profile_core_from_log.py`):

| graph | `field_mode=False` | `field_mode=True` | hand-offs/tick |
|---|---|---|---|
| 8 channels (imu0 + mag missing) | 576.9 µs | 632.7 µs | 2.92 |
| **12 channels (full graph)** | 709.1 µs | **840.0 µs** | 4.28 |

The first row is not a baseline, it is a **defect**: a dispatch regression had
removed `imu0` and the magnetometer from the graph, so every earlier timing
figure here was measured on a crippled system. Restoring them costs ~33% more
core time, which is what two more nodes and their relations should cost.

**Use the 12-channel row.** The published `latency_us` understates the real
drive cost by roughly **2.4x** (840.0 against 297-356 µs), and `field_mode` —
which a real vehicle requires — adds ~18%.

**R13 status on desktop:** ~840 µs core + ~216 µs v1.1 adapter ≈ **1056 µs
against the 2 ms budget, about 1.9x headroom.** Not the ~6x the benchmark row
implied, and not a failure. The margin is thinner than any figure previously
recorded in this document.

---

#### Correction: the R13 "failure" was a measurement artifact, and it was mine

This entry first recorded the core at ~1.5 ms and concluded *"R13 headroom was
never ~6×… on companion-class ARM the budget is exceeded outright."*
**That was wrong**, and the way it was wrong is worth more than the number.

The 1542–1590 µs came from phase timing inside
`tools/deploy/shadow_sitl_check.py`, where the telemetry tee runs as a
**thread in the same interpreter**, forwarding 68,000 messages while the core
is being timed. Python's GIL means that work is charged to the core's wall
clock.

Controlled, same log, same core, varying only concurrent in-process load:

| concurrent GIL threads | core median |
|---|---|
| 0 | 679.5 µs |
| 1 | 954.6 µs |
| 2 | **1598.3 µs** |

The live figure was 1590 µs. It reproduces the two-thread case, not a property
of CSIA.

**What survives:** `latency_us` is a sub-measurement, the drive cost is ~1.8×
the published number, and headroom is ~2.4× rather than ~6×.

**What does not:** the core is not 1.5 ms, and R13 does not fail on desktop.

**The lesson, recorded because it will recur:** a timing harness that shares
an interpreter with the traffic generator measures the harness. On a real
aircraft the tee is a separate process or hardware and does not contend — so
the deployment configuration was never the one that failed. Any future timing
claim must state what else was running in the same process.

**Gate 2 must still measure on target hardware.** ~2.4× headroom on a desktop
is not ~2.4× on companion-class ARM, and the figure to measure is the full
drive cost, not `latency_us`.

#### W-8 addendum, 2026-08-24: the tail is not measurable here at all

Two further steps, and the second one closes this entry as far as it can be
closed on this infrastructure.

**1. The tee now runs in a separate interpreter.** `--tee-mode process` is the
default; `--tee-mode thread` is retained as the null control. Same rig, same
flight, back to back:

| | tee as thread | tee as process |
|---|---|---|
| tick median | 1253.9 µs | **1125.8 µs** |
| p99 | 2118.5 µs | **1768.2 µs** |
| core phase median | 1097.7 µs | **952.2 µs** |
| over 2 ms | 9 / 751 | **2 / 751** |

Real and in the predicted direction, and it is the faithful arrangement: on a
real aircraft the tee is the GCS or a UART split, never a thread inside CSIA.

**2. The latency instrument had no null control, and now it does.** A loop
doing identical arithmetic on every iteration — no CSIA, no I/O — sized to the
tick's own median and run the same number of times in the same process:

```
median 508.9 us   p95 706.0   p99  847.1   max  2057.7   over-2ms  1/751
median 520.6 us   p95 812.5   p99 2067.0   max 26730.8   over-2ms 10/751
median 492.2 us   p95 890.0   p99  995.9   max  4160.9   over-2ms  1/751
```

Constant work, a 26.7 ms outlier, up to ten ticks over budget. In a live run
the same day the control went over **15 / 749** times while CSIA went over
**9 / 749**: on this host the full v1.1 stack is *quieter than a busy loop*.

**Conclusion, and it is not a pass.** Central tendency is measurable and
sound — deterministic replay of a real 30 s flight gives a core median of
430–495 µs with p95 604–848 µs across six passes, against a 2000 µs budget.
The **deadline property R13 actually asserts is not measurable on shared cloud
infrastructure**, because the instrument's own noise floor exceeds the budget.
`csia/simulation/host_noise.py` now runs the control on every timing run and
the R13 verdict is three-valued: `PASS`, `FAIL`, or `INDETERMINATE` — the last
only when the control failed too, so it can never rescue a real failure. A
clean control leaves `FAIL` standing, because a control that passes proves
nothing: it may simply have run during a quiet stretch.

**What this changes for Gate 2:** nothing about the requirement, everything
about where it can be discharged. R13 must be measured on the target companion
computer with a quiet scheduler, and no verdict from this container — pass or
fail — may be quoted as evidence either way.

### W-7 The first heartbeat is discarded on every connection

**Found after the freeze**, by the v1.1 equivalence instrument
(`tests/test_adapter_core_equivalence.py`), not by any v1 test.

`csia/runtime/plugins.py:map_mavlink` has no clock of its own. It stamps an
untimestamped message with `ctx["t_last"]` and returns `[]` when that is unset.
`HEARTBEAT` is untimestamped, and on a real link it is the **first** message —
pymavlink's `wait_heartbeat()` guarantees it. So the first `armed` report is
thrown away on every connection, and `armed` stays `None` until the next
heartbeat about a second later.

Measured, both orderings:

| order | `map_mavlink` output |
|---|---|
| HEARTBEAT first | `[]` — armed flag discarded |
| HEARTBEAT after any timestamped message | `['vehicle_status']` |

`armed` gates the motor edges and the failsafe, so this is a real if brief
startup gap: for up to ~1 s after connecting, v1 does not know whether the
vehicle is armed.

**Not fixed.** The v1 core is frozen; changing `map_mavlink` would move the
baseline. It is pinned by `test_v1_drops_the_first_heartbeat` so the behaviour
stays visible.

**Deployment consequence.** The v1.1 adapter path does not inherit this: it
uses the monotonic deployment clock, so the armed flag is available from the
first heartbeat in any order. This is listed in
`tests/test_adapter_core_equivalence.py::INTENTIONALLY_ADDED` as a named
difference between the two ingestion paths rather than an accidental one.

---

## 4. Known simulator artifacts

| artifact | status |
|---|---|
| ESC current/rpm stub (W-5) | confirmed by source read; regression test |
| `SIM_WIND_SPD` applies no force in ArduCopter 3.3 | confirmed; the Phase-I campaign varied one axis, not two |
| `SIM_GPS_*` renamed `SIM_GPS1_*` on 4.x | confirmed; Phase-I scripts do not run unmodified on 4.8 |
| SITL vibration amplitude comes from `SIM_ACC*_RND`, not `SIM_VIB_MOT_MAX` alone | confirmed after two failed probes |
| `gpsDriftNE` monitor exists in ArduPilot but is gated `&& onGround` | confirmed by source read |
| PX4 SIH publishes no `SCALED_IMU2`, so `imu1` and the dual-IMU cross-check cannot be evaluated on that backend | confirmed under motion, 2026-08-24 |
| PX4 SIH publishes `BATTERY_STATUS` at ~9.7 Hz with `current_battery = -1` — implemented stream, no sensor | confirmed; 387 sentinel frames in 40 s |
| PX4 `MAV_CMD_NAV_TAKEOFF` param7 is AMSL, not height above home | confirmed by source read (`navigator/takeoff.cpp:193-210`) |
| PX4 has moved diagnostics off `STATUSTEXT` to the `EVENT` protocol (410/411) | confirmed; 0 STATUSTEXT and 15 event frames in the same run |

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
