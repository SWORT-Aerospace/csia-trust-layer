<!-- publication-guard: research-note -->
# REVIEWER RED TEAM — SYSTEMS PAPER

Brief B7. Four simulated reviewers. Each objection carries: the claim
challenged, the best version of the criticism, the evidence response, the
**remaining weakness** (never omitted), and the manuscript change it forces.

A criticism with no remaining weakness listed has almost certainly been
answered too easily. Every objection below lists one.

---

## REVIEWER 1 — AIAA / DASC avionics

### 1.1 "Your baseline is an autopilot from 2015."

**Claim challenged:** every Phase-I measurement (`SC-01`, `SC-12`–`SC-15`).

**Best criticism.** ArduCopter 3.3 SITL, dronekit-assets prebuilt,
2015-10-22. GNSS integrity handling has moved substantially since. A referee
is entitled to ask whether the paper reports a defect that upstream fixed
years ago, and if so the contribution collapses to a historical note.

**Evidence response.** Two parts. (a) The *mechanism* is structural, not
version-dependent: P3 in `FORMAL_CORE.md` follows from the signature table and
the gate, and holds for any system with hypothesis-relative applicability and
a skip-style gate. (b) Phase II re-ran on **ArduCopter 4.8.0-dev**, and the
finding did not vanish — E1 records three validated significant GNSS cells
escalated by neither the estimator nor CSIA. Phase II is *excluded* from Paper
I by `phase_guard.py` because mixing autopilots into one table is worse than
the criticism.

**Remaining weakness.** The paper cannot itself show the 4.8 result without
breaking its own phase guard, so the referee has to take §Limitations' word
for it. That is genuinely unsatisfying and there is no way to fix it inside
Paper I's scope.

**Manuscript change.** §Limitations must state the baseline date, name the
4.8 replication and its exclusion, and give the artifact path so a referee can
look — rather than only saying "3.3".

### 1.2 "The vehicle was never actually in danger."

**Claim challenged:** the operational significance of `SC-01`.

**Best criticism.** The failsafe reached CAUTION and reconfigured navigation
throughout. Nothing was lost. A reader could reasonably conclude the paper
documents a naming inconvenience.

**Evidence response.** Conceded, and it is in the abstract, not buried: *"The
vehicle is not blind… It cannot name the cause."* The claim is about
**attribution**, which is what a maintenance action, a fleet-wide grounding
decision or an operator's next step depends on. A layer whose stated product
is a cause distribution reporting `nominal` at 1.0 for a whole fault window is
a defect in the thing it exists to produce.

**Remaining weakness.** No evidence is offered that a misattribution ever cost
anything operationally. The paper cannot supply it and does not claim it.

**Manuscript change.** State once, explicitly, that no operational harm is
demonstrated and none is claimed.

### 1.3 "5.1% of every clean flight is 'indistinguishable'. Why is that not a
false-alarm story about your own metric?"

**Claim challenged:** `SC-05`.

**Best criticism.** If a metric fires on 76 ticks of a nominal flight, the
metric may be measuring startup rather than anything about faults.

**Evidence response.** It *is* measuring startup, and that is why it is
reported as a separate window with its cause named (`gvalid · (t > 3.0)`, the
smoother warm-up) rather than pooled into the fault number. The failsafe is
not armed for the first 10 s in any case (`FailsafeConfig.arm_time`). The
value of reporting it is that it shows the metric is not fault-triggered — it
is a property of `ACTIVE`, and it correctly reads the same in clean flight.

**Remaining weakness.** It does mean the headline "18.4% of GNSS_FIX_LOSS" is
5.1 points of startup plus 13.3 points of fault. The paper must present the
decomposition, not the pooled figure.

**Manuscript change.** Report the two windows separately in the table. Never
quote 18.4% alone.

---

## REVIEWER 2 — fault diagnosis / control

### 2.1 "This is state-dependent observation, and Dong, Yin and Li did it."

**Claim challenged:** the novelty of Mechanism A.

**Best criticism.** A state-dependent observation map
`O: Q × Σ → 2^(Δ ∪ {ε})` owns this mechanism in full generality. Everything
here is an instance.

