# STALENESS RUNTIME SPEC — Phase 4.5 §§3–11

Gate B. One canonical rule for "how old may a measurement be before it stops
being evidence", replacing two layers that disagreed.

Implementation: `csia/v1_1/staleness.py`.
Applied at: `csia/deploy/shadow.py`.
Evidence: `validation/v1_1/deployment/`.

    GATE B  nominal-rate   PASS
    GATE C  hard-dropout   PASS

---

## 1. THE CORRECTION THAT COMES FIRST

Phase 4 §68 predicted that on a live PX4 shadow flight `motor_esc` would be
treated as stale for roughly 0.9 s of every 1.0 s. **That prediction was
wrong, and the reproduction is what found it.**

`motor_esc` never reaches the frozen core on **either** platform, because its
channels are not admissible:

| platform | `esc.rpm` | `esc.current` |
|---|---|---|
| ArduPilot | `STUB_OR_NONINFORMATIVE` | `STUB_OR_NONINFORMATIVE` |
| PX4 | `AVAILABLE_UNVALIDATED` | `STUB_OR_NONINFORMATIVE` |

`to_core_samples` emits a sensor only when **every** required channel is
usable, and usability is decided by the qualification contract **before any
watchdog runs**. The Phase 4 arithmetic was right — a 1 Hz stream against a
0.1 s watchdog does leave the node stale 90% of the time — but the conclusion
skipped a layer. The node is withheld one level earlier, so the watchdog never
gets to be wrong about it.

`PX4_MOTOR_ESC_STALENESS_PRE_FIX.csv` and `..._POST_FIX.csv` are the record:
`motor_esc_reached_core` is **False on every tick in both arms**, at 0.1 s and
at 5.0 s. Two arms, opposite timeouts, identical result — which is exactly how
you tell that the timeout is not the cause.

**The pre-fix reproduction produced a negative result and it is committed as
one.** Phase 4's claim is corrected in §76–77 of the review report rather than
quietly dropped.

## 2. ARE THE TWO TIMEOUTS THE SAME CONCEPT? — §6

**Yes. Same concept, two layers, two different rate assumptions.**

| | `MaxAge` | `STALE_TIMEOUT_S` |
|---|---|---|
| file | `csia/aircraft/adapters/base.py:42` | `csia/runtime/online.py:47` |
| layer | canonical ingestion (v1.1) | frozen trust layer (v1) |
| keyed by | channel | node |
| question | may this channel still appear in an `AircraftSample`? | may this node's evidence still enter the trust update? |
| stated rule | `MAX_AGE_MARGIN(5) / declared_rate_hz`, **derived per platform** | "~5x the sensor's nominal period", **hand-written, one table** |

Both answer *"how many producer periods of silence before this measurement
stops counting as evidence"*, and both apply the same margin of five periods.
They disagree because one derives the period from the channel contract per
platform and the other has it baked into a constant, and the frozen core
cannot derive it — by design, it knows nothing about adapters.

Two undocumented meanings are not retained. There is **one** rule, below.

## 3. THE CANONICAL RULE

    runtime_stale_timeout[node] = max over required channels of max_age[channel]

    max_age[channel] = MAX_AGE_MARGIN / declared_rate_hz   (per platform)
                       -> MaxAge table -> DEFAULT_MAX_AGE

**In one sentence: the runtime watchdog agrees with the ingestion layer that
feeds it.** A node's evidence is withdrawn by the trust layer at the same
moment ingestion withdraws the channel it depends on, instead of up to 4.9 s
earlier.

**Why `max` and not `min`.** A node reaches the core only when *every*
required channel is usable, so it stops arriving when its **slowest-permitted**
channel stops being usable. A timeout set from the fastest channel would fire
while the node was still legitimately arriving.

> Phase 4 §68 said "node timeout = `min` over the channels the node requires".
> The wording was wrong; `max` is correct. **No published number changes** —
> every node's required channels share a declared rate on both platforms, so
> `min` and `max` coincide throughout the table. Recorded because a
> justification that happens to give the right answer is still the wrong
> justification.

### No new constant — §9

`MAX_AGE_MARGIN = 5.0` is **imported** from
`csia/aircraft/adapters/base.py`, where it was already declared and already
justified: *"a channel that has missed five consecutive publications is not
slightly old, it is gone."* The same factor of 5 already appears in
`ulog_source.stale_timeouts(factor=5.0)`, which has derived per-source
timeouts on the replay path since before this phase.

