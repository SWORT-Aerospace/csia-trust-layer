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

---

## IV-12 — I pushed with a red test. Again.

**What happened:** `tests/test_post_e1_hardening_round2.py::test_the_build_provenance_describes_this_checkout`
requires `research/physical_validation/results/BUILD_PROVENANCE.json` to name a
commit within the last three. It named `c3ee776`, the prior phase's final
bookkeeping commit. The moment this phase reached its second commit, `c3ee776`
fell out of the window and the test went red.

It stayed red through commits `8d7a625`, `45544bb`, `cfbfadd`, `f9e007c` and
`cbe90cb`, all of which were pushed.

**How it got past me:** I ran the full suite, but I read its progress dots while
it was still running, committed on the strength of targeted runs of the tests I
had just written, and never went back to the tail of the completed log. That is
the same mechanism as `RC-22` in the prior phase — where a shell pipeline
masked pytest's exit status — wearing different clothes. The lesson from RC-22
was "check the exit code", and I did capture the exit code this time; I simply
did not read it before committing.

**Fix:** `BUILD_PROVENANCE.json` regenerated with `--regenerate`, which the
tool requires and which demands the diff be explained. The diff is the `source`
block only: commit, `describe` string and dirty-path list. `declared`,
`frozen_core`, `host`, `installed`, `interpreter`, `schema` and
`undeclared_dependency_check` are byte-identical, which is what one would
expect from the same container an hour later.

**Process change:** the artifact has to be regenerated in the last commit of
any series, which is what the prior phase's `c3ee776` was for. And a full-suite
exit code that has not been *read* is not a full-suite run.

**Not amended away.** The five commits that carried the red test stay as they
are.

---

## IV-13 — My routing predicate made every case look like an unknown fault

**Found:** the first unknown-fault sweep counted a case as "routed to unknown"
when the certificate returned `UNKNOWN_OR_MODEL_MISMATCH` **or**
`MODEL_MISMATCH_LIMITED`. The second is the in-model "my error budget cannot
resolve this" answer, and at a 0.010 Ω target it is what a **no-fault** run
returns.

The result was a routing rate of 1.000 at every amplitude including zero, and a
"boundary" of 0.439 σ with **zero observations below it** — a number produced
entirely by the predicate.

**Compounding it:** the operating point was saturated. At 0.010 Ω this
command's union bound is 0.005161 against an allowed 0.005000, dominated by the
polarization term, so the certificate never certifies anything, fault or no
fault.

**Fix:** count `UNKNOWN_OR_MODEL_MISMATCH` only, and run at a 0.020 Ω target
where the no-fault case certifies — the operating point the prior phase's
ablation used. Both changed before the boundary was read.

**After the fix:** routing is 0.000 up to 0.15 V, 0.333 at 0.20 V, 0.667 at
0.30 and 0.40 V, 1.000 at 0.60 V, and the boundary is 3.363 σ with a rate of
0.901 above and **0.000 below**, over 426 and 870 trials.

**Test:** `tests/test_iv_openset.py::test_no_boundary_is_invented_when_the_data_has_none`
pins the estimator's refusal to produce a boundary the data does not contain.

---

## IV-14 — Dropout was disconnected, and its sensitivity of exactly zero looked like a finding

**Found:** the sensitivity audit reported `∂M_R^out/∂dropout = 0` exactly. The
harness passed the full measured arrays to the estimator, so samples the
telemetry layer had marked invalid were still being fitted. A 20% dropout
changed nothing because nothing was dropped.

This is the preregistered falsifier "sensing defects remain absent because the
evaluator forgot them", and for one parameter it was true.

**Fix:** the harness now uses `Observation.kept()`. Dropout registers at
−2.25e-5 on the outcome and −9.43e-4 on the certificate.

