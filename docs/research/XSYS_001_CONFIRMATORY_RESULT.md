# XSYS-001 confirmatory result

**Verdict: XSYS_001_PRIMARY_SUPPORTED.**

This is the frozen result of the XSYS-001 confirmatory campaign, run under
the manifest chain XSYS-001 → A1 → A2. Every number below is copied from the
sealed artifacts in `research/xsys_001_confirmatory_campaign/`. The frozen
result manifest, `research/xsys_001_confirmatory_campaign/CONFIRMATORY_RESULT_MANIFEST.json`,
hashes them all; its own SHA-256 is in `CONFIRMATORY_RESULT_MANIFEST.sha256`
beside it.

Nothing in CSIA, the thresholds, the windows, the evidence definitions, the
exclusions, the hypotheses, the endpoint, the statistics or the zero-WRONG
rule was changed. Nothing was tuned or re-run after the result was seen.

## A. Executive result

| quantity | value |
|---|---|
| flights attempted / expected | 66 / 66 |
| valid flights / excluded flights | 66 / 0 |
| valid matched pairs | 55 (of 55) |
| resolved matched pairs (both A and B UNIQUE_CORRECT at C3 under V3) | 55 |
| primary resolving rate | 1.0 |
| one-sided 95% lower bound (cluster-conservative, 11 nuisance conditions) | 0.7615958096191473 |
| WRONG (A and B trials, C3/V3) | 0 |
| AMBIGUOUS (C3/V3) | 0 |
| UNSUPPORTED (C3/V3) | 0 |
| frozen decision rule | SUPPORTED iff lower95 > 0.5 AND wrong_A_B == 0 |
| **H_PRIMARY** | **SUPPORTED** |

All six secondary hypotheses were also supported. Because the primary was
supported, they are interpreted as confirmatory under the frozen
gatekeeping (one Holm family of eight, §K).

**What the result is.** It is a **ceiling result on a small number of
independent units**:

- Every eligible pair was resolved, at every degradation level.
- The lower bound of 0.7616 equals 0.05^(1/11). That is the largest value
  the frozen cluster-conservative bound can take with 11 conditions.
- The p-value 0.00048828125 equals 0.5^11, the smallest it can take.
- The experiment cannot say how far above 0.76 the true resolving rate
  lies.

**What made the difference.** Each window alone separated every pair:

- the dynamics witness in T1 (V1);
- the compensation witness in T3 (V2).

The temporal part of the finding therefore rests on the preregistered
negative control, not on the combination adding resolving power. Reading the
dynamics witness **outside** its window (V4) produced the wrong cause on all
55 case-A trials (§O).

## B. Provenance

| item | value |
|---|---|
| XSYS-001 manifest | `868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b` |
| A1 manifest | `55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b` |
| A2 manifest (campaign, stages 0–2) | `d86e857d000d54502ec66bcbc83dbf679c55903aaf8ffe5e557e4514b1dded8f` |
| PX4 source | `547e2caa9883bc1609325f02b4914b4e2482fe62` + the frozen SIH effectiveness patch (`c057ba45…`) |
| PX4 binary (every flight) | `4073466f1b3e42ed073b88d45bda4e4d1168a35730eb23f470ae5a0744dfc085` |
| logger configuration | `9d2c61280b623d53de3b9ff463cff20fce2f3493e1a5a739fcf1c12c7d9dd8df` (matches A2 and every trial record) |
| frozen stage-1 code and v2 | match the A2 manifest (`stage1/STAGE1_SEAL_RECORD.json`) |
| analysis environment | Python 3.11.15, numpy 2.4.6, scipy 1.16.2: equal to the reference environment (`ENVIRONMENT.json`) |
| historical manifests | unchanged; all three freeze verifiers pass (`UNBLINDING_GATE.json`) |

## C. Campaign execution

- The executor was `research/xsys_confirmatory_001/amendment_a2/execution_a2/run_confirmatory_a2.py`.
- It ran from 2026-09-27T21:41:35Z to 2026-09-28T00:56:26Z, and its exit code
  was 0.
- It flew all 66 flights of the A1 matrix, once each, in the frozen A1
  execution order:
  - 55 case-A flights: 11 nuisance conditions × η ∈ {0.95, 0.85, 0.75, 0.65, 0.55};
  - 11 nominal NB flights.
