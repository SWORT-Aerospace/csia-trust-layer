# External-engineer test, onboard hold, FORGE hold, stop conditions (RB-001 Parts 32-35)

**2026-10-02.**

## 1. Part 32: the external-engineer test package

**The precondition is not met.** The brief: "If the Analyzer is stable
enough on physical/HIL data". There is no physical or HIL data yet. The
Analyzer has run on 4 real boards' logs, none of which flew a propulsion
event (RB0).

**So no study was prepared,** and none was simulated or fabricated.

**What the package will contain once physical or HIL data exists,** fixed
now so it cannot be shaped by the results:

| item | content |
|---|---|
| logs | physical/HIL ULogs only: at least the RB2 nominal corpus subset, the A and B pairs, and one nominal RB5 flight; each with its SHA-256 |
| Analyzer | the tagged commit; `python -m csia_evidence_assurance analyze <log>`; no research inputs |
| quick start | one page: install, run, where the report is, how to read its first section |
| questions | for each log: what happened? which component, if any? how sure, and why? what would you check next? what could the log not show you? |
| ground-truth key | the run sheets (what was changed, when), stored **separately** and released only after scoring |
| scoring rubric | per question: correct / partially correct / wrong / "cannot tell" (and whether "cannot tell" was right); time to answer; with and without the Analyzer, on different logs (a within-subject crossover) |

## 2. Part 33: onboard port hold

**The H743 port is held.** Per the brief, nothing is ported until physical
evidence shows the producer and evidence architecture is worth preserving.
The feasibility estimate of the 2.1 shadow program
(`H743_FEASIBILITY.md`) is the only onboard work, and it stays an estimate.

## 3. Part 34: FORGE hold

**FORGE stays blocked.** The gate for even shadow FORGE integration, and
where it stands now:

| gate condition | status |
|---|---|
| useful assurance on physical/HIL data | **not met**: no physical/HIL data |
| zero known wrong UNIQUE | met on all data so far (SITL, XSYS-001, RB0); the stock evidence never yields UNIQUE |
| controlled false symptoms | met in SITL with the 2.3 final code (0 at any time on 13 + 4 nominal maneuvering flights); **not demonstrated** at the budget's 0.1/h (needs 30 nominal hours, `FALSE_ALARM_BUDGET.md`) |
| valid evidence lifecycle | met in SITL; the jitter receipt (RR-04) shows it is not yet robust to real timing |
| producer-health behaviour | met on the tested cases (synthetic and RB0) |
| real source lineage | **not met**: lineage roots are from topic structure, not hardware (`HARDWARE_EVIDENCE_PLANS.md`, Part 19) |

## 4. Part 35: stop conditions

**The brief's Part 35 is cut off after its first condition and the start of
the second:**
> STOP and report rather than patching broadly if: Semantic Core 2.1.1
> fails on physical data for a semantic reason / 2.2

**How it was applied.** The first condition was applied as written. For the
second, the conservative reading was taken: **any 2.2 evidence-model
failure on real data is reported, not patched broadly.**

**What happened:**
- **Semantic Core 2.1.1:** no semantic failure on any real data. It
  received no physical propulsion evidence, so this is not yet a strong
  statement.
- **2.2:** one failure on real data: RR-01, the estimator adapter crashing
  on other PX4 versions.
  - **What it was:** a data-access defect in one adapter, not in the
    evidence model (envelope, health, contracts, lineage, admissibility).
  - **What was done:** fixed narrowly, so a schema mismatch becomes a
    coverage notice, with a test.
  - **What did not change:** every historical output reproduces byte for
    byte.
  - **What was not done:** no broad patch.
- **Not patched, reported:** the timing weaknesses (RR-04, RR-05).

**The rest of the stop-condition list is unknown.** The owner should resend
Part 35 if more conditions were intended.
