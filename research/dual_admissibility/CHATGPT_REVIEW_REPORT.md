# DUAL-CHANNEL ADMISSIBILITY — CHATGPT REVIEW REPORT

Base commit `d4f9cd3`. Frozen production core modified: **NO**.
Reproduce: `make dual-admissibility` (about four minutes).

## 1. Executive Verdict

**`PROMISING_BUT_CONFOUNDED`.**

The coupling is real and pinned in source. The motivating tradeoff reproduces
exactly. A closed-form model predicts the implementation to 1 × 10⁻⁵. Under
*sustained* invalidity the split is the entire effect and the matched coupled
controls gain exactly nothing. The transport control passes cleanly.

And then two things stop it short of the strong verdict, both found by trying
to kill it:

1. **The operational half of the two-objective story has no measured
   operational consequence.** Objective O improves from 0.000 to 0.996 — and
   the `FailsafePolicy` outcome is *bit-identical across all ten arms*. Same
   transition at t = 11.08 s, same 898 ticks at CAUTION, same 31 `nav_degraded`
   ticks, same 3.036 s to first raise it. Only the reason string differs. On
   the one real recording, correcting the operational gate changed nothing an
   operator would see. "Pareto dominant" on an axis whose value is assumed
   rather than demonstrated is not a result to bank.

2. **On the one real recording the effect is detector-dominant.** The h_acc
   term *with D coupled to A* recovers +0.138 of gps_fault top-share; the
   split adds +0.002 on top. The split-dominant regime — where the coupled
   controls get literally zero — appears only on a synthetic sustained-
   invalidity fixture.

`STRONG_ARCHITECTURAL_CANDIDATE` requires the improvement not to be explained
by detector dominance. On synthetic patterns it is not. On the real data it is.
That split decision is the honest answer, and it is a conditional result rather
than a verdict for the architecture.

**NOVELTY: NOT ESTABLISHED.** No literature search was performed.

## 2. Source-Level Discovery

`source_validity_role_audit.py` pins 16 gates — each a pattern required to
occur exactly once, resolved to a line, then re-read to confirm the number
before publishing it. Three are coupled: `CV_USABLE`, `SLOT_VALID_WRITE` and
`FRESH`.

`fresh` is computed once per tick (`csia/runtime/online.py:603`) and then used
for both roles from that single value:

* **D** — multiplies every edge gate (`:610`) and physics gate (`:613`), and
  gates the Beta update (`csia/trust_engine/engine.py:146`).
* **A** — published on `TrustState.fresh`, read by
  `FailsafePolicy._conditions` (`csia/runtime/failsafe.py:100`), which raises
  `nav_degraded` → `SWITCH_NAV_INERTIAL`, `INHIBIT_GPS_MODES` (`:145`).

> `D_gps == A_gps == fresh["gps"]` **by construction.** The coupled
> architecture is not a hypothetical alternative; it is what is implemented.

It bites here because `CAUSES["gps_fault"] == ["phys_gps"]` — one supporting
feature, whose gate carries `fresh["gps"]`. A GNSS fault that makes the
receiver report no fix closes the only gate that could evidence it.

## 3. Existing Coupling

Item 34 asks whether the core already separates A and D. It does not — but two
near-misses are worth recording.

`Quality.admissible`'s own docstring reads *"Whether a present value may be
used as diagnostic evidence"*. The qualification vocabulary is already D-only.
But `ChannelValue.usable` is consumed by both `to_core_samples` (D) and the
operational sample view (`usable_channels`, `_armed`, the flight log,
`shadow.py:412`). The word is D-scoped; the use is coupled.

`csia_may_use` is a genuine second gate — `estimator.variances` is
`INFORMATIVE` and still excluded, because an assurance layer cannot be
independent of an estimator it consumes. That is a policy channel, not an A/D
split.

**One partial decoupling already exists, by omission.** `temp_<sensor>`
features are built with the gate hard-coded to `1.0` (`online.py:630`) from
`slot.hist_val`, frozen at the last accepted sample — so `temp_gps` keeps
contributing a *retained* score after `fresh["gps"]` closes. That is the
retained-state hazard from the previous work package appearing on the evidence
path, not a designed split.

