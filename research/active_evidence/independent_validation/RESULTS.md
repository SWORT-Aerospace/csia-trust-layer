# Results — RCEC Independent Validation

**RESEARCH ONLY. POST-FREEZE. QUARANTINED. SIMULATOR.**
Not a certified safety artifact. Not airworthy. Not production-ready. Synthetic
pack, no chemistry claimed, no hardware representativeness implied. Novelty
status `NOVELTY_UNRESOLVED`; the closest named source could not be retrieved.

**Primary evidence: the sealed final partition**,
`results/CAMPAIGN_FINAL.json` — 69 120 rows, 196 045 plant runs, 6674 s, 40
hash-derived seeds opened exactly once under the conditions recorded in
`SEAL_OPENING_RECORD.md`. Validation (`CAMPAIGN_VALIDATION.json`, 41 472 rows,
24 seeds) ran the same frozen design first and is quoted where the two are
worth comparing; **every finding below reproduces across both**.

Every number is computed by a committed tool, not transcribed by hand.

---

## 1. Verdict

**`SUPPORTED_WITH_NARROW_SCOPE`** on the central question, with three
preregistered hypotheses rejected and one preregistered claim rejected.

The strongest defensible sentence:

> Within a declared simulator envelope, on 1440 matched sealed-partition
> cells, the compensated active probe P2 achieved a lower independent point
> error than the ordinary mission manoeuvre in 1440/1440 cells, passive hover
> in 1439/1440, random-safe excitation in 1346/1440 and the naive palindrome in
> 1399/1440; and every one of the 3925 inferences accepted by the
> realized-telemetry certificate was correct against simulator truth — zero
> false certificates, one-sided 95% upper bound 1.5e-3 on 2009 distinct
> experiments — at a coverage cost of 81.8%.

---

## 2. Did the independent evaluator preserve or reverse the advantage?

**Preserved on the point metric. Dissolved on the preregistered change metric,
for a derivable reason.**

`A_s`, grid resolution area, nominal drift:

| arm | `A_s` point | frontier | mean energy | median `AE_R` |
|---|---|---|---|---|
| P0 passive | 0.017 | `> 0.04` | 0 A·s | 4.81e-2 Ω |
| P6 mission | 0.056 | `> 0.04` | 48.0 A·s | 7.66e-2 Ω |
| P7a benchmark | 0.681 | 0.010 | 80.0 A·s | 2.09e-3 Ω |
| P5 random-safe | 0.711 | 0.010 | 20.4 A·s | 2.55e-3 Ω |
| P3 shaped | 0.753 | 0.010 | 14.0 A·s | 1.82e-3 Ω |
| P7b change-oracle | 0.862 | 0.010 | 48.1 A·s | 8.10e-4 Ω |
| P4 feedback | 0.871 | 0.006 | 56.0 A·s | 1.54e-3 Ω |
| P1 palindromic | 1.000 | 0.002 | 50.9 A·s | 4.42e-4 Ω |
| **P2 compensated** | **1.000** | **0.002** | 71.3 A·s | **2.10e-4 Ω** |
| **P7b point-oracle** | **1.000** | **0.002** | 52.2 A·s | **4.25e-5 Ω** |

On the preregistered change metric every arm except P0 scores `A_s = 0.933`
identically. That is not a finding about the arms; it is
`PREREGISTRATION_AMENDMENT_2.md`, measured again at validation scale.

**Predicate, stated with the number:** point resolution is
`AE_R < 0.5·|ΔR_target|`; change resolution is `M_R^out > 0` with
`τ_R = 0.5·|ΔR_target|`. The prior phase's frontier table was read as a
certification claim when it was a margin claim, and this phase does not repeat
that.

---

## 3. Certificate calibration, and every false certificate

**Zero false certificates observed, on both metrics, out of 21 600
sealed-partition main-block cells. That is a count, not a rate, and the denominator matters more than the
zero.**

Unlike the prior phase's identical-sounding claim, this one comes from a check
that can be non-empty: `evaluator.false_certificates` compares a certified cell
against simulator truth, and a test constructs a case where it returns one.

### The denominator, and the bound

For zero observed failures in `N` independent trials the one-sided 95% upper
bound is approximately `3/N`. `N` is **not** the row count:

| denominator | `N` | 95% upper bound | |
|---|---|---|---|
| certified rows | 3925 | 7.64e-4 | inflated — see below |
| **distinct experiments** | **2009** | **1.49e-3** | **the honest count** |
| distinct seeds | 40 | 7.50e-2 | the most conservative reading |

Several arms choose the **same action in the same cell**, and when they do they
are one simulation counted several times — up to **seven** arms share a single
experiment here. Counting rows would halve the bound for free, and that is
exactly the sort of free tightening that should not be available.

