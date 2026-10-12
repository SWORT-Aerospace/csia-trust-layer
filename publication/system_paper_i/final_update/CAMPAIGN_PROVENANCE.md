# Paper I — provenance of the current-stack campaigns

Read-only extraction, 2026-10-12, from committed trial records, campaign
reports, derived artifacts and `git log`. Nothing listed here was re-sealed,
re-hashed or edited. Every SHA-256 below is also pinned in
`VALUE_BINDINGS.yaml` and re-checked by `verify_bindings.py check`.

No campaign has a single "generating commit", and none is invented here. Each
one has a plan head, a span of trial heads, a preregistration commit, a raw
archive commit (where one exists) and a results commit. All five are given.

## 1. Mechanism A on the current stacks: A1, A2, P1

| | A1 | A2 | P1 |
|---|---|---|---|
| directory | `campaigns/physical_validation/mechanism_a_repeat_ap` | `campaigns/physical_validation/mechanism_a_trust_completion_a2` | `campaigns/physical_validation/mechanism_a_px4_repeat_p1` |
| platform | ArduPilot SITL | ArduPilot SITL | PX4 SITL (SIH) |
| autopilot build | ArduCopter V4.8.0-dev @ `01a504b472259602e13df4cf07df7c0cdbb35993` | same build, 40/40 records | PX4 `547e2caa9883bc1609325f02b4914b4e2482fe62`, version string `v1.18.0-beta1-395-g547e2caa98` |
| frozen core | `csia-v1.0-research-final`, diff empty, 40/40 | same, 40/40 | same, 40/40 |
| planned / valid | 40 / 40 (20 FAULT + 20 CONTROL) | 40 / 40 | 40 / 40 |
| plan head | `33d3d61` | `ceeaf4a` | `acb5b6a` |
| preregistration | `MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md`, SHA-256 `f08e3dde…540a`, one commit `bfc16f5` 04:23:59Z | own text `MECHANISM_A_ARDUPILOT_TRUST_COMPLETION_PREREG.md`, SHA-256 `b8340445…6a07`, one commit `ceeaf4a` 20:00:32Z; plan and trial records cite the A1 text and hash | `MECHANISM_A_PX4_REPEATED_PREREG.md`, SHA-256 `78d02317…1f93`, one commit `1968ffd` 20:19:52Z |
| first trial (flight id, head) | 04:18:11Z at `33d3d61` | 20:03:01Z at `ceeaf4a` | 21:00:50Z at `c449934` |
| last trial (flight id, head) | 04:45:52Z at `bfc16f5` | 20:30:54Z at `63af8c2` | 21:33:51Z at `c5ea4d2` |
| trial heads | `33d3d61` x8, `bfc16f5` x32 | `ceeaf4a` x5, `ba9a8f4` x12, `1e7fb04` x6, `1968ffd` x4, `63af8c2` x13 | `c449934` x3, `b93624e` x6, `94c7437` x1, `76e2e69` x3, `7ca96bd` x2, `adbd6d0` x1, `c5ea4d2` x24 |
| working tree dirty at trial | 39 of 40 | 36 of 40 | 39 of 40 |
| trust trace | NOT CAPTURED (FL-014) | captured 40/40 | captured 40/40 |
| raw archive | none | `research/physical_validation/results/a2_traces_raw/`, 40 gzipped traces, manifest SHA-256 `7c7db871…8149`, committed `d5c048b` | `p1_traces_raw/`, 40 traces, manifest `0cfc30f3…7e07`, committed `77e91f9` |
| archive integrity, re-checked today | n/a | 40 of 40 decompressed traces match the manifest | 40 of 40 match |
| reduction script | `tools/csia_experiment/extract_mechanism_a.py` (reads gitignored flight logs) | `tools/csia_experiment/extract_trust_a2.py --campaign-key a2` | same script, `--campaign-key p1` |
| summary artifact | `mechanism_a_repeat_ardupilot.json`, `aa79eb64…`, at `c87a325` | `mechanism_a_a2_trust_ardupilot.json`, `c251c433…`, first `d5c048b`, current bytes `b93624e` | `mechanism_a_p1_trust_px4.json`, `c4ace83d…`, at `77e91f9` |
| seal | `_CAMPAIGN_A1.yaml`, `93c54c45…`, sealed at `c87a325`, committed `ceeaf4a` | no seal file | no seal file |

