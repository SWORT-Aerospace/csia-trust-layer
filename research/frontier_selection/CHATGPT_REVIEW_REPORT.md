# CHATGPT REVIEW REPORT — CSIA FRONTIER SELECTION GATE, STAGE R0.2

Base commit `76eaa17`. Search date 2026-09-01. No implementation.

---

## 1. EXECUTIVE VERDICT

**This stage could not meet the evidence standard it was given, and the honest
headline is that fact rather than the candidate it selected.**

Item 3 requires full paper, publisher version, author manuscript, arXiv full
text or official technical report for any source used to kill or support the
top-three ranking. Fifteen scholarly hosts were probed at the start of the
session — arXiv, ACM, Springer, IEEE, ScienceDirect, Semantic Scholar,
OpenAlex, Crossref, OpenReview, NTRS, CORE, MDPI, HAL, NCBI, export.arXiv —
and **all fifteen were unreachable** through this environment's egress proxy.
`WebFetch` on an arXiv abstract returned `EGRESS_BLOCKED`. All 90 indexed
sources are therefore `PARTIAL_SOURCE_ONLY`, item 3's fallback applies without
exception, and item 42's bar cannot be cleared by any candidate.

Within that constraint, three things were established.

**First, the required families are occupied.** All nine candidate families the
brief named (A–I) reduce to an established abstraction that the search surfaced
*by name*: monitorability and monitoring under imperfect information (A);
common-cause failure theory and dependent-evidence fusion (B); diagnosability
under loss of observations and dynamic observations (C); label-free calibration
under shift (D); conformal prediction for perception-based control (E);
stealthy false-data injection (F); open-set recognition (G); passive and active
fault-tolerant control (H); decentralised fusion under unknown correlation (I).
Six of the nine were killed outright. This is not a failure of the search; it
is what a literature-first stage is supposed to produce.

**Second, the open assumptions cluster in one place.** Runtime assurance has
three mature layers — control, specification, argument — sitting on one thin
one: the *evidence* layer. Every layer above it states its assumption about
what arrives at the monitor's input, in plain language, and never revisits it.
The Simplex architecture "does not address sensors" (S004). Multi-sensor FDI
requires sensors "which do not share component dependency" (S067) and never
rechecks it. Learned separation policies "assume accurate position and velocity
information derived from GNSS; an assumption that fails" (S011, 2026). IEC
61508's diagnostic coverage is an FMEDA constant (S066). Nine of the 22 rows in
`OPEN_ASSUMPTION_LEDGER.csv` are open at snippet level, and they all say the
same thing from different angles.

**Third, one narrow candidate survives, provisionally.** **Candidate B** —
whether a runtime layer can compute the *effective number of independent
evidence sources* currently backing an assurance verdict, and whether that
number collapses in flight without anything noticing. Weighted frontier score
**5.900**, highest of twelve. Its formal content is a corollary of Menger's
theorem and this report says so in four places rather than dressing it up. Its
status is `PROVISIONAL`, and its Stage-0 prompt opens with a prior-art gate
rather than an experiment.

**Recommendation: proceed to the Stage-0 *reading*, not the Stage-0
experiment.** The single most likely cause of death — that runtime effective
independence is ARP4761 common-mode analysis recomputed at each tick — is
answered by obtaining one paywalled aerospace standard, not by running
anything. That must happen on a machine with library access before a line of
code is written.

---

## 2. WHY THE SEARCH STRATEGY CHANGED

The previous four work packages all ran the same loop: notice something in
CSIA, invent an explanation, search whether anyone did it, discover established
literature, pivot. Four times, four pivots — evidence-semantic equivalence
(`IMPLEMENTATION_DEFECTS_ONLY`), AI contract synthesis
(`HEURISTICS_SUFFICIENT`), semantic authority conflict
(`ENGINEERING_INCONSISTENCY_ONLY`), and before them dual admissibility and
invalidity masking. Eleven directions abandoned in total.

Item 1 inverted the method: literature frontier → explicit unresolved
assumption → closest hostile prior art → formal gap → smallest falsifiable
experiment → only then implementation. This stage followed that order strictly.
The 36 queries were written before any CSIA artefact was consulted; the first
mention of CSIA in the working order is the feasibility audit
(`SELECTED_CANDIDATE.md` §4), which happens *after* the candidate was chosen.

The inversion worked, in the sense that it killed six families before any
effort was spent on them. It also exposed something the previous loop hid:
**every one of the nine families was already occupied**, which means the
previous four pivots were not bad luck. They were the predictable output of
starting inside the system.

The inversion did not, however, rescue the stage from its real constraint. A
literature-first method is only as good as its access to literature, and this
environment has none.

