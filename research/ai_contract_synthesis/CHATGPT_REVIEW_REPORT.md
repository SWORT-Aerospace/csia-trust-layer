# AI-assisted evidence contract synthesis — Stage 0/1 review report

Base: commit `2036a2a`. Freeze: commit `bc9c85f`. Prior-art kill test,
blind-ordered contract extraction, deterministic verification, hallucination
containment. No paper, no production agent, no change to CSIA production
semantics.

Written for hostile review. Read §31 before any number in §14–§28.

---

## 1. Executive verdict

**`HEURISTICS_SUFFICIENT`. Novelty: NOT ESTABLISHED.**

Two findings, and the second is the one worth keeping.

**The architecture is published.** ISSTA 2025 already does docs → LLM
specification → independent verification → traceable localisation, and
already separates *LLM hallucination* from *implementation bug*. That is
items 25–26 in a paper from last year.

**The bottleneck was misdiagnosed.** The previous package concluded that the
checker's limitation was the hand-written contract. This package tested that
and found the MAVLink schema already carries the sentinel semantics in a
machine-readable attribute:

```xml
<field type="int16_t" name="current_battery" units="cA" invalid="-1">
```

A two-line XML lookup (`B0b`) scores **14/14** on the frozen held-out pilot,
with authoritative citations and a 0.000 unsupported-assertion rate. The AI
reading only implementation source (`B1`) abstains on 8 of 14, and its single
correct positive is an ungrounded recall that the grounding layer refuses —
correctly.

**The clause the schema settles is the clause nobody needed help with. The
clauses that need help — retention, freshness, forbidden merges, the consumer
requiring each — are the ones no authority carries, and this pilot could not
score them because the only available reference for them is model judgement.**

Zero defects were promoted from any held-out contract.

## 2. Exact research question

> Can an AI system synthesize useful, source-grounded evidence-semantic
> contracts from real autonomous-system software and protocol documentation,
> while a deterministic verification layer prevents unsupported AI
> interpretations from becoming safety claims?

Second half: **yes, demonstrably, on fixtures written for it.** First half:
**not on this protocol, because the contracts are already machine-readable.**

## 3. Closest AI/specification-mining prior art

1. **Validating Network Protocol Parsers with Traceable RFC Document
   Interpretation** (ISSTA 2025 / PACMSE) — the whole architecture, including
   the quasi-oracle framing and the hallucination-versus-bug separation.
   69 bugs, 36 confirmed.
2. **SpecSyn** (2026) — LLM specification synthesis with mutation-based
   strength refinement.
3. **Quokka / loop-invariant synthesis with verifier feedback / VeriAct /
   SpecGen** (2025–26) — B3's verifier-feedback loop is the standard one; one
   revision is the conservative end.
4. **SafePilot, RAFT, agentic requirement formalization → UPPAAL** (2026) —
   LLM formalization for cyber-physical systems.
5. **Neuro-symbolic guardrails** (ARc and others) — hallucination containment
   by symbolic checking, named as such.
6. **Daikon** (2001) — non-AI specification mining, the baseline the whole
   field compares against.
7. **PSMBENCH** — a 1,580-page reference set for doc-derived protocol
   specifications, so even "we built a reference set" is done.

## 4. What prior art kills

* AI-generated formal specifications — crowded.
* Verifier-feedback refinement — standard.
* Treating LLM output as a fallible oracle — ISSTA calls it *quasi-oracle*.
* Separating hallucination from implementation bug — ISSTA's core mechanism.
* Containment by symbolic checking — neuro-symbolic guardrails.
* Building a reference set for extracted specifications — PSMBENCH.

Of item 4's ten columns, **two are unoccupied** (C: data/status/provenance
semantics; H: diagnostic consequence), and both are about the domain rather
than the method.

## 5. Exact surviving candidate

> Pointing an established AI-proposes / verifier-disposes architecture at
> **sensor evidence/status semantics in an autonomy ingest path**, and
> measuring whether it beats a mechanical baseline there.

