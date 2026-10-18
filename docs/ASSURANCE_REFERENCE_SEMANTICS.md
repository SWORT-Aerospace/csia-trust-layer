# Assurance reference semantics

**Status: EXPERIMENTAL.** Not reviewed outside this repository, not part of the
frozen CSIA scientific core, and not production semantics. §9 is the gate that
would have to be passed before any of that changed.

**Purpose of this document.** It defines the support semantics precisely enough
that **another implementation can be built from it without reading the CSIA
production code**. If a second implementer needs to look at `csia/diagnosis/`
to resolve an ambiguity here, this document has failed and the ambiguity is a
defect in it.

---

## 1. The objects

| term | definition |
|---|---|
| **hypothesis** | a candidate explanation. The admitted set `H` is declared by the configuration; it is not discovered and not extended at runtime |
| **evidence term** | a comparison whose outcome is observable. The set `E` is declared by the configuration |
| **signature** `LOW(h)` | for hypothesis `h`, the subset of `E` the model expects to read LOW under `h`. A declared property of the model, not a measurement |
| **gate weight** `w(e)` | a number in `[0, 1]` |
| **evidence state** `s(e)` | exactly one of `ACTIVE`, `INACTIVE`, `INAPPLICABLE`, `STALE`, `ABSENT` |
| **leader** `h*` | the hypothesis the scoring layer ranked first. An **input** here, never recomputed |

## 2. Activity

> `e` is **active** iff `s(e) = ACTIVE` **and** `w(e) > 0`.

Both conjuncts are load-bearing and each has a test.

* **State alone is not enough.** A term marked `ACTIVE` with weight `0` carries
  nothing.
* **Weight alone is not enough.** A term at weight `1.0` whose state is `STALE`
  or `INAPPLICABLE` is **not active**. Treating weight as sufficient is the
  precise defect this whole programme exists about, and it is why the state is
  a separate field rather than folded into the weight.

**`w(e) > 0` is a strict comparison with no tolerance.** A tolerance here would
be a threshold, and a threshold is the thing this layer exists not to have.
Values that cannot be *interpreted* are rejected earlier, by §5 — that is a
validity rule, not a threshold.

## 3. Discrimination

> `D(a, b) = ( LOW(a) △ LOW(b) ) ∩ ACTIVE`

where `△` is symmetric difference. **This one line is the whole semantics.**
Everything else in this document is bookkeeping over it.

`a` and `b` are **distinguishable now** iff `D(a, b) ≠ ∅`.

**Consequences, each verified in the bounded domain (§8):**

* **symmetric** — `D(a,b) = D(b,a)`, because `△` is;
* **independent of ranking and of priors** — neither appears in the formula, so
  no assignment of them can change it;
* **unchanged by irrelevant evidence** — a term with `e ∉ LOW(a) △ LOW(b)`
  contributes nothing to that pair whatever its state;
* **monotone in activation, per pair** — activating further terms cannot empty
  a non-empty `D(a,b)`.

## 4. Support

> `SUPPORTED_UNIQUE(h*)` iff `|H| ≥ 2` and `D(h*, h) ≠ ∅` for **every**
> `h ∈ H \ {h*}`.

The five outputs, and they are not orderable by preference:

| verdict | condition |
|---|---|
| `SUPPORTED_UNIQUE` | every competitor has a non-empty `D` |
| `AMBIGUOUS` | some competitors have an empty `D`, some do not |
| `NON_IDENTIFIABLE` | every competitor has an empty `D` |
| `NOT_EVALUABLE` | the question cannot be asked — §5, or `|H| < 2` |
| `UNKNOWN` | no leader was asserted |

**`|H| < 2` is `NOT_EVALUABLE`, never `SUPPORTED_UNIQUE`.** A one-hypothesis
model trivially "identifies" its only member; reporting that as supported is
how a degenerate configuration reads as a healthy one.

**A large score does not force support.** The score is a ranking over a model;
support is a statement about the evidence held. The canonical case:

```
scoring layer:  leader = nominal, weight = 0.9999
firewall:       D(nominal, gps_fault) = ∅   ->  AMBIGUOUS
```

That is a legal, expected, and correct pair of outputs.

## 5. Validity, and failing closed

Before anything in §2–4 is computed, the input must be interpretable. Each
condition below yields `NOT_EVALUABLE` **with that reason**, and never any
other verdict:

