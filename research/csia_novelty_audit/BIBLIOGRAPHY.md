# Bibliography: CSIA novelty and prior-art audit

This bibliography supports the pre-result novelty audit of 2026-09-27, the
same day the searches were run. Identifiers `Bnn` (literature) and `Pnn`
(patents) are cited by every other file in `research/csia_novelty_audit/`.
The claims `C1`–`C20` are defined in `research/csia_novelty_audit/CSIA_PRIOR_ART_MATRIX.csv`.

## Read this first: what "verified" means here

**No full text was read for any entry.** Two routes were tried and both are
blocked by the environment's egress policy:

- `curl` returned HTTP 403 for 14 hosts:
  - `api.crossref.org`, `doi.org`, `api.openalex.org`,
    `api.semanticscholar.org`, `dblp.org`;
  - `ntrs.nasa.gov`, `export.arxiv.org`, `www.osti.gov`, `scholar.archive.org`;
  - `patents.google.com`, `ppubs.uspto.gov`, `api.patentsview.org`;
  - `ieeexplore.ieee.org`, `www.sciencedirect.com`.
- `WebFetch` reported `EGRESS_BLOCKED` for five hosts: `arxiv.org`,
  `patents.google.com`, `www.semanticscholar.org`, `ntrs.nasa.gov` and
  `www.sba.org.br`.

Only a web-search tool worked. It returns titles, URLs and a summary written
from the pages it indexed. Every statement below about what a source does rests
on that summary. The limitation cuts one way: it can only **understate** prior
art. It can never make a source look closer to CSIA than it is. A generous
difference recorded in this package should be assumed to be too generous.

| code | meaning |
|---|---|
| **SC** | search-corroborated. Title, authors or venue and year appear consistently in two or more returned results, or in the result from an indexing site. Content comes from the search summary |
| **SS** | a single search summary. The details shown are those the summary returned; other fields are marked *not shown* |
| **RP** | carried from an earlier repository prior-art record. The status and caveats recorded there apply |
| **(unconfirmed)** | a detail, such as a volume or issue number, that came from background knowledge and was not shown by any search in this session |

Patents are listed for a **technical prior-art screen only**. No claim was
read, and nothing here is a legal conclusion about patentability, validity or
freedom to operate.

## A. Foundational fault detection and isolation (FDI) and analytical redundancy

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B01 | A. S. Willsky, "A survey of design methods for failure detection in dynamic systems", *Automatica* 12(6):601–611, 1976 | doi 10.1016/0005-1098(76)90041-8; https://www.sciencedirect.com/science/article/abs/pii/0005109876900418 | C1, C2, C3 | SC |
| B02 | A. S. Willsky, H. L. Jones, "A generalized likelihood ratio approach to the detection and estimation of jumps in linear systems", *IEEE Trans. Automatic Control*, 1976 (volume and pages unconfirmed) | https://www.semanticscholar.org/paper/bc6991bcec2bb5b61cd2470cbd30a805fc52778f | L1 | SC |
| B03 | R. V. Beard, MIT PhD thesis, 1971; H. L. Jones, "Failure detection in linear systems", MIT PhD thesis, 1973 (the Beard–Jones detection filter) | https://www.researchgate.net/publication/279834158_Failure_Detection_in_Linear_Systems | C1, C3 | SC |
| B04 | J. E. Potter, M. C. Suman, "Thresholdless redundancy management with arrays of skewed instruments", NATO AGARDograph 224, pp. 15-1 to 15-25, 1977 (the origin of parity space) | http://jglobal.jst.go.jp/en/public/201002064777220137 | C1 | SC |
| B05 | E. Y. Chow, A. S. Willsky, "Analytical redundancy and the design of robust failure detection systems", *IEEE Trans. Automatic Control* AC-29:603–614, 1984 | NTRS 19840056958; https://ntrs.nasa.gov/citations/19840056958 | C1, C2, C3 | SC |
| B06 | P. M. Frank, "Fault diagnosis in dynamic systems using analytical and knowledge-based redundancy: a survey and some new results", *Automatica* 26(3):459–474, 1990 | https://www.semanticscholar.org/paper/f8b5a731c266b463c6d744b193e1e1f76e5def85 | C1, C2, C3 | SC |
| B07 | R. Isermann, P. Ballé, "Trends in the application of model-based fault detection and diagnosis of technical processes", *Control Engineering Practice* 5(5):709–719, 1997. It proposes the IFAC SAFEPROCESS terminology | https://www.sciencedirect.com/science/article/abs/pii/S0967066197000531 | C9, crosswalk | SC |
| B08 | J. Gertler, *Fault Detection and Diagnosis in Engineering Systems*, Marcel Dekker, 1998. Structured residuals, the incidence matrix and coding sets, strong and weak isolability | https://www.semanticscholar.org/paper/e03c342670252eec29ca3380ba7939bf11631619 | C8, C11 | SC |
| B09 | M. Blanke, M. Kinnaert, J. Lunze, M. Staroswiecki, *Diagnosis and Fault-Tolerant Control*, Springer (editions 2003, 2006, 2016). Structural analysis chapter, pp. 109–188 of the 3rd edition | doi 10.1007/978-3-662-47943-8 and 10.1007/978-3-540-35653-0 | C2, C8, C10, C11 | SC; earlier repo record S055 RP |
| B10 | M. Basseville, I. V. Nikiforov, *Detection of Abrupt Changes: Theory and Application*, Prentice-Hall, 1993 | https://dl.acm.org/doi/abs/10.5555/151741 | L1 | SC |
| B11 | E. S. Page, "Continuous inspection schemes", *Biometrika* 41, 1954 (CUSUM) | `research/math-paper/PRIOR_ART_MATRIX.csv` | L1 | RP |
| B12 | D. T. Magill, "Optimal adaptive estimation of sampled stochastic processes", *IEEE Trans. Automatic Control* 10(4):434–439, 1965 (the origin of the multiple-model bank) | https://ieeexplore.ieee.org/document/1098191/ | C3 | SC |
| B13 | H. A. P. Blom, Y. Bar-Shalom, "The interacting multiple model algorithm for systems with Markovian switching coefficients", *IEEE Trans. Automatic Control* 33(8):780–783, 1988 | https://research.tudelft.nl/en/publications/the-interacting-multiple-model-algorithm-for-systems-with-markovi/ | C3 | SC |
| B14 | V. Venkatasubramanian, R. Rengaswamy, K. Yin, S. N. Kavuri, "A review of process fault detection and diagnosis, Part I: quantitative model-based methods", *Computers & Chemical Engineering* 27:293–311, 2003 | https://www.ece.lsu.edu/mcu/lawss/add_materials/FaultDetectionPart1.pdf | C11 | SC |
| B15 | M. Iri et al., "An algorithm for diagnosis of system failures in the chemical process", *Computers & Chemical Engineering*, 1979 (the signed directed graph) | https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2021.641545/full (secondary) | C11 | SS |
| B16 | M. A. Kramer, B. L. Palowitch, "A rule-based approach to fault diagnosis using the signed directed graph", *AIChE Journal*, 1987 | https://aiche.onlinelibrary.wiley.com/doi/abs/10.1002/aic.690330115 (a related Kramer 1987 paper) | C11 | SS |
| B17 | "A signed directed graph-based systematic framework for steady-state malfunction diagnosis inside control loops", *Chemical Engineering Science*, c. 2006. Authors not shown | https://www.sciencedirect.com/science/article/abs/pii/S0009250905007967 | C4 | SS |
| B18 | I. Hwang, S. Kim, Y. Kim, C. E. Seah, "A survey of fault detection, isolation, and reconfiguration methods", *IEEE Trans. Control Systems Technology* 18(3):636–653, 2010 | doi 10.1109/TCST.2009.2026285 | C9, C10 | SC |
| B19 | Y. M. Zhang, J. Jiang, "Bibliographical review on reconfigurable fault-tolerant control systems", *Annual Reviews in Control* 32:229–252, 2008 | doi 10.1016/j.arcontrol.2008.03.008 | C10 | SC |
| B20 | T. A. Johansen, T. I. Fossen, "Control allocation—a survey", *Automatica* 49(5):1087–1103, 2013 | doi 10.1016/j.automatica.2013.01.035 | C4 | SC |
| B21 | A. Cristofaro, T. A. Johansen, "Fault tolerant control allocation using unknown input observers", *Automatica* 50(7):1891–1897, 2014. Allocation uses input redundancy to make actuator faults observable | arXiv 1306.5369 | C4, active evidence | SC |
| B22 | R. Dunia, S. J. Qin, T. F. Edgar, T. J. McAvoy, "Identification of faulty sensors using principal component analysis", *AIChE Journal* 42(10):2797–2812, 1996 (introduces the sensor validity index) | doi 10.1002/aic.690421011 | C1, crosswalk | SC |
| B23 | "On fault detectability and isolability", *European Journal of Control*, 2001. Authors not shown in the snippet. It relates two isolability definitions for sensor and actuator faults in linear systems | https://www.sciencedirect.com/science/article/abs/pii/S0947358001702026 | C18 | SS |
| B24 | M. Krysander, J. Åslund, M. Nyberg, "An efficient algorithm for finding minimal overconstrained subsystems for model-based diagnosis", *IEEE Trans. Systems, Man, and Cybernetics A*, 2008 (MSO sets) | https://drops.dagstuhl.de/entities/document/10.4230/OASIcs.DX.2024.13 (secondary) | C11, C14 | SC |
| B25 | M. Krysander, M. Nyberg, "Fault isolability prediction of diagnostic models", DX 2005 | https://www.fs.isy.liu.se/Publications/Articles/DX_05_MK_MN.pdf | C18 | SS |
| B26 | B. Pulido, C. Alonso-González, "Possible conflicts: a compilation technique for consistency-based diagnosis", *IEEE Trans. SMC B* 34(5):2192–2206, 2004 | doi 10.1109/TSMCB.2004.835007 | C7 | SC |
| B27 | M.-O. Cordier, P. Dague, F. Lévy, J. Montmain, M. Staroswiecki, L. Travé-Massuyès, "Conflicts versus analytical redundancy relations: a comparative analysis of the model based diagnosis approach from the artificial intelligence and automatic control perspectives", *IEEE Trans. SMC B* 34(5):2163–2177, 2004 | doi 10.1109/TSMCB.2004.835010; https://hal.science/hal-01931749 | C8, C12, crosswalk | SC |

