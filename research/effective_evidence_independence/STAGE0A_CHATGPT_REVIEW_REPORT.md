# CANDIDATE B — STAGE 0A REVIEW REPORT

Prior-art closure and formal problem freeze. Frontier commit `65fa17e`,
canonical base `76eaa17`. No implementation, no experiment, no κ claim.

---

## 1. EXECUTIVE VERDICT

**Prior art: `INCONCLUSIVE_MISSING_FULLTEXT`. Science:
`PROVENANCE_METRIC_INSUFFICIENT`. Stage 0B: not authorised.**

Two independent things happened, and only one of them was expected.

**The expected one.** Item 1's gate could not be executed. Not a single full
text was obtainable — publisher hosts, author copies at `isas.iar.kit.edu` and
`ivan.ece.ufl.edu`, NASA, SRI, `doi.org`, CiteSeerX, ResearchGate, all blocked.
Four source groups are individually capable of killing the candidate and none
was read. Item 1 then forces the stop, and no sentence of the form "we did not
identify a method that…" appears anywhere in this package.

**The unexpected one, which matters more.** The parts of Stage 0A that need no
library **damaged the candidate on their own**:

1. Item 11's hostile null `H_KILL_PROVENANCE` is **correct in both
   directions**. A shared source with different downstream transforms leaves the
   residual sensitive; distinct sources with a shared physical disturbance leave
   it blind. κ_prov therefore neither certifies nor refutes diagnostic
   diversity, and item 11's instruction not to rescue it by redefinition is
   binding. **The central quantity of candidate B does not work.**

2. The frontier report's **bound direction was backwards**. Omitted edges make
   κ_prov an *under*-estimate, so an incomplete audit manufactures deficits that
   do not exist — the direction that flatters the hypothesis.

3. The re-centring that (1) forces — from graph cuts to residual fault
   sensitivity — moves the candidate **onto structural FDI's own ground**, where
   the nearest prior art is closer than it was. The prior-art position got
   worse, not better.

Set against that, the one gate that passed cleanly: **the runtime topology does
change**, provably, in ArduPilot, invisibly on the wire. Item 16's
`STATIC_DEPENDENCE_ONLY` verdict is avoided. But PX4 already publishes exactly
this information as a first-class message, which reframes the ArduPilot finding
as a telemetry gap in one stack.

**Recommendation: do not proceed to Stage 0B.** Not because the literature
closed it — the literature was not readable — but because the metric the
candidate was built on has been refuted from first principles, and the
replacement quantity lands in a well-occupied field. The reading in
`REQUIRED_READING_MANIFEST.md` should be done before any further work, and if
the candidate is revived it must be revived around a different measurand.

---

## 2. FULL TEXTS ACTUALLY READ

**Zero.** `FULLTEXT_READING_LOG.md`.

What *was* read in full, being the only primary material obtainable: ArduPilot
`GCS_Common.cpp` (the three IMU/vibration senders), `AP_InertialSensor.h`
(accessor overloads), `AP_InertialSensor.cpp` (`update()` health/selection
block), `common.xml` (`VIBRATION` definition); PX4 `SensorSelection.msg`,
`voted_sensors_update.cpp`, `VehicleAngularVelocity.cpp`; CSIA
`adapters/ardupilot.py` and `adapters/base.py`.

That establishes what the systems do. It establishes nothing about what has
been published about it.

## 3. SOURCES STILL MISSING

All of them. Six groups, in `REQUIRED_READING_MANIFEST.md` §1, with the exact
sections and what each would decide: ARP4761/ARP4761A CCA-CMA; Noack et al.
ICI (Automatica 2017) and Le Caillec conditional-independence testing (Signal
Processing 2017) and the data-incest graph literature; meta-diagnosis and
structural FDI; dynamic fault trees and the 2024/25 DFT review; Ruchkin et al.
CoCo (ICCPS 2022); Littlewood & Miller (1989).

Access evidence, re-probed this stage rather than carried over, is in
`REQUIRED_READING_MANIFEST.md` §0.

## 4. ARP4761 / ARP4761A VERDICT

**UNRESOLVED.** The standard is paywalled; the FAA cross-check material item 2
names is also unreachable.

The question item 15 requires — does ARP demand *runtime verification of
realised independence*, or only *design-time demonstration that independence
mechanisms are not defeated by identified common causes* — is unanswered.