## 4. Formal State Model

`SEMANTIC_STATE_MODEL.md`. Of item 4's seven candidate observation states, three
are upstream-representable here (`OBSERVED_VALID`, `OBSERVED_INVALID`,
`NOT_OBSERVED`), `STALE` exists only as a downstream state, `RETAINED` is
implicit with no marker, and `IMPUTED` / `ESTIMATED` have no representation at
all. They are recorded as absent rather than invented.

As implemented: `A_gps(t) = D_gps(t) = fresh["gps"](t)`.

Under the split, D is decomposed by what the evidence is *about*:

```
D_value(t)  = A_gps(t)                        the navigation value never
                                              becomes admissible while the
                                              receiver disowns it
D_status(t) = 1[t - t_last_MESSAGE <= 0.5 s]
D_hacc(t)   = 1[hacc_valid(last usable h_acc)] . 1[t - that message <= 0.5 s]
```

`D_status` gating on **message arrival** rather than sample acceptance is the
only thing separating "the receiver reported no fix" from "no message
arrived". Gate it on anything derived from `last_t` and the status feature
fires on transport starvation, which is worse than having no status feature.

## 5. Reproduction of S0 vs S1 Tradeoff

Item 8's hard stop. The tick loop was **re-implemented** rather than imported,
precisely so the reproduction tests something.

| metric | committed | reproduced | exact |
|---|---|---|---|
| S0 final `gps_fault` | 0.892201 | 0.892201 | ✓ |
| S1 final `gps_fault` | 0.722429 | 0.722429 | ✓ |
| S0 leading ticks | 963 | 963 | ✓ |
| S1 leading ticks | 836 | 836 | ✓ |
| S0 min trust | 0.197184 | 0.197184 | ✓ |
| S1 min trust | 0.234617 | 0.234617 | ✓ |

12/12 bit-for-bit. The study was permitted to proceed.

## 6. S2 Split Semantics

Ten arms; each split arm has a **matched coupled control carrying identical
evidence terms and differing in one boolean**.

| | policy | status | h_acc | D gating | h_acc freshness |
|---|---|---|---|---|---|
| `S0` | drop invalid | – | – | – | – |
| `S1` | propagate | – | – | – | – |
| `S1Da` | propagate | ✓ | – | **D = A** | message |
| `S1Db` | propagate | – | ✓ | **D = A** | message |
| `S1D` | propagate | ✓ | ✓ | **D = A** | message |
| `S2a` | propagate | ✓ | – | independent | message |
| `S2b` | propagate | – | ✓ | independent | message |
| `S2c` | propagate | ✓ | ✓ | independent | message |
| `S2b2` | propagate | – | ✓ | independent | valid_hacc \* |
| `S2c2` | propagate | ✓ | ✓ | independent | valid_hacc \* |

\* POST-HOC — see §24.

No new scale was chosen. The h_acc transform is the one frozen in
`research/maer/maer_hacc_transform.py` and never used in a scored run; the
status feature is binary in the frozen consistency domain, `c ∈ {0,1}`, which
is the strongest that domain permits — recorded as a known confound, not tuned;
the freshness window reuses `STALE_TIMEOUT_S["gps"] = 0.5 s`.

## 7. Exact Same-Input Proof

Every arm is replayed from the identical decoded message list in one process.
Hashes are taken once, before any arm runs:
`message_stream_sha256`, `gnss_stream_signature_sha256`, `fixture_sha256`, plus
the shared frozen constants (`EPS`, `SMOOTH_ALPHA`, `EVIDENCE_MULT`,
`PRIOR_NOMINAL`, `STALE_TIMEOUT_S`) recorded alongside. Config diff between
`S1D` and `S2c` is exactly `{arm, d_coupled_to_a}`, asserted by test.

## 8. Operational Correctness

| arm | objective O | nav_degraded ticks | time to nav_degraded | first transition reason |
|---|---|---|---|---|
| `S0` | **0.000000** | 31 | 3.036 s | GPS trust 0.42 |
| every propagating arm | **0.996377** | 31 | 3.036 s | GPS data invalid |

