# Paper I — final scientific update, manuscript-independent part

**Status, 2026-10-12: evidence binding complete; manuscript not yet provided.**

The owner's brief asks for the final hardening of CSIA Systems Paper I,
"Self-Occlusion and Threshold-Crossing Persistence in a Cross-Sensor
Diagnostic Layer". That manuscript is not in this repository. The only
manuscript here, `papers/csia_systems/main.tex`, is the earlier Phase-I paper
under a different title, and it lacks Mechanism B, the CUSUM table and the
current-stack campaigns. It was not edited.

Until the manuscript arrives, this package does only the work that does not
depend on its text. That covers the following:
- binding every value the paper is expected to state to an artifact, a key
  and a hash;
- recording campaign provenance;
- re-running every generator whose inputs are committed;
- re-measuring the reference routes;
- writing down what the evidence requires of the text.

## Contents

| file | what it is |
|---|---|
| `VALUE_BINDINGS.yaml` | 123 value bindings across 26 artifacts, each with key path, expected value, traceability level and provenance commits; plus the forbidden-value list |
| `verify_bindings.py` | `check` re-reads every binding against the pinned artifacts; `scan` checks a manuscript against the bindings; `rerun` re-executes the generators on a clean archive |
| `CAMPAIGN_PROVENANCE.md` | A1, A2, P1 and Mechanism B: platform, frozen core, preregistration and amendment, first and last trial, raw archive, reduction script, summary artifact, seal |
| `REDERIVATION_RECORD.md` | what was re-run or recomputed today, and what cannot be from committed evidence |
| `MANUSCRIPT_FINDINGS.md` | 21 findings the manuscript must satisfy, and the successor-boundary and simulation statements ready to paste |
| `REFERENCE_STATUS.md` | the verification routes re-measured, search corroboration, and the exact list a person with publisher access must check |

Traceability levels, by count of bindings:

| level | meaning | bindings |
|---|---|---|
| T1 | generator re-executed today, every key reproduced | 69 |
| T2 | recomputed independently from committed inputs | 21 |
| T3 | pinned at a key of a committed artifact; generator needs gitignored inputs | 28 |
| T4 | prose only; must be qualified or removed | 2 |
| not supported | no evidence; must not be claimed | 3 |

## Governance, stated plainly

**NO PRIME-1 PRODUCT CODE OR FROZEN RESULT WAS MODIFIED.** This package adds
files under `publication/system_paper_i/final_update/` and one guard test. It
does not touch PRIME-1, the freeze, any sealed artifact, any historical hash,
the failure ledger or the corrections ledger. Every generator was re-run in a
temporary `git archive` outside the working tree. PRIME-2 was not begun. None
of the post-freeze sanity-review findings were implemented.

Where a value could not be tied to evidence, it is marked T4 or not
supported, and nothing was reconstructed from memory.

## What remains, and what it waits for

The phases that read the manuscript's own text are pending:
- the paper-to-claim map;
- the Table 8 and Table 9 rewrites;
- the abstract, introduction, conclusion and title audits;
- the terminology and "detected"-language audits;
- the claim-ledger and falsification-record reconciliation;
- the limitations and data-availability text;
- the figure and table audit;
- the supplement and publication package;
- the clean reproduction of the manuscript build;
- the reviewer red team;
- the sentence-by-sentence claim test.

No submission decision token is issued until those are run on the exact text.

When the manuscript is provided:

```
python publication/system_paper_i/final_update/verify_bindings.py check
python publication/system_paper_i/final_update/verify_bindings.py scan path/to/manuscript.tex
```

`scan` fails on any forbidden value (for example the net-of-dwell 7.72 s) and
lists every number that matches no binding, with its line, so each one is
bound, qualified or removed before submission.
