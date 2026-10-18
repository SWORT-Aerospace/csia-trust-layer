# Error taxonomies

Items 41 and 42, kept apart on purpose. Confusing the two is the failure the
whole package is built to avoid: **a wrong specification is not a faulty
implementation.**

## Contract errors — the AI got the SPECIFICATION wrong (item 41)

`Ĉ != C*`. These say nothing about the implementation.

| code | meaning | observed here |
|---|---|---|
| `MISSED_STATE` | a state the reference records, absent from the candidate | — |
| `INVENTED_STATE` | a state with no source support | **fixtures F2, F3** |
| `WRONG_SENTINEL` | a sentinel condition that disagrees with the authority | **fixture F4** (comment says 255, code tests 0) |
| `WRONG_VALIDITY_PREDICATE` | the condition is right, the meaning is not | **fixture F1** (`valid` is a weight, not admissibility) |
| `WRONG_FRESHNESS_EVENT` | ages against the wrong event | — |
| `WRONG_TIMEOUT` | right event, wrong horizon | — |
| `WRONG_RETENTION_SEMANTIC` | claims discard where the code retains, or vice versa | **fixture F1**, second clause |
| `WRONG_ALLOWED_MERGE` | permits a merge the reference forbids | — |
| `WRONG_FORBIDDEN_MERGE` | forbids a merge the reference permits | — |
| `WRONG_CONSUMER` | names a consumer that does not read the field | **fixture F6** |
| `UNSUPPORTED_SOURCE_CLAIM` | no citation resolves | **`GPS_RAW_INT.epv` under B1** — and it was the *correct* rule |
| `FAILURE_TO_ABSTAIN` | confident answer to an underdetermined question | **fixture F5** |

Six of twelve were exercised. The six that were not are all clause kinds the
protocol schema is silent about, so the pilot could not reach them — which is
itself the finding in §"What the schema does not carry".

## Implementation defects — the CODE violates a supported contract (item 42)

Only reachable from `Phase 1 = SOURCE_SUPPORTED`.

| code | meaning | observed in THIS package |
|---|---|---|
| `SEMANTIC_COLLAPSE` | two required-distinct states become one | none |
| `SEMANTIC_DIVERGENCE` | two implementations disagree | none |
| `RETAINED_AFTER_DISAVOWAL` | a disowned value keeps being served | none |
| `SENTINEL_AS_VALUE` | a sentinel enters as a measurement | none |
| `INVALID_AS_ABSENCE` | explicit invalidity becomes silence | none |
| `STALE_AS_CURRENT` | an aged value presented as current | none |
| `PROVENANCE_LOSS` | the origin of a value is discarded | none |
| `PATH_NON_EQUIVALENCE` | ingest paths differ on one raw condition | none |

**Every cell is empty.** Zero defects were promoted from any held-out
contract (`results/DEFECT_DISCOVERY_RESULTS.csv`: 42 candidates evaluated, 0
promoted, 19 inconclusive, 10 reaching Phase 2).

Instances of all eight codes exist in this codebase — the previous package
found and localised them — but **none was rediscovered from an AI-synthesized
held-out contract**, and the reason is structural rather than a failure of
the model. See the report, §29.

## The crossing rule

An error in the first table can produce a Phase-2 counterexample that reads
exactly like an entry in the second. That is item 25's dangerous case. The
only defence implemented is Phase 1: a contract that fails C2–C6 never
reaches the checker, so it can never manufacture a defect.

The defence is only as good as Phase 1's checks, and C3 — the one with real
authority — exists only because this protocol ships a machine-readable
sentinel attribute.
