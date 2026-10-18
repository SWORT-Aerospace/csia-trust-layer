# Owner authorization — cross-system research exception

**State: IN FORCE for documents and post-hoc analysis, and — since the owner's
second grant (§7) — for the PX4 research build, the minimal SIH
actuator-effectiveness patch and experimental apparatus validation. Since the
third grant (§8) it also covers designing, freezing and validating the
XSYS-001 preregistration, and since the fourth (§9) a pre-data amendment of
its nuisance design with nominal-only pilots. The fifth (§10) adds a second
pre-data amendment that corrects criterion C4 only. The confirmatory
experiment itself is NOT authorized.**

| | |
|---|---|
| granted | 2026-09-26, by the program owner, in Claude Code session `https://claude.ai/code/session_01Nn3eZyZZd4Tg4tzr5BpZvJ` |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| base commit | `e7594e4f72e71a812ee2e7b959533a3d1e5456c9` (clean tree) |
| governs | research into temporal evidence and physical cross-domain witnesses on top of CSIA v2 Phase C |
| does not govern | anything in the table of `docs/CURRENT_PROGRAM_STATE.md` §1, which still governs where the two disagree |

---

## 1. The authorization, verbatim

Recorded exactly as given. It is reproduced without paraphrase because it is
the only thing that makes this work permissible, and a paraphrased
authorization is not an authorization.

> Do NOT modify frozen CSIA v1 behavior, frozen CSIA v2 Phase C behavior,
> sealed/preregistered artifacts, thresholds, certificate semantics, or
> historical experimental outputs.
>
> [...]
>
> I authorize a narrow owner exception for RESEARCH-ONLY work outside the
> frozen CSIA v1/v2 implementation.
>
> Permitted:
>
> - post-hoc latency analysis
> - experimental instrumentation outside runtime decision semantics
> - research-only experiment scaffolding
> - deterministic twin-run analysis
> - SITL experiment design
> - adapters that consume frozen CSIA outputs without modifying them
>
> Not permitted:
>
> - modification of frozen v1 behavior
> - modification of frozen v2 Phase C behavior
> - threshold tuning against sealed results
> - rewriting historical experiments
> - modifying sealed artifacts
> - production FORGE implementation
> - changing certificate semantics
>
> Record this exception explicitly in the appropriate research governance
> document before implementation.

The elided line joins the preamble, which applies to the whole instruction, to
the authorization paragraph; nothing between them widens or narrows scope.

---

## 2. The governing rule this does not repeal

`docs/CURRENT_PROGRAM_STATE.md` §1 still lists the estimator domain, the energy
domain and Forge production code among FORBIDDEN work, and states that it
governs where documents disagree. **That rule stands and has not been
rewritten.** This record adds a pointer row to §1a of that file and nothing
else. Anyone reading §1 still finds the prohibition; anyone reading this file
finds the exception and its limits.

