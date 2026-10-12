# Clean shadow flights, both platforms — 2026-08-25

**Seven clean SITL shadow flights through the full v1.1 stack: four ArduPilot,
three PX4 (plus one earlier PX4 flight, eight in total).** No injected fault
on any of them. The question is the one a shadow deployment turns on: **on a
flight where nothing is wrong, does CSIA stay quiet?**

That number has existed for the bench simulator since the freeze — "clean: 0
false alarms", verdict document §2.2. It had never been measured through the
v1.1 ingestion path. The adapter, the semantic qualification layer, the
freshness gate and the shadow runner all sit between the vehicle and the
frozen core now, and none of them existed when that row was written.

**These are SITL flights, not hardware.** "Clean" means no injected fault, not
"representative of an airframe": the noise profile is the simulator's, and W-3
records that detection can be a property of the noise model rather than of the
fault. Nothing here transfers to a real aircraft.

---

## 1. PX4 replication — what had to be fixed first

`shadow_sitl_check.py` offered `--platform px4` and **could not run it**.
`RIG_LINK` was a single module constant holding ArduPilot's SERIAL1
(`tcp:127.0.0.1:5762`). PX4 never opens that port, so the harness launched the
simulator, started the tee, and died:

```
=== tee: udp:127.0.0.1:14550 -> udp ('127.0.0.1', 14561) (13 message types flowing)
no TCP listener on tcp:127.0.0.1:5762
```

The two platforms genuinely differ, and the shape was decided by measurement
rather than by symmetry. Measured on a live SIH boot, 4 s per link:

| PX4 mavlink instance | bind | heartbeat | message types |
|---|---|---|---|
| Normal | 14550 | yes | 29 |
| **Onboard** | **14540** | **yes** | **35**, `HIGHRES_IMU` at 50 Hz |
| Onboard (rate-capped) | 14030 | yes | 22 |

**ArduPilot needs the tee.** Stream rates are per-link runtime state
established only by a transmit on that link (`GCS.h:537`,
`persist_streamrates() == false`), and CSIA cannot transmit — so something
with authority must drive SERIAL0 while the rig commands on SERIAL1.

**PX4 does not.** Every instance streams a full set unprompted. So the rig
commands on the Normal link and CSIA binds the Onboard link directly, which is
what a companion port *is* on a real PX4 vehicle. Interposing a tee there
would model a constraint the platform does not have.

`RIG_LINKS`, `DIRECT_PASSIVE` and `NEEDS_TEE` are per platform now, and the
result file records which arrangement produced the numbers.

---

## 2. Results

| platform | flights | flights with an escalation | ticks above NORMAL | tick median |
|---|---|---|---|---|
| **ArduPilot** | 4 | **0** | 0 / 749–751 each | 968.8–1010.2 µs |
| **PX4 SIH** | 4 | **2** | 140 and 178 of 751 | 766.4–789.1 µs |

**Command authority was `NO_COMMAND_PATH_REACHABLE` on all eight flights**,
with `command_long_send`, `set_mode_send` and `rc_channels_override_send`
denied on the live socket every time. Zero exceptions. That is the property
shadow mode exists to guarantee and it is the one result here with no caveats
attached.

### 2.1 ArduPilot is quiet

Four clean flights, 749–751 ticks each, **not one tick above NORMAL**. Trust
mid-flight: `imu1 0.995`, `vibration 0.996`, `imu0 0.974`, `mag 0.973`,
`battery 0.983`, `gps 0.939`, `baro 0.849`. Pre-arm magnetometer trust was
0.893, 0.894, 0.895, 0.896 across the four — reproducible to three decimals.

The v1.1 ingestion path does not, by itself, manufacture alarms.

### 2.2 PX4 escalates on some clean flights, and I cannot say which

Two of four clean PX4 flights raised CAUTION — 140 and 178 ticks, roughly 19 %
and 24 % of the flight. The other two stayed NORMAL for all 751.

What the escalation looks like, from the log:

```
level        CAUTION           (recommendation.level)
disagreement CSIA_ONLY         (the autopilot did not react)
csia_top     nominal           177 of 178 ticks
diagnosis    nominal 0.4939 | imu0_bias_drift 0.4943   -- a coin flip
trust        mag 0.554  baro 0.533  imu0 0.840  imu1 0.800  battery 0.800
```

