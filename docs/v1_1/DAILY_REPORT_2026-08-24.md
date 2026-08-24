# CSIA v1.1 — engineering report, 2026-08-24

**Branch:** `claude/code-reviewer-repo-export-zicovg`
**Commits:** `b5e5f17` → HEAD
**Tests:** 696 passing (634 at start of day)
**Frozen core:** untouched — `tests/test_v1_frozen.py` green, no `FROZEN_PATHS`
file in any diff

---

## 1. Summary

The PX4 takeoff is fixed and both platforms now qualify **PASS**. That is the
smaller half of the day. The larger half is what fixing it exposed: **a chain
of instruments that were reporting their own limitations as properties of the
thing they measured.** Eleven of the eighteen defects below are that one
shape, and not one of them was visible to a passing test suite.

Every fix in this report was verified before being written up. Where a
hypothesis was refuted, the refutation is recorded too — a refuted hypothesis
is a result.

---

## 2. Defect ledger

### 2.1 The PX4 takeoff — seven defects, one cause

| # | defect | fix |
|---|---|---|
| 1 | `MIS_TAKEOFF_ALT` never set; PX4 used its 2.5 m default | set explicitly, readback verified |
| 2 | every parameter sent as `INT32`, including floats | typed `I32` / `F32` |
| 3 | success threshold `alt_m*0.5` = 12.5 m, unreachable | `CLIMB_OK_M = 1.5` |
| 4 | harness discarded `takeoff_ack` / `arm_ack` / `takeoff_alt_param` — the exact fields added to diagnose the failure | full evidence passthrough |
| 5 | `STATUSTEXT` never requested — a RULE A null-control failure committed *while adding a null control* | requested at 10 Hz |
| 6 | PX4 console going to `DEVNULL` | captured to `px4_console.log` |
| **7** | **`param7` of `MAV_CMD_NAV_TAKEOFF` is an AMSL altitude, not a height** | **send `NaN`** |

SIH sits at 489.4 m AMSL (`SIH_LOC_H0`). The rig sent 25.0, so the commanded
target was **464 m underground**; the navigator clamped it and the vehicle
correctly did nothing (`navigator/takeoff.cpp:193-210`). `NaN` makes the
navigator use `MIS_TAKEOFF_ALT` relative to the current position.

Six rounds of hypotheses were spent before the console was read, and the
console had been discarded the whole time.

### 2.2 The decoder reported itself as the platform

Published, as a property of PX4 SIH:

> **No ESC telemetry.** `ESC_STATUS` never arrives.

PX4 was sending it at ~1 Hz throughout. The installed pymavlink carries a
reduced `common.xml` (205 messages) with no message 291, so
`MAVLink.decode()` returned `MAVLink_unknown` and every frame was counted as
`UNKNOWN_291`, binned with the traffic we ignore on purpose.

The instrument could not read the message and reported the **platform** as not
sending it — the same error as calling a channel a stub because the aircraft
never moved. It survived review because "never arrived" and "I cannot decode
this" produce identical evidence at the layer that was looking.

Fixed twice, and the second half matters more:

1. **Decode with the vehicle's own definitions.** `csia/simulation/dialect.py`
   generates a dialect from the autopilot's own `message_definitions` and
   activates it before the connection is built. PX4: 250 message types,
   **0 undecodable frames**. ArduPilot: 300, verdict unchanged.
2. **An undecodable frame can no longer become a claim.** Every surviving
   `UNKNOWN_<id>` is resolved against the vehicle's XML; if it names a message
   the contract depends on, that channel is `UNDECODABLE` — never
   `UNAVAILABLE` — receives neither agreement nor disagreement, and the run is
   `INSTRUMENT_DEAD`.

Hidden by the old decoder: `ESC_STATUS` (291), `ESC_INFO` (290), `EVENT`
(410), `CURRENT_EVENT_SEQUENCE` (411), `CURRENT_MODE` (436),
`GNSS_INTEGRITY` (441), `ESTIMATOR_SENSOR_FUSION_STATUS` (514),
`LINK_NODE_STATUS` (8), `TIME_ESTIMATE_TO_TARGET` (380).

### 2.3 Instruments and gates

