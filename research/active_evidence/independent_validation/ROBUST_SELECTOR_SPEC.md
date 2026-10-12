# Robust Selector Specification — S0 to S3

**Research only. Post-freeze. Quarantined. Simulator.**
Implementation: `csia_independent_validation/strategies.py`. Tests:
`tests/test_iv_selectors.py`.

## 1. The question

The prior locked result says P2 is strongest under nominal conditions and
collapses to never under elevated drift, while P4 keeps a 0.010 Ω frontier.
Committing globally to the best nominal arm is therefore fragile. The question
is whether a selector using **only pre-action observable quantities** can do at
least as well in the worst case as committing to either arm.

H3 in the preregistration. It is allowed to come out false.

## 2. What a selector may see

`Observable` has exactly ten fields and the test suite pins the set:

| field | unit | what it is |
|---|---|---|
| `lag_estimate_s` | s | online estimate of the command-to-current lag |
| `lag_uncertainty_s` | s | half-width of the interval around it |
| `drift_estimate_v_per_s` | V/s | pre-probe open-circuit drift estimate |
| `drift_uncertainty_v_per_s` | V/s | its uncertainty |
| `sigma_i_bound_a` | A | commissioned current-noise bound |
| `sigma_v_bound_v` | V | commissioned voltage-noise bound |
| `remaining_energy_as` | A·s | charge available for probing |
| `remaining_time_s` | s | window available |
| `mission_phase` | — | cruise, hover, manoeuvre, landing |
| `clip_margin_a` | A | headroom before the declared current limit |

There is no field for the plant, the fault, the magnitude, the seed or any
outcome. `strategies.py` is inside `LAYER_A_MODULES`, so the import-graph audit
holds it to the same rule as the certificate itself, and its transitive closure
contains no truth-bearing module.

## 3. The strategies, and an honest note about the mapping

P0–P6 are **re-instantiations of the prior phase's arms inside the shared
finite action space**, not the same code. They have to be: a ceiling only means
something when the oracle and the strategies choose from one set.

| arm | rule |
|---|---|
| P0 passive | hold station |
| P1 palindromic | one fixed symmetric burst, ignoring lag and drift |
| P2 compensated | minimise the **predicted** realized drift lever among actions clearing `S_II_MIN` |
| P3 shaped | cheapest action clearing `S_II_MIN` |
| P4 feedback | best predicted excitation per unit of charge moved |
| P5 random-safe | deterministic pseudo-random admissible pick |
| P6 mission | a sustained hold — current correlated with time |

P4 deserves the note. The prior phase's feedback arm corrected current *within*
a window. Inside a fixed action space there is nothing to correct mid-flight,
so what carries over is its **objective** — information per unit cost rather
than information at any cost — and not its mechanism. The name is kept for
continuity with the prior results and this paragraph is the mapping rather than
an implication in the name.

## 4. The selectors

`S0` always P2. `S1` always P4. Both are controls.

`S2` is a preregistered threshold rule, and the thresholds
(`DRIFT_ELEVATED_V_PER_S = 1.0e-3`, `LAG_UNCERTAINTY_LIMIT = 0.5` of the lag
estimate, `MIN_USEFUL_ENERGY_AS = 10.0`) were fixed before any selector
comparison ran. It counts drift **uncertainty** towards the threshold, so a
confident small estimate and a vague one are not treated as the same evidence.

`S3` is a minimax over the declared lag interval implied by the online estimate
and its uncertainty:

```
s* = argmax_{s ∈ {P2, P4, WAIT, DENY}} min_{θ ∈ Θ_current} M_s^pred(θ)
```

`M_s^pred` is a declared construction from **predicted** moments — excitation
above the floor, penalised by the drift leverage the action will hand a slow
open-circuit change. It is not an outcome, not a certificate, and not anything
Layer B computed.

## 5. Declining is a first-class answer

A selector forced to choose between two actions is a coin. All three
abstentions are reachable and each is tested:

* `NO_SAFE_INFORMATIVE_ACTION` — not enough energy, or not enough current
  headroom, or no candidate clears its own worst-case floor;
* `INSUFFICIENT_NUISANCE_KNOWLEDGE` — the lag is unknown, or its relative
  uncertainty exceeds the declared limit;
* `WAIT_FOR_MISSION_EVIDENCE` — the mission phase is one where probing is not
  appropriate.

`test_every_abstention_is_reachable_from_s2` asserts the set of reached
abstentions equals the declared set, so an abstention that stops being
reachable fails the suite rather than quietly becoming decoration.

## 6. Leakage testing

The property is negative: **given an identical observable history, nothing
about the hidden world may change the selection.**

Structurally, hidden state is not an argument to any selector, and a test
asserts no selector signature accepts `plant`, `delta`, `truth`, `fault`,
`r0_true` or `outcome`. Behaviourally, each selector is called fifty times on
the same `Observable` while a hidden world is shuffled around it, and the
selection must be identical every time — which catches leakage through global
or cached state, the only route left once the signatures are clean.

## 7. Two defects the tests found during construction

`PASSIVE` carried a nominal eight-second duration, so it failed a
remaining-time budget it does not actually consume. It now has duration zero
and consumers fall back to their own default window.

`P1` returned its fixed waveform whatever the remaining energy, time or current
headroom. A strategy that proposes an inadmissible action is not naive, it is
broken; hard constraints are declared and knowable, so every arm respects them
and falls back to passive. What P1 still ignores is the lag and the drift,
which is the naivety the comparison is actually about.

Both were found before any selector comparison was run.

## 8. What this specification does not claim

That any of these selectors is good. The comparison against S0 and S1, the
worst-case `A_s`, the energy accounting, the false-certificate count and the
regret against P7b and P7c are all still to be measured, and H3 is written so
that it can be rejected.
