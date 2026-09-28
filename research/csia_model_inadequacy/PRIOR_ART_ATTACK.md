# Assurance under model incompleteness: prior-art attack

Written on 2026-09-28. The problem is defined in
`research/csia_model_inadequacy/PROBLEM_DEFINITION.md`. The exact queries
are in `research/csia_model_inadequacy/SEARCH_LOG.md` (MIQ1–MIQ52).

**The aim of this attack was to kill the candidate problem, not to support
it.** The searches went beyond modern ML terminology into historical
literature:

- the reject option (1970) and the ambiguity/distance reject (1993);
- consistency-based diagnosis and unknown modes (1987–1991);
- belief functions (1986–1990);
- model criticism (1980) and model discrepancy (2001);
- analytical redundancy, the generalized likelihood ratio (GLR), unknown input
  observers (UIO) and multiple-model adaptive estimation (MMAE) (1976–1999).

## 0. Method and limits

- **Access.** This environment reaches only `raw.githubusercontent.com`
  (SEARCH_LOG.md, direct fetch attempts):
  - direct fetches of arXiv, ATSB, BEA, ESA, NASA NTRS, CVF, lfcps.org and
    dekleer.org returned 000, 403 or `EGRESS_BLOCKED`;
  - every paper, patent and report below is therefore **V0**, a search-engine
    title and summary only. Each carries **REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION**
    (`research/csia_model_inadequacy/FULLTEXT_VERIFICATION_QUEUE.md`).
- **Exceptions.** The only exceptions are:
  - one authors' README (V2);
  - three fielded or local code sources read line by line (V4): PX4, ArduPilot
    and CSIA.
- **Verification scale.** The same V0–V4 scale as the novelty audit:

  | level | meaning |
  |---|---|
  | V0 | search result or snippet only |
  | V1 | abstract verified |
  | V2 | substantial primary-source text inspected |
  | V3 | complete relevant primary source inspected |
  | V4 | claim traced to an exact section, page, claim, equation or source line |

- **Status codes.** **SC** means corroborated by two or more results or an
  indexing page. **SS** means a single search summary.
- **Novelty scale.** The same N0–N4 scale as the novelty audit:
  - N0: known;
  - N1: close, or only terminologically different;
  - N2: possibly distinct combination;
  - N3: apparently distinct in the searched literature;
  - N4: requires V3/V4. N4 is not used.
- **Wording discipline.** Where nothing matching was found, this package says
  "no directly matching work was identified in the searched sources". A source
  that could not be read makes a finding **UNCLEAR**, never NO.

## 1. Source register

### Classification with incomplete knowledge of the classes

| id | reference | ids / URL | level |
|---|---|---|---|
| M01 | C. K. Chow, the optimum error–reject trade-off ("reject option"), *IEEE Trans. Information Theory* 16(1), 1970. Reached only through M02's summary, which says M02 extends "the reject option proposed by Chow" | — | V0 SS |
| M02 | B. Dubuisson, M. Masson, "A statistical decision rule with incomplete knowledge about classes", *Pattern Recognition* 26(1):155–165, 1993. Two reject options: **ambiguity reject** (the sample is close to several known classes) and **distance reject** (the sample is far from every known class; "the number of classes is not the true one") | sciencedirect 003132039390097G | V0 SC |
| M14 | W. J. Scheirer, A. Rocha, A. Sapkota, T. E. Boult, "Toward open set recognition", *IEEE TPAMI* 35(7), 2013 ("open space risk"). A. Bendale, T. E. Boult, "Towards open world recognition", CVPR 2015, and OpenMax, CVPR 2016 | openaccess.thecvf.com | V0 SC |
| M15 | Open-set and open-world fault diagnosis, 2019–2026. Examples: cross-domain open-set FD (PMC9961812); rolling-bearing open-set domain adaptation (*Sci. Rep.* s41598-025-88353-1); physics-informed open-set domain generalization (arXiv 2607.04188); fine-grained open-set FD (arXiv 2607.13368). The field is described as moving "from a closed-world paradigm to an open-world paradigm" | as listed | V0 SC |
| M16 | Y. Geifman, R. El-Yaniv, selective classification for deep networks (arXiv 1705.08500, 2017); R. El-Yaniv, Y. Wiener, the risk–coverage framework (2010); SelectiveNet (ICML 2019) | arXiv 1705.08500; PMLR v97 | V0 SC |
| M17 | P. F. Jaeger, C. T. Lüth, L. Klein, T. J. Bungert, "A call to reflect on evaluation practices for failure detection in image classification", ICLR 2023. Misclassification detection, OoD detection, selective classification and predictive uncertainty "all state to address the same eventual goal" but form "largely separated research fields" | arXiv 2211.15259; README of `IML-DKFZ/fd-shifts` read at raw GitHub, sha256 `2dca7ac9…` | **V2** |

### Consistency-based and abductive diagnosis