Answered in this package: **it does not**, for a reason that has nothing to
do with prior art. Item 5's kill condition does not fire literally — the
ISSTA work is on network protocols, not CPS — but a domain instantiation of a
published architecture that loses to an attribute lookup is not a
contribution.

## 6. Existing deterministic infrastructure reused

From `research/evidence_semantics` (`2036a2a`), unchanged: the canonical
evidence-state alphabet (`V I N S X R M E`), the contract schema shape, the
bounded trace-equivalence checker, shortest-counterexample search,
first-collapse localisation, downstream consequence tracing, and the
tool-self-audit discipline. Item 12 says not to invent a second ontology and
`schemas/AI_CANDIDATE_CONTRACT.schema.json` reuses the first.

## 7. Development cases

`DEVELOPMENT_CASE_MANIFEST.json`. **18 of 106** fields are contaminated:
`GPS_RAW_INT.fix_type`, `BATTERY_STATUS.current_battery`,
`BATTERY_STATUS.voltages`, `SCALED_IMU.{x,y,z}mag` from previous packages —
and **all 14 `BATTERY_STATUS` fields**, because that message's whole schema
block including every `invalid=` attribute was printed to the terminal while
checking whether MAVLink carries machine-readable sentinels. That
contaminated 14 fields in one action and is recorded, not quietly excluded.

No extraction number is computed on development cases.

## 8. Held-out cases

`BENCHMARK_SPLIT.json` / `HELD_OUT_PILOT.json`. Universe: every field of every
message in the adapter's `HANDLED_TYPES` — **106 fields, 11 messages**, no
judgement in the rule. Held-out: 88.

Pilot: **14 cases across 9 messages**, drawn by SHA-256 under a committed
salt, stratified on consumed/not-consumed (7/7), capped at two per message.
The draw is dominated by IMU axes, which is what an unbiased sample of this
universe looks like. Nothing was chosen for being interesting.

Two stratification errors are known and **left uncorrected** because the split
was frozen before the pilot was drawn: `ESC_TELEMETRY_1_TO_4.voltage` and
`SCALED_IMU2.temperature` are marked consumed by a plain string match that hit
the `BATTERY_STATUS` and `SCALED_PRESSURE` branches respectively.

## 9. Leakage controls

`EVALUATION_VISIBILITY_MANIFEST.json`.

**Enforced mechanically**: candidates hashed in `FREEZE.json` and committed
(`bc9c85f`) before the reference existed; `build_reference.py` refuses to run
unless every hash matches; a test re-runs every citation so a later edit
cannot leave a stale reference.

**Not enforceable, and stated**: the model's MAVLink knowledge from training;
its memory of the previous packages in this same conversation; the fact that
one model produced both predictions and reference.

## 10. Source-audited reference methodology

**Not a gold standard, not ground truth, not human reviewed.**

* **Sentinel clause — MECHANICAL.** Derived from the schema's `invalid=`
  attribute. No model judgement. 15 of 106 fields carry one.
* **Everything else — JUDGEMENT**, read off the committed adapter by the same
  model that produced the candidates, and labelled as such in every entry.

Only the mechanical half is scored. Scoring the judgement half would measure
agreement with itself.

## 11. AI miner architecture

Minimal, per item 50: one extraction prompt, one JSON schema, one
source-grounding validator, the existing deterministic checker, one report
generator. The AI layer is replaceable — the miner's output is a JSON file
that anything could have written.

## 12. Prompt version

`prompts/semantic_contract_miner_v1.md`, hashed in `FREEZE.json`
(`d60b6b46…`), unchanged since. It mandates a citation per clause, permits
abstention, makes `NO_EXPLICIT_SEMANTIC_STATE_FOUND` first-class, forbids
inferring a sentinel from a field name, and states that confidence has no
authority.

## 13. Baselines

