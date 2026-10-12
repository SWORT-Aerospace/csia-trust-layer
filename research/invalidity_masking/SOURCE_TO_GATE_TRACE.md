# Source trace: `GPS_RAW_INT.fix_type` to `gvalid`

Every line cited here is resolved from the working tree by
`source_to_gate_trace.py`, which requires each cited pattern to occur **exactly
once** in its file and fails if it does not. Line numbers below are the ones
that script recorded; `results/SOURCE_TO_GATE_TRACE.json` carries the verbatim
line text and a SHA-256 of every file it read.

Run: `make invalidity-trace` (or the script directly). 28 facts, all verified.

---

## The verdict asked for in item 3

> *"A raw GPS observation with `fix_type < 3` does not explicitly invalidate the
> core GPS slot; instead, no new GPS `SensorSample` is emitted, so the previous
> accepted slot state persists until another accepted update or freshness/state
> logic changes it."*

**`PARTLY_TRUE` — and the part that is not true is the interesting part.**

It is exactly true of **one** of the three committed ingest paths, and exactly
false of the other two. The repository contains both semantics, feeding the
same frozen core.

| Path | On `fix_type < 3` | `slot.valid` | Statement holds? |
|---|---|---|---|
| `csia/aircraft/adapters/` (v1.1, deployed) | withholds the sample | stays `True` | **TRUE** |
| `csia/runtime/plugins.py` (v1 live MAVLink) | emits `valid=False` | set `False` | **FALSE** |
| `csia/runtime/ulog_source.py` (v1 ULog replay) | emits `valid=fix>=3` | set `False` | **FALSE** |

Two further qualifications to the statement as written:

1. **"does not explicitly invalidate"** is stronger than "leaves unchanged". On
   the v1.1 path `slot.valid` is not merely left alone — it is *unreachable as
   `False` for GPS after the first accepted fix*, because the hand-off writes
   `chans["valid"] = True` unconditionally
   (`csia/aircraft/adapters/base.py:335`) and `slot.valid` is written nowhere
   else (`csia/runtime/online.py:316`, the only `.valid =` in the file).

2. **"or freshness/state logic changes it"** is the load-bearing clause, and it
   is true — but it is true of `fresh`, not of `gvalid`. `gvalid` has no time
   term of any kind. See below.

---

## The chain, stage by stage

### 1. Protocol

`csia/aircraft/adapters/ardupilot.py:227` reads `fix_type`;
line 228 is the predicate `if fix is None or fix < 3:`.

### 2. Adapter — it does the right thing, deliberately

```python
# csia/aircraft/adapters/ardupilot.py:229-236
# Explicitly forget the previous fix rather than let it age out
# slowly: a lost fix is information, and a stale position that
# keeps looking fresh for a second is a lie about the present.
self._latest.pop("gnss.position", None)
self._latest.pop("gnss.velocity", None)
self._reject_sentinel("gnss.position", "gnss.velocity",
                      reason=MissingReason.NO_3D_FIX)
return
```

The adapter keeps the distinction: it deletes the stale value, records the
*specific* reason `NO_3D_FIX`, and increments `sentinel_counts()`. Its own
comment states the intent — **"a lost fix is information"**.

`INDISTINGUISHABILITY_CHECK.json` confirms the adapter really does retain it:
`sentinel_counts()` differs between a stream whose GPS reports no fix and one
whose GPS is silent.

### 3. Hand-off — where the information is destroyed

`to_core_samples` can express exactly two things about a sensor: *here is a
sample*, or *nothing*. It has no third state.

* A sensor is emitted only when **all** its channels are usable
  (`base.py:317`, `complete = False`); GPS needs both `gnss.position` and
  `gnss.velocity` (`base.py:270`) — the two the reject just deleted. So an
  invalid fix withholds the whole GPS sensor.
* Every sample that *is* emitted carries `chans["valid"] = True`
  (`base.py:335`) — hard-coded, with no `False` branch anywhere in the file.

So the adapter's carefully preserved `NO_3D_FIX` reaches the core as **absence**,
byte-for-byte identical to a link that stopped delivering.

That is not an inference. `INDISTINGUISHABILITY_CHECK.json` replays two streams
that differ *only* in whether the invalid messages are delivered at all, and
compares the resulting core state tick by tick:

> **1175 ticks × 13 core-state fields, 0 differing cells.**