§9 forbids optimising a multiplier after seeing the matrix. There is no
multiplier in `csia/v1_1/staleness.py` to optimise — a test asserts the module
defines no numeric literal of its own and that `channel_max_age` agrees with a
live adapter's `_derive_max_age` on every channel.

### The derived map

| node | ArduPilot | PX4 | frozen | driving channel |
|---|---:|---:|---:|---|
| `imu0` | 0.200 | 0.100 | 0.05 | `imu0.accel` (25 / 50 Hz) |
| `imu1` | 0.200 | 0.200 | 0.05 | `imu1.accel` (25 Hz) |
| `baro` | 0.500 | 0.500 | 0.10 | `baro.altitude` (10 Hz) |
| `mag` | 0.200 | 0.357 | 0.10 | `mag.field_ut` (25 / 14 Hz) |
| `gps` | 1.000 | 1.000 | 0.50 | `gnss.position` (5 Hz) |
| `motor_esc` | 0.500 | 5.000 | 0.10 | `esc.current` (10 / 1 Hz) |
| `battery` | 0.500 | 0.500 | 0.50 | `battery.current` (10 Hz) |
| `vibration` | 0.500 | 0.500 | 0.50 | `vibration.rms` (10 Hz) |

`battery` and `vibration` are unchanged — the frozen table was right wherever
the sensor really does publish at the 10 Hz it assumed.

## 4. WHAT WAS ACTUALLY BROKEN — AND IT IS SMALLER THAN CLAIMED

Measured over the **admissible** nodes only, `STALENESS_MATRIX.csv`,
8 nodes × 4 conditions × 2 platforms × 2 arms.

**At exactly nominal rates, nothing false-stales.** Zero exposure on every
admissible node, both platforms, both arms. The frozen defaults are adequate
when the wire is perfect.

**Under ±30% rate jitter, `baro` false-stales:**

| platform | node | frozen timeout | stream | false-stale fraction |
|---|---|---:|---|---:|
| ArduPilot | `baro` | 0.10 s | `SCALED_PRESSURE` 10 Hz | **2.77%** |
| PX4 | `baro` | 0.10 s | `SCALED_PRESSURE` 10 Hz | **3.69%** |

The frozen `baro` timeout is 0.10 s against a 0.10 s nominal period — the
margin is exactly zero, so **any** positive jitter trips it. Under the derived
0.50 s the exposure is **0.00%** on both platforms.

That is the whole of the reproduced defect: one node, ~3% of ticks, only under
jitter. It is real, it is worth fixing, and it is not the 90% figure Phase 4
predicted for a different node.

## 5. THE COST OF THE FIX — §7

Every derived timeout is **longer**, so the risk is delayed detection of a
genuinely dead source. Measured on the `SUSTAINED_DROPOUT` control, admissible
nodes only:

| platform | node | frozen → derived timeout | frozen → derived detection latency |
|---|---|---|---|
| ArduPilot | `imu0` | 0.05 → 0.20 | 0.08 → **0.24 s** |
| ArduPilot | `imu1` | 0.05 → 0.20 | 0.08 → **0.24 s** |
| ArduPilot | `mag` | 0.10 → 0.20 | 0.12 → **0.24 s** |
| ArduPilot | `baro` | 0.10 → 0.50 | 0.16 → **0.56 s** |
| ArduPilot | `gps` | 0.50 → 1.00 | 0.56 → **1.08 s** |
| ArduPilot | `battery`, `vibration` | unchanged | 0.56 s, unchanged |
| PX4 | `imu0` | 0.05 → 0.10 | 0.08 → **0.12 s** |
| PX4 | `mag` | 0.10 → 0.357 | 0.12 → **0.36 s** |
| PX4 | `baro` | 0.10 → 0.50 | 0.16 → **0.56 s** |
| PX4 | `gps` | 0.50 → 1.00 | 0.56 → **1.08 s** |
| PX4 | `vibration` | unchanged | 0.56 s, unchanged |

**Every latency is `timeout + one to two ticks`**, and every node still
detects a hard dropout. Worst case moves from 0.56 s to **1.08 s**, on `gps`.

The bound is not an empirical accident: detection fires on the first tick at
which `age > timeout`, so latency ∈ `(timeout, timeout + 1/tick_hz]` by
construction. Nothing here is tuned to make a number look acceptable — the
timeouts come from the contract and the latencies follow from them.

**The false-stale problem was not fixed by making detection arbitrarily slow.**
The largest relaxation is `baro` at 5×, and it buys 0.40 s of extra detection
latency to remove a 3% false-stale rate on a node whose evidence gates the
`altitude_baro` relation.

