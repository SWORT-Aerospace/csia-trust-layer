# MAER — Final Freeze Report (Stage 1.1)

Self-contained. **No scored trial has been run.** All five Stage 1.1
corrections are applied; one of them changed the experiment's headline framing.

---

## 1. Corrected saturation derivation

The Stage 1 report stated saturation at `h_acc ≈ 2.8×` nominal. **That was
wrong, and it was asserted rather than derived.**

```
consistency(lam) = exp(-0.5 * max(0, lam - 1))

set consistency = 0.01:
    exp(-0.5 (lam - 1)) = 0.01
    -0.5 (lam - 1)      = -ln 100
    lam                 = 1 + 2 ln 100 = 10.21034037

with u = log(h_acc/h0)/kappa_h, kappa_h = log 2, and lam = u^2 at steady state:
    u          = sqrt(lam) = 3.19536
    h_acc / h0 = 2 ** sqrt(lam) = 9.1601        (2748 mm at h0 = 300 mm)
```

**9.16×, not 2.8×.** The likely source of the error: 2.9176× is the ratio at
consistency **0.5**, and the two were conflated. At 2.8× the consistency is
0.547, not 0.01.

Worked points from the canonical module:

| `h_acc` (mm) | `h_acc/h0` | `lam` | `consistency` |
|---|---|---|---|
| 300 | 1.00 | 0.0000 | 1.000000 |
| 600 | 2.00 | 1.0000 | 1.000000 |
| 875 | 2.92 | 2.3849 | 0.500342 |
| 2748 | 9.16 | 10.2102 | 0.010000 |
| 300000 | 1000 | 99.3169 | ~0 |

**Automated test:** `tests/test_maer_hacc_transform.py` executes the derivation
on every run, round-trips ratio → consistency for 0.5 / 0.1 / 0.01, and fails
if any value in (2.7, 2.9) reappears as the 0.01 threshold. 13 tests, all
passing.

## 2. Stale-claim search result

Repository-wide search for the 2.8× figure. Three live sites found, all fixed:

| file | disposition |
|---|---|
| `MAER_PREREGISTRATION.md` | rewritten (v2) with the corrected derivation |
| `MAER_PREREGISTRATION_REVIEW_REPORT.md` | marked **SUPERSEDED** with a banner listing all four corrections; the one numeric mention annotated |
| `maer_evidence_scale_audit.py` | `saturation_note` replaced by a computed `saturation` block carrying the correction |

Remaining textual occurrences are explicit statements *of* the correction. Raw
capture files contain `2.8…` only as `t_rel` timestamps.

## 3. Final `h_acc` equation

Canonical definition in `research/maer/maer_hacc_transform.py`, imported by the
audits, the tests and the sidecar so the three cannot drift.

```
valid(msg) iff  h_acc present
            and h_acc != 0xFFFFFFFF
            and h_acc > 0
            and eph  != 0xFFFF
            and satellites_visible > 0

u_t   = max(0, log(h_acc_t / h0)) / kappa_h        h0 = 300 mm, kappa_h = log 2
lam_t = EWMA_0.15( u_t^2 )                         invalid samples skipped entirely
c_t   = exp(-0.5 * max(0, lam_t - 1))
```

## 4. Final interpretation of `kappa_h`

**`kappa_h` is a declared LOG SCALE, not a standard deviation.**

> One doubling of reported horizontal uncertainty above nominal equals one
> normalized degradation unit.

Renamed from `sigma`, which implied an empirical spread that was never
estimated and that the data cannot support: clean SITL `h_acc` is a constant
(300 mm), so it has no spread to estimate. That is the same degeneracy that
killed the Stage 0.5 MAD form; calling the replacement `sigma` carried the
implication forward under a different name.

Neither `h0` nor `kappa_h` may be influenced by any fault outcome. `h0` is read
from `SIM_GPS1_ACC`.

## 5. Full downstream score-influence calculation

Traced from the frozen source, `csia/diagnosis/bayes.py::DiagnosisCore.step`:

```
per feature, gate-weighted:
    in the cause's low-set : ll += gate * log(1 - c + EPS)
    otherwise              : ll += gate * log(c + EPS)
smoothed = (1 - SMOOTH_ALPHA) * smoothed + SMOOTH_ALPHA * ll
score    = log_prior + EVIDENCE_MULT * smoothed
post     = softmax(score)

EPS 0.02   SMOOTH_ALPHA 0.06   EVIDENCE_MULT 1.5   PRIOR_NOMINAL 0.86
8 causes -> prior_other = 0.02
```

For **one** added relation in `gps_fault`'s low-set, at gate 1:

| quantity | value |
|---|---|
| per-tick pairwise correction, `c = 0` | **+3.931826** |
| per-tick pairwise correction, `c = 1` | −3.931826 |
| bound | `log((1+EPS)/EPS)` = 3.931826 |
| × `EVIDENCE_MULT`, steady state | **+5.897738** |
| `log_prior(nominal)` | −0.150823 |
| `log_prior(gps_fault)` | −3.912023 |
| prior barrier | **+3.761200** |
| **net margin** | **+2.136538** |
| ticks to 90 % of steady state | 37.2 (≈1.5 s at 25 Hz) |

**One sustained saturated relation alone puts `gps_fault` above `nominal`, with
no other evidence present.**

Effect of EPS/clipping: `EPS` is what bounds the correction. Without it,
`log(c)` → −∞ as `c` → 0 and a single relation would carry unbounded weight.
With `EPS = 0.02` the bound is ±3.93 **for every relation in the layer**.

## 6. Verdict

**`DETECTOR_DOMINANT_BUT_DECLARED`.**

Not `INVALID_SCALING`: the per-relation bound is identical for every existing
relation, so `h_acc` is not privileged by its units, and the transform is not
the cause. The dominance follows from the **frozen diagnosis design** — a
single-feature cause (`CAUSES["gps_fault"] == ["phys_gps"]`) plus an `EPS`
floor. Any saturated relation in that low-set would do the same.

**This changes the experiment's framing and is declared before scoring.** H1's
*direction* is close to structurally implied once the relation is live and
degraded. The informative content sits in **H2's crossover**, and in magnitude
and timing, not in the sign of H1. Reporting H1 as a discovery would overstate
it.

The Stage 1 claim — "consistency is bounded in (0,1], therefore the relation
cannot dominate diagnosis by unit choice" — is **withdrawn**. Bounding the input
to the likelihood mapping does not bound the pairwise log-score correction,
which is what decides ranking.

## 7. `h_acc` validity / sentinel rules

`h_acc = 0` through the transform gives `max(0, log 0) = 0`, hence `lam = 0` and
`consistency = 1.0` — a receiver reporting nothing scoring as **perfectly
healthy**. The committed captures contain two zero populations:

| signature | count | nature |
|---|---|---|
| `fix_type 0, sats 0, eph 65535, v_acc 0` | 870 | pre-lock |
| `fix_type 1, sats 3, **eph 121**, v_acc 0` | 30 | early acquisition |

The second has a **valid** `eph` and a **non-zero** satellite count, so only the
`h_acc <= 0` clause rejects it — the clause is load-bearing, not redundant. A
test asserts both populations exist and that neither passes the predicate.

Invalid samples contribute nothing **and do not update the smoother**. 900 of
10,163 capture samples are rejected. Applying the predicate reduced the
clean-phase distribution from n=3163 to n=2263 — the 900 removed were being
scored as consistency 1.0.

## 8. Exact paired-scenario design

The onset-varied runs are **DISTINCT PREREGISTERED DETERMINISTIC SIMULATOR
SCENARIOS**, not i.i.d. repetitions. Onset changes global simulator/RNG history
and may change pre-fault internal state. **No random-sample population inference
is claimed.**

Every arm consumes the **same** scenario: for scenario *i*, A0ᵢ, A1ᵢ, A1Gᵢ, A2ᵢ,
A3ᵢ see the same captured trajectory. **A1 vs A1G is within-scenario.** Reported
as scenario-level outcomes, paired differences and counts. An unpaired analysis
is not used where a paired one is available.

A fixed-onset RNG seed hook is recorded as an **optional robustness extension**,
not a requirement.

## 9. Final MC1

> For the same `h_acc` trajectory, A1 retains the receiver-health contribution
> on `gvalid = 0` ticks and A1G suppresses that identical contribution.

**A manipulation check, not a finding. Failure invalidates the experiment.**
This is the old H1, correctly demoted: "multiplying by zero removes evidence"
is arithmetic.

## 10. Final H1

> A1 improves `gps_fault` attribution relative to **both** A1G and A0 during the
> declared jam / fix-invalid windows, without violating the clean budget.

Endpoints: `gps_fault` top-rank share; unsupported-normal exposure; time to
useful attribution; unique attribution and ambiguity where defined.

Carried with it, per §6: the direction is close to structurally implied.

## 11. Final H2 crossover equation

```
D(arm, M) = t_response(A0, M) - t_response(arm, M)        positive = faster

crossover holds iff BOTH:
    D(A1, M1) > D(A2, M1)
    D(A2, M2) > D(A1, M2)
```

Evaluated per scenario and reported as counts plus paired differences. **If the
crossover does not hold, H2 is REFUTED and reported as refuted.** It must not be
reinterpreted.

## 12. Exact primary metric for H2

**Time to useful response**, seconds after onset, **right-censored at the window
end**:

- **M1**: first tick at which `gps_fault` is top-ranked after onset.
- **M2**: first tick at which the assurance threshold is crossed after onset.
- No response ⇒ value = window length, recorded and reported **as censored**.

