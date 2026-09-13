# Document index

418 markdown files exist in this repository. Most are the frozen research
record: preregistrations, work-package reports and audits that were written
once, cite a commit, and are never revised. Indexing all 418 individually would
produce a table nobody maintains, so this index works at two granularities.

<!-- The two numbers above are checked against `git ls-files '*.md'` by
     tests/test_doc_counts.py::test_the_document_index_states_the_real_file_count.
     They read 319 for an unknown period; the true count at the time of that
     correction was 342, and the guard exists so the next drift is caught in
     the commit that causes it rather than by a reader. FL-010. -->


**Individually indexed:** the documents a new researcher reads, and every
document that governs what is true or what may be worked on.

**Indexed by directory:** the work-package research record, which is uniformly
historical, uniformly load-bearing, and uniformly cited by artifact maps.

## Status vocabulary

| status | meaning |
|---|---|
| **CANONICAL** | governs. If another document disagrees, this one wins |
| **HISTORICAL** | a true record of a completed activity. Not revised, not superseded, cited by claims |
| **SUPERSEDED** | replaced. Kept for provenance; `superseded_by` names the replacement |
| **GENERATED** | produced by a script; edit the script, not the file |
| **SCRATCH** | working notes with no downstream reference |

**Load-bearing** means a test, artifact map, manifest, manuscript or guard
resolves the path. A load-bearing document may not be moved or renamed without
updating what points at it.

---

## Start here

| document | status | purpose | canonical? | superseded_by | load-bearing? |
|---|---|---|---|---|---|
| `README.md` | CANONICAL | what CSIA is, current focus, status, quickstart, repository map | yes | — | no |
| `docs/CURRENT_PROGRAM_STATE.md` | **CANONICAL** | **what may be worked on**, the three freeze tags with their commits, test status, blockers, limitations. Written so the state is recoverable without conversation history | yes | — | **yes** — `tests/test_program_state.py` |
| `RESEARCH_STATE.md` | CANONICAL | what is scientifically established, refuted, and which paper owns which evidence | yes, for scientific truth | — | yes |
| `CLAIMS_INDEX.md` | CANONICAL | which of the ten claim registers governs which class of claim, and two traps worth naming | yes, for register routing | — | yes |
| `docs/DOCUMENT_INDEX.md` | CANONICAL | this file | yes | — | no |
| `PAPER_I_SCOPE_GUARD.md` | **CANONICAL** | what the mission extension may and may not contribute to Paper I. Paper I's scientific scope is frozen | yes, for Paper I scope | — | **yes** — `tests/test_paper_i_scope_guard.py` |
| `handoff/CSIA_TO_XR_FLIGHT_ARCHITECTURE.md` | CANONICAL | the whole stack from frozen core to future planner, with the prohibited claims listed | yes, for architecture | — | no |
| `docs/mission/NOVELTY_CLASSIFICATION.md` | **CANONICAL** | every mission-layer idea classified. `NOVELTY_NOT_ESTABLISHED` on every row | yes, for novelty | — | **yes** — `tests/test_paper_i_scope_guard.py` |

`CURRENT_PROGRAM_STATE` and `RESEARCH_STATE` do not compete: the first governs
*what may be worked on*, the second governs *what is established*.

## Papers

| document | status | purpose | canonical? | superseded_by | load-bearing? |
|---|---|---|---|---|---|
| `papers/csia_systems/README.md` | CANONICAL | Systems Paper I: status, build, artifact sources, bibliography state, blockers, submission gate | yes | — | no |
| `papers/gate_conditioning/README.md` | CANONICAL | mathematical paper, same fields | yes | — | no |
| `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` | CANONICAL | every figure, table and headline scalar bound to an artifact | yes | — | **yes** — `make artifact-map` |
| `papers/gate_conditioning/GATE_PAPER_ARTIFACT_MAP.yaml` | CANONICAL | same, for the mathematical paper | yes | — | **yes** |
| `papers/BIB_VERIFICATION_LEDGER.yaml` | CANONICAL | verification status and route for every bibliography entry | yes | — | **yes** — `tests/test_bib_verification_ledger.py` |
| `CANONICAL_MANUSCRIPT_MANIFEST.md` | GENERATED | which manuscript file is authoritative, at a stated commit | — | — | yes |

## Research: the two papers' evidence

