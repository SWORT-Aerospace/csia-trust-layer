# TOP THREE

Item 30: exactly three, force-ranked. Item 31: each finalist carries the full
required set.

| rank | id | candidate | weighted frontier score |
|---:|---|---|---:|
| 1 | **B** | Runtime collapse of effective evidence independence at an assurance monitor's input | **5.900** |
| 2 | **A** | Can an RTA layer determine online whether its own safety verdict is evidentially supportable? | 4.250 |
| 3 | **J** | Runtime-checkability of the assumption sets that CPS guarantees rest on | 3.950 |

> Every HIL, hardware and cost figure below is a **feasibility estimate,
> design only**. No physical HIL was executed in this stage — no hardware is
> present in this environment, and item 36 forbids execution regardless.

---

## 0. THE TIE-BREAK RULE, STATED BEFORE IT WAS USED

J and H both scored **3.950**. The rule applied:

> **On a tie, prefer the candidate whose closest prior art is further from a
> complete solution.**

- H's closest prior art (S055, Blanke et al.) is a textbook that *answers* H's
  question: when the fault is not isolated, fall back to robust control. S056
  (2025) makes that quantitative.
- J's closest prior art (S042, 2025) *states* J's gap — it maps 423 assumptions
  and reports where they are inadequately specified — and does not close it.

J advances. H is rejected, with two further independent kill reasons recorded
in `REJECTED_CANDIDATES.md`. Candidate **K** scored 4.200 — higher than both —
and is disqualified under item 0 as a rename of a killed direction, not
demoted on score. All three facts are published rather than smoothed over.

---
---

# TOP #1 — CANDIDATE B

## Exact problem statement

A runtime assurance monitor accepts agreement between nominally redundant
channels as evidence that a monitored quantity is healthy. The number of
*genuinely distinct upstream sources* behind those channels is fixed at design
time — in a β-factor, a common-cause group, a structural model, or an
architectural assertion that the channels "do not share component
dependency". At time *t* in flight, the realised provenance of those channel
values may collapse to fewer distinct sources than the design assumed, because
of shared GNSS fixes, a shared estimator state, a shared decoder, a shared
clock, or a shared configuration path.

**Question.** Can a runtime layer compute the *effective number of independent
evidence sources* currently backing a given assurance verdict, does that number
fall below its nominal value during ordinary operation, and does anything in
the stack notice when it does?

## Five-part gap test (item 12)

**1. EXISTING WORK.** Existing methods solve —

- the *design-time probability* that nominally diverse channels fail together
  (S065 Littlewood & Miller; S069; S066 IEC 61508 β-factor and diagnostic
  coverage);
- the *consistency of a fused estimate* when the correlation between inputs is
  unknown (S060 Inverse Covariance Intersection; S061; S062 data incest);
- the *statistical detection of shared information* between fusion inputs
  (S063);
- *isolability from a fixed structural model*, recomputable when the available
  measurement set changes (S050, S052).

**2. ASSUMPTION.** They require the dependency structure among evidence
sources to be **known and fixed at design time** — as a β-factor, a CCF group,
a structural model, a bound on common information, or an architectural
assertion (S067: the compared sensors "do not share component dependency";
S004: the architecture "does not address sensors").

**3. FAILURE.** That assumption fails in autonomous assurance because the
realised provenance of a monitor's inputs is produced at runtime by the
protocol, the decoder, the estimator's gating, the freshness policy and the
vehicle's configuration — none of which is a design-time constant. S088
documents the extreme case in service: spoofed GNSS is consistent across
satellites, so residual checks stay small while every channel is wrong. S011
(2026) states the assumption it violates: learned policies "assume accurate
position and velocity information derived from GNSS; an assumption that fails"
in the field.

**4. UNSOLVED GAP.** Existing methods do not tell a **monitor** that a
**diagnostic test it is currently running has lost its power** because the
channels it compares now trace to one upstream source, and they do not report
the current effective independence of a verdict. The fusion literature repairs
an *estimate*; a widened covariance does not restore a residual's ability to
separate hypotheses. That estimate-versus-test boundary is the gap.

**5. FALSIFIABLE TEST.** Construct the evidence-provenance DAG for each CSIA
monitored verdict directly from producer source (ArduPilot, PX4) and consumer
source (the three CSIA decode paths), every edge pinned to a verified
`file:line`. Compute, per tick on real logged data, the minimum upstream vertex
cut κ separating the verdict's channel set from the sensing frontier. Then
inject a single upstream fault in SITL and test whether ≥2 nominally
independent channels move together while every cross-check stays silent. If κ
equals its nominal value everywhere, or if every κ drop is already declared by
design-time common-cause analysis, the candidate is dead.

