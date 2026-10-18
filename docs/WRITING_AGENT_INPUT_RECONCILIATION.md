# Writing-agent input reconciliation

Final dual-manuscript integration pass, 2026-09-04, at HEAD
`f2244fc319e7eff740bbee2e2eb95e054f8b7ef0`.

## The finding, stated first

**The writing agents' revisions never reached this repository.** The
integration brief describes a 27-page systems revision with specific sections,
claim identifiers and defects. None of them exist in any file here. The working
tree was clean, the remote matched HEAD, and `handoff/` contained only the three
bundles this agent wrote in the previous pass.

Integration was therefore impossible for the manuscript changes, and **no
attempt was made to reconstruct them.** Fabricating the described defects in
order to "fix" them would have produced a manuscript that matched a document
nobody could check.

## What the brief described, and what is actually here

Each row was checked by direct search of the canonical manuscript
`papers/csia_systems/main.tex` (26 pages, 15 sections, claim IDs `SC-01`…`SC-26`).

| brief §  | described defect | search | actual state |
|---|---|---|---|
| §2 A | Discussion §15.2: *"The replication answers that objection for the fix-loss mechanism on two current stacks"* | `"two current stacks"` → **0 hits**; the manuscript has 15 sections and no §15.2 | **NOT PRESENT.** The manuscript says *"**One** mechanism has been repeated on a current stack"*, singular, and names it as the **threshold-crossing** mechanism (Mechanism B, `sec:algebra`). It makes no Mechanism-A replication claim |
| §2 B | claim ledger row `R01`, ArduPilot 4.8 fix-loss replication | `\bR01\b` across `papers/ research/ engineering/ docs/` → **0 hits** | **DOES NOT EXIST.** The ledger is `research/systems-paper/CLAIMS.csv`, 26 rows, all `SC-nn` |
| §2 C | claim ledger row `R02`, PX4 SIH fix-loss replication | `\bR02\b` → **0 hits** | **DOES NOT EXIST** |
| §2 D | prose naming *"Mechanism A cross-platform replication 48a528a"* | `48a528a` → **0 hits** | **NOT PRESENT** |
| §3 | Related Work §2.6: *"We run no comparison against a cumulative-sum baseline"* | `cusum` / `cumulative-sum`, case-insensitive → **0 hits in the entire manuscript** | **NOT PRESENT.** The manuscript never mentions CUSUM. The detector comparison lives in `research/systems-paper/MECHANISM_B.md`, which is a research note, not this paper |
| §4 | claim ledger `I02`: *"GPS_INPUT unresolved … not a verified inapplicability"* | `\bI02\b` → **0 hits** | **DOES NOT EXIST.** The manuscript states PX4 SIH is *inapplicable*, with the reason: no fix-preserving GNSS position offset exists, four candidate routes read out of source and all four fail, and the preregistration forbids substitution |
| §5 | §12 and §13 confusing two public-log activities | the manuscript mentions the 26-log corpus twice, both in Limitations; there is no §12/§13 pair and no support-exposure study presented as run | **NO CONFUSION PRESENT** |
| §8 | Conclusion typo *"The For the measured parameter set…"* | `"The For the"` → **0 hits** | **NOT PRESENT** |
| §10 | *"eighteen eligible entries"* to re-check | `eighteen` → **0 hits** | **NOT PRESENT.** No ledger count is hand-typed in the manuscript |

**Nine described defects, nine absent.** The canonical manuscript was already
self-consistent on every point.

## What this most likely means

The writing agents worked from the handoff bundles rather than from the
repository — which is what they were designed to do, since neither has
repository access. Their revision is a **separate artifact** that exists
wherever they wrote it. The section numbering (§15.2, §17.4), the claim-ID
scheme (`R01`, `R02`, `I02`) and the page count (27 versus 26) all differ from
the canonical manuscript, which is consistent with an independently
restructured document rather than an edit of this one.

**Nothing here says their revision is wrong.** It says it is not in this
repository, so this agent cannot verify it, integrate it, or attest to it.

## What was integrated instead

The parts of the brief that were actionable against the canonical repository
were done, and are the substance of this pass:

