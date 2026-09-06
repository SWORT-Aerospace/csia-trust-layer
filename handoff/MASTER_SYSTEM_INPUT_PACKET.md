# CSIA — master system input packet

**For:** whoever designs the system CSIA sits inside.
**Written:** 2026-09-06, at the hardware checkpoint.
**Updated:** 2026-09-06, after the software-evidence completion pass — §F, §G
and §K carry new measurements, including one that **corrects how §G's headline
must be stated**. Nothing was removed; the superseded readings are named as
superseded rather than deleted.
**Authority:** where this document and an artifact disagree, **the artifact
wins**, and the artifact is named in every section.

This packet is deliberately not a summary of achievements. It is the set of
facts a designer needs in order to not build on something that is not there.
Sections **N** and **O** are the ones to read first if you read only two.

---

## A. What CSIA is, in terms that survive review

A **diagnostic layer**. It consumes sensor telemetry from a vehicle, compares
quantities that are physically related to each other, and emits statements
about which sensors and which functions are trustworthy.

It is **not** a controller, **not** an estimator, and **not** a replacement for
an autopilot's own failsafe. It runs beside those and produces an opinion.

The one property that distinguishes it from an ordinary health monitor is what
it refuses to say: it is built to report *unassessable* rather than *healthy*
when the evidence a judgement would need is not there.

## B. The frozen scientific core

Six paths are **frozen** — read, run and replayed, never edited:

```
csia/trust_engine   csia/diagnosis   csia/runtime/online.py
csia/runtime/failsafe.py   csia/scenarios.py   csia/profiles.py
```

Frozen means: byte-identical to tag `csia-v1.0-research-final`, checked two
ways — a tag diff, and a recorded-hash file that works without git history.

**The tag is LOCAL ONLY.** The push was refused HTTP 403; the remote carries
only `v0.7.0`. On a fresh clone the tag-diff test *skips*, which reads as
green. This is blocker **O-1**.

Authority: `research/physical_validation/EVIDENCE_EXTENSION.yaml`,
`tests/test_v1_frozen.py`.

## C. Terminology that must not drift

| use | do not use | why |
|---|---|---|
| **normalised hypothesis weight** | "posterior", "probability" | the deployed output departs from a Bayes posterior in four documented ways: an `EPS = 0.02` floor inside the log, EWMA smoothing (`SMOOTH_ALPHA = 0.06`, ~15 ticks), `EVIDENCE_MULT = 1.5` tempering, and a softmax over a **table-asserted** hypothesis set |
| **validity factor** (`w_h`) | "weight" unqualified | overloaded against the trust-engine's own `w_phys`/`w_stat`/`w_temp`/`w_nbr` |
| **trust coefficient** | "confidence" | **"confidence" is forbidden**: it names at least four different quantities in this field, and a claim using it is not checkable |
| **unassessable** | "unknown", "degraded" | it is a third state, not a shade of the other two |

The math paper's `q_h`/`p_h` **are** posteriors and are correctly named; the
deployed quantity is not the same object.

Authority: `tests/test_manuscript_terminology_lint.py`.

## D. What CSIA outputs

Per tick, at a configured rate (25 Hz in every committed campaign):

* a **trust coefficient** in [0, 1] per sensor node;
* a **failsafe level** recommendation (NORMAL / CAUTION / …), with the
  conditions that produced it;
* a **hypothesis report**: ranked candidate causes with normalised weights, an
  `UNKNOWN` hypothesis, and per-source usability;
* **function eligibility**: which vehicle functions the evidence currently
  supports a judgement about.

## E. What CSIA does not do — enforced structurally, not by configuration

**CSIA has no command path to the autopilot in any mode.** This is not a
setting. `csia/deploy/shadow.py` half-closes the write side of the socket, and
every run records a live probe of the denial:

```
command authority: NO_COMMAND_PATH_REACHABLE (write_half=CLOSED_ENOTCONN)
live transmit probe: command_long_send: denied; set_mode_send: denied;
                     rc_channels_override_send: denied
```

`RUN_MODES` contains no mode with command authority, and a deployment config
declaring one is refused at load. A master system must supply its own actuation
authority; CSIA will never provide it.

## F. Evidence tiers — where the evidence actually is

