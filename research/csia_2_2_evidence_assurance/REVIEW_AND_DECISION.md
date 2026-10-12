# CSIA 2.2: review and decision

**2026-10-01. NON-CONFIRMATORY.**

## 1. Decision

**`CSIA_2_2_READY_FOR_OFFBOARD_PILOT`**

The evidence-assurance layer and the Flight Assurance Analyzer are ready to
be used offboard, on real SITL, HIL and flight-test logs, as a pilot.

**On every historical input it either leaves 2.1.1's decision unchanged or
changes it only by refusing evidence its own contract says is invalid.**
Every such change has a receipt.

**Not claimed:**
- that the layer has been validated on a real fault seen by several real
  producers (`DATASETS.md`, "what they do not show");
- any onboard use.

**The token is this package's own.** The brief as received ends at Phase 29,
the difference receipts, with no deliverables list or decision tokens; it
may have been truncated. This package follows the conventions of the
previous briefs, and the token names what the evidence supports.

**Alternatives considered:**

| token | why not |
|---|---|
| `..._NOT_READY` | no test, replay or dataset failed; every rejection is explained |
| `..._SEMANTIC_CORE_DEFECT_FOUND` | no 2.1.1 behaviour needed changing (§4) |
| `..._READY_FOR_FLIGHT_USE` | the Analyzer is offboard by design and has no flight-control authority |

## 2. Baseline and governance

| check | result | evidence |
|---|---|---|
| baseline verified before any 2.2 code | yes | `BASELINE_2_2.json`: revisions active, r2 digest, PV1-PV9, 273/197/0/0/0, 68,640 injections (168 → 0), E1 (9 → 0), XSYS 3,872/3,872 and 55/55 with LB 0.7616, Phase C, revision tests |
| baseline re-verified at the end | yes, all checks | `FINAL_STATE_2_2.json` |
| frozen v2.0, Phase C artifacts, XSYS-001 / A1 / A2, sealed manifests, earlier audits, shadow and revision packages, result hashes | not modified | `test_no_frozen_artifact_changed_since_the_2_1_1_baseline` (git diff against 2b2adcc is empty for every one of those paths); manifests verified by the final-state check |
| Semantic Core 2.1.1 | not modified: `csia_semantic_core/` is identical to 2b2adcc; 2.2 only imports it | same test |
| failure ledger | unchanged (SHA pinned); nothing appended | same test |
| `csia/` imports 2.2 | never | `test_nothing_in_csia_imports_2_2_and_2_2_never_attributes_unsupported` |

## 3. The three operating conditions, enforced

| condition | how 2.2 enforces it |
|---|---|
| 1. pacing declarations grounded in the implementation | PG1 (`profile_gate.py`): a pacing declaration without a citation (repository, commit, path, lines, statement), or with a mismatched one, is an ERROR and the profile is REFUSED. r2's citation: PX4 547e2ca `EKF2.cpp` lines 625-767, V4 |
| 2. valid configuration-epoch context | a contract declares each claim's epoch dependency. An output without its stamp is CONTRACT_INVALID (MISSING_EPOCH). A stale stamp is decided by R-3 itself (CONFIGURATION_MISMATCH). The PX4 adapter supplies the context from the log, and refuses estimator evidence when the selector should run but is not logged |
| 3. successor profiles pass the static validator | PV1-PV9 as the load gate. An ERROR refuses the profile, and the Analyzer then reasons with nothing (PROFILE_REFUSED). A specification with no function table is NOT_APPLICABLE and says so on every result |

## 4. Semantic-core defects

**None found.** Nothing in 2.2 required a change to 2.1.1, so the brief's
stop rule was not triggered.

**Two behaviours were examined and are not defects:**
- **Under the XSYS-001 specification, attribution is NO_EVIDENCE while a
  localization is SUPPORTED.** The witnesses' records are non-attributable by
  the frozen adapter's design, and attribution needs attributable records.
  The result shows both, in the headline.
- **Dataset F: a predicate fault widens a SUPPORTED to AMBIGUOUS.** This is
  R-1 as approved: the surviving hypothesis may rest on the failed refuter,
  and the fault impact is reported.

## 5. What the build found, and changed in 2.2 itself

