# EXPOSITION COMPRESSION PLAN — MATHEMATICAL PAPER

Peer-review hardening campaign, §17. A ranked cut order for
`papers/gate_conditioning/main.tex`, prepared in advance so that a page limit
is met by decision rather than by whatever is easiest to delete at the deadline.

**Nothing is cut by this document.** Compression is a venue decision. What is
fixed here is the *order*, and the list of things that may not be cut at all.

Measured 2026-09-04: **11 pages, 872 source lines, 14 sections.**

---

## 0. The honest headline

**The paper is not over-long.** At 11 pages with every proposition proved,
every proposition conceded as KNOWN, an implemented instance, and a limitations
section, it is already shorter than most venues allow. There is no compression
problem to solve today.

What there is, is a **risk**: a venue with a hard 8- or 10-page limit, and an
author under time pressure cutting the wrong thing. Every item in the
do-not-cut list below is something whose removal would convert a conceding
paper into an overclaiming one, and that conversion is silent — the text left
behind still reads well.

## 1. Do not cut. Ever

| item | § | why removal is fatal |
|---|---|---|
| §1.1 "What $q$ is measured against" (Reading A / Reading B) | Setting | Reading A makes the entire framework **vacuous** ($w\equiv1$, $p=q$, $R=0$). A reader who does not know which reading is in force cannot tell whether the paper says anything. This is the defect the math red team found, and it was found *after* the first draft shipped without it |
| Remark `r:counterfactual` (the baseline is not evaluable) | Setting | the paper's single largest weakness. Removing it hides it |
| Remark `r:marginal` (what $p$ is) | Ignorability | pre-empts "this is information loss, not distortion", which is the first objection a missing-data reader raises. Added 2026-09-04 from `COARSENING_REDUCTION.md` |
| Remark `r:car` (C2 is **not** the CAR condition) | Ignorability | without it the paper contains a false statement about the missing-data literature. It contained one until 2026-09-04 |
| Remark `r:mapblind` / P8 | MAP robustness | P4 is **vacuous** in the measured regime. Deleting the remark leaves a sufficient condition that looks applicable and is not |
| The novelty table (`tab:novelty`) | What is new | every row says KNOWN. It is the paper's central concession and its absence is a priority claim by silence |
| Limitations | Limitations | as above |

**Rule of thumb, and it is not a joke:** in this paper the cuttable material is
the material that makes the paper look *better*. Everything that makes it look
worse is load-bearing.

## 2. Cut order, if a limit forces it

Ranked. Take from the top; stop as soon as the limit is met.

| rank | target | ≈ lines | ≈ pages | what is lost | what is NOT lost |
|---|---|---|---|---|---|
| 1 | §Verification, compressed to two sentences plus a pointer to `proof_audit.json` | 34 | 0.4 | the table of worst-case deviations in the paper itself | the verification — it is a committed artifact and `tools/publication/proof_audit_check.py` gates it |
| 2 | §"A separate body of work, not in this paper" | 15 | 0.2 | a scope fence | nothing mathematical. Move it to a footnote in Related work, do not delete it |
| 3 | P6c's attainment paragraph, reduced to the statement plus the witness | ~12 | 0.15 | the two-branch symbolic check narrative | the claim that the bound is attained, and its licence — `NOVELTY_AUDIT.md` §1 |
| 4 | The P5a/P5b proofs, replaced by "both are one line from P1 and Jensen" | ~18 | 0.2 | two short proofs | the identities, which are the cited results |
| 5 | §Exact divergences and bounds, merged into one section with §MAP robustness | ~15 | 0.2 | separate framing | no statement |
| 6 | §An implemented instance, reduced to the checker result and one table | ~35 | 0.4 | the walk-through of the signature table | **`SC-03`: 378,000 of 378,000. This number may not be cut at any rank** |

Cutting ranks 1–6 in full recovers **about 1.5 pages** and leaves the paper at
roughly 9.5. Below that, no cut exists that does not remove either a proof or a
concession, and at that point the correct action is a different venue.

## 3. What must NOT be done to save space

* **Do not delete a proof and keep its proposition.** Every proposition here is
  one to five lines; a proposition without its proof in a paper this short
  reads as an appeal to authority, and the authority is us.
* **Do not merge the KNOWN labels into a single sentence.** "The results are
  standard" is not the same concession as a table with one row per proposition
  and its prior art named. The row-level version is what
  `tests/test_math_paper_proofs.py` and `NOVELTY_AUDIT.md` enforce.
* **Do not move Limitations to an appendix.** A limitation a referee has to
  find is a limitation the paper is hiding.
* **Do not compress by removing hedges.** The hedges are load-bearing:
  `PRIOR_ART_MATRIX.csv` records 20 of 21 rows as unread or unverified, and
  every "as far as we can establish" in the manuscript is that fact surfacing.
  A tighter sentence would be a false one.

## 4. Where the length actually is, and why it stays

The three largest sections are Setting (100 lines, 11.5%), Pinning (107,
12.3%) and Ignorability (102, 11.7%) — **34% of the paper in three sections**,
and all three grew during hardening rather than during writing:

* Setting grew by §1.1, which exists because the framework was vacuous without
  it.
* Pinning grew by P7/P7b/P7c, which exist because P3's literal hypotheses are
  **not** the ones the implemented case satisfies.
* Ignorability grew by `r:marginal` and `r:car`, which exist because the paper
  was making an imprecise claim about coarsening at random.

Each addition removed a defect a referee would otherwise have found. **The
paper is long in exactly the places where it used to be wrong**, and that is
the right place for a paper to be long.