---

## 3. AREAS SEARCHED

36 queries, listed verbatim in `SEARCH_PROTOCOL.md` §3, grouped by the family
they targeted. Approximately 300 result rows, roughly 220 distinct URLs
screened by title and snippet, **90 indexed**, **0 read in full**.

| area | queries | sources indexed |
|---|---:|---:|
| Runtime assurance architectures and standards | 8 | 14 (S001–S012 + related) |
| Runtime verification, monitorability, monitoring under partial information | 9 | 19 (S013–S031) |
| Assurance cases, conditional certificates, defeaters, assumptions | 5 | 11 (S032–S042) |
| Fault diagnosis: DES diagnosability, structural analysis, open-set, FTC | 5 | 17 (S043–S059) |
| Fusion, dependent evidence, common-cause failure | 5 | 10 (S060–S069) |
| Estimator gating and self-confirmation | 1 | 2 (S070–S071) |
| Calibration and uncertainty quantification | 2 | 5 (S072–S076) |
| Perception assurance and conformal methods | 2 | 6 (S077–S082) |
| Security: stealthy attacks, GNSS spoofing | 2 | 8 (S083–S090) |

Coverage against item 31 (≥5 CLOSE sources and ≥2 hostile/foundational per
finalist): A has 13 CLOSE / 16 HOSTILE / 1 FOUNDATIONAL; B has 13 / 2 / 2; J
has 5 / 7 / 0 — with S042 and S032 serving as J's hostile pair. All three
finalists clear the bar on count. **None clears it on depth**, because depth
was unobtainable.

---

## 4. SATURATED / DEAD AREAS

Nine areas, each closed as far as titles and snippets show:

1. **Monitorability, including its runtime form.** Classical property-level
   monitorability (S013), expressive verdicts (S014), totally ordered verdict
   domains (S015, 2024), timed monitorability (S017–S018, 2025), and — the
   decisive one — S016 (TOSEM 2025), whose snippet describes a generalised
   monitor that decides "when to safely give up on verification when it will
   never be able to conclude anything", which the snippet calls *moving the
   monitorability check to runtime*.
2. **Monitoring under partial, imperfect or lossy traces.** S019–S023, S026.
   All sound, all requiring a supplied loss model.
3. **Diagnosability under loss of observations.** S043–S049. Permanent loss,
   intermittent loss, dynamic observations, networked delay, a survey, and a
   2025 Bayesian formulation conditioned on the applied control sequence.
4. **Open-set / unknown-fault diagnosis.** S049, S056, S058, S059.
5. **Label-free calibration under shift.** S072–S076.
6. **Conformal perception monitors for control.** S077–S082, including S081
   whose title pre-empts the OOD retreat.
7. **Stealthy attacks on state estimation.** S083–S089, including an AIAA
   journal treatment specific to UAS.
8. **Decentralised fusion under unknown correlation.** S060–S063.
9. **Diagnostic ambiguity → control authority.** S054–S056, S080, plus a
   textbook (S055).

Eight of the brief's nine required families land in one of these nine areas.

---

## 5. IMPORTANT OPEN ASSUMPTIONS FOUND

`OPEN_ASSUMPTION_LEDGER.csv` holds 22 rows. Nine are open at snippet level, one
is open but rests on an unread standard, one is foundational-and-known, eleven
are subsumed. The open ones fall into two clusters that are the same assumption
seen from two sides.

**Cluster 1 — the monitor's inputs are assumed sound.**

- **S004**, *A Component-Based Simplex Architecture* (2017): the architecture
  "does not address sensors and some logical faults". The switching proof is
  stated over plant state with no evidence term.
- **S011**, *Runtime Safety Filtering … under GNSS Degradation* (2026): learned
  policies "assume accurate position and velocity information derived from
  GNSS; an assumption that fails in urban environments where multipath, signal
  blockage, and intentional interference routinely degrade navigation
  integrity". The paper attacks this by worst-case state bounding — it does not
  ask whether the channels remain independent.
- **S002/S003**, ASTM F3269: the monitor checks behaviour against pre-defined
  limits. What happens when a limit cannot be evaluated is not visible.

**Cluster 2 — the dependency structure among evidence sources is a design-time
constant.**

- **S067**, multi-sensor FDI for autonomous vehicles (2021): the method
  compares "correlated sensors which do not share component dependency". The
  non-sharing is asserted as a design property and never rechecked at runtime.
- **S066**, IEC 61508 via a secondary description: diagnostic coverage
  DC = λ_DD/λ_D is an FMEDA-derived constant entering the SIL calculation.
