# Novelty search log (reproducibility record)

Part of the pre-result novelty audit. **Every search was run on 2026-09-27**,
in one session, while the XSYS-001 confirmatory campaign was running. No
search result was used to inspect, and no search touched, any campaign
artifact.

## 1. Tools and access

| route | result |
|---|---|
| `WebSearch` (a web-search tool returning titles, URLs and a summary of the indexed pages) | **worked**: every query below |
| `WebFetch` on `ntrs.nasa.gov`, `arxiv.org`, `patents.google.com`, `www.semanticscholar.org`, `www.sba.org.br` | **EGRESS_BLOCKED** |
| `curl` on 14 hosts: `api.crossref.org`, `doi.org`, `api.openalex.org`, `api.semanticscholar.org`, `ntrs.nasa.gov`, `export.arxiv.org`, `patents.google.com`, `ieeexplore.ieee.org`, `www.sciencedirect.com`, `dblp.org`, `scholar.archive.org`, `www.osti.gov`, `ppubs.uspto.gov`, `api.patentsview.org` | **HTTP 403** from the egress gateway (a policy denial; not retried or routed around) |

**Consequence.** No full text was read. All content statements rest on search
summaries. Section 1 of `research/csia_novelty_audit/BIBLIOGRAPHY.md` explains
what this does and does not license.

**How to reproduce.** Rerun the queries below, verbatim, with any general web
search engine, then read the full texts listed in section 6. Search engines
change, so the returned lists will differ. The citation trails in section 5
are the stable part.

## 2. Internal sources consulted (pre-confirmatory only)

- `docs/CSIA_MASTER_ARCHITECTURE.md`
- `README.md`
- `docs/research/CROSS_SYSTEM_ARCHITECTURE_SEED.md`
- `docs/research/CROSS_SYSTEM_BASELINE_AUDIT.md`
- `docs/research/XSYS_001_PREREGISTRATION.md` (sections 1, 3, 7, 14, 19)
- `research/math-paper/NOVELTY_AUDIT.md`
- `research/math-paper/PRIOR_ART_MATRIX.csv`
- `docs/mission/NOVELTY_CLASSIFICATION.md`
- `research/evidence_semantics/PRIOR_ART_MATRIX.md`
- `research/frontier_selection/LITERATURE_FRONTIER_MAP.md`
- `research/frontier_selection/PRIMARY_SOURCE_INDEX.csv` (rows S001–S012,
  S043–S069, S080)

Earlier searches recorded in those files were **not rerun** unless listed
below. Where they are reused, they are marked RP in the bibliography.

## 3. Queries, in the order run

"Hit" names the source kept; the ids are in the bibliography. "FP" marks
false positives.

