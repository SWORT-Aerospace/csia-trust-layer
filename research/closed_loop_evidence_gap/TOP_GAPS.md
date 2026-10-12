# Top gaps and decision

Closed-loop evidence gap search, 2026-09-28. Source ids `Lnnn` are defined in
`research/closed_loop_evidence_gap/PROBLEM_LANDSCAPE.md` §2. Candidate ids
`Pnn` are defined in `CANDIDATE_PROBLEMS.csv`.

## 1. Survival test

A candidate survives only if all five of the brief's conditions hold:

1. it is useful;
2. current systems genuinely fail at it;
3. the distinction is not terminology;
4. the solution is not a trivial application of known control or diagnosis
   theory;
5. it generalises beyond one XSYS-001 witness.

| id | short name | 1 | 2 | 3 | 4 | 5 | classification |
|---|---|---|---|---|---|---|---|
| P01 | feedback masking of physical faults | YES | PARTIAL | YES | NO | YES | KILLED |
| P02 | invalidation of evidence relations by compensating actions not tracked | YES | PARTIAL | YES | NO | YES | ENGINEERING_ONLY |
| P03 | validity indexed by time instead of action history | YES | PARTIAL | YES | NO | YES | KILLED |
| P04 | monitor does not model its own intervention's evidential effect | YES | PARTIAL | YES | PARTIAL | YES | OPEN_BUT_CROWDED |
| P05 | estimator interventions change downstream evidence semantics | YES | PARTIAL | YES | NO | YES | ENGINEERING_ONLY |
| P06 | safety actions reduce diagnosability unnoticed | YES | PARTIAL | YES | NO | YES | OPEN_BUT_CROWDED |
| P07 | symptom suppression creates false exoneration | YES | PARTIAL | YES | NO | YES | KILLED |
| P08 | no action provenance on evidence | YES | PARTIAL | PARTIAL | NO | YES | ENGINEERING_ONLY |
| P09 | in-service assurance evidence confounded by own interventions | PARTIAL | UNCLEAR | YES | NO | YES | OPEN_BUT_CROWDED |
| P10 | adaptation absorbs faults; excitation lost | YES | PARTIAL | YES | NO | YES | KILLED |
| P11 | runtime-assurance switching biases later data | PARTIAL | UNCLEAR | YES | NO | YES | OPEN_BUT_CROWDED |
| P12 | monitor semantics not invariant to policy | YES | PARTIAL | YES | NO | YES | KILLED |
| P13 | no unified cross-domain theory | PARTIAL | NO | NO | NO | YES | KILLED |

**No candidate passes all five conditions, so no candidate is classified
POTENTIAL_GAP.**

- **Condition 4 is the one that fails.** In every case, the solution is an
  application of theory that already exists:
  - integrated control and diagnosis;
  - mode-dependent residuals;
  - active diagnosis;
  - navigation integrity;
  - causal inference.
- **Condition 2 is PARTIAL throughout.**
  - Fielded modular stacks do fail in places (V4: L066, L068).
  - Research systems and the relevant standards do not.

## 2. Scores

Scoring covers the seven candidates that were not killed. They are scored so
that the choice between ENGINEERING_ONLY and NO_GAP rests on stated
usefulness. **None is a survivor under §1.** Each score of 4 or more cites
evidence in `CANDIDATE_PROBLEMS.csv`.

| id | classification | importance | unsolvedness | depth | generality | aerospace | commercial | testability | embedded | SWORT fit | defensibility | total /50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P02 | ENGINEERING_ONLY | 4 | 2 | 2 | 3 | 4 | 3 | 4 | 4 | 4 | 1 | 31 |
| P05 | ENGINEERING_ONLY | 4 | 2 | 2 | 3 | 4 | 3 | 3 | 4 | 3 | 1 | 29 |
| P06 | OPEN_BUT_CROWDED | 3 | 2 | 4 | 3 | 4 | 2 | 4 | 2 | 3 | 1 | 28 |
| P08 | ENGINEERING_ONLY | 3 | 2 | 1 | 4 | 3 | 3 | 3 | 4 | 3 | 1 | 27 |
| P09 | OPEN_BUT_CROWDED | 3 | 3 | 4 | 4 | 2 | 3 | 2 | 3 | 1 | 2 | 27 |
| P04 | OPEN_BUT_CROWDED | 3 | 2 | 4 | 4 | 3 | 2 | 3 | 2 | 2 | 1 | 26 |
| P11 | OPEN_BUT_CROWDED | 2 | 2 | 3 | 3 | 3 | 2 | 3 | 3 | 2 | 1 | 24 |

