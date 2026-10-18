# MECHANISM A — VALIDITY GATING CAN REMOVE THE DISCRIMINATING EVIDENCE

Brief B2, B3. Claims `SC-02` … `SC-06` in `CLAIMS.csv`.

> **Validity/freshness gating can remove the discriminating evidence between
> diagnostic hypotheses.**

---

## 1. The mechanism, in closed form

CSIA's diagnosis is naive Bayes over a feature vector. Per tick, per
hypothesis `h`:

    ll_h  =  Σ_j  g_j · [ lo_j  if j ∈ LOW(h)  else  hi_j ]

with `lo_j = log(1 − c_j + ε)`, `hi_j = log(c_j + ε)`, `g_j` the feature's
gate, and `LOW(h)` the features hypothesis `h` drives low
(`csia/diagnosis/bayes.py` `CAUSES`). For any two hypotheses:

    ll_a − ll_b  =  Σ_j  g_j · (lo_j − hi_j) · ( 1[j ∈ LOW(a)] − 1[j ∈ LOW(b)] )

Every feature in **both** `LOW` sets, or in **neither**, contributes exactly
zero — identically, for every value of `c_j`. So the pair can only be
separated by features in the symmetric difference

    D(a,b)  =  ( LOW(a) △ LOW(b) )  ∩  ACTIVE,    ACTIVE = { j : g_j > 0 }.

When `D(a,b) = ∅` the instantaneous difference is zero, the EW smoother is
linear so the smoothed difference is zero, and the score difference reduces to
the log prior ratio:

    log(p_a / p_b)  =  log(π_a / π_b)      exactly, at every tick.

The pair is not weakly separated. It is **pinned**, and no further evidence of
this kind can move it. The formal statement is **P7c** in
`research/math-paper/FORMAL_CORE.md` §9a — *every distinguishing feature gated
⇒ pinned to the prior* — verified to 1.776 × 10⁻¹⁵ numerically.

**This document used to cite P3, and P3 is the wrong pointer.** P3 assumes
`L_a = L_b` **and** `w_a = w_b`. Measured against the full evidence the layer
could in principle have scored, the implemented case satisfies **neither**:
the withheld feature contributes differently to the two hypotheses, so
`L_a ≠ L_b` and `w_a ≠ w_b`, and the ratio is pinned because the two
inequalities cancel exactly. P7c reaches the same conclusion from the gate
condition, which is the thing this document actually measures. The correction
is recorded in `research/math-paper/REVIEWER_RED_TEAM_MATH.md` §4.2; **no
number in this document changes.**

**Gating causes this by shrinking `ACTIVE`.** `D(a,b)` can be non-empty at one
tick and empty at the next with no change to the model, purely because a gate
closed.

## 2. The pair this matters for

`nominal` has `LOW = ∅`. `gps_fault` has `LOW = {phys_gps}`. So

    D(nominal, gps_fault) = {phys_gps} ∩ ACTIVE

and the pair is distinguishable **exactly when the GPS physics feature is
active** and pinned otherwise. `phys_gps`'s gate is
`gvalid · (t > 3.0)` (`csia/prediction/comparator.py`): it closes when the
receiver reports no valid fix.

**A fault that removes the GNSS fix therefore removes the only evidence that
could name it.** That is the self-occlusion result.

## 3. Measured, by a checker that cannot see the answer

`research/systems-paper/independent_checker.py` evaluates `D(a,b)` for all 28
unordered pairs at every tick of nine scenarios. It imports **no** `csia`
module and **no** part of the support-aware implementation
(`engineering/v1_1/support/`). Its only inputs are the committed signature
matrix and an active-set export that carries no leader, no posterior and no
support label. A test runs it in a fresh interpreter and asserts `sys.modules`
contains neither.

| scenario | ticks | ticks with `D(nominal, gps_fault) = ∅` | fraction |
|---|---|---|---|
| CLEAN | 1500 | 76 | 5.1% |
| DUAL_IMU_AMBIGUITY | 1500 | 76 | 5.1% |
| GNSS_BIAS_RAMP | 1500 | 76 | 5.1% |
| **GNSS_FIX_LOSS** | 1500 | **276** | **18.4%** |
| HIGH_SPEED_ENVELOPE | 1500 | 76 | 5.1% |
| IMU_BIAS | 1500 | 76 | 5.1% |
| MAG_DEGRADED | 1500 | 76 | 5.1% |
| POWER | 1500 | 76 | 5.1% |
| VIBRATION | 1500 | 76 | 5.1% |

Two windows, and they are different in kind:

- **Ticks 0–75, every scenario including clean.** The GPS physics gate is
  closed during the smoother warm-up by construction (`t > 3.0`). The pair is
  pinned to the prior for 76 ticks of every flight, fault or no fault. This is
  a startup property, not a fault, and the failsafe is not armed for the first
  10 s anyway (`FailsafeConfig.arm_time`).
- **Ticks 625–824, GNSS_FIX_LOSS only.** 200 ticks = 8.0 s at 25 Hz = exactly
  the injected fix-loss window. The pair is pinned for the whole of it.

**`gps_fault|nominal` is the only pair in this catalogue that ever collapses.**
All 28 were evaluated; 27 never do.

## 4. Agreement with production: 378,000 / 378,000

`research/systems-paper/results/checker_agreement.json`.

