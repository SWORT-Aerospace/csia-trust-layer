# Field integration runbook — plugging CSIA into a real system

**Read §0 before anything else.** The rest of this document assumes you have
accepted what CSIA is.

This runbook covers software integration, what to expect at each stage, how to
measure it, and how to prove or disprove each hypothesis. It does **not**
repeat the hardware build: boards, wiring, power and the fault injector are in
`hardware/validation_rig/E2_BUILD_PACKET.md` and
`hardware/validation_rig/FAULT_INJECTOR_PROTOCOL.md`. The bench-to-flight gate
sequence is in `docs/hardware_validation.md`.

---

## 0. What CSIA is, and the two things it cannot do

CSIA is a **read-only observer**. It consumes telemetry, maintains a trust
value per sensor, diagnoses causes, and writes a flight log. It produces
*recommendations* in that log.

**It has no command path to the autopilot, in any mode.** There are two modes,
`SHADOW` and `ADVISORY`, and both report `may_command = False`. There is
deliberately no `ACTIVE` member of that enum — adding one is a separate safety
work package. The read-only connection denies 21 send-capable attribute names;
preflight proves this on your build, every time.

Two consequences you must design around:

1. **CSIA will never save your aircraft.** If it says EMERGENCY, a human or
   the autopilot's own failsafe must act. Nothing in CSIA acts.
2. **CSIA failing does nothing to the aircraft.** Kill the process mid-flight
   and the vehicle does not notice. This is the point.

Fly with props off until `docs/hardware_validation.md` Gate D says otherwise.

---

## 1. Physical topology

```
   ┌───────────────┐   telemetry (MAVLink)    ┌────────────────────┐
   │ flight        │ ────────────────────────►│ companion computer │
   │ controller    │                          │   running CSIA     │
   │ (ArduPilot /  │ ◄───── NOT CONNECTED ────│  (RX wire cut)     │
   │  PX4)         │                          └────────────────────┘
   └───────────────┘
```

The receive wire into the flight controller is **cut on purpose** (E2 build
packet §4.1). The software guard and the missing copper are two independent
barriers, and you want both: software can be misconfigured, a cut wire cannot.

CSIA runs on the companion computer. It never runs on the flight controller.

---

## 2. Install and prove the build

```bash
git clone <repo> csia-trust-layer && cd csia-trust-layer
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,mavlink,logs]"
```

Then, **before every session**:

```bash
.venv/bin/python tools/deploy/preflight.py \
    --platform ardupilot \
    --out logs/preflight-$(date -u +%Y%m%dT%H%M%SZ).json
```

Ten checks, three outcomes, and **only `READY` is green**:

| verdict | meaning |
|---|---|
| `READY` | every check passed |
| `DO_NOT_FLY` | at least one check failed |
| `INCONCLUSIVE` | a check could not run — **this is not a pass** |

What it proves, and why each matters:

| check | why you care |
|---|---|
| `frozen_core_vs_tag` / `_vs_source_digests` | the algorithm is the one the evidence describes. Two independent methods, because the tag is local-only on a fresh clone and the digests are reproducible anywhere |
| `working_tree_clean` | a run from an uncommitted tree cannot be attributed to a commit, and its log will name one that does not describe it |
| `no_mode_claims_command` | both modes report `may_command=False` |
| `read_only_connection_has_no_transmit_surface` | 21 send-capable names, all DENIED or ABSENT, **on this build** |
| `staleness_timeouts_derived` | the watchdog agrees with the ingestion layer; no constant was introduced |
| `failsafe_policy` | which failsafe will be in force, stated *before* the flight |
| `log_dir_writable` / `_free_space` | the log **is** the trial. Under 200 MB fails |

Keep the preflight JSON with the flight log. A trial without one is a trial you
cannot attribute.

---

## 3. Connect

```bash
.venv/bin/csia-shadow \
    --config configs/vehicle/example_quad.yaml \
    --platform ardupilot \
    --connection udp:0.0.0.0:14550 \
    --log-dir logs/field \
    --context vehicle
```

Copy `configs/vehicle/example_quad.yaml` and edit it for your airframe. The
config is hashed into the log header, so a changed config is visible later.

**Connection strings:** `udp:0.0.0.0:14550` (listen — usual for a companion on
the same network), `/dev/ttyACM0` or `/dev/serial0` with a baud rate for a
direct serial link. It must be a link the autopilot is *sending* on.

**Start with a self-test**, which needs no vehicle:

```bash
.venv/bin/csia-shadow --self-test --self-test-seconds 10
```

### Turning on loss-of-data supervision

```bash
.venv/bin/csia-shadow ... --data-loss-supervision
```

The frozen failsafe alarms when a sensor's *trust* falls, and for seven of the
eight nodes says nothing when the sensor **stops delivering** (SR-001). The
overlay supplies the missing rule and can only *raise* the level, never lower
it. It is **off by default** and the log header records
`failsafe_policy: FROZEN_ONLY` or `FROZEN_PLUS_DATA_LOSS_SUPERVISION`.