- There were no retries and no operational failures.
- Flight wall times ranged from 49.4 s to 305.5 s (median 176.8 s).
- The completion record, `CAMPAIGN_COMPLETION.json` (sha256
  `03265374ef446a81b4b4ae38ee482cbefea4ce1046090d2b0d2610ff9b0c334c`), was
  sealed and pushed (commit `df44d8a`) before stage 0. It contains no CSIA
  outcome.

## D. Raw-data integrity

- Every ULog was hashed. Each hash matches the one in its trial record.
- Every ULog was compressed with `xz -9e`. Each xz copy decompresses to the
  original SHA-256.
- Sizes: 4.60 GB raw, 0.81 GB compressed.
- `RAW_DATA_MANIFEST.json` (sha256
  `19cb3e4b39116558767990480e1ff2f961f7ac3b9b5316bad56b4c2215095531`)
  records every raw file and xz copy. For each it gives:
  - the trial;
  - the location;
  - the SHA-256;
  - the size.

**Durable storage: DURABLE_STORAGE_PENDING.** The raw ULogs and their xz
copies are **not** in git. They exist only in this session's raw-artifact
directory, recorded in the raw-data manifest. That directory is on
ephemeral storage. No durable artifact store was available, so nothing was
deleted. Until the raw logs are copied to durable storage, the manifest
proves what they were, but the raw data can be lost when the session's
container is reclaimed.

## E. Stage 0

The frozen stage 0 ran from 01:41:13Z to 01:42:37Z:

- `amendment_a1/pipeline_a1/stage0_prepare_a1.py`, unchanged;
- `--mode confirmatory`;
- under the A2 manifest.

There was no manual override and no manual exclusion.
`stage0/STAGE0_REPORT.json` (sha256
`1e1f79f7149cadfc4c9103cde7be346050abf7336ad39a9b0ac838cc09ffee53`) was
sealed and pushed (commit `a2d0f0d`) before stage 1.

| custody item | value |
|---|---|
| flights expected / attempted / valid | 66 / 66 / 66 |
| analysis trials expected / valid | 121 / 121 (55 A, 55 B, 11 N) |
| matched pairs expected / valid / excluded | 55 / 55 / 0 |
| logging, synchronization and manipulation checks | every frozen check passed on every applicable flight (§13 of the preregistration). Onset uncertainty ≤ 8 ms; no gap over 2 steps; ≤ 0.5% missing; no dropouts |
| case-B construction | 55 / 55 within the ratio tolerance (5e-4); motor-0 RPM the only changed channel |
| opaque stage-1 inputs | 121; INDEX.json sha256 `43ee7f4c94afe6f4a18c3f6c1d3ef0a4e0e7678a8739273d46fe0e705114c23b` |
| label key sha256 | `5fe3fe2624176bac1c0b3f06a5a45292ea65bfa945dd37b312c2feb51da02050` |

The key and QC record stayed in custody outside the repository until stage 2.

## F. Exclusions

**None.**

- No flight was excluded, and no analysis trial or pair.
- Every frozen check passed.
- The preregistered report-only independence audit
  (`amendment_a1/independence/audit_campaign_a1.py`) found criterion C1
  holding in the campaign's own nominal flights: max I = 0.00059 ≤ 0.001,
  all 11 conditions audited (`INDEPENDENCE_AUDIT_A1.json`). By its frozen
  rule it cannot exclude anything.

## G. Blindness verification

The external audit, `run_stage1_blinded.py` (unchanged since commit
`224ef03`), was **self-tested before stage 1**
(`BLINDNESS_AUDIT_SELFTEST.json`):

- it flagged each planted access to the label key, QC, the stage 0 report,
  a raw ULog, and the key plus a flight record;
- it flagged nothing on a clean trace.

It then ran stage 1 under `strace`, which recorded every file syscall of
every thread. All blindness checks passed:

| check | result |
|---|---|
| B1: the blind directory holds only INDEX.json and opaque npz | pass |
| B2: the npz files hold only the frozen numeric on-board keys | pass |
| B3: every input is cut at t_rel = −5 s | pass |
| B4: the opaque ids are salted | pass |
| B5: the stage-1 source names no label source | pass |
| B6: self-test, then strace (665 paths touched, **0 forbidden**) | pass |
| B7: the key lies outside every stage-1 input | pass |

## H. Stage 1 seal

- The frozen `stage1_evidence.py` ran exactly once, from 01:43:41Z to
  01:43:44Z, on the 121 opaque inputs. It produced 121 outputs.