| # | exact query | domain(s) | kept | notes |
|---|---|---|---|---|
| Q1 | `Chow Willsky 1984 "Analytical redundancy and the design of robust failure detection systems"` | 5 analytical redundancy | B05 | — |
| Q2 | `Willsky 1976 "A survey of design methods for failure detection in dynamic systems" Automatica` | 1 FDI | B01, P11 | P11 surfaced as a side result |
| Q3 | `Reiter 1987 "A theory of diagnosis from first principles" Artificial Intelligence consistency-based diagnosis` | 6, 7, 45 | B28 | — |
| Q4 | `de Kleer Williams 1987 "Diagnosing multiple faults" GDE candidate generation conflicts` | 6, 7 | B29 | — |
| Q5 | `Cordier Dague Staroswiecki Travé-Massuyès 2004 "Conflicts versus analytical redundancy relations" DX FDI bridge` | 5, 7 | B27 | — |
| Q6 | `Frank 1990 "Fault diagnosis in dynamic systems using analytical and knowledge-based redundancy" Automatica survey` | 1, 11 | B06 | — |
| Q7 | `Isermann Ballé 1997 "Trends in the application of model-based fault detection and diagnosis of technical processes" terminology fault detection isolation identification` | 1 | B07 | — |
| Q8 | `Gertler structured residuals fault signature matrix isolation "Fault Detection and Diagnosis in Engineering Systems" 1998` | 10, 13 | B08, P19 | — |
| Q9 | `Blanke Kinnaert Lunze Staroswiecki "Diagnosis and Fault-Tolerant Control" structural analysis isolability book` | 12, 22 | B09 | — |
| Q10 | `Mosterman Biswas "Diagnosis of continuous valued systems in transient operating regions" TRANSCEND fault signatures` | 16, 17 | B37, P13 | **key**: transient versus steady-state signatures |
| Q11 | `Brusoni Console Terenziani Theseider Dupré "A spectrum of definitions for temporal model-based diagnosis" 1998` | 17 | B32 | — |
| Q12 | `Daigle Koutsoukos Biswas "A qualitative event-based approach to continuous systems diagnosis" relative measurement orderings` | 16, 17 | B38, B39 | — |
| Q13 | `Meseguer Puig Escobet "fault signature dynamics" timed fault signatures residual activation order diagnosis interval observers` | 13, 17 | B40, P14 | — |
| Q14 | `Zhang Li 1998 "Detection and diagnosis of sensor and actuator failures using IMM estimator" IEEE Transactions Aerospace Electronic Systems` | 9, 20, 21 | B43 | — |
| Q15 | `Maybeck multiple model adaptive estimation detecting sensor and actuator/surface failures aircraft flight control 1999` | 8, 22 | B44, B107 | — |
| Q16 | `"double-model adaptive fault detection and diagnosis" real flight data sensor faults actuator faults Lu van Eykeren van Kampen Chu` | 20, 31 | B45 | — |
| Q17 | `distinguish actuator fault from sensor fault isolation same symptom closed-loop "sensor fault" "actuator fault" discrimination` | 20, 21 | P03, P04, P05 | **key**: the EPOS family |
| Q18 | `"On-board estimator actuator system fault accommodation in engine control" patent assignee LVDT actuator sensor failure versus actuator hardware failure engine response` | 50, 32 | P03, P05 | assignee not shown |
| Q19 | `Kobayashi Simon "bank of Kalman filters" aircraft engine sensor fault versus component fault health parameter diagnostics` | 32, 20 | B46, B47 | — |
| Q20 | `quadrotor actuator fault detection two-stage Kalman filter loss of effectiveness Amoozgar Chamseddine Zhang experimental` | 31, 21 | B48 | — |
| Q21 | `multirotor motor failure detection distinguish ESC RPM telemetry fault from rotor thrust loss using IMU attitude dynamics` | 31 | B51, B52, B53 | — |
| Q22 | `closed-loop fault diagnosis controller compensation masks fault "manipulated variable" control signal used as fault indicator feedback hides fault effect` | 22, 35 | B99, B100 | — |
| Q23 | `ArduPilot thrust loss detection motor imbalance "thrust boost" failed motor detection motor output saturation` | 31 | B55 | **key**: fielded compensation-as-evidence |
| Q24 | `PX4 failure detector actuator failure detection FD_ACT_EN ESC current motor failure detection documentation` | 31 | B56 | the latch rationale |
| Q25 | `control effort based fault detection multirotor "control allocation" residual actuator effectiveness estimation incremental nonlinear dynamic inversion fault detection` | 23, 31 | B54 | — |
| Q26 | `Vehicle Integrated Prognostic Reasoner VIPR Honeywell NASA vehicle-level reasoning ambiguity groups fault conditions` | 2, 3 | B59 | — |
| Q27 | `Honeywell Boeing 777 central maintenance computer fault isolation cascaded effects "Aircraft Diagnostic and Maintenance System" fault model reasoning` | 2 | B58, P12 | — |
| Q28 | `R2U2 Reinbacher Rozier Schumann temporal logic runtime observer Bayesian network system health management unmanned aerial systems sensor failure` | 30, 47 | B67 | **key** |
| Q29 | `Aaseng 2001 "Blueprint for an integrated vehicle health management system" DASC` | 2 | B57 | — |
| Q30 | `Schumann Mbaya Mengshoel Rozier "Towards real-time, on-board, hardware-supported sensor and software health management for unmanned aerial systems" sensor failure versus system failure` | 30, 31 | B68 | — |
| Q31 | `Williams Nayak 1996 Livingstone "A model-based approach to reactive self-configuring systems" mode identification reconfiguration Deep Space One` | 6, 42 | B66 | — |
| Q32 | `HyDE hybrid diagnosis engine NASA Ames Narasimhan Brownston 2007 candidates consistency` | 16 | B42 | — |
| Q33 | `TEAMS multi-signal flow graph Deb Pattipati 1995 testability fault diagnosis ambiguity group D-matrix` | 13, 14 | B62 | — |
| Q34 | `Sha 2001 "Using simplicity to control complexity" Simplex architecture IEEE Software runtime assurance` | 26, 27 | B79 | — |
| Q35 | `Schierman runtime assurance framework AFRL "highly adaptive flight control" 2015 technical report run time assurance` | 26, 49 | B80, B81 | — |
| Q36 | `receiver autonomous integrity monitoring fault detection and exclusion "integrity not available" protection level alert limit ARAIM` | 41 | B87 | **key** for the assurance semantics |
| Q37 | `Henry Clarke 1993 "The self-validating sensor: rationale, definitions and examples" measurement value status CLEAR BLURRED DAZZLED BLIND` | 20 | B89 | FP: the tool's first follow-up returned art-auction and baseball pages for "Henry Clarke" |
| Q38 | `guaranteed fault diagnosis set-valued observers "guaranteed" isolation no false isolation bounded uncertainty Rosa Silvestre Shamma Athans` | 44 | B72, B73, B112 | — |
| Q39 | `Choi Lee Kim Xu 2018 "Detecting Attacks Against Robotic Vehicles: A Control Invariant Approach" CCS` | 40 | B92, B115 | — |
| Q40 | `SAVIOR securing autonomous vehicles physical invariants CUSUM drone sensor attack detection USENIX Security 2020 Quinonez` | 40 | B93 | — |
| Q41 | `Dempster-Shafer evidence theory multi-sensor fault diagnosis conflict "Basir" "Yuan" engine fault information fusion 2007` | 48 | B96 | — |
| Q42 | `automotive ESP yaw rate sensor plausibility monitoring vehicle model cross-check lateral acceleration steering angle wheel speed sensor fault detection Bosch` | 20 (automotive analogue) | B90, B114, P23 | — |
| Q43 | `Krysander Åslund Nyberg 2008 minimal structurally overdetermined sets MSO algorithm model-based diagnosis IEEE SMC` | 12 | B24 | — |
| Q44 | `structural analysis fault isolability UAV MAVLink structural model Dulmage-Mendelsohn multirotor actuator sensor faults` | 12, 31 | (earlier repository record S051) | — |
| Q45 | `Sampath Sengupta Lafortune Sinnamohideen Teneketzis 1995 "Diagnosability of discrete-event systems" IEEE TAC` | 43 | B36 | — |
| Q46 | `Bauer Leucker Schallhart three-valued LTL runtime verification inconclusive verdict "?" LTL3 monitors 2011 TOSEM` | 47 | B70 | — |
| Q47 | `ConSerts conditional safety certificates runtime Schneider Trapp dynamic assurance case runtime certification evidence` | 29, 49 | B84 | — |
| Q48 | `automated contingency management propulsion Tang Kacprzynski diagnosis prognosis reconfiguration decision making aircraft 2007` | 42, 4 | B97 | — |
| Q49 | `Niemann 2006 "A setup for active fault diagnosis" IEEE TAC auxiliary input design Campbell Nikoukhah` | 24, 25 | B74, B75 | — |
| Q50 | `fault isolation "temporal validity" of residuals transient window "valid only during" fault onset evidence time window diagnosis observability window closes compensation` | 17 | — | **no match for the term "temporal validity"**; transient-state reachable-set isolation seen |
| Q51 | `"fault accommodation" hides fault "observability" after reconfiguration active fault tolerant control diagnosis detectability loss integrated design FDI and FTC interaction` | 22 | — | generic FTC material only |
| Q52 | `"diagnosability" "evidence" sufficiency runtime "cannot be isolated" report "ambiguity group" aircraft fault isolation onboard "isolation to ambiguity group" LRU` | 14, 29 | P06, P07 | **key** patents |
| Q53 | `IEEE 1232 AI-ESTATE standard diagnostic reasoner outcomes fault tree D-matrix diagnostic inference model` | 13, 49 | B63 | — |
| Q54 | `"System fault isolation and ambiguity resolution" patent US11061390 assignee inventors filed` | 50 | P06 (RTX; Volponi, Tang, Lee) | FP: unrelated network and data-centre fault-isolation patents |
| Q55 | `"structural-temporal analysis of fault propagation graphs" patent US12134484 assignee` | 50 | P07 | assignee not shown; FP: spatio-temporal GNN papers |
| Q56 | `patent unmanned aerial vehicle detect motor failure compare expected angular acceleration IMU with motor commands propeller damage detection Amazon Technologies` | 50, 31 | P09, P20 | FP: parachute stall-detection papers |
| Q57 | `patent aircraft actuator fault detection using aircraft response distinguishing actuator failure from actuator position sensor failure flight control surface` | 50, 21 | P01, P02, P10 | **key**: P01 (1987) |
| Q58 | `Lerner Parr Koller Biswas 2000 "Bayesian fault detection and diagnosis in dynamic systems" AAAI dynamic Bayesian network hybrid` | 15, 16 | B35 | — |
| Q59 | `Beard 1971 failure detection filter Jones 1973 "failure detection in linear systems" observer-based fault detection history` | 11 | B03 | — |
| Q60 | `Potter Suman 1977 "Thresholdless redundancy management with arrays of skewed instruments" parity space inertial sensors` | 10 | B04 | — |
| Q61 | `Basseville Nikiforov 1993 "Detection of Abrupt Changes: Theory and Application" book GLR CUSUM Willsky Jones 1976 generalized likelihood ratio` | 18, 19 | B10, B02 | — |
| Q62 | `sensor fault that mimics actuator fault indistinguishable faults isolability "actuator fault" "sensor fault" same signature non-isolable pair structural isolability` | 12, 20, 21 | B23, B25 | — |
| Q63 | `false data injection attack mimicking actuator fault UAV ESC telemetry spoofing motor RPM telemetry falsified detection` | 40 | — | **no ESC/RPM-telemetry spoofing literature returned**; GPS/IMU dominated (FP) |
| Q64 | `diagnostic competition DXC blind evaluation hidden test scenarios false isolation metric Kurtoglu 2009 "first international diagnosis competition"` | benchmarking | B65 | blind (hidden-scenario) evaluation **not confirmed** by the summary |
| Q65 | `preregistered experiment robotics fault detection evaluation preregistration "pre-registered" cyber-physical systems experimental methodology blinded analysis` | methodology | — | **no match**; FP: generic CPS fault-detection papers |
| Q66 | `quadrotor rotor speed sensor fault versus motor fault isolation Freddi Longhi Monteriù model-based fault diagnosis mini quadrotor` | 31 | B49 | — |
| Q67 | `Denney Pai Habli 2015 "Dynamic safety cases for through-life safety assurance" ICSE runtime evidence assurance case` | 29 | B85 | — |
| Q68 | `Hawkins Kelly Knight Graydon 2011 "A new approach to creating clear safety arguments" assurance claim points confidence argument evidence sufficiency` | 29 | B86 | — |
| Q69 | `exoneration assumption consistency-based diagnosis "no exoneration" component not in conflict not exonerated physical impossibility fault models GDE+ Struss Dressler` | 45 | B30 | — |
| Q70 | `patent vehicle health management cross-subsystem evidence hypotheses consistent physical model reasoner determines root cause across subsystems aircraft "hypothesis" "evidence" monitors` | 50, 2 | B60, P18 | — |
| Q71 | `patent run time assurance monitor switching to backup controller based on health of sensors aircraft "run time assurance" autonomous flight` | 50, 26 | B82 (via NTRS) | no patents returned (papers only) |
| Q72 | `patent validating sensor telemetry using physical response of vehicle "plausibility" motor speed sensor validated with inertial measurement multicopter` | 50 | P21 | FP: crash-sensor and telematics patents |
| Q73 | `"Method and system for detecting a failure or performance degradation in a dynamic system such as a flight vehicle" patent 6643569 assignee` | 50 | P11 (U. Michigan) | FP: Honeywell patent-sale lists |
| Q74 | `Venkatasubramanian Rengaswamy Yin Kavuri 2003 "A review of process fault detection and diagnosis" part I quantitative model-based methods signed digraph` | 1, 14 | B14 | — |
| Q75 | `Iri 1979 signed directed graph fault diagnosis chemical process cause-effect graph Kramer Palowitch 1987 rule-based SDG` | 14 | B15, B16, B17 | — |
| Q76 | `"Vehicle-Level Reasoning Systems" chapter NASA integrating system-wide data health state authors` | 2, 38 | B60, B108, B109 | — |
| Q77 | `Narasimhan Biswas 2007 "Model-based diagnosis of hybrid systems" IEEE Transactions Systems Man Cybernetics mode changes fault signatures` | 16 | B41, B111 | — |
| Q78 | `GNSS INS integrated navigation integrity monitoring solution separation fault detection exclusion inertial coasting protection level aviation` | 41 | B88 | — |
| Q79 | `Copilot NASA runtime verification stream language flight software monitors Pike Goodloe 2010 embedded` | 47 | (background only) | not cited as a claim source |
| Q80 | `Johansen Fossen 2013 "Control allocation — A survey" Automatica actuator failure reconfiguration effectiveness` | 23 | B20 | — |
| Q81 | `Zhang Jiang 2008 "Bibliographical review on reconfigurable fault-tolerant control systems" Annual Reviews in Control FDD FTC integration` | 22 | B19 | — |
| Q82 | `Cristofaro Johansen fault tolerant control allocation unknown input observers actuator fault isolation over-actuated marine vessel Automatica 2014` | 23, 24 | B21 | — |
| Q83 | `digital twin fault diagnosis aircraft physics-based model real-time diagnosis uncertain disambiguation Matei de Kleer "System resilience through health monitoring and reconfiguration"` | 36, 39 | B76 | — |
| Q84 | `cross-layer fault diagnosis cyber-physical systems distinguishing cyber attack from physical fault sensor fault versus attack discrimination` | 33, 34, 35 | B94 | — |
| Q85 | `qualitative reasoning diagnosis Kuipers QSIM 1986 "Qualitative simulation" de Kleer Brown qualitative physics confluences` | 46 | B33, B34 | — |
| Q86 | `Dunia Qin Edgar McAvoy 1996 "Identification of faulty sensors using principal component analysis" sensor validity index distinguish sensor fault from process change` | 20 | B22 | — |
| Q87 | `multirotor fault isolation using ESC rotor speed telemetry and gyroscope distinguish rotor speed sensor fault from motor loss of effectiveness analytical redundancy` | 31, 20 | B50, P15 | — |
| Q88 | `gas turbine engine sensor bias versus component performance deterioration discrimination Volponi gas path analysis sensor error estimation` | 32 | — | gas-path deterioration discrimination; nothing new for the matched set |
| Q89 | `FAA technical report run-time assurance certification adaptive flight control verification "run time monitoring" DOT/FAA/TC` | 49 | B82, B83, B113, P08 | — |
| Q90 | `patent US12087171 "Assurance module" assignee claims autonomy runtime` | 50 | P08 | FP: software-assurance patents |
| Q91 | `patent "ambiguity group" aircraft health management "insufficient evidence" diagnostic reasoner declines to isolate fault report ambiguity Honeywell Boeing` | 50 | P17 | **no patent with explicit refusal semantics surfaced** |
| Q92 | `patent "control effort" OR "controller output" used to detect actuator degradation aircraft "compensat" actuator effectiveness monitoring flight control law integrator` | 50 | P16 | — |
| Q93 | `patent causal consistency monitoring cyber-physical anomaly "physically consistent" hypotheses elimination vehicle multi-domain sensors root cause "consistency"` | 50, 35 | B116 | FP: microservice RCA; **term collision**: "temporal consistency" means data timing |
| Q94 | `MIL-STD-2165 testability fault isolation requirement ambiguity group percentage false alarm "cannot duplicate" misdiagnosis BIT metrics` | 14, 29 | B64 | — |
| Q95 | `Hwang Kim Kim Seah 2010 "A survey of fault detection, isolation, and reconfiguration methods" IEEE Transactions on Control Systems Technology` | 1, 22 | B18 | — |
| Q96 | `Blom Bar-Shalom 1988 interacting multiple model algorithm Markovian switching coefficients IEEE TAC; Magill 1965 optimal adaptive estimation sampled stochastic processes` | 8, 9 | B12, B13 | — |
| Q97 | `system health management ambiguity "not diagnosable" onboard reasoning "diagnostic uncertainty" guidance decision "fault ambiguity" autonomous spacecraft mission safe mode decision under ambiguous diagnosis` | 42, 43 | (safe-mode practice; no single cited source) | — |
| Q98 | `UAV health management onboard reasoning Valenti Bethke How "health management" UAV MIT mission planning actuator degradation health-aware planning` | 30, 39 | B98 | — |
| Q99 | `physics-informed anomaly detection UAV flight data residual dynamics model telemetry validation "physics-based" consistency check drone logs` | 37 | — | recent physics-informed ML anomaly detectors; detection, not attribution |
| Q100 | `fault detectability window closed-loop transient before controller compensation "detectable only during transient" feedback compensates actuator fault becomes undetectable steady state` | 17, 22 | — | **no named formalization found**; FP: "disturbance quelling" patents |
| Q101 | `system-of-systems health management cross-subsystem fault propagation aircraft "integrated system health management" NASA ISHM Figueroa Schmalzel knowledge-based anomaly root cause` | 3, 38 | B61, B110 | — |
| Q102 | `Console Torasso 1991 "A spectrum of logical definitions of model-based diagnosis" abductive consistency-based covering explanation Computational Intelligence` | 45 | B31 | **key** for the verdict logic |
| Q103 | `Pulido Alonso-González 2004 "Possible conflicts" consistency-based diagnosis dynamic systems structural IEEE SMC` | 7, 12 | B26 | — |
| Q104 | `"cross-sensor" consistency trust graph sensor nodes edges physical relationships trust score UAV sensor fusion fault isolation "trust" Beta reputation sensor network` | 20, 5 | B95 | FP: GNN tracking |
| Q105 | `diagnosis "not measurable" observation unavailable three-valued predicate Kleene logic model-based diagnosis unknown observations "missing observations" candidates not eliminated` | 43, 45 | — | Kleene K3 background; FP: a learning paper on K3 |
| Q106 | `quadrotor experiment distinguishing propeller or motor degradation from rotor speed sensor fault same symptom isolation experimental comparison loss of effectiveness versus sensor bias` | 31 | B106 | **no matched-construction experiment found** |
| Q107 | `runtime diagnosability certificate formal "diagnosis certificate" guarantee fault isolation correctness proof-carrying diagnosis` | 43, 49 | B71, B101, P22 | FP: software-fault-isolation sandboxing (**term collision**) |
| Q108 | `"multiple hypothesis" fault isolation aircraft "indistinguishable" report set of candidate faults conservative decision "reconfiguration" only after unique isolation aircraft flight control FDIR policy` | 22, 42 | — | **no source stating "reconfigure only after unique isolation"** |
| Q109 | `"Formal design of asynchronous fault detection and identification components using temporal epistemic logic" authors journal correctness completeness FDI requirements` | 43, 47 | B71 | — |
| Q110 | `"A Unified Framework for Runtime Verification and Model-Based Diagnosis in LOLA" 2026 authors` | 47 | B69 | — |