Chosen because it applies to both arms on both mechanisms: a detector arm (A2)
changes *when* a response occurs, not the hypothesis ranking, so a rank-only
metric could not compare A1 against A2 on M2. Declared here, before scoring.

## 13. Same-platform ArduPilot transport feasibility

**FEASIBLE, and adopted. The platform confound is removed.**

Measured on stock ArduPilot, requesting `GPS_RAW_INT` on the consumer link:

| requested | measured |
|---|---|
| 5 Hz | 5.05 Hz |
| 0.5 Hz | 0.50 Hz |
| starvation ratio | **10.1×** |

Same platform, same message, same physically-generated receiver data, same
freshness semantics; only delivery is reduced. No modification to the autopilot
or the frozen CSIA core, and no physical-fault label involved.

M3 therefore becomes `ARDUPILOT_TRANSPORT_STARVE` rather than the PX4 condition.
**The preregistration does not need to declare transport confounded with
platform.**

## 14. Final experiment matrix

5 scenarios per cell, paired per §8.

| | M0 CLEAN | M1 JAM | M2 RAMP | M3 TRANSPORT |
|---|---|---|---|---|
| A0 BASELINE | 5 | 5 | 5 | 5 |
| A1 RECEIVER_HEALTH_UNGATED | 5 | 5 | 5 | 5 |
| A1G RECEIVER_HEALTH_GATED | 5 | 5 | 5 | 5 |
| A2 CUSUM | 5 | 5 | 5 | 5 |
| A3 MECHANISM_AWARE_COMBINED | 5 | 5 | 5 | 5 |

**100 scored trials**, 20 scenarios × 5 arms. **No INAPPLICABLE cells** now that
M3 is same-platform — an improvement on the Stage 1 matrix, which had two.

The gate-event Bayesian likelihood arm remains removed.

## 15. Valid N / scenario count plan

- 20 scenarios: 5 per mechanism, drawn from the 10 verified-distinct onsets
  (8, 11, 14, 17, 20, 23, 26, 29, 32, 35 s), extended by (38, 41, 44, 47, 50 s)
  on replacement.
- Each scenario is consumed by all 5 arms ⇒ 100 trials.
- A trial is valid only if RULE B holds (for M1: ≥1 message at `fix_type < 3`
  with a predicate-valid `h_acc` taking >1 distinct value), readback confirms,
  and the scenario signature is distinct.
- Invalid only for declared mechanical reasons. **No trial excluded for its
  outcome.**

## 16. Updated preregistration commit

`research/maer/MAER_PREREGISTRATION.md` (v2), committed **before any scored
trial**. Commit hash in §17 of the terminal summary accompanying this report.

## 17. Remaining scientific blockers

None that block running. Limitations to carry into any result:

1. **Simulation-bound.** No physical receiver data.
2. **Structural arm is ArduPilot-only.** PX4 rejected every candidate as
   `DIRECT_ORACLE`, so H1 is not cross-platform replicated.
3. **M1 is jamming**, not the original fix-loss fault. The candidate family
   transfers; the physics do not.
4. **Scenarios are distinct but not i.i.d.** Onset timing is not a seed.
5. **Saturation above 9.16× nominal** — near-binary under heavy jamming.
6. **`DETECTOR_DOMINANT_BUT_DECLARED`** — one saturated relation flips the
   ranking, so H1's direction is close to structurally implied. This is the most
   important limitation to carry, and it is a property of the frozen diagnosis
   design rather than of the candidate.
7. **Candidate selection was exploratory** (Stage 0.5) and is not itself
   preregistered.

## 18. Final verdict

**`READY_FOR_SCORED_MAER`** — campaign deliberately not started.

The Stage 1.1 gate conditions are all satisfied:

| condition | status |
|---|---|
| saturation arithmetic mismatch | **resolved** — 9.16×, derived and unit-tested |
| `INVALID_SCALING` | **no** — `DETECTOR_DOMINANT_BUT_DECLARED` |
| A1/A1G differ anywhere besides gate placement | **no** — one parameterised factor, one code path, test-enforced |
| `h_acc` validity semantics unresolved | **resolved** — predicate frozen, two zero populations characterised |
| primary crossover metric undefined | **resolved** — time to useful response, censored, declared |
| scenario pairing cannot be guaranteed | **resolved** — 10/10 distinct scenarios, paired design mandatory |

The one judgement a reviewer should press on: **`DETECTOR_DOMINANT_BUT_DECLARED`
is being accepted rather than fixed.** The alternative would be to widen
`gps_fault`'s evidence set or lower `EVIDENCE_MULT`, and both would modify the
frozen core, which this study may not do. Accepting it means H1 is a weak test
and H2 carries the result. If that trade is wrong, it is wrong *now*, before
100 trials are spent on it.