**Evidence response.** **Conceded in the manuscript already**, in the related-
work section, in those words: the paper *asserts no priority* over the general
mechanism. What is offered is a measurement of the mechanism in a deployed
continuous-signal diagnostic layer, with the structural condition checkable
statically from the signature table, plus the implemented consequence
(`SUPPORT_LOST_FOR_REQUIRED_INFORMATION`).

**Remaining weakness.** The bibliography entry for that reference is
`FROM-BRIEF-UNVERIFIED` and the title is a `VERIFY` placeholder. A referee who
checks the citation will find the authors did not check it. This blocks
submission (`make bib-guard`) and is not fixable from this environment
(`CURRENT_STACK_BLOCKERS.md` B6-6).

**Manuscript change.** None to the argument. The **bibliography must be
verified before submission**, full stop.

### 2.2 "Naive Bayes with a skip-gate is a straw man. No serious diagnostic
system does this."

**Claim challenged:** the generality of the result.

**Best criticism.** A residual-generator/structural-analysis FDI design would
never treat an unavailable residual as absent evidence; it would mark the
fault set unisolable. The paper may be documenting one implementation's
mistake.

**Evidence response.** Partly conceded, and it is the strongest objection in
this document. The response is that the implementation is *deployed*, that the
mistake is a natural one (a gate that skips is the obvious way to implement
"not applicable"), and that the paper's product is a **checkable design rule**
plus a **one-line repair with its full measured cost** — which only makes
sense if the mistake is one someone would make.

**Remaining weakness.** n = 1 implementation. The paper cannot claim the class
of systems that share the defect is large, and it does not.

**Manuscript change.** State that the finding is about one deployed layer and
that the design rule is offered as a check, not as evidence of prevalence.

### 2.3 "Your CUSUM comparison is unfair to the trust path."

**Claim challenged:** `SC-09`.

**Best criticism.** The CUSUM alarms on a raw residual; the trust coefficient
is a smoothed, forgetting-weighted quantity feeding a dwell-timed state
machine. Comparing their first-crossing times compares a detector against a
detector-plus-policy.

**Evidence response.** Correct, and the artifact reports both alongside the
two λ series precisely so the reader can see which is which. The `dwell_up`
of 1.0 s is part of the trust path's latency by design.

**Remaining weakness.** The paper does not decompose the trust latency into
detector time plus dwell time. It could and should.

**Manuscript change.** Report `trust_latency − dwell_up` as well, or state
plainly that the trust figure includes policy dwell.

---

## REVIEWER 3 — statistical

### 3.1 "You call `p = 0.9767` a trust coefficient and `p_nominal = 1.0` a
posterior. Neither is a probability of anything."

**Claim challenged:** the interpretation of every reported scalar.

**Best criticism.** The trust coefficient is a Beta-recursion state under
adaptive forgetting, not a calibrated probability. The diagnosis posterior is
a tempered softmax over EW-smoothed pseudo-log-likelihoods with an
`EVIDENCE_MULT` of 1.5. Calling either one a probability invites a reader to
do arithmetic that is not licensed.

**Evidence response.** The paper does not calibrate them and does not claim
they are calibrated. **The word "confidence" is not used for the posterior
anywhere**, and a test enforces that. The mathematical results (P1–P6) are
invariant to the tempering: `EVIDENCE_MULT` scales `log q` for every
hypothesis, so P2's decomposition and P3's pinning are unaffected.

**Remaining weakness.** The scalars are still reported to four decimal places,
which implies a precision the construction does not have.

**Manuscript change.** Add one sentence saying these are model states, not
calibrated probabilities, and that no calibration is claimed. Consider fewer
significant figures.

### 3.2 "20,000 random instances is not a proof."

**Claim challenged:** the verification of P1–P6.

**Best criticism.** A numeric sweep over a Dirichlet-and-lognormal instance
family can miss a failure mode the family does not generate.

**Evidence response.** The numeric pass is a **regression test**, not the
proof. Every identity is proved in one line in `FORMAL_CORE.md` and verified
**symbolically** with sympy for `n = 4` (`simplify(lhs − rhs) == 0`, exact).
The numeric pass exists because sympy is not a CI dependency.

**Remaining weakness.** The symbolic check is at `n = 4`, not for general `n`.
The hand proofs are general; the machine check is not.

**Manuscript change.** State the symbolic check's arity. Do not let a reader
infer a general-`n` machine verification.

### 3.3 "P4 is stated as if it characterised argmax stability."

