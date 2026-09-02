# COMPUTE / PROCESS HEALTH DOMAIN — v2 §5

Implementation: `csia/v2/domains/compute.py`.

---

## 1. FOUR QUESTIONS, FOUR ANSWERS

§5 asks for four outcomes to be distinguishable. They are four separate
relations, not four levels of one health number:

| relation | question |
|---|---|
| `compute.process_alive` | does the process exist? |
| `compute.process_producing` | is it emitting output? |
| `compute.deadline_met` | did the output arrive in time to be used? |
| `compute.resource_headroom` | does the machine have room to keep doing it? |
| `compute.stability` | queue backlog and restarts |

They are separate because they **fail separately and mean different things**.
A perception process that is alive, producing, and 40 ms late is not "80%
healthy": it is a process whose output is unusable for closed-loop control and
perfectly usable for logging. One scalar destroys exactly the distinction the
function graph needs.

## 2. THE SENTENCE THAT DRIVES THE DESIGN

> A value produced after its deadline should not **automatically** remain
> operationally equivalent to an on-time value. (§5)

Note "automatically". This module does not decide that a late value is
useless. It reports the deadline as violated, and each function says what that
costs via `no_degradation_domains`: `PRECISION_LANDING` and
`PRECISION_NAVIGATION` stop, `LOGGING` continues. Same evidence, two correct
answers, because the requirement is declared per function.

## 3. EVIDENCE BEATS A CLAIM

`alive: true` with a heartbeat older than its declared limit is reported
`VIOLATED` with `COMPUTE_HEARTBEAT_STALE`. The flag is a claim the process
makes about itself; the heartbeat age is an observation. Where they disagree,
the observation wins.

Likewise a reported `deadline_misses` count is honoured even when this tick's
runtime was fine: the platform observed something we did not.

## 4. STATELESS BY CONTRACT

Restart counts, deadline-miss counts and heartbeat ages are **read from the
snapshot**, not accumulated here. A domain that kept counters could not be
replayed from a single snapshot, and replay is what the ledger is for.

## 5. DECLARATIONS

`ProcessSpec` carries the name, the functions it bears on, and its limits:
`heartbeat_limit_s`, `output_age_limit_s`, `deadline_s`, `queue_depth_limit`,
plus `depends_on` (§22). **There is no default deadline**, because a default
deadline is a made-up requirement and a function graph built on made-up
requirements produces made-up eligibility. A process without a declared
deadline is not judged on one, and says so in `unevaluated`.

`ResourceSpec` carries the CPU and memory warn/fail fractions and the
functions the machine's headroom bears on.

Functions attach **per process**: the estimator, the CSIA process and the
logger do not limit the same things.

## 6. WHAT IS NOT MODELLED

- **Scheduling analysis.** No WCET, no priority inversion, no response-time
  analysis. The domain compares an observed runtime to a declared deadline.
- **Memory leak detection.** A fraction is compared to a threshold; a trend
  would need state.
- **Which process caused a CPU overload.** The resource record says the
  machine is saturated; attributing that to one process needs per-process CPU
  attribution the snapshot does not carry. The `compute_timing` relation and
  the declared `depends_on` are what connect a saturated CPU to a late
  channel — as an `AMBIGUOUS` verdict with the CPU as common cause, not as a
  claim that the CPU is at fault.
