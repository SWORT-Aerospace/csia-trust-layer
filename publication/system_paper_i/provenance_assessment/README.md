# Paper I provenance assessment: dirty trees, frozen-core identity, injection-onset fix

2026-10-18. Read-only. No campaign was rerun, and no frozen evidence, product
code, sealed ledger or manifest was modified. Every number below is in
`assessment.json`, which `build_assessment.py` generates from committed trial
records, committed plans, committed Mechanism B results and git objects.
`python publication/system_paper_i/provenance_assessment/build_assessment.py --check`
recomputes it and fails on any difference. Today's working tree was not used to
infer anything about what was dirty when a trial ran.

Labels used throughout:

- **VERIFIED**: recomputed today from committed bytes or git objects.
- **RECORDED**: written at the time by the harness or a committed document, and
  not independently re-checkable now.
- **UNRECOVERABLE**: no record exists from which it could be established.

## 1. The counts (VERIFIED)

| campaign | trials | `dirty: true` | clean trials |
|---|---|---|---|
| A1 (ArduPilot repeat) | 40 | 39 | MECHA-ARDUPILOT-009 |
| A2 (ArduPilot trust completion) | 40 | 36 | MECHA2-ARDUPILOT-006, -018, -024, -028 |
| P1 (PX4 repeat) | 40 | 39 | MECHP1-PX4-017 |
| **total** | **120** | **114** | 6 |

The manuscript's 39/40, 36/40, 39/40 and 114/120 are correct. Every manifest's
`manifest_sha256` recomputes (120 of 120).

## 2. What the flag measures

`tools/csia_experiment/manifest.py`, `provenance()`:
`"dirty": bool(_git("status", "--porcelain"))`, evaluated when
`orchestrator.run_trial` writes the manifest, which is after the flight. It is
true for any untracked or modified file that is not gitignored, generated
results included. Ignored files do not count. No file list, diff or hash was
stored. So the flag means "the working tree was not identical to HEAD", not
"trial code had uncommitted changes".

## 3. What made the trees dirty

**3.1 A sufficient explanation, VERIFIED.** The runner writes `_plan.json` and
each trial's manifest into the campaign directory inside the repository.
Other trial output did not count: the A2 and P1 records state that their trust
traces went to `/tmp` (for example
`trust_trace_path: /tmp/a2/trace/MECHA2-ARDUPILOT-001_FAULT.trace.jsonl`), the
runner's raw-output default is `/tmp/p8/raw` (A1 records no location), and
flight logs go to the gitignored `logs/`. For each trial, `build_assessment.py` lists the
runner outputs that existed before it (the plan, and every earlier trial's
manifest by flight time) and asks git whether each was in the recorded HEAD.
"At least one was absent" predicts the recorded flag in **120 of 120** trials,
including all six clean ones: each clean trial is the first one after a commit
that contained every earlier output. No trial is dirty without such a file,
and none is clean with one.

**3.2 Trial-affecting code that ran uncommitted, VERIFIED.**

- **A1-001 to A1-008, HEAD `33d3d61`.** The runner
  (`run_mechanism_a_repeat.py`), the manifest writer, the orchestrator, the
  adjudicator (`validity.py`) and the A1 preregistration are all absent from
  that commit's tree. `manifest.py` ran `git rev-parse HEAD` in its own
  repository and got `33d3d61`, so it was an untracked file there. All five were
  first committed in `bfc16f5` (2026-09-06T04:23:59Z). The preregistration is
  the one dirty file with a contemporaneous hash: the recorded
  `prereg_sha256` `f08e3dde…540a` equals the committed text.
- **A2-001 to A2-005, HEAD `ceeaf4a`.** The committed runner there (blob
  `db518e8`) has neither `--trust-trace-dir` nor `--campaign-id`, yet these
  records carry `trust_trace_path` and `trust_trajectory: CAPTURED` under
  campaign `MECHA2-ARDUPILOT`. The first runner that can produce them (blob
  `51658c0`) was committed in `ba9a8f4` (20:06:49Z), after A2-005.

**3.3 Committed changes during the campaigns, VERIFIED.** The recorded HEAD
moved 1 time in A1, 4 times in A2 and 6 times in P1. Classified by path
(`head_transitions` in `assessment.json`):

| campaign | transition | trial-affecting code changed |
|---|---|---|
| A1 | `33d3d61` to `bfc16f5` | the five harness files of 3.2, first committed |
| A2 | `ceeaf4a` to `ba9a8f4` | runner `db518e8` to `51658c0` (the trace capability of 3.2) |
| A2 | three later transitions | none: trial files, post-trial analysis code, mutation tooling, docs, tests |
| P1 | six transitions | none: trial files, the post-trial extractor and its output, docs, tests, the `Makefile` default interpreter |

The SITL driver `tools/deploy/shadow_sitl_check.py` is blob `abdfdf9` and the
`csia/` tree is one tree id at every head of all three campaigns.

Classes are assigned by path; the rule is `classify()` in `build_assessment.py`.

