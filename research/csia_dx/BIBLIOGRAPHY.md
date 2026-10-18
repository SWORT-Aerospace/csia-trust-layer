# CSIA-DX bibliography

Sources for the CSIA-DX problem-formalization and adversarial novelty review
(2026-09-28). Identifiers `Dnn` are cited by every file in
`research/csia_dx/`. The "audit id" column cross-references the same source
in `research/csia_novelty_audit/BIBLIOGRAPHY.md`, where one exists.

**Access.** This environment can reach only `raw.githubusercontent.com`; see
`research/csia_novelty_audit/NOVELTY_SEARCH_LOG.md` §S2.1. The USPTO, MDPI,
PubMed Central, arXiv and publisher hosts all return 000/403. So:

- every paper, patent and vendor page below is **V0**: a search-engine title
  and summary only. Each is marked **REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION**;
- the only exceptions are CSIA's own code (V4) and one tool README (V2);
- no abstract page was reachable, so nothing is at V1.

| level | meaning |
|---|---|
| V0 | search result or snippet only |
| V1 | abstract verified |
| V2 | substantial primary-source text inspected |
| V3 | complete relevant primary source inspected |
| V4 | claim traced to an exact section, page, claim, equation or source line |

Status codes: **SC** means corroborated by two or more results or an
indexing page; **SS** means a single search summary.

## Diagnosability, conditional and robust diagnosability

| id | reference | ids / URL | audit id | level |
|---|---|---|---|---|
| D01 | M. Sampath, R. Sengupta, S. Lafortune, K. Sinnamohideen, D. Teneketzis, "Diagnosability of discrete-event systems", *IEEE Trans. Automatic Control* 40(9), 1995 | ieeexplore 412626 | B36 | V0 SC |
| D02 | M. Sampath, S. Lafortune, D. Teneketzis, "Active diagnosis of discrete event systems", *IEEE Trans. Automatic Control* 43(7):908–929, 1998. Controller designed so that the closed loop is diagnosable | — | — | V0 SC |
| D03 | A. Paoli, S. Lafortune, "Safe diagnosability for fault-tolerant supervision of discrete-event systems", *Automatica*, 2005. Detection required before a forbidden (unsafe) string; necessary and sufficient conditions; **active safe diagnosis** by controller design | https://www.sciencedirect.com/science/article/abs/pii/S0005109805001111 | B77 | V0 SC |
| D04 | L. K. Carvalho, J. C. Basilio, M. V. Moreira, robust diagnosis of DES against intermittent loss of observations (*Automatica* 48, 2012) and against permanent loss of observations (*Automatica*, 2012/2013) | S000510981200297X; S0005109812004803 | B103 | V0 SC |
| D05 | "Comparative analysis of related notions of robust diagnosability of discrete-event systems", *Annual Reviews in Control*, 2021. Robust diagnosability under permanent and intermittent sensor failures unified as generalized robust diagnosability. Also K-loss robust diagnosability (IFAC 2021) | S1367578821000158; S2405896321001361 | — | V0 SC |
| D06 | F. Cassez, S. Tripakis, "Fault diagnosis with static and dynamic observers", 2008. **Dynamic sensor activation policies** minimal for diagnosability; the most permissive observer. Also "Optimal sensor activation for diagnosing discrete event systems", *Automatica* 2010 | arXiv 1006.4681; S0005109810001615 | — | V0 SC |
| D07 | M. Krysander, E. Frisk, "Sensor placement for fault diagnosis", *IEEE Trans. Systems, Man and Cybernetics A*, 2008. Structural isolability: a fault is isolable from another if the latter is detectable in a sub-model excluding the first; sensor sets for required isolability | ieeexplore 4648949 | — | V0 SC |
| D08 | Frisk, Krysander et al., sensor placement for fault isolation in linear differential-algebraic systems, *Automatica* 2009. All sensor sets meeting a required isolability | S000510980800472X | — | V0 SS |
| D09 | D. Eriksson, E. Frisk, M. Krysander, "A method for quantitative fault diagnosability analysis of stochastic linear descriptor models", *Automatica* 49(6):1591–1600, 2013. A pairwise **distinguishability** measure between fault modes (Kullback–Leibler), bounding fault-to-noise ratios | S0005109813001349; diva2:610501 | — | V0 SC |
| D10 | "A method for quantitative fault diagnosability analysis of systems with probabilistic sensor faults", *Int. J. Control, Automation and Systems*, 2018 | doi 10.1007/s12555-018-0319-z | — | V0 SS |
| D11 | J. M. Kościelny and co-workers (author list unconfirmed), "Fault isolability with different forms of the faults–symptoms relation", *Int. J. Applied Mathematics and Computer Science* 26(4):815–826, 2016. **Conditional and unconditional isolability / unisolability** defined for multiple-valued symptom evaluation and symptom sequences. Also "Definitions and comprehensive assessment of fault isolability in expert-based diagnostic systems", *MSSP*, 2025 | doi 10.1515/amcs-2016-0058; S0888327025006806 | — | V0 SC |
| D12 | Fault Diagnosis Toolbox (Python), repository README: structural analysis, **fault isolability analysis, sensor placement analysis**, residual generation from the same model | https://raw.githubusercontent.com/faultdiagnosistoolbox/pyfaultdiagnosistoolbox/master/README.md | B134 | **V2** |
| D13 | "Sensor placement for online fault diagnosis", 2022. Joint sensor placement and (active) diagnosis via answer-set programming; about 500 components in minutes | arXiv 2211.11741 | — | V0 SS |
| D14 | Bayoudh, Travé-Massuyès (co-authors unconfirmed), "Active diagnosis of hybrid systems guided by diagnosability properties" and "Improving diagnosability of hybrid systems through active diagnosis" (IFAC). Diagnosers that decide whether a hybrid system is diagnosable passively or **actively**; controllable events executed or blocked to reach discriminating states | S1474667016357792; ResearchGate 269074838 | B119 (related) | V0 SC |
| D15 | E. Chanthery, L. Travé-Massuyès, Y. Pencolé, R. De Ferluc, B. Dellandrea, "Applying active diagnosis to space systems by on-board control procedures", *IEEE* 2019 | arXiv 1903.01710; ieeexplore 8737853 | — | V0 SC |
| D42 | Mode-dependent (hybrid-system) diagnosability. Fault detectability and isolability evaluated per operating mode; mode signatures (for example "Diagnosability analysis of hybrid systems cast in a discrete-event framework", *DEDS* 2012). Mode-sequence ARRs (audit B119) | doi 10.1007/s10626-012-0153-z | B119 | V0 SC |
| D43 | "Fault diagnosability evaluation of industrial cyber-physical systems with multiple time delays and communication constraints", *J. Franklin Institute*, 2025. Quantitative diagnosability under missing measurements | S001600322500701X | — | V0 SS |

