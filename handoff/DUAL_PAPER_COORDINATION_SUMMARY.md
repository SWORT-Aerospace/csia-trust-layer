# CSIA dual-paper coordination summary

For the agent writing the next two prompts. Everything below was measured at
the HEAD named, not recalled. Full detail is in the two bundles; this is the
map.

| | |
|---|---|
| **HEAD** | `228bebeb14395aebda60d76dbf6a54b292d0e344` |
| branch | `claude/code-reviewer-repo-export-zicovg` (remote matches) |
| evidence freeze | `csia-dual-paper-evidence-freeze` = `eb2577d6830208b26d33facb283aa5be0ddf7c86` |
| tests | **1684 collected, all passing** |
| frozen v1 | **PASS** — zero diff against `csia-v1.0-research-final` = `ec5acd18…` |
| Phase C freeze | **PASS** — all recorded hashes hold at `50c5d357…` |
| scientific artifact drift since the evidence freeze | **NONE** — `git diff` empty across `research/ engineering/ csia/ campaigns/ figures/ datasets/` |
| blocking publication guards | **PASS** |
| bibliography guard | **FAIL, expected** — 52 markers, 0 verified |

---

## SYSTEMS PAPER

**Canonical manuscript**: `papers/csia_systems/main.tex`, **26 pages**, all
citations resolved. Nothing else is a systems manuscript. Note the naming trap:
`docs/research/PAPER1_EMPIRICAL_SECTION.md` belongs to the *mathematical*
paper despite the filename.

### What is final

| | |
|---|---|
| **Mechanism A** | measured on the bench pipeline: `nominal` reported for the whole GNSS-denial window, `gps_fault` never named, GPS trust 0.9767. Collapse of `(nominal, gps_fault)` for **200 consecutive ticks** = 8.0 s at 25 Hz, plus **76 ticks** at the start of *every* scenario including clean. Structural claim `SC-02` is **PROVED**; the window figures are `EMPIRICAL_ONLY` |
| **Independent checker** | **378,000 / 378,000 agreements, 0 real disagreements, 0 degenerate cases.** VERIFIED. 9 scenarios x 1500 ticks x 28 pairs. Imports only stdlib + yaml; a test asserts no CSIA module reaches `sys.modules` |
| **Negative control** | **15,595 ticks / 20 ArduPilot 4.8 trials / 0 collapses.** VERIFIED, and the decomposition checks: CLEAN 5,100 (5 trials) + RAMP 887 (5) + STEP 9,608 (10) = 15,595 |
| **Mechanism B** | detector-to-detector, VERIFIED: **7.72 vs 2.96** (1 m/s), **2.36 vs 1.16** (3 m/s), **2.24 vs 0.72** (6 m/s) |
| **Escalation decomposition** | mass term **118.82** against margin term **1.0**; `N*` = 93.31 ticks; observed crossing tick 94; closed form matches shipping code to **0.0** |

### What changed

1. **The `125` -> `118.82` correction, and the explanation behind it.** The
   manuscript value 118.82 is correct and was already correct. What was wrong,
   twice, was the *account of its provenance*. Settled chain:
   `S_0 = 475.6775` (**measured settled Beta mass**, not the cap 500),
   `T_0 = 0.999791` (**measured settled trust**, not 1.0), `T* = 0.75`;
   `475.6775 x (0.999791 - 0.75) = 118.8199584…`
   **`125` came from the generating script's own docstring** — an idealised
   illustration at the cap and `T_0 = 1.0` — which the manuscript had
   transcribed as if it were a result.
   **`0.98764` refers to nothing.** It was back-solved from `118.82/500 + 0.75`
   and reproduces 118.82 only because `500 x 0.23764 = 118.82` exactly.
   **SCIENTIFIC RESULT UNCHANGED**; two documentation notes corrected, and a
   new test pins `S_0` and `T_0` themselves rather than only their product.
2. **Monte Carlo limitation.** `generate_flight(seed)` is byte-identical across
   seeds — 12 truth fields, 6 seeds, 0 differences, both profiles. All 150
   campaign runs flew **one trajectory**. The campaign varies fault class,
   amplitude, onset and the clean/faulted split; it does **not** vary the
   flight. **No campaign artifact changed** — `campaigns/monte_carlo.json`
   regenerates bit-identically.
3. **Five claim clusters audited and pinned**, one design-rule guard hardened
   so it can no longer degrade into a silent skip.

### What remains blocked

| # | blocker | who clears it |
|---|---|---|
| 1 | **bibliography** — 11 entries, 0 verified, 37 markers. Six routes tested, all HTTP 403 | a human with publisher access |
| 2 | **public-log study** — `SC-22` `PROVISIONAL`, plan preregistered, `review.px4.io` denied | a host with egress |
| 3 | **Mechanism A has no current-stack replication** — `SC-23` `PROVISIONAL`. No fix-loss arm exists in the 4.8 data | a new campaign |
| 4 | **prevalence** — n = 1, one deployed layer | out of scope |