**3.4 Consistency, VERIFIED.** The committed adjudicator (`validity.py`, blob
`83e98d3`, its only committed version, present at every head except `33d3d61`)
re-run over the recorded records reproduces the
recorded adjudication in 120 of 120. The recorded preregistration hash equals
the blob at the recorded HEAD wherever that HEAD contains the
preregistration: 32 of 40 in A1 (the other 8 are the trials of 3.2), 40 of 40
in A2 and 40 of 40 in P1.

**3.5 UNRECOVERABLE.**

- The full dirty contents of any of the 114 trials. No porcelain listing,
  diff, snapshot or file hash was kept, the preregistration aside.
- Whether other files were on disk, for example the DEA and mutation files
  that entered git with `bfc16f5`.
- Whether the runner bytes that ran equal the first committed version. The
  runner is one long-lived process that loads its modules once, so a later
  trial's `head` does not identify the runner code in memory.
- Whether the driver or an unfrozen `csia/` module carried an uncommitted edit
  at any dirty instant.

A bound exists: at the six clean instants the whole non-ignored tree equalled
HEAD, so the driver and `csia/` equalled the committed blobs, which are the
same at every head of the campaign. An edit made and reverted between two
clean instants is not excluded.

## 4. Frozen-core identity without the research tag

- **Tag:** `csia-v1.0-research-final` is absent locally and on GitHub (the push
  was refused).
- **RECORDED at trial time, 120 of 120:** `frozen_core_tag_resolves: true` and
  `frozen_core_diff_empty: true`. The check is
  `git diff --stat <tag> -- <FROZEN_PATHS>`, which compares the tag with the
  working tree, so an uncommitted edit to a tracked frozen file would have
  shown. It ran after the flight.
- **RECORDED 13 days earlier:** the tag names commit `ec5acd1`
  (`docs/v1/FROZEN_BASELINE.json`, first committed `4c213d6`, 2026-08-24).
- **VERIFIED today:** `ec5acd1` exists. Its 12 baseline SHA-256 digests cover
  exactly the files under the six frozen paths at that commit. At all 15 heads
  (14 trial heads and the P1 plan head `acb5b6a`): `ec5acd1` is an ancestor,
  the frozen-path diff against it is empty, `FROZEN_BASELINE.json` is unchanged,
  all 12 digests match, and the firewall's `FROZEN_PATHS` is unchanged.
- **Independent of the documented mapping:** at the six clean instants the
  working tree equalled HEAD and the recorded diff against the tag was empty.
  So the tag's frozen-path content equalled HEAD's, which equals `ec5acd1`'s.
  With the recorded empty diff at every trial, the tracked frozen-path content
  of the working tree equalled `ec5acd1` at every manifest write. This holds
  provided the local tag was not moved during 2026-09-06; no move is recorded,
  and `FROZEN_SOURCE_DIGESTS.json` (2026-09-07) again records an empty diff.
- **Limits:** a new untracked file under a frozen path is invisible to
  `git diff`. The check ran after the flight, not when the modules loaded. The
  tag object cannot be inspected. None of this pins the unfrozen harness.

## 5. The later injection-onset fix

**Commit:** `9f39474054d7f332971b8f7f8202c5d7a7e62a7a`, 2026-08-25T20:14:32Z.
**File:** `tools/deploy/shadow_sitl_check.py` (blob `a503e7c` to `ac57102`).
It is named in `tools/simulation/paper_scalar_audit.py`.

**Affected campaign:** Mechanism B on the current stack, the GNSS-glitch
campaign on ArduPilot 4.8 SITL (`research/v1_1/CURRENT_STACK_REPLICATION.md`,
runner `tools/deploy/mechanism_b_campaign.py`). Its 20 trials flew
02:45:12Z to 03:09:52Z on 2026-08-25, and the results were committed in
`670aa7a` (03:18:20Z), all before the fix.

**Not affected: A1, A2 and P1.** They inject `gps_fix_loss`, not `gps_glitch`,
and every trial head carries driver blob `abdfdf9`, which already contains the
fix (it is the blob of `b8dcdc8`, a descendant of `9f39474`).

**Behaviour before and after the fix:**

- *Old:* `run_gps_glitch` read the base `SIM_GPS1_GLTCH_X` inside the
  injection timer. The first write landed 2.17 to 2.68 s after the commanded
  20.0 s (recorded `wrote_at_rel_s` 22.17 to 22.68 s).
- *New:* `prepare_gps_glitch` reads the parameter at setup, so the write
  follows the commanded instant within milliseconds. The fix also adds a ramp
  cancellation event. The historical records already carry both `at_s` and
  `wrote_at_rel_s`.

**Unaffected, VERIFIED from the committed results and tick logs:**

- Onset handling. In 15 of 15 faulted trials the analysis onset is the
  recorded write, and `fault_truth` starts at `onset_tick`. The reported
  position residual responds 1 to 2 ticks later on steps and 7 to 8 ticks later
  on ramps, which start small.
- The results, all counted from that onset:
  - crossing counts (ramp 5 of 5, every other arm 0 of 5);
  - crossing ticks 94 to 99, with observed equal to predicted;
  - reconstruction errors;
  - minimum trust;
  - reported offsets.