| tier | meaning | status |
|---|---|---|
| **E0** | desktop simulation | complete |
| **E1** | current-stack SITL/SIH | complete; **repeated 20+20 on ArduPilot** this program, PX4 still n=1 |
| **E2** | real flight-controller hardware | **NOT STARTED** — needs purchase (**O-4**) |
| **E3** | real sensor + physical fault | NOT STARTED |
| **E4** | physical actuator/output path | NOT STARTED |
| **E5** | controlled physical flight | NOT STARTED |

**Nothing above E1 exists.** Any claim about hardware, real sensors or flight
is unsupported today. `PAPER_IMPACT_LEDGER.yaml` records, per result, what it
licenses and — in the load-bearing field — what it does **not**.

**E1 is now closed as far as software can close it, and E2 is the checkpoint.**
Two ArduPilot campaigns (A1: 40 trials, no trust; A2: 40 trials, trust
captured) and a preregistered, built, `NOT_RUN` PX4 campaign. Repeating a
simulation a third time produces more simulator runs, not a tier change.
**The next thing that changes what either manuscript may say is a board**, and
the software waiting for it is listed in `USER_ACTION_REQUIRED.md` §A-2.

## G. The headline mechanism, and the number that matters

A deployed diagnostic layer emitted health while holding no evidence it was
entitled to assert health from, because its gate **skipped** an inapplicable
feature instead of marking it unassessable.

Measured across a GNSS fix-loss fault on both current-stack platforms:

| | ArduPilot 4.8 | PX4 SIH |
|---|---|---|
| `gps_gate_weight_sum` | 3.0 → **0.0** | 1.0 → **0.0** |
| trust coefficient | 0.9213 → **0.9300** | 0.9856 → **0.9875** |
| nominal hypothesis rank | 1 | 1 |

**Trust RISES as the gate collapses, on both platforms.** That is not a bug:
removing an inconsistent comparison removes a source of disagreement, and a
layer scoring agreement scores higher with less to disagree about. A master
system must not assume that a falling trust value is the signal of a lost
sensor. **The signal is the gate weight, not the trust.**

**AND THE SENTENCE ABOVE IS MISLEADING WITHOUT THE CONTROL ARM (FL-016).**
Campaign A2 measured both arms, n = 20 each, and the **control arm rises about
three times more** than the fault arm — Δ median **+0.020594** against
**+0.007007**, ranges completely disjoint. Trust rises in **both** arms as
evidence accumulates over a flight. Under the fault it rises **less**, because
the gate closes and the node stops receiving evidence, **freezing** the
coefficient at whatever it had reached. **The fault suppresses an ongoing rise;
it does not cause one.** This was already visible in the frozen n = 1 artifact —
control +0.014020 against fault +0.008656 — and the arm-to-arm comparison was
never made.

For a master system the practical rule is unchanged and is now better founded:
**do not read the trust value at all as a lost-sensor signal.** It neither
falls nor rises distinctively; it stops moving.

Confound, recorded and not resolved: ArduPilot is UNAFFECTED and PX4 is
PARTIALLY_AFFECTED (1 of 4 relations live pre-fault).

**Repeated this program, ArduPilot only, on the same pinned build** (ArduCopter
V4.8.0-dev @ `01a504b`, rebuilt from source): 40 of 40 trials valid, the
intermediate quantity present in **20 of 20 fault trials and 0 of 20 matched
controls**, and the original single observation (`first_t` 12.043901 s, 450
ticks) falls inside the repeat's range (12.0399–12.0827, median 12.0432;
449–450 ticks).

**The trust figures were repeated on ArduPilot, in a SECOND campaign.** The
first (A1) ran without `--trust-trace` and captured no trust series at all
(FL-014) — `NOT_CAPTURED`, which is not `FAIL`, `ZERO` or `UNCHANGED`. A1 is
sealed and was not re-run into. **Campaign A2** repeated it with the
instrument on: 40 of 40 valid, trust captured in 40 of 40.

| ArduPilot, A2, n = 20 per arm | PRE | POST | Δ median | Δ range |
|---|---|---|---|---|
| FAULT | 0.924816 | 0.931823 | **+0.007007** | +0.006996 … +0.007145 |
| CONTROL | 0.924813 | 0.945407 | **+0.020594** | +0.020572 … +0.020804 |

