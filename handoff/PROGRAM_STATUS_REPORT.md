# Program status report — physical validation + standards candidate

**Session:** 2026-09-06. **Branch:** `paper/physical-validation-and-vehicle-adapter`.
**Stop point:** the hardware checkpoint, as instructed.

Read `USER_ACTION_REQUIRED.md` first if you read one thing.
Read §4 of this document if you read two.

---

## 1. What was asked, and what state each part is in

| part | state |
|---|---|
| §11 edge-identifier defect | **DONE** |
| §12 profile/science firewall hardening | **DONE** |
| §1 profile/deployment seam | **DONE** — policy resolved, unification left to the user |
| §2 / P11 mutation testing | **DONE** — 5 findings |
| §3 adversarial bad implementations | **DONE** — 8, in the DEA regime |
| P4 + §5 orchestrator and validity predicates | **DONE** |
| P5 fault injector | **PROTOCOL + SIMULATED BACKEND. No firmware** — §3.4 |
| P6 end-to-end dry run | **DONE** — 9 invalid-trial demonstrations, plus a real 40-trial run |
| P7 preregistration | **DONE and frozen**, after being corrected pre-freeze |
| P8 repeated campaign | **RUN — ArduPilot only.** PX4 `NOT_RUN` |
| Program B (DEA) §13–§22 | **DONE** — profile, schemas, runner, 9 references |
| §23 `USER_ACTION_REQUIRED.md` | **DONE** |
| §24 purchase justification | **DONE**, unpriced by design |
| §28 master system input packet | **DONE** |
| §30 next-prompt requirements | **DONE** |
| §32 this report | **DONE** |

**Tests: 1939 collected, 0 failures** (baseline at session start: 1787).

## 2. The results, in order of what they are worth

### 2.1 The Mechanism-A repeat — the strongest thing here

The original result was **n = 1** fault trial plus one control, per platform.
It is now **n = 20 + 20 on ArduPilot**, on the **same pinned autopilot build**
the original used — `ArduCopter V4.8.0-dev @ 01a504b`, fetched, rebuilt from
source, and verified by the binary's own MAVLink version string.

```
planned 40 | attempted 40 | valid 40 | invalid 0 | not_attempted 0
```

| | FAULT (20) | CONTROL (20) | original n=1 |
|---|---|---|---|
| `gnss.position MISSING` occurred | **20/20** | **0/20** | yes |
| `first_t` (s) | 12.0399–12.0827, med **12.0432** | — | **12.043901** |
| ticks observed | 449–450 | 0 | **450** |
| `gps_gate_weight_sum` | 3.0 → **0.0** | 3.0 → 3.0 | 3.0 → 0.0 |

**The original's single observation falls inside the repeat's range** and its
median is within 0.0007 s of it.

Bounded honestly: still **E1**; **ArduPilot only**; **no timing claim** (the
host was contended); and **trust was not captured at all** (§3.3).

### 2.2 Mutation testing found five unpinned places

24 deliberate mutations of the scientific core. **18 killed behaviourally, 5
killed only by a file-hash guard, 1 invalid, 0 survived outright.**

The five can be changed with no behavioural test objecting. **Three are in
`csia/diagnosis/baselines.py` — the baselines the Mechanism-B comparison is
against.** If a referee asks how we know the baselines are the baselines the
paper describes, the answer today is a file hash.

A sixth, found the same way: the paper's `S_0 = 475.6775` is pinned by a test
that reads a **stored artifact**, and nothing re-derives that artifact from the
engine. Change `alpha0` and the test still passes *because the artifact is
stale*.

### 2.3 The firewall is now generated, not remembered

`csia/aircraft/firewall.py` derives 47 protected parameter names from the
frozen source by AST. Fuzzed through six respellings, every framing prefix,
four nesting depths and five environment-reference forms — and asserted **not**
to fire on 27 ordinary plumbing keys, because an over-eager guard gets
disabled.

### 2.4 DEA is a candidate profile, not a standard

Ten requirements, four verdicts, **no score**. A conforming reference that
shares no code with CSIA and is not even in avionics. Eight deliberately bad
references, each rejected for the requirement it violates, plus a test that
every requirement is violated by at least one — so a requirement nobody can
fail cannot enter the profile.

## 3. What did not go to plan

Full detail in `FAILURE_LEDGER.yaml`, which grew from 7 entries to **15**.