## B. Model-based diagnosis in artificial intelligence (the DX community), temporal and hybrid diagnosis

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B28 | R. Reiter, "A theory of diagnosis from first principles", *Artificial Intelligence* 32(1):57–95, 1987 | https://www.sciencedirect.com/science/article/abs/pii/0004370287900622 | C8, C12 | SC |
| B29 | J. de Kleer, B. C. Williams, "Diagnosing multiple faults", *Artificial Intelligence* 32(1):97–130, 1987 (GDE) | https://dekleer.org/Publications/Diagnosing%20Multiple%20Faults%20AIJ%20reprint.pdf | C8 | SC |
| B30 | P. Struss, O. Dressler, "'Physical negation': integrating fault models into the general diagnostic engine", IJCAI 1989 (GDE+) | https://www.researchgate.net/publication/2611807_Assumptions_in_Model-based_Diagnosis (secondary) | C16 | SS |
| B31 | L. Console, P. Torasso, "A spectrum of logical definitions of model-based diagnosis", *Computational Intelligence* 7(3):133–141, 1991 | doi 10.1111/j.1467-8640.1991.tb00388.x | C12, L5 | SC |
| B32 | V. Brusoni, L. Console, P. Terenziani, D. Theseider Dupré, "A spectrum of definitions for temporal model-based diagnosis", *Artificial Intelligence* 102(1):39–79, 1998 | https://www.sciencedirect.com/science/article/pii/S0004370298000447 | C6 | SC |
| B33 | B. Kuipers, "Qualitative simulation", *Artificial Intelligence* 29(3):289–338, 1986 | https://www.cs.utexas.edu/ftp/qsim/papers/Kuipers-aij-86-els.pdf | L1 | SC |
| B34 | J. de Kleer, J. S. Brown, "A qualitative physics based on confluences", *Artificial Intelligence* 24(1–3):7–83, 1984 | (secondary) https://www.cs.utexas.edu/ftp/qsim/papers/Kuipers-aij-93b.pdf | L1 | SS |
| B35 | U. Lerner, R. Parr, D. Koller, G. Biswas, "Bayesian fault detection and diagnosis in dynamic systems", AAAI 2000 (hybrid dynamic Bayesian networks; covers measurement errors and drifts) | https://cdn.aaai.org/AAAI/2000/AAAI00-081.pdf | C7 | SC |
| B36 | M. Sampath, R. Sengupta, S. Lafortune, K. Sinnamohideen, D. Teneketzis, "Diagnosability of discrete-event systems", *IEEE Trans. Automatic Control* 40(9):1555–1575, 1995 | http://wpage.unina.it/detommas/sed/1995_Sampath_Diagnosability_Automata.pdf | C14, C15 | SC |
| B37 | P. J. Mosterman, G. Biswas, "Diagnosis of continuous valued systems in transient operating regions", *IEEE Trans. SMC A* 29(6):554–565, 1999 (TRANSCEND). Fault signatures of the predicted transient; progressive monitoring until transient analysis gives way to steady-state analysis | https://ieeexplore.ieee.org/document/798059/ | C5, C6, C7 | SC |
| B38 | M. Daigle, X. Koutsoukos, G. Biswas, "A qualitative event-based approach to continuous systems diagnosis", *IEEE Trans. Control Systems Technology*, 2009 (volume unconfirmed). Relative measurement orderings; see also the Allerton 2005 paper | http://matthewjdaigle.com/pubs/DaigleEtAl-QualitativeEventBasedApproachFaultDiagnosisContinuousSystems.pdf | C5, C6, C7 | SC |
| B39 | M. Daigle et al., "Qualitative event-based diagnosis with possible conflicts applied to spacecraft power distribution systems", IFAC SAFEPROCESS 2012 | https://c3.ndc.nasa.gov/dashlink/static/media/publication/8-DaigleEtAl-QED-Safeprocess2012.pdf | C7 | SC |
| B40 | J. Meseguer, V. Puig, T. Escobet, "Fault diagnosis using a timed discrete-event approach based on interval observers: application to sewer networks", c. 2010 (venue unconfirmed). Separate fault signature matrices for the Boolean, sensitivity, occurrence-order and occurrence-time properties | https://digital.csic.es/bitstream/10261/38926/1/Fault%20Diagnosis%20Using.pdf | C5, C6 | SS |
| B41 | S. Narasimhan, G. Biswas, "Model-based diagnosis of hybrid systems", *IEEE Trans. SMC A* 37(3):348–361, 2007 | https://link.springer.com/chapter/10.1007/978-3-540-78929-1_47 (related) | C7 | SC |
| B42 | S. Narasimhan, L. Brownston, "HyDE – a general framework for stochastic and hybrid model-based diagnosis", DX 2007 | https://citeseerx.ist.psu.edu/document?repid=rep1&type=pdf&doi=f879efb7a64e346e29fe74109b629b45d624a14e | C7, C12 | SC |
| B101 | A. Cimatti, C. Pecheur, R. Cavada, "Formal verification of diagnosability via symbolic model checking", IJCAI 2003 | https://mlanthology.org/ijcai/2003/cimatti2003ijcai-formal/ | C14 | SS |
| B102 | C.-W. Kong, J. McMahon, M. Lahijanian, "Bayesian diagnosability and active fault identification", 2025 | arXiv 2509.04708 | C14, active | RP (S049) |
| B103 | L. K. Carvalho, J. C. Basilio, M. V. Moreira, "Robust diagnosis of discrete event systems against intermittent loss of observations", *Automatica* 48(9), 2012 | `research/math-paper/PRIOR_ART_MATRIX.csv` | C15 | RP |
| B104 | W. Dong, X. Yin, S. Li, "Verification of diagnosability for discrete-event systems under state-dependent observations", *IEEE Trans. Automatic Control* 69(1), 2024 | `research/math-paper/PRIOR_ART_MATRIX.csv` | C15 | RP |
| B105 | M. Speekenbrink, I. Visser, "State-dependent missingness in hidden Markov models", *Psychometrika*, 2025 | `research/math-paper/PRIOR_ART_MATRIX.csv` | C15 | RP |