The counter-argument is recorded at equal weight in
`ARP4761_CCA_REDUCTION.md`: the ArduPilot switch happens *because* the
autopilot declared an accelerometer unhealthy, and a design-time CMA that
already treats "loss of accel 0" as a condition may well cover the
reconfiguration. That is Reviewer A's objection and it cannot be answered here.

## 5. COMMON-INFORMATION FUSION VERDICT

**UNRESOLVED**, and weaker for the candidate than the frontier stage judged.

The estimate-versus-test distinction survives as an argument: CI/ICI widen a
covariance so a fused estimate stays consistent, which does not restore a
residual's ability to separate hypotheses. It has not been checked against
text. `COMMON_INFORMATION_REDUCTION.md`.

## 6. CONDITIONAL-INDEPENDENCE VERDICT

**UNRESOLVED, and this is now a stronger attack than the frontier stage
allowed for.**

A signal-level conditional-independence test on the monitor's inputs would
detect counterexample B — the shared physical disturbance with no software edge
— which a provenance graph provably cannot see. On that failure mode the
statistical test is **strictly better** than κ_prov.

Where provenance wins is explainability: it names the shared node. Item 12
pre-emptively rules that insufficient for a dissertation contribution.

## 7. DYNAMIC-FAULT-TREE VERDICT

**UNRESOLVED.** `DYNAMIC_FAULT_TREE_REDUCTION.md`.

The material point is not the verdict but the loss of a fallback: if the
surviving content of candidate B were "recompute a minimal cut set as topology
changes", item 14's rule fires immediately. Since κ_prov is not even a reliable
bound (§13 below), that fallback is worse than the original position, not
better.

## 8. META-DIAGNOSIS VERDICT

**UNRESOLVED — and now the most serious technical threat**, ahead of the fusion
literature the frontier stage ranked first.

The reason is structural, not bibliographic. Once the counterexamples force the
candidate off κ_prov and onto **residual fault sensitivity**, it lands on
exactly what structural FDI computes — fault signature matrices, isolability,
ARR sensitivity — with meta-diagnosis sitting above that asking whether the
relation in use is sound.

The only distinction left to test, stated as a question because it has not been
checked: meta-diagnosis is generally understood to address relations that are
*wrong*; does any of it address a relation that is *formally correct and
currently uninformative* because runtime source selection made its two
arguments the same measurement? A treatment of ARR applicability under
reconfiguration would very plausibly say yes.

## 9. STRUCTURAL FDI VERDICT

**UNRESOLVED**, and inseparable from §8. Structural analysis already computes
isolability from a structural model and, in some work, recomputes it when the
available measurement set changes. Whether it recomputes when the measurement
*provenance* changes — the same channel name, a different transducer behind it
— is the open question.

## 10. THREE TYPES OF INDEPENDENCE

`INDEPENDENCE_TAXONOMY.md`.

| | question | object | home | timescale |
|---|---|---|---|---|
| **failure independence** | do components fail together? | joint failure probability, β-factor | ARP4761, IEC 61508, fault trees, Littlewood-Miller | design time |
| **statistical independence** | are the variables independent? | distributional property | CI/ICI, data incest, conditional-independence testing, d-separation | runtime, on signals |
| **diagnostic information diversity** | do the channels supply distinct information for discriminating *these* hypotheses? | residual sensitivity, structural distinguishability | structural FDI, meta-diagnosis | both |

Candidate B concerns the third. It is influenced by the first two and equal to
neither.

## 11. WHY κ_prov IS NOT STATISTICAL INDEPENDENCE

Because a graph edge is not a correlation, and a cut is not a factorisation.

κ_prov is a **fourth** thing — a structural provenance quantity — and calling
it "effective independence" asserted a relationship to the first two that has
not been established and that §14 shows to be false in both directions. Item 5
required the rename and this package adopts it: **κ_prov**, *structural
evidence diversity*, *provenance cut cardinality*. None is claimed to be a
standard name.

Reviewer F's objection — "your graph cut does not measure independence" — is
**conceded categorically**.

## 12. EXACT GRAPH MODEL

`PROVISIONAL_GRAPH_MODEL.md`. G_t = (V, E_t), a DAG; F the sensing frontier;
E_v(t) the evidence supporting verdict *v*;

