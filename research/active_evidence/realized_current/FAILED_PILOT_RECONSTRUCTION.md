# The failed pilot — RECONSTRUCTED, NOT RECOVERED

**Status: `RECONSTRUCTED_NOT_RECOVERED`.** This file must not be cited as a
recovered original.

## Why it cannot be recovered

`git log -S "deficit ** 2 + coupling ** 2" -- tools/research/rcec_campaign.py`
returns nothing. The failing objective was written, run, and replaced within
uncommitted working state, so **the pilot artifact never existed as a file
and cannot be retrieved.** Committing only the repaired version was itself a
process failure: a defect that is fixed before the first commit leaves no
evidence, and the correction trail this repository requires then rests on
prose alone.

What is preserved instead is a deterministic reconstruction from the exact
wording of RC-3 in `COUNTEREXAMPLE_LOG.md`, re-run on the `diagnostic`
partition, recorded in `results/RCEC_DIAGNOSTICS.json` under
`optimizer.reconstructed_pilot_choice`.

## The three statements required, stated plainly

> **P3 produced zero certificates in the pilot.**

True of the pilot. **Not true of the committed state**, where P3 reports
`CERTIFIED_IN_MODEL` 50 times out of 50 in all three plant models. The
failure was found and repaired before the first artifact was written.

> **The original task metric reached its upper bound and was
> non-discriminating.**

True, and understated: it is floored at 0.00 for every arm at 0.005 ohm and
ceilinged at 1.00 for every arm at 0.020 and 0.040. Exactly one of four grid
points discriminates.

> **Passive performance changed when `effort_drift` was removed; the
> active/passive comparison is nuisance-model-dependent.**

True. Passive moves from 5 unresolved to 9 while every active arm stays at 6,
reversing the sign of the active advantage.

None of these is a successful result and none is reinterpreted as one.

## What the reconstruction shows

| | reconstructed pilot objective | repaired objective |
|---|---|---|
| chosen candidate | chirp, 2 A, 2 s | palindromic, 4 A, 8 s, 6 cycles |
| certifies | **no** | yes |
| binding condition | error budget | — |

Over all 120 grid candidates on the diagnostic partition:

| first binding condition | count |
|---|---|
| model mismatch / error budget | 76 |
| certified | 24 |
| excitation | 20 |

**The feasible set is not empty.** A witness exists and the repaired
objective finds it, so the pilot failure was **objective misspecification, a
form of optimizer failure** — not infeasibility, not prediction/realization
mismatch, not a certificate defect.

## Configuration of the reconstruction

| item | value |
|---|---|
| partition | `diagnostic`, seeds 11000–11700 |
| partition manifest SHA-256 | `e872d36f…5b6f65c2` |
| locked seeds read | **none**, original or amended |
| plant | `battery_1rc`, `SYNTHETIC_*` constants |
| candidate grid | `rcec_campaign.p3_candidates()`, 120 entries |
| artifact | `results/RCEC_DIAGNOSTICS.json` |

## What was not preserved, and is gone

The pilot's realized current traces, its per-seed certificate outputs, its
P0–P7 scores at that moment, and its optimizer trace. Those existed only in
terminal output. The reconstruction reproduces the *decision* the pilot made
and the fact that it does not certify; it does not reproduce the pilot's
numbers, and no number in this file should be read as one of them.