## C. Multiple-model, sensor-versus-actuator and aircraft FDI

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B43 | Y. M. Zhang, X. R. Li, "Detection and diagnosis of sensor and actuator failures using IMM estimator", *IEEE Trans. Aerospace and Electronic Systems* 34(4):1293–1313, 1998 | doi 10.1109/7.722715 | C3, XSYS Q2 | SC |
| B44 | P. S. Maybeck, "Multiple model adaptive algorithms for detecting and compensating sensor and actuator/surface failures in aircraft flight control systems", *Int. J. Robust and Nonlinear Control* 9(14):1051–1070, 1999. VISTA F-16; a bank of Kalman filters, one per failure hypothesis, plus command redistribution | https://onlinelibrary.wiley.com/doi/10.1002/(SICI)1099-1239(19991215)9:14%3C1051::AID-RNC452%3E3.0.CO;2-0 | C3, C10, XSYS Q2 | SC |
| B45 | P. Lu, L. Van Eykeren, E. van Kampen, C. de Visser, Q. Chu, "Double-model adaptive fault detection and diagnosis applied to real flight data", *Control Engineering Practice* 36:39–57, 2015 | https://www.sciencedirect.com/science/article/abs/pii/S0967066114002809 | C3 | SC |
| B46 | T. Kobayashi, D. L. Simon, "Application of a bank of Kalman filters for aircraft engine fault diagnostics", ASME Turbo Expo GT2003 (also NASA TM). Uses m+1 filters: one for component and actuator faults, one per sensor | NTRS 20030067984; https://ntrs.nasa.gov/api/citations/20030067984/downloads/20030067984.pdf | C2, XSYS Q2 | SC |
| B47 | T. Kobayashi, D. L. Simon, "Aircraft engine sensor/actuator/component fault diagnosis using a bank of Kalman filters", NASA report, 2003 | NTRS 20030032975 | C2, XSYS Q2 | SC |
| B48 | M. H. Amoozgar, A. Chamseddine, Y. Zhang, "Experimental test of a two-stage Kalman filter for actuator fault detection and diagnosis of an unmanned quadrotor helicopter", *J. Intelligent & Robotic Systems*, 2012/2013. Rotor loss of effectiveness, Qball-X4 | doi 10.1007/s10846-012-9757-7 | C3, C4 | SC |
| B49 | A. Freddi, S. Longhi, A. Monteriù, "A model-based fault diagnosis system for a mini-quadrotor", c. 2009 (Thau observer) | https://www.researchgate.net/publication/261550850 | C3 | SS |
| B50 | "Rotor fault detection and isolation in aerial vehicles with dozens of rotors". Authors not shown. Roll and pitch tracking error orders the faulty-rotor search space | https://par.nsf.gov/biblio/10609864-rotor-fault-detection-isolation-aerial-vehicles-dozens-rotors | XSYS Q3, Q4 | SS |
| B51 | "Multirotor motor failure detection with piezo sensor", *Sensors*, c. 2023. The snippet describes a high PWM command with insufficient attitude change, confirmed by ESC RPM | https://pmc.ncbi.nlm.nih.gov/articles/PMC9862776/ | XSYS Q3, Q4 | SS |
| B52 | "In-hover quadrotor rotor degradation monitoring using null-space excitation and lock-in detection", *Drones* 10(5):395, 2026. Active excitation; closed-loop interactions obscure rotor-specific anomalies | doi 10.3390/drones10050395 | active evidence, XSYS | SS |
| B53 | "Propeller damage detection, classification and estimation in multirotor vehicles", 2024 | arXiv 2410.05447 | XSYS | SS |
| B54 | "Actuator fault detection, identification, and control of a multirotor air vehicle using residual generation and parameter estimation approaches", *Int. J. Aeronautical and Space Sciences*, 2023 | doi 10.1007/s42405-023-00633-0 | C3 | SS |
| B106 | J. A. Guzmán-Rabasa et al., "Actuator fault detection and isolation on a quadrotor unmanned aerial vehicle modeled as a linear parameter-varying system", *Measurement and Control*, 2019 | doi 10.1177/0020294018824764 | C3 | SS |
| B107 | "Aircraft sensor and actuator fault detection, isolation, and accommodation", *J. Aerospace Engineering* 24(1), 2011. Authors not shown | doi 10.1061/(ASCE)AS.1943-5525.0000052 | C3 | SS |

## D. Deployed products and documentation

| id | reference | URL | bears on | status |
|---|---|---|---|---|
| B55 | ArduPilot Copter documentation, "Thrust Loss and Yaw Imbalance Warnings". A motor saturating at 100 % means the requested roll, pitch, yaw and throttle can no longer be achieved; a failed ESC, motor or propeller drives that motor's output to maximum. Issues #7525 and #11929 | https://ardupilot.org/copter/docs/thrust_loss_yaw_imbalance.html | C4, XSYS Q4 | SC |
| B56 | PX4 User Guide, "Motor Failure Recovery" and "Safety (Failsafe) Configuration". It checks ESC current against the motor command (MOTFAIL_C2T, MOTFAIL_OFF, MOTFAIL_TIME). The check latches, because recovery stops the failed motor, *which would otherwise make it look healthy again* | https://docs.px4.io/main/en/config/motor_failure_recovery | C4, C15 | SC |

