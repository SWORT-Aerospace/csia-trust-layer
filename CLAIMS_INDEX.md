# Claim registry index

**There is no single claim registry, and there should not be.** Ten registers
exist because they answer different questions, are maintained by different
work, and have different lifecycles. What was missing was an index saying
which governs what. This is it.

**Rule: a claim lives in exactly one register.** If the same statement appears
in two, the register named below as authoritative for that class governs and
the other is a transcription that may be stale. Silently contradictory
registries are the failure mode this file exists to prevent.

---

## The registers

| register | governs | format | status |
|---|---|---|---|
| `docs/math/PROOF_STATUS.md` | **mathematical-paper claims about ANYTIME-VALID EVIDENCE**: T-1 … T-5, e-processes, Ville's inequality, and their counterexamples | markdown table | authoritative |
| `research/math-paper/FORMAL_CORE.md` §10 | **mathematical-paper claims about POSTERIOR DISTORTION**: P1–P8, C2, C3. A DIFFERENT body of work from the row above, under the same paper. P7 (gated-score form) and P8 (a negative result about P4) were added by the red-team pass recorded in `REVIEWER_RED_TEAM_MATH.md` | markdown table + `research/math-paper/results/proof_audit.json` | authoritative |
| `research/math-paper/PRIOR_ART_MATRIX.csv` | **novelty status** of every proposition in either row above | CSV, machine-checked | authoritative |
| `research/systems-paper/CLAIMS.csv` | **systems-paper claims at CLAIM granularity**, each with counter-evidence and an alternative explanation | CSV, machine-checked | authoritative |
| `research/PROSE_NUMERIC_BINDINGS.yaml` | **every headline number quoted in research prose**, bound to the artifact and JSON pointer it came from | YAML, machine-checked | authoritative |
| `papers/BIB_VERIFICATION_LEDGER.yaml` | **the verification status of every bibliography entry**, and what route was used | YAML, machine-checked | authoritative |
| `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` | **systems-paper claims**: every figure, table and headline scalar, bound to a committed artifact | YAML, machine-checked | authoritative |
| `papers/gate_conditioning/GATE_PAPER_ARTIFACT_MAP.yaml` | **mathematical-paper artifact bindings**: formal sources, verification scripts, counterexamples, tables and scalars | YAML, machine-checked | authoritative |
| `research/phase2/claims.yaml` | **Phase-II research candidates**: C1–C25, including withdrawn ones | YAML, machine-readable | authoritative, ongoing |
| `docs/audit/WP_A2_CLAIM_PROVENANCE_MATRIX.csv` | **outward-facing prose claims** audited for scope inflation and prohibited framing | CSV | authoritative, historical |

Two further documents are records, not registers, and are cited by the above:
`docs/audit/CSIA_EXTERNAL_CLAIM_PROVENANCE_AUDIT.md` and
`docs/traceability/traceability_matrix.md`.

**A trap worth naming.** `docs/math/PROOF_STATUS.md` and
`research/math-paper/FORMAL_CORE.md` are BOTH "the mathematical paper's
claims" and they govern **different, non-overlapping** results — e-processes
in the first, posterior distortion in the second. A reader who assumes one
covers both will look for P3 in `PROOF_STATUS.md`, not find it, and conclude
something is missing. Nothing is. See `research/PAPER_RELATIONSHIP.md`.

**And a second one.** `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` binds
NUMBERS to artifacts; `research/systems-paper/CLAIMS.csv` binds CLAIMS to
evidence, counter-evidence and alternative explanations. A number can be
correctly bound and the claim built on it still wrong, which is why both
exist. Where they overlap, the artifact map governs the number and CLAIMS.csv
governs the claim.

---

## Required fields

Every claim in every register carries, or is amended to carry:

`ID` · `statement` · `status` · `paper eligibility` · `artifact` · `commit` ·
`scope` · `superseded_by` where applicable.

`research/phase2/claims.yaml` already carries all of these. The others predate
the convention; each entry below states where its fields live.

---

## 1. Mathematical-paper claims

**Register:** `docs/math/PROOF_STATUS.md`
**Paper eligibility:** gate-conditioning paper only.
**Commit scope:** claims are statements about mathematics, not about a build;
the verification numbers come from `docs/math/proofs/eprocess_null_simulation.py`.
**Artifact binding:** `papers/gate_conditioning/GATE_PAPER_ARTIFACT_MAP.yaml`.

| status | count | note |
|---|---|---|
| PROVED | 3 | assumption-conditional proofs written out |
| PROVED given A3 | 1 | A3 itself is EMPIRICAL ONLY |
| EMPIRICAL ONLY | 1 | A3 at L=50 for ρ ≤ 0.94 |
| **REFUTED** | **6** | counterexamples, all retained |
| OPEN | 4 | T-2 through T-5 |

The six refutations are `CX-1` to `CX-6` in the gate-paper artifact map. They
are not failures of the paper; they are why the construction has the shape it
has. One (`CX-5`, restart validity without first-observation conditioning) was
found by the project's own verification suite against the project's own
proposal.

---

## 2. Systems-paper claims

