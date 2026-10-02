# Defensible claim and IP screen (PRIME Tracks D2-D3)

**2026-10-02. NOT LEGAL ADVICE. NO PATENT DRAFTED.**

**Engineering value and patent novelty are kept apart.** A useful product
does not need patent novelty.

## 1. D2: the candidate claim, challenged

**The brief's candidate:**

> "A system for qualifying heterogeneous diagnostic evidence before
> cross-system fault attribution by tracking source dependence, validity
> context, producer health and competing hypotheses."

**Challenged, element by element** (`COMPETITOR_FUNCTION_MATRIX.md`):

| element | anticipated by (as far as V0 summaries show) |
|---|---|
| heterogeneous diagnostic evidence → cross-system attribution | aircraft vehicle-level reasoners (Honeywell ADMS/VIPR), consistency-based diagnosis |
| tracking source dependence | Honeywell US 7,337,086 (evidence aggregated by dependency); ARP4761 common-cause analysis; the repository's own reduction (`effective_evidence_independence`) |
| validity context | mode-scoped ARR validity, residual validity regions, phase-conditioned suspension in fielded autopilot code (earlier audit: B119, B142, B130) |
| producer health | monitor self-test and BIT; runtime-monitor health (R2U2-style) |
| competing hypotheses | consistency-based diagnosis; TEAMS ambiguity groups |

**Verdict: as a whole, the candidate is too broad to defend.** Each element
is established, and the combination is close to what deployed aircraft
reasoners do.

**The narrowest strong statement the implementation and data support** is
an engineering claim, not a patent claim:

> **For PX4 multirotor flight logs, CSIA reports, for every conclusion, which
> monitor outputs were admitted and which were refused, and why: validity
> window, steadiness regime, producer health, log gap, schema. It counts
> corroboration by shared hardware/software lineage rather than by how many
> monitors fired. It never reports an unobserved record as healthy. In SITL
> it kept a telemetry corruption matched to a motor loss's RPM symptom from
> becoming a motor-failure symptom, in every one of 1,056 perturbed runs,
> while naming the right motor for hover and hold losses.**

**The qualifiers are part of the claim:**
- SITL only;
- one airframe;
- PX4 547e2ca for full analysis;
- no real propulsion validation.

## 2. D3: IP screen

**No claim was read. No legal conclusion is drawn.**

### 2.1 Potentially protectable combinations (for a registered patent attorney only)

| # | combination | nearest threat | technical concern |
|---|---|---|---|
| 1 | **MNC-1 (earlier audit):** separating physical rotor-effectiveness loss from telemetry corruption that matches the local RPM symptom, with a transient dynamics witness and a compensation witness, each valid only in its own window | **EPOS family (RTX): US 10,557,418, 11,203,950, 11,319,834, 11,905,891**; US 4,641,517 | **HIGH** (`research/csia_novelty_audit/CSIA_PATENT_PRIOR_ART_SCREEN.md`) |
| 2 | detectability-gated "nominal" affirmation (a witness may refute a loss only if the loss would have been detectable) | consistency-based diagnosis with fault-sensitivity conditions | unknown, needs full text |
| 3 | event-relative validity windows plus steadiness regimes plus producer health as one offboard admissibility gate for autopilot logs | Honeywell ADMS/VIPR monitor architecture; mode-scoped validity in FDI | LOW to MODERATE: likely an instance of known practice |
| 4 | coverage classes that never collapse unobserved evidence into healthy | three-valued logic; standard | LOW: not worth pursuing |

### 2.2 Direct prior-art threats

| threat | relevance |
|---|---|
| EPOS family (RTX) | the XSYS-001 idea on an engine: an actuator's own sensor against the actuator, a shared local symptom, a physical-response discriminator |
| US 4,641,517 | sensed against synthesized actuator position; sensor or actuator fault |
| Honeywell US 7,337,086 | dependency-aware combination of diagnostic evidence |
| Honeywell US 8,346,700 (vehicle health monitoring reasoner architecture), ADMS, VIPR | monitors, reference model, reasoner; vehicle-level reasoning |
| QSI TEAMS-RT | ambiguity groups, multisignal models |
| ArduPilot `thrust_balance` (fielded code, earlier audit B130) | controller compensation as root-cause evidence |

### 2.3 Open-source and licence check (the product's runtime path)

| item | licence | status |
|---|---|---|
| numpy, scipy, networkx | BSD-3 | permissive |
| matplotlib (declared dependency) | matplotlib licence (PSF-style) | permissive |
| pyulog (the `logs` extra) | BSD-3 | permissive |
| PX4 (logs only; no code linked) | BSD-3 | no contamination |
| test data: pyulog test logs | BSD-3 | used in tests and research; keep the notice if redistributed |
| test data: PX4 docs boat log | CC-BY-4.0 | attribution required if redistributed; not redistributed |
| RflyMAD tool repository | **no licence file** | read for its topic descriptor only; nothing copied into the product |
| this repository | "Proprietary" (pyproject); GitHub: private, no licence asserted | — |

**No copyleft code is in the product path** (dependencies as declared in
`pyproject.toml`). A full dependency audit (transitive licences) belongs
in the commercial release checklist.

### 2.4 Claims that are too broad

These are anticipated, so they must not appear as differentiators:
- "cross-system assurance";
- "evidence assurance for autonomous systems" (as a technical claim);
- "dependency-aware corroboration";
- "explicit ambiguity";
- "hypothesis elimination";
- "AI diagnostics";
- "motor fault detection".

### 2.5 What is already public

**As far as the repository shows:**
- the GitHub repository is **private**;
- the two papers have no submission-candidate tag
  (`docs/CURRENT_PROGRAM_STATE.md`);
- the one GitHub release is in the private repository.

**Unknown here:** any sharing outside the repository (documents sent,
talks, demos). The earlier audit already put the effect of commit dates
and visibility to the attorney (`CSIA_IP_CANDIDATE_MAP.md`).

**If any filing is considered, it should precede any public demo or paper
that discloses combination 1 or 2.**

## 3. What follows commercially

**The defensible asset is know-how and validation, not a patent:**
- **the PX4-specific validity rules** (steadiness regime, event windows,
  the timing traps such as D-PRIME-1);
- **the sim-to-real receipts;**
- **the support matrix,** and later a real-data corpus with ground truth.

Real validation data is the moat competitors cannot copy from a paper.
That puts the commercial weight back on Track B.
