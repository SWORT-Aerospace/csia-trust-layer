# Top three gaps

Gap analysis, 2026-09-28. Source ids `Rnnn` are defined in
`research/autonomous_assurance_gap_search/GAP_LANDSCAPE.md` §1. Scores and
evidence for every score ≥ 4 are in `CANDIDATE_GAPS.csv`. The attacks are in
`PRIOR_ART_KILL_MATRIX.csv`.

**Scope.** No design is proposed. Where a question is stated, it is a
question, not a method.

## Summary

- **Candidates.** 17 generated (G01–G17). 13 killed. 4 survived: G02, G07,
  G08 and G12.
- **Selection.** G02, G08 and G07, ranked by total score. G12 (28/50) survived
  but ranks fourth.

| rank | id | short name | score /50 | A | B | C | D | E | F | G | H | I | J | novelty |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | G02 | compound degradation → runtime capability margin (electric rotorcraft) | **35** | 4 | 3 | 4 | 5 | 4 | 3 | 3 | 3 | 2 | 4 | N2 (LOW) |
| 2 | G08 | navigation integrity without GNSS | **34** | 5 | 4 | 4 | 5 | 4 | 3 | 3 | 1 | 2 | 3 | N1 |
| 3 | G07 | validity of the runtime-assurance recovery assumption under degradation | **31** | 3 | 3 | 4 | 4 | 3 | 4 | 3 | 2 | 2 | 3 | N1 |

Score key:

| letter | meaning |
|---|---|
| A | importance |
| B | unsolvedness |
| C | scientific depth |
| D | aerospace relevance |
| E | commercial value |
| F | experimental testability |
| G | embedded feasibility |
| H | fit with SWORT/CSIA assets |
| I | defensibility against prior art |
| J | platform potential |

**No score was inflated to reach a threshold.**

- Defensibility is 2/5 for all three. Each field is crowded.
- G08 scores 1/5 on SWORT fit.

## G02: compound degradation → runtime capability margin (electric rotorcraft)

**Exact problem.** Take an electric rotorcraft: a multirotor UAS or an eVTOL.
Several degradations may each be individually acceptable:

- battery power capability, which depends on state of charge, temperature and
  ageing;
- propulsor or ESC derating or damage;
- wind and payload demand.

The vehicle cannot currently determine, **before** actuator or power
saturation, whether these together still leave enough control authority and
power for the current and planned flight states.

**Why current systems fail.**

- **Fielded open-source autopilots** (all V4):
  - they check wind against a fixed threshold (R080);
  - they compare a return-time estimate with battery time (R081, R082);
  - they recognize thrust loss only after 1 s of descent at ≥ 90 % throttle
    (R084).
- **Research methods** each cover one or two channels:
  - rotor authority: R033;
  - authority-degraded reachability given a bound: R034, R035;
  - battery power capability: R043;
  - battery-aware planning: R042;
  - thrust margin for turboshaft rotorcraft: R045.

**Closest prior art.**

- R042: battery-aware predictive planning and control for multirotors under
  disturbances, including motor saturation and actuator degradation. This is
  **the kill threat**.
- R034 / R035: guaranteed reachability and viability under degraded control
  authority.
- R036: NASA ICM dynamic vehicle assessment.
- R043: eVTOL battery power capability for landing.
- R045: rotorcraft thrust-margin monitoring.

**What is actually missing** (V0; no directly matching work was identified in
the searched sources). A runtime, conservative margin that has all of these:

- it composes electrical power capability, propulsor degradation and
  aerodynamic/wind demand;
- it is evaluated against the demand of the current and planned flight
  states;
- it is available before saturation;
- it can be stated as an assurance claim, not only used as an optimization
  constraint.

**Who needs it.**

- eVTOL developers who must show continued safe flight and landing after
  "combination of failures", including remaining rate of climb (R053).
- Delivery-drone operators flying BVLOS with battery-limited contingency
  (R062, R067).
- Planetary rotorcraft.

**Why they would care.**

- It is a certification consideration (R053).
- Combined-margin loss is the classic rotorcraft accident pattern (R066).
- eVTOL batteries can fail to deliver power at low SOC under sustained load
  (R044).

**Why it is scientifically hard.**

