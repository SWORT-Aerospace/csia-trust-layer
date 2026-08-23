# WP-C4 — Full Algorithm Exposition and Non-Invasive Stress Testing

**Date:** 2026-08-22 · **Branch:** `research/wp-e1` · **PR #13**
**Suite: 467 → 467.** No production file touched. No test added — WP-C4
records findings rather than pinning them.
**Artifacts:** `research/wp_c4/results/`, `figures/wp_c4_*.png`,
`docs/research/CSIA_ALGORITHM_EXPOSITION.md`,
`docs/audit/VERSION_BOUNDARY.md`

---

## 1. Verdict

**The headline result survives, and its mechanism is renamed.** The sparsity
objection was the most likely way a referee kills the effective-signature
gap, and it is settled: in a controlled synthesis the gap **does** vanish with
density when a hypothesis's evidence is drawn freely — but it **saturates at
exactly 1/7 and never decays** when the hypothesis's evidence necessarily
lives behind the gate it closes, which is CSIA's actual situation. The result
is not about sparsity. It is about **evidence–gate coincidence**.

And `SOI(gps_fault) = 1.0` is no longer a property of a matrix. Run against
the deployed pipeline with a GPS denial, **the diagnosis never once names
`gps_fault`** — it sits on `nominal` for the full 40 s with GPS trust at
0.9767, above the actionable threshold. The failsafe still escalates, through
its independent freshness branch. The blind spot is in attribution, not in
escalation, exactly as WP1 argued and now measured rather than argued.

Three further results: the theoretical **chatter resonance is confirmed** on
the real implementation; the promotion created **no new order-one cut set**,
refuting my own WP-C3 concern; and `DiagnosisCore` has **no input validation**
where `TrustCore` does.

---

## 2. Part 2.4 — the sparsity objection, settled

Controlled synthesis over the same gate structure, 400 draws per cell, one
designated hypothesis `h*` closing `gvalid` (the `gps_fault` role).

| Features per hypothesis | ARM A "uniform" mean gap | P(gap>0) | ARM B "physically forced" mean gap | P(gap>0) |
|---|---|---|---|---|
| 1 | 0.0264 | 0.185 | 0.1018 | 0.713 |
| 2 | 0.0050 | 0.037 | 0.1400 | 0.980 |
| 3 | 0.0011 | 0.007 | 0.1425 | 0.998 |
| 4 | 0.0004 | 0.003 | 0.1425 | 0.998 |
| 5 | **0.0000** | **0.000** | **0.1429** | **1.000** |
| 6–8 | 0.0000 | 0.000 | **0.1429** | **1.000** |

- **ARM A** draws `h*`'s features uniformly from the whole pool. The gap
  collapses to exactly zero by density 5. **If this were CSIA, the objection
  would be correct.**
- **ARM B** draws `h*`'s features only from `gvalid`-gated features, because
  a GPS fault's evidence is necessarily GPS evidence. The gap **rises** with
  density and **saturates at 0.14286 = 1/7**, the real system's value, with
  `P(h* fully silenced) = 1.000` at *every* density.

**The real system is unambiguously ARM B**, verified programmatically:
`gps_fault`'s feature set is `['phys_gps']`, and **all of its features are
`gvalid`-gated**.

> **The claim to make is not "design-time analysis overstates isolability"
> and not "sparse matrices are fragile."** It is: *when a hypothesis's
> evidence pool is contained in a gate's controlled-feature set, and that
> hypothesis closes that gate, no amount of additional evidence repairs the
> collapse.* Adding features to `gps_fault` cannot help, because every
> additional GPS feature is also behind `gvalid`. That is a sharper claim than
> the one we started with, and it is the one the data supports.

This also explains why the WP-C2 GPS study found that only *ungated* relations
repair the pair: they are the only candidates outside the containment.

---

## 3. Part 2.3 — self-occlusion, observed

Three arms, same truth and seed, shipping `FailsafePolicy` driven exactly as
`csia/dashboard/export.py` drives it.

| | A: spoof only (fix valid) | B: denial (fix invalid) | C: spoof → denial |
|---|---|---|---|
| `gvalid` closed, post-onset | 0% | **62%** | 50% |
| `gps_fault` on top | 66.5% | **0.0%** | 15.6% |
| `nominal` on top | 33.5% | **100%** | 84.4% |
| Time to first `gps_fault` lead | 1.44 s | **never** | 1.44 s |
| Seconds `nominal` on top while faulted | 13.4 | **40.0** | 33.8 |
| …of which "confident-wrong" (GPS trust ≥ 0.85) | 12.7 | **40.0** | 12.7 |
| GPS trust minimum | 0.5905 | **0.9767** | 0.7003 |
| Max failsafe level | CAUTION | **CAUTION** | CAUTION |

**Arm B is the result.** A GPS fault that destroys the fix is never named. The
diagnosis reports `nominal` for the entire fault, and GPS trust stays at
0.9767 — because absence of data freezes the Beta belief (`engine.py:146`), so
the trust channel also says nothing is wrong. **40 seconds of confident-wrong.**

