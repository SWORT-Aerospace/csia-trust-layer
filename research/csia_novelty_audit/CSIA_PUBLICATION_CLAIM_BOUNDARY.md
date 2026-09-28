# CSIA publication claim boundary (stage 2, pre-result)

This file is part of the second-stage novelty verification (2026-09-27/28).
Source ids are listed in `research/csia_novelty_audit/BIBLIOGRAPHY.md`.

**Written without reading XSYS-001.** No confirmatory log, stage output,
completion record or result was opened. The middle section is conditional by
construction:

- It states what a supported primary hypothesis **would** license.
- It does not say whether the primary is supported.
- If the primary is not supported, or the campaign is invalid, nothing in that
  section may be used.

Every claim below should be written with its citations. The "cite against"
column names the prior art a reviewer will expect to see.

## SAFE NOW

These are supported by the literature review and by the existing CSIA code and
documents.

| # | claim, in wording that is safe | cite against |
|---|---|---|
| S1 | CSIA v2 localizes a symptom by deterministic set elimination over declared hypotheses and three-valued predicates. A predicate that cannot be evaluated eliminates nothing | B28, B29, B70, B89 |
| S2 | CSIA names a cause only when it is the last candidate standing **and** some predicate affirmatively confirms it. Otherwise it reports AMBIGUOUS, UNSUPPORTED or NO_EVIDENCE. This combines consistency-based and abductive criteria | B31, B30, B137 |
| S3 | The experimental support certificate records, for each modelled competitor, the active discriminator that separated it, with applicability, freshness and provenance fields. It carries no probability of error and is weaker than integrity monitoring | B62, B87, B122 |
| S4 | CSIA issues no command. Function eligibility is reported, not enforced | B79, B81 |
| S5 | Controller compensation is used as root-cause evidence in fielded autopilots. The XSYS-001 allocator statistic belongs to the same family as ArduPilot's `thrust_balance` | B130 (V4) |
| S6 | Local motor-failure logic that compares an ESC signal with the motor command cannot, by itself, separate a failed motor from a telemetry defect. Field reports describe telemetry-triggered false detections | B131 (V4); B140, B146 |
| S7 | XSYS-001 is a **preregistered** test of whether two witnesses, each used only in its preregistered window, separate physical rotor-effectiveness loss from RPM-telemetry corruption that replays the same local symptom, without naming a wrong cause. The witnesses are a transient body-rate witness and a post-compensation allocator witness | EPOS (P03–P05), B117, B118, B37, B119 |
| S8 | The design includes an invalid-window negative control, frozen rules, two-stage label-blinded scoring, zero-WRONG in the primary decision and the nuisance condition as the unit | B122, B71, B147 |
| S9 | In the searched sources, no directly matching work was identified for this multirotor pairing and matched design. Closely related work exists on engines (EPOS), electro-hydraulic loops (B118), SISO closed loops (B117) and multirotor actuator/IMU faults (B123, B124) | search log §§S2.3–S2.4 |
| S10 | The underlying principles are established: closed-loop compensation masks physical faults in the plant state while exposing them in the control effort, and evidence valid in the transient must not be read after compensation. They are established by B37, B117, B118, B119, and in fielded code by B130 and B131 | as listed |

Required framing for S7–S9: **an application and evaluation of known
principles to a specific, practically relevant pair.** It is not a new
diagnostic principle.

## SAFE ONLY IF XSYS-001 SUPPORTS PRIMARY

Each claim is conditional on the preregistered primary decision rule being met:

- the cluster-conservative one-sided 95% lower bound on the pair resolution
  rate exceeds 0.5; **and**
- no A or B trial is WRONG at C3 under V3.

Each is also bounded by:

- **simulation only** (PX4 SIH);
- one airframe, one motor and one fault direction;
- an offline multiplicative telemetry replay;
- an internal comparison (V0–V4), with no external baseline.

| # | claim, in conditional form |
|---|---|
| C1 | If the primary is supported: in PX4 SIH simulation, the windowed pairing separated matched physical-versus-telemetry pairs with a lower bound above 0.5, and named no wrong cause in any symptomatic trial at the primary checkpoint |
| C2 | If the primary is supported: the RPM symptom alone (V0) resolved none of the pairs by construction, and the windowed cross-domain evidence (V3) resolved them at the reported rate. This is resolving power beyond the local symptom **in this simulated setting** |
| C3 | If, **in addition**, H3(b) is supported: reading the dynamics witness outside its window (V4) produced wrong attribution on case A at the reported rate. That would be an in-simulation demonstration of the known out-of-regime hazard (B131, B117) inside an elimination engine |
| C4 | If H3(a) and H3(c) are also supported: combining the two windowed witnesses lost nothing against either alone and produced no wrong attribution. Only this may be said; "the combination outperforms its parts" does not follow, because H3(a) is a no-loss test |
| C5 | The reported certification latency may be described as **set by the evidence windows** (0.2 s or 15 s), as frozen in the preregistration. It is not a computation-speed result |

Even if the primary is supported, the following remain **not safe**:

- anything about real ESCs, real rotors or real telemetry failure modes;
- other airframes, other motors, or multiple simultaneous faults;
- any comparison with MMAE, IMM, DBN, set-valued observers or ArduPilot/PX4
  logic, none of which was run;
- any statement that the result shows something new about diagnosis in
  general. The novelty status stays N2 (§17 of the verification).

## NOT SAFE

| # | claim | why |
|---|---|---|
| N1 | "CSIA is a novel architecture" / "the first cross-system assurance layer" | contradicted by prior art (B58–B60, B67/B68, P07); the full combination is N1 |
| N2 | "CSIA cross-validates the whole aircraft" | too broad; unsupported |
| N3 | "CSIA distinguishes sensor faults from actuator faults" (as a contribution) | contradicted: P01, B43, B44, B46, the EPOS family |
| N4 | "Using controller compensation as evidence is a new idea" | contradicted: B130 (V4) |
| N5 | "CSIA introduces temporal evidence validity" | contradicted in principle: B37, B119, B142, B130/B131 (V4). CSIA v2 is atemporal; the windows are in the XSYS-001 adapter |
| N6 | "CSIA's AMBIGUOUS/UNSUPPORTED verdicts are a new semantics" | contradicted: B28, B31, B137. UNSUPPORTED is also overloaded |
| N7 | "CSIA certifies its diagnoses" / "certified attribution" | misleading. The code says EXPERIMENTAL; it carries no error bound; it is weaker than B87 and B122 |
| N8 | "CSIA bounds runtime authority" / anything about FORGE | unsupported: not implemented; dependent on future work; concept known (B87, B79–B81, P24) |
| N9 | "CSIA performs temporal + structural diagnosis" | contradicted (B37, B39, B119); also false of v2 |
| N10 | "XSYS-001 shows CSIA works on real aircraft / real drones" | dependent on real-flight validation, which does not exist |
| N11 | "XSYS-001 shows CSIA outperforms established methods" | no external baseline was run |
| N12 | "No prior work addresses actuator-versus-telemetry discrimination" | contradicted (EPOS, P15, B117, B118). Say only "no directly matching work was identified in the searched sources" |
| N13 | "CSIA prevents wrong attribution" | zero-WRONG is an empirical criterion on a finite simulated set, not a guarantee (compare B122, B72) |
| N14 | any claim that rests on the full-text content of a V0 source | the sources were not read (`CSIA_FULLTEXT_VERIFICATION_QUEUE.md`) |
