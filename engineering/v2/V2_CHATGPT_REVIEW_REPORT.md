# CSIA v2 — CROSS-SYSTEM ASSURANCE ARCHITECTURE: ENGINEERING REVIEW REPORT

Engineering only. **No novelty is claimed** (§39). Modularity and cross-domain
monitoring are ordinary product architecture; research novelty remains a
separate workstream and nothing here contributes to it.

The twenty items §40 asks for are §§1–20 below. §21 answers §38's product
question. §22 is what is still wrong.

| | |
|---|---|
| frozen v1 | `csia-v1.0-research-final` @ `ec5acd189295dab9259d4989657d42184d6142a3` — **zero diff** |
| v1.1 | unchanged; output schema `1.1.0` unchanged |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| V2A | `ecfb0ca` framework, six domains, two profiles, specs, tests |
| V2B | `e05c9c8` this report and the run artifacts |
| tests | 1211 → **1,388** (177 new, all v2) |
| documents | 18 specs in `engineering/v2/` + this report |

---

## 1. ARCHITECTURE

The product abstraction moves from SENSOR ASSURANCE to SYSTEM FUNCTION
ASSURANCE. The question becomes: *which functions of this system remain
justified right now, on what evidence, and what domain is limiting them?*

```
  raw platform signals                  v1.1 output payload (schema 1.1.0)
          |                                          |
          v                                          v
  +-------------------------------------------------------------------+
  |  DOMAIN PLUGINS   POWER  COMPUTE  TIMING  COMM  ACTUATION          |
  |                   SENSOR = the v1.1 wrapper                        |
  +-------------------------------------------------------------------+
          |  EvidenceRecord: categorical verdict + OPTIONAL numbers
          v
  +-------------------------------------------------------------------+
  |  FUNCTION GRAPH     which functions are still justified            |
  |  ATTRIBUTION        UNIQUE / AMBIGUOUS / UNSUPPORTED / NO_EVIDENCE |
  +-------------------------------------------------------------------+
          |
          v
  SYSTEM  +  per domain  +  per function  +  WHAT LIMITS EACH FUNCTION
          |
          v
  the autopilot / controller decides what to DO about it     (§33)
```

**Why not more nodes in the existing graph** (§1). The v1 trust core is a Beta
recursion over *cross-sensor consistency*: two sensors that should agree, and
a residual saying whether they do. That model has content because "these two
measure the same physical quantity" is true of a sensor set. It is not true of
a power rail. A 5 V rail is not *inconsistent* with a CPU load; it is inside or
outside a datasheet band, and that is a threshold comparison, not a
likelihood. Forcing it through the recursion would produce a number that looks
like a trust and means nothing — which is what §18 exists to prevent.

So a domain is a plugin. The eight-node sensor graph stays eight nodes and
stays v1.1's.

## 2. PLUGIN CONTRACT

`csia/v2/domain.py`, `csia/v2/registry.py`. Spec: `DOMAIN_PLUGIN_SPEC.md`.

Seven declarations — `domain_id`, `schema_version`, `required_inputs`,
`optional_inputs`, `relations`, `affected_functions`, `reason_codes` — and one
method, `evaluate(snapshot) -> DomainResult`.

§2 proposed `observe()`, `evaluate()` and `evidence()` as separate calls and
said not to commit to names before reviewing the v1.1 APIs. Having reviewed
them, the three collapsed into one: splitting them would require the plugin to
hold state between calls, and holding state is what the determinism
requirement forbids. A domain that could not be replayed from a single
snapshot would make the ledger unreplayable too.

`DomainResult` carries `records` **and `unevaluated`** — what could not be
assessed and why. That second field is not decoration: a domain that silently
skips a relation looks identical to one that found it healthy.

The registry (§21) refuses, loudly and never as a warning: an unknown or
duplicate `domain_id`, a foreign schema major, no relations, no affected
functions. `domains()` returns them **sorted by id**, so two hosts that
registered the same plugins in different orders produce the same evidence
sequence and the same ledger — asserted directly by a test.

**Determinism is part of the contract.** No clock, no RNG, no network, no
global state, no accumulation between ticks. Restart counts and deadline-miss
counts are read from the snapshot, not counted here. Where a domain would want
history — jitter, a filtered no-load voltage reference — the host supplies it
as a signal, which keeps the filtering where the host already does it.

## 3. THE v1.1 WRAPPER

`csia/v2/domains/navigation.py`. Spec: `V1_1_NAVIGATION_PLUGIN_SPEC.md`.

It consumes the **published payload** through the same strict parser the
external monitor uses, and transcribes it. It imports no v1.1 producer — not
the trust engine, not the diagnosis, not the eligibility policy — and a test
parses its import graph to prove it.

That is the §36 guarantee, and it is structural rather than careful: **the
wrapper cannot alter a v1.1 verdict because it has no way to compute one.**

Four supporting properties:

1. the state map is a **bijection** — four states in, four out, nothing merged
2. `v1_1.source_health` records carry `affected_functions = ()`, so a low
   trust reading cannot degrade a function v1.1 called eligible