**Why it was not obvious:** four *other* parameters are also exactly zero, and
all four are correct — a constant voltage offset is absorbed by the intercept,
a constant current offset leaves the centred regressor alone, voltage noise
cancels in the paired difference, and the estimator never reads time so
timestamp jitter cannot reach it. A zero is not evidence of a bug and it is not
evidence of insensitivity. It is evidence of nothing until somebody derives it,
which is why every zero in `SENSITIVITY_AUDIT.md` now carries a derivation and
a test.

**Test:** `tests/test_iv_sensitivity.py::test_dropout_is_connected_which_it_was_not_at_first`,
plus one derivation test per exact zero.

---

## IV-15 — The benchmark that failed is the textbook optimal design

**Not a failure of mine, and worth recording as a correction to how the prior
result should be read.**

Inverting the Fisher matrix for `(E, R)` under `V = E − R·I + η` gives
`var(R) = σ_V²/S_II` exactly. So minimising the Cramér–Rao variance of the
resistance is *identically* maximising the centred second moment of current —
P7a's objective. Measured over the 72-action space, `argmin var(R)`,
`argmax S_II` and P7a's selection are the same action, `doublet_10A_8s`.

P7a loses to the hindsight oracle by a median factor of 11 while spending 2.4×
the energy.

**Consequence:** "the oracle was not an oracle" is a sharper claim than it
looked. The object that failed is the classical A-optimal design, and it failed
because the model it is optimal *for* is not the plant. Any write-up that
presents this as a design flaw in P7a is wrong; it is a model-mismatch result.

---

## IV-16 — One arena for the whole campaign meant every ceiling solved the wrong problem

**Found, while building the runner, before any campaign row existed:** the
first `Campaign` held a single `ceilings.Arena`, and `Arena` simulated with
default conditions — nominal drift, no ringing, nominal sensing — regardless of
the cell.

So under elevated drift, P0–P6 and S0–S3 ran in a drifting world while P7a,
P7b and P7c were computed in a quiet one. The ceiling invariant would still
have *passed*, because P7b was a valid argmin for the problem it was solving;
it would simply have been the wrong problem, and every regret number under
elevated drift would have been meaningless. Gate B would have reported green on
exactly the cells where it mattered most.

**Fix:** `Conditions` is now a first-class object, one arena per distinct
world, keyed by drift, ringing and the full sensing configuration.

**Test:** `tests/test_iv_runner.py::test_conditions_key_the_arena`,
`::test_ringing_and_sensing_also_key_the_arena`,
`::test_the_oracle_is_computed_under_the_cell_conditions`, and
`tests/test_iv_ceilings.py::test_the_invariant_holds_under_elevated_drift_too`.

**Also fixed alongside:** the arena cached the full observation and ground
truth for every (action, plant, seed). At campaign scale that is roughly 400 MB
of arrays nobody reads twice. Only the scalars the comparison needs are kept
now, and traces are stripped from cached truths.

---

## IV-17 — A clipped execution is not an incomplete one

**Found by a test, before the campaign ran:** the runner marked a clipped
execution `completed=False`. `certify` checks completeness before it checks
clipping, so every clipped row came back `ABORTED_INCOMPLETE` and the
`CLIPPED_CERTIFICATE_INVALID` path was never exercised at all.

A clipped action runs to the end of its window; what changed is the waveform
the authority allowed. Only an abort is incomplete. The fix is one line, and
the value is entirely in the two tests that now distinguish the cases —
without them the campaign would have reported an execution ablation in which
one of its three levels quietly did not exist.

---

## IV-18 — IV-12 recurred, because the fix was discipline rather than design

**What happened:** `BUILD_PROVENANCE.json` was regenerated at IV-7, went stale
again three commits later at IV-10d, and the full suite came back red on the
same assertion.

**Why:** the guard requires the recorded commit to be within three of `HEAD`.
The task's own commit protocol asks for twelve small scientific commits. Those
two requirements collide by construction, and "remember to regenerate at the
end" is not a fix, it is a hope. The first time it cost five commits pushed
red; the second time it cost one.