- The degradations interact through coupled nonlinear physics (battery
  voltage sag feeds motor torque, which feeds rotor thrust, which feeds
  attitude and position demand).
- A conservative bound needs uncertainty propagation through that coupling.
- The theory for guaranteed reachability under diminished authority exists,
  but takes the degradation bound as given (R034, R035). Obtaining that bound
  from runtime evidence, without being uselessly conservative, is the
  unsolved part.

**Smallest falsifiable question.**

- *The question.* In a physics-based simulation with controlled,
  individually sub-threshold battery, propulsor-effectiveness and wind
  degradations, does a runtime-computable **conservative** margin exist that
  both (a) turns negative before every loss of altitude-hold or attitude
  authority, and (b) stays non-negative in a preregistered share of nominal
  flights?
- *The comparison.* Does it give lead time over the fielded per-factor checks
  (R080–R084)?
- *Falsified if* no such margin exists, or if it gives no lead time.

**Why SWORT has an advantage. Modest, and partly procedural.**

What SWORT has (R090):

- a PX4 SIH apparatus with a motor-effectiveness injection patch, used under
  preregistered and blinded evaluation in XSYS-001;
- a CSIA power domain that already models battery droop across an internal
  resistance;
- evidence and certificate plumbing across power, actuation and navigation
  domains.

What it lacks:

- battery, ESC and motor-current physics in SIH (R090 cites the CSIA-DX note);
- any hardware result;
- any reachability tooling;
- any eVTOL model.

The main advantage is falsification discipline, not method.

**What would kill the direction.**

1. Full text of R042, R036 or R034 shows the composed conservative runtime
   margin already exists (queue Q1–Q3).
2. Evidence that fielded eVTOL or delivery-drone flight control already does
   it (not observable from here: UNCLEAR).
3. Simulation shows per-factor checks with ordinary margins already catch
   every unsafe composition.
4. The conservative bound is too loose to be usable.

**Usefulness and feasibility.**

| aspect | rating | basis |
|---|---|---|
| commercial usefulness | HIGH | R053, R045, R043 |
| research usefulness | MEDIUM | composition under coupled uncertainty; pieces exist |
| experimental feasibility | MODERATE | requires adding battery/ESC physics to the SITL apparatus before any trial |

## G08: navigation integrity without GNSS

**Exact problem.** Autonomous aircraft and landers that rely on vision, lidar
or terrain-relative navigation cannot bound their navigation error with
integrity, meaning protection levels at a stated integrity risk. When
terrain, lighting or weather departs from the design case, the
estimator-quality assumption fails silently.

**Why current systems fail.**

- R070: "algorithm integrity is one of the main challenges of certifying
  visual navigation systems".
- Fault frequency and magnitude are scene-dependent.
- Existing approaches focus on accuracy, not integrity.
- Recent remedies add sensors rather than integrity bounds (R065).

**Closest prior art.**

- R071: VIO and vision integrity-monitoring research, GNSS/INS/vision
  integrity, a visual-odometry integrity patent, and UAM vertiport navigation
  requirements.
- R024: perception contracts.
- GNSS RAIM/ARAIM, as the template.

**What is actually missing.** Certifiable protection levels for vision, lidar
and terrain-relative navigation under scene-dependent faults. Examples of
such faults:

- texture loss (R060);
- terrain discontinuity misread as sensor fault (R061);
- weather-affected ranging (R062);
- low light (R065).

**Who needs it.**

- Planetary rotorcraft and lunar landers: R060, R061, R065.
- UAM vertiport operations: R071.
- Delivery drones: R062.

**Why they would care.** Five total or partial vehicle losses at four
organizations in 2023–2025: R060–R062, R065.

**Why it is scientifically hard.**

- Fault models for vision are scene-dependent and hard to bound
  probabilistically at aviation integrity risk levels (R070).
- The true error is latent.

**Smallest falsifiable question.**

- *The question.* For a given vision or terrain-relative navigation
  pipeline, can a runtime protection level be computed that bounds the true
  error at a stated integrity risk across preregistered scene classes, as
  checked against ground truth? Example scene classes: textured, bland,
  discontinuous terrain, low light.
- *Falsified if* the bound is exceeded above the stated risk in any class,
  or is too large to be usable.

