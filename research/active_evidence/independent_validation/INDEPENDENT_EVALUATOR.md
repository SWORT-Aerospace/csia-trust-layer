# The Independent Outcome Evaluator

**Research only. Post-freeze. Quarantined. Simulator.**

## 1. Why the prior metric could not do this job

The locked campaign scored itself with

```
M_R^cert = |ΔR_target| − (|B_total| + U_R)
```

Every term on the right is computed from the realized current and the declared
uncertainty envelope. None of them reads the plant's voltage response. The
consequence is measurable and it is total: across the 2012 cells where all
three plants produced a margin, `M_R^cert` is **bit-identical** — not close,
not equal to twelve decimal places, identical in every bit
(`tests/test_iv_provenance.py::test_certificate_margin_is_bit_identical_across_plants`).

So the campaign's plant comparison was not weak, it was empty, and its
withdrawal was correct. The same structure explains the second finding: the
campaign's false-certificate check asked whether a `CERTIFIED_IN_MODEL` row had
`M_R^cert < 0`, but `certify()` issues `CERTIFIED_IN_MODEL` only on the branch
where `M_R^cert > 0`. Zero false certificates was a restatement of an `if`.

A certificate margin is a statement about whether the method *believes* it can
resolve a change. Whether it *did* is a different question and needs a
different instrument.

## 2. What the evaluator computes

`csia_independent_validation/evaluator.py`, Layer B, offline, with access to
simulator truth.

Point estimates, against the resistance the plant actually ran with:

```
e_R  = R̂₀ − R₀,true
AE_R = |e_R|
RE_R = |e_R| / max(|R₀,true|, 1e-9)
```

Change estimates, across a matched nominal/fault pair driven by common random
numbers:

```
e_ΔR    = (R̂_fault − R̂_nominal) − (R_fault − R_nominal)
M_R^out = τ_R(d) − |e_ΔR|
```

Interval and set estimates: truth coverage, width, nominal/fault separation
(positive only when the two sets are disjoint), false exclusion of the true
hypothesis, simultaneous coverage when a family claims it, and calibration
stratified by plant and by nuisance level.

`resolved` is `M_R^out > 0`, strictly. A margin of exactly zero is not
resolved; ties go against the claim. The predicate is reported with every
number, because the prior phase's frontier table was read as a certification
claim when it was a margin claim (`COUNTEREXAMPLE_LOG.md` IV-2).

## 3. τ_R, and what it is not

`τ_R(d) = 0.5·d` is the primary accuracy requirement, preregistered in §2 of
`PREREGISTRATION.md` before any outcome was produced.

The justification is internal to the experiment and nothing else: the magnitude
grid is spaced by roughly a factor of two, so an error of half the claimed
change is the loosest requirement under which the estimate still carries the
right sign and cannot be confused with the neighbouring grid point. A secondary
absolute form, `τ_R = 0.002` ohm — the smallest magnitude on the grid — is
reported alongside.

**τ_R is not an application requirement.** There is no application here. There
is no airframe, no duty cycle, no dispatch decision and no hardware. Presenting
τ_R as an engineering tolerance would be inventing a number, and this document
says so in the place where a reader would otherwise assume it.

## 4. Independence, and how it is enforced

The evaluator must not reuse the certificate's error budget. If it did, a
certificate that is confidently wrong would be scored by the same confidence
that made it wrong.

Enforcement is structural rather than by convention:

* `csia_independent_validation/audit.py` parses the import graph statically. A
  runtime check only fails on paths a test happens to exercise; an AST walk
  fails on paths nobody has written yet.
* Layer A's transitive closure is 28 local modules, all inside
  `csia_active_evidence`, and contains none of `truth`, `plants`, `evaluator`
  or `ceilings`.
* The evaluator's own imports are exactly `csia_independent_validation.truth`.
  It imports nothing from `csia_active_evidence` at all, so it cannot call
  `rcec`'s resolution-margin computation even by accident.
* Truth-bearing modules are discovered by reading the source for a
  `TRUTH_BEARING = True` declaration, so a module becomes protected when it
  declares itself, not when somebody remembers to add it to a list.
* Leaks through the *data schema* are checked separately: the Layer A
  `Observation` is pinned to exactly seven field names, and a field name
  containing `true`, `fault`, `label`, `hidden`, `actual`, `oracle` or `gt_`
  fails the guard.

Every one of these guards has a positive control in the same test file. The
leak checker is pointed at a module that genuinely does import truth and must
fire; the schema checker is handed seven planted field names and must catch
each one. A guard that has never caught anything is not evidence.

## 5. Detectors for a broken experiment

| detector | fires when | negative control |
|---|---|---|
| `detect_leakage` | the estimate equals truth to 1e-12 across every cell | an estimator off by 1e-4 is not flagged |
| `is_degenerate_nominal` | the estimated change is zero everywhere | an estimator recovering 90% of the change is not flagged |
| `false_certificates` | a cell is `CERTIFIED_IN_MODEL` and `M_R^out ≤ 0` | a sound run returns an empty list; non-certified states are never counted |
| `calibration_by_state` | `resolved_fraction` below `COVERAGE_TARGET` for a state | reports `n` per state and refuses mismatched lengths |

`detect_leakage` deliberately returns `False` below three cells. Two exact hits
is a coincidence, not evidence, and a detector that fires on coincidences gets
switched off by the people who have to read it.

## 6. Censoring-aware statistics

`grid_resolution_area` (`A_s`), `drift_interaction` (`I_s`) and
`censored_frontier` live here rather than in the runner so that they are
testable in isolation.

`drift_interaction` **raises** on any input that is not a probability in
`[0, 1]`. That is the direct fix for the prior phase's preregistered
interaction scalar, which encoded "never resolves" as `float("inf")` and then
did arithmetic on it, producing `NaN`. `censored_frontier` returns the string
`"> 0.04"` rather than a float when nothing on the grid reaches the target, so
the value cannot be fed into arithmetic by accident.

## 7. What this evaluator still cannot tell you

It scores estimates against **simulator** truth. It says nothing about any real
pack, any chemistry, or any hardware. A perfect `M_R^out` here means the
estimator recovered a number that this code put in, which is a necessary
condition for the method being any good and nowhere near a sufficient one.

It also cannot, by itself, distinguish "the estimator is good" from "the plant
is easy". That is what Q0, Q1 and Q2 and the P7b ceiling are for.
