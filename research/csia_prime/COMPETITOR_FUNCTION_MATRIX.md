# What established categories already provide (PRIME Track D1)

**2026-10-02. Not a novelty hunt.**

**The question:** for each established category, does it typically provide
each function CSIA claims? The aim is to find what is commercially
defensible, not to claim uniqueness.

## 1. Basis and its limits

**Sources:**
- this repository's earlier prior-art packages:
  - `research/csia_novelty_audit/` (closest systems, the minimum remaining
    core, the patent screen; bibliography ids B…/P…);
  - `research/effective_evidence_independence/` (the independence reduction
    to ARP4761 common-cause analysis, common-information fusion and
    meta-diagnosis);
  - `research/csia_usefulness_architecture/` (admissibility, correlation,
    monitor health, contracts);
- PRIME's own searches of 2026-10-02 for products (§4 sources).

**Access:** patent full texts, the PX4 forum and USPTO hosts are blocked
here. Product entries are read from search summaries (V0). "Not typical"
means **not shown in the sources read**, never "absent".

**Key:** Y typical · P partial or in some systems · N not typical in the
sources read · ? not shown.

## 2. The function matrix

| category | heterogeneous producers | evidence validity | temporal validity | configuration validity | producer health | source lineage | dependency-aware corroboration | explicit ambiguity | hypothesis bookkeeping | reason receipts | missing-evidence explanation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| residual-based FDI (parity, observers, GLR) | N (one subsystem) | P (residual validity regions) | P (transient/steady) | P (mode-scheduled) | N | N | N | P (isolability) | N | N | N |
| built-in test (BIT) | N | P (inhibit conditions) | P (persistence, debounce) | P (mode-dependent) | P (self-test) | N | N | P (ambiguity groups) | N | P (fault codes) | N |
| EKF health monitoring (innovation tests) | P (multi-sensor fusion) | Y (gating) | Y | Y (aiding modes, lane selection) | P | N | N | N | N | N | N |
| structural diagnosis (ARRs, D-matrix, diagnosability) | Y | P | N | P | N | P (structural dependencies) | P | Y (isolability) | Y | P | **Y** (which tests would isolate) |
| consistency-based model-based diagnosis (GDE family) | Y | P | P | P | P (sensors as components) | P | P | Y (diagnosis sets) | Y | Y (conflicts) | **Y** (measurement selection) |
| **aircraft vehicle-level reasoners (Honeywell ADMS / VIPR; QSI TEAMS)** | **Y** | P (not shown in detail) | P | **Y** (reference model encodes configuration) | P | P (reference model) | **P (Honeywell US 7,337,086: evidence aggregated by its dependency)** | **Y** (ambiguity groups) | **Y** | P | P (testability analysis) |
| runtime assurance (Simplex, R2U2-style monitors) | P | P | Y (temporal logic) | P | P | N | N | N | N | P | N |
| active diagnosis | P | P | P | P | N | N | N | Y | Y | N | Y (designs inputs), **but needs control authority** |
| digital-twin diagnostics | Y | P | P | P | N | N | N | P | P | N | N |
| predictive maintenance | P | N | P | N | N | N | N | N | N | N | N |
| **drone flight-log tools** (Flight Review, Foxglove, FlightMD, BBA Flight Hub, LogLens, Auterion Suite) | P (many topics, per-check rules) | P (rule thresholds) | N | N | N | N | N | **N (health score; pass/warn/fail)** | N | P (findings, parameter fixes) | N |
| **CSIA Flight Assurance** (as built; validated in SITL only) | Y | Y (2.2 admissibility) | Y (event-relative windows, content time) | Y (configuration epochs) | Y (producer health) | Y (lineage roots per output) | Y (lineage groups; independent lines) | Y (AMBIGUOUS, UNSUPPORTED) | Y (2.1.1) | Y (receipts) | Y (coverage classes; diagnosability) |

## 3. What the matrix says

**Every function CSIA has exists in established practice somewhere:**
- **Aircraft vehicle-level reasoners** come closest. They separate monitors
  (evidence) from a reference model and a reasoning engine, are deployed
  on transport aircraft, and keep ambiguity groups.
  - Honeywell holds a patent on combining diagnostic evidence according to
    its interdependence.
  - Consistency-based diagnosis has proposed discriminating measurements
    since the GDE work.
- **The independence question reduces to known problems** (the repository's
  `effective_evidence_independence` study): ARP4761 common-cause analysis,
  common-information fusion, meta-diagnosis.

**Where CSIA does differ, commercially, is the gap between those two
worlds:**
- **Drone flight-test tools** give per-check results, health scores and
  pass/warn/fail flags. None shown reasons about evidence validity,
  producer health, lineage or ambiguity.
- **Aerospace reasoners that do** are built for certified, manned-aircraft
  programs with hand-built reference models.
- **CSIA's position** is evidence assurance for the PX4/ULog
  flight-test engineer, offboard, with no reference-model project:
  - the profile is shipped;
  - the producers wrap PX4's own monitors;
  - every conclusion carries a receipt.

**That is a product position, not a technical first.** Its defensibility is
execution:
- the stock-PX4 producers and their contracts;
- the validity rules learned from PX4's actual behaviour (the steadiness
  regime, the event windows, the D-PRIME-1 class of timing traps);
- the receipts;
- above all, real-data validation, which does not exist yet.

## 4. Product sources (V0, search summaries of 2026-10-02)

| product | what the summary shows |
|---|---|
| PX4 Flight Review | plots and basic analysis of ULog; PX4's own log tool |
| Foxglove | robotics observation platform; replays ULog; visualisation |
| FlightMD (open source) | .ulg/.bin/.tlog; 8 deterministic rule checks (oscillation, vibration, EKF, battery, GPS, parameters, motors); a health score and parameter fixes; validated against 50 public PX4 logs |
| BBA Flight Hub | web; automatic charts (motor health, battery, GPS, vibration FFT, EKF); AI-generated reports with severity and fix recommendations; supports .ulg |
| LogLens | offline app; deterministic rules (battery, GPS, vibration, estimator, failsafes) |
| Auterion Suite | fleet cloud; every flight analysed; metrics flagged pass/warning/failure; vehicle status Healthy/Warning/Critical; predictive maintenance |
| Honeywell ADMS (777, 787) and VIPR | monitors, reference model and reasoner kept apart; vehicle-level reasoning over subsystem monitors |
| QSI TEAMS-RT | multisignal models; ambiguity groups (suspect/absolved components); multiple modes |
| Honeywell US 7,337,086 | combining diagnostic evidence for turbine-engine fault detection, with aggregation by evidence dependency |
