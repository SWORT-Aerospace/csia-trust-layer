# WP-C3 — The Effective Signature Matrix and Diagnostic Reliability Structure

**Date:** 2026-08-22 · **Branch:** `research/wp_e1` · **Not merged to main**
**Suite:** 463 → **467**. One production change, separately authorized: the
IMU repair promoted to default.
**Artifacts:** `research/wp_c3/results/`, `figures/wp_c3_*.png`

---

## 1. Verdict

**The gap is not zero.** Design-time isolability analysis on `S` says CSIA is
fully isolable — κ(S) = 0.000, all eight hypotheses distinguishable. The
effective analysis says it is not: κ(S_eff) = 0.1429. **Standard practice
overstates this aircraft's achievable isolability by exactly one distinction
in seven, and the overstated distinction is `gps_fault` versus `nominal`** —
the safety-critical one, and the one with no repair inside the current feature
set. The self-occlusion index isolates the cause: `SOI(gps_fault) = 1.0`, the
only hypothesis above zero, meaning a GPS fault destroys **100%** of its own
evidence. The reliability structure then ranks components by diagnostic
criticality and disagrees informatively with the WP-C1 sole-protector ranking.
The design rule falls out with exactly one violation, now pinned by a test.
Neither object is claimed as novel; full-text access is still blocked.

---

## 2. Promotion of the IMU repair (authorized, separate commit)

`attitude_gravity_mag` is now in `imu0_bias_drift`'s production LOW signature.

- **WP1 finding F-D1 is repaired.** The lock test that preserved it as a
  documented counterexample became a repair regression test: it now asserts
  the signatures stay distinct with the motor edges gated off, that the repair
  stays asymmetric between the units, and that the posterior favours the
  correct unit in *both* directions.
- **Measured:** peak `P(imu0_bias_drift)` = 0.9203 in production, matching the
  WP-C2 "after" value exactly. Latency and min-trust unchanged on all five
  scenarios; clean false positives 0/999. `campaigns/bench.json` regenerates
  bit-identical.
- **The WP-C2 flag is retained as a no-op** so the before/after experiment
  stays re-runnable, and the flag tests were inverted to pin the promotion —
  a silent revert now fails the build.

**A factual error in the WP1 record, corrected while regenerating it.**
Version 1.0.0 of `diagnostic_signature_matrix.yaml` listed `temp_gps` among
`features_removed` for the GPS-invalid modes. `bayes.py:135-136` gates every
`temp_*` feature with `np.ones` unconditionally, so no gate can close it. The
record therefore reported a **three-way** collision (`gps_fault` ≡ `nominal` ≡
`unexpected_maneuver`) where source gives a **two-way** one. This is the
discrepancy WP-E1 flagged from an independent recomputation; here it is fixed
at source, and the artifact is at 1.1.0 with both changes in its changelog.

---

## 3. Part 1 — the effective signature matrix

### 3.1 `closes(h, g)`, and how much of it source supports

**29 of 32 cells (91%) are derived from source.** Three are `UNKNOWN`, all on
`speed_gate`.

| Gate | Closed by | Basis |
|---|---|---|
| `armed_gate` | **nothing** | reads vehicle arming state and elapsed time (`online.py:491-496`); no monitored channel feeds it. Closure is exogenous to every hypothesis. |
| `gps_warmup` | **nothing** | pure elapsed time, `ticks > 3.0` (`comparator.py:199`). |
| `gvalid` | **`gps_fault`** | fix validity (`comparator.py:115`; `fix_type >= 3` at `ulog_source.py:178`). Denial, jamming and many spoofing modes invalidate the fix. **The canonical endogenous gate.** |
| `speed_gate` | `gps_fault`, `power_fault`, `unexpected_maneuver` = **UNKNOWN** | computed from GPS-derived horizontal velocity (`comparator.py:112-113`). A GPS fault perturbs its input, but whether it drives the gate *closed* depends on the spoof's velocity profile, which the fault model does not fix. Not derivable from source. |

**The uncertainty does not matter here, and that is worth stating.** Computing
`S_eff` with every `UNKNOWN` treated as open and again with every `UNKNOWN`
treated as closed gives the **identical** result — κ, the partition, the merged
pair, and the SOI ranking are unchanged. `speed_gate` controls only
`heading_course`, which is not the sole feature of any hypothesis, so it cannot
move the partition either way. **91% coverage is sufficient for this
conclusion.**

### 3.2 The gap

| | Classes | κ |
|---|---|---|
| Π(S) — classical design-time | 8 | **0.000000** |
| Π(S_eff) — effective | 7 | **0.142857** |
| **Gap** | | **0.142857 = 1/7** |

Merged only in `S_eff`: **`gps_fault` + `nominal`**.

**Theorem verified.** Π(S_eff) ⪰ Π(S) held across the full hypothesis set in
both UNKNOWN treatments; no violation, as expected from `S_eff ≤ S` entrywise.

