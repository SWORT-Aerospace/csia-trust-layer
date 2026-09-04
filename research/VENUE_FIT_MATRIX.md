# VENUE FIT MATRIX

Peer-review hardening campaign, §28.

> **THIS DOCUMENT IS EDITORIAL JUDGEMENT, NOT VERIFIED FACT.** No venue's
> current scope statement, page limit, deadline or review policy was fetched:
> publisher and conference hosts are blocked from this environment, the same
> blockage recorded in `papers/BIB_VERIFICATION_LEDGER.yaml`. **Nothing below
> may be treated as a citable statement about any venue.** Every named venue
> is a *category exemplar* — check its actual call before submitting anywhere.
>
> What this document does contain, and what it is for: a mapping from each
> paper's **surviving objections** to the venue characteristics that would
> amplify or neutralise them. That mapping follows from the two hostile
> reviews, which are internal evidence, and it is the part worth having.

---

## 0. The framing question

Both hostile reviews end the same way: the remaining route to rejection is a
judgement about **significance and fit**, not an error. So the question is not
"how do we make the papers stronger" — that work is done — but "which kind of
venue is being asked the question these papers actually answer?"

| paper | the question it answers |
|---|---|
| systems | *what does a deployed diagnostic layer emit when it holds no applicable evidence, how long does it do it for, and what does the fix cost?* |
| math | *when is a runtime validity gate's coarsening ignorable, and is that decidable before the system runs?* |

## 1. Systems paper — objection-to-venue mapping

Surviving objections, from `FINAL_HOSTILE_REVIEW_SYSTEMS.md`: R1 (a defect in
our own software), R2 (2015 simulator), R3 (no real flight data), R6 (no harm
demonstrated).

| venue character | R1 | R2/R3 | R6 | net |
|---|---|---|---|---|
| **Dependability / safety engineering** (DSN, SAFECOMP, ISSRE as exemplars) — rewards measured failure modes in real systems and checkable design rules | **neutralised.** "A defect in a deployed layer, measured, with a rule" is the genre | amplified: these venues expect field or at least current-platform evidence | tolerated; hazard analysis is normally separate | **best fit** |
| **Runtime verification / formal methods** (RV as exemplar) — rewards decidable properties checkable before execution | partly neutralised: the static-checkability result is the contribution | mostly irrelevant; the property is static | irrelevant | **good fit for the pair**, weaker for the systems paper alone |
| **Robotics** (ICRA / IROS as exemplars) — rewards demonstrated capability on hardware | amplified: no capability is demonstrated | strongly amplified: SITL only | strongly amplified | **poor fit** |
| **Aerospace / UAV systems** — rewards flight evidence and operational relevance | amplified | strongly amplified: a 2015 build reads as stale here | strongly amplified: "no harm" is close to fatal | **poor fit until real-flight data exists** |
| **Workshop or short-paper track** — rewards a sharp negative result with an honest scope | neutralised | tolerated | tolerated | **strong fit, and the natural fallback** |

**Recommendation (judgement).** Dependability/safety first; workshop track as
the deliberate fallback rather than as a consolation. Robotics and aerospace
venues should not be attempted until either a real-flight corpus or an $n>1$
current-stack campaign exists — R2, R3 and R6 compound there rather than
cancel.

**What would move the systems paper up a tier**, in order of cost:

1. Run the public-log exposure study (SC-22). It needs egress, not new science.
   Closes R3 in part and is the single highest-value missing experiment.
2. Raise the current-stack self-occlusion replication above $n=1$. The
   apparatus exists, the preregistration exists, both platforms are wired.
   Closes R2.
3. A second implementation exhibiting the pattern. Closes R1 — and this is the
   only one that would change the paper's claim rather than its evidence, so it
   is also the one to be most careful about.

## 2. Mathematical paper — objection-to-venue mapping

Surviving objections, from `FINAL_HOSTILE_REVIEW_MATH.md`: M1 (no theorem),
M5 (the decision rule is subsumed), M6 (the setting is examined elsewhere),
M7 (prior art unread).

| venue character | M1 | M5/M6 | net |
|---|---|---|---|
| **A mathematics or statistics venue** | **fatal.** Every proposition is KNOWN and the paper says so | fatal in combination | **do not submit** |
| **Runtime verification / formal methods** — rewards a decidable property and its implemented instance | neutralised: no theorem is expected; the contribution is the static condition | tolerated if conceded, which it is | **best fit** |
| **Missing-data / statistical methodology** | fatal | fatal: this is precisely the literature that owns the setting | **do not submit** |
| **Companion technical note alongside the systems paper** (same venue, or an appendix/report) | neutralised: it is the systems paper's algebra, stated once and properly | neutralised | **strong fit, and arguably the honest one** |
| **arXiv-only technical report** | neutralised | neutralised | **the zero-risk baseline**, and it costs nothing to do first |

**Recommendation (judgement).** The mathematical paper is a **companion**, not
a standalone mathematics submission. Its own novelty audit says every
proposition is KNOWN; submitting it where novelty is the currency is asking for
a rejection the paper has already conceded in writing.

The two viable routes are: (a) a runtime-verification venue, where
"statically decidable from a configuration file, with a deployed layer that
fails it" is the contribution; or (b) alongside the systems paper, where it
does the job it was written for — making the systems paper's structural claim
exact.

## 3. What must NOT be done to improve fit

* **Do not manufacture a theorem.** A known theorem is acceptable; an
  unsupported novelty claim is not. Any new proposition would have to survive
  `NOVELTY_AUDIT.md`, and there is no reason to expect it would.
* **Do not drop the limitations to look stronger for a harder venue.** Both
  compression plans mark them do-not-cut, and a limitation a referee has to
  find is a limitation the paper is hiding.
* **Do not split the pair to hide M9.** The mathematical paper's empirical
  content is shared with the systems paper. Presenting it as independent would
  be a misrepresentation, and `research/PAPER_CROSS_CONSISTENCY.md` exists so
  the two can be read together without collision.
* **Do not submit anywhere while `make bib-guard` is red.** Zero entries are
  verified, and three entries were found to carry wrong metadata. That is a
  blocker in both papers — R8 and M7 — and it is one person's afternoon.

## 4. Sequencing

1. Clear the bibliography (`papers/BIB_EXTERNAL_VERIFICATION_PACKET.md`). It
   blocks everything and needs no new science.
2. Post both as technical reports. Zero risk, establishes the record, and the
   evidence capsules make them independently checkable.
3. Systems paper to a dependability/safety venue; mathematical paper as its
   companion or to a runtime-verification venue.
4. Only then consider whether experiments 1–3 of §1 are worth running for a
   higher tier — and that is a programme decision, not a paper decision.
