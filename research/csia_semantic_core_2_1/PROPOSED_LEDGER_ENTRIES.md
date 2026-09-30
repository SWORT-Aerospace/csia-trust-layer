# Proposed failure-ledger entries FL-054 to FL-060 (Phase K)

**Status: RECORDED HERE, NOT IN THE FAILURE LEDGER. 2026-09-30.** The seven
entries in §4 are complete and parse-checked, ready to append to
`research/physical_validation/FAILURE_LEDGER.yaml`. Appending them is the
owner's decision (§2).

## 1. Phase K's answer

The brief asked whether the confirmed v2 semantic defects should receive new
failure-ledger entries **according to repository governance**. The answer has
two parts:

- **They warrant entries.** Each is a defect in code this program built,
  found by its own audit. That is the ledger's `OUR_OWN_ERROR` kind, and
  FL-001 is the precedent.
- **Appending them is not permitted without a further owner decision:**
  - The ledger is pinned by three sealed-phase SHA-256 manifests:
    `research/consequence/phase32/SHA256_MANIFEST32.json`,
    `research/phase4/SHA256_MANIFEST4.json` and
    `research/phase5/SHA256_MANIFEST5.json`.
  - Any append changes its hash, and each phase's
    `test_the_manifest_matches_every_file_it_lists` then fails.
  - Rule **R8** of `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`: "No
    append to the failure ledger without the owner's decision".
  - This brief also requires that historical manifests remain valid
    (promotion criterion 15).

So the entries are held here, exactly as commit `b75ad0c` held the Mechanism B
entry (`docs/research/MECHANISM_B_DWELL_DISCREPANCY.md`, proposed FL-053).

**What happened, stated plainly.** In this phase the seven entries were first
appended to the ledger. The runbook count was raised with them, which is
precisely what `b75ad0c` and rule R8 exist to prevent. The suite caught it
before any commit: `tests/test_consequence_phase32.py::test_the_manifest_matches_every_file_it_lists`
failed on the ledger's hash. The ledger was then restored byte for byte from
git, SHA-256 `6c7e6cf3b8bde3cbac050a67b0bc9cb6fef5aeba587eabca142c823879f5b58f`,
which matches all three manifests again. The runbook count went back to 124.
**No manifest was edited, and nothing wrong was ever committed.**

## 2. To promote them into the ledger (owner decision)

1. **Decide the order with the pending Mechanism B entry.** These are
   numbered on the assumption that proposed FL-053 is promoted first. If it
   is not, renumber these FL-053 to FL-059.
2. Append the block in §4 to the ledger.
3. In each of the three manifests, rewrite the ledger's hash and
   `head_at_build`, and nothing else, as commits `b7f1816`, `d69919d`,
   `c2aac29` and `39dc509` did.
4. Raise "ledger has 124 entries" in `docs/FIELD_INTEGRATION_RUNBOOK.md` by
   the number of entries appended (`tests/test_runbook_numbers.py` couples
   the two).
5. Run the three manifest tests and the runbook test.

**Do not mark any of them resolved.** The defects stay in 2.0.0, which is
frozen and the default. 2.1.0 corrects them only in a successor that is ready
for shadow mode, not deployed.

## 3. What they record

| proposed id | finding | successor correction |
|---|---|---|
| FL-054 | SC-01: an irrelevant NOMINAL record licenses UNIQUE | C1 |
| FL-055 | SC-02: UNIQUE contradicts the same tick's localization; two wrong-cause UNIQUE verdicts | F2 |
| FL-056 | SC-03, SC-04: "could not look" read as "fine" | C2 |
| FL-057 | SC-05: subject-free predicates and detector | C3 |
| FL-058 | SC-06, SC-07: silent predicate exceptions and non-bool returns | C4 |
| FL-059 | SC-12, SC-13: order and duplicate dependence | C6 |
| FL-060 | the semantic audit's misstatement of where the 7 changed UNIQUE verdicts are recorded | not applicable (a documentation error) |

Each entry records:
- the defect;
- the affected version (2.0.0, the Phase C freeze `50c5d35`);
- the discovery audit;
- the successor correction;
- the historical impact;
- the XSYS impact.

That is every field the brief asked for.

## 4. The entries, verbatim, ready to append

