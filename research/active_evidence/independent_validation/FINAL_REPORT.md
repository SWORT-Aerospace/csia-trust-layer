# Final Report — RCEC Independent Validation

**RESEARCH ONLY. POST-FREEZE. QUARANTINED. SIMULATOR.**
Not a certified safety artifact, not airworthy, not production-ready. Synthetic
pack, no chemistry claimed, no hardware representativeness implied. No hardware
was operated and none is authorised.

The nineteen items the task asks for, in order.

---

## 1. Verdict

**`SUPPORTED_WITH_NARROW_SCOPE`.**

Three preregistered hypotheses (H2, H3) and one preregistered claim (the
two-gate combined claim) are **rejected**. Four hypotheses are supported, two
of them only within a stated narrowing.

## 2. Strongest defensible result, one sentence

> Within a declared simulator envelope, on 1440 matched sealed-partition cells,
> the compensated active probe P2 achieved a lower independent point error than
> the ordinary mission manoeuvre in 1440/1440, passive hover in 1439/1440,
> random-safe excitation in 1346/1440 and the naive palindrome in 1399/1440;
> and all 3925 inferences accepted by the realized-telemetry certificate were
> correct against simulator truth — zero false certificates, one-sided 95%
> upper bound 1.5e-3 over 2009 distinct experiments — at a coverage cost of
> 81.8%.

## 3. Did the independent evaluator preserve or reverse the advantage?

**Preserved on the point metric, dissolved on the preregistered change metric**
for a reason derived before the campaign ran.

`A_s` on the change metric is 0.933 for **every** arm except P0 passive. Under
the paired design `e_ΔR = |λ̂ − 1|·Δ` with λ̂ ≈ 1.001, so the error is a
thousandth of the change while `τ_R` is half of it. The metric separates "did
you excite" from "did you not" and nothing else
(`PREREGISTRATION_AMENDMENT_2.md`).

On the point metric the ordering is clear: P0 0.017, P6 0.056, P7a 0.681,
P5 0.711, P3 0.753, P7b-change 0.862, P4 0.871, P1 1.000, P2 1.000.

## 4. Certificate calibration and every false certificate

**Zero false certificates**, both metrics, 21 600 sealed main-block cells.

| state | n | resolved (point) | median `AE_R` |
|---|---|---|---|
| `CERTIFIED_IN_MODEL` | 3925 | **1.0000** | 3.12e-4 Ω |
| `UNKNOWN_OR_MODEL_MISMATCH` | 196 | 0.9898 | 7.51e-4 Ω |
| `MODEL_MISMATCH_LIMITED` | 14 469 | 0.8617 | 5.87e-4 Ω |
| `INSUFFICIENT_EXCITATION` | 2986 | 0.0794 | 4.25e-2 Ω |
| `DRIFT_COUPLED` | 24 | 0.0000 | 1.02e-2 Ω |

Two things make the zero mean something. The **denominator**: 3925 rows collapse
to 2009 distinct experiments because up to six arms share one simulation, so the
honest bound is 3/2009 = 1.5e-3, short of 1e-4 by a factor of fifteen. And the
**kind**: `results/VACUITY_AUDIT_FINAL.json` classifies both false-certificate
checks `SOUND_BUT_UNEXERCISED` — constant on the data, with controls proving
they can fire. The prior phase's equivalent would have scored
`VACUOUS_IN_ENVELOPE`.

**The certificate is sound and markedly conservative.** It refused roughly
12 660 inferences that would have been correct, against 3925 accepted.

## 5. Q0 / Q1 / Q2

| plant | median `AE_R` | `A_s` point | `A_s` change |
|---|---|---|---|
| Q0 zero-RC | 2.94e-4 Ω | 0.868 | 0.933 |
| Q1 one-RC | 1.68e-3 Ω | 0.741 | 0.933 |
| Q2 richer | 1.37e-3 Ω | 0.728 | 0.933 |

