# Prior-art matrix — end-to-end evidence-semantic equivalence

Item 4. Searched August 2026, before any tooling was built (item 3 orders it).
The purpose was to **kill** the direction, not to defend it.

## Method, and its limit — read this before the table

Searches were run with a web-search tool that returns titles, URLs and
extracted snippets. **Full-text retrieval was blocked by this environment's
egress policy for every scholarly host tried** (`dl.acm.org`, `arxiv.org`,
`sciencedirect.com`, `sigmodrecord.org`, `users.metu.edu.tr`,
`reference.opcfoundation.org` — all returned `EGRESS_BLOCKED`). So each row
below is grounded in title + venue + returned snippet, not in a reading of
the paper.

That is a real limitation and it cuts one way only: **it can only cause prior
art to be UNDER-stated.** Any row marked "overlap: total" is safe; any row
whose surviving difference looks generous should be assumed to be too
generous. No claim in this package rests on a paper being narrower than its
abstract suggests.

Term families searched (item 3's list, condensed to the queries actually
run): sensor status propagation verification · quality metadata propagation ·
abstraction-induced diagnosability loss / DES observation masks · ISO 26262 &
AUTOSAR E2E protection · assume-guarantee interface contracts & compositional
verification · ROS 2 / DDS sample validity semantics · OPC UA StatusCode
propagation & conformance · differential testing of protocol parsers ·
quality-flag propagation in data-reduction pipelines · SQL null semantics
(applicable vs inapplicable) · SOTIF sensor degradation · information-flow /
taint / provenance propagation · MAVLink `fix_type` handling conformance ·
SSN/SOSA observation quality · device-driver conformance model checking ·
runtime verification of robotic middleware adapters.

---

## The five statuses item 4 requires

| Area | Status | Why |
|---|---|---|
| **GENERIC_EQUIVALENCE_CHECKING** | **KNOWN/SUBSUMED** | Bounded exhaustive search for a shortest distinguishing trace over a finite alphabet is textbook. Trace equivalence, bisimulation, refinement checking, differential testing and CEGAR all predate this by decades, and `ParDiff` (OOPSLA 2024) does *static* differential analysis of multiple protocol-parser implementations specifically to find semantic discrepancies. Nothing about the search here is claimed. |
| **STATUS_PROPAGATION** | **KNOWN/SUBSUMED** | Value+status pairs and rules for how status must propagate are standardised in at least four independent traditions: ARINC 429 SSM, SEVA, NAMUR NE 107 and OPC UA. OPC UA even specifies the *merge* rule this package's contracts encode — a returned array's StatusCode severity must be Bad if any element is Bad, Uncertain if any is Uncertain. That is an allowed-merge clause in a published conformance specification. |
| **END_TO_END_EVIDENCE_SEMANTICS** | **NOT ESTABLISHED AS NOVEL — closest neighbours are strong** | AUTOSAR E2E protection is literally "end-to-end preservation of a status through a communication chain", with a receiver-side state machine and profiles; quality-flag propagation through multi-stage data-reduction pipelines is routine in astronomy/EO (DQ arrays are conserved and combined stage by stage). Neither is framed as *verifying* that an assurance pipeline preserves distinctions, but the property being preserved is the same kind of thing. |
| **DIAGNOSTIC_CONSEQUENCE_LINK** | **PARTIALLY OPEN — the least covered of the five** | DES diagnosability under observation masks is exactly "a coarser observation destroys the ability to diagnose", and is total prior art on the *formal* result. What was not found is a tool that takes a real sensor-ingest implementation, finds where a distinction dies, and then *measures* what the loss does to a downstream diagnostic and failsafe layer. This is the only place where something specific survives, and it survives as engineering, not theory. |
| **DOMAIN_SPECIFIC_AUTONOMY_CHECKER** | **NOT ESTABLISHED AS NOVEL** | Runtime verification for ROS/robotic middleware is an active area with published adapters (e.g. an RTLola ROS adapter, RV4JaCa, contract-based RV monitors for modular robotic systems). A monitor comparing an event trace against a formal model of intended behaviour is precisely the shape of the checker in this package. |

**Overall: nothing in this direction is available as a novelty claim.** See
§"What survives" at the bottom for the narrow engineering residue.

---

## Matrix

