# Amended locked campaign — results

**Run once, on the sealed partition, 2026-09-13.** 8640 rows, 209.5 s.
E0 simulation, synthetic pack, quarantined post-freeze. No novelty claimed.

| | |
|---|---|
| branch | `claude/code-reviewer-repo-export-zicovg` |
| preregistration | `84576af5` |
| amendment 1 | `020b0dd1` |
| scope clarification | `ef572c02` |
| HEAD at run | `c3ee776c` |
| partition manifest SHA-256 | `e872d36f…5b6f65c2` |
| locked seeds | 14000–15900, 20 seeds, opened once |
| frozen-core digest-of-digests | `b0b011c6…915ba5a8`, unchanged |
| baseline tests before run | 3069, all passing; blocking guards PASS |

Reproduce: `.venv/bin/python tools/research/rcec_locked_campaign.py --out
research/active_evidence/realized_current/results/RCEC_LOCKED_CAMPAIGN.json`

## 1. Strongest defensible result

> **The delay-compensated probe P2 resolves a 0.006 ohm pack-resistance
> change where the naive palindromic probe needs 0.020 ohm, and where passive
> hover and an ordinary mission manoeuvre never resolve at any magnitude
> tested. It beats the mission manoeuvre on 140 of 140 matched
> drift/magnitude/seed triples and the naive probe on 240 of 240, at 45.85
> against 40.74 amp-seconds. Zero false certificates in 8640 runs.**

## 2. Worst counterexample: the best arm is the most fragile

Smallest change resolved at 90% or better, one-RC plant, by drift level:

| arm | drift absent | nominal | elevated |
|---|---|---|---|
| P0 passive | never | never | never |
| P1 palindromic | 0.020 | 0.020 | 0.020 |
| **P2 compensated** | **0.006** | **0.006** | **never** |
| P3 shaped | 0.010 | 0.010 | **never** |
| P4 feedback | 0.010 | 0.010 | **0.010** |
| P5 random safe | 0.020 | 0.020 | 0.020 |
| P6 mission | never | never | never |
| P7 oracle (not deployable) | 0.040 | 0.040 | 0.040 |

**At elevated drift the two best arms collapse to never, and the feedback arm
does not.** P4 is worse at nominal drift and the only one of the three still
working when the nuisance grows. An arm chosen on nominal performance is the
wrong choice under drift.

The scalar interaction came out undefined: with "never" encoded as infinity,
the difference of two infinities is not a number. **The interaction is real
and the scalar is not computable**, so the table above is the result and no
number is quoted in its place.

## 3. P0–P7 comparison, one-RC, nominal drift

| arm | cert % | median M_R | worst M_R | realized S_II | median &#124;lever&#124; | energy A·s | mission A·s | min safety A | ms |
|---|---|---|---|---|---|---|---|---|---|
| P0 passive | 0.0 | — | — | 2.8 | 1.0875 | 0.00 | 0.00 | −6.34 | 3.3 |
| P1 palindromic | 16.7 | −0.00259 | −0.00873 | 9098.8 | 0.0330 | 40.74 | 40.74 | −13.22 | 28.6 |
| **P2 compensated** | **50.0** | **+0.00349** | −0.00261 | 11581.3 | 0.0275 | 45.85 | 45.85 | −14.12 | 28.6 |
| P3 shaped | 33.3 | +0.00176 | −0.00536 | 1360.0 | 0.0670 | **20.37** | 20.37 | −8.85 | 28.5 |
| P4 feedback | 33.3 | −0.00080 | −0.00689 | 10197.9 | **0.0224** | 40.74 | 40.74 | −14.12 | 29.8 |
| P5 random safe | 16.7 | −0.00352 | −0.00970 | 6866.5 | 0.0380 | 35.39 | 35.39 | −12.31 | 28.6 |
| P6 mission | 0.0 | −0.01852 | −0.02890 | 2988.6 | 0.6416 | 0.00 | 0.00 | −10.23 | 3.5 |
| P7 oracle **NOT DEPLOYABLE** | 0.0 | −0.01371 | −0.01974 | 21445.3 | 0.0180 | 64.00 | 64.00 | −14.27 | 28.9 |

Negative minimum safety margin means the realized peak current exceeded the
declared authority figure used as the reference. It is reported rather than
suppressed; the authority constant is a planning number, not an enforced
limit, in this simulator.

## 4. P7 is not a ceiling. Claim withdrawn.

P7 has the **highest** realized excitation (21445) and the **lowest** drift
lever (0.018) and the **worst** frontier (0.040). It maximises the second
moment of current, which is not the objective. Its energy sits at the
window's fundamental, about 0.125 Hz, where the polarization branch follows
it completely.

**A quantity that is an upper bound on excitation is not an upper bound on
resolution.** P7 was declared an oracle ceiling in MX-039 and that claim is
withdrawn. It remains in the table, marked not deployable, as a measured
counterexample to its own description.

## 5. Certificate confusion, all 8640 rows