| | |
|---|---|
| comparisons | 9 scenarios × 1500 ticks × 28 pairs = **378,000** |
| agreements | **378,000** |
| real disagreements | **0** |
| degenerate-class cases | **0** (see below) |
| verdict | `CHECKER_AGREES_WITH_PRODUCTION` |

Production computes a **numeric** test (`|contribution difference| > τ` in
`engineering/v1_1/support/decompose.py`); the checker computes a **structural**
one (set symmetric difference). They are not the same definition, and there is
exactly one way they can differ: `lo_j = hi_j` when `c_j = 0.5`, making a
structurally distinguishing term contribute zero numerically. That class was
predicted before the comparison was run, is counted separately, and **occurred
zero times** in this corpus. It is reported as a known disagreement class that
was not observed, not folded into the agreement count.

## 4b. A negative control on real current-stack data

`research/systems-paper/results/current_stack_structural.json`, claim `SC-26`.

The predicate above was run over **15,595 ticks from 20 real ArduPilot 4.8
SITL trials** — the per-trial tick logs of the preregistered Mechanism B
campaign (`research/v1_1/CURRENT_STACK_REPLICATION.md`). That campaign's
validity criterion was that the **fix never dropped**: `gvalid = 1.0` on every
scored tick.

| condition | trials | ticks | gate-closed ticks | pair collapsed |
|---|---|---|---|---|
| CLEAN | 5 | 5,100 | 0 | **0** |
| RAMP | 5 | 887 | 0 | **0** |
| STEP | 10 | 9,608 | 0 | **0** |
| **total** | **20** | **15,595** | **0** | **0** |

**The test was declared before the run and it is the direction that could have
falsified the account.** Under §1, the pair is distinguishable exactly when
`phys_gps` is active. On a fix-preserving trial the gate is open, so the
predicate *must* report "distinguishable" at every tick. **A single collapse
would have shown the structural account is wrong.** There are none in 15,595.

**This is a control, not a replication, and it is not presented as one.**
Self-occlusion requires a fault that **removes** the fix. These trials are
fix-preserving by construction and therefore *cannot* exhibit it; no fix-loss
arm exists on ArduPilot 4.8 in this repository and none was constructed. What
the run establishes is narrower and still worth having: the predicate has been
exercised against real current-stack traces rather than only against the bench
simulator, and it behaved as the theory requires.

## 5. Posterior is not confidence

At every tick of the pinned window, `p_nominal` is high and rising while
`D(nominal, gps_fault) = ∅`. Those two facts are consistent, and their
coexistence is the point:

- **posterior concentration** is a property of all hypotheses' scores and of
  the prior;
- **discriminating support** is a property of which terms are active.

C3 in `FORMAL_CORE.md` proves they can be arbitrarily far apart. The
implemented consequence is that `csia/v1_1/eligibility.py` fires
`SUPPORT_LOST_FOR_REQUIRED_INFORMATION` on a leader at 0.9998 with zero
discriminating evidence, **independently of freshness**, so removing the
freshness rule would not rescue it.

**The word "confidence" is not used for the posterior anywhere in the
manuscript.** A test enforces this (`tests/test_systems_paper_evidence.py`).

## 6. What Mechanism A does NOT claim

- **Not an observability claim.** Receiver observables detect GNSS denial
  well. The failure is one of evidence routing and applicability semantics.
- **Not blindness.** The failsafe still reaches CAUTION through an independent
  data-freshness disjunct and reconfigures navigation. It cannot name the
  cause.
- **Not a claim about all faults.** It is specific to faults that remove the
  fix. A retained-fix glitch does not close the gate at all — a scope
  correction the project's own campaign forced, and one the abstract reports
  rather than buries.
- **Not a claim about all flights.** Nine bench scenarios and one WP-C4
  injection campaign. The bench catalogue and the WP-C4 arms are *different
  experiments* and their numbers must not be conflated: the 200-tick window
  above is `csia/scenarios.py`'s `gps_dropout`, not WP-C4's arm B.

## 7. Reproduce

```
python research/systems-paper/export_active_sets.py
python research/systems-paper/independent_checker.py
python research/systems-paper/compare_checker_vs_production.py
```

Deterministic. The exporter's output is committed with its SHA-256 in the
artifact header, and `tests/test_systems_paper_evidence.py` re-runs the
checker and the comparison in CI.

## 8. Status against the brief's B2

The brief asks for a from-scratch reconstruction on the **current** ArduPilot
stack, and on PX4 where the route is valid, recording per tick: freshness,
gate state, active relations, suppressed relations, leader, posterior,
discriminating-evidence count, identifiability, ambiguity and function
eligibility.

**What is done:** the structural half, on the frozen bench simulator, with an
independent checker and full agreement. Gate state, active relations,
suppressed relations and the discriminating-evidence count are all recorded
and independently re-derived.

**What is partly done:** §4b runs the predicate over 15,595 real ArduPilot 4.8
ticks as a negative control. Those tick logs live in `research/v1_1/`, which
the phase guard does **not** exclude, so they are citable by Paper I.

**What is NOT done, and why:** no fix-loss arm exists on ArduPilot 4.8 here, so
self-occlusion itself has not been reproduced on a current stack, and no PX4
SITL is available. The per-tick leader, posterior, ambiguity and function
eligibility that §B2 also asks for are not in those tick logs, which carry a
single gate column. See `CURRENT_STACK_BLOCKERS.md`. **No current-stack
replication was fabricated.**
