# Repository finalization report

Companion to `docs/REPOSITORY_FINALIZATION_PRECHECK.md`, which recorded the
measured state before any presentation edit. Every row there is re-measured
here. The purpose of the pair is a single provable claim: **the cleanup changed
how the repository reads, and changed no scientific result.**

Completed 2026-09-04.

## Heads and branch

| | |
|---|---|
| pre-cleanup HEAD | `eb2577d6830208b26d33facb283aa5be0ddf7c86` |
| post-cleanup HEAD | `64f9acc1fbba03566f01ad863de4a94eb81f51ec` (this document is committed on top of it as R3) |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| remote | `github.com/SWORT-Aerospace/csia-trust-layer` |

## Tags

| tag | commit | local | remote |
|---|---|---|---|
| `csia-v1.0-research-final` | `ec5acd18…` | yes | **no** |
| `csia-v2-phasec-frozen` | `50c5d357…` | yes, annotated | **no — push refused** |
| `csia-dual-paper-evidence-freeze` | `eb2577d6…` | yes, annotated, created at the pre-cleanup evidence HEAD | **no — push refused** |
| `v0.7.0` | `758f4ae5…` | yes | yes, pre-existing |

No tag was moved. `csia-dual-paper-evidence-freeze` did not previously exist;
`csia-v2-phasec-frozen` already pointed at `50c5d35` and was not altered.

### Tag push is BLOCKED, and it is an authorization limit

The branch pushed cleanly — `origin/claude/code-reviewer-repo-export-zicovg`
matches local HEAD. Both tag pushes fail with:

```
error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403
```

Four attempts with exponential backoff (2 s, 4 s, 8 s, 16 s) produced the same
403 every time, so this is not a transient network fault. The agent proxy
reports **zero** relay failures for any GitHub host, so it is not an egress
denial either: GitHub is refusing the ref creation. This session's credential
is scoped to push the designated branch and not to create tags.

**No workaround was attempted, and none should be.** The tags exist locally
with their full annotated messages, and both point at commits already present
on the remote branch, so nothing is lost — only the refs are missing.

**Remedy, for someone with tag-creation rights on the repository:**

```sh
git push origin refs/tags/csia-v2-phasec-frozen
git push origin refs/tags/csia-dual-paper-evidence-freeze
git push origin refs/tags/csia-v1.0-research-final   # also local-only
```

Alternatively, grant ref-creation to the session's GitHub App installation and
the same commands succeed unattended. Until then `docs/CURRENT_PROGRAM_STATE.md`
records the tag-to-commit mapping, and the commit SHAs are the durable record:
a tag can be moved, a SHA cannot.

## Freeze status

| | result |
|---|---|
| **frozen v1** | **PASS** — zero diff against `csia-v1.0-research-final`, checked twice (git diff, and SHA-256 per file) |
| **Phase C freeze** | **PASS** — every recorded artifact hash holds; the record still names commit `50c5d35` and its gate verdict matches the gate artifact |
| **dual-paper evidence freeze** | **PASS** — see the drift check below |

### The drift check that matters

```
git diff --stat csia-dual-paper-evidence-freeze HEAD \
    -- research engineering csia campaigns figures datasets
```

**Empty.** Not one byte changed under any directory that holds an algorithm, a
scenario, a threshold, a generated artifact, a proof output, a figure or a
dataset. Everything the finalization touched is documentation, tests, packaging
metadata and the two manuscripts' prose.

## Tests

| | pre-cleanup | post-cleanup |
|---|---|---|
| collected | 1683 | 1684 |
| result | all pass | all pass |

The one added test is `tests/test_program_state.py::test_the_program_state_names_the_three_canonical_freezes`,
which asserts the state document names each freeze tag together with its
commit SHA — a tag can be moved, a SHA cannot.

## Paper builds

| paper | build | pages | citations |
|---|---|---|---|
| CSIA Systems Paper I | **PASS** | 26 | all resolved |
| Posterior distortion / gate conditioning | **PASS** | 10 | all resolved |