3. the transcribed verdict, the support statement and the aggregate are
   `attributable=False` — evidence, never cause candidates
4. the profile lists SENSOR as **required** and **not** no-degradation, so the
   roll-up can neither soften nor harden what v1.1 said; a test asserts both
   against the table so the guarantee cannot be lost by editing it

§17 and §36 look contradictory and are not. `domain_states["SENSOR"]` **is**
v1.1's verdict, unaltered and always visible; the v2 function of the same name
is the roll-up over every required domain, of which SENSOR is one.

## 4. POWER DOMAIN

`csia/v2/domains/power.py`. Spec: `POWER_DOMAIN_SPEC.md`.

Six relations: `source_health`, `p_equals_vi`, `droop_vs_current`,
`cell_balance`, `rail_tolerance`, `load_current_response`. Nothing here is
novel — Joule's law, a datasheet band, Ohm's law across an internal
resistance.

**The relation worth having is §28-B.** "POWER: FAULT" tells an operator
nothing they can act on; "the battery is fine and the thing between it and
your sensors is not" tells them where to go. It requires two design choices:
the source is monitored *separately* from the rails it feeds, and a healthy
source emits an **affirmative** NOMINAL record. Silence cannot exonerate
anything, so `power.source_health` emits on every good tick.

The exoneration is conditional, and a test checks the negative case: with the
source itself drooping, the rail gets no distribution finding. A rule that
always fires is not a finding.

The load relation is **one-sided on purpose**: current far below the expected
draw is a power-path finding; current above it is a mechanical finding (§8),
and claiming it here would count one event against the wrong domain.

**A defect corrected during the build.** The first version attached every rail
to every function. On a 5 V regulator failure it reported total loss of a
vehicle whose IMUs run off 3V3 and whose motors run off the battery — a
vehicle that could still navigate inertially, log, and fly home. Rails now
declare what they feed, and a test holds it in place.

## 5. COMPUTE DOMAIN

`csia/v2/domains/compute.py`. Spec: `COMPUTE_DOMAIN_SPEC.md`.

§5's four questions are four separate relations — alive, producing, on time,
resourced — plus stability. They are separate because they fail separately and
mean different things. A process that is alive, producing and 40 ms late is
not "80% healthy"; it is unusable for closed-loop control and fine for
logging.

§5's key word is **automatically**: "a value produced after its deadline
should not *automatically* remain operationally equivalent". This module
reports the deadline as violated and does not decide what that costs. Each
function decides, via `no_degradation_domains`. The same evidence stops
`PRECISION_NAVIGATION` and leaves `LOGGING` untouched.

`alive: true` with a stale heartbeat is reported VIOLATED. The flag is a claim
the process makes about itself; the heartbeat is an observation, and where
they disagree the observation wins.

**There is no default deadline.** A default deadline is a made-up requirement,
and a function graph built on made-up requirements produces made-up
eligibility. A process without a declared deadline is not judged on one and
says so.

## 6. TIMING DOMAIN

`csia/v2/domains/timing.py`. Spec: `TIMING_DOMAIN_SPEC.md`.

v1.1's staleness watchdog answers "is this too old to use?". It cannot answer
§6's question: *the value is late — where did the time go?*

Four stamps partition the delay into segments with different owners:
`SENSOR_SLOW`, `TRANSPORT_DELAY`, `PROCESSING_DELAY`, `DECISION_DELAY`. One
`age` field is the sum of all four and identifies none of them, and the same
60 ms sends you to the sensor, the network, the CPU or the scheduler.

**Only a segment over its own budget is named.** The largest share of an
acceptable total is not a finding, and reporting it as one trains an operator
to ignore the domain. When the end-to-end deadline is missed with every
segment inside budget, `classification` is `null` and the report says the
total failed with nothing to blame — which is the honest answer to a channel
whose budgets sum to more than its deadline.

**Clock consistency is checked first, and stops everything.** A stamp ordering
that cannot happen physically is `TIMING_CLOCK_INCONSISTENT` and **no latency
is computed at all**. Negative latencies get averaged into fake headroom;
publishing arithmetic on stamps just shown to be untrustworthy would be worse
than publishing nothing.

## 7. COMMUNICATION DOMAIN

`csia/v2/domains/communication.py`. Spec: `COMMUNICATION_DOMAIN_SPEC.md`.

> Do not treat link failure as sensor failure. (§7)

In v1.1 a receiver that stops being heard becomes a stale source, and within
the sensor domain that is correct: from inside it, "the receiver died" and
"the link dropped" are the same observation. v2 distinguishes them only
because the link is monitored separately and emits its own evidence.

A dead link is **not also** judged on rate, loss, integrity and queue — zero
messages over a dead link is one finding reported five times, and
double-reporting makes one fault look like several. Rate and loss are measured
independently, because a link can hold its rate while dropping every third
message and can fall below rate with no loss at all.

