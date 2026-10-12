# The engineering report: summary, magnitudes, coverage, diagnosability (Phases 21-24)

**2026-10-02.** **Code:** `csia_evidence_assurance/stock_report.py`
(schema 4), `runs.stock_flight`, `diagnosability.py`. Examples:
`reports/V*/report.txt` (validation flights, the product's own output).

## 1. Schema 4, and what it leaves alone

Schema 4 = schema 3 plus five sections, built ONLY for stock runs (when
`runs.stock_flight` hands the report its extras):

| section | phase | content |
|---|---|---|
| `summary` | 21 | the engineer's questions, answered first |
| `events`, `evidence_values` | 12, 22 | the discovered events with every trigger; every stock output with value, unit, threshold, window, sample count and producer health |
| `coverage_report` | 23 | profile records expected against observed, each unobserved one with its operational meaning; producers; topics absent; fields that never vary |
| `diagnosability` | 24 | which explanations the available evidence could ever eliminate, and which record is missing for the rest |

Every earlier report is byte-identical. The pinned pilot reports and the
66-flight 2.2 batch reproduce (`BASELINE_2_3.json`, `FINAL_STATE_2_3.json`).

## 2. The summary comes first (Phase 21)

The human report opens with the brief's questions, in this order:

1. WHAT HAPPENED?
2. WHEN?
3. WHAT DID CSIA OBSERVE? (adverse outputs, with magnitudes)
4. WHAT COULD CSIA NOT OBSERVE?
5. WHAT EXPLANATIONS REMAIN?
6. WHAT WAS ELIMINATED, AND WHY?
7. WHICH MONITORS AGREED?
8. WERE THEY INDEPENDENT?
9. WHAT WOULD RESOLVE THE REMAINING AMBIGUITY?
10. IS ATTRIBUTION JUSTIFIED?

**The summary computes nothing new.** It reads the other sections and
2.1.1's result:
- it never upgrades a verdict;
- it never names a cause 2.1.1 did not reach;
- "IS ATTRIBUTION JUSTIFIED?" is "yes" only for a UNIQUE attribution.

The detail follows: events with their triggers, every evidence value, the
coverage, the diagnosability. The full 2.2 timeline and trace stay in
`report.json`.

**Example (V1, motor_1 at eta = 0.6, an ordinary log):**
- **What happened.** One event at 49.20 s (compensation and telemetry
  change on motors 0 and 1). COMMAND_NO_RESPONSE on motor_1, AMBIGUOUS
  among 4 explanations.
- **Observed:**
  - motor_1 compensation 0.6617 (threshold 0.00688; 1/eta - 1 = 0.667 for
    a compensated loss to 0.6);
  - motor_1 telemetry deficit 0.3991 (the injected 0.4).
- **Eliminated.** SENSOR/response_sensor, by PHYSICAL_RESPONSE_NOMINAL_FALSE
  (the compensation, 0.6617).
- **Independence.** 2 adverse outputs in 1 lineage group: both read the
  four motor commands, so they are one line of evidence, not two.
- **What would resolve it:**
  - ESC current would eliminate drive_no_current and test the stall
    (mechanical);
  - a measured battery current would eliminate path_unavailable;
  - nothing in a stock log can show that the command reached the ESC
    (command_not_delivered).
- **Attribution: no.** AMBIGUOUS (ACTUATION/motor_1).

## 3. Magnitudes (Phase 22)

**What each value carries.** Every value in the report has:
- its unit;
- its threshold;
- its window;
- the samples it rests on;
- its producer health (`evidence_values`).

**Where the meaning is stated:**
- **The compensation unit** says what a genuine loss gives: "compensation
  ratio change (1/eta - 1 for a compensated loss)".
- **The telemetry deficit** is a fraction of commanded thrust implied by
  the reported RPM.
- **The rate transient** is in rad/s.

**No confidence number is invented.** The thresholds are 2 x the largest
null value. A value 96 times its threshold (V1) is reported as exactly
that, never as "96 % confident". The report carries no probability, because
none was estimated.

## 4. Coverage, per flight (Phase 23)

The coverage section is more than a count ("4 of 29"). It lists each
unobserved profile record with what it would have told the engineer.

| unobserved record | meaning in the report |
|---|---|
| `actuation.command_path` | whether each motor's ESC received its command (no stock topic shows delivery; `actuator_outputs` is only what the FMU computed) |
| `actuation.electrical_response` | motor current per command (ESC current absent or zero) |
| `actuation.mechanical_response` | the stall check: current with no rotor speed (needs ESC current) |
| `power.source_health` | battery voltage and current both present (v2: current must be measured) |
| `power.droop_vs_current` | voltage sag under load (needs measured current) |
| `compute.*` | process liveness, output and deadlines (no stock topic) |
| `compute.resource_headroom` | CPU headroom (cpuload exists, but nothing pairs it with a deadline; in SITL it measures the host) |

**The section also lists:**
- coverage notices, by producer;
- topics absent from the log;
- per topic, the fields that never vary.

In SIH those are ESC current and voltage, which are all zero. **The header
line says: "unobserved is not healthy".**

## 5. Diagnosability (Phase 24)

**The method.** It is the fault-signature (isolability) analysis of
structural diagnosis, computed on 2.1.1's OWN symptom specifications and
predicate table. Both are read and never changed (a test checks this).
It is not a CSIA-specific diagnosability method.

**How it works.** A probe index holds only the records this log's
producers can emit, with the profile's declarations, once all NOMINAL
and once all adverse. Then:
- a symptom is raisable if its detector fires on the adverse probe;
- a hypothesis is eliminable if one of its refuting predicates evaluates
  on either probe.

For each predicate that cannot be evaluated, the probe finds the single
catalog records whose addition makes it evaluable. That is the "what would
resolve it" line.

**The SIH stock floor** for COMMAND_NO_RESPONSE on any motor is
{drive_no_current, command_not_delivered, path_unavailable}. No analysis
of a SIH stock log can be more specific than that.

With ESC current and a measured battery current, the floor shrinks to
{command_not_delivered}. That is a statement about which log would be
needed, not a claim about any flight.