| finding | change |
|---|---|
| reading a record's own processing time as the producer's metadata marked five scenarios' TIMING producers FAULTED (372 decision differences) | envelope times describe the output; record times stay evidence (`CONTENT_TIME.md`) |
| connected components under-count independent lines (W_DYN and W_RPM share nothing but are joined through W_CTRL) | independent lines = the largest pairwise-disjoint set, the shadow preview's `max_disjoint`; groups kept for display |
| an epoch dependency declared per relation refused 240 valid outputs in E1 (other processes' deadline records) | per-component claims in the legacy adapter; `other_rejections == 0` pinned |
| the estimator's reset, aiding and IMU counters arrive with the claims, so as dependencies they protect nothing | only the lane counter is a dependency; the others are context |
| the human report's short ids dropped the producer, so three monitors' outputs read alike | the producer is shown |

## 6. Results in one table

| question | answer | where |
|---|---|---|
| does 2.2 change 2.1.1 on the v2 corpus? | no: 2,640 ticks, 0 rejections, 0 changes | `REPLAY_AND_RECEIPTS.md` |
| on XSYS-001? | only V4_INVALID_WINDOW at C3: 110 slots, all receipted and expected; primary result unchanged (55/55, LB 0.7616, 0 wrong) | same |
| on E1? | no: per-tick identical to REVISED_2_1_1_R2, 0 stale ticks, 9 CONFIGURATION_MISMATCH, nothing valid refused | `ADMISSIBILITY.md` |
| can rejected evidence affect 2.1.1? | no: 12 metamorphic cases, inverted and same-state twins | `ADMISSIBILITY.md` §5 |
| are dependent monitors kept apart? | yes: three IMU1 monitors are 1 line; three CUSUM alarms in power_sag are 1 line | `LINEAGE_AND_DEPENDENCE.md`, `DATASETS.md` |
| does a monitor that cannot see a fault say so? | yes: CUSUM on imu0 gives a coverage notice, never a NOMINAL | `ADAPTERS.md` §1 |
| one interface for statistical, estimator and physical producers? | yes: CUSUM, PX4 EKF2 and the XSYS witnesses through one Analyzer; estimator and witnesses on one time axis in dataset H | `ADAPTERS.md` |
| are reports deterministic? | yes: byte-identical across runs | `ASSURANCE_RESULT_AND_REPORTS.md` |

**Offboard cost** (desktop CPython, measured here; 720 ticks of four
aircraft scenarios, 68 records per tick):

| path | median | p99 |
|---|---|---|
| Analyzer step (admissibility, 2.1.1 with trace, result) | 2.4 ms | 4.8 ms |
| 2.1.1 alone, on the same records | 0.7 ms | 1.7 ms |

A 172 s flight at 10 Hz analyses in a few seconds. Nothing here is an
onboard figure.

## 7. Limitations

1. **Real faults seen by several real producers are untested.** XSYS-001's
   degradation was invisible to EKF2's innovation tests in the one flight
   analysed with the estimator. Dataset G's correlated monitors are
   synthetic.
2. **One flight log was analysed end to end with the estimator** (E055, and
   NB for the B trial). The other 64 were read only for the gyro device id.
3. **The estimator claims are non-attributable.** They can block
   "affirmatively nominal" and appear as adverse evidence, but no profile
   hypothesis yet reads them.
4. **The v2 domain plugins are wrapped as IN_PROCESS producers.** Their
   health is the frozen plugin runtime's; there is no separate fault signal
   for them.
5. **Lineage names are declared by the adapters.** A producer that declares
   its lineage wrongly will be treated as independent. Lineage is checked
   against the contract (PER_OUTPUT or fixed), not against the world.
6. **Lane switches are pinned on a synthetic log.** No flight in the
   repository ran the EKF2 selector (`SENS_IMU_MODE` = 1 in all of them).

## 8. Recommended next steps

1. **Run the Analyzer on new SITL logs with `SENS_IMU_MODE` = 0 and an
   injected IMU fault.** This exercises a real lane switch end to end.
2. **Add a profile hypothesis that reads the estimator's innovation claims,**
   through the normal successor-profile route: an overlay, the PV1-PV9 gate,
   and citations where pacing is involved.
3. **Inject a fault visible to both a statistical and an estimator producer
   in SITL,** and use it to check that the lineage report stays conservative
   on real data.