**CSIA escalated while its own top hypothesis was `nominal`.** That is W-1's
signature exactly — "in shadow mode this shows up as an escalation with no
cause" — now observed live rather than reasoned about, and on a platform
rather than a bench.

`imu1` and `battery` sit at 0.800, the untouched prior: PX4 SIH provides
neither channel, both are narrowed to `UNAVAILABLE`, so no evidence updates
them. That is correct abstention, and it also means the `redundant_imu`
cross-check is dark (`gates.redundant_imu` weight 0.0) — the strongest
corroboration for `imu0` is unavailable on this backend.

### 2.3 A hypothesis I formed and then refuted, within the same session

After three PX4 flights the pattern looked clean:

| flight | pre-arm mag trust | escalated? |
|---|---|---|
| 1 | 0.485 | yes, 178 ticks |
| 2 | 0.768 | no |
| 3 | 0.448 | yes, 140 ticks |

"Pre-arm magnetometer trust predicts the escalation" — tidy, mechanistic, and
about to be written down. The fourth flight had the **lowest** pre-arm mag
trust of all, **0.433**, and stayed quiet for all 751 ticks.

The hypothesis is dead. Escalating flights: 0.485, 0.448. Quiet flights:
0.768, **0.433**. No separation.

**So: PX4 clean flights escalate intermittently, 2 of 4, and I have not
identified what determines it.** That is the result. Three points looked like
a law and the fourth was the control that killed it.

### 2.4 What IS systematic

PX4 trust runs materially lower than ArduPilot's on the same code and the same
flight profile:

| node | ArduPilot (mid-flight) | PX4 (mid-flight) |
|---|---|---|
| mag | 0.973 | 0.672 |
| baro | 0.849 | 0.589 |
| imu0 | 0.974 | 0.831 |
| imu1 | 0.995 | 0.800 (prior — channel absent) |
| battery | 0.983 | 0.800 (prior — channel absent) |
| gps | 0.939 | 0.989 |

That difference is consistent across every flight. It is *not* what decides
whether a given flight escalates — 2.3 rules that out for the magnetometer —
but it is the reason PX4 sits close enough to the threshold for anything to
tip it.

---

## 3. What would actually settle 2.2

Two candidate explanations, neither tested, each with a control that would
test it. Naming them is not the same as having run them.

1. **Fewer cross-checks.** PX4 lacks `imu1` and `battery.current`, so
   `redundant_imu` and the power relations are dark and the surviving
   residuals carry more weight.
   **Control:** fly ArduPilot with `imu1.*` and `battery.current` blocked at
   the adapter — same platform, same data, only channel availability changed.
   If ArduPilot then escalates, the explanation holds.
2. **Ground-period accumulation.** Trust settles during ~11 s of pre-arm
   ground time and W-4 puts ~3.7 s of banked evidence behind any move, so the
   state at arming may dominate the first part of the flight.
   **Control:** vary the pre-arm dwell and see whether the escalation rate
   moves with it.

Until one of those is run, "PX4 escalates on some clean flights" is the whole
claim. It is enough to matter for a deployment decision and not enough to
explain.

---

## 4. Timing, for completeness

| platform | tick median across flights | R13 |
|---|---|---|
| ArduPilot | 968.8 / 977.4 / 1010.2 µs | FAIL, 1–2 ticks of 751 |
| PX4 | 766.4 / 785.9 / 789.1 µs | FAIL, 1 tick of 751 |

PX4 is cheaper per tick because it delivers fewer channels. Every one of these
`FAIL`s is 1–2 ticks out of 751, on a host where a constant-work control goes
over the same budget up to ten times in 751 iterations. **No R13 verdict from
this container is admissible** — see `csia/simulation/host_noise.py` and the
Gate 2 procedure.

---

## 5. Reproducing

```bash
python tools/deploy/shadow_campaign.py --platform ardupilot --flights 3
python tools/deploy/shadow_campaign.py --platform px4 --flights 3
```

Writes `research/v1_1/results/shadow_campaign_<platform>.json` plus one result
file per flight under `research/v1_1/results/shadow_flights/`. The campaign
exits non-zero if any flight fails to complete, if any flight's command
authority is anything other than `NO_COMMAND_PATH_REACHABLE`, or if any flight
log could not be read — "no alarms" from a log nobody could parse is not a
result, and the first version of the reader looked for a field that does not
exist and would have reported exactly that.