Where the search tool issued its own follow-up searches, as in Q37, Q54,
Q56, Q61 and Q73, only the kept results are recorded.

## 4. Coverage of the fifty required domains

Domain numbers follow the order of the brief. Two statuses are used:

- **searched**: one or more dedicated queries.
- **partial**: covered only through a related query or the repository's
  earlier records.

| domain | status | queries |
|---|---|---|
| 1 FDI | searched | Q2, Q6, Q7, Q74, Q95 |
| 2 IVHM | searched | Q26, Q27, Q29, Q70 |
| 3 ISHM | searched | Q101 |
| 4 PHM | partial | Q48, Q64, Q88 |
| 5 analytical redundancy | searched | Q1, Q5 |
| 6 model-based diagnosis | searched | Q3, Q4, Q31 |
| 7 consistency-based diagnosis | searched | Q3, Q4, Q5, Q103 |
| 8 MMAE | searched | Q15, Q96 |
| 9 IMM | searched | Q14, Q96 |
| 10 parity space | searched | Q60, Q8 |
| 11 observer-based FDI | searched | Q59, Q6 |
| 12 structural analysis | searched | Q9, Q43, Q44, Q62 |
| 13 fault signature matrices | searched | Q8, Q13, Q33 |
| 14 causal graphs / Bayesian networks | searched | Q75, Q33 |
| 15 dynamic Bayesian networks | searched | Q58 |
| 16 hybrid diagnosis | searched | Q32, Q77 |
| 17 temporal diagnosis | searched | Q10, Q11, Q12, Q13, Q50, Q100 |
| 18 sequential change detection | searched | Q61 (earlier repository record: Page 1954) |
| 19 CUSUM / GLR / SPRT | searched | Q61; SPRT not separately searched |
| 20 sensor FDI | searched | Q37, Q86, Q42, Q87 |
| 21 actuator FDI | searched | Q14, Q17, Q57, Q62 |
| 22 fault-tolerant control | searched | Q9, Q15, Q81 |
| 23 control allocation | searched | Q80, Q82, Q25 |
| 24 active fault diagnosis | searched | Q49, Q82 |
| 25 active diagnosis / probing | searched | Q49, Q21 (null-space excitation) |
| 26 runtime assurance | searched | Q34, Q35, Q71 |
| 27 Simplex | searched | Q34 |
| 28 safety filters / runtime monitors | partial | Q34, Q46; earlier repository records S001–S010, S080 |
| 29 assurance cases / evidence sufficiency | searched | Q47, Q67, Q68 |
| 30 autonomous vehicle health management | searched | Q28, Q30, Q98 |
| 31 UAV fault diagnosis | searched | Q20, Q21, Q23, Q24, Q66, Q87, Q106 |
| 32 propulsion health monitoring | searched | Q18, Q19, Q88 |
| 33 cross-domain anomaly detection | partial | Q84, Q93 |
| 34 cross-layer diagnosis | searched | Q84 |
| 35 CPS diagnosis | searched | Q84, Q93, Q22 |
| 36 digital twins for diagnosis | searched | Q83 |
| 37 physics-informed anomaly detection | searched | Q99 |
| 38 system-of-systems health management | partial | Q101, Q76 |
| 39 resilient autonomy | partial | Q83, Q98 |
| 40 sensor spoofing / integrity | searched | Q39, Q40, Q63 |
| 41 GNSS/INS integrity | searched | Q36, Q78 |
| 42 contingency management | searched | Q48, Q97 |
| 43 partial observability | partial | Q45, Q105; earlier repository records S043–S049 |
| 44 set-based diagnosis | searched | Q38 |
| 45 abductive / consistency-based | searched | Q69, Q102 |
| 46 qualitative reasoning | searched | Q85 |
| 47 temporal-logic runtime monitoring | searched | Q28, Q46, Q79, Q109, Q110 |
| 48 Dempster–Shafer | searched | Q41 |
| 49 aviation assurance / runtime certification | searched | Q35, Q89 |
| 50 patents | searched | Q18, Q54–Q57, Q70–Q73, Q90–Q93 |

