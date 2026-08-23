# External documents

Every document sent outside the company — white papers, submissions,
one-pagers, slide decks — belongs here, with its hash recorded in
`MANIFEST.csv`.

## Why

An outward-facing claim that cannot be diffed against the evidence base is
how a superseded figure stays in circulation. In 2026-08 the repository
corrected its real-flight-log claim, wrote down why, and enforced the new
wording with a test. The correction reached the README. It did not reach the
document already submitted to the Army, because no one could tell which
document said what. See
[`../audit/CSIA_EXTERNAL_CLAIM_PROVENANCE_AUDIT.md`](../audit/CSIA_EXTERNAL_CLAIM_PROVENANCE_AUDIT.md).

## Rules

1. **Commit the artifact that was actually sent**, not a regenerated
   equivalent. If it was a PDF, commit the PDF.
2. **Record its sha256** in `MANIFEST.csv` at the moment of submission,
   alongside the recipient and date.
3. **Re-audit on every evidence correction.** When a figure in
   `docs/evidence/evidence_matrix.md` changes status, check this directory
   for documents that quote it and record whether a correction is owed.
4. **Never state a test count in prose.** `tests/test_doc_counts.py` enforces
   this for tracked documentation; external documents are outside its reach,
   which is exactly why they need this manifest.

## `audit_status` values

| Value | Meaning |
|---|---|
| `CURRENT` | Every claim traced and consistent with the present evidence base |
| `PARTIAL` | Some claims traced; others unverifiable or not yet audited |
| `CORRECTION_OWED` | A superseded or prohibited claim is in circulation and the recipient has not been notified |
| `CORRECTION_SENT` | Correction issued through the submission channel; record the date in `notes` |
| `SUPERSEDED` | Replaced by a later document, itself listed here |
