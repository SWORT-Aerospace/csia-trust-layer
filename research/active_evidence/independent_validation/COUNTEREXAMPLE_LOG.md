# Counterexample and Failure Log — RCEC Independent Validation

Every entry is something that was believed, tested, and found wrong, or an
instrument that was found not to measure what it claimed. Entries are appended,
never edited away. `IV-n` numbering continues independently of the prior
phase's `RC-n` log, which is frozen.

---

## IV-1 — "Zero false certificates in 8640 runs" could not have failed

**Believed:** the locked campaign demonstrated empirical soundness of the
certificate: 8640 runs, zero false certificates.

**Found:** `tools/research/rcec_locked_campaign.py::false_certificates`
selects rows where `state == CERTIFIED and M_R < 0`. In
`csia_active_evidence/rcec.py::certify`, the `CERTIFIED` return is reached only
after the guard `if achieved >= margin: return <not certified>`, and
`M_R = margin - achieved`. So `CERTIFIED` implies `M_R > 0` on every code path.
The selected set is empty by construction.

**Status:** the claim "zero false certificates" is **withdrawn as evidence of
soundness**. It is a true statement about a code invariant and says nothing
about whether any certificate was correct about the world. Detecting a genuine
false certificate requires comparing the estimate to simulator truth, which the
locked campaign never did.

**Consequence:** `RESULTS_LOCKED.md` §7's sentence "Separating plants requires
scoring the estimate against plant truth, which only the false-certificate
check does here" is false in its second clause. Not edited; recorded.

**Test:** `tests/test_iv_provenance.py::test_certify_only_returns_certified_when_the_margin_is_positive`,
`::test_no_locked_row_can_be_certified_with_a_negative_margin`,
`::test_the_locked_campaign_never_scored_against_plant_truth`.

---

## IV-2 — The "90% resolution frontier" does not require a certificate

**Believed:** the headline frontier numbers (P2 at 0.006 ohm, and so on)
describe how small a resistance change each probe can *certify*.

**Found:** the stored `resolvable_fraction` counts rows with `M_R > 0`,
irrespective of state. Requiring `CERTIFIED_IN_MODEL` as well moves every
frontier one grid step worse, and removes the old P7 from the table entirely:

| arm | published (`M_R > 0`) | requiring a certificate |
|---|---|---|
| P1 palindromic | 0.020 | 0.040 |
| P2 compensated | 0.006 | 0.010 |
| P3 shaped | 0.010 | 0.020 |
| P4 feedback | 0.010 | 0.020 |
| P5 random-safe | 0.020 | 0.040 |
| P7 (old) | 0.040 | **never** |

**Status:** the published numbers are arithmetically correct for the predicate
used. The *label* was wrong. Both predicates are computed and reported from
here on, and the predicate is stated with the number.

**Test:** `tests/test_iv_provenance.py::test_published_frontier_reproduces_under_margin_positive`,
`::test_frontier_is_strictly_worse_when_certification_is_required`,
`::test_the_old_p7_never_certifies_anywhere_on_the_grid`.

---

## IV-3 — The paired-win denominators were a single-plant slice

**Believed:** "P2 beat P6 on 140 of 140 matched triples and P1 on 240 of 240"
described the campaign.

**Found:** those are the `one_rc` slice. Campaign-wide the same comparisons are
420/420 and 726/726. The `simple` plant yields 246, not 240, against P1,
because P1 produced a margin in six more cells there.

**Status:** the win *rate* and the median differences reproduce exactly
(+0.0391840889243677 and +0.006057004416076926 ohm on the one-RC slice). The
denominators were under-reported by a factor of three and the scope was not
stated. Reported correctly from here on. Not a falsification of the direction
of the result.

**Test:** `tests/test_iv_provenance.py::test_published_paired_wins_are_the_one_rc_slice`,
`::test_campaign_wide_denominators_are_larger_and_still_unanimous`.

---

## IV-4 — The certificate margin is bit-identical across plants, not merely equal to 12 dp

**Believed:** "median certificate margin was identical to twelve decimal places
across the three plant arms in 2012 cells", which reads like a numerical
coincidence worth investigating.

**Found:** in all 2012 cells where all three plants produced a margin, the
values are **bit-identical**. `M_R^cert` is computed from the realized current
and the declared envelope; it never reads the plant's voltage response. There
was nothing to investigate: the quantity is plant-independent by construction.

