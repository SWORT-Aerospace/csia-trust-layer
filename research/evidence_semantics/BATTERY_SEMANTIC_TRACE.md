# Battery: a disowned current, served as a measurement

Item 13. **Question:** the producer says `current_battery == -1` — the
documented MAVLink "not measured" sentinel — and the pipeline goes on serving
`5.00 A`. Which transformation is responsible, what are the exact states, what
is the shortest trace, does the numeric value stay equal, and what is the
downstream consequence?

Every answer below is executed against the committed adapter, not read off it.

---

## The witness

**`X`, one message.** Exhaustive over all 120 words of length ≤ 4 in
`{V, X, N}`; minimal by construction.

The shortest *collapsing pair* is `V` / `X` — a nominal message and a sentinel
message are indistinguishable downstream after **two** words explored.

## Stage-by-stage, `X` against `V`, v1.1 adapter (clause BATT-F1)

| stage | `w1 = "X"` | `w2 = "V"` | identical? |
|---|---|---|---|
| `T1_protocol` | `X@12  N@12.32` | `V@12  N@12.32` | no |
| `T2_decode` | `X@12  N@12.32` | `V@12  N@12.32` | no |
| `T3_ingest` | **`R@12`** | `V@12` | no |
| `T4_channel` | `R@12  S@12.32` | `V@12  S@12.52` | no |
| **`T5_core_bridge`** | **`V@12` (value `5.0`)** | **`V@12` (value `5.0`)** | **YES** |
| `T6_slot` | `V@12` | `V@12` | yes |
| `T7_admissible` | `A@12  0@12.52` | `A@12  0@12.52` | yes |
| `T8_evidence` | identical | identical | yes |
| `T9_assurance` | `N@12` | `N@12` | yes |

`first_equivalent_level: VALUE`. `downstream_consequence: NONE`.

**The numeric value stays equal.** Both runs put `5.00 A` into the core. This
is item 6's example, measured: `(5.00 A, OBSERVED_VALID)` and
`(5.00 A, RETAINED_AFTER_SENTINEL)` are VALUE-equivalent *and* STATE-equivalent,
so no level of the hierarchy can separate them.

## The responsible transformation

Two lines, in two files.

**Where the state is created** — `ardupilot.py:176-181`:

```python
cur = g("current_battery", CURRENT_NOT_MEASURED)
if cur is not None and cur != CURRENT_NOT_MEASURED and finite(cur):
    self._put("battery.current", float(cur) / 100.0, ...)
else:
    self._reject_sentinel("battery.current")     # <-- no pop
```

Compare the GNSS branch six lines of code away (`ardupilot.py:232-235`),
which **does** pop:

```python
self._latest.pop("gnss.position", None)
self._latest.pop("gnss.velocity", None)
self._reject_sentinel("gnss.position", "gnss.velocity",
                      reason=MissingReason.NO_3D_FIX)
```

**Where the state is destroyed** — `base.py:198-208`. `_channel_value` tests
`entry is None` *first*; the sentinel branch is only reachable when no value
is retained. Because the battery branch left the entry in place, the sentinel
is recorded and never consulted:

```python
entry = self._latest.get(channel)
if entry is None:
    record = self._sentinel_at.get(channel)      # <-- unreachable here
    ...
value, t_recv, t_source, frame, unit = entry
```

So: the **first stage at which the distinction is destroyed is
`T5_core_bridge`**, and the **enabling omission is the missing `pop` at
`ardupilot.py:181`**. The checker names the collapse site; this document names
both, because a fix at either point would close it and only one of them is a
one-line change.

## The retained window, executed

Against the committed `ArduPilotAdapter`, `max_age["battery.current"] = 0.5 s`:

```
t = 0.00   current_battery = 500   ->  5.00 A stored
t = 0.10   current_battery = -1    ->  sentinel counted, 5.00 A RETAINED

sentinel_counts() == {'battery.current': 1}

  t = 0.11   usable=True   value=5.0   missing=None
  t = 0.30   usable=True   value=5.0   missing=None
  t = 0.60   usable=False  value=None  missing=MissingReason.STALE
  t = 1.20   usable=False  value=None  missing=MissingReason.STALE
```

Asserted as a test in `tests/test_dual_admissibility_confirmatory.py:204`, and
re-derived here by the stage probe.

**For 0.5 s the adapter reports 5.00 A as usable while simultaneously holding
a sentinel count for the same channel.** The two statements contradict each
other and only the first reaches the core. When the value finally goes, the
reason is `STALE`, not `SENTINEL` — the producer's own disavowal is recorded
in a counter and never delivered.