| id | reference | ids / URL | level |
|---|---|---|---|
| M03 | J. de Kleer, B. C. Williams, "Diagnosis with behavioral modes", IJCAI-89, pp. 1324–1330. Correct and faulty modes, plus an **unknown mode U(x) that has no model**; the Sherlock system. Faulty components can be identified "without necessarily knowing how they fail" | dekleer.org (fetch 000); Semantic Scholar | V0 SC |
| M04 | P. Struss, O. Dressler, "'Physical negation': integrating fault models into the General Diagnostic Engine", IJCAI-89 (GDE+). With fault models, GDE+ checks "whether the faultiness of components would really explain the observations". It can prove components correct and rule out implausible hypotheses | dl.acm 10.5555/140524.140549; novelty audit B30 | V0 SC |
| M05 | R. Reiter, "A theory of diagnosis from first principles", *AI* 32(1), 1987. J. de Kleer, B. C. Williams, "Diagnosing multiple faults" (GDE), *AI* 32(1), 1987. **Multiple-fault diagnosis** by minimal hitting sets of conflicts | novelty audit B28, B29 | V0 SC |
| M06 | L. Console, P. Torasso, "A spectrum of logical definitions of model-based diagnosis", *Computational Intelligence* 7(3):133–141, 1991. Its abductive end requires hypotheses to **explain** the observations. The same result mentions that M.-O. Cordier (1998) treats cases where "abductive diagnosis fails to explain too precise observations" | Wiley 10.1111/j.1467-8640.1991.tb00388.x | V0 SS |
| M29 | M. W. Hofbaur, B. C. Williams, mode estimation and hybrid estimation of probabilistic hybrid automata (HSCC 2002; "Hybrid estimation of complex systems", 2004). Includes an approach "to continue hybrid estimation in the presence of **unknown behavioral modes**" | MIT MERS AI_Memo01_HME; Springer b105591 | V0 SC |
| M30 | B. C. Williams, P. P. Nayak, "A model-based approach to reactive self-configuring systems" (Livingstone), AAAI-96. Flown in the Deep Space 1 Remote Agent Experiment, May 1999. Whether Livingstone used an unknown mode was **UNCLEAR** in the summaries | AAAI-96; JPL | V0 SC |
| M31 | S. Narasimhan et al., HyDE, a hybrid diagnosis engine for stochastic hybrid systems (NASA Ames). How it handles "no consistent candidate" was **UNCLEAR** in the summaries | citeseerx f879efb7…; NASA catalog | V0 SC |
| M33 | QSI TEAMS and TEAMS-RT; D-matrix reasoners. Tests pass, fail or are unknown. The result is a single failure mode "responsible for all failed tests", or an **ambiguity group**. Component states: good, bad, suspected, unknown | ResearchGate fig 3719292; NASA ARC-18051-1; CSIA-DX D27 | V0 SC |
| M37 | "No faults in structure? How to diagnose hidden interactions". Model-based diagnosis engines under a closed-world assumption "misinterpret[] a single structural change as multiple simultaneous component failures" | lacuna.tiptreesystems.com (index page) | V0 SS |
| M38 | "A compositional approach to diagnosing faults in cyber-physical systems" | arXiv 2507.05438 | V0 SS |
| M48 | P. J. Mosterman, G. Biswas, temporal causal graphs from bond graphs (1999). Hybrid bond graphs and **global analytical redundancy relations** (GARRs) across energy domains. Signed bond graphs for multiple faults | arXiv 1312.2047; *Eng. Appl. AI* S0952197614001869 | V0 SS |

### Belief functions and evidential uncertainty

| id | reference | ids / URL | level |
|---|---|---|---|
| M07 | P. Smets, "The combination of evidence in the transferable belief model", *IEEE TPAMI* 12(5), 1990. **Open-world assumption**: the frame "is not necessarily exhaustive", and mass on the empty set indicates "belief in a hypothesis outside the frame of discernment". Also Smets, "The nature of the unnormalized beliefs encountered in the TBM" | dl.acm 10.1109/34.55104; arXiv 1303.5430 | V0 SC |
| M08 | L. A. Zadeh (1986), a critique of Dempster's rule. Two experts give `m1(A)=0.9, m1(C)=0.1` and `m2(B)=0.9, m2(C)=0.1`; normalized combination gives `m(C)=1`. High conflict "can suggest either an incomplete frame of discernment or unreliable sources". Smets' remedy is the unnormalized conjunctive rule | stat.berkeley.edu dempster_shafer.pdf; arXiv 0906.5119 | V0 SC |
| M09 | A. Jøsang, subjective logic: **vacuity** (lack of evidence) versus **dissonance** (conflicting evidence). M. Sensoy, L. Kaplan, M. Kandemir, "Evidential deep learning to quantify classification uncertainty", NeurIPS 2018. Multidimensional evidential networks, AAAI 2021 | NeurIPS 7580; AAAI ojs 16954 | V0 SC |
| M10 | E. Hüllermeier, W. Waegeman, "Aleatoric and epistemic uncertainty in machine learning: an introduction to concepts and methods", *Machine Learning* 110(3):457–506, 2021 | arXiv 1910.09457 | V0 SC |

### Conformal prediction

