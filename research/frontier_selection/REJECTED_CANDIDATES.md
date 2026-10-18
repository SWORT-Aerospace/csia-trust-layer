# REJECTED CANDIDATES

Item 29. Nothing is silently discarded. Each entry carries: closest prior art,
kill reason, the exact abstraction that subsumes it, whether it survives as
useful engineering, and whether it could still be a minor paper.

**Standing caveat.** Every kill below rests on snippet-level reading only
(`SEARCH_PROTOCOL.md` §0). A kill made from a snippet is *safe in the
direction that matters* — it can only be too harsh, never too generous — so
these rejections are the one class of conclusion the missing full text does
not endanger. If a rejected candidate is ever revived, it must be revived
against full text, not against this file.

---

## C — RUNTIME STRUCTURAL AMBIGUITY / ONLINE DIAGNOSABILITY

**Closest prior art.**
S043 *Robust diagnosis of DES against permanent loss of observations*
(Automatica 2012) · S044 *…against intermittent loss of observations*
(Automatica 2012) · S047 *Codiagnosability and coobservability under dynamic
observations* · S046 *Intermittent fault diagnosability of DES: an overview*
(DEDS 2021) · S052 *FDI based on structural analysis* (2025) · S049 *Bayesian
Diagnosability and Active Fault Identification* (2025).

**Kill reason.** The candidate's distinction — offline diagnosability of the
whole system versus online diagnosability given the currently active evidence
— is a named, worked concept. S047 calls the general setting *dynamic
observations*. S044 handles intermittent loss with necessary and sufficient
conditions. S052's snippet states that structural analysis is used to handle
a *varying* set of available measurements and adjust the FDI system
accordingly. S049 (2025) defines diagnosability relative to the control
sequence actually applied. The brief's instruction — *"If this exact problem
is known: kill it"* — fires.

**Exact subsuming abstraction.** Diagnosability of partially observed systems
under a time-varying observation map.

**Useful engineering?** Yes. Knowing which CSIA fault hypotheses are currently
separable is worth having in the product regardless of novelty. It belongs in
engineering work, not in the dissertation frontier.

**Minor paper?** Possibly an applications note: *structural isolability of a
MAVLink-fed trust layer under realistic channel availability*. But S051
already applies structural analysis to MAVLink-enabled UAVs, so even the
application is taken.

---

## D — ONLINE CALIBRATION FAILURE WITHOUT LABELS

**Closest prior art.** S073 *LaSCal* (NeurIPS 2024) · S072 *Estimating
calibration error under label shift without labels* · S074 *Unsupervised
Detection and Correction of Model Calibration Shift at Test-Time* · S075
*Unsupervised Calibration under Covariate Shift* · S076 *Conformal prediction
beyond exchangeability* (Annals of Statistics 2023).

**Kill reason.** The candidate question is "can a runtime detect its own
calibration has failed without labels". S072–S074 answer exactly that, by
name, with estimators and corrections. S076 bounds what happens when the
underlying exchangeability assumption breaks.

**Exact subsuming abstraction.** Label-free calibration-error estimation under
distribution shift.

**Useful engineering?** Not for CSIA. CSIA's trust output is not a probability
and is not fit by learning, so there is no calibration object to monitor.

**Minor paper?** No.

---

## E — PHYSICS + LEARNED PERCEPTION ASSURANCE

**Closest prior art.** S077 *Perceive With Confidence* · S078 *Safe
Perception-Based Control under Stochastic Sensor Uncertainty using Conformal
Prediction* · S079 *Conformal Safety Shielding for Imperfect-Perception
Agents* (RV 2025) · S080 *Closing the Loop on Runtime Monitors with
Fallback-Safe MPC* · S081 *Out-of-Distribution Detection Is Not All You Need*.

**Kill reason.** The brief supplied the kill in advance: *"Kill if surviving
contribution is just: apply conformal prediction to drones."* After the five
sources above, that is all that is left. S081 even pre-empts the fallback
position by title.

**Exact subsuming abstraction.** Conformal prediction for perception-based
control.

**Useful engineering?** Not applicable — CSIA has no learned perception
component, and item 43 of the prior work package forbids adding one.

**Minor paper?** No.

---

## F — ADVERSARIAL CONSISTENCY