- `stage1/STAGE1.json` has sha256
  `ccbc10f5aecde43bbfe7297e2073907089ece1562190383c57e0682c11a0e8e3`, which
  matches its seal.
- `stage1/STAGE1_SEAL_RECORD.json` has sha256
  `6963b2c2f696f3aef0491279649442600a51e4230e662b408ddbe0f6b20300fb`.
- The seal was pushed (commit `c986dac`) before unblinding. It records:
  - the input set: `c5c22659803177e81d3929861c980867c5e76ceae37616faae080401f6e9e4e7`;
  - the code, calibration and v2 hashes;
  - the manifest chain;
  - the timestamps;
  - the blindness result.

## I. Unblinding

- The hard unblinding gate is in `UNBLINDING_GATE.json`. All 11 items passed
  at HEAD `c986dac`:
  - completion, raw-data manifest and stage 0 sealed;
  - exclusions frozen;
  - stage-1 inputs sealed;
  - blindness audit passed;
  - stage 1 complete and sealed;
  - all three manifests valid.
- **The experiment became unblinded at 2026-09-28T01:44:37Z.**
- The frozen stage 2 (`amendment_a1/pipeline_a1/stage2_score_a1.py`,
  unchanged, under the A2 manifest) then ran once, from 01:44:44Z to
  01:44:51Z.
- No individual trial was inspected before it executed.

## J. Primary endpoint

| quantity | value |
|---|---|
| VALID_MATCHED_PAIRS | 55 |
| RESOLVED_MATCHED_PAIRS | 55 |
| PRIMARY_RESOLVING_RATE | 1.0 |
| ONE_SIDED_95_LB | 0.7615958096191473 |
| p vs 0.5 (cluster-conservative) | 0.00048828125 |
| independent units (nuisance conditions) | 11 |
| WRONG | 0 |
| AMBIGUOUS | 0 |
| UNSUPPORTED | 0 |
| NO_EVIDENCE | 0 |
| pairs AMBIGUOUS under local evidence alone (V0) | 55 / 55 |
| PRIMARY_SUPPORTED | **YES** |

The bound is compared with 0.5 at full floating-point precision, as the
frozen code does. 0.7615958096191473 > 0.5, with no rounding near the
threshold. The pair-level exact bound, which assumes independence the design
does not claim, is 0.95900. It is reported by the frozen code only as a
contrast; it is not the decision bound.

## K. H1–H6

The secondary hypotheses are **confirmatory**: H_PRIMARY was supported, so
the fixed-sequence gate opens. H1, H2, H3(b) and H4 at each of five levels
form one Holm family of eight at one-sided α = 0.05. H5 and H6 are
zero-tolerance criteria without a test.

| hypothesis | statistic | raw p | Holm p | estimate | 95% lower bound | status |
|---|---|---|---|---|---|---|
| H1 early dynamics separates (A False, B True in T1) | pair rate | 0.00048828125 | 0.00390625 | 55/55 = 1.0 | 0.7616 | **SUPPORTED** (confirmatory) |
| H2 persistent compensation separates (T3) | pair rate | 0.00048828125 | 0.00390625 | 55/55 = 1.0 | 0.7616 | **SUPPORTED** (confirmatory) |
| H3(a) combining windows loses nothing | PRR(V3) ≥ max(PRR(V1), PRR(V2)) | — | — | 1.0 ≥ max(1.0, 1.0) | — | true (**equality**) |
| H3(b) the invalid window makes A WRONG | WRONG rate among A under V4 | 0.00048828125 | 0.00390625 | 55/55 = 1.0 | 0.7616 | true |
| H3(c) correct use is safe | WRONG under V3 | — | — | 0 | — | true |
| **H3** (a ∧ b ∧ c) | | | | | | **SUPPORTED** (confirmatory) |
| H4 per level η = 0.95 / 0.85 / 0.75 / 0.65 / 0.55 | pair rate | 0.00048828125 each | 0.00390625 each | 11/11 = 1.0 each | 0.7616 each | 5 of 5 levels pass (≥ 3 required): **SUPPORTED** (confirmatory) |
| H5 safe ambiguity | V0 always AMBIGUOUS_CORRECT; no WRONG and no nominal attribution in any valid configuration | — | — | 110/110 V0 ambiguous at C1 and C3; 0 WRONG; 0 nominal attributions | — | **SUPPORTED** (zero tolerance) |
| H6 no wrong-cause improvement | WRONG(V3) ≤ WRONG(V0) and = 0, at C1 and C3 | — | — | C1: 0 vs 0 (UNIQUE 110 vs 0); C3: 0 vs 0 (UNIQUE 110 vs 0) | — | **SUPPORTED** (zero tolerance) |

