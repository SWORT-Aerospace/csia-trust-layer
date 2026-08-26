# MAER — Preregistration Review Report

Self-contained. The reviewer is assumed to have no repository access.
**No scored trial has been run.** The preregistration is committed; the campaign
is not started.

---

## 1. Seed / variation mechanism found

**Jam onset time. No seed mechanism exists in ArduPilot, and none was added.**

Searched and confirmed absent:

```
get_random16()   libraries/AP_Math/AP_Math.cpp:350
                 static uint32_t m_z = 1234, m_w = 76542;
                 hard-coded, never reseeded. Drives num_sats.
rand_float()     SITL branch returns libc random(); ArduPilot calls
                 srandom() nowhere outside the bundled Lua interpreter.
                 Drives horizontal_acc -> h_acc.
SIM_ parameters  no seed parameter exists.
```

Both generators therefore replay the same sequence every boot, which is exactly
why Stage 0.5's five runs were byte-identical.

The sequence is nonetheless **consumed over time** by every other SITL user of
those generators, so generator state at the moment jamming begins is a function
of elapsed runtime. Changing the onset changes that state without touching the
jamming model, the distribution, or any simulator source. This is the brief's
option C, admitted only because it was verified to work.

## 2. Was a simulator patch required?

**No.** No file in ArduPilot, PX4 or CSIA's frozen core was modified. The
simulator is stock at `ArduCopter V4.8.0-dev@01a504b`.

## 3. Exact simulator diff

**None.** There is no diff to report.

## 4. Number of genuinely distinct candidate trajectories

**10 of 10 distinct**, all usable.

Onsets 8, 11, 14, 17, 20, 23, 26, 29, 32, 35 s; 40 s of jamming each;
distinctness judged on SHA-256 of the `(fix_type, satellites_visible, h_acc)`
jam sequence — the same signature that exposed the Stage 0.5 replays.

| onset (s) | jam msgs | invalid-fix msgs | `h_acc` distinct while invalid | signature |
|---|---|---|---|---|
| 8 | 400 | 144 | 30 | `3521782f…` |
| 11 | 400 | 146 | 34 | `56817e60…` |
| 14 | 400 | 143 | 32 | `c216bfa0…` |
| 17 | 400 | 140 | 37 | `e923f2cd…` |
| 20 | 400 | 155 | 32 | `58729325…` |
| 23 | 400 | 140 | 32 | `dc5ceac3…` |
| 26 | 400 | 149 | 31 | `97762114…` |
| 29 | 400 | 142 | 29 | `205b9196…` |
| 32 | 400 | 144 | 28 | `443dd4d2…` |
| 35 | 400 | 134 | 27 | `c6bda904…` |

Every trajectory has invalid-fix ticks present **and** live `h_acc`, so all 10
satisfy the validity criterion. Requirement was ≥ 5.

The Stage 0.5 five runs remain committed as evidence of the determinism
finding, and are counted as **one** realisation, not five.

## 5. Final `h_acc` transform equation

```
h0    = 300 mm
resid = log(1 + max(0, h_acc - h0) / h0)
sigma = log(2) = 0.693147
lam   = EWMA_0.15( (resid / sigma)^2 )
```

consumed downstream by the layer's existing map,
`consistency(lam) = exp(-0.5 * max(0, lam - 1))`.

Worked points (pre-EWMA `lam`):

| `h_acc` | `lam` | `consistency` |
|---|---|---|
| 300 (nominal) | 0.00 | 1.000 |
| 600 (2× nominal) | 1.00 | 1.000 |
| 3000 | 11.04 | 0.007 |
| 300000 | 99.32 | ~0 |

## 6. Why every constant was selected

| constant | value | justification |
|---|---|---|
| `h0` | 300 mm | `SIM_GPS1_ACC` (0.3 m) × 1000 — the **declared** nominal receiver accuracy of the configuration under test. Read from the simulator parameter, not estimated from any trace, clean or faulted. |
| form | one-sided log | Accuracy better than nominal is not a fault, so the residual is zero below `h0`. Logarithmic because `h_acc` spans three decades under jamming. |
| `sigma` | `log 2` | **One doubling of excess error over nominal is one sigma.** An engineering statement about what counts as meaningful degradation, fixed before scoring. No fault separation was consulted. |
| EWMA α | 0.15 | The constant `_lam_upd` already uses. Not a new choice. |

**The Stage 0.5 form is withdrawn.** It divided by `max(MAD_clean, 1e-3)` on a
clean series whose MAD is zero — an arbitrary 1000× gain that would have let the
research arm win on scaling rather than information. I had already noted the
degenerate MAD and then covered it with a floor, which is the same mistake in
statistical clothing.

## 7. Evidence-scale comparison