Transport-agnostic by construction: `transport` is free text carried into the
record, nothing branches on it, and a test asserts identical verdicts across
CAN-FD, DDS, SPI and an unspecified label on identical signals.

## 8. CROSS-DOMAIN RELATIONS

`csia/v2/attribution.py`. Spec: `CROSS_DOMAIN_RELATION_SPEC.md`.

Four declared for the aircraft profile: `actuation_power.demand_vs_current`,
`compute_timing.saturation_vs_latency`, `comm_sensor.link_vs_source`,
`power_sensor.shared_rail`. Two for the test stand. They are data — listed in
`declarations()`, carried into the API document, reviewable.

§14 also names FIRMWARE + TIMING. It is **not declared**, because the firmware
domain is not built and a relation whose firmware side can only ever be
`UNSUPPORTED` would add an entry to every timing fault and teach an operator
to ignore the field.

**Common cause is reachability, not adjacency.** A rail feeds a converter
feeds a bus feeds a sensor; the sensor declares the bus and nothing declares
the rail twice, so counting direct dependencies would miss exactly the case
§28-E is about. The walk is over the host's declared graph, cycle-safe, with
ties broken on node id.

A shared dependency that is **healthy** is never offered as a common cause.
The battery feeds everything and is reachable from every candidate; when it
reads nominal the honest conclusion is that it has been exonerated.

## 9. SYNTHETIC TEST RESULTS — §§27, 28

Spec: `V2_SYNTHETIC_SCENARIOS.md`. Full artifact:
`V2_SCENARIO_RESULTS.json`. Assertions: `tests/test_v2_scenarios.py`.

**These are wiring tests for the assurance logic, not evidence about any real
machine.** Every injected value was chosen to exercise a declared threshold;
none is a measurement. The profile's thresholds were declared **before** the
scenarios and were not adjusted afterwards to make one come out a particular
way.

The one non-synthetic input is the v1.1 payload: the SENSOR domain's evidence
comes from real payloads produced by the frozen v1.1 runtime, because a
synthetic v1.1 payload would make §36's baseline circular. Only `timestamp` is
rewritten.

Each scenario perturbs the smallest set of signals representing its fault, **at
the source of the fault, never at the conclusion**. `CPU_OVERLOAD` raises
`cpu_load` and lets the runtime, the latency and the missed deadline follow; it
does not set `deadline_misses` by hand.

### Final tick, 200 ticks per scenario

| scenario | § | system | attribution | limiting | common cause |
|---|---|---|---|---|---|
| `NOMINAL` | — | NORMAL | NO_EVIDENCE | — | — |
| `POWER_SAG` | 27 | UNAVAILABLE | AMBIGUOUS | POWER | `POWER/battery` |
| `REGULATOR_FAILURE` | 27, 28-B | RESTRICTED | **UNIQUE** `POWER/rail_5v` | POWER | — |
| `CPU_OVERLOAD` | 27 | RESTRICTED | AMBIGUOUS | COMPUTE | `COMPUTE/cpu` |
| `PROCESS_STALL` | 27 | RESTRICTED | **UNIQUE** `COMPUTE/state_estimator` | COMPUTE | — |
| `NETWORK_LATENCY` | 27, 28-A | RESTRICTED | AMBIGUOUS | COMMUNICATION | `COMMUNICATION/telemetry_radio` |
| `PACKET_LOSS` | 27 | RESTRICTED | **UNIQUE** `COMMUNICATION/gnss_serial` | COMMUNICATION | — |
| `CLOCK_DRIFT` | 27 | RESTRICTED | **UNIQUE** `TIMING/nav_solution` | TIMING | — |
| `ACTUATOR_NO_RESPONSE` | 27 | RESTRICTED | **UNIQUE** `ACTUATION/motor_0` | ACTUATION | — |
| `STALLED_ACTUATOR` | 28-C | RESTRICTED | **UNIQUE** `ACTUATION/motor_0` | ACTUATION | — |
| `ESTIMATOR_LATE` | 28-D | RESTRICTED | AMBIGUOUS | COMPUTE | `COMPUTE/state_estimator` |
| `SHARED_RAIL` | 28-E | RESTRICTED | AMBIGUOUS | COMM, POWER, SENSOR | `POWER/rail_5v` |
| `SHARED_SOURCE` | 28-E literal | UNAVAILABLE | AMBIGUOUS | POWER | `POWER/battery` |
| `TS_NOMINAL` | 37 | NORMAL | NO_EVIDENCE | — | — |
| `TS_SUPPLY_SAG` | 37 | RESTRICTED | **UNIQUE** `POWER/dc_supply` | POWER | — |
| `TS_REGULATOR_FAILURE` | 37 | RESTRICTED | **UNIQUE** `POWER/rail_5v` | POWER | — |
| `TS_STALLED` | 37 | RESTRICTED | **UNIQUE** `ACTUATION/dyno_motor` | ACTUATION | — |
| `TS_ENCODER_LOSS` | 37 | RESTRICTED | **UNIQUE** `COMMUNICATION/encoder_bus` | COMMUNICATION | — |
| `TS_CPU_OVERLOAD` | 37 | RESTRICTED | AMBIGUOUS | COMPUTE, TIMING | `COMPUTE/cpu` |

