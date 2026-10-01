# Admissibility, configuration epochs and the profile gate (Phases 9-12 and 22)

**2026-10-01. Code:** `csia_evidence_assurance/admissibility.py`,
`profile_gate.py`, `pacing_citations.json`.

## 1. Statuses (Phase 9)

**Every output gets exactly one status.** Only states with an operational
meaning were kept.

| status | the engineer should | what 2.1.1 receives |
|---|---|---|
| ADMISSIBLE | nothing | the record, with its epoch stamped where R-3 reads it |
| CONTRACT_INVALID | fix the producer, its version or its contract | withheld |
| PROFILE_MISMATCH | use a profile the producer was declared for | withheld |
| PRODUCER_INVALID | look at the producer: it is faulted, unavailable, or not reporting | withheld |
| STALE | look at the producer's rate or the link: its content is too old | withheld |
| REGIME_INVALID | use the output only inside the window it was validated for | withheld |
| CONFIGURATION_MISMATCH | nothing: the configuration changed and the evidence is from the old one | the stamped record; **2.1.1's own R-3** withholds it |
| DUPLICATE | find the relay: the same output arrived under two identities | dropped; the first copy stands |

**Considered and not kept:**

| candidate | why not |
|---|---|
| UNKNOWN status | every failing check names its status; a catch-all would hide which one |
| DEPENDENCY_CONFLICT | dependent evidence is not inadmissible: 2.1.1 uses it logically and never counts it (`LINEAGE_AND_DEPENDENCE.md` §4). The one dependency that must not reach the core twice, a republished duplicate, is DUPLICATE |

**Order.** The first failing check decides the status. Every failing check
is listed in the reasons.

**Withheld means what R-3 means:**
- if an admitted output answers the same (relation, component), the
  withheld one is dropped;
- otherwise it becomes UNAVAILABLE ("could not look"), with its identity and
  declared structure kept and its content cleared.

## 2. Configuration epochs reuse R-3 (Phase 10)

**There is no second staleness system for configuration.**
- 2.2 stamps each record with its envelope's `config_epoch`
  (`provenance["config_epoch"]`).
- It hands the candidates and the integration's `EpochContext` to
  `csia_semantic_core.admission.admit`, 2.1.1's own R-3.
- Whatever R-3 does not admit is reported CONFIGURATION_MISMATCH, with R-3's
  reason, key and epochs.
- The core then applies R-3 itself, unchanged.

**E1, pinned permanently** (`test_e1_through_2_2_is_a_permanent_regression`):

| measure | value |
|---|---|
| stale position-symptom ticks | 0 (2.1.0: 9) |
| per-tick verdicts | equal to the revision's REVISED_2_1_1_R2 |
| CONFIGURATION_MISMATCH | on 9 ticks |
| other rejections | 0 |

**A finding on the way.** The first 2.2 contract for E1 declared the epoch
dependency per relation. That refused the deadline and stability records of
the `csia` and `logger` processes (240 outputs, MISSING_EPOCH): they share
those relation names but depend on no estimator lane. Decisions were
unchanged, but valid evidence was being refused. The legacy adapter now
declares a dependency per component (`relation@component`).

## 3. Content-time validity

| contract rule | status when violated | producers |
|---|---|---|
| `max_content_age_s` | STALE | PX4 estimator (0.4 s); dataset G (0.5 s) |
| `event_window_s` relative to a named event | REGIME_INVALID; also when the event is unknown | XSYS-001 witnesses |
| none | — | v2 domain plugins (a TIMING record's age is its claim) and the CUSUM (a SNAPSHOT, valid for its tick only) |

## 4. The profile gate: PV1-PV9 plus PG1 (Phases 11 and 12)

**Run once when a profile is loaded, never per tick.**

| check | severity | effect |
|---|---|---|
| validator ERROR (PV1-PV9, unchanged) | ERROR | profile REFUSED; the Analyzer reports PROFILE_REFUSED and reasons with nothing |
| validator WARNING | WARNING | kept on every result |
| validator GAP | INFO | kept: 2.1.1 will report scope gaps there |
| PG1: a pacing declaration with no citation, a citation naming other inputs, mode or version, or an incomplete reference | ERROR | REFUSED |
| a specification with no function table (XSYS-001's) | INFO (PG0_NOT_VALIDATED), status NOT_APPLICABLE | reasoned with, and every result says it was not validated |

**r2 is ACCEPTED:**
- 3 PV2 warnings;
- 1 PV3 warning;
- its pacing citation present.

**PG1 citations** (`pacing_citations.json`, keyed by the profile digest, so
the r2 file and its digest are unchanged):

| field | value |
|---|---|
| subject | `state_estimator` |
| inputs | `SENSOR/source.imu0` |
| mode | ALL |
| reference | PX4/PX4-Autopilot 547e2ca, `src/modules/ekf2/EKF2.cpp` lines 625-767 |
| verification | V4 |

The runtime does not parse the reference. It is there for engineering audit.

## 5. Admissibility comes before reasoning (Phase 22)

**2.1.1 receives only:**
- the admitted records;
- the stamped candidates R-3 itself will judge;
- the withheld records as UNAVAILABLE, or nothing.

Rejected evidence stays in the result with its reason, and never takes part
with its content.

**Pinned** (`test_rejected_evidence_cannot_affect_2_1_1`, 3 scenarios × 4
rejection kinds):
- **Twin check.** Every admitted record gets an inverted twin from a
  producer that is STALE, FAULTED, CONTRACT_INVALID or PROFILE_MISMATCH. The
  decision equals the decision without the twins, and the used evidence is
  identical.
- **Content check.** With the originals removed, inverted twins and
  same-state twins give the same decision. Rejected content cannot speak
  even when it is the only answer.