- **S069**: diverse redundancy's effectiveness "is determined by the failure
  correlation between diverse components" — again, a design property.
- **S041**, CoCo (ICCPS 2022): assumption monitors are *composed*, with
  calibration and conservatism bounds that depend on how the constituents
  relate to one another.

The two clusters meet at one sentence: **what reaches the monitor is assumed to
be what the design said would reach it, from where the design said it would
come.** Nothing in the searched literature visibly checks that at runtime.

---

## 6. TOP CANDIDATE #1

**Candidate B — runtime collapse of effective evidence independence at an
assurance monitor's input.**

A monitor credits *k* nominally independent channels when it reads a
cross-check as evidence of health. Define the **effective independence** κ_t(v)
of a verdict *v* as the minimum upstream vertex cut of *v*'s
evidence-provenance graph — the number of genuinely distinct sources that
currently back it. Define the **nominal independence** κ̂(v) as the number the
design credits. The question is whether Δ_t(v) = κ̂(v) − κ_t(v) is ever
positive in ordinary flight, and whether anything in the stack notices.

Weighted frontier score **5.900**, highest of twelve. Scores:
NOVELTY_SURVIVAL 5, PRIOR_ART_RISK 7, FORMAL_DEPTH 6, FALSIFIABILITY 9,
EXPERIMENTAL_CLARITY 9, CLAUDE_CODE_FEASIBILITY 9, SITL_FEASIBILITY 9,
HIL_FEASIBILITY 7, PHYSICAL_VALIDATION_FEASIBILITY 6,
CONNECTION_TO_EXISTING_CSIA 9, GENERALITY 8, COMMERCIAL_VALUE 7,
DISSERTATION_VALUE 7.

---

## 7. CLOSEST PRIOR ART #1

Ten close sources and four hostile/foundational ones.

**Closest.** S060 (Inverse Covariance Intersection, Automatica 2017) · S061
(fusion under unknown correlation) · S062 (data incest) · S063 (conditional-
independence testing for shared information in fusion) · S067 (multi-sensor FDI
requiring non-shared dependency) · S041 (CoCo) · S069 (diverse redundancy and
failure correlation) · S029 (RTLola on a certified eVTOL) · S011 (GNSS-degraded
safety filtering, 2026) · S088 (GNSS spoofing defeats RAIM through
cross-satellite consistency).

**Hostile / foundational.**

- **S065 — Littlewood & Miller (1989).** The *principle* that agreement between
  commonly-sourced channels is not evidence. 37 years old. Candidate B may
  never claim it.
- **S063.** The single most dangerous source. It detects shared information
  between fusion inputs statistically. If its full text attaches that verdict
  to a monitor's decision, candidate B is dead.
- **S060.** Explicitly "finds the maximum possible common information shared by
  the estimates to be fused" and removes a bound on it.
- **ARP4761 common-mode analysis — not obtained.** Aerospace certification
  already does this as a *process*. The most likely place for candidate B to
  already exist under a different name, and unreachable here.

---

## 8. EXACT GAP #1

**Existing work solves** the design-time probability that diverse channels fail
together (S065, S066, S069), the consistency of a fused *estimate* under
unknown correlation (S060–S062), the statistical detection of shared
information between fusion inputs (S063), and isolability from a fixed
structural model recomputable when the measurement set changes (S050, S052).

**They require** the dependency structure among evidence sources to be known
and fixed at design time — as a β-factor, a common-cause group, a structural
model, a bound on common information, or an architectural assertion.

**That fails** because the realised provenance of a monitor's inputs is
produced at runtime by protocol timing, decoder semantics, estimator gating,
freshness policy and vehicle configuration. S088 documents the extreme case in
service: spoofed GNSS is consistent across satellites, so residual checks stay
small while every channel is wrong.

**Not resolved:** telling a *monitor* that a *diagnostic test it is currently
running has lost its power* because the channels it compares now trace to one
upstream source; and reporting the current effective independence of a verdict.
The fusion literature repairs an estimate — a widened covariance does not
restore a residual's ability to separate hypotheses.

**Falsifiable by:** building the evidence-provenance graph from producer and
consumer source with every edge pinned to a verified `file:line`, computing
κ_t per tick on real logged data, and injecting one upstream fault to test
whether ≥2 nominally independent channels move together while every cross-check
stays silent.

---

## 9. WHY GAP #1 IS NOT MERELY APPLICATION NOVELTY

Three arguments, and one concession.

**The object is different, not the domain.** Covariance Intersection makes a
*fused estimate* consistent. Candidate B asks whether a *diagnostic test* has
power. These can diverge: a conservative fused covariance and a powerless
cross-check coexist happily, because widening an ellipsoid does not restore a
residual's ability to separate hypotheses. If the difference were only "on
UAVs", item 11 would reject it — and this report would say so.

