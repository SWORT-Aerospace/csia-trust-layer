# Planner interventions: safety versus diagnosability (key question 5)

Closed-loop evidence gap search, 2026-09-28. Source ids `Lnnn` are defined in
`research/closed_loop_evidence_gap/PROBLEM_LANDSCAPE.md` §2.

**The brief's example.**

1. A planner suspects propulsion degradation and chooses a gentle trajectory.
2. The gentle trajectory never generates the evidence that would separate
   motor degradation from telemetry corruption.
3. The vehicle becomes **safer but less diagnosable**.

## 1. What is already covered

| work | what it does | aerospace or robot evidence | level |
|---|---|---|---|
| s-FEAST, Ragan, Riviere, Hadaegh and Chung, Science Robotics 2024 (L009) | belief-space tree search that selects informative actions to estimate faults, including **simultaneous actuator and sensor faults intertwined with state estimation**, while enforcing probabilistic state constraints | robotic spacecraft simulator on a collision course; open code (readme read at V4: "actively estimate these faults, even when subject to safety constraints that will be violated shortly") | V0; V4 readme |
| safe real-time active model discrimination, arXiv 2606.19590, 2026 (L008) | output-feedback policy that robustly enforces state-input safety constraints while driving outputs to be consistent with at most one model | simulated quadrotor and fighter-jet model, hardware ground robot, quadruped; up to 11 fault modes; under 50 ms | V0 |
| guaranteed active diagnosis by input design (L007) | zonotope and set-valued-observer input design with state and input constraints; closed-loop version | general | V0 |
| unified active detection and control (L006) | control objective and detection objective in one optimal design; control conflicts with excitation | general | V0 |
| closed-loop active diagnosis with minimum performance loss (L005) | auxiliary inputs that minimise closed-loop performance degradation | general | V0 |
| safe diagnosability and active safe diagnosis (L010, L011) | diagnose before forbidden behaviour; controller designed so that the system stays diagnosable | discrete-event systems; space on-board procedures (L011) | V0 |
| observability-aware planning (L018) | planners tend to move into unobservable subspaces; trajectories optimised for observability | quadrotor GPS-IMU self-calibration | V0 |
| dual effect (L013) | control affects the quality of future estimates | theory | V0 |
| the repository's own active-evidence study (L071) | with no current variation, a resistance rise was invisible to the fitted estimate | desktop simulation; its prior-art search is recorded as incomplete | V4 |

**The trade-off is named and studied**, under several names:

- "safety versus diagnosability";
- "control conflicts with excitation";
- "performance degradation from auxiliary inputs";
- "safe diagnosability".

There are aerospace examples (L008, L009), including the exact actuator-
versus-sensor ambiguity that XSYS-001 constructed.

## 2. What remains

The narrowest remaining question is **passive accounting**:

- a planner or controller chose an action for safety, not for diagnosis;
- the monitor should recognise that this action made the competing
  hypotheses indistinguishable;
- persisting ambiguity is then "uninformative because of our own action",
  not evidence of health.

**Red team.**

1. **A likelihood-based or set-based diagnoser already does this.** If both
   hypotheses predict the same observation for the executed input, the
   posterior does not move, or the sets do not separate.
   - The false exoneration in XSYS-001 (L069) came from a **threshold
     witness** read against a closed-loop envelope (L070).
   - It did not come from a diagnoser that evaluates hypotheses under the
     executed input.
2. **Computing separability for a given input in real time** is what L007
   and L008 do. L008 does it in under 50 ms for aircraft-like models.
3. **Choosing actions that trade safety against diagnosis** is what L006,
   L009 and L010 do.

## 3. Answer to key question 5

**Active diagnosis covers the trade-off.** It includes a safety-constrained,
real-time, aerospace-relevant form (L008, L009) for actuator-versus-sensor
ambiguity.

- What remains, passive accounting of diagnosability lost through other
  modules' actions, is handled by construction in any probabilistic or
  set-based diagnoser.
- Its only open part is scale and speed, which is already being pursued.
- Candidate P06 is **OPEN_BUT_CROWDED**, N1.
- Condition 4 of the brief fails: the residual is a direct application of
  known diagnosis theory.
