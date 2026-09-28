# CSIA-DX (conditional diagnosability): formalization, adversarial novelty review, usefulness, decision

Written 2026-09-28. **This is a review, not an implementation.**

- No CSIA code, frozen behaviour or XSYS-001 artifact was changed.
- Nothing was built or run, apart from a throwaway check of the toy
  matrices, which is not in the repository.

Source ids are listed in `research/csia_dx/BIBLIOGRAPHY.md`. The queries are
in `research/csia_dx/SEARCH_LOG.md`.

The package:

| file | content |
|---|---|
| `research/csia_dx/CSIA_DX_CLAIMS.csv` | atomic claims DX-C1 to DX-C13, with statuses |
| `research/csia_dx/CSIA_DX_TOY_EXAMPLE_AND_FEASIBILITY.md` | formal objects, the toy example, computation |
| `research/csia_dx/CSIA_DX_USEFULNESS_SCORECARD.md` | problems, users, product forms |
| `research/csia_dx/CSIA_DX_FIRST_EXPERIMENT.md` | the smallest falsifiable experiment, design only |

## Separation from XSYS-001

XSYS-001 is a completed, frozen confirmatory experiment. It is used here
**only** as an existing empirical primitive. Under one tested matched-set
condition, evidence availability and resolving power depended on physical
relationships and on time: dynamics evidence expired once the controller
compensated.

It is **not** evidence that CSIA-DX works. Its result, manifests and novelty
audit are not modified or reinterpreted.

## Rules followed

- **Verification levels V0–V4.** Only two kinds of source rise above V0:
  - CSIA's own code, read at V4 (D39);
  - one tool README, read at V2 (D12).

  Every paper, patent and vendor page is V0 and marked
  REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION. The environment blocks every
  publisher and patent host.
- **Unreadable means unclear, not absent.** Where nothing matching was
  found, the text says "no directly matching work was identified in the
  searched sources".
- **No bare use of the word for newness.** Statuses are N0–N4.
- **The goal was to kill the idea.** Every one of the 35 queries was aimed
  at a specific claim.

## 1. The candidate question, restated

At run time, given the vehicle state, the surviving sensors and actuators,
the candidate hypotheses, the accumulated evidence and the constraints,
CSIA-DX would determine:

1. which hypothesis pairs are separable now;
2. which are not;
3. why not;
4. the minimum additional evidence that would separate them;
5. whether that evidence can be obtained safely now;
6. if not, which uncertainty must remain;
7. which actions are justified meanwhile.

It would also reuse the same representation at design time.

## 2. Prior art, field by field

| field | what already exists | closest sources | level |
|---|---|---|---|
| diagnosability as a property of the observation set | diagnosability of DES; robust diagnosability under permanent or intermittent sensor loss; K-loss robustness; generalized robust diagnosability | D01, D04, D05 | V0 |
| diagnosability that depends on mode or operating point | mode-dependent detectability and isolability in hybrid systems; mode signatures; mode-sequence ARRs | D42, D14 | V0 |
| **the terms "conditional" and "distinguishability"** | **conditional and unconditional isolability / unisolability** (Kościelny et al.); **quantitative pairwise distinguishability** (Kullback–Leibler) between fault modes, and its extension to probabilistic sensor faults | D11, D09, D10 | V0 |
| structural isolability, missing witnesses, minimal sensor sets | structural analysis names which residuals and sensors isolate each fault pair; all sensor sets meeting a required isolability; a tool that does both from one model | D07, D08, D12 | V0 / V2 |
| explaining non-diagnosability | non-diagnosability is witnessed by a critical pair of indistinguishable traces | D01 | V0 |
| runtime sensor use for diagnosability | dynamic observers and sensor-activation policies that are minimal for diagnosability, decided during execution | D06 | V0 |
| minimum evidence / test selection | test sequencing with AO* (NP-complete optimal trees); GDE measurement selection; active sequential hypothesis testing with cost-constrained sensing | D24, D25, D26 | V0 |
| active diagnosis | controller design for diagnosability (DES); auxiliary input design; **active diagnosis guided by diagnosability properties** (hybrid systems); **on-board active diagnosis procedures for spacecraft**; quadrotor excitation and null-space probing | D02, D14, D15, D16, D19, D22, D23, D36 | V0 |
| **safe** active diagnosis | **active safe diagnosis** (detect before forbidden behaviour); constrained active fault detection; active isolation input guaranteed under state constraints; **s-FEAST**: online belief-space active fault estimation with probabilistic state constraints, discriminating simultaneous actuator and sensor faults; real-time safe active diagnosis via differentiable reachability | D03, D17, D18, D20, D21 | V0 |
| action authority under uncertainty | runtime assurance; NASA Intelligent Contingency Management / Dynamic Vehicle Assessment; belief-space reach-avoid control; switching among candidate controllers until isolation; health-score-gated reconfiguration | D30, D31, D32, D38, D44 | V0 |
| design-time / runtime unification | **TEAMS-Designer → TEAMS-RT** on one model; **MADe** sensor-set design that flags unisolable failures and generates diagnostic rules; eXpress; joint sensor placement and online diagnosis | D27, D28, D29, D13 | V0 |
| embedded computation | onboard diagnosis by knowledge compilation (JPL); OBDD diagnosis polynomial in the compiled size | D33 | V0 |
| CSIA itself | **`minimum_resolving_subsets`** ("RPM alone cannot localize the fault; RPM plus current can"); three-valued "not measurable" predicates; **`competitors_without_witness`**; per-function eligibility | D39 | **V4** |

