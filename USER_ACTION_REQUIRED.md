# User action required

**Written:** 2026-09-06, after the software-evidence completion pass.
**Audience:** the repository owner.

Everything below is blocked on something **outside this environment**:
hardware that must be bought and wired, access this environment is denied, or
a judgement that is not an agent's to make.

**Nothing here is a software task.** Anything that could be done in software
has been done or is recorded in
`handoff/NEXT_MASTER_PROMPT_REQUIREMENTS.md`.

The three sections are deliberately kept apart. Mixing a purchase decision with
a library-access problem produces a list where nothing looks actionable.

---

# A. PHYSICAL HARDWARE

Everything above evidence tier **E1** is behind this section, and no amount of
further software work substitutes for any of it.

## A-1. Purchase decision for evidence tier E2

| tier | needs | status |
|---|---|---|
| E0 desktop simulation | — | complete |
| E1 current-stack SITL/SIH | — | complete: **three campaigns, 120 trials, 120 VALID** — ArduPilot A1 and A2, PX4 P1, each 20+20 |
| **E2 real flight-controller hardware** | flight controller, companion computer, bench harness | **NOT STARTED** |
| E3 real sensor + physical fault | E2 + fault-injection rig | NOT STARTED |
| E4 physical actuator path | E3 + thrust stand | NOT STARTED |
| E5 controlled flight | E4 + airframe, site, pilot | NOT STARTED |

**What is needed:** a decision on which tier to fund.
**Itemised:** `hardware/validation_rig/PURCHASE_JUSTIFICATION.csv` — 12 rows,
each with what it buys, what claim it licenses, and **what it does not**.

**Deliberately unpriced.** Vendor sites are unreachable from this environment,
so every price would have been invented. `docs/HARDWARE_BOM.md` carries 2026
planning estimates that say on their face to verify at purchase.

**E2 is the smallest step that changes what either manuscript may say.**

## A-2. What is already built and waiting for hardware

So the purchase is not blocked on further software:

* the campaign orchestrator, the eight-state validity vocabulary and the
  twelve-cause invalid-trial matrix (12/12 classified, no manual adjudication);
* the fault-injector **wire protocol** and a simulated backend;
* immutable, content-hashed trial manifests.

Both the hardware backend and the serial injector **refuse to construct** rather
than returning plausible values. That is deliberate: a stub would produce E2
and E3 numbers from nothing, indistinguishable from measurements downstream.

**No firmware has been written.** There is no board to test it on, and untested
firmware sitting in `hardware/validation_rig/` would read as a validated
component.

## A-3. Authorisation, before any physical trial

Not needed today; listed so it is not discovered late.

* **props removed** for every bench phase — declared in every shipped profile;
* **independent pilot authority** — a human with a kill path who is not the
  experimenter;
* **flight site and airspace clearance** for E5. Money does not solve this one.

Out of scope by instruction and implemented nowhere: RF jamming, GPS spoofing
transmitters, counter-UAS behaviour, autonomous targeting. The GNSS fault in
the rig is produced by **physically disconnecting a receive antenna or data
line**; nothing on the purchase list can transmit.

---

# B. BIBLIOGRAPHY AND EXTERNAL ACCESS

Administrative and access blockers. **None of these is a hardware problem and
none is a software problem.**

## B-1. Zero bibliography entries are publisher-verified

| status | count |
|---|---|
| `UNVERIFIED` | 10 |
| `CORROBORATED_NO_PUBLISHER_RECORD` | 9 |
| **`VERIFIED`** | **0** |

**This environment cannot clear it.** The agent proxy answers **403 at
CONNECT** for `doi.org`, `dl.acm.org`, `ieeexplore.ieee.org`,
`link.springer.com`, `www.sciencedirect.com`, `arxiv.org` and
`api.crossref.org`. That is a policy denial at the gateway — not TLS, not rate
limiting, and not something a retry or another client fixes. **No further
engineering time will be spent on those hosts.**

**The work order is prepared:**
`papers/BIBLIOGRAPHY_HUMAN_VERIFICATION_WORKORDER.md` — all 19 entries with
title, authors, venue, year, DOI where one exists, and the authoritative target.

**Consequence:** while `publisher_verified = 0`, neither manuscript is
submission-ready if the publication gate requires authoritative verification.

## B-2. Four freeze tags exist only on one machine

```
$ git ls-remote --tags origin
758f4ae...  refs/tags/v0.7.0          <- the only tag on the remote
```

