# AI-assisted evidence contract synthesis — Stage 0/1

**Verdict: `HEURISTICS_SUFFICIENT`. Novelty: NOT ESTABLISHED.**
Read `CHATGPT_REVIEW_REPORT.md`, and §31 of it before any number.

## The question

The previous package concluded that its deterministic checker was bounded by
a hand-written contract — "the declaration is the hard part". This package
tested whether an AI can write that declaration while a deterministic layer
stops its mistakes from becoming safety findings.

## The two answers

**The architecture is published.** ISSTA 2025 (*Validating Network Protocol
Parsers with Traceable RFC Document Interpretation*) already does docs → LLM
specification → independent verification → traceable localisation, and
already separates LLM hallucination from implementation bug.

**The bottleneck was partly illusory.** MAVLink's own schema carries the
sentinel semantics in a machine-readable attribute:

```xml
<field type="int16_t" name="current_battery" units="cA" invalid="-1">
```

A ~20-line XML lookup scores **14/14** on the frozen held-out pilot with
authoritative citations and zero unsupported claims. The AI reading only
implementation source abstains on 8 of 14, and its one correct positive is an
ungrounded recall the grounding layer refuses.

| condition | abstain | TP | FP | TN | FN | unsupported |
|---|---|---|---|---|---|---|
| B0a regex over source | 0 | 0 | 0 | 12 | 2 | — |
| **B0b schema attribute** | 0 | **2** | 0 | 12 | 0 | **0.000** |
| B1 AI, code only | 8 | 1 | 0 | 5 | 0 | 0.091 |
| B2 AI + docs *(confounded)* | 0 | 2 | 0 | 12 | 0 | 0.000 |
| B3 AI + one verifier revision | 9 | 0 | 0 | 5 | 0 | 0.000 |

**The clause the schema settles is the clause nobody needed help with.**
Retention, freshness, forbidden merges and the consumer requiring each — the
four the previous package identified as the real bottleneck — appear in no
schema attribute, and could not be scored here because the only reference for
them is model judgement.

## Other results

* **Zero defects promoted** from any held-out contract (42 evaluations).
  The one correct held-out sentinel, `GPS_RAW_INT.epv`, is `INCONCLUSIVE`
  because no committed decoder reads the field. Correct extraction is not
  the binding constraint; reachability is.
* **One verifier revision** drove unsupported assertions 0.091 → 0.000 and
  true positives 1 → 0, in the same step.
* **All six deliberately wrong contracts stopped at Phase 1** — but two of
  them passed the first run, and the checks were then corrected by the same
  author who wrote the fixtures. That figure is fitted, not an estimate.

## Reading order

1. `CHATGPT_REVIEW_REPORT.md` — 40 sections, hostile review A–J
2. `PRIOR_ART_MATRIX.md` — the kill test, run first
3. `RESEARCH_QUESTION.md` — the architecture and the two propositions
4. `SOURCE_GROUNDING_MODEL.md` — what "supported" means mechanically
5. `HALLUCINATION_CONTAINMENT.md` — read the caveat before the number
6. `ERROR_TAXONOMY.md` — specification errors and implementation defects, apart
7. `CLAIM_LEDGER.json` — 17 claims, 3 refuted predictions

## Running it

```bash
make ai-contract-freeze-check   # did the frozen predictions move?
make ai-contract-baselines      # B0a and B0b
make ai-contract-ground         # the source-grounding validator
make ai-contract-containment    # the six NON-SCORED fixtures
make ai-contract-score          # all conditions vs the reference
make ai-contract-defects        # two-phase promotion over the pilot
```

`build_reference.py` refuses to run unless `FREEZE.json` matches, so the
reference cannot be built before the predictions were written.

## The limitation that governs everything

One model, in one conversation, produced the candidates, the reference, the
metrics, the checks, the fixtures and this file. **The ordering is enforced
by hashes; the independence is not, and cannot be.**

The conclusion that a schema lookup beats the AI is the most robust claim
here, precisely because it does not depend on any judgement of mine: the
attribute exists, the lookup is mechanical, and the reference is that same
attribute.

Nothing here is called ground truth. Nothing reaches `HUMAN_REVIEWED`.
