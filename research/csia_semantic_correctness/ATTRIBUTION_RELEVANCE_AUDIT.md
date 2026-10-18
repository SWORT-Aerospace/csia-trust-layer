# Attribution relevance audit (Parts 1, 2, 3, 4, 7)

CSIA semantic correctness audit, 2026-09-29.

- **Result ids.** They refer to `semantic_probe_results.json`.
- **Literature ids** (`Lnn`). They are defined in `SOURCES.md`. Every
  external source is at V0, a search summary only.

## 1. Answer

**Can current CSIA become more certain for the wrong reasons? Yes**, in both
halves of the reasoning.

- **Attribution** turns AMBIGUOUS into UNIQUE on the strength of one NOMINAL
  record that has nothing to do with the candidate (R1).
- **In shipped profiles** attribution has never once withheld UNIQUE from a
  single adverse component. That held on 889 of 889 single-candidate ticks
  (E.tick_census).
- **Localization** is changed by records about components that its subject
  does not use, in both directions:
  - adding them: P1, N5 (94 of 96 configurations);
  - removing them: P2.

## 2. Part 2: what "relevant" means today

**Relevance is not represented explicitly anywhere in v2. This is an
architectural fact.**

Each stage infers it from a different structure
(`CURRENT_SEMANTICS_MAP.md` §5):

| stage | inferred from | consequence |
|---|---|---|
| attribution discriminator | domain label only (attribution.py:174-176) | any NOMINAL record in any other domain counts |
| attribution common cause | declared `dependencies`, reachability | relevant, but only for **adverse** shared nodes |
| attribution `unsupported` | relation table (attribution.py:163-167) | lists implicated components without looking at whether they were observed |
| localization, channel or actuator subjects | the subject's declared `dependencies` in a domain | relevant |
| localization, function subjects (POSITION_UNAVAILABLE) | nothing: whole-tick aggregates | any process, link or channel anywhere |
| function graph | `affected_functions` per record | relevant, but a different declaration from the dependencies |
| `EvidenceRecord.source` | never read | two detectors of one source are indistinguishable from two sources |

The repository already contains a relevance-gated rule, outside v2.

- **Where.** `csia_assurance/firewall.py` (the EXPERIMENTAL support layer
  over v1).
- **The rule.** The leader is `SUPPORTED_UNIQUE` only with
  `ACTIVE_WITNESS_AGAINST_EVERY_COMPETITOR` (firewall.py:274). A witness
  counts against a competitor only if the two signatures differ on it.
- **Use here.** This is the reuse precedent for the correction
  (`MINIMAL_CORRECTION_DESIGN.md`, C1). It is the same idea as fault
  isolability from a fault signature matrix (L02). A test that is insensitive
  to both faults cannot separate them.

## 3. Part 3: irrelevant-evidence invariance

### 3.1 The established concept

The property in the brief is well known under several names. None of them
needs a CSIA-specific term.

| field | name | what it says | source |
|---|---|---|---|
| fault detection and isolation | **isolability** / fault signature matrix | a residual isolates fault *i* from fault *j* only if it is sensitive to one and not the other | L02 |
| belief revision | **Parikh's relevance-sensitive axiom (P)** | new information about one compartment of a split belief set must not change the other compartment | L03 |
| nonmonotonic inference | **the irrelevance problem**; rational monotony | adding information that does not bear on a conclusion should not withdraw it | L04 |
| probabilistic reasoning | conditional independence (d-separation) | evidence d-separated from the query does not change its posterior | general textbook background, not cited as a verified source |

**This package uses "irrelevance invariance".** It means isolability applied
to discriminators, plus Parikh's axiom applied to candidate sets.

### 3.2 What was tested

**P1: add one record about a component nothing declares.** The additions
were:

- relations for six component types: a process, a link, a channel, a rail,
  an actuator and a sensor source;
