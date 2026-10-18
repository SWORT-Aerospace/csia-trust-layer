# Trajectory feasibility prior art: current versus planned demand

G02 kill test, 2026-09-28. Source ids `Knnn` are defined in
`research/g02_capability_margin/G02_DEEP_AUDIT.md` §1.

The brief's example:

- current hover feasible, planned climb into a headwind infeasible;
- return route A feasible, route B infeasible.

The question is whether existing planners already do this **under
interacting health degradation**.

| source | capability side | demand side | interacting degradations? | output | level |
|---|---|---|---|---|---|
| K016 Mueller / Hehn / D'Andrea | thrust and body-rate limits (fixed) | motion primitive (planned) | no (limits given) | feasible / infeasible (sufficient test) | V0 |
| K002 BC-NMPC | evolving thrust ceiling from the battery | NMPC horizon; replanned trajectory | battery × propulsion map | replanned trajectory | V0 |
| K001 Kidambi | terminal-voltage-dependent actuator capability | candidate trajectories propagated closed loop under disturbance | **battery × disturbance × actuator capability** | selected trajectory; reserve penalty | V0 |
| K015 capability-analysis control | quantized remaining capability under actuator faults | regenerated trajectory derivatives | **faults × disturbances** | degraded trajectory | V0 |
| K030 impaired-aircraft trajectory optimization | trim-point envelope of the impaired aircraft | motion primitives from steady-state manoeuvres | damage | trajectory | V0 |
| K007 MDP contingency autonomy | discrete propulsion-failure and battery-degradation states | continue versus land versus terminate | **propulsion failure and battery degradation** | discrete policy | V0 |
| K004 NASA ICM | vehicle capability projected forward | mission modification | propulsive failure; authority degradation; disturbances | mission decision | V0 |
| gap-search R037 / R038 (EA-FMS; emergency landing planner) | damaged-aircraft envelope | routes and landing sites | damage | ranked routes | V0 |
| K027 mission feasibility (UAM; drone delivery) | battery energy | mission plan | energy | feasibility assessment | V0 |
| K029 chance-constrained / CVaR planning | energy or trajectory under uncertainty | planned route | wind; model noise | risk-bounded plan | V0 |
| K031 automotive (friction envelope) | online friction → acceleration envelope | candidate motion plans | friction | selected plan | V0 |
| PX4 (fielded) | battery time remaining | return-time estimate with wind | energy only | return trigger | V4 (gap-search R081, R082) |

## Answer

**Yes. Planners already evaluate planned demand against capability, including
under two-way interacting degradation:**

- battery × disturbance (K001);
- faults × disturbances (K015);
- propulsion failure × battery degradation, as discrete states (K007).

**G02 narrows substantially.** What remains is to feed a single continuous,
four-way composed and **bounded** capability into such a planner:
G02-E2 (N1) and G02-G (N2, LOW).
