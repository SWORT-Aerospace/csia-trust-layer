# CSIA minimum novel core: the subtraction (stage 2, pre-result)

This file is part of the second-stage novelty verification (2026-09-27/28).
Source ids are listed in `research/csia_novelty_audit/BIBLIOGRAPHY.md`. Status
levels N0–N4 are defined in
`research/csia_novelty_audit/CSIA_NOVELTY_VERIFICATION.md` §17. No XSYS-001
confirmatory material was opened.

The exercise follows the brief:

1. Start from the whole CSIA vision.
2. Remove everything the prior art establishes.
3. Stop when only potentially distinct elements remain.

**The remainder is small, and it is not made to look larger.**

## 1. The starting set

This is the whole vision, as CSIA's own documents and code describe it (stage-1
matrix C1–C20, plus the architecture):

| # | element |
|---|---|
| S1 | cross-sensor validation |
| S2 | analytical redundancy across subsystems ("cross-system assurance") |
| S3 | a cross-domain evidence graph / signature matrix |
| S4 | physical consequences as witnesses (vehicle dynamics) |
| S5 | actuator-versus-sensor/telemetry discrimination |
| S6 | controller compensation as evidence |
| S7 | temporal fault signatures; evidence usefulness changing through onset and compensation |
| S8 | explicit temporal validity of evidence |
| S9 | structural hypothesis elimination |
| S10 | three-valued evidence ("not measurable" is neither true nor false) |
| S11 | candidate sets and retained ambiguity (AMBIGUOUS) |
| S12 | "survival is not support" (UNIQUE requires affirmative confirmation; UNSUPPORTED) |
| S13 | gated negative evidence (a "nominal" witness only if a genuine fault would be detectable) |
| S14 | diagnostic self-occlusion (the response removes the evidence) |
| S15 | separability decidable from the signature table before the run |
| S16 | detection / isolation / certification / action separation |
| S17 | the support certificate |
| S18 | temporal + structural integration |
| S19 | bounded runtime action authority (FORGE) |
| S20 | fault-tolerant reconfiguration |
| S21 | the combined architecture |
| S22 | the XSYS-001 pairing: windowed dynamics and compensation witnesses for physical loss versus matched RPM-telemetry corruption |
| S23 | the XSYS-001 validation design: matched by construction, invalid-window control, preregistered and blinded, zero-WRONG, cluster unit |

## 2. The subtraction

| # | remove? | why | closest source | level |
|---|---|---|---|---|
| S1 | **REMOVE** | analytical redundancy, parity relations | B04, B05, B06 | V0 (textbook) |
| S2 | **REMOVE** | vehicle-level reasoning across subsystems | B58, B59, B60, P12 | V0 |
| S3 | **REMOVE** | D-matrix, fault-signature matrix, fault-propagation graph | B08, B62, P07 | V0 |
| S4 | **REMOVE** | multiple-model banks, control invariants, fielded autopilot | B44, B92/B133, B130 | **V4** (B130) |
| S5 | **REMOVE** | a 1987 patent, IMM/MMAE, engine filter banks, the EPOS family | P01, B43, B44, B46, P03–P05 | V0 |
| S6 | **REMOVE** | `thrust_balance` and the yaw integrator as root-cause evidence | B130 | **V4** |
| S7 | **REMOVE** | transient signatures; transient then steady state | B37, B38, B40 | V0 |
| S8 | **REMOVE** as a principle | mode-scoped ARR validity; residual validity regions; phase-conditioned suspension in fielded code | B119, B142, B130 | **V4** (B130) |
| S9 | **REMOVE** | consistency-based diagnosis | B28, B29 | V0 |
| S10 | **REMOVE** | Kleene / LTL3 inconclusive; SEVA BLIND status | B70, B89 | V0 |
| S11 | **REMOVE** | minimal diagnosis sets; ambiguity groups | B28, B62, P06 | V0 |
| S12 | **REMOVE** | consistency–abduction spectrum; explicit insufficient-evidence verdicts | B31, B137 | V0 |
| S13 | **REMOVE** as a concept | physical negation; sensitivity-conditioned FDI. The 2× rule is a parameter | B30, B138 | V0 |
| S14 | **REMOVE** | the PX4 latch rationale, in code; closed-loop masking | B131, B117, B99 | **V4** (B131) |
| S15 | **REMOVE** | structural isolability analysis; diagnosability | B23, B25, B36, B134 | V0 / V2 |
| S16 | **REMOVE** | FD versus FDE versus integrity in RAIM; an FDI component with a separate assurance monitor and contingency management | B87, B120 | V0 |
| S17 | **REMOVE** | a distinguishing-test record; weaker than protection levels or false-isolation bounds | B62, B87, B122 | V0 |
| S18 | **REMOVE** | TRANSCEND, QED, mode-sequence ARRs, structural-temporal propagation | B37, B39, B119, P07 | V0 |
| S19 | **REMOVE** (not implemented; concept known) | RAIM authorization, Simplex/RTA, health-score-gated reconfiguration | B87, B79–B81, P24 | V0 |
| S20 | **REMOVE** | FTC and control allocation | B19, B20, B44 | V0 |
| S21 | **REMOVE** | no emergent capability, interaction or formal relation shown | CSIA_NOVELTY_VERIFICATION §§13, 15 | — |
| S22 | **KEEP, narrowed** → MNC-1 | the conjunction was not found in the searched sources | EPOS, B117, B118 closest | V0 |
| S23 | **KEEP, narrowed** → MNC-2 | the conjunction was not found in the searched sources; analogues exist | B147, B122, B65 closest | V0 |

