# Autonomous aerospace assurance: gap landscape

Adversarial gap analysis, 2026-09-28. The package lives in
`research/autonomous_assurance_gap_search/`. Candidate gaps are defined in
`CANDIDATE_GAPS.csv` and attacked in `PRIOR_ART_KILL_MATRIX.csv`. The
selection and the decision are in `TOP_THREE_GAPS.md`.

## Status and method change

- **What this is.** A search for an important, unsolved assurance problem in
  autonomous aircraft, **found independently of CSIA**.
- **What this is not.** No CSIA architecture, code, simulator work,
  experiment or product pitch. No equations beyond what the literature
  already defines.
- **What was not touched.** XSYS-001, amendments A1 and A2, the confirmatory
  result and its manifests, the novelty audit, the CSIA-DX review and the
  model-inadequacy package are unmodified and are not reinterpreted. The
  FAILURE_LEDGER was not appended.
- **Earlier kills are not reopened.** These directions were killed or reduced
  earlier and are only cross-referenced here:
  - cross-system fault diagnosis;
  - temporal fault signatures;
  - sensor-versus-actuator discrimination;
  - controller compensation as evidence;
  - conditional or runtime diagnosability;
  - active evidence acquisition;
  - design-time and runtime diagnosability;
  - ambiguity versus model inadequacy;
  - open-set diagnosis.
- **Candidates are phrased without CSIA.** CSIA appears only in score H and in
  the "why SWORT has an advantage" field of `TOP_THREE_GAPS.md`.

## 0. Limits, scales and decision rule

**Access.** Only `raw.githubusercontent.com` is reachable from this
environment. Every paper, standard, patent and accident report below is
therefore **V0**, a search-engine title and summary. Each carries
**REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION** (`FULLTEXT_VERIFICATION_QUEUE.md`).
The exceptions are PX4 and ArduPilot source files, read line by line at
**V4**, and this repository's own files, also **V4**.

**Verification levels.**

| level | meaning |
|---|---|
| V0 | search result or snippet only |
| V1 | abstract verified |
| V2 | substantial primary-source text inspected |
| V3 | complete relevant primary source inspected |
| V4 | claim traced to an exact section, page, claim, equation or source line |

**Status codes.** **SC** means corroborated by two or more results or an
index page. **SS** means a single search summary.

**Novelty scale** (the same as the earlier packages).

| level | meaning |
|---|---|
| N0 | known |
| N1 | close, or only terminologically different |
| N2 | possibly distinct combination |
| N3 | apparently distinct in the searched literature |
| N4 | needs V3/V4 full text; not used |

**Wording discipline.** Where nothing matching was found, this package says
"no directly matching work was identified in the searched sources". A source
that could not be read makes a finding UNCLEAR, not absent.

**Red-team kill tests, from the brief.**

| test | outcome |
|---|---|
| SOLVED | KILL |
| TERMINOLOGY (the difference is only in naming) | KILL |
| COMMERCIALLY_IRRELEVANT | KILL |
| EDGE_CASE (useful only in unrealistic cases) | KILL |
| UNAVAILABLE_TECHNOLOGY | DOWNRANK |

**Decision rule.** It is applied mechanically to the scores in
`CANDIDATE_GAPS.csv`. A candidate counts as a **high-value gap** only if all
five conditions hold:

1. it survives the red team;
2. A (real-world importance) ≥ 4;
3. B (unsolvedness) ≥ 3;
4. D (aerospace relevance) ≥ 4;
5. the total is ≥ 30 out of 50.

**Sensitivity.** Adding a sixth condition, I (defensibility against prior
art) ≥ 3, would leave **no** candidate qualifying. `TOP_THREE_GAPS.md` reports
this.

## 1. Source register

Ids `Rnnn` are cited by every file in the package. Where a source already
appears in an earlier package, that package's id is cross-referenced.

### Runtime assurance and Simplex

