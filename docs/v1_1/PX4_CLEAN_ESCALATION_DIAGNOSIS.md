# Why 2 of 4 clean PX4 flights escalate — tick-level cause

**No tuning. This document identifies the cause and changes nothing.**

Two of four clean PX4 SIH shadow flights raised CAUTION; two did not. `n=4` is
far too small to publish as a rate, and no rate is claimed here. It is large
enough to establish that **PX4 clean behaviour is not qualified**, and that is
the only inferential use made of it.

---

## 1. The predicate

`csia/runtime/failsafe.py:169` — the frozen core, unmodified:

```python
if T["mag"] < cfg.heading_caution and fresh.get("mag"):
    out["heading_degraded"] = (FailsafeLevel.CAUTION, ...)
```

`heading_caution = 0.60`. `update()` then applies two gates and a dwell:
`state.armed is False` → reset timers and return; `t < arm_time (10.0 s)` →
return; and a condition must persist **continuously for `dwell_up = 1.0 s`**
(25 ticks at 25 Hz) before the level rises. `_cond_since[name]` is **deleted**
whenever the condition clears, so the timer restarts from zero.

That deletion is the operative detail.

---

## 2. What the S9 logs could exclude, and did

Every candidate the log can see was excluded with evidence before replaying
anything:

| candidate | measurement | verdict |
|---|---|---|
| predicate value | mag trust < 0.60 in 3 of 4 flights, **including one that stayed quiet** | not sufficient |
| dwell length | the quiet flight held mag < 0.60 for a contiguous 290 ticks (11.6 s) vs `dwell_up` 1.0 s | not it |
| armed gate | armed channel 100/100 usable and true in the decision window of every flight | not it |
| `arm_time` | every flight had 78–93 ticks below threshold **after** t = 10 s | not it |
| channel freshness | `mag.field_ut` never appeared in `evidence_unavailable`, any flight | not it |

What remained was `TrustState.fresh` — **node** freshness, computed inside the
core as `s[n].valid and s[n].seen` (`online.py:603`) — which is the second
term of the predicate and which the flight log does not record.

## 3. The replay, and its positive control

`tools/deploy/diagnose_escalation.py` replays a logged flight through the
frozen core and a fresh `FailsafePolicy`, recording `state.fresh`,
`state.trust` and the active conditions per tick.

**A replay that does not reproduce the flight is not evidence about it**, so
the tool compares replayed trust against the logged `trust_post` tick by tick
and withholds the diagnosis if they diverge. Both flights:

```
replay control: 6000 values compared, 0 over tolerance, worst delta 0.0
                -> FAITHFUL
```

Worst absolute delta **0.0** across 6000 trust values. The replay is the
flight.

## 4. The cause

Window t ∈ [9, 20] s, 275 ticks, `dwell_up` = 1.0 s = 25 ticks:

| | **escalated** (001940) | **quiet** (002030) |
|---|---|---|
| `heading_degraded` active | 114 / 275 ticks | 87 / 275 ticks |
| mag node **NOT** fresh | **5** ticks | **22** ticks |
| **longest contiguous run** | **40 ticks = 1.60 s** | **10 ticks = 0.40 s** |
| run lengths | 40, 37, 24, 13 | 10, 10, 6, 6, 6, 6, 6, 6 |
| outcome | CAUTION at t = 13.2 s | NORMAL throughout |

Both flights spend comparable *total* time with the magnetometer below the
trust threshold. The escalating flight holds the condition **continuously for
1.60 s**, clearing the 1.0 s dwell. The quiet flight's longest unbroken run is
**0.40 s**: its condition is chopped into fragments by magnetometer node
freshness dropouts — 22 non-fresh ticks against 5 — and each dropout deletes
`_cond_since`, restarting the dwell before it can mature.

**The escalation is decided by whether PX4's magnetometer node freshness
happens to stay continuous long enough during the low-trust window.** It is a
race between a rising trust curve and an intermittently-fresh node, arbitrated
by a 1 s dwell.

The failsafe is behaving exactly as specified. The dwell is doing precisely
what it was written to do — suppress flapping. Nothing here is a defect in the
state machine.

### 4.1 Why the trust is low at all

Separate from the intermittency, and systematic across every PX4 flight: mag
trust starts around 0.43–0.48 and climbs to ~0.74 over the run, where
ArduPilot sits at 0.973 with a pre-arm value reproducible to three decimals
(0.893, 0.894, 0.895, 0.896 across four flights). PX4 also lacks `imu1` and
`battery.current`, so `redundant_imu` is dark and those nodes hold the 0.800
prior.

Why PX4 magnetometer trust is low is **not** answered here. It is the next
question, and it is a different question from the one this document settles.

## 5. The finding that outlives the timing detail

On the escalating flight, at the moment of escalation:

```
failsafe NORMAL -> CAUTION @ t=13.2s:
    magnetometer untrusted (mag 0.56; diagnosis nominal p=0.71)
```

**CSIA raised CAUTION while its own diagnosis said `nominal` at p = 0.71**, and
the autopilot did nothing (`disagreement.state = CSIA_ONLY`). On the other
escalating flight the top hypothesis was `nominal` on 177 of 178 CAUTION
ticks, with the posterior a coin flip between `nominal` (0.4939) and
`imu0_bias_drift` (0.4943).

This is **assurance output ≠ diagnostic attribution**, occurring with **no
injected fault**. The escalation is driven by the trust recursion crossing a
threshold; the Bayesian attribution layer is simultaneously reporting nominal.
They are separate mechanisms and they disagree.

W-1 predicts this shape ("in shadow mode this shows up as an escalation with
no cause"); W-6 records that response is not attribution. Both were written
from ArduCopter 3.3 campaign data. This is the first observation of the shape
on a current stack, on a second autopilot, with no fault present.

## 6. Consequences

**Shadow mode is passive, so an erroneous CAUTION controlled nothing.**
Command authority was `NO_COMMAND_PATH_REACHABLE` on all eight flights, with
every transmit probe denied on the live socket. Had CSIA held control
authority, an unexplained nominal escalation would be a considerably more
serious event. This is the deployment sequence working as intended.

| platform | status |
|---|---|
| **ArduPilot** | 4/4 clean flights silent. Closer to a first physical shadow flight. |
| **PX4** | **Not yet.** The intermittent nominal escalation must be resolved first, and PX4 clean behaviour must not be described as qualified. |

## 7. What is deliberately NOT done here

No threshold moved, no dwell changed, no trust weight touched. The frozen core
is untouched — `tests/test_v1_frozen.py` passes and no `FROZEN_PATHS` file is
in the diff.

Two questions are open and each needs its own measurement:

1. **Why is PX4 magnetometer node freshness intermittent?** Measured
   effective rate is 13.9 Hz (`fields_updated` gates the mag fields inside a
   ~49 Hz `HIGHRES_IMU`), against a derived `max_age` of 0.357 s. A dropout
   means a gap longer than 0.357 s, which implies substantial jitter in the
   bitmask cadence. Measure the inter-arrival distribution.
2. **Why is PX4 magnetometer trust low at all?** The residuals and gate
   weights are in the logs; nothing has been attributed yet.

Neither should be answered by adjusting a constant until the symptom stops.

## 8. Reproducing

```bash
python tools/deploy/diagnose_escalation.py \
    logs/shadow-sitl-px4/<escalating>.jsonl \
    logs/shadow-sitl-px4/<quiet>.jsonl
```

Writes `research/v1_1/results/escalation_diagnosis.json`, including the replay
control for each flight. It exits non-zero if any replay was not faithful,
because a diagnosis from an unfaithful replay describes the replay.
