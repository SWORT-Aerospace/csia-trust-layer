# Full-text verification queue

Gap analysis, 2026-09-28. Source ids `Rnnn` are defined in
`research/autonomous_assurance_gap_search/GAP_LANDSCAPE.md` §1.

**Why this queue exists.** Everything below is **V0** (a search summary). It
carries **REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION**, because this
environment reaches only `raw.githubusercontent.com`.

**Order.** Items are ordered by how directly the answer could **kill** a
surviving gap (G02, G08, G07) or revive a killed one. A "decision-critical"
item can, on its own, change the decision in `TOP_THREE_GAPS.md`.

| # | source | question to answer from full text | if the answer is yes / different | gap | priority |
|---|---|---|---|---|---|
| Q1 | R042, battery-aware predictive planning and control for multirotors (arXiv 2609.12188) | Does it produce a **conservative runtime margin** of authority/power against current and planned demand, composing battery power capability, propulsor degradation and wind, stated as a guarantee? Or does it only plan optimally under those constraints? | if it produces such a margin: G02 unsolvedness falls to ≤ 2, G02 is no longer high value, and the decision may drop to ONE (G08) | G02 | **decision-critical** |
| Q2 | R036, NASA ICM / dynamic vehicle assessment, and the 2023 UAM benchmark | Is a composed capability margin for electric rotorcraft computed at runtime, with conservatism? What does the benchmark say is open? | if solved: as Q1 | G02 | **decision-critical** |
| Q3 | R034 / R035, Ornik group | How is the degradation bound obtained? Is there an electric-rotorcraft example with battery and propulsor coupling? | if yes: G02 residual narrows to engineering | G02 | high |
| Q4 | R001, ASTM F3269-21 | Does the standard require the recovery control function's capability to be re-established at runtime after degradation? | if yes and solved: G07 is killed | G07 | high |
| Q5 | R004, the adaptive Simplex papers (STTT 2025; arXiv 2501.01831; arXiv 2606.25371) | Do they obtain the degradation bound from runtime evidence? | if yes: G07 is killed | G07 | high |
| Q6 | R003, Black-Box Simplex and Neural Simplex | Which paper states that "any model error invalidates the safety guarantee", and in what setting? | the attribution in G07's evidence is corrected | G07 | medium |
| Q7 | R070, *NAVIGATION* 69(2) review | Exact wording on algorithm integrity as a certification challenge; the state of protection-level methods for vision | if protection levels are shown to be mature: G08 unsolvedness falls | G08 | high |
| Q8 | R071, vision integrity monitoring papers; US 11,899,469 | Do any give protection levels validated at aviation integrity-risk levels across scene classes? | as Q7 | G08 | high |
| Q9 | R060, NASA/JPL Ingenuity flight 72 report | The exact root-cause statement; whether navigation-health monitoring existed and why it did not prevent the descent | G08 evidence is strengthened or weakened | G08 | medium |
| Q10 | R061, ispace Mission 1 and Mission 2 reports | The exact software logic that rejected the rangefinder; the Mission 2 cause | as Q9 | G08 | medium |
| Q11 | R062, NTSB docket for the Amazon MK30 crashes | Confirm the rain-lidar mechanism and the software-update cause (currently news-reported via Bloomberg) | as Q9 | G08 | medium |
| Q12 | R065, Intuitive Machines IM-1 / IM-2 reviews | Exact findings | as Q9 | G08 | low |
| Q13 | R053, EASA SC-VTOL-01 and MOC | Exact text on performance after failure combinations for continued safe flight and landing | G02 importance / aerospace evidence | G02 | medium |
| Q14 | R043, R044, eVTOL battery power capability; *Joule* | Whether the power-capability assessment is intended for runtime use onboard | G02 residual narrows | G02 | medium |
| Q15 | R045, US 11,623,741 | Claims scope; whether it extends to electric propulsion | G02 residual narrows | G02 | medium |
| Q16 | R066, ATSB AO-2015-033; USHST bulletin | Exact wording on combined factors | G02 evidence | G02 | low |
| Q17 | R039, Belcastro LOC analyses | Share of multi-factor accidents; definitions | G02 evidence | G02 | low |
| Q18 | R020, CoCo; R019; R022 | Confirm that the assumption monitors cover latent capability quantities only through supplied bounds | if they estimate latent capability directly: G01 residual (and G02/G07) narrows | G01, G02, G07 | medium |
| Q19 | R010–R016, dynamic assurance-case literature | Confirm the runtime-update semantics | G04 kill confirmed | G04 | low |
| Q20 | R064, NTSB ASR-19-01 | The exact recommendations about assumptions | G12 evidence | G12 | low |
| Q21 | R031, FAA AI roadmap | Exact scoping of learned versus learning AI | G15 kill confirmed | G15 | low |

**Also not verified.**

- **PX4.** Paths other than R080–R083 and R086 were not traced. Examples: the
  failsafe framework's action mapping, and any motor-failure detector.
- **ArduPilot.** Paths other than R084 were not traced. Example: the battery
  failsafe.
- **Consequence.** The "fielded per-factor, post-saturation" characterization
  holds for the files read. It is **UNCLEAR** for the full code bases.
