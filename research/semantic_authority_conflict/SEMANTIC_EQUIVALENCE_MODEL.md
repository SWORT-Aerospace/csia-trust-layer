# Semantic equivalence — what counts as the same interpretation

Item 20 is explicit: **do not call every difference a conflict.** Two
authorities that encode the same meaning differently agree.

## The equivalence relation

Two interpretations are equivalent iff they place the raw state in the same
cell of the canonical evidence-state alphabet inherited from
`research/evidence_semantics` (`V I N S X R M E`) **and** impose the same
retention obligation.

Under that relation:

| pair | equivalent? | why |
|---|---|---|
| enum `INVALID` vs `valid=False` | **yes** | both map the observation to `I` with the same retention obligation; the encoding differs, the meaning does not |
| `NOT_MEASURED` (spec) vs `current = -1` (producer) | **yes** | the producer's `-1` *is* the spec's encoding of `NOT_MEASURED`; this is agreement expressed in two vocabularies |
| `RETAIN_PREVIOUS` vs `SUBSTITUTE_ZERO` | **no** | `R` versus `M`; different states and different values |
| `DROP_AND_RECORD_REASON` vs `PASS_THROUGH_MARK_INVALID` | **no** | one emits nothing, the other emits `I` with a real payload |
| `TREAT_AS_ABSENT_SILENTLY` (A) vs the same in (B) | **yes** | identical: both withhold and record nothing |

The battery row is the one that does real work. Reading the producer's `-1`
as a *different* interpretation from the spec's `NOT_MEASURED` would have
manufactured a `SPEC_VS_PRODUCER` conflict out of an encoding. They agree.

## Raw numeric equality is not semantic equivalence

Inherited from the previous package and re-checked here: `5.00 A` served as a
current the producer has disowned is not equivalent to `5.00 A` measured,
even though the numbers match. `DECLARED_VS_EFFECTIVE_SEMANTICS.csv` records
the declared interpretation and the measured core value in separate columns
for exactly this reason, and a test asserts they are never conflated.

## Aspect matching

Two authorities are comparable only when they speak about the same *aspect*
of the raw state. `fix_type` semantics and lat/lon/alt content are different
aspects of `fix_type < 3`. The first version of `conflicts.py` compared them
and reported a `SPEC_VS_PRODUCER` conflict that does not exist; after the
correction, that conflict type is empty everywhere.

## Consequence for the conflict count

Applying equivalence and aspect matching before counting:

| status | pairs |
|---|---|
| `CONFLICT` | 17 |
| `UNDERSPECIFICATION` | 7 |
| `AGREEMENT` | 2 |

and of the 17 conflicts, **none is between the specification and the
producer**.