## E. IVHM, ISHM, vehicle-level reasoning, testability

IVHM is integrated vehicle health management. ISHM is integrated system
health management.

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B57 | G. B. Aaseng, "Blueprint for an integrated vehicle health management system", 20th Digital Avionics Systems Conference (DASC), 2001 | https://ieeexplore.ieee.org/document/963350/ | C12 | SC |
| B58 | "The Honeywell on-board diagnostic and maintenance system for the Boeing 777", IEEE DASC, 1992. Authors not shown. The central maintenance function screens out **cascaded** faults across LRUs (line-replaceable units); for example, a 115 VAC bus failure makes many LRUs appear failed | https://ieeexplore.ieee.org/document/282113/ | C2, C11 | SC |
| B59 | D. Mylaraswamy et al. (Honeywell), "Vehicle Integrated Prognostic Reasoner (VIPR) final report", NASA/CR-2013-217972. Also the 2010 annual report and the Metric Report | NTRS 20130011181, 20110012171, 20130012455; https://c3.ndc.nasa.gov/dashlink/static/media/other/avsafe_vipr-2011.pdf | C2, C8, C12 | SC |
| B60 | A. N. Srivastava, D. Mylaraswamy, R. W. Mah, E. G. Cooper, "Vehicle-level reasoning systems: integrating system-wide data to estimate the instantaneous health state", book chapter (NASA DASHlink) | https://c3.ndc.nasa.gov/dashlink/static/media/publication/VLRS_Chapter_v10-dashlink.pdf | C2, C12 | SC |
| B61 | F. Figueroa et al., "Integrated system health management: foundational concepts, approach, and implementation"; also the ISHM for the test stand and J-2X engine | NTRS 20100021235, 20080015891 | C12 | SC |
| B62 | S. Deb, K. R. Pattipati, V. Raghavan, M. Shakeri, R. Shrestha, "Multi-signal flow graphs: a novel approach for system testability analysis and fault diagnosis", *IEEE AES Magazine*, 1995 (TEAMS, D-matrix). Author list beyond Deb and Pattipati unconfirmed | https://www.researchgate.net/publication/229034100 | C8, C11 | SC |
| B63 | IEEE Std 1232-2010, "Artificial Intelligence Exchange and Service Tie to All Test Environments (AI-ESTATE)"; also IEC 62243 | https://ieeexplore.ieee.org/document/5743076/ | C9, crosswalk | SC |
| B64 | MIL-STD-2165, "Testability Program", 1985; MIL-HDBK-2165, 1995. Specifies BIT false-alarm rate and fault isolation to N sub-items. See also IEEE P1522 testability metrics | https://www.dsiintl.com/wp-content/uploads/2017/04/mil_std_2165.pdf; https://www.cs.montana.edu/sheppard/pubs/auto-2001b.pdf | C8, C17 | SC |
| B65 | T. Kurtoglu et al., "First International Diagnosis Competition – DXC'09", DX 2009; also DXC'10, '11 and '13 | NTRS 20100024257 | C17 | SC |
| B66 | B. C. Williams, P. P. Nayak, "A model-based approach to reactive self-configuring systems", AAAI 1996 (Livingstone, Deep Space 1). Mode identification plus mode reconfiguration | https://aaai.org/papers/144-aaai96-144-a-model-based-approach-to-reactive-self-configuring-systems/ | C9, C10, C12 | SC |
| B67 | T. Reinbacher, K. Y. Rozier, J. Schumann, "Temporal-logic based runtime observer pairs for system health management of real-time systems", TACAS 2014 (R2U2) | doi 10.1007/978-3-642-54862-8_24 | C6, C7, C12 | SC |
| B68 | J. Schumann, K. Y. Rozier, T. Reinbacher, O. J. Mengshoel, T. Mbaya, C. Ippolito, "Towards real-time, on-board, hardware-supported sensor and software health management for unmanned aerial systems", PHM 2013 and *IJPHM* 2015. Author list partly unconfirmed | NTRS 20160001256; https://papers.phmsociety.org/index.php/ijphm/article/view/2243 | C7, C12 | SC |
| B69 | R. Hipler, M. Leucker, P. Rodler, "A unified framework for runtime verification and model-based diagnosis in LOLA", June 2026 | arXiv 2606.23720 | C7, C12 | SC |
| B108 | "The NASA integrated vehicle health management technology experiment for X-37" | https://www.researchgate.net/publication/228806692 | C12 | SS |
| B109 | "Characterization of model-based reasoning strategies for use in IVHM", NASA | NTRS 20030032435 | C12 | SS |
| B110 | "Advances in integrated system health management for mission-essential and safety-critical aerospace applications", *Progress in Aerospace Sciences*, 2021 | https://www.sciencedirect.com/science/article/pii/S0376042121000622 | C12 | SS |

## F. Formal FDI, guaranteed and active diagnosis

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B70 | A. Bauer, M. Leucker, C. Schallhart, "Runtime verification for LTL and TLTL", *ACM TOSEM* 20(4), 2011. Three verdicts: true, false, inconclusive | doi 10.1145/2000799.2000800 | C13 | SC |
| B71 | M. Bozzano, A. Cimatti, M. Gario, S. Tonetta, "Formal design of asynchronous fault detection and identification components using temporal epistemic logic", *Logical Methods in Computer Science* 11(4), 2015. A language for FDI requirements (correctness, completeness, maximality, trace-diagnosability); synthesis; aerospace case study. TACAS 2014 version: doi 10.1007/978-3-642-54862-8_22 | https://lmcs.episciences.org/1605; arXiv 1506.04871 | C9, C17 | SC |
| B72 | P. Rosa, C. Silvestre, J. S. Shamma, M. Athans, "Fault detection and isolation of LTV systems using set-valued observers", IEEE CDC 2010. Model invalidation; no false alarm while the bounds and the model hold. Later applied to a fixed-wing aircraft | https://www.wikidata.org/wiki/Q58488615; https://www.sciencedirect.com/science/article/abs/pii/S0967066112002262 | C8, C17 | SC |
| B73 | D. M. Raimondo, G. R. Marseglia, R. D. Braatz, J. K. Scott, "Closed-loop input design for guaranteed fault diagnosis using set-valued observers", *Automatica*, 2016 | https://web.mit.edu/braatzgroup/Raimondo_Automatica_2016.pdf | active, C17 | SC |
| B74 | H. Niemann, "A setup for active fault diagnosis", *IEEE Trans. Automatic Control* 51(9):1572–1578, 2006 | https://eudml.org/doc/207902 (related) | active | SC |
| B75 | R. Nikoukhah, S. L. Campbell, "Auxiliary signal design for active failure detection in uncertain linear systems with a priori information", *Automatica* 42(2):219–228, 2006 | (listed with B74) | active | SC |
| B76 | I. Matei, W. Piotrowski, A. Perez, J. de Kleer, J. Tierno, W. Mungovan, V. Turnewitsch, "System resilience through health monitoring and reconfiguration", *ACM Trans. Cyber-Physical Systems* 8(1), 2024 | doi 10.1145/3631612 | C10, C12 | SC; RP |
| B77 | A. Paoli, S. Lafortune, "Safe diagnosability for fault-tolerant supervision of discrete-event systems", *Automatica*, 2005 | `research/math-paper/PRIOR_ART_MATRIX.csv` | C10 | RP |
| B111 | M. Harirchi, N. Ozay, "Guaranteed model-based fault detection in cyber-physical systems: a model invalidation approach" | arXiv 1609.05921 | C17 | SS |
| B112 | "Set-based guaranteed active fault diagnosis for LPV systems with unknown bounded uncertainties", *Automatica*, 2021 | https://www.sciencedirect.com/science/article/abs/pii/S0005109821001229 | active, C17 | SS |

