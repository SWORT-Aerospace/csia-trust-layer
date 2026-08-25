# Mechanism B — preregistration

**This file is committed BEFORE any Mechanism B trial is executed.** Its
purpose is to make the campaign falsifiable: the grid, the endpoints, the
tolerances and the classification rule are fixed here, so a result cannot be
rescued afterwards by widening the grid or moving a criterion. `git log` on
this file against the results commit is the audit trail.

Nothing in the frozen v1 core is modified by this work. `FROZEN_PATHS` —
`csia/trust_engine`, `csia/diagnosis`, `csia/runtime/online.py`,
`csia/runtime/failsafe.py`, `csia/scenarios.py`, `csia/profiles.py` — are
read, cited and replayed, never edited.

---

## 1. The claim under test

`docs/v1/V1_FINAL_RESEARCH_VERDICT.md` W-4, the **history-dominated
threshold crossing**. The trust recursion in `csia/trust_engine/engine.py:145-152`
is

```
S(k)  = rho(k) * S(k-1) + 1
T(k)  = ( rho(k) * S(k-1) * T(k-1) + e(k) ) / S(k)
```

with `S = alpha + beta` and `T = alpha / S`. Banked evidence `S(k-1)` sits in
front of the new evidence `e(k)`, so a node whose evidence collapses does not
drop to the new evidence level — it *walks* there over a number of ticks set by
`S` and `rho`. W-4 gives the constant-coefficient closed form

```
x   = rho^N
M   = 1 / (1 - rho)
T_N = ( x*S0*T0 + (1-x)*M*e_f ) / ( x*S0 + (1-x)*M )
```

and reports `N* = 93.31` ticks to a threshold crossing in the ArduCopter 3.3
campaign.

**Question.** Does the same recursion, with no fitted parameters, predict when
a trust node crosses a failsafe threshold on the **current** stack —
ArduPilot 4.8 and PX4 SIH?

`MECHANISM_A_MODERN_REPLICATION.md` §6 states explicitly that fix-loss cannot
test this: self-occlusion removes the evidence, so the node never moves and
there is no crossing to time. **This campaign therefore must not use fix
loss**, and does not.

## 2. Intervention

**`mag_emi` — a constant hard-iron offset added to the published magnetometer
field, mid-flight, applied equally to the three body axes.**

Chosen because it is the one injection available on both current simulators
that is **evidence-preserving**: the `mag.field_ut` channel keeps arriving at
its normal rate, every gate that carries magnetometer evidence stays open, and
the residuals therefore *move* rather than disappearing. That is the precise
opposite of the fix-loss case and is what Mechanism B requires.

### 2.1 Parameter, API and type — read out of simulator source before use

| platform | parameters | MAV type | unit | write |
|---|---|---|---|---|
| ArduPilot 4.8 (`01a504b`) | `SIM_MAG1_OFS_X`, `_Y`, `_Z` | **REAL32** | milligauss | `current − 10·u` |
| PX4 (`547e2ca`, SIH `sihsim_quadx`) | `SIM_MAG_OFFSET_X`, `_Y`, `_Z` | **REAL32** | gauss | `current + u/100` |

where `u` is the arm's magnitude in **microtesla**.

Source evidence:

* ArduPilot — `libraries/SITL/SITL.cpp:779`
  `AP_GROUPINFO("MAG1_OFS", 4, SIM, mag_ofs[0], 0)`; `SITL.h:204`
  `AP_Vector3f mag_ofs[HAL_COMPASS_MAX_SENSORS]; // in mag units`, boot default
  `Vector3f(5, 13, -18)` (`SITL.h:156`). `AP_Compass_SITL.cpp:124`
  **subtracts** it from the simulated field:
  `Vector3f f = (_eliptical_corr * new_mag_data) - _sitl->mag_ofs[i].get();`
  The compensating `COMPASS_OFS` is written **once, at construction**
  (`AP_Compass_SITL.cpp:30-32`, and only when the compass offsets are zero), so
  a runtime change to `SIM_MAG1_OFS` is **not** re-absorbed by calibration and
  shifts the published field.
* PX4 — `SensorMagSim.cpp:153-155` **adds** it to `expected_field`;
  `SensorMagSim.hpp:101-103` declares all three as `ParamFloat`;
  `parameters.yaml` gives `type: float`, `unit: gauss`, `default: 0.0`, and
  **no** `reboot_required`. `SensorMagSim.cpp:113-118` subscribes to
  `parameter_update` and calls `updateParams()`, so the write is live in
  flight. The module is running because airframe
  `10040_sihsim_quadx:17` sets `SENS_EN_MAGSIM 1`, and SIH itself publishes no
  magnetometer.

