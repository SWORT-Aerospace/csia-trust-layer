# CSIA FLIGHT ASSURANCE PILOT: the offer (PRIME-1 Phases 21 and 26)

**2026-10-03.** OFFBOARD. ZERO CONTROL authority. NO FORGE. Not a
self-service SaaS product: a services-assisted engineering pilot with a
locally run Analyzer.

## 1. One-page technical overview

**What it is.** CSIA Flight Assurance reads PX4 flight logs (ULog) after the
flight. It decides **what the evidence in the log actually justifies**:
- which monitor outputs may be used, and which must be refused (and why);
- which outputs share a source, and so count once;
- which explanations remain, and which are eliminated by what;
- what the log could not observe at all;
- which measurement would separate what remains.

It states conclusions as **semantic states** (UNIQUE, AMBIGUOUS, SUPPORTED,
NO_EVIDENCE), never as probabilities. Every conclusion carries a receipt.

**What it is not:**
- anomaly detection sold as diagnosis;
- a replacement for PX4's monitors (it consumes them);
- onboard software;
- a flight-safety approval.

**Where it stands (stated to every customer before signing):**
- validated in **PX4 simulation** on one quad-X airframe (PX4 547e2ca);
- **not yet validated on real propulsion faults:** no real propulsion log
  with known truth has been analysed;
- real logs are read, their support state is decided, and what cannot be
  judged is stated.

## 2. Target customer

PX4 **quad-X** engineering teams (flight test, autonomy, integration) with
SITL, HIL or flight-test ULogs, who already use PX4's monitors and ESC RPM
telemetry, and who spend engineering time deciding what a log supports.

## 3. Scope and deliverables

| deliverable | from |
|---|---|
| assurance analysis per log | `csia-assure` first page and machine report |
| event timeline | the discovered events with their semantics (RPM_DEFICIT_EVENT, RPM_EXCESS_EVENT, COMPENSATION_CHANGE_EVENT, ESC_OFFLINE_EVENT, PX4 monitors) |
| evidence-quality report | evidence admitted and refused, with reasons, per conclusion (receipts) |
| coverage matrix | every profile record in OBSERVED, NO_ANOMALY, NO_COVERAGE, UNAVAILABLE, STALE, FAULTED, NOT_APPLICABLE, UNKNOWN |
| source-lineage map | the lineage roots per conclusion and the independent-line count |
| candidate hypotheses | the explanations remaining per symptom, and the ones eliminated |
| withheld conclusions | what the log cannot justify, stated as such |
| missing instrumentation | the measurements that would separate the remaining explanations (ESC current, battery current, command delivery, an independent RPM/thrust witness) |
| engineering review session | a SWORT engineer and the customer's engineers, per flagged log |

**Out of scope:**
- other vehicle classes: the Analyzer reports UNSUPPORTED_VEHICLE_CONFIGURATION
  and gives generic analysis only;
- certification credit;
- any onboard or control use.

## 4. Supported configurations

**The machine-readable contract is
`csia_evidence_assurance/support_contract_prime1.json`;** the readable form
is `SUPPORT_MATRIX.md`.

| configuration | state | validation level |
|---|---|---|
| quad X, PX4 with control allocation, ESC RPM telemetry | SUPPORTED on PX4 547e2ca; PARTIAL (version untested) on other versions | SIMULATION |
| quad X without ESC RPM telemetry | PARTIAL | SIMULATION |
| quad X on PX4 before control allocation | PARTIAL | REAL_LOG_CONTEXT_ONLY |
| other multirotors, fixed wing, VTOL, rover/boat | UNSUPPORTED_VEHICLE_CONFIGURATION | REAL_LOG_CONTEXT_ONLY |
| not a PX4 ULog | UNSUPPORTED_SCHEMA | REAL_LOG_CONTEXT_ONLY |

**Nothing is PHYSICAL_VALIDATED.**

## 5. Limitations (in every pilot agreement)

- Simulation-only validation of every diagnostic behaviour; every threshold
  calibrated in SITL.
- Losses during continuous maneuvering are discovered but not confirmed.
- Stock PX4 logs no ESC current: four explanations of a propulsion loss
  usually remain (AMBIGUOUS is a correct answer).
- A static telemetry offset, a slow drift, or a stuck value in steady hover
  are not discovered as changes.
- Event discovery's held-out promotion is simulation-only
  (`HELDOUT_RESULTS.json`).

## 6. Data requirements

**Per log:**
- the ULog;
- the PX4 version;
- the airframe or vehicle class;
- whether ESC telemetry is enabled;
- known modifications.

**Optional:** architecture or wiring notes, for hardware-level lineage.
`PILOT_INTAKE_AND_PROTOCOL.md` asks only for what is needed. **Logs never
leave the customer's control unless they choose; the Analyzer runs offline.**

## 7. Sample sanitized report

`sample_reports_prime1/`: the PRIME-1 first page, receipts and support
decision for three SITL logs (no customer data):
- a motor loss in hover;
- an RPM excess on a healthy motor (blinded);
- a real boat log (unsupported vehicle, generic analysis).

## 8. Timeline estimate

**An estimate, not a commitment.** For up to 20 logs:

| week | step |
|---|---|
| 0 | agreement, data-handling terms, intake form |
| 1 | intake (hashing), support screen, analysis, seal |
| 2 | the customer reveals their diagnosis; comparison; draft findings |
| 3 | review session; final report with integration recommendations |

## 9. Pricing hypothesis

**COMMERCIAL HYPOTHESIS, NOT YET MARKET-VALIDATED.**
- **Structure:** a fixed-fee pilot for a bounded number of logs (up to 20)
  and one review session, credited against a later licence.
- **Effort basis:** about 8 to 12 SWORT engineering days for 20 logs
  (intake, support screen, analysis, comparison, review, report). The fee
  is that effort at SWORT's day rate.
- **No currency figure is stated**, because none can be justified before a
  pilot has been sold.
- **No ROI figure is claimed.** Value metrics are gathered in the pilot
  (`PILOT_METRICS.md`).