The gate improves completely. **The recommendation does not change at all** —
same transition time (11.08 s), same 898 ticks at CAUTION, same actions. S0
reaches the same operational condition by a different route: degraded *trust*
rather than absent *data*. This is the finding that most weakens the study,
and it is stated before the results that flatter it.

## 9. Diagnostic Preservation

M1, ArduPilot `SIM_GPS1_JAM`, N = 1, 29% of post-onset observations invalid:

| arm | D top-share | final `gps_fault` |
|---|---|---|
| `S0` | 0.963964 | 0.892201 |
| `S1` | 0.836837 | 0.722429 |
| `S1Da` status, coupled | 0.000000 | 0.022220 |
| `S1Db` h_acc, coupled | 0.974975 | 0.996656 |
| `S1D` both, coupled | 0.819820 | 0.722426 |
| `S2a` status, split | 0.000000 | 0.067394 |
| `S2b` h_acc, split | **0.976977** | **0.998946** |
| `S2c` both, split | 0.965966 | 0.963395 |
| `S2c2` both, split, post-hoc | 0.965966 | 0.963395 |

Note what wins: **`S2b`, the arm without the status feature.** And `S1Db`, its
*coupled* twin, is within 0.002 of it.

## 10. H1

**SUPPORTED at the gate, NULL at the recommendation.** O: 0.000 → 0.996.
Operational outcome: identical across all ten arms. See §8.

## 11. H2

**SUPPORTED, conditional on sustained closure.** M1: 0.837 → 0.966 (S1 → S2c).
Sustained invalidity: 0.000 → 0.961 (S1 → S2a). The effect is real in both
regimes but comes from **different terms** — h_acc on the intermittent
recording, status under sustained invalidity — which is itself a warning that
"the split preserves evidence" is too coarse a summary.

## 12. H3 / Pareto Result

Axes defined in code before any S2 arm ran:
X = `1 − (obs-invalid ticks with A open)/(obs-invalid ticks)`;
Y = `share of post-onset ticks with gps_fault leading`.

| arm | O | D |
|---|---|---|
| `S0` | 0.000000 | 0.963964 |
| `S1` | 0.996377 | 0.836837 |
| `S1D` | 0.996377 | 0.819820 |
| `S2b` | 0.996377 | **0.976977** |
| `S2c` | 0.996377 | 0.965966 |

`S2c`: **`PARETO_DOMINANT`** over both `S0` and `S1`. `S1D`:
`TRADEOFF_ONLY`, and dominated by `S1`.

The H3 pattern reproduces exactly as item 33 predicted. The *interpretation*
does not survive §8: dominance on an axis with no demonstrated operational
consequence is dominance on an assumption.

## 13. S2 Ablations

The experiment that decides the question. Gains in D top-share:

**M1 (intermittent, longest A-closed run ≈ 0.36 s):**

| term | detector gain (coupled − S1) | split gain (split − coupled) |
|---|---|---|
| h_acc | **+0.138138** | +0.002002 |
| status | −0.836837 | 0.000000 |
| both | −0.017017 | +0.146146 |

**Every synthetic pattern:**

| pattern | longest A-closed run | detector gain | split gain |
|---|---|---|---|
| `P0_ALL_VALID` | 0.0 s | 0.0000 | 0.0000 |
| `P1_BURST_BELOW_TAU` | 0.0 s | 0.0000 | 0.0000 |
| `P2_ALTERNATING` | 0.2 s | 0.0000 | 0.0000 |
| `P4_CLUSTERED` | 0.8 s | 0.0000 | 0.0000 |
| `P1_BURST_ABOVE_TAU` | 1.0 s | **0.0000** | +0.0206 |
| `P5_PERMANENT` | 34.0 s | **0.0000** | **+0.9611** |

**Detector gain is exactly zero on every pattern.** The coupled controls, which
carry the identical evidence terms, gain nothing at all. Under sustained
invalidity the split is the whole effect.

On the real recording it is the other way round. That is the confound, and it
resolves into a statement rather than a contradiction: **the split earns its
complexity in proportion to how long A stays closed at a stretch.** T5 gives
the mechanism — the frozen smoother forgets a saturated fault in 7.29 ticks
(0.29 s), so evidence alternating faster than that averages away, and a
coupled architecture keeps seeing the receiver during the valid gaps.