Columns follow item 4. "Multi-path" = compares two or more independent
implementations of the same interface. "E2E status" = verifies a status
survives a whole chain. "Min CE" = generates minimal counterexamples.
"Diag consequence" = measures the effect on a downstream diagnosis.
"Autonomy sensor pipelines" = targets heterogeneous autonomy ingest.

| Work | Year | Field | System | Semantic state model | Multi-path | E2E status | Min CE | Diag consequence | Autonomy | Exact overlap | Surviving difference |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **ParDiff — static differential analysis of network protocol parsers** (Zheng et al., OOPSLA / PACMPL 2024) | 2024 | PL / security | Network protocol parsers | Symbolic FSAs lifted from parser code | **Yes** | No | Discrepancy witnesses | No | No | **Total** on cross-implementation semantic-discrepancy finding | Field/format level, not a quality coordinate; no downstream consumer is modelled |
| **Differential testing generally** (cross-referencing oracle; JSON parsers ASIA CCS 2024; HTTP Garden 2024; JEST 2021) | 2021–24 | SE / security | Parsers, engines | none — output comparison | **Yes** | No | Shrinking / minimisation is standard | No | No | Total on "run one input through N implementations and diff" | none |
| **AUTOSAR E2E Protection Library / ISO 26262** | 2003– | Automotive safety | ECU communication | E2E state machine: OK / repeated / wrong-sequence / error, with counters and thresholds | No | **Yes** | No | No | No | **Total** on "a status must survive the whole communication chain and the receiver must maintain a state machine over it" | Protects against corruption/loss/repetition of a *message*; says nothing about a consumer collapsing two legitimate source states |
| **OPC UA StatusCode / DataAccess quality, incl. PROFINET qualifier mapping** | 2006– | Industrial automation | Client/server, gateways | Value + 32-bit StatusCode with sub-bits; Good/Uncertain/Bad severities | Gateway mappings are specified | **Yes**, by specification | No | No | No | **Total** on value/status separation AND on specified allowed merges (worst-of propagation for arrays) | Specification, not a checker; consumer-side loss is a known practical failure, not a verified property |
| **SEVA self-validating sensors** (Henry & Clarke, Oxford, 1993; US 5570300) | 1993 | Process instrumentation | Smart transmitters | VMV / VU / MV Status | No | No | No | Partially — status carries fault info | No | Total on separating a measurement from a status that stays informative when the value is not | Sensor-side; assumes the consumer honours the status |
| **NAMUR NE 107** | 2006 | Process automation | Field devices | Failure / Function Check / Out of Spec / Maintenance Required, split operator-summary vs technician-detail | No | No | No | Yes, by construction | No | Total on the operational/diagnostic audience split | Says nothing about a consumer's admissibility gate destroying it |
| **ARINC 429 SSM** | 1977– | Avionics | Data bus | NO / FT / FW / NCD in-band; absence by refresh-rate timeout | No | No | No | No | Partly | Total on an in-band status vocabulary; the timeout convention for absence is borrowed directly by this package's `t1_protocol` | Wire-level encoding, no consumer obligation |
| **DES diagnosability under observation masks / partial observation** (Sampath et al. 1995 and successors; abstraction-based diagnosis, Schmidt 2009; unified framework for observational properties, 2022) | 1995– | Discrete-event systems | Automata | Observation mask over an event set; diagnostic partition on states | No | n/a | Counterexamples in the twin-plant sense | **Yes — this IS the formal result** | No | **Total** on "coarsening an observation can destroy diagnosability", including the abstraction-preserves-diagnosability conditions | Framed as sensor-selection / mask design, not as an implemented ingest path to be audited |
| **Codd's A-marks and I-marks; SQL's conflation of them** (Codd 1979/1986–87; *On the Codd semantics of SQL nulls*, 2019) | 1979– | Databases | Relational model | Two distinct nulls: missing-but-applicable vs inapplicable | No | No | No | No | No | **Total** on the shape of finding F1. SQL deliberately merged two semantically distinct absences into one marker, and the consequences have been studied for forty years. The GNSS `I ≡ N` collapse is the same mistake in a different domain | none — this is the cleanest single piece of prior art for the *state model* |
| **Missing-indicator methods / MNAR** | — | Statistics, clinical ML | — | Binary missingness indicator | No | No | No | Partially | No | Total on "absence is informative" | Does not distinguish *kinds* of absence |
| **Quality-flag propagation in data-reduction pipelines** (HST/ACS DQ arrays; Herschel-HIFI; Landsat pixel QA) | 1990s– | Astronomy / EO | Multi-stage pipelines | Per-pixel DQ bitmask, conserved and OR-combined across stages | No | **Yes** in practice | No | No | No | Total on "carry a quality flag through every processing stage and combine it explicitly" | Engineering convention; no verification that a stage preserves what it should |
| **Assume-guarantee contracts / compositional verification** (Benveniste et al.; Pacti, ACM TCPS 2025; AG refinement via LP, 2021) | 2000s– | Formal methods / CPS | Components | Assume/guarantee pairs, refinement, quotient | n/a | via refinement | via model checking | No | Some | **Total** on the compositional question in item 21 | General theory; nothing sensor-semantic about it |
| **Runtime verification for robotic middleware** (RTLola ROS adapter, RV 2025; RV4JaCa 2023; contract-based RV for modular robotic systems, 2022) | 2019– | RV / robotics | ROS nodes | Monitors over event traces vs a formal spec | No | Partially | No | No | **Yes** | Total on "attach a contract monitor to an autonomy middleware interface" | Monitors behaviour, not the evidence-quality coordinate specifically |
| **Information-flow / taint / provenance tracking** | 1976– | Security / systems | Programs | Labels propagated through data and control dependencies | No | **Yes** — label preservation IS the property | No | No | No | Total on "verify a metadata tag is not dropped as data flows through a program" | Confidentiality/integrity labels, not measurement-quality states |
| **SOTIF / ISO 21448** | 2022 | Automotive | Perception | Functional insufficiency, performance limitation | No | No | No | No | Yes | Low — concerns the sensor's *limits*, not the software's handling of a reported status | none needed |

