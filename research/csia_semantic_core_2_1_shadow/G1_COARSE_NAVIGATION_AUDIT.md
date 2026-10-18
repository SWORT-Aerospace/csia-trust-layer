# G-1: what actually serves COARSE_NAVIGATION

**2026-09-30. Part 4 of the shadow-validation brief.** No profile was edited to
write this. The frozen aircraft profile (`csia/v2/profiles/aircraft.py`) is
unchanged. The accepted declarations live in a separate, versioned successor
profile (`csia_semantic_core/successor_profiles/aircraft_successor_r1.json`).

**Source levels.** Repository files and the PX4 tree at commit `547e2ca` were
read at the lines cited (V4). Nothing here rests on an external paper.

## 1. The gap, as 2.1 sees it

2.1's C3 correction scopes the POSITION_UNAVAILABLE detector and its
predicates to the components declared to serve the subject. A component
serves a function when one of its serving relations names that function in
`affected_functions`. The serving relations are timing.end_to_end,
compute.process_* and comm.link_state. The dependency closure of the serving
components is then added.

- **Nothing serves COARSE_NAVIGATION.** No serving relation names it anywhere
  in the frozen aircraft profile. The static validator reports this as
  `PV1_SUBJECT_WITHOUT_SERVING_COMPONENT` (see `PROFILE_VALIDATOR_SPEC.md`).
- **The cause is one tuple.** The estimator process (aircraft.py line 242),
  the CPU resource (line 255) and the nav_solution channel (line 258) all
  take `_NAV_SET = ("PRECISION_NAVIGATION", "POSITION_HOLD",
  "AUTONOMOUS_MISSION")` (line 71). That tuple leaves COARSE_NAVIGATION out.
- **The effect in dataset A.**
  - **601 units are decided by the missing declaration, not by evidence.**
    481 COARSE_NAVIGATION symptoms are no longer raised, and 120 are
    weakened.
  - **Five scenarios' OUTPUT_MISSING units are also weakened.** Those are the
    123 G-2 units, covered in `G2_ESTIMATOR_INPUT_AUDIT.md`.

## 2. What the repository says COARSE_NAVIGATION is

| source | what it says | level |
|---|---|---|
| `engineering/v1_1/FUNCTION_REQUIREMENTS.yaml` lines 53-61 | "Know approximately where the vehicle is." Requires source `gps` and relation `velocity_gps_doppler`; tolerates ambiguity | V4 |
| `csia/v2/profiles/aircraft.py` lines 83-90 | required domains SENSOR and POWER; **supporting** domains COMPUTE and TIMING; "latency and compute pressure degrade but do not remove it"; fallback INERTIAL_CONTINUATION | V4 |
| `engineering/v2/FUNCTION_DEPENDENCY_SPEC.md` line 93 | the same row: SENSOR POWER required, COMPUTE TIMING supporting | V4 |
| aircraft.py lines 215-231 | both rails name COARSE_NAVIGATION: the GNSS receiver is on 5 V, the inertial set on 3V3 | V4 |
| aircraft.py lines 263-268, nav_solution comment | "The position this channel carries arrives over the GNSS link and is computed on the CPU by the estimator." | V4 |
| `engineering/v2/V2_SYNTHETIC_SCENARIOS.md` line 71, scenario D | ESTIMATOR_LATE: "PRECISION_NAVIGATION INELIGIBLE, COARSE_NAVIGATION ELIGIBLE" | V4 |
| `csia/v2/profiles/matched_scenarios.py` lines 396-446 | set D, "position function failure": POSITION_UNAVAILABLE is the symptom for MS_D1 to MS_D4, on every navigation function the v1.1 payload names | V4 |

**The table contradicts itself.** It names COMPUTE and TIMING as domains that
support COARSE_NAVIGATION. No compute or timing component, however, names the
function. The declaration is therefore **dead**: it can never act. The
validator reports it as `PV2_DEAD_SUPPORTING_DOMAIN` for COMPUTE and for
TIMING.

