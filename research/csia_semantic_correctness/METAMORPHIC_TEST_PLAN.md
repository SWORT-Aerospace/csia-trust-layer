# Metamorphic and property-based test plan (Parts 12, 13, 15)

CSIA semantic correctness audit, 2026-09-29. **Design only: none of these
tests are added to the production suite in this phase.**

## 1. Part 12: established terms, before naming anything

The brief asks for established terminology first. The properties below use
existing names (`SOURCES.md`):

| brief's wording | established term | source |
|---|---|---|
| supporting relevant evidence should not refute its hypothesis; refuting evidence should not strengthen it | **monotonicity of set elimination** (information ordering). In nonmonotonic inference: **cautious** and **rational monotony** | L04; L01 for the elimination framework |
| irrelevant evidence should not resolve ambiguity | **isolability** (FDI); **Parikh's relevance-sensitive axiom (P)** (belief revision); the **irrelevance problem** (nonmonotonic reasoning) | L02, L03, L04 |
| conflicting evidence should be exposed, not silently resolved | **conflict** between sources, as studied in evidence combination (the architecture package's S062). Diagnosis keeps conflicts as first-class objects | architecture package S062; L11 |
| missing evidence must not act as evidence | **Kleene strong three-valued logic**; the SQL NULL semantics built on it | L05 |
| order and duplication must not matter | **commutativity** and **idempotence** of combination. For non-distinct evidence: the cautious rule | L10 |

**What the enumeration found (N1).** Set elimination itself passes the
monotonicity properties. The two shapes are:

- the XSYS shared-symptom pair: 27 valuations;
- a three-hypothesis shape with a specific confirmer and a specific refuter
  per hypothesis: 729 valuations.

On both, **zero** violations of either rule:

- making an unknown confirmer True never rejects its hypothesis;
- making an unknown refuter True never makes its hypothesis supported.

**Where adding information does lower coherence.** The failures of "adding
information" are not in the elimination rule. They are in three places:

1. what reaches it: irrelevant (P1) and unknown (P6) inputs are turned into
   values;
2. the silent SUPPORTED → UNSUPPORTED transition when a specifically
   confirmed hypothesis gains a refuter (P13): 27 such transitions in the
   specific shape, with no record of the conflict;
3. the silent SUPPORTED → AMBIGUOUS drop in attribution when an unrelated
   second fault appears (R14).

## 2. Part 13: the property suite

**The executed matrix** is `SEMANTIC_PROPERTY_MATRIX.csv`:

- 20 properties;
- for each: precondition, transformation, expected invariant, current result,
  PASS/FAIL, and the shadow-successor result.

**Frozen v2 fails 15 and passes 5:**

- P7: candidate preservation;
- P8: deterministic replay;
- P10: trace consistency;
- P14: monotone information;
- P15: idempotence of attribution decisions.

**Under the shadow successor, 16 pass and 4 still fail:**

| still failing | why |
|---|---|
| P16 | a profile declaration gap, not reasoning |
| P17 | record validation is left to governance |
| P18 | correlation is deliberately not addressed |
| P20 | optional fix C8 is deferred |

**How the suite is organized when implemented:**

| layer | what it runs | inputs | cost |
|---|---|---|---|
| **metamorphic, corpus** | P1-P4, P6, P9, P12, P16 | the final tick of every shipped scenario, and every tick for P9 and P16 | ~2 min in CPython today (the whole probe is ~3 min) |
| **metamorphic, minimal** | the R-cases as fixed fixtures | about 40 records in total | < 5 s |
| **exhaustive small-state** | N1-N6 (`SMALL_STATE_ENUMERATION.md`) | 10,113 configurations over six tables (756 + 125 + 3,072 + 1,296 + 4,608 + 256), plus each configuration's reversed, duplicated and completed variants | ~1 min |
| **property-based** | the same invariants on generated inputs (section 3) | random evidence sets | bounded by example count |
| **characterization** | pins CURRENT frozen behaviour per defect | the R-cases | < 5 s |

**Two views of every test.**

- **The 2.0.0 view** keeps the frozen behaviour and the frozen tests
  (`EXISTING_TEST_COVERAGE.csv`: T01, T02, T04 and T05 stay as compatibility
  tests).
- **The successor view** asserts the corrected invariants.

**Characterization tests.** A test that pins current behaviour is labelled as
such. It is written to **flip** when the successor lands. It must never be
edited to pass (L08).

## 3. Part 15: property-based strategy

`hypothesis` 6.168.0 is already installed in the repository environment, so
no dependency is added. The design:

```
strategies (all deterministic under a fixed database seed; derandomize=True in CI)

  domains      sampled_from(DOMAINS)                       # the six v2 domains
  states       sampled_from(ObservationState)              # all five, including UNAVAILABLE and NOT_APPLICABLE
  component    text(ascii_lowercase, 1..8) per domain       # small alphabet, forces collisions
  relation     sampled_from(relations the SIG predicates read) | text(...)
  record       builds(EvidenceRecord, domain, component, relation,
                      observation_state=states,
                      applicability=consistent with the state,
                      dependencies=lists(node ids drawn from the same draw, max 3),
                      reason_codes=subsets of the codes the predicates read,
                      affected_functions=subsets of the profile's functions,
                      attributable=booleans())
  tick         lists(record, 0..12)
  graph        the dependencies inside `tick` (cycles allowed; attribution is cycle-safe)
  candidates   whatever `tick` makes adverse
```

**Transformations**, each a strategy over a drawn tick:

| transformation | what it does |
|---|---|
| `permutations(tick)` | order |
| `tick + [choice(tick)]` | exact duplicate |
| `tick + tick` | group duplicate |
| `tick + [irrelevant]` | `irrelevant` draws a component whose id appears in no `dependencies` of the tick, in no relation's implicates, and in no subject's scope. Rejected with `assume` otherwise |
| `tick - [r]` for r out of scope | removal |
| `twin(r, UNAVAILABLE)` with both completions | missing evidence |
| predicate injection | wrap one predicate so it raises, or returns `numpy.True_`, `1` or `nan` |
| record corruption | set one tuple field to None |

**Assertions** are the invariants in `SEMANTIC_PROPERTY_MATRIX.csv`. Each is
split into a `decision` part, which must hold, and a `trace` part, which is
reported. The decision part is the projection used by the probe: verdict,
supported, unresolved, rejected ids, candidates and common cause.

**Shrinking.** Hypothesis shrinks each failure to a minimal tick. The R-cases
in `MINIMAL_REPRODUCTIONS.md` are what such shrinking should find. R1B is two
records and R6 is nine. **They become the regression database's seed
examples.**

**Budget.** 200 examples per property per CI run, 5,000 nightly. Every
counterexample is saved to the database and replayed first thereafter.

**What the fuzzer must not do.** It must not assert properties that frozen v2
is not meant to have:

- **Adding legitimate relevant evidence** may lower certainty. Example: a
  second confirmed hypothesis turns SUPPORTED into AMBIGUOUS. That is allowed
  by P14 and must not be flagged.
- **A second adverse component** may turn UNIQUE into AMBIGUOUS. That is
  allowed (SC-17) until governance decides multi-fault semantics.

## 4. What the executed probe already provides

`semantic_probe.py` implements all of section 2 except the property-based
layer. It uses fixed-seed shuffles instead of Hypothesis for P3, so its
output is byte-reproducible.

**Its instrument check.** With no correction switched on, the shadow
reproduces the frozen output on all 2,640 shipped ticks. That is 0
mismatches in decision or trace (SH.IDENTITY_CHECK). **Every difference the
probe attributes to a correction is therefore caused by that correction, not
by a re-implementation error.**
