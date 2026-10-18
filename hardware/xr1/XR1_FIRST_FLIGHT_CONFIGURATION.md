# F1 — first-flight minimum configuration

**MINIMUM. Every item earns its place by producing evidence F1 needs; nothing
is here because it would be nice to have.**

---

## The configuration

| # | item | what evidence it produces | why F1 needs it |
|---|---|---|---|
| 1 | **flight controller** | `attitude.supported`, `imu.primary.supported`, `baro.altitude.supported`, `actuator.elevon.command_echo` | the aircraft flies, and the frozen core reads its telemetry |
| 2 | **GNSS** | `gnss.position.supported`, `gnss.velocity.supported`, `mag.field.supported` | the four GNSS-gated relations must be **live before** anything else is claimed. E1's PX4 demonstration was narrow (1 of 4) and this is where that gets tested in the air |
| 3 | **calibrated airspeed** | `airspeed.supported` | a flying wing without airspeed has no independent check on its energy state, and `airspeed_regulation` is a declared capability |
| 4 | **reference IMU** | `imu.reference.supported` | `redundant_imu` is a relation in the frozen trust graph. One IMU cannot exercise it. **See `XR1_IMU_COMMON_MODE.md`: same device family, so device-family independence is NO at F1** |
| 5 | **RGB payload** | `camera.rgb.available`, `camera.rgb.calibration_valid`, `visual_odometry.supported` | the mission-product layer needs at least one real product. RGB is the one that produces `bridge_rgb_inspection` |
| 6 | **research logger / CM4** | `timebase.supported` | hosts the CSIA runtime, and holds the **independent** raw archive. If the only copy is on the flight computer's card, a flight-computer failure takes the evidence with it |
| 7 | **power telemetry** | `power.telemetry.supported` | per-domain current and voltage. Without it a power-related degradation is invisible to the assurance layer |
| 8 | **timing / event markers** | underpins `timebase.supported` | a shared hardware edge is what relates the flight computer's clock to the research computer's by **measurement**. Everything that correlates two sensors rests on it |

## What F1 runs

**CSIA SHADOW ONLY.**

| | |
|---|---|
| ZETH authority | **none** |
| active Forge | **none** — contracts are hand-written, not compiled into the runtime |
| SACA | **none** — `ComputeEvidence` comes from the Linux collector, and fields it cannot answer read `UNKNOWN` |
| deliberate physical fault | **none.** That is F3 |
| command path from CSIA | **physically absent.** Receive wire unconnected, verified by tracing it |

## What is deliberately NOT in F1

| absent | why |
|---|---|
| thermal payload | F2. F1 needs one product path, not two |
| structural instrumentation | F2 |
| surface-position sensing | F2/F3 (R10). Its absence is why F1 cannot identify surface effectiveness |
| heterogeneous reference IMU | F2 (R8). F1 accepts the same-device-family limitation and records it |
| four control-surface zones | reserved, not fitted — `XR1_CONTROL_SURFACE_STUDY.md` |
| fault-injection harness | F3 |
| any propulsion redundancy | not assumed anywhere |

## What F1 can and cannot establish

**Can:**
- that the frozen CSIA core ingests real flight telemetry from a real
  airframe in flight;
- which trust-graph relations are **live** on real hardware in real
  conditions — the question E1's PX4 qualification leaves open;
- whether the capability and product layers behave on real evidence as the
  contracts say;
- a latency distribution on the actual research compute, **recorded and not
  adjudicated**, same discipline as E1.

**Cannot:**
- anything about a **fault** — none is injected;
- anything about self-occlusion — that needs a fault;
- any **rate, frequency or prevalence** — one airframe, one configuration,
  under the tested conditions;
- anything about **airworthiness**. Nothing here is a safety case, and no part
  of this repository has been reviewed as one;
- anything about glide, endurance or any aerodynamic property.

## The gate into F1

Every F0 gate item in `XR1_STAGED_CONFIGURATIONS.md`, and in particular:

> **Every `UNKNOWN` sensor transform that F1 depends on must be `MEASURED`.**

Today that is *all of them* (`XR1_PAYLOAD_AND_TRANSFORMS.yaml` —
`usable_for_physical_residual_analysis: NONE`). Until the mount datums exist
and the transforms are measured, F1 would produce evidence whose lever arms
are unknown, and a residual analysis on it would attribute errors to the wrong
place.

## Preregistration

F1 is preregistered before the first flight, on the pattern of
`research/physical_validation/prereg/E2_HARDWARE_BOUNDARY_PREREG.md`:
hypothesis, pinned environment, arms including a **null control**, n and
stopping rule with `planned = valid + invalid + not_attempted`, captured
quantities, and **success is not "it matches"**.

That document does not exist yet and cannot honestly be written until the
airframe does.