## 3. What PX4 says, at the code

These lines are from the PX4 tree at `547e2ca`, the commit XSYS-001 flew
(V4):

- **EKF2 publishes the position.** It publishes `vehicle_local_position` and
  `vehicle_global_position` (`src/modules/ekf2/EKF2.hpp` lines 477-478).
  EKF2Selector republishes the selected instance.
- **Every position consumer reads EKF2's output.** The position controller
  (`mc_pos_control/MulticopterPositionControl.hpp`), the navigator
  (`navigator/navigator_main.cpp`) and the flight-mode manager
  (`flight_mode_manager/FlightModeManager.hpp`) all subscribe to
  `vehicle_local_position`, the estimator output.
- **The one raw-GNSS consumer is conditional.** The navigator's geofence
  check reads raw GNSS only when the parameter selects it
  (`navigator_main.cpp` lines 1185-1203, `Geofence::GF_SOURCE_GPS`). The
  default is the estimator's global position.

**So on this vehicle a "coarse" position is the estimator's position.**
Coarse and precise differ in how much accuracy the function needs, not in
where the position comes from.

## 4. Every candidate relationship

The candidates were written down, with sources, **before** any of them was
run (`profile_candidates.json`).

| id | relationship | physical / information dependency | documented at | evidence that uses it | scenario that needs it | kind |
|---|---|---|---|---|---|---|
| R2 | state_estimator serves COARSE_NAVIGATION | EKF2 produces every position a navigation function consumes | §3; aircraft.py 83-90 (COMPUTE supporting) | ESTIMATOR_PROCESS_HEALTHY (scoped) | PROCESS_STALL, MS_D2, MS_A4, ESTIMATOR_LATE, CPU_OVERLOAD, MS_C4, MS_D4 | **DIRECT** |
| R3 | nav_solution serves COARSE_NAVIGATION | the timing channel that carries the position; its declared dependencies are the estimator, the CPU and the GNSS link | aircraft.py 258-270 and its comment; 83-90 (TIMING supporting) | FUNCTION_TIMING_WITHIN_DEADLINE, NO_TIMING_SEGMENT_OVER_BUDGET, and FUNCTION_LINKS_NOMINAL through the closure | CLOCK_DRIFT, MS_A1, MS_A2, MS_A3, MS_D3, MS_C3, PACKET_LOSS | **DIRECT** |
| R1 | gnss_serial serves COARSE_NAVIGATION | the GNSS measurement rides the link, but reaches the function only through the estimator | aircraft.py 186-189 (SOURCE_DEPENDENCIES gps) | FUNCTION_LINKS_NOMINAL | MS_D3, MS_C3, PACKET_LOSS | **DERIVED**: implied by R3's closure |
| R4 | gnss_serial serves POSITION_HOLD, PRECISION_NAVIGATION, GEOFENCE_SUPPORT | as R1, for the sibling functions | as R1 | as R1 | none changes | **DERIVED** for POSITION_HOLD and PRECISION_NAVIGATION. **CONDITIONAL** for GEOFENCE_SUPPORT: raw GNSS only under GF_SOURCE_GPS |
| R-BAD | esc_can serves the navigation functions | none: the ESC CAN bus carries motor telemetry and commands (aircraft.py LinkSpec esc_can, `carries=(motor_esc,)`) | — | — | none | **NOT ACTUALLY VALID** (the over-connection control case) |

**What the declarations do inside the frozen function graph.** An overlay
declaration also enters the frozen `FunctionGraph.evaluate`, because the
graph reads the same `affected_functions`.

- **R2 and R3 fall in domains the table already watches** (supporting
  COMPUTE, supporting TIMING). The graph therefore calls COARSE_NAVIGATION
  DEGRADED under an estimator or timing fault. That matches the table's own
  "degrade, not remove".
- **R1 and R4 are COMMUNICATION declarations.** COMMUNICATION is not a domain
  any navigation function watches (aircraft.py lines 75-108). The graph
  ignores them, and the validator reports them as
  `PV3_UNWATCHED_DECLARATION`.

