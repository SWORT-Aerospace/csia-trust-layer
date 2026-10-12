# Software-evidence completion — final report

**Session:** 2026-09-06. **Branch:** `claude/code-reviewer-repo-export-zicovg`
(canonical; see `handoff/BRANCH_DECISION.md`).
**Brief:** close the remaining software-evidence gaps **before** physical
hardware begins.
**Stop point:** the hardware checkpoint, as instructed.

**Tests: 2018 collected, 0 failures** (1939 at the start of the previous
session). `make check-blocking`: **PASS**.

---

## 1. What was asked, and the state of each part

| # | part | state |
|---|---|---|
| 1 | verify HEAD, choose ONE canonical branch | **DONE** — both refs were at `c87a325`; no merge, no rewrite |
| 2 | seal Campaign A1 as immutable, `TRUST_TRAJECTORY: NOT_CAPTURED` | **DONE** |
| 3 | freeze a new A2 preregistration before any trial | **DONE** — `ceeaf4a`, and byte-identical since (now a test) |
| 4 | run A2 with `--trust-trace` | **DONE** — 40/40 VALID, trust captured 40/40 |
| 5 | `ARDUPILOT_MECHANISM_A_REPEAT_TABLE.csv`, 22 named columns | **DONE** — zero `NOT_CAPTURED` cells |
| 6 | `ARDUPILOT_REPEAT_RECONCILIATION.md` | **DONE** — and the disagreement is root-caused |
| 7 | reconstruct the PX4 environment before its prereg may freeze | **DONE** — prereg frozen after, at `1968ffd` |
| 8 | reproduce Mechanism A on PX4 | **DONE** — Campaign P1, 40/40 VALID |
| 9 | adjudicate the five integrity-only mutants, classes A–E | **DONE** — 4 of 5 killed; **one deliberately left open** |
| 10 | `baselines.py` special treatment | **DONE** — and it corrected an earlier finding of mine |
| 11 | investigate S0 reconstruction | **DONE** — `SOURCE_REDERIVABLE`, sensitivity measured |
| 12 | `SCALAR_DERIVATION_GRAPH.yaml` | **DONE** — 13 scalars, 11 with oracles |
| 13 | audit P4/P5/P6/P7 by **running their tests** | **DONE** — P4/P6/P7 PASS, P5 PARTIAL |
| 14 | verify the 12-case invalid-trial matrix, report x/y | **DONE** — **12 of 12**, no manual adjudication |
| 15 | update (not rewrite) the master packet | **DONE** — §F, §G, §K |
| 16 | restructure `USER_ACTION_REQUIRED.md` into three sections | **DONE** |
| 17 | `BIBLIOGRAPHY_HUMAN_VERIFICATION_WORKORDER.md` | **DONE** — 19 entries |
| 18 | remove stale-artifact dependencies that can honestly be re-derived | **DONE** — `ARTIFACT_SUMMARY_ONLY` went 3 → 1 |

Nothing in the brief was skipped. Nothing was faked.

## 2. The campaigns

Three campaigns, **120 trials, 120 VALID**, each preregistered before its first
trial, each arithmetic balancing.

| | platform | n | trust | verdict |
|---|---|---|---|---|
| **A1** | ArduPilot | 20+20 | **`NOT_CAPTURED`** (FL-014) | sealed, not re-run into |
| **A2** | ArduPilot | 20+20 | captured 40/40 | complete |
| **P1** | PX4 SIH | 20+20 | captured 40/40 | complete |

`NOT_CAPTURED` is not `FAIL`, `ZERO`, `UNCHANGED` or `INCONCLUSIVE`. A1 was not
re-run into, amended, or regenerated; A2 is a separate campaign with its own
preregistration and directory.

## 3. The measurements

### 3.1 What reproduces

On **both** platforms, from n=1 to n=20+20: `first_t`, the MISSING tick count,
the gate collapse (20/20 FAULT, 0/20 CONTROL), the nominal hypothesis staying
rank 1, the failsafe transition, and the **direction** of the trust change.

PX4's preregistered qualification reproduces exactly: `gps_gate_weight_sum` is
**1.0, not 3.0**, because only 1 of 4 GNSS-gated relations is live pre-fault on
the passive link. Measured 40/40 instead of argued from one trial. **A cleaner
link was not adopted to improve the number.**

### 3.2 FL-016 — the finding that changes how the headline must be stated

