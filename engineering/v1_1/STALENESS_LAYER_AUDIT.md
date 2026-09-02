# STALENESS LAYER AUDIT — Phase 4 §27

The banked blocker was one row:

    MaxAge["gnss.position"] = 1.00 s   vs   STALE_TIMEOUT_S["gps"] = 0.50 s

§27 requires an audit before eligibility is designed on top of either. **The
audit found the disagreement is not one row. It is six of eight nodes, it has
a single common cause, and one instance of it is materially worse than the row
that was banked.**

> **Nothing is changed by this document.** §27 says do not change silently
> without regression analysis, and no timeout is altered in this commit.

---

## 1. WHAT EACH TIMEOUT MEANS, AND WHO OWNS IT

| | `MaxAge` | `STALE_TIMEOUT_S` |
|---|---|---|
| file | `csia/aircraft/adapters/base.py:42` | `csia/runtime/online.py:47` |
| layer | **adapter / canonical ingestion** (v1.1) | **frozen trust layer** (v1, FROZEN) |
| keyed by | **channel** (`gnss.position`) | **node** (`gps`) |
| decides | whether the channel appears in an `AircraftSample`, and with what `missing_reason` | whether the node's evidence enters the trust update this tick (gate → 0) |
| stated rule | `MAX_AGE_MARGIN(5) / declared_rate_hz`, **derived per platform from the channel contract** | "~5x the sensor's nominal period", **hand-written, one global table** |
| overridable | yes, `_derive_max_age` from the contract | yes — `OnlineTrustLayer(stale_timeout_s=...)`, already used by the ULog CLI |

**They are not different concepts.** Both answer "how old may this
measurement be before it stops counting as evidence", and both apply the same
rule — five producer periods. They are measured at two points on one path, and
they disagree because **they assume different producer rates for the same
sensor.**

`MaxAge` derives its rate from `docs/simulation/CHANNEL_SEMANTICS.yaml`, per
platform. `STALE_TIMEOUT_S` has a rate baked into a constant and no platform
to derive it from, because it is inside the frozen core, which by design knows
nothing about adapters.

## 2. THE FULL DISAGREEMENT

`implied rate` = `5 / STALE_TIMEOUT_S`, applying the frozen table's own stated
rule backwards.

| channel | node | MaxAge | declared rate (AP / PX4) | `STALE_TIMEOUT_S` | rate the frozen table implies | agree? |
|---|---|---:|---:|---:|---:|---|
| `imu0.accel` / `.gyro` | `imu0` | 0.20 | 25 / **50** | 0.05 | **100 Hz** | no |
| `imu1.accel` / `.gyro` | `imu1` | 0.20 | 25 / 25 | 0.05 | **100 Hz** | no |
| `baro.altitude` / `.temp_c` | `baro` | 0.50 | 10 / 10 | 0.10 | **50 Hz** | no |
| `mag.field_ut` | `mag` | 0.20 | 25 / **14** | 0.10 | **50 Hz** | no |
| `gnss.position` / `.velocity` | `gps` | 1.00 | 5 / 5 | 0.50 | **10 Hz** | no — *the banked row* |
| `esc.rpm` / `.current` | `motor_esc` | 0.50 | 10 / **1** | 0.10 | **50 Hz** | **no — worst case** |
| `battery.voltage` / `.current` | `battery` | 0.50 | 10 / 10 | 0.50 | 10 Hz | **yes** |
| `vibration.rms` | `vibration` | 0.50 | 10 / 10 | 0.50 | 10 Hz | **yes** |

The two rows that agree are exactly the two whose declared rate is 10 Hz. The
frozen table is not arbitrary — it is right wherever the sensor really does
publish at the rate it assumed.

## 3. THE FINDING THAT IS WORSE THAN THE BANKED ONE

**`motor_esc` on PX4.**

`ESC_STATUS` publishes at **1 Hz** on PX4 — a fact already discovered and
fixed once, on the adapter side, where `_derive_max_age` now yields
`5 / 1 = 5.0 s` instead of the hand table's 0.50 s. **The same fix was never
available to the frozen layer**, whose watchdog still assumes 50 Hz.

The exposure is not theoretical, and it needs three facts to be real. All
three hold:

1. `PlatformAdapter.to_core_samples` emits a sensor **only when it has new
   data** (`base.py:300`), deliberately, so the frozen core sees one sample
   per actual measurement rather than 25 re-feeds a second. At 1 Hz,
   `motor_esc` advances `last_t` once per second.
2. The frozen watchdog is an arrival-age test on exactly that value:
   `(tau - s[n].last_t) <= self._stale[n]` (`online.py:604`).
3. `csia/deploy/shadow.py:109` constructs `OnlineTrustLayer` **without**
   `stale_timeout_s`, so the live shadow path takes the frozen defaults. The
   ULog CLI path does override them (`cli.py:166`).

