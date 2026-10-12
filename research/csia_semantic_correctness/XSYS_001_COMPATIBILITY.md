# XSYS-001 compatibility (Part 16)

CSIA semantic correctness audit, 2026-09-29.

**No XSYS-001 file was modified.** The sealed files were only read:

- `research/xsys_001_confirmatory_campaign/stage1/STAGE1.json`
- `research/xsys_001_confirmatory_campaign/stage2/RESULTS.json`
- `research/xsys_001_confirmatory_campaign/stage2/PRIMARY_RESULT_RECORD.json`
- the frozen pipeline modules

The replay runs only through the shadow successor, in
`semantic_probe.py`, section X.

## 1. What XSYS-001 used from v2

`research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py` imports exactly
these, and nothing else:

| used | not used |
|---|---|
| `localize()`, `EvidenceIndex`, `Predicate`, `Hypothesis`, `SymptomSpec`, the verdict constants, `EvidenceRecord`, `ObservationState`, `Applicability` | `attribute()`; `signatures.PREDICATES` and `SYMPTOMS`; the engine; the function graph; any profile |

It declares **its own** spec (the COMMAND_NO_RESPONSE pair, ACTUATION/mechanical
versus SENSOR/response_sensor) and **its own** three predicates, plus their
negations.

- **Missing evidence is already handled correctly there.** Its `_state` helper
  maps UNAVAILABLE and NOT_APPLICABLE to None.
- **Its records cannot become candidates.** They are all `attributable=False`.

## 2. The replay

**The reconstruction.**

1. For each of the 121 sealed trials, 4 motors and 8 variant/checkpoint cells,
   the records are rebuilt from the sealed Stage-1 features. This uses the
   frozen `stage1_evidence.plan()` and `xsys_v2_adapter.records_for()`, giving
   3,872 localization slots.
2. Each slot is localized with frozen v2.
3. Each slot is then localized with each proposed fix switched on.
4. Every motor-0 slot of an A or B trial is scored with the frozen
   `stage2_score.outcome_symptomatic()`, against the truth recorded in the
   sealed Stage-2 results.

| check | result |
|---|---|
| SHA-256 of the sealed STAGE1.json equals the seal (`ccbc10f5…e8e3`) | **yes** |
| frozen replay identical to the sealed Stage-1 localization, field for field | **3,872 / 3,872** |
| record states present | NOMINAL 3,432; NOT_APPLICABLE 6,974; VIOLATED 1,210; **UNAVAILABLE 0** |
| predicates that raised, with the catch-all bypassed | **0** |
| predicates that returned a non-bool | **0** |
| silent confirm-and-refute, all slots | 660, **all through the shared confirmer** LOCAL_RPM_DEFICIT; **0** through a specific confirmer |
| the same, primary cell (C3/V3_TEMPORAL, motor 0) | 110, all shared; 0 specific |

**Why the 660 shared-confirmer collisions are not conflicts.** The local
RPM deficit confirms **both** causes by design (the adapter docstring). The
dynamics or compensation witness refuting one of them is precisely the
discriminating information XSYS-001 tested. **Refute-over-confirm is the
mechanism of the primary result, not a defect in it.**

## 3. Classification of every proposed correction

| correction (`MINIMAL_CORRECTION_DESIGN.md`) | decision diffs, 3,872 slots | motor-0 outcome diffs | classification |
|---|---|---|---|
| C1 relevance-gated UNIQUE | — (XSYS-001 never calls `attribute()`) | — | **NO EFFECT ON XSYS-001** |
| F2 UNIQUE withheld while the same tick's localization keeps another domain | — (no attribution) | — | **NO EFFECT ON XSYS-001** |
| C2 Kleene aggregation in the shipped predicates | **0** | **0** | **NO EFFECT ON XSYS-001** (XSYS has its own predicates, and no UNAVAILABLE record occurs) |
| C3 subject-scoped function predicates and detector | — (XSYS has no function-subject symptom) | — | **NO EFFECT ON XSYS-001** |
| C4 predicate errors and non-bool returns reported | **0** | **0** | **NO EFFECT ON XSYS-001** (0 errors to report) |
| C5 split labels (NO_CONSISTENT_HYPOTHESIS, INSUFFICIENT_EVIDENCE, implicated_*) | — | — | **NO EFFECT ON XSYS-001** (the sealed verdict tallies contain no UNSUPPORTED, and the frozen scorer reads the 2.0.0 view) |
| C6 duplicate idempotence; conflicting same-key records answer neither | **0** | **0** | **NO EFFECT ON XSYS-001** (three distinct relations per subject) |
| C7 trace entries: confirmed-and-refuted; supported with an unmeasured refuter | 0 decision diffs | 0 | **CHANGES INTERNAL TRACE ONLY** (the 660 shared-confirmer collisions, and the V1/V2 cells where one witness is withheld, would gain trace entries) |
| all localization fixes together (C2 + C4 + C6) | **0** | **0** | **NO EFFECT ON XSYS-001** |

**The primary result** (`PRIMARY_RESULT_RECORD.json`) is unchanged under every
proposed correction:

- 55 of 55 valid matched pairs resolved;
- one-sided 95% lower bound 0.762;
- `PRIMARY_SUPPORTED = YES`.

**No proposed correction changes the XSYS-001 primary result, and none
changes any secondary outcome.** The STOP condition in Part 16 is not
triggered.

## 4. A correction that is NOT proposed, checked anyway

**The counterfactual.** A successor that *refuses* to eliminate a hypothesis
supported by a specific confirmer would turn such cases into a disagreement
verdict. That is one way to read the brief's "expose conflict rather than
silently selecting a winner".

- **On the sealed data it changes 0 slots,** because no XSYS-001 slot has a
  specific-confirmer collision.
- **It is still not proposed.** In general it changes set-elimination
  semantics: N1 finds 217 of 729 valuations affected. It is exactly the kind
  of change that would need its own governance decision. The minimal design
  exposes the conflict in the **trace** (C7) and keeps the rejection.

## 5. What would have required a governance STOP, and did not happen

- **Any fix to XSYS-001's own predicates.** None is needed: they are already
  Kleene-correct.
- **Any change to how refutation beats a shared confirmation.** None is
  proposed.
- **Any relabelling the frozen Stage-2 scorer would read.** The scorer keeps
  the 2.0.0 view.