## L. η-level results

| η | valid pairs | resolved (C3/V3) | UNIQUE_CORRECT A / B | AMBIGUOUS_CORRECT | WRONG | resolving rate | certification |
|---|---|---|---|---|---|---|---|
| 0.95 | 11 | 11 | 11 / 11 | 0 | 0 | 1.0 | all 22 trials at C1 (0.2 s) |
| 0.85 | 11 | 11 | 11 / 11 | 0 | 0 | 1.0 | all 22 at C1 |
| 0.75 | 11 | 11 | 11 / 11 | 0 | 0 | 1.0 | all 22 at C1 |
| 0.65 | 11 | 11 | 11 / 11 | 0 | 0 | 1.0 | all 22 at C1 |
| 0.55 | 11 | 11 | 11 / 11 | 0 | 0 | 1.0 | all 22 at C1 |

η = 0.95 is kept and did not perform worse. It was preregistered as the
hardest level, and its margins are the thinnest (min, median and max over the
11 trials; thresholds θ_dyn = 0.02456, θ_ctrl = 0.002194):

| η | D_T1 case A | D_T1 case B | C_T3 case A | C_T3 case B |
|---|---|---|---|---|
| 0.95 | 0.0376 / 0.0431 / 0.0617 | −0.0071 / −0.0036 / 0.0168 | 0.0523 / 0.0525 / 0.0531 | −0.0004 / −0.0001 / 0.0003 |
| 0.85 | 0.1293 / 0.1346 / 0.1552 | same as above | 0.1761 / 0.1765 / 0.1769 | same |
| 0.75 | 0.2350 / 0.2396 / 0.2569 | same | 0.3330 / 0.3333 / 0.3338 | same |
| 0.65 | 0.3411 / 0.3456 / 0.3568 | same | 0.5381 / 0.5385 / 0.5388 | same |
| 0.55 | 0.4614 / 0.4634 / 0.4753 | same | 0.8177 / 0.8183 / 0.8186 | same |

Case B's statistics are the same at every level. Each B trial is its
nominal source flight with only motor 0's RPM replaced, and every level
reuses the same 11 NB flights.

The thin margin is at η = 0.95:

- **the dynamics witness** in case A had its smallest value at 1.53 θ_dyn;
- **the detectability gate**, which lets case B affirm "dynamics nominal",
  passed by about 4%: s_dyn · L_T1 ≈ 0.0512 against 2 θ_dyn = 0.0491.

The compensation witness had a wide margin at every level: about 24 θ_ctrl
at η = 0.95.

## M. WRONG cases

**Primary configuration (C3/V3): 0. Every other valid configuration: 0.**
The valid configurations are:

- C1: V0, V1, V3;
- C3: V0, V1, V2, V3.

There is no WRONG to list individually. No nominal trial received a cause in
any configuration. No spurious localization occurred on motors 1–3.

The only WRONG outcomes in the whole analysis are the 55 preregistered ones
of the invalid-window negative control. They are listed individually in
`RESULT_SUMMARY.json` under `wrong_individual.V4_invalid_window_negative_control`
and summarized in §O.

## N. Ambiguity

**No pair is ambiguous under the primary configuration.** The only
AMBIGUOUS_CORRECT outcomes are the preregistered local-only ones:

| configuration | AMBIGUOUS_CORRECT (A + B) |
|---|---|
| C1/V0 local only | 110 / 110 |
| C3/V0 local only | 110 / 110 |
| C1/V1, C1/V3, C3/V1, C3/V2, C3/V3, C3/V4 | 0 |

Under local evidence alone, every symptomatic trial kept both causes
(ACTUATION/mechanical + SENSOR/response_sensor), in all 11 conditions, at all
five η, at both checkpoints. The design requires this, because the matched
RPM symptom confirms both causes. Ambiguity was never scored as an error.

## O. Temporal result and the negative control