* **B0a** regex over consumer source — item 15's design. **3/106** YES.
* **B0b** protocol-schema `invalid=` attribute lookup. **15/106** YES.
* **B1** AI, implementation source only.
* **B2** AI + protocol schema. **Confounded, and reported as confounded**:
  the reference's sentinel answer comes from the same attribute B2 reads, so
  its accuracy is reading comprehension.
* **B3** B1 plus exactly one verifier-feedback revision (item 16). Initial,
  feedback and revision all preserved.

## 14. Semantic-state extraction results

Pilot, 14 cases. `results/AI_VS_HEURISTIC_RESULTS.csv`.

| condition | abstain | TP | FP | TN | FN | cond. accuracy |
|---|---|---|---|---|---|---|
| B0a regex | 0 | 0 | 0 | 12 | **2** | 0.857 |
| **B0b schema** | 0 | **2** | 0 | 12 | 0 | **1.000** |
| B1 AI code-only | **8 (0.571)** | 1 | 0 | 5 | 0 | 1.000 |
| B2 AI + docs | 0 | 2 | 0 | 12 | 0 | 1.000 *(confounded)* |
| B3 AI + feedback | **9 (0.643)** | 0 | 0 | 5 | 0 | 1.000 |

No condition produced a false positive. The universe is 86% negative and the
negative cases were handled correctly everywhere.

## 15. Sentinel / invalidity extraction

The two held-out positives: `GPS_RAW_INT.epv` (`UINT16_MAX`) and
`SCALED_IMU2.temperature` (`0`).

* **B0b** found both, cited to the schema, zero unsupported claims.
* **B0a** found neither — the committed decoder tests neither, so a regex over
  consumer source has nothing to find.
* **B1** produced the correct rule for `epv` **with no citation**, and
  abstained on `temperature`.

## 16. Freshness / retention extraction

**Not scored, and the reason is the result.** The schema carries no attribute
for either, so the only available reference is model judgement, and scoring
the model against its own judgement measures nothing.

B1 did emit retention and provenance clauses that B0 cannot produce at all —
11 clauses across 6 kinds, against B0b's 2 clauses of 1 kind. That is the
surviving qualitative difference and it is unquantified.

## 17. Forbidden-merge extraction

**Zero emitted, zero in the reference.** Neither the schema nor the
implementation states which distinctions must survive downstream; that is a
consumer design decision. Item 41's `WRONG_ALLOWED_MERGE` and
`WRONG_FORBIDDEN_MERGE` were never exercised, and could not be.

This is the clause kind the previous package identified as the real
bottleneck. **The pilot could not reach it.**

## 18. Abstention

Reported jointly with coverage, per reviewer H.

| condition | abstention rate | decided | accuracy on decided |
|---|---|---|---|
| B0a / B0b | 0.000 | 14 | 0.857 / 1.000 |
| B1 | 0.571 | 6 | 1.000 |
| B3 | 0.643 | 5 | 1.000 |

B1's perfect conditional accuracy is bought with 57% abstention. Reviewer H
is right, and the table is laid out so the point cannot be hidden.

## 19. Unsupported-assertion rate

B1: **0.091** (1 of 11 clauses). B3: **0.000**. B0b: **0.000**.

## 20. High-confidence unsupported rate

B1: **0.091** — the single unsupported clause carried confidence 0.85. Every
unsupported assertion the miner made was a confident one. That is the failure
mode item 19 calls the most important, and it is exactly the one observed.

## 21. Exact-contract rate

Not computed as a headline, because only the sentinel clause has a mechanical
reference and a one-clause "contract" is not a contract. Per-clause figures
are in `results/CLAUSE_LEVEL_RESULTS.csv`.

## 22. Unsafe-contract rate

**0 of 14 for every condition.** The five unsafe conditions were frozen in
`METRICS.md` before evaluation; none was triggered. No condition labelled a
sentinel as observed-valid, and no condition missed an explicit invalidity
that the reference records.

## 23. Defect recall

**Zero.** `results/DEFECT_DISCOVERY_RESULTS.csv`: 42 candidate evaluations,
**0 promoted**, 19 `INCONCLUSIVE`, 10 reaching Phase 2. Every cell of the
item-42 defect taxonomy is empty.