**The quantity is not obtainable from theory.** Menger gives κ once you have
the graph. Getting the graph is the work: it requires reading ArduPilot, PX4
and three CSIA decode paths and pinning every derivation edge to a line of
source. No amount of theory produces it, and no other candidate in this stage
requires an artefact that does not already exist.

**Nothing is fitted.** No labels, no thresholds, no learned parameters, no
tuning. Given a repository whose three previous packages each ended with an
effect that could not be rescued without tuning, a candidate that *cannot* be
tuned is worth more than a candidate with a higher ceiling.

**The concession.** If the measurement reveals nothing that design-time
common-cause analysis already lists, then the contribution *is* merely
integration and the direction should be abandoned. That is written into the
Stage-0 stop conditions as null H0b, and into the answer to hostile Reviewer I.

---

## 10. KNOWN MATHEMATICS #1

- **Menger's theorem (1927).** Maximum vertex-disjoint paths = minimum vertex
  cut. This is the entire content of κ's definition.
- **d-separation in DAGs.** If a single vertex separates two channels from the
  sensing frontier, all information they carry about a frontier fault is
  already in that vertex, and their difference carries none of it.
- **Minimal cut sets in fault-tree analysis.** A minimum vertex cut of a
  provenance graph is formally the same object as a minimal cut set. **If
  runtime κ is nothing more than a minimal cut set recomputed at each tick,
  candidate B is common-mode analysis with a clock and should be abandoned.**

---

## 11. FORMAL OPPORTUNITY #1

> **Proposition (structural blindness).** If every path from the sensing
> frontier to channels {a, b} passes through a single vertex *c*, then for any
> fault modelled as a perturbation at *c*, the consistency test T_ab has zero
> power.

**This is a corollary of Menger plus the definition of a residual. It is not a
contribution, and this report does not present it as one.** It is stated so it
can be used, and so that hostile Reviewer D's objection is conceded before it
is made.

The real formal opportunity is smaller and more honest: a *definition* (κ_t)
plus a *sound-by-construction procedure* for obtaining the graph from source,
with five proof obligations enumerated in
`SELECTED_CANDIDATE_FORMAL_TARGET.md` §6. The most important is PO-2: because
static analysis of configuration-dependent wiring cannot be assumed complete,
**κ_t is an upper bound on effective independence.** A deficit found under an
upper bound is real; an absence of deficit proves nothing. Labelled
`SYSTEMS_CONTRIBUTION_ON_KNOWN_MATHEMATICS`.

The counterexample worth hunting is not against the proposition but against its
reach: a channel pair with κ = 1 whose agreement is *still* informative,
because the two paths apply independent physical constraints downstream of the
shared vertex. A proposition with no boundary has no content.

---

## 12. SMALLEST KILL TEST #1

**A source-provenance audit plus one paired single-upstream-fault injection.**

*Arm 1 (no manipulation).* Compute κ_t for every monitored verdict across the
real 9.6 MB PX4 ULog already in the repository, the existing real MAVLink
captures, and one nominal SITL run per platform. Arm 1 alone decides the
structural null.

*Arm 2 (paired).* Inject one fault at the smallest cut vertex found by Arm 1
and record channel co-movement, cross-check silence, and any failsafe action
difference against the paired nominal run.

Deterministic. No labels, no thresholds, no statistics — item 20's instruction
that deterministic falsification is stronger applies directly. Hours of compute;
the long pole is source reading, at one to two days.

---

## 13. HIL / PHYSICAL PATH #1

`software → SITL → replay of real PX4 ULog and MAVLink captures → bench HIL`.

Bench HIL requires **one Pixhawk-class flight controller and one GNSS module**.
The manipulation is degrading or removing the single upstream source and
observing two nominally independent channels respond together. No motion table,
no RF transmission, no radio equipment, no flight. Safe and legal on a bench.

**No physical HIL was executed in this stage** — no hardware is present in this
environment (`pyserial` sees only `/dev/ttyS0`), and item 36 forbids execution
regardless.

---

## 14. COMMERCIAL VALUE #1

An **effective-redundancy meter**: a runtime number published alongside each
assurance verdict — *"this verdict is currently backed by 1 independent source,
not 3."*

- **UAV / eVTOL OEMs:** dispatch and degraded-mode decisions grounded in
  delivered rather than designed redundancy.
- **Fleet analytics and MRO:** post-flight identification of intervals where
  claimed redundancy was not delivered — a maintenance and airworthiness
  artefact, not a research plot.