- **Prior-art defensibility is 1 or 2 everywhere.** Every candidate has
  direct prior art at problem level.
- **Unsolvedness never exceeds 3.** P09 reaches 3 only because no aerospace
  instance was found. Its formal problem is established (L022, L023, L026,
  L027).

## 3. Decision rule (stated before applying it)

The three outcomes are named below in words. The decision token appears only
on the last line of this file.

- **Gap found** requires at least one candidate that:
  - is classified POTENTIAL_GAP;
  - passes all five survival conditions;
  - scores at least 30/50;
  - has real-world importance of at least 4, unsolvedness of at least 3,
    aerospace relevance of at least 4 and prior-art defensibility of at
    least 3.
- **Otherwise, engineering only** requires at least one candidate classified
  ENGINEERING_ONLY with real-world importance of at least 3. That is, a
  useful engineering residue exists.
- **Otherwise, no gap.**

**Applied.**

- No candidate is POTENTIAL_GAP, so there is no gap.
- P02 (importance 4), P05 (4) and P08 (3) are ENGINEERING_ONLY with
  importance of at least 3.
- The rule therefore yields the engineering outcome.

## 4. The strongest remaining candidates

None survives. The three highest-scoring candidates are recorded in full so
that the engineering residue and the crowded research frontier are explicit.

## P02: invalidation of evidence relations by compensating actions not tracked

**Exact problem.** After a compensating or reconfiguring action, a runtime
monitor keeps applying evidence relations that the action has invalidated.
Examples of such actions:

- a gain change;
- an allocation change;
- motor removal;
- a mode change.

**Why current systems fail.** In the fielded files read:

- the ArduCopter vibration check removes its compensation using the same
  detector evaluated under the compensated controller (L066);
- the PX4 imbalance metric carries filter state across an estimator switch
  (L068).

XSYS-001 measured the size of the error when a relation is used after
compensation: 55/55 wrong (L069).

**Closest prior art.**

- mode-dependent and mode-sequence ARRs (L017);
- command-conditioned mode identification, flown on DS1 (L012);
- action-conditioned model monitors (L035);
- mode-scoped requirement monitors (L037);
- integration issues in active FTC (L004).

**What is actually missing.** A convention in modular stacks by which each
intervention is published as a mode, and each monitor declares its validity
per mode. This is an interface and discipline problem, not a method.

**Who needs it.** Autopilot developers (PX4, ArduPilot) and integrators of
UAS autonomy with several monitors.

**Why they would care.** Masked or misread evidence after compensation is
the mechanism behind the autopilot-masking upsets (L057, L059).

**Why it is scientifically hard.** It is not. The theory is established
(L012, L017, L035). The work is integration.

**Smallest falsifiable question.** Engineering form:

- **Setup.** In a PX4 SIH closed loop, replay the XSYS-001 matched set.
- **Condition.** Scope the dynamics witness's validity by a published
  "compensation active" mode, instead of by a time window.
- **Test.** Does this remove all 55 wrong attributions without adding wrong
  attributions in the other arms?

A single new wrong attribution falsifies it. This is a test of an engineering
change, not a research question.

**Why SWORT has an advantage.** It has the XSYS-001 apparatus and matched-set
data (L069, L070). That is a testing advantage, not a methodological one.

**What would kill the direction.** A fielded PX4 or ArduPilot mechanism that
already scopes every monitor by intervention mode. Only a few files were read
(L063-L068), so this is not excluded.

## P05: estimator interventions change downstream evidence semantics

**Exact problem.** Monitors and assurance arguments that consume an estimator
output are not told of, and have no validity rule for:

- resets;
- exclusions;
- lane switches;
- covariance adaptation;
- re-classification;
- validity holds.

**Why current systems fail.** Incidents: MH124 (L055), QF72 (L061), Uber ATG
(L056) and SOHO (L054). In the fielded code read, reset provenance reaches
controllers (L063-L065) but not every monitor (L068).

**Closest prior art.**

- ARAIM protection levels after exclusion (L040);
- Kalman-filter integrity with residual history (L041);
- fielded reset counters, lane-switch reset data and switch hold-off (L063,
  L064, L065).

**What is actually missing.** A system-wide rule that every consumer of an
estimator output is notified of each estimator action, with a validity rule
per consumer. Navigation-grade mathematics exists for exclusion. Covariance
adaptation and reset transients are UNCLEAR (L042, L075).