| brief § | action | outcome |
|---|---|---|
| §6, §11 | the eight terminology substitutions | **APPLIED** — 2 in the systems manuscript, 6 in the mathematical one. Both rebuild clean. The pinning test in `tests/test_support_state_posterior_range.py` was updated in the same commit, because it asserts the literal sentence one substitution changed |
| §7 | the 118.82 chain | **already correct**; `S_0 = 475.6775`, `T_0 = 0.999791`, `T* = 0.75` confirmed against the artifact; 125 and 0.98764 absent from the manuscript, figures, captions, artifact map and ledger |
| §9 | the canonical 49-literal audit | **CREATED** — `papers/csia_systems/NUMERIC_LITERAL_AUDIT.csv`, generated from the repository's own strict-numbers output rather than from the writers' 607-row scan |
| §10 | ledger counts | **checked** — no count is hand-typed; the "19 signature entries / 18 clean" figures are a different quantity and are verified by test |
| §12 | Rukhin 1997 | **STATUS CORRECTED** — see below |
| §13, §14, §15 | Di Noia, Athanasopoulou, Heitjan & Rubin | **corroborated, not verified** — see below |
| §20 | cross-paper consistency | **regenerated** |

## Bibliography: what actually changed, and what did not

**Web *search* became available to this environment in this pass. Web *fetch*
of any publisher host did not.** Both were tested:

| host | result |
|---|---|
| `api.crossref.org`, `doi.org`, `dblp.org` | CONNECT → 403 |
| `www.impan.pl`, `projecteuclid.org` | `EGRESS_BLOCKED` |
| `ieeexplore.ieee.org`, `arxiv.org` | `EGRESS_BLOCKED` |

So four references can now be corroborated in detail — multiple independent
search indices agreeing on every field, with no field in dispute — while **no
accepted route is reachable**. The ledger already lists `WEB_SEARCH` and
`SECONDARY_INDEX` as **rejected routes**: *"a second unverified source, not a
publisher record."* Marking these `VERIFIED` would retire a marker on a route
the ledger exists to refuse.

A third state was therefore added, `CORROBORATED_NO_PUBLISHER_RECORD`, with its
own guard: **the marker stays, and `bib-guard` stays red.**
`test_a_corroborated_row_still_carries_its_marker` enforces that it cannot
become a soft `VERIFIED`.

### The one genuine correction

`research/math-paper/PRIOR_ART_MATRIX.csv`, the bounded-likelihood-ratio row,
was `NOT_FOUND_NEEDS_HUMAN`. **That was a factual error about the world.** The
reference exists:

> Rukhin, A. L. *Information-type divergence when the likelihood ratios are
> bounded.* Applicationes Mathematicae **24**(4), 415–423, 1997.
> DOI `10.4064/am-24-4-415-423`.

Independent sources reproduce the metadata and describe Theorem 2.1: a
likelihood-ratio bound implies upper bounds on f-divergences for bowl-shaped
`f` with a minimum at 1. The status is now
**`LOCATED_CORROBORATED_NOT_READ`**, and that status is in the guard's `weak`
set, so the row is required to state what may not be concluded from it.

**The consequence for the paper is unchanged: no sharpness may be claimed for
P6b.** Secondary descriptions call *Rukhin's own bound* sharp. That is not the
same statement as sharpness of our elementary specialization, the theorem has
not been read, and the two must not be conflated.

`heitjan1991car` moved to `CORROBORATED_NO_PUBLISHER_RECORD` with the Annals of
Statistics metadata and DOI `10.1214/aos/1176348396`. It is the entry that makes
the ignorability proposition KNOWN, so it matters most and is still not
verified.

## Status after this pass

| | |
|---|---|
| **systems paper** | FINAL EXCEPT EXTERNAL BLOCKERS — bibliography (11 entries, 0 verified) and the preregistered public-log study (not run, egress) |
| **mathematical paper** | FINAL EXCEPT EXTERNAL BLOCKERS — bibliography (6 entries, 0 verified), one reference located but unread, one high-priority reference unread |
| **neither** | is a submission candidate. Calling either one now would require retiring markers on a rejected route |

## What a human should do with the writers' revision

Deliver it into the repository — as a branch, a patch, or the `.tex` itself.
Then this agent can diff it against the canonical manuscript, check every
number it moved against the frozen artifacts, and integrate what the evidence
supports. Until then the canonical manuscript is what builds, what the tests
guard, and what the artifact maps bind.
