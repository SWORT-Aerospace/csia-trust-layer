# MAER — Revised Preregistration (DRAFT, NOT COMMITTED AS A PREREGISTRATION)

> **This is a draft for review, not a preregistration.** No scored trial may be
> run against it. It becomes a preregistration only when the open decisions in
> §12 are closed and it is committed in that state, before any scored trial.
> Stage 0.5 was exploratory and its candidate selection is **not** covered by
> any preregistration.

## 1. Research question

When diagnostic evidence becomes unavailable for different causal reasons, are
mechanism-specific mitigations necessary, or does a generic repair recover
performance across mechanisms?

## 2. What changed from the original MAER design, and why

| change | reason |
|---|---|
| gate-event likelihood arm **removed** from the primary matrix | only 2 fix-loss flights exist; no calibration/test split is possible, and an undercalibrated arm would contaminate the causal comparison |
| structural arm now uses a **raw receiver-health residual** | no admitted CSIA residual survives fix loss; `h_acc` does |
| M1 is **jamming**, not fix-loss disable | `SIM_GPS1_ENABLE=0` freezes the message; nothing is live to rescue |
| structural arm is **ArduPilot-only** | every PX4 candidate is a `DIRECT_ORACLE` |

## 3. Candidate and transform (to be frozen)

Input: `GPS_RAW_INT.h_acc` (mm), ArduPilot, ingested by a research-only sidecar.
The production adapter discards it via its early return on `fix_type < 3`; the
frozen core is not modified.

```
x_t      = log(h_acc_t + 1)
z_t      = (x_t - median_clean) / max(MAD_clean, 1e-3)
lambda_t = z_t^2
```

`median_clean`, `MAD_clean` estimated on **clean flights only**. The `1e-3`
floor is fixed here, in advance, because SITL's clean `h_acc` is constant and
MAD would otherwise be zero. No constant may be chosen by inspecting fault
traces.

## 4. Arms

```
A0   BASELINE                    frozen core, unmodified
A1   RECEIVER_HEALTH_UNGATED     lambda_t contributes to gps_fault, x 1
A1G  RECEIVER_HEALTH_GATED       lambda_t contributes to gps_fault, x gvalid
A2   CUSUM                       frozen B4: S = max(0, S + z - 0.5), alarm S > 500,
                                 mu0/sigma0 from the clean arm only
A3   MECHANISM_AWARE_COMBINED    A1 + A2 + evidence-cause classification
```

A1 and A1G must differ **only** in that multiplication. Identical input,
samples, transform, calibration, evidence mapping, hypothesis association,
temporal filter and normalization. Any other difference invalidates the causal
reading and must fail the run.

## 5. Mechanisms

```
M0  CLEAN                    no injection
M1  JAM                      SIM_GPS1_JAM = 1 (ArduPilot)
M2  PERSISTENCE RAMP         fix-preserving GNSS position ramp (ArduPilot)
M3  TRANSPORT STARVATION     passive vs requested PX4 link
```

## 6. Matrix

5 repetitions per cell. A1/A1G × M3 are **INAPPLICABLE** — M3 is PX4 and the
candidate is rejected there. Marked, not manufactured.

|  | M0 | M1 | M2 | M3 |
|---|---|---|---|---|
| A0 | 5 | 5 | 5 | 5 |
| A1 | 5 | 5 | 5 | INAPPLICABLE |
| A1G | 5 | 5 | 5 | INAPPLICABLE |
| A2 | 5 | 5 | 5 | 5 |
| A3 | 5 | 5 | 5 | 5 |

= 90 scored trials.

## 7. Hypotheses

**H1 (gate placement).** Under M1, A1 preserves `gps_fault` support after the
navigation solution becomes invalid; A1G does not. Primary endpoint: share of
invalid-fix ticks on which `gps_fault` is the top hypothesis.

**H2 (temporal specificity).** Under M2, A2 responds earlier than A0 without
exceeding the clean budget.

**H3 (non-substitutability).** A2 does not recover `gps_fault` support under M1.

**H4 (evidence-cause discrimination).** The runtime distinguishes
`STARVED_BY_TRANSPORT` from `EVIDENCE_GATE_CLOSED` without access to
injected-fault labels.

**H5 (combined).** A3 achieves A1's M1 behaviour and A2's M2 behaviour without
exceeding the clean budget.

## 8. Clean budget

No assurance transition on any M0 trial, for any arm. An arm that gains fault
sensitivity while producing clean transitions **fails**, regardless of its fault
performance.

## 9. Outcome hierarchy

`CORRECT_UNIQUE_ATTRIBUTION` > `SAFE_AMBIGUITY` >
`EVIDENCE_UNAVAILABLE_CORRECTLY_DECLARED` > `WRONG_ATTRIBUTION` >
`UNSUPPORTED_NORMAL`. Ambiguity is reported separately and never counted as
correct.

## 10. Validity and exclusion

A trial counts only if RULE B holds — the declared downstream observable is
present. Invalid simulator runs are replaced only for declared mechanical
reasons (crash, no heartbeat, injection not confirmed), never for outcome.
Every rejection is recorded with its reason.

## 11. No adaptive tuning

Once the first scored trial runs, every parameter is frozen. Any later change
creates MAER_V2 with a new preregistration.

## 12. OPEN DECISIONS — must be closed before this becomes a preregistration

1. **Realisation independence.** Five JAM runs were byte-identical; SITL does
   not expose the RNG seed. Either patch SITL to accept a seed, or vary initial
   conditions and jam onset time, and declare the mechanism here. **Without
   this there is no replication, only repetition.**
2. **Statistical plan.** With 5 per cell, state explicitly that the reading is
   deterministic implementation behaviour, not population inference.
3. **M1-to-Mechanism-A relationship.** M1 is jamming; the original
   self-occlusion result is fix-loss. State what transfers and what does not.
4. **Sidecar verification.** A test must prove A1 and A1G differ by exactly one
   multiplication — ideally by asserting both arms are the same code path with
   one gate factor parameterised.

## 13. What this cannot claim

Nothing here licenses a statement about physical GNSS receivers. `h_acc` under
jamming is `|rand_float()| * 300` in a simulator. The result, if positive, is
**simulation-based receiver-health availability** and must be worded that way.
