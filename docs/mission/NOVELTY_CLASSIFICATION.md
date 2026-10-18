# Novelty classification — mission-assurance extension

**EVERY IDEA IN `csia_mission/` IS CLASSIFIED BELOW. NONE IS CLAIMED AS
NOVEL.**

---

## The classification, applied

| idea | status | note |
|---|---|---|
| **evidence-preserving reconfiguration** / self-occlusion detection | `EXPERIMENTAL`<br>`POSSIBLE_RESEARCH_CONTRIBUTION`<br>**`NOVELTY_NOT_ESTABLISHED`** | Resembles observability analysis and reconfigurable-systems FDI. **No literature search has been done.** It may well be a known result under a name this repository has not looked for |
| **mission-product assurance** with independently qualified quality properties | `EXPERIMENTAL`<br>`POSSIBLE_RESEARCH_CONTRIBUTION`<br>**`NOVELTY_NOT_ESTABLISHED`** | Data-quality flags on geospatial products are ordinary practice. What may or may not be new is deriving them from a live evidence-support chain rather than from processing metadata. **Not established either way** |
| **capability support certificates** | `EXPERIMENTAL`<br>**`NOVELTY_NOT_ESTABLISHED`** | Capability-based mode management is long-established in avionics. The witness-carrying form here follows directly from the DEA profile, which is prior work in this repository |
| **compute-aware product qualification** | `EXPERIMENTAL`<br>`POSSIBLE_RESEARCH_CONTRIBUTION`<br>**`NOVELTY_NOT_ESTABLISHED`** | Real-time systems have treated deadline misses as failures for decades. Whether *propagating a missed deadline into a data-product qualification* is new is unexamined |
| three-level graph separation | `EXPERIMENTAL`<br>**`NOVELTY_NOT_ESTABLISHED`** | A layering choice. Almost certainly not novel |
| the forge-seed compiler | `EXPERIMENTAL`<br>**`NOT_NOVEL`** | A topological sort with cycle detection. Textbook, and claimed as nothing else |
| the eight bounded properties | `EXPERIMENTAL`<br>**`NOT_NOVEL`** | Exhaustive enumeration over a small domain. Not a theorem, not for-all, not new |
| the six experimental metrics | `EXPERIMENTAL`<br>**`NOT_NOVEL`** | `false_product_certification_rate` is a renamed false-positive rate. Calling it a contribution would be silly. It is here because it is the number that matters |

## Why "no literature search has been done" appears twice

Because it is the reason the top rows say `NOVELTY_NOT_ESTABLISHED` rather
than `NOVEL`. The honest position is not "we checked and it is new" and not
"we checked and it is known" — it is **"we have not checked"**, and that
supports no priority claim in either direction.

## What this means in practice

1. **No manuscript priority claim.** Not in Paper I, not in the mathematical
   paper, not in any future paper, until a real prior-art search has been
   done and recorded the way `research/math-paper/PRIOR_ART_MATRIX.csv`
   records one.
2. **Paper I may reference this work only as FUTURE WORK.** See
   `PAPER_I_SCOPE_GUARD.md`. No feature here may be described as an E1
   result.
3. **Every artifact carries its status.** `reconfiguration.py`,
   `metrics.py` and the generated JSON all carry `NOVELTY_NOT_ESTABLISHED` in
   their own output, so a reader who sees only one artifact still sees the
   classification.

## What would move a row

A recorded prior-art search: the databases queried, the terms used, the
candidates found, and a per-candidate statement of what it does and does not
cover. The existing `PRIOR_ART_MATRIX.csv` is the pattern. Anything less
moves nothing.