- **Defence autonomy:** evidence-independence collapse as a jamming/spoofing
  indicator that requires no attack model, because it measures structure rather
  than behaviour.
- **Certification support:** a runtime counterpart to the common-mode analysis
  an applicant already performs on paper.

Not "AI safety". A number, computed per tick, with a defined meaning.

---

## 15. HOW #1 COULD FAIL

The pre-mortem, in probability order (`SELECTED_CANDIDATE.md` §3):

1. **It already exists as ARP4761 common-mode analysis.** Most likely single
   cause of death. Unreachable in this environment.
2. **S063 already does it.** If its full text attaches a shared-information
   verdict to a monitor's decision, the gap closes.
3. **κ is static.** If the provenance graph never changes shape in flight, the
   runtime framing collapses to a drawing.
4. **κ is trivially 1 everywhere.** If everything routes through the EKF, the
   answer is obvious to any engineer on the project and worth nothing.
5. **The consequence null wins.** Deficits occur, are undeclared, and change no
   action — which is what all three prior CSIA packages found for their own
   phenomena. **This is the most probable experimental outcome.**
6. **Provenance cannot be soundly established from source.** Configuration-
   dependent wiring may make the endpoint unmeasurable; the honest output would
   then be a negative methods result.
7. **Reviewer J is right.** Twelfth idea, eleven abandoned. Only a full-text
   audit repays the credibility discount, and this stage could not perform one.

Reasons 1 and 2 are answered by reading. Reasons 3–5 are answered by the audit
itself, in days, and each is a publishable negative result about a real
autopilot stack rather than a wasted month. Reason 7 is recorded, not argued.

---

## 16. TOP CANDIDATE #2

**Candidate A — can a runtime assurance layer determine, online, whether its
own safety verdict is currently evidentially supportable?** Weighted score
4.250.

Closest prior art: S016 (TOSEM 2025), S013, S020 (TOSEM 2025), S041, S032,
S024, S029, S004.

**Ranked second because it may already be closed by a single unread paper.**
S016's snippet describes a generalised monitor deciding when it can never
conclude — the monitorability check moved to runtime. S041 builds calibrated
confidence monitors for verification assumptions. S032 shifts certification to
runtime. `PRIOR_ART_RISK = 9`.

What might remain: RV monitorability reasons about future extensions of a trace
over a *fixed* alphabet, while an aircraft's difficulty is that the alphabet
itself varies — which channels exist, at what rate, with what semantics. The
previous CSIA packages showed one raw condition producing three different
downstream tokens across three consumers, which is an alphabet problem rather
than a trace-extension problem. **Whether that difference is substantive cannot
be established without full text.** Its kill test is three papers and zero code.

---

## 17. TOP CANDIDATE #3

**Candidate J — runtime-checkability of the assumption sets that CPS guarantees
rest on.** Weighted score 3.950. Added under item 9, motivated by S042 (Li,
Faghfoorian & Ruchkin 2025: 423 assumptions from 104 papers, with reported gaps
around sensing, initialization, perception, neural components and uncertainty).

For a published formal guarantee, what fraction of its assumptions are
decidable from the signals a real autopilot actually produces? ConSerts (S032)
evaluates *enumerated* conditions; ACCESS (S037) invalidates fragments when
readings leave *authored* ranges; CoCo (S041) monitors assumptions that already
have monitors. Each requires the assumption to be *already* expressible as a
runtime-evaluable condition — and S042's reported gaps are exactly the
assumptions least likely to be.

**Ranked third for formal depth (4/10) and for an endpoint that depends on
human classification.** Best outcome: a good SAFECOMP or EMSE paper. Kill test:
one guarantee, one assumption list, one classification pass against the
106-field MAVLink+uORB universe already enumerated in
`research/ai_contract_synthesis/`. Hours.

**Tie-break disclosure.** J tied candidate H at exactly 3.950. The rule was
fixed before the scores were compared: *on a tie, prefer the candidate whose
closest prior art is further from a complete solution.* H's closest prior art
(Blanke et al., a textbook) answers H's question; J's (S042) states J's gap and
does not close it. J advanced.

---

## 18. COMPARATIVE SCORECARD

Full matrix in `CANDIDATE_SCORECARD.csv`. Weighted score per item 25:
`0.25·NOVELTY_SURVIVAL + 0.15·FORMAL_DEPTH + 0.15·FALSIFIABILITY +
0.10·EXPERIMENTAL_CLARITY + 0.10·HIL_FEASIBILITY + 0.10·GENERALITY +
0.10·DISSERTATION_VALUE + 0.05·COMMERCIAL_VALUE − 0.15·PRIOR_ART_RISK`.