Note also that **closed *fraction* is not the predictor**: `P2` has A closed
half the time and gains nothing; `P1_BURST_ABOVE_TAU` has A closed 3% of the
time and gains something.

## 14. Temporal Pattern Results

`results/TEMPORAL_PATTERN_RESULTS.csv`, eight patterns × ten arms. Summarised
in §13. Scope: these fixtures program the GNSS validity schedule over the real
non-GNSS carrier and hold the GNSS payload constant, so they measure the gate
and the status/h_acc terms — not physics residuals. Every trust and posterior
number attributed to real data comes from M1.

## 15. Transport-vs-Sensor-Invalidity Separation

The cleanest single result in the package. `P5_PERMANENT` and
`T_TRANSPORT_STARVED` produce **identical operational state** — A closed for
34.0 s in both — and opposite diagnoses:

| | `S2a` final `gps_fault` | leading cause |
|---|---|---|
| receiver reports no fix | **0.894386** | `gps_fault` |
| healthy receiver, no messages | **0.022723** | `nominal` |

`0.022723` is the coupled steady state from T4 — exactly the prior. Every
coupled arm says `nominal` in **both**. This is T3's necessity direction
confirmed: the split cannot manufacture evidence that was never observed, and
it does not try to.

## 16. Cross-Ingest-Path Semantics

120 words over `{V, I, N}` up to length 4, driven through the v1.1 adapter and
through the committed `csia/runtime/plugins.py` decoder.

* **79/120 diverge semantically** — does this path ever mark the GPS slot
  invalid? Shortest divergent word: **`'I'`**, one message reporting no fix.
* 106/120 differ in A-closed tick counts, but that also moves with the stamping
  convention (tick time vs message receive time) and is **not** counted as
  semantic divergence.

The same raw condition means different things depending on which decoder a
deployment happens to use, into the same frozen core.

## 17. Minimal Counterexample

`MINIMAL_COUNTEREXAMPLE.md`. Two hypotheses, two features, closed form:

| regime | `D_value` | `D_status` | steady `P(fault)` |
|---|---|---|---|
| healthy | 1 | 1 | 0.000000 |
| fault, coupled | 0 | 0 | **0.022727** |
| fault, split | 0 | 1 | **0.894404** |

Under coupling a sustained GNSS fault leaves the posterior at **exactly the
prior** — not weakly detected; the log ratio is `log(π_a/π_b)` with no evidence
term at all, while the fault is still happening.

## 18. Formal Results

`FORMAL_RESULTS.md`. T1 evidence deletion; T2 self-masking faults (necessary
and sufficient condition, satisfied here by construction); T3 what the split
can and cannot restore (necessity gives the transport prediction); T4
steady-state posterior; T5 time to rank reversal. All
`PROVED — NOVELTY NOT ESTABLISHED`.

**T4 validated against the implementation:**

| arm | predicted (2 hypotheses) | measured (8-cause softmax) | diff |
|---|---|---|---|
| `S1D` coupled | 0.022727 | 0.022723 | 4 × 10⁻⁶ |
| `S2a` split | 0.894404 | 0.894386 | 1.8 × 10⁻⁵ |

The theory predicts the experiment, not the other way round.

## 19. Information-Loss Analysis

Exact, on stated distributions — one recording cannot support a KL estimate and
none is offered.

| mapping | `D_KL` downstream | loss (nats) | states collapsed |
|---|---|---|---|
| `φ_S0` drop-invalid | 0.000000 | **2.456816** | 1 |
| `φ_S1` coupled | 0.000000 | **2.456816** | 1 |
| `φ_S2` split | 2.456816 | 0.000000 | 0 |

Upstream `D_KL = 2.456816`. Under S0 and S1 it is *entirely* destroyed: a
failed receiver and a failed link become the same downstream distribution, so
no downstream procedure whatsoever can tell them apart. The data-processing
inequality is textbook; nothing here claims it or this application is novel.

## 20. Counterexample Generator

