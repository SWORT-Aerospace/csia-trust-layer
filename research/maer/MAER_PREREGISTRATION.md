# MAER — Preregistration (v2, Stage 1.1 corrections applied)

**Status: PREREGISTRATION. Committed before any scored trial.**
Nothing in the scored matrix has been run. No arm has been implemented.

Everything below is frozen on commit. Any later change creates MAER_V3 and
requires a new preregistration.

---

## 1. Research question

> When fault-relevant receiver-health evidence remains observable after
> navigation validity changes, does preserving that evidence outside the
> validity gate improve attribution, and is this mitigation specific to an
> evidence-suppression failure rather than an evidence-accumulation failure?

No novelty claim. No "first", "novel" or "unprecedented".

## 2. What this study is not

- Not a physical-GNSS result. `h_acc` under jamming is
  `fabsf(rand_float()) * 300` in ArduPilot SITL: a
  `SIMULATED_RECEIVER_HEALTH_OBSERVABLE / STOCHASTIC_FAULT_MODEL_OUTPUT`.
- Not an early-warning study. Qualification measured lead time **−1.4 s**;
  health degradation followed fix loss. Fault parameters must not be altered
  to manufacture a lead.
- Not a claim that "multiplying by zero removes evidence". That arithmetic is
  a manipulation check (MC1), not a finding.

## 3. Candidate — FROZEN

`GPS_RAW_INT.h_acc`, ArduPilot, ingested by a research-only sidecar.
**`h_acc` only.** `v_acc`, `vel_acc` and `satellites_visible` are alternates,
substituted only if `h_acc` fails §10, never added to it.

The production adapter discards it (early return on `fix_type < 3`). The frozen
core is not modified.

## 4. Transform — FROZEN

Canonical definition: `research/maer/maer_hacc_transform.py`, imported by the
audits, the tests and the sidecar so the three cannot drift.

```
u_t   = max(0, log(h_acc_t / h0)) / kappa_h
lam_t = EWMA_0.15( u_t^2 )
c_t   = consistency(lam_t) = exp(-0.5 * max(0, lam_t - 1))
```

| constant | value | what it is |
|---|---|---|
| `h0` | 300 mm | `SIM_GPS1_ACC` (0.3 m) × 1000 — the **declared** nominal receiver accuracy of the configuration under test. Not estimated from any trace. |
| `kappa_h` | `log 2` | A **declared log scale, not a standard deviation.** One doubling of reported horizontal uncertainty above nominal is one normalized degradation unit. The earlier name `sigma` implied an empirical spread that was never estimated and that the data cannot support — clean SITL `h_acc` is constant. |
| EWMA α | 0.15 | the constant `_lam_upd` already uses. |

### 4.1 Saturation — corrected

An earlier report stated saturation at `h_acc ≈ 2.8×` nominal. **That was
wrong**, and asserted rather than derived. Solved:

```
consistency = exp(-0.5(lam - 1)) = 0.01
  => lam = 1 + 2 ln 100 = 10.21034037
  => h_acc / h0 = 2 ** sqrt(lam) = 9.1601        (2748 mm at h0 = 300)
```

2.9176× is the ratio near consistency **0.5**, which is the likely source of
the error. Worked points, from the canonical module:

| `h_acc` (mm) | `lam` | `consistency` |
|---|---|---|
| 300 | 0.0000 | 1.000000 |
| 600 | 1.0000 | 1.000000 |
| 875 | 2.3849 | 0.500342 |
| 2748 | 10.2102 | 0.010000 |
| 300000 | 99.3169 | ~0 |

Executed on every test run by `tests/test_maer_hacc_transform.py`, which also
fails if the 2.8× figure reappears.

### 4.2 Validity predicate — FROZEN

`h_acc = 0` is **not** excellent accuracy. Through the transform it gives
`max(0, log 0) = 0`, hence `lam = 0` and `consistency = 1.0` — a receiver
reporting nothing scoring as perfectly healthy.

The committed captures contain **two** zero populations:

| signature | count | nature |
|---|---|---|
| `fix_type 0, sats 0, eph 65535, v_acc 0` | 870 | pre-lock |
| `fix_type 1, sats 3, **eph 121**, v_acc 0` | 30 | early acquisition |

The second has valid `eph` and satellite count, so **only the `h_acc <= 0`
clause rejects it**. Predicate:

```
valid iff  h_acc is present
       and h_acc != 0xFFFFFFFF        (UINT32 unknown)
       and h_acc > 0                  (pre-lock / acquisition artifact)
       and eph  != 0xFFFF             (the message's own unknown marker)
       and satellites_visible > 0     (a receiver tracking nothing states nothing)
```

An invalid sample contributes **nothing** and does not update the smoother. It
is never scored as health, good or bad. 900 of 10,163 capture samples are
rejected by this rule.

## 5. Downstream score influence — `DETECTOR_DOMINANT_BUT_DECLARED`

