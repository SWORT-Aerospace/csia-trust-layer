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

## D-PRIME-3: the participant wheel could not analyse a log (found in PRIME-1 Phase 39)

| field | D-PRIME-3 |
|---|---|
| original defect | `pyproject.toml` never listed `csia_evidence_assurance/stock_calibration.json` as package data. Every wheel built from the repository omitted it. An installed `csia-assure` crashed (FileNotFoundError) on every SUPPORTED or PARTIAL log; only withheld logs (boat, VTOL) completed |
| found | PRIME-1 Phase 39: a fresh virtual environment, the wheel installed from file, `csia-assure` run outside the repository (`fresh_install_prime1.py`), 2026-10-03 |
| minimal reproduction | install the wheel from PRIME's participant bundle (`install/csia_trust_layer-0.8.0-py3-none-any.whl`) in a new venv; run `csia-assure` on any SITL sample log |
| affected versions | every wheel of the analyzer, including the one inside PRIME's participant bundle. Repository runs (`.venv`, editable install) were never affected |
| why PRIME's install check missed it | `prime_a_gate.py --install` installed from the source directory (`pip install <repo>[logs]`), not from the wheel shipped in the bundle. That check passed and is recorded as it was |
| fixed version | PRIME-1 (`pyproject.toml`: `"*.json"` and `"contracts/*.json"` for the package) |
| historical impact | none on any analysis result. **PRIME's participant bundle is unusable as shipped** and must not be given to anyone; it stays as recorded |
| regression tests | `tests/test_csia_prime1.py::test_every_runtime_data_file_of_the_product_is_packaged`; `FRESH_INSTALL_PRIME1.json` (the wheel itself, installed, outputs byte-identical to the repository's) |
| public relevance | none outside the pilot. It is the reason the pilot gate now tests the shipped artifact, not the source tree |

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