| | FAULT Δ median | CONTROL Δ median | ratio | ranges |
|---|---|---|---|---|
| ArduPilot A2 | **+0.007007** | **+0.020594** | 2.9× | disjoint |
| PX4 P1 | **+0.003513** | **+0.009499** | 2.7× | disjoint |

Trust rises in **both** arms as evidence accumulates. Under the fault it rises
**less**, because the gate closes and the node stops receiving evidence,
freezing the coefficient. **The fault suppresses an ongoing rise; it does not
cause one.**

**This was already in both frozen n=1 artifacts and the comparison was never
made** — ArduPilot control +0.014020 against fault +0.008656, PX4 +0.003332
against +0.001884. Two platforms, two frozen artifacts, the same un-made
comparison. Neither artifact was edited.

### 3.3 FL-017 — the original values are not repeatable, and why

| | original Δ | repeated FAULT range | inside? |
|---|---|---|---|
| ArduPilot | +0.008656 | +0.006996 … +0.007145 | **NO** |
| PX4 | +0.001884 | +0.002269 … +0.003999 | **NO** |

**Root cause, measured.** The original trials ran a **0.5 s** gps stale timeout
— the frozen core's `STALE_TIMEOUT_S` — and the repeats ran **1.0 s**, which
`csia/v1_1/staleness.py` derives from the adapter's own MaxAge (Phase 4.5
Gate B). The frozen core is **byte-identical** between the two commits;
`csia/deploy/shadow.py` changed, deliberately and with its own validation.

Closed further than "the constant differs":

> **dwell ≈ watchdog − channel age at the last usable tick**

| run | watchdog | predicted | measured | residual |
|---|---|---|---|---|
| ArduPilot ORIGINAL | 0.5 | 0.487183 | 0.478777 | −0.008406 |
| PX4 ORIGINAL | 0.5 | 0.387800 | 0.400208 | +0.012408 |
| ArduPilot A2, n=20 | 1.0 | 0.993714 | 0.999657 | +0.005943 |
| PX4 validation pair | 1.0 | 0.907148 | 0.919577 | +0.012429 |

Every residual inside one tick period (0.04 s), across two platforms and both
watchdog values — so it is not fitted to the case it explains.

**Neither run is wrong.** The repeats repeated a different deployment
configuration, and **neither preregistration named the watchdog as a pinned
field**. That omission is the finding.

### 3.4 The PX4 pre-fault difference, attributed by a controlled experiment

PX4 had one symptom ArduPilot did not: its **pre-fault** trust also failed to
reproduce (0.985624 → 0.952172), where ArduPilot's was stable (0.924639 →
0.924816).

`tools/csia_experiment/watchdog_replay.py` drives the **same committed log**
through the **same frozen core** twice, changing only the stale-timeout table:

| log replayed | under 0.5 s | under 1.0 s |
|---|---|---|
| the original n=1 log | **0.986420** | **0.952526** |
| a P1 repeat log | **0.985924** | **0.949056** |
| *measured* | *artifact **0.985624*** | *P1 **0.952172*** |

**Both logs reproduce both values.** The link state itself reproduced — same
channels usable at the same shares, same live relation count, same gates — so
the other obvious explanation is ruled out.

### 3.5 FL-019 — an unresolved mechanism, labelled

**Why ArduPilot's pre-fault trust was stable across the same change is not
established.** The replay that settles PX4 is **not a valid instrument on
ArduPilot**: it gives 0.979440 and 0.941275 against a measured 0.924639 and
0.924816, wrong by 0.055 and 0.017 and in a direction the flights did not show.
The hand-off reconstruction under-counts when consecutive readings repeat, and
ArduPilot's higher channel rates make that bias much larger.

A hypothesis is recorded **as a hypothesis** (ArduPilot's channels are usable
~100% of the time so a longer timeout changes nothing; PX4's baro sits at ~50%
and its battery and vibration at ~24%). A test asserts the replay **still
fails** on ArduPilot, so the limit cannot lapse silently.

## 4. Mutation adjudication — the count is the least useful number in it

| mutant | was | now | class |
|---|---|---|---|
| `TIMING-04`, `SUPPORT-04`, `DIAGNOSIS-04` | integrity-only | **KILLED** | **A** — a pre-existing test was **missing from my selection** |
| `EVIDENCE-05` | integrity-only | **KILLED** | **B** — oracle written *after* the mutant was known |
| `CONFIGURATION-02` | integrity-only | **integrity-only** | **C** — **deliberately left open** |
| `SUPPORT-01` | invalid | invalid | **D** — the core refuses to import |

