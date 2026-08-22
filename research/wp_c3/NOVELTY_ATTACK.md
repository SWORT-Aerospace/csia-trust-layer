# WP-C3 Part 4 — Novelty attack on both objects

**Same standing limitation.** Full-text access is still refused —
`sciencedirect.com`, `arxiv.org`, `inria.hal.science`, `drops.dagstuhl.de`,
`faultdiagnosistoolbox.github.io` all return `EGRESS_BLOCKED`. **Zero full
texts have been read across WP-C1, WP-C2 and WP-C3.** Everything below rests
on search snippets and recall. Bibliographic details are unverified. **Absence
of a match here is weak evidence and this is not a literature review.**

Posture unchanged: **claim novelty nowhere.** The reading list in
`research/wp_c2/NOVELTY_ATTACK_REQUEST.md` is extended below rather than any
conclusion being drawn.

---

## Object 1: the effective signature matrix `S_eff`

| # | Closest known result | Variable mapping | Implies ours? |
|---|---|---|---|
| 1 | **Fault masking in multi-fault FDI.** One fault's effects obscure another's, producing ambiguous signatures and reduced isolability. | their masking ↔ two faults producing similar *symptoms* | **NO — checked, and it is a different thing.** Masking concerns symptom *similarity* between co-occurring faults. `S_eff` concerns a fault destroying the *availability* of its own evidence. A masked fault's residual still exists and is computed; a self-occluded one is skipped entirely (`bayes.py:99-100`). The prompt's suspicion that these might be the same under different words does not hold. |
| 2 | **Isolability of faults in sensor fault diagnosis** (Mech. Syst. Signal Process. 2011) | sensor faults as first-class hypotheses | **UNCLEAR.** Snippet-level only. Concerns isolating sensor faults from process faults, not availability that depends on the hypothesis. |
| 3 | **Structural isolability / isolability matrix** (Fault Diagnosis Toolbox line) | their isolability matrix ↔ Π(S) | **NO for `S_eff`, YES for `S`.** The classical object is exactly our `S`, computed with residual availability fixed at design. That is the baseline `S_eff` is measured against, and we claim nothing about it. |
| 4 | **Robust diagnosability under sensor loss** (Carvalho et al.) | their failed-sensor subsets ↔ our closed gates | **PARTIAL, and the gap is precise.** They quantify over *all* loss patterns, adversarially and hypothesis-independently. `S_eff` makes the loss pattern a *function of the hypothesis under test*. Whether their formulation admits a hypothesis-indexed loss set is the single question that decides this, and it needs the full text. |

**What survives, narrowly and unverified:** an entrywise mask
`S_eff = S ∧ ¬closes` making residual availability hypothesis-indexed, with
the immediate monotonicity theorem and the resulting *overstatement gap*
κ(S_eff) − κ(S) as a measurable quantity for a real system.

**The term that would settle it**, still unresolved by snippet search:
*fault-induced unobservability*, *self-masking faults*, *diagnosis under
fault-correlated observation loss*.

---

## Object 2: diagnostic reliability structure

| # | Closest known result | Variable mapping | Implies ours? |
|---|---|---|---|
| 5 | **Birnbaum importance, coherent systems** (Birnbaum 1969; Fussell–Vesely relationships) | their components ↔ our gates and channels; their structure function ↔ φ_ab | **YES for the machinery.** We apply standard coherent-system theory unchanged. Nothing about cut sets or Birnbaum importance is ours. |
| 6 | **Diagnostic Importance Factor (DIF)** | P(component failed \| system failed) | **NO — a false friend, and worth naming.** DIF measures a component's importance *to diagnosing a system failure*. Ours measures a component's importance *to the system's capacity to diagnose at all*. The word "diagnostic" appears in both and means opposite things. |
| 7 | **Non-coherent Birnbaum extensions** (Boolean/BDD formulations) | — | **NO.** Our φ is monotone, verified across all 4096 states, so the coherent theory suffices and the non-coherent extension is not needed. |

**What survives, narrowly and unverified:** applying coherent-system structure
functions to *diagnostic capability* rather than to function, so that minimal
cut sets are minimal degradations that destroy a fault distinction and
Birnbaum importance ranks components by diagnostic rather than functional
criticality. **This one has a real chance of being occupied under a name
neither of us has guessed** — that assessment from the task prompt is
unchanged by anything found here.

---

## Extension to the reading list

Add to `research/wp_c2/NOVELTY_ATTACK_REQUEST.md`:

### 6. Carvalho et al. 2013 — one additional question

Does the sensor-failure set quantified over depend on the fault being
diagnosed, or is it a fixed adversarial set independent of the hypothesis?
**This single question decides whether `S_eff` is occupied.**

### 7. Any FDI text with a masking chapter

Confirm the distinction asserted in row 1: does "masking" anywhere denote a
fault suppressing the *availability* of a residual, as opposed to two faults
producing similar residual *values*? If any source uses masking in the
availability sense, row 1 flips to `PARTIAL` and `S_eff` is largely occupied.

### 8. Reliability-theory sweep

Search for coherent-system structure functions applied to observability,
detectability, or diagnosability *as the top event* — i.e. where the "system
failure" being analysed is the loss of a diagnostic distinction rather than
the loss of a function. Candidate venues: Reliability Engineering & System
Safety, IEEE Trans. Reliability. **If this exists, Object 2 is occupied.**

---

## Bottom line

Neither object is claimed as novel. Object 1's nearest neighbour (masking) was
checked and is genuinely a different phenomenon. Object 2's machinery is
entirely standard and only its *application target* is unusual. Both remain
`UNCLEAR` pending full text, which this environment cannot supply.

**Sources** (search results only; none fetched):

- [Isolability of faults in sensor fault diagnosis — MSSP](https://www.sciencedirect.com/science/article/abs/pii/S0888327011001105)
- [Isolability analysis and sensor placement — Fault Diagnosis Toolbox](https://faultdiagnosistoolbox.github.io/tutorial/isolability-and-sensorplacement/)
- [Fault detection and isolation — overview](https://grokipedia.com/page/Fault_detection_and_isolation)
- [Relationships of Fussell–Vesely and Birnbaum importance to structural importance in coherent systems — RESS](https://www.sciencedirect.com/science/article/abs/pii/S0951832099000435)
- [On the Boolean extension of the Birnbaum importance to non-coherent systems — RESS](https://www.sciencedirect.com/science/article/abs/pii/S0951832016310286)
- [Robust diagnosis of DES against permanent loss of observations — Automatica](https://www.sciencedirect.com/science/article/abs/pii/S0005109812004803)
