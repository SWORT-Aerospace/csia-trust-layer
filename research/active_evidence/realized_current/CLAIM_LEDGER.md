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
