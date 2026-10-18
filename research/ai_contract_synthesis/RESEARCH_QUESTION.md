# Research question

> Can an AI system synthesize useful, source-grounded evidence-semantic
> contracts from real autonomous-system software and protocol documentation,
> while a deterministic verification layer prevents unsupported AI
> interpretations from becoming safety claims?

## Where the question came from

The previous package (`research/evidence_semantics`, commit `2036a2a`) built
a deterministic checker for end-to-end preservation of evidence semantics and
concluded `IMPLEMENTATION_DEFECTS_ONLY`. Its `TOOLING_FEASIBILITY.md` named
the binding limitation in one sentence:

> "the tool's value is bounded above by the quality of a hand-written
> declaration, and the declaration is the hard part."

That is the bottleneck this package tests. **The chronology is worth stating
plainly** (reviewer J): AI was not the plan. It is being applied to a
bottleneck the earlier work identified empirically, and the question is
whether it moves it.

## The architecture under test

```
source code + protocol schema + comments + tests
        │
        ▼   AI SEMANTIC CONTRACT MINER          proposes
candidate contract clause, with citations
        │
        ▼   PHASE 1  contract evidence          is the premise supported?
        ▼   PHASE 2  implementation conformance does T preserve it?
        │
        ▼
finding, or INCONCLUSIVE
```

The AI proposes semantics. The deterministic layer establishes implementation
behaviour. **These roles are never inverted**, and the code enforces it:
`verification/containment.py:promote()` only reaches Phase 2 from
`SOURCE_SUPPORTED`.

## The distinction the whole package rests on

**AI output is not evidence.** An assistant saying "-1 means
CURRENT_NOT_MEASURED" is a hypothesis. The ladder, and nothing is allowed to
skip a rung:

| status | means |
|---|---|
| `AI_INFERRED` | the model said it |
| `SOURCE_SUPPORTED` | a citation resolves and the executable source corroborates it |
| `EXECUTION_CONFIRMED` | the implementation was actually run |
| `CHECKED_TO_BOUND` | exhaustively checked over a bounded alphabet |
| `HUMAN_REVIEWED` | a person looked |

Nothing in this package reaches `HUMAN_REVIEWED`. Nothing in it is called
ground truth.

## Two propositions, never merged (items 40, 47)

Let `C*` be the source-supported contract, `Ĉ` the AI's candidate, `T` the
implementation.

* **P1** — `Ĉ` is supported by source evidence as an extraction of `C*`
* **P2** — `T` violates `Ĉ`

A trustworthy finding needs P1 established **and** P2 violated. The dangerous
failure (item 25) is a false `Ĉ` for which P2 holds trivially: the checker
then produces something that looks like a counterexample but is a
specification error wearing an implementation error's clothes.

A **specification error** and an **implementation error** are different
things and the pipeline must never report one as the other.

## What would count as success (item 44)

All eight, or it is not a promising result. Assessed in
`CHATGPT_REVIEW_REPORT.md` §40; three of the eight fail outright.

## What is explicitly out of scope

No learned safety detector, no neural anomaly detection, no LLM in the
runtime (item 43). The AI belongs in **development-time specification
mining**. Runtime safety stays deterministic and frozen.