| id | reference | ids / URL | level |
|---|---|---|---|
| R001 | ASTM F3269-17 / F3269-21, "Standard practice for methods to safely bound flight behavior of UAS containing complex functions". A safety monitor checks behaviour against predefined safety limits and engages a recovery control function (RCF). Discussed in "ASTM F3269 – an industry standard on run time assurance for aircraft systems", AIAA SciTech 2021 | astm.org F3269; arc.aiaa.org 10.2514/6.2021-0525 | V0 SC |
| R002 | X. Wang, N. Hovakimyan, L. Sha, "L1Simplex: fault-tolerant control of cyber-physical systems", ICCPS 2013. The original Simplex is "unsuitable" when physical failures change the dynamics. Also RSimplex (*ACM TCPS* 2018) and NetSimplex | ieeexplore 6603998; dl.acm 10.1145/3121428 | V0 SC |
| R003 | Simplex model-mismatch statements in the searched set: "any model error invalidates the safety guarantee", because the formal safety controller relies on simulating the plant model. The results include Black-Box Simplex (arXiv 2102.12981) and Neural Simplex (arXiv 1908.00528). **Which paper makes the statement is UNCLEAR at V0** | as listed | V0 SS |
| R004 | Simplex variants for changed conditions: "An adaptive, provable correct simplex architecture" (*STTT*, 2025); "Emergency-Brake Simplex … abrupt runtime reachability constraint changes" (arXiv 2501.01831); "Conformal recovery-deadline certificates for runtime assurance of adapting controllers" (arXiv 2606.25371) | link.springer 10.1007/s10009-025-00779-0; as listed | V0 SC |
| R005 | Backup control barrier functions (Gurriet, Ames et al.). The invariant set is evaluated online by forward-integrating the dynamics under a fixed backup policy. See arXiv 2104.11332; output-feedback backup CBFs under input bounds and estimation error (arXiv 2604.19893) | as listed | V0 SC |
| R006 | F-16 Auto-GCAS, fielded in 2014 and credited with saving pilots and aircraft. Trajectory prediction depends on the aircraft's performance constraints. Also performance-limited Auto-GCAS (AFIT) and a small-UAV Auto-GCAS (NASA/TM-2015-218732) | researchgate 260657762; scholar.afit.edu etd/2214; NTRS 20150014106 | V0 SC |
| R007 | NASA/CR-20210026909, "Run time assurance for electric vertical takeoff and landing aircraft" (terminal recovery control; RTA subsystem interactions). "A verification framework for runtime assurance of autonomous UAS" (NASA, DASC 2024) | NTRS 20210026909; NTRS 20240007986 | V0 SC |
| R008 | "Mission-level runtime assurance framework for autonomous driving" (arXiv 2606.06996). Most failures occur after fallback activation, because "the current fallback controller is not always sufficiently capable of restoring mission feasibility" | as listed | V0 SS |
| R009 | S. Bak et al., "Real-time reachability for verified Simplex design", RTSS 2014 | stanleybak.com bak2014rtss.pdf | V0 SS |

### Dynamic assurance cases and runtime confidence

| id | reference | ids / URL | level |
|---|---|---|---|
| R010 | D. Schneider, M. Trapp, conditional safety certificates (ConSerts), including "Conditional safety certification of open adaptive systems" (*ACM TAAS*, 2013). Guarantees are tied to demands (assumptions) that are resolved at runtime | dl.acm 10.1145/2491465.2491467 | V0 SC |
| R011 | E. Denney, G. Pai, I. Habli, "Dynamic safety cases for through-life safety assurance", ICSE 2015 | NTRS 20150011054 | V0 SC |
| R012 | E. Asaadi, E. Denney, J. Menzies, G. Pai, D. Petroff, "Dynamic assurance cases: a pathway to trusted autonomy", *IEEE Computer*, 2020, applied to autonomous taxiing of a UAS. Also "Quantifying assurance in learning-enabled systems" (SAFECOMP 2020) | dl.acm 10.1109/MC.2020.3022030 | V0 SC |
| R013 | R. Calinescu, D. Weyns, S. Gerasimou et al., ENTRUST: "Engineering trustworthy self-adaptive software with dynamic assurance cases", *IEEE TSE*, 2018. Runtime evidence updates the dynamic elements of the assurance case | arXiv 1703.06350 | V0 SC |
| R014 | C. Hartsell et al., "ReSonAte: a runtime risk assessment framework for autonomous systems", SEAMS 2021. Bow-tie models plus runtime monitors estimate hazard rates, including "assumptions made at design time" (DARPA Assured Autonomy, AFRL) | arXiv 2102.09419 | V0 SC |
| R015 | UL 4600 safety performance indicators (SPIs), per Koopman: SPIs "provide metrics on safety case validity", including "assumption validity". "Towards an argument pattern for the use of safety performance indicators" (arXiv 2410.00578) | as listed | V0 SC |
| R016 | E. Denney, G. Pai, "Reconciling safety measurement and dynamic assurance", SAFECOMP 2024 (NASA System-Wide Safety; AdvoCATE; autonomous taxiing) | arXiv 2405.19641 | V0 SC |
| R017 | R. Bloomfield, J. Rushby, Assurance 2.0: defeaters, and confidence in Assurance 2.0 cases | arXiv 2409.10665; arXiv 2205.04522 | V0 SC |
| R018 | "A subjective logic-based method for runtime confidence updates in safety arguments" | arXiv 2605.22530 | V0 SS |

