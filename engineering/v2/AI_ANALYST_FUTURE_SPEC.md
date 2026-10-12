# AI ANALYST — THE SEAM, DOCUMENTED AND NOT BUILT

Phase C §§33–34.

**Nothing in this document is implemented.** No model is called, no inference
runs, and no code path in `csia/` reaches an AI system. This describes where
such a component *could* attach and, more importantly, the three things it
may never do.

---

## 1. The three prohibitions (§34)

An AI analyst **may not**:

1. **Modify function eligibility directly.** Eligibility is derived from
   declared requirements and deterministic evidence. A model that could set it
   would make the function verdict unverifiable, and the whole ledger becomes
   a record of an opinion.
2. **Issue control commands.** This layer has no path to an actuator and an AI
   component does not get one. The existing technical no-command enforcement
   is not weakened.
3. **Turn an unsupported hypothesis into a confirmed cause.** `SUPPORTED`
   means a discriminating predicate returned `True`. A model's confidence is
   not a measurement, and promoting `unresolved` to `supported` is exactly the
   §2 failure the whole layer exists to prevent.

The Phase C tagline is the design rule: **AI may help interpret. Deterministic
evidence decides.**

## 2. Where the seam is

The natural attachment point is **downstream of `Localization` and
`FunctionExplanation`**, reading their structured output and producing prose
or prioritisation for a human.

```
    domains -> evidence -> localization -> explanation -> [SEAM] -> operator
                                   ^                         |
                                   |                         |
                              deterministic            interpretation only
                                                       (no back edge)
```

There is no back edge, and that is the entire safety argument. Everything to
the left of the seam is reproducible from the ledger; everything to the right
is advice. A reviewer can replay the run and get the same verdict whether or
not the analyst ever ran.

## 3. What it could usefully do

- **Rank an ambiguous set for investigation order.** Set B returns two equally
  supported hypotheses on the multirotor. Nothing in the evidence separates
  them, but service history might suggest which to check first. That is a
  recommendation about *where to look*, not a claim about *what is true*, and
  the verdict stays `AMBIGUOUS`.
- **Explain the rejection chain in prose.** `rejected` is a list of
  `(hypothesis, predicate)` pairs. Turning that into a paragraph is
  presentation, and §32 already says prose is optional and never canonical.
- **Point at model gaps.** Set C's result is "the dependency model is blind to
  COMMUNICATION and COMPUTE sharing for this source pair". Suggesting which
  dependencies to declare is engineering advice to a human, delivered offline.
- **Cluster ledger history.** Recurring symptom/verdict patterns across many
  runs is an offline analysis over an append-only record, with no live path.

## 4. What it must not be asked to do

- **Fill in an unmeasurable predicate.** `None` means the platform cannot
  measure it. A model guessing a value would convert an honest ambiguity into
  a fabricated resolution, and every downstream artifact would look identical
  to a real one.
- **Choose between `SUPPORTED` and `AMBIGUOUS`.** That follows mechanically
  from the counts.
- **Author or edit hypothesis declarations at runtime.** The signature matrix
  is generated from the declarations the runtime uses; a runtime-mutable
  matrix would make the generated artifact meaningless.

## 5. If it is ever built

Minimum conditions, none of which are met today:

1. The seam is a **read-only consumer** of the serialised explanation. It
   receives `to_dict()` output and returns text plus an ordering. It gets no
   handle on the engine, the registry, or the evidence records.
2. Its output is a **separate field** in the operator view, visibly labelled as
   interpretation, and is not written into the assurance ledger — or if it is,
   into a distinct event type that replay verification ignores.
3. A test asserts that removing the analyst entirely changes no verdict, no
   reason code, and no ledger hash on the full scenario corpus. If that test
   cannot be written, the seam is in the wrong place.
4. Its prompt and model identity are recorded alongside its output, because an
   unattributed interpretation in a safety record is worse than none.

Until all four hold, the correct state of this document is the one it is in:
a description of a boundary that has not been crossed.
