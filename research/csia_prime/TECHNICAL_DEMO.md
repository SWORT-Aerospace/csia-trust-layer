# The technical demo: one RPM symptom, two truths (PRIME Track D4)

**2026-10-02. BUILT ON SITL + OFFLINE TELEMETRY CORRUPTION. Not a physical
result; the physical version is `B4_MATCHED_AB_PROTOCOL.md`.**

**Files:**
- **script:** `demo_ab.py`;
- **facts:** `DEMO_AB.json`;
- **the product's own first pages and receipts:** `demo/A/`, `demo/B/`.

## 1. The setup

| | CASE A: physical degradation | CASE B: telemetry corruption |
|---|---|---|
| log | 2.3 V4 (SITL): motor_0 at 60 % effect from the onset, hover | RB-001 CAL1 (SITL), nominal hover; motor_0's logged RPM × √0.6 from 70 s |
| truth | the motor lost effect | the motor is healthy; only its RPM report is wrong |
| the local symptom an RPM rule sees | ESC telemetry deficit **0.399** of commanded thrust | ESC telemetry deficit **0.400**: matched by construction |

**What any RPM-versus-command rule would say:** the two are identical
("motor_0 underperforming"). PX4's own ESC-based checks and the log tools
in `COMPETITOR_FUNCTION_MATRIX.md` look at this signal, so they cannot
separate them either.

## 2. What CSIA shows (from `DEMO_AB.json`)

**Case A:**

| monitor on motor_0 | state, value |
|---|---|
| ESC telemetry response | DEGRADED 0.399 |
| allocator compensation (physical response) | **VIOLATED 0.663** |
| rate transient (IMU, first 0.2 s) | DEGRADED 0.127 |

**What CSIA concludes:**
- **three monitors agree, but they are 2 independent lines, not 3.** The
  compensation and the telemetry statistic share the motor commands
  (lineage);
- `COMMAND_NO_RESPONSE` on motor_0;
- the sensor explanation is **eliminated** by the physical-response
  evidence;
- **AMBIGUOUS among 4** (drive without current, mechanical, command not
  delivered, power path);
- attribution **not justified**;
- **what would resolve it:** ESC current, command-delivery evidence,
  battery current.

**Case B:**

| monitor on motor_0 | state, value |
|---|---|
| ESC telemetry response | DEGRADED 0.400 |
| allocator compensation (physical response) | **NOMINAL 0.0015** |
| rate transient | NOMINAL 0.008 |

**What CSIA concludes:**
- **no symptom;**
- the telemetry deficit is listed as an **UNCONFIRMED** observation, not a
  fault: "context only: no symptom reads this output";
- attribution NO_EVIDENCE.

## 3. What the demo communicates, honestly

1. **Which evidence is independent:** A's three agreeing monitors are two
   lines.
2. **Which evidence shares a source:** compensation and telemetry share
   the motor commands. The rate transient shares the IMU with the
   compensation.
3. **Which evidence is valid, and when:** the rate transient only in its
   first 0.2 s; the compensation only in steady flight.
4. **Which evidence is excluded:** in a maneuvering version of A (2.3 V13,
   `sample_reports/10_maneuvering_loss`), the compensation is refused as
   NOT_STEADY_FLIGHT. CSIA then **declines to confirm** the loss and says
   why, instead of guessing.
5. **Which hypotheses remain:** four in A, with the measurement that would
   split them.

## 4. What the demo must not be used to claim

- **Not physical.** Both cases are SIH; B's corruption is offline.
- **Not "detects motor failures".** The value shown is refusing to treat B as
  A, and stating what remains unknown in A.
- **Not general.** It holds for one airframe, a hover, and 40 % loss.

**What upgrades it:**
- the bench A/B (`B4_MATCHED_AB_PROTOCOL.md`), with a load-cell witness and
  a real pole-count misconfiguration as B;
- then a restrained vehicle (RB5) for the closed-loop version.
