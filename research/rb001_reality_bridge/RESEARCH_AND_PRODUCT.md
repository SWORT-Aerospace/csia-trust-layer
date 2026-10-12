# The research question and the product question (RB-001 Parts 30-31)

**2026-10-02.**

## 1. Part 30: the research question is not asked yet

**The brief: "Only after physical data exists ask whether a research
contribution emerged."** No physical data exists in RB-001
(`HARDWARE_INVENTORY.md`). So the question is **not asked**, and no
contribution is claimed.

**What is fixed now** is what each candidate question would need, so that
the physical data cannot be read into a question chosen afterwards. The
three candidates are the brief's examples.

| candidate question | what the physical data would have to show | what is already known (not physical) | established methods that may already solve it |
|---|---|---|---|
| a sim-to-real evidence-validity problem: evidence valid in SITL silently stops being valid on hardware | on RB2/RB3/RB5 data, a 2.3 output keeps its SITL meaning in some conditions and loses it in others, and the loss is invisible without an explicit validity condition | RB0: the steadiness condition does not transfer (RR-06); the gap rule depends on timing (RR-04/05). Both are validity conditions failing, not evidence failing silently: in both cases the product refused rather than misreported | domain-shift detection and applicability-domain checks in data-driven FDI; a validity condition per statistic is ordinary engineering practice |
| maneuver-conditioned evidence: a control-conditioned residual keeps evidence valid through maneuvers | on RB5/RB6 flights, B3 or B4 (if one passed in SITL) keeps zero false symptoms in nominal maneuvering at the Part 15 budget and detects the RB5 reversible loss mid-maneuver | the SITL maneuver study (`MANEUVER_STUDY.md`) | **yes**: model-based FDI (parity space, GLR, unknown-input observers, control-allocation-aware estimators) is decades old; the SITL candidates are textbook forms (`LITERATURE.md`). A contribution would at most be an evaluation, not a method |
| dependency-aware physical assurance: lineage from the real hardware map changes the conclusion | the Part 24/25 cases (`PHYSICAL_EVIDENCE_CASES.md`): agreement between outputs that share an ESC MCU or a power rail is reported as one line, and that changes what an engineer would conclude | SIH: the lineage policy did not over-count (2.2 pilot, 121/121); its roots came from topic structure | common-cause analysis (FMEA/CCA, ARP 4761), dependence diagrams; the question is whether an offboard log analyzer applies them correctly to real lineage |

**Not forced.** If the physical data shows only that established methods
work once recalibrated, that is the result: use them. The brief: "If
established methods solve the problem: use them."

## 2. Part 31: is CSIA useful to an engineer on physical hardware?

**Not answerable from this session.** No engineer has used it on a
physical log, and no physical log with a propulsion event exists here.
The table records what is known, from where, and what would answer each
question. "Did our tests pass?" is not the question, so test results are
not listed as answers.

| the brief's question | what is known | from | what would answer it |
|---|---|---|---|
| does it expose something useful that raw telemetry or individual monitors do not? | in SITL, yes in a narrow case: it separated a motor loss (telemetry and compensation agree) from an ESC telemetry fault (telemetry alone), which an RPM plot alone does not do | 2.3 V1-V4, V9, V10 (SITL) | RB2-3: A (real motor change) against B (telemetry-only change), read by an engineer with and without the report |
| does it prevent false certainty? | it has never given a wrong UNIQUE; on stock evidence it gives AMBIGUOUS among 4 and says which evidence would split them; on the 4 real boards' logs it claimed nothing | 2.3, RB0 | the Part 15 budget on 300 nominal hours; the Part 32 study's "cannot tell" answers |
| does it identify missing evidence? | **yes, on real logs**: on all four real boards it listed what it could not observe and why (no `actuator_motors`, no ESC telemetry, the estimator schema). Before RR-01 it crashed instead | RB0 (real) | a real propulsion log where some telemetry is missing (RB2-0: telemetry wire unplugged) |
| does it explain dependencies? | in SITL it reported 2 adverse outputs as 1 independent line where they shared the motor commands | 2.3 V1, 2.2 pilot | Part 24/25 on the bench: lineage from the hardware map |
| does it make debugging easier? | unknown | — | the Part 32 external-engineer study, after the bench |

**What RB-001 adds to the answer.** It can say, for the first time on real
logs, that the analyzer degrades honestly when the log is not what it was
built for. That is a precondition for usefulness, not usefulness.

**The cheapest step that would change this table** is RB2-1 and RB2-3: one
motor and one ESC with telemetry on a load-cell stand, driven by PX4's
actuator test from a current-limited bench supply: no battery, no airframe,
and the propeller fitted only inside a guard. `MINIMUM_PHYSICAL_EXPERIMENT.md`
gives the parts and the procedure.
