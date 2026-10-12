# Novelty red team: a mock hostile reviewer

This is part of the pre-result novelty audit (2026-09-27). Source ids are in
`research/csia_novelty_audit/BIBLIOGRAPHY.md`, and claim ids are in
`research/csia_novelty_audit/CSIA_PRIOR_ART_MATRIX.csv`. It uses no
XSYS-001 result.

The reviewer below writes from FDI, DX and IVHM experience and has read the
sources this audit could only see in summary. Each objection is written as
strongly as the evidence allows, then judged:

- **VALID**: the objection stands; the paper must concede it.
- **PARTIALLY VALID**: it stands for part of the claim; the paper must
  concede that part and argue the rest with evidence.
- **NOT SUPPORTED**: the evidence found does not sustain it.

---

## R1. "This is analytical redundancy."

> Every CSIA witness is a residual between a measured signal and a model
> prediction, thresholded:
>
> - RPM against a first-order motor lag;
> - body rate along the loss axis against the pre-fault baseline;
> - allocator ratio against the other motors.
>
> That is the definition of an analytical redundancy relation. Chow and Willsky
> (B05) characterized it in 1984, Potter and Suman (B04) in 1977, Beard and
> Jones (B03) in the early 1970s.

**VALID for the evidence layer.** Every witness in
`docs/research/XSYS_001_PREREGISTRATION.md` §7.2 is an analytical redundancy
relation with a threshold, and so is every edge of the v1 trust graph.

What the objection does not address is what happens after the residuals: the
verdict rule. That is taken up in R5 and R7.

**Concede:** CSIA contributes no new residual-generation method.

## R2. "This is ordinary model-based FDI."

> Residual generation, then evaluation, then isolation against a signature
> matrix: the textbook pipeline (B06, B07, B08). The decision layer is
> consistency-based diagnosis. Cordier et al. (B27) showed in 2004 that the
> FDI and DX formulations coincide under stated conditions.

**PARTIALLY VALID.**

- **VALID for the diagnostic core.** v2 localization is conflict-driven set
  elimination over a signature matrix.
- **Not fully answered by the core:** CSIA's verdict lattice.
  - It separates UNIQUE from AMBIGUOUS from UNSUPPORTED from NO_EVIDENCE.
  - It requires affirmative confirmation, not merely survival, for UNIQUE.
  - It makes out-of-window evidence inapplicable rather than negative.

Console and Torasso (B31) already frame elimination plus confirmation as one
point on a known spectrum. The lattice is therefore a **stated
configuration** of known logic, not a new logic.

**Concede:** the core is model-based FDI and DX.
**Argue only:** that the configuration is chosen for assurance use and
evaluated under a zero-WRONG criterion.

## R3. "This is IVHM."

> Aircraft-level reasoning over evidence from many subsystems, candidate
> hypotheses, ambiguity groups, mitigation of adverse events. VIPR (B59, B60)
> did this with Honeywell and NASA. The 777's central maintenance function
> screened cascaded faults across LRUs in 1992 (B58). Aaseng's blueprint (B57)
> is from 2001.

**PARTIALLY VALID.** IVHM names a discipline and a scope. CSIA lies inside
that scope: a runtime, vehicle-level evidence reasoner.

The objection is weakest on a point this audit **could not check**: whether
VIPR and similar reasoners rank ambiguity groups toward a single named cause
(the summaries say they "rank-order"), or refuse to name one without a
discriminating measurement.

If they refuse, R3 becomes VALID. If they rank, the difference is real but
narrow: a decision policy, not an architecture.

**Concede:** CSIA is an IVHM reasoning layer.
**Do not claim:** a new IVHM architecture.

## R4. "Fault signature matrices already do this."

> The v2 signature matrix is a fault signature matrix with entries true, false
> and unknown. Gertler (B08) formalized structured residuals and isolability.
> Timed matrices that record occurrence order and time (B40) already encode
> the temporal dimension. D-matrices (B62) are the testability form.

**VALID.** The three-valued, cross-domain signature matrix is a fault
signature matrix. CSIA's temporal windows decide when an entry is applicable
rather than adding time as a signature property, but that does not escape
the objection: timed and mode-dependent signatures cover it closely (matrix
C6, CLOSE_PRIOR_ART).

**Concede fully.**

## R5. "Consistency-based diagnosis already preserves candidate sets."

> Reiter (B28) returns every minimal diagnosis. GDE (B29) keeps the candidates
> and asks for the best discriminating measurement. "AMBIGUOUS" is the ordinary
> output of 1987-era diagnosis.

**VALID.** Ambiguity preservation is the default of consistency-based
diagnosis. The earlier repository audits reached the same verdict for the
analogous claims.

The one thing CSIA adds is a rule forbidding a probabilistic layer from
turning ambiguity into a named cause. It matters only against probabilistic
reasoners (MMAE, Bayesian networks, VIPR-style ranking), and it is
demonstrated only if a head-to-head comparison is run. XSYS-001 does not run
one.

**Concede fully.**

## R6. "Fault-tolerant control already uses controller and vehicle response."

> MMAE/IMM banks (B43, B44, B12, B13) separate sensor from actuator failures
> through the dynamics, and redistribute commands. Loss-of-effectiveness
> estimation on quadrotors (B48, B54) reads the attitude response. ArduPilot
> (B55) reads motor saturation, which is controller compensation, as evidence
> of propulsion failure.

**VALID.** Both CSIA witnesses are established signal choices; see matrix C3
and C4 (KNOWN).