Unchanged from the precheck. The build fails on any undefined citation or
reference, so "resolved" is enforced.

## Publication guards

| guard | pre | post |
|---|---|---|
| artifact maps | PASS | PASS |
| proof audit reproduces | PASS | PASS |
| figure bundles match `figures/` | PASS | PASS |
| Phase-I papers cite no Phase-II results | PASS | PASS |
| manuscript hard style rules | PASS | PASS |
| secrets scan | PASS | PASS |
| public release allowlist and sanitization | PASS | PASS |
| **blocking guards, aggregate** | **PASS** | **PASS** |
| bibliography guard | FAIL, expected | **FAIL, expected** |

## Bibliography status

**UNRESOLVED, and deliberately so.** 52 provenance markers remain across both
`refs.bib` files. No entry is marked verified. **No marker was deleted, edited
or retired during the finalization.**

Six verification routes were tested and all six fail at the proxy's CONNECT
with 403: `api.crossref.org`, `doi.org`, `dblp.org`, `api.openalex.org`,
`api.semanticscholar.org`, `export.arxiv.org`. The last three are
`rejected_routes` in the ledger and could not have retired a marker even on
success; they were checked so that "no route exists" is a measurement rather
than an assumption. That finding was added to
`papers/BIB_VERIFICATION_LEDGER.yaml`.

This is the binding constraint on both papers and it needs a human with
publisher access.

## Files removed

**None.** No document, artifact, script or record was deleted.

## Files moved

| from | to | why |
|---|---|---|
| `README.md` §§ "The real-time runtime", "Architecture", "Production properties", "Scenario results", "Hardware context", "Path to flight", "Known limitations", "Validation status" | `docs/RUNTIME_AND_ARCHITECTURE.md` | so the README reads in under two minutes. **Moved verbatim** — every number and caveat is byte-identical, and the pre-move state is at `csia-dual-paper-evidence-freeze` |

No load-bearing path moved. Paths cited by manifests, hashes, manuscripts,
artifact maps, tests and preregistrations were left where they are, including
the three root-level demo scripts, which are indexed instead.

## Files rewritten

| file | change |
|---|---|
| `README.md` | rewritten to ten sections; deep material relocated, not trimmed |
| `docs/CURRENT_PROGRAM_STATE.md` | new first screen; canonical tags with commits; blockers with owners; limitations with citations |
| `CLAIMS_INDEX.md` | said "four registers" over a ten-row table; scalar range and unmapped-literal count were stale |
| `docs/audit/WP_C6_REPORT.md` | one conversational fragment in a section heading |
| `papers/BIB_VERIFICATION_LEDGER.yaml` | records six tested routes instead of three |
| `.gitignore` | coverage and notebook-checkpoint rules |
| `Makefile`, `.github/workflows/publication.yml` | stale "(scaffold)" wording for the mathematical paper; new `proof-audit-check` guard wired into `BLOCKING_GUARDS` and CI |

## Files created

`docs/DOCUMENT_INDEX.md` · `docs/RUNTIME_AND_ARCHITECTURE.md` ·
`docs/REPOSITORY_FINALIZATION_PRECHECK.md` · this report ·
`papers/csia_systems/README.md` · `papers/gate_conditioning/README.md` ·
`tools/publication/proof_audit_check.py` ·
`tests/test_systems_paper_numeric_claims.py` ·
`tests/test_flight_truth_determinism.py` · `tests/test_package_lint.py` ·
`tests/test_support_state_posterior_range.py` ·
`research/math-paper/REVIEWER_RED_TEAM_MATH.md`

## Load-bearing files touched