```yaml
  - id: FL-054
    date: 2026-09-30
    phase: CSIA Semantic Core 2.1 (owner-approved successor to the v2 semantics)
    kind: OUR_OWN_ERROR
    what_happened: >-
      SC-01. Frozen v2 attribution licensed UNIQUE on ANY affirmatively
      NOMINAL record from a domain other than the candidate's, whether or not
      that record was about anything that could have explained the fault. One
      VIOLATED rail gave AMBIGUOUS; adding one unrelated NOMINAL CPU record
      gave UNIQUE (reproduction R1). In every shipped scenario a single
      adverse component was UNIQUE on 889 of 889 ticks.
    affected_version: >-
      CSIA v2 reasoning semantics 2.0.0: csia/v2/attribution.py at the Phase C
      freeze 50c5d35, byte-identical since.
    found_by: >-
      The CSIA semantic correctness audit, research/csia_semantic_correctness/
      (commit d87834c), finding SC-01, S3.
    successor_correction: >-
      C1 in csia_semantic_core 2.1.0. UNIQUE also requires every DECLARED
      alternative (dependency ancestors and relation implicates) to be
      affirmatively NOMINAL, with a relevant discriminator from another
      domain. It can only turn UNIQUE into AMBIGUOUS, with a named reason.
    historical_impact: >-
      None on shipped results: C1 alone changes 0 of 2,640 shipped ticks. In
      the audit's attribution enumeration UNIQUE falls from 21 of 125
      configurations to 4.
    xsys_impact: none. XSYS-001 never called attribute().
    verdict: RECORDED
    consequence: >-
      Not resolved. The defect stays in 2.0.0, which is frozen and remains the
      default. 2.1.0 corrects it in a successor that passed its validation
      and is recommended for shadow mode only
      (research/csia_semantic_core_2_1/PROMOTION_DECISION.md). No historical
      record was edited.
    artifact: >-
      csia_semantic_core/attribution.py; tests/test_semantic_core_2_1.py;
      research/csia_semantic_core_2_1/SEMANTIC_CORE_2_1.md

  - id: FL-055
    date: 2026-09-30
    phase: CSIA Semantic Core 2.1 (owner-approved successor to the v2 semantics)
    kind: OUR_OWN_ERROR
    what_happened: >-
      SC-02. Frozen v2 attribution could say UNIQUE for a component while the
      same tick's localization on that component still kept a hypothesis
      from another domain. It did so on 281 of 889 shipped UNIQUE ticks,
      including MS_B5_RESPONSE_SENSOR and MS_TS_B5_RESPONSE_SENSOR. In those
      two scenarios the injected cause is the response sensor, yet
      attribution named the actuator UNIQUE.
    affected_version: >-
      CSIA v2 reasoning semantics 2.0.0 (csia/v2/attribution.py and
      csia/v2/engine.py, Phase C freeze 50c5d35).
    found_by: >-
      The CSIA semantic correctness audit, finding SC-02, S3 (property P9).
    successor_correction: >-
      F2 in csia_semantic_core 2.1.0: UNIQUE is withheld while a same-tick
      localization on the candidate's component retains another domain's
      hypothesis. The two stages stay separate.
    historical_impact: >-
      2.1 replay differs from the recorded run; nothing recorded is edited.
      - 60-tick corpus: 281 attribution ticks change under F2 alone, and 362
        together with C3.
      - Recorded 200-tick V2_SCENARIO_RESULTS.json: 4 of its 10 UNIQUE final
        verdicts become AMBIGUOUS (ACTUATOR_NO_RESPONSE, CLOCK_DRIFT,
        STALLED_ACTUATOR, PROCESS_STALL), and 23 TS_STALLED ticks change.
      - The Phase C gate headline and its qualifying answers are unchanged.
    xsys_impact: none. 3,872 sealed slots, 0 decision and 0 outcome differences.
    verdict: RECORDED
    consequence: >-
      Not resolved. 2.0.0 is frozen and remains the default. The successor
      withholds both wrong-cause UNIQUE verdicts. It also withholds seven
      that named the right component without the evidence to call it unique
      (research/csia_semantic_core_2_1/PHASE_C_GOVERNANCE_REPORT.md).
    artifact: >-
      csia_semantic_core/attribution.py;
      research/csia_semantic_core_2_1/PHASE_E_CHANGE_RECEIPTS.jsonl

  - id: FL-056
    date: 2026-09-30
    phase: CSIA Semantic Core 2.1 (owner-approved successor to the v2 semantics)
    kind: OUR_OWN_ERROR
    what_happened: >-
      SC-03 and SC-04. 18 of the 26 shipped v2 predicates read "could not
      look" as "fine": an aggregate over rows ignored UNAVAILABLE ones, and a
      declared shared node that nobody reported counted as "not adverse".
      Consequences:
      - missing estimator telemetry during a true stall gave SUPPORTED
        processing_delay;
      - two sources sharing four unreported nodes gave SUPPORTED
        independent_faults.
    affected_version: >-
      CSIA v2 reasoning semantics 2.0.0 (csia/v2/signatures.py, Phase C freeze
      50c5d35).
    found_by: >-
      The CSIA semantic correctness audit, findings SC-03 and SC-04, both S3
      (properties P6 and P12).
    successor_correction: >-
      C2 in csia_semantic_core 2.1.0: strong-Kleene aggregation in exactly
      those 18 predicates. Unknown never decides a hypothesis and missing
      evidence never becomes affirmative nominal.
    historical_impact: >-
      None on shipped results: 0 of 2,640 ticks change, since no shipped
      scenario drops telemetry. Unknown-based rejections in the enumerations
      fall to 0 (1,208, 486 and 224 in N3, N4 and N6), P6 falls from 382 to 0
      and P12 from 15 to 0.
    xsys_impact: none. XSYS-001 used its own predicates, which already read UNAVAILABLE as unknown.
    verdict: RECORDED
    consequence: >-
      Not resolved in 2.0.0, which is frozen and the default. Corrected in
      the 2.1.0 successor, which is recommended for shadow mode only.
    artifact: csia_semantic_core/predicates.py; tests/test_semantic_core_2_1.py

  - id: FL-057
    date: 2026-09-30
    phase: CSIA Semantic Core 2.1 (owner-approved successor to the v2 semantics)
    kind: OUR_OWN_ERROR
    what_happened: >-
      SC-05. Five function-level predicates and the POSITION_UNAVAILABLE
      detector ignored their subject and read the whole tick. A late logger
      process produced "estimator stale" SUPPORTED on navigation functions
      that the function graph called ELIGIBLE.
    affected_version: >-
      CSIA v2 reasoning semantics 2.0.0 (csia/v2/signatures.py, Phase C freeze
      50c5d35).
    found_by: >-
      The CSIA semantic correctness audit, finding SC-05, S3 (properties P1,
      P2 and P16).
    successor_correction: >-
      C3 in csia_semantic_core 2.1.0: those predicates and the detector read
      only components DECLARED to serve their subject. Where nothing is
      declared the predicate is None and the profile gap is surfaced. The
      function graph and the profiles are unchanged.
    historical_impact: >-
      664 of 2,640 localization ticks change. Of the changed units:
      - 670 are navigation symptoms no longer raised on a function the frozen
        function graph calls ELIGIBLE. 189 of those were raised only by
        unrelated components (the ESC CAN link, the telemetry downlink): a
        real fix. The other 481 were raised by navigation-chain components
        that are never declared to serve COARSE_NAVIGATION (gap G-1), so the
        missing declaration decides them.
      - 243 are weakened because a profile declares nothing serving the
        subject (gaps G-1 and G-2, SC-18).
      In the recorded LOCALIZATION_RESULTS.csv, 4 D-set rows on
      COARSE_NAVIGATION change. The D set stays non-qualifying, and the gate
      headline is unchanged.
    xsys_impact: none. The XSYS-001 predicates are not in the C3 set.
    verdict: RECORDED
    consequence: >-
      Not resolved in 2.0.0. Profile gaps G-1, G-2 and G-3 are exposed rather
      than fixed; profile data is an owner decision and the profiles are
      frozen with v2.
    artifact: csia_semantic_core/predicates.py; csia_semantic_core/profile_check.py

  - id: FL-058
    date: 2026-09-30
    phase: CSIA Semantic Core 2.1 (owner-approved successor to the v2 semantics)
    kind: OUR_OWN_ERROR
    what_happened: >-
      SC-06 and SC-07. A v2 predicate that raised, or that returned something
      other than True, False or None, was silently "not measurable". The
      fault was indistinguishable from missing evidence. Injected faults
      changed decisions for 19 of 26 predicates, created 9 SUPPORTED
      verdicts, and were visible in 0 outputs.
    affected_version: >-
      CSIA v2 reasoning semantics 2.0.0 (csia/v2/localization.py
      Predicate.__call__, Phase C freeze 50c5d35).
    found_by: >-
      The CSIA semantic correctness audit, findings SC-06 and SC-07, S2
      (property P5).
    successor_correction: >-
      C4 in csia_semantic_core 2.1.0. A fault still eliminates nothing, as in
      2.0.0. It is also recorded: predicate, evaluated id, subject, error
      class and the hypotheses it touched. The localization's evaluation
      status becomes PREDICATE_FAULT. A missing predicate id is a
      configuration error raised before any tick.
    historical_impact: >-
      None: 0 of 2,640 shipped ticks change, and no shipped predicate raises.
      Every injected fault is now reported (259 of 259 evaluations). Governance
      option G5, withholding SUPPORTED over a faulted refuter, is NOT
      implemented. The verdict R9B creates therefore still stands, now marked
      PREDICATE_FAULT.
    xsys_impact: none. The catch-all never fired in XSYS-001.
    verdict: RECORDED
    consequence: >-
      Not resolved in 2.0.0. In 2.1.0 the fault is observable; the verdict
      rule is unchanged by design. G5 and intake validation (SC-08) remain
      deferred.
    artifact: csia_semantic_core/predicates.py; csia_semantic_core/localization.py

  - id: FL-059
    date: 2026-09-30
    phase: CSIA Semantic Core 2.1 (owner-approved successor to the v2 semantics)
    kind: OUR_OWN_ERROR
    what_happened: >-
      SC-12 and SC-13. In frozen v2, when two records disagreed about one
      (relation, component), container order decided between SUPPORTED and
      UNSUPPORTED (R6). An exact duplicate of one adverse source record
      created a MULTIPLE_SENSORS_DEGRADED symptom from a single source (R7).
    affected_version: >-
      CSIA v2 reasoning semantics 2.0.0 (csia/v2/localization.py
      EvidenceIndex.one, Phase C freeze 50c5d35).
    found_by: >-
      The CSIA semantic correctness audit, findings SC-12 and SC-13, S2
      (properties P3 and P4).
    successor_correction: >-
      C6 in csia_semantic_core 2.1.0:
      - exact duplicates count once;
      - two different records for one key answer neither, and the conflict
        is listed in the trace;
      - nothing is resolved by order, count or weight.
    historical_impact: >-
      None on shipped results: 0 of 2,640 ticks change. P4 decision changes
      fall from 3 to 0, and both R6 orders give the same answer.
    xsys_impact: none. There were no duplicates or conflicts in the 3,872 sealed slots.
    verdict: RECORDED
    consequence: >-
      Not resolved in 2.0.0, which is frozen and the default. Corrected in
      the 2.1.0 successor, which is recommended for shadow mode only.
    artifact: csia_semantic_core/index.py; tests/test_semantic_core_2_1.py

  - id: FL-060
    date: 2026-09-30
    phase: CSIA Semantic Core 2.1, Phase G (Phase C governance report)
    kind: OUR_OWN_ERROR
    what_happened: >-
      The semantic correctness audit (IMPLEMENTATION_GATE.md section 3 and
      row G3) said F2 turns "7 recorded UNIQUE final verdicts" into
      AMBIGUOUS. It said they are in V2_SCENARIO_RESULTS.json and the
      review-report tables and include the two wrong-cause cases. That is not
      what the records hold.
      - The 7 are the final ticks of the audit's own 60-tick replay of all 44
        scenarios.
      - The recorded V2_SCENARIO_RESULTS.json is a 200-tick run of 19
        non-matched scenarios, repeated in the review report. Of its 10
        UNIQUE finals, 4 change under 2.1: three by F2 and PROCESS_STALL by
        C3 and F2.
      - The two wrong-cause scenarios, MS_B5 and MS_TS_B5, are matched
        scenarios whose attribution no Phase C artifact records at all.
    affected_version: research/csia_semantic_correctness/IMPLEMENTATION_GATE.md (commit d87834c)
    found_by: >-
      Replaying each recorded Phase C artifact at its own tick count, instead
      of reading the 60-tick corpus as if it were the record
      (research/csia_semantic_core_2_1/semantic_core_2_1_differential.py,
      section G).
    successor_correction: not applicable (a documentation error)
    historical_impact: >-
      The governance decision is not affected in kind: every recorded change
      is UNIQUE to AMBIGUOUS by an approved rule, and no gate headline moves.
      The audit file is a previous semantic audit result and is not edited.
    xsys_impact: none
    verdict: RECORDED
    consequence: >-
      The precise per-artifact figures are in
      research/csia_semantic_core_2_1/PHASE_C_GOVERNANCE_REPORT.md, and that
      document governs where the two disagree. The lesson this ledger keeps
      recording: a count in prose is a claim, and it has to be measured
      against the artifact it names.
    artifact: research/csia_semantic_core_2_1/PHASE_C_GOVERNANCE_REPORT.md
```
