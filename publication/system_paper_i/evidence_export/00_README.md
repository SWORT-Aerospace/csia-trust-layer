# 00 — README: Systems Paper I evidence export

**You are a writing agent with no repository access. This package is your
repository.** Everything needed to write CSIA Systems Paper I is here. If a
value is not in this package, do not invent it: it is marked
`UNRECOVERABLE` and the reason is stated.

**Generated:** 2026-08-23T23:53:48.724052+00:00
**Generator:** `publication/system_paper_i/build_evidence_export.py`
**Every number was read from a committed artifact at build time.** No value
was transcribed from a manuscript draft or from conversational memory.

---

## Read in this order

| # | file | why |
|---|---|---|
| 1 | `01_PHASE1_SCOPE.md` | **read first.** What may and may not be claimed, and the prohibited wording list |
| 2 | `02_FROZEN_DEFINITIONS.md` | **BLOCKING.** The four exposure quantities and SOI, verbatim from source. No exposure number means anything without it |
| 3 | `03_SELF_OCCLUSION_RESULT.md` | the primary run |
| 4 | `04_REPAIR_EXPERIMENT.md` | the fix-preserving contrast, then the repair candidate table |
| 5 | `05_ESCALATION_RESULT.md` | step sweep, ramp contrast, the recursion, the closed form |
| 6 | `06_EXPOSURE_RESULTS.md` | the four quantities, per arm |
| 7 | `07_HARNESS_CONTRACT.md` | what the harness records, and the validity rule |
| 8 | `08_REAL_LOG_RESULTS.md` | the corpus, and the five things it cannot establish |
| 9 | `09_STRUCTURAL_RESULTS.md` | enumeration results, separated from runtime results |
| 10 | `10_CORRECTIONS_LEDGER.md` | fourteen corrections the paper must carry |
| 11 | `11_CLAIM_LEDGER.yaml` | every claim with status, scope and eligibility |
| 12 | `12_ARTIFACT_MAP.yaml` | figure/table/scalar to artifact, with SHA256 |
| 13 | `13_REFERENCE_AUDIT.md` | **no reference is verified.** What remains to do |
| 14 | `14_REPRODUCTION_COMMANDS.md` | exact commands per result |
| 15 | `15_REPOSITORY_STATE.json` | full commit hashes, versions, build identification |

---

## The four things this paper says

1. A deployed diagnostic layer emits **health** when it holds no evidence it
   is entitled to assert health from, and this is measurable.
2. The mechanism is **structural**: every feature that would name a GPS fault
   is behind a gate a GPS fault closes. `SOI(gps_fault) = 1.0`.
3. It is **observed for tested fix-loss faults**, not for GNSS faults in
   general. A fix-preserving fault in the same artifact is diagnosed correctly
   in 1.44 s.
4. Escalation is **duration-limited**, and a closed form for the shipping
   recursion predicts the boundary with zero numerical error over the verified
   horizon.

---

## Four rules for the writing agent

1. **Never invent a number.** If it is not here, it is `UNRECOVERABLE`.
2. **Never widen a scope.** `01_PHASE1_SCOPE.md` section 3 gives the exact
   sentences.
3. **Never label anything a theorem.** The monotonicity result is
   monotonicity; the repair result is a design rule; the escalation result is
   an analytical implementation result.
4. **Never cite a reference as verified.** `13_REFERENCE_AUDIT.md` shows zero
   verified entries.

---

## Phase-II is excluded

Ongoing Phase-II work runs on ArduCopter 4.8 and appears nowhere in this
package except one clearly labelled reproducibility note in `07` section 4
about a MAVLink parameter rename. No Phase-II number is here. Do not ask for
one and do not import one.

---

## Package contents

| file | size | sha256 |
|---|---|---|
| `01_PHASE1_SCOPE.md` | 5,247 B | 64b93bc84ce68f5c... |
| `02_FROZEN_DEFINITIONS.md` | 9,660 B | 24b9f78d358b701f... |
| `03_SELF_OCCLUSION_RESULT.md` | 5,101 B | dae76cbca9623c0d... |
| `04_REPAIR_EXPERIMENT.md` | 6,939 B | ba423bf1d3a24991... |
| `05_ESCALATION_RESULT.md` | 6,914 B | ac5ac06dca680222... |
| `06_EXPOSURE_RESULTS.md` | 4,765 B | 6f3cdb59274030a0... |
| `07_HARNESS_CONTRACT.md` | 5,122 B | 51adfad188c9d8a2... |
| `08_REAL_LOG_RESULTS.md` | 4,400 B | 1129d5a2f214711b... |
| `09_STRUCTURAL_RESULTS.md` | 6,810 B | 81154e86a1dac3a3... |
| `10_CORRECTIONS_LEDGER.md` | 6,206 B | 815d68dd8435a3b5... |
| `11_CLAIM_LEDGER.yaml` | 9,624 B | 2761c26f45e0f837... |
| `12_ARTIFACT_MAP.yaml` | 20,697 B | 3dc3215f4646e1d0... |
| `13_REFERENCE_AUDIT.md` | 5,397 B | 0c508d0ce73b38eb... |
| `14_REPRODUCTION_COMMANDS.md` | 7,159 B | 31242fc1fe096249... |
| `15_REPOSITORY_STATE.json` | 7,674 B | 369a0594b48dc74a... |
