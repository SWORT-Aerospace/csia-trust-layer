# G02 deep audit: combined degradation → runtime capability margin

This is the focused kill test of candidate G02, written on 2026-09-28. G02
came from `research/autonomous_assurance_gap_search/TOP_THREE_GAPS.md`
(35/50, N2 LOW).

**Status**

- This is a kill test only. No solution was designed or implemented. No CSIA
  code, simulator work, experiment or threshold was produced.
- Nothing earlier was changed or reinterpreted: XSYS-001, A1, A2, the
  result manifests, the novelty audit, the CSIA-DX, model-inadequacy and
  gap-search packages.
- The FAILURE_LEDGER was not appended.

**The candidate under test.** Several individually tolerable degradations and
demands may combine so that the aircraft no longer has enough physical
capability for its current or planned manoeuvre. Examples are battery power
capability, motor effectiveness, wind and mass. The proposed output was a
conservative runtime margin between capability available and capability
required, before any subsystem crosses its own fault threshold.

## 0. Method, access and scales

- **Access.** This environment reaches only `raw.githubusercontent.com` and
  `pypi.org`.
  - Every other host tried returned 000, 403 or `EGRESS_BLOCKED`. That
    includes arXiv (abs, export, HTML), Semantic Scholar, Crossref,
    OpenAlex, the Internet Archive, NTRS, dashlink, publisher sites, EASA,
    NTSB, gov.uk, USPTO, Google Patents and author homepages. The list is in
    `SEARCH_LOG.md`.
  - So **no P0 paper could be read in full.** Every paper, patent, standard
    and report below is **V0** (a search summary).
  - Each V0 item is marked **REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION**,
    abbreviated **FT**.
- **Above V0.** Only fielded or open code reached a higher level, at V4:
  - ArduPilot and PX4 motor, battery, allocation and estimator files;
  - Paparazzi's electrical module;
  - NASA ProgPy.
- **Verification scale.**

  | level | meaning |
  |---|---|
  | V0 | search result or snippet only |
  | V1 | abstract verified |
  | V2 | substantial primary-source text inspected |
  | V3 | complete relevant primary source inspected |
  | V4 | claim traced to an exact section, page, claim, equation or source line |

- **Status codes.** **SC** means two or more corroborating results. **SS**
  means a single summary.
- **No gap-filling.** Gaps are not filled from abstracts. Where a summary is
  silent, the field reads **NOT STATED (FT)**.
- **Novelty scale.**

  | level | meaning |
  |---|---|
  | N0 | known |
  | N1 | close prior art, mostly integration |
  | N2 | possibly distinct combination |
  | N3 | apparently distinct in searched literature |
  | N4 | strong novelty candidate after full-text adversarial review; **not usable here, because nothing was read at V3** |

- **Wording.** Where nothing was found, this package says "no directly
  matching work was identified in the searched sources".

## 1. Source register

Ids `Knnn` are cited by every file in `research/g02_capability_margin/`.