| id | reference | ids / URL | level |
|---|---|---|---|
| M11 | Conformal prediction set semantics: a **singleton**; a set of several labels ("too many things are plausible"); an **empty set** ("nothing is plausible enough"). "Out-of-distribution detection should use conformal prediction (and vice-versa?)", 2024 | arXiv 2403.11532 | V0 SC |
| M12 | Conformal prediction applied to fault detection: "Calibrated prediction set in fault detection with risk guarantees via significance tests" (arXiv 2508.01208). Fault detection and diagnosis for a space launcher's engine electrical system with calibrated classifiers (arXiv 2507.13022) | as listed | V0 SS |
| M13 | L. Lindemann, X. Qin, J. V. Deshmukh, G. J. Pappas, "Conformal prediction for STL runtime verification", ICCPS 2023. Also conformal predictive monitoring (arXiv 2312.01959) | dl.acm 10.1145/3576841.3585927 | V0 SC |

### Statistical model criticism

| id | reference | ids / URL | level |
|---|---|---|---|
| M18 | G. E. P. Box, "Sampling and Bayes' inference in scientific modelling and robustness", *JRSS A* 143:383–430, 1980 (model criticism, separated from estimation within a model). A. Gelman, X.-L. Meng, H. Stern, "Posterior predictive assessment of model fitness via realized discrepancies", *Statistica Sinica* 6:733–807, 1996 | sinica j6n41 | V0 SC |
| M19 | J. M. Bernardo, A. F. M. Smith, *Bayesian Theory*. The **M-closed**, M-complete and **M-open** perspectives: whether the true model is among the candidates. M. Clyde, E. Iversen, "Bayesian model averaging in the M-open framework" | Duke dspace 10161/11779 | V0 SC |
| M20 | M. C. Kennedy, A. O'Hagan, "Bayesian calibration of computer models", *JRSS B* 63(3), 2001. **Model inadequacy** is captured by a discrepancy function | asc.ohio-state.edu kennedy01.pdf | V0 SC |

### Fault detection and isolation, estimation and model invalidation

| id | reference | ids / URL | level |
|---|---|---|---|
| M21 | J. Gertler, structured residuals and parity equations (1991 onward). The fault signature matrix: a unique signature makes a fault isolable. A signature that matches no column is unanticipated | IFAC S1474667017502104 | V0 SC |
| M22 | A. S. Willsky, H. L. Jones, "A generalized likelihood ratio approach to the detection and estimation of jumps in linear systems", *IEEE TAC* AC-21:108–112, 1976 | willsky.lids.mit.edu 14_pub_IEEE.pdf | V0 SC |
| M23 | J. Chen, R. J. Patton, H.-Y. Zhang, unknown input observers and robust fault detection filters, *Int. J. Control* 63(1), 1996. J. Chen, R. J. Patton, *Robust model-based fault diagnosis for dynamic systems*, 1999. An accurate model "is never available in practice" | tandfonline 10.1080/00207179608921833 | V0 SC |
| M24 | P. S. Maybeck, MMAE for sensor and actuator failures in flight control (the VISTA F-16), *Int. J. Robust Nonlinear Control* 9(14), 1999. It uses "residual monitoring". K. A. Fisher, "Multiple model adaptive estimation using filter spawning" (AFIT) | Wiley RNC452; scholar.afit.edu/etd/5138 | V0 SC |
| M25 | Normalized innovation squared (NIS) filter consistency tests: Y. Bar-Shalom et al.; R. Piché, "Online tests of Kalman filter consistency", *IJACSP*, 2016 | Wiley acs.2571 | V0 SC |
| M26 | F. Harirchi, N. Ozay, model invalidation for switched affine systems with applications to fault and anomaly detection (IFAC ADHS 2015); guaranteed model-based fault detection by model invalidation, *Automatica* 93, 2018. T-detectability and I-isolability, via mixed-integer linear programming (MILP) feasibility | arXiv 1704.05947; dl.acm 10.1016/j.automatica.2018.03.040 | V0 SC |
| M43 | Closed-loop fault masking. "The negative impact of closed-loop control on fault detection" (Univ. Manchester). H. Niemann, J. Stoustrup et al., controller modification for active fault detection (2014). "Anomaly detection under closed-loop fault masking" (2026 case study) | research.manchester.ac.uk; vbn.aau.dk | V0 SC |
| M44 | Angle-of-attack analytical redundancy detecting **common-mode** failures. "An innovative angle of attack virtual sensor for physical-analytical redundant measurement system applicable to commercial aircraft" (*ASTESJ* 6(1):76). US 11,003,196 "Flight control system for determining a common mode pneumatic fault". US 11,029,706 "… determining a fault based on error between a measured and an estimated angle of attack" | astesj.com v06 i01 p76; USPTO | V0 SC |

### Runtime model validation and assumption monitoring

