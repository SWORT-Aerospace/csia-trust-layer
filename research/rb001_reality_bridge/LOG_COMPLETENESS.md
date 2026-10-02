# Log completeness under stress (RB-001 Part 18)

**2026-10-02.**

- **Script:** `log_completeness_stress.py`.
- **Output:** `LOG_COMPLETENESS_STRESS.json`.

**Method.** Offline damage to 2.3 validation logs (PX4 default logging),
then the unchanged product path on the damaged log:
- V4: a 40 % loss on motor_0, in hover;
- V5: nominal, maneuvering.

## 1. The rule held

**Missing samples never became healthy evidence.** In every damaged case:
- no output computed over a gap was admitted as NOMINAL;
- no symptom appeared that the undamaged log did not have.

## 2. Results

| case | V4 symptom (undamaged: `COMMAND_NO_RESPONSE|motor_0`) | outputs refused by producer health | reading |
|---|---|---|---|
| propulsion topics silent 2 s inside the AFTER window | none: refused | 8 | correct: the evidence over the gap is UNAVAILABLE; the loss goes unconfirmed rather than wrongly confirmed |
| propulsion topics logged at 2 Hz instead of 10 Hz | none: refused | 12 | **over-refusal:** the gap rule compares sample spacing to PX4 547e2ca's default interval (100 ms), so a vehicle logging at a lower rate looks like one long gap |
| battery producer silent | still raised | 0 | correct: one producer's silence does not affect another's evidence |
| ESC topic absent | none | 0 | correct: no propulsion evidence, said in the coverage notices |
| a 120 ms logger dropout over the AFTER window | none: refused | 9 | correct |
| **real-board timing jitter** (10 ms std on 100-200 ms topics, 0.7 ms on IMU, from RB0) | **none: refused** | 12 | **a weakness, see section 3** |

**On V5, nominal:** no symptom in any case, and the number of NOMINAL
outputs fell as refusals rose.

## 3. The weakness the jitter case exposed (receipts RR-04, RR-05)

**Two 2.3 data-access rules interact badly with real timing:**
1. **Default-rate emulation.** `runs.stock_flight` always re-decimates the
   log to PX4 547e2ca's default intervals. It keeps the first sample at or
   after each boundary. That was built for XSYS-001's 250 Hz research logs.
   **On a log already at default rates with real jitter,** a sample that
   arrives a few ms early is skipped, so the next kept one is nearly two
   intervals later.
2. **The gap rule:** a gap is longer than 3 x that same default interval.

**Together, on the jittered V4:**
- `esc_status` showed 302 ms gaps against a 300 ms limit;
- `control_allocator_status` showed 605 ms against a 600 ms limit;
- the compensation, which correctly measured C = 0.664 on motor_0, was
  refused, and the loss went unreported.

**The fix, specified but not applied.** The brief's Part 1 says not to
change evidence definitions yet, and no real propulsion log has confirmed
the problem:
- re-decimate only topics logged faster than their default interval;
- measure gaps against the log's own median interval for that topic, not
  the default.

**Neither changes any historical result:** the XSYS-001 logs are at 250 Hz,
and the 2.3 logs have SITL timing.

**The gate for applying it:** the first real propulsion log (RB0 with the
owner's logs or RflyMAD, or RB3).

## 4. What this does not test

**Synthetic damage on real-structure logs is not real data.** The jitter
statistics are real (RB0); the logs they were applied to are SITL.

**Not done here:**
- **The logger's own rate reduction** on a real board, through a different
  `SDLOG_PROFILE` or `logger_topics.txt` (RB3);
- **real producer silence**, such as an ESC telemetry wire unplugged
  (RB2-0).
