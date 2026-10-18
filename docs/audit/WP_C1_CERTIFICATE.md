# WP-C1 — Assurance Observability Certificate for CSIA

**Date:** 2026-08-22 · **Branch:** `research/wp_e1` · **Not merged to main**
**Suite:** 448 passed before and after. No production file modified.
**Artifacts:** `research/wp_c1/results/`, `figures/wp_c1_*.png`

> **This is not a novel method.** Worst-case diagnosability under sensor loss
> and isolability across operating modes are established results
> (Carvalho et al., Automatica 2013; the multi-mode structural-diagnosability
> line; Krysander & Frisk sensor placement; Blanke et al. on isolating only to
> the granularity reconfiguration requires). WP-C1 applies that machinery to
> CSIA. See `research/wp_c1/NOVELTY_ATTACK.md`, including its own severe
> limitation: no full text could be read, because every academic domain was
> refused by this environment's egress policy.

---

## Headline

**CSIA does not carry an assurance certificate.** Two decision-relevant fault
distinctions fail under gate closure alone, at full sensor availability, and
no admissibility assumption recovers them.

| | |
|---|---|
| Hypothesis pairs | 28 |
| Decision-relevant (`D_critical`) | **27** |
| Response-equivalent | 1 — `nominal` ≡ `unexpected_maneuver` |
| Guaranteed at full channel availability | 26 of 28 |
| **Critical pairs exposed** | **2** — `gps_fault`+`nominal`, `imu0_bias_drift`+`imu1_bias_drift` |
| `D_critical ⊆ Δ_guaranteed`? | **No, at every admissibility level** |

---

## 1. The joint lattice

A configuration `c = (G, X)`: `G` the closed gates, `X` the present channels.
A diagnostic feature is observable iff every channel it spans is in `X` and no
gate in `G` controls it.

**`C_reach` is not the product.** A gate whose every feature already has an
absent channel is *vacuous* — closing it changes nothing, so `(G ∪ {g}, X)`
is the same configuration as `(G, X)`. Canonicalising on that rule:

| | |
|---|---|
| Naive product (2⁴ gates × 2⁸ channels) | 4096 |
| Reachable `C_reach` | **1232** |
| Reduction | **×3.325** |

### κ_max by admissibility

`κ = (H − P)/(H − 1)`, H = 8. Unrestricted `κ_max = 1.0`, but only because the
empty channel set trivially collapses everything — **a non-degenerate
certificate requires an admissibility assumption**, and saying so is part of
the result.

| At least k of 8 channels | κ_max | Worst configuration |
|---|---|---|
| 8 | **0.2857** | `armed_gate` + `gps_warmup` closed |
| 7 | 0.4286 | same gates |
| 6 | 0.5714 | same gates |
| 5 | 0.7143 | same gates |
| 4 | 0.8571 | `armed_gate` closed |
| 3 | 0.8571 | — |
| ≤ 2 | 1.0000 | — |

The k = 8 value reproduces WP-E1's gate-only ceiling of 0.286 exactly. That
agreement between two independent enumerations is the main internal check on
this computation.

Over the corpus's own six channel configurations (19 reachable configurations
across 26 logs), **κ_max = 1.0** and `Δ_guaranteed` is **empty**.

---

## 2. Sub-additivity — and a test I got wrong

**Verdict: SUB-ADDITIVE**, at both levels.

- **Feature level:** additive by construction. A feature dies if its channel
  is absent **or** a controlling gate is closed, so joint feature loss is
  exactly the union of the marginals. 0 configurations exceed it.
- **Partition level:** 0 configurations merge a pair beyond the **transitive
  closure** of the two marginal merge relations.

My first version of this test reported **1784 super-additive configurations**.
It was wrong, and the error is instructive enough to keep in the output
(`pair_level_raw_union`). Merging is an *equivalence relation*; the union of
two merge relations is not one. If gate closure gives A ≡ B and channel
absence gives B ≡ C, then A ≡ C holds jointly **by transitivity alone**, with
no higher-order mechanism involved. Comparing joint merges against the raw
union of marginal merges counts every such transitive link as an interaction.

I found it by hand-verifying one concrete case rather than trusting the
aggregate: with only `gps` present and `gps_warmup` closed, the "novel" merges
were all of the form `gps_fault + <everything>`, which arises because gate
closure puts `gps_fault` in `nominal`'s class while channel absence puts
everything else there too.

**There is no higher-order interaction structure in this architecture.**

---

## 3. `D_critical` — the safety projection

Derived from the failsafe automaton's condition/action table
(`csia/runtime/failsafe.py:96-176`), **including action parameters**.

| Hypothesis | Commanded response |
|---|---|
| `nominal` | — |
| `unexpected_maneuver` | — |
| `gps_fault` | `SWITCH_NAV_INERTIAL`, `INHIBIT_GPS_MODES` |
| `imu0_bias_drift` | `SELECT_IMU(use=imu1)` |
| `imu1_bias_drift` | `SELECT_IMU(use=imu0)` |
| `mag_interference` | `HEADING_HOLD_GYRO` |
| `power_fault` | `REDUCE_POWER`, `LAND_NOW` |
| `vibration_anomaly` | `LIMIT_THROTTLE`, `LAND_SOON` |

