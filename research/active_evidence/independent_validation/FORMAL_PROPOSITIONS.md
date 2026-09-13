# Formal Propositions A, B, C

**Research only. Post-freeze. Quarantined. Simulator.**
No grand theorem is attempted. Each statement below is narrow, has its
assumptions in view, and points at an executable check in
`tests/test_iv_propositions.py`. Constructions live in
`csia_independent_validation/propositions.py`.

None of these is claimed to be novel. Novelty status for this phase remains
`BLOCKED_EXTERNAL_ACCESS`; see §13 of the task and `BASELINE_MAPPING.md`.

---

## Proposition A — command-space certificates are not sufficient

### Assumptions

* A sampled window of `N` points at spacing `dt`, `N = 400`, `dt = 0.02` s.
* A commanded excitation `u(t)` in amperes of excess demand.
* A command-to-current transformation `F` that is **causal**, **bounded**,
  linear and time-invariant. Instantiated as the first-order lag
  `x[k+1] = x[k]·e^(−dt/τ) + u[k]·(1 − e^(−dt/τ))`, which is the response every
  plant in this phase has. Causality and boundedness are tested, not assumed.
* Two command-space admissibility conditions with declared constants:
  `S_II(u) ≥ S_II_min` and `|S_tI(u)|/S_II(u) ≤ γ`.

### Units and domains

`S_II` in A², `S_tI` in s·A², the drift lever `S_tI/S_II` in seconds, `τ` in
seconds, `γ` in seconds.

### Statement

> There exist a causal bounded `F`, a command `u` and declared constants
> `(S_II_min, γ)` such that `u` satisfies both command-space conditions while
> the realized current `I = F(u)` violates at least one of them.

This is a **counterexample proposition**, not a universal theorem. It says
command certificates are not sufficient; it does not say they are never
informative.

### Counterexample

`u` is a palindromic cosine burst, symmetric about the window midpoint to
1e-12, so `S_tI(u) = 0` exactly and the command lever is `0` to 1e-9.
`τ = 0.25` s, `γ = 0.01` s, `S_II_min = 1000` A².

| cycles | `S_II(u)` | `S_II(I)` | lever(u) | lever(I) | command passes | realized passes |
|---|---|---|---|---|---|---|
| 1 | 20050 | 17582 | −0.000000 | **−0.027847** | yes | no |
| 2 | 20050 | 15966 | −0.000000 | **−0.027690** | yes | no |
| 3 | 20050 | 13841 | −0.000000 | **−0.027533** | yes | no |
| 6 | 20050 | 8046 | −0.000000 | **−0.027625** | yes | no |

The realized lever exceeds `γ` by a factor of 2.8 in every case.

A **second, independent** failure mode exists on the same construction: with
`S_II_min = 10⁴` A² and `γ` relaxed to 1 s, the six-cycle command passes the
excitation condition at 20050 A² while the realized current fails it at
8046 A² — the lag removes 60% of the second moment. So both conditions, not
just the drift condition, can pass in command space and fail in realized space.

### Limitation

The construction is not vacuous and it is also not adversarial: `F` is an
ordinary first-order lag, not a pathological operator. With `τ → 0` the
realized current equals the command and both sides pass, which is tested, so
the proposition is about a real transformation and not about a contrived one.
The magnitude of the violation grows monotonically with `τ` across the tested
range 0.01 to 1.0 s.

### Tests

`test_the_transformation_is_causal`, `test_the_transformation_is_bounded`,
`test_a_palindromic_command_has_zero_drift_lever`,
`test_proposition_a_holds_for_every_tested_waveform`,
`test_the_failing_condition_is_the_drift_lever`,
`test_excitation_alone_can_also_be_the_failing_condition`,
`test_the_construction_is_not_vacuous_when_there_is_no_lag`,
`test_lag_magnitude_controls_the_size_of_the_violation`.

### Claim-ledger entry

`B7` / H7 — **supported by counterexample**, inside this model and these
constants. Not a universal theorem.

---

## Proposition B — conditional soundness of a realized certificate

### Assumptions

1. **Telemetry validity.** The measured current and voltage are the ones the
   plant produced, within the declared sensing envelope.
2. **The declared error set contains the true estimator error.** For each
   window, `|R̂ − R_true| ≤ h`, where `h = |B_total| + k·SE` is the
   certificate's own declared half-width.

Assumption 2 is the load-bearing one and it is **not verifiable from inside
the system**. It is the assumption that makes every conditional-soundness
result of this shape conditional, and it is named here rather than absorbed
into the algebra.

### Statement

> Under assumptions 1 and 2, if the nominal and fault parameter sets
> `[R̂_nom ± h]` and `[R̂_fault ± h]` are disjoint, then the sign of the
> claimed change equals the sign of the true change. No false certificate is
> issued inside the declared model envelope.

### Proof

Disjointness of two symmetric intervals of equal half-width is exactly
`|R̂_fault − R̂_nom| > 2h`. By assumption 2, `R_nom ∈ [R̂_nom ± h]` and
`R_fault ∈ [R̂_fault ± h]`. Two points drawn from disjoint intervals are
ordered the same way as the intervals. Hence
`sign(R_fault − R_nom) = sign(R̂_fault − R̂_nom)`. ∎

