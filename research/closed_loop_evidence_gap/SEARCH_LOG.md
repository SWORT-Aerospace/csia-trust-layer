# Closed-loop evidence search log

Searches run on 2026-09-28. Source ids `Lnnn` are defined in
`research/closed_loop_evidence_gap/PROBLEM_LANDSCAPE.md` §2.

**The tool.** A web-search tool that returns titles, URLs and summaries.
Queries are recorded **verbatim**.

**Aim.** The aim was to **kill** each candidate problem by finding the
strongest existing work, in every field the brief lists and in fielded code.

## 1. Access attempts

| target | result |
|---|---|
| `https://arxiv.org/`, `https://export.arxiv.org/` | HTTP 000 (curl, 8 s) |
| `https://api.semanticscholar.org/`, `https://api.crossref.org/`, `https://api.openalex.org/` | HTTP 000 |
| `https://ntrs.nasa.gov/`, `https://www.ntsb.gov/` | HTTP 000 |
| `https://arxiv.org/abs/2002.06673` (fetch tool) | refused: `EGRESS_BLOCKED` |
| `https://raw.githubusercontent.com/` | reachable (HTTP 301 at root; files returned 200) |
| `https://github.com/treyra/s-FEAST`, `https://api.github.com/repos/treyra/s-FEAST` | HTTP 403 |

## 2. Files read at V4

Each file was fetched from raw.githubusercontent.com on 2026-09-28 at the
branch head named. The commit was not recorded, so the file hash identifies
the exact content read.

| id | file | SHA-256 |
|---|---|---|
| L009 | `treyra/s-FEAST` `master/readme.md` (`main/README.md` and other paths returned 404) | `72a900e55bc5ff38f61c711eebe56254c842fd301d0a8073d1bcbab28a5a0b12` |
| L063 | `PX4/PX4-Autopilot` `main/msg/versioned/VehicleLocalPosition.msg` | `4a24c882529ffaa71d834f0ef75e9cbacbe179db72b9227a13bca35205ccdd53` |
| L064 | `PX4/PX4-Autopilot` `main/src/modules/ekf2/EKF2Selector.cpp` | `e6cff5d668c6fa1054678cae4f034e87823351919dd3acc66dda17abb6bc9b0c` |
| L065 | `ArduPilot/ardupilot` `master/libraries/AP_NavEKF3/AP_NavEKF3.cpp` | `ec0cfed330da9c0754407bf493455a057693c06b913bac0a8fbaef4a6e7350a8` |
| L066 | `ArduPilot/ardupilot` `master/ArduCopter/ekf_check.cpp` | `84d95994ab848c60857c35a945e273a792377b65326981718bec136b5f1229ac` |
| L067 | `PX4/PX4-Autopilot` `main/src/modules/control_allocator/ControlAllocator.cpp` | `4139d45d21efce50ab08b2d16e8d44b403333cae9f92134b254d8993a75e2430` |
| L068 | `PX4/PX4-Autopilot` `main/src/modules/commander/failure_detector/FailureDetector.cpp` | `44d1d8718a3af1c3b427ba112b3770de943c3c65891005a32778038bc71091d5` |

Repository documents read at V4:

- `docs/research/XSYS_001_CONFIRMATORY_RESULT.md` (L069);
- `docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md` (L070);
- `research/active_evidence/RESULTS.md` (L071).

None was modified.

## 3. Queries

