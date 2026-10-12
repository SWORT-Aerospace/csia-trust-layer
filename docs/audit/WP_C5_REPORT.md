# WP-C5 — Reposition as a Systems Paper, Close the Loose Ends

**Date:** 2026-08-22 · **Branch:** `research/wp_e1` · **PR #13**
**Suite: 467 → 482.** One production change: the `DiagnosisCore` input guard,
committed only after verifying it changes nothing.
**Deliverables:** `papers/csia_systems/`, `docs/audit/WP_C5_REPORT.md`,
`research/wp_c5/Q_GVALID_MEASUREMENT_SPEC.md`

---

## 1. Verdict

The repositioning is right and the paper is stronger for it. Stripping every
framework claim left exactly what the evidence supports: **a deployed
aerospace diagnostic layer reporting healthy for 40 seconds while a fault it
was built to catch destroyed the evidence that would name it, with the trust
channel independently agreeing.** That needs no mathematics and survives every
demotion.

The manuscript is written, passes the hard rules mechanically, and cites the
four frameworks as the ones this work instantiates. **One thing I could not
do as instructed: the BibTeX was not supplied to this session.** I
reconstructed entries from the author names and years in the brief and marked
every one with a verification status. That file must be checked before
submission and I have said so in the file itself, in this report, and nowhere
softer.

---

## 2. What the kill report changed

Stated plainly, because it is the argument for the systems framing.

**Fifteen claims have now been demoted or refuted across this programme.**
Counting the ones that were mine and the ones that were the brief's:

| # | Claim | Fate |
|---|---|---|
| 1 | "62-test automated fault harness" validates the system | Scope-inflated 4× to 7.75×; the 62 was the whole suite |
| 2 | "26 real PX4 logs, 0.66 flight-hours" as validation | Superseded: 0.518 monitored h, and "validated" is prohibited wording |
| 3 | The submitted document fabricated figures | **Refuted.** Every number was true at some commit |
| 4 | "45% of the graph is dead weight" (mine) | Refuted: four of five constant-gate edges are load-bearing |
| 5 | Super-additive gate/channel interaction (mine) | Refuted: 1784 instances were all transitivity artifacts |
| 6 | CWE inverts the severity ordering (the brief's) | Refuted: it widens it the same way |
| 7 | GPS candidates differ on physical grounds (mine) | Refuted: they differ on gate dependence |
| 8 | The promotion traded IMU exposure for `mag` exposure (mine) | Refuted: no new order-one cut set; strict improvement |
| 9 | The chatter probe showed no resonance (mine, first pass) | Refuted: the probe was broken, not the prediction |
| 10 | "Every fault magnitude is detected" (mine, first pass) | Refuted: the window included the warm-up dip |
| 11 | The joint-lattice certificate is unoccupied | **Dead.** Carvalho et al.; Krysander et al. |
| 12 | The reliability structure is a framework | **Occupied.** Hurdle et al.; Reeves et al. |
| 13 | `S_eff` broad claims | **Dead.** Yin et al.; Krysander and Hashemniya |
| 14 | The coarsening result is a theorem | Proved but it is monotonicity under row deletion |
| 15 | WP1's three-way `gps_fault` collision | Corrected to two-way; `temp_gps` is ungated |

**The measurement survived every one of them.** Arm B was not weakened by a
single demotion, because it never depended on any of them. That asymmetry is
the whole case for the systems framing: what we own is the observation, and
the observation is robust to the entire theoretical apparatus being someone
else's.

Two things the kill report changed operationally. First, the containment
result from WP-C4 2.4 was produced after the research brief went out, so it
was never assessed. It is stated in the paper as an observation about this
system with priority explicitly not asserted, pending the follow-up. Second,
Section 2 of the paper is now "Related work: what we instantiate", with a
`What we take` / `What we claim: nothing` pair for each framework. That is a
better section than the gap-claiming one it replaces.

---

## 3. Part 1 — the manuscript

`papers/csia_systems/main.tex`, 10 sections following the required structure,
plus `refs.bib` and three figures copied into the paper tree.

**Hard rules, checked mechanically rather than by eye:**

| Rule | Result |
|---|---|
| No em dash characters | **0** (also 0 en dashes) |
| The word "novel" appears nowhere | **0** after two fixes |
| Nothing labelled a theorem that is monotonicity | **0** occurrences of "theorem" at all |
| Braces balanced | yes |
| `\begin`/`\end` environments matched | yes, no mismatch either direction |
| Every `\cite` key resolves | 8 cited, 8 in the bib, none missing, none unused |
| Every `\includegraphics` target exists | 3 of 3 |

My first draft violated two of them: "novelty" contains "novel", and I had
written "not as a theorem" in a sentence intended to disclaim it. Both are
gone; the disclaimers are now phrased as "We assert no priority."

**Compilation could not be verified.** There is no LaTeX toolchain in this
environment (`pdflatex`, `xelatex`, `latexmk`, `tectonic` all absent). The
checks above are the strongest verification available here and they are
structural, not a build. **Someone must compile it before it is treated as
final.**

**Every number in the manuscript traces to a committed artifact:**

| Number | Source |
|---|---|
| Arm A/B/C table | `research/wp_c4/results/self_occlusion.json` |
| Density sweep table | `research/wp_c4/results/sparsity_probe.json` |
| κ(S)=0.000, κ(S_eff)=0.143 | `research/wp_c3/results/effective_signature.json` |
| Chatter 16.67 predicted / 21 observed | `research/wp_c4/results/adversarial_search.json` |
| Repair before/after | `research/wp_c2/results/repair_experiment.json`, `research/wp_c4/results/cutsets_post_promotion.json` |
| Gate table, signature table | `research/wp_e1/gate_map.py`, `csia/diagnosis/bayes.py` |
| 27 of 28 decision-relevant | `research/wp_c1/results/certificate.json` |

### The bibliography problem, stated at full strength

**The brief said to use the BibTeX the research agent supplied and not to
hand-write citations. That BibTeX did not reach this session.** I had author
names and years from the brief text and nothing else.

What I did: reconstructed entries from those names and years, marked each with
a verification status, and put a warning block at the top of the file. Three
entries are `VERIFIED-BY-SEARCH` (author, year and venue seen in search results
this session, pages and DOI unchecked). Four are `RECONSTRUCTED` (author and
year from the brief only; title and venue are placeholders containing the
literal string `VERIFY`).

What I did not do: invent a DOI, a page range, or a venue for anything. The
`VERIFY` strings will make the bibliography fail conspicuously rather than
silently if it is compiled without being fixed, which is the intended
behaviour.

**This is a blocker on submission, not a nit.** Citing four frameworks as the
prior art we defer to, with three of the seven entries carrying placeholder
venues, would be the single most embarrassing way to publish this paper.

---

## 4. Part 2 — the stale number and the guard

### 4.1 The gate ceiling

Scanned every tracked markdown file for `0.286` and `0.2857`: 15 occurrences
across 7 files. **Only two needed changing.** Every other occurrence is an
explicitly pre-promotion historical record (the WP-C1 certificate, the WP-E1
report, the WP-C2 report) or the flag itself (`VERSION_BOUNDARY.md`,
`WP_C4_REPORT.md`). Rewriting those would have falsified the record.

In `docs/research/PAPER1_EMPIRICAL_SECTION.md`: κ_max 0.286 → **0.143**, CWE
and IRE 0.074 → **0.037**, "two that survive" → "the one that survives", plus
a version note giving both sets and pointing at `VERSION_BOUNDARY.md`. The
argument is unchanged in either version; only the numbers moved.

One thing I broke and fixed: my first patch inserted the version-note
blockquote mid-paragraph, splitting a sentence across it. Caught on read-back.

### 4.2 The `DiagnosisCore` guard

`bayes.py` now rejects consistency outside `[0, 1]` with a `ValueError` naming
the offending feature, matching the bounds rejection `TrustCore` already has.

**The condition for committing it was that it changes nothing, and it does
not:**

| Check | Result |
|---|---|
| Minimum trust, all five fault scenarios plus clean | identical to 6 decimals: 0.590541, 0.765697, 0.276357, 0.399116, 0.165837, 0.810713 |
| `campaigns/bench.json` | regenerates bit-identical |
| Suite | 467 → 482, all passing |

**A placement decision worth recording.** The guard sits *after* the gate
short-circuit, not before it. A gated feature contributes nothing to any
hypothesis, so its value is irrelevant, and validating it would change
behaviour on data the system currently ignores. That is pinned by
`test_gated_feature_is_skipped_before_the_guard`, and it is the difference
between a guard and a behaviour change.

The WP-C4 boundary probe's vocabulary gained `REJECTED`, since a deliberate
input rejection is not a crash. Its two `SILENT_BAD` cases now read
`REJECTED`; the JSON carries a note explaining the transition so the WP-C4
report's original finding stays legible.

---

## 5. Part 3 — the measurement spec

`research/wp_c5/Q_GVALID_MEASUREMENT_SPEC.md`.

**The finding that came out of writing it:** `fix_type` *is* plumbed, and
`gvalid` is a function of `fix_type` and nothing else. So the gate trace
itself is obtainable on today's ingestion path. **The blocker is not the gate,
it is the label.** `q_gvalid | h` conditions on the true hypothesis, and the
corpus is unannotated, so the conditioning variable does not exist in the data.

Three routes are specified, with controlled injection (L1) recommended as the
only one giving a defensible label. The spec explicitly forbids reporting
unconditional `q_gvalid` as a substitute: it mixes both hypotheses in unknown
proportion and bounds nothing about the ratio.

The estimator uses **the flight as the independence unit, not the tick**.
Gate closure is strongly autocorrelated within a flight, and a binomial
interval over ticks would understate the width by roughly the square root of
the block length. That is named in the spec as the single most likely way to
get this wrong.

Cell counts are required before any inferential quantity, with stopping rules
fixed in advance, including what to do when either arm has zero closures.

**The outcome table is the part worth reading.** Three of its four outcomes
weaken or complicate the programme's current position and one strengthens it.
In particular, if `gvalid` never closes in either arm, the paper's central
measurement would be a property of the simulator's denial model rather than of
flight. That is the strongest refutation available, and it is the reason the
measurement should be run **before** submission rather than after.

---

## 6. What I got wrong

- **Two hard-rule violations in the first draft.** "novelty" contains "novel";
  and I used the word "theorem" in a sentence disclaiming it. Both caught by
  the mechanical check, which is the argument for running one rather than
  proof-reading.
- **A split paragraph** in the empirical section, from inserting a blockquote
  mid-sentence.
- **I could not follow the citation instruction** and said so rather than
  producing plausible-looking entries.

Nothing was refuted this round in the sense of a hypothesis dying, because
this package had no hypotheses to test. It executed decisions already made.

---

## 7. Open, with owners

| Item | Owner | Blocking |
|---|---|---|
| **Verify every bib entry** | You | submission blocker |
| **Compile the manuscript** | You | no LaTeX in this environment |
| `q_gvalid` conditioned on hypothesis | WP-E2 | corpus + injection campaign; spec is ready |
| Plumb `satellites_used`, `noise_per_ms`, DOP | Engineering | nothing |
| Containment-observation priority assessment | Research agent | follow-up brief out |
| `failsafe.py:106` fail-open on `att` | Engineering | unanalysed since WP1 |
| `engine.py:104` stale "12 edges" comment | Trivial | nothing |
| `SWORT_CSIA.pdf` + submission date | You | four documents still blocked |
