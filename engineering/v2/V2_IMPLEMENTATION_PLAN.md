# V2 IMPLEMENTATION PLAN — SCOPE, DEFERRALS, AND THE AI LAYER

> §26: do NOT build all ten domains completely.
> §35: implement ONLY the framework, the v1.1 wrapper, power, compute,
> timing, communication, and the synthetic scenario harness.

---

## 1. WHAT WAS BUILT

| component | module | status |
|---|---|---|
| evidence record | `csia/v2/evidence.py` | built |
| plugin contract | `csia/v2/domain.py` | built |
| registry | `csia/v2/registry.py` | built |
| function graph | `csia/v2/functions.py` | built |
| attribution | `csia/v2/attribution.py` | built |
| engine | `csia/v2/engine.py` | built |
| ledger | `csia/v2/ledger.py` | built |
| API | `csia/v2/api.py` | built |
| scenario harness | `csia/v2/scenarios.py` | built |
| SENSOR (v1.1 wrapper) | `csia/v2/domains/navigation.py` | built |
| POWER | `csia/v2/domains/power.py` | built |
| COMPUTE | `csia/v2/domains/compute.py` | built |
| TIMING | `csia/v2/domains/timing.py` | built |
| COMMUNICATION | `csia/v2/domains/communication.py` | built |
| ACTUATION | `csia/v2/domains/actuation.py` | built (the §26 sixth) |
| aircraft profile | `csia/v2/profiles/aircraft*.py` | built |
| test-stand profile | `csia/v2/profiles/test_stand*.py` | built |

ACTUATION was built because §26 permits a sixth "if architecture remains
clean" and it is the one that tests the claim: it spans electrical and
mechanical evidence, it is what the §37 test stand is built around, and it
required **no core change**.

## 2. WHAT WAS DELIBERATELY NOT BUILT

| domain | spec | why not |
|---|---|---|
| FIRMWARE_CONFIGURATION | `FIRMWARE_DOMAIN_SPEC.md` | outside §26's scope |
| THERMAL | — | outside §26's scope |
| ESTIMATOR | `ESTIMATOR_DOMAIN_SPEC.md` | outside scope **and** needs a framework extension (§4 below) |
| STORAGE | — | outside §26's scope |
| SECURITY_INTEGRITY | `SECURITY_DOMAIN_FUTURE_SPEC.md` | §30: security-ready, not security-dependent |

THERMAL (§10) and STORAGE (§12) have reserved ids and no spec document, because
§34's document list does not include them. THERMAL would compare temperature
to load, distinguishing expected heating from anomalous heating; STORAGE would
distinguish "assurance computation available" from "assurance record
unavailable". Neither needs anything the framework does not have.

## 3. THE ORDER TO BUILD THE REST IN

1. **FIRMWARE_CONFIGURATION.** Highest value per unit of work, needs nothing
   new, and unlocks §14's firmware↔timing relation — the class of incident
   where a rate parameter changes, the staleness watchdog fires, and the
   investigation goes to the sensor.
2. **STORAGE.** Small, and it answers a question the assurance system should
   be able to answer about itself: can the record still be written?
3. **THERMAL.** Needs load correlation to be worth anything; without it, it is
   a thermometer with a threshold.
4. **SECURITY_INTEGRITY**, starting with output-firewall denials, which are
   already the highest-quality security evidence in the system and are
   currently counted and not surfaced.
5. **ESTIMATOR**, last, because it needs the extension below.

## 4. THE ONE KNOWN FRAMEWORK GAP

The estimator domain's most valuable finding — "SENSOR says the source is
healthy **and** ESTIMATOR is rejecting it" — is a **predicate over two
domains' states**. The relation table today declares which components a
relation can implicate; it does not express a conjunction over their verdicts.

That is a real extension, and recording it now is more useful than discovering
it later. It is the only place in this document set where a specified domain
would not slot in without a core change, and it is the reason the estimator
domain is last rather than first.

## 5. THE AI LAYER — §§31, 32: DOCUMENTED, NOT IMPLEMENTED

```
    deterministic assurance core
              |
              v
    evidence ledger / domain graph
              |
              v
    optional AI analyst            <-- NOT BUILT
              |
              v
    hypothesis proposal / fleet learning
              |
              v
    deterministic validation gate  <-- nothing promotes without passing this
```

**No LLM or ML model is in the deterministic v2 assurance decision** (§31).
`tests/test_v2_api_ledger.py` asserts that no learning library is imported
anywhere under `csia/v2/`, and that the decision path imports nothing outside
the standard library at all — a third-party numeric library would make the
answer depend on its version, and determinism and replay are the promise.

What an AI analyst would be *allowed* to do:

- summarise evidence for a human reading a ledger
- rank logs for review
- **propose** new cross-domain relations
- detect recurring patterns across a fleet
- suggest hypotheses

What it may never do:

- appear in the decision path
- change a function's eligibility
- command anything (§33 already forbids CSIA itself from commanding)

Every proposal must pass **deterministic replay** before promotion: a proposed
relation is added to the table, the recorded traces are replayed, and it is
accepted only if it changes the recorded outcomes in the way claimed. The
ledger is what makes that gate possible, which is a large part of why the
ledger exists.

## 6. CONTROLLER / AUTOPILOT INTEGRATION — §33

CSIA remains **independent assurance middleware**. The consumer asks
`function_eligible(doc, "PRECISION_NAVIGATION")`; CSIA answers with the state,
the limiting domain, the reason codes and the host's own declared fallback.
**The autopilot owns the switching action.**

That separation is not deference. It is what makes the same middleware serve
an aircraft and a factory machine, and it is what keeps the certification
argument tractable: an advisory component that cannot actuate has a different
and much smaller assurance obligation than one that can.

`csia/v1_1/firewall.py` already enforces the equivalent boundary for v1.1
outputs by default-deny. v2's API has no command surface at all, and a test
asserts that no public function in `csia/v2/api.py` is named for an action.

## 7. WHAT WOULD HAVE TO BE TRUE BEFORE ANY OF THIS FLIES

Unchanged from v1.1, and v2 does not move it: no hardware has been measured,
every threshold in every profile is declared configuration rather than a
characterisation, and every scenario is synthetic. v2 adds architecture, not
evidence about a vehicle.
