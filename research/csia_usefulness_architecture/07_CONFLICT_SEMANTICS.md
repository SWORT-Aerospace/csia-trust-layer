# Conflict, not just fusion; and the verdict repair (Phases 10, 30)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

## 1. Phase 10: prior art first

| source | what it says about disagreement |
|---|---|
| Dempster-Shafer and Zadeh's criticism (S062) | normalising conflict away produces confident minority conclusions. Measure disagreement before combining |
| cautious combination (S060) | non-distinct sources should not reinforce each other |
| avionics redundancy management (S066) | miscompare between redundant channels is detected and managed, not averaged |
| consistency-based diagnosis and ATMS (S061) | **"conflict" is a technical term there**: a set of components that cannot all be healthy. CSIA's elimination already computes that implicitly (S032) |
| CSIA v2 (S002) | when a hypothesis is both confirmed and refuted, refutation wins and nothing is reported (AF-05) |

**Terminology decision.** The new outward state is named
**`EVIDENCE_DISAGREEMENT`**, not `EVIDENCE_CONFLICT`. "Conflict" already
means something specific in model-based diagnosis, which is the literature
CSIA's set elimination belongs to. Reusing the word for a different object
would invite exactly the confusion the novelty audits warned about.

## 2. What counts as a disagreement

A disagreement is **opened** when either of these holds.

- **D1: confirm-and-refute collision.** An admissible predicate confirms a
  hypothesis H while another admissible, independent predicate refutes H.
  The predicate values are already computed inside localization (S002, the
  `values` map), so detection is free.
- **D2: same-relation opposition.** Two admissible records from different
  producers, about the same component and relation, carry opposite verdicts
  (NOMINAL against DEGRADED or VIOLATED).

Neither is averaged.

## 3. The disagreement record

Each record carries the following fields.

**Identity**

- `disagreement_id`: a deterministic hash of the participants.
- `kind`: `D1` or `D2`.

**What it is about**

- `participants`: the evidence ids and their producers.
- `subject`: the component, relation or hypothesis.

**Where the participants differ**

- `states`: each participant's verdict.
- `shared_tags`: the dependency tags the participants have in common.
- `contracts`: each participant's contract id and validation status.
- `context_epochs`: each participant's context epoch.
- `windows`: each participant's acquisition window.

**Explanations**

`explanations` is a list chosen by the deterministic rules in §4, never by a
score.

**Effect**

`effect` states what was retained. For example: "H kept unresolved rather
than eliminated".

## 4. Why they disagree: rule-based explanations

| explanation | rule that selects it | what a consumer should do |
|---|---|---|
| `DIFFERENT_VALIDITY_REGION` | the participants' contracts have different `requires` regimes, and the current context satisfies them differently | trust the one whose regime holds; the other should have been NOT_APPLICABLE, so this is a contract bug |
| `DIFFERENT_TIMESCALE` | the acquisition windows do not overlap, or one class is `TRANSIENT_WITNESS` and the other `ACCUMULATED_STATISTIC` | both can be right: the transient saw onset, the accumulation saw steady state (the XSYS-001 shape) |
| `COMMON_SOURCE` | the participants share a `src:` or `est:` tag | cannot be two opinions; suspect the shared source |
| `STALE_PARTICIPANT` | one participant is near its maximum age | refresh |
| `CONFIGURATION_MISMATCH` | the participants' context epochs differ on a dimension one of them names | recompute |
| `MODEL_MISMATCH` | the participants share a `model:` tag and disagree with a third, independent participant | suspect the model |
| `UNEXPLAINED` | none of the above | legitimate uncertainty: report and keep both hypotheses open |

## 5. What a disagreement does to reasoning

**The conservative rule.** A D1 collision **keeps H unresolved** rather than
eliminating it. Today refutation wins silently, so this is a **behaviour
change**. It widens candidate sets in exactly the cases where the evidence
disagrees, which is the safe direction for diagnosis.

**Rollout.** Because it changes decisions, it enters in shadow mode first
(`13_MIGRATION_AND_VALIDATION.md`, M6). It becomes the default only if the
replay shows no loss of correct UNIQUE and SUPPORTED results that were
backed by admissible, independent evidence.

