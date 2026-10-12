# Trying to make 2.1.1 give a worse answer (Phase 12)

**2026-10-01.** Each row says what was tried and what happened, including the
probes that found nothing.

**What counts as worse:**
- **WORSE** is a wrong answer, or a right answer lost for a wrong reason.
- **LESS CERTAIN** is reported in its own column and is not counted as worse.
  The brief asked for the two to be kept apart.

**Where the numbers come from:**
- `worse_answer_revision.py` (`WORSE_ANSWER_REVISION.json`);
- `dataset_a_three_way.py` (dataset A);
- `fault_replay.py` (dataset D);
- `transition_replay.py` and `epoch_adversarial.py` (dataset E);
- `profile_validation.py`.

## 1. The search

| looked for | how | worse | less certain | verdict |
|---|---|---|---|---|
| new wrong UNIQUE | dataset A (2,640 ticks) against v2.0 and against 2.1.0 + r1; dataset D (71,280 injections); E1 and 14 variants; 13 profile variants of MS_B5 / MS_TS_B5 | **0** | — | none found. The 3 wrong UNIQUE at TS_CPU_OVERLOAD onset (L16) are shared with v2.0 and 2.1.0 |
| new wrong SUPPORTED | dataset A against 2.1.0 + r1; dataset D; E1 with every predicate failed (1,620 injections) | **0** | — | none found. The 7 wrong SUPPORTED in dataset A are shared with v2.0 and 2.1.0 |
| true hypothesis eliminated | dataset A against 2.1.0 + r1 | **0** new | — | the 121 L16 onset eliminations are shared with v2.0 |
| relevant evidence wrongly invalidated | E1 and the 14 epoch variants against a per-record validity truth | 0 in E1 and in every variant that keeps the epoch contract | EARLY_NEW_EPOCH 2 record-ticks, MISSING_TRANSITION 61, MALFORMED 51, ROLLOVER 9, no context 111: all fail-closed | **see §2.1**: fail-closed costs, with one consequence that needs the contract |
| epoch rule too broad | the same | — | the fail-closed rows above | too broad only when the contract is broken; in E1 0 valid records were withheld |
| epoch rule too narrow | the same | **MISSING_TRANSITION_SILENT 9 ticks, RESTART_COUNTER_ONLY 6 ticks, SWITCH_BACK_LANE_ID 4 ticks** | — | each is a contract violation. Under 2.1.0 the same streams give 9 stale ticks in every variant, so these are not worse than the pre-revision system |
| policy B withholding unrelated conclusions | dataset D roles | **0**: 0 of 75,752 IRRELEVANT pairs lost anything; 0 withholds without a material refuter | 42 correct SUPPORTED that rested on a failed refuter withheld | the 42 were right by luck (the failed refuter happened to be False); withholding them is the rule working |
| starvation ignoring a true pacing dependency | H1, below | **yes, when the profile omits a real pacing input** | — | **see §2.2**: a profile error class R-2 depends on |
| profile interaction | R-2 with r1, r2, every shadow candidate and R-BAD; pacing mutations PM0-PM7; overlays carrying epoch stamps | PM2 (GNSS declared as pacing on an existing edge) restores the wrong W7 answer | PM4 / PM5: 204 G-2 units back to uncertain | PV9 catches PM1 and PM5; PM2 is a wrong statement of architecture no static rule can see (§2.2). Overlays keep every epoch stamp |
| order or duplicate dependence | all 2,640 dataset A ticks under 2.1.1 + r2, reversed, shuffled and duplicated; the 60 E1 ticks with epochs, reversed and duplicated | **0** decision changes | — | order changes only the order of `candidate_detail` lists inside the 2.0 view. Frozen `attribute()` does that in 2.1.0 too (459 ticks), so it is presentation, not decision |
| UNKNOWN acting as healthy | E1 with no context; MALFORMED; EARLY_NEW_EPOCH | — | **5, 5 and 1 real POSITION_UNAVAILABLE ticks not raised** | **see §2.1** |
| hidden predicate failure | dataset D under 2.1.1 | **0** hidden | — | 15,118 of 15,118 (R-1 only), 17,400 of 17,400 (all + r2) and 123 of 123 (pacing predicate) evaluated faults visible |