| document | status | purpose | canonical? | superseded_by | load-bearing? |
|---|---|---|---|---|---|
| `research/math-paper/FORMAL_CORE.md` | **CANONICAL** | the proofs. P1–P8, C2, C3, with assumptions stated exactly and counterexamples to weakened ones | yes, for posterior distortion | — | **yes** |
| `research/math-paper/NOVELTY_AUDIT.md` | CANONICAL | per-proposition novelty status; every row KNOWN. Forbidden-phrase list | yes | — | **yes** — `tests/test_math_paper_proofs.py` |
| `research/math-paper/PRIOR_ART_MATRIX.csv` | CANONICAL | prior art, with the verification route for each row | yes | — | **yes** |
| `research/math-paper/REVIEWER_RED_TEAM_MATH.md` | CANONICAL | four reviewers, eleven objections, remaining weakness never omitted | yes | — | no |
| `research/systems-paper/CLAIMS.csv` | **CANONICAL** | systems claims with counter-evidence and an alternative explanation each | yes, for systems claims | — | **yes** |
| `research/systems-paper/MECHANISM_A.md` | CANONICAL | self-occlusion: what was measured and what it does not prove | yes | — | yes |
| `research/systems-paper/MECHANISM_B.md` | CANONICAL | threshold-crossing persistence on the bench simulator. **Explicitly not** the current-stack replication | yes | — | yes |
| `research/systems-paper/REVIEWER_RED_TEAM.md` | CANONICAL | four reviewers, eleven objections | yes | — | no |
| `research/systems-paper/CURRENT_STACK_BLOCKERS.md` | CANONICAL | what cannot be measured here, and why | yes | — | no |
| `research/systems-paper/PUBLIC_LOG_STUDY_PLAN.md` | CANONICAL | the study that egress policy prevents; `SC-22` is PROVISIONAL until it runs | yes | — | yes |
| `research/PROSE_NUMERIC_BINDINGS.yaml` | CANONICAL | every headline number in research prose, bound to artifact and JSON pointer | yes | — | **yes** — `tests/test_prose_numeric_bindings.py` |
| `research/PAPER_RELATIONSHIP.md` | CANONICAL | which paper owns which result, and what neither may do | yes | — | no |
| `research/FUTURE_RESEARCH_FRONTIER.md` | CANONICAL | questions deliberately not pursued yet | yes | — | no |
| `research/v1_1/CURRENT_STACK_REPLICATION.md` | **CANONICAL** | the preregistered replication campaign. ArduPilot 4.8 REPLICATED, PX4 SIH INAPPLICABLE | yes | — | **yes** |
| `research/physical_validation/ARDUPILOT_REPEAT_RECONCILIATION.md` | **CANONICAL** | twelve headline quantities across the original n=1, Campaign A1 and Campaign A2. Nine reproduce; three do not, root-caused to a 0.5 s vs 1.0 s runtime watchdog | yes, for what the Mechanism-A numbers mean | — | **yes** — `tests/test_ardupilot_repeat_reconciliation.py` |
| `research/physical_validation/PX4_REPEAT_RECONCILIATION.md` | **CANONICAL** | the same, second platform: twelve quantities across the PX4 n=1 and Campaign P1. Ten reproduce; two do not, attributed by a controlled watchdog replay | yes | — | **yes** — `tests/test_px4_repeat_reconciliation.py` |
| `research/physical_validation/SCALAR_DERIVATION_GRAPH.yaml` | CANONICAL | where each headline scalar comes from, and which have an oracle that closes the loop | yes | — | no — hand-compiled, and says so |
| `research/physical_validation/mutation/MUTATION_ADJUDICATION.md` | CANONICAL | per-mutant adjudication of the six unresolved mutants, in five classes | yes | — | no |
| `research/physical_validation/mutation/MUTATION_SURVIVORS.md` | HISTORICAL | the original campaign at `33d3d61`. **Its §2–4 is contradicted** by the adjudication and kept | — | partly, by `MUTATION_ADJUDICATION.md` | no |
| `research/physical_validation/P4_P7_STATUS_AUDIT.md` | CANONICAL | P4–P7 audited by running their tests. P4/P6/P7 PASS, P5 PARTIAL at the hardware boundary | yes | — | no |
| `research/physical_validation/E1_FINAL_CLAIM_TABLE.csv` | **CANONICAL** | per current-stack claim: what repeated, what did not, what is configuration dependent, and the wording each licenses | yes, for what may be written about E1 | — | **yes** — `tests/test_e1_claim_table.py` |
| `research/physical_validation/E1_FREEZE_MANIFEST.yaml` | **CANONICAL** | the state E1 was frozen at: core, campaign, prereg, trace, extractor, claim-table and paper digests | yes | — | **yes** — `tests/test_e1_freeze_manifest.py` |
| `hardware/validation_rig/E2_BUILD_PACKET.md` | CANONICAL | what to buy and wire for E2, and what E2 does and does not license | yes, for the next tier | — | **yes** — path checked by `tests/test_e1_freeze_manifest.py` |
| `research/physical_validation/prereg/E2_HARDWARE_BOUNDARY_PREREG.md` | **TEMPLATE, NOT A PREREGISTRATION** | E2's design fixed before purchase; every environment field left `[FILL:]` until a board exists. `E2_STATUS: NOT_RUN` is the only line citable today | **no** — nothing in it is evidence | — | **yes** — `tests/test_post_e1_hardening_round2.py` fails if the FILL markers vanish |
| `research/physical_validation/FAILURE_LEDGER.yaml` | **CANONICAL** | every failure, negative result and self-correction, append-only | yes | — | yes |
| `research/physical_validation/PAPER_IMPACT_LEDGER.yaml` | **CANONICAL** | what each result licenses — and what it does not | yes | — | yes |
| `docs/math/PROOF_STATUS.md` | CANONICAL | claim register for the **anytime-valid e-process** work (T-1…T-5). A different body of work; it does **not** govern P1–P8 | yes, for e-processes | — | yes |