The two deltas are chosen so the **published field moves identically on both
platforms**: `+u` µT on each FRD axis. ArduPilot's adapter converts milligauss
to µT with `× 0.1` (`csia/aircraft/adapters/ardupilot.py:148`), and the SITL
sign is negative, so `Δ = −10·u` mG → `+u` µT. PX4's adapter converts gauss to
µT with `× 100` (`csia/aircraft/adapters/px4.py:126`), and the sign is
positive, so `Δ = +u/100` G → `+u` µT.

The write is **relative to the parameter's current value**, read back from the
vehicle immediately before the write. This makes `u = 0` a genuine no-op write
rather than a small perturbation — ArduPilot's boot default is not zero.

### 2.2 Authority

The **rig** connection transmits, exactly as in Mechanism A. CSIA's connection
is shut for writing and every send on it raises `CommandAuthorityError`; the
live transmit probe is recorded per flight.

### 2.3 Readback — required, all three axes

Each parameter is read back via `PARAM_VALUE` and compared against the
commanded value. An arm is **NOT CONFIRMED** unless all three match to
`1e-6` after type-correct decoding (`decode_param_value`). A parameter write
nobody confirmed is an assumption.

### 2.4 Expected downstream observable (RULE B)

**Readback is not the measurement.** The declared downstream observable is:

> the mean `mag.field_ut` vector over the 2.0 s **after** injection differs
> from the mean over the 2.0 s **before** injection by a Euclidean distance of
> `u·√3` µT.

This is exact and attitude-independent: the injected offset is a constant
vector in the body frame, so the difference of the two body-frame means is the
offset itself, whose norm is `u·√3` regardless of vehicle heading.

### 2.5 Validity condition — declared before execution

An arm is a **valid trial** iff **all** of:

1. the flight completed and its log is readable;
2. command authority is `NO_COMMAND_PATH_REACHABLE`;
3. all three parameters read back CONFIRMED;
4. the observed field shift of §2.4 is within **±40 %** of `u·√3` µT for an
   injected arm (`u > 0`), or **< 1.0 µT** for the null arm (`u = 0`);
5. the reconstruction's own positive control passes (§5, E1).

**No trial counts unless the intervention is verified downstream.** An arm
failing (3) or (4) is a *failed trial*, reported as such, and contributes
nothing to any verdict in either direction.

### 2.6 Null control (RULE A)

`u = 0.0` µT. The parameters are read, written back with their own values, and
read back again. The write happens; the field does not move. This controls for
the act of writing, for the rig transmitting mid-flight, and for anything the
harness does around the injection instant.

### 2.7 Fault truth definition

A tick is **under injected EMI** iff `t_mono ≥ t_inject` **and** the arm's
readback was CONFIRMED. There is no partial or ramping state: the offset is a
step.

## 3. The campaign — frozen here, not widened later

Per platform, **three arms, three repetitions each**: 9 flights per platform,
**18 flights total**.

| arm | `u` (µT) | role | predeclared expectation |
|---|---|---|---|
| `CLEAN` | 0.0 | null control (RULE A) | **no crossing** |
| `SUB` | 0.5 | expected non-crossing | **no crossing** |
| `CROSS` | 15.0 | expected crossing | **crossing** |

Fixed flight parameters, identical across every arm and both platforms:

* shadow window **40.0 s**, tick rate 25 Hz (≈ 1000 ticks);
* arm and climb before the window (`--fly`), as in every previous campaign;
* injection at **t = 15.0 s** into the window, leaving ≈ 625 post-injection
  ticks — comfortably more than the ~93-tick scale W-4 reports;
* `field_mode` on, profile `FIELD_DERIVED_NOISE` (the shadow default).

**The grid is not widened after seeing results.** If `SUB` crosses or `CROSS`
does not, that is recorded as a missed predeclared expectation, not repaired
with a new magnitude.

## 4. What is measured per tick

A per-engine-step trust trace is written alongside the flight log. Only the
last engine state of each shadow tick reaches the flight log
(`csia/deploy/shadow.py:223`), which is not sufficient to reconstruct a
recursion, so the trace records **every** engine step:

| symbol | field | source |
|---|---|---|
| `T(k)` | `trust[n]` | `TrustState.trust` — the runtime value |
| `e(k)` | `evidence[n]` | `TrustState.evidence` |
| `c_nbr, c_phys, c_temp, c_stat` | `components[n]` | `TrustState.components` |
| `fresh(k)` | `fresh[n]` | `TrustState.fresh` — the update gate |
| `S(k)` | `S[n]` | `core.alpha[n] + core.beta[n]` — runtime, for cross-check only |

