# Preregistration — Consequence, Support, and Cross-Architecture Validation

**Written and committed before any result in this phase exists.** The seed
partitions are fixed by `csia_consequence/partitions.py`, manifest
`36c707f2061d7bc044f39abd723be4ecf01ee3ccaccd54626d755e492e3e562b`, and the
`locked` partition raises on access unless the call site says it is opening it.

**Scope: simulation, replay and SITL only.** No hardware is operated, no RF is
transmitted, no vehicle is armed, no real actuator is commanded, and no flight
validation is claimed. The E2M hardware campaign stays `AUTHORIZED_NOT_RUN` and
is untouched by this phase.

**Nothing frozen is modified.** Not the CSIA core, not a sealed artifact, not a
prior preregistration, not a historical result, not Paper I, not the Gate
Conditioning paper, not an existing negative result or correction record. This
phase is additive: harnesses, adapters, schemas, manifests and tests.

---

## 1. Partitions

| partition | seeds | use |
|---|---|---|
| `development` | 16 | tuning, debugging, threshold selection. Look freely. |
| `validation` | 24 | rehearsal of the frozen design. |
| `locked` | 32 | opened **once**, after the design is frozen and committed. |

**No threshold, scoring rule, gate definition or hypothesis may change after
the locked partition is inspected.** If a defect is found after opening, it is
recorded as a defect and the locked result stands as what it is.

## 2. Evidence levels

Every result in this phase carries exactly one, and the ladder is not
negotiable:

`SOURCE_ANALYSIS` · `DETERMINISTIC_SIMULATION` · `REPLAY` · `SITL` · `HIL` ·
`BENCH_HARDWARE` · `FLIGHT`

This phase can reach `SITL` at best. `HIL`, `BENCH_HARDWARE` and `FLIGHT` are
unreachable here and any result claiming one is a defect.

**A closed-loop result is labelled `MODEL_BASED_ACTION_CONSEQUENCE` unless a
real autopilot path actually executed the action, in which case and only in
which case it is `SITL_CLOSED_LOOP_EXECUTION`.** The distinction is recorded
per run, from what the harness actually invoked, not from intent.

## 3. Hypotheses, kill criteria, and what a null result means

Each hypothesis is stated with the observation that would **kill** it. A null
result is a valid outcome and is reported as prominently as a positive one.

### H1 — Uncovered occlusion

> There exists at least one fault-dependent validity or health gate for which
> measurements remain fresh, the gate closes, the diagnostic relation needed
> for attribution disappears, and no independent freshness path forces an
> equivalent warning.

**Killed if:** every gate enumerated from source either (a) cannot close while
its protected sensors are fresh, or (b) closes only in lockstep with a
freshness signal that independently raises an equivalent warning. Then the
occlusion is always covered and the phase's premise is wrong.

**Evidence level:** `SOURCE_ANALYSIS`, corroborated at
`DETERMINISTIC_SIMULATION`.

**Predeclared:** the count of uncovered cases is **not** fixed in advance. A
figure of eight has been alleged elsewhere; this phase derives the count from
source and reports whatever it finds, including a different number.

### H2 — Operational consequence

> At least one uncovered case causes a difference between the correct
> fault-conditioned response and the response produced by the current
> diagnostic output.

**Killed if:** for every uncovered case, the recommended action under the
current output equals the correct action under latent truth. Then the
occlusion is real but inconsequential, which is a publishable negative result.

**Evidence level:** `MODEL_BASED_ACTION_CONSEQUENCE` unless an autopilot path
runs.

### H3 — Closed-loop mitigation

> An explicit support state or abstention policy reduces incorrect actionable
> decisions, even if it increases ambiguity or abstention.

**Killed if:** the support-aware policy does not reduce incorrect actionable
decisions, or reduces them only by abstaining on everything — measured as a
strict increase in incorrect decisions, or an abstention rate at which correct
confident outputs fall to zero.

**Abstention is not a solved safety problem and this phase does not treat it as
one.** The tradeoff is reported as a curve, not as a win.

### H4 — Detector tradeoff

> The trust-persistence detector has a measurable delay/false-alarm tradeoff
> against a matched CUSUM comparator.

**Killed if:** no operating point exists at which the two are comparable, or
the curves are statistically indistinguishable across the whole grid.

**Binding constraint:** comparison is at **matched false-alarm operating
points** over a preregistered threshold grid. A single hand-picked threshold
against another single hand-picked threshold is not a comparison and is
forbidden. **No claim that CUSUM is inferior may be made** except at matched
false-alarm rates, and CUSUM is a standard method whose correct implementation
is the baseline's responsibility, not a straw man.

### H5 — Cross-architecture recurrence

> The structural pattern is present, absent, or unresolved in each audited
> PX4/ArduPilot path.

**Not a recurrence hypothesis.** It predicts nothing about prevalence. Each
audited path is classified `STRUCTURALLY_PRESENT`, `STRUCTURALLY_ABSENT`,
`RUNTIME_REPRODUCED`, `RUNTIME_NOT_REPRODUCED`, `UNVERIFIED` or
`BLOCKED_BY_SOURCE_ACCESS`, and the distribution is reported.

**Killed if:** nothing can be classified at all.

**No universality claim may be drawn from any number of audited paths.** RAIM
may be cited as a *design analogy* for availability/integrity reporting; it is
not evidence that CSIA's mechanism exists, and RAIM and CSIA are not claimed to
solve the same problem.

### H6 — Independent reproduction

> A CSIA-Lite implementation reproduces the two mechanisms without importing
> the proprietary CSIA implementation.

**Killed if:** the reference implementation cannot reproduce them, or can only
do so by importing the production modules. Import-independence is asserted by a
test that inspects `sys.modules` in a fresh interpreter, following the
precedent of `research/systems-paper/independent_checker.py`.

## 4. What this phase may not conclude

No hardware validation. No RF validation. No flight safety. No universal
prevalence. No certification. No airworthiness. No novelty. No claim that an
autopilot executed an action unless the simulator executed it. No claim that
RAIM proves CSIA's mechanism. No claim that ambiguity has been eliminated.

## 5. Order of operations

Enumeration (Phase 2) and harness construction happen on `development`.
`validation` rehearses. `locked` is opened once, last, with a recorded opening
state, and nothing is tuned afterwards.
