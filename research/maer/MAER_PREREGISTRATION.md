# MAER — Preregistration

**Status: PREREGISTRATION. Committed before any scored trial.**
Nothing in the scored matrix has been run. No arm has been implemented.

Everything below is frozen on commit. Any later change creates MAER_V2 and
requires a new preregistration.

---

## 1. Research question

> Do diagnostic failure mechanisms that remove available evidence require
> different mitigations from mechanisms that preserve evidence but delay its
> accumulation?

Subquestion:

> Can fault-relevant receiver-health evidence remain available after the
> navigation-validity gate closes, yet become unusable solely because of its
> placement behind that gate?

## 2. What this study is not

- Not a physical-GNSS result. Every observation is simulator-generated.
  `h_acc` under jamming is `fabsf(rand_float()) * 300` in ArduPilot SITL.
- Not a novelty claim. CUSUM, analytical redundancy, active FDI, abstention and
  transport-aware diagnosis are all prior art.
- Not a claim about early warning. Measured lead time in qualification was
  **−1.4 s**; health degradation followed fix loss. No early-warning hypothesis
  is preregistered, and fault parameters must not be altered to manufacture one.

## 3. Candidate — FROZEN

`GPS_RAW_INT.h_acc`, ArduPilot, ingested by a research-only sidecar. **`h_acc`
only.** `v_acc`, `vel_acc` and `satellites_visible` are alternates, not
ensemble members, and may be substituted only if `h_acc` fails a validity
criterion in §10 — never added to it.

Interpretation, per Stage 0.5: `h_acc` is a
**SIMULATED_RECEIVER_HEALTH_OBSERVABLE / STOCHASTIC_FAULT_MODEL_OUTPUT**. It is
not a physical receiver measurement and not a direct gate duplicate in the
evaluated ArduPilot model.

The production adapter discards it (early return on `fix_type < 3`,
`csia/aircraft/adapters/ardupilot.py`). The frozen core is not modified.

## 4. Transform — FROZEN

The Stage 0.5 MAD-floor form is **withdrawn**: clean SITL `h_acc` is constant,
so `MAD ≈ 0`, and `max(MAD, 1e-3)` is an arbitrary gain that would let the
research arm win by numerical scaling.

```
h0    = 300 mm                                   # SIM_GPS1_ACC (0.3 m) x 1000
resid = log(1 + max(0, h_acc - h0) / h0)
sigma = log(2) = 0.693147
lam   = EWMA_0.15( (resid / sigma)^2 )
```

`lam` is then consumed exactly as every other relation is, through
`consistency(lam) = exp(-0.5 * max(0, lam - 1))`.

Why each constant:

| constant | value | why, and why not otherwise |
|---|---|---|
| `h0` | 300 mm | the **declared** nominal receiver accuracy of the configuration under test, read from `SIM_GPS1_ACC`. Not estimated from any trace, clean or faulted. |
| form | one-sided log | better-than-nominal accuracy is not a fault, so the residual is zero below `h0`; logarithmic because `h_acc` spans three decades. |
| `sigma` | `log 2` | **one doubling of excess error over nominal is one sigma.** An engineering statement about what counts as meaningful degradation, fixed in advance. No fault separation was consulted. |
| `EWMA 0.15` | 0.15 | the smoother `_lam_upd` already uses. Not a new choice. |

**Known property, declared now rather than discovered later:** the contribution
saturates. `consistency` falls below 0.01 at `lam ≈ 10.2`, i.e. `h_acc ≈ 2.8x`
nominal. Under heavy jamming the contribution therefore behaves as a strong
near-binary indicator and is graded only near the threshold. This is a
consequence of the declared sigma and is **not** to be retuned after seeing
scored results.

## 5. Scale compatibility — audited

`MAER_EVIDENCE_SCALE_AUDIT.json`. Measured in the layer's own bounded space:

| distribution (consistency, (0,1]) | p50 | mean |
|---|---|---|
| existing layer, clean flights | 1.0 | 0.919 |
| existing layer, fault flights | 1.0 | 0.918 |
| proposed `h_acc`, clean phase | 1.0 | 1.000 |
| proposed `h_acc`, jam invalid-fix | 0.0 | 0.102 |

The contribution cannot dominate by unit choice: `consistency` is bounded in
(0,1] by construction, which is a structural guarantee rather than a tuned one.
It is quiet on clean data and moves on fault. No scored outcome was consulted.