**Status:** strengthens rather than contradicts the prior withdrawal of the
simple-versus-one-RC comparison. It also fixes the target for H5: an outcome
metric that is *also* plant-independent would be a failed instrument, not a
finding.

**Test:** `tests/test_iv_provenance.py::test_certificate_margin_is_bit_identical_across_plants`.

---

## IV-5 — `RAW_CHECKSUMS.sha256` pins files that are supposed to change

**Found:** the prior phase's checksum manifest lists nine living source and
document files (`rcec.py`, `test_rcec.py`, `DERIVATION.md`, `CLAIM_LEDGER.md`
and others) alongside the immutable raw campaign JSON. Those nine legitimately
changed in MX-040 and MX-042, so the manifest fails on 9 of 18 entries today.
The immutable raw JSON still verifies.

**Status:** a checksum file that mixes immutable artifacts with files expected
to evolve produces a permanent red that everybody learns to ignore, which is
worse than no manifest. Not repaired in place — the old file is evidence of
what was true at MX-039. This phase checksums **immutable raw outputs only**.

---

## IV-6 — The frozen-core digest had no committed derivation

**Found:** `b0b011c6…915ba5a8` appears exactly once in the repository, in
prose, with no code that produces it. A number nobody can recompute is not a
verification.

**Status:** the derivation is
`sha256(json.dumps(FROZEN_BASELINE.json["files"], sort_keys=True))`. Recovered
by enumerating ten plausible formulations and testing each; nine did not match.
Now pinned in `tools/research/iv_base_provenance.py` and asserted in
`tests/test_iv_provenance.py::test_frozen_core_digest_and_its_derivation`. All
12 files match their recorded digests.

---

## IV-7 — An inactive branch was shifting an active stream (found in construction)

**Found:** the first draft of `csia_independent_validation/plants.py` drew the
timestamp-jitter block only when jitter was enabled:

```python
jitter = rng["telemetry"].normal(...) if sensing.timestamp_jitter_s > 0 \
    else np.zeros(n)
keep = rng["telemetry"].random(n) >= sensing.dropout
```

Both draws come from the `telemetry` generator, so enabling jitter consumed
`n` values and silently changed the dropout mask of the same seed. Two runs
differing only in a timestamp setting would have dropped different samples, and
any effect attributed to jitter would have been partly an effect of losing
different data.

**Fix:** draw the block unconditionally and scale it afterwards. The decision
to enable a defect now consumes exactly the same randomness as the decision not
to.

**Test:** `tests/test_iv_plants.py::test_enabling_jitter_does_not_change_the_dropout_mask`
and `::test_injecting_ringing_does_not_disturb_the_current_channel`.

Found before any outcome was produced. Recorded because the same class of
defect cost the prior phase a whole pilot campaign (the P4 arm that never ran).

---

## IV-8 — A "dynamic" effect slower than the probe is not a dynamic effect

**Found:** Q2's Plett hysteresis was first parameterised with
`hysteresis_gamma = 0.08`. With `dh/dt = -(γ|I|/Q)(h - sign I)` at 20 A and
4 Ah that is a rate of 1.1e-4 s⁻¹, a time constant near **9000 s**. Across a
12 s probe the state moves by 0.13% of its range: removing hysteresis entirely
changed the terminal voltage by 4.7e-5 V, below the 0.020 V sensor noise.

Q2 exists to carry at least one dynamic effect the deployable estimator has no
term for. At that rate it carried a **constant offset** instead, which the
estimator absorbs into its intercept for free. The plant would have looked
richer than the others while being, in the only respect that mattered,
identical.

**Fix:** use `hysteresis_gamma = 60.0`, the value already declared by the prior
phase's `battery_multirc.py`. At 20 A that is a time constant near 12 s,
comparable to a probe window. This is a repository-backed value, not a number
chosen to make an effect appear; the check that it lands in a usable range is
an executable test, not a judgement.

**Test:** `tests/test_iv_plants.py::test_hysteresis_moves_within_a_probe_window`,
`::test_removing_hysteresis_is_detectable_on_q2`.

Found before any outcome was produced.

---

## IV-9 — The preregistered change metric cancels the plant almost entirely