## 5. Citation trails followed

- Mosterman & Biswas (B37) → Daigle, Koutsoukos & Biswas (B38) → QED with
  possible conflicts (B39) → Pulido & Alonso-González (B26).
- R2U2 TACAS 2014 (B67) → UAS SHM, PHM 2013 / IJPHM 2015 (B68) →
  "Toward runtime assurance of complex systems with AI components" (the RTA
  switch).
- VIPR (B59) → the vehicle-level reasoning systems chapter (B60).
- Kobayashi & Simon (B46) → the engine "on-board estimator" patent family
  (P03–P05) → the RTX ambiguity-resolution patent (P06; inventor Volponi is
  also a gas-path-analysis author).
- The Amazon propeller search → P09 and P20.
- The aircraft actuator-versus-position-sensor patent search → P01 (1987),
  which is the earliest direct antecedent of the XSYS-001 discrimination idea
  found.
- The earlier repository records S049, S054, S055 and S080 → B102, B73, B09,
  and the finding that "diagnostic ambiguity → control authority" is saturated.

## 6. Promising sources that must be read in full before any claim

| priority | source | why |
|---|---|---|
| 1 | B59 VIPR final report | whether it ranks toward a single cause or refuses without discriminating evidence (decides R3) |
| 2 | B68 / B67 R2U2 SHM | its output semantics under sensor-versus-real-failure ambiguity (decides C12) |
| 3 | P03–P05 EPOS patents, full claims | how broadly they claim actuator-sensor versus actuator-hardware discrimination through plant response (XSYS question 1) |
| 4 | B69 Hipler, Leucker & Rodler 2026 | the RV + MBD unification (C12) |
| 5 | B37, B38, B41, B42 | whether any represents out-of-window evidence as inapplicable (C6) |
| 6 | B71 Bozzano et al. | the exact correctness requirement against zero-WRONG (C17) |
| 7 | P06 RTX ambiguity resolution | claim scope over evidence-based ambiguity resolution |
| 8 | ArduPilot `AP_MotorsMatrix` thrust-loss logic; PX4 failure detector source | the exact fielded compensation logic (C4) |