**Why SWORT has an advantage. None.** SWORT/CSIA has no vision, lidar or
perception assets (R090). The field is crowded with GNSS-integrity, vision
and ML-perception communities.

**What would kill the direction for SWORT.**

- Its fit score (H = 1).
- The strength of incumbent communities (R070, R071, R024).

As a gap it remains real.

**Usefulness and feasibility.**

| aspect | rating | basis |
|---|---|---|
| commercial usefulness | HIGH | the listed losses |
| research usefulness | HIGH | — |
| experimental feasibility for SWORT | LOW | no assets |

## G07: validity of the runtime-assurance recovery assumption under degradation

**Exact problem.** Runtime-assurance architectures verify their recovery
function and switching boundary offline against a nominal vehicle model.
After degradation, the searched fielded and standard material does not show
the architecture establishing at runtime that recovery is still achievable.

**Why current systems fail.**

- The searched Simplex literature states that model error invalidates the
  guarantee (R003; attribution UNCLEAR).
- A mission-level RTA study reports that the fallback is "not always
  sufficiently capable" (R008).
- Whether ASTM F3269 requires a runtime re-establishment of recovery
  capability is UNCLEAR, because the standard was not read (R001).

**Closest prior art.**

- R002: L1Simplex.
- R004: adaptive provably correct Simplex; emergency-brake Simplex; conformal
  recovery-deadline certificates.
- R005: backup CBFs with online forward integration.
- R034: online reachable sets under diminished authority.

**What is actually missing.** The degradation bound that these adaptive
methods take as input, established from runtime vehicle evidence before
recovery is needed. That makes it **dependent on G02**.

**Who needs it.**

- UAS applicants using ASTM F3269 (R001).
- eVTOL RTA designs (R007).
- RTA for learning-enabled functions (R030).

**Why they would care.** A silently incapable recovery function voids the
runtime-assurance argument.

**Why it is scientifically hard.** It needs guarantees under changed dynamics
with a bound obtained online (R034, R035).

**Smallest falsifiable question.**

- *The question.* When the recovery function's actuator authority is
  degraded below its design assumption, does a runtime recoverability
  statement, computed from vehicle evidence before engagement, correctly
  predict recovery success or failure in degraded-authority simulation
  trials?

**Why SWORT has an advantage. Small.**

- It has the degradation-injection apparatus (R090).
- It has no RTA implementation.

**What would kill the direction.**

- Full text of R001 or R004 shows runtime re-establishment of recovery
  capability is already required or solved (queue Q4–Q6).
- No aircraft incident attributable to it was found; the importance score is
  already 3 for that reason.

**Usefulness and feasibility.**

| aspect | rating |
|---|---|
| commercial usefulness | MEDIUM |
| research usefulness | MEDIUM-HIGH |
| experimental feasibility | MODERATE-HIGH in simulation |

## Decision rule applied

The rule is the one stated in `GAP_LANDSCAPE.md` §0. A high-value gap needs
all of:

- it survives the red team;
- A ≥ 4;
- B ≥ 3;
- D ≥ 4;
- total ≥ 30.

| id | survives | A ≥ 4 | B ≥ 3 | D ≥ 4 | total ≥ 30 | high value? |
|---|---|---|---|---|---|---|
| G02 | yes | 4 ✓ | 3 ✓ | 5 ✓ | 35 ✓ | **yes** |
| G08 | yes | 5 ✓ | 4 ✓ | 5 ✓ | 34 ✓ | **yes** |
| G07 | yes | 3 ✗ | 3 ✓ | 4 ✓ | 31 ✓ | no |
| G12 | yes | 4 ✓ | 3 ✓ | 4 ✓ | 28 ✗ | no |

**Sensitivity.** Adding "I (defensibility) ≥ 3" would disqualify every
candidate. Both qualifying gaps are **real and unsolved, but crowded**.
Neither is an uncontested research territory.

**Next research dollar: G02.**

- It is the only qualifying gap where SWORT has any asset fit.
- Its fielded shortfall is observed at V4 (R080–R084).
- **The first spend should be the full-text kill check** on R042, R036 and
  R034 (queue Q1–Q3), before any design work.

**Decision:** `MULTIPLE_HIGH_VALUE_GAPS_FOUND`