### Assumption and contract monitoring

| id | reference | ids / URL | level |
|---|---|---|---|
| R019 | "Monitoring assumptions in assume-guarantee contracts". Verification is complemented by post-deployment monitoring that the environment assumptions hold | arXiv 1606.00505 | V0 SC |
| R020 | I. Ruchkin et al., "Confidence composition for monitors of verification assumptions" (CoCo), ICCPS 2022. It uses calibrated confidence monitors per verification assumption, composed into confidence in the verified safety guarantee | arXiv 2111.03782 | V0 SC |
| R021 | ModelPlex runtime model compliance, with the partial-observability extension and US 10,872,187 / 11,204,838. Cross-reference: `research/csia_model_inadequacy/PRIOR_ART_ATTACK.md` M27 | arXiv 1811.06502 | V0 SC |
| R022 | NASA FRET → Ogma → Copilot. Requirements are compiled into hard-real-time C99 monitors, deployable as cFS applications or ROS 2 nodes | NTRS 20220000049; arXiv 2209.14030; github nasa/ogma | V0 SC |
| R023 | Weakly-hard real-time control: (m,k) deadline-miss constraints. Runtime monitors switch to a safe mode when the weakly-hard assumption is violated (survey, PMC10222610) | PMC10222610 | V0 SC |
| R024 | A. Astorga, C. Hsieh, P. Madhusudan, S. Mitra, "Perception contracts for safety of ML-enabled systems", OOPSLA 2023. Also refining perception contracts for vision-based auto-landing (arXiv 2311.08652) | dl.acm 10.1145/3622875 | V0 SC |
| R025 | Pacti: scaling assume-guarantee reasoning for system analysis and design | arXiv 2303.17751 | V0 SS |
| R026 | R. Calinescu, C. Ghezzi, M. Kwiatkowska, R. Mirandola, "Self-adaptive software needs quantitative verification at runtime", *CACM*, 2012 | prismmodelchecker.org cacm-runtime.pdf | V0 SC |

### ODD, ML guidance and certification programmes

| id | reference | ids / URL | level |
|---|---|---|---|
| R027 | EASA AI Concept Paper Issue 2 (2024) and proposed Issue 03 (June 2026). The ODD appears in all four building blocks; runtime monitoring and safeguards increase with automation level | easa.europa.eu | V0 SC |
| R028 | DLR, "From operational design domain to runtime monitoring of AI-based aviation systems" (DASC 2024): ODD transformed into RTLola monitors. Also "Runtime monitoring of operational design domain to safeguard ML components" | elib.dlr.de 212160 | V0 SC |
| R029 | ISO 34503:2023, ODD taxonomy, including ODD boundary and ODD exit | iso.org 78952 | V0 SC |
| R030 | D. Cofer et al., "Run-time assurance for learning-enabled systems", NFM 2020 (neural-network aircraft taxiing) | Springer 978-3-030-55754-6_21 | V0 SC |
| R031 | FAA, "Roadmap for artificial intelligence safety assurance", version I, August 2024. It distinguishes learned (static) from learning AI and scopes learning AI as a later step | faa.gov/media/82891 | V0 SC |
| R053 | EASA SC-VTOL-01 and MOC SC-VTOL. For continued safe flight and landing, "any changes in aircraft performance … (e.g. range, expected height loss, remaining rate of climb) … after a single failure or combination of failures not extremely improbable should be considered" | easa.europa.eu SC-VTOL-01.pdf; MOC SC-VTOL | V0 SC |
| R054 | FAA minimum equipment list preamble: "No flight shall be conducted with multiple unrelated deferred items that create a hazard" (AC 91-67A and related) | faa.gov AC_91-67A | V0 SS |
| R055 | NASA In-time Aviation Safety Management System (IASMS) and In-time System-wide Safety Assurance (ISSA) concept of operations (NASA/TM-2020-5003981): monitor, assess, mitigate; risks "wherein the interplay of hazards may not be known and cannot be accounted for at design time" | NTRS 20205003981; NTRS 20210017625 | V0 SC |
| R056 | A. Goodloe, "Challenges in high-assurance runtime verification" (NASA, 2016): runtime verification helps "only if the RV itself can be trusted" | NTRS 20160012454 | V0 SS |
| R057 | DoD Directive 3000.09 (2023) and the Developmental Test and Evaluation of Autonomous Systems Guidebook (2025). Reuse of T&E results "remains an elusive and technically challenging problem" | esd.whs.mil; cto.mil | V0 SC |
| R058 | SAE ARP5150, safety assessment of transport airplanes in commercial service: in-service data validate safety-assessment assumptions | saemobilus ARP5150 | V0 SC |