## 3. Atomic claims

The full table, with the closest prior art, the residual difference, its
type, the confidence and what would change each status, is in
`research/csia_dx/CSIA_DX_CLAIMS.csv`.

| claim | short form | status |
|---|---|---|
| DX-C1 | diagnosability conditional on state and hardware | **N0** |
| DX-C2 | runtime loss changes the relation | **N0** |
| DX-C3 | name the missing witness for an unresolved pair | **N1** |
| DX-C4 | minimum evidence that restores separation | **N0** |
| DX-C5 | active actions that generate the missing evidence | **N0** |
| DX-C6 | active acquisition constrained by the safe envelope | **N0** |
| DX-C7 | an explicit state for "safe acquisition impossible" | **N1** |
| DX-C8 | authority depends on the unresolved set | **N1** |
| DX-C9 | the same representation at design time and run time | **N0** |
| DX-C10 | the six-part integration adds a capability | **N2** (LOW confidence) |
| DX-C11 | embedded computation by precomputed pair masks | **N1** |
| DX-C12 | a predictive, evidence-independent separability state per pair | **N1** |
| DX-C13 | a probe is admissible only if safe under every candidate | **N1** |

**No claim is N3 or N4.** Nothing closest was read at V3/V4, apart from
CSIA's own code, and that code **reduces** the claims: DX-C3 and DX-C4
already exist inside CSIA in retrospective form.

## 4. The most important novelty question: does the six-part combination exist?

The six parts:

1. runtime conditional diagnosability;
2. explicit missing witnesses;
3. minimum-evidence planning;
4. safety-constrained active acquisition;
5. ambiguity-dependent authority;
6. design-time / runtime reuse.

**No single searched source was seen to contain all six** (V0). The subsets
are well covered:

| source | parts it covers | parts not shown at V0 |
|---|---|---|
| s-FEAST (D20) | 1 implicitly (belief over faults, incl. actuator vs sensor), 3 in effect (it chooses the most informative actions), 4 (probabilistic state constraints), part of 5 (safety dominates the plan) | 2 (no explicit pairwise separability or reason-tagged missing witness), 6 |
| active diagnosis guided by diagnosability, and on-board procedures (D14, D15) | 1, 3 and 4 at event level (active diagnosis where passive diagnosis fails), on board a spacecraft | an explicit safety envelope over hypotheses, 5, 6 |
| active safe diagnosis in DES (D03) | 4 and 1 (detection before forbidden behaviour, by controller design) | runtime, 2, 5, 6 |
| TEAMS / MADe (D27, D28) | 6, 2 at design time, 1 at run time (ambiguity after unavailable tests) | 4 and 5 (no active safe probing, no authority) |
| RTA and ICM (D30, D31) | 5 in capability terms | 2, 3, 4 |

**Is the integration a new capability, or an obvious assembly?** On the
evidence, **an assembly**. The integration adds explicit, auditable
statements:

- which pairs cannot be separated now, and why;
- that no safe probe exists;
- which actions are therefore justified.

These are **representations** of quantities the closest systems compute
implicitly:

- a belief that does not concentrate, in s-FEAST;
- an infeasible constrained input design, in D17 and D18;
- an ambiguity group, in TEAMS-RT.

No capability was found that the composition has and its parts lack. The
brief's own test was: does absence of one paper with all six make it new?
It does not. **DX-C10 = N2, LOW confidence, and most exposed to D20.**

## 5. Formalization