---

## Internal prior art — and it is the closest of all

**This repository already contains a per-channel machine-readable semantic
contract, and it already states the exact distinctions this package's
contracts encode.**

`docs/simulation/CHANNEL_SEMANTICS.yaml` has one row per channel with a
`missing_semantics` field. Three rows, verbatim:

| channel | `missing_semantics` |
|---|---|
| `gnss.position` | "fix_type < 3 is NOT a zero position. It is MISSING with reason NO_3D_FIX. Treating it as a position at the origin would inject a fictitious kilometre-scale jump." |
| `battery.current` | "-1 means 'not measured' -> MISSING, not zero current" |
| `mag.field_ut` | "all-zero triple is treated as ABSENT, not as a zero field" |

It also supports **per-platform overrides**, and the PX4 row for
`battery.current` is set to `UNAVAILABLE` with a measured justification
("390 producer frames in 40 s (~9.8 Hz), every one carrying the -1 sentinel").

So the *content* of `ARDUPILOT_INGEST_CONTRACTS/*.json` is, to a first
approximation, already written down here. Two things are different, and only
these two:

1. `missing_semantics` is **prose**. It is loaded into
   `ChannelContract.missing_semantics` (`csia/aircraft/qualification.py:83`)
   and used in exactly one place — as a `note=` string on a `NOT_RECEIVED`
   ChannelValue (`qualification.py:243`). No code reads it as a requirement,
   and `tests/test_channel_semantics.py:28` only checks that the field is
   non-empty.
2. Nothing checks that the pipeline **honours** it along a trace.

That is the honest description of what this package adds, and it is small:
it turns three sentences of existing documentation into three checkable
clauses and then shows they are violated.

---

## Novelty kill conditions (item 26), applied

Item 26 says: if an existing method already (a) defines equivalent evidence
semantics, (b) verifies end-to-end preservation across sensor adapters,
(c) generates minimal counterexamples, and (d) connects violations to
diagnostic consequences — then mark KNOWN/SUBSUMED and stop.

No single work found does all four. But:

* (a) is done better by NE 107 / SEVA / OPC UA and, for the state model
  itself, by Codd.
* (b) is done by AUTOSAR E2E for a different property and by DQ-array
  pipelines as an engineering convention.
* (c) is done by ParDiff and by every differential-testing paper.
* (d) is done as theory by DES diagnosability under masks.

**Four out of four exist; what does not exist in one place is the
combination.** A combination of four established techniques applied to one
codebase is not a dissertation contribution, and this matrix is not going to
be argued into saying otherwise. The verdict follows in
`CHATGPT_REVIEW_REPORT.md`.

---

## Not searched, and it should be before any publication

* IEC 61508 / 61511 diagnostic coverage and the "detected dangerous" vs
  "undetected dangerous" split — flagged as unsearched in the previous
  package and **still unsearched**.
