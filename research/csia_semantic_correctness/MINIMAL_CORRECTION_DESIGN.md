# Minimal correction design (Parts 19 and 21)

CSIA semantic correctness audit, 2026-09-29.

**Design only.** No production CSIA code is changed.

- **What the effect figures are.** Each is a measurement of the **shadow
  successor** in `semantic_probe.py`, run against frozen v2.
- **How to read them.** The shadow is a measuring instrument. With every fix
  switched off it reproduces frozen v2 on all 2,640 shipped ticks
  (SH.IDENTITY_CHECK: 0 mismatches). Every difference reported below is
  therefore the effect of the fix named.

## 1. Constraints

1. **Frozen v2 is not edited.** The correction is a **post-freeze successor**,
   schema 2.1.0, with a **2.0.0 compatibility view** that reproduces today's
   documents byte for byte. The architecture package's migration step M1
   described the same pattern.
2. **It fixes confirmed defects only.** No relevance system, no correlation
   model, no admissibility engine.
3. **It reuses what exists:**
   - the dependency graph and the relation table that `attribute()` already
     walks;
   - the `affected_functions` declarations the function graph already reads;
   - the assurance firewall's rule, "an active witness against every
     competitor" (`csia_assurance/firewall.py`);
   - Kleene's strong logic (L05).
4. **No fix raises certainty except to undo a wrong refutation.** Measured
   over the 2,640 shipped ticks and the 4,368 N3 and N4 configurations:
   - **UNIQUE.** The fixes create **no** UNIQUE that frozen v2 did not give.
   - **SUPPORTED.** They create exactly **one** SUPPORTED frozen v2 did not
     give: an N4 configuration with the R8B pattern. There, the true cause
     is restored after frozen v2 had rejected it on an UNAVAILABLE record.
   - **Everything else.** Every other decision change lowers certainty.
5. **XSYS-001 is unchanged.** Every fix is classified NO EFFECT or CHANGES
   INTERNAL TRACE ONLY (`XSYS_001_COMPATIBILITY.md`).

## 2. The corrections

### C1: relevance-gated discriminator (fixes SC-01; resolves SC-19)

The successor keeps every frozen condition for UNIQUE and adds one.

**UNIQUE**, for the single adverse attributable component *c*, requires all
of the following:

- *c* has at least one **declared alternative**. Declared alternatives are:
  - every node *c* transitively depends on, via `dependencies`, the walk
    `attribute()` already does for common causes;
  - every component implicated by a `CrossDomainRelation` whose `domains`
    include *c*'s domain.
- **Every** declared alternative is **affirmatively NOMINAL**. That means at
  least one NOMINAL attributable record, and no UNAVAILABLE or adverse record,
  for that component.
- At least one of those relevant discriminators comes from a domain other than
  *c*'s. This keeps the frozen cross-domain rule unchanged.

Otherwise the verdict is AMBIGUOUS, with a reason code:

- `NO_DECLARED_ALTERNATIVE_WAS_EXCLUDED`;
- `DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL`, listing the alternatives
  not excluded;
- `NO_RELEVANT_DISCRIMINATOR_FROM_ANOTHER_DOMAIN`.

**Trace.** `discriminators` splits into `relevant_discriminators`, which did
the excluding, and `other_nominal`, which did not.

**Effect.**

| where | result |
|---|---|
| shipped ticks | **0 / 2,640 changed**. Every shipped UNIQUE already satisfies the stricter rule |
| minimal reproductions | R1B, R2, R3, R7C, R8G and R16B give AMBIGUOUS; R4 (control) stays UNIQUE |
| N2 | UNIQUE falls from 21 configurations to 4, all of the form "A adverse, its declared alternative B NOMINAL" |
| P6 corpus | "UNIQUE despite an unknown alternative" falls from 185 to 0 |
| producer unavailable | MS_B2 with the POWER plugin down gives AMBIGUOUS instead of UNIQUE motor_0 |