| evidence | window | what happened |
|---|---|---|
| W_DYN | T1 = [0, 0.2) s, its valid window | case A read "not nominal" (False) and case B read "nominal" (True) in **all 110** symptomatic trials. With RPM alone (V1), it resolved all 55 pairs by C1 = t0 + 0.2 s |
| W_CTRL | T3 = [10, 15) s, its valid window | the same pattern in all 110. Alone (V2), it resolved all 55 pairs at C3 = t0 + 15 s |
| W_DYN read in T3 (V4, the preregistered negative control) | outside its window | case A read "nominal" (True) in **all 55**: \|D_T3\| ≤ 0.0018 against θ_dyn 0.0246, because the controller had compensated. The physical cause was refuted by "DYN_T1_NOMINAL" and the sensor cause was SUPPORTED. **55 / 55 case-A trials WRONG** (rate 1.0, lower bound 0.7616, Holm p 0.0039). Case B was unaffected (55 / 55 UNIQUE_CORRECT) |

The negative control behaved exactly as preregistered in H3(b). It was not
reinterpreted. It shows that, in this closed loop, the physical-dynamics
evidence that separates the causes in the transient reads as exoneration
after compensation. Using it outside its window produced the wrong cause
every time.

**H3(a) held only with equality.** V1 and V2 each already resolved every
pair, so combining the windows (V3) added no resolving power in this
experiment. What the combination demonstrably did was:

- certify at the earlier checkpoint (C1) with the dynamics witness;
- stay correct at C3 by using the compensation witness rather than the
  expired dynamics witness.

## P. Latency

| kind | definition (frozen) | result |
|---|---|---|
| physical onset → first local symptom (detection) | first post-onset step with 1 − ρ² ≥ δ_rpm on motor 0 | 0.0 s in all 110 symptomatic trials: the first step after t0, the same as the dry run. The onset is an instantaneous simulated step |
| physical onset → first valid W_DYN evidence | end of T1 | 0.2 s (C1) by construction |
| physical onset → W_CTRL evidence | end of T3 | 15 s (C3) by construction |
| isolation latency | the checkpoint at which C?/V3 is UNIQUE_CORRECT | 0.2 s for all 110 symptomatic trials (C1) |
| certification / decision latency | frozen: 0.2 s if C1/V3 UNIQUE_CORRECT, else 15 s if C3/V3, else none | 0.2 s for all 110. v2 isolates and certifies in the same call, so the two coincide. They are resolved only to the two checkpoints, not continuously |
| action latency | — | not measurable: XSYS-001 commands nothing |
| computational latency | §Q | not an evidence latency |

These are **evidence-accumulation** latencies set by the preregistered
windows. They are not computation times.

In all 11 nominal flights, the per-sample detection statistic crossed
δ_rpm on at least one motor at some sample. No window-level
LOCAL_RPM_DEFICIT formed, and no localization occurred.

## Q. Computational cost

The frozen stage 1 measures one quantity per trial: the wall time, on the
analysis host, of feature extraction plus the v2 localizations. That is four
motors × nine configurations.

| measurement | value |
|---|---|
| stage-1 per-trial compute (extraction + v2), median | 0.00989 s |
| per-trial min / p95 / max | 0.00894 / 0.01596 / 0.01724 s |
| sum over 121 trials | 1.28 s |
| whole stage-1 process, including strace and freeze verification | 3.03 s |
| evidence extraction alone | **not separately measured**: the frozen code times extraction and localization together |
| v2 localization alone | **not separately measured** (same reason) |

Offline, one host, Python. These are not onboard or flight-hardware figures.
No extrapolation is made.

## R. Preregistration deviations

**NO PREREGISTERED ANALYTIC DEVIATIONS.** Stages 0, 1 and 2 ran the frozen
code, unchanged, once each, under the A2 manifest. No threshold, window,
evidence definition, exclusion, hypothesis, endpoint, statistic or rule was
changed.

Operational deviations and notes:

| deviation | when | why | before / after unblinding | impact on primary | disposition |
|---|---|---|---|---|---|
| `seal_campaign.py` gained operational fields: order position, exit and retry status, xz hashes and sizes, logger-configuration hash (commit `ebac43b`) | after the flights, before the seal and stage 0 | the authorization asked for these fields in the completion record | before | none: no outcome read or computed | accepted; recorded |
| the report-only independence audit ran after stage 2, not "before or beside stage 0" | 01:45Z onward | ordering in this session | after | none: frozen, outcome-blind, reads NB gyro noise only, and by rule cannot exclude or re-analyse | accepted; result C1 holds |
| stage 1 ran through the external wrapper (`run_stage1_blinded.py`) under `strace`, not bare as in §18 of the preregistration | stage 1 | the blindness audit | before | none: the frozen stage-1 script ran unchanged; the wrapper adds audit only | accepted |
| post-flight steps paused about 25 minutes between the executor's exit and authorization | 00:56Z to about 01:20Z | awaiting owner authorization | before | none | recorded |
| the raw logs are not yet in durable storage | now | no artifact store available | after | none on the analysis; a custody risk | **DURABLE_STORAGE_PENDING** (§D) |

