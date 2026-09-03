# FORGE — PRIOR ART THAT MUST BE WORKED THROUGH FIRST

**DOCUMENTATION ONLY. NO IMPLEMENTATION.**

This is a reading and reduction list, not a bibliography. Each row must end
with one of three conclusions **written down**, before any Forge code exists:

- **SUBSUMED** — the existing work does this; use it, do not rebuild it
- **ADJACENT** — related, does not do this, and here is the specific difference
- **GAP** — genuinely not covered, and here is the evidence for that claim

A row with no conclusion is an unfinished row. `GAP` requires the most
evidence and is the least likely correct answer.

---

## 1. Model-based diagnosis and structural analysis

| topic | why it matters to Forge | conclusion |
|---|---|---|
| structural analysis / Dulmage–Mendelsohn decomposition for FDI | this is the established route from a model to which faults are isolable. Forge's whole premise overlaps it | TO BE WRITTEN |
| minimal structurally overdetermined (MSO) sets | residual generator selection from a structural model | TO BE WRITTEN |
| sensor placement for fault diagnosis (Krysander & Frisk) | already cited by the systems paper; directly the "what should we instrument" question Phase C's set B raised | TO BE WRITTEN |
| test selection for multimode systems (Krysander & Hashemniya, DX 2024) | mode-dependent signatures = CSIA's gate-dependent effective signatures | TO BE WRITTEN |
| fault trees and sensor selection by diagnostic performance (Andrews et al.) | the metric side of the same question | TO BE WRITTEN |

## 2. Architecture description and error modelling

| topic | why | conclusion |
|---|---|---|
| **AADL + EMV2** error propagation analysis | this is the closest existing thing to CSIA's dependency graph, with tooling (OSATE). If EMV2 already expresses what CSIA needs, Forge is an *importer*, not a modelling language | TO BE WRITTEN |
| SysML v2 API and services | the modern interchange route | TO BE WRITTEN |
| CycloneDX / SPDX | software composition; the version and configuration-hash side of the ledger | TO BE WRITTEN |
| ARP4761 / FHA-FMEA-FTA tooling | the safety-assessment artifacts an aerospace organisation already produces | TO BE WRITTEN |

## 3. Diagnosability and its verification

| topic | why | conclusion |
|---|---|---|
| diagnosability of discrete-event systems (Sampath et al. and successors) | the formal question Forge would ask Z3 | TO BE WRITTEN |
| robust diagnosis under intermittent / permanent loss of observations (Carvalho, Basilio, Moreira, Lafortune) | already cited; directly Mechanism A's territory | TO BE WRITTEN |
| state-dependent observation maps (Dong, Yin, Li) | owns the general mechanism; CSIA asserts no priority | TO BE WRITTEN |
| **safe diagnosability** (Paoli & Lafortune, Automatica 2005) | detection before a forbidden string, so reconfiguration can be forced in time. **This is the closest prior art to PART G's proposal and it is close** | TO BE WRITTEN |
| active fault diagnosis / active model discrimination | designing inputs to increase separability under safety constraints | TO BE WRITTEN |

## 4. Resilience, reconfiguration and digital twins

| topic | why | conclusion |
|---|---|---|
| **Matei et al., *System Resilience through Health Monitoring and Reconfiguration*, ACM TCPS 8(1), 2024, DOI 10.1145/3631612** | named in the brief as required reading. Digital twin + diagnosis + prognostics + reconfiguration, *including interventions to disambiguate uncertain diagnosis*. Overlaps both Forge and PART G substantially | TO BE WRITTEN |
| fault-tolerant control (Blanke, Kinnaert, Lunze, Staroswiecki) | the reconfiguration side; already cited | TO BE WRITTEN |
| dynamic reconfigurable discrete-event systems | the formal reconfiguration literature | TO BE WRITTEN |
| autonomic computing (MAPE-K) | the monitor-analyse-plan-execute loop Forge+CSIA+controller resembles | TO BE WRITTEN |
| runtime certification / conditional safety certificates | certificates conditional on runtime evidence — very close to "which functions are still justified" | TO BE WRITTEN |
| digital-twin resilience | the model-in-the-loop framing | TO BE WRITTEN |

## 5. Solvers and encodings

| topic | why | conclusion |
|---|---|---|
| SMT encodings of diagnosability | before writing a Z3 encoding, find the ones that exist | TO BE WRITTEN |
| CP-SAT for redundancy allocation and sensor placement | before writing an OR-Tools model, find the ones that exist | TO BE WRITTEN |

---

## The rule

**A `GAP` conclusion requires evidence, not absence of a search.** "I did not
find it" is not a gap. The bar is: the closest work was located, read, and its
specific difference stated.

## Verification status of this list

Every reference named above that is not already in
`papers/csia_systems/refs.bib` is **unverified**. Egress from this environment
denies `doi.org`, `dblp.org` and `api.crossref.org`, so no publisher record
was consulted. The two entries with the most detail — Paoli & Lafortune 2005
and Matei et al. 2024 — came from web search and are recorded in
`research/math-paper/PRIOR_ART_MATRIX.csv` with status
`CANDIDATE_UNVERIFIED`.