## Active and safe active diagnosis

| id | reference | ids / URL | audit id | level |
|---|---|---|---|---|
| D16 | H. Niemann, "A setup for active fault diagnosis", *IEEE TAC* 51(9), 2006; R. Nikoukhah, S. L. Campbell, auxiliary signal design for active failure detection | — | B74, B75 | V0 SC |
| D17 | I. Punčochář, J. Široký, M. Šimandl, "Constrained active fault detection and control", *IEEE Trans. Automatic Control*, 2015; also approximate-dynamic-programming AFD (CDC 2015) | — | — | V0 SC |
| D18 | D. M. Raimondo, G. R. Marseglia, R. D. Braatz, J. K. Scott, "Closed-loop input design for guaranteed fault diagnosis using set-valued observers", *Automatica* 2016. Xu et al., "Sensor-fault tolerance using robust MPC with set-based state estimation and **active fault isolation**", *IJRNC* 2017: an active input designed to guarantee isolability **subject to input and state constraints** | Raimondo_Automatica_2016.pdf; doi 10.1002/rnc.3627 | B73 | V0 SC |
| D19 | "Input design for active fault diagnosis", *Annual Reviews in Control*, 2019 (survey) | S1367578819300070 | — | V0 SS |
| D20 | J. Ragan, B. Riviere, F. Y. Hadaegh, S.-J. Chung, "Online tree-based planning for active spacecraft fault estimation and collision avoidance" (**s-FEAST**, safe fault estimation via active sensing tree search), *Science Robotics*, 2024. Belief-space tree search choosing the most informative actions while enforcing probabilistic state constraints; discriminates simultaneous actuator and sensor faults; AIAA GNC 2023 best graduate student paper | doi 10.1126/scirobotics.adn4722; GitHub treyra/s-FEAST (README not reachable) | — | V0 SC |
| D21 | "Safe, real-time active model discrimination and fault diagnosis for nonlinear systems via differentiable reachability", 2026 | pith.science 2606.19590 | — | V0 SS |
| D22 | "Excitation operator based fault separation applied to a quadrotor UAV" (fault separation scheme with an excitation operator, a safety controller and control allocation, "guarantee[ing] under-actuated system safety when auxiliary input signals are injected") | arXiv 2308.10217 | — | V0 SC |
| D23 | "In-hover quadrotor rotor degradation monitoring using null-space excitation and lock-in detection", *Drones* 10(5):395, 2026 | https://www.mdpi.com/2504-446X/10/5/395 | B52 | V0 SC |
| D36 | "Active diagnosis for probabilistic systems", FoSSaCS 2014 (authors unconfirmed); "N-diagnosability for active on-line diagnosis in discrete event systems", *Automatica* 2017 | doi 10.1007/978-3-642-54830-7_2; S0005109817302856 | — | V0 SS |

## Evidence selection, test sequencing, hypothesis testing

