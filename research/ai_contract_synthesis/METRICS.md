# Metric definitions — FROZEN before any reference was built

Item 17 forbids collapsing everything into one accuracy number, and item 31
requires the metrics to exist before held-out answers are revealed. This file
is hashed in `FREEZE.json` and committed before `build_reference.py` is run
for the first time.

## Unit of scoring

A **case** is one `MESSAGE.field`. A **clause** is one semantic claim about
that case. Cases and clauses are scored separately, because a candidate can
be right about the sentinel and wrong about retention.

## Extraction metrics (item 17), computed per clause kind

For each of `SENTINEL_CONDITION`, `INVALID_CONDITION`, `RETENTION`,
`FRESHNESS`, `ALLOWED_MERGE`, `FORBIDDEN_MERGE`:

* **precision** = correct clauses of that kind / clauses of that kind emitted
* **recall** = correct clauses of that kind / clauses of that kind in the
  source-audited reference

A clause is **correct** iff its `raw_condition` normalises to the reference's
raw condition AND its `state` (where it names one) matches.
Normalisation: strip whitespace, `==`, brackets; upper-case; map the literal
forms of the same constant onto each other (`65535` ≡ `UINT16_MAX`,
`32767` ≡ `INT16_MAX`, `255` ≡ `UINT8_MAX`, `4294967295` ≡ `UINT32_MAX`).

## Primary decision metric

`explicit_semantic_state_found` ∈ {`YES`, `NO_EXPLICIT_SEMANTIC_STATE_FOUND`,
`UNKNOWN`} against the reference's `has_explicit_state` ∈ {true, false}.
`UNKNOWN` counts as an abstention, never as a `YES` and never as a `NO`.

Reported as a 2×2 over the non-abstained cases plus a separate abstention
count. **Negative cases are the majority of the universe** and a method that
says `YES` everywhere must score badly here; that is the point of item 9.

## Abstention (item 18)

* **abstention rate** = abstained cases / cases
* **conditional accuracy** = correct decisions / non-abstained cases
* **correct-abstention rate** = abstentions on cases the visible evidence
  genuinely cannot settle / abstentions

Precision and coverage are reported **jointly** and never separately, so that
"high precision because it abstains constantly" (reviewer H) is visible.

## Unsupported assertions (item 19) — the most important failure metric

* **UNSUPPORTED_ASSERTION_RATE** = clauses whose citations do not resolve, or
  which cite nothing / total clauses emitted
* **HIGH_CONFIDENCE_UNSUPPORTED_RATE** = of those, the fraction with
  `confidence >= 0.8`

Resolution is decided by `verification/grounding.py`, which checks that the
quoted text is present at the cited locator. It is a text check, not a
meaning check, and is not evidence that a grounded clause is true.

## Contract-level metrics (item 20)

* **exact-contract rate**: every clause the reference lists is present and
  correct, and no extra clause is emitted
* **partially-correct rate**: some clauses correct, none unsafe
* **unsafe-contract rate**: at least one clause meets an UNSAFE condition

**UNSAFE is defined here, before evaluation**, per item 20. A contract is
unsafe if it does any of:

1. labels a value the reference marks as sentinel/invalid as `V` (observed-valid);
2. removes or contradicts a forbidden merge the reference requires;
3. asserts operational usability for a state the reference marks unusable;
4. fails to represent an explicit invalidity the reference records
   (`has_explicit_state` true, candidate says `NO_EXPLICIT_SEMANTIC_STATE_FOUND`);
5. asserts a provenance (`REAL`) for a value the reference marks retained,
   imputed or estimator-derived.

Abstention is **never** unsafe. Item 18: a method that declines is preferable
to one that guesses.

## Defect discovery (item 21)

* **real defect recall** = reference-confirmed defects found from candidate
  contracts / reference-confirmed defects
* **false defect count** = promoted findings the reference does not support
* **missed defect count**
* **invalid counterexample count** = counterexamples that fail re-execution

Every defect must survive re-execution through the deterministic checker from
`research/evidence_semantics` (item 22). An explanation is not a finding.

## Containment (item 24)

* **containment rate** = wrong rules that do NOT reach
  `CHECKER_CONFIRMED_IMPLEMENTATION_VIOLATION` / wrong rules injected

Measured on NON-SCORED fixtures only. It contributes to no extraction metric.

## Repeatability (item 38)

Clause-level agreement across independent extraction attempts, where
independent attempts are possible. **Item 39: agreement is stability, not
truth.** Agreement is never used to promote a clause.

## What is NOT computed

No single headline accuracy number. No F1 over mixed clause kinds. No metric
in which a confident wrong answer scores the same as an abstention.