**H5 supported on the point metric**: a 5.7-fold spread. The change metric gives
three identical figures, and the certificate margin is **bit-identical** across
plants in 48 of 48 development cells. An independent classical baseline agrees:
set-membership invalidation separates them at 2.46, 4.90 and 7.31 σ.

## 6. Frontiers and matched cost

| arm | `A_s` point | frontier | mean energy | median `AE_R` |
|---|---|---|---|---|
| P0 passive | 0.017 | `> 0.04` | 0 | 4.81e-2 |
| P6 mission | 0.056 | `> 0.04` | 48.0 | 7.66e-2 |
| P7a benchmark | 0.681 | 0.010 | 80.0 | 2.09e-3 |
| P5 random-safe | 0.711 | 0.010 | 20.4 | 2.55e-3 |
| P3 shaped | 0.753 | 0.010 | 14.0 | 1.82e-3 |
| P7b change-oracle | 0.862 | 0.010 | 48.1 | 8.10e-4 |
| P4 feedback | 0.871 | 0.006 | 56.0 | 1.54e-3 |
| P1 palindromic | 1.000 | 0.002 | 50.9 | 4.42e-4 |
| **P2 compensated** | **1.000** | **0.002** | 71.3 | **2.10e-4** |
| **P7b point-oracle** | **1.000** | **0.002** | 52.2 | **4.25e-5** |

**Gate E, honestly.** P1, P2, P4 and P7b share one declared energy class, so
this is like-for-like by class. Within it, P2's advantage over P1 is **smaller
than validation suggested**: both reach `A_s` 1.000 on the sealed run, and the
only difference is median point error, 2.10e-4 against 4.42e-4, bought with 40%
more energy. Whether that trade is worth making is an application question this
phase cannot answer.

**P4 loses to the naive palindrome in 95.6% of matched cells.**

## 7. Did P7b pass the ceiling invariant?

**Yes, everywhere.** Development, validation and the sealed partition; both
oracles, both losses; 1440 matched cells each on the sealed run. **Zero
violations.** No deployable arm beat either oracle on that oracle's own
objective.

Median regret against the point oracle: P2/S0/S3 1.09e-4 Ω, S2 2.78e-4,
P1 2.86e-4, P4/S1 1.38e-3, P7a 1.82e-3, P5 2.59e-3, P0 4.75e-2, P6 7.29e-2.

`P7a` is never called an oracle. `BASELINE_MAPPING.md` §3 shows why it fails:
its objective **is** the classical A-optimal design for resistance,
`var(R) = σ_V²/S_II`, and the optimum for the *assumed* model is not the
optimum for the plant.

## 8. S0–S3 and regret

| selector | nominal | elevated | worst-case | `I_s` |
|---|---|---|---|---|
| S0 always-P2 | 1.000 | 1.000 | **1.000** | −0.0056 |
| S1 always-P4 | 0.871 | 0.885 | 0.871 | +0.0083 |
| **S2 threshold** | 1.000 | **0.885** | 0.885 | **−0.1208** |
| S3 minimax | 1.000 | 1.000 | **1.000** | −0.0056 |

**H3 rejected.** S2 is strictly worse than committing globally to P2, with the
worst drift-interaction score of any arm. Its threshold switches to P4 under
elevated drift — exactly what the prior locked result motivated — and **that
result does not reproduce**: P2 does not collapse here. S3 ties S0 by never
choosing P4, so it is a more expensive way of always choosing P2.

**H2 rejected.** P4 is worse than P2 in *both* drift conditions.

**No selector abstained** in 69 120 rows. All three paths are reachable and
tested; the vacuity audit scores this `SOUND_BUT_UNEXERCISED`, not `VACUOUS`.

## 9. Finite drift interaction

Primary statistic `I_s`, point metric, difference in differences against
passive. Every value finite, range −0.1208 (S2) to +0.0917 (P7a). The statistic
this replaces went `NaN` whenever an arm never resolved, because "never" was
encoded as infinity; `drift_interaction` now **raises** on any input that is not
a probability.

## 10. Unknown-fault detectability boundary

