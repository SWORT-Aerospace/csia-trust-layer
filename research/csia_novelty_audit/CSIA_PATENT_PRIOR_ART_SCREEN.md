# CSIA patent prior-art screen (stage 2, pre-result)

This file is part of the second-stage novelty verification (2026-09-27/28).
Patent ids are listed in `research/csia_novelty_audit/BIBLIOGRAPHY.md`.

## What this is, and what it is not

This is **technical prior-art triage**:

- It asks whether a patent document **discloses** technology close to CSIA's
  remaining candidate (MNC-1 and MNC-2 in
  `research/csia_novelty_audit/CSIA_MINIMUM_NOVEL_CORE.md`), or to CSIA's
  broader vision.
- It is **not legal advice.**
- It reaches **no conclusion on patentability, validity, infringement or
  freedom to operate.**
- Any decision on those questions belongs to a registered patent attorney.

**Access.** No patent claim was read. Google Patents, the USPTO full-text and
PDF hosts, Justia and freepatentsonline are all blocked from this environment
(search log §S2.1). The PDF host was retested on 2026-09-27. Everything below
comes from search-engine titles and summaries (**V0**). For the EPOS family,
it also comes from a short excerpt of the patent text rendered by the search
engine (S2Q35). **"Independent claims most relevant" is therefore unknown for
every patent.** It is marked REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION, and
the claim numbers to check are those the full text shows as independent.

**Concern level** is a technical judgement about how closely the **disclosure**
(the description, not only the claims) approaches CSIA's candidate. It is not
a legal risk rating. The levels are:

- **LOW:** the disclosure, as shown, is outside the candidate.
- **MODERATE:** it overlaps a component of the candidate or the vision.
- **HIGH:** it states the idea of a candidate element.
- **UNKNOWN_PENDING_FULL_TEXT:** too little is shown to judge.

## The ten patents

### 1. EPOS family: US 10,557,418 (P03), with US 11,203,950 (P04), US 11,319,834 (P05) and US 11,905,891 (P25)