| id | candidate | NOV | RISK | FORM | FALS | EXP | HIL | GEN | COMM | DISS | **score** | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **B** | effective evidence independence at runtime | 5 | 7 | 6 | 9 | 9 | 7 | 8 | 7 | 7 | **5.900** | **SELECTED** |
| **A** | monitor's own evidential supportability | 3 | 9 | 6 | 7 | 7 | 6 | 7 | 6 | 6 | **4.250** | TOP #2 |
| K | gate-conditioned self-confirming evidence | 3 | 8 | 6 | 7 | 7 | 6 | 6 | 6 | 5 | 4.200 | **disqualified (item 0)** |
| H | authority under diagnostic ambiguity | 3 | 8 | 7 | 5 | 5 | 5 | 7 | 6 | 6 | 3.950 | rejected (lost tie-break) |
| **J** | runtime-checkability of assumptions | 4 | 8 | 4 | 6 | 6 | 4 | 8 | 5 | 6 | **3.950** | TOP #3 |
| L | monitor/controller shared-input coupling | 2 | 8 | 4 | 8 | 8 | 7 | 6 | 6 | 4 | 3.900 | folded into B |
| C | runtime structural ambiguity | 2 | 9 | 7 | 7 | 6 | 5 | 7 | 4 | 5 | 3.750 | rejected |
| F | adversarial consistency | 1 | 10 | 7 | 7 | 6 | 5 | 7 | 8 | 5 | 3.550 | rejected |
| G | unknown fault / misspecification | 2 | 9 | 6 | 6 | 6 | 4 | 7 | 5 | 5 | 3.400 | rejected |
| I | dynamic evidence dependency | 1 | 10 | 7 | 6 | 6 | 4 | 7 | 5 | 4 | 3.050 | rejected |
| D | calibration failure without labels | 2 | 9 | 5 | 6 | 6 | 3 | 6 | 5 | 4 | 2.950 | rejected |
| E | physics + learned perception | 1 | 10 | 5 | 6 | 5 | 4 | 6 | 7 | 4 | 2.650 | rejected |

Three properties of this table are worth stating rather than hiding.

**No candidate scores above 5 on NOVELTY_SURVIVAL** — capped deliberately,
because no full text was read and novelty survival cannot be estimated from
snippets.

**The disqualified candidate K outscored two finalists.** It is excluded on
rule (item 0), not on merit, and its score is published so the ranking cannot
be accused of quietly suppressing it.

**The weighted score did not discriminate at the bottom of the top three.** H
and J tied exactly. Item 25 says the score is prioritisation only, not a
scientific metric; this is what that looks like in practice.

---

## 19. REJECTED CANDIDATES AND WHY

Full ledger in `REJECTED_CANDIDATES.md`, each with closest prior art, kill
reason, subsuming abstraction, remaining engineering value, and minor-paper
prospects.

| id | subsuming abstraction | decisive source |
|---|---|---|
| C | diagnosability under a time-varying observation map | S044, S047, S049, S052 |
| D | label-free calibration-error estimation under shift | S073 (LaSCal), S072, S074 |
| E | conformal prediction for perception-based control | S077–S079, S081 |
| F | stealthy FDI / secure state estimation | S083–S087, S089 |
| G | open-set recognition (item 26 hard kill) | S049, S058, S059 |
| H | passive/active FTC under set-valued diagnosis | S055 (textbook), S056 |
| I | decentralised fusion under unknown correlation | S060, S062 |
| K | selection bias in gated estimation; **and item 0** | S070 |
| L | candidate B restricted to the monitor/controller pair | folded, not killed |

Two salvages were made rather than discarding everything:

- From **F**: S088's mechanism — spoofed GNSS is consistent across satellites,
  so RAIM residuals stay small — is carried into candidate B as a real-world
  instance of a single upstream source manufacturing agreement. No attack is
  built, modelled, or evaluated.
- From **I**: the estimate-versus-test boundary. The fusion literature repairs
  an estimate's consistency; candidate B asks about a test's power. Candidate I
  is rejected; the distinction is not.

---

## 20. SELECTED FRONTIER

**Candidate B.** Can a runtime layer compute the effective number of
independent evidence sources currently backing an assurance verdict; does that
number fall below its nominal value during ordinary flight; and does anything
in the stack notice when it does?

Selected on `novelty survival × scientific depth × falsifiability ×
tractability` per item 32 — not on excitement, and not on the highest ceiling.
The decisive properties are that its kill test requires no model, no label, no
threshold and no fitted parameter; that its nulls can win cheaply and quickly;
and that CSIA holds the specific instrument it needs.

