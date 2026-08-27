# The authority model

Items 1, 2, 7, 10, 18. Four authority kinds, each pinned to an independently
identifiable source (item 58-I), each citation re-read from disk by
`authorities.py:verify()`.

| authority | what it is | evidence tier |
|---|---|---|
| `C_spec` | the MAVLink message definition — attribute and description | protocol schema |
| `C_producer` | ArduPilot's own executable source: what actually fills the field | producer source |
| `C_consumer_{A,B,C}` | the three committed CSIA ingest paths | consumer source |
| `C_observed_{A,B,C}` | what those paths actually put into the frozen core, measured | runtime |

No `C_test`, `C_documentation` or `C_operator`. Item 1 says not to inflate
the set and none of the three cases needed them.

**No authority carries a weight.** Item 10 forbids inventing precedence
numbers, and nothing in this package assigns one. The analysis uses set
inclusion, equality of downstream outcome, and silence — nothing else.

## Two coordinates every authority entry carries

Both were added after the first run produced a wrong answer, and both are
recorded rather than quietly repaired.

**`scope`** — which *raw state* the authority speaks about. `C_producer_absence`
describes "no GPS configured, no message sent", which is a different raw state
from `fix_type < 3`. Pooling it made `IMPLEMENTATION_FIRST` read as
self-inconsistent on GNSS when it is not.

**`aspect`** — which *part* of the raw state it speaks about. `C_spec` says
what `fix_type` MEANS; `C_producer` says what the lat/lon/alt fields CONTAIN.
Comparing them produced a spurious `SPEC_VS_PRODUCER` conflict in the first
run. After the correction there are **zero** conflicts of that type anywhere.

Only authorities sharing both `scope` and `aspect` are comparable.

## SILENT is not an interpretation

The fifth value, and the one that matters most:

```
C_a(r) = SILENT     the authority does not speak to this raw state
```

Item 8 defines conflict as `|{C_a(r)}| > 1`. Encoding silence as an
interpretation would make every gap look like a disagreement. It is not one:
**an authority that says nothing does not contradict anybody.**

This is why the taxonomy in `conflicts.py` has a status the brief did not
list — `UNDERSPECIFICATION` — and why that status, not `CONFLICT`, describes
the magnetometer case and the GNSS position fields.

## The interpretation set

```
S*(r) = { C_a(r) : a admissible, C_a(r) != SILENT }
```

A **set**, not a distribution (item 9). No weights, no priors, no
combination rule. Where `|S*(r)| = 1` the authorities agree; where `> 1` they
disagree; where `S*(r)` is empty every downstream choice is licensed and the
gap is in the standard.

## What the model found

| case | `\|S*\|` | composition |
|---|---|---|
| battery | 3 | `NOT_MEASURED` (spec **and** producer) vs three different consumer readings |
| GNSS position fields | 4 | spec SILENT; producer + three consumers each different |
| magnetometer | 2 | spec SILENT; two consumer readings |

**The spec and the producer never disagree.** Zero `SPEC_VS_PRODUCER`
conflicts across all three cases. Every conflict counted is
`CROSS_CONSUMER` (8), `PRODUCER_VS_CONSUMER` (6) or `SPEC_VS_CONSUMER` (3).
