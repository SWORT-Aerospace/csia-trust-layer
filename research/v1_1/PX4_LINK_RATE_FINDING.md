# PX4 stream rates are a property of the link, not of the platform

**Status:** open defect, cause identified and measured, fix scoped but NOT applied.
**Affects:** PX4 shadow flights only. No committed scientific result depends on it
(Mechanism B on PX4 is `INAPPLICABLE` for unrelated reasons, recorded in
`CURRENT_STACK_REPLICATION.md`).

## 1. The conflict

Two committed artifacts disagree about the same channel by an order of magnitude,
and both are correct:

| source | `baro.altitude` on PX4 |
|---|---|
| `research/v1_1/results/qualification_px4.json` | 9.82 Hz (393 samples / 40 s) |
| `research/v1_1/results/shadow_flights/*.jsonl` | 1.00 Hz (40 arrivals / 40 s) |

`docs/simulation/CHANNEL_SEMANTICS.yaml` declares `producer_px4: rate_hz: 10`.

## 2. Why this matters downstream

`max_age` is derived from the declaration, not measured:

    max_age = MAX_AGE_MARGIN / declared_rate_hz = 5.0 / 10 = 0.50 s

A channel that actually arrives every 1.00 s is therefore STALE for half of every
period. Measured consequences, from the committed flight logs:

- `baro.altitude` usable on a minority of ticks; the `baro` node fresh on
  **82 of 1001 ticks (8.2 %)**
- `altitude_baro` — the only baro/GNSS cross-check — carried non-zero gate weight
  on **8.1 %** of PX4 ticks, against **99.9 %** on ArduPilot

Nothing fails or warns. Absence of evidence is handled correctly by design, so a
starved relation is indistinguishable from a relation the platform cannot produce
unless somebody measures which relations were live.

## 3. The wrong fix, and why it was reverted

The first response was to "correct" the contract from 10 Hz to 1 Hz. That edit was
made, then reverted unpushed. It is wrong twice over:

1. It breaks `tests/test_platform_contract.py::test_the_declared_px4_rates_match_what_was_measured`,
   which checks the declaration against the qualification probe — a probe that
   measures the **other** link.
2. It replaces one link-conditional constant with another. 1 Hz is no more a
   property of PX4 than 10 Hz is.

## 4. The measurement

Two things differed between the two tools at once, so neither artifact alone could
identify the cause:

- **instance** — qualification binds 14550 (Normal); CSIA binds 14540 (Onboard)
- **requests** — qualification calls `rigs.connect()`, which sends
  `MAV_CMD_SET_MESSAGE_INTERVAL` for msg 29 at 10 Hz; CSIA's link is a bare passive
  bind that requests nothing, because shadow mode may not transmit

`tools/simulation/px4_link_rate_probe.py` holds one variable at a time. Every arm
binds **both** links inside the **same** simulator run, so the instance comparison
is made under identical conditions rather than across two boots. 40 s per arm,
first 3 s discarded as settling. Artifact:
`research/v1_1/results/PX4_LINK_RATE_PROBE.json`.

| message | passive/14540 | passive/14550 | request/14550 | request_onboard/14540 |
|---|---|---|---|---|
| SCALED_PRESSURE | 1.000 | 0.975 | **9.800** | **9.825** |
| BATTERY_STATUS | 0.500 | 0.475 | **9.775** | **9.800** |
| VIBRATION | 0.500 | 0.100 | **9.775** | **9.800** |
| ATTITUDE | 98.147 | 49.073 | 48.900 | 98.073 |
| GLOBAL_POSITION_INT | 49.073 | 49.073 | 9.775 | 49.024 |
| GPS_RAW_INT | 7.850 | 4.900 | 4.900 | 7.850 |

Reading the table:

- **The instance is not the cause.** With neither link requesting, both stream the
  disputed channels slowly (1.000 vs 0.975 Hz).
- **The requests are the cause,** and they are per-link **in both directions**:
  requesting on 14550 leaves 14540 at 1.000 Hz, and requesting on 14540 leaves
  14550 at 0.975 Hz.
- **Controls behave.** `ATTITUDE` is requested by no arm and does not move
  (98/49 Hz throughout), so no arm merely perturbed the boot.
- **`SET_MESSAGE_INTERVAL` sets an exact interval, not a floor.**
  `GLOBAL_POSITION_INT` *drops* 49.073 → 9.775 Hz when requested at 10 Hz. The
  qualification probe's own requests therefore slow a channel CSIA reads.
- The requesting-link figure (9.825 Hz) reproduces `qualification_px4.json`
  (9.82 Hz) on an independent boot.

## 5. The claim this falsifies

`tools/deploy/shadow_sitl_check.py` justified running PX4 without a tee:

> It runs several mavlink instances, each streaming a full set unprompted …
> Interposing a tee there would model a constraint the platform does not have.

That was measured by counting message **types** over 4 s per link. A 1 Hz message
is present in a 4 s window, so a type count cannot distinguish 1 Hz from 10 Hz.
The claim is true of message **presence** and false of message **rate**, and rate
is what decides staleness.

PX4 has the same constraint ArduPilot has. Only the **default** differs:
ArduPilot's unprompted link carries no sensor data at all; PX4's carries all of it
slowly. Slowly still starves, because `max_age` comes from a declaration measured
on the requesting link.

## 6. The fix, scoped but not applied

The starvation is **fixable, not inherent**: arm 3 shows that a transmit on CSIA's
own link raises that link's rates (baro 1.000 → 9.825 Hz). CSIA itself must not
transmit — `tests/test_shadow_mode.py::test_no_send_calls_in_deployment_source`
asserts the deployment tree contains zero MAVLink transmit calls, and that
guarantee is the point. So the transmit must come from the rig, which means giving
PX4 the same driven link ArduPilot already has:

- `csia/simulation/tee.py` binds 14540, forwards bytes unmodified to CSIA on
  `TEE_OUT`, and sends the interval requests itself
- its stream profiles are currently ArduPilot-specific (`MAV_DATA_STREAM_*` via
  `request_data_stream_send`) and would need a PX4 profile using
  `SET_MESSAGE_INTERVAL`
- `NEEDS_TEE["px4"]` flips to `True`

This is **not applied here.** It changes how PX4 flights are captured, and the
campaigns are frozen. It is a decision to take explicitly, not a side effect of
correcting a comment. Committed PX4 flights remain valid records of what CSIA
received; they are simply records of a starved link, and this document is what
makes that legible.

## 7. Guarding the reconciliation

`tests/test_px4_link_rate.py` holds both ends in place:

- the contract must keep describing the **requesting** link
- the probe artifact must keep showing that requests, not instances, are the cause
- the committed qualification artifact must keep measuring the disputed channels
  fast

If the contract is ever deliberately moved to the passive regime, the qualification
probe must be changed to measure the passive link **in the same commit**. The test
says so in its failure message.
