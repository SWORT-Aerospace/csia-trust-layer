# CSIA — master system input packet

**For:** whoever designs the system CSIA sits inside.
**Written:** 2026-09-06, at the hardware checkpoint.
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

Confound, recorded and not resolved: ArduPilot is UNAFFECTED and PX4 is
PARTIALLY_AFFECTED (1 of 4 relations live pre-fault).

**Repeated this program, ArduPilot only, on the same pinned build** (ArduCopter
V4.8.0-dev @ `01a504b`, rebuilt from source): 40 of 40 trials valid, the
intermediate quantity present in **20 of 20 fault trials and 0 of 20 matched
controls**, and the original single observation (`first_t` 12.043901 s, 450
ticks) falls inside the repeat's range (12.0399–12.0827, median 12.0432;
449–450 ticks).

**The trust figures above were NOT repeated.** The campaign ran without
`--trust-trace` and captured no trust series (FL-014), so the trust rise still
rests on **n = 1 per platform**. PX4 is `NOT_RUN`, not "no difference".

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

**The five are a finding.** They can be changed with no behavioural assertion
objecting. Three are in `csia/diagnosis/baselines.py` — *the baselines the
Mechanism-B comparison is against*. If a reviewer asks how we know the
baselines are the baselines we describe, the current answer is a file hash.

A sixth finding: the systems paper's `S_0 = 475.6775` is pinned by a test that
reads a **stored artifact**, and nothing re-derives that artifact from the
engine. Change `alpha0` and the test still passes, *because* the artifact is
stale.

Authority: `research/physical_validation/mutation/MUTATION_SURVIVORS.md`.

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