`HELD_OUT_AI_DISCOVERED_DEFECT`: **none**. Item 45's strong result did not
occur.

The reason is structural, and it is the sharpest thing the pilot produced:
**`GPS_RAW_INT.epv` — the one correct, source-supported held-out sentinel —
is unreachable, because no committed decoder reads the field.** Correct
extraction is necessary and nowhere near sufficient; the field must also be
read, and the distinction must also matter downstream.

## 24. False defects

**Zero.** Nothing was promoted, so nothing was falsely promoted. This is not
a strength of the method — it is what happens when the gate is set correctly
and nothing gets through it.

## 25. Hallucination containment

**6/6 stopped at Phase 1, none reaching the checker.**
`HALLUCINATION_CONTAINMENT.md`.

| fixture | wrong rule | stopped by |
|---|---|---|
| F1 `valid` means something else | "valid==0 ⇒ discard" | **C6** effect not implemented |
| F2 −1 is a real value | "−1 is the sentinel" | **C2** nothing tests −1 |
| F3 zero is legitimate | "0 means not measured" | **C2** |
| F4 **stale comment** | "quality==255 ⇒ discard" — **the comment says exactly that** | **C2** executable tests `==0`; comment outranked |
| F5 inverted flag | confident answer to an underdetermined bit | **C5** contradictory readers |
| F6 documented, never received | correct rule, unreadable field | **C4** unreachable |

F4 is item 25's dangerous case: the citation is genuine, and only the
precedence hierarchy refuses it.

**The caveat is not optional.** The same author wrote the fixtures, the wrong
contracts and the checks, and iterated the checks until they caught the
fixtures — **two of six passed on the first run**. 6/6 demonstrates that such
checks are writable. It is not an estimate of containment on unseen
hallucinations, and it must never be quoted as one.

## 26. One-revision verifier feedback

`candidates/B3_VERIFIER_FEEDBACK.json`. One revision fired, on
`GPS_RAW_INT.epv`: the verifier reported that no citation resolved, and the
candidate withdrew the clause and abstained.

**Unsupported-assertion rate 0.091 → 0.000. True positives 1 → 0.**

The loop made the miner strictly safer and strictly less useful in the same
step. n=1; that is a demonstration of the mechanism, not a measured trade.

## 27. Heuristic comparison

The comparison the whole package turns on.

| | B0b schema lookup | B1 AI code-only |
|---|---|---|
| positives found (pilot) | **2/2** | 1/2, ungrounded |
| conditional accuracy | 1.000 | 1.000 |
| abstention | 0.000 | 0.571 |
| unsupported assertions | **0.000** | 0.091 |
| citations | authoritative, tier 1 | tier 3, or none |
| clause kinds produced | 1 | **6** |
| implementation | ~20 lines of XML parsing | a language model |

The AI is beaten on the clause the schema settles, and is the only source for
five clause kinds the schema is silent about — none of which could be scored.

## 28. Repeatability

**NOT RUN**, and reported as not run. Three attempts by one model in one
conversation are not independent: the second is conditioned on the first,
which is already in its context. Reporting their agreement would be item 39's
warning arriving one step early.

## 29. Held-out discoveries

None. §23. The one correct held-out contract yielded `INCONCLUSIVE` because
the field is never read.

## 30. Cross-project feasibility

Both trees are already present: `/home/user/ardupilot/ardupilot` and
`/home/user/px4` (with `msg/` uORB definitions). Item 36's unseen-project
test needs no download.

**PX4 uORB is the experiment that matters**, because a `.msg` file has no
`invalid=` attribute. That removes C3 — Phase 1's only refuting check — and
removes B0b, the baseline that wins here. It is the one condition under which
this architecture could matter, and this package did not run it.

Expectation recorded in advance, so it can be scored later: B1 will abstain
on most uORB fields, and its few positives will be recalled rather than
derived.

