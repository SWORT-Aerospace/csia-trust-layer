# Canonical evidence-state model

Items 5 and 6. **Derived from committed source, not proposed a priori.** Every
state below has a named producer in this repository; a state with no producer
is a promise the system does not keep, and `csia/aircraft/sample.py:63-72`
already records what happened last time one was carried in the vocabulary
unproduced.

**This model is not claimed as new.** Codd argued in 1979 for two distinct
nulls — missing-but-applicable and missing-and-inapplicable — and SQL's
decision to merge them has been studied for forty years. ARINC 429, SEVA,
NAMUR NE 107 and OPC UA each define a richer status vocabulary than this one.
See `PRIOR_ART_MATRIX.md`.

---

## 1. An observation is a pair

```
E = (x, q)
```

* `x` — the numeric or structured value, or ⊥ when there is none
* `q` — the quality/provenance coordinate

**Equality of `x` is not equivalence of `E`.** The battery case is the exact
counterexample item 6 asks for, and it is measured rather than imagined:

```
(5.00 A, OBSERVED_VALID)   ≠   (5.00 A, RETAINED_AFTER_SENTINEL)
```

Both cross into the frozen core as `battery.current = 5.0` with
`valid = True`. `CROSS_PATH_EQUIVALENCE.csv` records them as VALUE-equivalent
and STATE-equivalent; `CAUSAL_BLAME_TRACES.json` shows every stage from
`T5_core_bridge` onward identical. The distinction exists at `T3_ingest` and
`T4_channel` and nowhere after.

## 2. The quality alphabet

Six states. Each row names the code that produces it.

| `q` | Name | Meaning | Produced by |
|---|---|---|---|
| **V** | `OBSERVED_VALID` | a value arrived and the producer stands behind it | `_put` (`base.py:140`) → `contract.qualify` |
| **I** | `OBSERVED_INVALID` | a message arrived and the producer says the value is not usable | `_reject_sentinel(..., reason=NO_3D_FIX)` (`ardupilot.py:234`); `plugins.py:157-159` emits `valid=False`; `ulog_source.py:189` emits `valid=(fix>=3)` |
| **N** | `NOT_OBSERVED` | nothing arrived | `MissingReason.NOT_RECEIVED` (`sample.py:55`); at the wire, inferred by refresh-rate timeout |
| **S** | `STALE` | a value arrived but is older than the channel's limit | `base.py:222-227`; `online.py:603-605` |
| **X** | `SENTINEL` | a message arrived carrying a documented "not measured" encoding | `_reject_sentinel` default (`base.py:152`); MAVLink `current_battery == -1`, `voltages[i] == 65535` |
| **R** | `RETAINED_AFTER_DISAVOWAL` | a value is being served that the producer has since disowned | **no producer.** See §4. |

`FIELD_ABSENT`, `NOT_QUALIFIED` and `STUB` also exist in
`MissingReason` and are real, but none of them is reachable from the input
alphabets used here, so they are not part of this model's working set.

## 3. The value-provenance coordinate

`R` is not a sibling of `V`/`I`/`N`/`S`/`X`. It is a statement about where
`x` came from while `q` still claims `V`. Three such provenances are
distinguishable in committed source:

| provenance | meaning | produced by |
|---|---|---|
| `REAL` | the value the producer sent | all three paths, nominal case |
| `RETAINED` | a real value the producer has since disowned | `ardupilot.py:181` calls `_reject_sentinel` **without** popping `_latest`, so `_channel_value`'s `entry is not None` branch keeps serving it (`base.py:199`) |
| `IMPUTED` | a value the decoder invented | `plugins.py:158` writes `pos=zeros(3), vel=zeros(3)`; `plugins.py:194` writes `max(msg.current_battery, 0)/100.0`, turning the −1 sentinel into `0.00 A` with `valid=True` |

Written as pairs, the two defects are:

```
R = (REAL-but-disowned, q=V)      the ArduPilot battery case
M = (IMPUTED,           q=V)      the plugins.py battery case
```

The probe emits `R` and `M` as tokens because the pair is what matters; the
implementation has a token for neither.

## 4. Why `R` has no producer — and why that is the finding

Every other state in §2 is something the code can say. `R` is a state the
code can be **in** and cannot **express**. The adapter records the sentinel
(`sentinel_counts()["battery.current"] == 1`) and simultaneously serves
`5.00 A` as usable. Both statements are true of the same instant and only the
second one reaches any consumer.

`_reject_sentinel`'s own docstring (`base.py:151-171`) was written to fix
precisely this class of loss for the GNSS case. It fixed the recording. It did
not fix the delivery.

## 5. States considered and REJECTED

Item 5 warns against ontology inflation. Two candidates were tested against
source and only one survived.

