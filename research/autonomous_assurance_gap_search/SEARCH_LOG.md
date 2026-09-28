# Gap-analysis search log

Searches run on 2026-09-28 for the autonomous-aerospace assurance gap
analysis. Source ids `Rnnn` are defined in
`research/autonomous_assurance_gap_search/GAP_LANDSCAPE.md` §1.

**The tool.** A web-search tool that returns titles, URLs and a summary. No
paper, standard or report full text was reachable. Fielded code was read from
`raw.githubusercontent.com` (below).

**Scope.** The XSYS-001 record was not opened. The earlier packages were
consulted only for cross-references.

**Method.** The candidate problems were generated **before** any CSIA fit was
considered. Every query aimed either:

- to find evidence that a problem is real (incidents, certification text,
  fielded code); or
- to **kill** a candidate by finding the strongest existing solution.

Queries are recorded **verbatim**.

| # | exact query | kept | what it showed |
|---|---|---|---|
| GQ1 | `ASTM F3269 run time assurance unmanned aircraft standard practice safety monitor recovery control function assumptions` | R001 | RTA standard: safety monitor against predefined limits; recovery control function |
| GQ2 | `L1Simplex fault-tolerant simplex architecture recoverable region actuator faults degraded dynamics Wang Hovakimyan Sha` | R002 | L1Simplex: original Simplex unsuitable when physical failures change dynamics |
| GQ3 | `runtime assurance limitations backup controller model assumptions invalid after actuator failure recovery region online update` | R004, R008 | conformal recovery-deadline certificates; mission-level RTA fallback not always capable |
| GQ4 | `Auto-GCAS runtime assurance F-16 trajectory prediction aircraft performance model degraded configuration limitations` | R006 | F-16 Auto-GCAS fielded 2014; trajectory prediction depends on aircraft performance |
| GQ5 | `backup control barrier functions Gurriet Ames online safe set forward integration backup controller real-time safety` | R005 | backup CBF invariant set evaluated online by forward integration under a backup policy |
| GQ6 | `ConSerts conditional safety certificates runtime evaluation evidence guarantees demands Schneider Trapp` | R010 | ConSerts: guarantees tied to runtime-resolved demands |
| GQ7 | `dynamic assurance cases Asaadi Denney Pai assurance measure runtime confidence autonomous aircraft taxiing` | R012 | dynamic assurance cases; autonomous taxiing UAS |
| GQ8 | `ENTRUST engineering trustworthy self-adaptive software runtime assurance cases Calinescu Weyns` | R013 | ENTRUST: runtime evidence updates dynamic assurance-case elements |
| GQ9 | `ReSonAte runtime risk assessment framework autonomous systems bow-tie assurance case Hartsell Karsai` | R014 | ReSonAte: bow-tie plus monitors estimate hazard rates at runtime |
| GQ10 | `UL 4600 safety performance indicators monitor validity of safety case assumptions field data Koopman` | R015, R018 | UL 4600 SPIs on safety-case and assumption validity; runtime confidence updates |
| GQ11 | `Ruchkin confidence composition monitors verification assumptions ICCPS learning-enabled autonomous systems dynamic assurance` | R020 | CoCo: calibrated confidence monitors of verification assumptions, composed |
| GQ12 | `Denney Pai Habli dynamic safety cases through-life safety assurance 2015 ICSE runtime update safety case` | R011, R016 | dynamic safety cases (ICSE 2015); safety measurement reconciled with dynamic assurance |
| GQ13 | `online safe flight envelope estimation damaged aircraft reachability Lombaerts van Kampen Chu database approach real-time` | R032 | safe flight envelope estimation for impaired aircraft (reachability, databases) |
| GQ14 | `available control authority index multirotor rotor degradation controllability Du Quan Cai` | R033 | ACAI for rotor degradation and failure |
| GQ15 | `prognostics-based decision making UAV battery remaining flying time mission replanning NASA Edge 540 Bole Saha Goebel` | R040 | remaining flying time prediction for electric UAVs; mission replanning |
| GQ16 | `Belcastro loss of control accident analysis combinations adverse onboard conditions external hazards vehicle upsets multiple causal factors` | R039 | LOC: factors act alone or more often in combination |
| GQ17 | `health-aware model predictive control UAV component degradation mission reconfiguration remaining useful life constraint` | R041 | health-aware control and MPC; health-aware MDP planning |
| GQ18 | `emergency landing planner damaged aircraft reachable landing sites flight envelope after damage Meuleau Atkins adaptive flight planning` | R038, R046 | emergency landing planner; energy-constrained multicopter emergency planning |
| GQ19 | `helicopter accidents insufficient power margin density altitude weight wind hover out of ground effect each factor within limits combined` | R066 | helicopter hover accidents from combined density altitude, weight and wind |
| GQ20 | `multirotor thrust margin battery voltage sag cold temperature wind motor saturation loss of control drone accident investigation report` | none registered | industry guidance on sag, cold and wind headroom; no accident report found |
| GQ21 | `eVTOL continued safe flight and landing SC-VTOL power margin failure combinations remaining capability assessment certification` | R053 | SC-VTOL continued safe flight and landing after failure combinations |
| GQ22 | `minimum equipment list multiple inoperative items combination not analyzed risk dispatch FAA concern` | R054 | MEL: no flight with multiple unrelated deferred items that create a hazard |
| GQ23 | `NASA intelligent contingency management urban air mobility vehicle capability assessment flight envelope degraded dynamic vehicle assessment` | R036 | NASA ICM and dynamic vehicle assessment for UAM |
| GQ24 | `multicopter flight envelope estimation battery power limit wind disturbance motor degradation combined remaining thrust margin online` | R042 | battery-aware predictive planning and control for multirotors (2026) |
| GQ25 | `Ingenuity Mars helicopter flight 72 crash investigation navigation system featureless terrain cause findings` | R060 | Ingenuity flight 72: degraded navigation over visually bland terrain |
| GQ26 | `ispace Hakuto-R Mission 1 lunar lander crash cause altitude estimate crater rim laser rangefinder measurement rejected software` | R061 | Hakuto-R M1 rejected a correct rangefinder reading as a fault; M2 laser rangefinder |
| GQ27 | `Amazon MK30 drone crashes rain lidar altitude sensor software update December 2024 FAA investigation` | R062 | MK30 crashes: rain-susceptible lidar after a software update (NTSB via Bloomberg) |
| GQ28 | `Helios HP03 mishap investigation report configuration change lack of adequate analysis methods risk assessment 2003` | R063 | Helios: analysis methods inadequate for configuration changes |
| GQ29 | `NTSB Boeing 737 MAX safety recommendation report assumptions pilot recognition response time safety assessment ASR-19-01` | R064 | ASR-19-01: pilot-response assumptions in safety assessment did not hold |
| GQ30 | `Intuitive Machines IM-1 IM-2 lunar landing tipped over laser rangefinder altimeter issue investigation findings` | R065 | IM-1 rangefinder switch; IM-2 altimeter noise and lighting |
| GQ31 | `FAA roadmap for artificial intelligence safety assurance 2024 runtime assurance learned adaptive systems` | R031 | FAA AI roadmap: learned versus learning AI; incremental |
| GQ32 | `EASA artificial intelligence concept paper issue 2 operational design domain runtime monitoring out of distribution aviation ML constituent` | R027, R028 | EASA AI concept paper ODD guidance; ODD-to-runtime-monitor for aviation |
| GQ33 | `NASA considerations in assuring safety of increasingly autonomous systems Alves challenges runtime assurance report` | R007, R055, R056 | NASA eVTOL RTA report; ISSA; trusted runtime verification challenge |
| GQ34 | `NASA in-time aviation safety management system IASMS concept of operations monitor assess mitigate risks UAM` | R055 | IASMS monitor-assess-mitigate |
| GQ35 | `DoD test and evaluation of autonomous systems challenges assurance operational envelope runtime monitoring DoDD 3000.09 verification validation` | R057 | DoD autonomy T&E guidance; reuse of T&E results remains hard |
| GQ36 | `Cofer run-time assurance learning-enabled systems verified input region monitor neural network controller Collins NFM 2020` | R030 | RTA for learning-enabled taxiing (NFM 2020) |
| GQ37 | `NASA CR 2021 run time assurance electric vertical takeoff landing aircraft recovery control assumptions degraded vehicle` | R007 | NASA/CR-20210026909 RTA for eVTOL |
| GQ38 | `runtime assurance safety monitor validity depends on vehicle model accuracy actuator degradation adaptive runtime assurance online model update guarantee` | R021 | runtime assurance depends on model accuracy; partial-observability ModelPlex appeared |
| GQ39 | `fault-tolerant control barrier function actuator faults loss of effectiveness safety guarantee adaptive CBF input constraints degraded authority` | none registered | fault-tolerant CBF/HOCBF with actuator faults; no runtime degradation-bound source |
| GQ40 | `weakly hard real-time control deadline misses runtime monitoring stability guarantee assumption timing violation control task` | R023 | weakly-hard (m,k) runtime monitors switch to a safe mode |
| GQ41 | `integrity monitoring visual inertial odometry protection levels vision-based navigation certification aviation open problem` | R070, R071 | visual navigation integrity: algorithm integrity a main certification challenge |
| GQ42 | `perception contracts safety ML-enabled control systems Mitra Astorga vision-based landing runtime monitoring contract violation` | R024 | perception contracts; vision-based auto-landing |
| GQ43 | `remaining control authority estimation online aircraft control effectiveness monitoring attainable moment set degraded actuators runtime` | R052, R035 | attainable moment sets; online control-effectiveness learning; viability |
| GQ44 | `capability-aware autonomy self-assessment of competence robot capability model degradation mission feasibility runtime "competency" assessment` | R047 | competency self-assessment for autonomous agents |
| GQ45 | `SINADRA situation-aware dynamic risk assessment Bayesian network autonomous systems Reich Trapp dynamic risk management` | R048 | SINADRA situation-aware dynamic risk assessment |
| GQ46 | `graceful degradation autonomous vehicles degraded modes capability monitoring functional architecture safe degraded operation minimal risk condition` | R049 | graceful degradation and dependability cages |
| GQ47 | `ICAROUS NASA integrated configurable algorithms reliable operations unmanned systems contingency detect and avoid geofence autonomy` | R050 | ICAROUS formally verified UAS autonomy functions |
| GQ48 | `flight envelope protection loss of control prediction onboard margin to loss of control metric real-time Belcastro envelope awareness` | R037, R039, R051 | envelope-aware FMS; AIRSAFE; envelope prediction and displays |
| GQ49 | `Rushby runtime certification formal analysis at runtime assumptions monitored aircraft certification envelope` | none registered | formal methods certification background; no runtime-certification source kept |
| GQ50 | `Reconciling safety measurement and dynamic assurance NASA system-wide safety 2024 assurance case safety performance indicators aviation` | R016, R055 | SPIs linked to safety case (SAFECOMP 2024); IASMS |
| GQ51 | `operational design domain exit detection runtime ODD monitor aviation UAS ISO 34503 in-ODD monitoring assumptions environment` | R028, R029 | ISO 34503 ODD exit; ODD runtime monitoring |
| GQ52 | `several individually acceptable degradations combine unsafe system level margin erosion no component exceeds threshold emergent hazard aircraft` | none registered | generic margin-erosion and STAMP material; nothing specific |
| GQ53 | `Viability under degraded control authority Ornik Bouvier guaranteed reachability unknown dynamics after failure` | R034, R035 | viability and online reachable sets under degraded control authority |
| GQ54 | `envelope-aware flight management system loss of control prevention Balachandran Atkins flight safety assessment management FSAM` | R037 | EA-FMS / FSAM, LOC prevention given rudder jam |
| GQ55 | `NASA FRET Copilot Ogma runtime monitors generated from requirements assumptions cFS ROS flight software` | R022 | FRET to Ogma to Copilot monitors on cFS and ROS 2 |
| GQ56 | `analysis civil drone accidents incidents causes technical failure power loss battery statistics Wild Murray Baxter` | R068 | UAS accident statistics; battery failures clustered in landing |
| GQ57 | `Assurance 2.0 defeaters Bloomfield Rushby assurance case confidence runtime assumptions eliminative argumentation` | R017 | Assurance 2.0 defeaters and confidence |
| GQ58 | `runtime quantitative verification self-adaptive systems Calinescu Ghezzi Filieri requirements guarantees parameter changes` | R026 | runtime quantitative verification of self-adaptive software |
| GQ59 | `in-service safety assessment validate safety assessment assumptions failure rates operational data ARP5150 continued airworthiness monitoring` | R058 | ARP5150 in-service safety assessment validates assumptions |
| GQ60 | `MQ-9 Reaper accident investigation board report degraded aircraft continued operation autonomous lost link multiple failures` | R067 | MQ-9 accident boards: battery-limited recovery; unreachable recovery site |
| GQ61 | `simplex safety controller recoverable region computed offline invalid when plant dynamics change model mismatch runtime assurance guarantee failure` | R003, R004 | model error invalidates Simplex guarantees (attribution UNCLEAR); adaptive Simplex |
| GQ62 | `predictive thrust margin power margin monitoring multirotor eVTOL hover capability prediction before saturation battery power limit` | R045 | rotorcraft thrust-margin monitoring patent |
| GQ63 | `eVTOL contingency landing reachable vertiports battery degradation energy reserve online feasibility emergency landing site selection` | R043, R044 | eVTOL battery power capability for landing; dynamic reserves; mid-air shutdown risk |
| GQ64 | `vehicle health management information not used by autonomous mission planning integration gap health-aware autonomy challenge UAS prognostics decision` | none new | health-aware planning and ACM; integration described as active research |
| GQ65 | `Online guaranteed reachable set approximation systems with changed dynamics and control authority Ornik IEEE TAC 2024 aircraft` | R034 | online guaranteed reachable sets under changed dynamics and control authority |
| GQ66 | `contract-based design UAV runtime monitoring assume-guarantee contracts flight software components violated assumptions at runtime aerospace` | R025, R019 | Pacti; assumption monitoring for A/G contracts |
| GQ67 | `online mass and inertia estimation multirotor payload change in flight adaptive hover thrust estimation fielded autopilot` | R074 | online mass/inertia estimation and adaptive control for payload changes |

