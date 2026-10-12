# Paper I — what the evidence requires of the manuscript

Written 2026-10-12 from the committed evidence alone. The manuscript named by
the owner is not yet in this repository, so these are requirements to check
it against, not edits to it. Each finding says what the manuscript must do:
**REPLACE** (a value is wrong), **QUALIFY** (true only with its condition
stated), **DO NOT CLAIM** (no evidence), or **DISCLOSE** (true, and a reviewer
will ask).

Value rows referred to as `XX-nn` are in `VALUE_BINDINGS.yaml`.

## A. Values and comparisons

**F-01 Table 9 latencies — REPLACE.** The trust latency is the first crossing
of the raw trust series below 0.75. That series comes from `run_pipeline`
(`csia/scenarios.py`), which runs the comparator, trust engine and diagnosis
and never steps `FailsafePolicy`. It contains no dwell. The committed
`policy_dwell` block of `research/systems-paper/results/mechanism_b.json` and
`research/physical_validation/CUSUM_FAIRNESS_TABLE.csv` subtract a 1.0 s dwell
that was never there, and the CSV labels the correct figures "DO NOT QUOTE".
The record is `docs/research/MECHANISM_B_DWELL_DISCREPANCY.md` (proposed
FL-053, held outside the sealed failure ledger for the owner to promote).

| arm | CUSUM (s) | trust crossing (s) | CUSUM lead (s) | do not quote |
|---|---|---|---|---|
| 1 m/s ramp | 2.96 | **8.72** | 5.76 | 7.72 |
| 3 m/s spoof | 1.16 | **3.36** | 2.20 | 2.36 |
| 6 m/s ramp | 0.72 | **3.24** | 2.52 | 2.24 |
| clean | no alarm | no crossing | — | — |

SC-09's conclusion survives with a larger margin. **QUALIFY** the comparison:
bench simulator only; `h = 500` is the smallest grid value giving zero alarms
on the same simulator's clean arm (textbook `h = 5` gave 2,681 clean alarm
ticks); the in-control mean and deviation also come from that clean arm; the
CUSUM bank covers five nodes and cannot see either IMU. The comparison is a
property of this configuration, not of the two detector families.

**F-02 S0 — QUALIFY.** 475.6775 is the Beta mass of the `gps` node after
1,500 healthy steps of a synthetic evidence sequence. It is not a flight
observable, and it is not settled: 498.79 by 3,000 steps against a cap of
500. T0 = 0.999791 is settled. Quote S0 with its horizon, and avoid
"settled mass".

**F-03 Bench N* against current-stack crossings — DO NOT CLAIM agreement.**
The bench predicts 93.31 ticks from S0 = 475.68; the current stack measured
S0 = 133–136 and crossed at 94–99 ticks from its own state. The preregistration
forbade testing against 93.31 because the banked state differs. What
replicates is the mechanism: the source recursion reproduces the runtime
trajectory (error at most 2.0e-15) and predicts each crossing exactly. The
numerical proximity of 94–99 to 93.31 is not evidence.

**F-04 History share — QUALIFY as post hoc and threshold-dependent.** 0.440
at T* = 0.75, 0.520 at 0.80, 0.566 at 0.85. "History is a large minority of
the delay" is true only at the preregistered 0.75. The S0 sweep was written
after the campaign against traces already on disk, n = 5, one platform, one
fault family.

**F-05 Trust under fix loss — QUALIFY.** On both platforms trust rose in all
20 fault trials, and rose more in the matched control: median delta
+0.007007 against +0.020594 on ArduPilot (ratio 2.94), +0.003513 against
+0.009499 on PX4 (2.70), ranges disjoint on both (FL-016). The supportable
reading is that the fix-loss fault did not lower GPS trust and slowed its
rise relative to the matched control. It is not that the fault raised trust.

**F-06 Original n = 1 deltas — DISCLOSE.** Both lie outside the repeated
fault ranges (FL-017): ArduPilot +0.008656 above [+0.006996, +0.007145]; PX4
+0.001884 below [+0.002269, +0.003999]. On PX4 the pre-fault trust also moved
(0.9856 to 0.9522), which a watchdog replay attributes to the 0.5 s to 1.0 s
stale-timeout change. That replay wrote no artifact and its inputs are
gitignored flight logs (T4). Why ArduPilot's pre-fault trust did not move is
UNRESOLVED.

**F-07 PX4 fix-loss onset range — QUALIFY or REMOVE.** "12.0005–12.1291 s,
444–451 ticks" appears only in `PX4_REPEAT_RECONCILIATION.md`; no committed
per-trial artifact carries it. The ArduPilot equivalent (12.0399–12.0827 s,
449–450 ticks) is artifact-backed.

**F-08 Two different A1 quantities — DO NOT CONFLATE.** `gnss.position`
MISSING begins at 12.04–12.08 s; the diagnostic gate closes about one second
later, 13.04–13.08 s. The original n = 1 artifact reports the first. A1
captured no trust (FL-014); no A1 trust value exists.

