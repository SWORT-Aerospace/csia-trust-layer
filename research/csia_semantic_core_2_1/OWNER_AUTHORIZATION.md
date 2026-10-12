# Owner authorization: CSIA Semantic Core 2.1

**Recorded 2026-09-30.** This is the governance record this package works
under. It records what the owner authorized and what the owner excluded.

## 1. What was decided

The owner approved the governance change recommended by the semantic
correctness audit (`research/csia_semantic_correctness/IMPLEMENTATION_GATE.md`)
and authorized **implementation** of a narrowly scoped successor to the
frozen v2 reasoning semantics.

| correction | authorized as |
|---|---|
| C1 relevance-gated discriminator | implement |
| C2 Kleene aggregation | implement, **only** for the predicates the audit identified |
| C3 subject-scoped function predicates | implement; surface profile gaps, do not redesign the function graph |
| C4 predicate-error transparency | implement |
| C6 idempotence and same-key conflicts | implement |
| F2 localization-agreement gate | implement; do not merge localization and attribution |
| C5 labels, C7 trace | **behaviour-neutral only**. A C5 or C7 change that turns out to alter a decision must be stopped and reported, not widened |

How this package reads the brief on the audit's open governance questions
(`IMPLEMENTATION_GATE.md` §4). The brief does not answer G1 to G5 one by one.
Each row gives the reading and the words it rests on.

| question | reading | basis in the brief |
|---|---|---|
| G1 | a post-freeze successor outside frozen v2, with 2.0.0 kept as the historical semantics and the default | "Prefer an additive successor layer outside the frozen v2 implementation"; "Do NOT make 2.1 the default runtime automatically" |
| G2 | C1 with no declared alternative gives AMBIGUOUS, the audit's recommendation | the owner approved "the governance change recommended by the CSIA semantic correctness audit", and asked for exactly the audit's C1 |
| G3 | the successor may disagree with recorded Phase C UNIQUE verdicts; the records are preserved and a differential is produced | "F2 disagrees with: 7 recorded Phase C UNIQUE verdicts … Preserve those historical records. Generate a successor differential report." (The count is corrected in `PHASE_C_GOVERNANCE_REPORT.md` §2) |
| G4 | C3 as designed; profile gaps are surfaced, not corrected | "Do not silently redesign the function graph. If profile declarations are incomplete: surface that as a profile/configuration problem" |
| G5 | **not** implemented. Withholding SUPPORTED over a faulted refuter, and intake validation, stay out | only C1, C2, C3, C4, C6 and F2 are approved, "exactly the following conceptual corrections" |

## 2. What must not change

These are preserved byte for byte:

- the frozen v2.0 reasoning implementation (`csia/v2`);
- the Phase C frozen artifacts and manifests;
- the sealed campaigns: XSYS-001, XSYS-001-A1, XSYS-001-A2 and the XSYS-001
  confirmatory result;
- historical result files and their hashes;
- the previous novelty, architecture and semantic audit results;
- the historical entries of `research/physical_validation/FAILURE_LEDGER.yaml`.

**How it is enforced here:**

| check | where |
|---|---|
| the four frozen reasoning files hash as locked | `PHASE_A_CHARACTERIZATION_LOCK.json`, checked by `tests/test_semantic_core_2_1.py` |
| 22 protected files hashed before and after the differential run | `semantic_core_2_1_differential.py`, `PROTECTED_FILES` |
| every hash the XSYS-001 result manifest records, re-verified: 225 files, its own seal, and the A1 and A2 protocol chain | the same run, `F.sealed_manifests` |
| the failure ledger is byte-identical to the hash its three sealed-phase manifests pin (rule R8) | `tests/test_semantic_core_2_1.py` and each phase's manifest test |

## 3. What was not authorized

These are **not implemented here, and not started:**

- the broader usefulness architecture;
- a general evidence provenance graph, producer registry, general monitor
  plugin framework or broad evidence contracts;
- correlation-aware fusion or active diagnosis;
- CUSUM, Kalman or reachability adapters;
- capability margin, model inadequacy, CSIA-DX, FORGE, ZETH or SICA;
- flight-control actions or automatic adaptation;
- a new large research campaign;
- **making 2.1 the default runtime.**

## 4. Where the work lives

| path | what |
|---|---|
| `csia_semantic_core/` | the successor package. Top level, outside `csia/`, like `csia_assurance/`. Nothing in `csia/` imports it |
| `research/csia_semantic_core_2_1/` | this record, the validation evidence and the decision |
| `tests/test_semantic_core_2_1.py` | the successor's executable contract |
| `research/csia_semantic_core_2_1/PROPOSED_LEDGER_ENTRIES.md` | seven proposed entries, FL-054 to FL-060, ready to append. The ledger itself is untouched: appending is the owner's decision under rule R8 |