**What the record actually says:** `declared`, `frozen_core`, `host`,
`installed`, `interpreter`, `schema` and `undeclared_dependency_check` are
byte-identical across every regeneration this session. The only field that
moves is `source` — commit, describe string, dirty paths. So the artifact is
never describing a different *environment*; it is describing a different
*commit*, and the guard is measuring commit cadence.

**What was not done:** the guard was not widened. It exists because a probe
once silently overwrote exactly this file (FL-013), and loosening a real guard
because my workflow trips it is how guards stop meaning anything.

**Adopted instead:** regenerate immediately before every commit in this phase,
not at the end of the series. Twelve one-field diffs, each explainable in one
sentence, is the honest cost of a guard that works.

**Full suite at this point:** 3410 collected, 3409 passing before the
regeneration and 3410 after — the single failure was this and nothing else.

---

## IV-19 — The pre-action gate's safety half cannot fail, and I nearly shipped it that way

**Found immediately after implementing `GATE_PRE`:** every admissible action
has a peak excess of at most 14 A on a 20 A hover draw, so the worst predicted
current is 34 A against a declared limit of 56 A. **No admissible action can
fail the safety sub-gate.** It fails only for an abstention, where there is no
action to check.

This is the same shape as IV-1 — a check whose selected set is empty by
construction — arriving in a different place, two hundred commits later,
written by somebody who had just spent a day documenting IV-1.

**It is a property of the action space, not of the check.** `PEAK_EXCESS_LIMIT_A`
is 16 A and was frozen before any of this. The check itself works: a 45 A hold
fails it, and that positive control is a test.

**Not repaired by moving the margin.** Widening `CLIP_MARGIN_A` until the
sub-gate bites would be choosing a threshold to manufacture a result, and the
threshold has no independent justification at any value.

**Consequence, which now travels with every gate result:** the pre-action
gate's entire discriminating power comes from the **separation** sub-gate. Any
reading of the 2×2 table as evidence about pre-action *safety* screening is
unsupported here, and `RESULTS.md` says so where the table appears.

**Tests:** `tests/test_iv_gates.py::test_no_admissible_action_can_fail_the_safety_sub_gate`,
`::test_the_safety_check_itself_works`,
`::test_the_module_says_the_sub_gate_is_vacuous` — the last one fails if
somebody deletes the caveat from the source.

---

## IV-20 — The volume surrogate cannot distinguish touching from separated

**Not my defect, and not the paper's either — a property of the objective**,
flagged by the supplied related-work draft and confirmed here as an executable
counterexample.

The pairwise objective minimises intersection **volume**. For `[0, 1]` and
`[1, 2]` the intersection is `{1}`: measure zero, and **not empty**. A baseline
that reads zero volume as separation calls those two hypotheses
distinguishable when they are not.

So `PairOutcome` reports three fields and never collapses them: `zero_volume`,
`empty_intersection` (strictly apart), and the signed `separation_margin`. The
gate requires `empty_intersection`, not `zero_volume`. Hausdorff distance is
reported beside the volume because it separates the two cases the volume
cannot: 1.0 for the touching pair, 5.0 for a far one.

**Test:** `tests/test_iv_discrimination.py::test_touching_sets_have_zero_volume_and_a_non_empty_intersection`
and `::test_the_volume_surrogate_cannot_tell_those_two_cases_apart`.

---

## IV-21 — The preregistered combined claim is rejected: the pre-action gate is redundant here

**The claim, as preregistered verbatim in `PREREGISTRATION_AMENDMENT_3.md` §4:**

> accepting an inference only when both the pre-action separation/safety gate
> and the post-action RCEC gate pass reduces false accepted inferences relative
> to **either** gate alone

**Measured on validation, 12 960 main-block cells, point metric:**

| | post fails | post passes |
|---|---|---|
| **pre fails** | n = 5473, wrong 1934 | **n = 0** |
| **pre passes** | n = 5083, wrong 892 | n = 2404, wrong **0** |

The `pre=False / post=True` cell is **empty**. Every cell that passes the
post-action gate already passes the pre-action gate, so the post gate's
accepted set is strictly contained in the pre gate's.