### Health to capability, envelopes and contingency

| id | reference | ids / URL | level |
|---|---|---|---|
| R032 | Safe flight envelope estimation for impaired aircraft by reachability and databases: Zhang, de Visser, Chu (*JGCD*, 2019); Nabi, Lombaerts et al. (*JGCD*, 2018); probabilistic envelope estimation (arXiv 2003.06588) | doi 10.2514/1.G003834; 10.2514/1.G003184 | V0 SC |
| R033 | G.-X. Du, Q. Quan, B. Yang, K.-Y. Cai, "Controllability analysis for multirotor helicopter rotor degradation and failure", *JGCD*, 2015. The **available control authority index (ACAI)**; also ArCAI | arXiv 1403.5986 | V0 SC |
| R034 | H. El-Kebir, A. Pirosmanishvili, M. Ornik, "Online guaranteed reachable set approximation for systems with changed dynamics and control authority", *IEEE TAC* 69(2):726–740, 2024. Intended for "on-board fault-tolerant path planning and failure recovery" | arXiv 2203.10220 | V0 SC |
| R035 | H. El-Kebir, R. Berlin, J. Bentsman, M. Ornik, "Viability under degraded control authority", *IEEE L-CSS*, 2023. Also resilience to partial loss of control authority (*Automatica*, 2023) | arXiv 2310.15132; arXiv 2209.08034 | V0 SC |
| R036 | NASA intelligent contingency management (ICM) for UAM and dynamic vehicle assessment (SciTech 2021). The vehicle must "ascertain its capability and make decisions about mission completion or modification". A UAM benchmark problem for ICM (2023) | NTRS 20205006970; 20205011183; 20230017549 | V0 SC |
| R037 | S. Balachandran, E. Atkins, envelope-aware flight management system (EA-FMS) and flight safety assessment and management (FSAM), *JGCD*. Envelope estimation, planning and LOC-risk override | doi 10.2514/1.G000252; 10.2514/1.G001743 | V0 SC |
| R038 | N. Meuleau et al., Emergency Landing Planner for damaged aircraft (NASA, IAAI 2009). E. Atkins, adaptive flight planning after degraded performance | NTRS 20090033735; aaai.org | V0 SC |
| R039 | C. Belcastro, J. Foster, aircraft loss-of-control accident analysis. LOC arises from factors "acting alone or more often in combination"; worst cases combine failures, upsets, icing and crew response. AIRSAFE (Belcastro & Jacobson); iReCoVeR | NTRS 20110012012; 20160007744 | V0 SC |
| R040 | NASA remaining-flying-time prediction for electric UAVs (Edge 540 sub-scale). End-of-discharge prediction supports mission replanning | NTRS 20180004466; 20160006424 | V0 SC |
| R041 | Health-aware control and MPC surveys; health-aware MDP planning for UAV missions ("reassessing vehicle capabilities"); quadrotor predictive maintenance with multi-actuator degradation (*Aeronautical Journal*) | ieeexplore 6669789; cambridge.org | V0 SC |
| R042 | "Battery-aware predictive trajectory planning and control for multirotors under disturbances" (arXiv 2609.12188). It couples SOC, terminal voltage, wind disturbance, motor saturation and actuator degradation in planning | arXiv 2609.12188 | V0 SS |
| R043 | "Novel battery power capability assessment for improved eVTOL aircraft landing" (*Applied Energy*, 2024). "Revisiting energy reserve requirements for battery-electric VTOL aircraft" (AIAA Aviation 2024): dynamic reserves that depend on battery state | sciencedirect S0306261924002319; arc.aiaa.org 10.2514/6.2024-3904 | V0 SC |
| R044 | *Joule* (2023), "Revealing hidden predicaments to lithium-ion battery dynamics for eVTOL": "sustained high power under low SOC may result in ohmic drops causing mid-air electrochemical shutdown". *Joule* (2021), battery requirements for eVTOL | cell.com S2542-4351(23)00312-4 | V0 SC |
| R045 | US 11,623,741, "Thrust margin monitoring device for rotorcraft": a thrust-margin parameter from available power and air density, compared in real time with thresholds | USPTO 11623741 | V0 SS |
| R046 | "Emergency flight planning for an energy-constrained multicopter" (*J. Intelligent & Robotic Systems*, 2016) | doi 10.1007/s10846-016-0370-z | V0 SS |
| R047 | Competency self-assessment for autonomous agents (arXiv 2303.01646); event-triggered generalized outcome assessment (*Frontiers*, 2023); for a learning-based aircraft system (*Frontiers*, 2025) | as listed | V0 SC |
| R048 | J. Reich, M. Trapp, SINADRA, situation-aware dynamic risk assessment (EDCC 2020). Dynamic risk management in CPS (arXiv 2401.13539) | ieeexplore 9236984 | V0 SC |
| R049 | Graceful degradation and "dependability cages" for automated vehicles (SAE, 2019); degraded-mode and minimal-risk transitions | researchgate 335692219 | V0 SC |
| R050 | ICAROUS (NASA): formally verified detect-and-avoid, geofencing and contingency decision-making for UAS | NTRS 20170001936; github nasa/icarous | V0 SC |
| R051 | Flight envelope prediction via optimal-control reachability (*JGCD*); flight-envelope-augmented displays (NASA); envelope protection for small aircraft | NTRS 20160005910; doi 10.2514/1.G006219 | V0 SC |
| R052 | Attainable moment sets and online control-effectiveness learning with allocation for over-actuated aircraft (arXiv 2606.13794) | as listed | V0 SS |
| R074 | Online mass and inertia estimation for multirotors with payload changes, e.g. RISE-based adaptive control with mass–inertia estimation (arXiv 2209.08209). Add-on estimators for ArduPilot were mentioned in a summary | as listed | V0 SC |