**Governance choice inside C1.** A component with **no** declared
alternative, such as a root node with no dependencies and no relation, is
AMBIGUOUS under this rule. Nothing was ruled out, because nothing was
declared.

- **The alternative.** "Vacuous UNIQUE" would allow it.
- **What it would change.** Only thin, undeclared configurations. No shipped
  tick has a single candidate without a declared alternative.
- **Recommendation.** AMBIGUOUS, matching the module's own sentence: "a cause
  is named only when something rules the alternatives out".

### F2: localization-agreement gate (fixes SC-02)

**The rule.** UNIQUE for *c* is withheld, giving AMBIGUOUS with reason
`SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN`, while any localization in
the same tick whose subject is *c*'s component still keeps a hypothesis from
another domain, supported or unresolved. The retained hypotheses are listed.

**Requirement.** Attribution receives the tick's localizations. The engine
already computes both from the same records (engine.py:293-301).

**Effect.**

- **281 of 2,640 shipped ticks** change attribution.
- **Final ticks:** UNIQUE becomes AMBIGUOUS in 7 scenarios:
  - ACTUATOR_NO_RESPONSE;
  - CLOCK_DRIFT;
  - MS_B3_DRIVE_NO_CURRENT;
  - MS_B4_MECHANICAL;
  - MS_B5_RESPONSE_SENSOR, whose true cause is the sensor;
  - MS_TS_B5_RESPONSE_SENSOR, whose true cause is the sensor;
  - STALLED_ACTUATOR.
- **P9** falls from 281 to 0.

**This changes recorded Phase C results.** The final attribution verdicts in
`engineering/v2/V2_SCENARIO_RESULTS.json` differ, and so do the tables in
`engineering/v2/V2_CHATGPT_REVIEW_REPORT.md` that list those scenarios as
UNIQUE. Those files are **not** edited. The successor would disagree with
them.

### C2: Kleene aggregation in predicates (fixes SC-03, SC-04)

**The 18 predicates** listed as "no" in `CURRENT_SEMANTICS_MAP.md` §3 adopt
the strong-Kleene rule:

- **aggregate ("every row fine")**:
  - any adverse row gives False;
  - otherwise, any UNAVAILABLE row gives None;
  - otherwise, True if any row;
  - NOT_APPLICABLE rows say nothing;
- **single record**: UNAVAILABLE gives None, the same as `_nominal` already
  does;
- **shared node**: a declared shared node that is unreported or UNAVAILABLE
  has **unknown** status, so the shared-dependency predicate is None, not
  False.

**Structure is unchanged.** Dependencies still come from every record,
including UNAVAILABLE ones.

**Effect.**

| where | result |
|---|---|
| shipped ticks | **0 / 2,640 changed**. No shipped scenario drops telemetry |
| P6 (Kleene violations under UNAVAILABLE) | 382 → **0** |
| P12 (inconsistent predicates) | 15 → **0** |
| N3 / N4 / N6 unknown-based rejections | 1,208 / 486 / 224 → **0** |
| engine variants | V_MIS_1 keeps SUPPORTED transport_delay; V_MIS_2 gives AMBIGUOUS, not the wrong processing_delay; V_MIS_3 gives INSUFFICIENT_EVIDENCE; V_MIS_4 keeps the power path unresolved |

### C3: subject-scoped function predicates (fixes SC-05)

**The scoped predicates.** ESTIMATOR_PROCESS_HEALTHY, FUNCTION_LINKS_NOMINAL,
FUNCTION_TIMING_WITHIN_DEADLINE, NO_TIMING_SEGMENT_OVER_BUDGET and
CPU_HEADROOM_NOMINAL, plus the POSITION_UNAVAILABLE detector, read only
components **declared** to serve their subject:

- the channels, processes and links whose `affected_functions` name the
  subject;
- everything those depend on, transitively;
- a channel's own segments.

Nothing declared gives None.

**Effect.**