Measured in the layer's own bounded space, because the logs contain consistency
scores rather than raw `lam` — comparing raw `lam` against them would not be
like-for-like.

| distribution (consistency, (0,1]) | n | p50 | mean |
|---|---|---|---|
| existing layer, clean flights | 48000 | 1.0 | 0.919 |
| existing layer, fault flights | 12000 | 1.0 | 0.918 |
| proposed `h_acc`, clean phase | 3163 | 1.0 | 1.000 |
| proposed `h_acc`, jam fix-valid | 4513 | 0.0 | 0.003 |
| proposed `h_acc`, jam fix-invalid | 2487 | 0.0 | 0.102 |

`consistency` is bounded in (0,1] by construction, so the contribution **cannot**
dominate the score by unit choice. That is a structural guarantee, not a tuned
one, and it is the real answer to the millimetres concern.

Checks: quiet on clean (p50 = 1.0) ✓; separates on fault (p50 = 0.0) ✓; same
bounded space as existing relations ✓.

**Declared property, not a discovery to be made later:** the contribution
**saturates**. `consistency` drops below 0.01 at `lam ≈ 10.2`, i.e. `h_acc ≈ 2.8×`
nominal. Under heavy jamming it is therefore a near-binary indicator, graded
only near the threshold. This follows from the declared sigma and must not be
retuned after scoring.

Incidental corroboration worth noting: the existing layer's fault-flight mean
(0.918) is indistinguishable from its clean mean (0.919). That is the
self-occlusion result arriving from a different direction — the layer's evidence
barely moves while the fault it was built to catch is active.

## 8. Exact A1 / A1G code difference

```python
# research-only sidecar; frozen core untouched
lam  = ewma.update((residual(h_acc) / SIGMA) ** 2)
gate = 1.0 if arm == "A1" else gvalid          # THE ONLY DIFFERENCE
contribution = (lam, gate)
```

Identical input, samples, transform, calibration constants, evidence mapping,
hypothesis association, temporal filter and normalization. One parameterised
factor on one code path.

A test must assert that A1 and A1G resolve to the same code path with only
`gate` differing. If any other difference exists, the causal interpretation
fails and the run is void.

## 9. H1 and H1b

**H1 (causal architectural).** Given a receiver-health residual that remains
live during periods of invalid GNSS navigation solution, placing that same
residual outside `gvalid` retains a nonzero diagnostic contribution during those
periods, whereas multiplying the identical residual by `gvalid` suppresses it.

**H1b (empirical diagnostic performance).** The ungated arm improves `gps_fault`
attribution relative to the matched gated control, without violating the clean
false-transition budget.

**They are separate and are reported separately. H1 may succeed while H1b
fails** — a contribution can survive the gate and still not change the
diagnosis. Conflating them would be the easiest way to overstate this result.

## 10. CUSUM crossover hypothesis

**H3.** A2 does not recover `gps_fault` support under M1 (evidence-loss), while
helping under M2 (persistence). The scientifically interesting quantity is
whether it helps M2 **substantially more** than M1.

CUSUM is tested on **both** mechanisms. The outcome is not assumed. **If CUSUM
recovers M1, H3 is refuted and that is the result**, reported as such.

Frozen parameters, unchanged from the existing validated detector: one-sided
CUSUM on the standardised pre-transform residual, `k = 0.5`, `h = 500.0`,
`mu0`/`sigma0` from the clean arm only, R10 clean alarms = 0, 0.618 µs/tick,
read-only on `_lam`.

## 11. Transport discrimination hypothesis

**H4.** The runtime distinguishes `STARVED_BY_TRANSPORT` (M3 — required evidence
absent or stale because the consumer link does not deliver fresh enough data)
from `EVIDENCE_GATE_CLOSED` (M1 — evidence delivered and degraded, applicability
changed), using only source / delivery / freshness / gate state.

**No injected-fault label may be an input to the classifier.** This matters more
now that the algorithm consumes raw receiver-health metadata: a starved link and
a degraded receiver must not collapse into one state.

## 12. Clean pass/fail criterion

**No assurance transition on any M0 trial, for any arm.** One or more clean
transitions = that arm **fails**, regardless of its fault performance. Fixed
before scoring.

## 13. Final experiment matrix

| | M0 CLEAN | M1 JAM | M2 RAMP | M3 TRANSPORT |
|---|---|---|---|---|
| A0 BASELINE | 5 | 5 | 5 | 5 |
| A1 RECEIVER_HEALTH_UNGATED | 5 | 5 | 5 | INAPPLICABLE |
| A1G RECEIVER_HEALTH_GATED | 5 | 5 | 5 | INAPPLICABLE |
| A2 CUSUM | 5 | 5 | 5 | 5 |
| A3 MECHANISM_AWARE_COMBINED | 5 | 5 | 5 | 5 |

