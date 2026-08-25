# HANDOFF — shared-branch state for the other CSIA agent

**Read this after you `git pull` on `main`.** Two agents work this repo; this
note keeps you both on the same page.

## Branch model (as of merge commit `c3016ca`)

- **`main` is the single shared branch.** Both agents work here now.
- `main` already contains **everything from both sessions**:
  - the code-review/integration line (former branch
    `claude/code-reviewer-repo-export-zicovg`) — verified fully contained;
  - the white-paper/research line (`research/wp_e1`);
  - PR #13 (assurance observability, identifiability repair, SITL-measured
    detection limits).
- The old feature branches are superseded by `main`. Don't keep committing to
  them — they'll re-diverge. Use `main`.

## Workflow so both agents always see each other's work

1. **Before starting:** `git fetch origin && git pull` on `main`.
2. **When done:** commit and `git push`. Only committed-and-pushed work is
   visible to the other agent — uncommitted changes are private to your
   checkout.
3. If `push` is rejected ("remote contains work you don't have"), the other
   agent pushed first: `git pull --rebase` (or `git pull`) then push again.

## What this session (code-review/integration line) contributed

Consolidated into `main`; highlights already present:
- `csia/seeker/` interceptor_seeker profile + `tools/interceptor_montecarlo.py`,
  `tools/interceptor_plots.py`, `tests/scenarios/test_seeker_scenarios.py`.
- `deliverables/` white-paper handoff set (`HANDOFF_WHITEPAPER.md`,
  `montecarlo_results.{md,json}`, `trust_graph_catalog.md`,
  `failsafe_transitions.md`, `license_audit.md`, `SUMMARY.md`, plots).
- Native C core (`csia/native/`), validation campaigns (`csia/validation.py`),
  docs (`ARCHITECTURE_REVIEW.md`, `ORG_BLUEPRINT.md`, `COMMERCIALIZATION.md`).

## Known external item (NOT in this repo — do not "fix" here)

`andrefp-co/swort` **PR #2** (the public website repo) adds this repo as a
private git submodule. Its Cloudflare Pages check fails because Cloudflare
can't clone a private submodule, and merging it would break the live site.
**Decision: close PR #2, do not merge.** All the CSIA work lives here in
`csia-trust-layer` — the website PR is redundant. This is a website-repo
action, unrelated to anything on `main`.

## Quick sanity check after pulling

```sh
python -m pytest -q            # full suite
csia report                   # scenario detection/diagnosis summary
```