**Concede fully.**

## R7. "There is no new algorithm."

> Set elimination, thresholded residuals, windowed means, a Clopper–Pearson
> bound. Nothing in the pipeline is algorithmically new.

**VALID.** The earlier repository audit of the mathematical paper
(`research/math-paper/NOVELTY_AUDIT.md`) reaches the same conclusion for its
own propositions: every one is KNOWN.

A paper must not position CSIA as an algorithmic contribution.

## R8. "The experiment is simulation-only."

> PX4 SIH is a simplified multirotor; there is no real ESC, rotor, telemetry
> path or sensor noise. The noise source is a single `rand()` stream. Any claim
> is about SIH, not aircraft.

**VALID.** The preregistration concedes it (§19). The amendments exist
because the simulator's noise needed an independence design.

The consequence for novelty: the experimental contribution is bounded to "in
the tested PX4 SIH environment and degradation regime". That is the wording
the confirmatory grant itself requires.

## R9. "The matched telemetry corruption is artificial."

> Case B multiplies a nominal flight's RPM by case A's observed ratio, offline.
> No known ESC failure produces exactly that. The experiment therefore tests a
> constructed adversary, not a failure mode.

**PARTIALLY VALID.**

- **Valid as to external validity.** Case B models no specific telemetry
  failure. The preregistration says so (§19).
- **Not valid as to the design's purpose.** Matching the local symptom by
  construction is what makes the question well posed. Any separation must
  then come from other domains, because the local channel carries none. This
  is the adversarial-test logic of the CPS-security literature
  (B92, B93, B115), and it is the strongest test of the specific claim.

**Concede:** the result cannot speak to realistic telemetry faults.
**Keep:** the argument that matched construction is a feature for the
question asked.

## R10. "The architecture merely combines known components."

> Three-valued evidence (B70, B89), consistency-based elimination (B28),
> temporal windows (B37), physical witnesses (B44, B92), compensation evidence
> (B55), ambiguity groups (B62), runtime-assurance separation (B81): all
> known. A combination of known parts is an integration, not a contribution,
> unless the combination has a property the parts lack.

**VALID, on present evidence.** The combination has not been shown to have a
property its parts lack.

The objection fails only if CSIA shows one of two things:

1. **A formal property.** For example, a soundness statement: under stated
   model-validity and window assumptions, UNIQUE implies the true cause. It
   would need a proof, and it would need to be compared with B71 and B72.
2. **An empirical property.** On the same matched set, established methods
   (MMAE/IMM, a dynamic Bayesian network, a TRANSCEND-style signature
   matcher) produce WRONG or unjustified UNIQUE outputs, and CSIA does not, at
   comparable resolving power.

Neither exists today (matrix C12, POSSIBLY_DISTINCT, LOW confidence).

---

## Additional objections the reviewer would raise

### R11. "Temporal validity is TRANSCEND with different words."

**PARTIALLY VALID.**

- The idea that the value of evidence depends on the fault's phase is
  TRANSCEND's (B37, 1999).
- CSIA's representation is not shown in any summary: out-of-window evidence is
  *inapplicable* (predicate None) inside a three-valued elimination engine.
- The hybrid- and mode-dependent-ARR literature (B41, B42) is the likely
  place to find it. It was not read.

(Matrix C6.)

### R12. "The zero-WRONG criterion is just an FDI correctness requirement."

**PARTIALLY VALID.**

- Bozzano et al. (B71) specify correctness (no false diagnosis) as an FDI
  requirement and synthesize components that meet it.
- Set-based FDI (B72) guarantees no false alarm under bounded uncertainty.
- XSYS-001 uses zero-WRONG as an **empirical, preregistered acceptance
  criterion** on a closed-loop continuous simulation, not as a synthesis
  target.

That is a difference in use, not in concept. (Matrix C17.)

### R13. "Your own v2 is atemporal. You cannot claim temporal evidence accumulation."

**VALID.** v2 accumulates no evidence across snapshots (repository gap G1).
XSYS-001 evaluates it at two checkpoints. On temporal accumulation, CSIA is
behind the prior art (B35, B37, B67). (Matrix C7.)

### R14. "CSIA does not bound any action, so 'runtime assurance' is a label."

**VALID.** CSIA issues no command and implements no authorization interface.
(Matrix C19, UNSUPPORTED_NOVELTY_CLAIM.)

---

## Summary

| objection | verdict |
|---|---|
| R1 analytical redundancy | VALID (evidence layer) |
| R2 ordinary model-based FDI | PARTIALLY VALID |
| R3 IVHM | PARTIALLY VALID |
| R4 fault signature matrices | VALID |
| R5 consistency-based diagnosis preserves candidates | VALID |
| R6 FTC uses controller / vehicle response | VALID |
| R7 no new algorithm | VALID |
| R8 simulation-only | VALID |
| R9 artificial matched corruption | PARTIALLY VALID |
| R10 merely combines known components | VALID (on present evidence) |
| R11 temporal validity = TRANSCEND | PARTIALLY VALID |
| R12 zero-WRONG = FDI correctness | PARTIALLY VALID |
| R13 v2 is atemporal | VALID |
| R14 no action bounded | VALID |

**No objection was judged NOT SUPPORTED.** The partially valid ones leave room
for four things:

- a configuration of known logic chosen for assurance use;
- an adversarially matched experimental instance;
- a preregistered zero-WRONG evaluation practice;
- a representation of temporal validity as applicability.

None of these is an algorithmic or architectural novelty claim.