## 2. The three findings that need words, not just a count

### 2.1 Admission that fails closed can hide a symptom

**What happens.** When stamped evidence is not admitted for a reason that does
not mean "stale", it becomes UNAVAILABLE. Those reasons are: no context, a
malformed stamp, or a context that is a tick behind. If that evidence was the
only thing that would raise a symptom, the symptom is not raised:
- in E1 with no context, POSITION_UNAVAILABLE on ticks 20-24 (5 ticks);
- with a malformed stamp, the same 5;
- with a new-epoch record arriving one tick early, 1 tick.

**Is it UNKNOWN acting as healthy?** Not in the decision rule. No hypothesis is
confirmed, rejected or narrowed by the UNAVAILABLE record, and nothing is
reported nominal. It is the detector rule that 2.1.0 already has: a scoped
detector raises on False, never on None.

**What is new is the cause:** an integration fault, rather than a missing
producer, can now make evidence UNAVAILABLE.

**Why it is not hidden:**
- every withheld record is in the tick's admission report, with its reason;
- in E1 and in every variant that keeps the contract, no valid record was
  withheld.

**Mitigation:**
- **Already true:** UNKNOWN_EPOCH_KEY and MALFORMED_EPOCH are reported.
- **Recommended, not built:** a deployment should treat either reason as a
  configuration error. A symptom-level flag ("a symptom this evidence could
  raise was not evaluated") would close the trace gap. Both are integration
  or trace work outside R-3's scope.

### 2.2 R-2 is only as good as the pacing declaration

**H1, undeclared pacing input.** The estimator was given a second IMU it
truly needs (ALL), but only imu0 was declared. When the undeclared imu1 dies:
- 2.1.1 rejects starvation (imu0 is healthy) and SUPPORTS process_stall,
  which is wrong;
- 2.1.0 + r1 said AMBIGUOUS there, because it has no declaration of any
  input;
- declaring both inputs gives AMBIGUOUS with starvation confirmed.

**The failover form gives the same:** the declared imu0 is not the one in
use, and the one in use dies.

**PM2, a wrong declaration on a real edge.** Declaring the GNSS link as the
pacing input, on top of the rejected R5b edge, restores the wrong W7 answer.
PV9 cannot catch it: the edge exists.

**What these are.** Profile errors, of the same class as the shadow study's
mutations M1 to M6. They are not defects in the rule.
- **Why the profile matters:** R-2 moved the starvation question from "which
  links are in the closure" (wrong by construction, L17) to "which inputs pace
  the output". The profile must state that correctly and completely.
- **What the frozen aircraft profile has:** one IMU, declared, with the EKF2
  source cited.

**What a new profile must do.** Declare every pacing input, with production
semantics:
- **ANY over all IMUs on PX4.** In multi-EKF mode each instance is paced by
  its own IMU and the selector publishes while any instance runs; the single
  EKF uses the voted IMU with failover.
- **Cite the code that gates the output.**

**What a static declaration cannot follow** is a pacing input that changes
with the configuration (L21). Pacing keyed by configuration epoch would close
it. That is a dependency of R-2 on R-3, which this revision stops at and does
not build.

### 2.3 The epoch rule needs its contract

There are five integration requirements (`R3_CONFIGURATION_EPOCH.md` §6):
1. supply the context;
2. key on a monotonic counter;
3. use a composite epoch across producer restarts;
4. unwrap narrow counters;
5. take the context from the configuration owner.

Each probe that broke one reproduced at most what 2.1.0 does with no rule at
all.

## 3. What was not found

Against frozen v2.0 or against the pre-revision 2.1, on any dataset, the
search found:
- no wrong UNIQUE;
- no wrong SUPPORTED;
- no eliminated true hypothesis;
- no hidden fault;
- no order or duplicate dependence;
- no unrelated conclusion withdrawn by the fault policy.

**The worse answers it did find all need a broken precondition:**
- a pacing declaration that is wrong or incomplete (§2.2);
- an epoch integration that breaks its contract (§2.3).

**Where the less-certain answers come from:** the fail-closed side of R-3.