> κ_prov(t, v) = minimum source-separating vertex cut between F and E_v(t),
> equivalently the maximum number of internally vertex-disjoint F→E_v paths.

One correction to the frontier report is recorded rather than applied silently:
the cut set is drawn from V \ E_v(t) and **may include frontier vertices**. The
frontier report excluded them, under which a graph whose transducers feed the
evidence directly admits no finite cut and the quantity is undefined in exactly
the case of interest.

Node and edge rules were fixed before any ArduPilot file was opened (item 18).
Edges carry categories, not probabilities (item 19): only
`PROVED_FROM_SOURCE` edges carry the structural result, and the audit uses no
other category. Shared clock, shared calibration, shared power rail and the
physical environment are **excluded** from the node set — a limitation, and
the last of them alone is sufficient to defeat the metric.

## 13. BOUND DIRECTION / GRAPH COMPLETENESS

Item 20 asked for a proof rather than an intuition, and the proof **overturns
the frontier report**.

- **Omitted edges.** Removing edges cannot create paths, so by Menger the min
  cut of a subgraph is ≤ that of the true graph. Worked case:
  true {s₁→a, s₁→b, s₂→b} has κ = 2; omit s₂→b and κ̂ = 1. **Under-estimate.**
- **Aliasing** (one physical object modelled as two nodes) splits a shared
  vertex and makes paths look disjoint. **Over-estimate.**

> κ_prov is a **lower** bound only under a no-aliasing assumption, an **upper**
> bound only under a no-omission assumption, and **neither in general**. A
> source audit discharges neither assumption.

`research/frontier_selection/SELECTED_CANDIDATE_FORMAL_TARGET.md` §6 PO-2
asserts κ is an upper bound and that "a deficit found under an upper bound is
real". **That is wrong**, and it is wrong in the dangerous direction: an
incomplete audit produces *false* deficits. Per the v1.1 brief's instruction not
to rewrite frontier-selection artifacts, that file is left byte-identical and
the correction lives in `FORMAL_REDUCTION.md` §4 and in claim `E6`.

## 14. SMALLEST COUNTEREXAMPLE TO κ=1 ⇒ BLINDNESS

`MENGER_CLAIM_COUNTEREXAMPLES.md` §1. With y₁ = f₁(c), y₂ = f₂(c) and
r = y₁ − y₂:

    ∂r/∂δ = f₁′(c) − f₂′(c)  ≠ 0  whenever f₁′ ≠ f₂′

**Instantiated on the audited pair itself.** In state N1, `vibration.rms` and
`imu1.accel` both derive from accel 1 — but one is a high-passed magnitude
statistic and the other a low-passed signed vector. A **step bias** at accel 1
moves `imu1.accel` and leaves `vibration.rms` nearly unchanged, because a
constant offset is exactly what a high-pass rejects. The comparison is *not*
blind. Even the motivating example refutes the claim.

## 15. EXACT CONDITIONS UNDER WHICH BLINDNESS DOES FOLLOW

Blindness requires **residual invariance at the cut vertex**, not graph
separation:

> R is blind to perturbations at *c* iff ∂R/∂c = 0 (or R(c+δ) = R(c) over the
> admissible perturbation set).

The sufficient special case in which topology alone suffices is narrow: κ = 1
with cut vertex *c*, **and** R = y₁ − g(y₂) **with** g ∘ f₂ = f₁ identically —
i.e. the residual re-derives one channel from the other. That is a real failure
mode and a much smaller class than "κ = 1".

Note what the condition needs: **the functional forms**. The graph does not
supply them, which is why item 9's research question — can graph structure
certify invariance without the functional model — is answered **no**.

## 16. WHETHER THE RUNTIME GRAPH ACTUALLY CHANGES

**YES.** Proved from source, and this is the one gate the candidate passes
cleanly.

`AP_InertialSensor::update()` runs once per main-loop iteration
(`AP_InertialSensor.cpp:1926`). Inside it, `_accel_healthy[i]` is cleared for
any accelerometer that has accumulated errors while another has none
(`:1986-1989`), and `_first_usable_accel` is then reassigned to the first
healthy, in-use instance (`:2001-2006`). This is not a boot-time parameter.

## 17. ARDUPILOT DYNAMIC EXAMPLE