## G. Runtime assurance, assurance cases, certification

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B79 | L. Sha, "Using simplicity to control complexity", *IEEE Software* 18(4), 2001 (Simplex) | doi 10.1109/MS.2001.936213 | C10 | SC |
| B80 | J. D. Schierman et al. (Barron Associates), "Runtime assurance framework development for highly adaptive flight control systems", AFRL-RQ-WP-TR-2016-0001, 2015. See also *JGCD* 2020, doi 10.2514/1.G004862 | https://apps.dtic.mil/sti/pdfs/AD1010277.pdf | C10 | SC |
| B81 | ASTM F3269-17/-21, "Standard practice for methods to safely bound behavior of aircraft systems containing complex functions using run-time assurance"; also the AIAA SciTech paper describing it | https://elib.dlr.de/144352/1/latestsubmission_v1_ASTM%20F3269_SciTech_Control-ID_3453655.pdf | C10 | SC; RP (S002, S003) |
| B82 | FAA, DOT/FAA/TC-17/59, "Initial investigations into alternate certification approaches using run-time assurance for small aircraft autopilots"; also NASA NTRS 20170007254 | https://rosap.ntl.bts.gov/view/dot/57738 | C10 | SC |
| B83 | FAA, DOT/FAA/TC-16/4, verification of adaptive systems (NASA Langley and Honeywell) | https://www.faa.gov/sites/faa.gov/files/aircraft/air_cert/design_approvals/air_software/TC-16-4.pdf | C10 | SC |
| B84 | D. Schneider, M. Trapp, conditional safety certificates (ConSerts), including "Conditional safety certification of open adaptive systems" | https://www.iese.fraunhofer.de/en/services/safety-engineering/conserts.html; https://www.researchgate.net/publication/221246468 | C10 | SC |
| B85 | E. Denney, G. Pai, I. Habli, "Dynamic safety cases for through-life safety assurance", ICSE 2015 | NTRS 20150011054 | C10 | SC |
| B86 | R. Hawkins, T. Kelly, J. Knight, P. Graydon, "A new approach to creating clear safety arguments", Advances in Systems Safety, Springer, 2011. Assured safety arguments with a separate confidence argument | doi 10.1007/978-0-85729-133-2_1 | crosswalk (evidence sufficiency) | SC |
| B113 | NASA/CR-20210026909, "Run time assurance for electric vertical takeoff and landing aircraft" | https://ntrs.nasa.gov/api/citations/20210026909/downloads/NASA-CR-20210026909.pdf | C10 | SS |

## H. Navigation integrity and sensor validity status

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B87 | Receiver autonomous integrity monitoring (RAIM) and advanced RAIM (ARAIM). Protection level against alert limit: when the protection level exceeds the alert limit, integrity is insufficient to perform the procedure. Covers fault detection and exclusion (FDE) and integrity risk. Sources: the ICAO RAIM introduction (2025) and a survey in *Frontiers in Physics* (2025) | https://www.icao.int/sites/default/files/APAC/Meetings/2025/2025%20PBNICG%2012/WPs%20IPs%20Presentations/SP05-ICAO_AI6-Introduction-to-Receiver-Autonomous-Integrity-Monitoring-RAIM.pdf; doi 10.3389/fphy.2025.1567301 | C9, C10 | SC |
| B88 | "A solution separation monitor using INS for detecting GNSS spoofing", ION GNSS+ 2020 (Illinois Tech NavLab) | http://www.navlab.iit.edu/uploads/5/9/7/3/59735535/a_solution_separation_monitor_using_ins_for_detecting_gnss_spoofing__gnss__2020__rev_c.pdf | C1, C3 | SS |
| B89 | M. P. Henry, D. W. Clarke, "The self-validating sensor: rationale, definitions and examples", *Control Engineering Practice* 1(4):585–610, 1993. Defines the validated measurement value, the validated uncertainty and the measurement value status (for example CLEAR, DAZZLED, BLIND) | https://www.sciencedirect.com/science/article/abs/pii/0967066193913827 | C13, crosswalk | SC; RP |
| B90 | "Model-based diagnosis of sensor faults for ESP systems", *Control Engineering Practice*, c. 2004. Authors not shown | https://www.sciencedirect.com/science/article/abs/pii/S0967066103002430 | C1, C3 | SS |
| B114 | "Yaw rate and lateral acceleration sensor plausibilisation in an active front steering vehicle", Linköping MSc thesis, 2006 | https://www.diva-portal.org/smash/get/diva2:22916/FULLTEXT01.pdf | C1, C3 | SS |

## I. CPS security, attack–fault discrimination, trust

CPS is cyber-physical systems.

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B92 | H. Choi, W.-C. Lee, Y. Aafer, F. Fei, Z. Tu, X. Zhang, D. Xu, X. Deng, "Detecting attacks against robotic vehicles: a control invariant approach", ACM CCS 2018, pp. 801–816 | https://github.com/hongjun9/CPS_Invariant; https://www.researchgate.net/publication/328325396 | C3 | SC |
| B93 | R. Quinonez, J. Giraldo, L. Salazar, E. Bauman, A. Cardenas, Z. Lin, "SAVIOR: securing autonomous vehicles with robust physical invariants", USENIX Security 2020 | https://www.usenix.org/system/files/sec20_slides_quinonez.pdf | C3 | SC |
| B94 | "Distinguishable attack and fault detection in interconnected cyber–physical systems", *Control Engineering Practice*, 2024 | https://www.sciencedirect.com/science/article/abs/pii/S0967066124003757 | C2 | SS |
| B95 | "Trust-based assured sensor fusion in distributed aerial autonomy", ICCPS 2025. Trust measures consistency with physical laws through kinematic models and with other trusted agents | doi 10.1145/3716550.3722038; arXiv 2507.17875 | C1, C3, C11 | SS |
| B115 | "Diagnosis-guided attack recovery for securing robotic vehicles from sensor deception attacks" | arXiv 2209.04554 | C2, C3 | SS |
| B116 | "Inferring anomaly situation from multiple data sources in cyber physical systems". Consistency analysis separates cyber attack, physical damage and system fault | https://pmc.ncbi.nlm.nih.gov/articles/PMC7888293/ | C2 | SS |