**Register:** `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml`
**Paper eligibility:** CSIA Systems Paper I only. Enforced: the map declares
`phase: 1` and `tools/publication/phase_guard.py` fails on any Phase-II
reference.
**Commit scope:** frozen baseline `848f556`. Reproduce at that commit, not HEAD.

`F01`–`F12` figures · `T01`–`T12` tables · `S01`–`S13` headline scalars, each
bound to a committed result file, a generating script, a JSON pointer where one
exists, and a regeneration command. `make artifact-map` fails if a figure is
unmapped, a mapped path is missing, a mapped scalar is absent from the
manuscript, or the table count disagrees.

**Open:** 49 prose numeric literals are not individually mapped. They are
listed on every run for human review. That list, not a green check, is the
enforcement of "no undocumented quantitative claim survives".

---

## 3. Phase-II research candidates

**Register:** `research/phase2/claims.yaml`
**Paper eligibility:** NONE of these are eligible for either current paper.
They were measured on ArduCopter 4.8; both papers are Phase-I.

| ID | subject | status |
|---|---|---|
| C1 | a joint miss exists at 55.7 m, slews 60/120/240 s | BOUNDED |
| **C1_WITHDRAWN** | F3 refuted at significant magnitude | **WITHDRAWN** — the displacement instrument read 38.89 m on a zero-injection arm |
| C2 | CSIA contributes no incremental escalation coverage on the E1 grid | MEASURED |
| C3 | detection and airframe consequence are inversely ordered at 55.7 m | MEASURED |
| C4 | the frozen baseline violates R10 on 4.8 | MEASURED, cause resolved by C11 |
| C5 | R10's verification evidence never covered an independent plant | MEASURED |
| C6 | pack resistance mismatch, a latent near-miss | MEASURED |
| C7 | GPS physics residual saturates on 3.3 and not on 4.8 | OPEN |
| C8 | is the ESC/pack current mismatch a simulator artifact | RESOLVED by C11 |
| C9 | would Phase-I displacements survive re-measurement | OPEN |
| C10 | does any of it hold on PX4 | OPEN |
| C11 | the modern R10 breach is a `SIMULATOR_ARTIFACT` | MEASURED |
| C12 | `-1` sentinel collapses to 0.0 A in ingestion | MEASURED, latent |
| C13 | `AVIONICS_CURRENT` has no counterpart in the plant | MEASURED |
| C14 | does real ESC telemetry satisfy the conservation model | OPEN, needs hardware |
| C15 | seven relations newly active, none validated | MEASURED |
| C16 | what R10 actually constrains | MEASURED |
| C17 | **F4 zero-coverage refuted as a general claim** | MEASURED |
| C18 | CSIA cannot attribute vibration on the legacy-compat rig | MEASURED |
| C19 | a GPS spoof makes CSIA blame the magnetometer | MEASURED |
| C20 | **B3 refuted** — breaks R10 at every setting | MEASURED |
| C21 | **B4 solves the fault-suite coverage problem** | MEASURED |
| C22 | ArduPilot's cumulative drift monitor is `onGround`-gated | MEASURED |
| C23 | the declared protected partition was contaminated | MEASURED |
| C24 | the wind factor is active on 4.8, cosmetic on 3.3 | MEASURED |
| C25 | `INFORMATIVE_VALIDITY` | PROVISIONAL, not implemented |

Historical IDs are preserved. `C1_WITHDRAWN` keeps its ID rather than being
deleted, and `C1` records `supersedes: C1_WITHDRAWN`.

---

## 4. Outward-facing prose claims

**Register:** `docs/audit/WP_A2_CLAIM_PROVENANCE_MATRIX.csv`
**Paper eligibility:** none directly; this register governs README, whitepaper
and TRL prose, and exists to stop scope inflation reaching a paper.

Statuses in use: `TRUE_BUT_SCOPE_INFLATED`, `INTERNALLY_INCONSISTENT`,
`PROHIBITED_FRAMING`. Each row carries the quoted text, the first-appearance
commit, the recomputed value, and the corrected text.

Two conventions that came out of this audit and are now machine-enforced:

- **no unscoped test count in live prose** — `tests/test_doc_counts.py`
- **no corpus log described as verified-healthy** — `tests/test_datasets.py`

---

## 5. Cross-register conflicts, resolved

| apparent conflict | resolution |
|---|---|
| `docs/research/PAPER1_EMPIRICAL_SECTION.md` sounds like Systems Paper I | it belongs to the **mathematical** paper; its own header says "draft for the theory paper". Recorded in `RESEARCH_STATE.md` §3.3 |
| R10 "holds" (Phase I) vs "violated" (Phase II) | both true and both retained. Phase I measured it on 3.3 and the bench; Phase II measured it on 4.8 where a simulator placeholder drives a false alarm. `research/phase2/claims.yaml` C4 and C16 carry the scoping |
| `F4 = zero incremental coverage` (E1) vs `refuted as a general claim` (P1) | E1's result is local to its GNSS-slew grid and stands; C17 refutes only the general architectural reading. The two are not pooled |
| B0 "detected 9 of 9" (Phase I) vs "5 of 7" (Phase II) | different fault domains on different autopilots. Neither is a correction of the other |