**Arm C is the attack.** Spoof first, get correctly diagnosed at 1.44 s, then
deny — and the system returns to `nominal` for 84% of the remaining window. A
GPS fault that reveals itself and then destroys the evidence ends up looking
healthy.

**Scope, stated precisely and in CSIA's favour.** Max failsafe level is CAUTION
in **all three arms**, with 3 actions issued in each. In arm B the escalation
comes from the failsafe's independent freshness disjunct
(`failsafe.py:144-145`), not from the diagnosis. **The vehicle is not blind to
GPS denial; it cannot name it.** WP1 called this "a diagnosis blind spot, not a
safety hole" — that is now measured, not argued.

---

## 4. Part 2.1 — adversarial search

### 4.1 Chatter resonance: CONFIRMED

Theory predicts the label flip rate peaks when gate closure duration is near
`1/α_s = 16.67` frames. Swept 1–100 frames against the real `DiagnosisCore`,
evidence pattern held fixed so **every flip is caused by gating alone**.

**Observed peak at 21 frames, 95 flips**, against 1–3 flips at durations below
18. Prediction confirmed within tolerance. This is the first empirical test of
that prediction against the implementation.

**A null result I caused and had to fix.** My first version set *every*
feature anomalous, which let a multi-feature hypothesis win whether the gate
was open or closed — 0 flips at every duration. The gated feature must be
*decisive* or there is nothing to flip. The corrected probe makes only
`phys_gps` anomalous. The original null was a property of my probe, not the
system.

### 4.2 Trust floor and recovery

| | Value |
|---|---|
| Floor reached | **0.0068** after 600 ticks of total inconsistency |
| Recovery to 0.85 | **801 ticks** (~32 s at 25 Hz) |
| Geometric bound `ln(0.15)/ln(ρ_max)` | 948 ticks |

Observed recovery **beats** the pure-decay bound because α accumulates while
β decays. **Correction to an earlier claim:** the 0.538 fused-evidence floor
pinned by `test_formalization_lock` is conditional — it holds when one
sub-score collapses and another survives. Collapse every available sub-score
and evidence goes to ~0 and trust follows. Recorded as discrepancy D-7.

### 4.3 Minimum undetected fault

| Mode | Largest never detected | Smallest detected |
|---|---|---|
| `imu0` bias drift | **0.0307 m/s²/s** | 0.0317 |
| `mag` EMI | **0.512 µT** | 0.513 |

**A second self-inflicted error.** My first pass reported *every* magnitude as
detected, because it scanned the whole run and was seeing the prior-convergence
warm-up dip rather than the fault. Corrected to a post-onset window.

---

## 5. Part 2.2 — boundary inputs: 13 OK, 2 SILENT_BAD, 0 CRASH

`TrustCore` handled every abuse correctly: NaN and Inf λ, negative λ, gate
above 1, gate negative, no evidence at all, 5000 stale ticks, 50 000 saturated
ticks, a channel appearing mid-flight, a channel flapping.

**Both failures are in `DiagnosisCore`, and they are the same defect:**

| Case | Result | Detail |
|---|---|---|
| `diagnosis_nan_consistency` | **SILENT_BAD** | NaN consistency → **NaN posterior**, no exception. `RuntimeWarning: invalid value encountered in log` at `bayes.py:107-108`. |
| `diagnosis_consistency_out_of_range` | **SILENT_BAD** | `c = 5.0` → `log(1 − 5 + 0.02)` = NaN; `c = −3.0` likewise. |

**The asymmetry is the finding.** `TrustCore` has bounds rejection (29 negative
cases under ASan/UBSan); `DiagnosisCore` has none. Not reachable from
production upstreams — `consistency()` maps λ into `(0,1]` — so this is a
latent robustness gap, not a live bug. **Recorded, not fixed.**

Rapid gate toggling at every period 1–100 kept the posterior a normalised
distribution throughout.

---

## 6. Part 2.5 — the promotion created no new order-one cut set

WP-C3 raised the concern that routing IMU discrimination through `mag` traded
one exposure for another. Birnbaum rank was suggestive; cut sets are the test.

| | Pre-promotion | Post-promotion |
|---|---|---|
| Pairs with an order-one cut set | 7 | **6** |
| Components in *any* order-one cut set | 9 | **7** |
| `channel:mag` order-one for | `mag_interference+nominal` | `mag_interference+nominal` — **unchanged** |
| **New `mag` order-one exposures** | — | **NONE** |
| `imu0+imu1` minimum cut size | **1** | **2** |
| `imu0+imu1` order-one cut sets | `armed_gate`, `channel:motor_esc` | **none** |

**My WP-C3 concern is refuted.** The promotion was a strict improvement:
`armed_gate` and `channel:motor_esc` dropped out of the order-one set
entirely, and no component entered it. `channel:mag` was already order-one for
`mag_interference+nominal` before the change and remains exactly that.
Birnbaum importance rose for `mag` without creating a new single point of
diagnostic failure — importance and criticality coming apart again, in the
benign direction this time.

---

