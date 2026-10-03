# Website and sales claims (PRIME-1 Phase 34)

**2026-10-03. The only wording SWORT may use in public about CSIA Flight
Assurance PRIME-1.** Each claim is a row of `CLAIM_EVIDENCE_MATRIX_PRIME1.md`,
quoted with its qualifiers. A sentence that is not here is not published.

**Product boundary, in every public text:**
- **OFFBOARD:** it analyses logs after the flight;
- **ZERO CONTROL authority:** it commands nothing and recovers nothing;
- **NO FORGE:** no onboard component;
- it gives no flight-safety approval.

## 1. SUPPORTED NOW

**Properties of the software, true for any PX4 ULog it reads.**

| claim (exact wording) | evidence |
|---|---|
| "One command analyses an ordinary PX4 ULog after the flight. You give it only the log: no onset time, labels or configuration files." | M-P1 |
| "The same log and the same version always give byte-identical outputs." | M-P2 |
| "Before interpreting anything, it decides whether the log is inside its supported scope, and says so. A vehicle outside its profiles gets no diagnosis, only a version, integrity and warnings summary." | M-P6 |
| "Evidence that was not observed is never reported as healthy. Every page states how many records it could not judge." | M-P3 |
| "No probability or confidence percentage is reported. Conclusions carry plain states: UNIQUE, AMBIGUOUS, SUPPORTED, NO_EVIDENCE." | M-P4 |
| "Every conclusion carries a receipt: the evidence for and against it, the evidence refused and why, its sources, the versions and the coverage." | M-P5 |
| "Corroboration is counted by independent source, not by how many monitors fired." | M-P7 |
| "Your logs stay with you: it runs locally, needs no network and no account, and its blind-engagement workflow hashes and seals every run before your diagnosis is revealed." | M-P8, M-P9 |

## 2. SIMULATION ONLY

**Each sentence must keep the words "in PX4 simulation".** None of these has
been checked against a real propulsion fault.

| claim (exact wording) | evidence |
|---|---|
| "In PX4 simulation, a motor's loss of effect in hover or a hold was attributed to the right motor, with the remaining causes listed." | M-S1 |
| "In PX4 simulation, ESC telemetry that reported less rotor speed than commanded (shortfall) and more (excess) were both found and reported as telemetry observations, never as a motor failure." | M-T1, M-T2 |
| "In PX4 simulation, an ESC reporting itself offline was stated as missing telemetry, never read as a loss or as health." | M-T5 |
| "In PX4 simulation, a telemetry corruption with the same RPM symptom as a real motor loss was not reported as a motor failure." | M-T6 |
| "In PX4 simulation, losses during continuous maneuvering are reported as found but unconfirmed, with the reason, rather than attributed." | M-S4 |
| "In PX4 simulation, on 14 new flights analysed blind, its event discovery found every injected propulsion and telemetry fault at onset and raised no propulsion event on about 18 minutes of nominal flight, including maneuvering, wind and a sensor reconfiguration." | M-E1 |

## 3. UNDER PHYSICAL VALIDATION

**May be said only as plans, with the word "planned" or "being tested".**

| statement (exact wording) | what is missing |
|---|---|
| "We are testing whether the separation of motor faults from telemetry faults holds on real propulsion hardware (a bench A/B test is designed)." | the bench and the matched A/B run (PRIME `B4_MATCHED_AB_PROTOCOL.md`) |
| "We are running blind pilots on flight-test teams' own logs, with their diagnosis sealed until our analysis is sealed." | a first pilot customer |
| "Thresholds for a customer's vehicle are being set from that vehicle's own nominal flights." | real nominal logs from a customer |

## 4. DO NOT CLAIM

| claim | why not |
|---|---|
| "Validated on real flights", "works on real propulsion faults", anything PHYSICAL_VALIDATED | no real propulsion event has been analysed against truth |
| "Detects motor failures", "AI diagnostics", "predictive maintenance" | crowded categories, and not the value shown |
| "Reduces analysis time", any ROI, any saving | no user study and no pilot has been run |
| "Low false-alarm rate" without "in PX4 simulation" and the measured hours | the held-out nominal set is a fraction of an hour of SITL |
| "Generic PX4 support", "works with any drone" | quad X only; other vehicles are refused by design |
| "Detects stuck, drifting or offset RPM telemetry" | not discovered as a change (telemetry matrix blind spots) |
| "Diagnoses maneuvering faults" | maneuvering losses are found but not confirmed |
| "First", "only", "unique in the market", or any comparison naming a competitor | not established against each product's documentation |
| "Patented", "patent pending" | nothing filed |
| "Certified", "safety approved", "flight-critical" | offboard analysis only; no certification exists |
