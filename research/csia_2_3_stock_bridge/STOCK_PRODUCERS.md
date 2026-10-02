# Stock producers and their contracts (Phases 8-9)

**2026-10-02.**

**Code:**
- `csia_evidence_assurance/adapters/px4_stock.py`: the producers;
- `stock_log.py`: data access;
- `stock_stats.py`: the statistics, defined once;
- `events.py`: event discovery.

**Contracts:** `csia_evidence_assurance/contracts/stock_*.json`, and
`px4_ekf2_estimator_status_2.json`.

## 1. The minimum stock producer set, ranked (Phase 8)

Ranked by what each one lets Semantic Core 2.1.1 decide on an ordinary
log. Context producers are reported but decide nothing.

| rank | producer | record | role | why this rank |
|---|---|---|---|---|
| 1 | `px4:allocator.compensation` | ACTUATION/motor_m `actuation.physical_response` | profile evidence | the only stock output 2.1.1 reads that both raises a propulsion symptom (VIOLATED) and eliminates an explanation (SENSOR/response_sensor: the vehicle confirmed the loss, so it is not a sensor artefact) |
| 2 | `px4:esc.telemetry_response` | ACTUATION/motor_m `esc.telemetry_response` | context, plus the power gate for rank 1 | localizes the reported deficit per motor; tells a telemetry fault from a motor fault together with rank 1; detects its own changes for event discovery |
| 3 | `px4:battery.status` | POWER/battery `power.source_health`, `power.battery_warning` | profile evidence, plus context | on a vehicle that measures current, NOMINAL source health makes POWER/path_unavailable eliminable; in SIH it is UNAVAILABLE and says so |
| 4 | `px4:vehicle.rate_transient` | ACTUATION/motor_m `vehicle.rate_transient` | context | the physical vehicle response; valid only in [0, 0.2] s after an onset known to a fraction of that |
| 5 | `px4:allocator.status` | COMPUTE/control_allocator `allocation.authority` | context, plus trigger | PX4's own authority report; silent in every XSYS-001 flight |
| (2.2) | `px4:ekf2.estimator_status` | COMPUTE estimator records | as 2.2 (contract version 2 adds the quad base) | navigation integrity, kept apart from the propulsion diagnosis |

That is five stock producers, plus the unchanged 2.2 estimator producer.
Nothing else in a stock PX4 547e2ca log met the claim register's bar.

## 2. How each output is computed

**Event-relative windows.** Every output compares a window after a
discovered event with the window before it:
- BEFORE: [t0 - 5, t0 - 0.5) s;
- EARLY: [t0 + 0.5, t0 + 2) s;
- AFTER: [t0 + 10, t0 + 15) s;
- T1: [t0, t0 + 0.2) s.

Producers run at three checkpoints per event:
- **T1** (t0 + 0.2): the rate transient;
- **EARLY** (t0 + 2): telemetry and allocation;
- **AFTER** (t0 + 15): telemetry, compensation, allocation.

The battery is sampled every tick (1 s).

**Compensation (rank 1):**
- **VIOLATED** when C_m >= theta_ctrl (0.00688): the loop asks motor m for
  more than before, against the median motor. A compensated loss gives
  C = 1/eta - 1.
- **NOMINAL** only through the power gate (XSYS-001's
  `compensation_witness`). Motor m's telemetry must report a deficit L
  large enough that a genuine loss would have produced
  C = 1/(1 - L) - 1 >= 2 theta_ctrl, and no such compensation came.
- **NOT_APPLICABLE** when there is nothing to test: no local deficit, or a
  change in the opposite direction.
- **UNAVAILABLE** when:
  - fewer than 10 samples are in a window;
  - the allocator saturated over most of the window;
  - a log gap touches a window.

**Telemetry (rank 2):**
- **DEGRADED** when L = 1 - q_after / q_before is beyond ±theta_tel
  (deficit or excess);
- **NOMINAL** within it;
- **UNAVAILABLE** when not measurable.

**Rate transient (rank 4):**
- **DEGRADED** when D_m >= theta_dyn (0.0288 rad/s) on motor m's loss axis;
- **NOT_APPLICABLE** when the response is opposite to that axis;
- **NOMINAL** otherwise.

**Battery (rank 3):**
- **Source health NOMINAL** only with voltage AND measured current (the v2
  meaning).
- **Source health UNAVAILABLE** when `current_a < 0`.
- **The warning** is DEGRADED on PX4's warning level or on a voltage below
  cells x `BAT1_V_EMPTY`.

## 3. Contracts (Phase 9)

Each contract declares:
- producer and contract versions (`csia-2.3-stock-r1`, `stock-1`);
- the claims, with their meaning and attributability;
- what NOMINAL means: an observation, or NO_ANOMALY for the warning and
  allocation claims;
- the validity window relative to `stock.event`;
- the update mode (sample and hold);
- profile compatibility (`csia_evidence_assurance/profiles/multirotor_quad.py`);
- fault behaviour: a statistic that cannot be computed is UNAVAILABLE,
  never NOMINAL.

**Validity windows:**

| contract | validity relative to the event |
|---|---|
| compensation | [10, 15] s: XSYS-001's validated T3 |
| telemetry, allocation | [0.5, 15] s |
| rate transient | [0, 0.2] s: XSYS-001's validated T1 |
| battery | content age 1 s |

**The 2.2 model is not weakened:**
- Admissibility, independence, contracts and the profile gate are 2.2's,
  unchanged.
- The stock producers add records. They change no rule.
- Every earlier report is byte-identical (schema 3; the pinned pilot
  reports and the 66-flight batch reproduce).

## 4. Calibration

Thresholds come from apparatus data only (`CALIBRATION_2_3.json`,
revision 2). The 32 nominal apparatus flights give 160 pseudo-onsets every
0.5 s in hover.

**The rule** is XSYS-001's: threshold = 2 x the largest null |value|;
CUSUM h = 3k.

**The sweep check.** On the 27-flight apparatus sweep, every eta <= 0.9 is
detected with a delay of 0.10-0.31 s. eta = 1.0 is never detected.

**What does not transfer.** SIH carries almost no noise on these signals,
so the thresholds are tiny (0.0069). They do not transfer to hardware.

A real vehicle needs its own null flights, by the same rule. The
validation flights also show that hover-only nulls do not cover
maneuvering (`FALSE_POSITIVES.md`).