### Accidents and incidents

| id | reference | ids / URL | level |
|---|---|---|---|
| R060 | NASA/JPL, Ingenuity flight 72 investigation (2024). Root cause: "degraded navigation due to visually bland terrain", possibly with high slopes. The vision system was designed for textured flat terrain; featureless sand ripples led to high touchdown velocity and blade damage | nasa.gov; jpl.nasa.gov; spacenews.com | V0 SC |
| R061 | ispace Hakuto-R Mission 1 (2023). The software rejected a correct laser-rangefinder altitude change at a crater rim "on the assumption that the instrument had malfunctioned". It believed it had landed about 5 km up and ran out of fuel. Also Mission 2 "Resilience" (2025), attributed to the laser rangefinder | spacenews.com; universetoday.com | V0 SC |
| R062 | Amazon Prime Air MK30: two test-flight crashes on 16 December 2024 in light rain. Per an NTSB investigation reported by Bloomberg, a software update made the lidar more susceptible to rain; misread altitude led the software to cut power. Also a Darlington, UK, crash (2026) reported as a regulator "contingency gap" | dronedj.com; techtimes.com; suasnews.com | V0 SC |
| R063 | NASA Helios HP03 mishap report (2004). "Lack of adequate analysis methods led to an inaccurate risk assessment of the effects of configuration changes", producing a configuration highly sensitive to turbulence | nasa.gov 64317main_helios.pdf; NTRS 20070022260 | V0 SC |
| R064 | NTSB ASR-19-01 (2019), "Assumptions used in the safety assessment process and the effects of multiple alerts and indications on pilot performance". Pilot responses to MCAS "were not consistent with the underlying assumptions" used in the functional hazard assessments | ntsb.gov ASR1901.pdf | V0 SC |
| R065 | Intuitive Machines IM-1 (2024): laser rangefinders non-functional because a safety switch was not enabled; navigation software rewritten in flight to use the NDL lidar; tipped over. IM-2 (2025): altimeter "signal noise and distortion" and dim polar lighting; landed on its side. The IM-3 remedy adds altimeters and a lighting-independent velocity sensor | spacenews.com; spacepolicyonline.com | V0 SC |
| R066 | Helicopter power-margin accidents: density altitude, weight and wind combining so that out-of-ground-effect hover is not available, even below maximum weight (ATSB AO-2015-033 R22; Flight Safety Foundation "Into thin air"; USHST "Power available limitations" bulletin) | atsb.gov.au ao-2015-033; flightsafety.org; vast.aero | V0 SC |
| R067 | USAF MQ-9 accident investigation board reports: generator loss with battery-limited recovery; a propulsion anomaly with no recoverable location in reach; propeller decoupling | afjag.af.mil AIB reports; airandspaceforces.com | V0 SC |
| R068 | UAS accident statistics: cross-national multirotor accident analysis 2016–2022 (*Computation* 14(9):214); Australian post-occurrence analysis (*Safety Science*); UK CAA "Preventing technical failures". The summaries attribute a large share to system/component failure, and a cluster of battery failures to the landing phase ("energy exhaustion at the end of mission") | mdpi.com 2079-3197/14/9/214; caa.co.uk | V0 SS |
| R069 | Earlier incident evidence, cross-referenced from `research/csia_model_inadequacy/PRIOR_ART_ATTACK.md`: XL 888T (M52), Lufthansa 1829 (M53), Schiaparelli (M54), Ariane 501 (M51), Qantas 72 (M50) | — | V0 SC |

