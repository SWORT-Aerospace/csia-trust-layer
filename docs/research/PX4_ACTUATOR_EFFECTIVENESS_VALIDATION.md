# PX4 SIH actuator-effectiveness apparatus — validation

**Status: EXPERIMENTAL APPARATUS VALIDATION. No CSIA version was run.** No
threshold was set, no algorithm was compared, and nothing under `csia/`
changed. This document asks one question: does the simulator generate the
causal distinctions the Set-B-plus-dynamics experiment needs? It does not ask
whether CSIA wins. Authorization: `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md` §7.

Every result is labelled:

- **MEASURED** for a flight trial;
- **PROVEN** for an exhaustive or compiled-code check;
- **SOURCE** for a PX4 line reference at `547e2ca`.

All apparatus files are in `research/px4_actuator_effectiveness/`.

| | |
|---|---|
| trials flown | 16 + 16 nominal-equivalence trials (two batches) and 27 sweep trials, all at PX4_SIM_SPEED_FACTOR 1 under lockstep |
| logger dropouts | 0 in all 59 logs |
| verdict | **APPARATUS_VALIDATED_WITH_LIMITATIONS** (end of document) |

---

## A. Patch description

A research-only change to PX4 SIH, and nothing else in PX4. Four parameters,
`SIH_MOT_EFF1`–`SIH_MOT_EFF4` (float, default 1.0, range [0, 1], no reboot),
give each quadcopter motor a **physical actuator effectiveness** η. It scales
that rotor's speed *target* inside `Sih::read_motors`, **before** the existing
first-order motor lag:

```cpp
float u_sp = actuators_out.output[i];                       // the command SIH received: untouched
if (_vehicle == VehicleType::Quadcopter && i < NUM_MOT_EFF) {
        u_sp *= _mot_eff[i];                                // physical effectiveness
}
_u[i] = _u[i] + dt / _T_TAU * (u_sp - _u[i]);              // the existing rotor lag
```

What it does **not** touch, and why each claim holds:

| not modified | why |
|---|---|
| controller command | `actuator_motors` and `actuator_outputs_sim` are produced upstream of `read_motors` and are only read there |
| allocator's requested command | the allocator is unchanged, and the patch runs downstream of it |
| CSIA | nothing under `csia/` changed. The patch lives in the PX4 tree and in `research/px4_actuator_effectiveness/patch/` |
| estimator | EKF2 and the hover-thrust estimator are unchanged. They see only the IMU and commands |
| telemetry after the fact | `esc_rpm` is still computed from the rotor state `_u[i]` (`sih.cpp:424` at `547e2ca`, line 436 after the patch) |

**Not a sensor fault.** The RPM reports the true, reduced rotor. The fault is
in the physics.

## B. PX4 baseline

| | |
|---|---|
| PX4 commit | `547e2caa9883bc1609325f02b4914b4e2482fe62` (fetched by SHA, not upstream HEAD) |
| patched tree | that commit plus one local commit, `4c34870` (feat(simulator_sih): …) |
| patch file | `research/px4_actuator_effectiveness/patch/0001-sih-actuator-effectiveness.patch`, SHA-256 `c057ba451fef91d532d5d033c5e02968aa0f0851055b635117e462451b36c32c`; applies cleanly to the pinned commit (`git apply --check`) |
| unmodified binary | `px4_sitl_default` `bin/px4`, SHA-256 `ace8ac8a5c9d501aa8a65ec374e3fb29d9f2edff864a603c57db7b5bac603deb` |
| patched binary | SHA-256 `4073466f1b3e42ed073b88d45bda4e4d1168a35730eb23f470ae5a0744dfc085` |
| toolchain | Ubuntu 24.04.4, GCC 13.3.0, CMake 3.28.3, Ninja 1.11.1, Python 3.11.15; empy 3.3.4, pyulog 1.2.4, pymavlink 2.4.50, numpy 2.4.6 |
| airframe | 10040 `sihsim_quadx`, default parameters. Lockstep at 250 Hz: min(`IMU_GYRO_RATEMAX` 800, `IMU_INTEG_RATE` 250) |

The binary hashes identify this session's builds. A rebuild elsewhere embeds
different paths and debug information, so it will not reproduce them
bit-for-bit.

## C. Modified files

