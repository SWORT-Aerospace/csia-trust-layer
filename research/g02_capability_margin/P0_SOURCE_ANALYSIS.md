# P0 source analysis: the three biggest threats to G02

G02 kill test, 2026-09-28. Source ids `Knnn` are defined in
`research/g02_capability_margin/G02_DEEP_AUDIT.md` §1.

**Access.** No P0 paper was reachable in full text. The attempts are listed
in `SEARCH_LOG.md`, direct access attempts. So:

- every cell below comes from search summaries (**V0**), except NASA ProgPy
  (K008), which was read as source code (**V4**);
- a cell reads **NOT STATED (FT)** when the summaries are silent. FT means
  **REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION**;
- **no field is filled from inference.**

**Additions to the brief's three threats.** The three P0 threats named in the
brief were widened when the search found stronger or closer members of the
same class:

- **Q1** (battery-aware multirotor planning) now also covers **BC-NMPC**
  (K002, flight-tested) and K003.
- **Q2** (NASA and autonomous contingency management) now also covers the
  risk-aware MDP contingency autonomy (K007) and NASA ProgPy (K008).
- **Q3** (reachability / safe envelope under reduced authority) now also
  covers ACAI, the CPI and the capability-analysis controller (K013–K015).

## Q1: battery-aware multirotor planning and control

| field | K001 Kidambi (2026) | K002 BC-NMPC (2026) | K003 battery-aware auxiliary reference (2026) |
|---|---|---|---|
| exact title | "Battery-aware predictive trajectory planning and control for multirotors under disturbances" | "BC-NMPC: battery-constrained NMPC with propulsion prediction and replanning for high-speed flight" | "Dynamic battery-aware auxiliary reference system for improving real-time model predictive control implementation in quadrotors" |
| authors | K. B. Kidambi, Univ. Dayton (the only author named in summaries) | Multi-robot Systems Group, CTU Prague (names NOT STATED, FT) | NOT STATED (FT) |
| year / venue | 2026 / arXiv preprint | 2026 / arXiv preprint | 2026 / *Systems Science & Control Engineering* 14(1) |
| DOI / id | arXiv 2609.12188 | arXiv 2607.23867 | doi 10.1080/21642583.2026.2671488 |
| problem formulation | candidate trajectories evaluated by closed-loop vehicle–motor–battery propagation under spatially localized disturbances | battery and propulsion models inside an NMPC to predict voltage, current, power and maximum collective thrust; replanning on the evolving thrust limit | a z-reference shaped from position error and desired voltage sag, to protect against over-discharge |
| state variables | SOC, terminal voltage, polarization named; full vector NOT STATED (FT) | NOT STATED (FT) | NOT STATED (FT) |
| degradation variables | battery depletion (SOC, voltage); actuator degradation **UNCLEAR** (FT) | battery depletion (OCV and internal resistance as polynomials of SOC); propulsor degradation **NOT STATED** (FT) | battery voltage sag |
| environmental variables | spatially localized disturbance regions | NOT STATED (FT) | NOT STATED (FT) |
| physical model | reduced-order battery model benchmarked against a Simscape equivalent circuit (power NRMSE 0.64 %); back-EMF couples maximum rotor speed to terminal voltage | polynomial motor–propeller maps (thrust, power, resistance against throttle, voltage, RPM; 30 bench runs 11.0–16.8 V); 4S LiPo IR model | NOT STATED (FT) |
| battery **power** capability or only SOC | **power-limited capability**: terminal-voltage-dependent actuator capability | **power**: terminal voltage, current, power and thrust ceiling predicted | voltage sag |
| actuator degradation modelled | UNCLEAR (FT) | NOT STATED (FT) | NOT STATED (FT) |
| wind modelled | disturbance regions (type NOT STATED, FT) | NOT STATED (FT) | NOT STATED (FT) |
| control authority modelled | "available actuator authority"; "preferred actuator reserve" penalty | collective-thrust ceiling (moment authority NOT STATED, FT) | NOT STATED (FT) |
| multiple degradations interact | battery × disturbance demand × actuator capability: yes | battery × propulsion map: yes; others NOT STATED | NOT STATED (FT) |
| current capability estimated online | NOT STATED (FT) | **yes**: 100 Hz inside the NMPC | NOT STATED (FT) |
| future / planned demand evaluated | **yes**: candidate trajectories | **yes**: NMPC horizon plus replanning | NOT STATED (FT) |
| output: binary or margin | penalty terms in the optimization (reserve, infeasibility); no margin output stated | thrust-ceiling constraint; no margin output stated | reference shaping |
| uncertainty bounded | NOT STATED (FT) | NOT STATED (FT) | NOT STATED (FT) |
| acts before saturation | via the reserve penalty (FT) | via the predicted ceiling and replanning | smoothing thrust before sag |
| replans | selects among candidates; replanning when capability becomes insufficient is **future work** | **yes**, in flight | NOT STATED (FT) |
| runs online | NOT STATED (FT) | **yes** | real-time MPC (FT) |
| computational cost | NOT STATED (FT) | mean solve **5 ms** | NOT STATED (FT) |
| experimental platform | simulation: 150-s, 640-m mission, three disturbance regions | outdoor multirotor flights up to 23 m/s and 44 m/s², down to about 300 mAh | NOT STATED (FT) |
| hardware validation | **none stated** (summaries describe simulation) | **yes** (terminal-voltage MAE 0.20 V) | NOT STATED (FT) |
| what G02 would add | propulsor degradation, if absent (FT); a conservative bound; an assurance-style margin output | propulsor degradation and wind (FT); a conservative bound; a margin output to mission logic | — |