* AFDX / ARINC 664 and MIL-STD-1553 status-word handling.
* Active diagnosis / diagnosability-enforcing supervisor synthesis.
* The DDS specification's `SampleInfo.valid_data` / instance-state semantics
  directly — the searches returned QoS material rather than the sample-state
  semantics that were actually wanted, and the specification itself was not
  retrievable here.
* Whether any of the RV-for-ROS tools has been applied specifically to
  sensor-quality metadata.

## Sources

Snippet-level only, per the method note above.

- [ParDiff: Practical Static Differential Analysis of Network Protocol Parsers (OOPSLA 2024)](https://dl.acm.org/doi/10.1145/3649854)
- [Cross-Language Differential Testing of JSON Parsers (ASIA CCS 2024)](https://dl.acm.org/doi/10.1145/3634737.3657003)
- [The HTTP Garden: Differential Fuzzing of HTTP/1.1 Implementations](https://arxiv.org/pdf/2405.17737)
- [AUTOSAR E2E Communication Protection](https://piembsystech.com/autosar-e2e-communication-protection/)
- [Overview of Functional Safety Measures in AUTOSAR (CP R22-11)](https://www.autosar.org/fileadmin/standards/R22-11/CP/AUTOSAR_EXP_FunctionalSafetyMeasures.pdf)
- [OPC UA Part 8: DataAccess — A.4.3.3 Quality](https://reference.opcfoundation.org/specs/OPC-10000-8/a-4-3-3)
- [OPC UA for PROFINET Remote IO — 6.8 Process Value Qualifier and StatusCode Relationship](https://reference.opcfoundation.org/specs/OPC-30142/6.8)
- [Recent Developments in Self-Validating (SEVA) Sensors — Oxford](https://ora.ox.ac.uk/objects/uuid:7af9a330-acb3-4b7f-9710-9da32477d9f0/files/m5f74fcae4a384cff560c88d5c98873de)
- [Why NAMUR NE 107 matters for device health — Endress+Hauser](https://www.endress.com/en/support-overview/learning-center/namur-ne-107)
- [Abstraction-based failure diagnosis for discrete event systems (Schmidt, 2009)](https://users.metu.edu.tr/schmidt/SCL2009_schmidt.pdf)
- [A Unified Framework for Verification of Observational Properties for Partially-Observed Discrete-Event Systems](https://arxiv.org/pdf/2205.01392)
- [Missing information (applicable and inapplicable) in relational databases — ACM SIGMOD Record](https://dl.acm.org/doi/10.1145/16301.16303)
- [On the Codd semantics of SQL nulls](https://www.sciencedirect.com/science/article/abs/pii/S0306437918301625)
- [A More General Model For Handling Missing Information In Relational Databases (SIGMOD Record)](https://sigmodrecord.org/publications/sigmodRecord/9109/pdfs/126482.126487.pdf)
- [Verifying Compositional Refinement of Assume/Guarantee Contracts using Linear Programming](https://arxiv.org/abs/2103.13743)
- [Pacti: Assume-Guarantee Contracts for Efficient Compositional Analysis and Design (ACM TCPS)](https://dl.acm.org/doi/10.1145/3704736)
- [A ROS Adapter for RTLola (RV 2025)](https://link.springer.com/chapter/10.1007/978-3-032-05435-7_6)
- [A Compositional Approach to Verifying Modular Robotic Systems](https://arxiv.org/pdf/2208.05507)
- [RV4JaCa — Runtime Verification of Multi-Agent Systems and Robotic Applications](https://www.mdpi.com/2218-6801/12/2/49)
- [DQ Flag Definitions — STScI](https://www.stsci.edu/hst/instrumentation/acs/data-analysis/dq-flag-definitions)
- [The Data Processing Pipeline for the Herschel-HIFI Instrument](https://arxiv.org/pdf/1905.04029)
- [Dynamic Information Flow Tracking: Taxonomy, Challenges, and Opportunities](https://pmc.ncbi.nlm.nih.gov/articles/PMC8399738/)
- [Runtime Analysis of Whole-System Provenance](https://arxiv.org/pdf/1808.06049)
- [What is ISO 21448 (SOTIF)?](https://www.swiftnav.com/glossary/what-is-iso-21448)
- [Semantic Sensor Network Ontology (W3C/OGC, 2023 edition)](https://www.w3.org/TR/vocab-ssn-2023/)