**`M = IMPUTED` — KEPT**, on the strength of `plugins.py:158` and
`plugins.py:194`. It is not a hypothetical: the checker measures
`plugins_py`'s battery output vocabulary as `['M', 'V']`.

**`E = ESTIMATED` — KEPT IN THE MODEL, MARKED NOT EXERCISED.** Justified by
exactly one committed line: `plugins.py:177`,
`elif k == "GLOBAL_POSITION_INT" and not ctx.get("has_raw_gps")`, which feeds
**EKF-fused output** into the same `gps` core slot that otherwise carries raw
receiver output, with no marker distinguishing them. That is a genuine extra
provenance and the file's own comment says why it matters ("the EKF
innovation-gates faults out of its fused output … hiding exactly what we
exist to detect", `plugins.py:152-154`). It is not exercised by any word in
this package's alphabets, which all carry `GPS_RAW_INT`, so it appears here
as a state of the model and **not** as a measurement.

**Nothing else was added.** In particular there is no `DEGRADED`, no
`UNCERTAIN` and no confidence scalar: no committed code produces one, and
`Quality` (`sample.py:32-43`) is explicit that its ladder is not a confidence
score.

## 6. The pipeline, as stages

The nine observation points the probe reads. `T1`–`T2` are the wire and the
decoder; `T3`–`T4` exist only in the v1.1 adapter; `T5` is the boundary of
the frozen core; `T6`–`T9` are inside it.

| stage | what it holds | site |
|---|---|---|
| `T1_protocol` | the wire, with absence inferred by a 1.5× refresh-rate timeout (the ARINC 429 receiver convention) | MAVLink field |
| `T2_decode` | the decoder's reading of the last message | `ardupilot.py:_ingest_gps` / `plugins.py:map_mavlink` / `ulog_source.py:_build_events` |
| `T3_ingest` | adapter retained state: `_latest` and `_sentinel_at` | `base.py:140-177` |
| `T4_channel` | the `ChannelValue` served, with its `MissingReason` | `base.py:198-229` |
| `T5_core_bridge` | what crosses into the frozen core | `base.py:306-337` |
| `T6_slot` | `slot.seen`, `slot.valid`, `slot.last_t` | `online.py:312-316` |
| `T7_admissible` | `fresh[sensor]` — operational admissibility | `online.py:603-605` |
| `T8_evidence` | evidence mass and trust for the sensor | `engine.py:146` |
| `T9_assurance` | failsafe level and issued actions | `failsafe.py:145-160` |

**Paths B and C have no `T3` or `T4` at all.** They map a message straight to
a core sample. This is not a limitation of the probe; it is why they cannot
carry a `MissingReason`, and the checker reports it as
`no_representation_stage` rather than blaming a file those paths never
execute.

## 7. Vocabulary width, measured

The width of each stage's output alphabet, as the checker measures it over
lengths 1–4:

| stage | distinct tokens it can carry |
|---|---|
| `T1`/`T2` | 3 per family (`V`,`I`,`N` / `V`,`X`,`N` / `V`,`Z`,`N`) |
| `T4_channel` | up to 6 (`V`,`I`,`N`,`S`,`X`,`R`) — `MissingReason` has 7 members |
| `T5_core_bridge` | **2**: emit a sample with `valid=True`, or emit nothing |

`to_core_samples` emits `chans["valid"] = True` unconditionally
(`base.py:335`); the only other outcome is `continue`. So the boundary into
the frozen core is one bit wide, and every state in §2 must be encoded in it.
Measured emitted vocabularies:

| family | `v1_1_adapter` | `plugins_py` | `ulog_source_py` |
|---|---|---|---|
| gnss | `['V']` | `['I','V']` | `['I','V']` |
| battery | `['V']` | `['M','V']` | `['V']` |
| mag | `['V']` | `['V']` | `['V']` |

A one-bit boundary is not automatically a defect — item 9 is explicit that a
merge only matters against a declared downstream property. `EQUIVALENCE_LEVELS.md`
defines those properties and `CROSS_PATH_EQUIVALENCE.csv` reports which merges
actually cost something.

## 8. Two staleness horizons for the same channel

Recorded because it surfaced from the stage traces and is easy to miss:

| channel | adapter `MaxAge` (`base.py:42-54`) | core `STALE_TIMEOUT_S` (`online.py:47-50`) |
|---|---|---|
| `gnss.position` | 1.00 s | 0.5 s (`gps`) |
| `battery.current` | 0.50 s | 0.5 s |
| `mag.field_ut` | 0.20 s | 0.1 s (`mag`) |

The core's limit is the stricter one everywhere, so it governs and no defect
follows. It does mean a channel can read `V` at `T4` while the core already
treats the sensor as inadmissible at `T7`, which is visible in the GNSS blame
trace (`T4: V@12 → S@12.84` against `T7: A@12 → 0@12.32`).