| file (PX4 tree) | change |
|---|---|
| `src/modules/simulation/simulator_sih/sih_params.yaml` | +56 lines: `SIH_MOT_EFF1`–`4` definitions |
| `src/modules/simulation/simulator_sih/sih.hpp` | +6: `NUM_MOT_EFF = 4`; `float _mot_eff[4] {1,1,1,1}`; four `ParamFloat` entries |
| `src/modules/simulation/simulator_sih/sih.cpp` | +12: `parameters_updated()` loads and clamps the four values to [0, 1]; `read_motors()` applies them before the lag |

No other PX4 file changed. `make check_format` was not run because astyle is
not installed here. The code follows the surrounding tab style.

## D. What η means mathematically

Per SIH step (dt = 4 ms, τ = `SIH_T_TAU` = 0.05 s, α = dt/τ = 0.08), for
motor i with received command c_i ∈ [0, 1]. The line numbers refer to
`547e2ca`:

```
u_i[k] = u_i[k-1] + α ( η_i · c_i[k] − u_i[k-1] )          rotor state (patched line)
T_i    = T_MAX · u_i          Q_i = Q_MAX · u_i             thrust, drag torque (sih.cpp:450-452)
rpm_i  = 10000 · sqrt(u_i)                                  telemetry (sih.cpp:424)
```

- **Steady state at constant command:** u_i = η_i c_i. The rotor settles at η
  of its commanded state with the **unchanged** time constant (63% of a step
  in 48 ms).
- **η → thrust is linear.** Rotor i's maximum thrust becomes η·T_MAX; so does
  its drag torque, and so do its roll and pitch moments through the same u_i.
- **η → RPM is not linear.** At a fixed command, RPM scales as √η. MEASURED in
  the telemetry-fault copies, reported RPM over true RPM at a nominal command:
  0.9486 at η = 0.9 (√0.9 = 0.9487), 0.8367 at 0.7 (0.8367), 0.7071 at 0.5
  (0.7071).
- **η is neither of these:**
  - a command corruption: c_i is unchanged;
  - a sensor fault: the RPM is honest.

  It changes neither τ nor the rigid body (mass, inertia, drag).
- **Physical reading:** "the rotor cannot reach the commanded speed", for
  example motor weakness, binding or a supply limit, with honest speed
  telemetry.
- **Identifiability:** η can be recovered from the log alone. Invert the rotor
  equation using the logged RPM (giving u) and the logged
  `actuator_outputs_sim` (giving c): η̂ = (u[k] − (1−α)u[k−1]) / (α c).

---

## E. Nominal equivalence: η = 1.0 against unmodified SIH

**Result: EQUIVALENT (PASS). Degradation testing was allowed to proceed.**

### E.1 Proven: the arithmetic is an identity at η = 1

- **Exhaustive check.** `research/px4_actuator_effectiveness/scripts/identity_check.cpp`
  was compiled with the flags PX4 used for `sih.cpp` (`-O2 -freciprocal-math
  -fno-signed-zeros -fno-trapping-math …`). It multiplies every one of the
  2³² float bit patterns by a run-time 1.0f.
  - All **4,278,190,082 non-NaN patterns come back bit-identical**.
  - The only changes are 8,388,606 signalling NaNs, which are quietened. SIH's
    command input is never NaN: the mixer maps NaN to the disarmed value, and
    `pwm_out_sim` leaves that channel at 0.
- **Compiled-code comparison.** The disassembled `Sih::read_motors` of both
  binaries (`research/px4_actuator_effectiveness/results/static_identity/`)
  contains the same lag arithmetic (`divss`, `subss`, `mulss`, `addss`) plus
  exactly **one** extra `mulss`, the effectiveness multiply. x86-64 without FMA
  is used, so there is no contraction.

So at η = 1, for identical inputs, the patched rotor update is bit-identical
to the original.

### E.2 Measured: flight trials

**Protocol.** Instance 0, speed factor 1, sequential runs, unmodified and
patched runs interleaved. Every trial follows one schedule in simulated time:
arm at 10 s, take off to 10 m, hold, disarm at 45 s. Comparison windows:
climb 10.5–20 s, hover 22–44.5 s.

**172 metrics:** the mean and standard deviation, in each window, of:
- the four motor commands (allocated and received);
- the four RPMs;
- true angular velocity, measured specific force and true position (3 axes each);
- true and estimated roll, pitch and yaw;
- estimated position and velocity;
- nine EKF innovations;
- the hover-thrust estimate.