The proof is three lines because the content is all in assumption 2.

### Counterexample when the assumption fails

With `R_nom = 0.060`, `R_fault = 0.040`, `R̂_nom = 0.042`, `R̂_fault = 0.058`
and `h = 0.005`: the sets are disjoint, the certificate would be issued, and
the claimed change is **positive when the true change is negative**. Each
estimate is 0.018 Ω from its own truth — well outside `h` — so assumption 2 is
violated and the proposition makes no claim. That is the point of testing it:
the conclusion is vacuously satisfied, and a reader who forgot the assumption
would have read the proposition as a guarantee it never gave.

### Limitation

The proposition is about **sign recovery on disjoint sets**, not about
magnitude accuracy, not about coverage, and not about anything outside the
declared model envelope. It says nothing when the sets overlap.

### Tests

`test_disjointness_is_the_obvious_interval_condition`,
`test_soundness_conclusion_holds_when_the_assumption_does`,
`test_the_conclusion_fails_when_the_error_set_does_not_contain_truth`,
`test_overlapping_sets_make_no_claim`,
`test_a_zero_change_is_reported_as_zero_not_as_a_sign`.

### Claim-ledger entry

**Conditionally proven**, with the condition stated. The empirical question of
whether assumption 2 actually holds is what Layer B's calibration table
measures, and it is a separate question from this proposition.

---

## Proposition C — a certificate for a proposed waveform is stale once the action is modified

### Assumptions

* A certificate whose excitation condition is a lower bound on `S_II` and an
  upper bound on `|S_tI|/S_II`, both computed for the **proposed** waveform.
* An execution that is clipped, truncated, delayed or aborted, so the realized
  waveform is a proper prefix or an amplitude-modified version of the proposal.

### Statement

> Truncation does not preserve the predicted moments in either direction. A
> certificate computed for the full proposed waveform bounds the realized
> prefix neither from below on `S_II` nor from above on `|S_tI|/S_II`.

### Derivation and measurement

`S_II` is a sum of squared deviations over the window, so removing samples
removes terms and shrinks it — **measured at every tested fraction**: 0.2, 0.25,
0.4, 0.5, 0.75, 0.9 and 0.95 all have strictly less second moment than the full
window. A predicted lower bound on excitation therefore overstates what the
prefix delivers, and a resolvability claim built on it is optimistic.

The drift lever is worse than that: it is **non-monotone in the executed
fraction and it changes sign**. For a three-cycle palindromic burst through a
0.25 s lag, with a full-window lever of −0.02753 s:

| executed fraction | `S_II` | realized lever (s) |
|---|---|---|
| 0.20 | 2394 | **−0.07692** (2.8× worse) |
| 0.25 | 3163 | **−0.09162** (3.3× worse) |
| 0.40 | 5571 | **+0.02828** (sign flipped) |
| 0.50 | 6387 | +0.00193 (nearly vanishes) |
| 0.75 | 10713 | +0.03864 |
| 0.90 | 13050 | −0.04726 |
| full | 13841 | −0.02753 |

The first version of this analysis assumed a prefix of a palindrome must carry
*more* drift leverage than the whole. Writing the test falsified it at 0.5, and
the table above is what replaced the assumption. This is the same shape as the
prior phase's finding that lag underestimation is not automatically
conservative.

### The narrow condition under which recomputation is safe

A certificate may be recomputed from the realized prefix when **all** of the
following hold:

1. every bound in the error budget is recomputed from the prefix's own
   measured moments, not carried over from the proposal;
2. the prefix's coverage independently satisfies the declared minimum;
3. the estimate being certified is computed from the prefix alone;
4. the prefix is treated as a complete window in its own right, with no claim
   inherited from the proposal — including no claim about the palindromy or
   symmetry of the executed waveform.

Under those conditions the prefix bounds itself trivially, which is tested. The
content of the condition is entirely in "recomputed from the prefix": a
certificate that reuses one predicted term is not a prefix certificate.

### Limitation

Truncation only. Amplitude clipping and transport delay are argued from the
same mechanism — the realized moments are not the predicted ones — but are not
separately enumerated here. The prior phase's campaign already routes clipped
executions to `CLIPPED_CERTIFICATE_INVALID` and aborted ones to
`ABORTED_INCOMPLETE`, which is the behaviour this proposition justifies rather
than discovers.

### Tests

`test_truncation_keeps_only_the_prefix`,
`test_a_prediction_for_the_whole_window_does_not_bound_a_truncation`,
`test_truncation_is_not_conservative_in_either_direction`,
`test_every_tested_truncation_loses_excitation`,
`test_a_full_execution_is_bounded_by_its_own_prediction`,
`test_recomputing_from_the_prefix_is_self_consistent`.

### Claim-ledger entry

**Proven for truncation**, within this model. The sufficient condition for safe
recomputation is stated and tested; whether any implementation satisfies it is
a separate question this proposition does not answer.
