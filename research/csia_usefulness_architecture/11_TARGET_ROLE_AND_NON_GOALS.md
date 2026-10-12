# Target role, non-goals and anti-roadmap (Phases 22, 23, 50)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

## 1. Phase 22: what CSIA should be

The brief offered a candidate wording and asked that it not be adopted
automatically. The audit changes it in three places.

1. **"Consumes heterogeneous evidence producers" undersells what exists.**
   CSIA already has its own producers (the v2 domains, the v1 trust layer,
   the XSYS-001 witnesses). They stay, alongside wrapped external ones.
2. **"Determines whether their outputs are currently admissible" is the
   centre**, not one item in a list. It is the only missing stage in the
   pipeline (AF-01), and the only wrong attributions in the confirmatory result (the preregistered negative control) came from skipping it
   (S014).
3. **"Reasons about compatible system-state hypotheses" is too broad.** CSIA
   eliminates **declared** hypotheses and says so when none survives. It does
   not model system state.

**The definition:**

> CSIA is an evidence-qualification and hypothesis-bookkeeping layer for
> autonomous aircraft. It sits between the monitors that already exist
> (autopilot health and estimator status, textbook change detectors, its own
> domain plugins) and the functions that depend on their conclusions.
>
> For every piece of evidence it decides, from a declared contract and the
> current configuration context, whether that evidence may be used **now**.
> It tracks what each accepted item depends on, so that a configuration
> change invalidates exactly the evidence it affects. It eliminates declared
> fault hypotheses only with admissible evidence that does not depend on the
> component under suspicion.
>
> It reports what remains:
>
> - a supported explanation;
> - a preserved ambiguity;
> - a disagreement between producers, with its likely reason;
> - insufficient evidence;
> - or no consistent hypothesis.
>
> Each report comes with the configuration it holds under, what evidence
> would resolve it, and a replayable justification trace.
>
> It detects no new phenomena of its own beyond what its producers detect,
> it fuses no estimates, and it commands nothing.

The definition does not describe CSIA as a universal fault detector, or as a
replacement for IVHM, FDI, runtime assurance, the flight controller, active
diagnosis, reachability or health-aware planning.

## 2. Phase 23: non-goals

CSIA delegates the following. Each line names who owns it instead.

| CSIA does not | owner | why (source) |
|---|---|---|
| implement every anomaly detector | the producers: autopilot monitors, textbook detectors, OEM BIT | INVENTION_GATE CLOSED (S030) |
| estimate battery electrochemistry | battery management and SOP estimators | G02 decision (S035) |
| perform trajectory planning | the planner | role boundary |
| implement reachability | flight-stack or RTA tools | G02 decision (S035) |
| replace EKF logic or fuse estimates | the estimator (covariance intersection and integrity are its tools, S059, S073) | role boundary |
| implement an active-diagnosis planner | s-FEAST-class planners; CSIA supplies the information need | S072; S033 |
| implement a safety controller or RTA | the RTA / Simplex layer | S075 |
| perform flight control or command actuators | the flight controller | S005; S022 |
| solve general PHM | IVHM / ISO 13374 systems (S058) | role boundary |
| predict remaining useful life unless supplied externally | prognostics producers | role boundary |
| pretend correlated evidence is independent | — | `05_PROVENANCE_AND_DEPENDENCE.md` |
| produce certainty when assumptions are violated | — | `03_EVIDENCE_ADMISSIBILITY.md` |
| produce a system health score or a percentage | — | v2 rule (S005) |
| call any output a certificate or a certification | — | the novelty audits; S017 |
| mirror the autopilot's state | — | context holds 16 dimensions read from messages (`04_CONFIGURATION_TRANSITIONS.md` §2) |
| decide which adaptation to attempt | FORGE (future) | `08_PERFORMANCE_SAFETY_BOUNDARY.md` §2 |

## 3. Phase 50: what not to build

This is the anti-roadmap. These are mechanisms that earlier audits showed
should **not** become major CSIA research or engineering projects.

| do not build | because | source |
|---|---|---|
| bespoke active diagnosis | safe active diagnosis exists, including aerospace examples and real-time forms | S072; S033 (CSIA_DX_PIVOT) |
| a bespoke CUSUM replacement | textbook CUSUM met every hard constraint; ArduPilot has a drift monitor | S030 |
| generic IVHM | a mature, standardised field (ISO 13374, OSA-CBM) | S058 |
| generic model-inadequacy detection | MODEL_INADEQUACY_KILL; CSIA's all-refuted state is consistency-based diagnosis | S032 |
| generic conditional diagnosability | CSIA_DX_PIVOT: the terms are already defined and the design-time need is served | S033 |
| a generic capability-margin planner | G02_ENGINEERING_ONLY: it belongs in the flight stack | S035 |
| a generic closed-loop diagnosis theory | CLOSED_LOOP_EVIDENCE_ENGINEERING_ONLY: fragmented across fields, each fragment known | S034 |
| custom reachability | flight-stack and RTA tools | S035 |
| a custom RTA | ASTM F3269-class runtime assurance exists | S075 |
| a custom flight controller | out of role | S022 |
| custom battery electrochemistry | BMS and SOP estimation | S035 |
| a new contract or temporal-logic language | the Trust Contract v0.1, DEM conditions, and FRET/Copilot exist | S023; S050; S074 |
| a numeric evidence-independence metric | a structural provenance cut is not independence | S025 |
| a belief-function or Bayesian replacement of set elimination | it would re-import the scores v2 excluded, and has no calibration data | S001 |
| a generic provenance database | minimal tags and `derived_from` suffice; PROV for export | S065 |
| an onboard runtime before the HIL and flight levels | maturity M2, not flight software; no target measurement | S046; S020 |
