# Model-inadequacy search log

Searches run on 2026-09-28 for the adversarial prior-art attack on
"assurance under model incompleteness". Source ids `Mnn` are defined in
`research/csia_model_inadequacy/PRIOR_ART_ATTACK.md` §1.

**The tool.** A web-search tool that returns titles, URLs and a summary. No
full text was reachable (direct fetch attempts below).

**Scope.** The XSYS-001 record was not opened for this attack.

**Aim.** Every query targeted a field or failure mode named in the brief, and
the aim was to **kill** the candidate problem. Historical literature was
searched deliberately:

- 1970: the reject option;
- 1976: the GLR;
- 1980: model criticism;
- 1986–1990: belief functions;
- 1987–1991: consistency-based and abductive diagnosis;
- 1993: ambiguity and distance reject;
- 1996–1999: the UIO and MMAE.

Queries are recorded **verbatim**, inside code spans.

| # | exact query | kept | what it showed |
|---|---|---|---|
| MIQ1 | `Dubuisson Masson "statistical decision rule with incomplete knowledge about classes" ambiguity reject distance reject` | M02, M01 | ambiguity reject versus distance reject; incomplete knowledge of the classes (1993) |
| MIQ2 | `de Kleer Williams "diagnosis with behavioral modes" unknown mode Sherlock fault models unknown behavior consistency-based diagnosis` | M03 | behavioural modes; the unknown mode U(x) has no model; Sherlock (IJCAI-89) |
| MIQ3 | `ModelPlex runtime validation of verified cyber-physical system models Mitsch Platzer model compliance monitor fallback` | M27 | runtime model compliance monitors; the reality gap; model, controller and prediction monitors |
| MIQ4 | `transferable belief model open world assumption mass on empty set frame of discernment not exhaustive unknown hypothesis Smets` | M07 | open-world TBM; mass on ∅ as belief outside the frame; non-exhaustive frame |
| MIQ5 | `open-set fault diagnosis unknown fault classes rejection industrial rotating machinery process open set recognition fault diagnosis survey` | M15 | open-set FD moving from closed-world to open-world; rejection of unknown faults |
| MIQ6 | `fault isolation structured residuals signature not in fault signature matrix "unknown fault" unmatched signature Gertler isolation unanticipated faults` | M21 | FSM isolability; a signature matching no column is unanticipated |
| MIQ7 | `multiple model adaptive estimation unanticipated failure none of the models matches residual monitoring detection of unmodeled failures aircraft Maybeck` | M24 | MMAE on the VISTA F-16 with residual monitoring; filter spawning |
| MIQ8 | `model invalidation fault detection switched affine systems Harirchi Ozay all models invalidated unknown fault set-membership` | M26 | sound and complete fault detection by model invalidation (MILP); T-detectability, I-isolability |
| MIQ9 | `subjective logic vacuity dissonance uncertainty evidential deep learning Sensoy Josang lack of evidence versus conflicting evidence` | M09 | vacuity (lack of evidence) versus dissonance (conflict); evidential DL |
| MIQ10 | `normalized innovation squared consistency test Kalman filter model mismatch detection chi-square Bar-Shalom filter consistency unmodeled dynamics` | M25 | NIS consistency tests online; model-mismatch detection |
| MIQ11 | `Kennedy O'Hagan model discrepancy Bayesian calibration model inadequacy posterior predictive check Box 1980 model criticism` | M20 | the Kennedy–O'Hagan discrepancy function for model inadequacy; nothing on Box 1980 in this result |
| MIQ12 | `NASA Inductive Monitoring System unknown faults "unknown unknowns" ISHM model-based diagnosis combined with data-driven anomaly detection unmodeled failures` | M32 | IMS data-driven anomaly detection integrated with model-based ISHM |
| MIQ13 | `Qantas Flight 72 ADIRU data spikes flight control primary computer algorithm vulnerability ATSB report failure mode not anticipated` | M50 | the FCPC algorithm could not manage AOA spikes 1.2 s apart; "not anticipated" |
| MIQ14 | `Ariane 501 inquiry board report inertial reference system operand error design assumed random hardware failure shut down both SRI common mode software` | M51 | SRI software design faults; processor shutdown on malfunction; both SRIs failed |
| MIQ15 | `XL Airways Germany 888T Perpignan angle of attack sensors blocked frozen together voting accepted consistent wrong values BEA report common mode sensor failure` | M52 | AOA 1 and 2 blocked by frozen water; the summaries lacked the voting details (see MIQ23) |
| MIQ16 | `diagnostic system misdiagnosis unknown fault forced into known fault class closed-world assumption overconfident wrong isolation model mismatch caused wrong fault isolation case study` | M37, M38 | closed-world MBD misreads a structural fault as multiple component faults |
| MIQ17 | `conformal prediction empty prediction set indicates none of the classes plausible out-of-distribution singleton ambiguous set size` | M11 | empty set = "nothing is plausible enough"; large set = ambiguous; conformal and OOD |
| MIQ18 | `Hofbaur Williams hybrid estimation unknown mode "unknown mode" probabilistic hybrid automata Livingstone unmodeled failure` | M29, M30 | PHA hybrid estimation; continuing estimation under unknown behavioural modes |
| MIQ19 | `Struss Dressler "physical negation" integrating fault models into general diagnostic engine GDE+ no consistent diagnosis unknown fault` | M04 | GDE+ uses fault models to check that faults explain the observations; rules out implausible hypotheses |
| MIQ20 | `RAIM fault detection and exclusion exclusion not possible no consistent subset ARAIM threat model unmonitored faults integrity risk` | M35 | ARAIM FDE; exclusion trades continuity for integrity; unmonitored fault modes |
| MIQ21 | `Hüllermeier Waegeman aleatoric and epistemic uncertainty in machine learning introduction to concepts and methods reject option` | M10 | aleatoric versus epistemic uncertainty (Machine Learning 110(3), 2021) |
| MIQ22 | `SOTIF ISO 21448 known unsafe unknown unsafe scenarios areas classification triggering conditions` | M36 | SOTIF areas known/unknown × safe/unsafe |
| MIQ23 | `BEA final report XL Airways D-AXLA angle of attack 3 rejected by voting because AoA 1 and 2 blocked consistent values monitoring` | M52 | the voting trusted ADR 1 and 2 (incorrect) and rejected ADR 3 (normal) |
| MIQ24 | `Lufthansa 1829 Bilbao 2014 two angle of attack sensors frozen alpha protection nose down BFU report` | M53 | two AOA sensors blocked, probably by ice; alpha protection nose-down; BFU report not reached |
| MIQ25 | `Schiaparelli lander inquiry IMU saturation flag longer than expected negative altitude estimate parachute released early ESA report` | M54 | IMU saturation about 1 s, longer than expected; negative altitude; premature release at about 3.7 km |
| MIQ26 | `Console Torasso "spectrum of logical definitions of model-based diagnosis" abductive diagnosis no explanation exists incomplete fault models` | M06 | the spectrum from consistency to abduction; Cordier 1998 on failing to explain too-precise observations |
| MIQ27 | `Bendale Boult "towards open world recognition" open set recognition Scheirer "toward open set recognition" open space risk` | M14 | open set recognition (TPAMI 2013); open world recognition (CVPR 2015); OpenMax |
| MIQ28 | `patent "runtime model validation" partially observable hybrid systems model compliance monitor ModelPlex US patent` | M27 | US 11,204,838 and US 10,872,187; arXiv 1811.06502 |
| MIQ29 | `Bernardo Smith M-closed M-complete M-open model perspectives true model not in the set of candidate models Bayesian model selection` | M19 | M-closed / M-complete / M-open; model averaging outside M-closed |
| MIQ30 | `Willsky Jones 1976 generalized likelihood ratio approach detection estimation jumps linear systems failure detection GLR unknown failure signature` | M22 | the GLR for jumps of unknown magnitude and time (IEEE TAC 1976) |
| MIQ31 | `Gelman Meng Stern 1996 posterior predictive assessment of model fitness discrepancies Box 1980 sampling and Bayes inference model criticism` | M18 | posterior predictive assessment via realized discrepancies (1996); Box 1980 cited |
| MIQ32 | `Narasimhan Biswas HyDE hybrid diagnosis engine NASA unknown fault "no candidate" all candidates eliminated hybrid model-based diagnosis` | M31 | HyDE for stochastic hybrid systems; "no candidate" handling not in the summaries (UNCLEAR) |
| MIQ33 | `runtime assumption monitoring autonomous systems environment assumptions violated at runtime assume-guarantee contracts monitor safety case assumptions` | M28 | runtime checking of assume-guarantee assumptions; RTA as contract checkers |
| MIQ34 | `failure detection unify misclassification detection and out-of-distribution detection Jaeger "a call to reflect on evaluation practices for failure detection"` | M17 | failure detection: misclassification detection, OoD detection, selective classification and uncertainty as separated fields |
| MIQ35 | `vehicle level reasoner IVHM cross-subsystem fault propagation conflicting subsystem diagnoses aircraft area manager integrated reasoning Honeywell Boeing` | M34 | VLRS fuses heterogeneous subsystem diagnoses; joint-inconsistency reporting UNCLEAR |
| MIQ36 | `spacecraft FDIR unforeseen faults unknown anomalies model-based on-board diagnosis "unexpected" failures not in FMEA autonomy` | M46 | hybrid ML+MBR to detect and diagnose anomalies never before encountered; MSR model-based FDIR |
| MIQ37 | `digital twin discrepancy detection model mismatch versus fault physical asset digital twin residual unknown degradation aerospace` | M39 | digital-twin quality assurance kept separate from fault detection; spacecraft twin discrepancy |
| MIQ38 | `unknown input observer robust fault detection modelling errors unstructured uncertainty Chen Patton robust model-based fault diagnosis false alarm modelling error` | M23 | UIO and robust fault-detection filters; an accurate model is never available |
| MIQ39 | `selective classification Geifman El-Yaniv risk coverage abstain "selective prediction" reject option guaranteed risk` | M16 | risk–coverage selective classification; SelectiveNet |
| MIQ40 | `El Al 1862 Bijlmer structural damage flight control simulation reconstruction unmodeled failure fault tolerant flight control benchmark GARTEUR` | M47 | El Al 1862 reconstructed as the GARTEUR AG16 / RECOVER benchmark; structural damage of unknown extent |
| MIQ41 | `Dempster-Shafer conflict mass high conflict indicates incomplete frame of discernment or unreliable sources Zadeh paradox Smets interpretation of conflict` | M08 | Zadeh's example; high conflict suggests an incomplete frame or unreliable sources; Smets' open-world remedy |
| MIQ42 | `multiple fault diagnosis incomplete fault models observations not explained by any combination of known fault modes "unknown fault" hybrid bond graph novel fault detection Biswas` | M48 | HBG / TCG and GARRs across domains; multiple-fault bond graphs; unknown-fault handling not in the summaries |
| MIQ43 | `Bayesian surprise runtime monitoring autonomous robot "surprise" model mismatch detection innovation-based self-assessment competence awareness` | M42 | Bayesian runtime verification of robots; Bayesian surprise for guided vehicles |
| MIQ44 | `DXC diagnostic competition ADAPT electrical power system unknown fault injected not in model diagnoser output evaluation metrics` | M45 | the ADAPT testbed; DXC'10 with single-fault scenarios; unknown-fault handling not in the summaries |
| MIQ45 | `falsification of causal models from observational data testing causal graph implied conditional independences runtime causal model invalid fault diagnosis` | M41 | falsifying causal graphs by implied conditional-independence tests |
| MIQ46 | `invariant mining cyber-physical systems specification mining runtime violation detection unknown attacks faults physical invariants drones` | M40 | mined invariants for CPS (ARTINALI, CoMID); violation as a deviation |
| MIQ47 | `Williams Nayak 1996 Livingstone "unknown" failure mode each component model-based reactive self-configuring systems Deep Space 1 Remote Agent mode identification` | M30 | Livingstone (AAAI-96) flown on DS1 in 1999; an "unknown" mode not confirmed (UNCLEAR) |
| MIQ48 | `D-matrix diagnostic reasoner test results conflict "no fault" explains inconsistent test outcomes TEAMS-RT unexplained failed tests "unknown" diagnosis output` | M33 | D-matrix: tests pass, fail or are unknown; ambiguity groups; states good, bad, suspected, unknown |
| MIQ49 | `fault masking by feedback control closed-loop fault detection faults hidden by controller compensation detectability closed loop Niemann Stoustrup` | M43 | closed-loop fault masking; controller modification for active detection |
| MIQ50 | `conformal prediction runtime monitoring cyber-physical systems signal temporal logic Lindemann conformal anomaly detection time series guarantees closed loop` | M13 | conformal STL runtime verification (ICCPS 2023); conformal predictive monitoring |
| MIQ51 | `angle of attack common mode failure detection analytical redundancy flight dynamics virtual sensor detect two frozen vanes consistent wrong values monitoring` | M44 | an AOA virtual sensor detecting common-mode failures; US 11,003,196; US 11,029,706 |
| MIQ52 | `conformal prediction fault diagnosis prediction sets unknown fault detection empty set ambiguous fault classes rotating machinery aircraft` | M12 | conformal fault detection with risk guarantees; a space-launcher electrical FDD with calibrated classifiers |