**The tolerance is the simulator's own repeatability, not an epsilon.** The
question is whether the patched runs can be told apart from another batch of
unmodified runs. The decision rule was fixed before any equivalence data were
analysed. STOP if any of these gives p < 0.05:
1. a per-metric permutation test, Holm-adjusted over all 172 metrics;
2. a multivariate energy-distance permutation test;
3. a permutation test on climb-trajectory distance.

| | batch 1 (8 + 8) | batch 2 (8 + 8) | pooled (16 + 16) |
|---|---|---|---|
| smallest Holm-adjusted p | 0.40 | 1.00 | 1.00 |
| metrics with raw p < 0.05 (expected by chance: 8.6) | 9 | 0 | 0 |
| largest \|Δ\| in run-to-run SD | 1.74 | 0.95 | 0.66 |
| energy-distance p | 0.37 | 0.73 | 0.81 |
| climb-trajectory p | 0.24 | 0.71 | 0.92 |
| verdict | PASS | PASS | **PASS** |

Batch 1 and batch 2 use exact permutation (all 12,870 relabellings). The
pooled set uses 20,000 seeded relabellings.

**The one thing that looked like an effect was checked, and it did not
replicate.**
- In batch 1, the four lowest-p metrics were all hover-yaw metrics, all lower
  in the patched build. Their size was 0.1° in yaw spread and ≤ 0.4° of drift
  over 22 s. Holm adjustment did not flag them, but a coherent cluster
  warranted a test.
- Before flying batch 2, the replication test was fixed
  (`research/px4_actuator_effectiveness/analysis/replication_test.py`): the
  four metrics, one-sided in batch 1's direction, Holm over four, STOP if any
  replicates.
- In batch 2 all four **reversed direction** (one-sided p = 0.85–0.94).
  Verdict: NOT_REPLICATED.

**Why a cluster can appear at all: realization families (MEASURED).**
- SIH seeds `rand()` once with a fixed seed (`sih.cpp:61`), and the GPS, baro
  and mag simulators draw from the same process-wide stream on other threads.
- Runs therefore replay one of a few noise realizations and branch only at
  thread-interleaving events. In batch 1, 12 of 16 runs (7 unmodified and 5
  patched) shared a **bit-identical** pre-arm accelerometer sequence; the rest
  branched off it (`research/px4_actuator_effectiveness/results/REALIZATION_FAMILIES_BATCH1.json`).
- Arm times differ by 4–12 ms between runs, so no two flights stay
  bit-identical after arming.
- The consequence is that within-build repeatability can look narrower than
  the simulator's real variability, especially for slow noise-driven modes
  such as heading drift. Pooling two batches is what exposed this.

---

## F. Causal separation

MEASURED on a representative level, η = 0.70, trial `sweep_eta070_r1`, with the
matched telemetry-fault copy (case B). The five categories stay distinct:

| category | variable (ULog) | pre-fault | case A: physical degradation, steady (10–20 s after onset) | case B: telemetry degradation, steady |
|---|---|---|---|---|
| **A. controller command** | motor-1 `actuator_outputs_sim` | 0.489 | **0.701** (peak 0.744): the controller compensates | 0.490: nothing to compensate |
| **B. physical rotor state** | η̂ recovered from the log | 1.0000 | **0.6999**; rotor u = 0.4904 = 0.70 × 0.701; thrust 2.45 N of a 3.50 N capacity | 1.0000; rotor at 7003 rpm (truth record, untouched) |
| **C. ESC/RPM telemetry** | motor-1 `esc_rpm` | 6995 | 7003: honest, equal to the other motors, **1367 rpm below** what its command implies (8370) | **5859 reported**, while the true rotor turns at 7003 |
| **D. vehicle response** | true ω, ω̇, tilt, specific force | nominal | onset: ω̇ peak 4.46 rad/s², ω 0.47 rad/s, tilt 5.6°, Δf 0.69 m/s². Steady: nominal (‖ω̇‖ 0.071 against the control's 0.075) | nominal throughout |
| **E. estimated state** | EKF innovations; hover-thrust estimate | nominal | EKF aiding innovations: no attributable response. Hover-thrust estimate +0.038 above the matched control | nominal |

At every level the first response after the physical onset t1 is ordered
physically (median over three repeats):
- the **rotor and the angular acceleration change in the same 4 ms step**;
- the body rate follows 4–16 ms later;
- the **controller command** responds 12–32 ms later, sooner for larger losses;
- the hover-thrust test ratio follows at 36–212 ms, and only for η ≤ 0.6.

In the η = 1.00 control arm, "first responses" occur only at 0.6–17 s. Those
are noise crossings, and they are the floor against which the degraded values
should be read.

**So the essential apparatus requirement is met.** For a degraded motor:
- the controller command stays high and compensates (κ → 1/η);
- the physical rotor capability is reduced (η̂ = η exactly);
- the vehicle dynamics respond at onset;
- the telemetry reports the physical rotor, not the command.

## G. Characterization table

MEASURED. Motor 1 (`SIH_MOT_EFF1` ↔ `_u[0]` ↔ CSIA `motor_0`), 9 levels × 3
repeats. Each cell is the median over repeats, with [min, max] where they
differ. κ = motor-1 command / mean of the others. "Steady" is 10–20 s after
onset.

| η | η identified | motor-1 command pre → steady (peak) | κ steady (1/η) | motor-1 RPM steady | RPM implied by its command | motor-1 thrust steady / capacity (N) |
|---|---|---|---|---|---|---|
| 1.00 | 1.0000 | 0.489 → 0.490 (0.498) | 1.00 (1.00) | 7003 | 7003 | 2.45 / 5.00 |
| 0.90 | 0.9000 | 0.489 → 0.545 (0.557) | 1.11 (1.11) | 7003 | 7382 | 2.45 / 4.50 |
| 0.80 | 0.8000 | 0.490 → 0.613 (0.636) | 1.25 (1.25) | 7003 | 7829 | 2.45 / 4.00 |
| 0.70 | 0.7000 | 0.489 → 0.701 (0.744) | 1.43 (1.43) | 7003 | 8370 | 2.45 / 3.50 |
| 0.60 | 0.6000 | 0.490 → 0.817 (0.888) | 1.67 (1.67) | 7003 | 9041 | 2.45 / 3.00 |
| 0.50 | 0.5000 | 0.489 → 0.976 (1.000) | 2.00 (2.00) | 6984 | 9877 | 2.44 / 2.50 |
| 0.40 | 0.4001 | 0.489 → *no steady flight* (1.000) | — (2.50) | — | — | — / 2.00 |
| 0.25 | 0.2500 | 0.490 → *no steady flight* (1.000) | — (4.00) | — | — | — / 1.25 |
| 0.00 | 0.0000 | 0.489 → *no steady flight* (1.000) | — (∞) | — | — | — / 0.00 |

| η | peak ‖ω‖ rad/s | peak ‖ω̇‖ rad/s² | peak Δ specific force m/s² | peak tilt ° | peak attitude error ° | peak EKF test ratio (pre-fault max) | peak hover-thrust test ratio (pre-fault max) | onset → peak rate, s |
|---|---|---|---|---|---|---|---|---|
| 1.00 | 0.017 | 0.25 | 0.32 | 0.4 | 0.3 | 0.109 (0.079) | 0.05 (0.09) | noise |
| 0.90 | 0.149 | 1.47 | 0.32 | 1.5 | 2.5 | 0.108 (0.070) | 0.03 (0.09) | 0.148 |
| 0.80 | 0.290 | 2.94 | 0.52 | 3.3 | 5.6 | 0.189 (0.079) | 0.03 (0.09) | 0.156 |
| 0.70 | 0.468 | 4.46 | 0.69 | 5.6 | 9.3 | 0.166 (0.081) | 0.05 (0.09) | 0.164 |
| 0.60 | 0.639 | 6.00 | 0.91 | 8.2 | 14.0 | 0.109 (0.071) | 0.14 (0.09) | 0.168 |
| 0.50 | 0.861 | 7.63 | 1.15 | 11.8 | 20.4 | 0.109 (0.071) | 0.32 (0.09) | 0.176 |
| 0.40 | 1.098 | 9.32 | 1.87 | 16.0 | 38.0 | 0.106 (0.070) | 0.38 (0.09) | 0.188 |
| 0.25 | 1.511 | 12.00 | 4.02 | 21.7 | 107.5 (yaw) | 0.081 (0.094) | 0.65 (0.09) | 0.204 |
| 0.00 | 4.492 | 17.86 | 12.69 | 122.0 | 161.8 | 0.099 (0.080) | 1.09 (0.09) | 1.392 |

**Reading the EKF column.** Peaks at every level, including the control's
0.066–0.188 across repeats, sit in the same range. The EKF's "first response"
at 0.6–1.7 s occurs in the control too: it is a scheduled estimator event, not
the fault. **The navigation EKF's aiding innovations show no fault-attributable
response at any level.** This is structural: the EKF's prediction is driven by
the IMU, which measures the true motion, so GPS, baro and mag agree with it.

Peaks at η ≤ 0.4 are taken before ground contact (§I). Every quantity above
is a magnitude, not a detection.

## H. Transient against steady state

MEASURED. The four phases, per trial, with t1 = the physical onset step:

| phase | span |
|---|---|
| PRE-FAULT | [t1 − 5 s, t1) |
| ONSET TRANSIENT | [t1, t_peak]. t_peak is the peak true body rate within 3 s, the step at which angular acceleration returns to zero and torque balance is regained: 0.15–0.20 s for 0.4 ≤ η ≤ 0.9 |
| COMPENSATION TRANSIENT | (t_peak, t1 + 10 s) |
| POST-COMPENSATION STEADY STATE | [t1 + 10 s, t1 + 20 s) |

Case B uses case A's phase boundaries at the same level. Phase means, median
over three repeats. "Δ" means a change from the trial's pre-fault mean:

| η | evidence variable (phase mean) | onset A | onset B | compensation A | compensation B | steady A | steady B |
|---|---|---|---|---|---|---|---|
| 0.90 | W_CTRL κ − 1 | +0.048 | −0.001 | +0.112 | +0.000 | **+0.111** | −0.000 |
| 0.90 | W_RPM RPM residual (rpm) | −258 | −251 | −379 | −359 | −379 | −359 |
| 0.90 | W_DYN ‖ω̇‖ rad/s² | **0.934** | 0.060 | 0.096 | 0.071 | 0.074 | 0.075 |
| 0.90 | W_DYN ‖ω‖ rad/s | 0.0907 | 0.0121 | 0.0141 | 0.0063 | 0.0071 | 0.0073 |
| 0.90 | W_EST hover-thrust estimate (Δ) | −0.0093 | −0.0093 | −0.0128 | −0.0178 | −0.0158 | −0.0257 |
| 0.70 | W_CTRL κ − 1 | +0.169 | −0.001 | +0.433 | +0.000 | **+0.428** | −0.000 |
| 0.70 | W_RPM RPM residual (rpm) | −872 | −818 | −1369 | −1144 | −1367 | −1144 |
| 0.70 | W_DYN ‖ω̇‖ rad/s² | **2.786** | 0.060 | 0.174 | 0.072 | 0.071 | 0.075 |
| 0.70 | W_DYN ‖ω‖ rad/s | 0.2820 | 0.0121 | 0.0389 | 0.0063 | 0.0074 | 0.0073 |
| 0.70 | W_EST hover-thrust estimate (Δ) | −0.0091 | −0.0094 | +0.0015 | −0.0178 | +0.0120 | −0.0257 |
| 0.50 | W_CTRL κ − 1 | +0.333 | −0.000 | +1.015 | +0.000 | **+0.999** | −0.000 |
| 0.50 | W_RPM RPM residual (rpm) | −1650 | −1479 | −2918 | −2051 | −2893 | −2051 |
| 0.50 | W_DYN ‖ω̇‖ rad/s² | **4.803** | 0.063 | 0.284 | 0.071 | 0.070 | 0.075 |
| 0.50 | W_DYN ‖ω‖ rad/s | 0.5131 | 0.0121 | 0.0776 | 0.0063 | 0.0076 | 0.0073 |
| 0.50 | W_EST hover-thrust test ratio (Δ) | +0.027 | −0.018 | **+0.129** | −0.033 | −0.016 | −0.041 |
| 0.50 | W_EST hover-thrust estimate (Δ) | −0.0089 | −0.0094 | +0.0259 | −0.0178 | +0.0598 | −0.0257 |

More variables, including torque setpoint, specific force and the EKF ratio,
are in
`research/px4_actuator_effectiveness/results/TRANSIENT_VS_STEADY_TABLE.md`.

**Findings. This is the answer to the question that matters for CSIA's
temporal architecture.**

1. **The dynamic consequence is a transient.** In case A during the onset
   transient, angular acceleration is 15–76 times its case-B value and body
   rate 7–42 times. It is weaker during compensation and
   **indistinguishable from nominal in steady state**, at every compensated
   level. The prediction that *moderate degradation produces a transient
   physical inconsistency, after which the aircraft looks nearly normal* is
   **confirmed**.
2. **The discriminating evidence does not exist only in the transient.**
   W_CTRL (command asymmetry κ, torque-setpoint offset) builds through the
   transient and **persists at steady state**: κ − 1 ≈ 1/η − 1 in A and
   exactly 0 in B. It is a command-side trace of the physical loss. A
   steady-state observer can see it, but only as evidence that the closed loop
   compensates something downstream of the command (H2 boundary).
3. **W_RPM does not separate A from B.** It is present in both at similar size
   by construction: it *is* the shared COMMAND_NO_RESPONSE symptom. Its
   magnitude grows more in A because A's compensating command raises the
   RPM the command implies. That extra is W_CTRL showing through, not an
   independent signal.
4. **W_EST is weak.**
   - The EKF aiding innovations carry nothing.
   - The hover-thrust estimator's innovation separates A from B only at
     η ≤ 0.6 and only during compensation.
   - The hover-thrust *estimate* drifts to a steady offset at η ≤ 0.7, a slow
     command-to-response consistency effect over seconds.
5. **Settling time is not resolvable on this apparatus.**
   - Even calibrated on the control arm (revision R1, §L), the η = 1.00 control
     trials "settle" at 2.4 s, 14.5 s, or never.
   - Degraded-level settle times (tilt 2.7–10.2 s, altitude 0.2–13.6 s at
     0.5 ≤ η ≤ 0.9) lie inside that noise floor.
   - So the end of the compensation transient is placed at a fixed 10 s
     (revision R2) rather than detected. Per-signal settle times are in
     `research/px4_actuator_effectiveness/results/CHARACTERIZATION_TABLES.md`
     with the control floor beside them.

## I. Control-authority boundary

MEASURED. The static prediction in the preflight was that 4-axis hover is
feasible for η ≥ 0.49.

| η | motor-1 command | outcome | ground contact after onset |
|---|---|---|---|
| 0.90 – 0.60 | below the limit | full compensation; attitude, yaw and altitude held | none |
| 0.50 | peaks at 1.000 and settles at 0.976 (saturated for 90% of the compensation phase) | **compensated at the limit**: 0.43 m mean altitude sag during compensation, lowest point 9.25 m from 10 m | none |
| 0.40 | pinned at 1.000 | attitude and yaw held (final \|yaw rate\| 0.015 rad/s), **altitude authority lost**: steady descent | 6.4 s |
| 0.25 | at the limit | **yaw authority lost**: spinning up, 0.58 rad/s at contact; tilt 21.7° | 3.4 s |
| 0.00 | at the limit | **attitude lost**: flips to 122° tilt | 2.1 s |

The boundary lies between η = 0.50 and 0.40, which confirms the preflight
bound. The informative range for a *discrimination* experiment is therefore
0.5 < η < 1: compensated flight, where the observability window may close.
η ≤ 0.4 tests loss of control.

## J. Logging and timestamp validation

MEASURED over all 59 logs. Topics were logged at interval 0 through
`research/px4_actuator_effectiveness/config/logger_topics.txt`. MAVLink was
the control path only; no measurement came from it.

| check | result |
|---|---|
| logger dropouts | **0** in 59 logs |
| common clock | lockstep sets the process clock to simulated time. Every step topic sits on the 4 ms grid: **0** off-grid timestamps |
| ESC, IMU and truth coverage | missing SIH steps between arm and disarm: `esc_status` 17 of 267,550 (sweep), `sensor_combined` 8, ground truth 78 |
| control-chain coverage | 0.6–1.4% of steps have no fresh command (`actuator_outputs_sim` 3,572 of 267,550). This is a lockstep control-cycle merge in PX4 itself, present in both builds |
| EKF outputs | every 8 ms (125 Hz: two IMU samples per filter update, not the 100 Hz the preflight estimated). Innovations are stamped at the **delayed horizon**: `timestamp − timestamp_sample` = 152–156 ms. Alignment must use `timestamp_sample` |
| injected change → PX4 | the `parameter_update` timestamp is 0–4 ms after the driver's send, in simulated time |
| change → physics | the physical onset t1 is **exactly one step (4 ms)** after the `parameter_update` stamp in all 24 sweep trials with a change. The three η = 1.00 controls set an unchanged value, which publishes no update, so their onset is taken from the driver's send time |
| command → rotor transport | of 20,806 identifiable rotor updates: **92.2% used the command stamped one step earlier**, 4.5% the one stamped at the step itself, 3.2% one stamped two steps earlier (`research/px4_actuator_effectiveness/results/COMMAND_ROTOR_PAIRING.json`) |
| response ordering | rotor and ω̇ at t1 (0 ms); ω +4–16 ms; command +12–32 ms; hover-thrust ratio +36–212 ms (η ≤ 0.6) |

**Temporal alignment error.** There is one clock, so clock skew is zero. The
structural offsets are known:
- command → physics is one step, ±1 step in 7.7% of updates;
- IMU and truth are stamped in the same step as the physics;
- the estimator's innovations lag by the 152–156 ms delayed horizon, which is
  explicit in every record.

Against a 50 ms rotor time constant and a 150–200 ms onset transient, a
4 ms (±4 ms) alignment is adequate. The estimator horizon is not negligible
and must be aligned explicitly.

## K. Revised witness definitions

W1, "the allocator reports torque not achieved", is **withdrawn as a
measurement of physical torque**. The allocator computes achievement from its
own effectiveness model, which never sees η. MEASURED:
- at η ≥ 0.6 it reports the torque setpoint achieved in **100% of in-flight
  steps**, before and after onset, and never raises motor 1's saturation flag;
- meanwhile motor 1 produces only 60–90% of its commanded thrust;
- at η = 0.5 it reports "not achieved" in only 1.6% of post-onset steps, while
  saturated.

Four evidence categories replace it. Each holds evidence **variables**; the
predicates and thresholds are left to the preregistration.

| category | data category | evidence variables | A | B | phase in which the evidence exists |
|---|---|---|---|---|---|
| **W_CTRL** | COMMAND | per-motor command against the symmetric hover expectation (κ_i); torque-setpoint offset; rate integrators; allocator saturation (demand only) | present | absent | onset → **steady** (persistent while compensation is feasible) |
| **W_RPM** | TELEMETRY (equal to PHYSICAL in SIH) | RPM against the healthy-rotor expectation from the command history; cross-motor RPM symmetry | present | present (the matched symptom) | all |
| **W_DYN** | VEHICLE RESPONSE | ω̇, ω, tilt, Δ specific force, altitude deviation against the control arm's envelope | present | absent | **onset transient**; fades during compensation; absent in steady state |
| **W_EST** | ESTIMATED STATE | EKF aiding innovations (**non-informative for this fault class**); hover-thrust innovation and estimate | weak: η ≤ 0.6 compensation; slow offset η ≤ 0.7 | absent | compensation (hover thrust) |

The same revision, with its reasoning, is in
`docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md` §6. It is not assumed that all
four will be needed. On this apparatus, W_CTRL and W_DYN carry the
discriminating information, W_RPM carries the symptom, and W_EST is marginal.

## L. Limitations

1. **Rotor, telemetry and thrust are still one variable in SIH.** Case A's RPM
   is honest because it is the same number that makes the thrust. A real ESC
   measures back-EMF with its own noise, delay and failure modes.
2. **The rotor model is a first-order lag**, with no load torque, current or
   voltage. η models "the rotor cannot reach commanded speed"; it does not
   model a specific mechanism. A jam stops faster than τ, and a damaged
   propeller would *raise* RPM.
3. **η scales thrust and drag torque together.** That is a modelling choice,
   declared rather than validated.
4. **Repeats are not independent.** Identical protocols replay near-identical
   noise realizations (§E). The three sweep repeats per level agreed to the
   step. Spread across repeats understates real variability, and a campaign
   must vary a declared nuisance to obtain independent samples.
5. **Settling and recovery times are noise-floor limited** (§H, item 5).
   Composite recovery times are reported only beside the control floor and are
   not used to cut phases.
6. **Two analysis revisions were made after seeing preliminary sweep outputs.**
   Both are disclosed in `research/px4_actuator_effectiveness/analysis/characterize.py`.
   - **R1:** the recovery envelope moved from each trial's own pre-fault
     maximum to the control arm's post-onset maximum, because the first rule
     failed its own control. It is calibrated on the control arm only.
   - **R2:** the end of the compensation phase became a fixed 10 s, because
     detected settling was not resolvable.
   - Two further corrections: flight windows end at ground contact, to exclude
     SIH's one-step ground-impact artefacts; and the nominal-equivalence
     replication test was specified before batch 2 was flown.
7. **Case B's corruption is a model.** The telemetry copy follows the same
   rotor-lag model with target η·c, so that its COMMAND_NO_RESPONSE symptom
   matches case A's by construction. Other telemetry-failure shapes (dropout,
   freeze, bias) are not characterized.
