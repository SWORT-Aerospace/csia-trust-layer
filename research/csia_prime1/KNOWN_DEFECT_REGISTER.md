# Known defect register (PRIME-1 Phase 31)

**2026-10-03. Part of the product's engineering provenance. Fixed defects are
recorded here, never erased.**

| field | D-PRIME-1 | D-PRIME-2 |
|---|---|---|
| original defect | the stock adapter rounded content times to the microsecond, the event anchor was not rounded, and the 2.2 gate compared floats with a 1 ns tolerance. A sub-microsecond representation difference rejected valid evidence (REGIME_INVALID) and changed the conclusion | the telemetry CUSUM was one-sided (deficit only), so an RPM excess opened no event. A late event compared a corrupted BEFORE window with a corrupted AFTER window and read NOMINAL |
| found | PRIME stress envelope v1 (off-grid jitter), 2026-10-02 | PRIME pilot-bundle blinding (removing PX4's simulation-only injection message from 2.3 V10), 2026-10-03 |
| minimal reproduction | `synthetic_stock.synth("motor")`, every timestamp + 0.7 us: `COMMAND_NO_RESPONSE|motor_0` lost, 13 rejected (`research/csia_prime1/reproductions.py`) | `synthetic_stock.synth("telemetry", motor=2, eta=100)`: no event at all. 2.3 V10 without the injection message: "nothing adverse was observed" |
| affected versions | stock bridge 2.3 (release `2.3`): `analyze`, PRIME's `assure` (now `assure --release prime`) | the same |
| real-log exposure | none known: ULog times are whole microseconds and the stock path never produces off-grid anchors from a ULog. Reachable from synthetic, resampled or nanosecond-clock inputs | **yes:** any real ESC telemetry corruption that raises the reported RPM |
| fixed version | release `prime1` (`assure` default, `csia-assure`) | release `prime1` |
| fix | canonical integer-microsecond timebase on ingestion; integer-tick comparisons at the declared resolution in the gate; per-producer clock resolution | RPM_DEFICIT_EVENT and RPM_EXCESS_EVENT as separate one-sided arms; telemetry baseline-validity condition (TELEMETRY_BASELINE_INCONSISTENT); reference-consistency gating; ESC_OFFLINE_EVENT; test-harness messages ignored |
| historical impact | none: release `2.3` unchanged | none: release `2.3` unchanged |
| historical conclusions changed? | **no** (`HISTORICAL_GATE.json`) | **no.** 2.3 V10's recorded result is true of the log as flown, with the simulation-only message |
| regression tests | `tests/test_csia_prime1.py`: the gate tests (boundaries, ticks, nanosecond and coarse clocks, negative windows, anchors, ordering, staleness) and end-to-end shifts; the 2.3 behaviour pinned as an ordinary test; PRIME's strict expected-fail kept for the historical path | `tests/test_csia_prime1.py`: deficit and excess semantics, the late-event condition, no `abs()`, the injection-message invariance; the 2.3 behaviour pinned; PRIME's strict expected-fail kept for the historical path |
| public relevance | low: a robustness property. Worth stating only as "timestamps are compared at their recorded resolution" | **high:** "reports RPM telemetry corruption" was only true for shortfalls before PRIME-1. The claim matrix now separates shortfall, excess, offline, dropout and stuck |

## Other product findings closed in PRIME-1 (not code defects)

| finding | where found | fixed in | how |
|---|---|---|---|
| a real boat log was analysed with the quadrotor profile and the report never said the vehicle was out of scope (PRIME RR-09) | PRIME real-data acquisition | `prime1` (and PRIME's view) | `support_prime1`: UNSUPPORTED_VEHICLE_CONFIGURATION decided before interpretation; generic analysis only |
| maneuvering raised hundreds of false candidate events per hour (PRIME C3) | PRIME C3 | `prime1` (promotion depends on the held-out evaluation) | steadiness- and heading-gated compensation alarms; identical-condition merge |
| SITL sample logs leaked their ground truth (SIH parameter changes, injection messages) | PRIME pilot bundle | PRIME-1 bundle builder | removed and audited (`BLINDNESS_AUDIT.json`) |

## Open items (not fixed; recorded)

| item | effect | where recorded |
|---|---|---|
| a compensation change between two steady holds at different headings is not an event, but the compensation EVIDENCE is not yet refused for a heading change | an event opened by another trigger at such a moment could admit it | support contract `known_blind_spots`; candidate validity condition for real-data review |
| a static telemetry offset, a slow drift, or a stuck value in steady hover are not discovered as changes | a gross static inconsistency is stated as a coverage notice; smaller ones are not | telemetry matrix; support contract `telemetry_classes` |
| every threshold is SITL-calibrated | real vehicles need their own nominal calibration | support contract; PRIME B5 |
| the telemetry level band (2) and the heading tolerance (15 degrees) are declared, not calibrated | they could be wrong for a real vehicle | `releases.py`, `events.py`, held-out preregistration |
