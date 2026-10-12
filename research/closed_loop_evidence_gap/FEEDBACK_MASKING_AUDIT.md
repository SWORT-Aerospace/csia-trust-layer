# Feedback masking audit (key question 1)

Closed-loop evidence gap search, 2026-09-28. Source ids `Lnnn` are defined in
`research/closed_loop_evidence_gap/PROBLEM_LANDSCAPE.md` §2.

**The question.** How thoroughly does existing work handle "controller
compensation hides the physical manifestation of a fault"? Beyond that, do
existing systems track **which** diagnostic evidence relations became
invalid because of the compensating action?

## 1. Is feedback masking established?

**Yes.** It is one of the oldest named problems in fault diagnosis.

| what | where | level |
|---|---|---|
| Feedback masks faults. Open-loop diagnostic indexes stop working in closed loop. Adaptive controllers mask data-driven signatures. Control effort and tracking error stay near nominal while the fault is masked. | L002 | V0 SC |
| Control and diagnosis are designed jointly **because** they interact: the four-parameter controller, 1988 | L003 | V0 SC |
| The interaction between diagnosis and reconfiguration (delay, false alarms) is a named integration issue in active FTC | L004 | V0 SC |
| Better control keeps outputs near set point, while detection needs deviations: an explicit detectability-performance trade-off with joint tuning | L014 | V0 SC |
| Closed-loop detection uses the set point, the measurement and the **controller output** | L021 | V0 SC |
| Model-based diagnosis names a "no-fault-masking" assumption and treats exoneration as optional, because correct outputs do not prove health when masking is possible | L020 | V0 SC |
| Accident record: the autopilot held the wings level against asymmetric thrust until the aileron limit (CA006); the autopilot masked icing effects, then disengaged into an upset (ATR 72, plus five earlier ATR 42 events) | L057, L059 | V0 SC |

**XSYS-001 in this frame.**

- The dynamics witness compared vehicle response with the nominal
  **closed-loop** envelope (L070).
- After compensation it read nominal in 55/55 physical-degradation trials,
  and exonerated the physical cause (L069).
- The compensation witness, a controller-output observation, stayed
  informative (L070).

This is the textbook pattern of L002, L014 and L021.

## 2. Do systems track which evidence relations the compensation invalidated?

This is the brief's sharper question. It is different from knowing that
feedback masks faults.

### 2.1 In theory

**Yes, where the intervention is modelled as a mode.**

- **Hybrid-systems diagnosis (L017).** Analytic redundancy relations are
  **mode-dependent**. Mode **sequences** are used to discriminate modes
  whose input-output behaviour is similar. A reconfiguration that is modelled
  as a mode change therefore carries an explicit statement of which residual
  relations hold after it.
- **Livingstone on Deep Space 1 (L012).** Mode identification combines
  **commands** with observations. Commanded transitions are part of the
  model, so the diagnoser's expectations change with the commands it knows
  about.
- **ModelPlex (L035).** The model monitor checks each observed transition
  **given the action taken**. Its validity is conditioned on the action by
  construction.
- **FRET and Copilot (L037).** Requirements carry a scope, such as a mode,
  so the monitor's obligation is conditioned on it.
- **Integrated design (L003, L004, L005).** Residual generators are designed
  for the closed loop that will actually run, so a controller change calls
  for a residual redesign. That is an acknowledged integration issue (L004).

### 2.2 In fielded autopilots

**Partly, and ad hoc.** From the files read at V4:

| system | intervention | what the downstream evidence users are told | what is not handled |
|---|---|---|---|
| PX4 estimator selector (L064) | switch of estimator instance | the switch becomes a reset event with a position-jump delta; the selector resets its own relative test ratios | — |
| PX4 local position (L063) | estimator reset | counters and deltas for every reset type are published to all consumers | whether every monitor uses them was not checked beyond L068 |
| PX4 failure detector (L068) | the selector changes the chosen accelerometer | the imbalanced-propeller metric follows the new accelerometer | its low-pass state is **not** reset, so it blends two sensors' statistics for a while |
| PX4 control allocator (L067) | motor removal on a motor-failure flag; restore when the flag clears | allocation and effectiveness are updated | whether the detector's evidence depends on the reconfiguration was not traced |
| ArduPilot EKF3 (L065) | lane switch | yaw and position reset data are updated "to capture changes due to the lane switch"; no second switch within 5 s | — |
| ArduCopter EKF check (L066) | the monitor itself requests a yaw reset, then a lane switch | the failure counter keeps counting on post-intervention evidence | no explicit statement of how the intervention changes the variance evidence |
| ArduCopter vibration check (L066) | vibration-resistant position-controller gains | compensation is removed after 15 s without detection | the clearing test is the **same detector evaluated under the compensated controller**; whether compensation suppresses its inputs is **UNCLEAR** |

## 3. Answer

1. **Feedback masking is KNOWN AND SOLVED** at problem level. The remedy is
   to read the control signal, or a command-driven plant residual, and not
   to exonerate on a regulated channel. This is textbook (L002, L003, L014,
   L020, L021).
2. **Tracking which evidence relations a compensating action invalidates is
   KNOWN in theory.** Examples: mode-dependent ARRs (L017), command-
   conditioned mode estimation (L012), action-conditioned monitors (L035)
   and mode-scoped requirements (L037).
3. **Fielded modular stacks implement it unevenly** (L063-L068). No
   directly matching fielded mechanism was identified in the files read that
   declares, for every monitor, which of its evidence relations each
   intervention invalidates.
4. **That residual is integration engineering.** It is not a research
   problem: represent each intervention as a mode that monitors see, and
   scope each monitor's validity by mode. See `CANDIDATE_PROBLEMS.csv` P01,
   P02 and P07.