## ≥5 closest sources

S060 (ICI, Automatica 2017) · S061 (fusion under unknown correlation) · S062
(data incest) · S063 (conditional-independence testing for shared information
in fusion) · S067 (multi-sensor FDI requiring non-shared component
dependency) · S041 (CoCo — composition of assumption monitors) · S069
(diverse redundancy and failure correlation in road-vehicle assurance) ·
S029 (RTLola on a certified eVTOL) · S011 (GNSS-degraded safety filtering,
2026) · S088 (GNSS spoofing defeats RAIM by cross-satellite consistency).

## Hostile prior-art sources

- **S065 — Littlewood & Miller (1989), foundational.** The *principle* that
  agreement between commonly-sourced channels is not evidence is 37 years old.
  Candidate B may never claim the principle. Only the runtime construction and
  the measurement are available to it.
- **S063 — conditional-independence testing in fusion.** The single most
  dangerous source. If its full text attaches a shared-information verdict to a
  monitor's decision, candidate B is dead.
- **S060 — Inverse Covariance Intersection.** Explicitly "finds the maximum
  possible common information shared by the estimates to be fused" and removes
  a bound on it. If the full text frames this as a general evidence-accounting
  result rather than an estimator-consistency result, candidate B narrows to
  nothing.
- **ARP4754A / ARP4761 common-mode analysis (not obtained).** Aerospace
  certification already performs common-mode analysis as a *process*. This is
  the most likely place for candidate B to already exist under a different
  name, and it was unreachable in this environment. Flagged as the largest
  unclosed risk.

## Known mathematics (item 13)

- **Mathematical object.** A time-indexed evidence-provenance DAG
  *G_t = (V, E)*; a verdict *v* computed from a channel set *S ⊆ V*; a sensing
  frontier *F ⊆ V* (physical transducers).
- **Known theory.** Menger's theorem (max vertex-disjoint paths = min vertex
  cut); d-separation in DAGs; minimal cut sets in fault-tree analysis;
  conditional independence; classical hypothesis-test power.
- **Potential proposition.** If the minimum vertex cut between *S* and *F* has
  size 1, every consistency residual over *S* has zero power against any fault
  located at the cut vertex.
- **Genuinely new, or a corollary?** **A corollary.** Stated plainly here and
  in `SELECTED_CANDIDATE_FORMAL_TARGET.md`. The proposition follows from
  Menger plus the definition of a residual. It is not a contribution.
- **Counterexample opportunity.** A channel pair with κ = 1 whose agreement is
  nevertheless informative — which would exist if the two paths apply
  independent physical checks after the shared vertex. Finding one bounds the
  proposition's practical reach and is worth more than proving it.
- **Complexity.** Min vertex cut is polynomial; the real cost is *soundly
  constructing G_t from source*, which is a program-analysis problem and is
  where the work actually is.

## Proposed formal result

Not a theorem. A **definition plus a measurement instrument**: effective
independence κ_t(v) of a verdict, and a sound-by-construction procedure for
obtaining G_t from producer and consumer source with every edge cited. Labelled
`SYSTEMS_CONTRIBUTION_ON_KNOWN_MATHEMATICS`, per item 13's instruction not to
force a theorem.

## Smallest kill test

Source-provenance audit (no execution) + one paired single-upstream-fault
injection. Full design in `SELECTED_CANDIDATE_STAGE0_DESIGN.md`.

## Expected failure modes

Seven, in `SELECTED_CANDIDATE.md` §Pre-mortem.

## HIL plan (item 17) and physical path (item 18)

`software → SITL → replay of the existing real PX4 ULog and MAVLink captures →
bench HIL`. Bench HIL needs one Pixhawk-class flight controller and one GNSS
module; the manipulation is removing or degrading the single upstream source
and observing two nominally independent channels respond together. No motion
table, no RF transmission, no flight. **Cost: $100–$500**, and $0 if the
existing captures suffice. Legal and safe: no RF emission, no airborne
operation.

## Expected time

Audit 1–2 days of source reading; SITL injection minutes per cell; total
Stage 0 well under a week.

## Paper-level ceiling

A solid systems paper at RV, ICCPS/EMSOFT, SAFECOMP or DASC, contingent on the
measurement being non-trivial and on the full-text audit not killing it.

## Dissertation-level ceiling

