# Flight-computer cassette — a physical-design requirement

**NO CAD IS EDITED BY THIS DOCUMENT.** It states a requirement and the reasons
for it. Whether and how to implement it is a separate decision with its own
geometry work.

---

## The situation that produces the requirement

Two boards are in play, for two different reasons:

| board | why it is in play |
|---|---|
| **Holybro Kakute H743-Wing** | the XR-1 research aircraft's current candidate. A wing-format board with the connector layout a flying wing wants |
| **Pixhawk FMUv6C class** (ref: Holybro Pixhawk 6C) | selected for **E2** from both ArduPilot's and PX4's own source trees — `hardware/validation_rig/E2_BOARD_SELECTION.md`. Four IMUs, MCU family agreeing across both stacks, PX4 SIH on the default target |

They were chosen against different criteria and both choices are right for
their purpose. The problem is what happens next.

## The research benefit, which is the actual argument

**E2 establishes what the frozen CSIA core does against real flight-controller
hardware. If the XR airframe cannot host that board, none of E2's result
transfers to XR without a new argument.**

That is the whole case. Everything below is detail.

Three specific consequences:

1. **A shared software configuration.** The same CSIA build, the same channel
   contract, the same stale-timeout source — the field FL-017 caught nobody
   pinning. If the two articles run different boards *and* different
   configurations, a disagreement between them has two candidate causes and
   the experiment cannot separate them.

2. **Board becomes a controlled variable rather than a confound.** With a
   cassette, "Kakute vs FMUv6C on the same airframe" is a one-variable
   experiment. Without one, it is a different aircraft.

3. **The four-IMU question stays askable.** E1's PX4 demonstration was narrow
   — 1 of 4 GNSS-gated relations live, because PX4 SIH publishes no
   `SCALED_IMU2`. E2 exists partly to find out whether that was the simulator
   or the platform. `redundant_imu` is a relation in the frozen trust graph,
   and a board with four declared IMUs is what lets XR ask the same question
   in the air. A single-IMU-class airframe cannot.

## Mass and volume implications

**No numbers are given here, because none can be honest yet.** What is known:

- An adapter plate adds mass. How much depends on material, thickness and
  whether it replaces existing structure or adds to it — none of which is
  decided.
- The cassette envelope is set by the **larger** of the two boards *plus* the
  **deepest connector stack**, which is usually the binding constraint and is
  usually underestimated. The Kakute outline is supplied (45 × 30 × 13.5 mm);
  the FMUv6C-class outline is **not supplied to this session** and is not
  being guessed.
- A cassette that adds mass **at the nose** moves the CG forward, and the CG
  budget is already unresolved because the battery envelope is `UNKNOWN`.

**To be measured before any geometry work:** both boards' hole patterns, both
outlines including connector stack-up, and the battery envelope — because the
cassette's mass and position interact with the one mass item that dominates
the CG.

## Connector considerations

- **The two boards do not share a connector layout.** A cassette that only
  solves the mounting holes solves the easy half.
- The harness should terminate at the **cassette**, not at the board, so
  swapping boards changes one adapter and not the loom.
- **CSIA's telemetry link must remain a physically separate path with its
  receive line unconnected** — the same rule as E2 §4.1. A cassette that
  bundles CSIA's link into a shared connector destroys the property that
  `NO_COMMAND_PATH_REACHABLE` is a fact about the wiring.

## Calibration implications

**A board swap invalidates calibration. All of it.**

- Accelerometer, gyro and magnetometer calibrations are properties of *that
  board in that orientation*, and do not transfer.
- The sensor transform changes: a different board puts the die somewhere
  else, and the die position is not the board centroid — the point
  `XR1_PAYLOAD_AND_TRANSFORMS.yaml` makes at length.
- So each cassette needs **its own `calibration_id`**, and the aircraft
  manifest must record which one flew. That is why `AircraftManifest` carries
  `fc_module_id` and `calibration_set` as separate fields.

## Configuration implications

A board swap changes the aircraft's configuration hash, and it should:

- `AircraftManifest.config_hash` covers `fc_module_id` and `software_set`.
- A **capability support certificate carries the vehicle configuration
  hash**, so certificates issued under one board do not silently apply to the
  other. Bounded property P5 checks exactly this, and BAD_PRODUCT_04 is the
  implementation that gets it wrong.
- The mission-product certificate carries the same hash, for the same reason:
  imagery georeferenced with one board's transforms is not georeferenced with
  the other's.

## The requirement, stated

> **XR-1 should be able to change research flight computer between a Kakute
> H743-Wing and an FMUv6C/Pixhawk-6C-class board without structural
> redesign.**
>
> This means: a cassette or adapter plate whose envelope accommodates both
> outlines plus connector stack-up; a harness terminating at the cassette;
> CSIA's telemetry path kept physically separate and receive-disconnected;
> and a `calibration_id` per cassette recorded in the aircraft manifest.

**Tier: LATER_RESERVED** (R7). Not required for F1 — F1 flies whichever board
is fitted. Required before any attempt to relate XR flight results to E2
bench results, which is the entire reason both exist.

## What would make this unnecessary

Stated so the requirement can be dropped honestly rather than carried out of
inertia: **if XR-1 adopts an FMUv6C-class board outright**, there is one
board, no cassette, and no transfer argument to make. That is a legitimate
answer. It costs the wing-format connector layout the Kakute was chosen for,
and that trade has not been evaluated here.