## 3. The remainder

### MNC-1: windowed paired witnesses for physical loss versus matched telemetry corruption

> For a multirotor under closed-loop attitude control, rotor *m*'s RPM
> telemetry is a monitoring channel, not a control feedback. The task is to
> tell physical loss of rotor *m*'s thrust effectiveness from corruption of
> that telemetry that reproduces the same local RPM deficit.
>
> Two witnesses do it, and the controller itself makes and unmakes their
> informativeness:
>
> - **a transient dynamics witness**: body rate along the rotor's loss axis in
>   the first 0.2 s after onset;
> - **a post-compensation witness**: the rotor's allocator command relative to
>   the other rotors, measured after compensation settles.
>
> Each witness is **inapplicable** (None), not negative, outside its window.
> Each may affirm "nominal" only when the RPM-implied loss would have produced
> at least twice its detection threshold. They are combined by set elimination
> that names a cause only if the rival is refuted and the named cause is
> confirmed; otherwise the answer is AMBIGUOUS.

| part | known? | closest |
|---|---|---|
| the pair and its shared local symptom | CLOSE (other plants) | EPOS; B118; P15 |
| dynamics witness in the transient | KNOWN | B37; B48, B54, B125; B130 (descent) |
| compensation witness after settling | KNOWN | B130 (**V4**); B118 |
| window-scoped applicability | CLOSE | B119; B142; B130/B131 (**V4**) |
| detectability gate | CLOSE | B30; B138 |
| elimination with confirmation; AMBIGUOUS | KNOWN | B28; B31 |
| **the conjunction, for this pair, on a multirotor** | **not found in the searched sources** | — |

**Status: N2 (possibly distinct combination), LOW confidence.**

It is pending the ten P0 sources in
`research/csia_novelty_audit/CSIA_FULLTEXT_VERIFICATION_QUEUE.md`. It drops
to N1 if B118, the EPOS text, B123/B124, B125 or the INDI source is found to
contain the transient-plus-compensation pairing, or the RPM-sensor case.

### MNC-2: the matched-by-construction validation design

> Case B is built by replaying case A's observed local-symptom ratio on the
> telemetry channel, so the local evidence cannot separate the pair by
> construction. The candidate rule is evaluated under:
>
> - frozen rules;
> - two-stage, label-blinded scoring;
> - a primary decision that requires **zero** wrong attributions;
> - the nuisance condition as the independent unit of the confidence bound;
> - a preregistered **negative control** that reads a valid witness outside
>   its window and predicts wrong attribution.

| part | known? | closest |
|---|---|---|
| constructing a corruption that matches the physics or local model | CLOSE (security) | B147; B94, B115 |
| a false-isolation constraint | KNOWN (theory) | B122, B121, B71 |
| preregistration, blinded outcome assessment, cluster as unit | KNOWN (other sciences) | standard methodology |
| ablation / control configurations | KNOWN (routine) | S2Q40 |
| **the conjunction, applied to FDI evaluation of this pair** | **not found in the searched sources** | — |

**Status: N2, LOW confidence.** It is also the element least likely to count
as a scientific contribution on its own. It is methodology.

## 4. What the remainder is not

- **Not an architecture.** CSIA v2 is unchanged by it, and v2 itself is
  atemporal.
- **Not a new diagnostic principle.** Every part is known or close.
- **Not strengthened or weakened by the XSYS-001 result, as a novelty
  status.**
  - A supported primary would be **evidence that the instance works** in
    simulation.
  - A failed primary would be evidence that it does not.
  - Neither changes what the literature already contains.
  - The status stays N2 either way until the P0 queue is read.

## 5. Stage-1 claims, re-graded

| claim | stage-1 status | stage-2 level | what moved it |
|---|---|---|---|
| C1 | KNOWN | N0 | — |
| C2 | KNOWN | N0 | — |
| C3 | KNOWN | N0 | B130 at V4 |
| C4 | KNOWN | N0 | B130 at V4 |
| C5 | KNOWN | N0 | — |
| C6 | CLOSE_PRIOR_ART | N1 | B119, B142; B130/B131 at V4 |
| C7 | KNOWN | N0 | — |
| C8 | KNOWN | N0 | — |
| C9 | LIKELY_KNOWN | N1 | B87; B120 |
| C10 | CLOSE_PRIOR_ART | UNSUPPORTED as a CSIA capability; concept N0 | P24 |
| C11 | KNOWN | N0 | — |
| C12 | POSSIBLY_DISTINCT | **N1** | the IVHM challenge (verification §13) |
| C13 | KNOWN | N0 | — |
| C14 | LIKELY_KNOWN | N1 | B134 (V2) |
| C15 | CLOSE_PRIOR_ART | N1 | the PX4 latch at V4 (B131) |
| C16 | CLOSE_PRIOR_ART | N1 | B138 |
| C17 | APPARENTLY_NOVEL (LOW) | **N2** (inside MNC-2) | B147; B122 |
| C18 | POSSIBLY_DISTINCT | **N2** (MNC-1) | the EPOS text (S2Q35) |
| C19 | UNSUPPORTED_NOVELTY_CLAIM | UNSUPPORTED | — |
| C20 | LIKELY_KNOWN | N1 | verification §10 |

Stage 2 raised nothing. Two statuses fell: C12, and C17 (from "apparently" to
"possibly distinct").