| id | reference | ids / URL | audit id | level |
|---|---|---|---|---|
| D24 | M. Naghshvar, T. Javidi, "Active sequential hypothesis testing", *Annals of Statistics*, 2013 (after Chernoff, 1959). Also "Sequential hypothesis test with online usage-constrained sensor selection", *IEEE Trans. Information Theory*, 2019 | arXiv 1203.4626; doi 10.1109/TIT.2019.2910730 | — | V0 SC |
| D25 | J. de Kleer, B. C. Williams, "Diagnosing multiple faults" (GDE), 1987. Next measurement chosen by expected information | — | B29 | V0 SC |
| D26 | K. R. Pattipati, M. G. Alexandridis, test sequencing with AO* (1990). S. Deb et al., multi-signal flow graphs (testability, ambiguity groups). The optimal test tree is NP-complete; stopping when no test can split the ambiguity group | doi 10.1109/tsmcb.2004.825940 | B62 | V0 SC |

## Design-time testability tools reused at runtime (industry)

| id | reference | ids / URL | audit id | level |
|---|---|---|---|---|
| D27 | Qualtech Systems (QSI) **TEAMS-Designer**: testability analysis marks uncovered faults and **ambiguity groups** on the model. **TEAMS-RT**: a real-time diagnostic engine "on board a flight vehicle or embedded into a run-time architecture" using the same multi-signal model; failed tests implicate, passing tests exonerate | https://www.teamqsi.com/products/teams-designer/ | — | V0 SC (vendor) |
| D28 | PHM Technology **MADe**: model-based sensor-set design that "autonomously identifies failures that cannot be uniquely identified with a selected sensor set"; compares sensor sets by coverage, weight, reliability and cost; generates diagnostic rules | https://www.phmtechnology.com/made/made-phm/ | — | V0 SC (vendor) |
| D29 | DSI International eXpress, "Designing for IVHM or any on-board health management" | https://www.dsiintl.com/solutions/improve-diagnostic-capability-system-design/balance-diagnostic-design-optimize-sustainment-alternatives/designing-ivhm-board-health-management/ | — | V0 SS (vendor) |

## Action authority, contingency management, belief-space planning

| id | reference | ids / URL | audit id | level |
|---|---|---|---|---|
| D30 | NASA Intelligent Contingency Management (ICM) and "Dynamic vehicle assessment for intelligent contingency management of urban air mobility vehicles", AIAA SciTech 2021: real-time assessment of the vehicle's capability to fly and complete the mission after off-nominal events | NTRS 20205011183, 20205010508; doi 10.2514/6.2021-1001 | — | V0 SC |
| D31 | Runtime assurance: Simplex (Sha, 2001); ASTM F3269 | — | B79, B81 | V0 SC |
| D32 | "Safety-critical control under partial observability: reach-avoid POMDP meets belief space control", 2026 | arXiv 2603.10572 | — | V0 SS |
| D38 | Supervisory switching among pre-computed candidate controllers when the fault is not yet isolated, *Automatica* 2009 | S0005109809003008 | — | V0 SS |
| D44 | US 9,725,187 (Boeing): health score from risk, confidence and benefit gating reconfiguration | — | P24 | V0 SS |

## Embedded computation

| id | reference | ids / URL | audit id | level |
|---|---|---|---|---|
| D33 | A. Barrett (JPL), "Model compilation for embedded real-time planning and diagnosis" (2004) and distributed real-time model-based diagnosis (2003). Onboard diagnosis by knowledge compilation. P. Torasso, G. Torta, OBDD-based diagnosis complexity (2006): all diagnoses and minimum-cardinality diagnoses polynomial in the OBDD size | https://ai.jpl.nasa.gov/public/documents/papers/barrett-iwpss2004-modelcomp.pdf | — | V0 SC |

## Need, regulation, patents, CSIA

| id | reference | ids / URL | audit id | level |
|---|---|---|---|---|
| D34 | No Fault Found (NFF) literature: avionics NFF rates reported between 20% and 50% of removals; testability limits create ambiguity at line maintenance ("No Fault Found events in maintenance engineering", Part 1; "A framework to estimate the cost of No-Fault Found events", *Int. J. Production Economics* 2015) | ResearchGate 259518754; S0925527315005381 | — | V0 SC |
| D35 | US 12,151,689, "Methods and systems for determining diagnostic coverage of sensors to prevent goal violations of autonomous vehicles"; assignee Volkswagen Group of America Investments, LLC; filed 2021-10-11, granted 2024-11-26 (as shown). A diagnostic-coverage metric scaled by field-of-view modality overlap, compared with a threshold | USPTO 12151689 | — | V0 SS |
| D39 | CSIA's own code: `csia/v2/localization.py` `minimum_resolving_subsets` (§6 "minimum resolving evidence", exhaustive over measurable predicates: "RPM alone cannot localize the fault; RPM plus current can"); three-valued predicates (None = not measurable); `csia_assurance/witness.py` `SupportCertificate.competitors_without_witness`; `csia/v2/functions.py` per-function eligibility | repository | — | **V4** |
| D40 | FAA AC 25.1309-1B / CS-25.1309: latent failures, monitoring and annunciation of unsafe system operating conditions | https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_25.1309-1B.pdf | — | V0 SS |