| id | reference | ids / URL | level |
|---|---|---|---|
| M27 | S. Mitsch, A. Platzer, "ModelPlex: verified runtime validation of verified cyber-physical system models", RV 2014 (LNCS 8734:199–214) and *FMSD* 49, 2016. Monitors check an execution's **compliance with the verified model** and "initiate[] provably safe fail-safe actions upon non-compliance". Extended to partial observability (arXiv 1811.06502). US 10,872,187; US 11,204,838 "Runtime model validation for partially-observable hybrid systems" | FMSD 10.1007/s10703-016-0241-z; USPTO | V0 SC |
| M28 | Runtime monitoring of assume-guarantee contract assumptions: "Monitoring assumptions in assume-guarantee contracts" (arXiv 1606.00505); "Confidence composition for monitors of verification assumptions" (arXiv 2111.03782); runtime assurance monitors as assume-guarantee contract checkers (SoS-VO) | as listed | V0 SC |
| M39 | Continuous validation of digital twins: "Reusing model validation methods for the continuous validation of digital twins of CPS" (arXiv 2512.04117). It separates digital-twin quality assurance (is the model still representative) from fault detection (is the asset faulty). Also: spacecraft digital-twin model-discrepancy reduction (ESA Cluster, *Aerosp. Sci. Technol.*) | as listed | V0 SS |
| M40 | Specification and invariant mining for CPS: ARTINALI; CoMID (arXiv 1807.02282). Violated mined invariants flag deviations | as listed | V0 SC |
| M41 | Falsifying causal graphs by the conditional independences they imply: arXiv 2305.09565; Karlsson et al., ICML 2025 | as listed | V0 SC |
| M42 | Bayesian runtime verification of autonomous robots after regular and singular events (*Communications Engineering*, 2024; arXiv 2303.08476). "Bayesian surprise" anomaly detection for guided vehicles | nature.com s44172-024-00162-y | V0 SS |

### System health management and integrity

| id | reference | ids / URL | level |
|---|---|---|---|
| M32 | D. L. Iverson, the Inductive Monitoring System (IMS), NASA Ames (2004 onward). Data-driven anomaly detection, integrated with "complementary model-based and rule-based methods" in integrated system health management (ISHM) | NTRS 20040068062; 20090037065 | V0 SC |
| M34 | Vehicle-level reasoning (VLRS). "An integrated reasoning framework for vehicle level diagnosis of aircraft subsystem faults" (PHM Society). It fuses heterogeneous subsystem diagnoses and isolates the root cause of propagated faults. Also the Vehicle Integrated Prognostic Reasoner (VIPR). Whether it flags **jointly inconsistent** subsystem conclusions was **UNCLEAR** | papers.phmsociety.org 707 | V0 SC |
| M35 | Advanced receiver autonomous integrity monitoring (ARAIM) fault detection and exclusion (FDE): solution separation and chi-squared tests (*IEEE TAES*, 2016). Detection is required for integrity; exclusion is not always possible. Integrity and continuity are allocated for **unmonitored fault modes** outside the monitored list | ieeexplore 7472967 | V0 SC |
| M36 | ISO 21448 (SOTIF): scenarios classified known/unknown × safe/unsafe. Area 3 is "unknown and unsafe" | lhpes.com; jamasoftware.com | V0 SC |
| M45 | NASA ADAPT electrical power system testbed; the international diagnostic competitions DXC'10 and DXC'11 | c3.ndc.nasa.gov DXC10paper_final.pdf; NTRS 20110011109 | V0 SC |
| M46 | Spacecraft fault detection, isolation and recovery (FDIR): hybrid machine-learning plus model-based reasoning to "detect and diagnose anomalies never before encountered" (AMOS 2022). Model-based FDIR for Mars Sample Return (IFAC) | amostech.com Stottler_2.pdf; IFAC S2405896316303263 | V0 SS |
| M47 | El Al 1862 (1992): structural damage of unknown extent. Reconstructed later as the GARTEUR AG16 / RECOVER fault-tolerant flight control benchmark, where the aircraft was found "recoverable if unconventional control strategies were used" | reports.nlr.nl; Springer 978-3-642-11690-2_6 | V0 SC |

### Incident reports

| id | reference | ids / URL | level |
|---|---|---|---|
| M50 | ATSB AO-2008-070, Qantas 72 in-flight upset, A330 VH-QPA, 7 October 2008. The flight control primary computer (FCPC) angle-of-attack (AOA) algorithm "could not manage a scenario where there were multiple spikes in AOA from one ADIRU that were 1.2 seconds apart". "Frequent data spikes had not been anticipated" | atsb.gov.au (fetch blocked) | V0 SC |
| M51 | Ariane 5 Flight 501 Inquiry Board report, 1996. Software design faults in the inertial reference system (SRI), including "shutdown of processor on detection of a malfunction". The backup SRI failed, then the active SRI. The alignment function "was not taken into account in the simulations" | esa.int press release; sunnyday.mit.edu (403) | V0 SC |
| M52 | BEA final report, A320 D-AXLA (XL Airways Germany 888T), 27 November 2008. AOA sensors 1 and 2 blocked by frozen water. "ADR 1 and 2, which provided incorrect data, were trusted and ADR 3, which provided normal data, was rejected" | bea.aero synopsis (fetch 000); SKYbrary | V0 SC |
| M53 | Lufthansa 1829, A321 D-AIDP, 5 November 2014. Two AOA sensors blocked, probably by ice, triggered alpha protection nose-down. The BFU report was not reached; the summaries are press and database pages | avherald 47d74074; aviation-safety.net 171411 | V0 SS |
| M54 | ESA ExoMars 2016 Schiaparelli anomaly inquiry. IMU saturation lasted about 1 s, "longer than would be expected". The navigation estimate of altitude became **negative**, which triggered parachute and backshell release, thruster firing and on-ground mode at about 3.7 km altitude | sci.esa.int inquiry PDF (fetch 000); esa.int | V0 SC |