- No carry-over. The base parameter read 0.0 before every write.
- The ramp ends at 42.17 to 42.68 s, inside the 60 s window, so the
  cancellation defect neither truncated nor extended a ramp.

**Affected, as description or interpretation:**

- (a) "onset at t = 20.0 s" is true of the clean arm only. Faulted onsets are
  22.17 to 22.68 s.
- (b) "40 s (1000 ticks) after onset" and "the ramp completes at t = 40 s".
  Faulted arms had 933 to 946 post-onset ticks and ramps ending at 42.17 to
  42.68 s; the clean arm had 1000 ticks.
- (c) Section 10.1 compares S0 and T0 at different instants. The clean arm is
  measured at 20.0 s (S0 120.46 to 120.51, T0 0.9541) and the faulted arms at
  their writes (S0 133.3 to 136.5, T0 0.960). The committed full trace of
  RAMP_20S_0 gives S 120.43 and T 0.9541 at 20.0 s, identical to the clean arm,
  and S 133.10 at its write. So the clean-against-faulted difference reflects
  when S0 was measured, not the condition. The control's precondition value
  (about 120.5 at 20.0 s) is about 13 to 16 below the banked state the faulted trials
  carried into the fault.

The fix does not invalidate the campaign. Its verdict and crossing pattern
stand.

## 6. Instruction for the paper-writing session

> **Dirty trees.** Keep 114 of 120 (39/40, 36/40, 39/40), but describe the flag
> exactly: "the working tree was not identical to the recorded commit when the
> trial manifest was written (`git status --porcelain` non-empty, untracked
> files included)". Do not write "uncommitted code changes" for all 114. State
> what is established: in every dirty trial the campaign's own uncommitted
> result files (the plan and earlier trial manifests) were present, and that
> alone accounts for every flag. Also state that A1 trials 1 to 8 ran harness
> code (runner, manifest writer, orchestrator, adjudicator) and the
> preregistration before they were first committed, and that A2 trials 1 to 5
> ran a runner revision first committed after them. Say the remaining dirty
> contents are not recorded.
>
> **Frozen core.** Say: "every trial manifest recorded an empty diff between
> the working tree's frozen-core paths and the freeze tag. The tag is not
> available in the public repository; it is documented as commit `ec5acd1`, and
> at every trial head the frozen-core files are byte-identical to that commit".
> Do not claim the unfrozen harness was pinned.
>
> **Onset fix.** It belongs to the current-stack Mechanism B GNSS-glitch
> campaign, not to A1, A2 or P1. If the paper reports that campaign: give the
> onset as the recorded write, 2.2 to 2.7 s after the commanded 20.0 s, with
> 933 to 946 post-onset ticks. Do not present the clean-against-faulted S0 or T0
> difference as a condition effect. The crossing results may be reported
> unchanged. A later fix is not evidence that these results are invalid, and
> the paper should not imply it is.

## 7. Supporting records

| claim | record |
|---|---|
| per-trial flags, heads, flight ids | `campaigns/physical_validation/{mechanism_a_repeat_ap,mechanism_a_trust_completion_a2,mechanism_a_px4_repeat_p1}/*.json`, `provenance` block |
| flag definition | `tools/csia_experiment/manifest.py`, `provenance()` |
| runner writes into the campaign directory; raw output to `/tmp` | `tools/csia_experiment/run_mechanism_a_repeat.py`, `main()`; `tools/csia_experiment/orchestrator.py`, `plan_campaign()`, `run_trial()` |
| reconstruction, transitions, harness blobs, adjudication re-run | `assessment.json`, keys `dirty.*` and `established_uncommitted_trial_code` |
| tag to commit | `docs/v1/FROZEN_BASELINE.json` (`commit`, 12 `files` digests); `docs/v1/V1_FINAL_RESEARCH_VERDICT.md` |
| frozen paths | `csia/aircraft/firewall.py`, `FROZEN_PATHS` |
| per-head frozen checks | `assessment.json`, key `frozen_core` |
| onset fix | commit `9f39474`, `prepare_gps_glitch` docstring in `tools/deploy/shadow_sitl_check.py`; `tools/simulation/paper_scalar_audit.py` |
| Mechanism B onset data | `research/v1_1/results/current_stack_replication.json`; `research/v1_1/results/mechanism_b_gps/*.json`, `ticks/*.csv`, `ardupilot_RAMP_20S_0.trace.jsonl.gz`; `assessment.json`, key `injection_onset_fix` |
| Mechanism B code invariance across its seven generating commits | `research/v1_1/results/PROVENANCE_BACKFILL.json` |

## 8. Relation to earlier records

`publication/system_paper_i/final_update/CAMPAIGN_PROVENANCE.md` ("Dirty
trees") and `MANUSCRIPT_FINDINGS.md` (F-19) describe the 114 trials as having
"uncommitted changes". That wording is less precise than section 2 here, and
this assessment supersedes it for the paper. Those files are left unchanged.
The SC-09 correction (FL-053) is a separate matter and remains PROPOSED.