### Navigation integrity

| id | reference | ids / URL | level |
|---|---|---|---|
| R070 | "Integrity of visual navigation — developments, challenges, and prospects", *NAVIGATION* 69(2), 2022. "Algorithm integrity is one of the main challenges of certifying visual navigation systems"; fault frequency and error magnitude are scenario-dependent; existing approaches focus "more on the accuracy and robustness … rather than their errors, integrity and reliability" | navi.ion.org navi.518 | V0 SC |
| R071 | Integrity monitoring for vision and UAM navigation: visual measurement integrity monitoring for UAV localization (arXiv 1909.08537); IM-GIV for GNSS/INS/vision (arXiv 2410.22672); US 11,899,469, integrity monitoring for visual odometry; vertiport navigation requirements for UAM (arXiv 2311.07487) | as listed | V0 SC |
| R073 | Angle-of-attack analytical redundancy detecting common-mode failures (patents). Cross-reference: `research/csia_model_inadequacy/PRIOR_ART_ATTACK.md` M44 | — | V0 SC |

### Fielded autopilot code, read line by line

| id | reference | ids / URL | level |
|---|---|---|---|
| R080 | PX4 `src/modules/commander/HealthAndArmingChecks/checks/windCheck.cpp` (`main`, fetched 2026-09-28, sha256 `ea15f9277aac…`). Line 51: `wind_limit_exceeded` is a fixed-threshold comparison of the wind estimate against the `COM_WIND_MAX` parameter. Lines 54–57: the failsafe flag is set if the configured action exceeds a warning | raw.githubusercontent.com | **V4** (this file only) |
| R081 | PX4 `…/checks/batteryCheck.cpp` (sha256 `c424ce129bdd…`). Lines 180–183: the worst `battery.time_remaining_s` is taken. Lines 301–314: `battery_low_remaining_time` when `rtl_time_estimate.safe_time_estimate * hysteresis ≥ worst_battery_time_s`, i.e. an **energy/time** comparison | raw.githubusercontent.com | **V4** (this file only) |
| R082 | PX4 `src/lib/rtl/rtl_time_estimator.cpp` (sha256 `fb9c97c7c23b…`). Line 70: safe estimate = parameter factor × estimate + parameter margin. Lines 137–144: wind reduces ground speed along the return path. Cruise speeds come from parameters (lines 52–59) | raw.githubusercontent.com | **V4** (this file only) |
| R083 | PX4 `…/checks/flightTimeCheck.cpp` (sha256 `fbc47827241d…`). A fixed maximum flight time `COM_FLT_TIME_MAX` (lines 49, 66) | raw.githubusercontent.com | **V4** (this file only) |
| R084 | ArduPilot `ArduCopter/crash_check.cpp` (`master`, sha256 `02bf3f877a9a…`). Lines 11–13: thrust loss is inferred after **1 s of descent while level at ≥ 90 % throttle**. Lines 100–180: on trigger, "Potential Thrust Loss", `set_thrust_boost(true)`, optional gripper release. Lines 184–229: a yaw-imbalance warning from the yaw integrator | raw.githubusercontent.com | **V4** (this file only) |
| R086 | PX4 `…/checks/rcAndDataLinkCheck.cpp` (sha256 `469e14a259f3…`). Lines 51–57: manual-control-lost flag. Lines 76–84: GCS-connection-lost flag with action from `NAV_DLL_ACT` | raw.githubusercontent.com | **V4** (this file only) |
| R085 | PX4 `EKF2Selector.cpp`. Cross-reference: `research/csia_model_inadequacy/PRIOR_ART_ATTACK.md` M60 | — | V4 |