---

## 21. EXACT STAGE-0 HYPOTHESIS

**H1.** On a real autopilot stack (ArduPilot and PX4, consumed by the frozen
CSIA v1 pipeline), there exists at least one monitored verdict *v* and at least
one tick *t* such that κ_t(v) < κ̂(v) — the effective independence, computed as
the minimum upstream vertex cut of *v*'s source-derived evidence-provenance
graph, is strictly less than the nominal independence the design credits —
**and** no mechanism in the stack signals that this has happened.

---

## 22. EXACT NULL

Three nulls, ordered by estimated probability, most likely first — deliberately,
so the design is not built around the preferred outcome.

**H0c — Consequence null (most likely).** Deficits occur and are undeclared,
but no assurance decision differs between a κ-aware and a κ-blind reading of
the same trace. *Real, and inert.* This is what all three prior CSIA packages
found for their own phenomena.

**H0b — Baseline null.** Every deficit lies inside a dependency a competent
design-time common-cause analysis would already have listed. *Real, and already
handled.*

**H0a — Structural null.** κ_t(v) = κ̂(v) for every verdict at every tick.
*No runtime collapse at all.*

---

## 23. EXACT PRIMARY ENDPOINT

The set of triples **(verdict *v*, tick range, cut vertex *c*)** for which
κ_t(v) < κ̂(v), computed from a provenance graph in which **every edge is pinned
to a verified `file:line`** in ArduPilot, PX4 or CSIA source, together with the
count of those triples for which no mechanism in the stack signalled the
deficit.

Deterministic. No threshold, no fitted parameter, no label, no statistic.

**Binding reporting rule:** κ must be reported for *every* monitored verdict,
including those with no deficit. Reporting only the deficits is selective
reporting and voids the result.

---

## 24. EXPERIMENTAL CONTROLS

**C1 — Null control.** Every cross-arm comparison repeated on an all-nominal
trace. Anything differing on the nominal control is `CONFOUNDED_BY_CONTROL` and
counts for nothing. This discipline has already disqualified results in two
prior packages.

**C2 — Positive control on the instrument.** A preregistered channel pair that
is independent by construction must yield κ = 2. If not, the graph is
over-connected and the run is **void**.

**C3 — Negative control on the instrument.** A preregistered pair known to
share an upstream vertex must yield κ = 1. If not, the graph is
under-connected — the dangerous direction, since missing edges inflate κ — and
the run is **void**.

**C4 — Frozen-core control.** `tests/test_v1_frozen.py` passes before and
after; any modification under `csia/` voids everything.

Void trials are recorded and published, not re-run with adjusted parameters
until they pass. Eight confounders and six invalid-trial rules are enumerated
in `SELECTED_CANDIDATE_STAGE0_DESIGN.md` §§7–8, including the two that bit
previous packages: float accumulator drift in the tick grid, and the 10.0 s
failsafe arm time below which no action can differ.

---

## 25. FORMAL TARGET

Objects: a time-indexed evidence-provenance DAG G_t; a sensing frontier F; a
verdict's channel set S(v); effective independence κ_t(v) as the minimum vertex
cut between S(v) and F.

Proposition: κ_t = 1 ⇒ every consistency residual over S(v) has zero power
against a fault at the cut vertex.

Reduces to: Menger's theorem, d-separation, minimal cut sets. **A corollary,
labelled as one.**

Five proof obligations (`SELECTED_CANDIDATE_FORMAL_TARGET.md` §6): soundness of
graph construction via re-verified citations; completeness, or the explicit
admission that **κ_t is an upper bound**; that time-indexing is real rather
than cosmetic; the proposition's boundary; and distinctness from minimal cut
sets and ARP4761 CCA — which, if it cannot be discharged, ends the candidate.

Novelty status: every element is `KNOWN/SUBSUMED` except the runtime quantity
(`PROVISIONAL`) and its measured incidence (`CONJECTURE`, nothing has been
run).

---

## 26. EXPECTED RUNTIME

| phase | estimate |
|---|---|
| Prior-art gate (reading, on a machine with library access) | 1–2 days |
| Provenance audit: ArduPilot + PX4 + 3 CSIA decode paths | 1–2 days of source reading |
| κ computation over real logs | minutes |
| Paired upstream injection in SITL | minutes per cell |
| Controls, tests, write-up | 1 day |
| **Total** | **under one week** |

Item 15's bar — minutes to hours, not weeks — is met for the experiment. The
reading is the long pole, and it is the part that must not be skipped.

---

## 27. EXPECTED HARDWARE / COST

