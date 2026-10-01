# Novelty discipline (Phase 29)

**2026-10-01.**

**The brief's rule:**
- no broad hunt;
- name a new technical question only if all three hold:
  - existing methods do not answer it;
  - it materially affects usefulness;
  - it is testable.

**Note on the brief.** Its text ends at "If none: say:". The wording it
meant to prescribe is missing. This document therefore states the outcome
plainly, in §3.

**What was not done:** no literature search.
- The candidates were taken only from this pilot's own findings.
- Existing methods were named from what this repository already cites
  where it has them:
  - S060 and S061 in `research/csia_usefulness_architecture/SOURCES.md`;
  - that package's `05_PROVENANCE_AND_DEPENDENCE.md` and
    `02_CSIA_FMEA.md`.
- Otherwise they were named as standard method families, without a new
  search.

## 1. Candidates from the pilot's findings

| candidate question | from | existing methods that answer it | materially affects usefulness? | testable? | passes all three? |
|---|---|---|---|---|---|
| when a hypothesis is eliminated by several refuters, are the refuters independent of each other? | the shared-IMU warning (110/110 fault trials) | dependence-aware combination: common-source tags and ATMS-style labels (S061), adopted by the architecture phase; the cautious rule for non-distinct sources (S060). The architecture phase already posed refutation independence (§3.2 there) | yes | yes | **no:** existing methods and this repository's own design answer it |
| what is the scope of a verdict when some components have no observer? | WA-3 | detectability and coverage analysis (FMEA detection columns; structural diagnosability over a sensor set); this repository's FMEA (`02_CSIA_FMEA.md`) | yes | yes | **no** |
| how should a transitive dependence group be explained? | FV-1 | a presentation question, not a technical one: name the shared root and its holders | small | yes | **no** |
| which claims are blind to which fault classes? | FV-2 | fault-signature and detectability matrices (FMEA; FDI isolability tables) | yes | yes | **no** |
| how can a witness be evaluated without a known onset? | G2 | change detection and onset estimation (CUSUM, GLR), which this repository already runs as the frozen CUSUM | yes | yes | **no** |
| does the estimator's innovation test respond to actuator loss? | `ESTIMATOR_CLAIM_MAPPING.md` §3 | a standard detectability question for a Kalman filter's innovation test; answered here empirically (it does not, AUC 0.43-0.55) | yes | yes | **no:** answered |

## 2. What the candidates have in common

Each is a known question, with a known kind of answer, applied to this
system's evidence. The pilot's value came from applying those answers:
- correctly;
- on real data;
- where an engineer reads them.

None came from asking a question nobody had asked. That is consistent with
the brief's primary objective, which was usefulness, not originality.

## 3. Outcome

**No new technical question was identified** that existing methods do not
answer, that materially affects usefulness, and that is testable.

**The open questions this pilot leaves are engineering and validation
questions:**
- producers for stock logs (G1);
- the onset (G2);
- the four-motor profile (G3);
- hardware logs (G4);
- whether engineers are helped (the external test).

They are listed in `PRODUCT_GAP_ANALYSIS.md` and `RESEARCH_STATUS.md`.
