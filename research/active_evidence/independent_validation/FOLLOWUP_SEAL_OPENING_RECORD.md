# Seal Opening Record — the paired-design follow-up

**GENERATED** by `tools/research/iv_followup_seal_record.py`. Every
value below is measured at run time; none is typed. The script
refuses to write if the working tree is dirty or the recorded suite
did not exit zero, so a record that exists is a record of a known
state.

This is the follow-up's own seal, on its own partition. **Phase
one's sealed partition is not reopened** and is not touched by this.

| field | value |
|---|---|
| opened at (UTC) | `2026-09-14T02:38:30Z` |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| HEAD | `32fb924637c2aca76f5e6d273db31eb09254db34` |
| working tree | clean, 0 dirty paths |
| recorded suite | `seal_suite2.txt`, 3545 tests, `PYTEST_EXIT=0` |
| frozen-core digest | `b0b011c61426a70ead42e170855a2650d5c62feb640c7a50fffc27bb915ba5a8`, 12/12 files re-hashed and matching |
| phase-one partition manifest | `b293e30f30a767c13b29d1abfa9ac4c3bdc49580f3224d037252513801786731`, untouched |
| follow-up partition manifest | `b6af853781b62631dde39c5b0c83a623a3c3c458d7936d10ac2ccb8218702515` |
| follow-up sealed partition | `final`, 24 seeds |
| follow-up validation artifact | `838a4f454c937252…`, 19008 rows |

## What the follow-up's seal protects

Twenty-four seeds drawn in a domain of their own, asserted at import
to be disjoint from every phase-one seed and from every companion
baseline seed. They have never been simulated. The design they run
is frozen by `PREREGISTRATION_AMENDMENT_4.md` and
`PREREGISTRATION_AMENDMENT_5.md`, both committed before this record.

## How it is opened

`csia_independent_validation.followup_partitions.seeds` raises
`PermissionError` for `final` unless the caller passes
`i_am_opening_the_sealed_partition=True`. One call site does, in
`tools/research/iv_followup_campaign.py`, reached only by
`--open-the-seal`. Both are one grep away.

## What opening it does not license

Nothing. It is a confirmatory run of a design frozen before it was
opened. It cannot change a hypothesis, a metric, a threshold or an
arm. If its results disagree with validation, that disagreement is
the result and is reported as one.

It does not license a novelty claim, a certification claim, an
airworthiness claim or a promotion. It runs three plants in a
simulator against a synthetic pack.