### What the manuscript may and may not say about these

- **A1 timing.** The plan records the preregistration's SHA-256, and that hash
  equals the committed text. But the plan and the preregistration entered git
  together at `bfc16f5`, 5 min 48 s after trial 1 began, and 8 trials ran at
  the earlier head `33d3d61`. "Preregistered" is supportable as "hash-fixed in
  the campaign plan before the first trial"; "committed before any trial" is
  not supportable for A1.
- **A2 and P1 timing.** Each preregistration was committed before its first
  trial: A2 at 20:00:32Z against a first trial at 20:03:01Z, P1 at 20:19:52Z
  against 21:00:50Z.
- **A2 citation.** A2's trial records and plan cite the A1 preregistration
  path and hash; A2's own trust-completion text is cited by the derived
  result. Both were committed before A2's first trial. State both.
- **Dirty trees.** Trials ran on working trees with uncommitted changes in 114
  of 120 trials. The frozen core diff was empty in all 120, so the scored code
  is pinned; the harness around it is not pinned by commit alone.
- **`b93624e`** changed the A2 summary by two metadata lines only (a
  `platform` field and the schema name). No value changed, and the regenerated
  CSV was byte-identical. Re-checked today: the extractor reproduces every
  trust field of both A2 and P1 from the committed archives.
- **Not re-derivable here.** Eleven per-trial fields of the A2 and P1 summaries
  (diagnosis ranks and weights, live-relation counts, flight-log name) and all
  A1 quantities come from flight logs under `logs/`, which is gitignored. The
  values stand as committed; they are T3 in the ledger, not T1.

## 2. Mechanism B on the current stack

| | |
|---|---|
| result | `research/v1_1/results/current_stack_replication.json`, `c257898a…64e1`, current bytes at `670aa7a` (2026-08-25T03:18:20Z) |
| path history | the same path first held an earlier mag_emi "does not replicate" result (`d792b3e`, 02:21:07Z), written before the authoritative preregistration and filed separately by it |
| preregistration | `research/v1_1/CURRENT_STACK_REPLICATION.md` at `b7d3d9e` (02:36:50Z), blob `0e18611` — the blob the result cites |
| amendment | `80959bb` (02:44:54Z), blob `f90ff69`: flight mode ALT_HOLD for the scored window; grid, magnitudes, threshold, tolerances and rule untouched. 18 s before the first trial. The result cites the pre-amendment blob, not this one |
| trials | 20 ArduPilot 4.8 trials, flight ids 02:45:12Z to 03:09:52Z (start times) |
| harness changes during the campaign | `256ca51` (an incomplete campaign returns CAMPAIGN_INCOMPLETE instead of a verdict) and `a4cd2e8` (tick logs gain their 20 pre-onset rows). Both before the ramp arm finished; neither touches threshold, tolerance or rule |
| per-tick logs | `research/v1_1/results/mechanism_b_gps/ticks/*.ticks.csv`, committed |
| trust traces | under gitignored `logs/mechanism_b_gps/`, except `ardupilot_RAMP_20S_0.trace.jsonl.gz` |
| post-hoc additions | `2622d0f` appended "Post-hoc addenda (NOT preregistered)": the S0 sensitivity and the threshold-dependent history share |
| reduction script | `tools/simulation/current_stack_replication.py` |
| PX4 | INAPPLICABLE; 0 trials; no substitute intervention, as the preregistration requires |

**The negative control (15,595 ticks) is not a separate campaign.** It is the
committed per-tick logs of these 20 trials, re-read by
`research/systems-paper/current_stack_structural.py`.

**One cosmetic data fault, no effect on any value.** In
`ardupilot_RAMP_20S_4.ticks.csv`, the `S_k` cell at tick 669 repeats tick 668.
`T_k` at 669 is correct, the recursion is consistent once that cell is
skipped, and the trial's crossing (tick 661) precedes it.
