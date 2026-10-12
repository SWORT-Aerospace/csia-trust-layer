# Future human-annotation protocol

Item 33. **Design only. Not executed — no reviewers exist.** Item 33 is
explicit that this must not be run without actual people, and it was not.

## Why it is required

Item 32 names the limitation this package cannot escape: one model produced
the candidate contracts, the reference, the metrics and this document.
`SOURCE_AUDITED_REFERENCE/` is deliberately not called ground truth. Every
extraction number here is provisional until independent annotators exist.

The *sentinel* clause is a partial exception — its reference is derived
mechanically from the protocol schema's `invalid=` attribute with no model
judgement — which is precisely why it is the one clause kind with a
trustworthy number, and why that number says the AI is unnecessary.

## Protocol

**Annotators.** Two engineers per interface, independently, blinded to all
AI output and to each other. A third adjudicates disagreements. None may have
worked on the CSIA adapters.

**Materials.** The `MESSAGE.field` list, the protocol definitions, the
committed decoders, the tests. Not: `candidates/`, `results/`,
`SOURCE_AUDITED_REFERENCE/`, or any previous research package.

**Labels**, per field: has an explicit invalid/sentinel encoding (yes/no/
cannot tell); the raw condition; the canonical evidence state; retention
requirement; freshness requirement; required forbidden merges and the
consumer needing each; and a free-text conflict note.

**Agreement.** Cohen's κ per label kind, reported separately — a single
pooled κ over a universe that is 86% negative would be dominated by
easy agreement on empty fields. Report the positive-class agreement
separately.

**Adjudication.** The third reviewer sees both labels without knowing which
annotator produced which, and records a reason. Adjudicated items are flagged
so they can be excluded from a sensitivity analysis.

**Order.** Annotation completes and is hashed *before* AI candidates are
revealed. The same freeze discipline as `freeze.py`, with the difference that
it would then be a real barrier rather than an ordering convention.

## Sample size

The universe here is 106 fields, 15 with an explicit encoding. That is too
few positives for a stable per-clause-kind κ. A serious study needs several
protocols — MAVLink, uORB, ARINC 429 label definitions, DDS `SampleInfo` —
to get the positive class into the low hundreds.

## What would make the effort worthwhile

Only one thing, and this package already suggests the answer is no: whether
human annotators produce clauses that a schema attribute lookup does not.
If the human reference for the sentinel clause matches the `invalid=`
attribute field-for-field, the annotation confirms that the bottleneck was
never the sentinel. The clause kinds worth paying annotators for are
**retention, freshness, forbidden merges and the consumer requiring each** —
the four the schema is silent about, and the four this pilot could not score
because the reference for them is model judgement.

**That, not extraction accuracy, is the study worth running.**
