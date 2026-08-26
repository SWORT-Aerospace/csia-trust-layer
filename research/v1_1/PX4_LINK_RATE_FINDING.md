# PX4 stream rates are a property of the link, not of the platform

> **SUPERSESSION.** An earlier artifact classified the PX4 `altitude_baro`
> starvation as `RATE_MISDECLARED`. **That label is falsified and must not be
> propagated.** The controlled link-rate experiment below established that the
> driven qualification connection explicitly requests the stream at ~10 Hz while
> the passive shadow connection receives a much lower default, so delivery is
> **link/configuration-conditioned**. The passive shadow consumer was
> evidence-starved *relative to the freshness contract*. This is **not** evidence
> that PX4 intrinsically supplies the channel at 1 Hz, and **not** evidence that
> the declared 10 Hz is universally wrong.
> The current label is **`STARVED_BY_TRANSPORT`** (link condition).

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

## 2. Why this matters downstream — two gates, not one

Evidence availability is gated **twice**, with different budgets, and the second
gate is the one that binds. An earlier version of this document described only
the first.

| # | gate | budget for baro | where it comes from |
|---|---|---|---|
| 1 | channel `max_age` | `MAX_AGE_MARGIN / declared_rate` = 5.0/10 = **0.50 s** | bought by the declared rate |
| 2 | node `STALE_TIMEOUT_S['baro']` | **0.10 s** | a fixed constant in the frozen runtime (`online.py:603`) that **no declaration feeds** |

A relation's weight is `gate * fresh(endpoint_a) * fresh(endpoint_b)`
(`online.py:610`), so it requires the **nodes**, not merely usable channels.
Measured on the PX4 shadow corpus with baro delivered at ~1 Hz:

| quantity | PX4 | ArduPilot |
|---|---|---|
| `baro.altitude` channel usable | 0.4943 | 0.9992 |
| `baro` **node fresh** | **0.0967** | 0.9992 |
| `altitude_baro` relation live | 0.0812 | 0.9984 |

The channel gate explains a factor of about two. The node gate explains the
rest. Both follow from the same root cause — delivery an order of magnitude
below the declaration — so the diagnosis and the fix are unchanged, but an
account mentioning only `max_age` predicts ~50 % availability where the
measurement shows ~8 %.

This is also a design implication: the channel contract associates a rate with
`(channel, platform)`, and there is a **second** freshness budget at the node
layer that the contract does not mention and no declaration can influence.

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

Measured on `PX4-Autopilot@547e2ca`, `PX4_SYS_AUTOSTART=10040`,
`PX4_SIM_MODEL=sihsim_quadx`. The build is recorded in the artifact, because
these are defaults of *that firmware* and a PX4 upgrade may move them.

| message | passive/14540 | passive/14550 | request/14550 | request_onboard/14540 |
|---|---|---|---|---|
| SCALED_PRESSURE | 1.000 | 1.000 | **9.750** | **9.775** |
| BATTERY_STATUS | 0.500 | 0.500 | **9.750** | **9.775** |
| VIBRATION | 0.500 | 0.100 | **9.750** | **9.775** |
| ATTITUDE | 97.945 | 48.998 | 48.799 | 97.696 |
| GLOBAL_POSITION_INT | 48.973 | 48.973 | 9.775 | 48.823 |
| GPS_RAW_INT | 7.850 | 4.900 | 4.875 | 7.825 |

Run three times across independent boots while this was being written. The
figures move in the third decimal (`SCALED_PRESSURE` requesting: 9.800, 9.825,
9.775) and the conclusions do not.

Reading the table:

- **The instance cannot explain the 10× conflict.** With neither link requesting,
  both stream the disputed channels far below the declared 10 Hz, and for
  `SCALED_PRESSURE` — the channel actually in dispute — they are equal
  (1.000 vs 1.000 Hz).
  This is *not* the stronger claim that the instances are identical: their
  defaults genuinely differ (`VIBRATION` 0.500 vs 0.100 Hz, `GPS_RAW_INT` 7.850 vs
  4.900, `ATTITUDE` 97.945 vs 48.998). The point is narrower and sufficient —
  no unrequested default on either instance comes near 9.8 Hz, so the instance
  cannot produce the qualification figure and the requests can.
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