**PX4 is still `NOT_RUN`** — not "no difference". Its repeat is preregistered
and its binary is built.

**DO NOT QUOTE `0.9213 → 0.9300` AS A REPEATABLE VALUE.** Its Δ (+0.008656) is
outside the repeated FAULT range, and the reason is measured (FL-017): the
original trial ran a **0.5 s** gps stale timeout — the frozen core's
`STALE_TIMEOUT_S` constant — and both repeats ran **1.0 s**, the value
`csia/v1_1/staleness.py` derives from the adapter's own MaxAge (Phase 4.5
Gate B). The gate therefore held 0.48 s in the original and 1.00 s in every
repeat, trust accrued for twice as long, and froze higher. The frozen core is
byte-identical between the two runs; the **driver** changed, deliberately.

**Neither run is wrong. They are different deployment configurations, and
neither preregistration pinned that field.** For a master system the lesson is
the durable one: **the runtime stale-timeout source is part of the
configuration a result is quoted against**, exactly like the tick rate in §I.
Every other headline quantity — `first_t`, tick count, gate collapse,
hypothesis ranks, failsafe transition — reproduces, because none of them
depends on how long the gate holds.

Authority: `research/physical_validation/ARDUPILOT_REPEAT_RECONCILIATION.md`,
which compares twelve headline quantities across all three campaigns.

Support state is **NOT RECORDED** in the original Mechanism-A artifacts —
grepping them for `support` and `eligib` returns nothing. Do not state one.

## H. Vehicle integration boundary

A new airframe on a **supported autopilot** is integrated by writing a
`profiles/*.yaml` file. The frozen core is unchanged, and a test performs the
whole integration and then verifies the core byte-identical afterwards.

**A new transport** — DroneCAN, ROS 2, a bespoke serial frame — needs a new
adapter class. "CSIA plugs into any vehicle" is **false**.

`csia-edge validate --profile <p>` answers, before anything is connected, which
diagnostic relations the airframe can feed and which it will be blind to. On a
single-IMU board that answer includes 7 of 11 relations structurally out.

## I. Configuration surface — two files, and an asymmetry

| | `profiles/*.yaml` | `configs/vehicle/*.yaml` |
|---|---|---|
| answers | what the airframe provides | how to connect, how the run is recorded |
| may set a diagnostic parameter | **no — refused at load, any depth, any spelling** | **two, and they are declared** |

The two the deployment config routes into the frozen core, measured by
following the call and not inferred from names:

* `csia.tick_hz` → `OnlineTrustLayer(tick_hz=)`. The smoothing is an EWMA over
  **ticks**, so the tick rate sets the smoothing **time constant**. 25 Hz and
  10 Hz are not the same detector.
* `csia.field_mode` → `OnlineTrustLayer(field_mode=)`.

`csia.profile` looks like a third and is not: it reaches the flight-log header
only. It is a provenance label.

Authority: `docs/VEHICLE_PROFILE_VS_DEPLOYMENT.md`.

## J. Campaign discipline a master system inherits

* **COMMAND ISSUED ≠ FAULT INJECTED.** A six-stage evidence chain, each stage
  satisfied by a measured number. A trial whose intervention cannot be
  evidenced is `INVALID_SCENARIO` — **not** a detector miss.
* **RULE A:** every instrument has a null control. A control arm that moves
  makes *every* arm unreadable.
* **RULE B:** no mechanism attribution without the intermediate quantity.
* **Eight trial states**, each decided by a machine-executable predicate, and
  `planned = valid + invalid + not_attempted` must balance or the report
  raises rather than printing.
* **Manifests are written once**, content-hashed, no force flag.

Authority: `tools/csia_experiment/`, `csia/simulation/contract.py`.

## K. Verification — and what is NOT pinned

24 deliberate mutations of the scientific core, run in a git-worktree sandbox:

| | |
|---|---|
| killed by a behavioural test | **18** |
| killed **only** by a file-hash guard | **5** |
| invalid (the program will not run) | 1 |
| survived entirely | 0 |

**The five were a finding, and four are now closed. The count is 4 of 5, not
5 of 5, and the difference between the two numbers is the point.**