**$100–$500**, and **$0** if the existing captures and SITL suffice for Stage 0.

Bench HIL needs one Pixhawk-class flight controller and one GNSS module. No
motion table, no RF transmitter, no network impairment rig, no camera. Safe and
legal on a bench: no RF emission, no airborne operation, no flight.

No hardware is present in this environment and none was used.

---

## 28. PUBLICATION CEILING

A solid systems paper at **RV**, **ICCPS/EMSOFT**, **SAFECOMP/DSN**, or
**DASC/AIAA SciTech** — contingent on the full-text gate passing and the
measurement being non-trivial.

What each community would demand: RV reviewers, a precise semantics for G_t and
a soundness argument for its construction; SAFECOMP reviewers, the comparison
against ARP4761 common-mode analysis — they would be the first to say this is
CCA done at runtime; DASC reviewers, the aircraft data and the bench result.

---

## 29. DISSERTATION CEILING

**One strong chapter and one systems paper. Not the dissertation core.**

Against item 27's eight outputs, candidate B plausibly produces five: A (new
problem formulation), C (new algorithm/system), D (controlled causal evidence),
F (bench HIL), H (operational design principle). It plausibly produces E
(cross-platform replication) and partially G (reusable artefact).

**It does not produce B — a nontrivial formal result** — because the
mathematics is a corollary. A dissertation core would need the theorem this
candidate does not have. Item 27's bar is three of eight; B clears it, and the
gap it does not clear is named rather than glossed.

---

## 30. NOVELTY STATUS

**NOT ESTABLISHED. `PROVISIONAL` is the ceiling, and it is a hard ceiling.**

Item 42 forbids awarding `PROVED — POSSIBLE NOVEL CONTRIBUTION` merely because
no identical title was found. `SEARCH_PROTOCOL.md` §0 establishes that
title-and-snippet is all this stage had. The two rules together make the
outcome unavailable, and `CLAIM_LEDGER.json` reflects that in every row.

What can honestly be said: **no source surfaced by 36 queries visibly computes a
runtime effective-independence count for a safety monitor's verdict.** What
cannot be said, and is not: that this is novel, that nobody has done it, or that
there is a gap in the literature. Claim F7 in the ledger records the absence and
names its four limitations — single engine, snippet depth, patents excluded,
aerospace standards unread.

Three refuted predictions are kept rather than deleted: that at least one
required family would survive unqualified (it did not); that the item-3
evidence standard could be met (it could not); and that the top three would
separate cleanly under the weighting (they tied).

---

## 31. WHAT MUST BE TRUE BEFORE IMPLEMENTATION

Four conditions, enforced as §1 of `SELECTED_CANDIDATE_STAGE0_PROMPT.md`:

1. **Full text of S063, S060, S062, S041 and S016 obtained and read.**
2. **ARP4761 common-mode analysis obtained**, and the question answered in
   writing: *is runtime κ anything other than CCA recomputed at each tick?* If
   the answer is no, or cannot be established, **stop**.
3. **Two further prior-art searches run** that this stage did not run at all:
   data-provenance theory (why/where/how-provenance, lineage) and fault-tree
   minimal cut sets. κ may already be one of those objects.
4. **If any of the above already computes a runtime effective-independence
   count for a monitor's verdict: STOP, record the kill, and do not adjust the
   candidate so that it survives.**

---

## 32. FINAL RECOMMENDATION

**Proceed to Stage 0 — but to its reading, not its experiment.**

The recommendation is deliberately narrower than the brief's template invites.
This stage was asked to select a frontier against a full-text prior-art audit,
and it could not perform one. What it can defensibly deliver is: nine families
reduced to named abstractions, twenty-two assumptions catalogued with the role
each plays, one narrow surviving question, and a Stage-0 design whose first
gate is the audit this environment could not run.

Three things should be resisted, and are resisted in these artifacts:

- **Do not treat candidate B as novel.** It is `PROVISIONAL`, and the most
  likely cause of death is a paywalled aerospace standard nobody here could
  open.
- **Do not treat the proposition as a theorem.** It is a Menger corollary,
  conceded in four places.
- **Do not widen the experiment if the consequence null wins.** H0c is the most
  probable outcome, it is a legitimate negative finding about a real autopilot
  stack, and the correct response is to write it down and stop — not to search
  until something moves.

The strongest sentence this stage supports is this one: *runtime assurance has
three mature layers resting on a thin evidence layer, and every layer above it
states its assumption about what arrives at the monitor's input in plain
language and never checks it again.* Whether that observation is a research
contribution or an already-solved engineering practice is exactly what the
Stage-0 gate is for, and it cannot be settled from here.
