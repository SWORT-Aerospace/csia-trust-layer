# Full-text verification queue

Written on 2026-09-28. Source ids `Mnn` are defined in
`research/csia_model_inadequacy/PRIOR_ART_ATTACK.md` §1.

**Why this queue exists.** Every paper, patent and report used in this attack
is **V0**, a search summary only, and carries
**REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION**. This environment could reach
only `raw.githubusercontent.com` (SEARCH_LOG.md, direct fetch attempts). The
exceptions are:

- M17 (V2, the authors' README);
- M60, M61 and M62 (V4, source code).

**How to use it.**

- Each item names the exact question to answer from full text, and what
  follows for the decision if the answer differs from the V0 summary.
- "Decision-critical" means that one answer, taken alone, could change the
  decision. The decision (`PRIOR_ART_ATTACK.md` §10) rests on the
  convergence of more than eight independent traditions, so **no single item
  is decision-critical**.
- Items are ordered by how much each one supports the kill.

| # | source | question to answer from full text | if the answer differs | priority |
|---|---|---|---|---|
| Q1 | M02 Dubuisson & Masson 1993 | Are "ambiguity reject" and "distance reject" defined as two distinct outputs of one rule, with distance reject tied to classes "not the true one"? | MI-C1 still stands on M03, M07, M21, M24 and M26 | high |
| Q2 | M03 de Kleer & Williams 1989 | Is the unknown mode U(x) reported as a distinct outcome when no known-mode assignment is consistent? How are U-diagnoses ranked? | MI-C1 and MI-C6 still stand on M04, M07 and M26 | high |
| Q3 | M07 Smets 1990 / M08 | Is `m(∅)` interpreted as "outside the frame" under the open-world assumption, as distinct from `m(Ω)`? What does the Zadeh example show exactly? | MI-C3 and MI-C4 still stand on M09 and on consistency-based diagnosis (CBD) conflicts | high |
| Q4 | M04 Struss & Dressler 1989 | With complete fault models, can GDE+ return "no consistent diagnosis"? How is that reported? | MI-C6 still stands on M03 and M06 | medium |
| Q5 | M27 ModelPlex (FMSD 2016; arXiv 1811.06502; US 10,872,187; US 11,204,838) | Exact monitor semantics on non-compliance: the fail-safe action, and robustness to partial observability. The claims of US 11,204,838 | MI-C7 still stands on M24 and M01/M02 | medium |
| Q6 | M26 Harirchi & Ozay | Semantics when every fault model is invalidated; the definitions of T-detectability and I-isolability | MI-C1 still stands | medium |
| Q7 | M24 Maybeck 1999; Fisher (AFIT) | How residual monitoring flags unanticipated failures; when filters are spawned; the flight-test status on VISTA | the aerospace-deployment cell for S4 drops to UNCLEAR | medium |
| Q8 | M37 "No faults in structure? How to diagnose hidden interactions" | Authors and venue; does it show closed-world engines diagnosing a structural fault as several component faults? | MI-C6's "documented masking" note becomes unsupported. MI-C6 stays N0 on M03/M04 | medium |
| Q9 | M52 BEA final report, D-AXLA | Did ADR voting trust ADR 1 and 2 and reject ADR 3 because the two blocked sensors agreed? | the V-equivalent example weakens. Lufthansa 1829 (Q13) and the general identifiability argument remain | medium |
| Q10 | M50 ATSB AO-2008-070 | The exact design limitation, and whether the failure mode was considered in the safety assessment | the Qantas 72 row stays UNCLEAR | low |
| Q11 | M51 Ariane 501 Inquiry Board | What the report says about the fault model the SRI exception handling assumed (widely quoted as addressing only random hardware failures). **Not asserted here** until read | the Ariane row stays limited to what the summaries state | low |
| Q12 | M54 Schiaparelli inquiry | Did any plausibility or consistency check exist on the navigation altitude (for example against the radar altimeter)? Why did it not prevent the release? | the Schiaparelli row's "a compliance check would flag it" becomes conditional | low |
| Q13 | M53 BFU report, D-AIDP | Confirm two AOA sensors blocked; alpha protection; the recommendations | the example stays at V0 SS | low |
| Q14 | M12 arXiv 2508.01208; arXiv 2507.13022 | Do these conformal fault-detection methods report empty sets as "unknown" distinctly from multi-label ambiguity? | MI-C11 remains N1 on M11 and M13 | low |
| Q15 | M44 ASTESJ 6(1):76; US 11,003,196; US 11,029,706 | The claims on common-mode detection by estimated-versus-measured AOA | MI-C9 remains N0 on analytical redundancy in general (M48, M23) | low |
| Q16 | M34 vehicle-level reasoning framework (PHM Society) | Does it report jointly inconsistent subsystem conclusions as a distinct output? | nothing changes; that cell is UNCLEAR now | low |
| Q17 | M33 TEAMS-RT documentation | Are conflicting or unexplained failed tests reported distinctly from ambiguity groups? | nothing changes; that cell is UNCLEAR now | low |
| Q18 | M30 Livingstone / DS1 Remote Agent | Did Livingstone models include unknown failure modes? Were they flown? | the aerospace cell for S1 remains UNCLEAR | low |
| Q19 | M29 Hofbaur | The mechanism for "continu[ing] hybrid estimation in the presence of unknown behavioral modes" | row 23 of PRIOR_ART_ATTACK.md §2 rests on M26 alone | low |
| Q20 | M35 ARAIM FDE | How integrity is allocated to unmonitored faults; the runtime output when exclusion fails | S9 cells become UNCLEAR | low |
| Q21 | M09 evidential deep learning | Is vacuity used as the OOD signal, conflating inadequacy with lack of evidence? | the caveat in AMBIGUITY_VS_MODEL_INADEQUACY.md §5e rests on M11 and M10 | low |
| Q22 | M17 Jaeger et al. (paper full text) | The exact wording on OoD-detection task formulation versus failure detection | already V2 from the README abstract; the full text would reach V3 | low |

**Also not verified.**

- Vehicle-level failsafes in PX4 (for example commander estimator checks) and
  in ArduPilot (the EKF failsafe) that act on estimator health were not
  traced. The system-level cells for S14 and S15 in
  `research/csia_model_inadequacy/CLOSEST_SYSTEMS.md` stay **UNCLEAR** until
  they are read at V4.