**Logs from the two are not comparable.** Pick one per campaign, or run the
same trial twice and compare deliberately. See `docs/SUPERVISION_LAYER.md`.

---

## 4. What to expect, stage by stage

Each row is falsifiable. If you see something else, that is a finding — write
it down before you explain it.

### Stage 1 — link up, vehicle disarmed on the bench

| observe | expect | how to measure |
|---|---|---|
| messages arriving | non-zero and rising | `stats.messages` in the log footer |
| tick rate | 25 Hz | `stats.ticks` ÷ wall seconds |
| trust, all nodes | rises from the 0.8 Beta prior toward ≥ 0.88 | `trust_post` per tick |
| failsafe level | `NORMAL` | `policy.level` |
| **first 10 s** | **no failsafe action at all** | `arm_time = 10.0 s`: the policy does not arm before then |

If trust does *not* climb above ~0.88 on a healthy bench vehicle, stop. Either
the channel mapping is wrong or the vehicle is not healthy — do not fly to find
out which.

### Stage 2 — sensors present, still disarmed

| observe | expect |
|---|---|
| `armed` in the log | `false` (real vehicle status, not the time proxy) |
| motor-coupled edges | gated **out** (weight 0.0) |
| worst trust across nodes | stays > 0.7 |

A disarmed ground idle with *no* `vehicle_status` drives the motor edges fully
inconsistent — measured worst ≈ 0.84 versus ≈ 0.99 armed-aware. If you see
that, your autopilot is not sending vehicle status and CSIA is falling back to
a time proxy. Fix the stream, don't reinterpret the number.

### Stage 3 — armed, props off, throttle up

| observe | expect |
|---|---|
| trust | stays high; motor edges now gated **in** |
| vibration node | responds to real rotor loading |
| latency | p99 **under 2000 µs/tick** (the R13 budget) |

### Stage 4 — induced faults (fault injector, props off)

The injector cuts a sensor line; see `FAULT_INJECTOR_PROTOCOL.md`. Per-sensor
staleness timeouts, **derived from the channel contract**, not chosen:

| node | ArduPilot | PX4 |
|---|---|---|
| imu0 | 0.200 s | 0.100 s |
| imu1 | 0.200 s | 0.200 s |
| mag | 0.200 s | 0.357 s |
| baro | 0.500 s | 0.500 s |
| battery | 0.500 s | 0.500 s |
| motor_esc | 0.500 s | 5.000 s |
| vibration | 0.500 s | 0.500 s |
| gps | 1.000 s | 1.000 s |

Expected response to a **cut line**:

| cut | frozen policy | with `--data-loss-supervision` |
|---|---|---|
| GPS | `CAUTION` ("GPS data invalid") | `CAUTION` (unchanged) |
| mag | **NORMAL — no alarm** | `CAUTION` |
| battery | **NORMAL — no alarm** | `CRITICAL` |
| baro | **NORMAL — no alarm** | `CAUTION` |
| motor_esc | **NORMAL — no alarm** | `CAUTION` |
| one IMU | **NORMAL — no alarm** | `CAUTION` |
| **both IMUs** | **NORMAL — no alarm** | **`EMERGENCY`** |

The left column is not a bug report — it is SR-001, measured and recorded. It
is why the overlay exists.

Timing to expect: a condition must hold `dwell_up = 1.0 s` before it escalates,
and `dwell_down = 5.0 s` of health before it de-escalates. **A recovery time
under 5 s is therefore impossible** and would mean your clock is wrong.

### Stage 5 — degraded data rather than absent data

Trust thresholds, from the frozen config:

| rule | threshold | level |
|---|---|---|
| `nav_caution` (gps) | 0.75 | CAUTION |
| `heading_caution` (mag) | 0.60 | CAUTION |
| `struct_critical` (vibration) | 0.60 | CRITICAL |
| `power_critical` (battery) | 0.70 | CRITICAL |
| `att_caution` (best IMU) | 0.82 | CRITICAL |
| `att_emergency` (best IMU) | 0.70 | EMERGENCY |

**`baro` and `motor_esc` have no trust threshold at all.** Degrade either and
the frozen failsafe will not alarm, ever. That is a property of the rule set,
not a fault.

---

## 5. How to measure each part

| what | tool | output |
|---|---|---|
| build identity, safety | `tools/deploy/preflight.py` | `preflight.json`, verdict |
| per-tick everything | the flight log itself | `logs/field/*.jsonl` |
| core cost per tick | `tools/deploy/profile_core_from_log.py <log>` | µs/tick, over-budget count vs 2000 µs |
| decisions reproduce | `tools/assurance/decision_replay.py` | four-way verdict |
| resource envelope | `tools/assurance/resource_envelope.py` | CPU/RSS |
| survives a kill | `tools/assurance/process_recovery.py` | recovery behaviour |
| config actually applied | `tools/assurance/config_proof.py` | what was in force |
| host fingerprint | `tools/assurance/portability_probe.py` | OS/kernel/interpreter |

