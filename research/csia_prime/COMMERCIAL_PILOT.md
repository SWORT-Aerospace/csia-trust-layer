# The first commercial pilot: "CSIA Flight Assurance Pilot" (PRIME E3-E4)

**2026-10-02. A DEFINITION, NOT A SALE. No price and no ROI figure: both
come from pilots, not from this document.**

**Scope:** OFFBOARD. ZERO CONTROL authority. NO FORGE. No onboard component,
no automatic recovery, no flight-safety approval.

## 1. Who it is for

**A team that develops or validates a PX4 multirotor** and already has:
- SITL, HIL or flight-test ULogs;
- PX4's own monitors, EKF2 status and ESC telemetry;
- engineers who spend time answering, per log: what happened, which
  evidence can be trusted, and whether a conclusion is justified.

**Entry condition (checked, not assumed):** the logs fall inside
`csia_evidence_assurance/support_matrix.json`:
- quad X;
- PX4 with control allocation (`actuator_motors`,
  `control_allocator_status`);
- ESC RPM telemetry for propulsion conclusions.

The support check runs first on every log. Its result is a deliverable in
itself.

## 2. What the pilot delivers (services-assisted)

**The brief's outputs, mapped to what exists today:**

| output | how it is produced | exists today? |
|---|---|---|
| assurance analysis | `csia-assure` per log: first page, machine report | **yes** |
| coverage map | `coverage_states.json` per log, plus a fleet summary table of classes per record | per log yes; the fleet table is a services step |
| evidence-lineage map | the lineage groups and independent lines per conclusion (`receipts.json`) | **yes**, at topic-channel level. Hardware-level lineage needs the customer's wiring map (section 5) |
| ambiguous / fault events | WHAT HAPPENED, UNCONFIRMED lines, remaining causes, resolving measurements | **yes** |
| configuration-transition findings | the CONFIGURATION section (EKF2 aiding, resets, sensor selection) | **yes** |
| engineering report | written by the CSIA engineer from the outputs and a review session | services |
| integration recommendations | the logging and instrumentation changes the coverage and support outputs point to (e.g. ESC current, battery current, `esc_status` rate margin, `failure_detector_status` rate) | services, from the outputs |

**Phases (a proposed structure; durations are the owner's decision):**
1. **Support screen** of every log supplied: SUPPORTED / PARTIAL /
   UNSUPPORTED with reasons, logging-rate margins, gyro bias at rest,
   dropouts. **Deliverable:** a coverage and instrumentation note.
2. **Assurance analysis** of the supported logs.
3. **Blind comparison against the customer's own truth,** where the customer
   has it. The customer gives their incident findings or injected-fault
   records **after** the analysis is delivered, so the comparison cannot be
   fitted.
4. **Review session and report:**
   - findings;
   - each ambiguous event with the measurement that would resolve it;
   - every disagreement between CSIA and the customer's truth, stated as
     such;
   - integration recommendations.

## 3. What the customer is told before signing

- **Validated in PX4 SITL on one quad X airframe** (PX4 547e2ca). **Not yet
  validated on real propulsion faults.** Real logs are read and their
  missing evidence is stated. No real propulsion conclusion has been
  checked against truth.
- **Losses during continuous maneuvering are reported as unconfirmed, not
  diagnosed** (Track C).
- **The tool prefers AMBIGUOUS** to a single cause when the log does not
  separate them. A pilot will produce AMBIGUOUS answers.
- **No probability is reported.**

**This is why the pilot is also the first real-data validation:** each
customer log analysed blind and checked against the customer's truth is
exactly the real evidence PRIME Track B lacks. Use of the logs, or of
statistics derived from them, for calibration needs the customer's written
permission. A customer may refuse it and still receive their report.

## 4. Inputs and responsibilities

| the customer provides | CSIA provides |
|---|---|
| ULogs (SITL, HIL, flight test, incident), any number; the airframe and PX4 version | the installable analyzer (wheel), or a services run on CSIA's side |
| their truth for any log where they have it, held back until after analysis | the analysis, the blind comparison, the review, the report |
| a wiring/topology note (which ESC feeds which telemetry, power distribution), if hardware-level lineage is wanted | a data-handling agreement: logs stay confidential; deletion on request |
| an engineer for the review session | a written statement of the version and support matrix used |

**Both modes are offered:** the customer runs the wheel on their own
machines (logs never leave), or CSIA runs it.

## 5. Exit criteria (fixed per pilot before analysis)

**The pilot is a success for the customer if** their engineers judge,
against their own truth, that the outputs:
- named nothing wrongly: **no wrong attribution** (the hard criterion);
- caught at least one evidence problem, dependency or missing measurement
  they had not recorded;
- shortened or clarified their log review, by the measures in section 6.

**The pilot fails** if CSIA makes a wrong attribution that a reader would
act on, or adds nothing beyond what their monitors already said (the
brief's stop condition 9). **Failure is reported to the customer as
plainly as success.**

## 6. E4: value metrics, gathered from pilots only

**No number is claimed here.** Each metric has a measurement method and a
baseline taken in the same pilot. A metric without a baseline is not
reported.

| metric | how it is measured in a pilot | baseline |
|---|---|---|
| fault-analysis time | minutes from log to a written answer, on matched logs, for the customer's engineers with and without the outputs (a light form of the E2 protocol) | the same engineers' current process |
| logs triaged | logs screened per engineer-hour, and the split SUPPORTED / PARTIAL / UNSUPPORTED | logs reviewed per engineer-hour today |
| invalid evidence caught | refusals in the receipts that the customer's engineers agree were right (each one listed) | refusals they had already made themselves |
| false certainty prevented | conclusions the customer had drawn, or would have drawn, that the receipts show to be unsupported (each one listed, customer-confirmed) | — (a case count, not a rate) |
| dependencies exposed | alarms the team had counted as independent that share a source | the team's own count before reading |
| missing instrumentation identified | recommendations made, and how many the team adopts | — |
| reproducibility | two engineers reaching the same answer from the receipts | two engineers from their own notes |
| **wrong attribution by CSIA** | count against the customer's truth | **must be zero; every one is reported** |

**Commercial value is then stated in the customer's own terms** (hours,
logs, re-flights avoided if they record them), from their data, with their
permission.

## 7. Pricing

**Not set here; an owner decision.** A structure that fits a
services-assisted pilot:
- a fixed fee for a bounded number of logs and one review;
- credited against a later licence.

**No price, discount or ROI figure is stated in any pilot material until
pilot data supports it.**