Even 2009 assumes distinct simulations are independent, which they are not:
they share 40 seeds, one plant family, one command library and one declared
envelope. The true effective count lies between 2009 and 40 and this phase does
not claim to know where.

**So the defensible statement is: zero false certificates observed, with a 95%
upper bound of 1.5e-3 on the false-certificate rate under the most favourable
independence assumption this data supports.** Reaching a 1e-4 bound would need
roughly **15 times** more distinct experiments. `zero` alone is never a rate
claim (`results/ZERO_EVENT_BOUND_FINAL.json`).

**And the zero is the good kind, which is now a measured fact rather than an
argument.** `results/VACUITY_AUDIT_FINAL.json` classifies every declared check
in this phase: 12 `DISCRIMINATING`, 3 `SOUND_BUT_UNEXERCISED`, 1
`VACUOUS_IN_ENVELOPE`, 0 `UNVERIFIED`. The false-certificate checks are
`SOUND_BUT_UNEXERCISED` — constant on the data, with controls proving they can
fire. The prior phase's equivalent would have scored `VACUOUS_IN_ENVELOPE`.

| certificate state | n | resolved (point) | median `AE_R` | meets 90% target |
|---|---|---|---|---|
| `CERTIFIED_IN_MODEL` | 3925 | **1.0000** | 3.12e-4 Ω | **yes** |
| `UNKNOWN_OR_MODEL_MISMATCH` | 196 | 0.9898 | 7.51e-4 Ω | yes |
| `MODEL_MISMATCH_LIMITED` | 14469 | 0.8617 | 5.87e-4 Ω | no |
| `INSUFFICIENT_EXCITATION` | 2986 | 0.0794 | 4.25e-2 Ω | no |
| `DRIFT_COUPLED` | 24 | 0.0000 | 1.02e-2 Ω | no |

**H4 supported.** `CERTIFIED_IN_MODEL` predicts a correct estimate in 3925 of
3925 cells.

**And the certificate is markedly conservative.** It declined 14 469 cells as
model-mismatch-limited of which 86.2% would in fact have resolved, and 196 as
unknown of which 99.0% would have. That is roughly 12 660 correct inferences
refused. Soundness here is bought with a large amount of coverage, and a reader
deciding whether this is a good trade needs both numbers.

`DRIFT_COUPLED` is the cleanest refusal in the table: 24 cells, none of which
would have resolved.

---

## 4. Q0 / Q1 / Q2

**H5 supported on the point metric, and the change metric is blind, exactly as
derived before the run.**

| plant | n | median `AE_R` | `A_s` point | `A_s` change |
|---|---|---|---|---|
| Q0 zero-RC | 7200 | **2.94e-4 Ω** | 0.868 | 0.933 |
| Q1 one-RC | 7200 | **1.68e-3 Ω** | 0.741 | 0.933 |
| Q2 richer | 7200 | **1.37e-3 Ω** | 0.728 | 0.933 |

A **5.7-fold** spread on the point error, and three identical figures to three
decimal places on `A_s` change. The certificate margin
is bit-identical across plants in 48 of 48 development cells
(`PLANT_INDEPENDENCE_AUDIT.md` §3); the preregistered change metric is
effectively so; the point metric is not.

An independent classical baseline agrees: set-membership model invalidation
separates the three plants at 2.46, 4.90 and 7.31 sensor sigmas
(`BASELINE_MAPPING.md` §4).

---

## 5. Matched cost, and the ceiling

P1, P2, P4, P7a, P7b and the selectors are all in the **same declared energy
class** ("high"), so the comparison below is like-for-like by class, with the
actual spend shown because class alone hides a 40% difference.

Paired on matched cells, point error, P2 as the reference:

| comparison | matched cells | P2 better | median advantage |
|---|---|---|---|
| P2 vs P6 mission | 1440 | **1440 (100%)** | +7.28e-2 Ω |
| P2 vs P0 passive | 1440 | 1439 (99.9%) | +4.74e-2 Ω |
| P2 vs P5 random-safe | 1440 | 1346 (93.5%) | +2.43e-3 Ω |
| P2 vs P1 palindromic | 1440 | 1399 (97.2%) | +1.65e-4 Ω |
| P4 vs P1 palindromic | 1440 | **63 (4.4%)** | −9.46e-4 Ω |

**Gate E, honestly:** P2's advantage over P1 is real and it is bought. P2 spends
71.3 A·s against P1's 50.9 — 40% more energy for a 1.65e-4 Ω median improvement
and, on the sealed partition, no difference in `A_s` at all: both reach 1.000. Whether that is worth it is an application question this
phase cannot answer, and the numbers are given so somebody with an application
can.

**P4 loses to the naive palindrome in 95.6% of matched cells.**

### The ceiling