## Direct fetch attempts

| source | method | result |
|---|---|---|
| `dekleer.org` (M03 PDF), `lfcps.org` (M27 PDF), `ksi.cpsc.ucalgary.ca` | curl | 000: not reachable |
| `reports-archive.adm.cs.cmu.edu` (M27 tech report) | curl | 403 |
| arXiv 1811.06502 (abs page and export mirror), `symbolaris.com` (M27), MIT MERS (M29), ESA Schiaparelli inquiry (M54), BEA synopsis (M52), ATSB AO-2008-070 (M50), CVF open access (M14), NASA NTRS (M32) | curl | 000: not reachable |
| `sunnyday.mit.edu` Ariane 5 report (M51) | curl | 403 |
| arXiv 1811.06502; ATSB AO-2008-070 | web fetch tool | `EGRESS_BLOCKED` |
| PX4 `src/modules/ekf2/EKF2Selector.cpp` (`main`) | curl, raw GitHub | 200; sha256 `e6cff5d668c6fa1054678cae4f034e87823351919dd3acc66dda17abb6bc9b0c`; read at the lines cited (M60, **V4**) |
| ArduPilot `libraries/AP_NavEKF3/AP_NavEKF3.cpp` (`master`) | curl, raw GitHub | 200; sha256 `ec0cfed330da9c0754407bf493455a057693c06b913bac0a8fbaef4a6e7350a8`; read at the lines cited (M61, **V4**) |
| `IML-DKFZ/fd-shifts` README (`main`) | curl, raw GitHub | 200; sha256 `2dca7ac95fed1b1b52bc7b51dea865874923d2b5bfcf74742259aadb59d89312`; the authors' abstract read (M17, **V2**) |
| this repository at 503321f: `csia/v2/localization.py`, `csia/v2/attribution.py`, `csia_assurance/witness.py` | local read | read at the lines cited (M62, **V4**) |

## What was not searched well

- **Full text.** IEEE Xplore, AIAA ARC, SAE, publisher full text, patent
  claims and accident-report full text were all blocked. Every paper, patent
  and report is V0.
- **Vehicle-level failsafes.** PX4 commander estimator checks and the
  ArduPilot EKF failsafe were not fetched. The system-level behaviour of the
  fielded autopilots is UNCLEAR.
- **"Anomaly explanation" as its own field.** No query returned a source that
  explains **why** no known hypothesis fits (PRIOR_ART_ATTACK.md §2, row 32).
  It is recorded as UNCLEAR, not as absent.
- **Non-English literature.** Not searched.