| id | reference | ids / URL | level |
|---|---|---|---|
| K001 | K. B. Kidambi (University of Dayton), "Battery-aware predictive trajectory planning and control for multirotors under disturbances", arXiv, submitted 10 Sep 2026. Candidate trajectories are evaluated by closed-loop vehicle–motor–battery propagation. Terminal voltage bounds the achievable rotor speed through back-EMF. SOC, terminal voltage, "preferred actuator reserve", utilization and "physical infeasibility" enter as penalty terms. Simulation: a 150-s, 640-m mission with three disturbance regions. Replanning when battery-dependent capability becomes insufficient is listed as **future work** | arXiv 2609.12188 | V0 SC |
| K002 | Multi-robot Systems Group, CTU Prague, "BC-NMPC: battery-constrained NMPC with propulsion prediction and replanning for high-speed flight", arXiv, Jul 2026. The NMPC predicts voltage, current, power and **maximum collective thrust** from the evolving SOC, using polynomial battery IR-circuit and motor–propeller models (30 bench runs, 11.0–16.8 V). It replans in flight on the evolving thrust limit. Outdoor flights reached 23 m/s and 44 m/s² down to about 300 mAh; terminal-voltage MAE 0.20 V; mean solve 5 ms | arXiv 2607.23867 | V0 SC |
| K003 | "Dynamic battery-aware auxiliary reference system for improving real-time MPC implementation in quadrotors", *Systems Science & Control Engineering* 14(1), 2026. Shapes the z-reference to limit voltage sag and over-discharge | doi 10.1080/21642583.2026.2671488 | V0 SS |
| K004 | NASA intelligent contingency management (ICM) and dynamic vehicle assessment (DVA): Gregory et al., DDDAS 2020 / SciTech 2021 (AIAA 2021-1001); the UAM ICM benchmark problem (2023); the GUAM simulation (2025); an ACC 2025 tutorial. Vehicle capability assessment (system ID, adaptive control, envelope prediction, handling qualities), projected forward for mission decisions. Benchmark contingencies include propulsive failures, control-authority degradation and atmospheric disturbances | NTRS 20205006970, 20205011183, 20230017549, 20240015379, 20250005043 | V0 SC |
| K005 | NASA Autonomous Operating System: "Model-based system health management and contingency planning for autonomous UAS" (AIAA 2019-1961): cFS, a diagnostic reasoner, R2U2 health monitoring and prognostics. "Prognostics for autonomous electric-propulsion aircraft" (*IJPHM*): electrochemical battery model with UKF, flight-tested; battery prognostics for contingency planning | doi 10.2514/6.2019-1961; NTRS 20190002780, 20190004923 | V0 SC |
| K006 | L. Tang, G. J. Kacprzynski, K. Goebel et al., "Prognostics-enhanced automated contingency management for advanced autonomous systems" (PHM 2008). Hierarchical: component and system control reconfiguration, then mission replanning, using diagnosis and prognosis; high-fidelity UAV simulation | ieeexplore 4711448 | V0 SC |
| K007 | Risk-aware MDP / POMDP contingency management autonomy for UAS (*J. Aerospace Information Systems*; arXiv 2304.01052). Covers propulsion-unit failure and/or battery degradation; outputs emergency landing, termination or continuation. Also MDP contingency landing management for AAM with a decentralized battery–thruster eVTOL (AIAA 2025-3399), and runtime performance verification of assured contingency landing management (2025) | doi 10.2514/1.I011235; doi 10.2514/6.2025-3399 | V0 SC |
| K008 | NASA ProgPy, read from raw GitHub (`nasa/progpy` master) and PyPI (v1.7.1): `battery_electrochem.py` lines 399–402: EOD = min(charge-based, **voltage-based** term against `VEOD`), so it responds to terminal voltage under load; `aircraft_model/small_rotorcraft.py`: a 6-DOF model with a feedback controller producing thrust and moments to follow waypoints; **no occurrence of `saturat`, `limit`, `clip` or `max_thrust`** in the file; line 337 says the linear model ignores wind rate of change; `dcmotor.py`, `esc.py`, `propeller_load.py`: separate BLDC, ESC and propeller-load models. | github nasa/progpy; sha256 in SEARCH_LOG.md | **V4** (these files) |
| K009 | H. El-Kebir, A. Pirosmanishvili, M. Ornik, "Online guaranteed reachable set approximation for systems with changed dynamics and control authority", *IEEE TAC* 69(2):726–740, 2024. Inner and outer reachable sets come from a nominal precomputed set, shrunk or inflated using **prior knowledge of trajectory-deviation growth**. Examples: ship heading, a lower-triangular system, coupled linear subsystems. Code is said to be on GitHub; the repository was not identified | arXiv 2203.10220; ieeexplore 10122986 | V0 SC |
| K010 | H. El-Kebir, R. Berlin, J. Bentsman, M. Ornik, "Viability under degraded control authority", *IEEE L-CSS*, 2023. Degradation is either affine maps on unknown input subsets or Lipschitz maps. Covers identifiability and real-time identification of the set of viable inputs. Example: a heat equation | doi 10.1109/lcsys.2023.3342059; arXiv 2310.15132 | V0 SC |
| K011 | J.-B. Bouvier, H. Panag, R. Woollands, M. Ornik, "Delayed resilient trajectory tracking after partial loss of control authority over actuators" (*JGCD* 48(3), 2025); resilience of linear systems to partial loss of control authority (*Automatica*, 2023) | arXiv 2303.12877; arXiv 2209.08034 | V0 SC |
| K012 | TU Delft safe-flight-envelope work: Zhang, de Visser, Chu, database-driven online SFE prediction (*JGCD*, 2019); Nabi, Lombaerts et al., structural failure effects on SFE (*JGCD*, 2018); online SFE determination for impaired aircraft (Springer 2015); quadrotor SFE prediction in the high-speed regime, Monte-Carlo (2019) | doi 10.2514/1.G003834; 10.2514/1.G003184 | V0 SC |
| K013 | G.-X. Du, Q. Quan, B. Yang, K.-Y. Cai, available control authority index (ACAI), *JGCD*, 2015 | arXiv 1403.5986 | V0 SC |
| K014 | "A control performance index for multicopters under off-nominal conditions" (Quan's group). The CPI is based on a degree of controllability. "Additional payloads, propulsor degradation, and unacceptable wind disturbances are all lumped as a disturbance", estimated to "tell … whether the multicopter will experience loss of control"; the vehicle lands "if the CPI approaches a value small enough before the vehicle becomes unstable" | arXiv 1705.08775 | V0 SC |
| K015 | "Safety flight control design of a quadrotor UAV with capability analysis", *IEEE Trans. Cybernetics*. Handles actuator faults and external disturbances through "quantization of system capability and safety margin". A degraded trajectory "is gracefully regenerated via the tradeoff between the remaining system capability and the expected derivatives" | doi 10.1109/TCYB.2021.3113168 | V0 SC |
| K016 | M. W. Mueller, M. Hehn, R. D'Andrea, "A computationally efficient motion primitive for quadrocopter trajectory generation" (*IEEE T-RO*, 2015). Sufficient criteria for trajectory feasibility against thrust and body-rate limits. Also the state-to-state feasibility verification of 2013 | flyingmachinearena.ethz.ch mueTRO15.pdf | V0 SC |
| K017 | Battery state-of-power (SOP) estimation: the peak power the battery can deliver over the next interval, as a function of SOC, SOH, temperature and current. Reviews: *JECST* 2024; *J. Energy Storage* 2024. G. Plett, pack power estimation with a dynamic cell model (*IEEE TVT*, 2004) | jecst.org 2024-00724; researchgate 3155265 | V0 SC |
| K018 | Patents: US 12,084,196 "Estimating available power for an aircraft battery"; US 9,989,595 on-line SOP; US 9,321,368 multi-step MPC peak-power estimation | USPTO | V0 SC |
| K019 | "Machine learning-driven prediction of lithium-ion battery power capability for eVTOL aircraft" (arXiv 2510.03497; IEEE 11107862, 2025). A power-limit prediction over long horizons that "accounts for the power needed for potential emergency landings". The summary calls in-flight available-power estimation for eVTOL "a particularly pressing and unresolved issue" | arXiv 2510.03497 | V0 SC |
| K020 | eVTOL landing power capability and dynamic reserves (*Applied Energy* 2024; AIAA 2024-3904); sustained high power at low SOC risks "mid-air electrochemical shutdown" (*Joule* 2023). Cross-reference: gap-search R043, R044 | as listed | V0 SC |
| K021 | "Accurate control under voltage drop for rotor drones" (arXiv 2503.09017; IEEE 11129752, 2025): a voltage-drop observer; real flights | arXiv 2503.09017 | V0 SC |
| K022 | "Topology-aware nullspace control allocation for eVTOL powertrain current protection" (*Aerospace Systems*, 2026): minimizes the maximum motor and battery-pack current in the allocation null space, including under motor or battery failure (simulated lift-plus-cruise). Also null-space allocation for load reduction | doi 10.1007/s42401-026-00499-6; 10.1007/s42401-026-00483-0 | V0 SC |
| K023 | Rotorcraft power margin, fielded concepts: Eurocopter power margin indicator (US 6,195,598; US 6,411,869); first limit indicator (FLI); rotorcraft thrust-margin monitoring (US 11,623,741); "Power safety instrument system", with real-time power required from hover performance data (US 9,035,802; 10,145,708; 9,352,849) | USPTO; Google Patents | V0 SC |
| K024 | Classical rotorcraft performance: hover ceiling where power required equals power available; excess power sets climb; weight, density altitude and wind effects (EASA HE 12 leaflet; CAA NZ "Helicopter performance") | easa.europa.eu HE12; aviation.govt.nz | V0 SC |
| K025 | Multirotor health and performance under wind: SHS-based health performance evaluation (*Nonlinear Dynamics*, 2020); flight performance assessment with an IMM particle filter and "health degree" (*Chinese J. Aeronautics*, 2019) | doi 10.1007/s11071-020-06041-3; S1000936119300184 | V0 SC |
| K026 | H. Kim, D. Lim, K. Yee, "Investigation of operable conditions and excess battery energy for quadrotors under wind turbulence", *JIRS* 104:52, 2022 | doi 10.1007/s10846-021-01494-z | V0 SC |
| K027 | A. Taye, P. Wei, flight mission feasibility assessment of UAM operations under battery energy constraint (AIAA 2024-0532). A. Taye et al., "Safe to fly? Real-time flight mission feasibility assessment for drone package delivery operations", DX'25 | doi 10.2514/6.2024-0532 | V0 SC |
| K028 | "Fault tolerant margins for UAV flight safety", *JIRS*, 2017: the stable range of control-effectiveness σ; margins "extremely sensitive" to aerodynamic parameter perturbations | doi 10.1007/s10846-017-0487-8 | V0 SC |
| K029 | Uncertainty-bounded energy and trajectory planning: CVaR flight-energy risk for multirotors (arXiv 2105.15189); chance-constrained UAV trajectory SOCP (*Aerosp. Sci. Technol.* 2021); rapid uncertainty propagation and chance-constrained planning for sUAS (arXiv 1911.02543); trajectory planning with finite-sample safety guarantees (arXiv 2108.06250) | as listed | V0 SC |
| K030 | Real-time trajectory optimization of impaired aircraft from steady-state manoeuvres (arXiv 2408.02316); NASA safe maneuvering envelope, physical approach (NTRS 20140005797) | as listed | V0 SC |
| K031 | Automotive analogue: a friction-limited motion-control envelope feeding planning ("Architecture for variable motion control envelope", US 11,654,932 / 12,545,283); adaptive trajectory planning at the limits of handling (arXiv 1903.04240) | as listed | V0 SC |
| K032 | Spacecraft analogue: reachability of electric-propulsion spacecraft (*J. Astronaut. Sci.* 2023); resilience to thruster loss (K011) | doi 10.1007/s40295-023-00408-5 | V0 SS |
| K033 | Motion-specific battery health assessment for quadrotors (arXiv 2603.12791); a modular energy-aware multicopter framework (arXiv 2504.03256); energy-aware and safe path planning for UAS (arXiv 2504.03271) | as listed | V0 SS |
| K034 | eVTOL certification: EASA SC-VTOL-01 and MOC SC-VTOL: continued safe flight and landing with performance after a failure "or combination of failures"; the MHQRM as a means of compliance for VTOL.2135; FAA AC 21.17-4, powered-lift type certification (2025); FAA powered-lift SFAR (Nov 2024): 20-minute VFR / 30-minute IFR reserve; Archer M001 airworthiness criteria (Federal Register, 2024). | easa.europa.eu; faa.gov; federalregister.gov | V0 SC |
| K035 | NASA eVTOL white paper: battery "sized to provide sufficient power for boosted hover, boosted climb, and OEI operations" | NTRS 20205000636 | V0 SS |
| K040 | UK AAIB Bulletin 7/2019, DJI Matrice 210 RTK: near free fall after reaching critical battery voltage shortly after the low-voltage warning. The warning had been set **below** the manufacturer's recommendation; a pre-flight voltage check was most likely not done | assets.publishing.service.gov.uk (blocked) | V0 SS |
| K041 | NTSB DCA22FA082, Joby JAS4-2 (Feb 2022): propeller-blade separation during envelope-expansion testing; tilt-actuator linkage contributing. A **component** failure | data.ntsb.gov (blocked) | V0 SC |
| K042 | AIBN, Pipistrel Alpha Electro, Norway (2019): power controller overheated from low coolant; motor failure. A **component** failure | ainonline.com | V0 SC |
| K043 | NTSB DCA17IA202, Aurora PAV: loss of hover lift thrust from a false on-ground rotor-speed reduction caused by vibration | data.ntsb.gov | V0 SC |
| K044 | Helicopter combined-margin accidents and loss-of-control combinations. Cross-reference: gap-search R066, R039 | — | V0 SC |
| K045 | Field reports: ArduPilot forum "Throttle saturation and uncontrolled descent" (discuss.ardupilot.org t/84558); UK AAIB UAS reports noting "power failure a common cause" (unmannedairspace.info) | as listed | V0 SS |
| K050 | ArduPilot `libraries/AP_BattMonitor/AP_BattMonitor_Backend.cpp` (master, sha256 `346d6448…`). Lines 85–133: online **battery internal-resistance estimate** from current and voltage steps. Line 133: resting-voltage estimate | raw GitHub | **V4** |
| K051 | ArduPilot `libraries/AP_Motors/AP_MotorsMulticopter.cpp` (master, sha256 `4f837941…`). What it does: lines 70–88: `MOT_BAT_VOLT_MAX`, `MOT_BAT_VOLT_MIN` and `MOT_BAT_CURR_MAX` parameters; line 275: lift maximum updated from battery voltage; lines 375–430 (`get_current_limit_max_throttle`): maximum current = min(parameter, measured current + (V_batt − V_min)/R_internal), i.e. an **ohmic limit to avoid sagging below the minimum voltage**; mapped to a throttle ceiling that "ensures some minimum authority above hover remains available"; lines 557–562: online **hover-throttle learning**; lines 653–835: thrust boost after a motor loss. | raw GitHub | **V4** |
| K052 | ArduCopter thrust-loss check (1 s of descent at ≥ 90 % throttle). Cross-reference: gap-search R084 | — | V4 |
| K053 | PX4 `src/lib/battery/battery.cpp` (main, sha256 `593f3d93…`). Lines 189–191 and 297–304: **internal-resistance estimate** and open-circuit-voltage estimate. Lines 394–428: time remaining from remaining capacity and current | raw GitHub | **V4** |
| K054 | PX4 `src/modules/mc_hover_thrust_estimator/MulticopterHoverThrustEstimator.cpp` (sha256 `e5ac7c4c…`). Lines 72–91 and 160–192: an EKF **hover-thrust estimate** fused from vertical acceleration and allocated thrust | raw GitHub | **V4** |
| K055 | PX4 `src/modules/control_allocator/ControlAllocator.cpp` (sha256 `4139d45d…`). Lines 657–687: publishes **unallocated torque and thrust** and "setpoint achieved" flags. This reports saturation after the fact | raw GitHub | **V4** |
| K056 | PX4 `src/modules/commander/failure_detector/FailureDetector.cpp` (sha256 `44d1d871…`). Lines 84–96: motor-failure, imbalanced-propeller and battery flags | raw GitHub | **V4** |
| K057 | PX4 wind limit, battery-time versus return-time and flight-time checks. Cross-reference: gap-search R080–R083 | — | V4 |
| K058 | Paparazzi `sw/airborne/modules/energy/electrical.c` (sha256 `c48a4697…`): voltage, current and energy bookkeeping; current estimated from the throttle command when no sensor is fitted (lines 47–49, 79–80). No capability margin identified | raw GitHub | **V4** |
| K060 | SWORT assets. Cross-reference: gap-search R090. The PX4 SIH used by XSYS-001 has no battery, ESC or motor-current physics (CSIA-DX first experiment §2) | local | V4 |

## 2. Subtraction: which pieces of G02 are already known

Each G02 element is taken in turn, and the closest known work is subtracted.
The atomic statuses are in `G02_CLAIM_MATRIX.csv`.

| G02 element | known? | closest | notes |
|---|---|---|---|
| **A.** Online battery **power** capability, P_available(t), not SOC | **N0** | K017, K018, K019; fielded K050, K053 | SOP estimation is a mature BMS function. ArduPilot and PX4 estimate internal resistance online |
| **A2.** Battery state → thrust or rotor-speed **ceiling**, online | **N0** | K002 (flown), K001; fielded K051 | BC-NMPC predicts the collective-thrust ceiling from SOC at 100 Hz. ArduPilot turns an ohmic current limit into a live throttle ceiling |
| **B.** Online propulsor effectiveness / health | **N0** | K013, K014, K021; fielded K056 | loss-of-effectiveness and damage estimation are established |
| **C.** Remaining control authority given degradation | **N0** | K013, K014, K028; K022 for current-limited eVTOL allocation | ACAI and attainable sets; the CPI adds disturbance |
| **D.** Required capability from wind and mass | **N0** | K014 (lumped disturbance), K024 (rotorcraft theory); fielded K054, K051 | hover-thrust estimation and learning are fielded |
| **E.** Composition into one vehicle-level runtime index (payload + propulsor degradation + wind) | **N1** | **K014** | the CPI does exactly this composition, minus the battery |
| **E2.** Composition that **also** includes battery power capability | **N1** | K014 + K002/K001/K051 | every pairwise coupling is published or fielded; no single searched source shows all four at once. This is **integration** |
| **F.** Planned-trajectory demand against capability | **N0** | K001, K002, K016, K015, K030 | candidate or planned trajectories are evaluated against battery-dependent or fault-reduced capability |
| **G.** Conservative (bounded) uncertainty on the composed margin | **N2 (LOW)** | K009, K010, K029 | the techniques exist (reachability given a bound; chance constraints). No searched source applies them to the coupled electro-propulsive-aerodynamic margin |
| **H.** Intervention before saturation | **N0** | K014 (land before instability), K023, K051 | the ArduPilot throttle ceiling keeps authority above hover (fielded) |
| **I.** Embedded runtime implementation | **N0** | K002 (5 ms on hardware), K051 | — |
| **J.** Integration with contingency planning | **N0** | K007, K004, K005, K006, K008 | the MDP contingency autonomy covers propulsion-unit failure and battery degradation |
| **K.** Rotorcraft P_avail − P_req margin at runtime | **N0** | K023, K024 | power-margin indicators and FLI |
| **L.** eVTOL emergency-landing power reservation | **N1** | K019, K020, K035 | battery-side research; a design-time OEI power budget |

## 3. The most important question

> Is there a technically meaningful difference between G02 and
> health-aware / battery-aware trajectory planning + degraded control
> authority + reachability / contingency management?

**Answer: no, not in the searched literature. G02 is essentially "putting
them in one module".**

- **Every coupling is known and often demonstrated.**
  - Battery state to thrust ceiling: K002 (flown), K001, K051 (fielded).
  - Propulsor degradation plus payload plus wind to a runtime
    loss-of-control index: K014.
  - Remaining capability to degraded trajectory regeneration: K015.
  - Candidate trajectories against battery-dependent actuator capability
    under disturbances: K001.
  - Evolving thrust limit to in-flight replanning: K002.
  - Propulsion-unit failure and battery degradation to contingency landing:
    K007.
  - Degraded authority to guaranteed reachable sets, given a bound: K009.
- **The composition adds only integration.** Uniting battery power, propulsor
  degradation, wind and mass in one runtime margin combines these known
  pieces (E2: N1).
- **The one element not found applied to this problem is G.** That is a
  conservative bound on the composed margin. Its tools are known:
  - reachability given deviation-growth bounds (K009);
  - viable-input identification (K010);
  - chance constraints and CVaR (K029);
  - SOP error analysis (K017).

  Applying them to an integrated electro-propulsive model is "reachability
  applied to an integration". That is the case the brief calls
  integration.

**G02 is killed as a research direction.**

## 4. What remains, and in what form

**The narrowest surviving problem** (G02-G, N2 LOW) is a conservative runtime
bound on the gap between two quantities for the next planned trajectory
segment:

- thrust and power capability, given online estimates of battery power
  capability (with temperature and ageing) and propulsor effectiveness, each
  with its own correlated estimation error;
- the thrust and power demand of that segment under estimated wind and mass.

This survives only as "no directly matching work was identified in the
searched sources" at V0. It rests on known techniques, so it fails the
brief's condition 3 ("not simply integration of known health-aware planning,
reachability and control-authority methods").

**The engineering residue is real.**

- The fielded open-source autopilots read at V4 have each piece: resistance
  estimate, sag-limited throttle ceiling, hover-thrust estimate, unallocated
  thrust, motor-failure flags, energy-time return check (K050–K057).
- They do **not** compose these into a **predictive** margin that
  mission-level logic can use for a planned manoeuvre or return route:
  - ArduPilot uses the ceiling inside the motor mixer (K051);
  - PX4 reports unallocated thrust after the fact (K055);
  - PX4 compares return time with battery time in energy terms (K057).
- This conclusion is limited to the files read.
- Exposing a composed margin to mission logic is useful integration
  engineering. It is not research.

## 5. The five RESEARCH_CONTINUE conditions

| # | condition | holds? | basis |
|---|---|---|---|
| 1 | a substantive N2+ gap survives | **marginal** | only G02-G, N2 LOW, and technique-level known |
| 2 | high practical value | **moderate** | fielded autopilots lack a predictive composed margin (V4); electric-rotorcraft incident evidence is indirect (`REAL_WORLD_EVIDENCE.md`); certification computes performance at design time (`EVTOL_CERTIFICATION_RELEVANCE.md`) |
| 3 | not simply integration of known methods | **NO** | §3 |
| 4 | a falsifiable research question | yes, but it tests an integration | `G02_USEFULNESS_MATRIX.csv` and final report item M |
| 5 | SWORT has a plausible test path | **partial** | the SITL used for XSYS-001 lacks battery physics (K060) |

Condition 3 fails, so RESEARCH_CONTINUE is excluded. The residue is useful
engineering: it is the integration and exposure of fielded pieces. That makes
the decision ENGINEERING_ONLY rather than KILL.

## 6. Does CSIA provide a unique advantage?

**No.**

- The margin is physics and performance estimation: battery equivalent
  circuit, motor–propeller maps, vehicle dynamics, reachability.
- CSIA's cross-domain evidence semantics, three-valued predicates and
  certificates add nothing necessary to that computation.
- Describing a performance margin as "CSIA evidence" would be branding, not
  capability.
- If the engineering residue is ever built, it belongs in the flight stack
  (autopilot or mission layer), with CSIA at most consuming its output.

**Decision:** `G02_ENGINEERING_ONLY`