**δ\* = 3.363 σ.** Routing rate 0.901 above it over 426 trials, **0.000** below
it over 870. The 0.10 V case the prior phase absorbed sits at 1.461 σ, about one
sigma above the 0.445 σ no-fault floor: its absorption is **structural**, not a
classifier defect. No threshold was lowered. One ringing family swept over
amplitude, frequency, damping, phase and onset — a detectability boundary, not
open-set coverage.

## 11. Sensor and telemetry sensitivity

Current gain error dominates at `J_q^out = −1.92e-2`; `e_ΔR ≈ −s·Δ/(1+s)` matches
measurement to 2e-6 Ω. Four parameters are **exactly** zero, each derived:
voltage offset absorbed by the intercept, current offset absorbed by the free
intercept, voltage noise cancelled by the paired design, timestamps never read
by the estimator. The certificate *does* read time — 2 ms of jitter moves its
margin, 10 ms returns `INVALID_INSTRUMENT`.

**Dropout measured exactly zero until the harness was fixed** to honour the
dropout mask: the preregistered falsifier "sensing defects remain absent because
the evaluator forgot them", true for one parameter until it was not.

## 12. Propositions

**A — command certificates are not sufficient. Proven by counterexample.** A
palindromic command with drift lever zero to 1e-9 and 20 050 A² of second moment
yields a realized lever of −0.0276 s through an ordinary causal bounded lag,
2.8× the declared γ. Second independent mode: at six cycles the lag removes 60%
of the second moment.

**B — conditional soundness. Proven, conditionally.** Disjoint error sets imply
the correct change sign *if* the declared error set contains the true error —
an assumption not verifiable from inside the system. A test violates it and
shows the conclusion collapsing.

**C — staleness. Proven for truncation.** Excitation drops at every tested
fraction; the drift lever is non-monotone and changes sign, so a full-window
certificate bounds a prefix in neither direction. My assumption that a prefix
must be *worse* was falsified by its own test.

## 13. Closest baseline result from prior art

**The primary text of the named closest source could not be retrieved.** Eight
endpoints, re-measured at `2026-09-14T01:14:18Z`: seven refused connections and
one direct 403. No content hash exists because no content was fetched. Sections
read: none. `results/EXTERNAL_ACCESS_CHECK.json`.

A **frozen faithful reduction** of the pairwise output-set overlap objective was
built instead, from the equation as given in the user-supplied sources, and it
keeps `zero_volume`, `empty_intersection` and `separation_margin` as three
distinct fields. **The distinction is not academic: 80 of 21 600 sealed cells
(0.37%) were touching rather than separated**, and a volume-only baseline would
have called those hypotheses distinguishable.