Every scenario replays bit-for-bit — asserted by running each twice and
comparing full dictionaries — and every ledger chain verifies.

### The five §28 cases

| case | expected | observed |
|---|---|---|
| **A** sensor healthy, network delayed | comm/timing degrade, sensor stays source-valid | SENSOR NOMINAL; COMM + TIMING adverse; TELEMETRY limited; **navigation untouched**; no SENSOR candidate |
| **B** battery healthy, 5 V rail failing | power distribution issue, not battery fault | UNIQUE `POWER/rail_5v`; battery in `unsupported`; `POWER_DISTRIBUTION_SUSPECT`; inertial continuation, logging and propulsion stay ELIGIBLE |
| **C** command sent, current rises, RPM does not | actuation/mechanical issue | UNIQUE `ACTUATION/motor_0` with `ACT_STALLED`, **not** `ACT_NO_ELECTRICAL_RESPONSE`; POWER and COMM affirmatively NOMINAL |
| **D** sensor fresh, estimator late | compute/timing limitation, not sensor failure | SENSOR NOMINAL; COMPUTE + TIMING adverse; `PRECISION_NAVIGATION` INELIGIBLE, `COARSE_NAVIGATION` ELIGIBLE |
| **E** shared rail affects dependants | common power cause **retained as an alternative** | AMBIGUOUS, `common_cause = POWER/rail_5v`, the rail **not** adopted as the answer |
| **E** literal: two sensors on one node | same, with two SENSORS | AMBIGUOUS, `common_cause = POWER/battery`, two SENSOR candidates, from a real unedited payload |

**§28-E's literal form, and a search I first ran too narrowly.** §28-E says
"two sensors". `SHARED_RAIL` runs the fix-loss payload — one adverse source —
with two links on the same rail, so its common cause sits under one source and
two links.

I first reported that the corpus contained no literal two-sensor tick. **That
was wrong, and it was wrong because my search was narrower than the wrapper's
own definition**: it looked only for sources that were *unfresh*, while the
wrapper calls a source adverse when it is unfresh **or** named in
`sequential.alarming`. Searching on the wrapper's definition finds **745
ticks** — `battery` and `motor_esc`, both alarming, both declared on
`POWER/battery`, in POWER_SAG.

So `SHARED_SOURCE` was added and runs §28-E literally, on a **real, unedited
payload** extracted by `engineering/v2/extract_shared_source_payload.py` from
the same `_payloads()` that produced the committed examples. The only
injection is a battery droop past its declared limit; the rails are untouched.
Result: `AMBIGUOUS`, `common_cause = POWER/battery`, candidates
`POWER/battery`, `SENSOR/source.battery`, `SENSOR/source.motor_esc`.

**It is also the sharpest §36 case in the set.** That payload's own
`function_eligibility` is `ELIGIBLE` across all five functions — a sequential
alarm is not a cause attribution (Phase 4 §11) — while v2 calls the same five
`INELIGIBLE` on POWER evidence. Both are true at once, and
`domain_states["SENSOR"]` still reads exactly `ELIGIBLE` for each. A leak in
the wrapper would show up here, because this is the input where the two
answers disagree.

### §17's worked example, reproduced

`V2_OUTPUT_EXAMPLE.json` is a validated API document for the final tick of
`ESTIMATOR_LATE`:

```
SYSTEM: RESTRICTED
  SENSOR NOMINAL   COMMUNICATION NOMINAL   POWER NOMINAL   ACTUATION NOMINAL
  COMPUTE VIOLATED   TIMING VIOLATED
  PRECISION_NAVIGATION  INELIGIBLE  <- limited by COMPUTE
  COARSE_NAVIGATION     ELIGIBLE
  CAUSE SUPPORT: AMBIGUOUS
    candidates: COMPUTE/state_estimator, TIMING/nav_solution,
                TIMING/nav_solution.processing_delay
    ruled out by affirmative evidence: ACTUATION, COMMUNICATION, POWER, SENSOR
    implicated but unsupported: COMPUTE/cpu
```

Every column of §17's example matches except one, and the difference is
reported rather than tuned away: **COMPUTE reads VIOLATED here, not
DEGRADED**, because at the end of this run the estimator's runtime is past its
deadline outright rather than inside the marginal band. Making it come out
DEGRADED would mean choosing a ramp endpoint to match an illustrative example,
which is not a reason to choose anything.

## 10. NON-AIRCRAFT GENERICITY TEST — §37

An **electric motor test stand**: a bench that spins a motor against a brake
and logs torque. No GNSS, no attitude, no navigation, no flight phase, no
v1.1, and **no SENSOR domain registered at all**.