- each in five states: NOMINAL, DEGRADED, VIOLATED, UNAVAILABLE and
  NOT_APPLICABLE;
- applied to the final tick of each of the 44 shipped scenarios.

That gives 1,320 cases.

| result | frozen | shadow |
|---|---|---|
| cases where a localization on **another** subject changed, or appeared | **142** (71 DEGRADED, 71 VIOLATED additions) | **0** |
| attribution changed on a NOMINAL addition | 0 | 0 |
| attribution became more certain (AMBIGUOUS to UNIQUE) | 0 | 0 |
| attribution lost a candidate | 0 | 0 |

**Why attribution never failed P1 on this corpus.** Every shipped tick already
contains dozens of NOMINAL records in other domains, from 18 to 57 per final
tick (E.baseline). One more makes no difference. The attribution violation
therefore appears only where the corpus does not reach:

- **R1.** One extra record turns AMBIGUOUS into UNIQUE.
- **N2.** Exhaustive enumeration of three components in three domains
  (125 configurations): an unrelated NOMINAL component turns the verdict
  UNIQUE in **6** configurations. The shadow: 0.

**P1's 142 localization failures have a single mechanism.** An adverse
process, link or channel anywhere creates POSITION_UNAVAILABLE on the
navigation functions. It does so through the whole-tick predicates and the
detector (SC-05).

**N5 isolates the same effect.** It enumerates every combination of
PRECISION_NAVIGATION's own declared evidence: v1.1 verdict, nav channel, GNSS
link and estimator, giving 96 configurations. Each is run against every
combination of three components it does not use: the logger, the telemetry
radio and the telemetry channel, giving 48 variants.

| | frozen | shadow |
|---|---|---|
| configurations whose result is changed by an irrelevant component | **94 of 96** | **0** |
| irrelevant variants that **create** a SUPPORTED verdict | **572** | 0 |

**Unrelated evidence also misses a different case: stale and contradictory
records.** The brief asks for irrelevant evidence that is stale or
contradictory "if current structures can express that".

- **Stale.** Current structures cannot express staleness to reasoning.
  Timestamps are carried but never read by localization or attribution
  (`CURRENT_SEMANTICS_MAP.md` §1).
- **Contradictory.** Contradiction is expressible, as two records for one
  (relation, component). It is covered under order (R6), because what it
  exposes is order dependence.

## 4. Part 4: removal, classified by reasoning path

**P2.** Remove each record of each shipped final tick in turn. Classify the
removal against every result it could touch.

**The classification uses the declared structure, not the change alone.**

- **A localization's scope is:**
  - its subject;
  - the channels, processes and links whose `affected_functions` name it;
  - everything those declare as dependencies, transitively;
  - a channel's own segment records.
- **Attribution's scope is:** the candidates, their declared alternatives and
  every adverse attributable record.

| class | definition | frozen | shadow |
|---|---|---|---|
| ESSENTIAL | in scope; removal changes the verdict | 227 | 276 |
| RELEVANT | in scope; removal changes the candidate sets or nothing | 2,208 | 2,041 |
| IRRELEVANT_BUT_DECISION_CHANGING | out of scope, and the subject declares a component in that record's domain (so the relevant one is known and this is not it); removal changes the decision | **6** | **0** |
| IRRELEVANT_AND_INVARIANT | out of scope; nothing changes | 6,792 | 5,735 |
| UNKNOWN | out of scope, but the subject declares **nothing** in that record's domain, so relevance cannot be decided from declarations | **17** | **0** |

The frozen and shadow totals differ because the shadow produces fewer
localizations. That reduces the number of record-by-result pairs.

**The six IRRELEVANT_BUT_DECISION_CHANGING cases (frozen).**

