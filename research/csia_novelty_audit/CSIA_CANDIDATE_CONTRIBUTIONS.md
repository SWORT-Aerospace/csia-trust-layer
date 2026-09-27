# Candidate contributions, positioning and the novelty boundary

Part of the pre-result novelty audit (2026-09-27). Source ids:
`research/csia_novelty_audit/BIBLIOGRAPHY.md`. Claim ids:
`research/csia_novelty_audit/CSIA_PRIOR_ART_MATRIX.csv`. No XSYS-001 result
was used.

---

## 1. Novelty by kind, kept separate

| kind | assessment | status | confidence | basis |
|---|---|---|---|---|
| **algorithmic** | none. Residuals, thresholds, windowed means, conflict-driven set elimination, CUSUM, a Beta recursion, a Clopper–Pearson bound: all established | KNOWN | HIGH | R1, R7; matrix C1–C5, C7, C11; `research/math-paper/NOVELTY_AUDIT.md` |
| **architectural** | a specific combination of three-valued cross-domain evidence, per-evidence temporal applicability, elimination-plus-confirmation verdicts, function justification and a read-only posture. No searched system was *seen* to combine all of them, but every part has an antecedent. The combination has no demonstrated emergent property | POSSIBLY_DISTINCT | LOW | matrix C12; `research/csia_novelty_audit/CSIA_CLOSEST_SYSTEMS.md` |
| **assurance-semantic** | the verdict lattice: UNIQUE only with affirmative confirmation, AMBIGUOUS, UNSUPPORTED, NO_EVIDENCE. Plus the rule that a posterior leader is never reported as a cause without a discriminating measurement. Antecedents: B31 (the consistency/abduction spectrum), B87 (integrity not available), B71 (FDI correctness), B28. Distinct only as a **configuration chosen for assurance**, across heterogeneous domains | CLOSE_PRIOR_ART | MEDIUM | matrix C8, C9, C13, C20; R2, R5 |
| **action / certification semantics** | proposed, not built. RAIM, ConSerts and RTA already bind evidence to permitted operation | CLOSE_PRIOR_ART (principle), UNSUPPORTED_NOVELTY_CLAIM (as a CSIA capability) | MEDIUM / HIGH | matrix C10, C19 |
| **experimental** | the XSYS-001 instance: a multirotor ESC-RPM channel against a physical rotor-effectiveness loss **matched by construction**, separated only by windowed dynamics and compensation evidence, with ambiguity permitted. Not found in the searched literature; the problem class is KNOWN | POSSIBLY_DISTINCT | LOW-MEDIUM | matrix C18; `research/csia_novelty_audit/XSYS_001_NOVELTY_AUDIT.md` |
| **validation methodology** | used together in an FDI evaluation: preregistration, frozen manifests, two-stage label-blinded scoring, zero-WRONG in the primary rule, the nuisance condition as the bounding unit, a simulator noise-independence audit. Not seen in the searched FDI/UAV/PHM literature. Each practice is standard elsewhere | APPARENTLY_NOVEL | LOW | matrix C17 |
| **product / engineering** | deterministic replay, sealed artifacts, a read-only output firewall, a no-command posture. Good engineering practice; fielded autopilots already run local and compensation-based propulsion detectors (B55, B56, P09) | KNOWN | MEDIUM | matrix C19; B55, B56 |

**Reading the table.** The only rows above CLOSE_PRIOR_ART are
**experimental** and **validation-methodology**, and both are LOW or
LOW-MEDIUM confidence, because the evidence is absence in search summaries.
Neither is an algorithm or an architecture.

---

## 2. Publication positioning the evidence supports

The labels below are ranked from least to most supportable. The ranking is
not by attractiveness.

| label | supportable? | why |
|---|---|---|
| new algorithm | **no** | R7; everything algorithmic is KNOWN |
| new architecture | **no, not yet** | R10; C12 is POSSIBLY_DISTINCT at LOW confidence, with no emergent property shown |
| new assurance semantics | **no, as stated** | C8, C9 and C13 are covered; the lattice is a configuration of B31-style logic |
| new diagnostic formulation | **weak** | the per-evidence temporal-applicability representation (C6) is CLOSE_PRIOR_ART |
| new integration of known methods | **yes, but modest** | an honest description of v2 plus the XSYS-001 witnesses |
| new application of established methods | **yes** | consistency-based diagnosis with windowed analytical-redundancy evidence, applied to a multirotor actuator-versus-telemetry pair |
| new empirical result | **possibly** | depends on the XSYS-001 result, which this audit does not use, and on a baseline comparison it does not include |
| new validation methodology | **possibly, modestly** | the preregistered, blinded, zero-WRONG, matched-set protocol (C17). Transplanted research-integrity practice, not new statistics |

**Best defensible positioning:**

> **An empirical and methodological study of an established diagnostic
> formulation.**
>
> - **Method.** Consistency-based diagnosis over analytical-redundancy
>   evidence, each piece admissible only in its physically justified time
>   window. The paper must cite Reiter, TRANSCEND, R2U2, VIPR, the IMM/MMAE
>   sensor-versus-actuator literature and RAIM as the antecedents.
> - **Test.** A deliberately matched multirotor case (physical rotor
>   effectiveness loss versus RPM-telemetry corruption replaying the same
>   ratio).
> - **Protocol.** A preregistered, label-blinded protocol whose primary rule
>   requires zero wrong attributions.

This fits a PHM, DX or SAFEPROCESS-type venue as an application and
methodology paper. It does **not** fit a claim of a new architecture or a new
theory.

---

## 3. The narrowest defensible candidate novelty statement