Consequence, stated conditionally because no PX4 hardware ran here: on a live
PX4 shadow flight, `motor_esc` would be treated as stale for roughly **0.9 s
of every 1.0 s**, withdrawing `power_thrust`, `accel_motor_current`,
`accel_esc_rpm` and `phys_motor_esc` from the evidence for ~90% of ticks.

**This is a deployment-layer defect, not a frozen-core defect**, and it is
therefore fixable without touching the freeze. It is recorded here and **not
fixed in this commit**: it changes live behaviour on a path with no test
coverage in this environment, which is precisely the regression analysis §27
requires first.

## 4. WHICH LAYER BINDS

For a node to contribute evidence, both tests must pass. The **tighter** limit
binds, and for every disagreeing row that is the frozen core's.

The interesting window is between the two limits. For `gps`: between 0.5 s and
1.0 s of silence, the `AircraftSample` still reports `gnss.position` **present
and fresh** while the frozen trust layer has already withdrawn `gps` evidence.
Two layers, two different answers to "is the GPS fresh", for up to half a
second.

## 5. THE CONSEQUENCE FOR FUNCTION ELIGIBILITY — A DESIGN DECISION, NOT A NOTE

An eligibility policy must read **one** notion of freshness, and this audit
decides which:

> **Eligibility reads the FROZEN LAYER's freshness** — the same `fresh[node]`
> that gates evidence into the trust update. The adapter's `missing_reason` is
> consumed **only to refine the reason code** (`SOURCE_ABSENT_SENTINEL` vs
> `_STALE` vs `_NOT_RECEIVED` vs `_NO_3D_FIX`), never to override the
> freshness verdict.

Reasoning: the binding limit is the frozen layer's, so anything else would let
a function be declared ELIGIBLE on a node whose evidence the trust layer had
already withdrawn — eligibility claiming support that the diagnosis underneath
it does not have. That is the exact failure mode Phase 2 exists to prevent.

This is implemented: `Observation.fresh` is the layer's view and
`Observation.missing_reason` only selects among the `SOURCE_ABSENT_*` codes.

## 6. PROPOSED CANONICAL RULE — NOT APPLIED

One rule, already written down, already implemented on one side:

> **`stale = 5 / declared_producer_rate_hz`, taken from the channel contract,
> per platform.**

The frozen core **already accepts this** without any change to it:
`OnlineTrustLayer(stale_timeout_s=...)` overrides the table, and the ULog CLI
already uses that hook. So the canonical rule can be adopted by **deriving the
per-node timeout from the same contract the adapter uses and passing it in at
construction** — no freeze break, no re-tag, no new constant.

Node timeout = `min` over the channels the node requires, since a node needs
all its channels.

What that would change, on PX4:

| node | today | derived | direction |
|---|---:|---:|---|
| `motor_esc` | 0.10 | **5.00** | far more tolerant — the defect above |
| `mag` | 0.10 | 0.36 | more tolerant |
| `gps` | 0.50 | 1.00 | more tolerant |
| `baro` | 0.10 | 0.50 | more tolerant |
| `imu0` | 0.05 | 0.10 | more tolerant |
| `imu1` | 0.05 | 0.20 | more tolerant |
| `battery` | 0.50 | 0.50 | unchanged |
| `vibration` | 0.50 | 0.50 | unchanged |

**Every change is in the direction of tolerating a slower producer, so the
risk it introduces is under-detection of a genuinely dead sensor, not
over-detection.** That is the right direction to be cautious about and the
reason this is a proposal rather than a patch.

## 7. WHY IT IS NOT ADOPTED IN PHASE 4

1. **Every v1 and v1.1 result to date was computed with the frozen defaults**,
   including the Phase 3A/3B architecture comparison and the Phase 4A
   trust-mode regression. Changing the effective staleness changes
   admissibility for all of them, and they would all require remeasurement —
   `V1_1_ENGINEERING_MANIFEST.md` §5 already carries that discipline.
2. **The deterministic scenario catalogue cannot exercise it.** It has no
   adapter and no producer rates; every node is fresh or explicitly dropped.
   Adopting a rule whose effect is invisible to every test available here
   would be adopting it on argument alone.
3. §27 says so.

## 8. WHAT THIS AUDIT LEAVES OPEN

- **The PX4 `motor_esc` exposure is unfixed** and is now the most concrete
  known deployment defect. It needs a PX4 replay or bench regression first.
- **No hardware ran here.** Every rate in §2 is a *declared* contract rate,
  not a measured one. A measured rate could differ, and the audit would then
  need redoing against measurement.
- **`vibration.rms` provenance** remains as banked in Phase 1: its producer
  instance is selected at runtime and the wire message does not say which.
  Unrelated to staleness, restated so this file is not read as a full ingest
  audit.