Two consequences worth stating precisely:

- **`nominal` ≡ `unexpected_maneuver` is not a safety concern.** Both command
  nothing. The system's inability to tell an unexpected manoeuvre from healthy
  flight costs no safety property — it is exactly the case where "we cannot
  name the cause" does *not* imply "we cannot choose the response."
- **`imu0_bias_drift` ≡ `imu1_bias_drift` IS a safety concern**, even though
  both raise the same *condition*. `SELECT_IMU` carries `{"use": best_imu}`;
  the parameter differs, so the commanded response differs. Reading conditions
  without parameters would have wrongly cleared this pair.

### The certificate fails

`D_critical ⊄ Δ_guaranteed` at **every** admissibility level (see
`figures/wp_c1_certificate_curve.png`). At k = 8 the two exposed pairs are
both critical:

| Exposed critical pair | Minimal breaking configuration |
|---|---|
| `gps_fault` ≡ `nominal` | either `gvalid` or `gps_warmup` closed, all channels present |
| `imu0_bias_drift` ≡ `imu1_bias_drift` | `armed_gate` closed, all channels present |

Both are single-gate failures at full instrumentation. Neither requires
channel loss.

---

## 4. Design inverse

### 4.1 No minimal sufficient channel set exists

Both exposed critical pairs fail through **gate** closure at full channel
availability. No amount of instrumentation closes a gate-induced collision.
The channel-side design inverse is **vacuous** for this architecture; the
actionable lever is the signature matrix.

### 4.2 Marginal channel value

Critical pairs lost if the channel is removed:

| Channel | Critical pairs solely protected |
|---|---|
| `imu0` | **4** |
| `imu1` | **4** |
| `mag` | 2 |
| `vibration` | 2 |
| `gps` | 1 |
| `baro`, `battery`, `motor_esc` | **0** |

**Zero does not mean useless.** It means *covered by redundancy*: removing
`battery` still leaves `power_fault` distinguishable through
`accel_esc_rpm`, `accel_motor_current` and `phys_motor_esc`. These three
channels are **not single points of assurance failure** — which is a positive
architectural property, not a case for removing them.

`imu0` and `imu1` are the load-bearing channels, consistent with WP-A2 E1's
independent finding that removing `redundant_imu` destroys IMU fault detection
outright.

### 4.3 Cheapest repair

Search constrained to physically admissible edits: never touch `nominal`
(its LOW set is definitionally empty), only wire in a feature spanning a
channel the hypothesis is about, and reject any fix creating a new critical
exposure.

**`imu0_bias_drift` ≡ `imu1_bias_drift` — COMPLETE repair, no new hardware.**
Add `attitude_gravity_mag` to `imu0_bias_drift`'s LOW set. It spans
`imu0`+`mag`, is **ungated**, and separates the two hypotheses under every
configuration. It is also physically correct: an `imu0` bias corrupts the
mag-heading-versus-`imu0`-yaw comparison, while an `imu1` bias does not.
**Cost: one line in the signature matrix.**

**`gps_fault` ≡ `nominal` — NO complete repair from existing features.** Every
GPS-spanning feature is gated by `gvalid` except `temp_gps`, and adding
`temp_gps` merges `gps_fault` with `unexpected_maneuver` — itself a critical
pair. The fix requires a **new GPS-integrity relation whose gate is
independent of fix validity** (carrier-to-noise or satellite-count
plausibility that survives fix loss). That is a firmware/instrumentation ask,
not a matrix edit.

Ranked recommendation: do the `attitude_gravity_mag` edit first — it is free.
The GPS repair is the one that needs engineering.

> **Not implemented.** WP-C1 changed no production file. These are structural
> options, unpriced, for the user to decide on.

---

## 5. What this does NOT establish

1. **The certificate is structural, not statistical.** Two hypotheses in one
   observable class may still separate if their conditional distributions
   differ in magnitude or variance. κ bounds structural indistinguishability
   only.
2. **`C_reach` is derived from source, not observed in flight.** A
   configuration deemed unreachable that occurs in practice invalidates the
   certificate for that case. Nothing here was validated against a flight.
3. **Nothing here measures frequency.** A certificate says what *can* happen,
   never how often. The corpus fraction figures in WP-A2 are a separate
   measurement and do not transfer.
4. **`D_critical` depends on the failsafe automaton as implemented.** Change
   the response set — add an action, parameterise one differently, merge two
   conditions — and the certificate must be recomputed. It is not a property
   of the trust graph alone.
5. **Gates are binary here.** `armed_gate` and `speed_gate` are ramps in
   [0, 1]; `bayes.py:99-100` skips only at `gate <= 1e-9`. The lattice
   describes endpoints of a continuum.
6. **The gate map was read from source by hand** (`research/wp_e1/gate_map.py`).
   Auditable, but not generated from code.
7. **The novelty attack could not read a single full text.** Absence of a
   closer prior result is weak evidence.