**F-09 Two escalation boundaries — QUALIFY.** N* = 93.31 separates WP-C7's
nine runs by floor-tick count (steps 26–40 never escalated, ramps 104–168 all
did; 9 of 9). The response surface uses N* + 25 = 118.31, crossing plus dwell,
and classifies 19 of 21 cells. These are different predicates: a floor-tick
count is not time below the threshold. The 5 s ramp escalated with 104 floor
ticks, fewer than 118.31; its sampled trace shows trust at or below 0.75 from
64.04 s and the CAUTION alarm at 65.44 s, 1.4 s later, which is consistent
with a crossing followed by the 1 s dwell. The tick-exact escalation boundary
is not resolvable: WP-C7 traces are sampled every 5 ticks.

**F-10 Escalation on the current stack — DO NOT CLAIM.** Only the threshold
crossing is measured there. The committed per-tick logs have an empty
`dwell_state` column, and `assurance_level` reads NORMAL for the 60 logged
ticks after the crossing.

**F-11 PX4 build — REPLACE** any "PX4 v1.18.0-beta1" with
`v1.18.0-beta1-395-g547e2caa98` (commit `547e2ca`, 395 commits after the
tag). ArduPilot is `ArduCopter V4.8.0-dev` at `01a504b`.

## B. Scope and status

**F-12 Negative control is not a replication.** 15,595 ticks, 20 trials, 0
collapses — on fix-preserving trials, which cannot exhibit self-occlusion by
construction. `MECHANISM_A.md` §4b and the artifact's `what_this_does_not_show`
field still say "no fix-loss arm exists on ArduPilot 4.8". That sentence is
stale: A1, A2 and P1 are fix-loss campaigns on the current stacks (SC-26's
row already carries the correction). The manuscript must not repeat it.

**F-13 PX4 narrowing — QUALIFY.** The PX4 link is PARTIALLY_AFFECTED by
passive-link starvation: one of four `gps_fault` relations live before the
fault, gate weight 1.0 rather than 3.0. The collapse stands, narrowed.

**F-14 The 26-log replay — QUALIFY.** 2 alert episodes in 0.5183 monitored
hours: 3.859 per hour, exact Poisson 95 percent interval 0.467 to 13.939.
Every log is UNANNOTATED and verified-healthy exposure is 0 h, so this is an
episode rate and never a false-alarm rate. The historical artifact counts 3
transitions; the merging rule that makes them 2 episodes is not recorded
anywhere machine-readable. The 26 input logs are listed by id with no
SHA-256, and they were not acquired on this host.

**F-15 Support-exposure study — NOT RUN.** SC-22 has no data and no result.
No other dataset may stand in for it.

**F-16 Five-stage evidence-availability taxonomy — no artifact defines one.**
`research/v1_1/results/EVIDENCE_AVAILABILITY.json` is a per-relation
live-share matrix over 32 ArduPilot and 12 PX4 flights, with 13
platform-relation pairs never live. A five-stage taxonomy in the manuscript is
a definition and must be presented as one, with this matrix as its only
measured support.

## C. Provenance a reviewer will ask about

**F-17 A1 preregistration timing — QUALIFY.** The plan fixed the
preregistration's SHA-256 before trial 1, but plan and text entered git at
`bfc16f5`, 5 min 48 s after trial 1 began; 8 trials ran at `33d3d61`. A2 and
P1 committed theirs before their first trials.

**F-18 Mechanism B preregistration — DISCLOSE.** The result cites blob
`0e18611` (`b7d3d9e`), not the ALT_HOLD amendment `80959bb` committed 18 s
before the first trial. Two harness commits landed mid-campaign, before the
ramp arm finished; neither touched threshold, tolerance or rule. The
post-hoc addendum is labelled as such in the preregistration file.

**F-19 Dirty working trees — DISCLOSE.** 114 of 120 current-stack Mechanism A
trials ran on a tree with uncommitted changes; the frozen-core diff was empty
in all 120.

**F-20 Observational units.** The unit is the trial: 20 per arm per platform,
plus 20 Mechanism-B trials. Ticks within a trial are not independent samples,
and the 378,000 comparisons are a deterministic enumeration (9 scenarios x
1,500 ticks x 28 pairs), not a sample. Neither may be used as a sample size.

**F-21 Determinism scope.** The bench is deterministic: seven generators
re-ran today with 0 differing keys. The SITL campaigns are not: values vary
within the reported ranges, and the campaigns report N, median, range and IQR
only, with no p-values, because they are runs of a deterministic simulator
under host jitter, not draws from a population.

## D. Text to insert

**Successor-system boundary**, ready to paste:

> The implementation evaluated in this paper is a frozen research system
> (`csia-v1.0-research-final`). Subsequent CSIA development introduced
> successor semantic, evidence-assurance and offboard analysis layers; those
> layers are outside this manuscript's evidence base. No result in this
> manuscript is recomputed using those successor systems.

**Simulation statement**, ready to paste:

> Every current-stack result is from software-in-the-loop simulation
> (ArduPilot SITL and PX4 SIH); every bench result is from the frozen
> research simulator. No result was obtained on flight hardware.
