# The product validation set (Phase 25)

**2026-10-02.**

- **Script:** `validation_set.py`.
- **Output:** `VALIDATION_SET.json`.

## 1. The rule

**Existing data first.** Synthetic data only where no real data exists,
and marked so. Each row records:
- the class and the case;
- the source;
- what was expected;
- what the product said;
- **correct:** the right outcome;
- **useful:** an engineer learns something actionable;
- **honest:** no claim beyond the evidence, and its gaps named.

**The sources:**
- **REAL SITL:** the thirteen validation flights and the 2.2 pilot's S1
  run, all ordinary logs;
- **XSYS-001 REPLAY:** stock logs at default rates. Case B is XSYS-001's
  frozen telemetry-only construction.
- **SYNTHETIC:** `synthetic_stock.py` logs, and one frozen v2 scenario.

## 2. The set

| class | case | source | outcome | correct | useful | honest |
|---|---|---|---|---|---|---|
| nominal | V5, V6, V11 (maneuvering) | REAL SITL | no symptom at any time; 11 false events each, dismissed | yes | **no** (the event list buries the answer) | yes |
| nominal | 11 benign-onset flights | XSYS-001 REPLAY | no event, no symptom | yes | yes | yes |
| motor degradation | V1-V4, V12 | REAL SITL | the injected motor, AMBIGUOUS among 4; response_sensor eliminated | yes (5/5) | yes | yes |
| motor degradation | 55 A trials | XSYS-001 REPLAY | motor_0, AMBIGUOUS, 55/55 | yes | yes | yes |
| motor degradation, maneuvering | V13 | REAL SITL | no symptom: compensation NOT_STEADY_FLIGHT; telemetry deficit reported | as stated in advance (a miss) | partly | yes |
| telemetry corruption | V9 (ESC off) | REAL SITL | no symptom; telemetry UNAVAILABLE (ESC offline) | not as stated in advance (`VALIDATION_FLIGHTS.md`); outcome right | yes | yes |
| telemetry corruption | V10 (ESC x 10) | REAL SITL | no symptom; excess reported on motor_2 | yes | yes | yes |
| telemetry corruption | 55 B trials | XSYS-001 REPLAY | no symptom; deficit unconfirmed by the vehicle, 55/55 | yes | yes | yes |
| power anomaly | V8 (battery wrong) | REAL SITL | battery warning and failsafe; no propulsion symptom; source health UNAVAILABLE | yes | yes | yes |
| navigation anomaly | V7 (GPS off) | REAL SITL | PX4 message and failsafe; no propulsion symptom; navigation outside the profile | yes | unclear: the estimator context carries the story | yes |
| configuration transition | S1 (EKF2 selector run) | REAL SITL | 13 configuration changes in the timeline; no false symptom | yes | unclear | yes |
| producer failure | esc_status silent 2 s inside a window | SYNTHETIC | outputs over the gap UNAVAILABLE and refused; no fault claimed from them | yes | yes | yes |
| no coverage | a motor loss with esc_status absent | SYNTHETIC | no propulsion evidence, no trigger, said so; the loss is missed | yes (the honest outcome) | yes | yes |
| ambiguous | every motor loss | REAL SITL and XSYS-001 REPLAY | AMBIGUOUS, with the records that would resolve it | yes | yes | yes |
| compute/timing anomaly | v2 CPU_OVERLOAD (2.2 path) | SYNTHETIC (frozen v2 scenario) | compute symptoms where compute evidence exists | — | — | yes |

## 3. What the set says

**Correct and honest everywhere it applies, with the final code.** As first
frozen, the maneuvering nominal flights were not correct: they raised
transient false symptoms (`FALSE_POSITIVES.md`).

**Useful where the stock log carries the evidence:** propulsion, telemetry
and power.

**Less useful in four places:**
- **Maneuvering flights:** noisy event lists.
- **Navigation:** the profile has no navigation records. The estimator
  context is the 2.2 producer's.
- **Configuration transitions:** reported, but nothing is decided from
  them.
- **A loss during continuous maneuvering:** stated and honest, but a miss.

**Compute and timing cannot be diagnosed on a stock PX4 log.**
- No stock topic pairs a process with a deadline.
- `cpuload` is context, and in SITL it measures the host.
- The frozen v2 scenario shows that 2.1.1 reasons about compute when the
  evidence exists. A stock log does not supply it.
- That is a statement about the log, made in every report's coverage
  section.

## 4. Limits

**What a row is.** Each SITL row is one flight. The XSYS-001 rows are
SIH. The synthetic rows pin logic, not accuracy.

**What the set is not.** It is a behaviour check across classes, not a
measured detection or false-alarm rate for any vehicle.
