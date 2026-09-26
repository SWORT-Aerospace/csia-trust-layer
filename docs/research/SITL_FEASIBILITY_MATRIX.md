# SITL feasibility matrix — PX4 vs ArduPilot for the Set-B-plus-dynamics experiment

**Status: FEASIBILITY ANALYSIS. Nothing was built, installed or flown.**
Written under `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`. Base commit
`e7594e4`.

**Grading rule.** Every cell is graded from **evidence already in this
repository** — a committed measurement, a documented source read, or code that
exists. Nothing is graded from general knowledge of the autopilots.

| grade | meaning |
|---|---|
| **CONFIRMED** | a committed measurement or a run recorded in this repository shows it working |
| **LIKELY** | the mechanism is shown working in this repository for a *neighbouring* case, or the repository's own decoder already declares it, but it has not been exercised for this case |
| **UNKNOWN** | no evidence either way in this repository |
| **UNAVAILABLE** | this repository's evidence shows it does not exist, or exists only in a form that cannot serve this experiment |

Versions are the ones this repository measured: **PX4-Autopilot @ `547e2ca`,
`px4_sitl_default`, SIH** (`docs/simulation/PX4_CURRENT.md`) and **ArduCopter
V4.8.0-dev @ `01a504b`** (`docs/simulation/ARDUPILOT_CURRENT.md`). The CI
qualification lane (`.github/workflows/v11.yml`) builds upstream HEAD, not
these commits, so a reproducible experiment must pin them itself.

---

## 1. The matrix

| capability | PX4 (SIH) | ArduPilot (SITL) |
|---|---|---|
| **fault injection** (motor / actuator) | **LIKELY** | **UNKNOWN** |
| **motor command** | **LIKELY** | **UNKNOWN** |
| **motor truth** (rotor state independent of telemetry) | **UNKNOWN** | **UNAVAILABLE** |
| **IMU** | **CONFIRMED** | **CONFIRMED** |
| **vehicle dynamics** | **CONFIRMED** | **LIKELY** |
| **estimator state** | **CONFIRMED** | **CONFIRMED** |
| **precise onset** (of a motor fault) | **UNKNOWN** | **UNKNOWN** |
| **determinism** (bit-exact, run to run) | **UNKNOWN** | **UNKNOWN** |
| **logging** | **CONFIRMED** | **CONFIRMED** |
| **automation** | **CONFIRMED** | **CONFIRMED** |

No motor or actuator fault has ever been injected on either platform in this
repository. That single fact is why no motor-fault row is CONFIRMED anywhere.

---

## 2. The evidence behind every cell

### PX4 (SIH)

| capability | grade | evidence |
|---|---|---|
| fault injection | LIKELY | PX4's `failure_injection` framework is present at `547e2ca` and was read for GNSS: `research/v1_1/CURRENT_STACK_REPLICATION.md` §2.1 tabulates `failure_injection::process_gnss` (`Off` / `Stuck` / `Wrong`). The **motor** unit was never exercised here, and whether SIH honours a motor failure is not established. |
| motor command | LIKELY | `csia/data/px4_topics.py` declares `actuator_motors` and `actuator_outputs` for the ULog decoder. Declared, not yet observed from an SIH run. |
| motor truth | UNKNOWN | `esc.rpm` **varies** on SIH: 5,558 RPM range, sd 1,307, n = 40 (`docs/simulation/PX4_CURRENT.md` §2.2, §2.5). But the same document says "nobody has read the PX4 source for this field's units, indexing or scaling". Whether SIH derives it from a rotor state or from the command is **not known**. `esc.current` is a stub, constant 0. |
| IMU | CONFIRMED | `imu0` accel and gyro INFORMATIVE under motion: range 3.84 m/s², n = 1,961 (`PX4_CURRENT.md` §2.2). `imu1` is **UNAVAILABLE**: SIH models one IMU. |
| vehicle dynamics | CONFIRMED | IMU informative under motion, and SIH ground truth was used as a reference: yaw vs SIH truth, mean \|err\| 0.237° (`PX4_CURRENT.md` §2). `vehicle_attitude` and `vehicle_local_position` are in the decoder. |
| estimator state | CONFIRMED | `estimator.variances` INFORMATIVE, n = 196 (`PX4_CURRENT.md` §2.2; blocked from CSIA use by policy, which does not stop an experiment from reading it). Innovations (`estimator_innovations`, test ratios) are declared in the decoder but not observed: LIKELY for innovations specifically. |
| precise onset | UNKNOWN | No motor-fault onset has been measured. The timing of the GNSS `failure_injection` path is not characterised here either. |
| determinism | UNKNOWN | The P1 repeat campaign reproduced its qualitative outcomes 20/20 (`research/physical_validation/PX4_REPEAT_RECONCILIATION.md`), but FL-017 records the original trial outside the repeated range, and `--speedup` was **accepted and ignored**, so SIH runs in real time (`PX4_CURRENT.md` §2.4d). Bit-exact repetition is not shown. |
| logging | CONFIRMED | The MAVLink stream passed qualification. An SIH ULog was produced and read with `pyulog` (`research/evidence_semantics/PX4_FEASIBILITY.md` §4). **That log is gitignored and exists only on the authoring machine.** |
| automation | CONFIRMED | `tools/simulation/qualify_platform.py --platform px4` (PASS); `tools/csia_experiment/run_mechanism_a_repeat.py` drove the MECHP1-PX4 campaign; the v11 qualification lane builds and flies PX4 SITL. |