The formal objects are defined in
`research/csia_dx/CSIA_DX_TOY_EXAMPLE_AND_FEASIBILITY.md` §1. Each
definition is mapped to its established counterpart there:

- the six-state relation D_ij;
- W_miss with reason tags;
- e* as weighted set cover;
- P_safe robust over H_active;
- A_allowed as an intersection.

Three representational choices came out of the toy and might be worth
keeping in an engineering implementation. **None is claimed as a
contribution.**

1. **VACUOUS hypotheses.** A hypothesis about a lost channel (an RPM
   telemetry fault after the telemetry disappears) should be retired, not
   reported as ambiguity.
2. **Probe admissibility over every candidate.** The toy's battery-load
   probe is least safe exactly when the battery hypothesis is true. Checking
   safety under the most likely hypothesis only is the failure mode.
3. **Authority by consequence, not by resolution.** If every candidate in
   an unresolved class implicates the same replaceable unit or propulsor, an
   action on that unit is justified without resolving the class. This is the
   testability practice of isolating to the replaceable unit (D26, D27).

## 6. Usefulness

The full scorecard is in `research/csia_dx/CSIA_DX_USEFULNESS_SCORECARD.md`.
In short:

- **Strongest evidenced needs: design-time and maintenance.** Diagnostic
  ambiguity drives No-Fault-Found removals, reported at 20–50% of avionics
  removals (D34), and sensor-set design.
- **Those needs are already served:** MADe, TEAMS, eXpress and structural
  analysis (D27, D28, D29, D12). **Product form A (a design-time tool)
  should be dropped.**
- **Runtime needs are moderately evidenced:**
  - NASA ICM for urban air mobility (D30);
  - fielded multirotor autopilots that do no active isolation (novelty audit,
    V4);
  - telemetry-triggered false motor failures (novelty audit B140, B146).

  These are partially covered, and CSIA-DX's addition is small and mostly
  representational.
- **The only product form with an apparent gap is C, an assurance API** that
  answers "what is known, what is ambiguous, what is justified". No demand
  evidence for it was found.

## 7. Computational feasibility

Details are in `research/csia_dx/CSIA_DX_TOY_EXAMPLE_AND_FEASIBILITY.md` §3.

- **Plausible for embedded runtime.** Pairwise separability is an OR of
  precomputed pair masks over the available witnesses: about 3.7 × 10⁴
  word operations at 137 hypotheses and 256 witnesses, and only on an
  availability or regime change.
- Missing-witness and single-pair minimum-evidence queries are index
  lookups.
- Probe admissibility and authority are table lookups over the active set.
- The limit is multiple-fault hypothesis growth (2^F), bounded by limiting
  fault cardinality.
- Online probabilistic planning (the s-FEAST class) is far costlier. Whether
  the cheap scheme loses safety-relevant decisions against it is open.

## 8. Kill criteria

| # | kill criterion | finding | met? |
|---|---|---|---|
| 1 | an existing aerospace architecture already provides substantially the same integrated runtime capability | s-FEAST (D20) provides the runtime safe active-diagnosis loop for a spacecraft. Diagnosability-guided on-board active diagnosis exists (D14, D15). Neither is seen to provide the explicit separability, missing-witness and authority outputs, or design-time reuse | **PARTLY** |
| 2 | the surviving distinction is merely terminology | every atomic claim is N0 or N1. The only N2 is the composition, and its residual is representational | **LARGELY** |
| 3 | the computation is incompatible with embedded runtime | no: bitset and table scheme | NOT MET |
| 4 | little practical value beyond ordinary FDI | modest runtime value; ordinary IVHM reasoners already output ambiguity groups given the available tests | **PARTLY** |
| 5 | the same result is obtainable much more simply with existing IVHM tooling | yes for design time and for runtime ambiguity (D27, D28); no for safe probing and authority | **PARTLY** |
| 6 | action-authority integration adds no meaningful capability | the intersection rule is a minimax over a discrete set, subsumed by RTA and belief-space methods. It adds auditability, not capability | **LARGELY** |
| 7 | design-time / runtime unification is already standard | yes (D27, D28, D12, D13) | **MET** |

## 9. Go criteria (all six are required)

