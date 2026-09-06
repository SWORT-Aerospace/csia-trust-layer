# Requirements for the next master prompt

**Purpose:** so the next agent session starts from what is true, not from what
the last one hoped. Written by the agent that ran the physical-validation and
standards-candidate program, at the hardware checkpoint.

This is a specification for a *prompt*, not a plan. It says what the next
prompt must contain, what it must forbid, and — most importantly — what it must
**not** ask for because the answer is already known.

---

## 1. Facts the next prompt must carry, or the session will re-derive them

Each of these cost real work to establish. A prompt that omits them buys them
again.

| fact | why it must be in the prompt |
|---|---|
| the frozen core is the six `FROZEN_PATHS`, and freeze tags are **local only** | a session that assumes the tags are pushed will trust a test that silently skips |
| the deployed output is a **normalised hypothesis weight**, not a posterior; "confidence" is forbidden | terminology drift is the failure mode the manuscripts are most exposed to |
| **trust RISES** across a gate collapse on both platforms, 20/20 fault trials on ArduPilot | every session that meets this for the first time assumes it is a bug and tries to "fix" it |
| **it rises ~3x MORE in the matched CONTROL arm** (Δ median +0.020594 against +0.007007, ranges disjoint) | "trust rises across a gate collapse" is true and misleading alone: the fault SUPPRESSES a rise that happens anyway. FL-016 |
| the single-trial figures 0.9213→0.9300 and 0.9856→0.9875 are **NOT repeatable values** | they were measured under a superseded 0.5 s runtime stale timeout; the repeats ran 1.0 s. FL-017 |
| the **runtime stale-timeout source** is part of the configuration a result is quoted against | it is not in the A1 or A2 preregistration, and that omission is what FL-017 is |
| `S_0 = 475.6775` is MEASURED, not the cap 500; `T_0 = 0.999791`, not 1.0; **`0.98764` exists nowhere** | these have each been wrong in a published draft once |
| support state is **NOT RECORDED** in the Mechanism-A artifacts | a writer will otherwise state one |
| nothing above **E1** exists | the single most common overclaim available |
| the deployment config routes exactly **two** values into the core (`tick_hz`, `field_mode`); `csia.profile` is a label | a session will otherwise either miss the two or invent a third |
| **both** ArduPilot SITL and PX4 SIH can be built and run here | superseded: PX4 SIH is built at `547e2ca`, drives the full stack, and its repeat campaign has run |
| PX4 SIH is **lockstep real time** and ignores `--speedup` | a 40-trial PX4 campaign takes ~35 min of wall clock; ArduPilot's takes ~30 at 5x |
| the pinned build is `01a504b472259602e13df4cf07df7c0cdbb35993`, reachable only after `git fetch --deepen` | a `--depth 1` clone does not contain it |

## 2. Constraints the next prompt must restate verbatim

These are not stylistic. Each one was tested this session and each one caught
something.

* Do only what you are 100% sure you can do correctly.
* **A NEGATIVE RESULT IS ACCEPTABLE. A KNOWN THEOREM IS ACCEPTABLE. AN
  UNRESOLVED MECHANISM IS ACCEPTABLE IF LABELED. AN UNSUPPORTED NOVELTY CLAIM
  IS NOT ACCEPTABLE.**
* No invented numbers. No citation invented to make a guard pass.
* Never tune to rescue a result; preserve failures.
* Do not modify frozen historical evidence to make a paper cleaner.
* If an experiment disproves a paper claim, **change the paper claim, not the
  experiment.**
* Do not create a parallel architecture. Extend what exists or say why not.

### 2.1 One constraint to ADD, learned this session

> **Before running any script that writes into `research/`, check whether its
> output path is git-tracked.**

`research/phase2/modern_replication.py` overwrote a committed artifact
silently, with exit code 0 (FL-013). `tools/evidence_guard.py` now refuses such
writes, but **only that one script is wired to it**. Every other research
script is still capable of it.

## 3. What the next prompt must NOT ask for

Asking for these wastes a session on work already done or already known to be
impossible.

| do not ask for | because |
|---|---|
| "verify the bibliography" | publisher hosts answer **403 at CONNECT** through the agent proxy. Measured six ways this session. It requires a human with journal access |
| "push the freeze tags" | refused HTTP 403. Requires a permission the agent does not have |
| "re-run P0–P3, P9, P10, P12" | complete, committed, and their artifacts are cited |
| "write tests that kill the five mutation survivors" | that gams the metric. The correct task is stated in `MASTER_SYSTEM_INPUT_PACKET.md` NEXT MASTER DESIGN TARGET 3 |
| "make the conformance runner produce a score" | deliberately refused, with the reason in `DEA_PROFILE.md` §7 |
| "add a `--force` to manifest writing" | deliberately absent; a test asserts no force parameter exists |
| "standardise 'gate closure shall lower trust'" | it would fail a correct implementation. See §G of the packet |
| "unify `profiles/` and `configs/vehicle/`" | **user decision O-3.** It orphans committed trial manifests. Do not decide it inside a session |

## 4. What a good next prompt should choose between

The next session should do **one** of these, not several. Each is a coherent
piece of work with a clear finish line.

### Option A — E2 hardware bring-up (requires purchase first)
Blocked on **O-4**. If hardware arrives, the whole orchestrator, fault-injector
protocol and validity vocabulary are already built and waiting; the work is a
hardware backend for `tools/csia_experiment/orchestrator.py`, replacing the one
that currently refuses.

### Option B — close the verification gaps
No purchase needed. Pin the baselines behaviourally, close the
artifact-mediated numeric bindings, and survey how many other bindings have the
same stale-able shape. This directly strengthens what the manuscripts may
claim.

### Option C — PX4 SIH half of the repeated campaign
No purchase needed. ArduPilot was rebuilt and run this session; PX4 needs its
own toolchain and build. It closes a real asymmetry: the current repeat is
ArduPilot-only, and PX4 is `NOT_RUN`, not `NO_DIFFERENCE`.

### Option D — DEA adversarial review
Software-only. The profile has four open questions it cannot currently answer,
particularly the open-world hypothesis set. Needs someone attacking it rather
than extending it.

**Do not attempt more than one.** This session ran a large multi-part brief and
the parts that went best were the ones with a single finish line.

## 5. Required outputs of the next session, whichever option

1. Every failure, negative result and self-correction appended to
   `research/physical_validation/FAILURE_LEDGER.yaml`. **Append-only**; a
   correction gets a NEW entry that supersedes, never an edit.
2. Any claim change routed through `PAPER_IMPACT_LEDGER.yaml` with all four
   fields, including `unsupported_upgrade`.
3. Full suite green, and the count stated as measured, not remembered.
4. `USER_ACTION_REQUIRED.md` updated if any blocker changed state.

## 6. How the next prompt should handle scale

This session's brief had 32 numbered sections. What worked and what did not:

**Worked:** measuring before asserting; validating a campaign runner on a 1+1
pair before running 40 (it caught two defects that would have invalidated all
40); running long jobs in the background while writing documents.

**Did not work:** writing a guard from prose rather than from parsed code. Four
guards this session fired on their own documentation. If a check is about where
something appears, check the *structure*, not the *string*.

**A specific recommendation:** ask for **fewer sections with harder finish
lines**. "Run the preregistered campaign and report the reconciliation" is a
better instruction than "continue the validation program", because the first
has a state where it is done.
