# Posterior Distortion from Hypothesis-Dependent Validity Gating in Runtime Diagnosis

**Status.** SUBMISSION PREPARATION. Not submitted, not accepted, not published.

**Build.**

```sh
make paper-math             # -> build/papers/gate_conditioning/main.pdf
```

The build fails on any undefined citation or reference. Current output:
10 pages.

## What it claims, and what it does not

A runtime diagnostic layer decides tick by tick which of its evidence is
*applicable*. That decision is a coarsening mechanism the system designed for
itself, so whether it may be ignored is a property of the software rather than
of the data. The paper gives the exact algebra: the reweighting identity, the
additive log-ratio offset, the pinning result, the ignorability condition and
its multivalued caveat, a sufficient condition for the MAP to be unchanged, and
exact divergence identities.

**No new mathematics is claimed.** Every proposition is labelled KNOWN in
`research/math-paper/NOVELTY_AUDIT.md`, and a test greps the manuscript for
phrases that would contradict that. What is claimed is the runtime-diagnostic
formulation, the observation that the condition is decidable *statically from a
signature table before the system runs*, and the implemented instance.

Two results are negative and stated as such: the baseline `q` is a
counterfactual and, in the measured case, not evaluable at all; and the
MAP-stability proposition provably cannot certify the regime the project
measures.

## Artifact sources

| what | where |
|---|---|
| artifact map — scalars, tables, verification | `GATE_PAPER_ARTIFACT_MAP.yaml` |
| the proofs | `research/math-paper/FORMAL_CORE.md` (**canonical**) |
| verification, symbolic and numeric | `research/math-paper/proof_audit.py` → `research/math-paper/results/proof_audit.json` |
| novelty status, per proposition | `research/math-paper/NOVELTY_AUDIT.md` |
| prior art | `research/math-paper/PRIOR_ART_MATRIX.csv` |
| red team | `research/math-paper/REVIEWER_RED_TEAM_MATH.md` |
| the implemented instance | `research/systems-paper/` and its independent checker |

Regenerate with `make proof-audit`; check it is current with
`make proof-audit-check`, which compares the committed artifact against what
the committed script produces (the `commit` field is exempt by name, and the
exemption is asserted).

The claim register for the *anytime-valid e-process* work
(`docs/math/PROOF_STATUS.md`) is a **different body of work** and does not
govern this paper. The manuscript says so explicitly so that a reader who finds
that register does not mistake its open items for gaps here.

## Bibliography status

**UNVERIFIED — this is the blocker.** Same situation and same ledger as the
systems paper: `papers/BIB_VERIFICATION_LEDGER.yaml`, enforced by
`tests/test_bib_verification_ledger.py`. The coarsening-at-random reference
that makes the ignorability proposition KNOWN is `RECONSTRUCTED` from search
alone and must be confirmed against the publisher record before that label is
safe to print.

## Current blockers

| # | blocker | who can clear it |
|---|---|---|
| 1 | bibliography verification | a human with publisher access |
| 2 | one named prior-art reference could not be located; `PRIOR_ART_MATRIX.csv` carries it as `NOT_FOUND_NEEDS_HUMAN`. No sharpness may be claimed for the TV bound until it is closed | a human with library access |
| 3 | one high-priority reference is `NOT_READ_HIGH_PRIORITY` (arXiv:2405.15141, *Likelihood distortion and Bayesian local robustness*) — the title alone makes it the most important unread item in the matrix | a human with access |

## Submission-candidate gate

Tag `math-paper-submission-candidate` may be created only when every gate in
`docs/CURRENT_PROGRAM_STATE.md` §4 reads PASS. Seven of eight do today; gate 8
is blocker 1 above.