**The consequence, stated plainly.** Any design-time isolability analysis of
this aircraft — the standard artifact, the isolability matrix every FDI text
prescribes — reports full isolability. It is wrong by one distinction in
seven, and the one it gets wrong is the pair that decides whether the vehicle
commands `SWITCH_NAV_INERTIAL` and `INHIBIT_GPS_MODES` or does nothing at all.

### 3.3 Self-occlusion index

| Hypothesis | SOI | Evidence it silences |
|---|---|---|
| **`gps_fault`** | **1.0000** | `phys_gps` — its only feature |
| all seven others | 0.0000 | — |

**Exactly one hypothesis exceeds 0.5, and it is completely self-shielding.**
Every feature that would reveal a GPS fault is a feature a GPS fault silences.

**Cross-check against WP-C1's exposed critical pairs:** the two were
`gps_fault`+`nominal` and `imu0`+`imu1`. Post-promotion the IMU pair is
repaired, and `SOI(imu0_bias_drift) = 0` — the repair worked precisely because
`attitude_gravity_mag` is ungated, so nothing the fault does can silence it.
The remaining exposed pair is the one with SOI = 1. **The two independent
constructions agree exactly.**

---

## 4. Part 2 — diagnostic reliability structure

12 components (4 gates + 8 channels), 4096 states. **All 27 critical pairs
verified monotone** — φ never unmerges under added failures — so coherent-system
theory applies without the non-coherent extensions.

### 4.1 Order-one cut sets: single points of diagnostic failure

| Pair | Single failures that merge it |
|---|---|
| **`gps_fault` + `nominal`** | `channel:gps`, `gps_warmup`, **`gvalid`** |
| `gps_fault` + `unexpected_maneuver` | `channel:gps` |
| `imu0_bias_drift` + `nominal` | `channel:imu0` |
| `imu1_bias_drift` + `nominal` | `channel:imu1` |
| `mag_interference` + `nominal` | `channel:mag` |
| `nominal` + `vibration_anomaly` | `channel:vibration` |

`gps_fault` ≡ `nominal` has **three** order-one cut sets — the only pair with
more than one. Three independent single failures each destroy it.

### 4.2 Birnbaum importance — and where it disagrees with WP-C1

| Rank | Component | Birnbaum | WP-C1 sole-protector |
|---|---|---|---|
| 1 | `channel:mag` | 0.2028 | 2 |
| 2 | `channel:imu0` | 0.1751 | 4 |
| 3 | `channel:gps` | 0.1635 | 1 |
| 4 | `channel:vibration` | 0.1632 | 2 |
| 5 | `channel:motor_esc` | 0.1218 | **0** |
| 6 | `channel:imu1` | 0.1166 | 4 |
| 7 | `channel:battery` | 0.0880 | **0** |
| 8 | `armed_gate` | 0.0339 | — |
| 9 | `gps_warmup` | 0.0327 | — |
| **10** | **`gvalid`** | **0.0327** | — |
| 11 | `speed_gate` | **0.0000** | — |
| 12 | `channel:baro` | **0.0000** | 0 |

Three disagreements worth naming:

- **`motor_esc` and `battery` rank 5th and 7th by Birnbaum but zero by
  sole-protector.** They matter in many environments and are uniquely
  necessary in none. That is the exact signature of redundancy, and it is why
  the two rankings must both be read: sole-protector finds single points of
  failure, Birnbaum finds where effort is generally leveraged.
- **`gvalid` ranks 10 of 12 — near the bottom — yet owns the unrepairable
  exposure.** Importance is not criticality. A component can matter in few
  environments and still be the sole cause of the one failure you cannot fix.
  Ranking by Birnbaum alone would deprioritise the GPS problem.
- **`mag` is now the single most diagnostically important component**, above
  both IMUs. This is a **consequence of the promotion we just made**: adding
  `attitude_gravity_mag` to `imu0_bias_drift` routed IMU discrimination
  through the magnetometer. We traded an IMU collision for increased reliance
  on `mag`. The trade is favourable — `mag` was already 4th and the collision
  was decision-critical — but it is a real coupling and it should be named
  rather than discovered later.
- **`speed_gate` and `channel:baro` are exactly 0.0000.** `speed_gate`
  confirms WP-E1's κ = 0 finding through a completely independent metric.
  `baro` flips no critical pair in any of 4096 states.

### 4.3 The probability bridge — symbolic, deliberately

```
P(φ_ab = 1) = Σ_s [ Π_{c∈s} q_c · Π_{c∉s} (1 − q_c) · φ_ab(s) ]
```

The operationally meaningful form is **conditional**, because closure
probabilities are hypothesis-dependent:

```
P(φ_ab = 1 | h_a true)      with q_gvalid | gps_fault  ≠  q_gvalid | nominal
```

