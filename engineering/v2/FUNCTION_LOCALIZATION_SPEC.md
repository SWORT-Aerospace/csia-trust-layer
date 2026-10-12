# FUNCTION DEPENDENCY ASSURANCE AND THE EXPLANATION OBJECT

Phase C §§1, 11–13, 28. Implementation: `csia/v2/functions.py`,
`csia/v2/explanation.py`. Generated data: `FUNCTION_REQUIREMENTS_V2.yaml`.

---

## 1. The explanation object (§1)

Every function produces one object per tick:

| field | meaning |
|---|---|
| `state` | `ELIGIBLE` / `DEGRADED` / `INELIGIBLE` / `UNKNOWN` |
| `limiting_domains` | SUPPORTED domains that prevent full eligibility |
| `possible_domains` | unresolved alternatives — **not causes** |
| `cleared_domains` | domains a named predicate argued against |
| `evidence` | the exact predicates and relations behind the above |
| `graph_limiting_domain` | the function graph's own answer, kept beside the localization one |
| `active_fallback` | which alternate requirement set is carrying the function |
| `symptoms` | every localization that bears on this function |

The three domain lists are three different epistemic states and collapsing any
two of them loses the point:

```
    limiting   something confirms this domain and nothing refutes it
    possible   it survived elimination and nothing confirms it
    cleared    a named predicate affirmatively argued against it
```

`cleared: [SENSOR, COMMUNICATION]` tells an operator those were **measured and
found fine** — a stronger and more actionable statement than their absence
from a list. `possible` is never presented as a cause (§2); a function with an
empty `limiting` and a non-empty `possible` is one where the system knows
something is wrong and honestly cannot say what.

### Two invariants, both enforced by test

**An `ELIGIBLE` function has no limiting domain.** §1 defines `limiting` as
what *prevents full eligibility*; if nothing is prevented, nothing is
limiting. The first implementation violated this — it attached any
localization touching a shared domain, so `INERTIAL_CONTINUATION` came back
`ELIGIBLE` and limited by `SENSOR` in the same object. A symptom whose subject
is a function now stays with that function, and an eligible function's
`limiting` is emptied into `possible`.

**A domain cannot be both cleared and limiting.** Being fine as an explanation
of symptom X says nothing about symptom Y, so `limiting` wins and `cleared` is
reduced.

Nothing in `explain()` re-decides anything. Every field is derived from the
function verdict and the localizations already produced this tick, so an
explanation cannot disagree with the verdict it explains.

## 2. Four kinds of dependency (§11)

| kind | declaration | semantics |
|---|---|---|
| REQUIRED | `required_domains` | adverse ⇒ the function is not eligible |
| REDUNDANT | `redundant_groups` | one-of-N over **components**; the function survives while one member is nominal |
| FALLBACK | `fallback_requirements` | a named alternate requirement set; the function runs degraded on it |
| OPTIONAL | `optional_domains` | absence is not a fault and is reported as such |

Redundancy is expressed over **component ids** (`"DOMAIN/component"`), not
domains. Two pumps are both `ACTUATION`; a domain-level group could not
express "either pump will do" at all. This was found by building the second
profile, which is what a second profile is for.

Two reason codes come out of it, and both survive to the caller:

- `REDUNDANT_GROUP_EXHAUSTED` — every member of a one-of-N group is adverse
- `REDUNDANCY_REDUCED` — the function is still met, and it is now running
  without margin. This is emitted **alongside** `ALL_REQUIREMENTS_MET`, because
  "eligible" and "eligible with no spare" are different operational facts.

## 3. Thresholds live in the profile (§28)

`FUNCTION_REQUIREMENTS_V2.yaml` is generated from the profile tables, which
are the source of truth. No threshold, rail name, function name, or platform
noun appears in `csia/v2/*.py`; a test parses the core modules' ASTs and
asserts it over identifiers (not source text — the first version matched
`esc` inside `description` and would have taught me to weaken the test).

Current declarations:

| profile | functions | notable |
|---|---|---|
| `aircraft` | 10 | `AUTONOMOUS_MISSION` requires five domains and takes no TIMING degradation |
| `test_stand` | 4 | no SENSOR domain exists at all |
| `pump_skid` | 4 | one-of-N over `ACTUATION/pump_a\|pump_b`; `PRESSURE_REGULATION` falls back to `OPEN_LOOP_ON_SPEED`; `CONDITION_MONITORING` treats TIMING as optional |

`PRECISION_LANDING` is deliberately absent from the aircraft profile. v1.1
omits it because there is no landing reference in the data, and carrying it
into v2 would have produced a permanent `UNKNOWN` that looked like a fault.

## 4. Common cause does not become several function failures (§13)

A shared adverse node is one finding. The function graph reports each affected
function's own state — that is what a function graph is for — but the
localization attached to them names **one** supported hypothesis, and records
derived from other records carry `attributable=False` so they can never enter
a candidate set. An operator reading three degraded functions and one
`POWER/shared_node` is looking at one fault with three consequences, and the
document says so.

## 5. Reconciling the two answers

The function graph and the localization layer answer different questions:

- the graph reads the function's **requirements** — which declared domain is
  adverse
- localization reads the **symptom's** alternatives — which hypothesis the
  evidence supports

They are kept side by side (`limiting_domains` vs `graph_limiting_domain`)
rather than merged, because a domain can limit a function without having
produced any symptom anyone declared, and where the two differ the difference
is worth seeing. The graph's answer is used only when localization has nothing
to say.
