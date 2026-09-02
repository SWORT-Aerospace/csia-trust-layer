# SYSTEM FUNCTION GRAPH — v2 §§15, 16, 17

Implementation: `csia/v2/functions.py`. Profiles: `csia/v2/profiles/`.

> Separate COMPONENT DOMAINS from FUNCTIONS. (§15)

---

## 1. WHY THE SEPARATION IS THE PRODUCT

A domain says "the 5 V rail is 4.3 V, out of its declared band". A function
says "precision navigation is no longer justified". Those are different
statements with different audiences, and the second one is what anybody
actually acts on.

v1.1 already made that distinction **inside one domain**. v2's contribution is
making it hold **across** domains, so the answer becomes

> which functions are still justified, by what evidence,
> and **what domain is limiting them**

A component-oriented monitor cannot produce the last clause at all. That is
the whole case for the function graph.

## 2. WHAT A FUNCTION DECLARES

| field | meaning |
|---|---|
| `required_domains` | every one must have evidence for this function |
| `supporting_domains` | improve it; their absence or failure only degrades it |
| `no_degradation_domains` | domains where DEGRADED is not tolerated |
| `fallback` | what the host may fall back to — recorded, never actioned |
| `acceptable_degradation` | prose, for the reader |

## 3. THE ROLL-UP

Domain observation state maps to a function verdict:

    NOMINAL / NOT_APPLICABLE  ->  ELIGIBLE
    DEGRADED                  ->  DEGRADED
    VIOLATED                  ->  INELIGIBLE
    UNAVAILABLE               ->  UNKNOWN

Then two declared modifiers, in order:

1. a domain in `no_degradation_domains` turns `DEGRADED` into `INELIGIBLE`
2. a `supporting_domain` turns `INELIGIBLE` or `UNKNOWN` into `DEGRADED` —
   that softening is exactly what makes it supporting rather than required

The function takes the **most restrictive** result, and remembers **which
domain produced it**. That domain is `limiting_domain`, and it is §17's
central column.

`UNKNOWN` outranks `INELIGIBLE`. "Cannot determine" must not be acted on as
though it were "available", and it must not be quietly softened to
"unavailable" either: they have different remedies.

**A required domain that said nothing is `UNAVAILABLE`, not fine.** No
evidence is not good news, and a function whose power domain was silent has
not been shown to be powered.

## 4. WHY THE SAME EVIDENCE COSTS DIFFERENT FUNCTIONS DIFFERENT AMOUNTS

This is §15's real content, and it is why `no_degradation_domains` is declared
per function rather than being a global rule.

`PRECISION_NAVIGATION` lists TIMING there: a late position is a wrong position
at speed, so a marginal timing budget stops it. `LOGGING` does not list TIMING
at all: a late log entry is still a log entry. The *same* degraded timing
evidence, two correct and opposite answers, because the requirement differs
and the requirement is declared rather than assumed.

`csia/v2/domains/compute.py` reports a missed deadline. It does not decide
what a missed deadline costs. That decision lives here, per function, where a
reviewer can read it.

## 5. THE SYSTEM WORD — §16

    NORMAL       every function eligible
    DEGRADED     something is degraded, nothing is lost
    RESTRICTED   at least one function is unavailable, but not all
    UNAVAILABLE  every function is ineligible or undetermined

Derived from the functions, never asserted independently.

## 6. THE AIRCRAFT PROFILE

Five names come from v1.1 and keep their meaning; five are new to v2.

| function | required | supporting | no-degradation | fallback |
|---|---|---|---|---|
| `PRECISION_NAVIGATION` | SENSOR COMPUTE TIMING POWER | — | TIMING | COARSE_NAVIGATION |
| `COARSE_NAVIGATION` | SENSOR POWER | COMPUTE TIMING | — | INERTIAL_CONTINUATION |
| `POSITION_HOLD` | SENSOR COMPUTE TIMING POWER | — | TIMING | attitude hold |
| `GEOFENCE_SUPPORT` | SENSOR POWER | COMPUTE | — | — |
| `INERTIAL_CONTINUATION` | SENSOR POWER | — | — | — |
| `SENSING` | SENSOR POWER COMMUNICATION | COMPUTE | — | — |
| `TELEMETRY` | COMMUNICATION POWER | COMPUTE TIMING | — | onboard log only |
| `LOGGING` | COMPUTE POWER | — | — | — |
| `PROPULSION` | POWER ACTUATION | COMPUTE | — | — |
| `AUTONOMOUS_MISSION` | SENSOR COMPUTE TIMING POWER ACTUATION | COMMUNICATION | TIMING | operator-supervised |

**`PRECISION_LANDING` is absent, and that is inherited rather than an
oversight.** `engineering/v1_1/FUNCTION_REQUIREMENTS.yaml` omits it under
Phase 4 §6 — "if a function cannot be specified honestly: omit it" — because
no landing reference (rangefinder, optical flow, beacon) exists in the node
set. v2 adds power, compute, timing, communication and actuation evidence. It
adds no landing reference. Nothing about the omission has changed, so listing
it would either report a permanent `UNKNOWN` or quietly reinstate a function
v1.1 declined to specify.

## 7. HOW §36 AND §17 ARE BOTH SATISFIED

They look contradictory: §36 forbids the plugin layer from altering v1.1's
function eligibility, and §17's example shows `PRECISION_NAVIGATION`
INELIGIBLE from a COMPUTE/TIMING violation.

They are different statements, and the profile keeps them distinguishable:

- `domain_states["SENSOR"]` **is** the v1.1 verdict, transcribed by a
  bijection, unaltered, and always visible in the output.
- the v2 function state is the roll-up over every required domain, of which
  SENSOR is one.

Two structural properties make it checkable rather than promised:

1. **Exactness** — with only the SENSOR domain registered, every v2 function
   state equals the v1.1 state exactly.
2. **Monotonicity** — adding domains can only hold or restrict a function,
   never relax it, because the roll-up takes the worst state and every map
   entry is order-preserving.

For both to hold, the five v1.1-named functions must list SENSOR as
**required** and must **not** list it in `no_degradation_domains`. Required,
because a supporting domain's INELIGIBLE would be softened; not
no-degradation, because a DEGRADED would be hardened. Either is an alteration.
`tests/test_v2_navigation_baseline.py` asserts both against the table, so the
guarantee cannot be lost by editing it.

## 8. PER-COMPONENT FUNCTION SCOPING

A domain's evidence attaches to functions **per component**, not per domain.

The first version of the power domain attached every rail to every function.
On a 5 V regulator failure it reported total loss of a vehicle whose IMUs run
off 3V3 and whose motors run off the battery — a vehicle that could still
navigate inertially, log, and fly home. That is not a refinement; it is the
difference between a useful answer and a misleading one, and it is why
`RailSpec`, `ProcessSpec`, `ChannelSpec`, `LinkSpec` and `ActuatorSpec` each
carry their own `affected_functions`.

The declaration is the host's, because the host knows its harness. It is
consistent with `SOURCE_DEPENDENCIES` in the same profile by construction:
one says which rail feeds a source, the other says what that costs.

## 9. COVERAGE

`coverage_report(engine)` names any function whose required domain has no
registered plugin. Such a function can only ever come out `UNKNOWN`, and
finding that at configuration time is better than finding it per tick for the
rest of a deployment.

`tests/test_v2_scenarios.py` goes further: on every tick of every scenario, a
function that is `UNKNOWN` must have a reason code from the domain that went
silent. A profile wiring gap must not be indistinguishable from a finding.