## 7. Not searched: known gaps

These are listed so that no absence below can be read as evidence:

- SAE IVHM standards: ARP6803, AIR6900, JA6268.
- HUMS credit guidance: FAA AC 29-2C, MG-15.
- ARP4754A / ARP4761 common-cause and zonal analyses.
- The ProDiMES engine diagnostic benchmark.
- PHM Society data-challenge rules.
- DShot / CAN ESC-telemetry fault-injection literature.
- The SPRT (Wald) literature, specifically.
- The registered-reports literature in robotics.
- European patents beyond EP equivalents surfaced incidentally.
- Chinese-language literature and CN patents, except one incidental hit.

---

# Stage 2: source verification and novelty-boundary searches

This stage was run on 2026-09-27, the same session as stage 1, and is still
independent of XSYS-001. No campaign artifact was opened. The broad-audit
record above is unchanged. This section is appended.

## S2.1 Access retest

| route | result |
|---|---|
| `curl` to crossref, doi.org, NTRS, arXiv, Google Patents, the USPTO PDF host, freepatentsonline, Justia, ardupilot.org, docs.px4.io, NASA DASHlink, LMCS, HAL, IRISA, AAAI, PHM Society, MDPI, Wiley, Springer, MIT, UT Austin, Linköping, FBK, York, DTIC, DLR, CSIC, PMC, USENIX, NSF PAR, ROSA P, FAA, NTNU, Vanderbilt ISIS | **blocked** (HTTP 000/403; policy denial) |
| `curl` to `github.com`, `codeload.github.com`, `api.github.com`, `*.github.io` | **blocked** (403 / 000) |
| `curl` to `raw.githubusercontent.com` | **reachable (200)**: the only route to primary text |
| local PX4 source clone at commit `547e2caa9883bc1609325f02b4914b4e2482fe62`, including `docs/en/` (the XSYS-001 apparatus tree; its one added commit, the SIH effectiveness patch, leaves every inspected file unchanged) | **available**. Primary source for PX4. Source code only; no campaign artifact was opened |
| `pdftotext` | installed, but no primary PDF was reachable |