| defect | evidence |
|---|---|
| **A `FAIL` verdict exited 0.** The exit code was computed from its own conditions and the FAIL branch had none, so `make sim-px4` was green on a failing qualification | exit code now derived from the verdict; an unmapped token fails rather than passes. Verified end to end: `REAL_EXIT=1` |
| **`MissingReason.SENTINEL` declared and produced nowhere.** PX4's `-1` battery current reached the S9 flight log as `NOT_RECEIVED` — identical to a message that never came. An earlier commit claimed this was fixed; only the *tally* had been | four inputs, four distinct outputs; a real value supersedes a sentinel |
| **`HEADING_REFERENCE_LATE` declared in `VERDICTS`, returned nowhere** | now measures alignment against arming; margin 8.4 s, measured not asserted |
| **`MissingReason.OUT_OF_RANGE` unproduced — and must stay so.** A plausibility gate that drops "physically impossible" values discards exactly the evidence CSIA exists to notice | removed; a test pins the remaining set |
| **The probe counted messages and called them samples.** `esc.rpm` reported `n=17,346` for **39** actual samples — 445×, and that figure was quoted inside a committed contract row. `sd` was dwell-weighted | every count now matches its declared producer rate; **no verdict moved** |
| **Two declared publish rates wrong; freshness inherited it** | §2.4 |
| **`--speedup` accepted by the PX4 launcher and never used** | §2.4 |
| **A CI step named "determinism" that tested nothing** | §2.5 |
| **`contract_version` frozen at 1 through five contract changes** | §2.5 |

### 2.4 Publish rates, staleness, and a guard that guarded nothing

Once sample counts were honest, declared could be compared against measured:

| channel | declared | measured |
|---|---|---|
| `esc.*` (PX4) | 10 Hz | **0.97 Hz** |
| `mag.field_ut` (PX4) | 50 Hz | **13.9 Hz** |

The magnetometer figure is **not** an adapter bug. `HIGHRES_IMU` does arrive
at ~49 Hz, and honouring PX4's `fields_updated` bitmask is correct — a field
whose bit is clear is a repeat, not a measurement. The row simply had to state
the effective channel rate.

**This decided staleness.** `MaxAge` is documented as "the declared producer
rate with a 5× margin" but was a hand table that could not express a
per-platform rate, so PX4 inherited ArduPilot's 0.50 s against a 1.03 s
period. Verified with a controlled clock rather than argued:

```
age 0.40s -> NOT_QUALIFIED (blocked, as expected)
age 0.60s -> STALE   "age 0.60s exceeds 0.50s"
age 0.99s -> STALE
```

On a real PX4 deployment those channels would read stale for about half of
every publish period — invisible today only because they are blocked for other
reasons, and waiting for whoever promotes the row.

`MaxAge` now **derives from the contract per platform** (`5 / declared_rate`),
so the rule is applied rather than restated. PX4 ESC 5.0 s, ArduPilot ESC
0.50 s, PX4 mag 0.357 s.

**Then the new guard disabled itself.** `launch_px4(workdir, speedup)`
accepted the argument and never used it — SIH runs lockstep at 1.0× whatever
is asked. The rate-drift check gates on "is this run real time?", read that
from the *requested* speedup, and skipped itself on every default PX4 run. Its
first live run printed `rate drift NOT assessed: speedup 10` — the check
disabling itself on the one platform it was written for. `HONOURS_SPEEDUP` and
`effective_speedup()` now report what each platform actually does.

After the corrections: **zero rate drift on PX4**, every channel within a few
percent of its declaration.

### 2.5 Two guards that could not fail

**`tests/test_determinism.py` does not exist and never did.** The CI step
named "determinism" ran `pytest -q tests/test_determinism.py -k determin ||
true`. pytest exits 4 for a missing path and `|| true` turned it green, so the
step reported success while testing nothing. The 14 determinism tests live
across 10 other files. The step now selects them by name and is allowed to
fail; `tests/test_ci_env.py` refuses both mistakes — a workflow naming a test
path that does not exist, and any `pytest` invocation whose result is
swallowed.

**`contract_version` stayed at 1** through five commits that changed what CSIA
may consume (five `platform_qualification` rows) and what counts as fresh (two
corrected producer rates). Every flight log stamps that number so a reader can
tell which contract produced it; frozen, it made logs from materially
different contracts indistinguishable. Bumped to **2**, and the content is now
hashed: the version cannot fail to move again without a test failing. An
existing test had pinned `version == 1`, which is part of why it never moved —
bumping it broke something that looked unrelated, so it was easier not to.

The qualification result also now records the contract version and path it
qualified against. A result that cannot name its contract cannot be compared
with a later one.

