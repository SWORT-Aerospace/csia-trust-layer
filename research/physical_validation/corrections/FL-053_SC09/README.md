# FL-053 / SC-09 — proposed correction of the dwell subtraction (for owner review)

**Status: PROPOSED. Not adopted.** Drafting this package does not adopt it. The
failure ledger is unchanged and does not contain FL-053. The correction becomes
authoritative only when the owner runs `adopt.py --apply` (section 5), which is
the decision rule R8 reserves to the owner.

This package supersedes the 2026-09-26 drafts
(`docs/research/MECHANISM_B_DWELL_DISCREPANCY.md`,
`docs/research/SC09_PROPOSED_CORRECTION.md`) as the review package. Those
drafts are kept unchanged. The draft's own remedy, which was to regenerate
`mechanism_b.json` from a fixed generator and edit `CLAIMS.csv`,
`MECHANISM_B.md` and `REVIEWER_RED_TEAM.md` in place, is **not** what is
proposed here. Regenerating `research/systems-paper/results` is forbidden
without tier completion, and the historical files are the record.

## 1. The four things this correction keeps apart

| | what | status |
|---|---|---|
| **Valid values** | trust first crossing of 0.75: **8.72 / 3.36 / 3.24 s**; CUSUM first alarm: **2.96 / 1.16 / 0.72 s** (1 m/s ramp, 3 m/s spoof, 6 m/s ramp), at `mechanism_b.json` `arms.*.crossing` | correct as committed; reproduced exactly by re-running the generator; nothing to change |
| **Erroneous metadata and subtraction** | `policy_dwell.trust_latency_includes_dwell: true` (E1) and `trust_detector_only_latency_s` = **7.72 / 2.36 / 2.24 s** (E2), plus the prose and closure built on them (E3) | wrong: the raw series is a crossing from `run_pipeline`, which never runs `FailsafePolicy`, so there was no dwell to subtract |
| **Substantive conclusion** | SC-09: "The CUSUM alarms earlier than the trust threshold in every faulted arm and never in the clean window." | **unchanged**; the CUSUM lead widens to 5.76 / 2.20 / 2.52 s from the stated 4.76 / 1.20 / 1.52 s |
| **Historical record vs proposed authority** | the historical files stay byte-identical, pinned by SHA-256 in `CORRECTION_RECORD.yaml`; the proposed authoritative statement is in that record | the historical record governs until adoption; after adoption the record governs and the history stays as history |

## 2. Why a successor record, and what the rules allow

- `research/physical_validation/EVIDENCE_EXTENSION.yaml` lists
  `research/systems-paper/results` as `forbidden_without_tier_completion`. So
  `mechanism_b.json` is not regenerated, now or on adoption.
- Rule R8 (`docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`): no append to
  the failure ledger without the owner's decision. The ledger is pinned by the
  Phase 3.2, 4 and 5 SHA-256 manifests.
