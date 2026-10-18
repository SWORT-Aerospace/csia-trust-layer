# Battery — `current_battery == -1`

Item 14/15. Reproduced exactly before anything else was built (item 51).

## Reproduction

| path | token at the core boundary | value |
|---|---|---|
| `v1_1_adapter` | `V` | **5.00 A** |
| `plugins_py` | `M` | **0.00 A** |
| `ulog_source_py` | `V` | **−1.00 A** |

Identical to `research/evidence_semantics` at commit `2036a2a`. Hard stop
cleared.

## The authority table

| authority | interpretation | citation |
|---|---|---|
| `C_spec` | `NOT_MEASURED` | `common.xml:BATTERY_STATUS.current_battery`, `invalid="-1"` and "-1: autopilot does not measure the current" |
| `C_producer` | `NOT_MEASURED` | `GCS_Common.cpp:390-393` — `if (battery.current_amps(current, instance)) { … } else { current = -1; }` |
| `C_consumer_A` | `RETAIN_PREVIOUS` | `ardupilot.py:181` — `_reject_sentinel` without popping `_latest` |
| `C_consumer_B` | `SUBSTITUTE_ZERO` | `plugins.py:194` — `max(msg.current_battery, 0) / 100.0` |
| `C_consumer_C` | `LITERAL_MINUS_ONE` | `ulog_source.py:196-199` — `valid: True`, unconditionally |

**The specification and the producer agree exactly.** ArduPilot writes `-1`
in precisely the case the schema says `-1` means. There is no
spec-versus-producer conflict here; the sole `AGREEMENT` row in this case is
that pair.

All three consumers disagree with that agreed authority, and with each
other. 9 `CONFLICT` pairs: 3 `SPEC_VS_CONSUMER`, 3 `PRODUCER_VS_CONSUMER`,
3 `CROSS_CONSUMER`.

## Decision sensitivity

| level | distinct outcomes | verdict |
|---|---|---|
| VALUE | 3 | SEMANTICALLY_AMBIGUOUS |
| STATE | 2 | SEMANTICALLY_AMBIGUOUS |
| EVIDENCE | 1 | **ROBUST** |
| DIAGNOSIS | 2 | CONFOUNDED_BY_CONTROL |
| ASSURANCE | 1 | **ROBUST** |
| ACTION | 1 | **ROBUST** |

A three-way disagreement about a safety-relevant current — 5.00 A, 0.00 A and
−1.00 A — and **operational admissibility, the failsafe level and the issued
actions are all identical.** The disagreement dies between STATE and
EVIDENCE.

The DIAGNOSIS row is `CONFOUNDED_BY_CONTROL`: the paths' trust trajectories
already differ on an all-nominal word, so that difference cannot be
attributed to the sentinel.

## Baselines

* **B0 SPEC_FIRST** — RESOLVES. `NOT_MEASURED`.
* **B1 IMPLEMENTATION_FIRST** — RESOLVES. `NOT_MEASURED`, the same answer.
* **B2 OBSERVATION_FIRST** — SELF_INCONSISTENT. Three runtimes, three answers.
* **B3 SET_VALUED** — flags ambiguity at VALUE and STATE. Neither reaches
  ACTION.

Spec precedence settles this case completely, and so does producer
precedence, because they say the same thing.

## Classification

**Not an authority conflict. Three consumer bugs against an authority that
speaks with one voice.** Fixing all three to honour the spec removes every
conflict in this case, which is item 52's test and item 55's
`ENGINEERING_INCONSISTENCY_ONLY` condition.