**Exception.** If the refuting predicate is **not independent** of H's
suspect scope (`05_PROVENANCE_AND_DEPENDENCE.md` §3.2, rule 3), it is not a
refuter at all. That case is not a disagreement.

## 6. Phase 30: separating the states that matter

Earlier audits found UNSUPPORTED overloaded (S031, S032), and this review
confirmed it by probe (S044c). The states below are distinguished only where
the **operational response differs**.

| state | meaning | operational response | replaces |
|---|---|---|---|
| `SUPPORTED` | one hypothesis survives and is affirmatively confirmed by admissible, independent evidence | act on the named cause | localization SUPPORTED (kept) |
| `AMBIGUOUS` | two or more survive; ambiguity preserved | seek discriminating evidence (information need) | localization AMBIGUOUS (kept) |
| `INSUFFICIENT_EVIDENCE` | survivors exist, but the admissible evidence cannot confirm any, including the single-unconfirmed-survivor case | collect evidence; do not name a cause | UNSUPPORTED sense (ii) |
| `NO_CONSISTENT_HYPOTHESIS` | every declared hypothesis was refuted by admissible, independent evidence | **the model is incomplete** or a refuter is wrong; escalate to engineering; do not reinstate a hypothesis | UNSUPPORTED sense (i); the "no consistent diagnosis" of consistency-based diagnosis (S032) |
| `EVIDENCE_DISAGREEMENT` | a D1 collision affects the result | inspect the participants and explanations; keep the candidates open | new |
| `NO_EVIDENCE` | the symptom is not present | nothing | localization NO_EVIDENCE (kept) |

**Invalid evidence is not a hypothesis-level state.** It is per record
(admissibility, `03_EVIDENCE_ADMISSIBILITY.md` §2.2). It appears in the result
as:

- an `inadmissible` summary;
- the information need;

never as a verdict.

**The attribution module's UNSUPPORTED** (sense iii: "implicated by a
relation without adverse evidence") becomes the list
`implicated_without_evidence` in the output. It is detail, not a verdict.

## 7. Migration of existing v2 outputs

| v2 today | new state | rule |
|---|---|---|
| SUPPORTED | SUPPORTED | unchanged when all contributing evidence is admissible and independent; otherwise re-evaluated |
| AMBIGUOUS | AMBIGUOUS or EVIDENCE_DISAGREEMENT | EVIDENCE_DISAGREEMENT when a D1 collision was involved |
| UNSUPPORTED (no survivors) | NO_CONSISTENT_HYPOTHESIS | |
| UNSUPPORTED (one unconfirmed survivor) | INSUFFICIENT_EVIDENCE | |
| NO_EVIDENCE | NO_EVIDENCE | |
| attribution UNIQUE | only if localization is SUPPORTED **or** the discriminators are declared relevant to a competing hypothesis (`12_TARGET_ARCHITECTURE.md` §6) | fixes FM-20 |
| attribution UNSUPPORTED | `implicated_without_evidence` list | |

**Compatibility.** A `2.0.0` compatibility view maps the new states back:

- INSUFFICIENT_EVIDENCE and NO_CONSISTENT_HYPOTHESIS both map to UNSUPPORTED;
- EVIDENCE_DISAGREEMENT maps to AMBIGUOUS.

A v2 `2.0.0` consumer therefore keeps working unchanged, with information
lost, exactly as today. The new states appear in schema `2.1.0`, which is
additive (`09_DOWNSTREAM_AND_PRODUCT.md` §2).

## 8. Is conflict operationally useful?

Yes, in two concrete ways. It is not useful as a number.

1. **It changes what the operator checks.**
   - `COMMON_SOURCE`: check the shared sensor.
   - `DIFFERENT_TIMESCALE`: check nothing; both are right.
   - `CONFIGURATION_MISMATCH`: re-run under the current configuration.
2. **It stops a silent elimination.** In the one case where silence is most
   dangerous, independent admissible evidence for and against the same
   hypothesis, it keeps the hypothesis open.