8. **Scope:**
   - one airframe (default SIH quad), hover only, no wind, default gains;
   - motor 1 only (EFF2–4 are implemented but not exercised);
   - onset is an instantaneous step in η, smoothed by τ.
9. **The EKF aiding innovations are blind to this fault class by
   architecture** (IMU-driven prediction). That is a property of PX4, not a
   defect of the apparatus.
10. **The binary hashes are environment-specific** (§B).

## M. Suitability for the matched-set experiment

**Suitable, with limitations.** The apparatus generates what H1 needs:

- **member A is a physical fault** that produces COMMAND_NO_RESPONSE through
  the physics, with the command intact (η̂ = η exactly);
- **member B is a telemetry fault** that leaves physics, dynamics and
  estimator nominal and keeps the true record (case B, truth preserved in
  27 of 27 copies);
- the two are **separable by cross-domain evidence that exists**: W_DYN in the
  onset transient, W_CTRL persistently;
- every signal is on one clock at 4 ms, with measured and explicit alignment
  offsets;
- the patch is **proven** neutral at η = 1 and **measured** equivalent in
  flight.

**Conditions for a preregistration that uses it:**
1. use W_CTRL, W_RPM, W_DYN and W_EST (§K), never allocator "torque achieved"
   as a physical witness;
2. evaluate W_DYN within the onset transient, whose timescale is 0.15–0.2 s;
3. restrict discrimination trials to compensated flight, 0.5 < η < 1;
4. obtain independent noise realizations by varying a declared nuisance, and
   never count identical repeats as independent;
