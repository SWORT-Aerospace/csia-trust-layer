# PX4 SIH preflight for the Set-B-plus-dynamics experiment (gates G1–G4)

**Status: PREFLIGHT, source read only.** Nothing was built, flown or patched.
No CSIA code, threshold, sealed artifact or ledger entry was touched. Written
under `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`. It answers the gating
source read in `docs/research/SITL_FEASIBILITY_MATRIX.md` §4 for the design in
`docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md`.

Every statement below carries one of these labels:

- **SOURCE**: read in PX4 at the pinned commit, with the file and line.
- **PROBE**: computed by a small script that re-implements only the cited
  equations. It is not a PX4 run.
- **PREDICTED**: follows from the source but has not been observed in a run.
- **UNVERIFIED**: not established by this read.

---

## 1. PX4 commit

| | |
|---|---|
| commit | `547e2caa9883bc1609325f02b4914b4e2482fe62` |
| subject | fix(uavcan): use rangefinder beam orientation (#28199) |
| commit date | 2026-08-24 |
| obtained by | `git fetch --depth 1 origin 547e2caa9883bc1609325f02b4914b4e2482fe62` from `https://github.com/PX4/PX4-Autopilot.git`, then `git checkout FETCH_HEAD` |
| not used | upstream HEAD on the day of the read, `bd7d86e141745e156ab75ff95132298b959a33ed` |

This is the SHA that the feasibility matrix and the experiment design pin.
Every PX4 line number below refers to this commit. The checkout was read-only
and is outside this repository.

---

## 2. Source files inspected

| area | file (PX4 tree) | what it established |
|---|---|---|
| SIH core | `src/modules/simulation/simulator_sih/sih.cpp` | loop timing (103-210), per-step order (224-278), parameter reload (279-359), rotor model and ESC publication (361-440), force model (443-456), rigid body (630-700), IMU synthesis (722-757), ground truth (850-920), noise (925-950), fixed seed (61) |
| SIH declarations | `src/modules/simulation/simulator_sih/sih.hpp` | publications (136-144), `actuator_outputs_sim` subscription (147), failure config (148), `_u[]` rotor state (266) |
| SIH parameters | `src/modules/simulation/simulator_sih/sih_params.yaml` | `SIH_T_MAX` 5.0 N (84), `SIH_Q_MAX` 0.1 N m, `SIH_T_TAU` 0.05 s (257), `SIH_MASS` 1.0 kg. There is **no** per-motor parameter |
| RPM mapping | `src/modules/simulation/simulator_sih/aero.hpp` | `throttle_to_rpm(u, rpm_max) = rpm_max·sqrt(clamp(u,0,1))` (267) |
| simulator output | `src/modules/simulation/pwm_out_sim/PWMSim.cpp`, `PWMSim.hpp` | `actuator_outputs_sim` built from the mixer output, motors rescaled to [0, 1] (63-97). PWM constants 900/1000/2000 (80-83). No failure hook |
| mixer | `src/lib/mixer_module/mixer_module.cpp` | also publishes `actuator_outputs` in PWM units from the same values (659-668) |
| failure library | `src/lib/failure_injection/FailureInjection.cpp` | `process_esc` (168-200): Off blanks an ESC report, Wrong scales rpm ×10 and V, I ×0.1 |
| failure catalogue | `src/modules/failure_injection_manager/FailureTable.cpp` | MOTOR supports only OK/OFF. ESC supports OK/OFF/WRONG. STUCK exists only for sensors (40-75) |
| failure gating | `src/modules/failure_injection_manager/failure_injection_manager_params.yaml` | `SYS_FAILURE_EN` default 0, reboot required |
| failure messages | `msg/FailureInjection.msg` | unit 101 MOTOR, 106 ESC |
| motor stop path | `src/modules/commander/failure_detector/FailureInjector.cpp` | MOTOR Off becomes `motor_stop_mask` (42-50) |
| allocator | `src/modules/control_allocator/ControlAllocator.cpp` | status publication gated at 5 ms (458). Stopped motors get NaN (611-632). The stop mask is consumed only when `CA_FAILURE_MODE` is 1 or 2 (805-830). Achievement is computed from the allocator's own model (638-690) |
| allocator params | `src/modules/control_allocator/module.yaml` | `CA_FAILURE_MODE` default 0 = Ignore (623-638) |
| ESC consumers | `src/modules/commander/HealthAndArmingChecks/checks/escCheck.cpp`; `src/modules/sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp`; `src/modules/esc_battery/` | all gated off by default: `COM_ARM_CHK_ESCS` 0, `FD_ACT_EN` 0, `IMU_GYRO_DNF_EN` 0, and `esc_battery` is not started for SIH |
| rates | `src/modules/sensors/vehicle_angular_velocity/imu_gyro_parameters.yaml`; `src/modules/sensors/vehicle_imu/imu_parameters.yaml` | `IMU_GYRO_RATEMAX` default 400, `IMU_INTEG_RATE` default 200, `IMU_GYRO_CUTOFF` 40 Hz, `IMU_DGYRO_CUTOFF` 20 Hz |
| startup | `ROMFS/px4fmu_common/init.d-posix/rcS`; `px4-rc.simulator`; `px4-rc.sihsim`; `px4-rc.mavlink`; `ROMFS/px4fmu_common/init.d/rc.mc_defaults`; `rc.logging`; `ROMFS/px4fmu_common/init.d-posix/airframes/10040_sihsim_quadx` | rate overrides, logger poll topic, MAVLink stream rates, quad geometry |
| lockstep | `boards/px4/sitl/sitl.cmake`; `boards/px4/sitl/default.px4board` | lockstep ON unless replay. `CONFIG_MODULES_FAILURE_INJECTION_MANAGER=y` |
| logger | `src/modules/logger/logged_topics.cpp`, `logger.cpp`, `module.yaml` | per-topic intervals, profiles, `logger_topics.txt`, poll topic, gap counter, parameter-change records |
| interval semantics | `platforms/common/uORB/SubscriptionInterval.cpp` | the decimation rule the logger applies (44-83) |
| MAVLink | `src/modules/mavlink/mavlink_main.cpp` | ESC_STATUS stream rates per mode (1636-2104) |
| estimator | `src/modules/ekf2/EKF2.cpp`, `module.yaml` | attitude every IMU sample (882). Innovations only on a filter update (827-847), stamped with the delayed horizon (1423). `EKF2_PREDICT_US` 10 ms, `EKF2_DELAY_MAX` 200 ms, `EKF2_LOG_VERBOSE` 1 |
| hover thrust | `src/modules/mc_hover_thrust_estimator/MulticopterHoverThrustEstimator.cpp`; `msg/HoverThrustEstimate.msg` | runs on `vehicle_local_position` updates |
| messages | `msg/EscReport.msg`, `msg/ActuatorOutputs.msg`, `msg/versioned/ActuatorMotors.msg`, `msg/ControlAllocatorStatus.msg`, `msg/EstimatorInnovations.msg`, `msg/ParameterUpdate.msg` | units and timestamp fields |

---

## 3. Signal and data flow (SOURCE)

The five categories the brief asks to keep apart are marked on the right.
Timing is for one lockstep step *k* of 4 ms of simulated time (see G3).

```
  mc_rate_control ── vehicle_torque_setpoint / vehicle_thrust_setpoint ─────────────────── COMMAND (controller)
        │                                   │
        │                                   ▼
        │                   control_allocator ──► actuator_motors.control[i]   [0,1]        COMMAND (allocated)
        │                     (NaN only if motor_stop_mask AND CA_FAILURE_MODE≠0)
        │                                   ▼
        │                   pwm_out_sim / MixingOutput
        │                     ├──► actuator_outputs.output[i]        PWM 1000..2000         COMMAND (same value, PWM units)
        │                     └──► actuator_outputs_sim.output[i]    [0,1], stamped t(k-1)  COMMAND INTO THE SIMULATOR
        │                                   ▼  read_motors(), sih.cpp:361-380, at t(k)
        │                   _u[i] ← _u[i] + (dt/τ)(u_sp − _u[i]),  τ = SIH_T_TAU           PHYSICAL STATE (rotor)
        │                        │                       │
        │                        │                       └► esc_rpm = round(10000·√_u[i])
        │                        │                           └► process_esc(failure cfg) ► esc_status   TELEMETRY
        │                        ▼  generate_force_and_torques(), sih.cpp:443-456
        │                   T_B = −T_MAX·Σ_u ;  M_B = (L·T_MAX·(±_u), L·T_MAX·(±_u), Q_MAX·(±_u))       PHYSICAL STATE (wrench)
        │                        ▼  equations_of_motion(), sih.cpp:630-700
        │                   ω̇ = I⁻¹(M_B + M_aero − ω×Iω),  v̇ = F/m                                  VEHICLE RESPONSE (truth)
        │                        ├► vehicle_{angular_velocity,attitude,local_position}_groundtruth    VEHICLE RESPONSE (truth, published)
        │                        ▼  reconstruct_sensors_signals(), sih.cpp:722-757
        │                   sensor_accel = specific force + noise ; sensor_gyro = ω + noise           VEHICLE RESPONSE (measured)
        │                        ▼
        │                   sensors ► sensor_combined, vehicle_angular_velocity, vehicle_acceleration
        │                        ▼
        └────────────────── rate loop       EKF2 ► vehicle_attitude, estimator_innovations,           ESTIMATED STATE
                                            vehicle_local_position ► hover_thrust_estimate
```

**Explicit collapse statements, as the brief requires.**

1. **PX4 SIH collapses TELEMETRY and PHYSICAL ROTOR STATE into one variable,
   `_u[i]`.** `esc_rpm` is a noiseless, deterministic, monotonic function of
   `_u[i]` (`sih.cpp:424`). No sensor model, noise, delay or failure sits
   between them. The only thing that can separate them natively is
   `process_esc` at publication (`sih.cpp:440`).
2. **PX4 SIH also collapses PRODUCED THRUST into the same variable.** Per-rotor
   thrust is `T_MAX·_u[i]` and yaw torque is `Q_MAX·_u[i]` (`sih.cpp:450-452`).
   Rotor speed, reported RPM and produced thrust are therefore three views of
   one number. Thrust and RPM are consistent (T ∝ RPM²), but neither is an
   independent physical state.
3. **COMMAND is kept separate from the rotor state, but only by a first-order
   lag.** `actuator_outputs_sim.output[i]` and `_u[i]` are different variables.
   Natively, `_u[i]` has no input except the command history.
4. **VEHICLE RESPONSE is genuinely independent of the telemetry.** The IMU,
   attitude and ground truth come from integrating the wrench through the
   rigid-body equations. Nothing in the control loop reads `esc_status`
   under the SIH quad defaults (§2, ESC consumers). A telemetry-only fault
   therefore cannot leak into the dynamics.
5. **ESTIMATED STATE is separate.** EKF2 and the hover-thrust estimator run on
   the synthesized sensors, not on SIH internals.

---

## 4. G1 — RPM semantics: **PARTIAL**

| question | answer | evidence |
|---|---|---|
| 1. Derived directly from the command? | **No.** It is derived from the lagged rotor state `_u[i]`, not from `actuators_out.output[i]`. For the quad no channel bypasses the lag; only fixed-wing surface channels (i<3) and tailsitter channels (i>3) do. | `sih.cpp:367-375`, `424` |
| 2. Independent rotor state? | **Partly.** `_u[i]` is a real state with its own dynamics. It has no load torque, no electrical model, no disturbance and no failure input, so it is a fixed function of the command history. | `sih.cpp:361-380`, `sih.hpp:266` |
| 3. Lag / inertia? | **Yes.** First-order, τ = `SIH_T_TAU` = 0.05 s, forward Euler with α = dt/τ = 0.08 at 4 ms. **PROBE:** a 0→1 step reaches 63 % at 48 ms and 95 % at 144 ms. | `sih.cpp:374`, `sih_params.yaml:257` |
| 4. Can commanded and physical RPM disagree? | **Only transiently, natively.** In steady state `_u[i] = u_sp` exactly, so a *persistent* disagreement cannot arise without modification. `SIH_T_TAU` can be raised in flight, which lengthens the transient for all rotors, but it is still a lag and not a deficit. | `sih.cpp:374`, `227-234` |
| 5. Source | `Sih::read_motors`, `Sih::publish_esc_status`, `Thruster::throttle_to_rpm`, `failure_injection::process_esc` | §2 |
| 6. Units | `esc_rpm` is int32, **rev/min** (`msg/EscReport.msg:4`). Mapping: `rpm = 10000·√u` with `max_rpm` hard-coded 10000 for multicopters (`SIH_F_RPM_MAX` applies to FW/VTOL only). **PROBE:** at hover u = 0.4904 and rpm = 7003. `esc_voltage` and `esc_current` are never set, so they are 0; there is no ESC current or voltage channel. `esc_temperature` is a constant 50. | `sih.cpp:407-424` |
| 7. Native rate | Published once per new `actuator_outputs_sim` sample, inside `read_motors`. Under lockstep that is once per SIH step: **250 Hz**. | `sih.cpp:363-378`; G3 |

**Why PARTIAL rather than PASS or FAIL.** The design's fear in
`docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md` §7 was that the RPM echoes the
command. **It does not.** It reports the rotor state, so it would be honest
about a rotor that is slower than commanded. But natively nothing can make the
rotor persistently slower than commanded, so PX4 SIH has no native "commanded
≠ physical RPM" beyond the 50 ms lag. PASS would need an independent rotor
state; FAIL would need a command echo. SIH has neither.

---

## 5. G2 — motor failure injection: **PATCHABLE**

Requirement: the controller commands thrust, the produced thrust is reduced or
zero, and the command signal is **not** falsified.

### Every native mechanism, traced into the physics (SOURCE)

| mechanism | acts on | reaches SIH physics? | command ≠ physical effect? | usable for member A? |
|---|---|---|---|---|
| `failure motor off` (unit 101). Needs `SYS_FAILURE_EN`=1 (default 0, reboot) | FailureInjector → `motor_stop_mask` → ControlAllocator | **only if `CA_FAILURE_MODE` ∈ {1,2}** (default 0). At the default it reaches neither command nor physics; it appears only in `failure_detector_status.motor_stop_mask` (`FailureDetector.cpp:95`) | **No.** When enabled, the allocator writes NaN into `actuator_motors`. The mixer maps NaN to the disarmed value (`mixer_module.cpp:543-544`), `pwm_out_sim` then leaves the channel at 0 (`PWMSim.cpp:73`), and SIH receives 0. Command and physics are both zero: **the command itself is falsified** | **No.** It is also OFF only, with no partial level |
| `failure esc off / wrong` (unit 106) | `process_esc` on SIH's outgoing `esc_status` | **No.** Telemetry only | n/a: physics untouched | No. It is a native **member B** (Off ≈ MS_B5 "speed channel dead"). Wrong ×10 over-reports, the opposite direction of COMMAND_NO_RESPONSE |
| STUCK failure type | sensors only (`FailureTable.cpp:45-58`) | no motor path | — | No |
| sensor units (gyro, accel, airspeed, distance) in SIH | SIH sensor publication | sensors, not actuators | — | No |
| `CA_FAILURE_MODE`, `FD_ACT_EN` failure detection | detection and re-allocation | response machinery, not injection | — | No |
| actuator test, ice shedding | command-side overrides | via command | command = physics | No |
| `pwm_out_sim` | — | no failure hook exists | — | No |
| **`SIH_T_MAX` changed in flight** | `Sih::parameters_updated`, applied at the next step | **Yes** | **Yes.** Command, `_u` and `esc_rpm` are untouched while thrust and roll/pitch torque scale down | **Symmetric only**: all four rotors at once. It cannot produce a `motor_0` fault. It is a native partial-loss probe, not a Set B member |
| `SIH_Q_MAX`, `SIH_T_TAU`, `SIH_MASS` in flight | same | yes | yes, all rotors | not a single-motor fault |

**Conclusion: no native mechanism reduces one motor's physical output while
leaving its command intact.** Mid-flight parameter reload is safe: it does not
reset position or attitude while the location parameters are unchanged
(`sih.cpp:320-338`).

### Smallest research-only simulator modification — SPECIFIED, NOT IMPLEMENTED

**Variant M: rotor-target effectiveness (recommended).** One per-motor
effectiveness η ∈ [0, 1] scales the rotor's *target*, so the rotor physically
cannot reach commanded speed.

```text
PROPOSED PX4 PATCH at 547e2ca — NOT APPLIED

sih_params.yaml      + SIH_MOT_EFF1 .. SIH_MOT_EFF4   float, default 1.0, min 0.0, max 1.0,
                                                      reboot_required false
                                                      (EFF1 is Motor1 = _u[0] = CSIA motor_0)
sih.hpp              + four ParamFloat entries in DEFINE_PARAMETERS
                     + float _mot_eff[4] {1.f, 1.f, 1.f, 1.f};
sih.cpp  parameters_updated()
                     + _mot_eff[k] = math::constrain(_sih_mot_effN.get(), 0.f, 1.f);   (k = 0..3)
sih.cpp  read_motors(), lagged branch, before the lag update (line 374)
                     + if (_vehicle == VehicleType::Quadcopter && i < 4) { u_sp *= _mot_eff[i]; }
```

About 15 lines in three files. The consequences, all read from the code as it
would stand after the patch (PREDICTED):

- **Command untouched.** `actuator_motors`, `actuator_outputs` and
  `actuator_outputs_sim` are produced upstream of the patch point.
- **The physics is the fault site.** The rotor settles at η·u_cmd with the
  existing τ. Thrust and yaw torque of that rotor fall by η, and roll/pitch
  torque falls through the same `_u`.
- **Telemetry stays honest.** `esc_rpm` reports the reduced rotor. The
  COMMAND_NO_RESPONSE symptom on `motor_0` is therefore **produced by the
  physics**, which is what the matched set requires
  (`docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md` §4).
- **Produced thrust is recoverable from the log.** T_i = T_MAX·(rpm_i/10000)².
  **PROBE:** integer rounding of rpm bounds the error at about 4·10⁻⁴ N.
- **A no-op at the default.** Multiplying by 1.0f is exact in IEEE-754, so an
  unpatched and a patched run at η = 1 differ in no arithmetic. That claim is
  verifiable by a twin run and must be checked before any trial.
- **Onset** is a parameter set (`param set SIH_MOT_EFF1 0.75`, or MAVLink
  PARAM_SET). SIH applies it at the start of the next step (`sih.cpp:227-234`).

**Variant P, rejected for this experiment: effectiveness in the force model.**
Scaling `_u[i]` only inside `generate_force_and_torques` models a damaged
propeller: the shaft turns at commanded speed and the RPM agrees with the
command. It would **not** produce COMMAND_NO_RESPONSE, so member A would leave
Set B's symptom class. Its produced thrust would also not be recoverable from
any logged topic without a further publication.

**Not proposed:** changing `failure_injection`, the allocator, `pwm_out_sim`
or the MOTOR unit. Each of those acts on the command path, which is what the
brief excludes.

---

## 6. G3 — rates: **PASS**, with a required logging configuration

### Simulator clock (SOURCE)

The lockstep loop runs at `min(IMU_GYRO_RATEMAX, IMU_INTEG_RATE)`
(`sih.cpp:105`). In the SIH quad startup:

- `rc.mc_defaults` raises `IMU_GYRO_RATEMAX` 400 → 800;
- `px4-rc.simulator` sets `IMU_INTEG_RATE` 250;
- so the rate is **250 Hz, 4000 µs of simulated time per step**.

SIH sets the process clock itself (`px4_clock_settime`, `sih.cpp:132-135`). It waits for every
lockstep component, including the logger, and for a fresh
`actuator_outputs_sim` before advancing (`sih.cpp:150-169`). The *realtime*
loop and its 250 Hz fallback (`sih.cpp:184-210`) are **not** used in the
default SITL build (`boards/px4/sitl/sitl.cmake`).

### Rate table

In the table below:

- "ULog default" is `SDLOG_PROFILE` = 1 in the SITL build.
- "Achievable" needs no code change: either a `SDLOG_PROFILE` bit or a line in
  the logger's `etc/logging/logger_topics.txt`, whose topics are added on top
  of the profile (`logged_topics.cpp:616`).
- Logged rates come from **PROBE** of the interval rule in
  `platforms/common/uORB/SubscriptionInterval.cpp:77` applied to a 4 ms stream.

| signal | topic | SIH internal | uORB publication | ULog default | ULog achievable | MAVLink (SITL scripts) |
|---|---|---|---|---|---|---|
| command into SIH | `actuator_outputs_sim` | read each step | 250 Hz | **not logged** | 250 Hz (topics file) | none |
| same command, PWM units | `actuator_outputs` | — | 250 Hz | 10 Hz | 250 Hz | SERVO_OUTPUT_RAW 50 Hz on the GCS link (`px4-rc.mavlink`) |
| allocated command | `actuator_motors` | — | 250 Hz | **10 Hz** | 250 Hz (profile bit 3 or 4, or topics file) | — |
| physical rotor state | `_u[i]`, not published | 250 Hz | only via `esc_status` | — | as `esc_status` | — |
| ESC RPM | `esc_status` | 250 Hz | 250 Hz | **10 Hz** | 250 Hz (topics file, interval 0). Bit 4 alone gives 200 Hz at alternating 4/8 ms spacing | **ESC_STATUS 1 Hz on the GCS link, 10 Hz on the offboard link** (`mavlink_main.cpp:1649`, `1719`) |
| angular velocity, raw | `sensor_combined.gyro_rad` | 250 Hz | 250 Hz | 250 Hz | 250 Hz | HIGHRES_IMU 50 Hz (onboard) |
| angular velocity, filtered | `vehicle_angular_velocity` | — | 250 Hz | 100 Hz (SITL block) | 250 Hz | ATTITUDE 50 Hz (GCS) |
| angular velocity, truth | `vehicle_angular_velocity_groundtruth` | 250 Hz | 250 Hz | 100 Hz | 250 Hz | — |
| angular acceleration | not published by SIH. `vehicle_angular_velocity.xyz_derivative` is a filtered derivative | 250 Hz | 250 Hz | 100 Hz | 250 Hz | — |
| linear acceleration | `sensor_combined.accelerometer_m_s2` | 250 Hz | 250 Hz | 250 Hz | 250 Hz | HIGHRES_IMU 50 Hz |
| attitude, estimated | `vehicle_attitude` | — | 250 Hz (EKF2 output predictor) | 250 Hz (SITL block, interval 0) | 250 Hz | ATTITUDE 50 Hz |
| attitude, truth | `vehicle_attitude_groundtruth` | 250 Hz | 250 Hz | 100 Hz | 250 Hz | — |
| estimator innovations | `estimator_innovations` | — | 100 Hz (filter update, `EKF2_PREDICT_US` 10 ms). Each aiding source changes only at its own sensor rate | 100 Hz (SITL block) | 100 Hz | — |
| allocation state | `control_allocator_status` | — | **125 Hz** (5 ms gate on a 4 ms loop, 8 ms spacing) | **5 Hz** | 125 Hz | — |
| torque / thrust setpoint | `vehicle_torque_setpoint`, `vehicle_thrust_setpoint` | — | 250 Hz | 50 Hz | 250 Hz | — |
| hover thrust estimate | `hover_thrust_estimate` | — | on each local-position update | 10 Hz | full | — |

**How the logger is driven (SOURCE).** In SITL the logger polls on
`ekf2_timestamps`, one per IMU sample (`rcS:373-378`). It is a lockstep
component (`logger.cpp:704`, `921`). For interval-0 topics it counts missed
generations (`logger.cpp:462-468`), so any drop is reported rather than silent.

**Verdict: PASS.** Every signal the witnesses need exists at 100–250 Hz in
simulation and can be captured in ULog at that rate with configuration alone.
That is 4 ms resolution against a 50 ms rotor time constant, which is ample
for sub-second discrimination.

**Two conditions come with the PASS:**

- **Logging configuration.** The default profile is **not** adequate. It logs
  `esc_status` and `actuator_motors` at 10 Hz, `control_allocator_status` at
  5 Hz, and not `actuator_outputs_sim` at all.
- **The experiment must read ULog, not MAVLink.** This repository's existing
  PX4 SITL path observed ESC data over MAVLink at about 1 Hz. That is the GCS
  stream rate, not the simulator rate, and it is **FAIL**-grade for this
  purpose.

---

## 7. G4 — partial thrust loss: **PATCHABLE**

| question | answer |
|---|---|
| native per-motor partial loss (100→75/50/25/0 %) | **No** (SOURCE). There is no per-motor parameter, and MOTOR supports OFF only |
| native continuous parameter | **Symmetric only.** `SIH_T_MAX` is continuous and reloads in flight, but applies to all rotors |
| minimum modification | the same Variant M patch as G2. η is continuous in [0, 1], so 1.0 / 0.75 / 0.50 / 0.25 / 0.0 are single parameter values |
| changes the rigid-body dynamics? | **Yes, through the wrench, not through the body.** Mass, inertia and drag are unchanged. Force and torque enter `equations_of_motion` (`sih.cpp:637`, `698`), so accelerations, rates, attitude and position respond |
| controller compensates? | **Yes, where the loss is feasible** (see below) |
| observables that expose compensation | `actuator_motors.control[0]` rising against the others (W2); `vehicle_torque_setpoint` offset (rate-loop integrator); `control_allocator_status.actuator_saturation[0]` **only when it saturates**; `hover_thrust_estimate` and `vehicle_thrust_setpoint` under symmetric loss; the onset transient in `sensor_combined` and ground-truth ω (W3) |

**Compensation bound (PROBE, static; the transient is PREDICTED only).**

The SIH quad's roll, pitch and yaw balance (`sih.cpp:450-452`) forces all four
effective rotor states to be equal in steady hover. With the defaults
(m = 1.0 kg, T_MAX = 5.0 N, g = 9.808 at the default latitude), hover needs
effective u = 0.4904 on every rotor, so motor 0 needs a command of 0.4904/η.

| η | command needed on motor 0 | full 4-axis hover | steady `esc_rpm` motor 0 | RPM implied by its command |
|---|---|---|---|---|
| 1.00 | 0.490 | feasible | 7003 | 7003 |
| 0.75 | 0.654 | feasible, compensated | 7003 | 8086 |
| 0.50 | 0.981 | feasible with 2 % margin, effectively at saturation | 7003 | 9904 |
| 0.25 | 1.96 | **infeasible**. If yaw is sacrificed: u0 = u1 = 0.25, u2 = u3 = 0.731, residual yaw torque −0.096 N m | — | — |
| 0.00 | ∞ | **infeasible**. If yaw is sacrificed, residual yaw torque −0.196 N m | — | — |

Two consequences for the design:

- **(a)** For η ≥ 0.5, steady state is **physically nominal**. Every rotor
  delivers hover thrust and all four RPMs read 7003. The fault persists only
  in the command asymmetry (W2) and in the command-vs-RPM residual on motor 0.
  The onset transient (W3) is the only dynamic signature, and it is exactly
  the observability-window risk F3.
- **(b)** For η ≤ 0.25, a quad **cannot** hold yaw (PREDICTED: it spins). That
  tests loss of control, as the feasibility matrix anticipated.

---

## 8. Observability and timestamp table

**The common clock (SOURCE).** Under lockstep:

- every `hrt_absolute_time()` returns **simulated time**, set by SIH once per
  step (`sih.cpp:132-135`);
- every uORB `timestamp` in the table is on that one clock;
- ULog stores each record with its own `timestamp` field.

There is therefore **no inter-clock synchronization error**. What remains are
structural offsets, all deterministic and all measurable from the log.

| quantity | source | timestamp field | offset from the physical event (SOURCE unless marked) |
|---|---|---|---|
| fault onset (patch) | `parameter_update` (logged, interval 0) and the ULog parameter record written in stream order (`logger.cpp:749-756`) | `parameter_update.timestamp` = the simulated time of the `param set` | applied at the **next** SIH step: ≤ 4 ms after the stamp. Visible as the first `esc_status` change on that motor |
| fault onset (native ESC failure) | `vehicle_command` (logged); `failure_injection` (**not** logged by default, add it to the topics file) | `.timestamp` | picked up at the next step's `_failure_config.update()` |
| motor command, allocated | `actuator_motors` | `timestamp`; `timestamp_sample` = the gyro sample it answers | none |
| motor command, into SIH | `actuator_outputs_sim` / `actuator_outputs` | `timestamp` = t(k−1) | applied at step k: **one step (4 ms) transport** |
| physical motor state | `esc_status` (unmodified by injection) | `timestamp` = t(k) | same step as the rotor update |
| produced thrust | derived: T_MAX·(rpm/10000)² | as `esc_status` | none. Rounding error ≤ 4·10⁻⁴ N (PROBE) |
| estimated thrust | `hover_thrust_estimate`, `vehicle_thrust_setpoint` | `timestamp_sample` | estimator dynamics; not a clock error |
| body angular acceleration | finite difference of `vehicle_angular_velocity_groundtruth` (truth) or of `sensor_combined.gyro_rad` | `timestamp_sample` / `timestamp` | the IMU is synthesized in the same step as the integration. The filtered `xyz_derivative` adds 40 Hz and 20 Hz low-pass lag (UNVERIFIED magnitude) and should not be the primary signal |
| linear acceleration | `sensor_combined` | `timestamp` + `accelerometer_timestamp_relative` | same step |
| attitude | `vehicle_attitude` (estimated), `vehicle_attitude_groundtruth` (truth) | `timestamp_sample` | the estimate follows the output predictor. Truth is exact |
| controller compensation | `actuator_motors`, `vehicle_torque_setpoint`, `control_allocator_status` | `timestamp` | one control cycle |
| RPM telemetry | `esc_status.esc[i].esc_rpm` | `timestamp` | as physical state (collapsed) |
| estimator innovations | `estimator_innovations` | **`timestamp_sample` = the EKF's delayed horizon** (`EKF2.cpp:1423`) | the horizon lags by the configured sensor delays, capped by `EKF2_DELAY_MAX` = 200 ms. **Align on `timestamp_sample`, never `timestamp`** |

**Verdict: synchronization error is negligible.** The largest structural offset
on the command → physics → response chain is one 4 ms step, known in sign and
size. The estimator's delayed horizon is not negligible, but it is explicit in
every innovation record.

---

## 9. Minimum simulator modifications required

| # | change | kind | needed for |
|---|---|---|---|
| M1 | Variant M per-motor effectiveness, §5 | **PX4 source patch, about 15 lines, SIH only** | member A and every partial-loss level (G2, G4) |
| C1 | `logger_topics.txt` listing, at interval 0: `actuator_outputs_sim`, `actuator_motors`, `esc_status`, `control_allocator_status`, `vehicle_torque_setpoint`, `vehicle_thrust_setpoint`, `vehicle_angular_velocity_groundtruth`, `vehicle_attitude_groundtruth`, `failure_injection` | runtime configuration, **not** a code change | G3 |
| C2 | `SYS_FAILURE_EN` = 1 | parameter | only if native ESC Off is used for member B. The design produces B in the adapter, which keeps the physical record intact; see §10 |

Nothing in CSIA changes. The patch lives in the PX4 tree, in a research build
that is not yet authorized (`docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`
§4 holds building PX4).

---

## 10. Scientific limitations

1. **Rotor, telemetry and thrust share one variable.** Member A's RPM is
   "honest" only because it is the same number that makes the thrust. A real
   ESC measures back-EMF with its own noise, delay and failure modes. Nothing
   here says what a real ESC reports during a real thrust loss.
2. **The rotor model is a pure first-order lag**, with no load torque, no
   current and no voltage. A real jam stops the shaft faster than τ = 50 ms,
   and a real damaged propeller *raises* RPM through reduced load. Variant M
   models "the rotor cannot reach commanded speed", not a specific mechanism.
3. **Yaw torque scales with η.** Variant M scales thrust and drag torque of
   the rotor together. That is a modelling choice, stated rather than
   validated.
4. **W1 is a saturation witness, not a thrust witness.**
   `torque_setpoint_achieved` is computed from the allocator's **own model**
   (`ControlAllocator.cpp:646-667`), which does not know η. For compensable
   losses (η ≥ 0.5, §7) W1 is PREDICTED **false** in member A after the
   transient, just as in B. The design's expected signature table
   (`docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md` §6) lists W1 = true for A.
   That entry holds only near saturation. This is a design finding for the
   preregistration, not a simulator defect.
5. **The observability window may close (F3).** At η ≥ 0.5 steady state is
   physically nominal (§7). Discrimination then rests on W2 and on the onset
   transient.
6. **Member B produced natively destroys the physical record.** `process_esc`
   runs before publication, so a logged `esc_status` under native ESC
   injection no longer contains the rotor state. Producing B in the adapter,
   as designed, keeps the truth in the log.
7. **C, D and E remain as in the design.** There is no command-delivery
   model (C). SIH publishes no ESC current or voltage (§4, question 6), so D
   and E are not expressible.
8. **Bit-determinism is not established.** SIH seeds `rand()` once with a
   fixed seed (`sih.cpp:61`). The same process-global generator is shared
   with the GPS, baro and mag simulators, which run on other work queues, so
   draw order is UNVERIFIED across runs. Twin-run t1 estimation must be
   checked empirically, as `docs/simulation/PX4_CURRENT.md` already warns.
9. **One airframe, one commit.** All figures are for the default SIH quad at
   `547e2ca`.

---

## 11. Does Set-B-plus-dynamics remain experimentally valid?

**Yes, narrowed and strengthened in known ways.**

- **H1 (A vs B) is testable** once M1 exists:
  - A is a physical fault that produces COMMAND_NO_RESPONSE through the
    physics, with honest telemetry;
  - B is a telemetry fault that cannot leak into the dynamics (§3,
    statement 4);
  - W2, W3 and the onset transient are observable at 4 ms resolution (G3).
- **The §7 fallback of the design is not triggered.** PX4's RPM does not echo
  the command. The limitation that replaces it is §10 item 1.
- **The design must absorb three findings before preregistration:**
  - W1 is expected to be silent for compensable losses (§10, item 4);
  - η ≥ 0.5 settles to physically nominal (F3 risk);
  - η ≤ 0.25 is loss of yaw control, not a discrimination case.

  The informative range is therefore about 0.5 < η < 1, together with the
  onset transient. These are PREDICTED from the source and must be confirmed
  on the development partition. They must **not** be tuned against.
- **H2 (C) stays a boundary probe.** H3 and H4 stay untestable on this
  platform, as the design already states.

---

## Overall verdict

**READY_WITH_MINIMAL_SIM_MODIFICATION**
