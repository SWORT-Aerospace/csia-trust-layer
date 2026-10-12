# Motor fault against telemetry fault, by evidence configuration (Phase 18)

**2026-10-02.**

## 1. The question

**Telling the two faults apart.** A motor that lost thrust and an ESC that
misreports its speed can look the same in the ESC's telemetry. Can the
product tell them apart, and with which evidence?

**The configurations:**
- **A:** stock producers only;
- **B:** stock producers and PX4's monitors (the product default);
- **C:** XSYS-001's research witnesses (frozen).

## 2. On XSYS-001 (121 cases, `BLIND_ONSET_REPLAY.json`)

| truth | configuration A | configuration B | configuration C |
|---|---|---|---|
| motor loss (55) | `COMMAND_NO_RESPONSE|motor_0` AMBIGUOUS, response_sensor eliminated, telemetry excluded as the explanation (55/55) | same (55/55) | UNIQUE ACTUATION/mechanical, correct (55/55) |
| telemetry-only deficit (55) | no symptom; deficit reported, unconfirmed by the vehicle (55/55) | same (55/55) | UNIQUE, correct (55/55) |
| benign onset (11) | no event, no symptom | same | no symptom |

**Read across the columns:**
- **Stock evidence (A, B) separates the two faults in every case.**
  - A motor loss raises a symptom. The vehicle's compensation confirms the
    loss, which eliminates the sensor explanation.
  - A telemetry deficit raises none. The vehicle did not compensate as a
    genuine loss of that size would have: the power gate's NOMINAL, from
    XSYS-001's own witness rule.
- **What stock evidence cannot do is name the part.** It cannot pick
  mechanical out of the propulsion chain.
- **XSYS-001's research witnesses (C) can, in this simulator.** They add
  RPM-per-command at 250 Hz, read as the mechanical response with the
  stall check that SIH's model allows.
- **The stock product refuses to do the same** (finding SB-1). Without ESC
  current, "no stall" cannot be checked, and placing an RPM-only deficit
  where 2.1.1 reads the stall signature would eliminate mechanical without
  evidence.

**PX4's monitors add nothing on XSYS-001.** B equals A, because none of
them fired in any flight.

## 3. On the validation flights (real PX4 failure injection)

| run | truth | configuration A | configuration B |
|---|---|---|---|
| V1-V4 | motor loss, each motor | correct motor, AMBIGUOUS (4/4) | same (4/4) |
| V9 | ESC 2 telemetry OFF (motor_1 healthy) | telemetry change on motor 1; no symptom | telemetry change and PX4 log message; no symptom |
| V10 | ESC 3 telemetry WRONG, RPM x 10 (motor_2 healthy) | **onset missed**; a later deficit-direction event only | PX4 log message at the injection; telemetry EXCESS reported on motor_2 (L = -98.6); no symptom |

**V9: the evidence was read wrongly the first time, and fixed.**
- With the code as frozen, the offline ESC's zero RPM was read as a
  measured 100 % deficit.
- The power gate's division guard then made the compensation UNAVAILABLE
  instead of NOMINAL. That met only part of the stated expectation.

The outcome was still correct: no symptom, so a healthy motor was not
blamed. But it was right for a weaker reason than intended.

The claim register already listed "telemetry dropout" as a failure mode,
so the bridge's code fell short of its own claim. After the fix:
- an ESC whose online bit PX4 cleared has its telemetry UNAVAILABLE
  (ESC_TELEMETRY_OFFLINE), and the report names it;
- the compensation is NOT_APPLICABLE: nothing was reported, so there is
  nothing to test;
- a total loss reported by an online ESC passes the power gate.

`VALIDATION_FLIGHTS.md` keeps both scorings.

**V10: one-sided detection.**
- The telemetry CUSUM watches for a deficit only, so an RPM jump of x 10
  (an excess) does not trigger it at onset.
- In configuration A, the change is found only 7 s later, in the deficit
  direction, when the trailing reference catches up. By then the event's
  BEFORE window already holds the corrupted values, and the excess is
  invisible.
- In configuration B, PX4's own warning, logged at injection, gives the
  event. The telemetry producer then reports the excess correctly.

**What V10 says about the monitors.** PX4's monitors are the difference
between catching and missing this telemetry fault. A two-sided telemetry
detector would close the gap without them. It needs its own calibration
and was not added here.

## 4. Conclusion

**The product separates the two faults.**
- From stock evidence alone, it separates a lost motor from lying
  telemetry: 110/110 on XSYS-001.
- On the validation flights it raised the right symptom or none in 6/6
  runs, in both configurations. In configuration A, V10's excess was not
  seen at all: correct by silence, not by evidence.
- It never attributes a telemetry fault to the motor.
- It never names the failed part of a motor's chain: the evidence for that
  is not in a stock log.
- PX4's monitors (B) matter where the stock detectors are one-sided: V10's
  excess.
- The research witnesses (C) show what richer evidence buys: UNIQUE
  attribution. They are not available on an ordinary log.
