# CSIA PRIME: Commercial Reality & Differentiation Program

**2026-10-03. NON-CONFIRMATORY except where a document says preregistered.**

**Boundary:**
- **OFFBOARD;**
- **ZERO CONTROL authority;**
- **NO FORGE;**
- no onboard component, no automatic recovery, no flight-critical
  authority.

**New work is additive.** Frozen v2.0, Semantic Core 2.1.1, Phase C,
XSYS-001/A1/A2 and the 2.2, 2.3 and RB-001 results are unchanged
(`FINAL_STATE_PRIME.json`).

**The program's two aims:**
1. a product a flight-test or autonomy engineer would pay for (CSIA Flight
   Assurance);
2. the strongest defensible evidence of what makes CSIA different from
   aggregating ordinary monitors.

**Decision: `CSIA_PRIME_BLOCKED_ON_REAL_DATA`** (`PRIME_REVIEW_AND_DECISION.md`).

## The result in six lines

1. **The commercial MVP exists** (PRIME-A met):
   - `csia-assure flight.ulg` writes a first page answering the engineer's
     questions in order;
   - receipts per conclusion;
   - eight coverage classes that never become "healthy" by default;
   - a support check against a machine-readable support matrix.
2. **The pilot package exists** (PRIME-E met as defined):
   - a wheel and 12 blinded sample logs;
   - the participant documents;
   - a frozen scoring rubric and a crossover protocol.

   **It has not been run with anyone.**
3. **Reality is still missing.** No real propulsion log, bench or HIL was
   reachable, so PRIME-B, C and D are blocked, not failed.
4. **In SITL, the differentiator holds for deficits.** A telemetry
   corruption matched to a motor loss's RPM symptom was never read as a
   motor failure: 0 confusions in 1,056 perturbed runs and in the demo. The
   product raised no UNIQUE and no false symptom in any PRIME run. B3, a
   candidate outside the product, did raise false losses under noise and CG
   steps.
5. **Two defects found, reproduced, reported, not patched** (stop condition
   2):
   - **D-PRIME-1:** sub-microsecond time breaks the event window. Not a
     ULog condition;
   - **D-PRIME-2:** an ESC telemetry excess is never discovered. 2.3's V10
     relied on PX4's simulation-only injection message.
6. **Product boundary:** option D, a services-assisted pilot with the
   Analyzer. The highest-value next action is one such pilot on a team's
   real flight-test logs, with their truth held back.

## Documents

| document | track | what |
|---|---|---|
| `PRIME_EXECUTION_PLAN.md` | 0 | the repository's actual state, the plan in priority order, gates |
| `REAL_DATA_ACQUISITION.md` | B1 | every real-data route tried; what was found |
| `STRESS_ENVELOPE.md` | B2 | the operating envelope per variable (SITL bases, offline perturbation) |
| `B4_MATCHED_AB_PROTOCOL.md` | B3-B5 | the minimum bench, the matched physical A/B, frozen before evaluation |
| `SIM_TO_REAL_RECEIPTS.md` | B6 | RR-09 to RR-12 and two updated RB-001 receipts |
| `DEFECT_D_PRIME_1.md` | B (stop 2) | off-grid time rejects valid evidence |
| `B3_CHALLENGE.md` | C2 | B3 against model mismatch; predicted REQUIRES_VALIDITY_CONDITION |
| `EVENT_DISCOVERY_PREREG.md`, `EVENT_DISCOVERY_STUDY.md` | C3-C4 | mature event-discovery methods compared; alert-burden target |
| `TRACK_A_MVP.md` | A1-A6 | the commercial MVP and gate PRIME-A |
| `COMPETITOR_FUNCTION_MATRIX.md` | D1 | what established categories already provide |
| `DEFENSIBILITY_AND_IP.md` | D2-D3 | the narrowest defensible claim; IP screen (no patent drafted) |
| `TECHNICAL_DEMO.md` | D4 | one RPM symptom, two truths |
| `EXTERNAL_PILOT_PACKAGE.md` | E1-E2 | the bundle, blinding, the engineering task test protocol |
| `COMMERCIAL_PILOT.md` | E3-E4 | the "CSIA Flight Assurance Pilot"; value metrics without numbers |
| `DEFECT_D_PRIME_2.md` | E (stop 2) | a telemetry excess is never discovered |
| `CLAIM_EVIDENCE_MATRIX.md` | all | every public claim, its evidence, and whether it is public-safe |
| `PRIME_REVIEW_AND_DECISION.md` | all | gates, stop conditions, the twenty answers, the boundary decision, the token |
| `pilot_package/` | E1 | participant documents (quick start, report guide, questions, feedback form) |
| `pilot_package_experimenter/` | E2 | the frozen scoring rubric (never given to a participant) |

## Reproducing

**Raw logs are outside git:**
- 2.3's flights: `/home/user/csia_2_3_raw/validation`;
- RB-001's flights and the pyulog logs: `/home/user/rb001_raw`;
- the pilot's S1 run: `/home/user/csia_2_2_pilot_raw`;
- the PX4 docs boat log: in the PX4 checkout at 547e2ca.

**Their SHA-256 values are in the JSON outputs.**

```
.venv/bin/python research/csia_prime/verify_prime_baseline.py [--final]
.venv/bin/python research/csia_prime/real_logs.py
.venv/bin/python research/csia_prime/stress_envelope.py && .venv/bin/python research/csia_prime/envelope_table.py
.venv/bin/python research/csia_prime/b3_challenge.py
.venv/bin/python research/csia_prime/event_discovery.py --stage cal|dev|eval|real   # eval was run once
.venv/bin/python research/csia_prime/sample_reports.py
.venv/bin/python research/csia_prime/prime_a_gate.py [--install]
.venv/bin/python research/csia_prime/demo_ab.py
.venv/bin/python research/csia_prime/build_pilot_bundle.py   # writes the bundle outside git
.venv/bin/python -m pytest -q tests/test_csia_prime.py
```

**The product command:** `csia-assure flight.ulg --out DIR` (or
`python -m csia_evidence_assurance assure ...`). `analyze` is unchanged.