The Stage 1 claim — "consistency is bounded in (0,1], therefore the relation
cannot dominate diagnosis" — is **withdrawn**. Bounding the input to the
likelihood mapping does not bound the pairwise log-score correction, which is
what decides ranking.

Traced analytically from the frozen source
(`MAER_HACC_SCORE_INFLUENCE_AUDIT.json`):

| quantity | value |
|---|---|
| per-tick pairwise correction, gate 1 | ±3.931826 = `log((1+EPS)/EPS)` |
| × `EVIDENCE_MULT`, steady state | +5.897738 |
| prior barrier `nominal` over `gps_fault` | +3.761200 |
| **net margin** | **+2.136538** |
| ticks to 90 % of steady state | 37.2 |

**One sustained saturated relation alone puts `gps_fault` above `nominal`, with
no other evidence.**

This is **not** a property of the `h_acc` transform. The bound
`log((1+EPS)/EPS)` is identical for every relation in the layer, and
`gps_fault`'s evidence set already had exactly one member. It is a property of
the frozen diagnosis design — a single-feature cause plus an `EPS` floor.

**Consequence, declared in advance: H1's direction is close to structurally
implied** once the relation is live and degraded. The informative content of
this experiment therefore sits in **H2's crossover** and in magnitude and
timing, not in the sign of H1. Reporting H1 as a discovery would overstate it.

## 6. Scenarios — matched, not i.i.d.

The onset-varied runs are **DISTINCT PREREGISTERED DETERMINISTIC SIMULATOR
SCENARIOS**, not random repetitions. Onset changes global simulator/RNG history
and may change pre-fault internal state. **No random-sample population
inference is claimed from onset variation.**

No seed mechanism exists in ArduPilot: `get_random16()` (`AP_Math.cpp:350`) uses
hard-coded statics `m_z=1234, m_w=76542`; `rand_float()` on SITL calls libc
`random()`, never `srandom()`-ed; no `SIM_` seed parameter. **No simulator patch
was made.**

Verified distinct: 10 onsets (8, 11, 14, 17, 20, 23, 26, 29, 32, 35 s) →
**10/10 distinct** signatures, each with invalid-fix ticks and live `h_acc`
(27–37 distinct values). `MAER_TRAJECTORY_DISTINCTNESS.json`.

A fixed-onset RNG seed hook is recorded as an **optional robustness
extension**, not a requirement.

### 6.1 Pairing — mandatory

Every arm is evaluated on the **same** scenario. For scenario *i*, A0ᵢ, A1ᵢ,
A1Gᵢ, A2ᵢ, A3ᵢ consume the same captured trajectory. **The A1 vs A1G comparison
is within-scenario.** An unpaired analysis must not be used where a paired one
is available. Report scenario-level outcomes, paired differences and counts.

## 7. Two experiments

**Experiment A — deterministic matched-trace causal test.** One trajectory
through A1 and A1G. Supports exactly one claim:

> For the exact evaluated input trajectory, gate placement alone changes
> whether the receiver-health contribution remains available after validity
> closure.

**No population statistics from Experiment A.**

**Experiment B — multi-scenario robustness.** The 10 distinct scenarios,
paired per §6.1.

## 8. Hypotheses — FROZEN

### MC1 — gate-placement manipulation check

For the same `h_acc` trajectory, A1 retains the receiver-health contribution on
`gvalid = 0` ticks and A1G suppresses that identical contribution.

**Failure of MC1 invalidates the experiment.** MC1 is a check, not a finding.

### H1 (primary) — diagnostic rescue

A1 improves `gps_fault` attribution relative to **both** A1G and A0 during the
declared jam / fix-invalid windows, without violating the clean budget.

Endpoints: `gps_fault` top-rank share; unsupported-normal exposure; time to
useful attribution; unique attribution and ambiguity where defined.

Per §5, the *direction* is close to structurally implied; the magnitude and
timing are not.

### H2 (primary) — mechanism-specific crossover

**The key scientific result. Metric declared here, before scoring.**

Primary metric: **time to useful response**, seconds after onset, right-censored
at the window end.

- M1: first tick at which `gps_fault` is top-ranked after onset.
- M2: first tick at which the assurance threshold is crossed after onset.
- If no response occurs, the value is the window length (censored, and reported
  as censored).

Per scenario *M* and arm:

```
D(arm, M) = t_response(A0, M) - t_response(arm, M)      positive = faster
```

Crossover holds iff **both**:

```
D(A1, M1) > D(A2, M1)        receiver-health helps evidence-suppression more
D(A2, M2) > D(A1, M2)        CUSUM helps evidence-accumulation more
```

Reported as counts of scenarios satisfying each inequality, plus paired
differences. **If the crossover does not hold, H2 is REFUTED and is reported as
refuted.** It must not be reinterpreted.

### H3 — transport cause discrimination

The runtime distinguishes `STARVED_BY_TRANSPORT` from `EVIDENCE_GATE_CLOSED`
using only source / delivery / freshness / gate state. **No injected-fault label
may be an input.**

## 9. Arms — FROZEN