`SELECTED_DYNAMIC_EXAMPLE.md`. ArduPilot `01a504b`.

| CSIA channel | message | producer instance | citation |
|---|---|---|---|
| `imu0.accel` | `RAW_IMU` / `SCALED_IMU` | accel 0, hardcoded | `GCS_Common.cpp:2241-2242`, `:6851` |
| `imu1.accel` | `SCALED_IMU2` | accel 1, hardcoded | `GCS_Common.cpp:6856` |
| `vibration.rms` | `VIBRATION` | `_first_usable_accel` | `GCS_Common.cpp:3075` → `AP_InertialSensor.h:312` |

All three sit in CSIA's same `"imu"` group (`adapters/base.py:58-71`).

- **N0**, `_first_usable_accel == 0`: `vibration.rms` ← accel0,
  `imu1.accel` ← accel1. κ_prov = 2.
- **N1**, accel0 unhealthy: both ← accel1. κ_prov = **1**. The pairing with
  `imu0.accel` swaps the other way at the same instant.

`VIBRATION` (id 241, `common.xml:6632-6641`) has seven fields and **no**
instance, device-id or selection field. A MAVLink consumer cannot tell.

## 18. PX4 DYNAMIC EXAMPLE IF AVAILABLE

Available, and it is the **contrast** rather than a confirmation.