## S. Limitations

1. **Simulation only.** PX4 SIH is a simplified multirotor model. No real
   ESC, rotor, airframe, sensor noise or telemetry failure is involved.
2. **Case B is an offline multiplicative replay** of case A's observed RPM
   ratio. It models no specific telemetry failure mode. In PX4 the RPM
   telemetry is a monitoring channel, not a control feedback, so a corrupted
   channel cannot move the controller. That makes case B structurally easy
   to separate from case A.
3. **One airframe, one motor (motor 0), one fault direction** (loss of
   effectiveness), and a single abrupt step onset.
4. **Few independent units.** There are 11 nuisance conditions. The perfect
   rate yields the largest attainable lower bound, 0.7616. The true rate
   cannot be bounded higher with this design.
5. **Ceiling effect.** Every evidence configuration that includes a valid
   window resolved every pair. The experiment does not show that combining
   windows is necessary (H3(a) held with equality). It does not measure
   performance near a boundary, except at η = 0.95, where the dynamics
   margin was thin (§L).
6. **Internal comparison only.** No external baseline was run on the
   matched set: MMAE, IMM, DBN, set-valued observers, or ArduPilot/PX4 logic.
7. **In-sample calibration origin.** The thresholds were set on
   apparatus flights before the freeze, not on this campaign. The
   confirmatory flights are new, but they come from the same simulator.
8. **Raw data not yet durable** (§D).

## T. Supported claim

> In a preregistered, blinded PX4 SIH matched-set experiment, temporally
> conditioned cross-domain evidence distinguished simulated physical
> rotor-effectiveness degradation from matched RPM-telemetry corruption
> beyond the local RPM symptom, under the tested conditions.

Two scoped additions are supported by the frozen secondary results:

- In the same setting, reading the transient dynamics evidence outside its
  preregistered window produced the wrong cause on every case-A trial
  (H3(b)). Using each evidence category only in its window produced no
  wrong attribution (H3(c), H5, H6).
- Each single valid window also sufficed in this setting (H1, H2). The
  combination lost nothing (H3(a)), but it did not add resolving power.

## U. Unsupported claims

This result does **not** support any of the following:

- that CSIA is new or first;
- general cross-system assurance;
- aircraft-wide fault diagnosis;
- real-flight or hardware validation;
- certification in any regulatory sense;
- FORGE or bounded-authority validation;
- general actuator-versus-sensor discrimination;
- superiority over any FDI method;
- that combining temporal windows is necessary;
- performance on real ESC or DShot telemetry faults;
- performance on other motors, airframes, fault shapes or simultaneous
  faults;
- any rate above the 0.7616 lower bound as a guaranteed figure.

## V. Relationship to the pre-result novelty audit

The novelty audit was completed and frozen **before** this result was
opened. It lives in `research/csia_novelty_audit/`, in two stages. It is
**not** revised here.

- Its classification of the surviving formulation, MNC-1 in
  `research/csia_novelty_audit/CSIA_MINIMUM_NOVEL_CORE.md`, is **N2: possibly
  distinct combination, LOW confidence**. That status is unchanged.
- As that audit anticipated, a supported primary strengthens the **evidence
  for the instance**. It does not change what the prior literature contains.
- The claim in §T sits inside the audit's "SAFE ONLY IF XSYS-001 SUPPORTS
  PRIMARY" section
  (`research/csia_novelty_audit/CSIA_PUBLICATION_CLAIM_BOUNDARY.md`).
- Every item in that file's NOT SAFE section remains not safe.

## W. Next scientific question

This section records the question; it authorizes nothing. XSYS-001 is closed.

In the simulated closed loop, each windowed witness alone already separates
physical loss from a replayed RPM symptom. The informative next test is
therefore one **built so that a single window is insufficient**. Examples:

- a telemetry corruption that is not a pure multiplicative replay;
- a corruption that enters a signal inside the loop;
- gradual or intermittent physical degradation that blurs the transient;
- a matched design with more independent nuisance conditions, so a
  near-ceiling rate can be bounded more tightly;
- at least one external baseline run on the same matched set.

Any such work would be a new experiment (XSYS-002 or later), with its own
preregistration.