## 31. Reference-bias limitation

**Read this before §14–§28.**

One model, in one conversation, produced: the candidate contracts, the
reference, the metrics, the checks, the fixtures, and this report. The
ordering is enforced by hashes and a refusing build script. The independence
is not enforced and cannot be.

What this means concretely:

* No number here is a capability estimate for any model.
* `SOURCE_AUDITED_REFERENCE/` is not ground truth. Its sentinel half is
  mechanical and trustworthy; its judgement half is not independent and is
  not scored.
* The containment figure is fitted.
* The conclusion that **B0b beats B1** is the *most* robust claim in the
  package, because B0b's reference is the same attribute B0b reads — the
  comparison does not depend on any judgement of mine.

The verdict rests on the parts that do not depend on my judgement: the schema
attribute exists, the mechanical baseline scores 14/14, and prior art already
publishes the architecture.

## 32. Formal interpretation, C* vs Ĉ

`C*` the source-supported contract, `Ĉ` the candidate, `T` the
implementation. Two independent propositions:

* **P1** — `Ĉ` is supported by source evidence as an extraction of `C*`
* **P2** — `T` violates `Ĉ`

A finding needs P1 established and P2 violated. Implemented as Phase 1
(`SOURCE_SUPPORTED` or nothing proceeds) and Phase 2, with `promote()`
structurally unable to reach Phase 2 from any other Phase-1 state.

**Item 47 asks whether this can be expressed as contract-synthesis soundness
versus implementation-conformance soundness. It can, and it should not be
given a name here.** It is the standard distinction between an incorrect
specification and an incorrect implementation, which predates all of this.
Item 48's principle — no AI-generated safety contract may be promoted solely
because a checker finds a counterexample to it — is likewise obvious, likely
established, claimed by nobody here, and **enforced in the code**.

## 33. Negative results

1. AI does not beat a schema attribute lookup on the sentinel clause.
2. Zero held-out defects discovered.
3. The verifier loop removed the one true positive.
4. Every unsupported assertion the miner made was high-confidence.
5. Forbidden-merge extraction — the actual bottleneck — could not be scored
   at all.
6. Repeatability could not be measured.
7. The naive regex baseline the brief specified is weak (3/106), but the
   right baseline is not a regex.

## 34. Unexpected results

1. **The MAVLink schema carries `invalid=`.** This was not anticipated by the
   brief, and it reframes the whole question: the specification bottleneck
   for this protocol was already solved by the protocol.
2. **The unreachability of the one correct held-out sentinel.** Extraction
   accuracy is not the binding constraint on defect discovery; reachability
   is.
3. **The containment checks were fooled twice by their own fixtures** — a
   constant definition read as a test, and `0` inside `0.25` read as a
   comparison.
4. **B2 is unscoreable by construction**, because the schema attribute is
   both the input and the reference. Noticed while designing, not after.

## 35. Hostile review

**A — "LLMs generating formal specifications is a crowded field."**
Conceded entirely. §3, §4. The architecture is subsumed, including the
hallucination-versus-bug separation.

**B — "Your AI just finds `== -1` and calls it a sentinel."**
Worse than that: it did not even find `== -1` from the code, because the
committed decoder does not test the held-out fields. B0a found 3 of 106. And
the AI lost to a baseline that does not read code at all.

**C — "The verifier validates the implementation against a hallucinated
contract."** The most serious objection, and the one taken most seriously.
Two-phase promotion, five Phase-1 checks beyond grounding, and F4
demonstrates the dangerous case being caught by precedence rather than by
grounding. But: containment is fitted to self-authored fixtures, and the only
*refuting* check exists solely because this protocol ships a machine-readable
attribute. On a protocol without one the objection stands substantially
un-answered.

**D — "Claude wrote both prediction and ground truth."**
Conceded. §31. The reference is deliberately not called ground truth. The
sentinel half is mechanical; the judgement half is not scored. Independent
annotation is specified in `FUTURE_HUMAN_ANNOTATION_PROTOCOL.md` and was not
run because no reviewers exist.

