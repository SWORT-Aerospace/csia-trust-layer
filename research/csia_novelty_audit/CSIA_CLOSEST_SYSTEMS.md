# The closest prior systems to CSIA

This file is part of the pre-result novelty audit (2026-09-27). Its
companions are:

- `research/csia_novelty_audit/CSIA_NOVELTY_AUDIT.md`
- `research/csia_novelty_audit/BIBLIOGRAPHY.md`, which holds the source ids

**Ranking rule.** The systems are ordered by how closely their reasoning
structure matches CSIA's, not by shared vocabulary. Five questions set the
order:

1. Does the system reason across physical domains?
2. Does it condition evidence on time?
3. Does it keep a candidate set rather than a single answer?
4. Are its output semantics close to UNIQUE / AMBIGUOUS / UNSUPPORTED?
5. Does it bound what an action may do?

**Evidence limit.** Every description below comes from search summaries. No
full text could be read, so the reasons are in `research/csia_novelty_audit/BIBLIOGRAPHY.md`.
Where a summary does not show a property, the entry says **not shown**. It
never says "absent". Read a "difference" row as provisional, and probably too
generous to CSIA.

**What CSIA is, for comparison.** CSIA has four layers:

- **v1:** a Beta-recursion trust graph over sensors, feeding a gated
  naive-Bayes diagnosis.
- **v2** (frozen): domain plugins emit three-valued `EvidenceRecord`s.
  Localization then eliminates hypotheses using a cross-domain signature
  matrix. A cause is **SUPPORTED** (UNIQUE) only when it is the last candidate
  standing **and** affirmatively confirmed. Otherwise the verdict is
  AMBIGUOUS, UNSUPPORTED or NO_EVIDENCE. A function graph states which
  functions remain justified. The layer issues no command.
- **XSYS-001** adds two witnesses, each valid only in its own window: body
  rate in 0–0.2 s and allocator compensation in 10–15 s. They feed the
  unchanged v2 engine, evaluated at two checkpoints.

Sources: `docs/CSIA_MASTER_ARCHITECTURE.md`,
`docs/research/CROSS_SYSTEM_BASELINE_AUDIT.md`,
`docs/research/XSYS_001_PREREGISTRATION.md`.

---

## 1. R2U2 and on-board UAS sensor and software health management (B67, B68)

| aspect | description |
|---|---|
| purpose | real-time, on-board system health management for UAS, small satellites and similar systems |
| domain | UAS; later extended to security threats and to small satellites |
| inputs | sensor, software and hardware signals of the flight system |
| reasoning method | runtime observer pairs for real-time projections of LTL / MTL, feeding **model-based diagnosis and Bayesian-network** reasoning; implemented on an FPGA |
| temporal reasoning | **yes, formal**: temporal-logic observers are the front end |
| cross-system reasoning | **yes**: sensor, software and hardware are diagnosed together; the summaries say it differentiates failure types across these domains |
| ambiguity handling | probabilistic (Bayesian network); whether it refuses a unique answer without discriminating evidence is **not shown** |
| output semantics | property verdicts plus posterior diagnoses; exact output lattice **not shown** |
| action integration | used as the monitor for runtime-assurance switching in later work (search result "Toward runtime assurance of complex systems with AI components") |
| experimental validation | flight-relevant UAS demonstrations and hardware implementation; details **not shown** |
| similarity to CSIA | the closest overall architecture: on-board, UAS, temporal evidence feeding diagnosis across heterogeneous subsystems, separating sensor failure from real vehicle failure |
| difference from CSIA | R2U2 is probabilistic and formally temporal. CSIA is deterministic set elimination with three-valued, window-scoped evidence, and it forbids a posterior leader from being reported as a cause. Whether R2U2's Bayesian-network layer would name a cause under the XSYS-001 matched symptom is **not established** |

## 2. TRANSCEND and qualitative event-based diagnosis (QED) (B37, B38, B39)