**Q1 verdict.** Battery power capability → thrust ceiling → planned-trajectory
feasibility and replanning is **known and flown** (K002). Candidate-trajectory
evaluation under disturbance with voltage-dependent capability is known in
simulation (K001).

## Q2: NASA and autonomous contingency management

| field | K004 NASA ICM / DVA | K005 NASA AOS / battery prognostics | K006 ACM+P (2008) | K007 risk-aware MDP contingency autonomy | K008 NASA ProgPy (**V4 code**) |
|---|---|---|---|---|---|
| exact title | "Intelligent contingency management for urban air mobility"; "Dynamic vehicle assessment for intelligent contingency management of UAM vehicles"; the UAM benchmark problem | "Model-based system health management and contingency planning for autonomous UAS"; "Prognostics for autonomous electric-propulsion aircraft" | "Prognostics-enhanced automated contingency management for advanced autonomous systems" | "Risk-aware Markov decision process contingency management autonomy for uncrewed aircraft systems"; AAM contingency landing (2025) | NASA Prognostics Python Package (ProgPy) |
| authors | Gregory et al. (NASA) | NASA Ames (Schumann et al.) (FT for the full list) | L. Tang, G. Kacprzynski, K. Goebel et al. | Z. Laouar et al. (FT) | NASA |
| year / venue | 2020–2025 / DDDAS, SciTech, NTRS | 2019 / AIAA SciTech; *IJPHM* | 2008 / PHM conference | JAIS; AIAA Aviation 2025 | v1.7.1 (PyPI) |
| DOI / id | AIAA 2021-1001; NTRS 20230017549 | doi 10.2514/6.2019-1961 | ieeexplore 4711448 | doi 10.2514/1.I011235; arXiv 2304.01052 | github nasa/progpy |
| problem formulation | assess vehicle capability, project it forward, decide on the mission | health monitoring, diagnosis and battery prognostics for contingency planning on cFS | diagnosis plus prognosis driving reconfiguration and replanning | MDP policy: land, terminate or continue under propulsion failure or battery degradation | prognostic models and prediction of events (e.g. end of discharge) along a future loading or trajectory |
| state variables | 6-DOF DEP vehicle (FT) | battery electrochemical states (UKF) | FT | discrete MDP states (FT) | battery electrochemical states; 6-DOF rotorcraft states (14) |
| degradation variables | propulsive failures; control-authority degradation | battery | actuator degradation (via reconfiguration) | propulsion-unit failure; battery degradation | battery (EOD); separate motor, ESC and propeller components |
| environmental variables | atmospheric disturbances | FT | FT | FT | wind rate of change ignored in the linear model (line 337) |
| physical model | variable-fidelity eVTOL aero, propulsion and actuator models | electrochemical Li-ion | high-fidelity UAV simulation | high-fidelity simulator (FT) | electrochemical battery; BLDC motor (back-EMF); ESC; propeller load; 6-DOF rotorcraft with feedback control |
| battery **power** capability or only SOC | NOT STATED (FT) | SOC and remaining capacity; "remaining battery power … not directly measurable" | FT | "low energy situations" (energy) | **voltage-aware energy endpoint**: EOD = min(charge term, voltage term against VEOD), lines 399–402 |
| actuator degradation modelled | **yes** | FT | **yes** | propulsion-unit failure: yes | motor, ESC and propeller models exist; no degradation parameters seen in the lines read |
| wind modelled | **yes** (atmospheric disturbances) | FT | FT | FT | not in the linear model |
| control authority modelled | **yes** (control-authority degradation) | FT | FT | FT | **no saturation or limit found** in `small_rotorcraft.py` |
| multiple degradations interact | FT | FT | FT | propulsion failure **and/or** battery degradation, as discrete states | composable in principle (FT for the composite-model class) |
| current capability estimated online | yes (DVA) | yes (battery) | yes | policy online | library; online use depends on the integrator |
| future / planned demand evaluated | **yes** ("project these into the future") | yes (battery prognostics) | yes (long-term plan) | yes (continue versus land) | **yes**: predict EOD along a trajectory |
| output: binary or margin | capability assessment (form FT) | remaining capacity / time | reconfiguration and plan | discrete action | event time (EOD) |
| uncertainty bounded | FT | UKF (probabilistic) | FT | risk-aware; partial observability studied | uncertainty propagation is a stated ProgPy feature (README) |
| acts before saturation | FT | yes (energy) | yes | yes | n/a (library) |
| replans | yes (mission level) | contingency planning | **yes** | yes (land, terminate, continue) | n/a |
| runs online | FT | yes | FT | yes (policy lookup) | n/a |
| computational cost | FT | FT | FT | FT | n/a |
| experimental platform | GUAM simulation | electric UAV flight tests (battery prognostics) | high-fidelity UAV simulation | high-fidelity simulator | software |
| hardware validation | FT | **yes** (battery prognostics) | FT | FT | n/a |
| what G02 would add | FT whether battery **power** capability enters the capability assessment; a conservative margin | power (not energy) capability and authority composition | electric power capability | continuous capability margin in place of discrete failure states | a thrust/authority ceiling in the rotorcraft model |