**Who needs it.** Navigation and perception integrators; certification of
UAS navigation.

**Why they would care.** Every incident above was fixed locally after the
fact.

**Why it is scientifically hard.** For navigation it is largely solved
(L040, L041). The remaining work is breadth of integration.

**Smallest falsifiable question.** Engineering form:

- **Setup.** In PX4 SITL, force estimator lane switches while the vehicle is
  healthy.
- **Measure.** Count how often the imbalance metric (L068) crosses its
  threshold within its filter time constant after a switch.
- **Compare.** Count the same crossings with the filter reset on each switch.

A count of zero in both cases falsifies the need.

**Why SWORT has an advantage.** It already runs PX4 SIH with a patched
effectiveness model. It has no navigation-integrity advantage.

**What would kill the direction.** PX4 or ArduPilot code, beyond the files
read, that already resets or scopes monitors on every estimator action.

## P06: safety actions reduce diagnosability unnoticed

**Exact problem.** A planner or controller chooses a safe action that removes
the excitation separating competing fault hypotheses. The assurance layer
then reads the persisting ambiguity as health.

**Why current systems fail.**

- Threshold witnesses read against closed-loop envelopes exonerate when the
  response is nominal (L069, L070).
- Planners tend to move into unobservable subspaces (L018).

**Closest prior art.**

- s-FEAST (L009), with actuator-plus-sensor faults under probabilistic safety
  constraints;
- safe real-time active model discrimination for quadrotor and fighter-jet
  models in under 50 ms (L008);
- safety-constrained guaranteed input design (L007);
- safe diagnosability (L010);
- unified active detection and control (L006).

**What is actually missing.** Passive accounting when another module chose
the action. Any likelihood-based or set-based diagnoser does this by
construction. The open part is scale and speed, which L008 and L009 already
address.

**Who needs it.** Autonomous aircraft that restrict manoeuvres after a
suspected fault.

**Why they would care.** Safer but less diagnosable flight can end in a wrong
return or abort decision.

**Why it is scientifically hard.** Real-time separability for
high-dimensional nonlinear systems with model uncertainty. This is hard, and
it is being worked on (L008, L009).

**Smallest falsifiable question.** Conditional, not pursued:

- **Setup.** The XSYS-001 matched set.
- **Question.** Does a diagnoser that evaluates both hypotheses under the
  executed commands avoid the 55 late-window errors that the closed-loop
  envelope witness made?
- **Falsified if** it also errs.

**Why SWORT has an advantage.** It has the matched-set apparatus (L069,
L070). It has none on method: s-FEAST code is public (L009).

**What would kill the direction.** It is already killed as a research
direction by L008 and L009, pending full-text checks (`FULLTEXT_VERIFICATION_QUEUE.md`).

## 5. Does existing CSIA provide a meaningful starting advantage?

This question is asked only after scoring, as the brief requires.

**No.**

- **Every candidate is stated and resolved without CSIA.** Where they
  resolve, they do so by:
  - control and diagnosis theory (L003, L006, L017);
  - navigation integrity (L040);
  - formal runtime monitors (L035, L037);
  - causal inference (L022).
- **Windowed witnesses and "not measurable" add nothing necessary.** CSIA's
  existing notions, the XSYS-001 windowed witnesses and the three-valued
  "not measurable" predicate, express time-limited validity. The searched
  literature already expresses validity conditioned on modes and actions
  (L012, L017, L035, L037), which is more general.
- **The only asset is a test bed, not a starting advantage.** The XSYS-001
  apparatus and matched-set data (L069, L070) could test the P02 and P06
  engineering questions.
- **Describing the residue as CSIA evidence would be branding.** The P02 and
  P05 residue belongs in the flight stack's monitor interfaces.

## 6. XSYS-001: example or unique evidence?

**It is an example.**

- It is a clean, preregistered, blinded quantification (55/55) of classic
  closed-loop masking. The dynamics witness was read against a closed-loop
  envelope (L070), and the compensation witness was a controller-output
  observation (L070).
- **It does not show action-history dependence.** The controller was fixed
  and the window was indexed by time (L069).
- **It does not compare** with an input-conditioned plant residual or any
  external diagnoser.
- **It is not hardware evidence.**

**Decision:** `CLOSED_LOOP_EVIDENCE_ENGINEERING_ONLY`
