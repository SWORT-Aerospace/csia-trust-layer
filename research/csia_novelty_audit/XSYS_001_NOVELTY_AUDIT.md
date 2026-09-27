# XSYS-001: novelty of the experimental question (pre-result)

This file is part of the pre-result novelty audit (2026-09-27). Source ids are
listed in `research/csia_novelty_audit/BIBLIOGRAPHY.md`.

## Independence from the running campaign

The XSYS-001 confirmatory campaign was running while this audit was written.
This file draws only on:

- the frozen preregistration: `docs/research/XSYS_001_PREREGISTRATION.md`;
- the two amendments: `docs/research/XSYS_001_A1_NUISANCE_INDEPENDENCE.md` and
  `docs/research/XSYS_001_A2_C4_CORRECTION.md`;
- the public literature.

**No confirmatory log, stage output, completion record or result was opened,
and none is referred to.** Every judgement here would read the same whatever
the campaign's primary result turns out to be. The result may be integrated
only in a later, separately labelled update.

## 1. The question, as frozen

> Can temporally conditioned cross-domain evidence increase the ability to
> distinguish PHYSICAL ACTUATOR DEGRADATION from RPM/ESC TELEMETRY
> CORRUPTION when both cases produce matched local RPM symptoms?
> (`docs/research/XSYS_001_PREREGISTRATION.md` §1)

The ingredients, as frozen in the preregistration:

| ingredient | frozen form |
|---|---|
| case A | rotor effectiveness η < 1 on motor 0 in PX4 SIH; the controller compensates |
| case B | a nominal flight whose motor-0 RPM telemetry is scaled offline to **replay case A's observed ratio**, so the local symptom is identical by construction |
| W_DYN | mean body-rate deviation along the motor's thrust-loss axis in T1 = [0, 0.2) s |
| W_CTRL | allocator-command ratio of motor 0 against the other motors, T3 = [10, 15) s minus T0 |
| verdicts | CSIA v2 set elimination, unchanged; UNIQUE only for the last candidate standing and affirmatively confirmed; AMBIGUOUS is permitted |
| primary rule | the cluster-conservative one-sided 95 % lower bound on the pair resolution rate exceeds 0.5 **and** there is no WRONG attribution |
| protocol | frozen manifests, two-stage label-blinded scoring, nuisance condition as the independent unit |

## 2. The seven questions