| mutant | was | now | why the new verdict is worth what it is |
|---|---|---|---|
| `TIMING-04`, `SUPPORT-04`, `DIAGNOSIS-04` | integrity-only | **KILLED** | **a pre-existing test was missing from the campaign's hand-picked selection.** A measurement error in the campaign, not a coverage gap in the suite |
| `EVIDENCE-05` (`alpha0`) | integrity-only | **KILLED** | by an oracle **written this session**, with the mutant already known. Records that the gap is closed; does **not** measure the suite as it stood |
| `CONFIGURATION-02` (`imu_isolation_gap`) | integrity-only | **integrity-only** | **deliberately left open.** Writing a test for it now would move the count to 5/5 and measure nothing |
| `SUPPORT-01` | invalid | **invalid** | the core validates its hypothesis catalogue at import and **refuses to run**. Stronger than any test — and it never reached the suite, so it is not a kill |

**THE DISTINCTION A MASTER SYSTEM SHOULD INHERIT**, because it is the reason
these numbers mean anything:

* **behavioural** — a test drives the code and asserts what it *does*;
* **value assertion** — a test reads a constant and compares it to a literal.
  Stronger than a hash (it survives reformatting) and **not** behavioural;
* **integrity guard** — a file hash or tag diff. Fires identically on a
  reformatted comment. Stops a change reaching a commit and establishes nothing
  about behaviour.

The three baseline mutants above are killed by a **value assertion** that
pre-dates them and by a **behavioural** re-derivation written after; they are
credited to the first. Reading all three categories as "a test failed" is what
made the original campaign's output ambiguous.

`S_0 = 475.6775` was the sixth finding — pinned by a test that read a **stored
artifact**, so `alpha0` could change 100× with the test still passing *because
the artifact was stale*. It now re-derives from the frozen engine, and the
oracle's sensitivity is **measured**: `alpha0` 8 → 80 → 800 gives `S_0` 475.6775
→ 479.2514 → 514.9906. A correction found while closing it: the field named
`settled_mass_S0` is **not settled** at n = 1500 (475.68 → 498.79 by n = 3000,
cap 500). The *trust* is settled; the mass is not, and `S_0` must be quoted with
`n_steps`. 118.82 is unaffected and the artifact was not rewritten.

Authority: `research/physical_validation/mutation/MUTATION_ADJUDICATION.md`
(per-mutant, with the classes), and `MUTATION_SURVIVORS.md` (the original
campaign, including the paragraph this correction contradicts, kept).

**Where every headline number comes from:**
`research/physical_validation/SCALAR_DERIVATION_GRAPH.yaml` — 12 scalars, 9
with an oracle that closes the loop, 2 still `ARTIFACT_SUMMARY_ONLY`, and one
(`cusum_latencies`) named as re-derivABLE with no oracle written, which is a
plan rather than a check.

**Component status, audited by running the tests rather than by observing that
files exist:** `research/physical_validation/P4_P7_STATUS_AUDIT.md` — P4 PASS,
P5 **PARTIAL** (the real serial injector refuses to construct; there is no
board, and a stub would manufacture E2 numbers), P6 PASS (12 of 12
invalid-trial causes classified with no manual adjudication), P7 PASS.

## L. The standards candidate (DEA)

An implementation-neutral **Diagnostic Evidence Assurance** profile. Core
property:

> A diagnostic layer shall not assert a unique attribution unless it holds
> active evidence separating the asserted hypothesis from every other
> hypothesis its own model admits. **A ranking is not a separation.**

It deliberately does **not** standardise "gate closure shall lower trust" —
§G shows why that rule would fail a correct implementation.

Ten requirements, four verdicts (`PASS`/`FAIL`/`INAPPLICABLE`/`INCONCLUSIVE`),
**no score**. A conforming non-CSIA reference exists in a different domain
entirely; eight deliberately bad references must each be rejected, and every
requirement must be violated by at least one of them.

**Status: CANDIDATE.** Not submitted to any body, not endorsed by one.

Authority: `standards/dea/DEA_PROFILE.md`.

## M. Timing and resource envelope