## Architecture, product and status

| document | status | purpose | canonical? | superseded_by | load-bearing? |
|---|---|---|---|---|---|
| `docs/CSIA_MASTER_ARCHITECTURE.md` | CANONICAL | the architecture across v1, v1.1 and v2 | yes | — | no |
| `docs/RUNTIME_AND_ARCHITECTURE.md` | CANONICAL | deployable-software detail, traceability to modules, validation evidence with limits. Relocated verbatim from `README.md` in the 2026-09 finalization | yes | — | no |
| `docs/product/CSIA_READINESS.md` | CANONICAL | what the system is and is not ready for, at maturity M2 | yes | — | yes |
| `docs/CSIA_RESEARCH_TO_PRODUCT_MAP.md` | CANONICAL | which research result became which product behaviour | yes | — | no |
| `docs/SWORT_AUTONOMY_STACK.md` | CANONICAL | where CSIA sits in the wider stack | yes | — | no |
| `docs/product/DATA_TO_ASSURANCE_MAPPING.md` | CANONICAL | how data becomes an assurance statement | yes | — | no |
| `engineering/v2/V2_PHASEC_FREEZE.md` | **CANONICAL** | the Phase C freeze record: commit, artifact hashes, gate verdict | yes | — | **yes** — `tests/test_phase_c_freeze.py` |
| `docs/v1/V1_FINAL_RESEARCH_VERDICT.md` | CANONICAL | the v1 freeze verdict | yes | — | yes |
| `forge/README_FUTURE.md` | CANONICAL | future architecture. **Documentation only**; no implementation permitted | yes | — | **yes** — `tests/test_program_state.py` forbids Forge code |
| `forge/PRIOR_ART_REQUIRED.md` | CANONICAL | prior art that must be cleared before Forge work may begin | yes | — | yes |

## Finalization records

| document | status | purpose | canonical? | superseded_by | load-bearing? |
|---|---|---|---|---|---|
| `docs/REPOSITORY_FINALIZATION_PRECHECK.md` | HISTORICAL | measured state immediately before the presentation cleanup; the baseline the report is compared against | — | — | no |
| `docs/REPOSITORY_FINALIZATION_REPORT.md` | HISTORICAL | what the cleanup did, and proof that no scientific result moved | — | — | no |
| `HARNESS_RELEASE_AUDIT.md` | CANONICAL | release decisions H-1…H-7 and the 24 open scan review items | yes, for release posture | — | yes |
| `CHANGELOG.md` | CANONICAL | software and evidence changes by release | yes | — | no |

## Transition and commercial

Written for an external programme reviewer. Accurate at the commit each names,
and excluded from public release archives by
`publication/system_paper_i/PUBLIC_RELEASE_MANIFEST.yaml`.