| # | question | answer from the searched literature | closest prior art | status for this element |
|---|---|---|---|---|
| 1 | Has this **exact** matched-set problem been studied before? | No directly matching prior work was identified in the searched literature. No source constructs a multirotor RPM-telemetry corruption that replays the observed ratio of a physical rotor-effectiveness loss. The problem **class** is well studied: see question 2 | P03 (EPOS engine patent: actuator-sensor drift versus actuator hardware failure, separated by the engine's response); P01 (1987); B43, B44 | POSSIBLY_DISTINCT (as an instance) |
| 2 | Has discriminating an actuator fault from an actuator-**sensor** fault been studied? | **Yes, for decades.** A 1987 patent (P01) decides whether a fault is in the position sensors or the actuator by comparing against a model. IMM (B43, 1998) and MMAE (B44, 1999) separate sensor from actuator failures in flight control. NASA engine work (B46, B47) separates sensor faults from component and actuator faults. EPOS patents (P03–P05) separate actuator-sensor drift from actuator hardware faults. Isolability theory treats the pair explicitly (B23, B25) | P01, B43, B44, B46, P03 | KNOWN |
| 3 | Has the aircraft's rigid-body response been used to validate actuator telemetry? | **Yes in substance.** Multiple-model banks judge actuator hypotheses from the dynamics (B44). Control-invariant and physical-invariant monitors reject sensor data the dynamics do not follow (B92, B93). Multirotor practice combines a high command with insufficient attitude change, confirmed by ESC RPM (B51), and ranks faulty rotors by roll/pitch tracking error (B50). A study that uses body rates specifically to **validate ESC RPM telemetry** against a matched corruption was not found | B44, B92, B50, B51 | LIKELY_KNOWN |
| 4 | Has controller compensation been used explicitly as diagnostic evidence? | **Yes.** ArduPilot flags potential thrust loss when a motor saturates while the controller compensates (B55). Process-control FDD adds manipulated variables because feedback masks faults (B99, B100). SDG methods diagnose inside control loops (B17). Control allocation has been used to expose actuator faults (B21) | B55, B99, B17, B21 | KNOWN |
| 5 | Has the change in evidence utility from transient to post-compensation been formalized? | **Largely yes.** TRANSCEND (B37, 1999) formalizes transient fault signatures and a progression to steady-state analysis. Event-based diagnosis uses the order of deviations (B38). Timed signature matrices use occurrence times (B40). PX4 latches because recovery removes the evidence (B56). **Not found:** a formalization in which each evidence channel carries its own validity window and is inapplicable (neither true nor false) outside it, applied to the actuator-versus-telemetry pair | B37, B38, B40 | CLOSE_PRIOR_ART |
| 6 | Has structural candidate-set diagnosis been combined with such temporal evidence? | **Yes, in general.** TRANSCEND and QED refine candidate sets from time-indexed signatures (B37, B39). R2U2 combines temporal-logic observers with model-based / Bayesian diagnosis on UAS (B67, B68). HyDE and hybrid-systems diagnosis track modes over time (B41, B42). A 2026 preprint unifies runtime verification with model-based diagnosis (B69). **For this problem:** not found | B37, B39, B67, B69 | KNOWN (general); POSSIBLY_DISTINCT (instance) |
| 7 | Has it been evaluated under a preregistered zero-wrong-attribution criterion? | No directly matching prior work was identified in the searched literature. The conceptual antecedents of zero-WRONG exist: formal FDI **correctness** requirements (B71), guaranteed no-false-alarm set-based FDI (B72, B111), and false-isolation metrics in testability standards (B64). Benchmarking frameworks exist (B65). Preregistration and blinded scoring in FDI/UAV evaluation were **not seen** (queries Q63–Q65 and Q106 in `research/csia_novelty_audit/NOVELTY_SEARCH_LOG.md`) | B71, B72, B64, B65 | APPARENTLY_NOVEL (as evaluation practice; LOW confidence) |

The phrase "was not found" throughout means: not found by roughly 110
web-search queries whose results were read at summary level, with no full text
available. That is weak evidence. It licenses "no directly matching prior work
was identified in the searched literature" and nothing stronger.

## 3. What the XSYS-001 question is, and is not

**It is not:**

- a new diagnostic idea (questions 2–4 are KNOWN);
- a new temporal-diagnosis formalism (question 5 is CLOSE_PRIOR_ART; question 6
  is KNOWN in general);
- a new algorithm: the v2 engine is consistency-based diagnosis (B28), unchanged.

**It may be:**

1. **An experimental instance** that the searched literature does not contain.
   It pits the ESC-RPM channel against a physical loss **matched by
   construction**, on a closed-loop multirotor, and asks whether windowed
   dynamics and compensation evidence separate them **without ever naming a
   wrong cause**.
2. **A validation methodology** rarely or never used in FDI:
   - preregistration;
   - frozen manifests;
   - two-stage label-blinded scoring;
   - zero-WRONG in the primary decision;
   - the nuisance condition as the unit of the confidence bound;
   - an independence audit of the simulator's noise across conditions.

   The methodology is the part most likely to survive a professional search,
   and also the part least likely to be regarded as a scientific contribution
   on its own.

## 4. Threats to the distinct-instance status

| threat | effect if found | likelihood |
|---|---|---|
| a PHM or UAV paper injecting ESC/DShot telemetry faults alongside physical rotor degradation | question 1 → KNOWN | moderate. The ESC-telemetry fault literature was barely reachable through the search tool, whose results were dominated by GPS/IMU spoofing |
| the claims of P03–P05 covering "distinguishing an actuator position-sensor fault from an actuator fault using the plant's dynamic response" in general terms | question 1 → KNOWN for the idea; the multirotor instance would remain an application | moderate to high. The summaries already describe this |
| an engine-diagnostics benchmark (for example ProDiMES) with matched sensor-bias versus component-fault cases | question 1 and matrix C17 → CLOSE_PRIOR_ART | moderate; not searched |
| a robotics or PHM registered report | question 7 → KNOWN | low to moderate |

## 5. Limits the question carries regardless of novelty

These are restated from `docs/research/XSYS_001_PREREGISTRATION.md` §19
because they bound any novelty claim:

- **Simulation only.** PX4 SIH is a simplified multirotor. Nothing here
  speaks to a real ESC, rotor or sensor noise.
- **Case B is an offline multiplicative replay.** It is the strongest matched
  test of the local channel, but it models no specific telemetry failure mode.
- **One motor, one fault direction, one platform.**
- **The comparison is internal.** Variants V0–V4 are compared with one another.
  No external baseline (MMAE, IMM, DBN, set-valued observers) is run on the
  same matched set. The question of what CSIA does that an established method
  would not therefore stays open whatever the result.