Feasible, and it found things. Shortest pair of distinct raw words with
identical downstream state:

| arm | witness | length |
|---|---|---|
| `S0` | `('I', 'N')` | **1** |
| `S1` | `('VV', 'IV')` | 2 |
| `S2c2` | `('III', 'INI')` | 3 |

The search also **caught a bug in this study's own instrument** (§24, N2) by
reporting that `'IV'` and `'VV'` were indistinguishable under a split arm,
which cannot be true if the status feature works.

**Checker feasibility (item 28): MODERATE.** The dynamic half is demonstrated —
a few hundred replays over a three-symbol alphabet found the length-1 witness
with no domain knowledge. What is *not* demonstrated is the static half:
detecting `INVALID → NO_UPDATE` or `RETAINED → CURRENT` by analysis rather than
by execution would need a dataflow analysis over the adapter/core boundary that
nothing here prototypes. `HIGH` would require that; `LOW` would understate a
working dynamic search.

## 21. Cross-Sensor Audit

Source only. No cross-sensor experiment was run.

| family | criteria met | candidate | blocker |
|---|---|---|---|
| **gnss** | **4/4** | **yes** | – |
| battery | 3/4 | no | the `-1` sentinel reject does not delete the retained value |
| vibration | 2/4 | no | no explicit INVALID state |
| esc, estimator, imu0, imu1, magnetometer | 1/4 | no | no explicit INVALID state; several have no operational consumer |
| barometer | 0/4 | no | all four |

**GNSS is the only candidate in this stack.** Reviewer G is conceded outright.
Battery is the near-miss and the natural second modality: it has an explicit
sentinel path, a failsafe consumer, and rich health fields
(`battery_remaining`, `fault_bitmask`, `charge_state`) — its only blocker is
one missing line.

## 22. Compute Cost

| arm | µs/tick |
|---|---|
| `S0` | 1048.22 |
| `S1` | 1080.35 |
| `S2c` | 1050.69 |

No measurable cost: 2 extra features per tick in an already-linear likelihood
loop, 3 extra state fields per monitored source. The figures include MAVLink
decoding and the whole adapter path, so they are an upper bound on the arm's
own cost rather than a measurement of it.

## 23. Clean Controls

Two fixtures: the real pre-onset segment of M1, and a synthetic all-valid
schedule over the full duration.

**No arm leads with `gps_fault` on any tick of either.** But the arms are *not*
identical: `S0`/`S1` end at `6.4 × 10⁻⁵`, every added-feature arm at `0.0`. A
healthy h_acc is maximally consistent, which actively pushes `gps_fault` down.
Directionally safe — fewer false alarms — but it is a change, and both fixtures
are short and one holds the GNSS payload constant. Real-flight false-alarm
behaviour is untested; that is LEVEL 3 of the HIL plan.

## 24. Negative Results

**N1 — the binary status encoding is harmful under intermittent invalidity.**
`S2a` scores 0.000 on M1 against `S1`'s 0.837. `c_status = 1` on a valid
observation is maximally consistent, i.e. strong evidence for `nominal`; with
71% of M1 observations valid, the status term spends most ticks arguing against
the fault. It is decisive under sustained invalidity and destructive under
intermittent invalidity. Consequence: `S2c` is **worse** than `S2b` on M1
(0.966 vs 0.977) — the best arm on real data is the one without the status
feature.

**N2 — this study's first detector-dominance reading was wrong.** It reported
`S1D − S1 = +0.126`, `S2c − S1D = +0.002`; the corrected values are `−0.017`
and `+0.146`. Cause: the sidecar held "the last thing I saw" instead of being
time-indexed, and the core emits the tick at τ only once a *later* sample
arrives — so the sidecar answered a query for τ with state from after τ, and
the coupled arm saw evidence at ticks where A was actually closed. Found by the
counterexample search. Fixed with an ordered log and as-of lookup; no constant
changed.