**90 scored trials.** A1/A1G × M3 are INAPPLICABLE because M3 runs on PX4, where
every receiver-health candidate is a `DIRECT_ORACLE`. Marked, not manufactured.

The gate-event likelihood arm is removed and stays removed: two fix-loss flights
cannot support a calibration/test split.

## 14. Primary and secondary endpoints

**Primary, causal availability (H1).** Share of `gvalid = 0` ticks on which the
receiver-health contribution is nonzero — A1 vs A1G on identical traces.

**Primary, diagnostic performance (H1b).** Share of post-onset ticks on which
`gps_fault` is the top hypothesis — A1 vs A1G vs A0.

**Secondary.** `gps_fault` rank; unique-attribution share; unsupported-normal
exposure; time to first correct attribution; ambiguity duration; clean
transition count; runtime cost per tick.

Contribution survival is **not** synonymous with correct diagnosis; the two are
reported separately.

## 15. Invalid / replacement policy

Invalid only for declared mechanical reasons: simulator crash, no heartbeat,
injection readback failure, or a duplicate trajectory signature. Replacement
draws the next onset from the preregistered extension list (38, 41, 44, 47,
50 s).

**No trial may be excluded for its outcome.** Every rejection is recorded with
its reason.

## 16. Preregistration path

`research/maer/MAER_PREREGISTRATION.md`

## 17. Preregistration commit

`632e381`, 2026-08-26 06:38:44 +0000, branch
`claude/code-reviewer-repo-export-zicovg`. Committed **before** any scored
trial; no scored trial exists.

## 18. Remaining scientific blockers

1. **Simulation-bound.** No physical receiver data. `h_acc` under jamming is
   `|rand_float()| * 300`. Nothing here licenses a claim about real receivers.
2. **Structural arm is ArduPilot-only.** PX4 cannot host it, so this is not a
   cross-platform replication of H1.
3. **M1 is jamming, not the original fix-loss fault.** What transfers is the
   candidate family, not the physics.
4. **Trajectory variation is onset timing, not a true seed.** The distribution
   is untouched and the 10 trajectories are genuinely distinct, but they are not
   i.i.d. draws in a formal sense.
5. **Saturation.** Above ≈2.8× nominal the contribution is near-binary.

None of these blocks the campaign; all must appear in any write-up.

## 19. Hostile review

**"You replaced one arbitrary transform with another."**
`h0` is read from `SIM_GPS1_ACC`, a declared configuration parameter. `sigma` is
a stated engineering convention (one doubling = 1σ). The EWMA constant is the
layer's existing one. None is estimated from a trace. The withdrawn form's
`1e-3` had no such provenance — that is precisely why it was withdrawn.

**"`sigma = log 2` was still chosen by you, after seeing the data."**
Accepted as a residual risk. Mitigation: it is declared before scoring, it is
justified independently of fault separation, and the downstream saturation it
implies is disclosed rather than left to be found. A reviewer who thinks a
different sigma is better should say so **now**, before the campaign.

**"Onset variation is not real randomisation."**
Conceded, and stated as blocker 4. The claim is only that the 10 trajectories
are genuinely distinct, which was measured, not that they are i.i.d.

**"Experiment A with one trace proves nothing."**
Experiment A supports one narrow within-trace claim and is explicitly barred
from producing population statistics. Experiment B carries the robustness claim.
Separating them is the point.

**"The candidate is still a simulator artifact."**
Partly conceded. It is a `MODEL_GENERATED_HEALTH` output, not a physical
measurement, and the preregistration says so. What distinguishes it from the
rejected PX4 fields is that its instantaneous value is not recoverable from the
intervention variable — PX4's is, exactly.

**"H1 will trivially succeed — of course multiplying by zero removes a
contribution."**
Partly true, and it is why H1 and H1b are separated. H1's content is not the
arithmetic but the premise: that a fault-relevant residual **remains live** after
validity closure, which is what Stage 0.5 established and what the first
feasibility audit found to be false for every admitted CSIA residual. H1b
carries the non-trivial claim.

## 20. Recommendation

**`READY_FOR_SCORED_MAER`** — with the caveat that the campaign has deliberately
not been started, pending this review.

The two Stage 1 blockers are closed: the transform no longer wins by scaling,
and 10 genuinely distinct trajectories exist without patching the simulator.
The remaining items in §18 are limitations to carry into the write-up, not
blockers to running.

The single most useful thing a reviewer can do: **challenge `sigma = log 2`
now.** It is the one constant with real discretion in it, it is frozen on
commit, and changing it after scoring would create MAER_V2. If a different
convention is better justified, this is the moment.