| where | result |
|---|---|
| P1 / P2 / N5 irrelevant-evidence violations | 142 / 6 / 94 → **0** |
| P16 contradictions (symptom on an ELIGIBLE function) | 838 → 168 |
| shipped ticks | **664 / 2,640** localization ticks change; 16 scenarios at the final tick |

**What the 664 changes are:**

- **Removals that fix a defect.** Wrong symptoms and causes on unrelated
  functions disappear: MS_B1 (ESC CAN) and NETWORK_LATENCY (telemetry
  channel).
- **Losses caused by profile gaps.** In most scenarios, POSITION_UNAVAILABLE
  on COARSE_NAVIGATION disappears. It also becomes AMBIGUOUS in two scenarios
  where it had been correctly SUPPORTED (MS_D1, SHARED_RAIL). OUTPUT_MISSING
  becomes AMBIGUOUS in three.
  - **Why.** The profile does not declare what serves COARSE_NAVIGATION
    (gap G-1), or what the estimator's input link is (gap G-2) (SC-18).
  - **The honest reading.** Those frozen answers were right, but not for a
    reason the model declares. C3 exposes the gap. It does not create it.
- **Knock-on to attribution.** Combined with F2, it also turns UNIQUE into
  AMBIGUOUS for PROCESS_STALL and MS_D2. OUTPUT_MISSING now keeps
  COMMUNICATION/input_starvation unresolved.

**This changes recorded Phase C results.** The D-set rows of
`engineering/v2/LOCALIZATION_RESULTS.csv` use COARSE_NAVIGATION as their
subject, so the successor would produce different rows there.

- **The Phase C gate headline is unchanged.** It rests on the two qualifying
  sets, A_STALE_OUTPUT and the bench pair. Their localizations are unchanged
  under every fix. The D set was already non-qualifying.

**The governance option C3′.** Scope only when the subject declares at least
one serving component; otherwise keep today's whole-tick behaviour.

- **What it keeps.** The COARSE_NAVIGATION answers.
- **What it also keeps.** The defect, for every undeclared subject.
- **Recommendation.** C3, plus fixing profile gaps G-1 to G-3 as profile data.

### C4: error transparency (fixes SC-06, SC-07; reports SC-08)

**The rule.**

- A predicate that raises, or returns anything other than
  `True`/`False`/`None`, is **still** unmeasurable for elimination.
- It is also recorded in `predicate_errors` as (predicate, subject,
  `RAISED:<class>` or `NON_BOOL:<type>`).
- A localization with a non-empty `predicate_errors` carries reason
  `PREDICATE_FAULT`.

**Effect.**

| where | result |
|---|---|
| shipped ticks | **0 / 2,640 changed**; no shipped predicate raises |
| P5 | visibility goes from 0 to every evaluation: 259 of 259 predicate-tick evaluations under injection |

**Deliberately not included** (governance options):

- **Withholding SUPPORTED** when an errored predicate was one of the supported
  hypothesis's own refuters. That is the R9B protection. It changes verdicts
  on inputs frozen v2 never recorded, and it is safe to add later.
- **A successor-side record validator** that turns a malformed record into a
  named UNAVAILABLE producer fault, instead of a `TypeError` in attribution
  (SC-08). It belongs in the successor's intake, not in `EvidenceRecord`,
  which is frozen.

### C5: labels (fixes SC-09, SC-10, SC-11, SC-20)

| frozen 2.0.0 output | successor 2.1.0 output |
|---|---|
| localization UNSUPPORTED, no survivor | NO_CONSISTENT_HYPOTHESIS |
| localization UNSUPPORTED, one unconfirmed survivor | INSUFFICIENT_EVIDENCE (reason UNMODELLED if the survivor is `unmodelled`) |
| attribution `unsupported` list | `implicated_nominal`, `implicated_unavailable`, `implicated_unobserved` |
| attribution UNSUPPORTED verdict (unreachable) | kept reserved and documented as unused |
| attribution NO_EVIDENCE | unchanged verdict, plus a `components_not_observed` detail listing declared components with no looking record |

The 2.0.0 view maps each successor label back exactly. No decision changes.