| # | exact query | kept | what it showed |
|---|---|---|---|
| CQ1 | `closed-loop system identification bias feedback correlation noise input direct approach Forssell Ljung` | L001 | input-noise correlation bias; direct, indirect and joint methods |
| CQ2 | `fault masking by feedback control closed-loop fault detection controller compensates hides fault` | L002, L014 | fault masking defined; adaptive controllers mask; detectability-performance trade-off paper |
| CQ3 | `integrated design fault detection and control interaction four-parameter controller Nett Jacobson Miller` | L003 | four-parameter controller, ACC 1988 |
| CQ4 | `"The negative impact of closed-loop control on fault detection"` | L002 | 2-DOF aircraft with six propeller faults; induction-motor closed-loop diagnosis |
| CQ5 | `Zhang Jiang issues on integration of fault diagnosis and reconfigurable control active fault-tolerant control FDD delay false alarm interaction` | L004 | integration issues in active FTC |
| CQ6 | `active fault diagnosis auxiliary input design closed-loop performance degradation trade-off Niemann Poulsen` | L005, L007 | closed-loop active diagnosis; YJBK; minimum performance degradation |
| CQ7 | `active fault detection and control unified formulation dual control Šimandl Punčochář detection objective control objective` | L006, L009 | unified formulation, Automatica 2009; s-FEAST found |
| CQ8 | `guaranteed active fault diagnosis safety constraints state constraints input design zonotope Scott Raimondo Braatz` | L007, L008 | zonotope input design; closed-loop version; arXiv 2606.19590 found |
| CQ9 | `safe diagnosability discrete event systems Paoli Lafortune diagnose before forbidden state` | L010 | safe diagnosability; active safe diagnosis |
| CQ10 | `active diagnosis discrete event systems Sampath Lafortune Teneketzis controller ensures diagnosability` | L011 | active diagnosis, IEEE TAC 1998; space on-board control procedures |
| CQ11 | `"Online tree-based planning for active spacecraft fault estimation and collision avoidance"` | L009 | s-FEAST details; code repository; data on Dryad |
| CQ12 | `"Safe, Real-Time Active Model Discrimination and Fault Diagnosis for Nonlinear Systems via Differentiable Reachability"` | L008 | quadrotor, fighter-jet model, hardware robot; under 50 ms; authors not in summary |
| CQ13 | `Livingstone mode identification reconfiguration Deep Space 1 Remote Agent commanded transitions model-based diagnosis Williams Nayak` | L012 | commands combined with observations; flown in 1999 |
| CQ14 | `time-varying confounding affected by prior treatment treatment-confounder feedback g-methods marginal structural models Robins` | L022 | treatment-confounder feedback; g-methods |
| CQ15 | `statistical inference with adaptively collected data bandit policy bias confidence intervals Hadad Zhang Janson Murphy` | L023 | adaptive weighting for valid inference |
| CQ16 | `performative prediction Perdomo decision-dependent distribution shift predictions change the outcome` | L024 | performative stability |
| CQ17 | `prognostic models will be victims of their own success clinical prediction model intervention changes outcomes monitoring calibration drift` | L025 | model-triggered interventions make effective models look degraded |
| CQ18 | `selective labels problem Lakkaraju decisions determine which outcomes are observed evaluation of algorithmic predictions` | L027 | selective labels, KDD 2017 |
| CQ19 | `Lucas critique policy change alters estimated relationships econometric evaluation structural invariance` | L028 | policy non-invariance of estimated relations |
| CQ20 | `monitoring deployed machine learning model performance when predictions trigger interventions performative drift detection causal monitoring` | L026 | monitoring under performativity (CLeaR 2024); intervention testing (2026) |
| CQ21 | `hidden feedback loops machine learning systems Sculley technical debt degenerate feedback loops recommender` | L029 | hidden feedback loops |
| CQ22 | `runtime assurance simplex architecture switching to safety controller effect on monitoring data distribution learning-enabled controller` | L032 | Simplex and RTA; distribution-shift monitoring; no evidential effect of switching found |
| CQ23 | `self-adaptive systems MAPE-K adaptation actions affect monitored data uncertainty assurance perpetual assurances Weyns` | L036 | perpetual assurances; uncertainty interaction |
| CQ24 | `shielded reinforcement learning shield interventions bias collected data off-policy correction safe exploration` | L033 | shield-induced data bias and corrections |
| CQ25 | `monitor validity after controller reconfiguration runtime verification adaptive system assumptions invalidated by adaptation` | L035, L036 | RV of self-adaptive systems; ModelPlex patents |
| CQ26 | `ModelPlex controller monitor model monitor runtime validation compliance of observed state transition with verified model Mitsch Platzer` | L035 | monitors over prior and posterior states given the action |
| CQ27 | `ARAIM fault detection and exclusion integrity after exclusion protection level probability of wrong exclusion` | L040 | protection levels after exclusion |
| CQ28 | `adaptive Kalman filter noise covariance estimation masks sensor fault absorbs fault covariance inflation fault detection degraded` | L042 | adaptation after detection; masking by adaptation not stated (UNCLEAR) |
| CQ29 | `Kalman filter integrity monitoring sequential fault history Joerger Pervan innovation-based detection time-correlated faults` | L041 | Kalman-filter integrity; sequential monitors |
| CQ30 | `Three Mile Island PORV indicator light showed solenoid command not valve position operators misled` | L052 | indicator reported the command |
| CQ31 | `Air France 447 stall warning stopped when airspeed below 60 knots invalid restarted when nose lowered BEA report` | L053 | action-conditioned validity of the stall warning |
| CQ32 | `SOHO 1998 mission interruption gyro deactivated emergency sun reacquisition used gyro despun investigation board` | L054 | command sequences and a ground command to turn off a gyro |
| CQ33 | `Malaysia Airlines 124 Boeing 777 2005 ADIRU failed accelerometer used after power cycle ATSB report` | L055 | ADIRU failure bypassed redundancy checks |
| CQ34 | `MH124 ADIRU software used faulty accelerometer 5 failure not recorded after power cycle accelerometer 6 failed` | L055 | failure detected but not reported; power-cycle detail **not** confirmed |
| CQ35 | `NTSB Uber ATG Tempe 2018 classification changed tracking history not retained object reclassified predicted path` | L056 | history discarded on re-classification |
| CQ36 | `China Airlines 006 1985 autopilot compensated engine flameout masked asymmetric thrust until disconnected upset NTSB` | L057 | autopilot compensation to the aileron limit |
| CQ37 | `Hitomi ASTRO-H loss attitude control gyro bias estimate star tracker thruster reaction wheel momentum anomaly report JAXA` | L058 | bias estimate and control chain |
| CQ38 | `autopilot masking effect icing out-of-trim condition NTSB recommendation autopilot disconnect upset ATR 72 Roselawn` | L059 | autopilot masking in icing; five earlier ATR 42 upsets |
| CQ39 | `B-2 crash Guam 2008 moisture air data sensors calibration skewed angle of attack accident investigation board` | L060 | calibration with moisture present |
| CQ40 | `Qantas 72 ATSB flight control primary computer algorithm AOA spikes 1.2 second memorisation design limitation` | L061 | memorisation period and second spike |
| CQ41 | `Schiaparelli lander IMU saturation persisted longer than expected navigation estimated negative altitude parachute jettison ESA inquiry` | L062 | saturation persistence |
| CQ42 | `FAA AC 25.1329 flight guidance system autopilot out-of-trim alert sustained trim awareness requirement crew alerting compensating` | L072 | mode indication; disengagement warning; out-of-trim alert not confirmed |
| CQ43 | `hybrid systems diagnosis mode-dependent analytical redundancy relations residual invalid after mode change observer reinitialization Narasimhan Biswas` | L017 | mode-dependent and mode-sequence ARRs |
| CQ44 | `fault estimation after fault accommodation diagnosis during fault-tolerant control residual changes after reconfiguration isolation of subsequent faults` | L019, L004 | accommodation versus reconfiguration; subsequent-fault isolation not found (UNCLEAR) |
| CQ45 | `input-dependent fault detectability multiplicative faults excitation closed-loop detectability depends on control input persistent excitation fault isolation` | L015 | excitation conditions; closed-loop covering of faults |
| CQ46 | `"out-of-trim" autopilot alert 25.1329 flight guidance system "out of trim" awareness sustained lateral trim annunciation` | L072 | out-of-trim requirement not confirmed (UNCLEAR) |
| CQ47 | `nonlinear observability depends on input singular inputs universal inputs observability-aware trajectory optimization self-calibration Hausman` | L018 | singular and universal inputs; observability-aware planning |
| CQ48 | `safety versus diagnosability trade-off planning robot fault identification informative actions risk constraints active diagnosis planning` | L009, L074 | s-FEAST again; interventional causal circuits (2026) |
| CQ49 | `decision provenance accountable systems data flow Singh Cobbe Norval provenance autonomous systems robots` | L043 | decision provenance, IEEE Access 2019 |
| CQ50 | `provenance-aware runtime monitoring cyber-physical systems robot ROS provenance graph fault diagnosis causal explanation` | L044 | ROS provenance and monitoring; no action-provenance-conditioned monitor found |
| CQ51 | `causal discovery closed-loop feedback control data Granger causality misleading under feedback controller confounding identifiability` | L031 | Granger under feedback and feedthrough |
| CQ52 | `counterfactual evaluation collision avoidance system alerts change encounter outcomes ACAS X safety evaluation encounter model simulation cannot use operational data` | none | ACAS X evaluated in simulation over encounter sets; counterfactual limitation not stated (UNCLEAR) |
| CQ53 | `safety performance indicators confounded by mitigations prevention paradox leading indicators autonomous vehicle in-service monitoring UL 4600 SPI validity` | L038 | SPIs and meta-SPIs; confounding by own mitigations not found |
| CQ54 | `latent faults masked by fault-tolerant control hidden fault accumulation redundancy exhausted passive FTC conceals degradation until capacity lost` | L051 | redundancy masking until exhaustion |
| CQ55 | `battery management system power derating current limiting masks cell degradation detection capacity fade diagnosis under derating` | L048 | derating documented; masking UNCLEAR |
| CQ56 | `adaptive modulation coding link adaptation masks jamming interference detection graceful degradation hides attack wireless monitoring` | L049 | link adaptation documented; masking UNCLEAR |
| CQ57 | `dynamic thermal management throttling masks hardware degradation timing anomaly detection DVFS changes execution time monitoring embedded` | L050 | throttling documented; masking UNCLEAR |
| CQ58 | `fault-tolerant control that preserves diagnosability diagnosis-aware fault accommodation controller reduces fault observability trade-off` | L019 | FTC and diagnosis texts; no diagnosability-preserving FTC identified |
| CQ59 | `runtime assurance active monitoring information gathering belief-space shield POMDP safety monitor partially observable` | L034 | belief-space shielding; active information gathering certified separately |
| CQ60 | `control-dependent diagnosability policy-dependent observability "diagnosability" depends on control policy continuous systems fault` | none new | diagnosability-observability theory (finite-state, approximate nonlinear) |
| CQ61 | `fault-tolerant flight control masks actuator failure detection delayed adaptive controller aircraft identification after reconfiguration flight test` | none new | FDIR in flight control; multiple-model filter banks |
| CQ62 | `exoneration assumption consistency-based diagnosis masking component correct output does not imply healthy de Kleer GDE` | L020 | no-fault-masking and exoneration assumptions |
| CQ63 | `Waymo counterfactual simulation disengagements safety driver takeover what would have happened safety performance data 2020` | L039 | counterfactual disengagement simulation |
| CQ64 | `NASA FRET requirement scope mode "in mode" temporal requirements Copilot Ogma runtime monitors mode-dependent` | L037 | FRETish scope; Ogma monitors for cFS and ROS 2 |
| CQ65 | `monitoring closed-loop system where monitor triggers controller change monitor accounts for its own effect on future observations reflexive` | L021, L045 | closed-loop performance monitoring; neuromodulation feedback distorting the monitored variable |
| CQ66 | `dual effect of control Bar-Shalom Tse caution probing control affects future estimation uncertainty certainty equivalence separation` | L013 | dual effect |
| CQ67 | `flight mode aware anomaly detection UAV flight logs PX4 ArduPilot mode-specific baseline controller mode changes data distribution` | L073 | UAV log anomaly datasets; mode-conditioned baselines not a documented focus |
| CQ68 | `fundamental trade-off fault detectability closed-loop performance robust controller attenuates fault effect detection limitation feedback` | L014 | detectability-performance trade-off with joint tuning |
| CQ69 | `closed-loop deep brain stimulation sensing during stimulation artifact biomarker altered by stimulation adaptive DBS confound` | L045 | stimulation artifacts mask the control biomarker |
| CQ70 | `adaptive control loss of persistent excitation parameter drift bursting when regulation good adaptive model no longer identifiable` | L016 | excitation lost after good regulation |
| CQ71 | `Kalman filter reinitialization reset transient innovation chi-square test false alarms after reset covariance reset fault detection` | L075 | chi-square tests; reset-transient handling not found (UNCLEAR) |
| CQ72 | `active perception Bajcsy revisiting active perception perception-action loop agent chooses actions to acquire information` | L046 | active perception |
| CQ73 | `probe effect instrumentation changes system behavior monitoring overhead runtime verification observer effect cyber-physical timing` | L047 | probe effect |
| CQ74 | `invariant causal prediction Peters Bühlmann Meinshausen invariance across interventions environments structural model` | L030 | invariant causal prediction |
| CQ75 | `closed-loop fault detection using control signal controller output reveals actuator fault compensated output tracking nominal control effort residual` | L021 | detection from set point, measurement and controller output; model driven by the command |

## 4. What was not found

In each case below, no directly matching work was identified in the
searched sources.

- A fielded or published mechanism that, for **every** runtime monitor,
  declares which evidence relations each intervention invalidates. Theory
  equivalents exist (L012, L017, L035, L037).
- A runtime-assurance architecture that models how its own switch changes
  its monitors' later evidence (CQ22, CQ59).
- Aerospace work on confounding of safety performance indicators by the
  system's own mitigations (CQ53).
- Documented masking of diagnosis by battery derating, link adaptation or
  thermal throttling (CQ55-CQ57): **UNCLEAR**.
- Isolation of a subsequent fault after accommodation (CQ44): **UNCLEAR**.