| scenario | removed record | result | change |
|---|---|---|---|
| MS_B1_COMMAND_LOST | ESC CAN link VIOLATED | POSITION_UNAVAILABLE on POSITION_HOLD and on PRECISION_NAVIGATION | SUPPORTED COMMUNICATION/starvation → symptom gone |
| NETWORK_LATENCY | telemetry downlink transport segment VIOLATED | the same two | UNSUPPORTED → **SUPPORTED** TIMING/deadline_violation |
| NETWORK_LATENCY | telemetry downlink end-to-end VIOLATED | the same two | UNSUPPORTED → symptom gone |

**The reasoning path.** Each of these records is read by a whole-tick
predicate, either FUNCTION_LINKS_NOMINAL or NO_TIMING_SEGMENT_OVER_BUDGET,
for a navigation subject it does not serve. In NETWORK_LATENCY, removing an
irrelevant record makes a navigation localization **more** certain.

**The 17 UNKNOWN cases** are all POSITION_UNAVAILABLE on COARSE_NAVIGATION.

- **Why unknown.** The profile does not declare any channel, process or link
  as serving COARSE_NAVIGATION. The estimator's `affected_functions` are
  PRECISION_NAVIGATION, POSITION_HOLD and AUTONOMOUS_MISSION. Relevance
  therefore cannot be decided from the declarations.
- **What this points to.** A profile declaration gap (SC-18, gap G-1), not
  only a reasoning defect.

**Attribution removal.** In the shipped corpus no single removal changed an
attribution decision. Each tick has many discriminators, so removing one is
invisible. The effect of removing the **last** irrelevant discriminator is R1
read backwards: UNIQUE becomes AMBIGUOUS.

## 5. Part 7: correlated evidence

**Can current CSIA tell three independent witnesses from three derived views
of one witness? No.** What decides the outcome is only how the producer
**names** its records (R18):

| producer naming | attribution | localization |
|---|---|---|
| three relations of one component | one candidate (correct, by accident of naming) | — |
| three components, each declaring the IMU as a dependency | three competing candidates; the IMU is not a common cause unless it has its **own** adverse record | — |
| three `v1_1.source_health` records differing only in `source` | one candidate | MULTIPLE_SENSORS_DEGRADED, "two or more sensor-derived sources are adverse", from one sensor |

The specific gaps:

- **Detector identity.** `EvidenceRecord.source` is read by no reasoning
  path.
- **A shared physical source.** SENSOR is not a common-cause domain
  (signatures.py:243). A shared physical source can therefore never be named
  by localization.
- **Counting.** Common-cause reach counts each adverse record, so a
  duplicated or derived record counts twice. This is R7B, and P4 found it in
  3 shipped cases.

**What set semantics already guarantees.** The attribution *verdict* is set
based, not count based:

- one discriminator or fifty give the same UNIQUE;
- one adverse record or three for the same component give one candidate.

So double-counting cannot inflate a score, because there is none. It changes
conclusions only through the two thresholds that count records:

- `len(_adverse_sources) >= 2`;
- shared-node reach ≥ 2.

**Established methods** exist, and the architecture package already names
them:

- the cautious rule is idempotent for non-distinct evidence (L10);
- ATMS labels carry the assumptions each datum rests on (L11).

**Not implemented here, as the brief requires.** The correction design leaves
this as a recorded limitation (SC-14) and does not propose a fix in the
minimal set.

## 6. Why the shipped scenarios did not expose it

The frozen test suite checks UNIQUE on scenarios where the relevant
alternatives **are** observed and NOMINAL. For example, REGULATOR_FAILURE
observes the battery and PROCESS_STALL observes the CPU.

In those cases the relevance-gated rule and the frozen rule agree. C1 alone
changes **0** of 2,640 shipped ticks (SH.ALL_TICKS). Every shipped UNIQUE
therefore happens to satisfy the stricter rule.

The defect shows only when:

- an alternative is unobserved or UNAVAILABLE (R2, R3, R8G); or
- the alternative is declared nowhere but in localization, as the response
  sensor is (MS_B5, which F2 catches).

**The tests exercised the rule only on inputs where its missing condition
happened to hold.**