`csia-v1.0-research-final`, `csia-v2-phasec-frozen`,
`csia-dual-paper-evidence-freeze` and `archive/handoff-source-of-record` are
local-only; the push was refused **HTTP 403**.

**Why it matters:** `test_diagnostic_core_is_unchanged_since_the_freeze` diffs
against `csia-v1.0-research-final`. On a fresh clone the tag does not exist, so
the test **skips**, and a skipped freeze test reads as green. A hash-file
fallback exists and runs everywhere, which is why this is a real problem and
not an emergency.

**Needed:** push the tags, or grant tag-push permission.

## B-3. Configuration-unification decision

`profiles/*.yaml` and `configs/vehicle/*.yaml` overlap. **Not an agent's call:**
unifying them changes the flight-log header hash and **orphans every committed
trial manifest that cites one**.

Documented at `docs/VEHICLE_PROFILE_VS_DEPLOYMENT.md` with three options and
what each costs. The status quo — two files, cross-checked, conflicts reported
and never silently resolved — is implemented and safe to leave.

---

# C. EXTERNAL INDEPENDENT VALIDATION

Judgements that need someone who did not build this.

## C-1. Adversarial review of the DEA candidate profile

`standards/dea/DEA_PROFILE.md` is a **candidate**, not a standard: not
submitted to any body, not endorsed by one.

It has been tested against itself as hard as its author can — a conforming
non-CSIA reference in a different domain, eight deliberately bad references
each rejected for the requirement it violates, and a test that every
requirement is violated by at least one of them.

**What it has not had is an attacker.** Its four open questions (§10 of the
profile) need answers from someone with no stake in it — particularly the
open-world hypothesis set, which DEA-6 currently cannot express.

## C-2. Independent replication of the E1 campaigns

Everything measured here ran on one host, in one container, driven by one
agent. The builds are pinned and the campaigns are preregistered so that
someone else **can** re-run them:

* ArduPilot `01a504b472259602e13df4cf07df7c0cdbb35993`
* PX4 `547e2caa9883bc1609325f02b4914b4e2482fe62`

**Nobody has.** Reproducibility that has never been exercised is a property of
the documentation, not yet of the result.

## C-3. Review of what the mutation campaign did not pin

The mutation results are a self-assessment: the agent chose the mutants and
chose the test selection, and **that selection was wrong once** — three
"survivors" in `csia/diagnosis/baselines.py` turned out to be an omission from
a hand-picked list rather than a gap in the suite.

All six unresolved mutants are now adjudicated, in
`research/physical_validation/mutation/MUTATION_ADJUDICATION.md`. **The count
moved from 0 of 5 killed to 4 of 5, and the raw count is the least useful thing
in that file**: three were the selection error above, one was killed by an
oracle written *after* the mutant was known, and **one is still pinned by
nothing but a file hash and was deliberately left that way** — writing a test
for it now would make the count 5 of 5 and measure nothing.

A reviewer choosing their own mutants would be worth more than another campaign
run by the same author. The specific thing to attack is
`CONFIGURATION-02` (`imu_isolation_gap`), which no behavioural test reaches.

---

## Where the record lives

| file | holds |
|---|---|
| `research/physical_validation/FAILURE_LEDGER.yaml` | every failure, negative result and self-correction, append-only |
| `research/physical_validation/PAPER_IMPACT_LEDGER.yaml` | what each result licenses — and what it does not |
| `research/physical_validation/SCALAR_DERIVATION_GRAPH.yaml` | where each headline number comes from |
| `research/physical_validation/ARDUPILOT_REPEAT_RECONCILIATION.md` | twelve headline quantities across n=1, A1 and A2. **Nine reproduce, three do not**, and why |
| `research/physical_validation/PX4_REPEAT_RECONCILIATION.md` | the same, second platform. **Ten reproduce, two do not**, attributed by a controlled watchdog replay |
| `research/physical_validation/P4_P7_STATUS_AUDIT.md` | P4–P7 audited by running their tests, not by observing files exist |
| `research/physical_validation/mutation/` | what no behavioural test pins — `MUTATION_ADJUDICATION.md` is the current state |
| `handoff/MASTER_SYSTEM_INPUT_PACKET.md` | for whoever designs the system around CSIA |
| `handoff/NEXT_MASTER_PROMPT_REQUIREMENTS.md` | for the next agent session |
| `papers/BIBLIOGRAPHY_HUMAN_VERIFICATION_WORKORDER.md` | §B-1, per entry |
