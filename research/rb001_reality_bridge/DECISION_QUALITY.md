# Decision quality (RB-001 Part 29)

**2026-10-02.**

## 1. The hardware table is empty, and says so

**The brief asks for hardware decision quality. There is no hardware data**
(`HARDWARE_INVENTORY.md`). Every physical cell below is "no data". Nothing
from simulation is moved into the physical column. Accuracy alone is not
used anywhere in this document.

**Columns:**
- **physical (RB2-RB6):** the question RB-001 was set.
- **RB0, real logs:** the 4 real boards' logs (`RB0_REAL_LOGS.md`). Real
  data, but none of it flew a propulsion event, so most rows are empty for
  a different reason.
- **SITL, product (2.3 final code):** the 13 validation flights V1-V13 on
  ordinary logs (`research/csia_2_3_stock_bridge/VALIDATION_FLIGHTS.md`).
  In-flight time 0.302 h.

| measure | physical (RB2-RB6) | RB0, real logs (4 boards, 1.1 s airborne in total) | SITL, product (V1-V13, 0.302 h) |
|---|---|---|---|
| correct UNIQUE | no data | 0 | 0 (stock evidence never splits the last explanations) |
| wrong UNIQUE | no data | 0 | **0** |
| correct AMBIGUOUS (the true cause among those that remain) | no data | 0 (nothing to diagnose) | 5: V1-V4, V12; the mechanical loss among 4 remaining, the sensor explanation eliminated |
| false AMBIGUOUS (the true cause eliminated) | no data | 0 | 0 |
| correct symptom (`COMMAND_NO_RESPONSE` on the injected motor) | no data | 0 | 5 of 6 propulsion losses |
| false symptom, at any time | no data | 0 | **0** (final code; the code as first frozen raised 22 in V5/V6) |
| missed fault | no data | none injected | 1 of 6 propulsion losses: V13, in continuous maneuvering (stated in advance). V7-V10 are not propulsion faults; none was blamed on a motor |
| candidate events per in-flight hour | no data | no meaningful time base (1.1 s airborne); 0 events | 57 events / 0.302 h = **189 / h**; hover 0 / h, maneuvering 287 / h |
| false symptoms per hour | no data | — | 0; the 95 % bound is 3 / 0.302 h = 9.9 / h, against the 0.1 / h budget |
| false attribution per hour | no data | — | 0; bound 9.9 / h, against 0.01 / h |
| coverage (profile records observed, of 29) | no data | 0-1: no `actuator_motors`, no ESC telemetry, no current, schema mismatch | 4 in hover flights; 0 in maneuvering flights (the compensation refused as NOT_STEADY_FLIGHT) |

## 2. What the table can and cannot carry

**The SITL column is behaviour, not rates.** Each condition was flown once.
The bounds in the per-hour rows are two orders of magnitude above the
Part 15 budget (`FALSE_ALARM_BUDGET.md`). They show only that nothing
went wrong in a third of an hour.

**The RB0 column is the only real data,** and what it shows is coverage:
on logs from other PX4 versions the analyzer observes almost nothing, and
says so. That is the correct behaviour. It is also a usefulness limit: an
engineer with a 2019 Pixracer log gets a list of what is missing and no
propulsion analysis.

**What the physical column needs, in order:**

| measure | first stage that can fill it | minimum data |
|---|---|---|
| correct / false symptom on telemetry vs motor (A vs B) | RB2-2 | 5 repeats per condition, `MINIMUM_PHYSICAL_EXPERIMENT.md` |
| candidate events per hour (nominal) | RB2-1 (bench), then RB5 | the nominal corpus (Part 13) |
| false symptoms per hour | RB5/RB6 | 30 nominal flight-hours for the 0.1 / h claim |
| wrong UNIQUE per hour | RB6 or a fleet | 300 nominal flight-hours for 0.01 / h |
| coverage | RB3 (FC on bench) | one log per logging profile in use |

## 3. The product on RB-001's 13 new SITL flights

**The shipped product (B0), on the maneuver study's evaluation flights**
(`MANEUVER_STUDY.md`). These are new data, flown after the preregistration:
- EN1-EN4 nominal maneuvering;
- EF1-EF6, maneuvering losses;
- EH1, a hover loss;
- ET1-ET2, telemetry faults.

In-flight time 0.482 h.

| measure | value |
|---|---|
| correct UNIQUE | 0 |
| wrong UNIQUE | **0** |
| correct AMBIGUOUS | 1 (EH1: `ACTUATION/motor_0`, attribution not justified) |
| false AMBIGUOUS | 0 |
| correct symptom | 1 (EH1) |
| false symptom, at any time | **0** |
| missed fault | **6 of 7**: every loss during maneuvering (EF1-EF6) |
| candidate events per in-flight hour | 161 / 0.482 h = 334 / h overall; 339 / h on the nominal and telemetry flights |
| false symptoms per hour | 0 (bound 6.2 / h) |
| false attribution per hour | 0 (bound 6.2 / h) |
| coverage | as in 2.3: the compensation, as replicated in the study harness (B0), refused at 141 of 152 scored events (NOT_STEADY_FLIGHT) |

**The trade, in one line:**
- the product is safe and blind during maneuvering;
- the one candidate that is not blind in SITL (B3) has not met reality.

**For comparison, not product numbers:** B3, the research candidate, on the
same flights:
- 0 false symptoms;
- 7 of 7 losses found;
- 0 wrong motors.
