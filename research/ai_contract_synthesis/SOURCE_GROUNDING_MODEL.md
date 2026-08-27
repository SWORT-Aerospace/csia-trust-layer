# Source grounding, and the precedence hierarchy

Items 13, 27, 29. What "supported" means here, mechanically.

## The grounding check is a TEXT check

`verification/grounding.py` answers one question per citation:

> does the quoted text exist at the cited locator?

Locator forms: `path/file.py:123`, `path/file.py:120-130`, and
`common.xml:MESSAGE.field` for a protocol schema field definition. Comparison
is whitespace-normalised, so a citation matches the text rather than the
indentation it was printed with.

**A grounded clause is not a true clause.** A comment can be quoted perfectly
and still be false. That is why Phase 1 does not stop here.

## Why a clause carries a `quote` and not just a line number

A line number alone drifts silently: the file changes, the number still
resolves, and the citation now points at something else. Requiring the text
makes the citation self-checking, and a test re-runs every citation so a
later edit to the adapter cannot leave a stale reference in a committed
result.

## Precedence (item 27)

Higher outranks lower. This hierarchy is **not invented casually** — it is
the one the previous package's contracts already used implicitly, written
down.

| tier | source | why it is where it is |
|---|---|---|
| 1 | authoritative protocol / schema field definition | the producer and consumer both agreed to it |
| 2 | executable producer semantics | what actually fills the field |
| 3 | executable consumer semantics | what actually reads it |
| 4 | tests | executable, but only over the cases someone wrote |
| 5 | structured internal specification | e.g. `CHANNEL_SEMANTICS.yaml` — reviewed, but local |
| 6 | comments | frequently true, never checked |
| 7 | prose documentation | may describe a version that no longer exists |

**Conflicts are recorded, never resolved by preference for the interesting
reading.** When sources disagree the status is `CONTRACT_AMBIGUOUS`
(item 27), and `SCALED_PRESSURE.press_abs` is a real instance in this
package's own pilot: the consumer's `p > 0` guard is consistent both with a
protocol sentinel of 0 and with a plausibility check the consumer invented,
and consumer source alone cannot separate them.

## The five Phase-1 checks beyond grounding

`verification/containment.py`. Each is deterministic and each can be read in
about twenty lines.

| check | question | catches |
|---|---|---|
| **C2** executable corroboration | does an executable line actually *test* the claimed condition? | a rule that exists only in a comment |
| **C3** schema contradiction | does the authoritative `invalid=` attribute disagree? | an invented sentinel, and a wrong one |
| **C4** reachability | does any executable line read the field at all? | a rule no trace can exercise |
| **C5** internal contradiction | do two decoders read the same field in opposite senses? | a confident answer to an underdetermined question |
| **C6** effect corroboration | if the clause claims a DISCARD, is a discard visible near the citation? | a real condition with an invented consequence |

**C3 is the strong one, and it only exists because MAVLink happens to carry a
machine-readable sentinel attribute.** For a protocol without one, C3 is
unavailable and Phase 1 loses its only authoritative contradiction check.
That is the single most important limitation of this architecture and it is
stated here rather than in a footnote.

## Two ways C2 was fooled, before it was fixed

Both by the fixtures it exists to catch, and both are kept on the record
(`FREEZE_AMENDMENTS.json`, `CLAIM_LEDGER.json`):

1. `FLOW_QUALITY_UNKNOWN = 255` — a constant **definition** counted as a
   test. C2 now requires the literal to appear in a comparison or a branch.
2. `weight = 1.0 if msg["valid"] else 0.25` — the `0` inside the float
   `0.25` matched a claimed comparison against zero. Integer literals are now
   matched with a boundary that rejects decimals.

A checker that its own author had to correct twice, against tests that same
author wrote, is not evidence of robustness on unseen input. It is evidence
that this class of check is *writable*.

## What grounding cannot do

* It cannot tell a true clause from a false one that is faithfully cited.
* It cannot detect a *missing* clause. A miner that says nothing is perfectly
  grounded.
* It cannot rank. Precedence orders evidence, but where the only evidence is
  tier 6, the status is ambiguous rather than weak-but-accepted.
* It cannot substitute for a person. Nothing in this package reaches
  `HUMAN_REVIEWED`.