`UNSUPPORTED_SCHEMA_VERSION`, `MISSING_CANONICAL_SAMPLE`,
`UNKNOWN_CONFIGURATION`, `CONFIG_HASH_MISMATCH`, `STALE_SUPPORT_CERTIFICATE`,
`HYPOTHESIS_SET_CHANGED`, `EVIDENCE_TOPOLOGY_CHANGED`, `TIMESTAMP_REGRESSION`,
`UNKNOWN_EVIDENCE_STATE`, `INVALID_GATE_STATE`, `FIREWALL_INTERNAL_EXCEPTION`.

**`INVALID_GATE_STATE` covers, and the last one was found by fuzzing:**
a non-numeric weight; a boolean; a weight outside `[0, 1]`; `NaN` (which fails
every comparison, so only `not (0 ≤ w ≤ 1)` catches it); and **any subnormal
weight**. A subnormal cannot arise from any computation this pipeline performs
— it is a symptom of numerical corruption, and `5e-324` licensing a unique
attribution is exactly what the campaign found. `-0.0` is **valid** and means
inactive: it is perfectly interpretable.

**Two shapes are forbidden outright**, each with its own test:

```
exception  ->  the leader's hypothesis          NEVER
exception  ->  the previous certificate stands   NEVER
```

## 6. Witnesses and certificates

A **witness** records one separation: target, competitor, the active
discriminators, their sources, applicability, freshness, timestamp.

A **certificate** carries enough witnesses to separate the target from every
competitor, plus the configuration hash, software hash, evidence hash,
semantics version, hypothesis set and evidence topology.

**It is an `EXPERIMENTAL_SUPPORT_CERTIFICATE`** and a test asserts the word
survives into the emitted record.

**A certificate is emitted on refusal too**, with `complete = false`. Emitting
only on success would leave the durable record covering just the decisions that
went well.

**Staleness** is decided against a later record, not asserted by the
certificate: semantics version changed, config hash changed, software hash
changed, hypothesis set changed, evidence topology changed, timestamp
regressed, or past `valid_until`.

## 7. Test vectors

`csia_assurance/vectors/*.json` — each carries an input record, the expected
verdict and the expected witnesses. **They are the conformance suite for a
second implementation**: an implementation built from this document alone
should pass them without modification.

## 8. What has been verified, and in what domain

`research/physical_validation/results/ASSURANCE_BOUNDED_VERIFICATION.json`,
z3, `|H| ≤ 4` and `|E| ≤ 6`, binary signatures and binary activity.

| property | result |
|---|---|
| P3 symmetry | no counterexample in the bounded domain |
| P4 irrelevant-evidence independence | no counterexample in the bounded domain |
| P5 addition monotonicity, pair-specific | no counterexample in the bounded domain |
| P6 support-witness requirement | no counterexample in the bounded domain |
| P8 expiry | no counterexample in the bounded domain |
| P7 configuration invalidation | **hazard instance found (expected)**, then run through the real firewall: `SUPPORTED_UNIQUE → NON_IDENTIFIABLE`, certificate refused. **HOLDS** |
| P1 ranking independence | **not a solver question** — see below |
| P2 prior independence | **not a solver question** — see below |

**`unsat` licenses exactly one sentence:** *No counterexample exists within the
verified bounded domain.* It is **not** a theorem, and no row may be quoted as
one.

**P1 and P2 are deliberately not encoded.** Neither a ranking value nor a prior
appears in `D(a,b)`, so asking the solver about an absent variable would return
a vacuous `unsat` that *reads as evidence*. They are carried instead by the
cross-check, which varies the real fields through the real implementation:
4096 concrete cases, 0 semantic mismatches, 0 ranking-or-prior sensitivities.

## 9. The gate before any of this becomes production semantics

The firewall stays an experimental wrapper until **all** of:

1. property and metamorphic tests pass;
2. bounded formal checks complete with every counterexample archived;
3. the hostile-input campaign is clean or its exceptions are accepted in
   writing;
4. decision replay passes;
5. E2 passes;
6. E3 and E4 pass;
7. **independent review approves integration** — by someone who did not build
   it.

Items 5–7 are not satisfied and cannot be satisfied by this repository alone.
**Do not silently make this production semantics.**