**One chapter, not the dissertation.** Under item 27's gate it plausibly
produces: A (new problem formulation), C (new algorithm/system), D (controlled
causal evidence), F (bench HIL) — four of eight. It does **not** plausibly
produce B (nontrivial formal result), because the mathematics is a corollary.

## Commercial use (item 22)

An **effective-redundancy meter**: a runtime number an OEM's assurance layer
publishes alongside each verdict — *"this verdict is currently backed by 1
independent source, not 3."* Concrete capability for UAV and eVTOL OEMs
(dispatch and degraded-mode decisions), fleet analytics and MRO (post-flight
identification of intervals where claimed redundancy was not delivered), and
defence autonomy (evidence-independence as a jamming/spoofing indicator
without an attack model). Not "AI safety".

## Publication venue and what reviewers would demand (item 23)

Runtime verification (RV), CPS (ICCPS), dependable systems (SAFECOMP/DSN), or
aerospace systems (DASC/AIAA SciTech). Reviewers in RV would demand a precise
semantics for G_t and soundness of its construction. SAFECOMP reviewers would
demand the comparison against ARP4761 common-mode analysis, and would be the
first to say this is CCA done at runtime. DASC would demand the aircraft data.

---
---

# TOP #2 — CANDIDATE A

## Exact problem statement

A runtime assurance layer emits a safety verdict at every tick. Its correctness
argument is stated over the plant model. Can the layer determine, at the same
tick rate, whether that verdict was actually *determined by the evidence it
received* — as opposed to being emitted by default because the relevant
evidence was absent, stale, or semantically misread?

## Five-part gap test (item 12)

1. **EXISTING WORK.** Monitorability classifies properties by whether a finite
   observation can produce a verdict (S013–S015); monitoring under partial and
   imperfect information keeps verdicts sound when the trace has gaps
   (S020–S022); CoCo attaches calibrated confidence to each verification
   assumption and composes it (S041); ConSerts and dynamic safety cases
   evaluate certificate conditions at runtime (S032–S037).
2. **ASSUMPTION.** They require the imperfection to be described by a **model
   supplied in advance** — a loss bound, a gap model, an indistinguishability
   relation, an enumerated certificate variant, or a calibration set per
   assumption.
3. **FAILURE.** In an autonomous aircraft the evidence-loss process is
   produced by protocol timing, decoder semantics, staleness policy, sentinel
   handling and gating. It is not one parametric loss model, and the prior CSIA
   work packages showed the same raw condition producing three different
   downstream tokens across three consumers.
4. **UNSOLVED GAP.** Whether anything remains after S016 moved the
   monitorability check to runtime **cannot be established without full text.**
   That is the honest state of this candidate.
5. **FALSIFIABLE TEST.** Read S016, S024 and S041 in full. If any computes
   per-tick verdict determinacy from the realised observation set, the
   candidate is dead with no experiment run.

## ≥5 closest sources

S016 (Ain't No Stopping Us Monitoring Now, TOSEM 2025) · S013 (Monitorability
for RV) · S020 (Rational monitor with imperfect information, TOSEM 2025) ·
S041 (CoCo) · S032 (ConSerts) · S024 (Uncertainty in RV: a survey) · S029
(RTLola on an eVTOL) · S004 (Simplex: sensors out of scope).

## Hostile prior-art sources

S016 and S041, either of which may close it outright; S024, a survey of the
whole space that would already list the gap if it were open.

## Known mathematics

Monitorability lattices; three- and four-valued LTL semantics; epistemic logic
over indistinguishability relations. A new result here would be an extension of
a well-developed theory, and would be judged as such.

## Proposed formal result

A per-tick determinacy predicate over the realised observation set, with a
soundness relation to classical monitorability. `CONJECTURE` at best;
`PRIOR_ART_RISK = 9`.

## Smallest kill test

Three full texts. Zero code.

## Expected failure modes

S016 already does it; the "aircraft alphabet varies" distinction turns out to
be expressible inside existing epistemic monitoring; the phenomenon exists but
never changes an action — the outcome the three previous CSIA packages all
reached.

## HIL plan / physical path

Same ladder as B and the same bench, but the manipulation (withholding a
channel) is easier to do in software than on a bench, so HIL adds little.
**Cost: $0–$100.**

## Expected time

Days, once full text is available. Blocked until then.

## Paper-level ceiling / dissertation ceiling

Workshop paper at best unless S016 leaves more room than expected. Not a
dissertation core.

## Commercial use