---

## 3. The heading reference

PX4 prints `Preflight Fail: no heading reference` on every boot.
`estimatorCheck.cpp:648-670` emits it on one condition, `!cs_yaw_align`, which
distinguishes nothing by itself: "not yet" and "not at all" produce the same
line. If the simulation genuinely had no heading source, every magnetometer,
GNSS-course, attitude and cross-sensor result on that backend would be
contaminated and nothing in the report would show it.

From the run's own ulog:

| question | answer | source |
|---|---|---|
| when did yaw align? | **2.384 s**, never regressed | `estimator_status_flags.cs_yaw_align` |
| what aligned it? | **the magnetometer** — `cs_mag` and `cs_mag_heading_consistent` turn true at the same timestamp | same topic |
| any other source? | none: `cs_gnss_yaw`, `cs_ev_yaw`, `cs_yaw_manual` never true | same topic |
| was it healthy? | `cs_mag_fault` never, `cs_mag_field_disturbed` never | same topic |
| actually fused? | **99.87 %** of samples after alignment, **0.0 %** rejected | `estimator_aid_src_mag` |
| was the heading *correct*? | **mean 0.24°, max 1.08°**, n=13,872 | `vehicle_attitude` vs `vehicle_attitude_groundtruth` |

The last row settles it. Alignment is a claim the estimator makes about
itself; an estimator can be confidently wrong. SIH publishes ground truth, so
the estimate is checkable, and the heading is right to about a degree.

Arming was at **10.816 s**, so the observation window sat 8.4 s inside the
aligned period. Now checked automatically on every PX4 run
(`csia/simulation/ulog_check.py`): if alignment never happens, is lost, or
follows arming, the heading-dependent channels are voided and the run is
`INSTRUMENT_DEAD`. A run that could not check reports `UNVERIFIABLE`, because
"could not check" and "was fine" must never read the same.

---

## 4. Qualification status

**ArduPilot: PASS** (0 narrowings). **PX4: PASS** (5 declared narrowings).

| channel | base | PX4 row | why |
|---|---|---|---|
| `imu1.accel` / `imu1.gyro` | INFORMATIVE | **UNAVAILABLE** | SIH models one IMU; `SCALED_IMU2` never published |
| `battery.current` | INFORMATIVE | **UNAVAILABLE** | `BATTERY_STATUS` at ~9.8 Hz carrying the `-1` not-measured sentinel; no current sensor modelled |
| `esc.current` | STUB | **STUB**, different reason | PX4 publishes 0, not a liveness placeholder; the ArduPilot source citation does not apply |
| `esc.rpm` | STUB | **AVAILABLE_UNVALIDATED** | it varies on PX4 — the base row is wrong here — and it is still refused |

**A platform row can only narrow.** Effective admissibility is the AND of base
and platform, enforced in `ChannelContract`; a row that tries to admit what
the base blocks raises. Without that rule this mechanism is the easiest
imaginable way to re-admit a stub. Every row carries a reason, an evidence
path that must exist, and the measured numbers.

**`esc.rpm` deserves the emphasis.** It varies (5,545 rpm range) and is still
refused. `INFORMATIVE` requires `VALIDATED_SEMANTICS` **and** demonstrated
variation, and nobody has read the PX4 source for its units or indexing.
Admitting it because it moves would be W-5 with the sign reversed. With honest
counting it also rests on **39 samples from one 2.7 m hop**.

**Consequence that must not be lost:** CSIA's dual-IMU cross-check relation
**cannot be evaluated on PX4 SIH at all**. That is one of the two families v1
handles best, and a PX4 evaluation that does not say so is omitting it.

---

## 5. Timing (R13 ≤ 2 ms/tick)

Moving the telemetry tee out of CSIA's interpreter is real and in the
predicted direction:

| | tee as thread | tee as process |
|---|---|---|
| tick median | 1253.9 µs | **1125.8 µs** |
| p99 | 2118.5 µs | **1768.2 µs** |
| core phase median | 1097.7 µs | **952.2 µs** |
| over 2 ms | 9 / 751 | **2 / 751** |

It is also the faithful arrangement: on an aircraft the tee is the GCS or a
UART split, never a thread inside CSIA.

But it does not close the gap, and chasing it further would have been wrong,
because **the latency instrument had no null control.** A loop of constant
arithmetic — no CSIA, no I/O — sized to the tick's own median, same process:

```
median 508.9 us  p95 706.0  p99  847.1  max  2057.7  over-2ms  1/751
median 520.6 us  p95 812.5  p99 2067.0  max 26730.8  over-2ms 10/751
median 492.2 us  p95 890.0  p99  995.9  max  4160.9  over-2ms  1/751
```

In a live run the same day the control went over **15/749** while CSIA went
over **9/749**. The full v1.1 stack is quieter than a busy loop on this host.

**The honest split:**

- **Central tendency is measurable and sound.** Deterministic replay of a real
  30 s flight: core median **430–495 µs**, p95 604–848 µs, against a 2000 µs
  budget.
- **The deadline property R13 actually asserts is not measurable on shared
  cloud infrastructure.** The instrument's noise floor exceeds the budget.

R13 is now three-valued — `PASS` / `FAIL` / `INDETERMINATE` — and
`INDETERMINATE` requires the control to have failed too, so it can never
rescue a real failure. A clean control leaves `FAIL` standing, because a
control that passes proves nothing: it may have run during a quiet stretch.
That case occurred and the `FAIL` was left standing.

**No verdict from this container, pass or fail, is admissible as evidence
about R13.**

---

## 6. Gate 2

`tools/deploy/gate2_timing.py` turns "measure it at Gate 2" from a sentence
into a command. It runs on the companion computer: no autopilot, no SITL, no
simulator, no network, no pymavlink. It replays a recorded shadow flight log
through the frozen core — exactly the per-tick work R13 constrains, with the
data a real flight produced.

It reports **two** things that must not be confused: the R13 verdict, and
whether the environment is fit to certify one. Scheduling policy, priority,
affinity, CPU governor and isolated CPUs are read from the kernel, never
assumed. An unreadable governor counts as unfit — a deadline measured under a
clock rate the process cannot see is not certifiable.

On this container it correctly answers:

```
=== scheduling: policy SCHED_OTHER prio 0, affinity [0,1,2,3], governor None
    *** NOT A CERTIFICATION ENVIRONMENT. Missing: a real-time policy
        (chrt -f 80 ...), CPU pinning (taskset -c N ...), a READABLE CPU
        governor (none exposed here, so the clock rate is set by something
        invisible to this process)
=== CERTIFIABLE AT GATE 2: NO
```

`make gate2-timing LOG=<flight.jsonl>`.

---

## 7. Hypotheses tested and refuted

| hypothesis | outcome |
|---|---|
| GC pauses cause the tick outliers | **refuted** by control: gc on max 1877 µs, gc off max 1674 µs, 0/751 over budget either way |
| `MaxAge` had drifted from its own 5× rule | **refuted** — every entry matched the declared rate. The *declaration* was wrong |
| a contract channel missing from `GROUP_OF`, silently never reaching the core | **refuted** — all 18 grouped |
| `battery.voltage` is a W-5-style stub on PX4 | **refuted** under load: range 0.689 V, sd 0.229. Recording it as UNCONFIRMED rather than as a finding was correct |

---

## 8. Open items

- Three PX4 contract rows await an owner's decision: `imu1.*` and
  `battery.current` are narrowed to `UNAVAILABLE`; promoting `esc.rpm` needs a
  source read of `ESC_STATUS.hpp` and the `esc_status` uORB definition.
- Dual-IMU cross-check cannot be evaluated on PX4 SIH.
- Gate 2 target-hardware timing — no ARM part available in this container.
- 37 bibliography entries (H-6) remain a submission blocker by design.
- `DiagnosticState.RECOVERING` and
  `Recommendation.INCREASE_NAVIGATION_UNCERTAINTY` are advisory vocabulary v1
  cannot emit. In the frozen core; recorded, not touched.

---

## 9. The pattern

Every significant defect today was an instrument misattributing its own
limitation:

- a decoder reporting its blind spot as the platform's silence;
- a probe counting messages and calling them samples;
- a timing harness charging its own GIL contention to the core;
- a rate guard reading a flag the simulator ignores;
- a CI step naming a file that does not exist and swallowing the error;
- a contract version that never moved while the contract did.

None was visible to a passing test suite. Every one was caught by a control
rather than by inspection. The guards added all have the same shape: **make
the instrument state what it could not see, and refuse to issue a claim in
that region.**

Three of these defects were introduced earlier the same day by this work, and
one was a commit message describing a fix that had not actually been made.