**Both invariants hold on development, validation and the sealed partition.**
1440 matched cells each on the sealed run, zero violations, on both losses. No
deployable arm beat either oracle on that oracle's own objective, anywhere.

`P7b_point_oracle` reaches `AE_R` of 4.25e-5 Ω at 52.2 A·s, against P2's
2.10e-4 Ω at 71.3 A·s. **A five-fold accuracy gap at 73% of the energy.** The
median regret of the best deployable arm against perfect hindsight is
**1.09e-4 Ω**; the worst deployable arm, P6, is at 7.29e-2 Ω.

`P7a` is never called an oracle, and its performance is the reason: `A_s` 0.681
at the full 80 A·s energy cap, worse than four deployable arms while spending
more than any of them. `BASELINE_MAPPING.md` §3 shows why — its objective is
exactly the classical A-optimal design for resistance, `var(R) = σ_V²/S_II`,
and the classical optimum for the *assumed* model is not optimal for the plant.

---

## 6. Robust selection: H3 rejected

| selector | `A_s` nominal | `A_s` elevated | worst-case | `I_s` |
|---|---|---|---|---|
| S0 always-P2 | 1.000 | 1.000 | **1.000** | −0.0056 |
| S1 always-P4 | 0.871 | 0.885 | 0.871 | +0.0083 |
| **S2 threshold** | 1.000 | **0.885** | 0.885 | **−0.1208** |
| S3 minimax | 1.000 | 1.000 | **1.000** | −0.0056 |

**H3 is rejected.** S2 does not match the worst case of committing globally to
P2; it is strictly worse. Its threshold switches to P4 under elevated drift,
which is exactly what the prior locked result motivated — and that result does
not reproduce here. P2 does **not** collapse under elevated drift in this
phase; it holds `A_s = 1.000`. So a selector built on the prior finding inherits
a premise that is false in this envelope and pays for it, at the worst
drift-interaction score of any arm.

S3 minimax ties S0 exactly. It never chooses P4, so it is a more expensive way
of always choosing P2.

**H2 is also rejected as stated.** The preregistered tradeoff was "P2 best
nominal, P4 better worst case". P4 is worse than P2 in both conditions.

**No selector ever abstained.** All three abstention paths are reachable and
tested, and none was reached in 69 120 rows — `SOUND_BUT_UNEXERCISED` in the
vacuity audit, not `VACUOUS`: the declared conditions never
made energy, headroom, lag knowledge or mission phase binding. Architecturally
present, empirically unexercised, and neither fact should be read as the other.

---

## 7. Finite drift interaction `I_s`

Primary statistic, point metric, difference in differences against passive:

| arm | `I_s` |
|---|---|
| P7a benchmark | +0.0917 |
| P6 mission | +0.0194 |
| P3 shaped | +0.0111 |
| P7b change-oracle / P7c | +0.0097 |
| P4 feedback / S1 | +0.0083 |
| P0 passive | 0.0000 |
| P1 / P2 / S0 / S3 / P7b-point | −0.0056 |
| P5 random-safe | −0.0931 |
| **S2 threshold** | **−0.1208** |

Every value is finite. The statistic this replaces went `NaN` the moment an arm
never resolved, because "never" was encoded as infinity
(`INTERACTION_METRIC.md` §1). `drift_interaction` now raises on any input that
is not a probability, so that failure cannot recur silently.

---

## 8. The two-gate contract: the combined claim is rejected

Full 2×2, point metric, **21 600 sealed-partition cells**:

| | post fails | post passes |
|---|---|---|
| pre fails | 9143 (3272 wrong) | **0** |
| pre passes | 8532 (1504 wrong) | 3925 (**0** wrong) |

| policy | accepted | coverage | false accepted | rate |
|---|---|---|---|---|
| accept always | 21 600 | 1.000 | 4776 | 0.2211 |
| accept if pre | 12 457 | 0.577 | 1504 | 0.1207 |
| accept if post | 3925 | 0.182 | **0** | 0.0000 |
| accept if both | 3925 | 0.182 | **0** | 0.0000 |

The `pre=False / post=True` cell is empty, so `accept_if_both` is identical to
`accept_if_post`. **The combined claim is rejected as preregistered**: both
gates beat the pre gate alone, and do not beat the post gate alone.

**Within this envelope the pre-action separation gate is redundant.** That is
one of the two negative outcomes `PREREGISTRATION_AMENDMENT_3.md` §4 named in
advance.

**Two caveats that must travel with this table.** The pre-gate's safety half
**cannot fail** for any admissible action — 34 A worst case against a 56 A limit
(`COUNTEREXAMPLE_LOG.md` IV-19) — so this says nothing about pre-action safety
screening. And the pre-gate is an interval over-approximation over an
enumerated envelope, **not a formal reachable-set guarantee**, on a one-output
battery model.