Run the whole set nightly with `scripts/optiplex_nightly.sh`.

**One caution on decision replay.** It is currently `DIVERGENT` on both
platforms (HF-004, HF-010). On ArduPilot the categorical differences fell from
511 to 13 once the hand-off reconstruction was fixed; PX4 is unchanged at 144
with an unattributed cause. **Do not treat replay agreement as a gate yet.** A
`decision_replay FAIL` in a nightly is the current, correct state.

---

## 6. Proving out a hypothesis

The protocol matters more than the tooling. Four rules, in order:

1. **Write the prediction down before the run**, with the number and the
   instrument that will produce it.
2. **Declare what would falsify it.** A hypothesis with no failing outcome is
   not a hypothesis.
3. **Run it, and keep the log whether or not you like the answer.**
4. **Record the result in `research/physical_validation/FAILURE_LEDGER.yaml`**
   — including, especially, the ones that failed.

A preregistration template lives in `research/physical_validation/prereg/`.

### The hypotheses worth testing first, and how each falsifies

**H1 — the core is cheap enough to run on the companion computer.**
Predict: p99 core time < 2000 µs/tick over ≥ 10 minutes.
Measure: `profile_core_from_log.py`, `over_budget` count.
Falsified by: any sustained excursion. Note the *distribution*, not the mean —
the tail is what misses a deadline.

**H2 — a cut sensor line is detected within its declared timeout + dwell.**
Predict: for node *n*, escalation at cut + `timeout(n)` + 1.0 s (dwell_up),
using the table in §4.
Measure: injector `cut` timestamp against the first transition in the log.
Falsified by: no escalation, or an escalation materially outside that window.
**Note that for seven of eight nodes the frozen policy predicts NO escalation
at all** — that is the SR-001 baseline, and it is the control for H3.

**H3 — the supervision overlay closes SR-001 on real hardware.**
Predict: same trials with `--data-loss-supervision` escalate per the right-hand
column of §4, and a clean flight stays `NORMAL` throughout.
Measure: run each cut twice, once per policy; compare `frozen_level` against
`level` in the same log.
Falsified by: any escalation on a clean flight (a false alarm is worse than the
gap it fills), or any case where the effective level is *below* the frozen one.
In simulation: detection 783/1000 → 969/1000, **0 detections lost**.

**H4 — trust recovers when the sensor returns.**
Predict: return to `NORMAL` no sooner than `dwell_down = 5.0 s` after restore.
Measure: `restore` timestamp to the de-escalation transition.
Falsified by: recovery faster than 5 s (impossible — suspect the clock) or no
recovery at all.

**H5 — CSIA cannot command the vehicle.**
Predict: zero bytes transmitted for the whole flight.
Measure: preflight probe evidence in the header, *plus* an independent packet
capture on the link. **Do not rely on CSIA to prove CSIA is silent.**
Falsified by: a single transmitted byte. This one is not negotiable.

**H6 — the same log replays to the same decisions.**
Currently **expected to fail** — see §5. Run it to watch the number move, not
as a gate.

### What a negative result is worth

A negative result that is recorded is worth more than a positive one that is
not. The ledger has 54 entries and the majority are things that did not work,
including several where the *instrument* was wrong rather than the system.
That is the point of keeping it.

---

## 7. What CSIA cannot tell you

- **Whether the aircraft is safe to fly.** It observes sensor consistency.
- **Anything about a sensor it cannot name.** `baro` and `motor_esc` have no
  cause label in the diagnosis vocabulary, so a fault on either is
  structurally unnameable however clearly the trust layer sees it.
- **Why a dropout happened.** A dropout is *detected* (freshness) but never
  *attributed* — the causal diagnosis reads `nominal` throughout, because
  absence supplies no inconsistency to reason about.
- **Anything about RF jamming, GNSS multipath, or control-surface flutter.**
  There is no primitive for any of them; see `docs/STRESS_TESTING.md` §6.
- **Sub-threshold degradation.** In simulation, 31 of 1000 stress variations
  stay undetected — dominated by slow `bias_drift` that never crosses a trust
  threshold. Characterising that detection floor on real hardware is itself a
  worthwhile experiment.

---

## 8. Minimum viable first session

```bash
# 1. prove the build
.venv/bin/python tools/deploy/preflight.py --platform ardupilot --out pf.json

# 2. no vehicle needed
.venv/bin/csia-shadow --self-test --self-test-seconds 10

# 3. bench, disarmed, 10 minutes — expect trust >= 0.88, level NORMAL
.venv/bin/csia-shadow --config configs/vehicle/<yours>.yaml \
    --connection udp:0.0.0.0:14550 --log-dir logs/field --max-seconds 600

# 4. what did it cost?
.venv/bin/python tools/deploy/profile_core_from_log.py logs/field/<log>.jsonl
```

If all four are clean you have a working integration and H1 answered. Stage 4
onward needs the fault injector.