**N3 — this study reproduced the very defect the previous package documented.**
Gating h_acc evidence on *any* message arrival meant a healthy pre-onset
accuracy kept being served as current while every arriving message carried
`h_acc = 0`. Under `P5_PERMANENT` that made `S2c` report `nominal` (0.000)
while `S2a` reported `gps_fault` (0.961). Arms `S2b2`/`S2c2` gate on the last
message carrying a *usable* h_acc; labelled POST_HOC everywhere. **It cannot be
accused of rescuing the M1 result because it does not change it** — `S2b2` ≡
`S2b` and `S2c2` ≡ `S2c` to six decimals there.

**N4 — the operational objective has no operational consequence.** §8.

**N5 — `S2b`'s 4/4 aliasing score is an artefact of N3.** It distinguishes
`SENSOR_INVALID` from `TRANSPORT_MISSING` only because invalid messages keep
the stale h_acc alive. `S2c2` reaches 4/4 without relying on that.

## 25. Unexpected Results

* **`S1D` is dominated by `S1`.** Adding both evidence terms *under coupling*
  makes the diagnosis worse than adding nothing (0.820 vs 0.837), because the
  status term's nominal-supporting side survives the gate while its
  fault-supporting side does not. Coupling does not merely fail to help; here
  it converts a useful term into a harmful one.
* **The best arm on real data barely needs the split.** `S1Db` (h_acc, coupled)
  = 0.975 against `S2b` (h_acc, split) = 0.977.
* **Closed *fraction* does not predict the split's value; sustained closure
  duration does.** `P2` at 50% closed gains nothing; `P1_BURST_ABOVE_TAU` at 3%
  closed gains something.
* **The counterexample search found a bug in the instrument, not in the
  system.** That is the search working.

## 26. Hostile Review A–J

**A. "You just invented two booleans."** Rebutted with measurement, not
argument: `P5_PERMANENT` vs `T_TRANSPORT_STARVED` have identical operational
state (A closed 34.0 s) and posteriors of 0.894 vs 0.023 under the split, 0.023
vs 0.023 under every coupled arm. The two booleans take different values on
real decoded telemetry and the difference is the diagnosis.

**B. "Safety systems already separate validity and status."** Conceded
entirely. `NOVELTY: NOT ESTABLISHED`, no search was run, and the contribution
cannot be the existence of validity/status metadata. What is offered is a
measured instance in one implemented architecture, with a closed-form model
validated to 1 × 10⁻⁵ and a necessary-and-sufficient condition (T2/T3).

**C. "S2 just bypasses the safety gate."** Refuted from source. Under every
propagating arm the adapter emits `valid=False`, so the *frozen core* closes
`gvalid` and `fresh`, and every value-bearing relation —
`altitude_baro`, `velocity_gps_doppler_0/1`, `heading_course`, `phys_gps` — is
gated off by code this study does not touch. `objective_O = 0.996` for every
split arm, identical to the coupled ones. The split adds features; it removes
no gate.

**D. "The invalid measurement is still being used."** It is not.
`VALUE_VS_STATUS_EVIDENCE_MATRIX.csv` classifies every field by one question —
does its meaning depend on the navigation solution being valid? `gnss.position`
and `gnss.velocity` are VALUE and are deleted by the adapter on `fix_type < 3`;
no arm can readmit them. A test asserts that the only features any arm may add
to `gps_fault` are the two STATUS ones.

**E. "Your diagnosis improves because you added a detector."** On the real
recording, **yes** — and the report says so in §1, §13 and the ledger. The
h_acc term with D coupled to A recovers +0.138 and the split adds +0.002. On
every synthetic pattern the detector gain is exactly 0.0000 and the split gain
is the whole effect. The matched coupled controls exist precisely so this
question has a number rather than an opinion.

**F. "The original drop-invalid behaviour was actually better."** On the
diagnostic axis alone it very nearly is: `S0` = 0.964 against `S2c` = 0.966, and
`S0` beats `S1` outright. `S0` loses only on O — an axis with no demonstrated
operational consequence (§8). Both objectives are reported; diagnostic
performance is not treated as the only notion of correctness.

**G. "The result is GNSS-specific."** Conceded, with the audit that proves it:
GNSS is the only 4/4 candidate in this stack, and six of ten families have no
explicit INVALID state at all.