| aspect | description |
|---|---|
| purpose | fault isolation for abrupt faults in continuous and hybrid dynamic systems |
| domain | process plants (a breeder-reactor cooling loop), spacecraft power (ADAPT) |
| inputs | measured variables and a topological (bond-graph / temporal causal graph) model |
| reasoning method | predicts **fault signatures**: the qualitative magnitude, slope and higher derivatives of each measurement's deviation. Refines the candidate set as measurements deviate. QED adds **relative measurement orderings**, and possible-conflict decomposition |
| temporal reasoning | **central**. Signatures describe the transient. Monitoring is progressive and gives way to steady-state analysis. The order in which measurements deviate is evidence |
| cross-system reasoning | yes, through the causal graph spanning components and energy domains |
| ambiguity handling | the candidate set is the output; a fault stays a candidate until its signature is refuted |
| output semantics | a set of consistent fault candidates, with later identification of the parameters |
| action integration | **not shown** |
| experimental validation | an applied case (reactor loop); the ADAPT electrical-power testbed through DXC |
| similarity to CSIA | the closest prior art for C5, C6 and C7. Evidence is read according to when it is informative: transient versus steady state. Candidates are eliminated as time-indexed evidence accumulates |
| difference from CSIA | TRANSCEND accumulates evidence continuously; CSIA's v2 is atemporal, and XSYS-001 uses two fixed checkpoints. CSIA adds an explicit NOT_APPLICABLE / None value outside a window, and a required affirmative confirmation for UNIQUE. Whether TRANSCEND's signature matching has an equivalent to "confirmed" beyond "not refuted" is **not shown** |

## 3. VIPR and vehicle-level reasoning systems (B59, B60)

VIPR is the Vehicle Integrated Prognostic Reasoner.

| aspect | description |
|---|---|
| purpose | detect, isolate and predict adverse events affecting flight safety, at aircraft level |
| domain | transport aircraft (Honeywell with NASA) |
| inputs | evidence from diagnostic and prognostic monitors supplied by subsystem vendors; heterogeneous, asynchronous data streams |
| reasoning method | hierarchical health managers reasoning over fault conditions and monitor evidence; generating and testing hypotheses about root cause; anomaly detection added |
| temporal reasoning | continuous and prognostic; formal temporal validity **not shown** |
| cross-system reasoning | **yes, the explicit purpose**: aircraft-level reasoning across subsystems |
| ambiguity handling | **ambiguity groups**, with the stated goal of minimizing the ambiguity group and **rank-ordering** it |
| output semantics | ranked fault hypotheses and ambiguity groups; exact semantics **not shown** |
| action integration | the stated purpose includes mitigating adverse events; the mechanism is **not shown** |
| experimental validation | NASA metric report; replay of historical safety incidents; details **not shown** |
| similarity to CSIA | the closest aerospace **cross-subsystem** reasoner, and ambiguity is an explicit output |
| difference from CSIA | VIPR ranks within ambiguity groups. CSIA's rule forbids promoting a ranked leader to a cause without a discriminating measurement. Whether VIPR has a "no unique answer" semantics is **not shown**; this is the most important unread comparison |

## 4. Consistency-based diagnosis engines: GDE, Livingstone, HyDE (B28, B29, B66, B42)

| aspect | description |
|---|---|
| purpose | GDE: diagnose multiple faults from first principles. Livingstone: identify and reconfigure the spacecraft mode. HyDE: stochastic and hybrid model-based diagnosis |
| domain | circuits (GDE); Deep Space 1 (Livingstone); NASA hybrid systems (HyDE) |
| inputs | a component model and observations |
| reasoning method | **conflicts → minimal candidates**, meaning set elimination by consistency. GDE adds best-measurement selection; Livingstone adds transition models and reconfiguration planning |
| temporal reasoning | Livingstone and HyDE track mode transitions over time; GDE is static |
| cross-system reasoning | yes, over whatever components the model spans |
| ambiguity handling | **all minimal diagnoses are returned**. Discrimination is by further measurement, not by choice |
| output semantics | the candidate set (GDE); the most likely mode trajectories (Livingstone); candidates with probabilities (HyDE) |
| action integration | **Livingstone reconfigures** the spacecraft from the diagnosed mode |
| experimental validation | Deep Space 1 flight experiment (Remote Agent); HyDE on NASA testbeds and DXC |
| similarity to CSIA | v2 localization **is** consistency-based diagnosis: three-valued predicates, conflict-driven elimination, candidate-set outputs. Reiter (B28) and Console & Torasso (B31) already cover combining elimination (consistency) with confirmation (abduction) |
| difference from CSIA | CSIA's hypotheses are cross-domain **cause classes** (for example ACTUATION versus SENSOR). Its evidence is pre-digested into three-valued witnesses by domain plugins, rather than being a component-level behavioural model. It reports UNSUPPORTED when evidence eliminates every hypothesis. These are modelling choices within the paradigm, not a new paradigm |

