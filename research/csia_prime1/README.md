# CSIA PRIME-1: Pilot Launch + Product Hardening

**2026-10-03. Not a research phase.** It fixed known product defects,
hardened event discovery, preserved every historical result, made the
external pilot usable, and prepared for blind real-customer data. It stops
where real propulsion data is required.

**Boundary:**
- **OFFBOARD;**
- **ZERO CONTROL authority;**
- **NO FORGE;**
- no onboard component, no H743 port, no flight-safety approval.

**Decision: CSIA_PRIME1_READY_FOR_EXTERNAL_PILOT. PHYSICAL VALIDATION
REMAINS OPEN** (`PRIME1_REVIEW_AND_DECISION.md`).

## The result in seven lines

1. **D-PRIME-1 and D-PRIME-2 are fixed in a versioned successor release,
   `prime1`.**
   - An integer-microsecond timebase.
   - Separate RPM_DEFICIT and RPM_EXCESS events, not an absolute value.
   - A telemetry baseline-validity condition.

   Release `2.3` still reproduces both defects exactly as recorded.
2. **No historical result changed:** XSYS, Phase C, 2.2, 2.3, RB-001 and
   PRIME reproduce (`FINAL_STATE_PRIME1.json`).
3. **Event discovery was promoted by a frozen, prospective, held-out
   comparison** on 14 new SITL flights. Against 2.3:
   - 1 nominal event (PX4's own magnetometer timeout; 0 propulsion events)
     against 92;
   - 6 of 6 faults found against 5;
   - 0 false symptoms and 0 wrong attribution.

   **EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY.**
4. **Support is decided before interpretation.** UNSUPPORTED_VEHICLE_CONFIGURATION
   and UNSUPPORTED_SCHEMA withhold every diagnosis. The support matrix is a
   machine-readable product contract; nothing in it is PHYSICAL_VALIDATED.
5. **A third defect, D-PRIME-3, was found and fixed.** The wheel never
   carried `stock_calibration.json`, so an installed `csia-assure` crashed on
   every analysable log; PRIME's bundle is affected. The shipped wheel now
   installs fresh and reproduces the repository's outputs byte for byte.
6. **The pilot is usable.**
   - A blinded bundle with ZERO KNOWN GROUND-TRUTH LEAKS.
   - The offer, intake, blind protocol, metrics and value classification.
   - A local engagement workflow: hash, run once, seal, reveal, verify.
   - A real log can be handled tomorrow without code.
7. **Physical validation is open.** Every diagnostic claim is
   simulation-only, and says so.

## Documents

| document | phases | what |
|---|---|---|
| `DEFECT_FIXES.md` | 2-7 | the versioned fixes, the release table, the tests |
| `KNOWN_DEFECT_REGISTER.md` | 31 | D-PRIME-1, D-PRIME-2, D-PRIME-3 and open items, never erased |
| `HELDOUT_PREREGISTRATION.md` | 10-11 | the comparison, frozen before the held-out flights |
| `EVENT_DISCOVERY_PRIME1.md` | 6-12 | the front end, the telemetry matrix, false-positive control, the held-out results |
| `SUPPORT_MATRIX.md` | 13-15 | rendered from `support_contract_prime1.json` |
| `CLAIM_EVIDENCE_MATRIX_PRIME1.md` | 18 | every claim, its artifact, dataset, version, result, limitation, validation level |
| `PUBLIC_CLAIMS.md` | 34 | SUPPORTED NOW / SIMULATION ONLY / UNDER PHYSICAL VALIDATION / DO NOT CLAIM |
| `PILOT_OFFER.md` | 21, 26 | the CSIA Flight Assurance Pilot; pricing a hypothesis |
| `PILOT_INTAKE_AND_PROTOCOL.md` | 22-23 | intake fields and the blind protocol |
| `PILOT_METRICS.md` | 24 | what the pilot measures |
| `VALUE_CLASSIFICATION.md` | 25 | each output: unique, aggregation, reformatted, misleading or no value |
| `DIFFERENTIATION.md` | 33 | product differentiation, without claims of firstness |
| `PRODUCT_READINESS.md` | 27-29, 37-39 | install, performance, engagement workflow, REAL_DATA_READY_CHECK |
| `PRIME1_REVIEW_AND_DECISION.md` | 40 | gates P1-P5, the 21 answers, the token |
| `pilot_package/` | 19 | participant documents (quick start, report guide, limitations, instructions, questions, feedback) |
| `pilot_package_experimenter/` | 19 | the scoring rubric (never given to a participant) |
| `sample_reports_prime1/` | 26 | the product's output on 8 sanitized logs, REAL or SITL labelled |
| `FAILURE_LEDGER_DRAFTS.yaml` | 32 | FL-053 to FL-057, proposed only; the ledger is unchanged |

## Reproducing

```
.venv/bin/python research/csia_prime1/verify_prime1_baseline.py --final   # history, defects, gates
.venv/bin/python research/csia_prime1/historical_gate.py                  # release 2.3 unchanged
.venv/bin/python research/csia_prime1/sample_reports_prime1.py
.venv/bin/python research/csia_prime1/build_pilot_bundle_prime1.py        # bundle + blindness audit
.venv/bin/python research/csia_prime1/fresh_install_prime1.py
.venv/bin/python research/csia_prime1/real_data_ready_check.py
.venv/bin/python research/csia_prime1/perf_prime1.py
.venv/bin/python -m pytest -q tests/test_csia_prime1.py tests/test_csia_prime1_docs.py
```

**The held-out evaluation is not re-runnable by design:** `heldout_eval.py`
refuses once `HELDOUT_RESULTS.json` exists.

**Historical outputs** are produced by `analyze`, by `assure --release prime`,
and by any function's default release (`2.3`). `assure` and `csia-assure`
default to `prime1`.

**Raw data is outside git** (`/home/user/prime1_raw`):
- the held-out ULogs;
- the participant bundle;
- the experimenter's ground truth.

Customer logs are git-ignored (`engagements/`, `customer_data/`, `*.ulg`).