### ArduPilot (SITL)

| capability | grade | evidence |
|---|---|---|
| fault injection | UNKNOWN | The scenario catalogue (`configs/simulation/scenarios_ardupilot.yaml`) covers GPS, IMU bias, magnetometer, battery voltage and vibration — **no motor or actuator failure**. And "a write to a nonexistent parameter does not fail" (`ARDUPILOT_CURRENT.md` §3), so any motor-failure parameter must be verified by its effect, never by its acceptance. |
| motor command | UNKNOWN | `SERVO_OUTPUT_RAW` is in neither the mapped nor the seen-and-unmapped MAVLink inventory (`ARDUPILOT_CURRENT.md` §5). The command exists inside SITL (`motors[i].get_command()`, `SIM_Frame.cpp:901`, per the source read below) but is not observed on any stream this repository consumes. |
| motor truth | UNAVAILABLE | SITL's RPM is `motors[i].get_command() * vibe_motor * 60` — **a scaled copy of the command, not a rotor measurement**, and identically 0 at the default `SIM_VIB_MOT_MAX = 0`. "It is not a motor-speed model." (`research/phase2/INFORMATION_CONTRACT_POWER_THRUST.md` §2.4). `esc.current` is a fixed 0.8 A-per-motor placeholder, constant 3.2 A (`ARDUPILOT_CURRENT.md` §1). |
| IMU | CONFIRMED | `imu0` and `imu1` INFORMATIVE, n = 131,570 (`ARDUPILOT_CURRENT.md` §1). **Both IMUs share one dynamics model**, so an imu0/imu1 disagreement is a noise-model artefact, not independent evidence (§4). |
| vehicle dynamics | LIKELY | IMU CONFIRMED; `ATTITUDE` and `AHRS2` arrive but are deliberately not consumed (§5). No ground-truth comparison is recorded. |
| estimator state | CONFIRMED | `estimator.variances` INFORMATIVE via `EKF_STATUS_REPORT`, logged only (§1). Innovations are not evidenced. |
| precise onset | UNKNOWN | Never measured for a motor fault. For GNSS, onset is commanded at a scripted time with a `verify` block (`research/v1_1/CURRENT_STACK_REPLICATION.md`, onset t = 20.0 s), and the effect-side latency varied across repeats (next row). |
| determinism | UNKNOWN | Outcomes reproduced 20/20, but gate-collapse latency spread 0.993–1.007 s across repeats and the original n = 1 value (0.479 s) fell outside that range (`research/physical_validation/ARDUPILOT_REPEAT_RECONCILIATION.md`, row 9). Bit-exact repetition is not shown. |
| logging | CONFIRMED | The MAVLink stream passed qualification: 131,570 messages in 45 s (`ARDUPILOT_CURRENT.md` §1). Dataflash `.bin` logging is not evidenced. |
| automation | CONFIRMED | `tools/simulation/qualify_platform.py --platform ardupilot` (PASS); `tools/simulation/current_stack_replication.py` (20 of 20 trials valid); `tools/sitl_validate.py`; the v11 lane. |

---

## 3. Rows the experiment needs that the template did not list