Functions: `TORQUE_DELIVERY`, `SPEED_MEASUREMENT`, `DATA_LOGGING`,
`TEST_SEQUENCE_EXECUTION`. Domains: POWER, COMPUTE, TIMING, COMMUNICATION,
ACTUATION — the **same five classes** the aircraft profile registers,
constructed with different declarations.

The claim under test is not "does it run". It fails if any of these is true:

- a core module must be edited to add the profile
- a domain must be edited to serve a non-vehicle
- a function must be named after a flight concept to be expressible
- the SENSOR domain or a v1.1 payload is required for the engine to work

None is. `csia/v2/` was not changed to add the bench, and its six fault
scenarios behave — including `TS_REGULATOR_FAILURE`, which reproduces §28-B's
source exoneration with no aviation code anywhere in the path.

**The strongest form of the test is run in a fresh interpreter.** It imports
only `csia.v2.profiles.test_stand`, runs a full scenario, and asserts that
`csia.v1_1`, `csia.trust_engine`, `csia.diagnosis` and the aircraft profile
were **never imported**. An in-process test cannot check that, because by then
the whole package is loaded.

That test failed the first time it ran, and the failure was real: convenience
re-exports in two `__init__.py` files meant importing any domain executed the
v1.1 stack, so a bench with no sensors loaded all of it. The re-exports are
now lazy. **The defect was in the framework, and it was fixed there rather
than by weakening the test** — modularity that only holds at the level of the
source tree is not modularity.

## 11. FUNCTION-ASSURANCE BEHAVIOUR

`csia/v2/functions.py`. Spec: `FUNCTION_DEPENDENCY_SPEC.md`.

A function declares `required_domains`, `supporting_domains`,
`no_degradation_domains`, a `fallback` and its acceptable degradation. The
roll-up maps each domain's observation state to a verdict, applies the two
declared modifiers, takes the most restrictive result, **and remembers which
domain produced it**. That last field is the product.

`UNKNOWN` outranks `INELIGIBLE`: "cannot determine" must not be acted on as
though it were "available", and must not be softened to "unavailable" either.
A required domain that said nothing is `UNAVAILABLE`, not fine.

**The separation §15 asks for, made concrete.** `PRECISION_NAVIGATION` lists
TIMING in `no_degradation_domains` — a late position is a wrong position at
speed. `LOGGING` does not list TIMING at all — a late log entry is still a log
entry. The same degraded timing evidence, two correct and opposite answers,
because the requirement is declared per function rather than assumed globally.

**A profile wiring gap must not look like a finding.** A test asserts that on
every tick of every scenario, a function that is `UNKNOWN` has a reason code
from the domain that went silent. Without it, forgetting to attach a domain
would be indistinguishable from a genuine "cannot determine".

**`PRECISION_LANDING` is absent, and that is inherited.** v1.1 omitted it
under Phase 4 §6 for want of a landing reference. v2 adds power, compute,
timing, communication and actuation evidence, and no landing reference.
Nothing about the omission changed, so listing it would either report a
permanent `UNKNOWN` or quietly reinstate a function v1.1 declined to specify.

## 12. AMBIGUITY BEHAVIOUR

Four verdicts (§29): `UNIQUE`, `AMBIGUOUS`, `UNSUPPORTED`, `NO_EVIDENCE`.

**A lone candidate is not unique.** One adverse component with nothing
affirmatively nominal elsewhere returns `AMBIGUOUS` with the reason recorded:
nothing has been ruled out, so nothing is claimed. `UNIQUE` requires a
**named** discriminator — a NOMINAL record from another domain — so a reader
can check what did the excluding rather than trusting that something did.

This is Phase 2's discipline carried across domains. There, a leader at
posterior 0.9998 with zero discriminating evidence is `NON_IDENTIFIABLE`. The
mechanism here is structural rather than Bayesian, because §18 forbids forcing
heterogeneous evidence through the eight-hypothesis core, but the standard is
identical: **a cause is named only when something rules the alternatives out.**

**A common cause is retained, never adopted.** When several adverse candidates
share an adverse dependency, the verdict stays `AMBIGUOUS` with the shared
node named. A rail fault and two coincident faults downstream of it produce
the same evidence at this level of modelling; "it must be the rail" is a guess
dressed as a diagnosis.

**Two words that must not blur.** `unsupported` means a relation pointed at a
component and the evidence did not support it. `domains_excluded` means a
domain was measured and found affirmatively fine. §17 asks the output to say
"sensor failure unsupported, transport failure unsupported"; v2 says it in the
second sense, which is the stronger one, and keeps both words available.

**Uniqueness is always among the modelled components.** v2 does not model
sub-components, so a unique attribution to `SENSOR/source.gps` does not
separate the receiver from its antenna. Listing the discriminators is what
lets a reader see the bound.

## 13. LEDGER

`csia/v2/ledger.py`. Spec: `V2_LEDGER_SPEC.md`.

The v1.1 mechanism, reused deliberately: canonical JSON, `content_sha256` per
event, `previous_event_hash` linking them, ids derived from content and
sequence rather than generated. Two ledgers that work differently cannot be
reconciled by an investigator months later.