> The potentially distinct contribution is **not**:
>
> - cross-sensor or cross-domain analytical redundancy;
> - consistency-based candidate elimination;
> - ambiguity groups;
> - temporal fault signatures;
> - the use of vehicle dynamics or controller compensation as fault evidence;
> - sensor-versus-actuator fault discrimination;
> - three-valued verdicts;
> - runtime assurance.
>
> All of these are established (B04, B05, B28, B29, B37, B43, B44, B55, B62,
> B70, B79, B87, P01, P03).
>
> It **is** the formulation and preregistered, label-blinded evaluation of a
> **zero-wrong-attribution verdict rule**. The rule issues a unique cause only
> when every alternative is refuted by analytical-redundancy evidence that is
> admissible in its own physically justified time window. Otherwise it returns
> AMBIGUOUS, UNSUPPORTED or NO_EVIDENCE.
>
> The conditions: a matched pair whose local symptom is **identical by
> construction** (physical rotor-effectiveness loss versus RPM-telemetry
> corruption replaying the same ratio), on a closed-loop multirotor
> simulation (PX4 SIH), with the nuisance condition as the independent unit.
>
> The semantics: out-of-window or ungated evidence is inapplicable, never
> negative, and a surviving hypothesis is never reported as the cause without
> affirmative confirmation.

**Conditions under which even this statement fails:**

1. A professional search finds a matched sensor-corruption versus physical-
   fault evaluation in the FDI, PHM or engine literature. ProDiMES and the
   EPOS family are the prime suspects.
2. A registered report or blinded evaluation exists in FDI or PHM.
3. The full text of B37, B41, B42 or B69 shows the temporal-applicability
   representation.

If all three hold, the literature supports **no** novelty statement beyond
"a careful application". The audit would then have to say so.

**What the statement does not say.** It claims no empirical result. Whether
the rule achieves anything on the matched set is exactly what XSYS-001 tests.
This audit is independent of that outcome.

---

## 4. What would make CSIA a stronger contribution

These directions come from gaps this audit found in the prior art. None
touches XSYS-001, CSIA v1/v2 or any frozen artifact. They are future work
for separate authorization.

| # | direction | gap it targets | nearest prior art to beat | why it could be distinct |
|---|---|---|---|---|
| F1 | **A soundness theorem for the verdict rule**. Under stated model-validity, noise-bound and window assumptions, UNIQUE ⇒ the true cause, and AMBIGUOUS whenever the evidence does not separate the causes. It should be mechanized, and relate the gate and window conditions to structural isolability | no searched source states a soundness property for a runtime cross-domain verdict with three-valued, window-scoped evidence | B71 (FDI correctness synthesis, discrete), B72 and B111 (guaranteed set-based FDI), B09 (structural isolability) | continuous closed-loop evidence with windowed applicability, rather than a discrete model or a single residual set |
| F2 | **A baseline comparison on the matched set**. MMAE/IMM, a hybrid dynamic Bayesian network, a TRANSCEND/QED-style matcher and a set-valued observer, each scored with the same WRONG / UNIQUE / AMBIGUOUS taxonomy | the internal-only comparison in XSYS-001 (V0–V4); R10 and R5 stand until this exists | B43, B44, B35, B37, B72 | it would show whether the refusal semantics avoid wrong attributions that probabilistic isolation makes when the local channel is matched. This is the only test that answers "IVHM with different words" |
| F3 | **Temporal diagnosability**. Derive each evidence channel's validity window from the dynamics (for example the time-varying detectability of a fault through the closed loop) instead of fixing it from apparatus data | windows are fixed empirically in XSYS-001 §7.1; TRANSCEND switches between transient and steady-state analysis qualitatively | B37, B38, B40, B41, B101 | a quantitative, per-channel window with a stated detectability condition, tied to the gate rule (matrix C16) |
| F4 | **Verdict-typed action authorization**. A "cause integrity" analogue of the protection level against the alert limit: each permitted downstream action requires a minimum verdict strength, with a risk budget for WRONG | CSIA issues no command (C19); RAIM does this for position only | B87, B84, B77, B81 | cross-domain root-cause authorization with a formal link to the verdict lattice. It must reduce against RAIM, ConSerts and safe diagnosability before any claim |
| F5 | **Evidence independence and common-cause provenance**. Does a verdict rest on channels that share an upstream source? | the thin "evidence layer" identified in `research/frontier_selection/LITERATURE_FRONTIER_MAP.md` | covariance intersection, ARP4761 common-cause analysis (not searched here) | already the repository's selected frontier candidate; it strengthens the soundness assumptions of F1 |
| F6 | **Real ESC / telemetry hardware**. A bench with a torque channel and real DShot/CAN telemetry fault injection | external validity (R8, R9) | B52 (null-space excitation), P09, B53 | turns the matched-set method into evidence about real failure modes |
| F7 | **Active evidence acquisition under the refusal rule**. When the verdict is AMBIGUOUS, design a safe excitation, for example in the control null space, that makes a discriminating witness applicable | the no-command posture forbids this today | B74, B75, B73, B52, B76 | combining active diagnosis with the zero-WRONG verdict rule and runtime-assurance constraints was not seen; lower priority, because active diagnosis itself is mature |
| F8 | **Multiple and unmodelled faults** within the verdict lattice (UNSUPPORTED as an open-set signal) | XSYS-001 tests one motor, one fault direction and two causes | B102, open-set diagnosis (earlier repository records S058, S059) | only if tied to F1's soundness statement |

**Priority.** F2 comes first, because it is the only one that answers the
hardest question. F1 comes second, because it is the only route to a
defensible "formulation" contribution. F3 comes third. F4 comes only after
F1 and F2.