### This repository

| id | reference | ids / URL | level |
|---|---|---|---|
| R090 | SWORT/CSIA assets, read locally: `csia/v2/domains/power.py` (battery droop as internal-resistance drop; declared thresholds); `research/px4_actuator_effectiveness/` (the PX4 SIH motor-effectiveness patch used for XSYS-001); `research/csia_dx/CSIA_DX_FIRST_EXPERIMENT.md` §2 ("PX4 SIH … models none of battery current, ESC current or motor current"); `research/consequence/` (model-based action-consequence phases). No hardware result exists in this repository | local | V4 |

## 2. What the state of the art already delivers

| field (brief) | what it delivers | what it assumes | where it stops, in the searched sources | ids |
|---|---|---|---|---|
| FDI / IVHM / ISHM | fault detection, isolation, vehicle-level reasoning | a fault library; see the earlier packages | earlier kills; not reopened | R069; earlier packages |
| PHM | remaining useful life; remaining flying time | a degradation model per component | per-component and energy-centric; power **capability** only in recent eVTOL work | R040, R043 |
| runtime assurance / Simplex | bounded behaviour of complex functions; certified path for UAS | recovery function and switching boundary verified against a model | "any model error invalidates the guarantee" (attribution UNCLEAR); adaptive variants appeared from 2013 through 2026 | R001–R009 |
| runtime verification | specified properties and assumptions monitored in hard real time | the property is observable | a capability quantity is not directly observable | R019–R023 |
| fault-tolerant control | reconfiguration after faults, including L1-adaptive and passive schemes | fault within design envelope | whether capability **remains sufficient for the mission** is not its output | R002, R033 |
| active diagnosis | earlier kill (CSIA-DX) | — | not reopened | — |
| model invalidation / open-set | earlier kill (model inadequacy) | — | not reopened | R069 |
| integrity monitoring | GNSS RAIM/ARAIM protection levels | characterized fault models | vision and terrain-relative integrity is open (R070) | R070, R071 |
| contingency management | capability assessment and mission modification (UAM); emergency landing planning | a capability estimate is available | NASA frames it as ongoing (benchmark problem 2023) | R036, R038, R050 |
| safe planning / envelope-aware FMS | envelope-constrained planning after damage | envelope estimate | mostly fixed-wing, research | R037, R038 |
| CBF / reachability / viability | invariance and viability under input bounds and degraded authority | dynamics and degradation bounds known or bounded | the source of the degradation bound at runtime is outside scope | R005, R034, R035 |
| health-aware control / MPC | control that trades performance for component life | RUL/SOH models | mostly single-channel; battery-aware multirotor MPC (2026) couples battery, wind and saturation | R041, R042 |
| digital twins | discrepancy and continuous validation (earlier package) | — | not reopened | — |
| assurance cases at runtime | guarantees updated from runtime evidence | the evidence nodes are computable | extensive; see G04 | R010–R018 |
| ODD monitoring | detects exits from the design domain | the ODD is specified as observable attributes | extensive; see G05 | R027–R029 |

