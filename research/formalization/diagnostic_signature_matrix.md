# Diagnostic signature matrix — candidate identifiability questions

Generated from `csia/diagnosis/bayes.py:44-56` (`CAUSES`) at
`bc3ed977e14d6eb6c5dc3a8b771b2349337de91a`. Machine-readable twin:
`diagnostic_signature_matrix.yaml`.

**This artifact states no theorem.** It records structural collisions in the
implemented signature table. Whether a collision is a genuine impossibility or
merely an artifact of this hand-built table is exactly what Paper 1 must decide.

## Why a shared LOW set is indistinguishability, not weak evidence

A gated feature is **skipped entirely** (`bayes.py:99-100`), not down-weighted.
Two hypotheses whose LOW sets coincide after gating therefore receive an
*identical* log-likelihood contribution from every surviving feature. Their
posterior ratio is pinned at the prior ratio for all time, regardless of the
data. No amount of evidence can separate them.

## Observable channels

Edge features (10 relation keys, 11 edges — `velocity_gps_doppler` is shared by
imu0–gps and imu1–gps), physics features `phys_<sensor>`, and four temporal
features `temp_{mag,battery,vibration,gps}` (`bayes.py:60`).

## Signatures

| Hypothesis | LOW features (all others expected HIGH) |
|---|---|
| `nominal` | — |
| `gps_fault` | `phys_gps` |
| `imu0_bias_drift` | `redundant_imu`, `accel_motor_current` |
| `imu1_bias_drift` | `redundant_imu`, `accel_esc_rpm` |
| `mag_interference` | `attitude_gravity_mag`, `heading_course`, `phys_mag`, `temp_mag` |
| `power_fault` | `phys_battery`, `temp_battery`, `accel_motor_current`, `accel_esc_rpm`, `phys_motor_esc` |
| `vibration_anomaly` | `vibration_prop_freq`, `phys_vibration`, `temp_vibration` |
| `unexpected_maneuver` | `temp_gps` |

## Collisions by gate mode

Every gate mode below is grounded in a verified source gate, not hypothesised.

### `all_gates_open` — 0 indistinguishable pairs
All seven fault signatures are pairwise distinct. `nominal` is nested inside
every fault (its LOW set is empty), which is structurally correct: a fault is
`nominal` plus specific features going low.

### `low_speed_hover` — 0 pairs
Removing `heading_course` (speed gate `≤2 m/s`, `comparator.py:33-34,112`)
leaves `mag_interference` with three distinguishing features. No collision.

### `non_quasi_static` — 0 pairs
Removing `attitude_gravity_mag` leaves `mag_interference` distinct.

### `disarmed_or_prearm` — **1 indistinguishable pair**
Gate: `armed_gate = 0.0` when the source reports disarmed
(`online.py:491-496`), removing `accel_motor_current`, `accel_esc_rpm`,
`phys_motor_esc`.

> **`imu0_bias_drift` ≡ `imu1_bias_drift`** — both collapse to `{redundant_imu}`.

The dual-IMU edge says *the two IMUs disagree*; the motor edges are what name
the culprit (`bayes.py:26-27` states this design intent explicitly). With the
motor edges gated off, the naming evidence is gone and the two hypotheses are
observationally identical. Their priors are equal (0.02 each), so the posterior
splits ~50/50 and stays there.

### `gps_fix_invalid` — **3 indistinguishable pairs**
Gate: `gvalid` (`comparator.py:115,144,155,168,199`), removing `phys_gps`,
`heading_course`, `altitude_baro`, `velocity_gps_doppler`, `temp_gps`.

> **`nominal` ≡ `gps_fault` ≡ `unexpected_maneuver`** — all three collapse to
> the empty LOW set.

Consequence: with an invalid GPS fix, `gps_fault` **can never be diagnosed**.
Its posterior is pinned at the prior ratio against `nominal` — 0.02 vs 0.86 —
so `nominal` dominates permanently. The failsafe still reacts through its
independent freshness/trust branch (`csia_implemented_system.md` §8), so this is
a *diagnosis* blind spot, not a safety hole. It is nonetheless the sharpest
finding in this artifact: **the single mode in which a GPS fault is most likely
is the mode in which the diagnoser is structurally unable to name it.**

### `gps_invalid_and_disarmed` — **4 indistinguishable pairs**
Union of the two above.

## Classification

| Pair | Classification |
|---|---|
| all fault pairs, gates open | distinguishable from structure alone |
| `nominal` vs any fault | nested signature (structurally intended) |
| `imu0_bias_drift` vs `imu1_bias_drift` | **context-dependent** — distinguishable armed, indistinguishable disarmed/pre-arm |
| `gps_fault` vs `nominal` | **context-dependent** — indistinguishable whenever the GPS fix is invalid |
| `gps_fault` vs `unexpected_maneuver` | **context-dependent** — same gate |
| every pair, statistically | unresolved — no test measures separation under realistic noise |

**Nothing here is classified "indistinguishable under current observables"
unconditionally.** Every collision found is gate-conditional. That is itself the
result: this signature table has no unconditional structural degeneracy, but it
has two context-dependent ones, both reachable in normal operation.

## What this does not establish

- No statistical separability analysis. Distinct signatures may still be
  inseparable at realistic SNR; that requires the residual distributions.
- Simultaneous faults are unrepresented in `CAUSES`, so simultaneous-fault
  collisions cannot be enumerated in this framework at all — the question is
  malformed until the hypothesis space admits joint causes.
- Whether these collisions matter operationally depends on how often the gate
  modes coincide with real faults. Unmeasured.

## Consequence for Paper 1

The two context-dependent collisions argue against pursuing *unique* isolation
as the headline result. The honest options are **set-valued isolation** (report
`{imu0_bias_drift, imu1_bias_drift}` when disarmed rather than a spurious 50/50)
or a **conditional impossibility theorem** (no gate-aware naive-Bayes diagnoser
over this feature set can separate these pairs in these modes). The second is
the stronger paper and the evidence currently supports attempting it.