The volume surrogate's blind spot occurred in the data: **80 cells** on the
sealed partition (0.37%, the same rate as validation) were `zero_volume` and
not `empty_intersection` — touching, not separated.

**The pre-gate's safety half is `VACUOUS_IN_ENVELOPE`** in
`results/VACUITY_AUDIT_FINAL.json`, firing rate exactly 1.0000 — the audit
confirms mechanically what §IV-19 found by hand, and a test fails if a second
vacuous check ever appears.

---

## 9. Unknown-fault boundary and sensing

**Boundary δ\* = 3.363 σ.** Routing rate 0.901 above it over 426 trials, 0.000
below it over 870. The 0.10 V case sits at 1.461 σ, about one sigma above the
0.445 σ no-fault floor: its absorption is structural, not a classifier defect.
No threshold was lowered. One ringing family, not open-set coverage.
(`UNKNOWN_BOUNDARY.md`.)

**Sensing:** current gain error dominates at `J_q^out = −1.92e-2`. Four
parameters are exactly zero, each derived: voltage offset absorbed by the
intercept, current offset absorbed by the free intercept, voltage noise
cancelled by the paired design, timestamps never read by the estimator. Dropout
measured exactly zero until the harness was fixed to honour the dropout mask —
the preregistered falsifier "sensing defects remain absent because the
evaluator forgot them", true for one parameter until it was not.
(`SENSITIVITY_AUDIT.md`.)

---

## 10. Propositions

**A — command certificates are not sufficient.** Proven by counterexample. A
palindromic command with a drift lever of zero to 1e-9 and 20 050 A² of second
moment yields a realized lever of −0.0276 s through an ordinary causal bounded
lag, 2.8× the declared γ. A second independent failure mode: at six cycles the
lag removes 60% of the second moment.

**B — conditional soundness.** Proven, conditional on the declared error set
containing the true error, and that assumption is not verifiable from inside
the system. A test violates it and shows the conclusion collapsing.

**C — staleness.** Proven for truncation. Excitation drops at every tested
fraction; the drift lever is non-monotone and changes sign, so a full-window
certificate bounds a prefix in neither direction. My assumption that a prefix
must be worse was falsified by its own test.

---

## 11. Worst counterexample

There is no false certificate to report, so the closest thing to one is the
certified cell with the largest independent error: **P7a on Q1 at Δ = 0.040,
`AE_R` = 4.534e-3 Ω** — still well inside its own tolerance of τ_R = 0.020 Ω,
and produced by the non-deployable benchmark rather than by any deployable arm
(`results/WORST_COUNTEREXAMPLE.json`).

The worst outcome overall belongs to `INSUFFICIENT_EXCITATION` at a median
`AE_R` of 4.25e-2 Ω — cells where the certificate declined and was right to.

---

## 12. What is implemented, simulated, conditionally proven, and unproven

**Implemented and tested:** the independent evaluator, three plant families on
an independent integration path, the corrected oracle taxonomy with two
legitimate ceilings, censoring-aware metrics, seven deployable strategies and
four selectors, the modelled-observation-set distance, the frozen reduction of
the pairwise-overlap objective, the two-gate contract, and static
import-graph isolation with positive controls.

**Simulated only:** every result above. There is no hardware in this
environment and none is authorised.

**Conditionally proven:** Proposition B, on an assumption that cannot be checked
from inside.

**Unproven and recorded as gaps:** formal reachable-set safety; calibrated
uncertainty sets from held-out or hardware data; embedded timing on the
intended target; hardware evidence of any kind; external replication; open-set
coverage beyond one ringing family.

---

## 13. Integrity

Frozen core `b0b011c61426a70e…`, 12 of 12 files matching. Prior sealed-partition
manifest `e872d36f…5c6f65c2` unchanged. This phase's partition manifest
`b293e30f…01786731`. No old raw artifact was edited.

The sealed final partition was opened **once**, from the state recorded in
`SEAL_OPENING_RECORD.md` before the run began, after
`tools/research/iv_gate_check.py` reported all ten conditions passing.

Three integrity checks that did not exist when this phase started now do, each
because something slipped past its absence:

* `tests/test_iv_integrity.py` reads both checksum manifests in both
  directions, refuses a pinned file git does not track, and verifies every
  campaign artifact carries the row count its own header claims — a digest
  proves a file has not changed since it was pinned and proves nothing about
  whether it was whole at the time (`COUNTEREXAMPLE_LOG.md` IV-23, IV-24);
* `tests/test_iv_vacuity.py` pins the vacuity audit: no check may be
  `UNVERIFIED`, and the vacuous set must be exactly `["gate::pre_safe"]`;
* `tests/test_ci_env.py` now catches pipelines that discard a pytest exit
  status, across every committed shell surface rather than the workflows
  alone.