| document | status | purpose | canonical? | superseded_by | load-bearing? |
|---|---|---|---|---|---|
| `docs/TRL_ASSESSMENT.md` | HISTORICAL | TRL self-assessment at `c13889f` | — | — | no |
| `docs/TRANSITION_REPORT.md` | HISTORICAL | transition report and audit | — | — | no |
| `docs/REQUIREMENTS.md`, `docs/requirements/requirements.md` | HISTORICAL | requirements baseline | — | — | no |
| `docs/HARDWARE.md`, `docs/HARDWARE_BOM.md`, `docs/hardware_validation.md`, `docs/embedded_checklist.md` | HISTORICAL | hardware integration, BOM, validation plan, checklist | — | — | no |
| `docs/VALIDATION_PROTOCOL.md` | CANONICAL | the held-out validation protocol | yes | — | yes |
| `docs/FMEA.md`, `docs/ARCHITECTURE_REVIEW.md` | HISTORICAL | failure-modes analysis; adversarial scored review | — | — | no |
| `docs/COMMERCIALIZATION.md`, `docs/ORG_BLUEPRINT.md` | HISTORICAL | strategy. **Excluded from every public archive** by name and by a filename tripwire | — | — | yes, as an exclusion target |
| `docs/latency_report_template.md`, `docs/reliability_report_template.md` | CANONICAL | report templates for hardware campaigns | yes | — | no |

## Superseded and non-load-bearing

| document | status | purpose | canonical? | superseded_by | load-bearing? |
|---|---|---|---|---|---|
| `HANDOFF.md` | **SUPERSEDED** | branch-coordination note from a period when two agents shared `main`. Describes a branch model that no longer applies | no | `docs/CURRENT_PROGRAM_STATE.md` | no — already excluded from public archives |
| `phase1_raw_sensors.py`, `phase2_trust_demo.py`, `phase3_dashboard_demo.py` | HISTORICAL | root-level demo scripts predating the package; thin wrappers over `csia`. Still run. **Not moved**: nothing depends on them, and the brief's priority is that paths cited by audits and manifests stay put | no | `csia report`, `csia service` | no |
| `deliverables/*.md` | HISTORICAL | packaged deliverables produced for external review | — | — | yes, some are release-manifest members |

## Indexed by directory: the research record

Every directory below is **HISTORICAL and load-bearing**. These are
preregistrations, work-package reports and result artifacts written once, each
citing the commit it was produced at, and referenced by claim registers and
artifact maps. They are preserved exactly; a repetitive-looking pair of files
is usually two arms of one experiment, not duplication.

| directory | files | what it holds |
|---|---|---|
| `engineering/v2/` | 28 | Phase C specifications, domain evidence contracts, review reports, the freeze record |
| `engineering/v1_1/` | 26 | architecture decisions, support-state results, phase-4 gate records |
| `docs/audit/` | 19 | work-package audits and claim-provenance matrices |
| `research/dual_admissibility_confirmatory/` | 16 | the confirmatory campaign and its held-out capture |
| `research/effective_evidence_independence/` | 15 | independence probes and their counterexamples |
| `research/phase2/` | 13 | Phase-II candidate registry, problem definition, baseline manifest |
| `publication/system_paper_i/evidence_export/` | 13 | the 16-file evidence export, allowlisted for release |
| `research/frontier_selection/` | 11 | literature frontier search protocol and selection |
| `research/semantic_authority_conflict/` | 11 | authority-conflict experiments |
| `research/ai_contract_synthesis/` | 10 | contract-synthesis experiments and freeze |
| `research/evidence_semantics/` | 10 | evidence-semantics feasibility work |
| `research/maer/` | 9 | MAER jamming and raw-GNSS qualification |
| `docs/validation/` | 9 | metric definitions, split policy, deduplication, exposure plan |
| `research/dual_admissibility/` | 8 | the original dual-admissibility work |
| `hardware/xr1/` | 11 | XR-1 draft profile, registries and physical requirements. **NON_FLIGHT_DRAFT throughout** — nothing has been built, and every number carries a provenance status |
| `handoff/` | 13 | status and handoff reports written at a stated commit, for the writing agents and for the next session. Each is a snapshot, **never** a claim register — `POST_E1_HARDENING_AND_E2_STATUS.md` is the current one |
| `research/wp_c*/`, `research/v1_1/`, `research/invalidity_masking/`, `research/formalization/` | ~30 | work packages C2–C9, v1.1 campaigns, invalidity masking, formalization |

## How to keep this index true

A new document in `docs/` or at the root, or a new canonical register, gets a
row. A new work-package document does not — it belongs to a directory that
already has one. If a document changes status, edit the row rather than
deleting it: `superseded_by` is how provenance survives.