`msg/SensorSelection.msg` carries `accel_device_id` and `gyro_device_id`; its
own comment says it is updated "when sensor selection changes"; it is published
on change at `voted_sensors_update.cpp:276` and subscribed by modules that must
follow the switch (`VehicleAngularVelocity.cpp:81-82`, whose comment reads
"sensor_selection needed to change the active sensor if the primary stops
updating").

**One of the two audited stacks already represents this as a first-class
message.** What ArduPilot lacks is a field on the wire, not the concept — which
pushes the finding toward an engineering defect report and away from a research
gap.

## 19. EXACT SURVIVING RESEARCH QUESTION

Nothing survives in the form the candidate had. What is left, stated honestly
as an open question rather than a claim:

> When a runtime source-selection or reconfiguration event changes which
> physical transducer stands behind a named evidence channel, does the
> fault sensitivity of the diagnostic relations that consume that channel
> change in a way that design-time common-cause analysis, dynamic reliability
> models, fusion-side shared-information handling, and meta-diagnosis of ARR
> validity do not already address?

Two things must be true before this is worth pursuing, and neither is
established: the four reductions in §§4–9 must leave it open, and a measurand
other than κ_prov must be identified, since κ_prov is insufficient and may not
be redefined to rescue it.

## 20. WHY IT IS NOT JUST A UAV APPLICATION

**It might well be.** The mechanism found is one message family in one
autopilot, and the other autopilot already publishes the missing information.
On present evidence the honest answer to this question is *unproven*, and §18
is the reason to doubt it.

## 21. WHY IT IS NOT JUST COMMON-CAUSE ANALYSIS

Unresolved. §4. The argument would be that CMA asks whether a common cause can
defeat redundancy, whereas the question here is whether the *comparison a
monitor is running right now* still has arguments that differ. Whether ARP's
dependence diagrams already cover a redundancy manager's reconfiguration cannot
be answered without the standard.

## 22. WHY IT IS NOT JUST FUSION

Unresolved, and the argument is weaker than the frontier stage thought. The
estimate-versus-test distinction stands as an argument; but a conditional-
independence test beats κ_prov outright on the physical-common-mode failure
mode, and provenance's remaining advantage is explainability, which item 12
rules insufficient. §§5–6.

## 23. WHY IT IS NOT JUST META-DIAGNOSIS

**This is the objection with the weakest answer.** §8. The candidate's own
re-centring moved it onto this ground. The only distinction left is
correct-but-uninformative versus wrong, and it is a question, not a finding.

## 24. SMALLEST FUTURE EXPERIMENT

Not designed, deliberately. Item 23 permits a Stage 0B design **only if the
prior-art and formal gates pass**. The prior-art gate returned
`INCONCLUSIVE_MISSING_FULLTEXT` and the formal gate returned
`PROVENANCE_METRIC_INSUFFICIENT`. No `STAGE0B_PREREGISTRATION_DRAFT.md` and no
`STAGE0B_EXECUTION_PROMPT.md` were written.

For the record, the shape it would take if both gates later pass: paired N0/N1
states over the audited pair, same vehicle state, same relation, same
thresholds, same frozen diagnosis core, same raw fault magnitude, differing
only in provenance topology — with the primary endpoint being residual
sensitivity, not κ, and not "an alarm happened" (item 25).

## 25. PRIMARY FUTURE ENDPOINT

Would be **residual fault sensitivity S_{R,f}** — how much the diagnostic
relation actually in use moves under a preregistered upstream perturbation —
with κ_prov demoted to a covariate at most. Item 25 forbids "alarm happened"
and item 26 makes clear the scientific question is whether diagnostic
distinguishability changes, not whether κ changes. Exact definition deferred
until the formal audit passes, which it has not.

## 26. NULLS

- **N-A.** Provenance changes and residual sensitivity does not — item 27's
  Outcome B. The provenance metric is insufficient. **This stage has already
  reached this conclusion analytically**, without an experiment, via
  counterexample A.
- **N-B.** Residual sensitivity changes without provenance change — item 27's
  Outcome C. κ misses the relevant structure. **Also already reached**, via
  counterexample B.
- **N-C.** Both change together but a design-time common-cause analysis already
  enumerates the condition. Unresolved; needs ARP4761.
- **N-D.** Both change and it is already meta-diagnosis. Unresolved; needs §8's
  reading.

Two of the four nulls have already won on analysis alone.

## 27. EXPECTED FAILURE MODES

1. ARP4761 covers reconfiguration; candidate is CMA with a timestamp.
2. Meta-diagnosis covers correct-but-uninformative relations; subsumed.
3. Conditional-independence testing does the job better and without a graph.
4. The re-centred quantity is ordinary residual sensitivity analysis.
5. The ArduPilot finding is a MAVLink telemetry defect, best fixed by adding a
   field, and PX4 shows the fix is already known.
6. The provenance audit cannot be made sound: κ_prov is unbounded in direction
   and its error mode manufactures false deficits.
7. Reviewer J is right — twelfth candidate — and the only defence, a full-text
   audit, is exactly what could not be done.

## 28. CLAIM LEDGER

`CLAIM_LEDGER.json`: 9 claims, 4 refuted predictions kept.

Statuses: `EMPIRICAL ONLY` ×1, `PROVED — NOVELTY NOT ESTABLISHED` ×4,
`REFUTED` ×2, `PROVISIONAL` ×2. **No claim receives `PROVED — POSSIBLE NOVEL
CONTRIBUTION`**, and item 32 makes that unavailable in this stage anyway: it
requires a genuinely new mathematical statement proved *and* surviving
prior-art audit, and there was no audit.

The four kept refuted predictions: that κ_prov could be the central quantity;
that κ was an upper bound; that the fusion literature was the top threat; and
the binary prediction that the source audit would either find no topology change
or find one that mattered — it found a change that does not demonstrably matter,
in a stack whose sibling already publishes it.

## 29. NOVELTY STATUS

**NOT ESTABLISHED, and this stage moved it backwards rather than forwards.**

Item 30's permitted sentence — "We did not identify, in the full-text sources
reviewed, a method that…" — **cannot be written**, because the number of
full-text sources reviewed is zero. It appears nowhere in this package.

## 30. RECOMMENDATION

**Do not proceed to Stage 0B. Do not implement anything.**

1. **Hand `REQUIRED_READING_MANIFEST.md` to someone with library access.**
   §1.3 (meta-diagnosis and structural FDI) and §1.1 (ARP4761) first — the
   threat ordering changed during this stage and §1.3 has overtaken the fusion
   literature.
2. **Do not revive candidate B around κ_prov.** Item 11 forbids rescuing it and
   the counterexamples are constructive, not speculative.
3. **If it is revived at all**, it must be around residual fault sensitivity —
   and that reformulation must clear §§8–9 first, because it lands squarely in
   structural FDI.
4. **Bank the engineering finding separately.** "ArduPilot's `VIBRATION`
   carries no accelerometer identity, while PX4 publishes `SensorSelection` on
   change" is a good, cheap, verifiable defect report against a real stack. It
   belongs in engineering work, not in a dissertation frontier, and it should
   not be dressed up as the research result.

The honest summary of Stage 0A: **the literature could not be consulted, and
the candidate was substantially damaged anyway — by its own mathematics.**
