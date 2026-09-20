# Consequence phase — status by phase

**This phase is not complete, and this file says which parts are not.** The
preregistration defines nine phases; eight have been executed. The rest are
listed with what they require, not with a partial result standing in for them.

| phase | state | evidence level reached |
|---|---|---|
| 0 — repository and lineage audit | **DONE** | measured |
| 1 — preregistration | **DONE**, committed before any result | n/a |
| 2 — uncovered-occlusion enumeration | **DONE** | `SOURCE_ANALYSIS` |
| 3 — closed-loop consequence simulation | **DONE** | `MODEL_BASED_ACTION_CONSEQUENCE` |
| 3.1 — actionability precondition | **DONE** | `MODEL_BASED_ACTION_CONSEQUENCE` |
| 3.2 — direct preregistered H2 test | **DONE** | `MODEL_BASED_ACTION_CONSEQUENCE` |
| 4 — detector delay/false-alarm curves | **NOT RUN** | — |
| 5 — explicit support output | **DONE** (classifier + tests) | `DETERMINISTIC_SIMULATION` |
| 6 — cross-architecture audit | **DONE** | `SOURCE_ANALYSIS` |
| 7 — CSIA-Lite reference implementation | **DONE** | `DETERMINISTIC_SIMULATION` |
| 8 — artifacts and claim discipline | **DONE** | n/a |
| 9 — verification | **DONE for what exists** | measured |

## Why phase 4 is not run rather than partially run

It needs a campaign over the preregistered seed partitions, and a campaign
produces numbers. A thin version would produce numbers too, and they would be
indistinguishable in a table from real ones. The preregistration fixes the
design; running it is the next work item, not this one.

Phase 4 carries a binding constraint — comparison against CUSUM
only at **matched false-alarm operating points**, over a preregistered
threshold grid. A single hand-picked threshold against another is forbidden
there in as many words, so a quick version of phase 4 is not a smaller phase 4;
it is a violation of the preregistration.

**No hypothesis has been tested at a level above `SOURCE_ANALYSIS`.** H1 has
an enumeration consistent with it, which is not a test: H1 as written also
requires that no independent freshness path forces an equivalent warning, and
that clause is established from source structure only. H5 has been addressed
and is **not killed** — twelve PX4/ArduPilot paths were classified, which is
what H5 asked for — but H5 was written so that classification is the whole
test, and it predicts nothing. H6 has been addressed and is **not killed**:
both mechanisms reproduce in `csia_lite` and a fresh interpreter importing it
loads no `csia` module, with the author-independence limit stated in
`CSIA_LITE.md` rather than glossed. **H2, H3 and H4 are untouched.**

## Phase 6 was recorded as blocked, and that was wrong

**Correction, kept rather than edited away.** An earlier version of this file
said:

> No PX4 or ArduPilot source tree exists in this environment. `find` over the
> repository returns prior audit *documents* ... but no source to audit.

Both trees were in the container the whole time, outside the CSIA repository,
at `/home/user/px4` (PX4-Autopilot `547e2caa`) and
`/home/user/ardupilot/ardupilot` (ArduPilot `01a504b4`). The search ran over
the **repository** and the conclusion was stated about the **environment**.
The scope of the search was narrower than the scope of the claim.

That is the same failure mode this phase exists to study, committed by the
phase, and it was caught only because a later step tried to attach the source
trees and found they were already there. It stays in the record because a
correction that leaves no trace teaches nothing.

Phase 6 has now run: `research/consequence/CROSSARCH_AUDIT.md` and
`results/CROSSARCH_AUDIT.json`, twelve paths across two stacks in one
subsystem family, all at `SOURCE_ANALYSIS`. **H5 is not killed.** No
prevalence and no universality may be drawn from it, and one of the twelve is
an ArduPilot source comment stating the mechanism outright — which is evidence
against novelty, not for it.

## What may be said about this phase today

That the gate inventory exists, that two independent derivations agree on eight
uncovered candidates, that a support classifier exists and behaves as its tests
describe, that twelve hand-read paths in PX4 and ArduPilot show the same
structure at `SOURCE_ANALYSIS`, and that a standard-library reimplementation
reproduces both mechanisms without importing CSIA.

Nothing about consequence. Nothing about detector performance. Nothing about
prevalence in either autopilot. Nothing about runtime behaviour in either
autopilot — none of it was executed. Nothing about hardware.