## 5. Multiple-model sensor-versus-actuator failure diagnosis: MMAE, IMM, DMAE (B12, B13, B43, B44, B45)

MMAE is multiple-model adaptive estimation, IMM is the interacting multiple
model estimator, and DMAE is double-model adaptive estimation.

| aspect | description |
|---|---|
| purpose | detect, isolate and accommodate sensor **and** actuator (control-surface) failures in flight control |
| domain | aircraft flight control, for example the VISTA F-16 (B44); real flight data (B45) |
| inputs | commands and sensor outputs; a dynamic model per failure hypothesis |
| reasoning method | a bank of Kalman filters, each matched to one hypothesis; residual-based hypothesis probabilities (MMAE, IMM with Markov switching) |
| temporal reasoning | recursive over time; hypothesis probabilities evolve |
| cross-system reasoning | yes: actuator and sensor hypotheses are separated through the vehicle's dynamics |
| ambiguity handling | probabilistic; a hypothesis probability near 1 is taken as isolation |
| output semantics | the most probable hypothesis and a state estimate |
| action integration | **yes**: B44 redistributes commands to non-failed surfaces |
| experimental validation | high-fidelity F-16 simulation; failures detected within 1 s (B44); real flight data (B45) |
| similarity to CSIA | the same **discrimination problem class** as XSYS-001 (sensor-type fault versus actuator-type fault), solved with vehicle dynamics |
| difference from CSIA | probabilistic isolation versus a deterministic refusal to name a cause without discriminating evidence. Whether an MMAE bank would return a confident wrong answer under a symptom matched by construction is exactly the baseline XSYS-001 does not run |

## 6. Engine on-board estimators: actuator sensor versus actuator hardware (P03–P05, B46, B47)

| aspect | description |
|---|---|
| purpose | detect and accommodate actuator-sensor faults (in-range LVDT drift), actuator hardware faults and engine sensor faults |
| domain | gas-turbine engine control |
| inputs | control demands, boundary conditions, engine-condition and effector sensing |
| reasoning method | an on-board engine model (EPOS) estimates the engine response and synthesizes sensor values. Kobayashi & Simon run m+1 Kalman filters: one for component and actuator faults, one per sensor |
| temporal reasoning | continuous estimation; windowing **not shown** |
| cross-system reasoning | **yes**: engine thermodynamic response is used to judge actuator and sensor channels |
| ambiguity handling | **not shown** |
| output semantics | a fault class and the resulting accommodation mode |
| action integration | **yes**: accommodation, such as deactivating a correcting mode |
| experimental validation | simulation (NASA); patents describe no evaluation, as expected |
| similarity to CSIA | the closest known instance of the XSYS-001 **idea**. The P03 summary states that an actuator-sensor fault and an actuator hardware fault both appear as a tracking failure, and that the engine response distinguishes them |
| difference from CSIA | a different plant (engine versus multirotor) and a different channel (LVDT position versus ESC RPM). There is no matched-by-construction evaluation, and no ambiguity-preserving verdict is **shown** |

## 7. RAIM, ARAIM and navigation integrity monitoring (B87, B88)

| aspect | description |
|---|---|
| purpose | guarantee that a position solution is safe to use for a given operation |
| domain | GNSS and GNSS/INS aviation navigation |
| inputs | redundant pseudoranges; integrity support messages; inertial data for coasting |
| reasoning method | consistency checks (residual-based or solution separation); fault detection and exclusion; protection levels computed against an allowed integrity risk |
| temporal reasoning | per epoch; integrity coasting over outages |
| cross-system reasoning | within navigation (satellites, constellations, INS) |
| ambiguity handling | if a fault cannot be excluded, integrity is **not available**; the solution is not certified |
| output semantics | a protection level against an alert limit. When the protection level exceeds the alert limit, **the operation is not authorized** |
| action integration | **yes**, formally: authorization of an operation or procedure |
| experimental validation | decades of certification practice and standards |
| similarity to CSIA | the closest precedent for CSIA's **assurance semantics**: separating detection from exclusion from sufficiency, and binding the strength of the evidence to what may be done (C9, C10) |
| difference from CSIA | a single domain (position) with a quantitative risk budget. CSIA's verdicts are categorical and cross-domain, and CSIA authorizes nothing |