```
A0   BASELINE                  frozen core at csia-v1.0-research-final
A1   RECEIVER_HEALTH_UNGATED   contribution x 1
A1G  RECEIVER_HEALTH_GATED     contribution x gvalid
A2   CUSUM                     frozen B4: S = max(0, S + z - 0.5), alarm S > 500,
                               mu0/sigma0 clean-arm only, read-only on _lam
A3   MECHANISM_AWARE_COMBINED  A1 + A2 + evidence-cause classification
```

The gate-event Bayesian likelihood arm is **removed and stays removed**: two
fix-loss flights cannot support a calibration/test split.

**Exact A1 / A1G difference** — one parameterised factor, one code path:

```python
lam  = ewma.update(degradation_units(h_acc) ** 2)   # invalid samples skipped
gate = 1.0 if arm == "A1" else gvalid               # THE ONLY DIFFERENCE
contribution = (consistency(lam), gate)
```

A test must assert A1 and A1G resolve to the same code path with only `gate`
differing. **If any other difference exists the run is void.**

## 10. Validity criteria

A trial counts only if:

1. **RULE B**: for M1, at least one message with `fix_type < 3` and `h_acc`
   passing §4.2 taking more than one distinct value during that period.
2. Injection readback confirms.
3. The scenario signature is distinct from every other scored scenario.

`h_acc` is replaced by an alternate only if criterion 1 fails on a majority of
M1 trials.

## 11. Conditions — FROZEN

```
M0  CLEAN                       no injection
M1  ARDUPILOT_JAM               SIM_GPS1_JAM = 1, onset per §6
M2  PERSISTENCE RAMP            fix-preserving GNSS position ramp (ArduPilot)
M3  ARDUPILOT_TRANSPORT_STARVE  GPS_RAW_INT requested at 0.5 Hz instead of 5 Hz
                                on the consumer link
```

**M3 moved to ArduPilot, removing the platform confound.** Measured feasible:
requesting `GPS_RAW_INT` at 5 Hz delivers 5.05 Hz; at 0.5 Hz delivers 0.50 Hz —
a 10.1× starvation ratio, same platform, same message, healthy source, no
modification to the autopilot or the frozen core. The receiver is physically
generating valid data; only delivery is reduced.

M1 is **jamming**, a different fault from the `SIM_GPS1_ENABLE=0` fix-loss used
in Mechanism A. What transfers is the candidate family, not the physics.

## 12. Matrix — FROZEN

5 scenarios per applicable cell, paired per §6.1.

| | M0 | M1 | M2 | M3 |
|---|---|---|---|---|
| A0 | 5 | 5 | 5 | 5 |
| A1 | 5 | 5 | 5 | 5 |
| A1G | 5 | 5 | 5 | 5 |
| A2 | 5 | 5 | 5 | 5 |
| A3 | 5 | 5 | 5 | 5 |

= **100 scored trials**, 20 scenarios × 5 arms. No cell is INAPPLICABLE now
that M3 is same-platform.

## 13. Clean budget — pass/fail

**No assurance transition on any M0 trial, for any arm.** One or more clean
transitions ⇒ that arm **fails**, regardless of fault performance.

## 14. Outcome hierarchy

`CORRECT_UNIQUE_ATTRIBUTION` > `SAFE_AMBIGUITY` >
`EVIDENCE_UNAVAILABLE_CORRECTLY_DECLARED` > `WRONG_ATTRIBUTION` >
`UNSUPPORTED_NORMAL`. Ambiguity is reported separately and never counted as
correct diagnosis.

## 15. Analysis plan

Paired, within-scenario. The primary reading is **deterministic implementation
behaviour under declared simulator conditions**, not population inference.
Report counts, paired differences, effect sizes, timing distributions and
censoring. Exact tests only where assumptions hold. No p-value fishing.

## 16. Invalid trials and replacement

Invalid only for declared mechanical reasons: simulator crash, no heartbeat,
injection readback failure, duplicate scenario signature. Replacement draws the
next onset from the extension list (38, 41, 44, 47, 50 s). **No trial may be
excluded for its outcome.** Every rejection is recorded with its reason.

## 17. No adaptive tuning

Once the first scored trial runs, everything above is frozen: `h0`, `kappa_h`,
the EWMA constant, the validity predicate, CUSUM `k` and `h`, gate logic, the
scenario set, the H2 metric. Any change creates MAER_V3.

## 18. Known limitations carried into any result

1. Simulation-bound; no physical receiver data.
2. The structural arm is ArduPilot-only; PX4 rejected every candidate as
   `DIRECT_ORACLE`.
3. M1 is jamming, not the original fix-loss fault.
4. Scenario variation is onset timing, not a seed; scenarios are distinct but
   not i.i.d.
5. The contribution saturates above 9.16× nominal `h_acc`.
6. One saturated relation alone flips the ranking (§5), so H1's direction is
   close to structurally implied.
7. Candidate selection (Stage 0.5) was exploratory and is not itself
   preregistered.