## 7. Part 1 — the exposition

`docs/research/CSIA_ALGORITHM_EXPOSITION.md`: tick pseudocode with line
ranges, every equation as implemented (clamps and fallbacks included), the
full persisting state vector, `S` and `S_eff` in one table where the
`gps_fault` collapse is readable off the page, all 14 gates split into 4
actuating / 2 constant / 8 freshness, the failsafe automaton with `D_critical`
identified, a real 20-tick numerical trace, and a 10-row discrepancy table.

Two new discrepancies surfaced by writing it: **D-7** (the conditional
evidence floor) and **D-8** (`DiagnosisCore` input validation). `UNSOURCED` is
used three times — the ≈45:1 endogeneity ratio, the 674 ns figure, and every
STM32H743 number.

---

## 8. Part 3 — version boundary

`docs/audit/VERSION_BOUNDARY.md`. Boundary commit `081cca3`. Headline: **the
WP-A2 correction package applies to both sides and is safe to send as
written.** The one artifact needing an edit before submission is the paper
empirical section, which quotes the gate ceiling as 0.286 — post-promotion it
is 0.143. The argument is unchanged (the ceiling still sits far below the
corpus's 1.000); the number is not. Flagged, not silently edited.

Also recorded: **do not re-run `repair_experiment.py` expecting a before/after
diff.** The flag is a no-op now, so a re-run collapses both arms to the post
state. That file was restored from git once already for exactly this reason.

---

## 9. Part 4 — what would falsify this

**The effective-signature gap is an artifact if:**
`gvalid` does not actually close during real GPS faults. The claim rests on
`closes(gps_fault, gvalid) = TRUE`, derived from `fix_type >= 3`
(`ulog_source.py:178`) plus physical reasoning about denial and jamming.
**Check:** per-tick `gvalid` traces from real logs containing a GPS
disturbance. If `gvalid` stays open through GPS faults in flight, `S_eff` = `S`
and the gap is zero. *This is checkable the moment the corpus is re-acquired.*

**Gate-induced coarsening is operationally irrelevant if:**
`q_gvalid | gps_fault ≈ q_gvalid | nominal` — that is, if the fix drops about
as often in healthy flight as during a fault. The structural result would
stand and the *risk* would vanish. **Check:** the conditional closure
frequencies. This is the single measurement that would most change the
conclusions, in either direction, and it is the same one WP-E2 needs.

**`C_reach` is wrong if:**
a configuration the model calls unreachable occurs in flight. The reachability
rule is that a gate on an absent channel is vacuous. **Check:** log the
(gate-state, channel-availability) pair every tick on real flights and look
for pairs outside the 1232. Any hit invalidates the certificate for that case.

**The certificate is too pessimistic if:**
merged pairs separate statistically. κ bounds *structural* indistinguishability
only; two hypotheses in one observable class may still differ in residual
magnitude or variance. **Check:** on the arm-B trace, does `P(gps_fault)` move
at all relative to prior? Measured here: it does not — occupancy 0.0%. But that
is one scenario, not a proof.

**The most consequential unexpected result** would be `q_gvalid | gps_fault`
coming back *low* — say under 0.1. That would mean real GPS faults mostly leave
the fix valid, which would make arm A the typical case rather than arm B,
demote the whole self-occlusion line to a corner case, and redirect the GPS
integrity work.

---

## 10. What I got wrong

Three defects in my own probes, all caught before they reached the report:

1. **The chatter probe could not flip.** Every feature anomalous meant a
   multi-feature hypothesis won regardless of gating — 0 flips at every
   duration, which I would have reported as refuting the prediction. The null
   was mine.
2. **"Every fault magnitude is detected"** — the detection window included the
   warm-up dip. Corrected to post-onset.
3. **Three API misuses in one file:** `TrustCore.step` takes `phys` not
   `physics`; its edge tuples carry λ, not a consistency (passing a
   consistency would have silently measured the wrong thing); and it returns a
   per-node dict of dicts, not a scalar. Also `Action.name`, not `.kind`.

And one avoided by looking first: I started reimplementing the batch→failsafe
adapter and found the shipping one already exists in
`csia/dashboard/export.py` with the `top_causes()` method the policy needs.
Importing it guarantees fidelity that a reimplementation would not.

**One prior conclusion of mine is now superseded** — the WP-C3 "traded for
reliance on `mag`" remark (§6).

---

## 11. Open, with owners

| Item | Owner | Blocking |
|---|---|---|
| `q_gvalid` conditioned on hypothesis | WP-E2 | corpus re-acquisition — **still the single most important missing number** |
| Update the paper's gate ceiling 0.286 → 0.143 | Author | nothing |
| `DiagnosisCore` input validation (D-8) | Engineering | judgement — latent, not live |
| `failsafe.py:106` fail-open on `att` (D-9) | Engineering | unanalysed since WP1 |
| `engine.py:104` stale "12 edges" comment (D-1) | Trivial | nothing |
| Full-text novelty attack | You | egress policy |
| `SWORT_CSIA.pdf` + submission date | You | four documents still blocked |