## 6. Realisation independence — RESOLVED

Stage 0.5's five runs were byte-identical and count as **one** realisation.

No seed mechanism exists in ArduPilot: `get_random16()`
(`AP_Math.cpp:350`) uses hard-coded statics `m_z=1234, m_w=76542` and is never
reseeded; `rand_float()` on SITL calls libc `random()`, and ArduPilot never
calls `srandom()`; there is no `SIM_` seed parameter.

**Mechanism adopted: vary the jam onset time.** The generators are consumed
continuously by other SITL users, so the generator state at jam onset is a
function of elapsed runtime. Changing onset changes that state **without
modifying any simulator source and without touching the jamming
distribution**. No simulator patch was required.

Verified: 10 onsets (8, 11, 14, 17, 20, 23, 26, 29, 32, 35 s) produced
**10 / 10 distinct** SHA-256 signatures over the
`(fix_type, satellites_visible, h_acc)` jam sequence, each with invalid-fix
ticks present and `h_acc` live (27–37 distinct values).
`MAER_TRAJECTORY_DISTINCTNESS.json`.

**Preregistered trajectory set:** those 10 onsets, in that order, are the
trajectory generator for Experiment B. Trajectories are re-generated at scoring
time by the same procedure; a run whose signature duplicates another is
discarded and the next onset in a preregistered extension list
(38, 41, 44, 47, 50 s) is used.

## 7. Two experiments, deliberately separated

### Experiment A — deterministic matched-trace causal test

The **same recorded trajectory** is replayed through A1 and A1G. Its supported
claim is narrow and is the only claim it may be used for:

> For the exact evaluated input trajectory, gate placement alone changes
> whether the receiver-health contribution remains available after validity
> closure.

**No population statistics are reported from Experiment A.** Independent
realisations are not required for this claim, because the comparison is within
a single fixed input.

### Experiment B — multi-realisation robustness

Does the gate-placement effect survive across genuinely different jamming
trajectories? Uses the 10 distinct trajectories of §6.

## 8. Hypotheses — FROZEN

**H1 (causal architectural).** Given a receiver-health residual that remains
live during periods of invalid GNSS navigation solution, placing that same
residual outside `gvalid` retains a nonzero diagnostic contribution during
those periods, whereas multiplying the identical residual by `gvalid`
suppresses it.

**H1b (empirical diagnostic performance).** The ungated arm improves
`gps_fault` attribution relative to the matched gated control, without
violating the clean false-transition budget.

**H1 and H1b are separate. H1 may succeed while H1b fails**, and that outcome
must be reported as such rather than merged.

**H2 (temporal specificity).** Under M2, A2 responds earlier than A0 without
exceeding the clean budget.

**H3 (non-substitutability).** A2 does not recover `gps_fault` support under
M1. **If CUSUM does recover it, H3 is refuted and that is the result.**

**H4 (evidence-cause discrimination).** The runtime distinguishes
`STARVED_BY_TRANSPORT` from `EVIDENCE_GATE_CLOSED` using only
source/delivery/freshness/gate state. **No injected-fault label may be an input
to the classifier.**

**H5 (combined).** A3 achieves A1's M1 behaviour and A2's M2 behaviour without
exceeding the clean budget.

No early-warning hypothesis is preregistered (§2).

## 9. Arms — FROZEN

```
A0   BASELINE                  frozen core at csia-v1.0-research-final
A1   RECEIVER_HEALTH_UNGATED   contribution x 1
A1G  RECEIVER_HEALTH_GATED     contribution x gvalid
A2   CUSUM                     frozen B4: S = max(0, S + z - 0.5), alarm S > 500,
                               mu0/sigma0 from the clean arm only, read-only on _lam
A3   MECHANISM_AWARE_COMBINED  A1 + A2 + evidence-cause classification
```

The gate-event Bayesian likelihood arm is **removed** and stays removed: only
two fix-loss flights exist, so no calibration/test split is possible, and an
undercalibrated arm would contaminate the causal comparison.

**Exact A1 / A1G difference.** One parameterised factor, one code path:

```python
# research sidecar; frozen core untouched
lam  = ewma.update((residual(h_acc) / SIGMA) ** 2)
gate = 1.0 if arm == "A1" else gvalid          # THE ONLY DIFFERENCE
contribution = (lam, gate)
```

Identical input, samples, transform, calibration constants, evidence mapping,
hypothesis association, temporal filter and normalization. A test must assert
that A1 and A1G resolve to the same code path with only `gate` differing; if
any other difference exists, the causal interpretation **fails** and the run is
void.

