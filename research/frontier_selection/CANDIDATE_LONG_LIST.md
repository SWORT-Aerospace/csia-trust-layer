# CANDIDATE LONG LIST

Twelve candidates. Nine are the families the brief required (items 8, A–I).
Three were added under item 9, each because a **primary source visibly exposed
an unresolved assumption** — never from imagination. Item 9's cap of 12 total
is respected exactly.

Every candidate below carries, per items 11, 14 and 15:

- **Reduction** — the established abstraction it collapses into (item 11)
- **Three-sentence abstract** — problem / contribution / result (item 14)
- **Hostile read** — the sentence that kills it, or the reason it survives
- **Smallest kill test** (item 15)
- **Current-stack feasibility** (item 16)

Scores and the weighted frontier score are in `CANDIDATE_SCORECARD.csv`.
Rejections are itemised in `REJECTED_CANDIDATES.md`.

**Two standing caveats apply to all twelve.**

1. No source was read past its snippet (`SEARCH_PROTOCOL.md` §0). Where a
   candidate is called "not visibly answered", that means *not visible in a
   snippet* — it does not mean absent from the literature, and it is never
   used as evidence of novelty.
2. Every HIL and hardware statement below is a **feasibility estimate, design
   only**. No physical HIL was executed, no hardware is present in this
   environment, and item 36 forbids execution regardless.

---

## The three added under item 9, and what motivated each

| id | added candidate | primary source that exposed the assumption |
|---|---|---|
| J | Runtime-checkability of the assumption sets that CPS guarantees rest on | **S042** Li, Faghfoorian & Ruchkin, *What Does It Take to Get Guarantees? Systematizing Assumptions in CPS* (2025) — extracted 423 assumptions from 104 papers and reports gaps in how assumptions around sensing, initialization, perception and uncertainty are stated |
| K | Gate-conditioned self-confirming evidence loops | **S070** *Selection-Induced Contraction of Innovation Statistics in Gated Kalman Filters* (2025) — post-gate innovations systematically underestimate innovation covariance, a self-confirming cycle |
| L | Monitor/controller shared-input coupling in RTA | **S004** *A Component-Based Simplex Architecture* (2017) — the architecture "does not address sensors"; **S067** requires channels that "do not share component dependency" |

K and L do not survive. They are still listed, scored and disposed of in
writing, per item 29.

---

## A — ASSURANCE OF THE ASSURANCE MONITOR

**Question.** Can a runtime assurance layer determine, online, whether its own
safety verdict is currently evidentially supportable?

**Reduction (item 11).** → *monitorability* in runtime verification, plus
*confidence in assurance arguments*.

**Three-sentence abstract.**
Runtime assurance architectures emit safe/unsafe verdicts whose correctness is
argued from a plant model, while saying nothing about whether the evidence
behind the verdict was actually present at the moment it was emitted. We give
a monitor a second output — whether its own verdict is currently determined by
the evidence it received — and show it can be computed at the same rate as the
verdict. On a real autopilot log the monitor's verdict is undetermined for a
measurable fraction of flight time during which the classical monitor reports
"safe".

