# Seal Opening Record

The sealed final partition is opened **once**. This is the record of the state
it was opened from, written before the run started.

| field | value |
|---|---|
| opened at (UTC) | `2026-09-13T23:14:08Z` |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| HEAD | `81aa415afe47b79db9e9c0b5baa324ae3af580c3` |
| working tree | clean, 0 dirty paths |
| full test suite | 3454 collected, `PYTEST_EXIT=0`, run twice on this exact tree |
| blocking guards | **PASS** |
| advisory guards | FAIL — 53 pre-existing bibliography markers, unchanged by this phase, needing a human with an outside source |
| frozen-core digest | `b0b011c61426a70ead42e170855a2650d5c62feb640c7a50fffc27bb915ba5a8`, 12/12 files |
| prior sealed-partition manifest | `e872d36fb3a9337704c18290e1b8ec0452d295c416eef0ba58a8b97c5b6f65c2`, untouched |
| this phase's partition manifest | `b293e30f30a767c13b29d1abfa9ac4c3bdc49580f3224d037252513801786731` |

## The ten conditions

`PREREGISTRATION.md` §6 lists ten. `tools/research/iv_gate_check.py` checks
each mechanically and exits non-zero if any fails. At the moment of opening it
reported **every mechanically checkable condition passing**:

1. controls present and passing — four development artifacts, each with its own
   positive and negative controls;
2. plant independence demonstrated — 48/48 cells identical on `M_R^cert`, 1/48
   on the outcome error;
3. P7b ceiling invariant on development **and** validation — both oracles,
   both losses, zero violations;
4. no truth leakage possible — Layer A import closure clean;
5. primary interaction statistic frozen — `I_s`;
6. accuracy and coverage requirements frozen — `τ_rel = 0.5`, `τ_abs = 0.002`,
   coverage 0.90;
7. full-scale validation run completed — 41 472 rows, 117 627 plant runs;
8. working tree clean;
9. full tests and guards pass — recorded above;
10. frozen-core digests match.

## How it is opened

`csia_independent_validation.partitions.seeds` raises `PermissionError` for the
`final` partition unless the caller passes
`i_am_opening_the_sealed_partition=True`. There is exactly one call site that
does, in `tools/research/iv_campaign.py`, reached only by the
`--open-the-seal` flag. Both are one grep away for anybody auditing this.

## What opening it does not license

Nothing. The final partition is a confirmatory run of a design frozen before it
was opened. It cannot change a hypothesis, a metric, a threshold or an arm, and
if its results disagree with validation that disagreement is the result.
