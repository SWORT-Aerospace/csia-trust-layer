# G02 kill-test search log

Searches run on 2026-09-28. Source ids `Knnn` are defined in
`research/g02_capability_margin/G02_DEEP_AUDIT.md` §1.

**The tool.** A web-search tool that returns titles, URLs and summaries.
Queries are recorded **verbatim**.

**Aim.** The aim was to **kill** G02:

- to find the strongest existing work for each G02 element;
- to find the exact intersection terms listed in the brief;
- to find fielded behaviour and real-world evidence.

| # | exact query | kept | what it showed |
|---|---|---|---|
| KQ1 | `"Battery-Aware Predictive Trajectory Planning and Control for Multirotors Under Disturbances" authors` | K001 | author and affiliation (Univ. Dayton), arXiv 2609.12188 |
| KQ2 | `battery-aware predictive trajectory planning multirotor terminal voltage polarization SOC wind disturbance motor saturation arXiv 2609.12188 github code` | K001, K002 | Kidambi details; BC-NMPC found (arXiv 2607.23867) |
| KQ3 | `Kidambi battery-aware multirotor terminal-voltage-dependent actuator capability closed-loop vehicle-motor-battery propagation candidate trajectories actuator degradation` | K001 | back-EMF couples maximum rotor speed to terminal voltage; battery terms nonbinding at nominal SOC |
| KQ4 | `BC-NMPC battery-constrained NMPC propulsion prediction replanning high-speed flight arXiv 2607.23867 voltage sag thrust limit` | K002 | NMPC predicts voltage, current, power and thrust ceiling; in-flight replanning (CTU MRS) |
| KQ5 | `Dynamic battery-aware auxiliary reference system model predictive control quadrotors 2026 Systems Science Control Engineering voltage drop thrust` | K003 | battery-aware auxiliary reference for MPC (2026) |
| KQ6 | `ctu-mrs github battery constrained NMPC thrust ceiling state of charge multirotor drone racing code repository` | none | no BC-NMPC repository identified in the ctu-mrs organization |
| KQ7 | `BC-NMPC CTU Prague multi-robot systems battery IR circuit polynomial motor-propeller collective thrust ceiling hardware experiments results replanning` | K002 | bench characterization (30 runs); outdoor flights 23 m/s; 5 ms solve; MAE 0.20 V |
| KQ8 | `NASA "Model-based System Health Management and Contingency Planning" autonomous UAS Schumann battery motor temperature prognostics contingency` | K005 | NASA AOS: SHM and contingency planning on cFS; battery prognostics |
| KQ9 | `prognostics-enhanced automated contingency management advanced autonomous systems Tang Kacprzynski Goebel UAV reconfiguration mission replanning actuator degradation` | K006 | ACM+P hierarchical reconfiguration and replanning |
| KQ10 | `Intelligent contingency management urban air mobility Gregory dynamic vehicle assessment flight envelope estimation machine learning vehicle capability propulsion failure eVTOL results` | K004 | ICM / DVA; benchmark contingencies include propulsive failure, authority degradation, disturbances |
| KQ11 | `El-Kebir Ornik github code reachable set changed dynamics control authority implementation aircraft example` | K009 | TAC 2024 online reachable sets; code on GitHub (repository not identified) |
| KQ12 | `battery state of power estimation SOP available power prediction online BMS peak power capability electric vehicle aircraft eVTOL` | K017, K018, K019 | SOP estimation mature; aircraft-battery available-power patent; eVTOL power capability |
| KQ13 | `helicopter power margin indicator first limit indicator power available versus power required onboard computation hover capability prediction display` | K023 | helicopter power margin indicator (Eurocopter); FLI; power margin = P_avail - P_req |
| KQ14 | `power-constrained control allocation multirotor battery current limit voltage available thrust attainable set eVTOL distributed electric propulsion` | K022, K001, K002 | current-limited eVTOL allocation; battery-aware multirotor planning and NMPC |
| KQ15 | `quadrocopter trajectory feasibility check thrust and angular rate limits computationally efficient motion primitive Mueller Hehn D'Andrea input feasibility` | K016 | thrust and body-rate feasibility of quadrocopter motion primitives |
| KQ16 | `eVTOL one propulsor inoperative hover power margin battery power limit emergency power rating continued safe flight analysis distributed electric propulsion failure` | K035 | eVTOL battery sized for boosted hover, climb and OEI |
| KQ17 | `fault-tolerant MPC multirotor rotor degradation battery voltage constraint trajectory replanning actuator loss of effectiveness combined` | K001 | fault-tolerant MPC family; Kidambi reserve penalty and future-work replanning |
| KQ18 | `Kidambi battery-aware multirotor preferred actuator reserve utilization penalty feasibility-aware replanning future work simulation only hardware` | K001 | penalty terms; simulation-based evaluation |
| KQ19 | `Machine Learning-Driven Prediction of Lithium-Ion Battery Power Capability for eVTOL Aircraft arXiv 2510.03497 landing power demand in flight` | K019 | eVTOL power-limit prediction including emergency-landing power (2025) |
| KQ20 | `Topology-aware nullspace control allocation eVTOL powertrain current protection rotor failure battery pack current thermal Aerospace Systems 2026` | K022 | topology-aware null-space allocation minimizing motor and battery current |
| KQ21 | `multirotor safe flight envelope estimation rotor failure reachable set hexacopter octocopter degraded thrust wind online envelope` | K012 | quadrotor SFE (Monte-Carlo); hexacopter controllability; octorotor envelope verification |
| KQ22 | `return to home feasibility battery voltage sag wind estimate drone energy reachability online reachable landing sites battery model uncertainty` | none registered | RTH guidance and industry blogs; an energy-constrained delivery paper |
| KQ23 | `"capability margin" OR "control authority margin" OR "maneuver margin" UAV runtime degraded vehicle autonomy decision propulsion battery` | K028, K015 | fault-tolerant margins (sigma range); capability-aware control |
| KQ24 | `quadrotor safety control actuator faults external disturbances quantization of system capability safety margin degraded trajectory regeneration IEEE Transactions on Cybernetics 2021` | K015 | TCYB capability analysis: quantized capability and safety margin; degraded trajectory |
| KQ25 | `"Safe to Fly" real-time flight mission feasibility assessment UAV battery DX 2025 George Washington University` | K027 | Safe to fly? real-time mission feasibility (DX'25) |
| KQ26 | `Fault tolerant margins for unmanned aerial vehicle flight safety Journal of Intelligent Robotic Systems 2017 control effectiveness sigma stability range` | K028 | FTM definition and sensitivity |
| KQ27 | `multicopter available control authority wind disturbance battery voltage combined health degree assessment decision-making Quan Quan flight safety` | K014, K025 | CPI; health evaluation under wind turbulence |
| KQ28 | `"A Control Performance Index for Multicopters Under Off-nominal Conditions" payload propulsor degradation wind index definition available control authority` | K014 | CPI lumps payload, propulsor degradation and wind as disturbance; land before LOC |
| KQ29 | `"Investigation of Operable Conditions and Excess Battery Energy for Quadrotors Under Wind Turbulence" operable region battery energy wind` | K026 | operable conditions and excess battery energy under wind turbulence |
| KQ30 | `"Accurate Control under Voltage Drop for Rotor Drones" arXiv 2503.09017 voltage drop thrust compensation` | K021 | voltage-drop observer; real flights |
| KQ31 | `"Flight Mission Feasibility Assessment of Urban Air Mobility Operations under Battery Energy Constraint" power feasibility battery model eVTOL` | K027 | UAM mission feasibility under battery energy constraint |
| KQ32 | `FAA powered-lift special federal aviation regulation performance requirements continued safe flight and landing definition critical change of thrust eVTOL 2024 AC 21.17-4` | K034 | FAA AC 21.17-4 powered-lift; CSFL comments |
| KQ33 | `EASA MOC SC-VTOL performance VTOL.2105 VTOL.2115 takeoff performance battery state of charge temperature power available conservative determination` | K034 | MOC SC-VTOL VTOL.2105 / VTOL.2115 sections exist; battery MOCs |
| KQ34 | `eVTOL battery energy reserve FAA rule powered-lift reserve requirements 20 minutes battery power at end of reserve landing power capability` | K034 | powered-lift SFAR reserves 20 min VFR / 30 min IFR |
| KQ35 | `Joby NTSB report accident February 2022 unmanned demonstrator propeller blade failure flight test envelope findings` | K041 | Joby JAS4-2: blade separation; component failure |
| KQ36 | `drone accident report cold temperature battery voltage drop loss of power multirotor crash investigation AAIB UAS report low temperature lithium polymer` | none registered | cold-weather voltage-sag guidance (industry); no report |
| KQ37 | `electric aircraft accident report battery power limitation motor power reduction climb insufficient Pipistrel Alpha Electro AIBN findings` | K042 | Alpha Electro Norway: power-controller overheat (component) |
| KQ38 | `AAIB UAS accident report multirotor descended despite full throttle high wind battery voltage low insufficient thrust loss of control report findings` | K040, K045 | AAIB Matrice 210 RTK; ArduPilot forum saturation thread |
| KQ39 | `delivery drone crash investigation insufficient power headwind heavy payload battery low temperature Wing Zipline Matternet Manna incident report` | none | no delivery-drone report attributed to combined performance limitation |
| KQ40 | `NTSB unmanned aircraft accident multirotor "loss of lift" OR "insufficient thrust" battery wind heavy payload final report` | K043 | Aurora PAV false rotor-speed reduction |
| KQ41 | `SC-VTOL controllability control margin lift thrust unit failure VTOL.2135 sufficient control power remaining after failure MOC` | K034 | MHQRM for VTOL.2135 controllability |
| KQ42 | `helicopter onboard performance computation real-time hover out of ground effect capability prediction landing site power required prediction avionics` | K023, K024 | power safety instrument patents; hover ceiling where P_req = P_avail |
| KQ43 | `Risk-aware Markov decision process contingency management autonomy uncrewed aircraft systems Journal of Aerospace Information Systems battery motor degradation` | K007 | risk-aware MDP contingency autonomy (propulsion failure, battery degradation) |
| KQ44 | `"Viability under degraded control authority" assumptions known admissible input set after failure unknown dynamics bounds example` | K010 | viability: degradation modes, viable inputs, heat-equation example |
| KQ45 | `chance-constrained energy-aware trajectory planning UAV battery uncertainty conservative guarantee return feasibility probabilistic reachability battery model` | K029 | chance-constrained and uncertainty-aware energy planning |
| KQ46 | `"Prognostics for Autonomous Electric-Propulsion Aircraft" battery motor prognostics trajectory prediction decision UAV IJPHM` | K005 | prognostics for autonomous electric-propulsion aircraft; flight tests |
| KQ47 | `remaining maneuverability dynamic flight envelope actuator saturation margin multirotor online estimation attainable force set degraded propulsion guidance` | K030 | impaired-aircraft trajectory optimization; safe maneuvering envelope |
| KQ48 | `automated driving friction-limited capability envelope online tire road friction estimation motion planning feasibility margin degraded actuator` | K031 | friction-limited motion-control envelope feeding planning (automotive) |
| KQ49 | `spacecraft thruster degradation onboard reachable set remaining control authority autonomous maneuver planning after thruster failure` | K032, K011 | EP spacecraft reachability; resilience to thruster loss |

## Direct access attempts

| target | method | result |
|---|---|---|
| arXiv abs / export API / HTML (2609.12188, 2607.23867) | curl; web fetch | 000; `EGRESS_BLOCKED` |
| Semantic Scholar (API and web), Crossref, OpenAlex, dblp, CORE, Europe PMC, Internet Archive, scholar.archive.org, alphaXiv, r.jina.ai, Hugging Face papers | curl; web fetch | 000; `EGRESS_BLOCKED` |
| NTRS, NASA dashlink (c3.ndc.nasa.gov) | curl; web fetch | 000; `EGRESS_BLOCKED` |
| mornik.web.illinois.edu (K009 PDF), pith.science, lacuna | web fetch | `EGRESS_BLOCKED` |
| tandfonline, Springer, PMC, EASA, NTSB data, gov.uk AAIB, Google Patents, USPTO | curl | 000 |
| github.com / api.github.com | curl | 400 / 403 |
| `raw.githubusercontent.com/ctu-mrs/bc_nmpc` / `bc-nmpc` (main, master) | curl | 404 (no public repository found) |
| **pypi.org** `progpy` JSON | curl | 200: v1.7.1, NASA ProgPy summary |

## Source code read (raw GitHub, V4)

| file | sha256 | registered as |
|---|---|---|
| nasa/progpy `README.md` | `6480b403d88cedb3a341b97f3d82e46758bb94cd63784a05de1d724fdc4eb0ea` | K008 |
| nasa/progpy `src/progpy/models/battery_electrochem.py` | `88dbd5c0a48dce131501115e7945d97e0fead6cce50a4e94967eba83c9987d35` | K008 |
| nasa/progpy `src/progpy/models/aircraft_model/small_rotorcraft.py` | `85df6b1e8e11072b5f7cc2dffc8d6d6d0f4e707484e3955da05cf1977388a73c` | K008 |
| nasa/progpy `src/progpy/models/dcmotor.py` | `8e478420a55ef12e42669426e22817b1e0581bc6a3339d3efd1e93ddc899dcea` | K008 |
| nasa/progpy `src/progpy/models/esc.py` | `c10ee94539acead8cd719be979da9e5fdc0016deb68e610caaa4f6b45842334b` | K008 |
| nasa/progpy `src/progpy/models/propeller_load.py` | `390b9ba71da681971230c70c115487d16ec420a8786e14dde5a47072abb71f1a` | K008 |
| nasa/progpy `src/progpy/models/battery_circuit.py` | `68678aae79cb9d1dba94ed29432b94902492ed7c1130069e2b315d8d0a927ad4` | (read, not cited) |
| ArduPilot `libraries/AP_BattMonitor/AP_BattMonitor_Backend.cpp` | `346d6448608386196d2376506c6830ea907c028c2d82d51de10165c10ad184ab` | K050 |
| ArduPilot `libraries/AP_Motors/AP_MotorsMulticopter.cpp` | `4f837941b6f00ea5b42c6f8efbb57ef8011c69a5a9a1ebb2720ca0aea5c4a342` | K051 |
| PX4 `src/lib/battery/battery.cpp` | `593f3d93c3bc9d97cb31c66a7f7f8016fbb15b712b5ee7aefa55ec7ef714ba76` | K053 |
| PX4 `src/modules/mc_hover_thrust_estimator/MulticopterHoverThrustEstimator.cpp` | `e5ac7c4c6cfd7691af4ff007d30b21019c9a462f81a0d194eb5a4035afa1d775` | K054 |
| PX4 `src/modules/control_allocator/ControlAllocator.cpp` | `4139d45d21efce50ab08b2d16e8d44b403333cae9f92134b254d8993a75e2430` | K055 |
| PX4 `src/modules/commander/failure_detector/FailureDetector.cpp` | `44d1d8718a3af1c3b427ba112b3770de943c3c65891005a32778038bc71091d5` | K056 |
| Paparazzi `sw/airborne/modules/energy/electrical.c` | `c48a4697f62d3dc8950b2199e034b6c8ff61cd96b3f546cd2207a68b75163ddb` | K058 |
| ArduPilot `libraries/AP_Motors/AP_MotorsMatrix.cpp`; `libraries/AC_AttitudeControl/AC_AttitudeControl_Multi.cpp` | (fetched, not analysed) | not cited |

## What was not searched well

- **Full text of every paper, standard and report.** Blocked.
- **OEM practice.** Proprietary eVTOL and delivery-drone flight-control
  practice (Joby, Archer, Wing, Zipline, Amazon) is unobservable.
- **Betaflight.** Not inspected: racing firmware; relevance judged low.
- **The ArduPilot and PX4 SITL battery models.** Not inspected.