**H. "This is simulator-only."** Conceded. No hardware was connected.
`PHYSICAL_HIL_VALIDATION_PLAN.md` specifies three levels with pass/fail
criteria stated in advance, including the criteria under which the split fails.

**I. "All this follows trivially from multiplying evidence by zero."** The
algebra is trivial — T1 is three lines and is labelled `PROVED — NOVELTY NOT
ESTABLISHED`. Three things are not algebra: that this implementation *does*
couple them (source audit); that a fault which closes the gate is the same
fault the gate was needed to diagnose (T2's containment condition, satisfied
by construction because `gps_fault` has a singleton feature set); and the
measured regime boundary — sustained-closure duration, not closed fraction —
which no amount of multiplying by zero predicts.

**J. "You searched for this after prior hypotheses failed."** Conceded, and the
chronology is on the record: MAER stopped at 0/100 trials, the invalidity-
masking package refuted its own harm hypothesis, and this question came out of
that refutation. Everything here is exploratory. A frozen preregistration and
an independent trace set are mandatory before any manuscript claim —
`DUAL_ADMISSIBILITY_PREREGISTRATION_DRAFT.md`.

## 27. Claim Ledger

`CLAIM_LEDGER.json` — 20 entries, each with evidence class, status, assumptions,
strongest allowed wording, forbidden stronger wording, and the next experiment.
Five are negative results kept deliberately; one records a refuted earlier
reading from inside this same study.

## 28. What This Establishes

* One value, `fresh[]`, is both the operational and the diagnostic gate in this
  implementation. **Source-verified.**
* A fault that closes that gate can drive the hypothesis it supports to exactly
  its prior, while the fault is happening. **Proved and numerically validated
  to 1 × 10⁻⁵.**
* Splitting D from A recovers attribution **if and only if** an observable
  outside the coupled gate discriminates the pair — with the transport control
  confirming the necessity direction.
* The split's value scales with **sustained** A-closure duration, not with the
  fraction of time A is closed. **Provisional, four points.**
* Three committed ingest paths give the same raw condition different meanings;
  the shortest witness is one message. **Source-verified and search-confirmed.**
* GNSS is the only sensor family in this stack with the ingredients.

## 29. What This Does NOT Establish

* That A and D need separating in assurance architectures generally.
* That the operational improvement is worth anything: it changed no
  recommendation on the one real recording.
* That the split beats the coupled alternative on real data: it does not, once
  the h_acc term is present (+0.002).
* That the status encoding is a good one: it is harmful under intermittent
  invalidity.
* That any of it generalises past GNSS.
* That any of it survives hardware. Nothing here is a hardware result.
* Novelty of anything, in any form.

## 30. Physical/HIL Validation Plan

`PHYSICAL_HIL_VALIDATION_PLAN.md`. LEVEL 1 deterministic UBX emulator → real
flight controller (the only level with a programmable independent variable, and
where a frozen preregistration should first apply); LEVEL 2 real receiver under
**conducted, shielded** impairment only; LEVEL 3 clean real flight in passive
shadow, for the false-alarm question the software controls answer least well.
No radiated jamming or spoofing is proposed at any level.

## 31. Novelty Status

**NOT ESTABLISHED.** No literature search was performed. Separating validity
from status metadata is long-standing practice in avionics and in real-time
middleware. The words *novel*, *first*, *unprecedented*, *new theorem* and *new
paradigm* appear nowhere in this package except in this sentence saying they do
not.

## 32. Recommendation

1. **Do not adopt S2.** On the one real recording the coupled arm with an h_acc
   term is within 0.002 of the best split arm, and the split's operational
   benefit changed nothing an operator would see.
2. **Do fix the cross-ingest-path inconsistency** (§16). That is a defect
   independent of everything else in this study: the same raw condition means
   different things in three committed decoders, undocumented, into one frozen
   core.
3. **Run the sustained-closure sweep** before anything else. The whole
   conditional result rests on four points and one fixture family; test T5's
   0.29 s time constant directly against a fine sweep of closure duration.
4. **Then preregister**, and confirm on traces not used to design S2. Nothing
   here is confirmatory.
5. **Do not write the word "novel"** until someone searches the on-off-attack
   and real-time-middleware literature.