**It is a simple hash chain. It detects a missing or reordered event. It is
not a blockchain, is not distributed, and is not tamper-proof against anyone
who can rewrite the whole file.** A test asserts the phrase is in the emitted
`chain_note`, and that no identifier in the module derives from `uuid`,
`random`, `secrets` or `time`.

§23's additions per event: `domain`, `component`, `limiting_domain`,
`affected_functions`, `dependencies`, and the full attribution.
`LIMITING_DOMAIN_CHANGED` is its own event type because "still degraded, but
now because of power rather than compute" is exactly what an investigator
needs and exactly what a state-only ledger loses.

`V2LedgerContext` carries a **plugin manifest hash** over every registered
plugin's declaration. A ledger replayed against a different plugin set is not
a replay, and this makes that detectable rather than merely unlikely.

## 14. API

`csia/v2/api.py`, schema `2.0.0`. Spec: `V2_API_SPEC.md`.

**One direction only.** v2 reads v1.1 payloads and writes its own document.
Nothing in v2 writes, extends, reinterprets or re-versions schema 1.1.0, and a
test parses every v2 module's import graph and fails on anything from
`csia/v1_1/` other than the payload parser.

**What it refuses to contain.** `validate()` raises on a top-level `score`,
`health`, `confidence`, `index`, `grade` or `percentage`. §3's rule is not
only about the record type: a "system health: 82%" field would re-import
exactly the false comparability that keeping evidence categorical exists to
prevent, and it would be a breaking change in *meaning* even though it is
additive in schema. There is no command surface, and a test asserts no public
function is named for an action.

Every rejection raises. There is no permissive path and no default for a
missing field, because a consumer that guessed at a malformed assurance
document would be worse than one that stopped.

## 15. COMPUTE

`V2_COMPUTE.json`. Measured on REGULATOR_FAILURE, 200 ticks, six domains, CPython on a general-purpose host.

| phase | median us/tick | max us/tick |
|---|---|---|
| `api_build` | 998.8 | 18,625.3 |
| `api_serialize` | 590.2 | 1,072.8 |
| `attribution` | 91.6 | 250.4 |
| `domain_ACTUATION` | 38.6 | 121.7 |
| `domain_COMMUNICATION` | 104.6 | 284.3 |
| `domain_COMPUTE` | 75.6 | 168.0 |
| `domain_POWER` | 68.8 | 147.6 |
| `domain_SENSOR` | 28,234.7 | 44,957.0 |
| `domain_TIMING` | 142.3 | 494.1 |
| `functions` | 201.5 | 443.7 |
| `ledger` | 18.8 | 843.1 |

| | us/tick |
|---|---|
| **the v2 decision** (five domains + roll-up + attribution) | **723.0** |
| ingesting the v1.1 payload (the SENSOR domain) | 28,234.7 |
| of which JSON Schema validation, timed alone | 28,028.5 |
| reporting (ledger + API build + serialise) | 1,607.9 |

68 evidence records per tick across six domains.

**An earlier version of this measurement was wrong, and it is recorded rather
than quietly replaced.** It timed all six domains as one phase and reported
~28,000 us as "core". That figure was almost entirely
`csia.v1_1.monitor.parse` running inside the SENSOR domain — the same class of
mistake Phase 4 caught in its own compute figure, where the CUSUM step alone
was timed and labelled with the name of the whole pipeline. Each domain is now
timed separately and the headline is reported twice.

**The finding that matters for an integrator**: the strict v1.1 payload parse
costs roughly two orders of magnitude more than the entire six-domain
decision, because it re-validates against the JSON Schema on every call. That
is a property of ingesting schema 1.1.0 strictly, **not** of the v2 decision,
and an integration that validates once at ingest rather than once per consumer
does not pay it repeatedly.

**Nothing in v1.1 was changed to improve that number** (§19). It is reported
as measured.

CORE and REPORTING are separated for the reason Phase 4 separated them:
folding logging and serialisation into a decision-path figure would overstate
what an embedded port must carry. **No target-hardware figure exists and none
is claimed**, and the Phase 4 v1.1 core figure is not comparable — it measured
a different thing on a different scenario.

## 16. COMPLEXITY

`V2_COMPLEXITY.json`. Code lines exclude blank lines and comments.

| layer | modules | code lines |
|---|---|---|
| core framework (`csia/v2/*.py`) | 10 | 1,357 |
| domain plugins (`csia/v2/domains/`) | 7 | 1,693 |
| platform profiles (`csia/v2/profiles/`) | 5 | 783 |

6 domains registered on the aircraft profile,
31 domain relations declared between them,
4 cross-domain relations, and
10 system functions.

**The number that matters is not the total, it is the marginal cost.** Adding
a domain is one module implementing `evaluate`, plus its declarations in a
profile. **No core module changes.** The six built domains are the evidence
for that; the five specified-but-not-built ones are the test of it that has
not been run, and §17 names the one place a specified domain would need a core
extension.

