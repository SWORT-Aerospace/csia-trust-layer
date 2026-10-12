# CROSS-DOMAIN RELATIONS AND CAUSE ATTRIBUTION — v2 §§14, 29

Implementation: `csia/v2/attribution.py`.

> This is where v2 becomes valuable. (§14)
> Do not invent certainty. (§29)

---

## 1. THE FOUR VERDICTS — §29

| verdict | meaning |
|---|---|
| `UNIQUE` | one candidate carries adverse evidence **and** something affirmatively excludes the others |
| `AMBIGUOUS` | several candidates carry adverse evidence and nothing separates them |
| `UNSUPPORTED` | a component is implicated by a relation but has no adverse evidence of its own |
| `NO_EVIDENCE` | nothing adverse anywhere |

These carry v1.1's discipline across domains. In Phase 2 a leader at posterior
0.9998 with zero discriminating evidence is `NON_IDENTIFIABLE`, not a
diagnosis. The mechanism here is structural rather than Bayesian — §18 forbids
forcing heterogeneous evidence through the eight-hypothesis core — but the
standard is identical: **a cause is named only when something rules the
alternatives out.**

## 2. WHAT MAKES A CANDIDATE UNIQUE

Not "it is the only one we noticed". A single adverse candidate with no
affirmatively nominal evidence from another domain returns `AMBIGUOUS`, with
the reason recorded: nothing has been ruled out, so nothing is claimed.

`UNIQUE` requires at least one **discriminator**: a `NOMINAL` record from a
different domain. Those are listed by name in the output, so a reader can
check what actually did the excluding instead of trusting that something did.

Affirmatively nominal readings inside the candidate's own domain — a healthy
battery beside a failing rail — are recorded separately in
`detail.same_domain_discriminators`. They are real exclusions and they are
reported, but they do not by themselves make a *cross-domain* attribution
unique: a deployment running one domain could otherwise claim system-level
uniqueness on single-domain evidence.

Uniqueness is always **among the modelled components**. v2 does not model
sub-components, so a unique attribution to `SENSOR/source.gps` does not
separate the receiver from its antenna. Listing the discriminators is what
lets a reader see the bound.

## 3. COMMON CAUSE — §14, §28 SCENARIO E

When several adverse candidates all transitively depend on a node that is
**itself adverse**, that node is retained as a `common_cause` **alternative**.
The verdict stays `AMBIGUOUS`.

That is the honest reading and it is not a hedge. A 5 V rail fault and two
coincident faults downstream of it produce the same evidence at this level of
modelling. "It must be the rail" is a guess dressed as a diagnosis; "these
three things are adverse and they share an adverse rail" is what is known.

Reachability, not adjacency. A rail feeds a converter feeds a bus feeds a
sensor: the sensor declares the bus, and nothing declares the rail twice, so
counting only direct dependencies would miss exactly the case §28-E is about.
The walk is over the host's declared graph, is cycle-safe, and ties break on
the node id so the answer does not depend on record order.

A shared dependency that is **healthy** is not offered as a common cause. The
battery feeds everything and is reachable from every candidate; when it reads
nominal the honest conclusion is that it has been exonerated, which is the
opposite of implicating it.

## 4. DECLARED RELATIONS

A `CrossDomainRelation` names an id, the domains it spans, the components it
can point at, and a description. It is data: listed in
`engine.declarations()`, carried into the API document, and reviewable.

The aircraft profile declares four:

| relation | spans | what it means |
|---|---|---|
| `actuation_power.demand_vs_current` | ACTUATION + POWER | actuator demand implies an expected current draw |
| `compute_timing.saturation_vs_latency` | COMPUTE + TIMING | CPU saturation → processing latency → missed deadline |
| `comm_sensor.link_vs_source` | COMMUNICATION + SENSOR | a source quiet behind a failing link is a link candidate |
| `power_sensor.shared_rail` | POWER + SENSOR | sources sharing a rail degrade together when it sags |

§14 also names FIRMWARE + TIMING (a message-rate parameter change altering
freshness behaviour). It is **not declared in either profile**, because the
firmware domain is not built: a relation that can only ever implicate a
component with no evidence would add an `UNSUPPORTED` entry to every timing
fault and teach an operator to ignore the field. It is specified in
`FIRMWARE_DOMAIN_SPEC.md` and will be declared when the domain exists.

## 5. HOW A RELATION PRODUCES `UNSUPPORTED`

A relation fires when any adverse record is in one of its domains. Every
component it `implicates` that carries **no adverse evidence of its own** is
listed as `unsupported`.

That is §29's third verdict doing real work, and it is where §28-B lands:
under a 5 V regulator failure the battery is named by the power relation,
carries no adverse evidence, and appears in `unsupported`. The operator reads
"the rail is the candidate; the battery was looked at and is fine" rather than
"POWER: FAULT".

## 5b. WHAT WAS RULED OUT, SAID RATHER THAN IMPLIED

§17's example output ends:

> sensor failure **unsupported**, transport failure **unsupported**, compute
> deadline violation **supported**

The first two are *not* `unsupported` in §29's sense. That word is reserved
for a component a relation **named** and the evidence did not support. A
domain that was looked at and found affirmatively fine is a stronger
statement, and it deserves to be said rather than inferred from an absence.

So an `AMBIGUOUS` verdict also carries `detail.domains_excluded` — domains
with affirmatively NOMINAL evidence and no candidate — and populates
`discriminators` with the records that did the excluding, by name. On the
ESTIMATOR_LATE scenario that reads `["ACTUATION", "COMMUNICATION", "POWER",
"SENSOR"]`, with COMPUTE and TIMING carrying the candidates.

The distinction is worth keeping sharp, because the two words mean opposite
things about how much work was done:

| | meaning |
|---|---|
| `unsupported` | a relation pointed here; there is no evidence for it |
| `domains_excluded` | this was measured, and it is fine |

## 6. DERIVED STATEMENTS ARE NOT CANDIDATES

Records marked `attributable=False` — roll-ups, aggregates, transcribed v1.1
function verdicts — are evidence for the domain state and the function graph
but never enter the candidate set. A conclusion computed from other records in
the same tick is not an answer to "what broke", and admitting it would count
its own inputs twice. Before this rule was added, the SHARED_RAIL scenario
produced eleven candidates, six of which were v1.1 function verdicts.

## 7. WHAT IS NOT DONE

- **No independence scores** (§22). Dependencies are walked, not weighted.
- **No probability over candidates.** There is no prior over "the rail failed"
  versus "two sensors failed together", and inventing one would be inventing
  certainty by a longer route.
- **No temporal reasoning.** Attribution is per tick. Onset order is in the
  ledger, and using it would need state the domain contract forbids.