**Closest prior art.** S083 *Black-box Stealthy GPS Attacks on UAVs* · S084
*Stealthy Perception-based Attacks on UAVs* · S085 *Vulnerability Analysis of
Nonlinear Control Systems to Stealthy FDI* · S086 *Analysis and Design of
Stealthy Cyber Attacks on Unmanned Aerial Systems* (AIAA JAIS) · S087 *Optimal
two-channel switching FDI attacks against UAV remote state estimation* · S089
*Model-based Randomness Monitor for Stealthy Sensor Attacks*.

**Kill reason.** "A fault engineered to stay inside the monitor's consistency
manifold" is the definition of a stealthy attack, and that field is large,
formal, current, and already specialised to UAVs in an AIAA journal.

**Exact subsuming abstraction.** Stealthy false-data injection / secure state
estimation.

**Useful engineering?** Yes, as a threat model to keep in mind — recorded, as
the prior package required, without building any exploit tooling.

**Minor paper?** No. And this direction would drag the work toward offensive
tooling, which the prior package explicitly ruled out and which nothing here
reopens.

**What was salvaged.** S088's mechanism — spoofed GNSS is *consistent across
satellites*, so RAIM residuals stay small — is the cleanest real-world
instance of a single upstream source manufacturing agreement across nominally
independent observations. It is carried into candidate B as a motivating
example only. No attack is built, modelled, or evaluated.

---

## G — MODEL MISSPECIFICATION / UNKNOWN FAULT