The v2 freeze record (`engineering/v2/V2_PHASEC_FREEZE.md`, "NO FURTHER V2
IMPLEMENTATION UNTIL PAPER LOCK RELEASE") also stands. This exception permits
nothing inside the v2 implementation. It permits code that **reads** v2's
outputs from outside it.

---

## 3. The permission, restated as checkable rules

Each rule names what would show it was broken, so compliance is a test rather
than a promise.

| # | rule | a violation looks like | caught by |
|---|---|---|---|
| R1 | No file in the frozen v1 core changes | a diff in any path listed in `docs/v1/FROZEN_BASELINE.json` | the provenance gate's frozen-core digest; `tests/test_v1_frozen.py` **(skipped in a clone without the freeze tag — see §5)** |
| R2 | No v2 Phase C behaviour changes | a changed digest among the Phase C artifacts, or a new registered domain | `tests/test_phase_c_freeze.py`, `tests/test_program_state.py` |
| R3 | No threshold, constant or config default changes | a diff in `csia/runtime/failsafe.py`, `csia/diagnosis/bayes.py`, `csia/trust_engine/engine.py` or `csia/v1_1/sequential.py` | the same frozen-core digest for the frozen files; review for the rest |
| R4 | No sealed or preregistered artifact changes | a diff in any `*_LOCKED*`, `*FREEZE*`, preregistration or SHA manifest | the phase SHA manifests and the append-only guards |
| R5 | Certificate semantics unchanged | a diff in `csia_assurance/witness.py` or `csia/v2/attribution.py` | review; both are read-only to this work |
| R6 | New code consumes frozen outputs and never feeds back into a decision | new code imported by `csia/runtime/` or `csia/v2/` | review; the research code lives outside both packages |
| R7 | No FORGE production code | any `.py` under `forge/` | `tests/test_program_state.py::test_forge_contains_no_code` |
| R8 | No append to the failure ledger without the owner's decision | a change to `research/physical_validation/FAILURE_LEDGER.yaml`, which the Phase 3.2, 4 and 5 SHA-256 manifests pin | each phase's `test_the_manifest_matches_every_file_it_lists` |

**Where new code may live.** Post-hoc analysis extends the existing latency
owner `csia/metrics/latency.py` only by adding functions that read an emitted
state stream. That module has no import on the runtime path, so it cannot
change a decision. Experiment scaffolding goes in a new research-only
directory outside `csia/`, named in the experiment specification when it is
created. Nothing is created until the owner reviews that specification.

---

## 4. What this exception does NOT authorize

- **Running SITL.** Designing the experiment is permitted; flying it is not,
  until the owner reviews the design. Building PX4 or ArduPilot is a large
  dependency step and is also held.
- **Hardware of any kind.** `HARDWARE — NOT CURRENT GATE` is unchanged. This
  exception does not touch the E2M bench exception either.
- **Energy-domain or estimator-domain implementation in the frozen packages.**
  The simulator-only energy exception in
  `research/active_evidence/realized_current/OWNER_AUTHORIZATION.md` is
  separate and is not widened by this one.
- **Paper claims.** Nothing produced under this exception enters either paper
  without separate review.
- **Resuming the unrelated audit bug fixes** (the owner kept them separate).

---

## 5. A limit on enforcement, stated so nobody relies on a guard that is off

`tests/test_v1_frozen.py` compares against the tag `csia-v1.0-research-final`.
**The freeze tags were never pushed** (`docs/CURRENT_PROGRAM_STATE.md`
explains the 403), so in a clone without them that test **skips**. At
`e7594e4` it skipped, along with six v1.1 freeze tests. The SHA-256 half of the
protection still runs through the provenance gate's frozen-core check. Until
the tags are pushed, R1 in a fresh clone rests on the digest check alone.

---

## 6. Quarantine

Every result produced under this exception is **post-freeze, research-only
evidence**. It is not a validated result, not a paper claim, and not a
replication of any sealed campaign. Documents written under it label each
statement HISTORICAL/SEALED, CURRENT VALIDATED, EXPERIMENTAL, PROPOSED or
UNPROVEN, and do not mix them.

---

## 7. Second grant: experimental apparatus validation

Granted by the program owner in the same session, after reviewing
`docs/research/PX4_SET_B_DYNAMICS_PREFLIGHT.md`. The operative lines,
verbatim:

> I approve the PX4 research build and the minimal SIH actuator-
> effectiveness patch.
>
> I also approve revising W1 before preregistration.
>
> We are NOT yet authorizing the final CSIA experimental campaign.
>
> This phase is:
>
>     EXPERIMENTAL APPARATUS VALIDATION
>
> [...]
>
> Do not:
>
> - tune CSIA
> - change v1
> - change v2
> - modify frozen thresholds
> - generate final CSIA claims
> - preregister final thresholds
> - compare algorithms for superiority

What this adds to §4, and nothing more:

| now permitted | still not permitted |
|---|---|
| building PX4 at `547e2ca`, unmodified and with the SIH effectiveness patch | running any CSIA version on the trials |
| flying SIH trials to validate the apparatus | preregistering thresholds or running the final campaign |
| revising witness W1 in the experiment design | any change to CSIA v1, v2, thresholds or sealed artifacts |

The PX4 patch lives in the PX4 tree and in
`research/px4_actuator_effectiveness/patch/`; nothing under `csia/` changes.
The results are in `docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md`.

## 8. Third grant: preregistration of the first confirmatory experiment

Granted by the program owner in the same session, after reviewing
`docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md`. The operative lines,
verbatim:

> I accept the apparatus; draft the preregistration
>
> We are now moving from EXPLORATORY APPARATUS CHARACTERIZATION to a
> PREREGISTERED CSIA CROSS-SYSTEM ASSURANCE EXPERIMENT.
>
> [...]
>
> Design, freeze, hash, and validate the preregistration for the first
> confirmatory CSIA cross-system experiment.
>
> DO NOT RUN THE CONFIRMATORY EXPERIMENT IN THIS SESSION.
>
> DO NOT generate new confirmatory flight data.
>
> DO NOT tune thresholds against new data.
>
> DO NOT modify frozen CSIA v1 or v2 behavior.
>
> DO NOT alter historical/sealed experimental artifacts.
>
> DO NOT change the PX4 apparatus based on desired CSIA results.

What this adds, and nothing more:

| now permitted | still not permitted |
|---|---|
| designing XSYS-001 and freezing it by SHA-256 (`docs/research/XSYS_001_PREREGISTRATION.md`, `research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.json`) | flying any confirmatory trial, or generating confirmatory data of any kind |
| setting thresholds by a fixed rule from **apparatus** data only | tuning any threshold, window or rule against new data |
| a nominal-only nuisance pilot (8 flights, no fault) to choose the nuisance mechanism and the benign onset event | a pilot with a fault, or any flight at a confirmatory condition |
| running CSIA v2's `localize()`, unchanged and by import, on apparatus data, in a pipeline dry run labelled IN-SAMPLE, NOT CONFIRMATORY | any change to CSIA v1, v2, thresholds, certificate semantics or sealed artifacts |
| research-only code under `research/xsys_confirmatory_001/` | code under `csia/` |

Two records from this grant:

- **The failure ledger** (R8) is untouched.
- **The freeze manifest's SHA-256** is in
  `research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.sha256`.
  `tests/test_xsys_001_preregistration.py` fails if the manifest or any file
  it lists changes.

Running the confirmatory experiment needs a further grant.

## 9. Fourth grant: pre-data amendment of the nuisance design (XSYS-001-A1)

Granted by the program owner in the same session, after reviewing the
frozen XSYS-001 preregistration. The operative lines, verbatim:

> I accept the scientific structure of XSYS-001 and the frozen
> preregistration.
>
> DO NOT run the confirmatory campaign yet.
>
> There is one final design issue that must be resolved before any
> confirmatory data exist:
>
>     INDEPENDENCE OF THE NUISANCE CONDITIONS.
>
> [...]
>
> If existing data cannot answer the independence question, you are
> authorized to run the MINIMUM number of additional NOMINAL-ONLY flights.
>
> [...]
>
> This authorization does NOT include running XSYS-001.
>
> Do not execute a single confirmatory fault flight.

What this adds, and nothing more:

| now permitted | still not permitted |
|---|---|
| a pre-data amendment of the nuisance-generation mechanism only (`docs/research/XSYS_001_A1_NUISANCE_INDEPENDENCE.md`) | any change to hypotheses, levels, evidence definitions, thresholds, windows, endpoints, decision rules, attribution semantics, v2 or the PX4 apparatus |
| nominal-only pilots (η = 1.00, no fault, no corruption, no CSIA scoring), ids `A1P-…`: five were flown | any fault flight, case-B construction or confirmatory scoring |
| freezing the amendment by a manifest that binds the XSYS-001 manifest | changing the XSYS-001 preregistration, manifest or any file it froze |

**The outcome is recorded here too.** The amendment's own acceptance rule,
frozen before use, failed criterion C4. XSYS-001-A1 is therefore frozen but
**not accepted for execution**, and its executor refuses to fly. Any run
needs a further amendment and a further grant. The failure ledger (R8) is
untouched.

## 10. Fifth grant: second pre-data amendment, C4 only (XSYS-001-A2)

Granted by the program owner in the same session, after reviewing
XSYS-001-A1. The operative lines, verbatim:

> A1 correctly remains NOT ACCEPTED because C4 failed under its
> preregistered criterion.
>
> Do NOT retroactively change A1.
>
> Do NOT change its verdict.
>
> Do NOT alter its manifest.
>
> Do NOT run confirmatory flights.
>
> [...]
>
> We will therefore create a SECOND PRE-DATA AMENDMENT:
>
>     XSYS-001-A2
>
> This amendment is limited to correcting the definition of C4.
>
> [...]
>
> DO NOT loosen C1.

The instruction's title reads "I approve the corrected C4 and C1". Its body
forbids changing C1, so C1 stays unchanged (§1 of
`docs/research/XSYS_001_A2_C4_CORRECTION.md`).

| now permitted | still not permitted |
|---|---|
| defining C4-A2 prospectively and freezing it before fresh data | changing A1, its verdict, its manifest, or any XSYS-001 file |
| fresh nominal-only validation pilots (η = 1.00, no fault, no corruption, no CSIA scoring), ids `A2P-…` | any confirmatory flight, case-B construction, confirmatory stage 1 or 2, or inspection of confirmatory outcomes |
| a manifest binding XSYS-001, A1 and A2 | changing C1, C2, C3 or C5, or any other frozen element |

If C4-A2 fails, the program stops and reports. No A3 is created
automatically.

**Outcome** (`docs/research/XSYS_001_A2_RESULTS.md`). Ten fresh nominal-only
pilots were flown under the specification committed at `4f3378f`. Every gate
passed: C1, C2, C3 and C5 as carried from A1, fresh C1, fresh C5, C4-A2 and
EV-A2. No confirmatory flight was flown. Running the confirmatory campaign
still needs a further grant.