- Rule R4: no sealed artifact changes. The established exception, used by
  commits `b7f1816`, `d69919d`, `c2aac29` and `39dc509`, rewrites exactly two
  lines per manifest (the ledger's hash and `head_at_build`) when an owner
  approves an append. `adopt.py` does that and nothing more.
- Precedent for correcting committed evidence by a successor:
  `research/physical_validation/results/s0_rederivation.json` sits beside an
  `escalation_algebra.json` that was left unedited.
- `research/physical_validation/` is an allowed path of the extension, so this
  package lives there.

## 3. Identifier check

The ledger has 124 entries (52 FL, 18 HF, 43 MX, 11 SR). The FL series is
FL-001 to FL-052 with no gap, so **FL-053 is free in the ledger**. It is reserved
in four places outside it:

| ids | holder | reserved | consequence |
|---|---|---|---|
| FL-053 | this correction | 2026-09-26, `b75ad0c` | the earliest claim |
| FL-054 to FL-060 | Semantic Core 2.1 proposals | 2026-09-30, `b409abe` | numbered on the stated assumption that FL-053 is promoted first |
| FL-061, FL-062 | Semantic Core 2.1.1 revision | 2026-10-01, `a970b5c` | the same assumption |
| FL-053 to FL-057 | PRIME-1 drafts, branch `claude/csia-prime-pilot` only | 2026-10-03, `231fa61` | **collides with all of the above.** The drafts say "the owner assigns the final ids". PRIME-1 is frozen and is not edited; at promotion they need new ids (FL-063 onward if everything above goes first) |

Assigning FL-053 here is consistent with every reservation except the PRIME-1
drafts. `adopt.py` refuses if FL-053 is taken or if the FL series no longer
ends at FL-052.

## 4. The canonical correction inventory

- **Paper I corrections ledger:**
  `publication/system_paper_i/evidence_export/10_CORRECTIONS_LEDGER.md`,
  identical to `_static/10_CORRECTIONS_LEDGER.md`. It has **14** rows and is the
  only repository list of corrections "that change what a sentence may say".
- **Failure ledger:** 124 entries. It is **not** a corrections list. It records
  every failure, guard, negative result and own error of the evidence-extension
  program, and its row count is not a correction count.
- **Ledgered current-stack entries a Paper I text may cite** as further
  corrections, by id: FL-014 (A1 trust not captured), FL-016 (the control arm
  rises more), FL-017 (the watchdog was not pinned), FL-018 (both replicate on
  PX4), FL-019 (why ArduPilot's pre-fault trust was stable is unresolved).
- **Proposed, not adopted:** FL-053, this correction.
- **Not Paper I:** FL-054 to FL-062 (Semantic Core proposals) and the PRIME-1
  drafts.

The writing session reports nineteen corrections, eighteen of them presented as
canonical. The repository cannot confirm eighteen as a single list: it holds
14 canonical Paper I corrections, plus ledgered entries that may be counted only
by naming them. In no case is the SC-09 dwell correction an adopted correction
while this record says PROPOSED.

## 5. Adoption

**Tier A, the correction itself.** Preview, which writes nothing:
`python research/physical_validation/corrections/FL-053_SC09/adopt.py`.
`ADOPTION.patch` is that preview as a diff, generated on top of the commit
named in its `head_at_build` lines and with placeholder decision fields; on
`--apply` those lines take the HEAD of that moment. On `--apply` it
changes exactly eight files:

1. `research/physical_validation/FAILURE_LEDGER.yaml`: FL-053 appended (`FL-053.ledger_entry.yaml`)
2. to 4. `research/consequence/phase32/SHA256_MANIFEST32.json`, `research/phase4/SHA256_MANIFEST4.json`, `research/phase5/SHA256_MANIFEST5.json`: the ledger hash and `head_at_build`, nothing else
5. `docs/FIELD_INTEGRATION_RUNBOOK.md`: "ledger has 124 entries" becomes 125
6. `research/physical_validation/PAPER_IMPACT_LEDGER.yaml`: PI-006 appended with `ready_to_integrate: true`
7. `docs/CURRENT_PROGRAM_STATE.md`: a pointer note after the systems-paper gate table; the gate-9 row is not rewritten
8. `CORRECTION_RECORD.yaml`: status ADOPTED, with the decision fields

**Those eight files are not enough.** The rehearsal (section 7) found that
seven later programs pin the ledger's exact SHA-256 as a baseline invariant.
The pins are in `tests/test_semantic_core_2_1.py`,
`tests/test_semantic_core_2_1_revision.py`,
`tests/test_semantic_core_2_1_shadow.py`,
`research/csia_2_2_evidence_assurance/common_2_2.py`,
`research/csia_2_2_offboard_pilot/common_pilot.py` (imported by the 2.3, PRIME
and RB-001 baseline verifiers),
`research/csia_semantic_core_2_1_revision/revision_common.py` and
`research/csia_semantic_core_2_1_shadow/verify_state.py`. They were added from
2026-09-30 on, after the last ledger append on 2026-09-22, so the manifest
precedent does not cover them. Any append, this one or the Semantic Core
proposals, changes the hash and fails four tests. They belong to Semantic Core,
CSIA 2.2 and the programs built on them, so `adopt.py` does not edit them.
Instead it lists them in the preview and refuses `--apply` without
`--guard-pins-decision`. `CORRECTION_RECORD.yaml` lists them under
`ledger_hash_pinned_in_code`.

**Tier B, propagation into the paper package.** A separate decision. Add this
as row 15 of `publication/system_paper_i/_static/10_CORRECTIONS_LEDGER.md`,
change "Fourteen" to "Fifteen" there and "fourteen" to "fifteen" in
`publication/system_paper_i/build_evidence_export.py`, then rebuild the evidence
export, which re-hashes its README table:

> `| 15 | trust latency "detector only" 7.72 / 2.36 / 2.24 s; red-team 2.3 closed by subtracting the policy dwell | **CORRECTED (FL-053)** | the trust latency is a crossing of the raw trust series from run_pipeline, which runs no failsafe policy, so it never contained the 1.0 s dwell; the raw figures 8.72 / 3.36 / 3.24 s against CUSUM 2.96 / 1.16 / 0.72 s are already detector-to-detector, and SC-09 holds by a wider margin | research/physical_validation/corrections/FL-053_SC09/CORRECTION_RECORD.yaml; research/systems-paper/results/mechanism_b.json arms.*.crossing | FL-053 |`

**The approval this needs, stated exactly.** The owner records a decision
covering:
- (a) appending FL-053 to the failure ledger under R8;
- (b) rewriting only the ledger hash and `head_at_build` in the three
  sealed-phase manifests, under the R4 precedent;
- (c) appending PI-006;
- (d) the program-state pointer note;
- (e) tier B, or not;
- (f) how the seven ledger-hash guards are handled. The options are:
  - re-pin them to the post-adoption hash in the adoption commit;
  - make them append-only, so the pinned bytes are a prefix of the ledger;
  - adopt FL-053 together with the Semantic Core ledger promotion, which breaks
    the same pins.

  Each option edits Semantic Core or CSIA 2.2 guard files, which this session
  may not do.

The owner then runs `adopt.py --apply --decided-by "<name>" --decision-reference "<where the decision is recorded>" --guard-pins-decision "<the decision on (f)>"`, applies (f), runs the suite, and commits. The PRIME-1 draft ids are renumbered at their own promotion and are not part of this decision.

## 6. Instruction for the paper-writing session

> **Status.** The SC-09 dwell correction (FL-053) is **PROPOSED and awaiting
> owner review**. It is not in the failure ledger. Do not call it accepted,
> adopted, applied or ledgered.
>
> **Count.** Do not count it among the paper's corrections. The repository's
> canonical Paper I corrections ledger has **14** entries. Any correction
> counted beyond those 14 must name an entry that exists in
> `research/physical_validation/FAILURE_LEDGER.yaml` (for example FL-016,
> FL-017, FL-018, FL-019). State the total as the number that maps, and give
> the dwell item separately: "one further correction to a supporting figure
> (FL-053) is proposed and awaiting review". Do not write "nineteen
> corrections" while FL-053 is proposed.
>
> **Values.** Use the raw first crossings, which are valid committed values
> whatever the decision: trust **8.72 / 3.36 / 3.24 s** against CUSUM
> **2.96 / 1.16 / 0.72 s**. Describe them literally: the first crossing of the
> raw trust series below 0.75, which no failsafe policy has acted on, and the
> CUSUM's first alarm. Do not present 7.72 / 2.36 / 2.24 s as detector-only or
> net-of-dwell latencies. Do not say red-team objection 2.3 was closed by
> correction.
>
> **Conclusion.** SC-09 is unchanged: the CUSUM alarms earlier in every faulted
> arm and never in the clean window. It is a bench-simulator result for one
> node and one profile.
>
> **Do not quote** the policy alert times 9.72 / 4.36 / 4.24 s. They are
> verification inside a proposed record, not a result.
>
> **If the repository later shows `status: ADOPTED`** in
> `CORRECTION_RECORD.yaml`, FL-053 may be counted as one more correction, and
> the paper may say the dwell subtraction was corrected. Not before.

## 7. Verification, 2026-10-18

`python research/physical_validation/corrections/FL-053_SC09/verification/verify_correction.py`: **43 of 43 checks pass.**

- **C1:** 15 historical files byte-identical to their pinned hashes.
- **C2 and C3:** the committed values; the subtraction is exactly crossing minus 1.0; the CUSUM is earlier on raw and subtracted figures alike.
- **C4:** an AST check of the source. `run_pipeline` references `PredictionComparator`, `TrustEngine` and `CausalDiagnosis` and no `FailsafePolicy`; `mechanism_b.py` never references `FailsafePolicy`.
- **C5:** the shipped `FailsafePolicy` stepped over the exact arms escalates exactly 1.00 s after each crossing (9.72 / 4.36 / 4.24 s), and never on the clean arm. The 2026-09-26 draft inferred 1.04 s from a different scenario.
- **C6:** status and identifier are consistent.
- **C7:** all three manifests pin the ledger on disk.
- **C8:** `ledger_hash_pinned_in_code` lists exactly the 7 tracked Python files
  that pin the ledger's hash. After adoption, the check requires a recorded
  guard-pins decision instead.

Also re-run today on a clean archive: `mechanism_b.py` reproduces
`mechanism_b.json` with 0 of 194 keys differing.

**Adoption rehearsal.** In a throwaway clone of `3a12efa`, `adopt.py --apply`
was run with placeholder decision fields; the repository itself was not
touched. It changed the eight files, and in each manifest only the two lines
it should. The ledger then had 125 entries ending at FL-053. The full suite
in the adopted clone (without `tests/test_hf_acquisition.py`, for disk space)
gave 4652 passed, 44 skipped, 2 xfailed and **4 failed**. The four failures are
the three Semantic Core ledger-pin tests and
`test_evidence_assurance_2_2.py::test_no_frozen_artifact_changed_since_the_2_1_1_baseline`,
and nothing else failed. That finding is decision (f) above. The clone was
deleted afterwards.

## 8. Contents

| file | role |
|---|---|
| `CORRECTION_RECORD.yaml` | the successor record: four-way distinction, pinned history, affected references with dispositions, identifier audit, inventory |
| `FL-053.ledger_entry.yaml` | the exact block `adopt.py` appends to the failure ledger (revises the 2026-09-26 draft) |
| `PI-006.paper_impact_entry.yaml` | the exact paper-impact row it appends (drafted not ready) |
| `adopt.py` | preview by default; `--apply` is the owner's |
| `ADOPTION.patch` | the preview as a reviewable diff, with placeholder decision fields |
| `verification/verify_correction.py`, `verification/measure_policy_alerts.py`, `verification/policy_alerts.json` | the checks, the policy-alert measurement and its output |