## 5. The counterfactual, in shadow

These runs are on dataset A, 2,640 ticks, against 2.1 without an overlay.
Source: `SHADOW_RESULTS.json`, `counterfactual_profiles`; the full table is
in `PROFILE_COUNTERFACTUAL_RESULTS.md`.

| profile | G-1 units restored | new incorrect | new wrong UNIQUE | POSITION_UNAVAILABLE on a function the graph calls ELIGIBLE |
|---|---|---|---|---|
| none (2.1 as shipped) | — | — | — | 168 of 1,322 |
| R3 alone | 601 | 0 | 0 | 423 of 1,803 |
| R2 alone | 0 (see below) | 0 | 0 | 168 of 1,635 |
| R1 alone | 0 (see below) | 0 | 0 | 252 of 1,406 |
| **R2 + R3 = successor r1** | **601** | **0** | **0** | **252 of 1,803** |
| R1 + R2 + R3 | 601 | 0 | 0 | 252 of 1,803 |

**Reading the rows.**

- **R3 alone restores all 601 units.** The closure brings in the estimator and
  the GNSS link, so R1 adds nothing to 2.1. R2 adds nothing to 2.1 either,
  but it takes 171 contradictions with the function graph away: the graph
  then sees the estimator and calls COARSE_NAVIGATION DEGRADED, not ELIGIBLE.
- **R1 or R2 alone restores nothing and marks some units POSSIBLE_REGRESSION.**
  This is a partial declaration, not a 2.1 fault.
  - With R1 alone the subject has a declared serving component, but the
    timing channel that carries the symptom's evidence is still outside its
    scope.
  - After the classifier was refined to check whether the **injected cause**
    lies inside the scope, R1 alone shows 42 such units and R2 alone none.
    The 42 are MS_A2's transport delay: the delay is visible on nav_solution
    timing, which R1 does not declare.
- **252 contradictions remain under successor r1, all in MS_C3 and MS_D3.**
  - **What the 252 are.** 84 units on each of COARSE_NAVIGATION,
    POSITION_HOLD and PRECISION_NAVIGATION. In every one the GNSS link is
    down and FUNCTION_LINKS_NOMINAL is False.
  - **Why the graph says ELIGIBLE.** It routes a link's effect on navigation
    only through the SENSOR domain, that is through the GPS source's own
    health record.
  - **The harness keeps that record NOMINAL.** It pairs a synthetic link
    fault with a real, clean v1.1 payload, so the source record never
    reflects the fault.
  - **2.1's reading is the physically right one here.**
    `PROFILE_REPAIR_PROPOSAL.md`, under R4, records this as G-3, a
    function-table and harness question that no overlay can settle.

## 6. Decision on G-1

**G-1 RESOLVED in successor profile r1.**

| declaration | decision |
|---|---|
| R2 | ACCEPT |
| R3 | ACCEPT |
| R1 | REJECT: derived through R3, and dead in the function graph |
| R4 | DEFER, with G-3 |

**Why r1 is acceptable:**
- Both declarations are physically direct on the flown vehicle.
- Both sit in domains the frozen table already names as COARSE_NAVIGATION's
  supporting domains, so they bring the dead declarations to life rather than
  invent a new relationship.
- Neither restores a known wrong UNIQUE (`WRONG_UNIQUE_REGRESSION.md`).
- Neither changes XSYS-001 or the Phase C headline
  (`PROFILE_COUNTERFACTUAL_RESULTS.md`).

**What the decision does not claim.**
- **Frozen v2.0 still behaves as it did.** Its function graph, given the
  frozen profile, still calls COARSE_NAVIGATION ELIGIBLE under an estimator
  stall, and v2.0 remains authoritative. Frozen code and data are not edited.
- **"Serves" here is information flow on PX4 EKF2.** A platform whose coarse
  position bypasses the estimator (a separate GNSS-only path) would need a
  different successor profile. The profile is a statement about one vehicle,
  and that is why it is versioned and hashed.