**Claim challenged:** P4.

**Best criticism.** `Δ > R ⇒ argmax p = argmax q` is sufficient only. A reader
who takes it as a criterion will over-trust the MAP whenever the condition
fails.

**Evidence response.** The audit reports **6,877 instances where the argmax
moved while the condition did not hold**, specifically so this cannot be
misread, and `FORMAL_CORE.md` §7 says "sufficient, not necessary" in bold.

**Remaining weakness.** None identified for this objection; the counterexample
count is the answer.

**Manuscript change.** Carry the 2,721 / 6,877 split into the paper, not just
the proposition.

---

## REVIEWER 4 — hostile on novelty

### 4.1 "Strip the aircraft and this is self-normalised importance weighting."

**Claim challenged:** the mathematical paper's contribution.

**Best criticism.** `p_h = q_h w_h / E_q[w]`, `KL(q‖p) = Jensen gap of log w`,
`|Δ log ratio| ≤ log(w_max/w_min)`. These are textbook. The novelty claim
is a re-labelling.

**Evidence response.** **Conceded, in writing, before the objection was
raised.** `PRIOR_ART_MATRIX.csv` labels P1/P5 `CANDIDATE_UNVERIFIED` against
self-normalised importance weighting and P4 against standard argmax-stability;
`NOVELTY_AUDIT.md` forbids the phrases "new information theory", "first
posterior-reweighting theorem", "novel KL bound" and "new Bayesian identity".
The allowed contribution language is the exact runtime-diagnostic formulation,
the structural-support interpretation, and the implemented counterexample.

**Remaining weakness.** Whether "the runtime formulation" is enough for a
venue is an editorial judgement the authors cannot make for the editor. It may
not be.

**Manuscript change.** None. The novelty language is already constrained by
`NOVELTY_AUDIT.md`, and a test enforces the forbidden phrases.

### 4.2 "C2 is coarsening at random. Heitjan and Rubin, 1991."

**Claim challenged:** C2, the exogeneity result.

**Best criticism.** The ignorability condition for a coarsening mechanism is
exactly this, and it has been known for thirty-five years.

**Evidence response.** **Found by this project's own prior-art search and
recorded as a conflict** (`PRIOR_ART_MATRIX.csv` row 1, `subsumes = LIKELY
YES`). `FORMAL_CORE.md` §5 says C2 must be labelled **KNOWN** and must cite
Heitjan & Rubin. The candidate contribution is narrowed to the *runtime*
reading: the coarsening mechanism here is a designed software component whose
non-ignorability is statically checkable from a signature table.

**Remaining weakness.** The Heitjan & Rubin entry is `CANDIDATE_UNVERIFIED` —
it came from a web search, not a publisher record, because egress blocks every
publisher route from here. Until a human verifies it, even the concession is
unverified.

**Manuscript change.** Cite it, label C2 KNOWN, and narrow the contribution
sentence to the runtime reading. **Verify the citation first.**

### 4.3 "You claim a 'Rukhin bound' you cannot produce."

**Claim challenged:** any sharpness claim for P6.

**Best criticism.** The brief names Rukhin-type bounded-likelihood-ratio
results as required reading. If the paper cannot locate them it cannot claim
its bounds are not already sharper elsewhere.

**Evidence response.** A search did not return a confirmable reference.
`PRIOR_ART_MATRIX.csv` row `PA-08` carries status `NOT_FOUND_NEEDS_HUMAN`, and
`FORMAL_CORE.md` §9 states explicitly that **no sharpness is claimed** for
P6a or P6b and that the reference must not be cited until located.

**Remaining weakness.** An unlocated reference is an open hole in the
prior-art coverage, and the paper is weaker for it.

**Manuscript change.** None yet. The hole is recorded; a human must close it.

---

## Objections with no adequate answer

Listed separately so they are not lost among the ones that were answered.

| # | objection | why it is not answered |
|---|---|---|
| 2.2 | naive Bayes with a skip-gate may be a straw man | n = 1 implementation; prevalence is not shown and cannot be |
| 1.2 | no operational harm is demonstrated | no data exists; not claimable |
| 4.3 | the named bounded-likelihood-ratio prior art was not located | egress-blocked; needs a human |
| — | every bibliography entry is unverified | egress-blocked; **blocks submission** |
