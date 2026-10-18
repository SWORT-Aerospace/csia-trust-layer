# Assurance under conflicting semantic authorities — Stage 0

**Verdict: `ENGINEERING_INCONSISTENCY_ONLY`. Novelty: NOT ESTABLISHED.**
Read `CHATGPT_REVIEW_REPORT.md`.

## The question, and what happened to it

The hypothesis: protocol, producer, consumer and runtime semantics need not
agree, so an assurance layer must reason about which authority to believe.

**The authorities do not disagree.** Zero `SPEC_VS_PRODUCER` conflicts across
three cases. MAVLink declares `invalid="-1"` for `current_battery`; ArduPilot
writes exactly `-1` when it has no current (`GCS_Common.cpp:390-393`). Where
they look like they differ, the higher authority is **silent**.

All 17 counted conflicts are consumer-side — 8 `CROSS_CONSUMER`,
6 `PRODUCER_VS_CONSUMER`, 3 `SPEC_VS_CONSUMER`. Three decoders disagreeing
with an authority that speaks with one voice is not semantic uncertainty; it
is three bugs.

**And none of it reaches an action.** 0 of 9 authority pairs. The failsafe
issues the same action set whichever consumer is used.

| level | battery | GNSS | mag |
|---|---|---|---|
| VALUE | 3 ambiguous | *confounded* | *confounded* |
| STATE | 2 ambiguous | 2 ambiguous | 2 ambiguous |
| EVIDENCE | **robust** | 2 ambiguous | 2 ambiguous |
| DIAGNOSIS | *confounded* | *confounded* | *confounded* |
| ASSURANCE | **robust** | 2 ambiguous | **robust** |
| ACTION | **robust** | **robust** | **robust** |

## The distinction the brief did not anticipate

`CONFLICT` is not the same as `UNDERSPECIFICATION`.

The MAVLink schema says **nothing** about what `lat/lon/alt` hold when
`fix_type < 3`, and nothing about an all-zero magnetometer triple. The three
consumers each make a different choice there — and each is *licensed*, because
no rule was broken. Seven authority pairs are underspecification, not
disagreement. **Nobody is wrong because nobody said.**

That residue is a gap in a standard, worth reporting to the MAVLink
community. It is not a research direction.

## Baselines

| baseline | resolves |
|---|---|
| B0 SPEC_FIRST | **2/3** — fails only where the spec is silent |
| B1 IMPLEMENTATION_FIRST | 2/3 — identical answer to B0 on the battery |
| B2 OBSERVATION_FIRST | **0/3** — three runtimes, three answers |
| B3 SET_VALUED | flags ambiguity at upstream levels; **0/3** reach ACTION |

## Running it

```bash
make authority-table        # 16 authorities, every citation re-read from disk
make authority-conflicts    # conflict vs underspecification vs agreement
make authority-sensitivity  # F at six levels, with a null control
make authority-baselines    # B0/B1/B2/B3
make semantic-authority     # all four
```

## Corrections kept on the record

* Two category errors of mine inflated the conflict count before they were
  caught: pooling an authority about a *different raw state*, and comparing
  authorities about *different aspects* of one state. The headline "zero
  `SPEC_VS_PRODUCER`" exists only after correcting a classifier that had
  manufactured one.
* The citation verifier caught five bad citations in its first run, including
  one of my own line numbers.
* The null control disqualified the DIAGNOSIS level in all three cases — the
  level that would otherwise have looked most like a semantic finding.

## Not done

No fixes applied (item 51 keeps the branch pre-fix), no physical HIL (no
hardware), no exploit tooling (item 48), no PX4 producer reading, no
ambiguity-exposure integral — with one word per case there is no time series
to integrate and a number from three points would be decoration.