`rho(k)` is **not** read from the runtime. It is re-derived offline from the
component scores by the source formula
(`engine.py:141-143`: `d = max(scores) − min(scores)` over the *available*
components, `rho = rho_max − (rho_max − rho_min)·d`), so the reconstruction
depends on the runtime only through the observed evidence and the update gate.

## 5. Endpoints, tolerances and criteria — fixed here

### E1 — recursion fidelity (**primary**)

Reconstruct `T̂(k)` forward from the **first** tick of the flight using only:

* `EngineConfig` constants: `alpha0 = 8.0`, `beta0 = 2.0` → `Ŝ(0) = 10.0`,
  `T̂(0) = 0.8`; `rho_max = 0.998`, `rho_min = 0.95`;
* the observed `e(k)`;
* `rho(k)` re-derived per §4;
* the update gate `avail(k) ∧ fresh(k)` (carry forward when it is false).

**No fitted parameters. No runtime trust is read except for comparison.**

> **PASS iff `max_k |T̂(k) − T_runtime(k)| ≤ 0.02`** over the whole flight, for
> the `mag` node.

`0.02` is the tolerance already used by `tools/deploy/diagnose_escalation.py`
for "is this the same flight". A reconstruction that fails E1 is not a
description of the runtime, and **no crossing claim is made from an arm that
fails E1**.

### E2 — closed-form crossing prediction (**secondary**)

At the injection tick, take `S0 = Ŝ(k_inject)` and `T0 = T_runtime(k_inject)`.
Take `e_f` and `rho_f` as the **medians** of the observed `e(k)` and re-derived
`rho(k)` over ticks `k_inject + 2 … k_inject + 26` (a fixed 1.0 s window,
declared here, not chosen after seeing the trajectory). Solve the W-4 closed
form of §1 for the smallest integer `N` with `T_N ≤ 0.60`.

> **PASS iff `|N* − N_obs| ≤ 25` ticks (1.0 s).**

The tolerance is loose on purpose and is justified rather than convenient: the
closed form assumes `e` and `rho` are *constant* after the step, and they are
not — `rho` in particular tracks the spread between component scores tick by
tick. E2 asks whether the closed form gets the crossing *time scale* right, not
whether it is exact. E1 is the exact test.

### E3 — attribution

The matched `CLEAN` arms on the same platform must show **no crossing** in the
same window. If a `CLEAN` arm crosses, E2 on that platform is **confounded**
and is reported as such rather than as a replication.

This is a live risk on PX4 and is written down before the campaign runs:
`docs/v1_1/PX4_CLEAN_ESCALATION_DIAGNOSIS.md` records mag trust reaching 0.554
with **no injected fault** on 2 of 4 clean PX4 flights. If that recurs here,
PX4's Mechanism B result is confounded by construction, and the honest verdict
is `INCONCLUSIVE` for PX4 — not a replication and not a failure.

### Crossing definition

`T_mag(k) ≤ 0.60`, the `heading_caution` constant in
`csia/runtime/failsafe.py`. `N_obs` is the first such `k` at or after
injection, expressed as an offset in ticks from `k_inject`.

**Escalation is NOT the criterion.** The failsafe additionally requires 1.0 s
of *continuous* dwell and node freshness, and
`PX4_CLEAN_ESCALATION_DIAGNOSIS.md` showed that on PX4 the dwell is what
decides the outcome, not the trust value. Systems Paper I claims threshold
crossing; threshold crossing is what is tested.

## 6. Classification rule — per platform, not pooled

Evaluated independently for ArduPilot and PX4. **Platforms are not pooled.**

| verdict | condition |
|---|---|
| **REPLICATES** | ≥ 1 valid `CROSS` arm crossed; **E1 passes on every valid arm**; E2 passes on ≥ 1 valid crossing arm; E3 holds |
| **DOES_NOT_REPLICATE** | ≥ 1 valid `CROSS` arm, E1 passes, but no crossing occurred, or E2 fails on every valid crossing arm |
| **INCONCLUSIVE** | no valid `CROSS` arm (interventions unconfirmed or downstream unverified), E1 fails, or E3 is confounded |

Combined verdict, mechanically from the two platform verdicts:
`MECHANISM_B_REPLICATES_BOTH` / `..._ARDUPILOT_ONLY` / `..._PX4_ONLY` /
`MECHANISM_B_DOES_NOT_REPLICATE` / `INCONCLUSIVE`.

## 7. If the mechanism fails to transfer

**The result is kept.** No `rho`, threshold, evidence weight or scenario
amplitude is tuned to recover it. A non-replication on a current autopilot is
an external-validity finding about a 2015-era characterisation, and it is worth
more than a replication manufactured by adjustment.

## 8. Deviations

Any departure from this document is recorded in
`research/v1_1/CURRENT_STACK_REPLICATION.md` under a **Deviations** heading,
with the reason, before any result is discussed.
