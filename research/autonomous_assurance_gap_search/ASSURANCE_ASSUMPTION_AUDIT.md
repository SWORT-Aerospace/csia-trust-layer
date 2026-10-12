# Assurance-assumption audit

Gap analysis, 2026-09-28. Source ids `Rnnn` are defined in
`research/autonomous_assurance_gap_search/GAP_LANDSCAPE.md` §1.

This file covers two of the brief's special-attention topics:

- **assumption failure without component failure;**
- **evidence → guarantee.**

It also attacks the brief's own candidate, **online assurance-assumption
validity** (G01), without privileging it.

## 1. Do existing runtime-assurance systems monitor the assumptions under their own guarantees?

| system / method | what it monitors at runtime | does it monitor its **own** guarantee's assumptions? | source |
|---|---|---|---|
| ASTM F3269 RTA | aircraft behaviour against predefined safety limits; engages a recovery control function | **UNCLEAR**: the standard was not read. The summaries describe monitoring of behaviour, not of the recovery function's continued capability | R001 |
| Simplex (original) | state against a recoverable region verified offline | **no**: the searched literature says model error invalidates the guarantee (attribution UNCLEAR), and L1Simplex calls the original "unsuitable" under physical failures | R002, R003 |
| L1Simplex / adaptive Simplex / emergency-brake Simplex / conformal recovery-deadline certificates | adapt the high-assurance controller or recompute constraints and deadlines when conditions change | **partly**: they adapt, given a model or bound of the change. Establishing that bound from vehicle evidence is not shown in the summaries | R002, R004 |
| backup CBFs | the safe set, by forward integration under the backup policy each cycle | **partly**: the guarantee tracks the model used in the integration; whether that model is updated for degradation is outside the method | R005 |
| online reachable sets under diminished authority | reachable sets shrunk or inflated from a nominal precomputation | **yes, given** a bound on trajectory-deviation growth after the change | R034 |
| ModelPlex | compliance of the execution with the verified model; fail-safe on non-compliance | **yes**, for the model's stated behaviour, including partial observability | R021 |
| CoCo | calibrated confidence per verification assumption, composed into confidence in the guarantee | **yes**, by design | R020 |
| assume-guarantee assumption monitors | environment assumptions of verified components | **yes** | R019 |
| weakly-hard monitors | (m,k) timing assumptions; switch to safe mode | **yes** | R023 |
| FRET/Ogma/Copilot | requirement formulas, including assumptions, as hard-real-time C monitors on cFS/ROS 2 | **yes**, for assumptions expressible over observed signals | R022 |
| perception contracts | perception error against contract bounds | **yes**, where ground truth is available | R024 |
| ODD monitors | ODD attributes; exit | **yes**, for specified attributes | R028, R029 |
| Auto-GCAS (fielded) | predicted trajectory against terrain, using an aircraft performance model | **UNCLEAR** whether degraded performance is tracked | R006 |
| PX4 / ArduPilot failsafes (fielded) | fixed-threshold signals: wind, battery time versus return time, flight time; post-saturation thrust loss | **no**: these are threshold monitors, not guarantee-assumption monitors | R080–R084 |

**Answer.**

- **Research: yes, with a precondition.** Runtime assurance and runtime
  verification do monitor the validity of their own assumptions. The
  precondition is that the assumption is **expressible over observed
  signals**, or comes with a given bound (R019–R024, R034).
- **Standard: unknown.** Whether the certified RTA standard requires the
  recovery function's capability to be re-established at runtime is UNCLEAR
  (R001 not read).
- **Fielded open-source autopilots: no.** They monitor signals against fixed
  thresholds (R080–R084).

## 2. The brief's example assumptions, classified by how observable they are