**E — "Your benchmark contains cases used to design the method."**
18 of 106 declared contaminated, including all 14 `BATTERY_STATUS` fields
because one terminal print contaminated the whole message. No number is
computed on them.

**F — "The AI never discovered anything a human had not already found."**
Correct. Zero held-out discoveries. §23.

**G — "The formal checker does all the real work; the AI is unnecessary."**
On the sentinel clause, conceded — and not even the checker is needed there,
an XML lookup suffices. The AI produced 11 clauses across 6 kinds against
B0b's 2 clauses of 1 kind, but five of those kinds could not be scored, so
the defence is unevidenced.

**H — "High precision comes only because it abstains constantly."**
Correct: 1.000 conditional accuracy at 0.571 abstention, and 0.643 after
feedback. §18 reports them jointly and never separately.

**I — "One model, one repository."**
Conceded. §30 shows the cross-project test is feasible and untried, and names
the expectation in advance.

**J — "You added AI because the previous novelty directions failed."**
Chronology conceded without qualification. AI was applied to a bottleneck the
previous package identified empirically. The scientific question was whether
it moves that bottleneck. It does not, and the reason — the bottleneck was
partly illusory and the rest is unscoreable — is more useful than a positive
result would have been.

## 36. Claim ledger

`CLAIM_LEDGER.json`, 17 claims: 1 `KNOWN/SUBSUMED`, 9 `EMPIRICAL ONLY`,
3 `PROVED — NOVELTY NOT ESTABLISHED`, 2 `PROVISIONAL`, 2 `REFUTED`,
**0 `PROVED — POSSIBLE NOVEL CONTRIBUTION`**. Three refuted predictions kept
on the record.

## 37. Strongest allowed wording

> On one autonomy ingest path and one protocol, a mechanical lookup of the
> protocol schema's own `invalid=` attribute matched or beat every AI
> extraction condition on sentinel semantics, with authoritative citations
> and no unsupported assertions. A two-phase gate — contract evidence, then
> implementation conformance — stopped all six deliberately wrong contracts
> at phase one, on fixtures the same author wrote. No held-out contract
> produced an implementation defect.

## 38. Strongest forbidden wording

* "novel", "first", "unprecedented", "new framework", "new theorem" —
  forbidden by item 2 and unsupported by §3.
* "AI-assisted contract synthesis works / does not work." One pilot, 14
  cases, one protocol, one model, self-authored reference.
* "Containment rate 100%." Fitted to six self-authored fixtures, two of which
  passed the first run.
* "Held-out evaluation", "blind evaluation", "ground truth", "gold standard".
* "The AI found nothing" — it produced the correct rule for `GPS_RAW_INT.epv`
  and could not ground it.
* "Verified." Nothing here is verified. Phase 2 is bounded exhaustive testing.
* Any claim about engineer time saved. Item 34: machine time is not human
  productivity, and no engineer time was measured.

## 39. What a peer-reviewed confirmatory study would require

1. **Independent annotators** — two per interface, blinded, third
   adjudicating, κ per label kind with the positive class reported
   separately.
2. **A protocol with no machine-readable sentinel vocabulary** — PX4 uORB, or
   a proprietary bus — where B0b does not exist and C3 is unavailable.
3. **Enough positives.** 15 in 106 will not support a stable per-clause-kind
   estimate. Several protocols, positives in the low hundreds.
4. **Genuinely independent extraction runs** — separate sessions, recorded
   model identifier and sampling settings.
5. **Adversarial hallucinations authored by someone else**, including
   contracts built to satisfy C2–C6 while still being false.
6. **Reachability-stratified sampling.** Half this pilot's cases could not
   yield a finding whatever the miner said.
7. **A comparison against a competent engineer with the schema open**, not
   against a regex. That is the baseline that matters and nobody has run it.
8. **Focus on the four unscoreable clause kinds** — retention, freshness,
   forbidden merges, consumer. They are where the bottleneck actually is.