**Found, in the development partition, before any campaign:** on matched
nominal/fault pairs driven by common random numbers, the paired change error is
the same to within a factor of two across Q0, Q1 and Q2 — median `|e_ΔR|` of
4e-6 ohm on all three — while the *point* error separates them cleanly: median
`AE_R` of 1.94e-4 (Q0), 6.57e-4 (Q1) and 5.06e-4 (Q2) ohm.

**Why.** The current trajectory in these plants is driven by command and lag,
not by terminal voltage, so a change in `R₀` does not change `I(t)`. Between a
matched pair every state is identical sample for sample and

```
V_fault(t) − V_nominal(t) = −ΔR₀ · I_true(t)
```

to floating point — verified at 1e-12. Least squares is linear in the response
and the regressor is shared, so

```
R̂_fault − R̂_nominal = ΔR₀ · cov(I_true, I_meas)/var(I_meas) = ΔR₀ · λ̂
```

Every plant-common nuisance — OCV curvature, both polarization branches,
hysteresis, self-heating, open-circuit drift, and the voltage-noise draw
itself — cancels exactly. What survives is only the finite-sample
errors-in-variables factor on the shared regressor. Measured: the ratio is
1.000946 for Δ = 0.002, 0.010 and 0.040 alike, and λ̂ computed directly from
the traces is 1.0009463544, agreeing to seven digits. The population value is
0.9998157; this particular noise draw happens to sit above one.

**Status:** not a defect, and **not repaired**. `e_ΔR` is the metric §5 of the
task defines and §2 of the preregistration froze, and it stays primary. But it
is now known to be near-blind to plant structure *by construction of the
paired design*, so:

* plant discrimination (H5) rests on the point metric `AE_R`, which was
  preregistered in §4.1 and does not cancel;
* any claim that "the richer plant did not change the outcome" must name which
  outcome, because for `e_ΔR` that is a theorem about the design and not a
  finding about the plant.

The cancellation is a property of this experimental design — common random
numbers, and a fault that does not move the current — not of the world. A
closed-loop fault that changed the current trajectory would break it.

**Tests:** `tests/test_iv_plants.py::test_a_fault_in_r0_changes_the_voltage_by_exactly_minus_delta_times_i`,
`::test_the_paired_change_error_is_exactly_the_finite_sample_eiv_factor`,
`::test_the_point_estimate_does_not_enjoy_that_cancellation`.

---

## IV-10 — I assumed a prefix of a palindrome carries more drift leverage. It does not.

**Believed, while drafting Proposition C:** truncating a palindromic probe
breaks its symmetry, so the realized drift lever of the prefix must be worse
than the full window's. That would make truncation at least *predictably* bad.

**Found:** measured across the executed fraction, the realized lever is
non-monotone and changes sign. Against a full-window lever of −0.02753 s:

| fraction | lever (s) | |
|---|---|---|
| 0.20 | −0.07692 | 2.8× worse |
| 0.25 | −0.09162 | 3.3× worse |
| 0.40 | **+0.02828** | sign flipped |
| 0.50 | +0.00193 | nearly vanishes |
| 0.75 | +0.03864 | |
| 0.90 | −0.04726 | |

The test written to confirm the belief failed at 0.5 and the belief was
replaced by the table. What survives, and is measured at every tested fraction,
is that `S_II` strictly drops — so truncation always costs excitation, and the
lever is not bounded in either direction.

**Status:** Proposition C is stated as "not conservative in either direction"
rather than "worse", which is what the data supports. Same shape as the prior
phase's finding that lag underestimation is not automatically conservative.

**Test:** `tests/test_iv_propositions.py::test_truncation_is_not_conservative_in_either_direction`.

---

## IV-11 — P7c is not robust under the metric it was given

**Found:** the robust model-envelope oracle, taking a minimax over all three
plants and all six magnitudes, selects **six different actions in six seeds**
under the preregistered change loss. Under the point loss it selects three
distinct actions in six seeds and converges on `cosine3_14A_8s`.

**Why:** the same mechanism as IV-9. The change loss is `|λ̂ − 1|·Δ` and `λ̂` is
a finite-sample quantity depending on the action and the current-noise draw.
Minimising it across an envelope minimises a noise realisation, so the
"robust" choice changes completely when the seed does.

**Status:** not a defect in P7c, which does exactly what it is specified to do.
It is a property of the objective it was handed. Recorded so that no reading of
the P7c results treats action selection under the change loss as a statement
about actions.