| capability | PX4 (SIH) | ArduPilot (SITL) | why it matters |
|---|---|---|---|
| installed in this container | UNAVAILABLE | UNAVAILABLE | neither source tree exists here; three tests skip naming the old ArduPilot path |
| RPM telemetry that could disagree with the command | UNKNOWN | UNAVAILABLE | hypothesis B is "the RPM telemetry is wrong"; that needs a telemetry channel that normally reports the rotor |
| RPM telemetry rate | ~0.97 Hz over MAVLink (`PX4_CURRENT.md` §2.4c); ULog rate UNKNOWN | — | 1 Hz bounds how fast any RPM-based predicate can decide |
| battery current (hypothesis D) | UNAVAILABLE: `-1` sentinel, no sensor modelled | CONFIRMED, but it is the pure motor-current sum with no avionics term | power-path degradation needs a current channel |
| second IMU | UNAVAILABLE | CONFIRMED, shared dynamics | not needed for A vs B; noted so nobody reads an IMU disagreement as independent |
| control-allocation achievement | LIKELY: `control_allocator_status` with `torque_setpoint_achieved` is in the decoder | UNKNOWN | a candidate witness for "the motors could not deliver the demanded torque", independent of RPM telemetry |

---

## 4. Which platform first, and why — from repository evidence only

**PX4 SIH is the better first platform, conditional on one source read that
must come before any flight.**

1. **The question needs an RPM channel that is a candidate rotor
   measurement.** On ArduPilot SITL it is known **not** to be one: it is the
   motor command scaled by a vibration constant, or zero. That is established
   by source read and by measurement. On such a channel, "the RPM sensor is
   lying" and "the RPM sensor is reporting the rotor" are not distinct states
   of the simulator. On PX4 SIH the RPM varies, and whether it measures the
   rotor is **open** rather than closed against us.
2. **PX4's failure-injection framework has already been read and used in this
   repository**, for GNSS. ArduPilot has no evidenced motor-failure route, and
   carries a documented hazard that a wrong parameter name injects nothing
   silently.
3. **PX4 SIH exposes ground truth that this repository has already compared
   against**, which t1 (first physically observable deviation) needs.
4. **The PX4 decoder already declares the witness topics**:
   `actuator_motors`, `control_allocator_status`, `estimator_innovations`.

**Against PX4, stated so the choice is not oversold:**

- one IMU;
- no battery current, so hypothesis D cannot be tested on it;
- ESC telemetry at about 1 Hz over MAVLink;
- runs in real time, since the speed-up flag is ignored;
- not installed here, and it is the heavier build.

**ArduPilot is the better platform for hypothesis D**, because it models
battery current. D is secondary in this experiment.

### The gating source read — before any build or flight

At `547e2ca`, read and record:

| # | question | why it gates the experiment |
|---|---|---|
| G1 | how SIH produces `esc_status.esc_rpm`: from a rotor or motor-speed state, or from the actuator command | if it echoes the command, PX4 has ArduPilot's limitation and the design in `FIRST_CROSS_SYSTEM_EXPERIMENT.md` §7 falls back to its stated alternative |
| G2 | whether `failure_injection` supports the motor unit under SIH, and which failure types (off / stuck / partial) | decides whether hypothesis A can be injected at all |
| G3 | at what rate `esc_status` is logged to ULog | decides the time resolution of every RPM-based predicate |
| G4 | whether a partial thrust loss can be expressed (a scale rather than off) | an "off" motor on a quadrotor is not recoverable, so it tests loss of control rather than discrimination |

Until G1 and G2 are answered, PX4's "fault injection" and "motor truth" cells
stay LIKELY and UNKNOWN, and nothing in this document should be read as
saying the experiment can run.

---

## 5. Dependency requirements — declared, NOT installed

From the CI qualification lane (`.github/workflows/v11.yml`, job "SITL
qualification", timeout 120 min) and this container:

| requirement | PX4 SIH | ArduPilot SITL | present here |
|---|---|---|---|
| source | `PX4-Autopilot`, recursive submodules, **pinned to `547e2ca`** | `ardupilot`, recursive submodules, **pinned to `01a504b`** | no |
| build | `make px4_sitl_default` | `./waf configure --board sitl && ./waf copter` | — |
| C/C++ toolchain | gcc/g++, cmake, ninja, make | gcc/g++, make, python waf | **yes**: gcc 13.3, cmake 3.28.3, ninja 1.11.1, make 4.3 |
| Python build deps | `kconfiglib jinja2 pyros-genmsg empy==3.3.4 packaging jsonschema future lxml pyserial toml` | same install step in CI | **no** for kconfiglib, jinja2, genmsg, empy |
| Python analysis deps | `pyulog`, `pymavlink` | `pymavlink` | **yes** |
| egress | a GitHub clone of each tree | same | clones to github.com work from this session; not tested for these repositories |
| disk | not measured in this repository | not measured | 26 GB free |

The pin matters. CI builds upstream HEAD on purpose, to detect drift weekly,
and the two documents above were verified at the pinned commits. An
experiment built on HEAD would be on a platform nobody here has qualified.
