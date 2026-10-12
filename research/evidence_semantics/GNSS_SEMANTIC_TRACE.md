# GNSS: where explicit invalidity becomes absence

Item 14. **Question:** at which pipeline boundary does `I` (the receiver
reported no 3-D fix) become indistinguishable from `N` (nothing arrived)?

**Answer: `T5_core_bridge`, `csia/aircraft/adapters/base.py:306-337`
(`to_core_samples`).** Not the adapter, which is where a reader would look
first — the adapter gets it right.

---

## The witness

Shortest distinguishing input: **`I`, one message.** Exhaustive search over
all 120 words of length ≤ 4 in `{V, I, N}`; nothing shorter than one symbol
exists, so minimality is by construction.

Reproduces the previously banked F1 (`shortest witness length = 1`) with an
independently written instrument. The `79/120` cross-path result from commit
`9071766` also reproduces exactly — see `results/PRIOR_RESULT_REPRODUCTION.json`.

## Stage-by-stage, `I` against `N`, v1.1 adapter

Read from `CAUSAL_BLAME_TRACES.json`. Notation `tok@t`: the token, and the
first tick at which it appears. Word onset is `t = 12.0`.

| stage | `w1 = "I"` | `w2 = "N"` | identical? |
|---|---|---|---|
| `T1_protocol` | `I@12  N@12.32` | `V@12  N@12.12` | no |
| `T2_decode` | `I@12  N@12.32` | `V@12  N@12.12` | no |
| `T3_ingest` | `I@12` | `V@12` | no |
| `T4_channel` | `I@12  N@13.04` | `V@12  S@12.84` | no |
| **`T5_core_bridge`** | **`-@12`** | **`-@12`** | **YES** |
| `T6_slot` | `V@12` | `V@12` | yes |
| `T7_admissible` | `A@12  0@12.32` | `A@12  0@12.32` | yes |
| `T8_evidence` | `1@12  1@12.16` | `1@12  1@12.16` | yes |
| `T9_assurance` | `N@12  C@13.36` | `N@12  C@13.36` | yes |

`first_equivalent_level: VALUE`. `downstream_consequence: NONE`.

## Reading the trace

**The adapter is not the culprit.** `_ingest_gps` (`ardupilot.py:226-236`)
does the right thing twice over: it pops the retained position and velocity
so a lost fix cannot keep looking fresh, and it records
`MissingReason.NO_3D_FIX` rather than the default. At `T3` and `T4` the two
inputs are still clearly different — `I` versus a retained `V` that later
ages to `S`.

**The loss is at the boundary into the frozen core.** `to_core_samples` has
exactly two outcomes per sensor:

```python
if cv is None or not cv.usable:
    ...
    complete = False
    break                     # base.py:312-318  -> emit NOTHING
...
chans["valid"] = True         # base.py:335      -> emit, always valid
```

"The producer said it has no value" and "no message arrived" both take the
first branch. There is no third outcome, so the seven-member `MissingReason`
vocabulary is encoded into one bit and six of the seven members mean the same
thing at this boundary.

**Downstream, the two are indistinguishable in every respect.** Admissibility
closes at the same tick (12.32) on both, because on this path `A` closes when
the *previous* fix ages out — the no-fix report does not accelerate it at
all. The failsafe escalates to `CAUTION` at the same tick on both, with the
same actions.

## The reason string in the flight log

`FailsafePolicy._conditions` (`failsafe.py:145-152`) builds its reason as:

```python
why = "GPS data invalid" if not fresh.get("gps", True) \
    else f"GPS trust {T['gps']:.2f}"
```

Since `fresh["gps"]` is the only input, the flight log records
**"GPS data invalid"** for both inputs — including the one where no GPS
message arrived at all and the receiver never said anything about validity.
The word "invalid" in that log line is not supported by the evidence the
system holds.

## Item 22's example, checked rather than assumed

Item 22 offers this as an illustration:

```
protocol   I != N
decoder    I != N
adapter    I -> NO_UPDATE,  N -> NO_UPDATE       =>  FIRST COLLAPSE: adapter
```

**Measured, the adapter is not where it happens.** `I` and `N` are still
distinct at `T3_ingest` and at `T4_channel`; the adapter records
`NO_3D_FIX` and the ChannelValue carries it. The collapse is one stage
later, at the bridge into the frozen core. The illustration's shape is right
and its attribution is wrong for this codebase — which is the case for
building the localisation rather than reading the code and guessing.

## The other two paths PASS this clause

| path | GNSS-F1 | emitted vocabulary |
|---|---|---|
| `v1_1_adapter` | **FAIL** — collapsed at `T5_core_bridge` | `['V']` |
| `plugins_py` | PASS — distinct through to the failsafe | `['I','V']` |
| `ulog_source_py` | PASS — distinct through to the failsafe | `['I','V']` |

`plugins.py:157-159` emits a core sample with `valid=False`, so `slot.valid`
goes false immediately and `fresh["gps"]` closes at once. `ulog_source.py:189`
emits `valid=(fix >= 3)` with the real position, same effect.

This is uncomfortable and is reported as measured: **the path with the
careful `MissingReason` handling is the one that loses the distinction, and
the two paths that fabricate or pass through a value are the ones that keep
it.** They keep it by accident — neither has any notion of a reason — but the
distinction survives to the failsafe on both.

## Cross-path consequence, quantified

`v1_1_adapter` against either other path, over 120 words:

| level | attributable divergent words | shortest |
|---|---|---|
| VALUE | 90/120 | `I` |
| STATE | 90/120 | `I` |
| EVIDENCE | 83/120 | `I` |
| ASSURANCE | 53/120 per pair (106 rows over both pairs) | `I` |

For every one of the 106 `ASSURANCE_STATE` rows: same level history
(`NORMAL → CAUTION`), **same action set**, escalation later by **0.32 s**
(80 rows) or **0.12 s** (26 rows) on the v1.1 adapter.

**The consequence is a latency, not a different decision.** No word in this
package produces a different failsafe action on any path. `CONTROL_FAILSAFE`
is not reached and is not claimed.

## Two staleness horizons

Visible in the trace above and worth stating: at `T4` the channel is still
`V` until 12.84 (adapter `MaxAge["gnss.position"] = 1.00 s`,
`base.py:47`), while at `T7` the core has already withdrawn admissibility at
12.32 (`STALE_TIMEOUT_S["gps"] = 0.5 s`, `online.py:48`). The stricter limit
governs, so nothing is broken; but the adapter would serve a position the
core has already stopped believing.

## Not exercised on real data

The committed 9.6 MB PX4 log contains **345 `vehicle_gps_position` samples,
every one with `fix_type == 3`** (`results/PX4_FEASIBILITY.json`). The
invalid branch is not exercised by the only real log available here. Every
GNSS result above comes from synthetic messages driven through the real
decoders.
