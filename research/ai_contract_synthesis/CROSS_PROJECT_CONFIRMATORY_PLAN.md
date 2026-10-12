# Cross-project confirmatory plan

Items 35, 36. **Design and feasibility only. Not executed.**

## What is already available locally

Checked, not assumed:

| stack | path | status |
|---|---|---|
| ArduPilot | `/home/user/ardupilot/ardupilot` | full source tree, plus `modules/mavlink/message_definitions/v1.0/` |
| PX4 | `/home/user/px4` | full source tree, `msg/` uORB definitions, and its own copy of the MAVLink definitions |

So item 36's unseen-project test is **feasible without downloading
anything**, and item 35's "do not download a third codebase merely to
increase N" is easy to honour.

## The experiment worth running (item 36)

Design prompts on ArduPilot; point the miner at **PX4 uORB message
definitions** (`/home/user/px4/msg/*.msg`) with no manual contract; then
source-audit the output independently.

uORB is the right target for a specific reason: **it has no `invalid=`
attribute.** A `.msg` file declares types and names, and any not-measured
convention lives in comments, in the publisher, or nowhere. That removes C3
— Phase 1's only refuting check — and removes B0b, the baseline that wins
here.

So the PX4 experiment tests the one condition under which this architecture
could matter:

> when no machine-readable authority exists, does an AI miner beat nothing,
> and can anything contain its errors?

This package cannot answer that. It ran on the protocol that *does* carry the
attribute, and the answer there is that the attribute wins.

## Protocol sketch

1. Enumerate every field of every uORB topic `ulog_source.py` consumes.
   Mechanical, same rule as `enumerate_universe.py`.
2. Freeze the split and the pilot before generation, as here.
3. Conditions: B0a regex only (B0b is unavailable — that is the point), B1
   consumer source, B2 plus PX4 publisher source (the true producer-side
   authority, tier 2 rather than tier 1), B3 one verifier revision.
4. Reference: **from PX4 publisher source**, which is executable and
   independent of the consumer. This is a genuine tier-2 authority and a
   better reference than model judgement.
5. Score with the metrics frozen in `METRICS.md`, unchanged.

## What would make it interpretable, which this package is not

Independent annotators (`FUTURE_HUMAN_ANNOTATION_PROTOCOL.md`). Without them
the same limitation recurs: one model producing both predictions and
reference. The PX4 experiment improves on this package in one respect only —
the reference can be derived from executable publisher code rather than
judgement — and that is worth having.

## Honest expectation, recorded before running

Stated so it can be scored later: **B1 will abstain on most uORB fields, and
the few positives it produces will be recalled from training rather than
derived from the visible source.** That is what happened here on
`GPS_RAW_INT.epv`, and uORB gives the model *less* to work from, not more.

If that expectation holds, the direction is finished: the AI helps where an
authority already exists (and is redundant there), and cannot be trusted
where none does.
