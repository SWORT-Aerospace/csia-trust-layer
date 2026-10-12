# research/frontier_selection — Stage R0.2

**Top-down open-problem search → prior-art reduction → assumption audit →
formal opportunity → experimental kill test → one selected research frontier.**

Base commit `76eaa17`. Search date 2026-09-01.

**No implementation.** Item 36 forbids it and none was done: no detector, no
CSIA modification, no threshold change, no scored experiment data, no new
production class, no campaign. Nothing under `csia/` was touched. No existing
research package was modified.

---

## Read this first

> **Zero full texts were read.** Every scholarly host is blocked by this
> environment's egress proxy — arXiv, ACM, Springer, IEEE, ScienceDirect,
> Semantic Scholar, OpenAlex, Crossref, NTRS, CORE, all of them. All 90
> indexed sources are `PARTIAL_SOURCE_ONLY`. Item 3's fallback applies to
> every one of them, so **no candidate can be called novel out of this stage**
> and none is. The selected candidate's status is `PROVISIONAL` and its Stage-0
> prompt opens with a full-text gate rather than an experiment.
>
> Full evidence for the block, and what it costs: `SEARCH_PROTOCOL.md` §0.

---

## Result in three lines

- **Nine of nine required candidate families reduce to an established
  abstraction** that the search surfaced by name. That is the main finding.
- **Selected: candidate B** — runtime collapse of effective evidence
  independence at an assurance monitor's input. Weighted frontier score 5.900,
  highest of twelve.
- **Its formal content is a corollary of Menger's theorem**, and this package
  says so rather than dressing it up. What could survive is narrow: a runtime,
  source-derived, per-verdict count of distinct upstream sources, and the
  measured fact of whether it collapses in flight without anything noticing.

---

## Files

| file | what it is |
|---|---|
| `SEARCH_PROTOCOL.md` | **read first.** Date, engines, all 36 queries verbatim, inclusion/exclusion criteria, screening counts, and the full-text block that governs everything |
| `LITERATURE_FRONTIER_MAP.md` | saturated areas, the active frontier, where open assumptions cluster, and the estimate-vs-test boundary the selection turns on |
| `PRIMARY_SOURCE_INDEX.csv` | 90 sources, `S001`–`S090`, every row `full_text_read=NO`, `source_depth=SNIPPET_ONLY` |
| `OPEN_ASSUMPTION_LEDGER.csv` | 22 assumptions with the role each plays, what breaks if it fails, whether follow-up work removes it, and a possible CSIA experiment |
| `CANDIDATE_LONG_LIST.md` | all 12 candidates (9 required + 3 added under item 9), each with reduction, three-sentence abstract, hostile read, smallest kill test |
| `CANDIDATE_SCORECARD.csv` | 13 dimensions per candidate plus the item-25 weighted frontier score |
| `REJECTED_CANDIDATES.md` | 9 rejections, each with closest prior art, kill reason, subsuming abstraction, engineering value, minor-paper prospects |
| `TOP_THREE.md` | the three finalists with item 31's full requirement set, and hostile reviewers A–J answered for each |
| `SELECTED_CANDIDATE.md` | why B, why not A or J, the 7-reason pre-mortem, feasibility audit, data, statistics, adversarial nulls, dissertation gate |
| `SELECTED_CANDIDATE_FORMAL_TARGET.md` | objects, proposition, the known theorem it reduces to, counterexamples, five proof obligations, and what is *not* being claimed |
| `SELECTED_CANDIDATE_STAGE0_DESIGN.md` | hypothesis, three nulls, manipulation, four controls, endpoints, confounders, invalid-trial rules, artifacts, runtime, stop conditions |
| `SELECTED_CANDIDATE_STAGE0_PROMPT.md` | the complete next prompt. **Not executed** |
| `CLAIM_LEDGER.json` | 12 claims, 3 refuted predictions kept, all prior verdicts preserved |
| `CHATGPT_REVIEW_REPORT.md` | the 32-section review report |

Guards: `tests/test_frontier_selection.py`. Run with `make frontier-check`.

---

## The three candidates added under item 9

Item 9 permits new candidates only when a primary source explicitly exposes an
unresolved assumption. Three qualified:

- **J** — from S042 (Li, Faghfoorian & Ruchkin 2025), which extracted 423
  assumptions from 104 CPS papers and reports gaps in how sensing,
  initialization, perception and uncertainty assumptions are stated. → TOP #3.
- **K** — from S070 (gated Kalman filter innovation-statistic contraction,
  2025). **Disqualified** under item 0 as a rename of killed direction 1
  (self-occlusion), despite scoring 4.200 — higher than two finalists. The
  score is published in `REJECTED_CANDIDATES.md` so the ranking cannot be
  accused of hiding it.
- **L** — from S004 (Simplex "does not address sensors") and S067 (requires
  channels that "do not share component dependency"). **Folded into B** as a
  special case rather than kept as a separate weaker contribution.

---

## What this stage does not claim

- It does not claim the literature was reviewed. It was searched, at snippet
  depth, with one engine.
- It does not claim candidate B is novel. It claims B was not visibly answered
  in any snippet, which is a much weaker statement.
- It does not claim a theorem. The proposition is a corollary and is labelled
  as one in three separate files.
- It does not claim the search was complete. Aerospace certification standards
  (ARP4761 common-mode analysis) were unreachable and are the largest known
  hole; data-provenance theory and fault-tree minimal cut sets were not
  searched at all. All three are written into the Stage-0 prompt as mandatory
  prior work.

---

## Next step

`SELECTED_CANDIDATE_STAGE0_PROMPT.md`, §1 first — the reading, not the
experiment. If the gate finds that a runtime effective-independence count for a
monitor's verdict already exists, the correct action is to record the kill and
select again from `TOP_THREE.md`, not to reword candidate B until it survives.
