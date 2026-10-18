# Claim ledger — Realized-Current Excitation Certificate

Tier **E0** throughout. Quarantined post-freeze, research-only.

| id | claim | status | evidence |
|---|---|---|---|
| RC-A1 | `S_tI/S_II` is the realized drift lever arm, in seconds | `VERIFIED` | dimensional test, sign test |
| RC-A2 | Measured `S_II` must have its noise power removed, with a significance floor | `VERIFIED` | pure-noise window refused |
| RC-A3 | The polarization bound falls as `1/sqrt(1+(2 pi f tau)^2)` | `VERIFIED` | 17× fall from 1 to 24 cycles |
| RC-A4 | The noise term rises with probe frequency | `MEASURED` | 0.00057 → 0.00246 |
| RC-A5 | The total error has an interior minimum | `MEASURED` | minimum at 6 cycles |
| RC-A6 | The optimum is where polarization bias equals the noise term | `MEASURED` | 0.00083 vs 0.00083 at 6 cycles |
| RC-A7 | Moving energy in frequency at constant cost cuts the resolvable change from 0.020 to 0.005 Ω | `MEASURED` | frequency sweep, locked seeds |
| RC-B1 | A large voltage step at constant current does not certify | `VERIFIED` | −0.80 V, insufficient excitation |
| RC-B2 | Zero false certifications across the declared envelope | `NO_COUNTEREXAMPLE_IN_2000_DRAWS` | adversarial phase |
| RC-B3 | The bound is not vacuous | `MEASURED` | worst case 0.928 of its own limit |
| RC-B4 | An unmodelled dynamic fault returns unknown, not a label | `SUPPORTED` | 10/10 at 0.40 V ringing |
| RC-B5 | A clipped or aborted action cannot inherit a certificate | `VERIFIED` | execution ablation |
| RC-B6 | An undeclared term fails closed and is named | `VERIFIED` | three budget fields tested |
| RC-C1 | Command palindromy survives the closed loop | **`REFUTED`** | realized lever arm −0.641 s for the mission arm |
| RC-C2 | A closed-loop-aware strategy reduces realized drift coupling | `SUPPORTED` | P4: +0.033 → −0.022 s, `S_II` +12% |
| RC-C3 | That mechanical gain improves fault separation | **`REJECTED`** | swept separation unchanged at 0.75 |
| RC-C4 | Because `B_drift` is 9% of the error and `B_dynamic` is 59% | `MEASURED` | term breakdown |
| RC-C5 | Active probing beats an ordinary mission manoeuvre | `SUPPORTED HERE` | 0.75 vs 0.50; reverses MX-038's finding on a different bank |
| RC-C6 | A purpose-built selector beats a fixed or random probe | **`REJECTED`** | all 0.75 |

## Explicitly not claimed

| | |
|---|---|
| robust operation across real battery chemistries | **NOT SUPPORTED.** Every parameter is synthetic; no cell data exists here |
| reliable behaviour under real RC dynamics | **only under the synthetic one-RC plant**, which excludes multi-RC, hysteresis and cell imbalance |
| command-space probes reliably produce adequate realized current | **REFUTED** — that is the premise of this whole campaign |
| novelty | **`BLOCKED_EXTERNAL_ACCESS`** |
| production integration into CSIA's authority path | **forbidden by the owner authorization** and not attempted |
| any formal safety guarantee | not claimed; Monte Carlo is not a proof |

## Multi-RC pack with hysteresis

| id | claim | status | evidence |
|---|---|---|---|
| RC-D1 | A richer pack trips the open-set detector on healthy data | **`REFUTED`** | multi-RC clean ratio 1.84 against one-RC's 2.17 |
| RC-D2 | Hysteresis acts without current reversal | **`REFUTED`** | `h` pinned at +1.0000 for the whole window at 20 A base |
| RC-D3 | The residual check catches a regressor-aligned nuisance | **`REFUTED`** | ratio 2.39 of 3.0 on a 4.81x wrong certificate |
| RC-D4 | A polarization-aware predicted residual removes the healthy-pack false alarm | `VERIFIED` | all four amplitudes certify, every error inside its bound |
| RC-D5 | `B_hysteresis = M_max |cov(sign I, I)|/var(I)` bounds the effect | `VERIFIED` | truthful declaration refuses the counterexample |
| RC-D6 | The bound holds inside its declared envelope | `NO_COUNTEREXAMPLE_IN_400_DRAWS` | 0 false, worst ratio 0.43 |
| RC-D7 | An under-declared bound produces wrong certificates | `MEASURED` | 11 of 290 certified, worst ratio 1.53 |
| RC-D8 | A second probe detects an under-declared bound | **`REFUTED`** | ratio 0.33, 0.55, 0.85 across three pairs, never above one |
| RC-D9 | Robust operation across real battery chemistries | **`NOT SUPPORTED`** | RC-D7 and RC-D8 together: the declaration must come from characterisation data this repository does not have |