## 40. Item 44's eight success conditions, assessed

| # | condition | met? |
|---|---|---|
| 1 | AI extracts a substantial fraction of source-supported contracts | **NO** — 57% abstention, 1 of 2 positives, ungrounded |
| 2 | beats the simple heuristic on nontrivial clauses | **NO** — loses to B0b; beats B0a only by abstaining |
| 3 | documentation measurably changes extraction | **CONFOUNDED** — B2 reads the reference's own source |
| 4 | the deterministic layer prevents unsupported claims being promoted | **YES** — 1/1 unsupported clause refused; 6/6 fixtures stopped |
| 5 | finds real implementation violations from held-out contracts | **NO** — zero |
| 6 | false contracts are detected rather than silently converted to bugs | **YES**, with the fitting caveat |
| 7 | at least some held-out cases succeed | **PARTIAL** — correct extraction on `epv`, unreachable |
| 8 | prior art does not subsume the architecture | **NO** — ISSTA 2025 |

**Three of eight fail outright, one is confounded, one is partial.** Item 44
requires all eight. The verdict follows.

## Final recommendation

**Stop treating this as a dissertation direction. Two things are worth doing
and neither is research.**

1. **Use the schema.** `docs/simulation/CHANNEL_SEMANTICS.yaml` states each
   channel's `missing_semantics` in prose. MAVLink already states the same
   thing in a machine-readable attribute. Generating the sentinel half of
   every channel contract from `invalid=`, and diffing it against the prose,
   is an afternoon's work with an authoritative citation on every row and no
   model in the loop. That is the actual deliverable of this package.

2. **Keep the two-phase gate, drop the miner.** The Phase-1 checks are worth
   having wherever *any* contract comes from — a colleague, a vendor
   datasheet, a model. Their value is refusing an unsupported premise, not
   producing one.

**And if the direction is revisited, run it on PX4 uORB**, where no
machine-readable authority exists. That is the only setting where the
question is still open, and this package deliberately did not run it.

---

### Artifact index

| item | artifact |
|---|---|
| research question | `RESEARCH_QUESTION.md` |
| prior art | `PRIOR_ART_MATRIX.md` |
| metric definitions (frozen) | `METRICS.md` |
| case universe / split | `BENCHMARK_SPLIT.json` |
| held-out pilot | `HELD_OUT_PILOT.json` |
| contamination | `DEVELOPMENT_CASE_MANIFEST.json` |
| visibility + leakage | `EVALUATION_VISIBILITY_MANIFEST.json` |
| freeze / amendments | `FREEZE.json`, `FREEZE_AMENDMENTS.json` |
| prompt | `prompts/semantic_contract_miner_v1.md` |
| candidate schema | `schemas/AI_CANDIDATE_CONTRACT.schema.json` |
| candidates | `candidates/B1_*.json`, `B2_*.json`, `B3_*.json`, `NONSCORED_*.json` |
| reference | `SOURCE_AUDITED_REFERENCE/REFERENCE.json` |
| grounding model | `SOURCE_GROUNDING_MODEL.md` |
| taxonomies | `ERROR_TAXONOMY.md` |
| containment | `HALLUCINATION_CONTAINMENT.md`, `results/HALLUCINATION_CONTAINMENT.json` |
| results | `results/AI_VS_HEURISTIC_RESULTS.csv`, `CONTRACT_EXTRACTION_RESULTS.csv`, `CLAUSE_LEVEL_RESULTS.csv`, `ABSTENTION_RESULTS.csv`, `DEFECT_DISCOVERY_RESULTS.csv`, `REPEATABILITY_RESULTS.csv`, `B0_HEURISTIC_RESULTS.json`, `GROUNDING_RESULTS.json` |
| future work | `FUTURE_HUMAN_ANNOTATION_PROTOCOL.md`, `CROSS_PROJECT_CONFIRMATORY_PLAN.md` |
| ledger | `CLAIM_LEDGER.json` |