### What the writing agent must write

- Apply the **two terminology substitutions** at lines 1405 and 1408 (below).
- Decide which of the **49 unmapped prose literals** are scientific results
  needing artifact binding; the full list with line and context is in the
  bundle.
- Correct any wording implying independent flights or a Monte Carlo over
  trajectories.
- Keep every conceded limitation: the checker does not validate the signature
  table; the negative control is not a replication; no operational harm is
  demonstrated.

**Must not**: delete a bibliography marker; quote 8.72 vs 2.96 without saying
the 8.72 includes a 1.0 s policy dwell; quote the clean arm's lambda crossings
as latencies (they are false alarms); call the negative control a replication;
claim CUSUM novelty.

---

## MATHEMATICAL PAPER

**Canonical manuscript**: `papers/gate_conditioning/main.tex`, **10 pages**,
all citations resolved. `docs/math/PROOF_STATUS.md` is a **different body of
work** (anytime-valid e-processes, T-1…T-5) and does not govern P1–P8.

### What is final

| | |
|---|---|
| **P7 / P7b / P7c** | the gated-score form `w_h = exp(-Σ_j (1-g_j) ℓ_j(h))`, the withheld-contribution identity, and pinning recovered from the gate condition. Verified at **5.551e-16**, **3.553e-15**, **1.776e-15**. Mapping VERIFIED |
| **P7c replaced the P3 pointer** | VERIFIED. Under the full-evidence baseline, in the measured case, **both** of P3's hypotheses are false (`L_a ≠ L_b` **and** `w_a ≠ w_b`); the ratio is pinned because the two cancel exactly. Every document that pointed at P3 was repointed. **No number changed** |
| **P8** | for a pinned pair with equal prior mass that is the top two under `q`, `Δ = |S|` and `R ≥ |S|`, so `Δ ≤ R` **always** — P4 can never certify the central pinned regime. **2,282** instances, **0** violations, worst slack **+8.882e-16**. VERIFIED |
| **P8 escape** | dropping equal priors lets P4 fire: **1,224 of 20,130** under a lopsided `Dirichlet(0.3)` prior. VERIFIED. Interpretation: the certificate was bought with **prior mass, not evidence**, which C3 already says is worthless as discriminating support |
| **Support definition** | purely structural, `D(a,b) = (LOW(a) △ LOW(b)) ∩ ACTIVE`. **No weight or posterior threshold is any part of it.** The false "leader above 0.999" is **gone — grep returns 0**. Observed firing range **0.9691 to 0.9998** over 44 rows; those are **observations, not thresholds**, and a rule gated at 0.999 would have passed most of them |
| **Novelty** | **every proposition is KNOWN.** None refuted, none withdrawn |

### What changed

**The baseline defect, which would have been fatal in review.** The earlier
draft defined `L_h` as the *active-evidence* likelihood. Under that reading the
gate is already inside `L_h`, so `w_h ≡ 1`, `p = q`, `R = 0`, and **P1, P2,
P5a, P5b, P6a, P6b are all true and all empty** for the paper's own worked
example. Both readings were computed; Reading A returns `w ≡ 1` exactly. Fixed
with §2.1 stating both readings, the new Proposition P7, and a rewritten
abstract.

### What remains blocked

| # | blocker | who clears it |
|---|---|---|
| 1 | **bibliography** — 6 entries, 0 verified. `heitjan1991car` is `RECONSTRUCTED` and is what makes C2 KNOWN | a human with publisher access |
| 2 | **Rukhin bounded-likelihood-ratio** `NOT_FOUND_NEEDS_HUMAN`. No sharpness may be claimed for P6b | a human with library access |
| 3 | **arXiv:2405.15141** `NOT_READ_HIGH_PRIORITY` — the most important unread reference in the matrix | a human with access |
| 4 | **the estimator literature behind P1/P5a** is named as a phrase, not engaged | blocked by (1) |
| 5 | **non-subsumption by DES / structural FDI** asserted, never proved | out of scope |

### What the writing agent must write

- Apply the **six terminology substitutions** in §10–§11 (below), and update
  the test assertion that pins one of the sentences.
- Keep both negative results visible: `q` is counterfactual and, under fix
  loss, **not evaluable at all**; and there is no MAP-stability result for the
  pinned regime, with P8 showing there cannot be one of P4's form.
- Keep every proposition labelled KNOWN.

**Must not**: claim any proposition is new; claim sharpness for P6b; present
`q` as something the system computes; cite the unlocated reference.