**Closest prior art.** S058 *Data-driven fault diagnosis analysis and open-set
classification of time-series data* · S059 *Diagnostics for Mechanical Systems
with Unknown Fault Modes: Open Set Recognition* · S049 *Bayesian
Diagnosability and Active Fault Identification* (2025, "explicitly accounts
for unmodeled faults") · S056 *Active Fault Identification … for Unknown
Bounded Faults*.

**Kill reason.** Item 26 hard-kills a candidate whose surviving contribution is
a "known detector". This one reduces to open-set recognition, which is named
in the sources by that exact term.

**Exact subsuming abstraction.** Open-set recognition / open-world diagnosis.

**Useful engineering?** Marginally — an "none of my hypotheses fit" output in
CSIA's diagnosis layer would be defensible engineering. The frozen core
forbids touching it in research work anyway.

**Minor paper?** No.

---

## H — SAFE AUTHORITY UNDER DIAGNOSTIC AMBIGUITY

**Closest prior art.** S055 *Diagnosis and Fault-Tolerant Control* (Blanke,
Kinnaert, Lunze, Staroswiecki — textbook) · S056 *Active Fault Identification
and Robust Control for Unknown Bounded Faults via Volume-Based Costs* (2025) ·
S053 *Set-Membership Estimation for Fault Diagnosis* · S054 *Closed-loop input
design for guaranteed fault diagnosis using set-valued observers* · S080
*Closing the Loop on Runtime Monitors with Fallback-Safe MPC*.

**Kill reason (three, any one sufficient).**

1. The relationship the candidate proposes to *discover* — ambiguous diagnosis
   ⇒ reduced authority — is the organising principle of fault-tolerant
   control, with a textbook (S055) and a 2025 quantitative sharpening (S056).
2. It is adjacent to killed direction 12 (*conflicting semantic authorities /
   set-valued interpretation as a general formal contribution*). Item 0
   forbids resurrecting or renaming killed ideas, and "set-valued diagnosis
   determines authority" is close enough to require the bar, not the benefit
   of the doubt.
3. The previous work package already measured the downstream half of this on
   CSIA and found **0 of 9 authority pairs reached the failsafe ACTION level**.
   The empirical lever is known to be weak on this stack.

**Exact subsuming abstraction.** Passive and active fault-tolerant control
under set-valued diagnosis.

**Tie-break record.** H tied J at **3.950**. The tie-break rule was fixed
before scores were compared (`TOP_THREE.md` §0): *on a tie, prefer the
candidate whose closest prior art is further from a complete solution.* H's
closest prior art is a complete answer in a textbook; J's closest prior art
(S042) *states* the gap and does not close it. J advances; H is rejected. Kill
reasons 2 and 3 independently confirm the direction of the tie-break.

**Useful engineering?** Yes — CSIA already degrades authority; documenting the
mapping is good engineering.

**Minor paper?** Possibly an aerospace-systems short paper, if the empirical
half were strong. It is not, on this stack.

---

## I — DYNAMIC EVIDENCE DEPENDENCY / DATA INCEST

**Closest prior art.** S060 *Decentralized data fusion with inverse covariance
intersection* (Automatica 2017) · S062 *Managing data incest in a distributed
sensor network* · S061 *Distributed Multisensor Data Fusion under Unknown
Correlation and Data Inconsistency* · S063 *Testing conditional independence to
determine shared information in a data/signal fusion process*.

**Kill reason.** The brief predicted it: *"This area is likely heavily
occupied. Kill it unless a sharp autonomy-assurance gap survives."* It is
occupied. ICI explicitly finds the maximum common information shared by
estimates and removes a bound on it.

**Exact subsuming abstraction.** Decentralised fusion under unknown
correlation; common-information management.

**The one line that survives, and where it went.** All of this literature
repairs a **fused estimate's consistency**. None of it, as far as any snippet
shows, tells a **monitor** that a **diagnostic test** it is running has lost
its power. That boundary — estimate versus test — is the only sharp point in
the area, and it is the load-bearing distinction of candidate **B**. Candidate
I is rejected; the distinction is not.

**Useful engineering?** Yes, if CSIA ever fuses.

**Minor paper?** No.

---

## K — GATE-CONDITIONED SELF-CONFIRMING EVIDENCE LOOPS

**Closest prior art.** S070 *Selection-Induced Contraction of Innovation
Statistics in Gated Kalman Filters* (2025) · S071 PX4 EKF2 gating
documentation.

**Kill reason — two, independently sufficient.**

1. **Item 0.** This is killed direction 1 (*self-occlusion*) in different
   clothing: a mechanism suppresses the evidence that would have revealed it.
   The mechanism differs (an innovation gate rather than a fault) but the
   argument shape is identical, and item 0's instruction is not "do not repeat
   the mechanism" but *"do not resurrect or rename killed ideas."*
2. **Already published.** S070's snippet states the effect directly: post-gate
   schemes "systematically underestimate the innovation covariance", and this
   "feedback mechanism arises as a direct consequence of ignoring the
   gate-conditioned nature of the observed innovation process."

**Exact subsuming abstraction.** Selection bias in gated estimation.

**Score disclosure.** K's weighted frontier score is **4.200**, which would
have ranked it second, above J and H. It is disqualified on rule, not on
score, and the score is published here so the ranking cannot be accused of
quietly suppressing it.

**Useful engineering?** Yes — it is a real property of the PX4 stack CSIA
consumes, and worth knowing when interpreting EKF innovation statistics as
health evidence. Bank it as engineering, per item 37.

**Minor paper?** No — S070 has it.

---

## L — MONITOR / CONTROLLER SHARED-INPUT COUPLING IN RTA

**Closest prior art.** S004 *A Component-Based Simplex Architecture* (states
that sensors are out of scope) · S041 CoCo · S067 (requires channels that do
not share component dependency).

**Kill reason.** Not wrong — *subsumed by candidate B*. The shared upstream
source is shared between monitor and controller instead of between two
monitored channels; that is one edge of the same provenance graph. Splitting
it out would produce two weaker contributions instead of one.

**Exact subsuming abstraction.** Candidate B, restricted to the
monitor/controller pair.

**Useful engineering?** Yes, and it is retained inside B's Stage-0 design as a
named sub-case that the provenance audit must cover.

**Minor paper?** Only as part of B.

---

## SUMMARY

| id | disposition | subsuming abstraction |
|---|---|---|
| C | rejected | diagnosability under a time-varying observation map |
| D | rejected | label-free calibration-error estimation under shift |
| E | rejected | conformal prediction for perception-based control |
| F | rejected | stealthy FDI / secure state estimation |
| G | rejected | open-set recognition |
| H | rejected (lost tie-break; two independent kills) | passive/active FTC under set-valued diagnosis |
| I | rejected | decentralised fusion under unknown correlation |
| K | disqualified under item 0, and already published | selection bias in gated estimation |
| L | folded into B | candidate B restricted to the monitor/controller pair |

Nine of twelve candidates die here. Two survive as finalists behind the
selected one. That ratio is the expected output of a literature-first stage
and is not a sign that the search failed.