| # | go criterion | finding | met? |
|---|---|---|---|
| 1 | at least one technically substantive N2/N3/N4 core survives | only DX-C10 at N2, LOW confidence, and not technically substantive: it is a composition with no emergent capability shown | **NO** |
| 2 | it solves a real aerospace problem | a real but modest runtime problem; the strong problems are design-time and already served | PARTLY |
| 3 | existing CSIA gives a meaningful implementation advantage | yes: three-valued predicates, `minimum_resolving_subsets`, `competitors_without_witness`, eligibility (D39) | YES |
| 4 | a falsifiable first experiment exists | yes (`research/csia_dx/CSIA_DX_FIRST_EXPERIMENT.md`) | YES |
| 5 | runtime implementation appears computationally practical | yes | YES |
| 6 | it would materially improve autonomous behaviour | unshown. The plausible improvement (robust probe admissibility, no action unjustified under some candidate) is known in principle (D18, D20) | **NOT SHOWN** |

**GO is not met:** criteria 1 and 6 fail.

## 10. Decision: PIVOT

**Killed.**

- The research framing "CSIA-DX as a new diagnostic concept": its claims are
  N0 or N1.
- Every novelty claim for DX-C1 to DX-C9 and DX-C11 to DX-C13.
- Product form A (a design-time diagnosability tool): a mature market.
- The term "conditional diagnosability" as a name: it collides with
  Kościelny's conditional isolability (D11), and "distinguishability"
  collides with Eriksson et al. (D09).

**Kept, as a pivot.** An engineering capability with an empirical question.
No novelty claim is made.

> **DX-lite:** a deterministic, embedded "diagnostic-capability monitor"
> built on CSIA v2's existing primitives. It maintains:
>
> - the six-state pairwise separability relation;
> - reason-tagged missing witnesses;
> - regime-indexed, offline-verified probes admissible only if safe under
>   every candidate;
> - an authority rule that intersects the actions acceptable under every
>   unresolved candidate.
>
> Its research question is comparative. At a fraction of the compute of a
> belief-space planner, does it:
>
> - make the same safety-relevant decisions;
> - never overclaim what the vehicle can know;
> - never execute an unsafe probe?

Whatever the answer, the scientific status stays at most N2. The
contribution would be an evaluated engineering trade-off (deterministic,
auditable, bounded compute against a richer planner). That is useful for an
assurance-oriented autonomy stack, but it is not a new concept.

**What would change this decision.**

- **Towards a stronger case:**
  - full-text reading of D20, D14, D15 and D27 shows none of them can
    express non-separability or authority explicitly; **and**
  - the first experiment shows DX-lite avoids unsafe or unjustified
    decisions that the strongest known baseline (B3 with the same
    admissibility rule, or B4) makes, at materially lower compute.
- **Towards KILL:**
  - the first experiment's decisive comparison (DX-lite against B3 and B4)
    shows no difference; **or**
  - a full-text source (most likely D20 or D27) already provides the
    explicit outputs.

**Not authorized by this review:** implementing DX-lite, building the
apparatus, or running the experiment.

## Final report

1. **Closest prior art.**
   - For the runtime loop: **s-FEAST** (D20, Science Robotics 2024). It does
     online, safety-constrained active fault estimation that separates
     actuator and sensor faults.
   - For design-to-runtime reuse: **TEAMS-Designer / TEAMS-RT** (D27) and
     **MADe** (D28).
   - For the theory: robust diagnosability under sensor loss (D04, D05),
     dynamic sensor activation (D06), active safe diagnosis (D03), and
     diagnosability-guided active diagnosis, including on board spacecraft
     (D14, D15).
2. **Atomic claims.** Twelve of thirteen are N0 (six) or N1 (six). One is N2
   (DX-C10, LOW confidence). None is N3 or N4.
3. **Terminology collisions.**
   - "Conditional isolability" is already defined (D11).
   - Pairwise "distinguishability" is already a quantitative measure (D09,
     D10).
4. **CSIA already has** retrospective minimum evidence
   (`minimum_resolving_subsets`), missing witnesses per competitor
   (`competitors_without_witness`), three-valued availability and function
   eligibility (D39, V4).
5. **Usefulness.** Real but modest at run time. Strong at design time, but
   already served. Only an assurance-API form shows an apparent, unevidenced
   gap.
6. **Feasibility.** Embedded-plausible (bitset pair masks and tables);
   limited by multiple-fault growth.
7. **Kill criteria.** 7 met; 2 and 6 largely met; 1, 4 and 5 partly met; 3
   not met.
8. **Go criteria.** 1 and 6 fail.
9. **First experiment.** Designed, not run. The decisive comparison is
   DX-lite against an information-greedy active-diagnosis baseline and a
   belief-space planner, not against a static FSM.
10. **Blocked access.** Every source except CSIA code and one README is V0.
    Full text of D20, D14, D15, D27 and D28 could move DX-C10 from N2 to N1.

**Decision:** `CSIA_DX_PIVOT`
