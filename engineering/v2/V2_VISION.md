# CSIA v2 — VISION

**No novelty is claimed** (§39). Modularity and cross-domain monitoring are
ordinary product architecture. Research novelty remains a separate workstream
and nothing in v2 contributes to it.

---

## 1. THE CHANGE OF ABSTRACTION — §0

v1.1 answers:

> which SENSORS can be trusted right now?

v2 answers:

> which FUNCTIONS of this electromechanical/autonomous system remain
> justified right now, based on which evidence, and **what domain is
> limiting them**?

The last clause is the one a sensor-health tool cannot reach at all, and it is
the reason the abstraction has to move rather than widen.

## 2. WHY NOT JUST ADD NODES — §1

The obvious cheap move is to put the 5 V rail, the CPU and the CAN bus into
the existing trust graph as more nodes. It is the wrong move, for a reason
that is structural rather than aesthetic.

The v1 trust core is a Beta recursion over **cross-sensor consistency**. Two
sensors that should agree, and a residual that says whether they do. That
model has content precisely because "these two measure the same physical
quantity" is true of the sensor set.

It is not true of a power rail. A 5 V rail is not inconsistent with a CPU
load; it either is or is not within its regulator's declared tolerance, and
the answer is a threshold comparison against a datasheet, not a likelihood.
Forcing it through the recursion would produce a number that looks like a
trust and means nothing — which is exactly what §18 exists to prevent.

So a domain is a **plugin**: it owns its own relations, emits the common
`EvidenceRecord`, and meets the other domains only at the function graph.
The eight-node sensor graph stays eight nodes and stays v1.1's.

## 3. THE SHAPE

```
  raw platform signals                     v1.1 output payload (schema 1.1.0)
          |                                             |
          v                                             v
  +---------------------------------------------------------------+
  |  DOMAIN PLUGINS   POWER  COMPUTE  TIMING  COMM  ACTUATION  ... |
  |                   SENSOR = the v1.1 wrapper                    |
  +---------------------------------------------------------------+
          |  EvidenceRecord (categorical verdict + optional numbers)
          v
  +---------------------------------------------------------------+
  |  FUNCTION GRAPH        which functions are still justified     |
  |  ATTRIBUTION           UNIQUE / AMBIGUOUS / UNSUPPORTED / none |
  +---------------------------------------------------------------+
          |
          v
  SYSTEM ASSURANCE  +  per domain  +  per function  +  WHAT LIMITS IT
          |
          v
  the autopilot / controller decides what to DO about it   (§33)
```

## 4. WHERE v2 SITS RELATIVE TO v1.1 — §19

**Above the published API, never inside the frozen runtime.**

`csia/v2/` imports exactly one thing from `csia/v1_1/`: the payload parser
(`csia.v1_1.monitor.parse`). It imports no producer — not the trust engine,
not the diagnosis, not the eligibility policy — and a test asserts that by
parsing the import graph. The consequence is that v2 *cannot* alter a v1.1
verdict, because it has no way to compute one.

v1.1 becomes the SENSOR domain. Its five functions keep their names, and its
verdict for each of them survives intact in `domain_states["SENSOR"]` while
the v2 function of the same name composes it with power, compute, timing and
communication. §36's exactness test and the monotonicity property are what
make that checkable rather than promised.

## 5. WHAT IS DELIBERATELY NOT HERE

**No ML or LLM in the decision path** (§31). The optional AI analyst of
§§31–32 is documented in `V2_IMPLEMENTATION_PLAN.md` and is not built. A test
asserts that no learning library is imported anywhere in `csia/v2/`.

**No scalar system health.** Not in the evidence record, not in the API
document, not anywhere. A "system health: 82%" field would re-import exactly
the false comparability that keeping evidence categorical exists to prevent,
and `csia/v2/api.py` refuses a document that has grown one.

**No command, no mode, no switch** (§33). CSIA answers "is precision
navigation eligible?" and reports the host's own declared fallback back to it.
The autopilot owns the action. That separation is what lets the same
middleware serve an aircraft and a factory machine, and it is what makes a
certification argument tractable.

**No unmodelled-fault hypothesis.** v1.1 does not have one; v2 does not add
one. `UNKNOWN` means the policy could not determine eligibility, and it is not
a synonym for "something unknown is wrong".

## 6. THE QUESTION THIS ARCHITECTURE IS BUILT TO ANSWER — §38

> Is CSIA aircraft sensor assurance, or reusable electromechanical/
> autonomous-system assurance middleware?

The architecture is arranged so that **evidence can decide it**. Two profiles
exist: a multirotor with v1.1 wrapped as its SENSOR domain, and an electric
motor test stand with no SENSOR domain, no v1.1 and no aviation vocabulary.
If the second one had required one line of aircraft-specific code in
`csia/v2/`, the answer would be A and the framework would be misnamed.

The verdict, and the evidence for it, are in `V2_CHATGPT_REVIEW_REPORT.md`.
