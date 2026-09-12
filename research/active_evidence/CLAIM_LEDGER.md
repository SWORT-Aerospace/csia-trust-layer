# Claim ledger — active evidence acquisition

Every claim this work makes, with the evidence that supports it and the tier
it sits at. Tier vocabulary from
`research/physical_validation/EVIDENCE_EXTENSION.yaml`: **E0** is desktop
simulation. Nothing here is above E0.

| id | claim | status | tier | evidence |
|---|---|---|---|---|
| AE-1 | `E[R_hat] = lambda (R + d cov(t,I)/var(I))` predicts the least-squares estimate | `VERIFIED` | E0 | `tests/test_identifiability.py`, 18 cases, worst error 2.1e-05 ohm |
| AE-2 | A steady operating point biases the estimate toward zero regardless of the true resistance, and more data does not fix it | `VERIFIED` | E0 | `test_a_steady_hover_is_biased_to_zero_however_long_it_runs`; 5 s and 60 s both within 25% of zero |
| AE-3 | Numerical rank is the wrong diagnostic: a noisy hover has full rank and zero information | `VERIFIED` | E0 | `test_rank_is_the_wrong_diagnostic_and_the_module_says_so` |
| AE-4 | The textbook slope variance is optimistic by up to 85% for a measured regressor | `MEASURED` | E0 | `test_the_naive_scatter_formula_is_optimistic`, 108 cases, three noise regimes |
| AE-5 | The delta-method scatter agrees with Monte Carlo within 2.2% | `VERIFIED` | E0 | same test; worst deviation 0.022 |
| AE-6 | A profile symmetric about its window midpoint has zero drift lever arm in the COMMANDED current | `VERIFIED` | E0 | `test_every_probe_is_a_palindrome_in_commanded_time`, measured at 1e-16 |
| AE-7 | That guarantee does not survive a closed loop for a single-excursion shape | `MEASURED — CORRECTS AE-6` | E0 | campaign `realisation`; realised lever arms -0.584 s to -1.138 s for four of six probes |
| AE-8 | A multi-cycle symmetric burst does keep the property through the loop | `MEASURED` | E0 | `burst_2hz` +0.019 s, `burst_wide` +0.004 s |
| AE-9 | A probe meeting all three necessary conditions resolves `delta_r` in an independent plant | `NO_COUNTEREXAMPLE_IN_THIS_GRID` | E0 | 28 cells, 20 met-and-resolved, **0 false positives** |
| AE-10 | A probe failing a condition does not resolve `delta_r` | `ONE COUNTEREXAMPLE, CONSERVATIVE DIRECTION` | E0 | 7 failed-and-unresolved, 1 false negative (`triangle` at 0.005) |
| AE-11 | The requirement is conservative because the closed loop amplifies the realised excitation | `MEASURED` | E0 | realised/predicted std(I) ratio 1.46 to 1.76 |
| AE-12 | The noise model can be recovered from the plant without reading its parameters | `VERIFIED` | E0 | successive differencing gives 0.02005 / 0.07864 against true 0.020 / 0.080 |
| AE-13 | CSIA gains no action authority from any of this | `HELD BY CONSTRUCTION AND TEST` | n/a | `test_no_module_here_can_reach_a_transmit_path`, `test_an_episode_that_claims_action_authority_is_refused`, `test_there_is_no_override` |
| AE-14 | The authorizer can refuse, and every refusal names itself | `VERIFIED` | n/a | six named hard refusals, each with its own test |
| AE-15 | A clipped probe is re-checked and may lose identifiability | `VERIFIED` | n/a | `test_a_clip_that_destroys_identifiability_is_not_silently_accepted` |
| AE-16 | The selector abstains rather than returning its best failing candidate | `VERIFIED` | n/a | `test_the_selector_returns_a_refusal_rather_than_its_best_failure` |
| AE-17 | The updater reports a falsified model as its own verdict, not as ambiguity | `VERIFIED` | n/a | `test_a_falsified_model_is_not_reported_as_a_diagnosis` |
| AE-18 | Anything here is new | **`NOVELTY_NOT_ESTABLISHED`** | — | the prior-art search could not be run; see `PRIOR_ART_MATRIX.md`. **No novelty claim is permitted** |
| AE-19 | Anything here is safe, certified, or flight-ready | **`NOT CLAIMED`** | — | it is not. `SIMULATOR_VALIDITY_ENVELOPE.md` |

## Claims deliberately NOT made

* that the probe library is complete, or that its shapes are good ones;
* that the envelope limits in `authority.py` are right for any vehicle —
  they are a mock and the module says so in its first paragraph;
* that the hypothesis set in any example is complete;
* that a real pack behaves like `V = E - I R` over a probe window;
* that this improves diagnosis, detection, or anything measured elsewhere in
  this repository. No frozen number moved and none was re-measured.