### Fielded and local source code

| id | reference | ids / URL | level |
|---|---|---|---|
| M60 | PX4 `src/modules/ekf2/EKF2Selector.cpp`, fetched from raw GitHub (`main`) on 2026-09-28, sha256 `e6cff5d6…`. What it does: an instance is "healthy" with no filter fault and a combined test ratio above 0 (line 299); a "warning" means test ratio ≥ 1 (line 302); when the primary is unhealthy, the selector prefers candidates without a sustained warning, and after a delay it falls back to the lowest-test-ratio candidate **even if every candidate carries a sustained warning** (lines 815–823) | raw.githubusercontent.com | **V4** (this file only) |
| M61 | ArduPilot `libraries/AP_NavEKF3/AP_NavEKF3.cpp`, fetched from raw GitHub (`master`) on 2026-09-28, sha256 `ec0cfed3…`. What it does: lane switching moves to a healthier or lower-error lane (line 1021); `checkLaneSwitch` accepts only an alternative whose error score is below both the primary's and 0.9 (line 1073), and otherwise keeps the primary | raw.githubusercontent.com | **V4** (this file only) |
| M62 | This repository at commit 503321f: `csia/v2/localization.py` (lines 196, 299, 321–335, 352–358), `csia/v2/attribution.py` (lines 7–13) and `csia_assurance/witness.py` (lines 61–71) | local | **V4** |

## 2. Attack by field

"Kills" names which part of the candidate problem the field already covers:

| code | part of the candidate problem |
|---|---|
| **CORE** | runtime separation of within-model ambiguity from model failure |
| **JOINT** | the V-joint case |
| **COMP** | compound faults |
| **SEM** | the four-way output semantics |
| **ACT** | preventing action on a wrong best fit |

| # | field in the brief | closest sources | what it already does | kills |
|---|---|---|---|---|
| 1 | open-set fault diagnosis | M15, M14 | rejects unknown fault classes at test time; known-class confusion stays inside the closed-set classifier | CORE (partly: unknown vs known, not unknown vs ambiguous) |
| 2 | open-world fault diagnosis | M15, M14 | detects unknowns, then labels them and updates the model incrementally | CORE |
| 3 | unknown-fault detection | M21, M24, M32 | a signature matching no column; MMAE residual monitoring; data-driven IMS beside model-based ISHM | CORE |
| 4 | new-fault ("novel fault") detection | M15, M46 | the same as rows 1–3, including spacecraft hybrid ML+MBR for "anomalies never before encountered" | CORE |
| 5 | OOD fault diagnosis | M15, M17 | OOD rejection. M17 records that OoD detection and misclassification detection are evaluated as separate fields | CORE, SEM (partly) |
| 6 | model invalidation | M26 | set-membership invalidation of every model by MILP. A model survives, or it is invalidated | CORE |
| 7 | model falsification | M18, M41 | model criticism and posterior predictive checks; falsifying causal graphs through implied conditional independences | CORE |
| 8 | consistency-based diagnosis | M03, M04, M05 | conflicts are sets of assumptions **jointly** inconsistent with the observations; several minimal diagnoses express ambiguity | CORE, JOINT, COMP |
| 9 | MBD with incomplete fault models | M03, M04, M06 | the unknown mode U(x) with no model; "physical negation"; abductive diagnosis that finds no explanation | CORE, COMP |
| 10 | residual-based unknown-fault detection | M21, M23, M48 | a signature outside the fault signature matrix; robust residuals; cross-domain GARRs | CORE, JOINT |
| 11 | generalized likelihood rejection | M22, M02 | GLR detection with jump estimation; the distance-reject decision rule | CORE |
| 12 | reject-option classifiers | M01, M02 | **ambiguity reject versus distance reject**, 1993 | CORE, SEM |
| 13 | selective classification | M16 | risk–coverage abstention. It does **not** separate the reason for abstaining | ACT (abstention) |
| 14 | abstention | M01, M16 | reject or abstain | ACT |
| 15 | epistemic uncertainty | M09, M10 | aleatoric versus epistemic; vacuity versus dissonance | SEM (partly) |
| 16 | Bayesian model inadequacy | M20, M19 | the discrepancy function; M-closed versus M-open | CORE (concept) |
| 17 | posterior predictive checks | M18 | realized-discrepancy tests of one model's fit | CORE |
| 18 | multiple-model invalidation | M26, M24 | I-isolability over several fault models; MMAE banks with residual monitoring and filter spawning | CORE, ACT |
| 19 | set-membership invalidation | M26 | as row 6 | CORE |
| 20 | FD under model uncertainty | M23, M43 | robust residuals and adaptive thresholds; closed-loop masking and active detection | limits of CORE |
| 21 | robust diagnosis | M23 | robust directional residuals | limits of CORE |
| 22 | unknown input observers | M23 | decouple unknown inputs from residuals | limits of CORE |
| 23 | hybrid-system model invalidation | M26, M29 | switched-affine invalidation; hybrid estimation with unknown behavioural modes | CORE |
| 24 | runtime model validation | M27 | runtime compliance with the verified model, then a verified fail-safe | CORE, ACT |
| 25 | runtime verification under model uncertainty | M27, M13 | partial-observability ModelPlex; conformal STL runtime verification | CORE, ACT |
| 26 | assumption monitoring | M28 | runtime checks of environment assumptions of assume-guarantee contracts | CORE, ACT |
| 27 | assumption-aware autonomy | M28, M36 | assumption monitors with confidence composition; SOTIF unknown-unsafe (design time) | CORE (partly) |
| 28 | specification mining / violation | M40 | mined invariants and their violation | CORE (anomaly level) |
| 29 | surprise / innovation monitoring | M25, M42 | NIS consistency tests; Bayesian surprise | CORE (single-model level) |
| 30 | open-set recognition | M14 | open space risk | CORE |
| 31 | open-world recognition | M14 | detect unknowns, label them, update | CORE |
| 32 | anomaly explanation | M32, M34 | UNCLEAR at V0: no source in the searched set explained **why** no known hypothesis fits | — |
| 33 | causal model falsification | M41 | implied-conditional-independence tests | CORE |
| 34 | digital-twin discrepancy detection | M39, M20 | twin quality assurance kept separate from asset-fault detection; the discrepancy term | CORE |
| 35 | integrity under unmodelled faults | M35, M36 | detection without possible exclusion; integrity allocated to unmonitored faults; SOTIF area 3 | CORE (design-time pricing), ACT |