## 3. The eight situations in the brief

| # | situation | best existing answer (searched) | residual, if any |
|---|---|---|---|
| 1 | every subsystem nominal, vehicle unsafe | helicopter power-margin charts and thrust-margin monitors; LOC analyses show combinations; SC-VTOL requires combinations to be considered | for electric rotorcraft, fielded autopilots check each factor against a fixed threshold, and thrust loss is inferred only **after** saturation (R080–R084) → **G02** |
| 2 | degradation known, remaining autonomy unknown | ICM capability assessment; EA-FMS; ACAI; guaranteed reachable sets | research, mostly fixed-wing or single-channel → **G02** (G03 merged) |
| 3 | health exists, mission logic cannot use it rigorously | PX4 compares an RTL time estimate with battery time (V4); prognostics-based replanning | energy-only in fielded code → **G02** |
| 4 | guarantees rest on assumptions that can become false | assumption monitors; CoCo; ModelPlex; ODD monitors; perception contracts | assumptions that are **latent capability quantities** or **navigation-error bounds** are not directly observable → **G02, G07, G08** |
| 5 | certification evidence valid only in a region | ODD monitoring; verified-region monitors; flight-envelope limitations | killed (G05) |
| 6 | several acceptable degradations combine into an unsafe condition | MEL rule on multiple deferred items; SC-VTOL combinations; LOC combination analyses | design-time or dispatch-time only for electric rotorcraft → **G02** |
| 7 | operating after the safety-analysis assumptions are false | ARP5150 in-service validation; UL 4600 SPIs; ReSonAte | in-flight, the incidents concern navigation or recovery assumptions (Ingenuity, Hakuto-R, MK30, IM-1/2) → **G08**; RTA recovery → **G07** |
| 8 | diagnosis and safe action disconnected | earlier kill (CSIA-DX) | not reopened (G06) |

## 4. Candidate outcomes

Seventeen candidates were generated (G01–G17). **Thirteen were killed and
four survived** (G02, G07, G08, G12). Details are in `CANDIDATE_GAPS.csv` and
`PRIOR_ART_KILL_MATRIX.csv`.

| id | short name | verdict | score /50 |
|---|---|---|---|
| G01 | online assurance-assumption validity (general) | KILL (SOLVED) | — |
| G02 | compound degradation → runtime capability margin (electric rotorcraft) | SURVIVES, narrowed | 35 |
| G03 | health → capability → allowable actions | KILL (TERMINOLOGY; merged into G02) | — |
| G04 | evidence → guarantee at runtime | KILL (SOLVED) | — |
| G05 | evidentiary region / ODD tracking | KILL (TERMINOLOGY) | — |
| G06 | diagnosis ↔ safe action | KILL (SOLVED; earlier review) | — |
| G07 | validity of the runtime-assurance recovery assumption under degradation | SURVIVES, narrowed | 31 |
| G08 | navigation integrity without GNSS | SURVIVES | 34 |
| G09 | common-mode / redundancy assumption | KILL (SOLVED; earlier package) | — |
| G10 | timing / compute assumption | KILL (SOLVED) | — |
| G11 | mass / CG / configuration change | KILL (SOLVED at runtime) | — |
| G12 | handover when assumptions fail | SURVIVES; below the total cut (28 < 30) | 28 |
| G13 | continuous safe-contingency feasibility | KILL (TERMINOLOGY; merged into G02) | — |
| G14 | in-service validity of safety-assessment assumptions | KILL (SOLVED) | — |
| G15 | assuring in-flight learning control | KILL (COMMERCIALLY_IRRELEVANT near term) | — |
| G16 | cross-function assumption consistency | KILL (SOLVED) | — |
| G17 | single environmental factor beyond the verified bound | KILL (SOLVED) | — |

## 5. What this search did not cover well

- **Industry proprietary practice.** Proprietary eVTOL and delivery-drone
  flight-control practice may already compose power and authority margins.
  Nothing public was found that says so either way: **UNCLEAR**.
- **Full text.** Standards (ASTM F3269, SC-VTOL MOC, ARP5150), accident
  reports and every paper are V0.
- **Fielded code scope.** Only the PX4 and ArduPilot files listed at V4 were
  read. Other failsafe and estimator paths were not traced.
- **Military autonomy.** Only public accident-board summaries were used.
