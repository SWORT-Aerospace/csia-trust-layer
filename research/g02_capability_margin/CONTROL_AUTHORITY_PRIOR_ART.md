# Control authority prior art

G02 kill test, 2026-09-28. Source ids `Knnn` are defined in
`research/g02_capability_margin/G02_DEEP_AUDIT.md` §1.

The brief asks: do these methods already produce a **runtime quantitative
margin**, and are battery/power and environmental constraints inside them or
kept separate?

| method | quantitative output | runtime? | battery / power inside? | environment inside? | level | source |
|---|---|---|---|---|---|---|
| attainable moment set / control allocation | set of moments achievable by the effectors (rate and position limits) | yes (allocation) | not in the summaries; current limits appear in eVTOL allocation (K022) | no | V0 | K022; gap-search R052 |
| ACAI | radius of the largest ball inside the attainable control polytope; a controllability test | computable online (FT) | **no** | **no** | V0 | K013 |
| control performance index (CPI) | index from a degree of controllability, with payload, propulsor degradation and wind **lumped as disturbance**; used to decide landing before loss of control | **yes** | **not stated** | **yes (wind)** | V0 | K014 |
| fault-tolerant margins (σ-range) | stable range of control effectiveness; sensitive to aerodynamic parameter perturbations | offline analysis (FT) | no | via parameter perturbations | V0 | K028 |
| capability-analysis safety control (TCYB) | quantized system capability and safety margin; degraded trajectory regeneration | **yes** | not stated | disturbances | V0 | K015 |
| guaranteed reachable sets under diminished authority | inner and outer reachable sets | **yes** (efficient) | no; takes a degradation bound as input | FT | V0 | K009 |
| viability under degraded authority | set of viable inputs; real-time identification | **yes** | no | no | V0 | K010 |
| current-limited eVTOL allocation | null-space allocation minimizing maximum motor and battery current, including under failures | yes (simulation) | **yes (currents)** | no | V0 | K022 |
| BC-NMPC | collective-thrust ceiling from the battery and propulsion maps | yes (flown) | **yes** | not stated | V0 | K002 |
| ArduPilot (fielded) | throttle ceiling from the ohmic current limit; learned hover throttle; thrust boost after motor loss | **yes** | **yes** | implicitly, through measured demand | **V4** | K051 |
| PX4 (fielded) | unallocated torque and thrust (saturation, after the fact); hover-thrust EKF; motor-failure flags | yes | resistance estimated separately; not in allocation (files read) | implicitly | **V4** | K054, K055, K056 |

## Answer

- **The runtime quantitative authority margin is known.** It exists as ACAI
  and the CPI (K013, K014) and as reachable or viable sets (K009, K010).
- **Environmental demand is already inside the CPI.** Wind is lumped with
  payload and propulsor degradation (K014).
- **Battery and power limits are handled separately.**
  - In research: BC-NMPC's thrust ceiling (K002); current-limited eVTOL
    allocation (K022).
  - In fielded code: ArduPilot's throttle ceiling (K051).
- **No single searched source combines both** battery power **and**
  propulsor degradation **and** wind in one authority margin. Combining them
  is integration (G02-E2, N1).