## J. Evidence theory, contingency management, closed-loop masking

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B96 | O. Basir, X. Yuan, "Engine fault diagnosis based on multi-sensor information fusion using Dempster–Shafer evidence theory", *Information Fusion* 8(4):379–386, 2007 | https://sciencedirect.com/science/article/pii/S156625350500076X | C8 | SC |
| B97 | L. Tang, G. Kacprzynski et al., "Prognostics-enhanced automated contingency management for advanced autonomous systems", PHM 2008; also "Simulation-based design and validation of automated contingency management for propulsion systems", IEEE Aerospace Conference 2007 | https://c3.ndc.nasa.gov/dashlink/static/media/publication/25_Prognsotics_Enhanced_ACM_for_Advanced_Autonomous.pdf | C10 | SC |
| B98 | M. Valenti, B. Bethke et al., "Embedding health management into mission tasking for UAV teams", ACC 2007 | https://www.researchgate.net/publication/228962240 (related) | C10 | SS |
| B99 | "Anomaly detection under closed-loop fault masking: a case study comparing one-class and supervised approaches on a two-tank level control system", Springer LNCS chapter, 2026. Adds controller-internal variables to reveal compensation | https://link.springer.com/chapter/10.1007/978-3-032-29254-4_6 | C4 | SS |
| B100 | "The negative impact of closed-loop control on fault detection", University of Manchester. Details not shown | https://research.manchester.ac.uk/en/publications/the-negative-impact-of-closed-loop-control-on-fault-detection/ | C4 | SS |

## K. Patents (technical prior-art screen only; no claim read)

| id | patent | assignee / inventors (as shown) | bears on | status |
|---|---|---|---|---|
| P01 | US 4,641,517, "Control system actuator position synthesis for failure detection". Sensed position is compared with a model-synthesized position, and a routine decides whether the fault is in the **sensors or the common actuator** | not shown | C3, XSYS Q2 | SS |
| P02 | US 4,841,209, "Actuator control system with displacement sensor fault detection". Notes that earlier systems could not discriminate between fault types | not shown | XSYS Q2 | SS |
| P03 | US 10,557,418, "On-board estimator actuator system fault accommodation in engine control" (EPOS). Actuator-sensor in-range drift and actuator hardware failure both break tracking; **the engine response distinguishes them** | not shown | C2, C3, XSYS Q1–Q3 | SS |
| P04 | US 11,203,950, "On-board estimator engine sensor fault accommodation in engine control" | not shown | XSYS Q2 | SS |
| P05 | US 11,319,834 B2 / US 2019/0226354 A1 / EP 3527805 A1, "On-board estimator sensor drift detection in engine control" | not shown | XSYS Q2 | SS |
| P06 | US 11,061,390 B2 / EP 3477412 A1, "System fault isolation and ambiguity resolution". Ranks ambiguity groups, locates supporting evidence in a diagnosis matrix, aggregates belief | RTX Corp. (formerly Raytheon Technologies); A. J. Volponi, L. Tang, S. J. Lee | C8, C2 | SC |
| P07 | US 12,134,484, "System and method for contextually-informed fault diagnostics using structural-temporal analysis of fault propagation graphs". An aircraft reasoner with a fault-pattern library | not shown | C7, C11 | SS |
| P08 | US 12,087,171, "Assurance module". A run-time assurance module for dynamic contexts (UAV, single-pilot operation) | not shown | C10 | SS |
| P09 | US 12,397,908 B1, "Sensorless propeller damage detection systems and methods". Compares commanded with measured RPM and looks for current ripple, then mitigates | Amazon Technologies, Inc.; X. Wang et al. | C4, XSYS | SC |
| P10 | US 8,763,950 B2 / EP 2342609 B1, "Method and apparatus for aircraft sensor and actuator failure protection using reconfigurable flight control laws" | not shown | C3, C10 | SS |
| P11 | US 6,643,569 B2, "Method and system for detecting a failure or performance degradation in a dynamic system such as a flight vehicle" | Regents of the University of Michigan; R. H. Miller, W. B. Ribbens | C3 | SS |
| P12 | US 4,943,919, "Central maintenance computer system and fault data handling method" | The Boeing Company | C2, C11 | SS |
| P13 | US 7,181,374, "Qualitative diagnosis system and method" | not shown | C5, C7 | SS |
| P14 | US 7,934,125 / US 7,596,718, "Ranged fault signatures for fault diagnosis" | not shown | C5, C6 | SS |
| P15 | US 11,691,747, "Fault detection for a speed sensing system of a multi-engine rotorcraft" | not shown | XSYS Q2, Q3 | SS |
| P16 | US 7,970,583, "Degraded actuator detection" | not shown | C4 | SS |
| P17 | US 9,008,895 B2, "Non-deterministic maintenance reasoner and method" | not shown | C8 | SS |
| P18 | US 2009/0138141 A1, "Vehicle health monitoring system architecture for diagnostics and prognostics". Subsystem managers are fused into a vehicle-level decision | not shown | C2, C12 | SS |
| P19 | US 6,356,857, "Sensor validation apparatus and method" | not shown | C1 | SS |
| P20 | US 12,077,279, "System and method for detecting and mitigating a propeller failure condition" | not shown | XSYS | SS |
| P21 | US 7,191,041 B2, "Method for diagnosing as to signal plausibility with a speed sensor of a motor vehicle" | not shown | C1, C3 | SS |
| P22 | US 11,204,838, "Runtime model validation for partially-observable hybrid systems" | not shown | C10, C13 | SS |
| P23 | US 6,427,102 B1, "Method and device for sensor monitoring, especially for ESP system for motor vehicles" | not shown (believed Bosch; unconfirmed) | C1, C3 | SS |

# Stage 2 additions: source verification (2026-09-27)

This section is appended for the second-stage verification layer. The rows
above are unchanged.

**The statement "no full text was read for any entry" still holds for
B01–B116 and P01–P23, with two exceptions.** The fielded-autopilot sources
behind B55 and B56 were read in primary form in stage 2, as B130 and B131.

Stage 2 retested access. Only `raw.githubusercontent.com` answers; see
`research/csia_novelty_audit/NOVELTY_SEARCH_LOG.md` §S2.1. Primary text was
therefore reachable only for open-source code and documentation hosted there,
plus the local PX4 source tree at commit `547e2ca`. Every paper and patent
remains at V0.

Verification levels, as defined in the stage-2 brief:

| level | meaning |
|---|---|
| V0 | search result or snippet only |
| V1 | abstract verified |
| V2 | substantial primary-source text inspected |
| V3 | complete relevant primary source inspected |
| V4 | claim traced to an exact section, page, claim, equation or source line |

A source that could not be obtained is marked
**REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION**. That applies to every V0 entry
below. No entry reached V1, because no abstract page was reachable. The "bears
on" column cites the frozen stage-2 features `F01`–`F27`, which are defined in
`research/csia_novelty_audit/CSIA_NOVELTY_VERIFICATION.md` §3.

## L. Stage-2 sources