## 8. Honeywell Boeing 777 on-board maintenance system, central maintenance function (B58, P12)

| aspect | description |
|---|---|
| purpose | isolate the LRU responsible for flight-deck effects, for maintenance turnaround |
| domain | transport aircraft avionics |
| inputs | fault reports from many LRUs |
| reasoning method | a consolidation module that **screens out cascaded faults**. For example, a 115 VAC bus failure makes many LRUs appear failed; the module isolates the bus |
| temporal reasoning | **not shown** |
| cross-system reasoning | **yes, the core function** |
| ambiguity handling | **not shown** |
| output semantics | an isolated fault message |
| action integration | maintenance, not flight action |
| experimental validation | in service on the 777 |
| similarity to CSIA | cross-system root-cause reasoning: symptoms reported in many domains are traced to a common cause (CSIA's "common-cause retention") |
| difference from CSIA | a maintenance context with no runtime assurance semantics shown |

## 9. Control-invariant and physical-invariant attack detection (B92, B93)

| aspect | description |
|---|---|
| purpose | detect physical and sensor attacks on robotic vehicles on the fly |
| domain | drones, rovers, cars |
| inputs | sensor readings, control commands, a vehicle dynamics or control-invariant model |
| reasoning method | residual between predicted (invariant) and observed behaviour; CUSUM in SAVIOR |
| temporal reasoning | windowed / CUSUM accumulation |
| cross-system reasoning | yes: control and dynamics are used to judge sensor data |
| ambiguity handling | detection-oriented; attribution to a particular cause **not shown** |
| output semantics | an attack alarm |
| action integration | recovery in later work (B115) |
| experimental validation | **real vehicles** (an Intel drone and a car in SAVIOR) |
| similarity to CSIA | physical consequence as the witness against falsified sensor data, the core intuition of C3 and of case B |
| difference from CSIA | detection rather than discrimination between two matched causes; no ambiguity verdict |

## 10. Timed fault-signature matrices with interval observers (B40, P14)

| aspect | description |
|---|---|
| purpose | integrate fault detection and isolation using when and in what order fault signals activate |
| domain | sewer networks and other water systems |
| inputs | interval-observer residuals |
| reasoning method | several fault signature matrices: Boolean, sensitivity, occurrence order, occurrence time |
| temporal reasoning | **explicit**: activation order and time are part of the signature |
| cross-system reasoning | across the network |
| ambiguity handling | candidate faults consistent with the observed pattern |
| output semantics | an isolated fault or a fault set |
| action integration | **not shown** |
| experimental validation | a real sewer-network application |
| similarity to CSIA | the v2 signature matrix plus temporal information is a timed FSM in this sense |
| difference from CSIA | residual timing is used **as** signature content. CSIA uses time to decide whether each piece of evidence is applicable at all |

## 11. Runtime assurance: Simplex, the AFRL framework, ASTM F3269 (B79, B80, B81, B82, P08)

| aspect | description |
|---|---|
| purpose | bound the behaviour of an unverified complex function using a monitor and a verified recovery function |
| domain | flight control, autopilots, eVTOL, robotics |
| inputs | vehicle state, envelope limits |
| reasoning method | a switching or filtering condition over the state |
| temporal reasoning | reachability / recoverability margins |
| cross-system reasoning | **not** a diagnostic function |
| ambiguity handling | not applicable. The earlier repository record S004 notes that Simplex "does not address sensors" |
| output semantics | which controller has authority |
| action integration | **the whole purpose** |
| experimental validation | flight test and simulation; an FAA study (B82) |
| similarity to CSIA | the "bounded downstream adaptation" part of CSIA's stated direction |
| difference from CSIA | runtime assurance acts but does not diagnose. CSIA diagnoses and does not act. The link between them (verdict-typed authorization) exists in neither |

## 12. Digital-twin health monitoring and reconfiguration (B76)

| aspect | description |
|---|---|
| purpose | end-to-end resilience: diagnosis, prognostics and reconfiguration |
| domain | cyber-physical systems |
| inputs | sensor data and a physics-based digital twin |
| reasoning method | model-based diagnosis with interventions **to disambiguate uncertain diagnoses**; surrogate models for real-time speed |
| temporal reasoning | through the dynamic twin |
| cross-system reasoning | yes |
| ambiguity handling | **explicit**: ambiguity is resolved by active intervention |
| output semantics | diagnoses; reconfiguration actions |
| action integration | **yes** |
| experimental validation | case studies (details not shown) |
| similarity to CSIA | ambiguity-aware diagnosis tied to action; the architecture a "PART G" extension would need to reduce against (earlier repository record) |
| difference from CSIA | a twin plus active intervention, where CSIA uses passive, read-only witnesses. CSIA reports non-identifiability; it does not resolve it |

## 13. Runtime verification unified with model-based diagnosis in LOLA (B69)

| aspect | description |
|---|---|
| purpose | a single stream-runtime framework that does both property monitoring and model-based diagnosis |
| domain | general cyber-physical systems (2026 preprint) |
| inputs | streams |
| reasoning method | the LOLA stream language, with MBD integrated |
| temporal reasoning | yes: stream-based temporal specification |
| cross-system reasoning | not shown |
| ambiguity handling | MBD candidate sets (inferred from "model-based diagnosis"; details not shown) |
| output semantics | not shown |
| action integration | not shown |
| experimental validation | not shown |
| similarity to CSIA | the most recent evidence that "temporal runtime monitoring + candidate-set diagnosis" is being unified in the formal-methods community |
| difference from CSIA | unknown until read; **high-priority reading** |

## 14. Fielded autopilot detectors: ArduPilot thrust loss, PX4 motor failure (B55, B56)

| aspect | description |
|---|---|
| purpose | detect propulsion failure in flight |
| domain | open-source multirotor autopilots |
| inputs | motor outputs from the mixer (ArduPilot); ESC current against motor command (PX4) |
| reasoning method | thresholds with persistence; motor-output saturation (ArduPilot) |
| temporal reasoning | persistence timers; PX4 **latches**, because recovery would make the failed motor look healthy |
| cross-system reasoning | ArduPilot: **controller compensation** judged against the propulsion state. PX4: local ESC telemetry |
| ambiguity handling | none: a warning or failsafe |
| output semantics | a warning or failure flag |
| action integration | PX4 motor-failure recovery; ArduPilot thrust boost |
| experimental validation | field use |
| similarity to CSIA | compensation as evidence (C4). PX4's latch is a fielded recognition that an **action can remove its own evidence** (C15) |
| difference from CSIA | no discrimination between physical loss and telemetry corruption; no ambiguity verdict |

## 15. Formal design of FDI components (B71)

| aspect | description |
|---|---|
| purpose | specify, verify and synthesize FDI components that are correct by construction |
| domain | discrete-event models; an aerospace case study |
| inputs | the plant model and FDI requirements |
| reasoning method | a requirements language in temporal epistemic logic: correctness, completeness, maximality, trace-diagnosability; synthesis |
| temporal reasoning | yes: temporal epistemic logic, asynchronous setting |
| cross-system reasoning | over the model |
| ambiguity handling | diagnosability and maximality make "cannot know yet" an explicit, specified state |
| output semantics | alarms that must be **correct**: raised only if the fault indeed occurred |
| action integration | not shown |
| experimental validation | aerospace case study |
| similarity to CSIA | the closest formal precedent for XSYS-001's **zero-WRONG** requirement and for "no unique claim before the evidence can support it" |
| difference from CSIA | a formal synthesis target over discrete models, not an empirical evaluation criterion on a continuous closed-loop simulation |

---

## What the fifteen together cover

| CSIA ingredient | covered by |
|---|---|
| cross-domain physical witnesses | 5, 6, 8, 9, 14 |
| evidence usefulness changing through the transient | 2, 10, 14 (PX4 latch) |
| set elimination with candidate sets | 2, 4, 10 |
| ambiguity as an explicit output | 3, 4, 7, 15 |
| refusing a conclusion the evidence cannot support | 7 (integrity not available), 15 (correctness), 4 (all minimal diagnoses) |
| binding evidence strength to permitted action | 7, 11, 12, 4 (Livingstone) |
| temporal monitoring feeding diagnosis on a UAS | 1 |
| unifying runtime verification with diagnosis | 13 |

Every ingredient is covered by at least one system. The table says nothing
about whether any **one** system combines them the way CSIA does. That
question is C12 in `research/csia_novelty_audit/CSIA_PRIOR_ART_MATRIX.csv`
(POSSIBLY_DISTINCT, LOW confidence). It cannot be settled from summaries: the
decisive properties of systems 1, 3 and 13 were **not shown**.
