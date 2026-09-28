# Health → capability → allowable actions: audit

Gap analysis, 2026-09-28. Source ids `Rnnn` are defined in
`research/autonomous_assurance_gap_search/GAP_LANDSCAPE.md` §1.

The brief asks how well existing aerospace systems carry out a three-step
chain:

    component / system health
            ↓
    remaining vehicle capability
            ↓
    allowable autonomy / mission actions

The target is statements such as:

- "maximum safe bank angle now 22°";
- "climb margin now 1.8 m/s";
- "return route A remains feasible, route B does not";
- "hover no longer guaranteed".

The brief does not want only "motor degraded 18 %". The numbers above are the
brief's illustrations; none is asserted here.

## 1. Who produces which link of the chain

| system / method | health input | capability output | action coupling | maturity (searched) | source |
|---|---|---|---|---|---|
| NASA ICM / dynamic vehicle assessment (UAM) | vehicle state, system identification, degradation | vehicle capability, projected into the future | mission completion or modification decisions | research programme; UAM benchmark problem posted 2023 | R036 |
| envelope-aware FMS + FSAM | damage / actuator jam (e.g. rudder jam) | safe flight envelope | envelope-constrained planning; LOC-risk override of crew or automation | research (transport aircraft) | R037 |
| safe flight envelope estimation | identified damage | reachable-set envelope (database or online) | envelope protection, planning | research (transport aircraft) | R032, R051 |
| emergency landing planner / adaptive flight planning | damage-adjusted performance | feasible routes and landing sites ranked by risk | route and site proposal | research (NASA, 2009 onward) | R038 |
| AIRSAFE / iReCoVeR | faults, upsets | LOC risk, envelope | resilient control, recovery | research architecture | R039 |
| ACAI | rotor degradation or failure | available control authority index; controllability test | none directly | research (multirotor) | R033 |
| online guaranteed reachable sets; viability under degraded authority | changed dynamics, diminished control authority | inner and outer reachable sets; viability | "on-board fault-tolerant path planning and failure recovery" | research (theory, examples) | R034, R035 |
| remaining flying time prediction | battery state | time to end of discharge | mission replanning | research, flight-tested on a sub-scale aircraft | R040 |
| battery power-capability assessment for eVTOL landing; dynamic reserves | battery SOC and state of health | deliverable **power** for landing; reserve | landing and reserve policy | research (2024) | R043 |
| health-aware MPC / planning | component RUL or SOH | constrained control effort; reassessed vehicle capability (MDP) | control allocation; mission plan | research | R041, R042 |
| rotorcraft thrust-margin monitor | available power, air density | thrust margin parameter against thresholds | alerting | patent (industry) | R045 |
| competency self-assessment | outcome predictions | task confidence | autonomy-level adjustment | research | R047 |
| PX4 remaining-flight-time check (fielded, V4) | battery time remaining | return-time estimate with parameter factor and margin, wind-aware ground speed | "Remaining flight time low" with configured action | fielded | R081, R082 |
| PX4 wind limit (fielded, V4) | wind estimate | none (threshold) | warning or failsafe action | fielded | R080 |
| ArduCopter thrust loss (fielded, V4) | throttle ≥ 90 %, level, descending for 1 s | none (a post-hoc inference) | thrust boost; optional gripper release | fielded | R084 |

## 2. The brief's four example outputs

| example output | is it produced anywhere in the searched sources? | where | for electric rotorcraft, fielded? |
|---|---|---|---|
| maximum safe bank angle (degraded) | yes, as part of an envelope estimate | R032, R037, R051 (fixed-wing research) | no directly matching fielded output identified |
| climb margin (degraded) | yes: remaining rate of climb is a named certification consideration | R053 (certification); R036 (ICM research) | no directly matching fielded output identified |
| route A feasible, route B not | yes | R038, R037, R046; energy-only in PX4 (R081, R082) | energy-only (PX4 V4) |
| hover no longer guaranteed | yes, as a controllability / authority test after rotor degradation | R033, R034, R035 | only after saturation (ArduCopter V4, R084) |

## 3. Assessment

- **The chain exists end to end in research.** Envelope-aware FMS and the
  emergency landing planner cover it for fixed-wing aircraft (R037, R038).
  NASA ICM covers it for UAM, as an ongoing programme (R036).
- **For electric rotorcraft, fielded open-source practice is thin.** The
  first link is energy-only (R081, R082). Authority is inferred only after
  saturation (R084). Other factors are single-factor thresholds (R080).
- **The missing link is the capability estimate under compound
  degradation.** In the searched sources, the translation from capability to
  actions is established (G03 is killed as terminology). What is missing is
  the middle box of the chain for electric rotorcraft. That box is
  `COMPOUND_DEGRADATION_AUDIT.md` and candidate G02.
- **Proprietary practice is unknown.** Industry eVTOL and delivery-drone
  practice may already produce such outputs internally. Nothing public was
  found either way: **UNCLEAR**.