Other baselines: persistent excitation, Fisher-information/A-optimal design
(which turns out to be P7a's objective exactly), finite-model discrimination,
set-membership volume reduction (which separates Q0/Q1/Q2 at 2.46/4.90/7.31 σ),
and conventional post-execution validation (whose interval covers truth on a
full window and does **not** on the same run truncated to 25%, in identical
language). Tube-MPC active diagnosis is deliberately **not** implemented, with
the reason recorded in code.

## 14. Worst counterexample

There is no false certificate, so the closest thing is the certified cell with
the largest independent error: **P7a on Q1 at Δ = 0.040, `AE_R` = 4.534e-3 Ω** —
inside its own tolerance of 0.020 Ω, and produced by the non-deployable
benchmark rather than any deployable arm.

## 15. Every withdrawn or falsified construct

From the prior phase: "zero false certificates" as evidence of soundness
(empty by construction); the claim that its false-certificate check scored
against plant truth; the label "90% resolution frontier" for a margin-only
predicate; campaign-wide paired-win denominators; `P7_oracle` as an oracle.

Mine, this phase: **H2**; **H3**; the **two-gate combined claim**; my belief
that the pre-action gate would add safety screening; my belief that a prefix of
a palindrome carries more drift leverage; P7c as "robust" under the change loss;
"closest **verified** source" in the supplied draft.

Instrument defects found and fixed: an inactive branch shifting an active RNG
stream; hysteresis parameterised a thousand times too slow; one arena for a
whole campaign; a clipped execution marked incomplete; a routing predicate that
made everything look unknown; dropout disconnected; a manifest nobody read; a
hand-typed timestamp; and three occurrences of discarding a pytest exit code.

## 16. Branch, SHAs, commits, tests, guards, hashes

| field | value |
|---|---|
| branch | `claude/code-reviewer-repo-export-zicovg` |
| base SHA | `34944ff` |
| commits this phase | 27 |
| tests | 3497 collected, `PYTEST_EXIT=0` |
| blocking guards | **PASS** |
| advisory guards | FAIL — 53 pre-existing bibliography markers, unchanged by this phase |
| frozen-core digest | `b0b011c61426a70ead42e170855a2650d5c62feb640c7a50fffc27bb915ba5a8`, 12/12 |
| prior sealed partition | `e872d36fb3a9337704c18290e1b8ec0452d295c416eef0ba58a8b97c5b6f65c2`, untouched |
| this partition manifest | `b293e30f30a767c13b29d1abfa9ac4c3bdc49580f3224d037252513801786731` |
| seal opened | once, state recorded in `SEAL_OPENING_RECORD.md` before the run |

## 17. Implemented / simulated / conditionally proven / unproven

**Implemented and tested:** independent outcome evaluator; three plant families
on an independent integration path; corrected oracle taxonomy with two
legitimate ceilings; censoring-aware metrics; seven strategies and four
selectors; modelled-observation-set distance; frozen reduction of the overlap
objective; two-gate contract; static import-graph isolation; vacuity audit;
integrity verification.

**Simulated only:** everything. No hardware exists here and none is authorised.

**Conditionally proven:** Proposition B, on an assumption uncheckable from
inside.

**Unproven, recorded as gaps:** formal reachable-set safety; calibrated
uncertainty sets from held-out or hardware data; embedded timing on the intended
target; hardware evidence of any kind; external replication; open-set coverage
beyond one ringing family.

## 18. Novelty status

**`NOVELTY_UNRESOLVED`**, and the first obstacle is that the closest named
source could not be retrieved from this container.

**Prohibited outright:** any novelty claim for active fault diagnosis, optimal
excitation, Fisher-information design, set-membership diagnosis, output-feedback
model discrimination, reachable-set safety, runtime assurance or
battery-resistance estimation individually. One of them is demonstrably textbook
*inside this phase*.

**Prohibited until resolution:** any claim that the composition across proposal,
authorization, physical realization and evidence acceptance is novel.

**Permitted now, and only this:** a description of what was built and measured
with the scope attached, ending in the admission that the closest named source
is unread. `CLOSEST_PAPER_CLAIM_MATRIX.md` §5 gives the exact sentence.

## 19. The single next highest-value experiment

**Break the paired-design cancellation, in simulation, without touching
hardware.**

`e_ΔR` collapses to `|λ̂ − 1|·Δ` because the fault does not move the current:
`V_fault − V_nominal = −ΔR₀·I_true` exactly, so every plant-common nuisance
cancels. That is why the preregistered primary metric is saturated, why the
change-loss oracle is uninformative, and why plant discrimination had to move to
a secondary metric.

The experiment: make the nominal window a **different** window — a different
seed, a different waveform, or an earlier flight phase — which is what a real
deployment would have, since no vehicle gets to re-fly the same probe with and
without a fault. The cancellation disappears, `e_ΔR` starts carrying plant
structure, and the change-loss ceiling becomes meaningful.

It is the highest value because it is the one change that would make the
*preregistered primary metric* informative, rather than working around it. It
costs one runner change and one campaign. It needs a new preregistration,
because it changes what the primary metric measures.

Second-highest, and cheap: raise the distinct-experiment count. The current
zero-event bound is 1.5e-3 on 2009 experiments; 1e-4 needs about fifteen times
more, and nothing but compute stands in the way.