**Reading.** Every field in the brief already contains at least a partial
form of the CORE distinction. Several contain it exactly.

- Rows 8, 9 and 12 are the oldest runtime forms (1989–1993).
- The ML fields (rows 1, 2, 5, 13–15) mostly frame the question as
  known-versus-unknown. They rarely frame it as ambiguous-versus-unknown.

## 3. The key distinction: ambiguity within the model versus failure of the model

The full analysis is in
`research/csia_model_inadequacy/AMBIGUITY_VS_MODEL_INADEQUACY.md`.

The two conditions are **already formally separated, at runtime, in at least
eight traditions**:

| tradition | ambiguity within the model | failure of the model | source |
|---|---|---|---|
| pattern recognition, 1993 | ambiguity reject | distance reject | M02 |
| consistency-based diagnosis, 1989 | several minimal diagnoses | only diagnoses that need U(x) | M03 |
| belief functions, 1990 | mass on a non-singleton set | mass on the empty set (open world) | M07 |
| conformal prediction | a set with several labels | an empty set | M11 |
| structured residuals | a signature shared by several columns | a signature matching no column | M21 |
| model invalidation | several models not invalidated | all models invalidated | M26 |
| statistical model criticism, 1980 | estimation within the model | criticism of the model | M18 |
| runtime model validation | (single model) | model non-compliance, then fail-safe | M27 |

Status: **N0**.

## 4. The second distinction: joint cross-system inconsistency

**No directly matching work that treats this as a separate problem was
identified in the searched sources.** Its formal content is nonetheless
already standard:

- **Consistency-based diagnosis.** A conflict is **by definition** a set of
  assumptions that is jointly inconsistent with several observations (M03,
  M05). Each observation alone may be consistent.
- **Evidence combination.** Under the open-world conjunctive rule, "each
  source supports some hypothesis, but no hypothesis is supported by all"
  produces mass on the empty set (M07). Zadeh's two-expert example (M08) is
  exactly the brief's battery-says-H1, propulsion-says-H2 pattern.
- **Multi-domain analytical redundancy relations.** GARRs from bond graphs
  (M48) are cross-domain consistency checks by construction.
- **Vehicle-level reasoners** fuse subsystem conclusions (M34).
  - Whether they report joint inconsistency as such is UNCLEAR.
- **The aircraft analogue.** Two angle-of-attack vanes agree with each other
  but disagree with the flight dynamics. This pattern is detected by an
  analytical-redundancy virtual sensor, and is claimed in patents for
  common-mode detection (M44).

Status: **N0**. The joint case adds an **implementation requirement**: check
the conjunction, not the per-subsystem verdicts. It adds no research content.

## 5. Compound faults

- **The weak case: H_motor + H_sensor with both modes in the library.** This
  is multiple-fault diagnosis (M05, 1987). It is solved in principle. The
  known cost is the combinatorial candidate space. **The weak case is killed.**
- **The strong case: no combination of modelled modes explains the evidence.**
  This is what the unknown mode U(x) of M03 is for. With complete fault
  models, "physical negation" (M04) can leave no consistent diagnosis.
- **A known failure mode in the other direction.** M37 reports that
  closed-world engines explain a single **structural** fault, which lies
  outside the component library, as **multiple component faults**.
  Multiple-fault diagnosis can therefore **absorb** the model-inadequacy
  signal by finding a wrong combination.
  - This is the brief's concern, and it is already documented (V0).
- The general statement is known wherever `H*` is enlarged:
  - adding combinations, or an unconstrained U mode, raises the chance that
    something in `H*` fits;
  - that suppresses the MODEL_INADEQUATE condition.

Status: **N0**.

## 6. Assurance semantics

The four labels in the brief already exist under other names. The mapping is
in AMBIGUITY_VS_MODEL_INADEQUACY.md §4:

| label | established names |
|---|---|
| KNOWN_UNIQUE | a unique minimal diagnosis; a singleton conformal set; an unambiguous failure mode |
| KNOWN_AMBIGUOUS | an ambiguity group; ambiguity reject; several minimal diagnoses; a multi-label conformal set |
| MODEL_INADEQUATE | distance reject; mass on the empty set; an empty conformal set; all models invalidated; model non-compliance |
| INSUFFICIENT_EVIDENCE | vacuity; total ignorance `m(Ω)`; unknown or untested test outcomes |

Status: **N1**, terminological only. **This package recommends against new
vocabulary.**

## 7. The critical safety question: confident action on a wrong best-fitting hypothesis

| case | what the model or library assumed | what happened | was inadequacy observable, and by what | source |
|---|---|---|---|---|
| Zadeh's example (formal) | the frame is exhaustive; normalize the conflict away | two experts who each reject C yield `m(C)=1`: **certainty in the minority hypothesis** | yes: the conflict mass before normalization (the open-world rule of M07) | M08 |
| XL Airways 888T (2008) | redundant AOA sensors fail independently (a single-sensor-fault voting model) | two vanes froze at consistent values; the voter **trusted the two wrong sensors and rejected the healthy one** | **not from the voted AOA evidence alone** (V-equivalent). Yes from the flight-dynamics analytical redundancy (M44) | M52 |
| Lufthansa 1829 (2014) | the same class | two AOA sensors blocked; alpha protection commanded nose-down | the same as 888T (V0 SS) | M53 |
| Qantas 72 (2008) | the FCPC spike-handling algorithm assumed spike patterns other than "multiple spikes 1.2 s apart" | pitch-down commands | UNCLEAR at V0. The summaries say only that the pattern "had not been anticipated" | M50 |
| Ariane 501 (1996) | the SRI software's handling of an out-of-range value: the processor shuts down on malfunction, in both redundant units | the backup SRI and then the active SRI failed together; the nozzles were driven to their extreme positions | the summaries confirm a common-mode software design fault. What the inquiry says about the assumed fault model is queued (FULLTEXT_VERIFICATION_QUEUE.md Q11) | M51 |
| Schiaparelli (2016) | IMU saturation of expected duration | a saturation of about 1 s gave a **negative altitude estimate** and triggered irreversible landing actions at about 3.7 km | yes: a negative altitude is inconsistent with the vehicle's own state model. A runtime compliance check (M27 style) would flag it. Whether such a check existed is queued (Q12) | M54 |
| El Al 1862 (1992) | a fault-tolerant control design base without structural damage of this extent | loss of control | a retrospective benchmark, not a diagnosis record | M47 |
| structural fault under closed-world MBD | the component library is complete | one structural fault diagnosed as several component faults | yes, with structural-fault hypotheses; not with the component library | M37 |
| out-of-distribution (OOD) versus misclassification detection | OOD detectors evaluated separately from misclassification | the task formulation "deviates from the stated purpose of detecting classification failures" | a documented research-practice gap in ML, recognized by the field itself | M17 (V2) |
| fielded multirotor estimator selection (V4) | the least-inconsistent estimator instance is the right one | PX4: after a delay it falls back to the lowest-test-ratio instance even when **every** instance carries a sustained warning. ArduPilot: stays on the primary unless an alternative scores below 0.9 | per-instance warnings are published. **This selector code has no state that separates "instances disagree" from "no instance is consistent"**. Downstream failsafes were not traced, so the system-level answer is UNCLEAR | M60, M61 |

**Reading.**

- The safety concern is real and documented. The mechanisms behind it are
  known:
  - normalization, whether Dempster's rule, a softmax, MMAE posteriors or
    least-bad selection;
  - closed-world hypothesis sets;
  - common-mode failures that defeat voting.
- The documented aircraft cases are **V-equivalent** with respect to the
  deciding logic's own evidence. A runtime MODEL_INADEQUATE output computed
  from that same evidence would not have fired.
- What would have exposed them is **additional, dissimilar evidence**, namely
  analytical redundancy from the flight dynamics. That is established and
  patented (M44).
- Existing assurance can prevent confident action on the wrong best fit
  **where the inadequacy is observable**, by three routes:
  - ModelPlex-style compliance monitors with a verified fail-safe (M27);
  - MMAE residual monitoring (M24);
  - reject or abstain rules (M01, M02, M16).
- **No method can do it where the inadequacy is not observable.** That limit
  is identifiability, not a missing algorithm. In aviation integrity practice
  it is handled at design time:
  - by dissimilar redundancy;
  - by pricing unmonitored threats into the integrity budget (M35);
  - by SOTIF area-3 validation (M36).

## 8. Candidate surviving gaps and their attack