### 4. Core slot

```python
# csia/runtime/online.py:312-316
def _apply(self, sensor: str, t: float, ch: dict):
    slot = self.slots[sensor]
    slot.seen = True
    slot.last_t = t
    slot.valid = bool(ch.get("valid", True))
```

`_apply` is called from exactly one place (`online.py:302`, inside `ingest`),
and `self.slots` is built once in `__init__` (`online.py:200`) and never
rebuilt. `seen`, `last_t` and `valid` are therefore written **only** on an
accepted sample and cleared nowhere in the package. `_SensorSlot` defaults are
`valid=False` (`online.py:132`) and `last_t=-1e9` (`online.py:134`), so the
initial state is correctly "invalid and infinitely stale" — it is only after
the first accepted fix that the retention begins.

### 5. The two gates, and the asymmetry between them

```python
# csia/runtime/online.py:482
gvalid = 1.0 if s["gps"].valid and s["gps"].seen else 0.0

# csia/runtime/online.py:603-604
fresh = {n: s[n].valid and s[n].seen
         and (tau - s[n].last_t) <= self._stale[n]
         for n in SENSORS}
```

`gvalid` is a pure retained-state predicate. **It contains no time term.** On
the v1.1 path, where `slot.valid` for GPS can never become `False`, `gvalid`
is `1.0` from the first accepted fix to the end of the flight, no matter what
the receiver reports afterwards. The M1 reanalysis measures this directly:
**0 of 999 post-onset ticks had `gvalid == 0`**, across 582 invalid raw
observations.

`fresh` is the same predicate plus a timeout, and
`STALE_TIMEOUT_S["gps"] = 0.5` s (`online.py:48`).

The asymmetry is harmless only because every relation that carries `gvalid` is
*also* multiplied by `fresh["gps"]`:

```python
# csia/runtime/online.py:610-613
E = {key: (lam, gate * float(fresh[self._edge_meta[key][0]])
           * float(fresh[self._edge_meta[key][1]]))
     for key, (lam, gate) in E.items()}
P = {n: (lam, gate * float(fresh[n])) for n, (lam, gate) in P.items()}
```

The four `gvalid` relations are `altitude_baro`, `velocity_gps_doppler_0`,
`velocity_gps_doppler_1` and `heading_course`. The trace script resolves their
endpoints from `csia.trust_graph.EDGES` and confirms **every one of them has
`gps` as an endpoint**, so `fresh["gps"]` multiplies all four. `P["gps"]` gets
`fresh["gps"]` from the line above.

**Therefore the effective GPS gate is `fresh["gps"]`, and `gvalid`'s missing
time term is currently redundant rather than exploitable.** That redundancy is
not documented anywhere, and it is one edit away from mattering: any future
relation that carries `gvalid` without `gps` as an endpoint would inherit an
uncloseable gate. Recorded as a latent hazard, not as the finding.

### 6. What the timeout is measured from

The finding is here. `fresh` times out against `last_t`, and `last_t` advances
**only on an accepted sample**. Rejected observations do not touch it. So the
gate does not measure *"how long has the receiver been reporting no fix"* — it
measures *"how long since the last fix we accepted"*.

Those coincide only when invalidity is continuous. When it is **intermittent**,
a single accepted fix inside the timeout window resets the clock and the gate
never closes, however many rejections surround it.

### 7. Downstream of the gate

`TrustCore.step` updates a node's Beta belief only while that node is fresh
(`csia/trust_engine/engine.py:146`, `if avail and fresh.get(n, True):`). An
open GPS gate therefore keeps the GPS node's trust updating, and keeps GPS as a
weighted neighbour for `baro`, `imu0`, `imu1` and `mag`.

Two side effects on the *other* paths are worth recording, because they are the
cost of the alternative semantics rather than of this one: `_apply` feeds the
GPS step detector (`online.py:371`) and the Holt historical predictor
(`online.py:401`, and GPS is in `HIST_CHANNELS`,
`csia/prediction/predictors.py:56`) from **every emitted sample, before any
validity flag is consulted**. The v1 live-MAVLink path emits zeros on an
invalid fix (`plugins.py:158-159`), so on that path a lost fix injects a
fictitious position step into a detector whose entire job is to catch position
steps. The gate suppresses the resulting evidence, but the state change has
already happened and outlives the invalid interval.
