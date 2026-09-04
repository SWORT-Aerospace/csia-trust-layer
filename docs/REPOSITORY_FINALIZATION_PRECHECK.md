# Repository finalization — pre-cleanup verification

State of the repository immediately before the presentation cleanup, measured
rather than recalled. Every figure below was produced by the command named
beside it. This document is the baseline the post-cleanup report is compared
against: if any line changes as a result of a presentation edit, the edit was
not a presentation edit.

Measured 2026-09-04.

## Repository

| | | command |
|---|---|---|
| branch | `claude/code-reviewer-repo-export-zicovg` | `git branch --show-current` |
| HEAD | `eb2577d6830208b26d33facb283aa5be0ddf7c86` | `git rev-parse HEAD` |
| working tree | clean, no untracked files | `git status --short --untracked-files=all` |
| tags at HEAD | none | `git tag --points-at HEAD` |

Existing tags: `csia-v1.0-research-final`, `csia-v2-phasec-frozen`, `v0.7.0`,
`archive/handoff-source-of-record`.

## Tests

| | | command |
|---|---|---|
| collected | 1683 | `pytest tests/ --collect-only` |
| result | all pass, 0 failures, 0 errors | `pytest tests/` |

## Freeze guards

| guard | result | command |
|---|---|---|
| v1 diagnostic core, zero diff against `csia-v1.0-research-final` | PASS | `pytest tests/test_v1_frozen.py` |
| v2 Phase C artifact hashes at `50c5d35` | PASS | `pytest tests/test_phase_c_freeze.py` |
| proof audit reproduces from its committed script | PASS, 8 identities and 3 bounds exact | `python tools/publication/proof_audit_check.py` |

## Publication guards

| guard | result |
|---|---|
| artifact maps | PASS |
| proof audit reproduction | PASS |
| figure bundles match `figures/` | PASS |
| Phase-I papers cite no Phase-II results | PASS |
| manuscript hard style rules | PASS |
| secrets scan | PASS, no credentials |
| public release allowlist and sanitization | PASS |
| **blocking guards, aggregate** | **PASS** (`make check-blocking`) |
| bibliography guard | **FAIL, expected** — 52 unresolved markers across two `refs.bib` files (`make bib-guard`) |

The bibliography guard is advisory, not blocking, precisely because only a
human with publisher access can clear it. See "Bibliography" below.

## Papers

| paper | build | pages | citations |
|---|---|---|---|
| CSIA Systems Paper I | PASS | 26 | all resolved |
| Posterior distortion / gate conditioning | PASS | 10 | all resolved |

`make papers`. The build fails on any undefined citation or reference, so
"citations resolved" is enforced rather than observed.

## Quickstart

`make quickstart` runs to completion; every step asserts its own result.

## Bibliography

**Unresolved, and it is the binding constraint on both papers.** 52 provenance
markers remain across `papers/csia_systems/refs.bib` and
`papers/gate_conditioning/refs.bib`. No entry is marked verified.

Six verification routes were tested from this environment and all six fail at
the proxy's CONNECT with 403: `api.crossref.org`, `doi.org`, `dblp.org`,
`api.openalex.org`, `api.semanticscholar.org`, `export.arxiv.org`. The last
three are `rejected_routes` in the ledger and could not have retired a marker
even on success; they were checked so that "no route exists" is a measurement.

`papers/BIB_VERIFICATION_LEDGER.yaml` makes marker deletion mechanically
detectable: an entry with no marker must carry a `VERIFIED` row with an
accepted route, a named checker, a date and the record consulted.
`tests/test_bib_verification_ledger.py` enforces it.

## Privacy and secret audit

| finding | classification | action |
|---|---|---|
| the private username appears in exactly one tracked file, `publication/system_paper_i/PUBLIC_RELEASE_MANIFEST.yaml`, as the `forbidden_patterns.private_username` entry | **not a leak** — this is the rule the sanitization guard matches on, and a rule against a string necessarily contains it | none. Removing it would disable the guard |
| the packed public archives | contain no manifest; both pass post-pack sanitization | none |
| the same username appears in git HISTORY, in a local machine path inside `docs/runbooks/UAV_SEAD_MAC_ACQUISITION.md` and `tests/test_mac_pipeline.py` at commits `ac8d21d` and `bc3ed97` | **privacy disclosure, not a credential**; already purged at HEAD | **history remediation is a separate decision and is NOT performed here.** Removing it requires a history rewrite, which would invalidate every published tag and freeze SHA. Reported for the owner to decide |
| credential scan | no API keys, tokens, private keys, cookies or password assignments | none |
| 24 remaining scan items | `/home/user`, the generic container path, not a private identity | already recorded in `HARNESS_RELEASE_AUDIT.md` |

## Tracked-file hygiene

| check | result |
|---|---|
| files over 2 MB | 2: `research/phase2/results/power_thrust_contract.json` (5.3 MB, research artifact) and `dashboard_standalone.html` (4.4 MB, shipped dashboard). Both intentional |
| `__pycache__`, `.pytest_cache`, `build/`, `dist/` | none tracked |
| LaTeX auxiliaries, generated PDFs | none tracked |
| IDE and OS metadata | none tracked |
| tracked `.log` files | one: `artifacts/ci/75881b9_failed_run.log`, the CI failure that motivated `tests/test_ci_env.py`. Evidence, not litter |

## What this baseline is for

Parts 3 and 16 of the finalization brief forbid any change to numerical
scientific results, algorithms, frozen constants, hypotheses, experiments,
scenario definitions, result files, Phase-C evidence, paper evidence bindings
or proof outputs. Every row above is re-measured after the cleanup and
reproduced in `REPOSITORY_FINALIZATION_REPORT.md`. A row that moves is a defect
in the cleanup, not a new result.