## S2.2 Primary sources inspected

| id | file | route | verification level |
|---|---|---|---|
| B130 | ArduPilot `libraries/AP_Motors/AP_MotorsMatrix.cpp` (`check_for_failed_motor`), `ArduCopter/crash_check.cpp` (`thrust_loss_check`, `yaw_imbalance_check`) | raw.githubusercontent.com, branch `master`, fetched 2026-09-27 | **V4** (function level, line ranges recorded) |
| B130 | ArduPilot wiki `copter/source/docs/thrust_loss_yaw_imbalance.rst` | raw.githubusercontent.com, `master` | **V3** |
| B131 | PX4 `src/modules/commander/HealthAndArmingChecks/checks/escCheck.cpp` L314–328; `src/modules/commander/failure_detector/FailureDetector.cpp`; `docs/en/config/motor_failure_recovery.md` L91–92 | local tree at `547e2ca` | **V4** |
| B132 | R2U2 repository `README.md` | raw.githubusercontent.com, `main` | V2 (the tool, not the 2013/2015 health-management paper) |
| B133 | CPS_Invariant repository `README.md` (Choi et al.'s artifact) | raw.githubusercontent.com, `master` | V2 (the artifact, not the paper) |
| B134 | pyfaultdiagnosistoolbox `README.md` | raw.githubusercontent.com, `master` | V2 |

## S2.3 Stage-2 queries (web search), in order

| # | exact query | kept | notes |
|---|---|---|---|
| S2Q0a | `github "Diagnosis of continuous valued systems in transient operating regions" pdf` (restricted to GitHub domains) | — | no GitHub-hosted copy |
| S2Q0b | `github pdf "A theory of diagnosis from first principles" Reiter` (restricted to GitHub domains) | — | no GitHub-hosted copy |
| S2Q0c | `github fault diagnosis toolbox structural analysis Frisk Krysander isolability documentation` (restricted to GitHub domains) | B134 | the manual is on github.io, which is blocked |
| S2Q1 | `temporal structural fault diagnosis aircraft transient steady state fault signature candidate elimination` | — | ML-dominated. Notes engine faults that show no steady-state symptom |
| S2Q2 | `controller compensation used as evidence fault isolation actuator loss of effectiveness versus sensor fault "control effort" diagnosis` | — | FTC compensation literature; LOE from desired against actual rate |
| S2Q3 | `motor fault versus RPM sensor fault discrimination multirotor UAV IMU body rates isolation` | — | **no discrimination study found** |
| S2Q4 | `actuator fault versus actuator feedback sensor fault isolation closed-loop "control signal" residual distinguishes` | B117 | closed-loop masking of sensor faults; residual from controller-demanded signals |
| S2Q5 | `"Robust fault detection and isolation technique for single-input/single-output closed-loop control systems that exhibit actuator and sensor faults" authors journal` | B117 | metadata |
| S2Q6 | `quadrotor rotor speed measurement fault versus propeller damage isolation using commanded thrust and angular acceleration residual "rotor speed" sensor fault` | B53 | commanded thrust against measured acceleration; per-rotor thrust from IMU |
| S2Q7 | `"simultaneous actuator and sensor fault" diagnosis quadrotor UAV loss of effectiveness sensor bias isolation experimental` | B123, B124 | actuator LOE against **IMU** sensor bias; flight tests |
| S2Q8 | `fault signature matrix transient and steady-state phases closed-loop controller compensation diagnosis dynamic fault signature` | B118, B127 | **key**: compensation redistributes steady-state actuator-fault effects but not feedback-sensor faults |
| S2Q9 | `"Steady-State Fault Propagation Characteristics and Fault Isolation in Cascade Electro-Hydraulic Control System" feedback sensor fault actuator fault isolation` | B118 | no further detail |
| S2Q10 | `mode-dependent analytical redundancy relations validity residual only valid in operating mode hybrid system diagnosis "valid" residual activation` | B119 | **key**: ARRs valid per mode; mode-sequence ARRs |
| S2Q11 | `temporal diagnosability fault isolation time window "detectable only" transient closed loop fault masking diagnosis timing phase-dependent residual` | B128, B129 | fault masking and compensation create signature sequences |
| S2Q12 | `exoneration fault diagnosis "fault would have been detected" residual sensitivity threshold exoneration condition structured residuals isolation logic` | B138 | expected residual magnitude sets sensitivity |
| S2Q13 | `"Overcoming Non-Discernibility through Mode-Sequence Analytic Redundancy Relations" authors year PHM` | B119 | metadata |
| S2Q14 | `health-aware control authority degraded mode diagnosis confidence reconfiguration only when fault isolated with confidence aircraft "health state" permitted maneuvers envelope` | P24 | **key patent**: health score from risk, confidence and benefit before reconfiguration |
| S2Q15 | `runtime assurance integrated with health management diagnosis switching recovery controller based on diagnosed fault UAV "health management" "runtime assurance"` | B139 | — |
| S2Q16 | `diagnosis under uncertainty decision making autonomous aircraft ambiguous fault candidate set contingency action selection robust to all candidates` | B120 | a maneuver to prune ambiguous sensor suspects is described; **source not attributable** (UNCLEAR) |
| S2Q17 | `"Fault-Adaptive Autonomy in Systems with Learning-Enabled Components" authors Sensors 2021 diagnosis contingency management UAV` | B120 | an AUV, not a UAV |
| S2Q18 | `"Vehicle health management systems and methods" patent 9725187 health score risk confidence benefit reconfiguration actuator assignee` | P24 | — |
| S2Q19 | `fault isolation integrity bound probability of wrong isolation "misdiagnosis" risk bound certified diagnosis protection level analogy hypothesis testing isolation guarantee` | B135, B136 | probability-of-false-isolation bounds |
| S2Q20 | `diagnosis output "insufficient evidence" versus "ambiguous" versus "no fault" verdict categories health monitoring explicit unknown state reasoner abstain` | B137 | an explicit INSUFFICIENT_EVIDENCE verdict in another domain |
| S2Q21 | `Lai 2000 "Sequential multiple hypothesis testing and efficient fault detection-isolation in stochastic systems" false isolation probability Nikiforov change detection isolation` | B121, B122 | **key** for zero-WRONG |
| S2Q22 | `UAV propulsion health monitoring ESC telemetry fault injection DShot telemetry spoofing or corrupted RPM feedback detection` | — | **no ESC-telemetry corruption literature found** |
| S2Q23 | `"actuator effectiveness" estimation multirotor distinguished from "rotor speed sensor" fault rpm feedback loss of effectiveness vs sensor failure incremental nonlinear dynamic inversion` | B125 | an INDI split between actuator dynamics and actuator effectiveness using RPM (source not attributable in the summary) |
| S2Q24 | `integrated vehicle health management ambiguity diagnosis temporal evidence cross subsystem UAV architecture "health management" reasoner candidate set temporal` | B126 | the VLRS chapter's temporal latching and trend windows |
| S2Q25 | `"On-board estimator actuator system fault accommodation in engine control" priority date assignee United Technologies OR "General Electric" OR "Pratt" inventors` | — | assignee and priority **not shown** |
| S2Q26 | `US12134484 "contextually-informed fault diagnostics" assignee Boeing OR Honeywell OR "GE Aviation" filed` | P07 | Boeing; Keller, Wang, Ethington |
| S2Q27 | `US12087171 "Assurance module" run-time assurance aerospace assignee BAE OR Airbus OR Thales OR Boeing` | P08 | assignee not shown; an input manager, safety manager and switch |
| S2Q28 | `US20100017049 "Vehicle Health Management Systems and Methods" Boeing Swearingen risk value confidence value benefit value health score` | P24 | Boeing; Swearingen, Keller; published 2010-01-21 |

**Field evidence surfaced in stage 1 (Q24) and re-examined here.** A PX4
issue, "[Bug] False motor failure detected with Dshot telemetry" (#23734),
and a PX4 forum thread on missing ESC-telemetry current triggering motor-
failure warnings show that telemetry defects trip local motor-failure logic in
practice (B140, V0; GitHub issues are not reachable through
raw.githubusercontent.com).

## S2.4 Late combination and exact-instance queries

The brief's own example queries for the combination search (its Step 5) were
checked against S2Q1–S2Q28. Five had no close counterpart, so they were run
nearly verbatim (S2Q29, S2Q30, S2Q31, S2Q34, S2Q37). Eight follow-up queries
came out of their results.

| # | exact query | kept | notes |
|---|---|---|---|
| S2Q29 | `physical response telemetry validation actuator fault versus feedback sensor fault vehicle dynamics` | — | steer-by-wire and drive-by-wire FDI (IMM; simultaneous actuator and sensor faults); EPOS patents resurfaced |
| S2Q30 | `control allocation residual actuator fault isolation multirotor controller command imbalance diagnosis motor` | B141 | an FDI module that uses ESC motor speeds and currents to separate **motor failure from propeller damage**, next to an IMU observer (attribution to one paper unconfirmed) |
| S2Q31 | `consistency based diagnosis dynamic systems temporal validity of observations transient fault candidate set` | B142, B143 | "a fault is detected only if the residual detects a fault **and is in its validity region**" |
| S2Q32 | `"Actuator fault detection and isolation system for multirotor unmanned aerial vehicles" electronic speed controller motor speeds currents distinguish motor failure propeller damage` | B141 | the attribution is still not confirmed |
| S2Q33 | `"validity region" residual consistency-based diagnosis data-driven residuals fault detected only if residual in its validity region` | B142 | validity region = the operating region covered by the residual's training data (out-of-distribution guard), not a time window |
| S2Q34 | `closed-loop compensation signature actuator fault masked steady state transient response used to distinguish sensor fault from actuator fault diagnosis` | B118, B144 | B118 summary restated: feedback removes the steady-state effect of actuator faults "except for the feedback sensor fault" |
| S2Q35 | `"actuator sensor failure" "actuator hardware failure" engine response pressure differential feedback actuator response signal drifts below requested control signal on-board estimator` | P03, P04, P05, P25 | **key**: the search engine rendered EPOS patent text (quoted below) |
| S2Q36 | `multirotor RPM sensor fault ESC telemetry fault detection IMU cross-check rotor speed measurement faulty versus motor degradation` | B146, P15 | field reports of unreliable ESC RPM telemetry; the P15 speed-sensing logic |
| S2Q37 | `diagnosis action authority uncertainty autonomous aircraft fault isolation confidence permitted maneuvers contingency ambiguous diagnosis` | B145 | control-based FDI for autonomous aircraft (control objectives used to build residuals) |
| S2Q38 | `sensor fault that mimics actuator fault identical local residual signature indistinguishable distinguished using closed-loop plant response experiment` | — | no matched-by-construction experiment found; EPOS resurfaced; sensor faults can be recast as actuator faults |
| S2Q39 | `"On-board estimator effector drift detection in engine control" patent assignee filed` | P25 | assignee and filing date shown for the EPOS family (see P25) |
| S2Q40 | `fault diagnosis evaluation ablation using transient residual outside its valid time window after compensation causes misdiagnosis negative control experiment` | — | no directly matching work identified; ablation with omitted components is routine, which makes the XSYS-001 invalid-window control a specific form of a common practice |
| S2Q41 | `"Limits of Residual-Based Detection for Physically Consistent False Data Injection"` (the title surfaced in S2Q33) | B147 | security work that **constructs** corrupted measurements consistent with the physics so that residual detectors miss them. It is the security analogue of building case B to match case A's local symptom |

**EPOS patent text as rendered by the search engine (S2Q35; V0: the PDF host
`image-ppubs.uspto.gov` is still blocked, retested 2026-09-27).** The engine
text reads:

> "Both actuator sensor faults and actuator hardware faults experience an
> inability of the minor loop of the control law module to keep an error
> between the feedback actuator response signal and the requested control
> signal within required tolerance. However, the engine response during an
> actuator sensor failure is very different and distinguishable from the
> engine response during an actuator hardware failure."

It goes on to say that when the measured pressure differential is detected
during an actuator **sensor** failure, the feedback signal drifts **below** the
request; during an actuator **hardware** failure, it drifts **above** the
request and tracks the actual actuator response. The rendering does not say
which family member (P03, P04 or P05) the text comes from.

This is the strongest threat found to the XSYS-001 **question**. The shared
local symptom and the physical-response discriminator are both stated,
although on a different plant. See
`research/csia_novelty_audit/XSYS_001_EXACT_PRIOR_ART.md`.

**Mapping of the brief's example queries.**

| brief example | run as |
|---|---|
| temporal structural fault diagnosis aircraft | S2Q1 |
| temporal fault signature structural diagnosis | S2Q1, S2Q10, S2Q13 |
| controller compensation fault isolation actuator sensor | S2Q2, S2Q4 |
| physical response telemetry validation actuator | S2Q29 |
| actuator sensor fault discrimination vehicle dynamics | S2Q6, S2Q7, S2Q29 |
| cross subsystem diagnosis temporal evidence | S2Q24 |
| integrated vehicle health management ambiguity diagnosis | S2Q24 |
| fault isolation candidate set temporal | S2Q16, S2Q31 |
| consistency based diagnosis dynamic systems temporal | S2Q31 |
| fault signature matrix transient steady state | S2Q8 |
| runtime assurance health management diagnosis | S2Q15 |
| diagnosis action authority uncertainty autonomous aircraft | S2Q14, S2Q37 |
| fault isolation control response as residual | S2Q4, S2Q37 |
| control effort actuator fault diagnosis | S2Q2, S2Q30 |
| closed loop actuator sensor fault isolation | S2Q4, S2Q8, S2Q34 |

**Citation chains followed.** The chains were:

- B118 → its steady-state propagation premise (S2Q34);
- EPOS title → patent text → the effector-drift family member (S2Q35, S2Q39);
- B119 → the mode-sequence ARR title (S2Q13);
- B117 → metadata (S2Q5);
- the P24 family (S2Q18, S2Q28).

Forward citation of any source was impossible, because every citation index
is blocked.