---

## CROSS-PAPER

### Terminology policy — resolved

Full table: `research/PAPER_CROSS_CONSISTENCY.md`.

| object | correct term |
|---|---|
| the mathematical paper's `q_h`, `p_h` | **posterior** — correct, keep it. Both are a prior times a strictly positive function of the data, normalized |
| the **deployed CSIA diagnosis output** | **normalized hypothesis weight** — *not* a posterior, *not* a probability |
| `"confidence"` | **FORBIDDEN** in both papers for both objects, except as a disclaimer about the word |

Four independent reasons the deployed output is not a posterior, **any one
sufficient**: `EPS = 0.02` is a floor inside the logarithm, not a density; the
evidence term is an **exponential moving average** over ~15 ticks rather than a
product of per-tick likelihoods; it is tempered by `EVIDENCE_MULT = 1.5`; the
softmax runs over eight causes asserted exhaustive by the signature table.

**Required replacements: systems paper 2, mathematical paper 6.**

- Systems, lines **1405** and **1408** — the manuscript already states the
  policy correctly at line 251 and these two contradict it. Ledger row `SC-20`
  needs the same substitution.
- Math, lines **648, 665, 667, 668, 669, 674** — all in §10–§11, all describing
  the deployed layer. Lines 56–532 use "posterior" for the formal objects and
  are **correct as they stand**.
- **Warning**: `tests/test_support_state_posterior_range.py` asserts the
  literal string `"no posterior threshold enters the rule"`. Changing math
  line 668 requires updating that assertion in the same commit.

### Collision hazard, stated once

The systems paper's **"normalized hypothesis weight"** (the output, sums to 1)
and the mathematical paper's **`w_h`** (the per-hypothesis validity factor,
does not sum to anything) are **different objects**. Neither paper may use the
bare word "weight" for the other's.

### Shared mechanism — one vocabulary

Diagnostic self-occlusion · target pair `(nominal, gps_fault)` · separating
feature `phys_gps` · gate `gvalid` · condition `D(a,b) = ∅` · design rule *"a
feature intended to discriminate `h` must not be gated by a gate that `h`
closes"*. The formal statement the implemented case satisfies is **P7c**, not
P3.

### Shared numbers — one artifact each

| number | artifact |
|---|---|
| 378,000 / 378,000 | `research/systems-paper/results/checker_agreement.json` |
| 200 ticks, 76 ticks, 28 pairs | `research/systems-paper/results/checker_verdicts.json` |
| 15,595 / 20 / 0 | `research/systems-paper/results/current_stack_structural.json` |
| 0.9691 – 0.9998 | `engineering/v1_1/SUPPORT_STATE_RESULTS.csv` |
| 118.82, 93.31 | `research/wp_c8/results/escalation_algebra.json` |

### Conflicts resolved

1. **118.82 / 125 / 0.98764** — settled; canonical chain above; scientific
   result unchanged.
2. **posterior vs normalized hypothesis weight** — settled; the deployed output
   is a weight, the formal objects are posteriors.
3. **"bench-only" vs "ArduPilot 4.8 replicated"** — both were true of different
   things. **Mechanism B replicates** on ArduPilot 4.8 (preregistered, 20/20,
   0-tick crossing error) and is **INAPPLICABLE** on PX4 SIH. **Mechanism A**
   has only a **negative control** on 4.8, not a replication.
4. **P3 vs P7c** — P7c is the statement the implemented case satisfies; P3
   remains true as the abstract form.

### Conflicts unresolved

| # | conflict | state |
|---|---|---|
| 1 | bibliography verification, both papers | **BLOCKED** — six routes, all 403 |
| 2 | estimator literature for P1/P5a | **BLOCKED** by (1) |
| 3 | non-subsumption by DES / structural FDI | **OPEN** — asserted, not proved |
| 4 | 49 unmapped prose literals, systems paper | **OPEN** — the writing agent decides which need binding |
| 5 | the eight terminology substitutions | **RESOLVED, NOT YET APPLIED** — policy explicit, writing agents apply it |

---

## Handoff files

| | |
|---|---|
| systems bundle | `handoff/SYSTEMS_PAPER_FINAL_HANDOFF.md` (780 lines, self-contained) |
| math bundle | `handoff/MATH_PAPER_FINAL_HANDOFF.md` (555 lines, self-contained) |
| cross-paper policy | `research/PAPER_CROSS_CONSISTENCY.md` |
| this summary | `handoff/DUAL_PAPER_COORDINATION_SUMMARY.md` |

Neither writing agent needs GitHub, a simulator, Python, PX4, ArduPilot or the
repository. Every conclusion that required running code was run here and the
result exported. Everything that could not be established in this environment
is marked **BLOCKED**, not guessed.