## 10. Validity criteria

A trial counts only if:

1. **RULE B**: the declared downstream observable is present — for M1, at least
   one message with `fix_type < 3` and `h_acc` taking more than one distinct
   value during that period.
2. The injection readback confirms.
3. The trajectory signature is distinct from every other scored trajectory in
   the same cell.

`h_acc` fails as a candidate, and an alternate from §3 is substituted, only if
criterion 1 cannot be met on a majority of M1 trials.

## 11. Conditions — FROZEN

```
M0  CLEAN                    no injection
M1  ARDUPILOT_JAM            SIM_GPS1_JAM = 1, onset per §6
M2  PERSISTENCE RAMP         fix-preserving GNSS position ramp (ArduPilot)
M3  PX4_TRANSPORT_STARVATION passive vs requested PX4 link
```

M1 is **jamming**, which is a different fault from the `SIM_GPS1_ENABLE=0`
fix-loss used in Mechanism A. What transfers is the *candidate family*, not the
physics. This is stated, not assumed.

## 12. Matrix — FROZEN

5 repetitions per applicable cell.

| | M0 | M1 | M2 | M3 |
|---|---|---|---|---|
| A0 | 5 | 5 | 5 | 5 |
| A1 | 5 | 5 | 5 | INAPPLICABLE |
| A1G | 5 | 5 | 5 | INAPPLICABLE |
| A2 | 5 | 5 | 5 | 5 |
| A3 | 5 | 5 | 5 | 5 |

= **90 scored trials.** A1/A1G × M3 are INAPPLICABLE because M3 runs on PX4,
where every receiver-health candidate is a `DIRECT_ORACLE` and rejected.
Marked, not manufactured.

## 13. Endpoints

**Primary — causal availability (H1).** Share of `gvalid = 0` ticks on which
the receiver-health contribution is nonzero, A1 vs A1G, on identical traces.

**Primary — diagnostic performance (H1b).** Share of post-onset ticks on which
`gps_fault` is the top hypothesis, A1 vs A1G vs A0.

**Secondary.** `gps_fault` rank; unique-attribution share; unsupported-normal
exposure; time to first correct attribution; ambiguity duration; clean
transition count; runtime cost per tick.

Contribution survival is **not** synonymous with correct diagnosis, and the two
are reported separately.

## 14. Clean budget — pass/fail

**No assurance transition on any M0 trial, for any arm.** An arm producing one
or more clean transitions **fails**, regardless of fault performance. This is
the applicable R10 criterion and is fixed here.

## 15. Outcome hierarchy

`CORRECT_UNIQUE_ATTRIBUTION` > `SAFE_AMBIGUITY` >
`EVIDENCE_UNAVAILABLE_CORRECTLY_DECLARED` > `WRONG_ATTRIBUTION` >
`UNSUPPORTED_NORMAL`. Ambiguity is reported separately and never counted as
correct diagnosis.

## 16. Analysis plan

With 5 per cell, the primary reading is **deterministic implementation
behaviour under declared simulator conditions**, not population inference.
Report counts, paired differences on matched traces, effect sizes and timing
distributions. Exact tests only where their assumptions hold. No p-value
fishing; no subgroup search.

## 17. Invalid trials and replacement

A run is invalid only for declared mechanical reasons: simulator crash, no
heartbeat, injection readback failure, or duplicate trajectory signature.
Replacement draws the next onset from the §6 extension list. **No trial may be
excluded for its outcome.** Every rejection is recorded with its reason.

## 18. No adaptive tuning

Once the first scored trial runs, every parameter above is frozen: thresholds,
`h0`, `sigma`, the EWMA constant, CUSUM `k` and `h`, gate logic, trajectory
set. Any change creates MAER_V2 with a new preregistration and a new campaign.

## 19. Known limitations carried into the result

1. Simulation-bound. No physical receiver data exists.
2. The structural arm is ArduPilot-only; PX4 cannot host it.
3. M1 is jamming, not the original fix-loss fault.
4. The contribution saturates above ≈2.8× nominal `h_acc` (§4).
5. Candidate selection was exploratory (Stage 0.5) and is not itself
   preregistered; only its use from here is.
6. Trajectory variation comes from onset timing, not a true seed. The
   distribution is untouched, but the realisations are not i.i.d. draws in a
   formal sense.
