# UNKNOWN / UNMODELED — MODEL-ADEQUACY AUDIT

§11. *"Do NOT implement UNKNOWN merely to complete the feature list."*
*"Determine whether the current model exposes a defensible MODEL-ADEQUACY
quantity."* — audited, not assumed.

## VERDICT

    UNKNOWN / UNMODELED:
    NOT IMPLEMENTED — MODEL ADEQUACY TEST REQUIRED

A threshold-free criterion **does exist** and was built and measured. It is
not adopted, for a reason that measurement exposed rather than a reason
assumed in advance. Both the criterion and its numbers are recorded below so
a later phase can adopt it if a principled tolerance is found.

---

## 1. CANDIDATES CONSIDERED

| candidate | why rejected |
|---|---|
| **Likelihood floor** — `max_h ll[h]` below some level | `ll` scales with the number of *active* features, which varies with sensor availability. Comparing across configurations needs a normalisation, and both the normalisation and the floor are arbitrary. Rejected before implementation |
| **Total absolute evidence adequacy** | same scaling problem |
| **Posterior predictive consistency** | the frozen core is a naive-Bayes score over consistency features, not a generative model of the observations. There is no predictive distribution to check against. Rejected as inapplicable, not as unpromising |
| **Residual-bank adequacy** | the residual bank lives in the trust engine, not the diagnosis core; using it would test a different model from the one whose adequacy is in question |
| **Structural set-adequacy** (below) | **built and measured**; see §4 |

## 2. THE ONE THRESHOLD-FREE CRITERION

The frozen core's likelihood has an exact indifference point. For feature *j*:

    lo_j = log(1 − c_j + EPS)      hi_j = log(c_j + EPS)
    lo_j = hi_j   ⟺   c_j = 0.5

So `c_j = 0.5` is **the core's own** boundary between "this feature evidences
LOW" and "this feature evidences HIGH". It is not a tuned value; it falls out
of the likelihood the core already uses.

Define, at tick *k*:

    F_low(k) = { j : gate_j > 0  and  lo_j > hi_j }     (active and evidencing LOW)

    h is SET-ADEQUATE   ⟺   F_low(k) ⊆ LOW[h]

    UNKNOWN(k)          ⟺   no modeled h is set-adequate

In words: *some active features are reading low, and no modeled cause claims
all of them.* No threshold, no label, no ground truth.

## 3. IT CLEARS ALL THREE OF §11's BARS

- **No arbitrary threshold.** 0.5 is the core's own indifference point.
- **No fault-label tuning.** Nothing was fitted; ground truth was never
  consulted to set anything.
- **Not circular.** It reads the `CAUSES` table and the current feature
  values, never the posterior it would qualify.

## 4. WHAT IT ACTUALLY DOES — MEASURED

Nine-scenario catalogue, 1500 ticks each, run before this verdict was written:

| scenario | UNKNOWN ticks | % | `|F_low|` distribution |
|---|---:|---:|---|
| `clean` | 0 | 0.0 % | {0: 1338, 1: 153, 3: 9} |
| `gps_dropout` | 0 | 0.0 % | {0: 1338, 1: 153, 3: 9} |
| `imu0_bias_drift` | 0 | 0.0 % | {0: 1069, 1: 179, 2: 220, 3: 32} |
| `gps_spoof` | 124 | 8.3 % | {0: 1028, 1: 339, 2: 124, 3: 9} |
| `dual_imu_failure` | 598 | 39.9 % | {0: 640, 1: 137, 2: 112, 3: 353, 4: 258} |

**Zero false positives on clean.** That is the test that matters most and it
passes.

**`dual_imu_failure` at 39.9 % is arguably correct.** `CAUSES` is a
single-fault model; that scenario injects two simultaneous IMU faults and
there is no dual-fault hypothesis. "No modeled hypothesis explains the
evidence" is literally true there, and a criterion that says so is doing its
job.

**`gps_spoof` at 8.3 % is the problem.** A modeled single fault fires UNKNOWN,
because the spoof drives `phys_gps` low (which `gps_fault` claims) *and*
disturbs `temp_gps` (which only `unexpected_maneuver` claims). No single
hypothesis covers both.

## 5. WHY IT IS NOT ADOPTED

Two reasons, and the second is decisive.

**5.1 It has no noise tolerance, and adding one is exactly the forbidden
threshold.** Containment `F_low ⊆ LOW[h]` is strict. One feature dipping below
0.5 for one tick, in a feature no hypothesis happens to claim, flips the whole
system to UNKNOWN. On this corpus that did not happen on `clean` — the
`|F_low| = 3` ticks were covered by *some* hypothesis — but that is a property
of which features happened to dip, not a property of the criterion. Making it
robust means allowing *m* unexplained features, and *m* is the arbitrary
threshold §11 forbids.

**5.2 Deciding whether `gps_spoof`'s 8.3 % is right or wrong requires exactly
the circularity §11 forbids.** Is a spoof that also perturbs temporal
stability genuinely unexplained by a single-fault model — in which case
UNKNOWN is correct and informative — or is it a modeled fault being
misreported? Answering that means adjudicating against the injected fault
label, and then tuning the criterion until the labels come out right. That is
fault-label tuning, and it is not permitted here.

So a criterion exists that passes §11's three bars formally, and it still
cannot be validated without breaking one of them.

## 6. WHAT WOULD UNBLOCK IT

Recorded so a later phase does not have to rediscover it:

1. **A dual-fault or "other" hypothesis in the model.** Most of the
   `dual_imu_failure` firing, and possibly the `gps_spoof` firing, is the
   single-fault assumption showing through. Adding an explicit compound or
   catch-all hypothesis would change what "no modeled cause explains this"
   means — but `csia/diagnosis` is **FROZEN**, so this is not a v1.1 change.
2. **A principled tolerance derived from the feature noise model** rather than
   chosen — e.g. a per-feature probability of dipping below the indifference
   point under nominal conditions, estimated from a declared clean development
   set. That is a real route and it is not a tuned constant, but it needs the
   clean-exposure corpus that does not yet exist (Phase 6 / G3).
3. **An adjudication set labelled independently of CSIA's own output**, so
   §5.2's question can be answered without circularity. Also Phase 6.

## 7. WHAT WAS SHIPPED INSTEAD

Nothing named UNKNOWN. `support_state` takes exactly four values and none of
them asserts model inadequacy:

    NO_APPLICABLE_EVIDENCE · NON_IDENTIFIABLE · PRIOR_SENSITIVE · EVIDENCE_BACKED

and `ambiguity` takes two, `UNIQUE` and `AMBIGUOUS`, per
`SUPPORT_STATE_SPEC.md` §7. The audit script that produced §4's table is
retained at `engineering/v1_1/support/unknown_audit.py` and is **not** wired
into the runtime.
