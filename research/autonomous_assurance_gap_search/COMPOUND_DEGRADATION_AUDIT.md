# Compound degradation audit

Gap analysis, 2026-09-28. Source ids `Rnnn` are defined in
`research/autonomous_assurance_gap_search/GAP_LANDSCAPE.md` §1.

## 1. The question

The brief's example:

- battery still acceptable;
- motor still acceptable;
- wind still acceptable;
- sensor still acceptable;
- but, together, available control authority < authority required for the
  current mission state.

No component crosses its own failure threshold, yet the aircraft-level safety
assumption is false.

Do existing FTC, health-aware control, MPC, reachability, dynamic envelopes
or IVHM already solve this adequately?

## 2. Is the pattern real?

| evidence | what it shows | level | source |
|---|---|---|---|
| helicopter hover accidents | density altitude, weight and wind combined; OGE hover unavailable even below maximum weight | V0 SC | R066 |
| transport-aircraft loss of control | factors act "alone or more often in combination"; worst combinations identified | V0 SC | R039 |
| eVTOL batteries | sustained high power at low SOC can cause "mid-air electrochemical shutdown"; cold behaves like ageing (industry blog summaries in GQ20, not registered) | V0 SC | R044 |
| certification | SC-VTOL: performance after "combination of failures not extremely improbable"; FAA MEL: no flight with "multiple unrelated deferred items that create a hazard" | V0 | R053, R054 |
| fielded autopilots | per-factor thresholds; thrust loss recognized after 1 s at ≥ 90 % throttle while descending | **V4** | R080–R084 |
| delivery drones / eVTOL | **no incident was found** that is specifically attributed to a composition of individually acceptable electrical, propulsor and wind degradations | — | — |

**Reading.** The pattern is real in rotorcraft and in loss of control. Its
certification relevance is explicit for eVTOL. Direct incident evidence for
electric rotorcraft was **not found**. That is the weakest link in this
candidate's evidence.

## 3. Does an existing family solve it?

| family | what it composes | what it does not do (searched summaries) | adequate? | source |
|---|---|---|---|---|
| fault-tolerant control (L1-adaptive, reconfigurable, passive) | keeps the loop stable after a fault within its design class | it does not output whether the remaining capability suffices for the **mission state** | no, for this question | R002, R033 |
| controllability / authority indices (ACAI, attainable moment set) | rotor degradation → authority index; effector limits → moment set | power-supply limits (battery sag, thermal) and wind demand are not in the summaries | partial | R033, R052 |
| guaranteed reachability / viability under degraded authority | changed dynamics and diminished authority → reachable or viable sets, efficiently, from a nominal precomputation | needs a bound on the degradation; it does not say where that bound comes from at runtime | partial: the theory is strong | R034, R035 |
| safe flight envelope estimation | damage → envelope (database, reachability) | mostly fixed-wing and structural damage; not battery or propulsor power | partial | R032, R051 |
| health-aware control / MPC | RUL/SOH → constrained control effort; battery, wind and saturation in multirotor planning (2026) | optimizes a trajectory; an assurance-grade margin statement is not described in the summary | partial: the **closest threat** | R041, R042 |
| battery power capability (eVTOL) | SOC/SOH → deliverable power for landing; dynamic reserves | the battery side only | partial | R043, R044 |
| thrust-margin monitoring (rotorcraft) | available power and air density → thrust margin against thresholds | turboshaft rotorcraft; electrical and propulsor degradation not in the summary | partial | R045 |
| IVHM / vehicle-level reasoning | fault propagation and root cause across subsystems | diagnoses faults; margin erosion **without** a fault is not its output (earlier packages) | no, for this question | R069 |
| NASA ICM / dynamic vehicle assessment | capability assessment across aerodynamics, propulsion and actuators for UAM | a research programme with a published benchmark problem (2023): **open by NASA's own framing** | partial | R036 |
| fielded autopilots (PX4, ArduPilot) | energy-time check; per-factor thresholds; post-saturation thrust loss | no composed, pre-saturation margin in the files read | no | R080–R084 |

## 4. Verdict

**Not adequately solved as a composed runtime capability. Status N2, LOW
confidence.**

- **The pieces exist.** Each one is N0:
  - authority indices;
  - reachability under degraded authority;
  - battery power capability;
  - battery-aware MPC;
  - thrust-margin monitoring.
- **What was not identified in the searched sources** is a method that
  combines four properties:
  1. it composes electrical power capability, propulsor degradation and
     aerodynamic/wind demand;
  2. it yields a **conservative** margin against the demand of the current
     and planned flight states;
  3. it is evaluated **before** saturation;
  4. it is usable as an assurance statement, not only as an optimization
     constraint.

**The closest threat.** R042, a battery-aware predictive planner that couples
SOC, terminal voltage, wind, motor saturation and actuator degradation. It
must be read in full before this candidate is relied on
(`FULLTEXT_VERIFICATION_QUEUE.md` Q1).

**What would kill it.**

1. **Full text shows it already exists.** R042, R036 or R034 already
   provides a conservative, runtime, composed margin for electric rotorcraft.
2. **Industry practice already does it.** Such margins are demonstrably
   standard in fielded eVTOL or delivery-drone flight control. This is not
   observable from here: UNCLEAR.
3. **Composition adds nothing in simulation.** Single-factor checks with
   ordinary margins already catch every unsafe composition in a controlled
   simulation.
4. **The conservative bound is useless.** It is too conservative to be
   useful, for example because it always alarms in normal operations.