| file | why it is load-bearing | what changed |
|---|---|---|
| `docs/CURRENT_PROGRAM_STATE.md` | `tests/test_program_state.py` resolves it | content, and the guard's token list was updated to the new header format. **The token set grew from 8 to 13**; nothing was dropped |
| `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` | `make artifact-map` | one scalar added (S13) binding a figure that was previously unbound and wrong |
| `papers/gate_conditioning/GATE_PAPER_ARTIFACT_MAP.yaml` | `make artifact-map` | two scalars added; one table entry moved to `scalars` where it belonged |
| `papers/*/main.tex` | both builds, both artifact maps | corrections listed under "Scientific results changed" below |
| `research/PROSE_NUMERIC_BINDINGS.yaml` | `tests/test_prose_numeric_bindings.py` | three bindings added (PB-30…PB-32) |
| `papers/BIB_VERIFICATION_LEDGER.yaml` | `tests/test_bib_verification_ledger.py` | a comment recording three further blocked routes. **No row's status changed** |

## Scientific results changed

# NO.

The `git diff` above is empty across every scientific directory. Three
manuscript figures were **corrected to match artifacts they already
disagreed with**, which is the opposite of changing a result:

| manuscript | printed | artifact | outcome |
|---|---|---|---|
| gate conditioning | "a leader above 0.999" as the support-rule threshold | no threshold exists; the rule is structural, and firing ticks run down to 0.9691 | corrected; both endpoints now bound and guarded |
| gate conditioning | `L_h` defined as the active-evidence likelihood | that reading makes P1, P2, P5 and P6 vacuous for the paper's own example | corrected with a new proposition (P7) and a new section; recorded in the red-team register |
| systems | `S_0(T_0 - T*) = 125` | artifact computes `118.82`; 125 appears in no artifact | corrected; bound as scalar S13 |

In each case the artifact was already right and the prose was wrong. No
artifact was regenerated to fit prose.

## Secret scan

**No credentials found.** No API keys, tokens, private keys, cookies, session
material or password assignments, tracked or untracked.

| finding | classification | action |
|---|---|---|
| the private username in `publication/system_paper_i/PUBLIC_RELEASE_MANIFEST.yaml` | **not a leak** — it is the `forbidden_patterns.private_username` rule the sanitization guard matches on. A rule against a string necessarily contains it | none. Deleting it would disable the guard |
| public archives | contain no manifest; both pass post-pack sanitization | none |
| the same username in **git history**, in a local machine path at `ac8d21d` and `bc3ed97` | **privacy disclosure, not a credential**; purged at HEAD | **history remediation NOT performed.** Removing it requires a rewrite that would invalidate every freeze tag and published SHA. Reported for the owner to decide |
| 24 remaining scan items | `/home/user`, the generic container path | already recorded in `HARNESS_RELEASE_AUDIT.md` |

## Known limitations

1. **Bibliography verification is unresolved** and blocks both papers.
2. **The public-log study has not run**; `SC-22` is `PROVISIONAL`.
3. **One prior-art reference could not be located**; no sharpness may be
   claimed for the TV bound until it is closed.
4. **One high-priority reference is unread** (arXiv:2405.15141).
5. **The mathematical paper's baseline is a counterfactual** and, in the
   measured case, not evaluable at all. The divergence results inherit this.
6. **No MAP-stability result exists for the pinned regime**, and P8 proves
   there cannot be one of P4's form.
7. **The implemented instance is n = 1.** Prevalence is not established.
8. **The private username remains reachable in git history.**
9. **`--strict-numbers` still reports 49 unmapped prose literals** in the
   systems paper. The most precise were audited by hand this session — one was
   wrong and is now bound — but the remainder are listed on every run for human
   review rather than individually bound.

## Next action

**FINAL SYSTEMS PAPER** and **FINAL MATHEMATICAL PAPER**.

The repository is ready for both. Every claim traces to a committed artifact;
every artifact regenerates from a committed script; every freeze is guarded;
the canonical state is recoverable from `docs/CURRENT_PROGRAM_STATE.md` without
conversation history. What neither paper can obtain here is a publisher record.