A "verdict determinacy" flag alongside each monitor output. Real, but a smaller
capability than B's effective-redundancy meter.

## Venue

RV, FM, NFM. Reviewers there know the monitorability literature intimately and
would open with S016.

---
---

# TOP #3 — CANDIDATE J

## Exact problem statement

A formal guarantee about a CPS transfers to a deployed vehicle only if the
assumptions it rests on hold there. Those assumptions are written in the
language of the proof. For a published runtime-assurance guarantee, what
fraction of its assumptions are decidable from the signals a real autopilot
actually produces — and what does the guarantee mean for the ones that are not?

## Five-part gap test (item 12)

1. **EXISTING WORK.** S042 (2025) extracted 423 assumptions and 321 guarantees
   from 104 CPS papers and tagged the language features assumptions need;
   ConSerts (S032) evaluates enumerated certificate conditions at runtime;
   ACCESS (S037) invalidates assurance-case fragments when sensor readings
   leave authored ranges; CoCo (S041) monitors verification assumptions with
   calibrated confidence.
2. **ASSUMPTION.** Each of these requires the assumption to be **already
   expressible as a runtime-evaluable condition** — an enumerated variant, an
   authored range, a monitored predicate with calibration data.
3. **FAILURE.** S042's own reported gaps are about assumptions concerning
   sensing, initialization, perception and uncertainty — precisely the ones
   least likely to be expressible that way. An assumption such as "the sensors
   are synchronised" or "the noise is stationary" has no obvious decision
   procedure over telemetry.
4. **UNSOLVED GAP.** No source visibly *measures* the checkable fraction of a
   guarantee's assumption set against a real vehicle's signal universe, nor
   says what a guarantee is worth when part of its precondition is
   permanently unobservable.
5. **FALSIFIABLE TEST.** Take one RTA guarantee from S007 or S011, enumerate
   its assumptions, and classify each as decidable / partially decidable /
   undecidable against the 106-field MAVLink+uORB universe already enumerated
   in `research/ai_contract_synthesis/`. If all are decidable, dead in an
   afternoon.

## ≥5 closest sources

S042 (Systematizing Assumptions, 2025) · S041 (CoCo) · S032 (ConSerts) · S037
(ACCESS) · S035 (operationalising dynamic safety cases, 2025) · S036
(subjective-logic runtime confidence, 2026) · S026 (anticipatory monitoring
with assumptions) · S012 (Rushby, Assurance of AI Systems).

## Hostile prior-art sources

S042 itself — it may already contain the measurement — and S032, whose entire
design is the runtime evaluation of guarantee preconditions.

## Known mathematics

Assume-guarantee contracts; refinement; the standard conditional reading of a
guarantee. No new mathematics is plausible here.

## Proposed formal result

None beyond a definition of the checkable fraction. `FORMAL_DEPTH = 4`. This is
the weakest finalist on formal depth and is ranked third for that reason.

## Smallest kill test

One guarantee, one assumption list, one classification pass. Hours.

## Expected failure modes

It becomes a survey with a table; S042 already did it; the classification is
subjective and the result is an artefact of who did the classifying —
a serious threat, and the reason a second independent classifier would be
mandatory.

## HIL plan / physical path

None needed; this is a paper-and-signal-universe study. `HIL_FEASIBILITY = 4`
reflects that HIL would add little, not that it is hard. **Cost: $0.**

## Expected time

Days for a pilot; weeks for anything defensible.

## Paper-level ceiling / dissertation ceiling

A good empirical-software-engineering or SAFECOMP paper. Not a dissertation
core; at most a framing chapter.

## Commercial use

A due-diligence instrument: given a vendor's claimed guarantee, report which of
its preconditions the platform can actually evidence. Real value in
certification and procurement, low technical depth.

## Venue

SAFECOMP, EMSE, ICSE-SEIP. Reviewers would demand inter-rater agreement on the
classification and a defence against S042.

---
---

## HOSTILE REVIEW OF ALL THREE FINALISTS (item 28)

Reviewers A–J, answered for each finalist. Concessions are made where the
reviewer is right.

### Reviewer A — "This is already known under another name."

- **B:** Partly right. The *principle* is Littlewood–Miller (1989) and
  common-cause analysis; the *estimate-side* repair is Covariance
  Intersection. What is claimed is neither: it is the runtime computation of a
  diagnostic test's remaining power. Whether that too has a name — likely
  candidates: common-mode analysis in ARP4761, minimal cut sets, provenance
  analysis — is **not established**, because no full text was read.