**Q2 verdict.**

- Contingency management with degraded capability already exists: capability
  assessment and forward projection (K004); battery and propulsion-failure
  contingency policies (K007); hierarchical reconfiguration and replanning
  (K006).
- These are known. What G02 could add at this layer is a continuous,
  power-and-authority-based capability input in place of discrete failure
  states. That is an **input-quality improvement**, i.e. integration.

## Q3: reachability, safe envelope and authority under degradation

| field | K009 online reachable sets (TAC 2024) | K010 viability (L-CSS 2023) | K012 TU Delft SFE | K013 ACAI (2015) | K014 CPI | K015 capability-analysis safety control (TCYB) |
|---|---|---|---|---|---|---|
| authors | El-Kebir, Pirosmanishvili, Ornik | El-Kebir, Berlin, Bentsman, Ornik | Zhang, de Visser, Chu; Nabi, Lombaerts et al. | Du, Quan, Yang, Cai | Quan's group (FT for the full list) | FT |
| year / venue | 2024 / *IEEE TAC* 69(2) | 2023 / *IEEE L-CSS* | 2015–2019 / *JGCD* and others | 2015 / *JGCD* | arXiv 1705.08775 (venue FT) | *IEEE Trans. Cybernetics* |
| DOI / id | arXiv 2203.10220 | doi 10.1109/lcsys.2023.3342059 | doi 10.2514/1.G003834 | arXiv 1403.5986 | arXiv 1705.08775 | doi 10.1109/TCYB.2021.3113168 |
| problem formulation | inner and outer forward reachable sets after changed dynamics and diminished control authority | identify control-authority degradation; the viable input set | the safe flight envelope of impaired aircraft (reachability; database) | controllability and available authority after rotor degradation or failure | a control performance index predicting LOC under off-nominal conditions | safety control with capability and margin quantization; degraded trajectory regeneration |
| degradation variables | changed dynamics; diminished authority | affine or Lipschitz input degradation | structural damage; control-surface failure | rotor efficiency or failure | **payload + propulsor degradation + wind**, lumped as disturbance | actuator faults; disturbances |
| environmental variables | FT | none | FT | none | **wind** | disturbances |
| battery power capability | **no** | no | no | no | **not stated** | not stated |
| control authority modelled | **yes** | **yes** | yes (envelope) | **yes** | **yes** (degree of controllability) | **yes** ("remaining system capability") |
| multiple degradations interact | via the deviation-growth bound | FT | FT | rotor combinations | **yes** (lumped) | faults × disturbances |
| current capability online | **yes** (efficient approximation) | **yes** (real-time identification) | yes (database interpolation) | FT (index computation) | **yes** (disturbance estimation) | yes |
| future demand evaluated | reachable sets over a horizon | viability | envelope for planning | no | no (current index) | **yes** (trajectory regeneration) |
| output: binary or margin | sets | a set of viable inputs | an envelope | **quantitative index** | **quantitative index**; land when small | a safety margin; regenerated trajectory |
| uncertainty bounded | **guaranteed inner and outer**, *given* prior deviation-growth knowledge | identifiability conditions | probabilistic variants (FT) | deterministic | FT | FT |
| acts before saturation | n/a | n/a | yes (protection) | n/a | **yes** (land before instability) | yes |
| platform | ship heading; lower-triangular; coupled linear | heat equation (surgery) | transport-aircraft simulation | hexacopter analysis | multicopter (FT for hardware) | quadrotor (FT for hardware) |
| hardware validation | no (examples) | no | FT | FT | FT | FT |
| what G02 would add | the electro-propulsive source of the deviation bound | the aircraft and battery setting | rotorcraft and battery power | battery power; wind demand | **battery power capability**; a planned-trajectory margin | battery power capability (FT) |

**Q3 verdict.**

- Degraded-authority reachability and viability with guarantees exist, given
  bounds (K009, K010).
- A runtime index that composes payload, propulsor degradation and wind to
  predict loss of control exists (K014).
- Capability-based degraded trajectory regeneration under faults and
  disturbances exists (K015).
- G02's only addition here is to include battery **power** capability in the
  composition and to bound the result conservatively.

## P0 conclusion

**All three threats hold.** Each G02 element maps to a known source. The
composition is covered pairwise, and in K014 three-way. What is not found in
any single searched source is the four-way composition, including battery
power capability, with conservative bounds against planned demand. That is
the integration residue discussed in `G02_DEEP_AUDIT.md` §§3–4.