| id | reference | ids / URL | bears on | status |
|---|---|---|---|---|
| B117 | Alavi, Izadi-Zamanabadi, Hayes (initials not shown), "Robust fault detection and isolation technique for single-input/single-output closed-loop control systems that exhibit actuator and sensor faults", *IET Control Theory & Applications*, c. 2008. Per the search summary: frequency-shaped residuals; in closed loop a sensor fault is suppressed in the measured signal after a short time, and a residual built from **controller-demanded signals** reveals it | doi 10.1049/iet-cta:20070382; https://www.researchgate.net/publication/224347339 | F06, F07, F09; XSYS | SC; V0 |
| B118 | "Steady-state fault propagation characteristics and fault isolation in cascade electro-hydraulic control system", *Machines* 12(9):600, 2024. Authors not shown. Per the summary: feedback transfers, attenuates or mitigates the steady-state effect of **actuator** faults but not of **feedback-sensor** faults; final value theorem; a fault influence distribution matrix used for isolation | doi 10.3390/machines12090600 | F06, F07, F24; XSYS | SS; V0 |
| B119 | Hofbaur, Travé-Massuyès, Rienmüller, Bayoudh (initials not shown), "Overcoming non-discernibility through mode-sequence analytic redundancy relations in hybrid diagnosis and estimation", Annual Conference of the PHM Society, 2010. Per the summary: analytic redundancy relation (ARR) sets are valid per mode; mode-sequence ARRs discriminate modes that single-mode ARRs cannot | PHM Society conference archive, article 1938 (URL form unconfirmed); https://www.researchgate.net/publication/407252194 | F09, F12, F25 | SC; V0 |
| B120 | Stojcsics, Boursinos, Mahadevan, Koutsoukos, Karsai (initials not shown), "Fault-adaptive autonomy in systems with learning-enabled components", *Sensors* 21(18):6089, 2021. BlueROV2 underwater vehicle; an FDI learning-enabled component, an assurance monitor using inductive conformal prediction, and contingency management | doi 10.3390/s21186089; https://pmc.ncbi.nlm.nih.gov/articles/PMC8470782/ | F13, F15, F16, F19 | SC; V0 |
| B121 | T. L. Lai, "Sequential multiple hypothesis testing and efficient fault detection-isolation in stochastic systems", *IEEE Trans. Information Theory* 46(2):595–608, 2000 | IEEE Xplore document 825826 | F13, F22 | SC; V0 |
| B122 | I. V. Nikiforov, "A generalized change detection problem", *IEEE Trans. Information Theory* 41(1):171–187, 1995. Detection and isolation under a false-alarm constraint and a **probability-of-false-isolation** constraint; an asymptotically optimal CUSUM-type procedure | — | F13, F14, F22 | SC; V0 |
| B123 | "Actuator and sensor fault detection and diagnosis for unmanned quadrotor helicopters", *IFAC-PapersOnLine*, 2018. Authors not shown. Interacting multiple model (IMM); actuator loss of effectiveness against **IMU** sensor bias | https://www.sciencedirect.com/science/article/pii/S2405896318324285 | F06, F24; XSYS | SS; V0 |
| B124 | Waitman et al., "Flight evaluation of simultaneous actuator/sensor fault reconstruction on a quadrotor minidrone", *IET Control Theory & Applications*, 2021 | doi 10.1049/cth2.12180 | F06, F21, F24; XSYS | SS; V0 |
| B125 | "Fast fault detection on a quadrotor using onboard sensors and a Kalman filter approach", 2021. RPM, gyro and accelerometer with a control-effectiveness model; a loss-of-effectiveness factor per actuator | arXiv 2102.06439 | F05, F06; XSYS | SS; V0 |
| B126 | "Integrated vehicle health and fault contingency management for UAVs", in *Handbook of Unmanned Aerial Vehicles*, Springer. Authors not shown. On-board health-state assessment and automated contingency management | doi 10.1007/978-90-481-9707-1_46 | F03, F19 | SS; V0 |
| B127 | "Integration of fault diagnosis and control based on a trade-off between fault detectability and closed loop performance", *Journal of Process Control*, 2016 | https://www.sciencedirect.com/science/article/pii/S0959152415002413 | F07, F09 | SS; V0 |
| B128 | "Diagnosis in cyber-physical systems with fault protection assemblies", Springer, 2018. Protective actions interact with diagnosis | doi 10.1007/978-3-319-74962-4_8 | F09, F16 | SS; V0 |
| B129 | "Multiple fault diagnosis in complex physical systems". Authors not shown (possibly Daigle, Koutsoukos and Biswas; unconfirmed). Per the summary: fault masking and compensation, together with the relative time of occurrence, produce many observable signature sequences and lower diagnosability | academia.edu document 2832502 | F08, F09, F21 | SS; V0 |
| B130 | ArduPilot, branch `master` as served on 2026-09-27 (commit hash not returned by the raw host): `libraries/AP_Motors/AP_MotorsMatrix.cpp`, `check_for_failed_motor` (L405–461); `ArduCopter/crash_check.cpp`, `thrust_loss_check` (L100–181) and `yaw_imbalance_check` (L183–232); wiki `copter/source/docs/thrust_loss_yaw_imbalance.rst` (L19, L31). Primary source for B55 | https://raw.githubusercontent.com/ArduPilot/ardupilot/master/libraries/AP_Motors/AP_MotorsMatrix.cpp; https://raw.githubusercontent.com/ArduPilot/ardupilot/master/ArduCopter/crash_check.cpp; https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/copter/source/docs/thrust_loss_yaw_imbalance.rst | F05, F07, F09, F13, F19 | primary; **V4** (code), V3 (wiki) |
| B131 | PX4 Autopilot at commit `547e2caa9883bc1609325f02b4914b4e2482fe62`: `src/modules/commander/HealthAndArmingChecks/checks/escCheck.cpp` L310–330 (the comment at L318 and L323); `src/modules/commander/failure_detector/FailureDetector.cpp` (imbalanced-propeller metric, L75–93); `docs/en/config/motor_failure_recovery.md` L91–92. The files are byte-identical in the local tree used for the XSYS-001 apparatus, whose only added commit is the SIH effectiveness patch (`git diff` against `547e2ca` is empty for these files). Primary source for B56 | local clone at `547e2ca` | F06, F09, F13 | primary; **V4** |
| B132 | R2U2 runtime-verification engine, repository `README.md`: a Mission-time LTL (MLTL) stream engine that emits verdict streams. The Bayesian-network health-management layer of B68 is not in this repository | https://raw.githubusercontent.com/R2U2/r2u2/main/README.md | F08, F09 | primary (tool); V2. B67 and B68 themselves stay V0 |
| B133 | CPS_Invariant repository `README.md`, the artifact of B92: control invariants identified as state-space models by system identification and checked at run time, with ArduCopter SITL | https://raw.githubusercontent.com/hongjun9/CPS_Invariant/master/README.md | F04, F05, F07 | primary (artifact); V2. B92 itself stays V0 |
| B134 | Fault Diagnosis Toolbox (Python), repository `README.md`: "analysis and design of fault diagnosis systems for dynamic systems", structural analysis of large-scale models, fault isolability analysis, sensor placement and code generation. The user manual is on github.io, which is blocked | https://raw.githubusercontent.com/faultdiagnosistoolbox/pyfaultdiagnosistoolbox/master/README.md | F10, F11 | primary (tool); V2 |
| B135 | "An FDR-oriented approach to multiple sequential fault detection and isolation" (title as shown). Per the summary: sequential FDI whose probability of false isolation is bounded, exponentially in the thresholds | NSF Public Access Repository 10054666 | F13, F22 | SS; V0 |
| B136 | "Certified decisions", 2025. Probabilistic certificates attached to actions | arXiv 2502.17830 | F13, F15 | SS; V0 |
| B137 | An 802.11 packet-capture diagnosis system with the verdicts CONFIRMED, PLAUSIBLE, INSUFFICIENT_EVIDENCE and NO_ISSUE_FOUND, 2026 | arXiv 2606.06871 | F12, F13 | SS; V0 |
| B138 | Sensitivity-based fault detection and isolation for road-vehicle chassis sensors. Per the summary: the expected residual magnitude for each fault sets the detection sensitivity | https://pmc.ncbi.nlm.nih.gov/articles/PMC6111285/ | F13; the XSYS-001 witness gate | SS; V0 |
| B139 | "Conformal recovery-deadline certificates for runtime assurance of adapting controllers", 2026 | arXiv 2606.25371 | F15, F19, F20 | SS; V0 |
| B140 | PX4 issue #23734, "[Bug] False motor failure detected with Dshot telemetry", and a PX4 forum thread on missing ESC-telemetry current triggering motor-failure warnings. Field evidence that telemetry defects trip local motor-failure logic | https://github.com/PX4/PX4-Autopilot/issues/23734 (not reachable from this environment) | F06, F24; XSYS motivation | SS; V0 |
| B141 | "Actuator fault detection and isolation system for multirotor unmanned aerial vehicles" (title as shown). The S2Q30 summary describes an IMU-based nonlinear observer for motor failures and a second module that uses ESC motor speeds and currents to separate **motor failure from propeller damage**. Attribution of that description to this paper is unconfirmed | https://www.researchgate.net/publication/363399424 | F01, F06; XSYS | SS; V0 |
| B142 | "Consistency-based diagnosis using data-driven residuals and limited training data", *Control Engineering Practice*, 2025. Grey-box RNN residuals each carry a modelled **validity region**, and the consistency-based decision logic uses a residual only inside it (an out-of-distribution guard over the operating region, not a time window) | https://www.sciencedirect.com/science/article/pii/S0967066125000462; http://www.diva-portal.org/smash/get/diva2:1945175/FULLTEXT01.pdf (blocked, HTTP 403) | F09, F10 | SS; V0 |
| B143 | "A consistency-based robust diagnosis approach for temporal causal systems". Authors not shown | academia.edu document 115311414 | F10, F25 | SS; V0 |
| B144 | "Actuator fault diagnosis and severity identification of turbofan engines for steady-state and dynamic conditions", *Chinese Journal of Aeronautics*, 2024. Dynamic-effect compensation lets the method separate steady-state from transient conditions | https://www.sciencedirect.com/science/article/pii/S1000936124003856 | F08, F18 | SS; V0 |
| B145 | J. Marzat, H. Piet-Lahanier, F. Damongeot, E. Walter, "Control-based fault detection and isolation for autonomous aircraft", *Proc. IMechE Part G*, 2012. The closed-loop control objectives are used to generate residuals; a structural sensitivity analysis is reported | doi 10.1177/0954410011413834 | F07 | SC; V0 |
| B146 | Field reports that ESC RPM telemetry is unreliable: AM32 ESC firmware issue #155 (reported RPM values far out of range during spool-up), ArduPilot issue #31763 ("ESC to RPM sensor processing") and Rotorflight documentation (an external frequency sensor takes precedence over telemetry RPM) | https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware/issues/155; https://github.com/ArduPilot/ardupilot/issues/31763; https://rotorflight.org/docs/setup/rpm-measurement | F24; XSYS motivation | SS; V0 |
| B147 | "Limits of residual-based detection for physically consistent false data injection", 2026. Constructs physically consistent, manifold-constrained perturbations that bypass residual-based bad-data detection in AC power-system state estimation. It is a constructive "matched by design" corruption from the security literature | arXiv 2602.10162 | F23; XSYS case B | SS; V0 |