**My earlier finding was partly wrong and the wrong paragraph is kept, not
edited.** `MUTATION_SURVIVORS.md` §2–4 said the answer to "how do we know the
baselines are the baselines you describe" was "a file hash". It was not:
`tests/test_shared_power_baselines.py` existed and asserted the constants. That
is a **measurement error in the campaign**, not a coverage gap in the suite,
and the two look identical in the output.

`CONFIGURATION-02` was left integrity-only on purpose. Writing a test for it now
would make the count 5 of 5 and measure nothing.

The adjudication also names a category the runner collapses: a **value
assertion** (a constant compared to a literal) is stronger than a file hash and
is **not** behavioural.

## 5. Component audit — by running the tests, not by observing files exist

| part | verdict | evidence |
|---|---|---|
| **P4** orchestrator + validity predicates | **PASS** | 29+14+3 tests, and it drove all three campaigns |
| **P5** fault injector | **PARTIAL** | protocol and simulated backend pass; the real serial injector **refuses to construct** |
| **P6** invalid-trial matrix | **PASS** | **12 of 12**, no manual adjudication, with both controls |
| **P7** preregistration | **PASS** | freeze order checkable from git; blob identity now a test |

P5's PARTIAL is correct behaviour, not a defect: a stub would manufacture E2 and
E3 numbers indistinguishable from measurements downstream.

## 6. Scalar provenance

| | at session start | now |
|---|---|---|
| scalars | 11 | **13** |
| `ARTIFACT_SUMMARY_ONLY` | 3 | **1** |
| with an oracle that closes the loop | 6 | **11** |

Closed: `S_0`, `T_0`, `mass_term_118_82`, `shared_power_baseline_verdicts`,
`mechanism_a_first_t_ardupilot`, `trust_rise_ardupilot`, `trust_rise_px4`.

**A correction found while closing `S_0`:** the field named `settled_mass_S0` is
**not settled** at n = 1500 (475.68 → 498.79 by n = 3000, cap 500). The *trust*
is settled; the mass is not, and `S_0` must be quoted with `n_steps`. 118.82 is
unaffected and the artifact was **not** rewritten.

Still open: `independent_checker_agreement` is the last artifact-summary-only
scalar, `cusum_latencies` is re-derivable with no oracle written, and **this
file is still hand-compiled** — the largest remaining defect in it, and it did
not shrink this session.

## 7. What this session did NOT establish

* **Nothing above E1.** 120 simulator runs are not evidence about hardware.
  Every tier from E2 up is NOT STARTED.
* **No pooling** — across platforms, or across ORIGINAL / A1 / A2 / P1.
* **No p-values, no confidence intervals.** Deterministic simulator, seed and
  timing jitter, not draws from a population.
* **No prevalence claim.** Nothing says how often GNSS fix loss occurs.
* **No timing claim.** Latency recorded and deliberately not adjudicated on a
  shared host; PX4's real-time lockstep makes its figures even less comparable.
* **Nothing about a driven-link PX4 configuration.** A separate experiment
  needing its own preregistration.
* **FL-019 is open.**
* **Zero bibliography entries are publisher-verified.** The proxy answers 403 at
  CONNECT for every publisher host; no further engineering time was spent there.
* **Four freeze tags are still local-only**, so the tag-diff test skips on a
  fresh clone.

## 8. What comes next, in order

1. **A board.** E2 is the only thing that changes what either manuscript may
   say. `USER_ACTION_REQUIRED.md` §A.
2. **The writing agents restate the trust claim with the control arm**, in the
   three places that carried the old phrasing. The evidence is ready; the prose
   decision is not the repository agent's.
3. **A reviewer picking their own mutants**, and specifically attacking
   `CONFIGURATION-02`.
4. **Independent replication.** Everything here ran on one host, in one
   container, driven by one agent. Both builds are pinned. Nobody has re-run
   them.

---

**The rule this session was held to:** do not optimise the story, optimise the
evidence chain. The two findings that most changed what may be said —
FL-016 and FL-017 — both make the headline weaker and more precise, and both
were found by running a control arm and asking why a number disagreed rather
than by looking for a result.
