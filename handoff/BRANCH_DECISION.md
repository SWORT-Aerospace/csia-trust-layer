# Canonical working branch

**Decision, 2026-09-06:** `claude/code-reviewer-repo-export-zicovg` is the
single canonical branch for this work. All subsequent commits go there.

## Why this one

It is the branch this session was instructed to develop on. The alternative,
`paper/physical-validation-and-vehicle-adapter`, carried the prior session's
work because that session continued from it.

## How the two were reconciled

They were **not** merged, and nothing was rewritten. At the point of decision
both refs pointed at the identical commit `c87a325`: the physical-validation
branch had been pushed there, and the designated branch had been
**fast-forwarded** to the same commit (`caa2aa1..c87a325`, a clean
fast-forward — the designated branch's tip was an ancestor).

So there is no divergence to resolve and no history to reconcile. The two names
describe the same commit; one of them is now the one that moves.

## Status of the other name

`paper/physical-validation-and-vehicle-adapter` is **frozen at `c87a325`** and
is not advanced further. It is left in place rather than deleted because
commits and documents written before this decision refer to it by name, and a
dangling reference in the record is worse than a stale branch.

**Do not commit to it.** If it ever needs to move again, that is a new
decision and it gets recorded here.