### C6: idempotence and same-key conflicts (fixes SC-12, SC-13)

**The rule.**

- Exact duplicate records count once, in localization and attribution.
- Two different records for one (relation, component) answer **neither**.
  `EvidenceIndex.one` returns nothing, and the disagreement is listed in the
  trace.

**Effect.**

| where | result |
|---|---|
| shipped ticks | **0 / 2,640 changed** |
| P3 counterexample R6 | order-invariant |
| P4 | 3 decisions → 0; 1,612 trace-only → 0 |

### C7: trace entries only (fixes SC-16, SC-21)

- `CONFIRMED_AND_REFUTED`: hypothesis, refuter, and its specific and shared
  confirmers.
- `SUPPORTED_WITH_UNMEASURED_REFUTERS`: the supported hypothesis's own
  refuters that were None.

The rejection rule is **unchanged**. The counterfactual of changing it is
analysed and rejected in `XSYS_001_COMPATIBILITY.md` §4.

### C8 (optional, deferred): rail source lookup (SC-15)

SOURCE_WITHIN_TOLERANCE for a rail subject would read the rail's declared
POWER dependencies. The defect is S1, and the answer is already carried by
the power domain's reason code. It is not in the minimal set.

### Not corrected here

| finding | why not |
|---|---|
| SC-14 correlated evidence | the brief defers it; it needs source identity, which the architecture package's provenance work covers |
| SC-17 multi-fault attribution | a semantics change, not a defect fix |
| SC-18 profile gaps G-1, G-2, G-3 | profile data, which the owner decides; the profiles are frozen with v2 |

## 3. Effect summary (SH)

| fix | shipped ticks changed (of 2,640) | final-tick scenarios changed (of 44) | changes a recorded Phase C result? | XSYS-001 |
|---|---|---|---|---|
| C1 | 0 | 0 | no | no effect |
| F2 | 281 (attribution) | 7 | **yes**: attribution verdicts | no effect |
| C2 | 0 | 0 | no | no effect |
| C3 | 664 (localization) | 16 | **yes**: D-set rows (not the gate headline) | no effect |
| C4 | 0 | 0 | no | no effect |
| C5 | 0 (labels only) | 0 | no (the 2.0.0 view is unchanged) | no effect |
| C6 | 0 | 0 | no | no effect |
| C7 | 0 (trace only) | 0 | no | trace only |
| all | 664 localization, 362 attribution | 23 | yes | no effect |

## 4. Where it would live, and its size

**Placement.** A small overlay package, for example `csia_v2_successor/`.

- **What it does.** It wraps the frozen `localize()`, `attribute()`,
  `EvidenceIndex` and predicate table. That is exactly what the shadow does,
  in about 400 lines of `semantic_probe.py`.
- **What it touches.** Nothing in `csia/v2`.
- **How it ships.** The successor view is additive, and the 2.0.0 view stays
  the default until the owner switches it.

**Cost.** About 400 lines of production code, plus the property suite in
`METAMORPHIC_TEST_PLAN.md`. The frozen tests remain as the 2.0.0
compatibility suite. Their successor twins are listed in
`EXISTING_TEST_COVERAGE.csv` (T01-T05).

## 5. Part 21: priority against the broader architecture

| order | what | items |
|---|---|---|
| 1. **correct** | S3 defects | C1, C2, C3, F2 |
| 1. **correct** | S2 defects | C4, C6 |
| 2. **explainable** | | C5, C7 |
| 3. **modular** | the architecture package's registry, adapters and admissibility overlay | — |
| 4. **extensible** | provenance, FORGE, new detectors, product UI | — |

**These corrections come before every item in the architecture package's top
five.** Two reasons:

- **Correct before extensible.** An adapter layer (architecture T5) would feed
  more producers into predicates that read "could not look" as "fine". It
  would also multiply the same-key conflicts that C6 addresses.
- **Overlap.** Architecture T1 (admissibility) overlaps C2 and C6. C2 and C6
  should land first, as the minimal kernel admissibility builds on.