| id | candidate gap | attack | outcome |
|---|---|---|---|
| G1 | separate KNOWN_AMBIGUOUS from MODEL_INADEQUATE at runtime | §3 | **killed** (N0) |
| G2 | detect joint cross-system inconsistency | §4 | **killed** (N0); an implementation requirement only |
| G3 | handle compound faults without losing the inadequacy signal | §5 | **killed** (N0). That combinations absorb inadequacy is itself documented (M37) |
| G4 | the four-way assurance semantics | §6 | **N1**, terminological |
| G5 | detect inadequacy that is observationally equivalent to a library hypothesis | §7 | **not a gap: an identifiability limit.** No runtime test on the same evidence can succeed. The remedies (dissimilar evidence, design-time threat pricing) are established (M44, M35, M36) |
| G6 | the window before closed-loop compensation hides an out-of-library fault (suggested by XSYS-001's finding that dynamic evidence expires once the controller compensates) | MIQ49 | **killed** (N0). Closed-loop fault masking and active detection to counter it are established (M43) |
| G7 | a coverage-calibrated inadequacy output (the empty set) over cross-domain physical evidence | MIQ50, MIQ52 | **N1**. Conformal runtime verification for CPS (M13), conformal fault detection (M12) and the empty-set semantics (M11) exist. What would remain is a combination built around a CSIA feature, which this phase's method rules out |
| G8 | fielded UAV autopilot estimator selectors expose no inadequacy state | M60, M61 | **a deployment observation, not a research gap.** The concept is N0, and the system-level behaviour is UNCLEAR |

## 9. The five CONTINUE conditions

| # | condition | holds? | why |
|---|---|---|---|
| 1 | a real technical gap survives | **NO** | G1–G3 and G6 are N0; G4 and G7 are N1; G5 is an identifiability limit; G8 is deployment |
| 2 | the gap is useful in autonomous aerospace | the **problem** is useful (§7; `research/csia_model_inadequacy/USEFULNESS.md`). **No surviving gap** is | the useful part is covered by established methods and design practice |
| 3 | more than open-set classification under new terminology | **NO**, as a research claim | beyond open-set, the richer content (ambiguity versus distance reject, the unknown mode, open-world belief) is itself older than open-set recognition |
| 4 | CSIA's evidence structure gives a meaningful advantage | **NO** | CSIA's set elimination is consistency-based diagnosis with declared refuters (novelty audit: N0/N1). Its all-refuted state is the GDE+ "no consistent diagnosis" signal. As of 503321f it localizes per symptom, so it does not check joint consistency (M62). Inadequacy is visible only where declared refuters fire |
| 5 | a falsifiable research question is visible | **only questions already addressed in the literature**: G6 (M43) and G7 (M11–M13) | none survives as a research question distinct from prior art |

## 10. Findings A–J (summary; the final report repeats them)

- **A. Closest prior art.** The four closest are:
  - de Kleer & Williams' behavioural modes with the unknown mode (M03), with
    GDE/GDE+ (M04, M05);
  - Dubuisson & Masson's ambiguity versus distance reject (M02);
  - Smets' open-world TBM (M07);
  - ModelPlex runtime model compliance with a verified fail-safe (M27).

  Next come MMAE with residual monitoring (M24), model invalidation (M26) and
  conformal set semantics (M11, M12). Details are in
  `research/csia_model_inadequacy/CLOSEST_SYSTEMS.md`.
- **B.** The ambiguity-versus-inadequacy distinction is **established**, at
  runtime, since at least 1989–1993. Its statistical form (1980) is older
  still.
- **C.** Cross-system joint inconsistency adds **nothing beyond** the
  conflicts of consistency-based diagnosis and open-world evidence
  combination. It is an implementation requirement.
- **D.** Multiple-fault diagnosis **kills the weak compound case**. The
  strong case is covered by the unknown mode. That combinations can mask
  inadequacy is itself documented.
- **E.** Open-set and OOD diagnosis kill the **known-versus-unknown** half.
  The **ambiguous-versus-unknown** half is killed by older, non-ML work.
- **F. Strongest surviving gap.** None survives as research. The hardest
  residue, observationally equivalent out-of-library causes, is an
  identifiability limit handled by dissimilar evidence and design-time
  integrity allocation.
- **G. Practical aerospace value.** The **problem** has real value (§7). The
  **gap** does not: the value lies in applying established methods, above all
  dissimilar cross-domain evidence and never normalizing inadequacy away.
- **H. CSIA.** CSIA gives no meaningful advantage:
  - its mechanism is a consistency-based diagnosis variant;
  - its all-refuted state already exists but shares the UNSUPPORTED token with
    other meanings;
  - it does not check joint consistency across symptoms.

  These are engineering observations (USEFULNESS.md §4), not research.
- **I. Novelty status.**

  | claim group | status |
  |---|---|
  | the problem's core, joint and compound parts, and its safety consequence | N0 |
  | the four-way semantics and calibrated inadequacy outputs | N1 |
  | anything at N2 or above | none. Nothing was proposed beyond N1 |

  The matrix is in `research/csia_model_inadequacy/NOVELTY_CLAIM_MATRIX.csv`.
- **J.** See the decision below.

**Why KILL and not PIVOT.** A pivot needs a narrower problem that survives the
attack. Three pivot targets were attacked, and each is established in the
searched sources:

- G6, the closed-loop masking window (M43);
- G7, calibrated inadequacy outputs (M11–M13);
- common-mode detection by cross-domain analytical redundancy (M44).

The only residue, CSIA's verdict overload and per-symptom localization, is
engineering hygiene against established semantics. It is not a research
problem. Every source here is V0 except M17, M60, M61 and M62. The decision
rests on the convergence of more than eight independent traditions, not on
any single source (FULLTEXT_VERIFICATION_QUEUE.md).

**Decision:** `MODEL_INADEQUACY_KILL`