## Direct fetches (raw GitHub, read line by line)

| file | branch | sha256 | result |
|---|---|---|---|
| PX4 `src/modules/commander/HealthAndArmingChecks/checks/windCheck.cpp` | main | `ea15f9277aac2dd32ffa58ef7ecc41f1034dbd6fad40db97903729789c8210a3` | 200; R080 (V4) |
| PX4 `…/checks/batteryCheck.cpp` | main | `c424ce129bdda25b6142089099c3fd1e02dff3a9fbb1b6220aafb734a228ce79` | 200; R081 (V4) |
| PX4 `src/lib/rtl/rtl_time_estimator.cpp` | main | `fb9c97c7c23b85f72ba7f4c11c8ffc6c96cedb58c6a190e782ef338b2e1174ab` | 200; R082 (V4) |
| PX4 `…/checks/flightTimeCheck.cpp` | main | `fbc47827241d6165f04a1beb4af69c851b3ca368234a9bf4fbb69195143dc6ba` | 200; R083 (V4) |
| PX4 `…/checks/rcAndDataLinkCheck.cpp` | main | `469e14a259f3058f9fe4ef4f8d9d92ab56f9ba31c59ce4a65889e55298159c99` | 200; R086 (V4) |
| PX4 `src/modules/commander/failsafe/failsafe.cpp` | main | (fetched, not analysed) | 200; not cited |
| PX4 `src/modules/navigator/rtl_time_estimator.cpp` | main | — | 404 (the file lives under `src/lib/rtl/`) |
| ArduPilot `ArduCopter/crash_check.cpp` | master | `02bf3f877a9a5bec2adbef070d0cfe9edfce13a355f4f79f9777b6116b42f170` | 200; R084 (V4) |
| ArduPilot `libraries/AP_BattMonitor/AP_BattMonitor_Backend.cpp` | master | (fetched, not analysed) | 200; not cited |

## What was not searched well

- **Full text.** Standards (ASTM F3269, SC-VTOL MOC, ARP5150), accident
  reports and every paper are V0.
- **Proprietary practice.** eVTOL and delivery-drone flight-control practice
  is unobservable from public sources.
- **Military.** Only public accident-board summaries were used.
- **Non-English literature.** Not searched.
- **Fielded code.** Only the files above were read.