| assumption (from the brief) | observable signal? | existing runtime treatment | status |
|---|---|---|---|
| maximum latency | yes | weakly-hard and requirement monitors (R022, R023) | MONITORED_DIRECTLY |
| computational timing | yes | the same | MONITORED_DIRECTLY |
| communication availability | yes | PX4 manual-control-lost and GCS-connection-lost flags with configurable action (R086, V4) | MONITORED_DIRECTLY |
| environmental bounds (wind) | estimated from the state estimate | PX4 wind limit (R080) | MONITORED_WITH_FIXED_THRESHOLD |
| battery reserve (energy) | estimated | PX4 return time versus battery time (R081, R082); NASA remaining flying time (R040) | ESTIMATED_AND_USED |
| battery **power** (peak deliverable) | latent: depends on SOC, temperature, ageing and load history | eVTOL power-capability assessment in research (R043, R044) | **LATENT_CAPABILITY** → G02 |
| minimum actuator / yaw authority | latent: depends on propulsor health, power available and demand | ACAI (R033), reachable sets (R034, R035), attainable moment sets (R052) in research; fielded only post-saturation (R084) | **LATENT_CAPABILITY** → G02, G07 |
| CG / mass envelope | estimated | online mass/inertia estimation (R074) | ESTIMATED_AND_USED (G11 killed) |
| aerodynamic envelope | latent after damage | safe flight envelope estimation (R032); EA-FMS (R037) | research (fixed-wing) → G02 for rotorcraft |
| sensor integrity | depends on the sensor | analytical redundancy (R073); integrity monitoring for GNSS | covered, except for vision/terrain navigation → G08 |
| estimator quality / localization error | **latent**: the true error is not observable | protection levels for GNSS; open for vision (R070) | **LATENT_ERROR_BOUND** → G08 |
| redundancy assumptions | partly | earlier package (R069, R073) | not reopened |
| model validity | via residuals and compliance | ModelPlex (R021); earlier package | covered |
| recovery achievable (the RTA's own assumption) | latent | adaptive Simplex and backup CBFs given a model (R002, R004, R005) | **LATENT_CAPABILITY** → G07 |

**Organizing finding.** In the searched sources, monitoring is established
for assumptions over **observable signals**. It is also established for
assumptions whose bound is **given**. What is not established in fielded
practice is monitoring for assumptions over **latent quantities**:

- remaining authority;
- deliverable power;
- recoverability;
- the true navigation error.

These need an estimate with a conservative bound. The estimate degrades
together with the vehicle, which is exactly when it is needed. This
observation organizes the survivors G02, G07 and G08. It is not offered as a
new result: the reachability and integrity literatures (R034, R035, R070)
state versions of it.

## 3. Assumption failure without component failure: documented cases

| case | assumption that failed | component failure? | source |
|---|---|---|---|
| Ingenuity flight 72 | terrain texture sufficient for feature tracking | no | R060 |
| Hakuto-R Mission 1 | abrupt altitude changes mean sensor failure | no (the sensor was right) | R061 |
| IM-2 | altimeter noise and lighting within the design case | no hardware failure reported in the summaries | R065 |
| Amazon MK30 (Dec 2024) | lidar altitude valid in rain after the software update | no hardware failure reported in the summaries | R062 |
| 737 MAX | pilot recognition and response as assumed in the hazard assessment | a sensor failure triggered it, but the failed assumption was about response | R064 |
| Helios HP03 | analysis methods adequate for the changed configuration | no | R063 |
| Schiaparelli, Ariane 501 | saturation duration; reused trajectory envelope | no hardware failure | R069 |

## 4. Evidence → guarantee: does "guarantee G holds because A1..An are supported by E1..Em" exist at runtime?

**Yes. Status: KILL (G04).** The searched sources contain:

- ConSerts: conditional safety certificates resolved at runtime (R010);
- dynamic safety cases (R011);
- dynamic assurance cases, demonstrated on an autonomous-taxiing UAS (R012);
- ENTRUST: runtime evidence updates the dynamic parts of an assurance case
  (R013);
- ReSonAte: runtime hazard-rate estimation from bow-ties and monitors,
  including design-time assumptions (R014);
- UL 4600 safety performance indicators on assumption validity (R015);
- consistency between safety indicators and the safety case in AdvoCATE
  (R016);
- Assurance 2.0 defeaters (R017);
- subjective-logic runtime confidence updates (R018);
- CoCo (R020).

**What remains** is the physical content of E1..Em for latent quantities
(§2). That is carried to G02, G07 and G08, not to the assurance-case layer.

## 5. Verdict on the brief's candidate (online assurance-assumption validity)

- **As posed:** **KILL (G01, N0).**
- **The surviving residue** is narrower and physical: conservative runtime
  bounds on latent capability quantities (G02, G07) and on navigation error
  (G08).
