# CSIA Systems Paper I

**Title.** Diagnostic self-occlusion in a deployed cross-sensor trust layer.

**Status.** SUBMISSION PREPARATION. Not submitted, not accepted, not published.

**Build.**

```sh
make paper-systems          # -> build/papers/csia_systems/main.pdf
```

The build runs `pdflatex → bibtex → pdflatex → pdflatex` and **fails** on any
undefined citation or reference, so a green build means every `\cite` and
`\ref` resolved. Current output: 26 pages.

## What it measures

A deployed cross-sensor diagnostic layer maintains a naive-Bayes posterior over
eight causes with a per-feature validity gate. For the pair
(`nominal`, `gps_fault`) the only distinguishing feature is the GNSS
internal-physics check, and its gate closes when the receiver reports no valid
fix. A fault that removes the fix removes the only evidence that could name it.

The paper measures that: the collapse window, the gate closure rate against a
real autopilot, the escalation delay and what sets it, the false-healthy
exposure, and the cost of an abstaining policy.

## Artifact sources

| what | where |
|---|---|
| artifact map — every figure, table and headline scalar | `PAPER1_ARTIFACT_MAP.yaml` |
| claim ledger | `research/systems-paper/CLAIMS.csv` (**canonical**) |
| mechanisms | `research/systems-paper/MECHANISM_A.md`, `MECHANISM_B.md` |
| independent checker | `research/systems-paper/independent_checker.py`, `research/systems-paper/results/checker_agreement.json` |
| red team | `research/systems-paper/REVIEWER_RED_TEAM.md` |
| prose-to-artifact bindings | `research/PROSE_NUMERIC_BINDINGS.yaml` |
| current-stack replication (preregistered) | `research/v1_1/CURRENT_STACK_REPLICATION.md` |
| Phase-I baseline | `main @ 848f556`, enforced by `tools/publication/phase_guard.py` |

Verify all of it with `make artifact-map` and
`pytest tests/test_systems_paper_numeric_claims.py`.

## Bibliography status

**UNVERIFIED — this is the blocker.** `refs.bib` carries unresolved provenance
markers and no entry is marked verified. Every publisher route
(`api.crossref.org`, `doi.org`, `dblp.org`) and every index route tried as a
fallback (`api.openalex.org`, `api.semanticscholar.org`, `export.arxiv.org`) is
denied from the authoring environment.

`make bib-guard` fails, correctly. `papers/BIB_VERIFICATION_LEDGER.yaml` plus
`tests/test_bib_verification_ledger.py` make a marker deletion detectable: an
entry with no marker must carry a `VERIFIED` row with an accepted route, a
named checker, a date and the record consulted. **Deleting a marker to make the
guard pass is falsification, not a fix.**

## Current blockers

| # | blocker | who can clear it |
|---|---|---|
| 1 | bibliography verification | a human with publisher access |
| 2 | public-log study not run — `review.px4.io` and `logs.px4.io` denied by egress policy; plan committed at `research/systems-paper/PUBLIC_LOG_STUDY_PLAN.md`, claim `SC-22` is `PROVISIONAL` | a host with egress |

Neither is a research problem.

## Submission-candidate gate

Tag `systems-paper-submission-candidate` may be created only when every gate in
`docs/CURRENT_PROGRAM_STATE.md` §3 reads PASS. Eight of ten do today; gates 5,
7 and 8 are the two blockers above.
