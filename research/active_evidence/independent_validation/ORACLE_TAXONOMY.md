# Oracle Taxonomy — P7a, P7b, P7c

**Development partition. Simulator. Nothing here promotes anything.**
Evidence: `results/ORACLE_TAXONOMY.json`, produced by
`tools/research/iv_oracle_taxonomy.py`. Six development seeds, three plants,
six magnitudes, 72 admissible actions.

## 1. What was wrong with the old P7

The prior campaign carried an arm named `P7_oracle`. Its objective was to
maximise the realized second moment of current. On the locked data it **never
issued a certificate at any magnitude on the grid**, which makes it the worst
arm in the table despite having the highest excitation
(`COUNTEREXAMPLE_LOG.md` IV-2).

Calling it an oracle meant every comparison against it was flattering by
construction: a deployable arm beating the "oracle" looked like a triumph when
it was a symptom of the oracle being mis-specified. The name is withdrawn and
it is not used again.

## 2. The three objects

**`P7a` — maximum-current-second-moment benchmark.** Maximises realized `S_II`
subject to the hard action and safety constraints. Uses no truth; `S_II` comes
from the measured current of the nominal run. It is a **benchmark**. A test
parses this repository's source and fails if the word "oracle" appears on a
line with `P7a` except to deny the association.

**`P7b` — hindsight outcome oracle.** May use true plant parameters, the
realized fault and the complete future trajectory. Exhaustively evaluates all
72 admissible actions and returns the one minimising the independent outcome
loss, under exactly the constraints every deployable strategy faces. Evaluation
only; Layer A cannot import it.

**`P7c` — robust model-envelope oracle.** Never sees the realized fault label.
Minimises the worst-case outcome loss over the declared envelope — all three
plants, all six magnitudes. Non-deployable because enumerating the envelope is
not something a vehicle can do online, and the docstring says so rather than
leaving a reader to assume.

## 3. The ceiling invariant

> No deployable strategy may outperform P7b on P7b's exact objective, action
> space, plant instance and constraints, beyond numerical tolerance.

**216 invariant checks, each against all 72 admissible actions — 15 552
comparisons — and zero violations,** on both the change loss and the point
loss, across Q0/Q1/Q2, six seeds and all six magnitudes.

This holds by construction, because P7b is an exhaustive argmin over the same
finite set every strategy draws from. That is the point. The invariant is not
interesting when it passes; it exists to fail loudly when the enumeration, the
outcome cache or the random-number alignment has a bug. `ceiling_invariant`
returns a report rather than raising, so a violation would be recorded as
evidence instead of disappearing into a traceback, and the preregistration
requires the phase to stop if `holds` is ever false.

## 4. Maximum excitation is not the objective

| | P7a benchmark | P7b oracle |
|---|---|---|
| action chosen | `doublet_10A_8s` in **108 of 108** cells | six different actions, one per seed |
| mean energy | **80.0 A·s** (the cap) | **33.3 A·s** |
| energy class | high in 108/108 | low in 54, medium in 36, high in 18 |
| agreement with the oracle | **0.0%** | — |
| median loss ratio | **11.0×** the oracle | 1× |
| loss ratio range | 3.9× to 15.3× | — |
| median regret | 1.68e-6 Ω | 0 |
| worst regret | 2.35e-5 Ω | 0 |

P7a spends **2.4 times the energy to land 11 times further from the answer.**
The prior phase asserted that maximising `S_II` is not equivalent to
maximising diagnosis quality; this measures it against a ceiling that is
legitimate, on independently implemented plants, and the two never once agree.

## 5. A prediction that came true, and what it means

P7b's chosen action is **constant across plant and magnitude within a seed** —
each of the six actions appears in exactly 18 cells, which is 3 plants × 6
magnitudes.

That is not a coincidence and it is not reassuring. It follows from
`COUNTEREXAMPLE_LOG.md` IV-9: under the paired design the change loss is
`|λ̂ − 1|·Δ`, where `λ̂` is the finite-sample errors-in-variables factor. `λ̂`
depends on the action and on the current-sensor noise draw, and on nothing
else — not on the plant, not on the magnitude. So the argmin over actions is
necessarily independent of both, and the data agrees exactly.

The same mechanism shows up in P7c. Under the change loss, P7c picks **six
different actions in six seeds** — the objective is dominated by a noise
realisation, so the "robust" choice is not robust at all. Under the point loss
it picks three distinct actions in six seeds, converging on `cosine3_14A_8s`,
which is stable behaviour.

**Read-across:** on this design, any conclusion drawn from the change loss
about *which action is better* is largely a statement about one noise draw.
The point loss is the one that carries information about the action. This is
reported rather than repaired, because `e_ΔR` is the metric the task defines
and the preregistration froze, and because the mechanism is now derived rather
than guessed.

## 6. What this does not show

That P7b is achievable, or close to achievable, by anything deployable. It has
the answer. The regret column measures how far a strategy is from a bound that
no online method can reach, and a small regret against P7b is evidence about
the action space being flat, not about the strategy being clever.

It also does not show that the action space is the right one. Seventy-two
waveforms under a peak and energy cap is a design decision, frozen before the
comparisons were run, and a different space would give different ceilings.