- **A:** Right, most likely fatally. The name is *monitorability*, and S016
  appears to have moved it to runtime already.
- **J:** Right in part. The name is *assume-guarantee contracts* / conditional
  certification. What is new would be the measurement, not the concept.

### Reviewer B — "This is just a UAV application of standard theory."

- **B:** The theory (Menger, d-separation) is standard and this package says
  so. The defence is that the object measured — a runtime provenance graph
  derived from real autopilot source — is not obtainable from theory, and that
  the *finding* (does κ actually drop, and does anyone notice) is empirical.
  If κ never drops, Reviewer B wins outright.
- **A:** Yes, and this is why A is ranked second.
- **J:** Yes, and this is why J is ranked third.

### Reviewer C — "Your result depends on one simulator bug."

- **B:** Strongest reviewer against B, and the design answers him: the primary
  endpoint is computed from **source-code provenance**, not from simulator
  behaviour, and it is evaluated on **real logged data** (the 9.6 MB PX4 ULog
  and real MAVLink captures) as well as SITL. Every provenance edge is pinned
  to a `file:line` in ArduPilot or PX4 upstream source. A simulator bug cannot
  create a provenance edge.
- **A/J:** Not applicable — neither has a simulator-dependent endpoint.

### Reviewer D — "Your formal theorem is a trivial corollary."

- **B:** **Conceded without argument.** It is a corollary of Menger. The
  package labels it that way in three separate files rather than defending it.
- **A:** The proposed determinacy predicate would be an extension of an
  existing lattice — again corollary-grade.
- **J:** There is no theorem, and none is claimed.

### Reviewer E — "Your baseline already solves the problem."

- **B:** The baselines are (i) design-time common-cause analysis and (ii)
  Covariance Intersection. The Stage-0 design runs both as explicit baselines
  and the null is written so they can win. If every κ drop is already in the
  design-time CCF group, the baseline wins and the candidate dies.
- **A:** S016 is plausibly that baseline.
- **J:** S042 is plausibly that baseline.

### Reviewer F — "The effect vanishes after controlling for common cause / history / timing."

- **B:** The irony is noted: for B, common cause *is* the effect, so the
  relevant control is different — the null control on an all-nominal word, as
  used in every prior CSIA package, plus a positive control on a channel pair
  that is independent by construction and must show κ = 2. If the positive
  control also shows κ = 1, the instrument is broken and the run is void.
- **A/J:** The relevant control is the same nominal-word control.

### Reviewer G — "No physical relevance."

- **B:** Answerable. S088 documents the mechanism in service (spoofed GNSS
  consistent across satellites), S090 is FAA operational guidance on GNSS
  interference, and the bench HIL path costs $100–$500. If the phenomenon
  cannot be shown on the bench, that is a real result against B.
- **A:** Weak here.
- **J:** No physical component at all; conceded.

### Reviewer H — "You require labels or assumptions unavailable online."

- **B:** No labels. κ is computed from source structure and observed message
  arrival; nothing is fitted, nothing is learned, no threshold is tuned.
  This is B's strongest answer to any reviewer.
- **A:** No labels either.
- **J:** No labels, but the classification is human-judgement-dependent, which
  is a different and equally real weakness.

### Reviewer I — "Your contribution is merely integration."

- **B:** Partly conceded. Building a provenance graph and running a min-cut is
  integration of known parts. The non-integration content is whether the
  measurement reveals something the design-time analysis missed. If it does
  not, the contribution *is* merely integration and B should be abandoned.
- **A/J:** Conceded more fully.

### Reviewer J — "This is another novelty pivot after earlier hypotheses failed."

**Chronology conceded, without qualification.** This repository has, in
sequence, abandoned: a general self-occlusion theorem; a graph-coarsening
theorem; CUSUM/slow-ramp detector novelty; validity gating; receiver-health
rescue; intermittent invalidity masking; dual admissibility; evidence-semantic
equivalence checking; shortest-counterexample generation; AI-assisted contract
synthesis; conflicting semantic authorities. Eleven abandoned directions
before this one, several of them abandoned only after being built.

The only legitimate answer is a stronger prior-art audit — and **this stage
cannot supply one**, because it could not read a single paper in full. That is
why the selected candidate's status in `CLAIM_LEDGER.json` is `PROVISIONAL`,
why `SELECTED_CANDIDATE_STAGE0_PROMPT.md` opens with a full-text gate rather
than an experiment, and why the executive verdict of this stage is not "we
found the frontier" but "we found where to look, and we could not yet check
whether someone is already standing there."