## 6. WHAT ELSE THE MATRIX FOUND

**`mag` is not an independent stream on either platform.** It rides
`SCALED_IMU` on ArduPilot and `HIGHRES_IMU` on PX4. The contract declares
`mag.field_ut` at 25 / 14 Hz, but those rates cannot be realised separately —
the magnetometer arrives exactly as often as `imu0` does. Its derived timeout
is therefore more conservative than it needs to be, which is harmless, and the
declared rate should not be read as an independent producer rate.

**Three of eight nodes are inadmissible on PX4** — `imu1` and
`battery.current` are `UNAVAILABLE`, `motor_esc` is stub/unvalidated — so a
PX4 shadow flight today runs on five nodes, not eight. That is a
qualification fact, not a staleness fact, and it belongs in a platform
readiness discussion rather than this one.

## 7. WHERE THE RULE IS USED

One function, three call sites, no copied numbers:

- `csia/deploy/shadow.py` — **applied**, the live/shadow path.
- Deployment-equivalent replay — `validation/v1_1/deployment/run_staleness.py`
  passes the same map.
- Any future HIL runner — same call, by construction.

The ULog CLI path already derived its own timeouts from the log's measured
topic rates (`ulog_source.stale_timeouts`) and is left as it is: a log's
logged rate is a measured fact and is the better source when it exists.

**The frozen core is not modified.** `OnlineTrustLayer` already accepted
`stale_timeout_s`; this phase computes what to pass it.

## 8. DID IT MOVE ANY PHASE 4 RESULT? — §12

**No.** `PHASE4_REGRESSION_AFTER_TIMEOUT.json`, two independent checks:

1. **Structural.** The Phase 4 runners are parsed and contain no reference to
   `OnlineTrustLayer`, `get_adapter`, `PlatformAdapter`, `ShadowRunner` or
   `build_runtime_stale_timeouts`. The nine scenarios take freshness from the
   deterministic simulator's `td.fresh`, so a runtime watchdog cannot reach
   them. **PASS.**
2. **Behavioural.** All ten Phase 4 artifacts regenerated and compared against
   the committed versions field by field. Every one is behaviourally
   identical; `FUNCTION_ELIGIBILITY_RESULTS.csv`, both acceptance controls and
   the API validation record are **byte-identical**.

Five artifacts differ in bytes only, and only in provenance: `software_sha`
moved with the commit, and it sits inside every ledger event's context by
design, so every content hash downstream of it moved with it. The excluded
fields are named in the artifact (`csia_sha`, `software_sha`,
`content_sha256`, `event_id`, `previous_event_hash`, `final_chain_hash`,
`configuration_hash`) rather than filtered silently.

    VERDICT: NO_BEHAVIOURAL_CHANGE

## 9. EVIDENCE TIERS — §4

| tier | what it is | used for |
|---|---|---|
| `REAL_PX4_ULOG_TIMING` | inter-arrival measured from real PX4 SITL logs, 241 topic rows | showing what real PX4 timing looks like on the **ULog/uORB** transport |
| `SYNTHETIC_DEPLOYMENT_REGRESSION` | the real adapter and the real `OnlineTrustLayer`, driven by synthesised MAVLink at contract-declared rates | the matrix, the pre/post reproduction, both controls |

**The matrix is tier C and is labelled tier C everywhere.** Only the wire is
synthetic — every component on the path is production code — but no physical
aircraft and no live MAVLink link was involved, and nothing here is offered as
physical evidence.

The real ULogs are informative and are **not** substituted for the MAVLink
path: they measure a different transport, whose rates differ (`esc_status` is
logged at 10 Hz there against the 1 Hz the contract declares for MAVLink
`ESC_STATUS`, and `sensor_accel` is logger-throttled to 1 Hz against a
publication rate orders of magnitude higher). Reading ULog rates as MAVLink
stream rates would be exactly the substitution §4 warns about.

## 10. WHAT IS STILL NOT CLOSED

- **No live MAVLink link was exercised.** Tier A remains unavailable in this
  environment. The stream rates are the contract's declared rates, not
  measured ones.
- **`motor_esc` is unusable on both platforms** for reasons that have nothing
  to do with staleness. Promoting `esc.rpm` on PX4 needs a source read, not
  another flight — the contract says so in its own justification field.
- **`imu1` and `battery.current` are `UNAVAILABLE` on PX4.**
- **Jitter is modelled as ±30% uniform on the nominal period**, seeded and
  reproducible. Real link jitter is not uniform and can be much worse; a
  bursty-loss model is not covered here.
