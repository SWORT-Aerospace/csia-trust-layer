# CSIA full-text verification queue (stage 2, pre-result)

This file is part of the second-stage novelty verification (2026-09-27/28).
Source ids are listed in `research/csia_novelty_audit/BIBLIOGRAPHY.md`.

**Why this queue exists.** From this environment, only open-source code on
`raw.githubusercontent.com` could be read. Every paper and every patent below
is at **V0**, and is marked REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION. The
remaining candidate contributions are:

- **MNC-1**: the windowed witness pairing;
- **MNC-2**: the matched validation design.

Both are at N2 with LOW confidence **because** these sources are unread
(`research/csia_novelty_audit/CSIA_MINIMUM_NOVEL_CORE.md`).

**Priority.**

- **P0**: reading the source can by itself change the novelty boundary, moving
  MNC-1 or MNC-2 to N1 (or the XSYS-001 formulation to CLOSE_PRIOR_ART or
  KNOWN).
- **P1**: the source can change the status of an element already at N0/N1,
  or the patent triage.
- **P2**: confirmatory.

**How to verify.** Record, for each source, the verification level reached
(V1–V4). For V4, record the exact section, page, equation or claim number.
Then update the claim chart cell, not only the prose.

## Ranked queue

| rank | source | identifier | level now | exact proposition to verify | why it could kill the candidate | section / claim to inspect | priority |
|---|---|---|---|---|---|---|---|
| 1 | Cascade electro-hydraulic steady-state fault propagation (B118) | doi 10.3390/machines12090600 (open access; host blocked here) | V0 | Does the isolation use (a) the controller output itself as a monitored variable, and (b) transient-phase evidence alongside steady state, to separate actuator faults from feedback-sensor faults? | (a) plus (b) is MNC-1's pairing on another plant. MNC-1 → N1 | the fault-influence distribution matrix section; the isolation procedure; any transient-response analysis; the list of monitored variables | **P0** |
| 2 | EPOS family: US 10,557,418; US 11,203,950; US 11,319,834; US 11,905,891 (P03–P05, P25) | USPTO full text and claims | V0 (search-rendered excerpt) | Does the description or an independent claim use time windows (transient against steady state), controller effort or loop compensation, or an ambiguity-preserving outcome, when separating actuator-sensor from actuator-hardware faults? Which member carries the quoted text? | if yes, MNC-1 → N1 and the XSYS-001 formulation → CLOSE_PRIOR_ART on another plant | the independent claims (numbers as shown in the full text); the description around "minor loop" and "engine response pressure differential"; the figures of the tracking-check logic | **P0** |
| 3 | Alavi, Izadi-Zamanabadi, Hayes (B117) | doi 10.1049/iet-cta:20070382 | V0 | Is the time over which the sensor fault is masked in closed loop made explicit, and are the controller-demanded residual and the output residual assigned to different time regimes? | explicit regime assignment of two residuals would be the MNC-1 structure (SISO). MNC-1 → N1 | the residual-design section; the discussion of closed-loop masking; the simulation section | **P0** |
| 4 | Hofbaur, Travé-Massuyès, Rienmüller, Bayoudh 2010 (B119) | PHM Society 2010 conference archive | V0 | Is ARR validity defined per mode only, or also per phase after a fault? Is using an ARR outside its mode shown to produce wrong isolation? | fault-phase validity plus a misuse demonstration would take the representation and the negative-control element. MNC-1 → N1, MNC-2 weakened | the definition of mode-sequence ARRs; the example | **P0** |
| 5 | TRANSCEND, Mosterman & Biswas 1999 (B37) | IEEE Trans. SMC-A 29(6):554–565 | V0 | Are transient-signature measurements explicitly marked **inapplicable** once feedback returns them to normal, rather than merely superseded by steady-state analysis? Is controller output a measurement? | explicit inapplicability after compensation, with controller output as evidence, would take MNC-1's temporal structure. MNC-1 → N1 | the progressive-monitoring section; the treatment of systems with feedback; the case study | **P0** |
| 6 | Qualitative event-based diagnosis (B38) and QED with possible conflicts (B39) | IEEE TCST 2009; SAFEPROCESS 2012 | V0 | Do the measurement-ordering signatures include a symbol for "deviation returns to normal because of compensation", and is a measurement discounted after that event? | same as rank 5, within an elimination framework | the signature definition; the event-ordering rules; the ADAPT case | **P0** |
| 7 | Quadrotor actuator and sensor FDD: IFAC 2018 (B123) and Waitman et al. 2021 (B124) | S2405896318324285; doi 10.1049/cth2.12180 | V0 | Is any sensor fault an **RPM / motor-speed** sensor fault, set against actuator loss of effectiveness? Are the fault cases matched in local symptom? | if yes, the XSYS-001 formulation → CLOSE_PRIOR_ART or KNOWN on a quadrotor | the fault model; the list of sensor faults; the flight-test fault cases | **P0** |
| 8 | INDI fault detection that splits actuator dynamics from actuator effectiveness using RPM feedback | **not attributed**. The search summary (S2Q23) described it without a source. Find it first, likely Delft INDI fault-tolerant control work | V0 (unattributed) | Does it treat an RPM-sensor fault as a hypothesis competing with effectiveness loss, using body-rate response? | if yes, the XSYS-001 formulation → KNOWN on multirotors | the fault-model and isolation sections | **P0** |
| 9 | R2U2 UAS sensor and software health management (B68) | PHM 2013; IJPHM 2015; NTRS 20160001256 | V0 (tool README V2) | Does the Swift UAS case pair time-bounded observers with a diagnosis layer that reports ambiguity for actuator-versus-sensor pairs, and are observer verdicts scoped to fault phases? | would take the architectural combination and reduce MNC-1's window element | the SHM architecture; the Bayesian-network models; the Swift UAS case study | **P0** |
| 10 | VIPR final report (B59) and VLRS chapter (B60) | NASA/CR-2013-217972; DASHlink chapter | V0 | Are monitors assigned validity by flight phase or fault phase, and does the reasoner retain ambiguity groups for actuator-versus-sensor cases on real aircraft data? | the vehicle-level combination with windowed monitors would reduce MNC-1 to an instance of VIPR practice | the monitor model; the reasoner's evidence-latching and temporal filters; the metrics report | **P0** |
| 11 | US 12,134,484 (P07) | USPTO | V0 | Does "contextually-informed" mean context-scoped evidence validity? Do the claims cover temporal-structural elimination on aircraft? | affects the F09/F25 elements (already N1/N0) and the patent triage | the independent claims; the "context" definition | P1 |
| 12 | US 9,725,187 / US 2010/0017049 (P24) | USPTO | V0 | Do the claims map a diagnostic confidence to permitted reconfiguration? What is the priority date? | affects only the action-authority vision (UNSUPPORTED) | the independent claims; the priority chain | P1 |
| 13 | Integrated vehicle health and fault contingency management for UAVs (B126) | doi 10.1007/978-90-481-9707-1_46 | V0 | Does the chapter's reasoner use temporal latching and ambiguity groups with contingency actions on UAVs? | strengthens the IVHM challenge; does not touch MNC-1's instance | the reasoning and contingency sections | P1 |
| 14 | Nikiforov 1995 (B122); Lai 2000 (B121) | IEEE TIT 41(1):171–187; 46(2):595–608 | V0 | the exact definition of the probability-of-false-isolation constraint | confirms the zero-WRONG antecedent (already N0 as a concept) | the problem statement and optimality criteria | P1 |
| 15 | Bozzano, Cimatti, Gario, Tonetta (B71) | LMCS 11(4), 2015 | V0 | Is FDI "correctness" (no wrong diagnosis) specified together with delay and maximality, as a requirement pattern? | confirms the zero-WRONG antecedent in formal methods | the requirements-language section | P1 |
| 16 | Console & Torasso 1991 (B31) | Computational Intelligence 7(3) | V0 | Is the definition matching "last standing **and** confirmed" in the spectrum? | confirms that the verdict rule is N1 | the definitions section | P1 |
| 17 | US 11,061,390 (P06) | USPTO | V0 | Do the claims cover retaining and ranking ambiguity groups by supporting evidence? | patent triage for the ambiguity layer (already N0) | the independent claims | P1 |
| 18 | Fast fault detection on a quadrotor (B125) | arXiv 2102.06439 | V0 | Is a faulty RPM measurement considered, or is RPM assumed correct? | if considered, rank 7's effect | the fault model; the assumptions | P2 |
| 19 | Timed fault-signature matrices (B40) | CSIC repository PDF | V0 | Are occurrence-time windows used to discount a signature after a time? | minor; F09 is already N1 | the timed-FSM definition | P2 |
| 20 | Runtime verification unified with model-based diagnosis in LOLA (B69) | arXiv 2606.23720 | V0 | Are stream-verdict validity windows fed into consistency-based elimination with ambiguity output? | would add a 2026 instance of temporal-plus-structural integration with windows | the framework definition; the examples | P2 |

## What reading the P0 set would settle

If all ten P0 sources are read at V3 or better and **none** contains:

- the transient-plus-compensation pairing with window-scoped applicability; or
- a multirotor RPM-sensor-versus-effectiveness case;

then:

- MNC-1 may move to **N3** (apparently distinct in the searched literature);
- the XSYS-001 formulation may move to APPARENTLY_DISTINCT_PENDING_VERIFICATION.

If any one contains it, MNC-1 falls to **N1**.

N4 would additionally need an adversarial full-text review of the closest of
these sources. That is out of reach from this environment.