**STATUS: NOT COMPUTABLE.** No per-gate closure probability and no
per-channel unavailability probability exists anywhere in this repository — no
emission table, no reliability block, no measured rates. **No probability was
invented; the expression is left symbolic.**

**The single measurement that unlocks it:** `q_gvalid` conditioned on
hypothesis — P(`gvalid` closed | `gps_fault`) versus P(`gvalid` closed |
`nominal`) — from per-tick gate traces on real logs. It is the same
measurement WP-E2 needs, and it converts every structural result in WP-C1
through WP-C3 into a risk statement.

The ≈45:1 figure supplied externally is **not used in any computation here**.

---

## 5. Part 3 — the design rule

> **A feature intended to discriminate hypothesis `h` must not be gated by any
> gate that `h` closes.**

Audit over all 19 signature entries: **18 clean, 1 violation, 0 at-risk.**

| Hypothesis | Feature | Closed by | Severity |
|---|---|---|---|
| `gps_fault` | `phys_gps` | `gvalid` | **FATAL — sole feature** |

The severity distinction matters: a violation on one of several features
merely weakens a hypothesis; a violation on its **sole** feature empties the
effective signature and absorbs it into `nominal`. This is the only violation
and it is the fatal kind.

**Now enforced.** `tests/test_signature_design_rule.py` pins the violation
list exactly — a *new* violation fails the build, and the known one failing to
appear also fails, so a silent repair cannot land without updating the record.
It also asserts the IMU repair introduced no violation, which is the property
that made it work.

**No repair proposed here.** WP-C2 Part 3 already ranked the candidates and
recommended `gps_cn0_stats`; the rule explains *why* that recommendation is
the right shape — not because of its physics, but because its gate is
independent of `gvalid`.

---

## 6. What this still cannot say

1. **`closes(h,g)` is derived, not measured.** If a fault closes a gate in
   flight that the model says it does not, `S_eff` is wrong **in the
   optimistic direction** — the real gap would be larger than 1/7.
2. **No frequency.** Structure only. `q_gvalid` is unmeasured.
3. **Structural, not statistical.** Merged pairs may still separate on
   magnitude or variance.
4. **Novelty unresolved.** Zero full texts read across WP-C1–C3.
5. **`D_critical` and the response map are implementation-dependent**;
   changing the failsafe action set invalidates every number here.

---

## 7. What I got wrong, and what surprised me

**Nothing was refuted this round, which is itself worth flagging** — after
three consecutive work packages where a hypothesis died, this one confirmed
its premise. The gap could have been zero and I said so in advance; it was not.

Two smaller errors, both caught before they propagated:

- The first `S_eff` run crashed serialising tuple-keyed rationale to JSON.
  Trivial, but it meant the rationale table was nearly dropped rather than
  fixed — the fix preserves the per-cell justification, which is the part a
  reviewer will actually check.
- `test_flag_is_now_a_no_op_after_promotion` initially compared sorted lists
  and failed on ordering, not content, because `repaired_causes` sorts only
  the entry it touches. Fixed to compare as sets.

Three things surprised me:

- **The UNKNOWN cells turned out not to matter.** I expected to carry two
  divergent answers through the whole report. Both treatments give the
  identical partition, which makes the 91% coverage sufficient rather than
  merely honest.
- **`gvalid` ranks 10th of 12 by Birnbaum importance.** The gate that owns the
  only unrepairable exposure is near the *bottom* of the diagnostic importance
  ranking. Importance and criticality come apart sharply here, and a programme
  that prioritised by importance alone would work on `mag` and never reach the
  GPS problem.
- **The promotion made `mag` the most diagnostically important component in
  the aircraft.** We fixed the IMU collision by routing IMU discrimination
  through the magnetometer.

  > **SUPERSEDED by WP-C4 §2.5.** This section originally called that a
  > "trade" and a "real coupling". The cut-set test says otherwise: the
  > promotion created **no new order-one cut set** at `channel:mag`, and the
  > set of components appearing in any order-one cut set *shrank* from 9 to 7
  > (`armed_gate` and `channel:motor_esc` dropped out). Birnbaum importance
  > rose for `mag` without creating a new single point of diagnostic failure.
  > The trade framing was too pessimistic; it was a strict improvement.

---

## 8. Open, with owners

| Item | Owner | Blocking |
|---|---|---|
| `q_gvalid` conditioned on hypothesis | WP-E2 | corpus re-acquisition — **the measurement that unlocks every risk statement** |
| Resolve the three `speed_gate` UNKNOWNs | WP-E2 | per-tick gate traces (low priority: does not change the partition) |
| Implement `gps_cn0_stats` | Engineering | GPS field plumbing, then corpus confirmation |
| Full-text novelty attack, both objects | You | egress policy; list extended in `research/wp_c3/NOVELTY_ATTACK.md` |
| Watch the new `mag` coupling | Design | consider whether IMU discrimination should have a second, mag-independent route |
| `SWORT_CSIA.pdf` + submission date | You | four documents still blocked |
