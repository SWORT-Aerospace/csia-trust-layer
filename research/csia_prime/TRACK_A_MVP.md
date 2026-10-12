# Track A: the commercial MVP (PRIME A1-A6, gate PRIME-A)

**2026-10-02. OFFBOARD, ZERO CONTROL authority, NO FORGE.**

## 1. What an engineer runs

```
pip install .[logs]              # from this repository
csia-assure flight.ulg --out DIR # or: python -m csia_evidence_assurance assure flight.ulg --out DIR
```

**What the user does not provide:**
- no onset;
- no sidecar;
- no label;
- no hypothesis id;
- no Python.

**`DIR` receives eight files:**

| file | what |
|---|---|
| `assurance_summary.txt` | **the first page** (A1): the engineer's questions answered in order |
| `receipts.json` | one receipt per conclusion (A3) |
| `coverage_states.json` | every profile record × producer in one of eight coverage classes (A4) |
| `support.json` | whether this log is inside the support matrix, and why not (A5) |
| `alerts.json` | events grouped; a re-raised identical PX4 condition becomes one alert |
| `report.json`, `report.txt`, `manifest.json` | **exactly** what `analyze` writes, byte for byte (tested) |

**Why each addition is allowed** (the reality-first rule):

| addition | justified by |
|---|---|
| summary, receipts, coverage states | a required commercial workflow (A1, A3, A4). Measured gap: the report had no "evidence rejected, and why" in its summary and no per-conclusion receipt |
| support check | **a measured usability gap on real data:** a real FMUv5 boat was analysed as a quadrotor without saying so (RR-09) |
| alert grouping | **measured on real data:** one persistent low-battery condition became 9 events (RR-10) |
| `csia-assure` | a required commercial workflow (installable one-command analyzer) |

**Nothing in Semantic Core 2.1.1 or the 2.2 evidence model changed.** The
view reads the machine report and adds no semantics. Every historical
report regenerates byte for byte (`verify_prime_baseline.py`).

## 2. A1, the first page

**The questions, in order (tested):**
1. what happened;
2. when it started;
3. which subsystem;
4. what causes remain possible;
5. what was eliminated, and why;
6. what evidence supports it;
7. **what evidence was rejected, and why** (new, with plain-language
   reasons);
8. which monitors share a source;
9. what was not observable;
10. what would resolve the ambiguity.

**Then:** what changed in the configuration (EKF2 aiding, resets, sensor
selection; start-up changes summarised in one line), and the grouped
alerts.

**Unconfirmed observations are named as such,** ranked by size against
their threshold, with why they were not confirmed. Example, 2.3 V13:
"UNCONFIRMED: motor_2 ESC telemetry DEGRADED 0.3989 … its physical
confirmation was refused (NOT_STEADY_FLIGHT: vehicle maneuvering…)".

## 3. A2, confidence discipline

**No percentage, probability or confidence figure.** The states are
UNIQUE, AMBIGUOUS, SUPPORTED, NO_CONSISTENT, NO_EVIDENCE and
UNCONFIRMED. The same text test that guards the 2.2 report guards the
summary.

## 4. A3, receipts

**Each symptom receipt carries:**
- the conclusion and its semantic state;
- supporting, refuting and rejected evidence, each with value, unit,
  threshold, window, content time and producer health;
- the rejection reasons;
- the source lineage (roots per evidence, lineage groups, independent
  lines);
- the producers' health;
- the configuration (changes; evidence not admitted by epoch);
- the profile, semantic, analyzer and view versions;
- what is still possible, and what would resolve it.

**Also:** one attribution receipt, and one "unconfirmed" receipt per
adverse output that no symptom reads.

## 5. A4, coverage classes

**The classes:** OBSERVED, NO_ANOMALY, NO_COVERAGE, UNAVAILABLE, STALE,
FAULTED, NOT_APPLICABLE and UNKNOWN. Each is mapped strictly from the
report's per-tick states (`assurance_view.py`).

**Permanent tests:**
- nothing unavailable, stale, faulted, unknown or uncovered becomes
  NO_ANOMALY;
- a NO_ANOMALY with gaps is marked `partial`.

## 6. A5, the support matrix