| state | count | share |
|---|---|---|
| `MODEL_MISMATCH_LIMITED` | 4723 | 54.7% |
| `INSUFFICIENT_EXCITATION` | 1440 | 16.7% |
| `CERTIFIED_IN_MODEL` | 1320 | 15.3% |
| `UNKNOWN_OR_MODEL_MISMATCH` | 620 | 7.2% |
| `DRIFT_COUPLED` | 537 | 6.2% |

## 6. False certificates: zero

**0 of 8640.** A false certificate is a `CERTIFIED_IN_MODEL` row whose signed
margin is negative. None occurred. Clipping and abort behaved as required:
clipped returns `CLIPPED_CERTIFICATE_INVALID`, aborted returns
`ABORTED_INCOMPLETE`, and only the full execution certifies.

## 7. The margin cannot distinguish plant models. Limitation, not a result.

Median M_R is **identical to twelve decimal places** across simple, one-RC and
multi-RC, in all 2012 comparable cells, and `B_total` takes exactly one value
per cell.

This is by construction and it was not anticipated. `M_R` is built from the
**declared envelope** and the **realized current**, and the realized current
is set by the control loop, which the polarization branch barely affects. So
`M_R` measures **what the certificate can bound, not what the plant does.**

The arm comparison under a common declared envelope stands. **The
simple-versus-one-RC comparison does not, and is withdrawn**: this campaign
cannot make it. Separating plants requires scoring the estimate against
plant truth, which only the false-certificate check does here.

## 8. Active probing versus the ordinary mission manoeuvre

**Active probing wins decisively, reversing MX-038.**

| comparison | matched pairs | active better | median paired difference |
|---|---|---|---|
| P2 vs P6 mission | 140 | **140 (100%)** | **+0.03918 ohm** |
| P2 vs P1 naive | 240 | **240 (100%)** | +0.00606 ohm |

P6 never resolves at any magnitude. Its realized drift lever is 0.64 s, an
order of magnitude worse than any purpose-built probe, because a slow mission
manoeuvre correlates current with time. **Waiting is free and it does not
work here.**

## 9. P3: feasible, cheapest, and fragile

Frontier 0.010 ohm at **20.37 A·s**, half of P1's energy for twice its
resolution. It collapses to never at elevated drift. Feasible, not dominated
on cost, not robust.

## 10. Unknown-fault routing and sensing robustness

| unmodelled ringing | state |
|---|---|
| 0.00 V | certified |
| 0.10 V | **certified — missed** |
| 0.40 V | `UNKNOWN_OR_MODEL_MISMATCH` |

The detector has a floor: a small unmodelled dynamic is absorbed.

Sensing defects barely move the margin. All of bias 1.0 A, scale error 2%,
current noise 0.2 A, 40 ms delay, 20% dropout and 0.05 A quantisation
certified, with M_R between 0.00542 and 0.00674 against a nominal 0.00576.

## 11. Lag error is not benign in either direction

| assumed/true | state | realized lever sign |
|---|---|---|
| 0.25 | `MODEL_MISMATCH_LIMITED` | **+1** |
| 0.50 | `MODEL_MISMATCH_LIMITED` | −1 |
| 1.00 | `CERTIFIED_IN_MODEL` | −1 |
| 2.00 | `MODEL_MISMATCH_LIMITED` | −1 |
| 4.00 | `MODEL_MISMATCH_LIMITED` | −1 |

Only the exact lag certifies, and the sign flip at a fourfold underestimate
is confirmed on locked data. The withdrawal of "conservative" stands.

## 12. Polarization bound: empirical coverage and exact scope

Bounded over the declared discrete model grid of 105 instances. Zero observed
bound violations in 1,800 preregistered simulator evaluations sampled from
the continuous envelope; under an IID interpretation the rule-of-three upper
limit is `p < 3/1800 ≈ 0.00167`, **not a formal guarantee**. Outside the
evaluated envelope the certificate fails closed. See
`POLARIZATION_BOUND_SCOPE.md`.

## 13. Withdrawn, superseded or falsified

| claim | status |
|---|---|
| MX-039 arm comparison | **withdrawn** — computed on a polarization bound understating fivefold |
| MX-039: P7 is an oracle ceiling | **falsified** — worst frontier of all arms |
| MX-039: lag underestimation is conservative | **withdrawn** — non-monotone, sign flips |
| MX-040 hysteresis limit as measured | **superseded** — measured under the unsound bound |
| MX-038: probing earns nothing over waiting | **does not transfer** — reversed here, on a different plant and metric |
| this campaign distinguishes plant models | **withdrawn before reporting** — M_R is plant-independent by construction |
| the binary separation score | **retained for audit, not primary** |

## 14. What is implemented, simulated, and unproven

**Implemented and tested:** the certificate and its ten states, the six error
terms, the envelope-evaluated polarization bound, four probe strategies, the
seed partitions, the difficulty ladder, the factorial.

**Simulated only:** every number above. One synthetic pack family, one loop
family, one platform.

**Unproven:** any behaviour on hardware; soundness on the continuum;
robustness across real chemistries; that the declared envelopes match any
real pack; that P2's advantage survives a nuisance not in this model.

## 15. Novelty

**`BLOCKED_EXTERNAL_ACCESS`.** Unchanged. Every scholarly host is denied by
organization policy.
