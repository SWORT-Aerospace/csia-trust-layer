# Action-conditioned evidence and the assurance feedback loop (key questions 2 and 3)

Closed-loop evidence gap search, 2026-09-28. Source ids `Lnnn` are defined in
`research/closed_loop_evidence_gap/PROBLEM_LANDSCAPE.md` §2.

## Key question 2: is validity(E_t) conditioned on u_0:t?

The brief contrasts two forms:

- **validity(E_t) depends on u_0:t**, the action history;
- **validity(E_t) depends on time since fault**.

Two identical timestamps after a fault could carry different evidence
meaning, depending on what the controller did.

### What the searched literature already conditions on the action history

| concept | how the input history enters | source | level |
|---|---|---|---|
| model-based residuals | the residual is y minus a prediction driven by the **applied** input, so the input history is inside the residual by construction | L021, L019 | V0 SC |
| input-dependent observability | nonlinear observability depends on the input; singular inputs make a system unobservable, universal inputs do not | L018 | V0 SC |
| persistent excitation and multiplicative faults | detectability of a multiplicative fault depends on how exciting the input is; in closed loop, control signals can cover small faults | L015, L016 | V0 SC |
| mode-sequence ARRs | discriminability depends on the **sequence** of modes visited, not the time | L017 | V0 SC |
| action-conditioned runtime monitors | ModelPlex checks each transition given the action taken | L035 | V0 SC |
| set-based active diagnosis | whether hypotheses separate is computed for a specific input sequence | L007, L008 | V0 SC |
| the dual effect | the action affects the quality of future estimates | L013 | V0 SC |
| command-conditioned mode identification | commands are inputs to the diagnoser (flown on DS1) | L012 | V0 SC |
| fielded validity gating | the AoA validity gate depended on airspeed, which the crew's own pitch inputs changed, so the stall warning stopped when the stall deepened and returned when the nose was lowered | L053 | V0 SC |

### XSYS-001 against this

- **Its window was indexed by time.** T1 = [0, 0.2) s (L069).
- **Its controller was fixed.** Time since onset was therefore a valid proxy
  for "before compensation has settled".
- **The experiment varied neither the controller nor the manoeuvre.** So it
  cannot show that validity depends on the action history rather than on
  time.
- **The general point is standard (L015, L018, L021):** the transient is
  controller-dependent and the residual depends on the input.

### Answer to key question 2

**KNOWN.**

- In model-based diagnosis, observability theory and active diagnosis,
  runtime diagnostic evidence is commonly conditioned on the input history.
- Fixed time-since-onset windows are a simplification that holds for a fixed
  controller.
- Candidate P03 is **KILLED** (`PRIOR_ART_KILL_MATRIX.csv`).

## Key question 3: does any assurance architecture close the loop?

The loop:

1. a monitor flags something;
2. the controller changes behaviour;
3. the monitor accounts for its own effect on future evidence.

### In theory: yes, closed

| framework | how the loop is closed | source |
|---|---|---|
| unified active fault detection and control | the "closed loop information processing strategy" respects the influence of the current decision and input on future behaviour | L006 |
| dual control | the controller values the information its action produces | L013 |
| belief-space planning and shielding | information gathering is a certified component; shields operate on beliefs | L034 |
| safe active diagnosis | actions are chosen for their diagnostic value under safety constraints | L008, L009 |
| performative monitoring (ML, medicine) | monitoring strategies account for model-triggered interventions | L025, L026 |

### In fielded or standard runtime-assurance architectures: not in the searched sources

- **Simplex and runtime-assurance summaries (L032)** describe:
  - switching authority to a backup controller;
  - distribution-shift monitoring.

  They do not describe a monitor that models how the switch changes its own
  later evidence.
- **Safe-RL work corrects the bias** that shield and recovery interventions
  introduce into **learning** data (L033). It does not address monitor
  validity.
- **ArduCopter's EKF failsafe (L066, V4)** does close a loop, crudely:
  1. near the failsafe threshold, the monitor requests a yaw reset;
  2. then it requests a lane switch;
  3. then it continues counting on the post-intervention evidence.

  The intervention is designed to change the evidence, and the monitor then
  judges whether it worked. There is no explicit model of that effect.
- **The same file (L066)** removes vibration compensation after 15 s using
  the same detector evaluated under the compensated controller.

### Answer to key question 3

**Adjacent theory makes the closed loop obvious in principle**, through dual
control, POMDP belief dynamics and unified active detection and control.

- For fielded runtime assurance, no directly matching work was identified in
  the searched sources.
- Applying the known theory there is **known-method application**, with an
  engineering part: declaring the monitor's own interventions as modes (P02).
- It is also crowded at the research frontier (L008, L009, L034).
- Candidate P04 is **OPEN_BUT_CROWDED**, N1.