## `X` against `N` — clause BATT-F2, and it survives further

The other forbidden merge behaves differently, which is worth recording
because it shows the checker is not simply reporting FAIL everywhere:

| stage | `w1 = "X"` | `w2 = "N"` | identical? |
|---|---|---|---|
| `T3_ingest` | `R@12` | `V@12` | no |
| `T4_channel` | `R@12  S@12.32` | `V@12  S@12.32` | no |
| `T5_core_bridge` | `V@12  -@12.04` | `-@12` | **no** |
| `T6_slot` | `V@12` | `V@12` | yes |
| `T7_admissible` | `A@12  0@12.52` | `A@12  0@12.32` | **no** |
| `T9_assurance` | identical | identical | yes |

`first_collapse: T9_assurance`, `downstream_consequence: DIAGNOSIS_SCORE`.

A sentinel message still advances `slot.last_t` (the voltage channel is
`_put` normally, so the sensor is re-emitted), which pushes admissibility
0.2 s further out than a silent link would. So `X` and `N` are distinguishable
right up to the failsafe, and only there do they converge. Making the pipeline
distinguish them **more** would be an improvement; the clause fails, but for a
different and milder reason than BATT-F1.

## Three decoders, one raw condition, three currents

The strongest single number in this package. Same `BATTERY_STATUS` with
`current_battery == -1`, measured at `T5`:

| path | token | value into the frozen core | source |
|---|---|---|---|
| `v1_1_adapter` | `V` | **5.00 A** — the previous reading, retained | `ardupilot.py:181` (no pop) |
| `plugins_py` | `M` | **0.00 A** — fabricated | `plugins.py:194`, `max(msg.current_battery, 0) / 100.0` |
| `ulog_source_py` | `V` | **−1.00 A** — the sentinel itself, as a measurement | `ulog_source.py:196-199`, `valid: True` unconditionally |

None of the three can emit `X`. The contract requires `["V", "X"]`; measured
vocabularies are `['V']`, `['M','V']` and `['V']`.

**And this is not synthetic for the ULog path.** The committed 9.6 MB PX4 log
carries `current_a == -1.0` on **all 216 `battery_status` samples**
(`results/PX4_FEASIBILITY.json`). `ulog_source.py` would feed −1.00 A into the
frozen core as a usable battery current for every one of them, on real flight
data.

## Downstream consequence — stated at its true size

| pair | VALUE | STATE | EVIDENCE | DIAGNOSIS | ASSURANCE |
|---|---|---|---|---|---|
| adapter vs plugins | 90/120 | 90/120 | 15/120 | confounded | **0/120** |
| adapter vs ulog | 90/120 | 24/120 | 15/120 | 45/120 | **0/120** |
| plugins vs ulog | 90/120 | 90/120 | 0/120 | confounded | **0/120** |

**No battery word in this package produces any failsafe difference at all.**
`power_fault` needs `T["battery"] < 0.70` and battery trust never falls that
far in a 15 s run. The consequence classification tops out at
`DIAGNOSIS_SCORE`, on 45 words, for one pair.

That is the honest ceiling. The mechanism by which a CRITICAL could be raised
on a disowned current is real and is documented in
`../dual_admissibility_confirmatory/BATTERY_DEFECT.md`
(`failsafe.py:155` reads `T["battery"] < power_critical and fresh["battery"]`),
but **it was not observed here**, and no claim is made that it was.

## PX4 already fixes this, by declaration

`docs/simulation/CHANNEL_SEMANTICS.yaml` sets `battery.current` to
`UNAVAILABLE` **for the px4 platform only**, with a measured justification
("390 producer frames in 40 s (~9.8 Hz), every one carrying the -1 sentinel").
Running the same contracts against `PX4Adapter` measures an emitted vocabulary
of `[]` — nothing crosses into the core at all, so the retained-value defect
cannot occur there.

The mechanism that prevents it is a **static per-channel declaration**, not a
preservation check: someone noticed on one platform and wrote it down. The
ArduPilot row carries the same `missing_semantics` sentence
("-1 means 'not measured' -> MISSING, not zero current") without the platform
override, and the defect is live there.

## Classification

`IMPLEMENTATION DEFECT`. It is not evidence that any architectural hypothesis
generalises, and it is not part of any A/D result. The fix is independent of
every research question in this package:

```python
else:
    self._latest.pop("battery.current", None)
    self._reject_sentinel("battery.current",
                          reason=MissingReason.SENTINEL)
```

plus an explicit rejection path for `battery.voltage`, which today has none at
all (`if volts:` simply does not `_put`).