5. align estimator evidence on `timestamp_sample`;
6. log at full rate through the ULog configuration given here, never through
   MAVLink;
7. keep the H2 boundary: W_CTRL does not separate A from C.

---

## Reproduction

| step | command |
|---|---|
| build both binaries | `research/px4_actuator_effectiveness/scripts/build_px4.sh <workroot>` |
| one trial | `research/px4_actuator_effectiveness/scripts/run_trial.py --build <build> --workdir <dir> --out <dir> --name <n> [--eta 0.7]` |
| nominal campaign | `research/px4_actuator_effectiveness/scripts/run_campaign.py nominal --base <b> --patched <p> --out <dir> --work <dir> --n 8` |
| sweep campaign | `research/px4_actuator_effectiveness/scripts/run_campaign.py sweep --base <b> --patched <p> --out <dir> --work <dir> --repeats 3` |
| equivalence gate | `research/px4_actuator_effectiveness/analysis/nominal_equivalence.py <runs> --out <json>` |
| replication test | `research/px4_actuator_effectiveness/analysis/replication_test.py <runs> --out <json>` |
| characterization and case B | `research/px4_actuator_effectiveness/analysis/characterize.py <runs> --out <json>`, then `research/px4_actuator_effectiveness/analysis/summarize.py` |
| timing | `research/px4_actuator_effectiveness/analysis/logging_check.py`, `research/px4_actuator_effectiveness/analysis/command_rotor_pairing.py` |
| static identity | `research/px4_actuator_effectiveness/scripts/identity_check.cpp` (compile with the flags in §E.1) |
| archive | `research/px4_actuator_effectiveness/scripts/archive_logs.sh <runs> <name>` |

**Raw logs** are in `research/px4_actuator_effectiveness/raw_ulog/`:
- `nominal_batch1/` and `nominal_batch2/` hold the equivalence batches. In the
  pooled analysis, batch-2 trials are named `_11`–`_18`.
- `sweep/` holds the sweep.

Each directory holds xz-compressed ULogs, each trial's JSON (schedule, event
times, binary and ULog SHA-256), the PX4 console output, and a `SHA256SUMS`
file. That file lists the **uncompressed** ULog hash, which is the one the
trial JSON records, and the compressed file's hash. Verify with
`xz -dc X.ulg.xz | sha256sum`.

**Results** are in `research/px4_actuator_effectiveness/results/`.

---

## Final verdict

**APPARATUS_VALIDATED_WITH_LIMITATIONS**