## Repair phase, 2026-09-13

| id | claim | status | evidence |
|---|---|---|---|
| RC-E1 | The shipped polarization bound is sound | **`REFUTED`** | understates fivefold: 0.00155 against a true 0.00797 |
| RC-E2 | A steady-state spectral form can bound the branch over a short window | **`REFUTED`** | a 1.2 A/s ramp gives 0.0176, larger than `R1` itself |
| RC-E3 | A Cauchy-Schwarz transient term repairs it | **`REFUTED`** | 80 violations in 1200 combinations |
| RC-E4 | Direct evaluation over the declared envelope is sound | `NO_COUNTEREXAMPLE_IN_1800_DRAWS` | zero violations, tightness 0.57–0.90 |
| RC-E5 | The MX-039 arm comparison stands as reported | **`WITHDRAWN`** | its three-cycle probe does not certify under the corrected bound |
| RC-E6 | Lag underestimation is conservative | **`WITHDRAWN`** | error non-monotone in the lag ratio; lever sign flips at 4x underestimate |
| RC-E7 | P3's pilot failure was infeasibility | **`REFUTED`** | 24 of 120 candidates certify; a witness exists |
| RC-E8 | P3's pilot failure was optimizer/objective misspecification | `SUPPORTED` | repaired objective finds the witness, pilot objective does not |
| RC-E9 | Excitation was the binding constraint | **`REFUTED`** | binds for 20 of 120; the error budget binds for 76 |
| RC-E10 | The MX-040 hysteresis limit as measured | **`SUPERSEDED`** | measured under the unsound bound; that window closes with the corrected one, the limit itself is not retired |
| RC-E11 | The failed pilot can be recovered | **`REFUTED`** | never committed; reconstruction only |

## Amended locked campaign, 2026-09-13

| id | claim | status | evidence |
|---|---|---|---|
| RC-F1 | A deployable active probe beats passive hover | `SUPPORTED` | P2 frontier 0.006 ohm; P0 never certifies |
| RC-F2 | A deployable active probe beats the ordinary mission manoeuvre | `SUPPORTED` | 140 of 140 matched pairs, median +0.03918 ohm; P6 never resolves |
| RC-F3 | A closed-loop-aware probe beats the naive palindrome | `SUPPORTED` | 240 of 240 matched pairs, median +0.00606 ohm |
| RC-F4 | The advantage survives an elevated nuisance | **`REFUTED`** | P2 and P3 collapse to never; only P4 holds |
| RC-F5 | P7 is an oracle ceiling | **`FALSIFIED`** | worst frontier of all arms |
| RC-F6 | Zero false certificates | `NO_COUNTEREXAMPLE_IN_8640_ROWS` | 0 of 8640 |
| RC-F7 | Clipping and abort invalidate a certificate | `VERIFIED` | both states returned |
| RC-F8 | The campaign distinguishes plant models | **`WITHDRAWN`** | M_R identical across all three by construction |
| RC-F9 | Unknown faults are routed | `SUPPORTED WITH A FLOOR` | 0.40 V routed, 0.10 V absorbed |
| RC-F10 | Lag error is benign in some direction | **`REFUTED`** | only the exact lag certifies; sign flips at 0.25x |
| RC-F11 | P3 is feasible and cheapest | `SUPPORTED` | 0.010 ohm at 20.37 A·s, half of P1's energy |
| RC-F12 | Sensing defects break the certificate | **`REFUTED`** | bias, scale, noise, delay, dropout, quantisation all certify |