**`csia_evidence_assurance/support_matrix.json`** (machine-readable;
shipped with the package). Every entry names its evidence. In short:

| | |
|---|---|
| supported vehicle | multirotor quad X (vehicle_type rotary wing, CA_ROTOR_COUNT 4, not VTOL), profile multirotor-quad r1 |
| unsupported | rover/boat, fixed wing, VTOL, other rotor counts, ArduPilot logs |
| PX4 | full analysis tested on 547e2ca (SITL); 1.6 to 1.14-era real and SITL logs: no crash, coverage stated. Propulsion evidence needs control allocation and ESC RPM telemetry; pre-allocation PX4 (RflyMAD's real flights) is PARTIAL |
| logging | gaps above 3 × the 547e2ca default interval refuse evidence; propulsion topics at ≥ 5 Hz keep every confirmation in the stress envelope |
| checked per log | gyro bias at rest < 0.05 rad/s; logger dropouts; topic gaps; estimator schema |
| diagnosable (SITL only) | motor loss in hover or a hold (right motor, AMBIGUOUS among 4); telemetry corruption kept as context; GPS and battery faults kept out of propulsion |
| partial | losses during continuous maneuvering (not confirmed); maneuvering's dismissed events |
| not diagnosable | compute/timing faults, command delivery, ESC current faults without ESC current, power path without battery current, propeller damage, **anything on real hardware (no real propulsion validation yet)** |

## 7. A6, representative reports (`sample_reports/`, `SAMPLE_REPORTS.json`)

| case | log | data | support | summary lines |
|---|---|---|---|---|
| nominal | RB-001 CAL1 | SITL | SUPPORTED | 35 |
| motor degradation | 2.3 V1 | SITL | SUPPORTED | 45 |
| telemetry corruption | 2.3 V10 | SITL | SUPPORTED | 43 |
| sensor loss (ESC telemetry offline) | 2.3 V9 | SITL | SUPPORTED | 36 |
| GPS loss | 2.3 V7 | SITL | SUPPORTED | 45 |
| configuration change (magnetometer lost) | 2.2 pilot S1 | SITL | SUPPORTED | 39 |
| ambiguous propulsion event | 2.3 V12 | SITL | SUPPORTED | 58 |
| missing telemetry | pyulog CubeOrange | **REAL** | UNSUPPORTED (VTOL airframe) | 34 |
| log dropout | pyulog AUAV X2.1 | **REAL** | PARTIAL (dropouts; pre-allocation PX4) | 34 |
| maneuvering | 2.3 V13 | SITL | SUPPORTED | 55 |
| unsupported vehicle | PX4 docs boat | **REAL** | UNSUPPORTED (rover/boat) | 42 |

**Case 03 (telemetry corruption) depends on a simulation artefact.** Found
later by the pilot bundle's blinding step: its UNCONFIRMED excess line exists
only because PX4's failure-injection message opened the event at the true
onset. Without that message, which no real fault prints, the excess is never
reported (`DEFECT_D_PRIME_2.md`). The sample is kept as run.

**Can an engineer understand the main result in two minutes?** That is not
measured here. It needs real engineers, and the protocol is
`EXTERNAL_PILOT_PACKAGE.md`. What is measured:
- the first line of each case states the result;
- every summary fits in 34-58 lines;
- every state is semantic.

## 8. Gate PRIME-A `COMMERCIAL_MVP_USABLE` (`prime_a_gate.py` → `PRIME_A_GATE.json`)

| requirement | measured |
|---|---|
| ordinary supported ULog | yes: `csia-assure flight.ulg` |
| no research sidecars | yes: the ULog path is the only input |
| clear report | the A1 first page, in order (tested); readability by engineers not yet measured |
| coverage explicit | yes: eight classes, with the never-healthy invariant tested |
| deterministic reproduction | **yes:** two runs on three logs (SITL, real boat, pilot), every output byte-identical |
| no crash on supported schemas | **yes: 39 of 39** reachable logs (13 + 18 SITL flights, the pilot run, 6 pyulog logs including 4 real boards, the real boat) |
| installable | **yes:** a fresh virtual environment, `pip install .[logs]`, `csia-assure`; the first page identical to the in-repository run |

**PRIME-A is met,** within what can be measured without a user.