### 3.1 I was wrong about the build being unidentifiable (FL-011 → FL-013)
I concluded from the Mechanism-A artifacts alone that the original autopilot
build could not be recovered, and wrote a preregistration around that
limitation. It is recorded in four other places. **Corrected before the
preregistration was frozen**, which turned a weaker campaign into a genuine
repeat.

### 3.2 I overwrote committed evidence (FL-013)
Running `modern_replication.py` to check the new build rewrote
`research/phase2/results/modern_replication.json` — silently, exit code 0.
Reverted within the minute; **no commit contains it**. `tools/evidence_guard.py`
now refuses such writes, but **only that one script is wired to it**.

### 3.3 The campaign missed one of its own preregistered quantities (FL-014)
Section 5 item 2 asks for the trust coefficient. The runner did not pass
`--trust-trace`, so no trust series exists in the logs. Reported
`NOT_CAPTURED`, never inferred. **The "trust rises across the fault"
observation therefore still rests on n = 1 per platform** — and that is the one
number a repeat would most have strengthened.

### 3.4 No fault-injector firmware was written
Deliberate. There is no board to run it on, and untested firmware sitting in
`hardware/validation_rig/` would read as a validated component. The protocol
and a simulated backend exist instead.

### 3.5 Four guards fired on their own documentation
A recurring mistake worth naming: a guard written against *prose* rather than
*parsed structure* flags the paragraph explaining the thing it forbids. Each
was rewritten to check structure.

### 3.6 Two runner defects, caught on a 1+1 pair before 40 trials
The driver's exit code is the **timing** verdict, not a fault signal — reading
it as a rig fault adjudicated both validation trials `HARDWARE_FAULT`. And the
control arm was read as `INSTRUMENT_DEAD` because a role-marker dict was
non-empty, which under RULE A would have declared the whole campaign
unreadable. **Validating on a pair before committing to the campaign is what
caught both.**

## 4. What a human must decide or do

| id | blocker | who |
|---|---|---|
| **O-1** | four freeze tags are local only (push refused 403) | needs permission |
| **O-2** | **0 of 19 bibliography entries verified**; publisher hosts 403 at CONNECT | needs journal access — **neither manuscript can be submitted** |
| **O-3** | unify the two config files, or keep them separate | user decision; unifying orphans committed trial manifests |
| **O-4** | hardware purchase for E2+ | user decision; everything above E1 is behind it |
| **O-5** | flight-site authorisation, independent pilot authority | needed before E5 regardless of purchase |

## 5. What I did not do, and why

* **PX4 SIH half of the repeat.** Needs its own toolchain and build; not
  attempted. Recorded as `NOT_RUN`, never as "no difference".
* **A second campaign to capture trust.** The gap was found at extraction time.
  Starting another 40-flight campaign to avoid recording a shortfall would have
  been the wrong order of operations; it is recorded and specified instead.
* **Tests aimed at the five mutation survivors.** That would move the number
  and establish nothing. The correct task is written up instead.
* **Any E2–E5 result.** No hardware exists. The hardware backend and the serial
  injector both **refuse to construct** rather than returning plausible values.

## 6. Where everything is

| what | where |
|---|---|
| blockers | `USER_ACTION_REQUIRED.md` |
| for the system designer | `handoff/MASTER_SYSTEM_INPUT_PACKET.md` |
| for the next agent session | `handoff/NEXT_MASTER_PROMPT_REQUIREMENTS.md` |
| every failure and correction | `research/physical_validation/FAILURE_LEDGER.yaml` |
| what results license, and what they do not | `research/physical_validation/PAPER_IMPACT_LEDGER.yaml` |
| what no test pins | `research/physical_validation/mutation/MUTATION_SURVIVORS.md` |
| the campaign | `campaigns/physical_validation/mechanism_a_repeat_ap/` |
| its preregistration and status | `research/physical_validation/prereg/` |
| the standards candidate | `standards/dea/DEA_PROFILE.md` |
| the config seam | `docs/VEHICLE_PROFILE_VS_DEPLOYMENT.md` |

## 7. The one-sentence version

The Mechanism-A mechanism now reproduces 20 out of 20 on ArduPilot against 20
clean controls on the original pinned build; mutation testing found five places
in the scientific core that no behavioural test pins, three of them in the
baselines the paper compares against; and **nothing above evidence tier E1
exists, the bibliography is unverified, and neither manuscript can be
submitted** until a human clears O-2.