The core is deliberately the smallest of the three layers. Most of the code is
in the domains, which is where it should be: a framework that is larger than
the things it composes has usually absorbed something that belonged in them.

## 17. COMPONENTS DEFERRED

| domain | status | why |
|---|---|---|
| FIRMWARE_CONFIGURATION | specified, not built | outside §26's scope |
| THERMAL | id reserved, no spec | outside §26's scope and §34's document list |
| ESTIMATOR | specified, not built | outside scope **and** needs a framework extension |
| STORAGE | id reserved, no spec | outside §26's scope and §34's document list |
| SECURITY_INTEGRITY | specified, not built | §30: security-ready, not security-dependent |

**One known framework gap, recorded now rather than discovered later.** The
estimator domain's most valuable finding — "SENSOR says the source is healthy
**and** ESTIMATOR is rejecting it" — is a *predicate over two domains' states*.
The relation table declares which components a relation can implicate; it does
not express a conjunction over their verdicts. That is a real extension, and
it is the only place in the eighteen specs where a specified domain would not
slot in without a core change. It is why the estimator domain is scheduled
last rather than first.

Also deferred: no retention policy for the ledger, no signing, no transport
for the v2 API, no authentication, and no JSON Schema file (deliberately —
v2 is still moving, and a schema file that drifts from the code it describes
is worse than none).

## 18. AI FUTURE ARCHITECTURE — §§31, 32

Documented, **not implemented**.

```
    deterministic assurance core
              |
    evidence ledger / domain graph
              |
    optional AI analyst            <-- NOT BUILT
              |
    hypothesis proposal / fleet learning
              |
    deterministic validation gate  <-- nothing promotes without passing this
```

An analyst would be allowed to summarise evidence, rank logs for review,
*propose* cross-domain relations, detect fleet patterns and suggest
hypotheses. It may never appear in the decision path, change an eligibility,
or command anything.

Every proposal must pass **deterministic replay** before promotion: add the
proposed relation to the table, replay the recorded traces, accept only if the
recorded outcomes change in the way claimed. The ledger is what makes that
gate possible, which is a large part of why the ledger exists.

Two tests enforce the boundary today: no learning library is imported anywhere
under `csia/v2/`, and the decision path imports **nothing outside the standard
library at all** — a third-party numeric library would make the answer depend
on its version, and determinism and replay are the promise.

## 19. CONTROLLER / AUTOPILOT INTEGRATION — §33

CSIA remains **independent assurance middleware**.

```python
API.function_eligible(doc, "PRECISION_NAVIGATION")
# {"eligible": False, "state": "INELIGIBLE", "limiting_domain": "POWER",
#  "reason_codes": ["POWER_RAIL_OUT_OF_TOLERANCE",
#                   "POWER_DISTRIBUTION_SUSPECT"],
#  "fallback": "COARSE_NAVIGATION",
#  "why": "limited by POWER: ..."}
```

The autopilot asks; CSIA answers with the state, the limiting domain, the
reason codes and **the host's own declared fallback reported back to it**.
Reporting a host's declaration to the host is not CSIA choosing anything. The
autopilot owns the switching action.

It returns the answer *and why*, because an integration that only got a
boolean would have no way to log what it acted on.

That separation is not deference. It is what lets the same middleware serve an
aircraft and a factory machine, and it is what keeps the certification
argument tractable: an advisory component that cannot actuate carries a much
smaller assurance obligation than one that can. `csia/v1_1/firewall.py`
already enforces the equivalent boundary by default-deny for v1.1 outputs;
v2's API has no command surface at all.

## 20. STRONGEST CURRENT COMMERCIAL CAPABILITY

Stated plainly, and bounded plainly.

**The strongest thing CSIA v2 can do today is answer, from evidence a platform
already produces, which system functions are still justified and which
subsystem is limiting each one — and refuse to name a cause when the evidence
does not separate the alternatives.**

Four things make that more than a dashboard:

1. **It exonerates.** A healthy battery beside a failing 5 V rail produces
   "the regulator/distribution path is the candidate, the battery is fine",
   not "POWER: FAULT". The vehicle keeps inertial continuation, logging and
   propulsion, and the report says so. That distinction is the difference
   between a maintainer going to the right box and stripping the wrong one.

2. **It does not convert a link fault into a sensor fault.** A GNSS receiver
   behind a failing serial link is a communication candidate with the sensor
   domain affirmatively nominal — the single most common misattribution in
   field telemetry, and it is structural here rather than a heuristic.

3. **It says what it ruled out, by name.** `UNIQUE` requires a named
   discriminator; `AMBIGUOUS` lists the domains measured and found fine. A
   consumer can check the exclusion instead of trusting it.

4. **Every answer is replayable.** Same trace, same software, same plugin set,
   byte-identical ledger — including the hashes. That is what makes a
   post-incident question answerable rather than reconstructed.

**What it is not.** It is not a diagnosis of anything below the modelled
component level. It is not calibrated: no false-alert rate is claimed or
supportable. It is not evidence about any real vehicle — every threshold is
declared configuration and every scenario is synthetic. And it has never run
on hardware.

