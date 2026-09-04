# CLAIM DENSITY AUDIT

Peer-review hardening campaign, §29.

**The premise.** A referee needs to break *one* claim to reject. So every
claim a paper makes that the story does not need is attack surface bought for
nothing. This measures how much of that each paper is carrying, and decides
what to do about it.

Measured 2026-09-04: systems paper 27 pages / 26 claims; mathematical paper
12 pages / 15 propositions.

---

## 1. Systems paper — 26 claims over 27 pages

Classification from `research/systems-paper/MAIN_STORY_AUDIT.md`.

| role | count | share | attack surface |
|---|---|---|---|
| `CORE` | 12 | 46% | **necessary.** Breaking one of these breaks the paper, which is what a core claim is for |
| `SUPPORTING` | 7 | 27% | necessary-ish. Each defends a specific objection a referee raises anyway; removing one does not shrink the surface, it opens a gap |
| `SUPPLEMENT_CANDIDATE` | 2 | 8% | **bought for nothing.** SC-07 and SC-08, the smoothing sensitivity study |
| `HISTORICAL_ONLY` | 5 | 19% | **negative surface.** Four are `REFUTED`/`WITHDRAWN` and one is `NOT RUN`; each appears under that label |

**Density: 0.96 claims per page.** For a measurement paper that is not high.

### 1.1 The two claims that cost more than they earn

`SC-07` (smoothing changes threshold-crossing behaviour, direction and size
depending on the arm) and `SC-08` (36→9 crossings of 374 in the pre-onset
window) live in the generator-dependent sensitivity study — the largest
section in the paper at 12.5% of the source, and the least load-bearing per
page.

**No CORE claim depends on either.** They are real results and they are
genuinely interesting; they are also two more numbers a referee can attack, in
a section that is explicitly generator-dependent — which is to say, the
section where an attack is easiest.

**Decision: keep, do not cut here.** Cutting is a venue decision, the cut order
is already fixed in `MAIN_STORY_AUDIT.md` §4, and removing a real measured
result to reduce attack surface is optimising for the referee rather than for
the record. **But they are first in the cut order and this is why.**

### 1.2 The five `HISTORICAL_ONLY` claims reduce the surface

Counter-intuitively, the refuted claims make the paper *harder* to reject, not
easier. A claim table containing

> *"A single exposure quantity suffices — **REFUTED by our own measurement.**
> It attributed the largest exposure to the wrong mechanism"*

removes an entire line of attack, because the attack has already been made and
answered by the authors. The same for the WP-C8 mass-invariance "theorem", for
R16 slow-IMU-bias detection, for "the campaign varied two axes", and for the
irreparability containment that is `NOT ESTABLISHED and not claimed`.

**Rule extracted: a refuted claim reported under its own label is negative
attack surface. A refuted claim quietly dropped is positive attack surface,
because the referee finds the gap and wonders what else went.**

### 1.3 The one claim that must never be promoted

`SC-22`, the public-log exposure study. Artifact field: `NONE - NOT RUN`. It
is the single most attractive thing a referee could ask for and therefore the
easiest claim to imply by accident. The manuscript's only sentence about it is
`UNMEASURED. No real logs are reachable and the corpus carries no labels`, and
that must stay the only one.

## 2. Mathematical paper — 15 propositions over 12 pages

**Density: 1.25 propositions per page.** Higher than the systems paper, and
this is where the honest analysis gets uncomfortable.

| | count | note |
|---|---|---|
| labelled **KNOWN** | **15 of 15** | every one. `NOVELTY_AUDIT.md` §3 |
| load-bearing for the paper's actual claim | 6 | P1, P2, P7, P7b, P7c, C3 |
| defensive (they exist to close a hole a referee would find) | 4 | P8, P6c, and the two divergence identities P5a/P5b in their stated-as-known form |
| completeness only | 5 | P3, C2, P4, P6a, P6b |

### 2.1 Does the density hurt?

**Less than it looks, and for a specific reason: a KNOWN proposition is not
attack surface.** A referee cannot reject a paper for a correct one-line
consequence of self-normalised importance weighting that the paper itself
labels KNOWN and attributes. There is nothing to break — the propositions are
verified symbolically and numerically (`proof_audit.json`, worst deviations at
the $10^{-15}$ level or better), and their novelty is conceded in advance.

**Where density *does* hurt is comprehension, not defensibility.** Fifteen
propositions in twelve pages is dense reading for a paper whose actual claim is
one structural condition and one measured instance.

### 2.2 The two propositions that earn the most per line

`P7c` — every distinguishing feature gated implies the pair is pinned to the
prior — because it, and not P3, is the statement the implemented case actually
satisfies. And `P8` — a pinned pair with equal prior mass always has
$\Delta \le R$, so P4 can never certify it — because it is a **negative**
result about our own sufficient condition, found and reported by us.

P8 is the clearest example of the rule from §1.2 applied to mathematics: a
proposition whose content is *"our other proposition cannot help here"* removes
attack surface rather than adding it.

### 2.3 Decision

**No proposition is dropped.** The compression plan
(`research/math-paper/EXPOSITION_COMPRESSION_PLAN.md`) ranks P5a/P5b's *proofs*
and P6c's *narrative* as compressible if a page limit forces it — the
statements stay. Deleting a proposition and keeping the exposition that
depends on it would leave a gap; deleting the exposition and keeping the
proposition leaves a shorter paper that says the same things.

## 3. Cross-paper: is anything claimed twice?

Yes, once, and deliberately: the implemented instance — 200 consecutive ticks,
378,000 of 378,000 checker agreements — appears in both. The mathematical
paper needs it as the measured instance of its structural condition; the
systems paper needs it as its independent verification.

`research/PAPER_CROSS_CONSISTENCY.md` fixes the shared terms so the two
renderings cannot drift, `research/PROSE_NUMERIC_BINDINGS.yaml` binds the
number in both documents, and `FINAL_HOSTILE_REVIEW_MATH.md` M9 records the
fair objection that the mathematical paper's empirical content is borrowed.
**Shared, disclosed, and bound — not double-counted.**

## 4. Verdict

| | |
|---|---|
| systems paper | **0.96 claims/page, 46% core, 19% self-refuting.** Defensible. Two claims are surplus and they are first in the cut order |
| mathematical paper | **1.25 propositions/page, 100% conceded KNOWN.** Dense to read, but a conceded proposition is not attack surface. No cut |
| the real surface | not the count. It is `SC-22` (must never be promoted), the unverified bibliography, and the $n=1$ current-stack replication — all three disclosed, all three tracked |

**Nothing is removed by this audit.** Its output is the ordering, and the
finding that the papers' attack surface is concentrated in three disclosed
blockers rather than spread across the claim count.