## M. Stage-2 patent additions and updates (technical prior-art screen only)

| id | patent | assignee / inventors (as shown) | bears on | status |
|---|---|---|---|---|
| P24 | US 9,725,187 B2, "Vehicle health management systems and methods"; pre-grant publication US 2010/0017049 A1, published 2010-01-21. Per the summary: a mission-critical module computes risk, confidence and benefit values; a flight-critical module compares a health score with a threshold before reconfiguration; vehicle information is filtered for internal and external consistency and for stability over time. A related family member, US 8,942,882, appeared in one result (unconfirmed) | The Boeing Company (as shown in the S2Q28 result); K. Swearingen, J. M. Keller | F13, F16, F19 | SS; V0 |
| P25 | US 11,905,891, "On-board estimator effector drift detection in engine control". Detects and accommodates in-range drift of effector parameters with an EPOS model that takes sensed effector measurements as an external input vector. A member of the EPOS family (P03–P05) | Raytheon Technologies Corp. (now RTX); inventor R. P. Meisner; a filing date of 2018-01-25 is shown (S2Q39). freepatentsonline shows US 2019/0226354 (P05) as assigned to United Technologies Corporation | F05, F06, F24 | SS; V0 |

**Update to P03–P05** (the EPOS family). S2Q35 surfaced search-rendered
patent text stating that actuator-sensor faults and actuator-hardware faults
share a minor-loop tracking error and are distinguished by the engine
response. It is quoted in `research/csia_novelty_audit/NOVELTY_SEARCH_LOG.md`
§S2.4. The family assignee is shown as United Technologies Corporation /
Raytheon Technologies (now RTX) (see P25). It is still V0.

**Update to P15** (US 11,691,747; publication US 2021/0380266 A1). The S2Q36
summary: shaft speed is compared with rotor speed; if shaft speed is higher, a
speed-sensing fault is declared; if lower, fuel flow is used to decide whether
the engine is still coupled to the rotor. This separates a speed-**sensor**
fault from a physical decoupling with a second physical channel. It is V0.

**Update to P07** (US 12,134,484). S2Q26 showed the assignee as The Boeing
Company and the inventors as Jason M. Keller, Lee Wang and James M. Ethington.
The stage-1 row above is left as written.

**No patent claim was read in either stage.** The patent screen in
`research/csia_novelty_audit/CSIA_PATENT_PRIOR_ART_SCREEN.md` is technical
triage. It is not a legal opinion on validity, infringement or freedom to
operate.

## N. Verification level of the 25 top threats

The threats `T01`–`T25` are the columns of
`research/csia_novelty_audit/CSIA_CLOSEST_PRIOR_ART_CLAIM_CHART.csv`.

| threat | sources | level | note |
|---|---|---|---|
| T01 | B130 (B55) | **V4** code; V3 wiki | functions read in full; line ranges recorded |
| T02 | B131 (B56) | **V4** | local tree at `547e2ca` |
| T03 | B37 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T04 | B38, B39 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T05 | B119 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T06 | B40 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T07 | B28, B29 | V0 | textbook material, not re-read in this session |
| T08 | B31 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T09 | B117 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T10 | B118 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION (open access, but the host is blocked) |
| T11 | P03, P04, P05 | V0 | claims not read; REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T12 | P01 | V0 | claims not read |
| T13 | B43, B44 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T14 | B123, B124 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T15 | B46, B47 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T16 | B67, B68; B132 | V0 paper; V2 tool | the tool README says nothing about the diagnosis layer |
| T17 | B59, B60 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T18 | P06 | V0 | claims not read |
| T19 | P07 | V0 | claims not read |
| T20 | P24 | V0 | claims not read |
| T21 | B121, B122 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T22 | B87 (B88) | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| T23 | B120 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION (open access, but the host is blocked) |
| T24 | B92; B133 | V0 paper; V2 artifact | |
| T25 | B76 | V0 | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