| policy | accepted | coverage | false accepted | rate |
|---|---|---|---|---|
| accept always | 12 960 | 1.000 | 2826 | 0.2181 |
| accept if pre | 7 487 | 0.578 | 892 | 0.1191 |
| accept if post | 2 404 | 0.186 | **0** | **0.0000** |
| accept if both | 2 404 | 0.186 | **0** | **0.0000** |

`accept_if_both` is **identical to `accept_if_post`**, cell for cell.

**Verdict: the combined claim is REJECTED as stated.** Requiring both gates
beats the pre gate alone — 892 false acceptances down to zero — and does not
beat the post gate alone, which already had zero. Within this envelope the
pre-action separation gate is **redundant** given the post-action gate.

This is one of the two negative outcomes Amendment 3 named in advance, in those
words: *"If `GATE_PRE` prevents no unsafe or non-separating action, the
reachability layer is redundant within this envelope."* It is reported as the
result, not as a disappointment.

**What it does not show.** Not that pre-action reachability analysis is
redundant in general. The pre-gate here is an interval over-approximation over
an enumerated envelope with a **safety half that cannot fail** (IV-19), on a
one-output battery model where the post-action certificate is unusually strong.
A pre-action gate that could reject on safety, on a plant where it could bite,
is a different object and this result says nothing about it.

**The other half is a strong positive.** The post-action gate accepted 2404
inferences and got **zero** of them wrong on both metrics, at a coverage cost
of 39.2 percentage points against the pre gate alone. Unlike the prior phase's
"zero false certificates", this count comes from a check that can be non-empty
and was measured against simulator truth.

---

## IV-22 — The touching case is not hypothetical: it occurs 48 times

**Found in the gate table:** across 12 960 cells, the predicted output sets are
`zero_volume` and **not** `empty_intersection` — touching, not separated — in
**48** of them.

A baseline reporting only intersection volume would have scored those 48 cells
as separated hypotheses. They are not: the intersection is non-empty and the
separation margin is exactly zero.

The counterexample in `tests/test_iv_discrimination.py` was constructed by
hand to make the distinction visible. It turns out not to have needed the
construction — the distinction the supplied related-work draft insists on has a
measurable frequency in this experiment, and it is 0.37% of cells.

---

## IV-23 — I wrote a checksum manifest and never read it, and it was already wrong

**Found by writing the test that reads it**, which should have existed from the
moment the manifest did.

`tools/research/iv_manifest.py` writes `RAW_CHECKSUMS.sha256`. No test, tool,
guard or CI step had ever checked a single line of it. On the first run of the
new verifier, **two entries were already wrong**:

1. `EXTERNAL_ACCESS_CHECK.json` had been amended — the roadmap's §15 note about
   the primary text being accessible elsewhere — and the manifest was never
   regenerated, so its pinned digest had been stale since that commit;
2. `ZERO_EVENT_BOUND_VALIDATION.json` was committed as a tracked raw artifact
   and was **not listed at all**, so nothing would ever have checked it.

**This is IV-1 and IV-19 a third time, and this time I built it.** IV-1 was a
check whose selected set was empty by construction. IV-19 was a gate half that
could not fail over its action space. This is a manifest nobody runs, which is
not weaker than a manifest that always fails — it is the same thing.

I spent this session documenting that pattern and then shipped a fresh instance
of it four commits later.

**Fix:** `tests/test_iv_integrity.py` reads both directions. Every pinned
artifact must still match its digest, and every *tracked* raw artifact must be
pinned — because a manifest that silently omits a file is the other way for
this to stop meaning anything. It also verifies the prior phase's locked
campaign against the digest `BASE_PROVENANCE.json` records for it, which was
likewise recorded and never compared: every §1 verification in this phase was
performed against that 13 MB file and nothing confirmed it was the same file.

**Not repaired:** the prior phase's own stale manifest. A test now pins it at
exactly nine documented failures, so its staleness is a checked fact rather
than a known-ignored red, and asserts that its immutable raw JSON entry still
verifies — which is the part that matters.