Measured through the full v1.1 stack on ArduPilot SITL: median ≈ 947 µs/tick,
p99 ≈ 1294 µs, against an R13 budget of 2000 µs.

**These numbers are from a contended container**, and the driver's own
host-noise control — constant work, same process — measured a *higher* median
than the real tick. **No timing claim may be made from this session's
campaign.** A master system needing a deadline guarantee must re-measure on its
own target.

## N. Known limitations, ranked by what they cost

1. **No evidence above E1.** Nothing about hardware, sensors or flight.
2. **The baselines are not behaviourally pinned** (§K).
3. **Zero bibliography entries are verified** (§O-2) — neither manuscript can
   be submitted.
4. **A new transport needs a new adapter** (§H).
5. **Trust rises across a gate collapse** (§G) — a master system reading trust
   as the loss signal will read it backwards.
6. **PX4 SIH publishes no `SCALED_IMU2`**, so `imu1` and the dual-IMU
   cross-check cannot be evaluated there at all. ArduPilot and PX4 results are
   never pooled.
7. **The freeze tags are local only** (§O-1).
8. **Support state is unrecorded** in the original Mechanism-A artifacts.

## O. Blockers that require a human

Full detail in `USER_ACTION_REQUIRED.md`.

| id | blocker | consequence |
|---|---|---|
| **O-1** | four freeze tags exist only on one machine (push refused 403) | the freeze test *skips* on a clean clone, which reads as green |
| **O-2** | 0 of 19 bibliography entries verified; publisher hosts answer 403 at CONNECT | **neither manuscript can be submitted** |
| **O-3** | unify the two config files, or keep them separate | unifying changes every flight-log header hash and orphans committed trial manifests |
| **O-4** | hardware purchase for E2+ | every tier above E1 stays NOT_STARTED |
| **O-5** | flight-site authorisation and independent pilot authority | E5 unreachable regardless of purchase |

## P. Interfaces a master system would use

| interface | what it gives | stability |
|---|---|---|
| `csia-shadow --config <deployment>` | the runtime. Reads telemetry, writes a flight log, commands nothing | mature |
| `csia-edge validate --profile <p>` | pre-flight: what this vehicle can and cannot be diagnosed for | new this program |
| `csia/v1_1` output API | the per-tick trust/hypothesis/eligibility record | versioned |
| flight log | the record. Header carries the config hash, the frozen-core tag and the adapter version | format frozen |
| `tools/csia_experiment/` | campaign planning, adjudication, immutable manifests | new this program |
| `tools/dea/conformance.py` | conformance runner for the candidate profile | candidate |

**There is no API by which a master system can ask CSIA to act.** §E.

---

## NEXT MASTER DESIGN TARGETS

Ordered by what unblocks the most. Each is stated as a decision, not a wish.

1. **Decide the E2 purchase (O-4).** It is the smallest step that changes what
   either manuscript may say. Everything in tiers E2–E5 is behind it, and no
   amount of further software work substitutes.
2. **Resolve the bibliography (O-2)** or accept that neither paper is
   submittable. This is the single hardest blocker and no agent in this
   environment can clear it.
3. **Pin the baselines behaviourally (§K).** Not by writing tests aimed at the
   five surviving mutants — by writing the test that asserts what the baseline
   detectors *do*, derived from the Mechanism-B comparison the paper makes.
   That test kills them incidentally, which is the difference between
   strengthening evidence and gaming a metric.
4. **Close the artifact-mediated numeric bindings (§K).** Re-derive
   `settled_mass_S0` from the live `TrustCore` and compare to the artifact, so
   an engine change invalidates the artifact instead of being invisible to it.
   Then survey how many other `research/*/results/*.json` bindings have the
   same shape.
5. **Decide O-3**, and record the decision either way. Leaving it open is
   itself a cost: two files that can disagree eventually will.
6. **Push the freeze tags (O-1).** Cheap, and it converts a skipping test into
   a running one.
7. **If a master system will consume trust:** design against the gate weight,
   not the trust coefficient, and read §G before writing any threshold.
8. **If DEA is to be pursued:** it needs adversarial review by someone who did
   not write it, and the four open questions in `DEA_PROFILE.md` §10 need
   answers — particularly the open-world hypothesis set, which DEA-6 currently
   cannot express.
