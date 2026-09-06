# Mechanism A repeated campaign — execution status

**Companion to** `MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md`, and written
**after** it. The preregistration is not amended by anything recorded here.

---

## 1. Environment

| item | measured |
|---|---|
| ArduPilot SITL installed at session start | **no** — `sim_vehicle.py`, `arducopter` and `px4` all absent |
| `firmware.ardupilot.org` | unreachable (000 through the agent proxy) |
| `github.com` clone of ArduPilot | **works** — 821 MB shallow clone in under 60 s |
| toolchain | gcc, g++, make, cmake, ninja all present |
| disk | 22 GB free |
| PX4 | **not attempted** — see §4 |

## 2. The build

**The preregistered build was reproduced exactly.**

```
$ git checkout 01a504b472259602e13df4cf07df7c0cdbb35993   # authored 2026-08-23
$ ./waf configure --board sitl && ./waf copter            # 4m 02s
$ python research/phase2/modern_replication.py --out /tmp/probe-orig.json
status: MODERN_TARGET_AVAILABLE
  firmware   ArduCopter V4.8.0-dev @ 01a504b4
  new params ['SIM_GPS1_ENABLE', 'SIM_GPS1_GLTCH_X', 'SIM_GPS1_NUMSATS']
  old params []
```

`ArduCopter V4.8.0-dev @ 01a504b4` is the string the committed artifacts record
(`research/phase2/results/modern_replication.json`,
`.../heldout_raw/CAPTURE_INDEX.json`, `.../STAGE2_1_KILL_TEST.json`). The
injection parameter the preregistration names is present and the pre-4.x names
are absent.

Reaching the commit needed `git fetch --deepen=4000`; a `--depth 1` clone does
not contain it.

## 3. Pipeline

`tools/deploy/shadow_sitl_check.py` — the existing driver, unchanged — was
pointed at the rebuilt binary via `CSIA_AP_ROOT`. A validation flight:

```
=== ardupilot SITL launched -> tcp:127.0.0.1:5760
=== rig: arming and climbing (rig authority, not CSIA)
    armed=True climbed=13.29 m
=== command authority: NO_COMMAND_PATH_REACHABLE (write_half=CLOSED_ENOTCONN)
=== live transmit probe: command_long_send: denied; set_mode_send: denied;
                          rc_channels_override_send: denied
    [t+12.0s] INJECTED gps_fix_loss: SIM_GPS1_ENABLE = 0; readback=0.0 -> CONFIRMED
failsafe NORMAL -> CAUTION @ t=14.1s: GPS data invalid
=== ticks: 751  messages: 104127
```

751 ticks against the original artifact's 751, and 104,127 messages against
104,112. The injection is confirmed by **readback**, not by the write
returning success — COMMAND ISSUED ≠ FAULT INJECTED.

`tools/csia_experiment/run_mechanism_a_repeat.py` wraps the driver, adjudicates
each flight through the eight-state vocabulary and writes an immutable
manifest per trial.

### 3.1 Two runner defects, both caught on a 1+1 validation pair

Recorded because the point of a validation pair is to find these before 40
trials, and it did.

1. **Driver exit code read as a rig fault.** `shadow_sitl_check.py` returns 0
   for R13 PASS, 2 for INDETERMINATE, 1 otherwise — the exit code is *purely
   the tick-latency verdict*. The first runner mapped non-zero to
   `rig_faults`, and both trials of the validation pair adjudicated
   `HARDWARE_FAULT` on a contended host. That is precisely the misreading §5
   exists to prevent. Fixed: a rig fault now requires a flight that produced
   no usable telemetry.
2. **Control arm read as INSTRUMENT_DEAD.** The driver always writes an
   `injection` block; on a control flight it is a role marker,
   `{"kind": null, "role": "CONTROL: fix preserved"}`. Testing
   `not bool(injection)` declared the control arm to have moved — which under
   RULE A would have made the entire campaign unreadable, both arms, because a
   dict was non-empty. Fixed: the test is whether a *parameter was written*.

## 4. Scope actually run

| platform | status |
|---|---|
| ArduPilot | **RUN** — 20 FAULT + 20 CONTROL, interleaved |
| PX4 SIH | **NOT RUN** |

PX4 is `NOT_RUN`, not `NO_DIFFERENCE`. The preregistration analyses the two
platforms separately and never pools them (§3), so an ArduPilot-only campaign
is an ArduPilot result. Building PX4 SIH requires its own toolchain and was not
attempted in this session.

## 5. The timing caveat, stated before any number is read

**No latency or timing claim may be made from this campaign.**

These trials share a container with the rest of this session's work. The
driver's own host-noise control — constant work, same process — measured a
966 µs median against the 946.7 µs median of the real tick, so most of the
variance is the host rather than the stack.

Latency is therefore **recorded and not adjudicated**: `timing_budget` is
deliberately absent from every trial record, which leaves the timing predicate
*undecidable* rather than false, and every manifest carries it in its
`undecidable` list. The full latency distribution and the R13 verdict are
preserved per trial under `latency_recorded_not_adjudicated` and
`r13_verdict_recorded_not_adjudicated`.

This is the preregistration's design working as written: `TIMING_INSUFFICIENT`
is last in precedence because a trial can be timing-insufficient for a latency
claim and still be valid evidence for a categorical one.

## 6. Results

Machine-readable, and the authority for anything quoted:

* `campaigns/physical_validation/mechanism_a_repeat_ap/_plan.json` — the
  denominator, written before the first trial
* `campaigns/physical_validation/mechanism_a_repeat_ap/MECHA-ARDUPILOT-*.json`
  — one immutable, content-hashed manifest per trial
* `campaigns/physical_validation/mechanism_a_repeat_ap/_report.json` — the
  reconciliation; `planned = valid + invalid + not_attempted` must balance or
  the report raises rather than printing

**The reconciled outcome is in `_report.json` and is not restated here**, so
that a number in prose cannot drift from the artifact it came from. That is the
rule FL-002 exists for.

## 7. What this campaign does not establish

Unchanged from §9 of the preregistration, and repeated because a status
document is what gets read:

* **E1 in, E1 out.** Nothing about physical hardware, real sensors or flight.
* **Nothing about PX4.**
* **Nothing about the signature table.** No amount of repetition tests whether
  a relation behaves as its `LOW(h)` entry says.
* **No frequency claim about deployed systems.** These are simulator runs on
  one pinned build.
* **No timing claim**, for the reason in §5.