**Hostile read.** **S016** (*Ain't No Stopping Us Monitoring Now*, TOSEM 2025)
already, per its snippet, generalises monitors to decide "when to safely give
up on verification when it will never be able to conclude anything" — which
the snippet describes as *moving the monitorability check to runtime*. **S041**
(CoCo, ICCPS 2022) already builds calibrated confidence monitors for
verification assumptions and composes them. **S032** (ConSerts) already shifts
certification to runtime. The idea is occupied from three directions at once.
`PRIOR_ART_RISK = 9`.

**What is left, if anything.** The RV results reason about *future extensions
of a trace over a fixed alphabet*. An aircraft's problem is that the alphabet
itself — which channels exist, at what rate, with what semantics — varies.
Whether that difference is substantive cannot be settled without reading S016
and S024 in full.

**Smallest kill test.** Read S016, S024 and S041 in full. If any computes a
per-tick determinacy of the monitor's own verdict from the realised
observation set, the candidate is dead with no experiment.

**Current-stack feasibility.** High. CSIA's frozen nine-stage pipeline already
records what evidence reached the trust core per tick; the probe harness from
`research/evidence_semantics/probe.py` drives it deterministically.

**Status:** `TOP #2`.

---

## B — COMMON-CAUSE / CORRELATED EVIDENCE FAILURE → **runtime collapse of effective evidence independence**

**Question, sharpened.** A monitor credits *k* nominally independent channels
when it accepts a cross-check as evidence of health. At time *t*, how many
*genuinely distinct upstream sources* are actually behind those *k* channels —
and does that number fall below *k* during ordinary flight, without anything
alarming?

**Reduction (item 11).** → *common-cause failure theory* (β-factor, coincident
failure) and → *dependent-evidence fusion* (covariance intersection, data
incest).

**Why the reduction does not finish the job.** Both reductions are real and
both stop short of the same line:

- CCF theory and Littlewood–Miller (**S065**) establish the *principle* —
  agreement between sources with a shared origin is not evidence — and price
  it into a *design-time reliability number*. They do not compute anything at
  runtime. The principle is 1989 and cannot be claimed.
- Covariance Intersection and Inverse Covariance Intersection (**S060**,
  **S061**) handle unknown correlation by making the *fused estimate*
  consistent. The object they repair is an estimate's covariance. The object
  at issue here is the *power of a diagnostic test* — a different object. A
  consistent fused estimate can coexist with a cross-check that has zero
  ability to detect the fault in the shared parent.
- **S063** (*Testing conditional independence to determine shared information
  in a data/signal fusion process*) is the closest and the most dangerous: it
  detects shared information between fusion inputs statistically. Whether it
  attaches that result to a *safety verdict*, or builds a *provenance
  structure*, is not visible.

**Three-sentence abstract.**
Runtime assurance monitors treat agreement between nominally redundant
channels as evidence of health, but the number of genuinely independent
upstream sources behind those channels is a design-time assumption that is
never checked in flight. We define the *effective independence* of a verdict
as the minimum upstream vertex cut of its evidence-provenance graph, construct
that graph from producer and consumer source code, and evaluate it per tick
against real autopilot data. On real flight data the effective independence of
several monitored verdicts falls below its nominal value while every
cross-check remains silent.

**Hostile read.** Reviewer D will say the proposition (κ=1 ⇒ the cross-check
has no power against a fault at the cut vertex) is a corollary of Menger's
theorem and of d-separation. That is **correct**, and this package says so in
`SELECTED_CANDIDATE_FORMAL_TARGET.md` rather than dressing it up. The claim,
if any survives, is the runtime construction and the measured incidence — not
the mathematics.

**Smallest kill test.** A source-provenance audit of the ArduPilot and PX4
producers plus the three CSIA consumer paths, every edge pinned to a verified
`file:line`, followed by one paired single-upstream-fault injection in SITL.
Hours, not weeks. Full design in `SELECTED_CANDIDATE_STAGE0_DESIGN.md`.

**Current-stack feasibility.** The highest of any candidate. CSIA has three
independent decode paths over the same wire data, the ArduPilot and PX4 source
trees on disk, a real 9.6 MB PX4 ULog, deterministic replay, SITL, and a
frozen diagnosis core that must not be touched — and does not need to be.

**Status:** **SELECTED**.

---

## C — RUNTIME STRUCTURAL AMBIGUITY / ONLINE DIAGNOSABILITY

**Question.** Can the runtime determine that the currently active evidence
structure makes two or more fault hypotheses observationally
indistinguishable?

**Reduction (item 11).** → *diagnosability of discrete-event systems under
loss of observations*, and → *structural isolability*.

**Three-sentence abstract.** Not written: the candidate dies before item 14.

**Hostile read — decisive.** The area is occupied end to end:
**S043**/**S044** (Automatica 2012) verify robust diagnosability against
permanent and intermittent loss of observations; **S047** names the general
setting *dynamic observations*; **S045** adds network delay; **S046** is a
whole survey of intermittent-fault diagnosability; **S052** already recomputes
structural analysis when the available measurement set changes; and **S049**
(2025) defines a quantitative diagnosability that "reveals when passive fault
identification is fundamentally limited by the given control sequence" —
i.e. diagnosability conditioned on what is actually happening now. The brief's
own instruction applies: *"If this exact problem is known: kill it."*

**Status:** `REJECTED`. See `REJECTED_CANDIDATES.md`.

---

## D — ONLINE CALIBRATION FAILURE WITHOUT LABELS

**Reduction.** → *unsupervised calibration-error estimation under shift*.

**Hostile read.** **S073** (LaSCal, NeurIPS 2024) is a label-free consistent
calibration-error estimator with a post-hoc correction. **S072** estimates
calibration error under label shift without labels. **S074** detects *and*
corrects calibration shift at test time from unlabelled data. **S076**
(Annals of Statistics 2023) bounds the coverage gap when exchangeability
fails. The named question has named answers.

**Status:** `REJECTED`.

---

## E — PHYSICS + LEARNED PERCEPTION ASSURANCE

**Reduction.** → *conformal prediction for perception-based control*.

**Hostile read.** **S077**, **S078**, **S079** and **S080** cover
conformally-calibrated perception monitors, conformal state-estimation
regions, conformal safety shielding and monitor-to-fallback closure. **S081**
pre-empts the obvious "detect OOD" contribution by title. The brief's own
kill applies verbatim: *"Kill if surviving contribution is just: apply
conformal prediction to drones."*

**Status:** `REJECTED`.

---

## F — ADVERSARIAL CONSISTENCY

**Reduction.** → *stealthy false-data injection and secure state estimation*.

**Hostile read.** Six sources (**S083**–**S087**, **S089**), including an AIAA
journal paper on stealthy attacks against UAS specifically, define
stealthiness relative to a residual detector and synthesise optimal attacks
inside it. **S088** documents that spoofed GNSS is consistent across
satellites so RAIM residuals stay small. The abstract problem — a fault or
attacker that preserves agreement — is the *definition* of that field.

**Status:** `REJECTED`. Note the one thing worth keeping: S088's mechanism is a
concrete instance of candidate B's phenomenon, and is retained there as a
motivating example, not as a security contribution.

---

## G — MODEL MISSPECIFICATION / UNKNOWN FAULT

**Reduction.** → *open-set recognition*, which item 26 hard-kills by name.

**Hostile read.** **S058**, **S059** are open-set fault diagnosis; **S049**
(2025) builds unmodelled faults into a Bayesian diagnosability framework
directly; **S056** signals an unmodelled fault when measurements leave the
estimated model set.

**Status:** `REJECTED`.

---

## H — SAFE AUTHORITY UNDER DIAGNOSTIC AMBIGUITY

**Question.** Is there a formal relationship between diagnostic
distinguishability and the amount of autonomy authority that remains
justifiable?

**Reduction.** → *passive and active fault-tolerant control*.

**Hostile read.** **S055** (Blanke, Kinnaert, Lunze, Staroswiecki) is a
textbook whose answer is: if the fault is not isolated, use robust/passive
control. **S056** (2025) makes the link quantitative via uncertainty-set
volume thresholds. **S054** designs inputs that force separation. **S080**
closes a monitor into a fallback controller with guarantees. The relationship
the candidate proposes to discover is the organising principle of a mature
field.

**Additional bar.** H is adjacent to killed direction 12 (*conflicting
semantic authorities / set-valued interpretation as a general formal
contribution*). Item 0 forbids resurrecting or renaming killed ideas.

**Tie note.** H scores 3.950, exactly tying candidate J. The tie-break rule
was fixed before the scores were compared and is stated in `TOP_THREE.md` §0.

**Status:** `REJECTED`.

---

## I — DYNAMIC EVIDENCE DEPENDENCY / DATA INCEST

**Reduction.** → *decentralised fusion under unknown correlation*.

**Hostile read.** **S060** (Automatica 2017) finds the maximum common
information shared by estimates and removes a bound on it; **S062** is the
named prior art for double counting; **S061** handles unknown correlation and
inconsistency. The brief predicted this: *"This area is likely heavily
occupied. Kill it unless a sharp autonomy-assurance gap survives."* It is, and
the surviving sharp point is not I's — it is the estimate/test boundary, which
belongs to candidate B.

**Status:** `REJECTED`.

---

## J — RUNTIME-CHECKABILITY OF THE ASSUMPTION SETS BEHIND CPS GUARANTEES *(added under item 9)*

**Motivating source.** **S042**, Li, Faghfoorian & Ruchkin (2025): 423
assumptions extracted from 104 CPS papers, with reported gaps in how
assumptions about sensing, initialization, perception, neural components and
uncertainty are stated, and 21 tags for the language features needed to
express them.

**Question.** For a published formal CPS guarantee, what fraction of the
assumptions it rests on are decidable from the signals a real vehicle actually
receives in flight — and what does a guarantee mean when they are not?

**Reduction.** → *assume-guarantee contracts* and → *conditional safety
certificates*.

**Three-sentence abstract.**
Formal guarantees for cyber-physical systems transfer to a deployed vehicle
only if their assumptions hold there, yet the assumptions are stated in the
language of the proof rather than the language of the vehicle's signals. We
take published runtime-assurance guarantees, decompose their assumption sets,
and classify each assumption by whether it is decidable, partially decidable
or undecidable from the telemetry a real autopilot produces. A majority of
assumptions in the sampled guarantees turn out not to be decidable in flight,
which bounds what any runtime evaluation of those guarantees can mean.

**Hostile read.** **S032** (ConSerts) already shifts certification to runtime
by enumerating conditions; **S037** (ACCESS) already invalidates assurance-case
fragments when sensor readings leave authored ranges; **S034**, **S035**,
**S036** are dynamic safety cases and runtime confidence updating; **S041**
already builds monitors *for verification assumptions*. And the contribution
risks being a survey with a table.

**Smallest kill test.** Take one RTA guarantee from S007 or S011, enumerate its
assumptions, and classify each against the MAVLink/uORB field universe already
enumerated in `research/ai_contract_synthesis/` (106 fields). If every
assumption is decidable, the candidate is dead in an afternoon.

**Status:** `TOP #3`.

---

## K — GATE-CONDITIONED SELF-CONFIRMING EVIDENCE LOOPS *(added under item 9)*

**Motivating source.** **S070** (2025): schemes operating on post-gate
innovations underestimate innovation covariance, producing a self-confirming
cycle. **S071**: PX4's EKF2 gates every observation by default
(`EKF2_*_GATE`).

**Question.** When the estimator's own gate decides which measurements are
admitted, the health statistics computed from admitted measurements are
conditioned on the gate — so the estimator's evidence of its own health is
partly manufactured by its own filtering.

**Disposition — disqualified before scoring on merit.** This is the same
*shape* as killed direction 1 (*unrestricted/general self-occlusion theorem*):
a mechanism suppresses the very evidence that would reveal it. Item 0 says:
**"DO NOT resurrect or rename killed ideas."** It is not enough that the
mechanism differs in detail; the argument structure is the killed one.
Independently, **S070** has already published the effect.

Its weighted score (4.200) would have placed it second. It is recorded here so
that the ranking cannot be accused of hiding it.

**Status:** `DISQUALIFIED` under item 0.

---

## L — MONITOR / CONTROLLER SHARED-INPUT COUPLING IN RTA *(added under item 9)*

**Motivating sources.** **S004**: the Simplex architecture "does not address
sensors". A patent-adjacent snippet in the same search states that a monitor
"assumes sensor data received by the controller and monitor are fault-free or
protected using existing methods".

**Question.** RTA's safety argument assumes the monitor is independent of the
thing it monitors. When both read the same sensor chain, in what sense is it?

**Disposition.** This is a **special case of candidate B** — the shared
upstream source happens to be shared between the monitor and the controller
rather than between two monitored channels. Keeping it separate would split
one contribution into two weaker ones. It is folded into B and its motivating
assumption is carried in `OPEN_ASSUMPTION_LEDGER.csv` under candidate A/B.

**Status:** `REJECTED — folded into B`.

---

## RANKING (from `CANDIDATE_SCORECARD.csv`)

| rank | id | weighted frontier score | disposition |
|---:|---|---:|---|
| 1 | **B** | **5.900** | **SELECTED** |
| 2 | **A** | **4.250** | TOP #2 |
| — | K | 4.200 | disqualified under item 0 |
| 3= | H | 3.950 | rejected (tie-break lost to J) |
| 3= | **J** | **3.950** | TOP #3 (tie-break won) |
| — | L | 3.900 | folded into B |
| — | C | 3.750 | rejected |
| — | F | 3.550 | rejected |
| — | G | 3.400 | rejected |
| — | I | 3.050 | rejected |
| — | D | 2.950 | rejected |
| — | E | 2.650 | rejected |

The weighted score is a prioritisation device, exactly as item 25 says. It is
not a scientific metric and nothing in this package rests on it beyond
ordering. Every input to it is a subjective 0–10 judgement made by one agent
with no full-text access.