The honest commercial position is **integration-ready middleware with an
unmeasured field performance**: the interfaces, the determinism, the audit
trail and the refusal semantics are real and testable today; the numbers a
customer would want — how often it is right, on their machine — do not exist.

## 21. THE PRODUCT QUESTION — §38

> Is CSIA now fundamentally **A.** aircraft sensor assurance, or **B.**
> reusable electromechanical/autonomous-system assurance middleware?

**B, for the framework. A, for the only mature domain in it.** Both halves
matter and the evidence decides each.

**The case for B, and it is evidence not branding:**

- An electric motor test stand runs on the same framework with **no SENSOR
  domain, no v1.1 payload, and no module in `csia/v2/` changed**. It is not a
  demonstration written beside the aircraft one — it registers the same five
  domain classes with different declarations.
- A test runs that bench **in a fresh interpreter** and asserts that
  `csia.v1_1`, `csia.trust_engine`, `csia.diagnosis` and the aircraft profile
  were never imported at all.
- The core carries no platform vocabulary, checked by parsing every module's
  AST for identifiers rather than by reading the README.
- Two defects found during the build were both **the framework leaking
  platform knowledge** — the harness holding one vehicle's battery voltages,
  and eager re-exports dragging v1.1 into a bench. Both were fixed in the
  code. A framework that could not survive that test would have failed here.

**The case for A, which is about maturity rather than architecture:**

- The SENSOR domain is the only one with a research history, a frozen core, a
  golden trace corpus, real ULog-derived qualification and a numeric
  equivalence spec. The other five have declared thresholds and synthetic
  scenarios and nothing else.
- Five of the ten domains are specified and not built, and one of those five
  needs a framework extension.
- The v1.1 payload seam costs more per tick than the entire six-domain
  decision, which is a property of an aircraft-shaped integration.

So: **the architecture is B and the product is A-plus-scaffolding.** Calling
it reusable middleware today would be true of the code and misleading about
the evidence. The accurate sentence is: *CSIA is a reusable system-assurance
framework whose one mature domain is aircraft sensor assurance.*

What would move it fully to B is not more architecture. It is a second domain
carried to the same depth as the first — declared thresholds replaced by
characterised ones, synthetic scenarios replaced by recorded ones — on a
machine that is not an aircraft.

## 22. WHAT IS STILL WRONG

Carried forward from v1.1 unchanged, because v2 does not move any of it:

1. **No hardware.** Nothing in v2 has run on a vehicle, a bench or a rig.
2. **Every v2 threshold is declared configuration**, chosen as ordinary
   engineering practice for the synthetic harness. Not one is a
   characterisation of any component.
3. **Every v2 scenario is synthetic.** They are wiring tests for the assurance
   logic, not evidence about how a regulator sags or an ESC behaves.
4. **Zero verified-clean hours.** No false-alert rate is claimed or
   supportable, for any domain.

New with v2, and stated rather than left to be found:

5. **Five of ten domains are unbuilt**, and the estimator domain needs a
   framework extension that does not exist (§17 above).
6. **The v1.1 ingest dominates the tick.** The strict payload parse costs
   roughly two orders of magnitude more than the whole six-domain decision.
   Nothing in v1.1 was changed to improve it (§19), and what to do about it is
   a decision for a later phase.
7. **One of my own search definitions was too narrow and produced a wrong
   negative**, corrected in §9: the §28-E literal case does occur in the real
   corpus, 745 times, and is now tested. The lesson generalises — a search
   whose definition of "adverse" differs from the code's own is a search that
   can only mislead.
8. **One profile, one bench, one author.** The genericity result is real but
   it is n=2, and both were written by the same person who wrote the
   framework. That is the same limitation Gate C had for the v1.1 consumer.
9. **No independence model.** Dependencies are declared structure walked
   deterministically. Whether two sources on one rail are *actually*
   correlated in a way that matters is not estimated, by design (§22).
10. **Attribution is per tick.** Onset order is in the ledger and is not used,
    because using it would need state the domain contract forbids.

**Product maturity: M2, unchanged.** v2 adds architecture, not evidence about
a vehicle.

---

## APPENDIX — ARTIFACTS

| file | what it records |
|---|---|
| `V2_DECLARATIONS.json` | every plugin's declaration and coverage, both profiles |
| `V2_BASELINE_V1_1.json` | §36 over every real v1.1 payload, plus the §28-E search |
| `V2_SCENARIO_RESULTS.json` | all scenarios, all ticks, with the expectation written before the run |
| `V2_LEDGER_EXAMPLE.json` | one scenario's full ledger, chain verified |
| `V2_OUTPUT_EXAMPLE.json` | a validated §17-shaped API document |
| `V2_COMPUTE.json` | per-phase cost, and the correction to an earlier wrong measurement |
| `V2_COMPLEXITY.json` | what the framework costs to carry |

All regenerated by `python engineering/v2/run_v2.py`.
