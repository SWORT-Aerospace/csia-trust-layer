# CSIA-DX usefulness scorecard

Part of the CSIA-DX review (2026-09-28). Source ids are listed in
`research/csia_dx/BIBLIOGRAPHY.md`.

**The scores are qualitative, and every one rests on V0 evidence** (search
summaries). No customer was interviewed. No market or procurement data was
reachable. The "evidence of need" column names what was actually found; a
blank in it means nothing was found, not that there is no need.

Scale:

- **NEED**: evidence that the problem matters. STRONG / MODERATE / WEAK /
  NONE_FOUND.
- **COVERAGE**: how much existing approaches already solve it. HIGH /
  PARTIAL / LOW.
- **DX GAP**: what CSIA-DX could add beyond the existing coverage. LARGE /
  SMALL / NONE.

## 1. The ten aerospace problems

| # | problem | evidence of need | existing approaches | NEED | COVERAGE | DX GAP | remaining gap, stated plainly |
|---|---|---|---|---|---|---|---|
| 1 | Sensor loss reduces fault-isolation capability | robust diagnosability exists as a research field (D04, D05); certification requires annunciating unsafe conditions and handling latent failures (D40) | robust diagnosability verification (D04, D05); runtime reasoners that treat unavailable tests as unknown (D27) | MODERATE | HIGH (offline) / PARTIAL (runtime statement) | SMALL | an explicit runtime statement of *which pairs* are no longer separable, before evidence arrives, is rarely surfaced as an output; the computation is trivial |
| 2 | A degraded aircraft operates with incomplete health information | NASA ICM / Dynamic Vehicle Assessment program (D30) | capability assessment, envelope estimation (D30) | MODERATE | PARTIAL | SMALL | ICM assesses what the vehicle *can do*; it is less explicit about what the vehicle *can know* |
| 3 | An autonomous aircraft decides whether a fault can be safely isolated | s-FEAST was built for exactly this, on a spacecraft (D20); active safe diagnosis in DES (D03) | constrained and safe active diagnosis (D17, D18, D20, D21) | MODERATE | HIGH (methods) / LOW (fielded UAV autopilots) | SMALL | methods exist; fielded multirotor autopilots do not use them (the ArduPilot and PX4 code read at V4 in the novelty audit does no active isolation) |
| 4 | Avoiding unnecessary component shutdown caused by an ambiguous diagnosis | NFF: 20–50% of avionics removals; ambiguity from testability limits (D34) | testability design (D26–D28); isolating to the replaceable unit | **STRONG** (maintenance) / WEAK (in flight) | HIGH (maintenance tools) | SMALL | in-flight: the rule "do not shut down a component unless every candidate justifies it" is cheap and well defined, but the need was not evidenced by an incident source here |
| 5 | Deciding whether a mission can continue under diagnostic uncertainty | ICM (D30); runtime assurance (D31); health-score gating (D44) | capability- and confidence-gated contingency management | MODERATE | PARTIAL | SMALL | an ambiguity-set intersection rule (DX-C8) is explicit and auditable; belief-space methods subsume it |
| 6 | Deciding which extra sensor would actually improve isolation | NFF (D34); sensor placement research (D07, D08) | MADe (D28), TEAMS (D27), eXpress (D29), structural sensor placement (D07, D08, D12) | STRONG | **HIGH** | NONE | solved commercially and academically |
| 7 | Reducing unnecessary redundancy | the same design-time tools compare sensor sets by coverage and cost (D28) | MADe, TEAMS, structural analysis | MODERATE | HIGH | NONE | solved at design time |
| 8 | Designing cheaper diagnostic sensor architectures | as for 6 and 7 | as for 6 and 7 | MODERATE | HIGH | NONE | solved at design time |
| 9 | Selecting safe diagnostic manoeuvres | multirotor excitation and null-space probing (D22, D23); spacecraft (D20) | constrained active diagnosis (D17, D18, D21) | MODERATE | PARTIAL (UAV) | SMALL | pre-verified, regime-indexed probe tables robust over the candidate set are cheap; belief-space methods cost more but are richer |
| 10 | Preventing autonomy from acting as though an ambiguous diagnosis were certain | ambiguity preservation is CSIA's existing discipline (novelty audit: N0/N1); RTA (D31) | candidate-set diagnosis, RTA, POMDP | MODERATE | HIGH | SMALL | coupling the preserved ambiguity to an authority rule is new *for CSIA*, not in the literature |

**Reading.**

- The needs with the strongest evidence (4, 6, 7, 8) are design-time and
  maintenance needs. There, existing tools already have high coverage.
- The runtime needs (1, 2, 3, 5, 9, 10) have moderate evidence and partial
  coverage. CSIA-DX's addition to each is small, and mostly representational.

## 2. Potential users

| user | plausible interest | evidence found |
|---|---|---|
| UAV manufacturers | runtime degraded-mode logic that does not over-react to ambiguous faults | none directly; field reports of telemetry-triggered false motor failures (novelty audit B140, B146) suggest the local-logic problem |
| autonomous aircraft / eVTOL developers | contingency management under uncertainty | NASA ICM for UAM (D30) |
| defense UAS programs | assurance of autonomous decisions | none found |
| space systems | on-board active diagnosis under safety constraints | D15 (on-board control procedures), D20 (s-FEAST) |
| industrial robotics, maritime | the same pattern | none found |

## 3. Product forms

| form | description | incumbents | verdict |
|---|---|---|---|
| A. design-time tool | diagnosability matrix, ambiguity pairs, missing witnesses, recommended sensors, redundancy value | **MADe (D28), TEAMS-Designer (D27), DSI eXpress (D29)**, Fault Diagnosis Toolbox (D12) | **KILL.** A crowded, mature market with the same outputs |
| B. runtime library | current candidate set, current diagnosability, missing evidence, safe probes | TEAMS-RT (D27) for the reasoning; research code for safe probing (D20) | **WEAK.** Only the thin combination is distinctive; embedded D-matrix reasoners exist |
| C. assurance API | what is known, what remains ambiguous, what actions are justified | none found as a product; RTA frameworks (D31) are closest | **the only form with an apparent gap.** Demand is unevidenced |
| D. certification / verification tooling | show that the system knows its diagnostic limits | none found | **speculative.** No certification basis asks for this explicitly (D40 asks for annunciation of unsafe conditions and handling of latent failures) |

## 4. Overall usefulness

| criterion | assessment |
|---|---|
| technically useful | **YES, modestly.** A cheap runtime statement of "what can be known now", tied to probe admissibility and action authority, is a sensible engineering capability |
| scientifically nontrivial | **NO**, as framed. Every atomic element is N0 or N1 (`research/csia_dx/CSIA_DX_CLAIMS.csv`) |
| meaningfully distinct from prior art | **ONLY AS A COMPOSITION** (N2, LOW confidence). The closest runtime loop (D20) is richer |
| compatible with CSIA | **YES.** The primitives already exist in CSIA (D39) |
| computationally plausible | **YES**, for single and bounded double faults (`research/csia_dx/CSIA_DX_TOY_EXAMPLE_AND_FEASIBILITY.md` §3) |