| field | content |
|---|---|
| number | US 10,557,418; family members US 11,203,950, US 11,319,834 B2 (pre-grant US 2019/0226354 A1; EP 3527805 A1) and US 11,905,891 |
| priority date | not confirmed. A filing date of 2018-01-25 is shown for the family (S2Q39; which member is unconfirmed) |
| assignee | shown as United Technologies Corporation (freepatentsonline, for US 2019/0226354) and Raytheon Technologies Corp. (for US 11,905,891); now RTX. Inventor shown: R. P. Meisner |
| independent claims most relevant | **REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION.** Check whether any independent claim recites distinguishing an actuator-sensor fault from an actuator-hardware fault using the engine (plant) response, and whether it recites time windows or loop behaviour |
| technical concept | an on-board engine model (EPOS) that estimates the engine response. Search-rendered text: "Both actuator sensor faults and actuator hardware faults experience an inability of the minor loop of the control law module to keep an error between the feedback actuator response signal and the requested control signal within required tolerance. However, the engine response during an actuator sensor failure is very different and distinguishable from the engine response during an actuator hardware failure." The feedback signal drifts below the request for a sensor failure, and above it (tracking the actual actuator) for a hardware failure. Fault accommodation follows |
| overlap with CSIA | **the XSYS-001 idea**: the pair (an actuator's own sensor versus the actuator), the shared local symptom, and a physical-response discriminator from another subsystem. Also the use of loop behaviour, through the direction of drift, as a cue |
| material difference (as far as V0 shows) | a different plant (gas-turbine engine) and channel (an actuator position sensor **inside** the loop, versus multirotor RPM telemetry **outside** it). No transient-versus-compensation windows are shown, no controller-effort witness, no ambiguity-preserving verdict, and no matched-by-construction evaluation |
| verification level | V0 (search-rendered text excerpt; no claim read) |
| concern level | **HIGH** for the XSYS-001 question and MNC-1 |

### 2. US 4,641,517 (P01)

| field | content |
|---|---|
| priority date | not shown. The grant is dated 1987 (stage-1 summary) |
| assignee | not shown |
| independent claims most relevant | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| technical concept | "Control system actuator position synthesis for failure detection": a sensed actuator position is compared with a model-synthesized position, and a routine decides whether the fault is in the **sensors or the common actuator** |
| overlap with CSIA | actuator-versus-own-sensor discrimination against a model |
| material difference | no second physical subsystem as witness, as shown; no windows, compensation witness or ambiguity output shown |
| verification level | V0 |
| concern level | **MODERATE** for broad actuator-versus-sensor claims; LOW for MNC-1 as shown |

### 3. US 11,691,747 (P15); publication US 2021/0380266 A1

| field | content |
|---|---|
| priority date | not shown |
| assignee | not shown |
| independent claims most relevant | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| technical concept | "Fault detection for a speed sensing system of a multi-engine rotorcraft". Per S2Q36: if shaft speed exceeds rotor speed, a speed-sensing fault is declared; if lower, fuel flow decides whether the engine is still coupled to the rotor |
| overlap with CSIA | separating a **speed-sensor** fault from a **physical** fault, using a second physical channel. This is the closest patent to the RPM-telemetry side of XSYS-001 |
| material difference | a rotorcraft engine and drivetrain; fuel flow rather than vehicle dynamics or controller effort; no windows or ambiguity output shown |
| verification level | V0 |
| concern level | **MODERATE** |

### 4. US 12,134,484 (P07)

| field | content |
|---|---|
| priority date | not shown |
| assignee | The Boeing Company (S2Q26); inventors J. M. Keller, L. Wang, J. M. Ethington |
| independent claims most relevant | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| technical concept | "Contextually-informed fault diagnostics using structural-temporal analysis of fault propagation graphs"; an aircraft reasoner with a fault-pattern library |
| overlap with CSIA | temporal plus structural reasoning over a cross-system graph (F17, F25); "contextually-informed" may cover context-scoped evidence validity (F09) |
| material difference | unknown at V0; no actuator-versus-telemetry pair or windowed witness shown |
| verification level | V0 |
| concern level | **MODERATE** for the architecture vision; **UNKNOWN_PENDING_FULL_TEXT** for MNC-1 |

### 5. US 9,725,187 B2 / US 2010/0017049 A1 (P24)

| field | content |
|---|---|
| priority date | not shown. Pre-grant publication 2010-01-21 |
| assignee | The Boeing Company (S2Q28); inventors K. Swearingen, J. M. Keller. A related member, US 8,942,882, was seen once (unconfirmed) |
| independent claims most relevant | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| technical concept | "Vehicle health management systems and methods". A change in actuator health state produces a health score from **risk, confidence and benefit** values. Confidence compares the current state with verification-and-validation conditions. A flight-critical module compares the score with a threshold before reconfiguration. Vehicle information is filtered for internal/external consistency and stability over time |
| overlap with CSIA | CSIA's **action-authority vision** (C10, C19; F19): diagnostic confidence gating what the vehicle may do. Also the separation of diagnosis from action (F16) |
| material difference | CSIA has **no implementation** of authority. Nothing can be distinguished today |
| verification level | V0 |
| concern level | **HIGH** for the action-authority vision; LOW for MNC-1 |

### 6. US 11,061,390 B2 / EP 3477412 A1 (P06)

| field | content |
|---|---|
| priority date | not shown |
| assignee | RTX Corporation (formerly Raytheon Technologies); inventors A. J. Volponi, L. Tang, S. J. Lee |
| independent claims most relevant | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| technical concept | "System fault isolation and ambiguity resolution": ranks ambiguity groups, locates supporting evidence in a diagnosis matrix, aggregates belief |
| overlap with CSIA | retained ambiguity and evidence support (F11–F13) |
| material difference | belief aggregation, where CSIA uses categorical elimination; no windowed witnesses shown |
| verification level | V0 |
| concern level | **MODERATE** for the ambiguity/sufficiency layer (already N0/N1); LOW for MNC-1 |

### 7. US 12,397,908 B1 (P09)

| field | content |
|---|---|
| priority date | not shown |
| assignee | Amazon Technologies, Inc.; X. Wang et al. |
| independent claims most relevant | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| technical concept | "Sensorless propeller damage detection": commanded against measured RPM, current ripple, then mitigation |
| overlap with CSIA | the XSYS-001 **local symptom** (commanded against measured RPM) |
| material difference | detects physical damage; telemetry corruption is not shown as a competing cause; no dynamics or compensation witness shown |
| verification level | V0 |
| concern level | **LOW** for MNC-1 as shown; the local symptom is not claimed by CSIA |

### 8. US 12,087,171 (P08)

| field | content |
|---|---|
| priority date | not shown |
| assignee | not shown |
| independent claims most relevant | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| technical concept | "Assurance module": a run-time assurance module with an input manager, safety manager and switch, alongside a mission planner, adapting to dynamic contexts (UAV; single-pilot operation) |
| overlap with CSIA | the runtime-assurance vision (F16, F19) |
| material difference | CSIA has no RTA implementation |
| verification level | V0 |
| concern level | **UNKNOWN_PENDING_FULL_TEXT** (too little shown) |

### 9. US 8,763,950 B2 / EP 2342609 B1 (P10)

| field | content |
|---|---|
| priority date | not shown |
| assignee | not shown |
| independent claims most relevant | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| technical concept | "Aircraft sensor and actuator failure protection using reconfigurable flight control laws" |
| overlap with CSIA | sensor and actuator failures on aircraft, followed by reconfiguration |
| material difference | unknown at V0 |
| verification level | V0 |
| concern level | **UNKNOWN_PENDING_FULL_TEXT** |

### 10. US 7,934,125 / US 7,596,718 (P14)

| field | content |
|---|---|
| priority date | not shown |
| assignee | not shown |
| independent claims most relevant | REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION |
| technical concept | "Ranged fault signatures for fault diagnosis" |
| overlap with CSIA | signature matrices with value ranges; possibly time-scoped signatures (F08, F09) |
| material difference | unknown at V0 |
| verification level | V0 |
| concern level | **UNKNOWN_PENDING_FULL_TEXT** |

## Summary

| patent | concern for MNC-1 / XSYS-001 | concern for the broader vision |
|---|---|---|
| EPOS family (P03–P05, P25) | **HIGH** | MODERATE |
| P01 | LOW | MODERATE |
| P15 | MODERATE | LOW |
| P07 | UNKNOWN_PENDING_FULL_TEXT | MODERATE |
| P24 | LOW | **HIGH** (action authority) |
| P06 | LOW | MODERATE |
| P09 | LOW | LOW |
| P08 | UNKNOWN_PENDING_FULL_TEXT | UNKNOWN_PENDING_FULL_TEXT |
| P10 | UNKNOWN_PENDING_FULL_TEXT | UNKNOWN_PENDING_FULL_TEXT |
| P14 | UNKNOWN_PENDING_FULL_TEXT | UNKNOWN_PENDING_FULL_TEXT |

**Strongest patent threat:**

- the EPOS family, for the XSYS-001 idea;
- US 9,725,187 (P24), for the action-authority vision.

**For a patent attorney.** Anyone considering protection for MNC-1 should give
the attorney:

- the full EPOS family (P03–P05, P25);
- P15;
- P01;
- the non-patent literature B117 and B118.

Anyone considering protection for an authority layer should give:

- P24;
- P08;
- the RTA standards (B81).

This screen does not say whether anything is protectable.
