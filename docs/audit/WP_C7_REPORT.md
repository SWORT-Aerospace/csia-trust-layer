# WP-C7 — Replication, the Glitch Non-Alarm, and False-Healthy Exposure

**Date:** 2026-08-23 · **Branch:** `research/wp_e1` · **PR #13**
**Suite: 482 → 482, all passing.** No production changes. The abstaining policy
is research code only.
**Deliverables:** `research/wp_c7/`, revised `papers/csia_systems/`,
`docs/audit/WP_C7_REPORT.md`, three figures.

---

## 1. Verdict

**Part 1.2 passes, with a correction.** The WP-C6 campaign is not one condition
replicated 24 times. Home site reached the simulation and changed the vehicle's
behaviour by 216 times the within-site spread. But **wind never reached the
physics**: `SIM_WIND_SPD` is stored and reads back correctly, and a vehicle
holding position tilts 0.159° at 0 m/s and 0.159° at 12 m/s. WP-C6 described
two axes of variation and had one. Everything downstream stands; the
description was wrong.

**Part 2 has a tested cause, and it is not the one we were given.** The
detector is not blind. It floors at every injected position error from 5.6 m to
5.6 km, so the layer sees every glitch. What it cannot do is escalate: the step
detector decays at 0.85 per tick, a step floors the residual for 26 to 40 ticks
whatever its size, and the trust recursion integrates over a far longer window.
**There is no step magnitude at which this system alarms.** A ramp of the same
total error does alarm. Escalation is duration-limited, not magnitude-limited.

**Part 3 produces the number the paper should have been reporting all along.**
On the attribution channel, `T_FH` is **23.97 of 25 s** under denial. On the
reported status it is **1.04 s**, because the freshness disjunct rescues the
failsafe without consulting the diagnosis. Both belong in the paper and either
alone misleads.

**A third scope correction came out of the satellite ladder**, which we did not
anticipate: the gate does not close at **any** satellite count down to zero.
WP-C6's fourth arm was labelled `degraded` and attributed to partial
constellation loss. That attribution was wrong; the closure came entirely from
byte loss. The arm is relabelled `link loss`.

---

## 2. Part 1.2 — the blocking check

`research/wp_c7/variance_investigation.py`

Four tests, because "the numbers differ" is not evidence that the conditions
did.

| Test | Question | Result |
|---|---|---|
| A | Did the inputs reach the autopilot? | **Yes.** Wind speed reads back 0/2/4/6/8/10, wind direction 45/90/135/180/270/315, six distinct home positions from the first GPS fix |
| B | Did the outputs differ? | Yes: mean roll 0.181 to 0.220 rad, pitch, groundspeed, throttle and track span all differ across specs |
| C | Did **wind** reach the physics? | **No.** Hold-position tilt is 0.159°, 0.160°, 0.159° at 0, 6, 12 m/s |
| D | Is B bigger than repeating one spec? | **Yes, by 216x.** Within-spec sd 5.9e-05 rad over three repeats; between-spec sd 0.0127 rad |

**Why test C exists.** A parameter readback proves the autopilot stored a
value. It does not prove the simulator uses it. The square-pattern flights of
test B tilt 0.18 to 0.22 rad regardless of wind and in an order that does not
track wind speed, because manoeuvring tilt swamps wind tilt. Commanding zero
ground velocity removes the manoeuvre, and then the only reason to tilt is
wind. There was none.

**Why test D exists.** Test B says the specs differ. It cannot say whether that
difference is a condition or jitter until you know what repeating one spec
produces. Flying spec 0 three times answers it: the between-spec spread is two
orders of magnitude larger.

**Gate response is deterministic.** First closure occurs 0.44 s after injection
in all six denial flights. That is why the between-flight variance is zero: the
injection dominates the gate regardless of where the vehicle is. It is a
property of the gate response, not an artifact of the experiment.

**Marginal value of more flights: none.** Bootstrap interval width is zero at
every n from 2 to 12, because there is no between-flight variance to resample.
Flying more of the same condition buys nothing, which is why this work package
spent its flights on a satellite ladder and onset variation instead.

---

## 3. Part 1.1 — the expanded campaign

`research/wp_c7/campaign_expanded.py`, 17 flights.

### 3.1 The satellite ladder never flips

| Commanded satellites | Reported | fix_type distribution | q_gvalid |
|---|---|---|---|
| 9 | 9.00 | 578 x fix 3 | 0.000 |
| 6 | 6.01 | 578 x fix 3 | 0.000 |
| 4 | 4.02 | 578 x fix 3 | 0.000 |
| 2 | 2.03 | 578 x fix 3 | 0.000 |
| **0** | **0.03** | **578 x fix 3** | **0.000** |

A receiver reporting zero satellites still asserts a valid 3D fix in this
simulator, and the gate believes it.

**Two readings, both of which belong in the record.**

The first is a fidelity limit. A real receiver does not assert a 3D fix on zero
satellites. This simulator's fix flag is not coupled to its own satellite
count, so the ladder does not tell us where a real receiver would flip. The
"operational definition of which faults are self-occluding" that the brief
asked for does not exist on this generator.

The second is the paper's point demonstrated end to end, and it is better
evidence than the ladder I set out to build. The injected fault was **fully
present in the telemetry**, in a field the receiver reported correctly at every
rung, and the layer never saw it, because `satellites_used` is not among the
fields the ingestion path reads. The diagnosis reported `nominal` throughout.
Nothing was unobservable. The observation was not routed.

**And it corrects WP-C6.** The fourth arm combined `SIM_GPS_NUMSATS=4` with
`SIM_GPS_BYTELOSS=20` and I attributed its closure to partial constellation
loss. The satellite count contributes nothing. The closure came from the byte
loss, a receiver link failure. The number is unchanged; the attribution was
wrong and the arm is relabelled.

### 3.2 Onset and duration replicate cleanly

| Injection phase | q_gvalid | Closure delay |
|---|---|---|
| climb (t=30) | 0.984 | 0.44 s |
| early cruise (t=45) | 0.984 | 0.44 s |
| mid cruise (t=60) | 0.984 | 0.44 s |
| late cruise (t=75) | 0.982 | 0.44 s |

| Denial duration | q_gvalid over the 25 s window | Reopen delay |
|---|---|---|
| 2 s | 0.088 | 0.64 s |
| 5 s | 0.208 | 0.64 s |
| 15 s | 0.609 | 0.64 s |

Gate occupancy is the denial duration divided by the window, to three
decimals, with 0.44 s closure latency and 0.64 s reopen latency at every
duration. The response does not depend on mission phase and tracks duration
exactly.

---

## 4. Part 2 — the glitch non-alarm, tested

`research/wp_c7/glitch_mechanism.py`, 10 flights.

### 4.1 The brief's hypothesis, answered in two halves

> the EKF absorbed the step into its state, the innovation stayed small, and a
> residual-based monitor saw nothing

| Half | Answer | Evidence |
|---|---|---|
| Did the EKF absorb the step? | **YES** | Fused position follows the glitched GNSS position by a fraction of 0.79 to 0.998 across the sweep |
| Did the innovation stay small? | **NO** | Reported horizontal position variance rises from ~0.006 to 1.15 / 4.50 / 11.14 / 44.54 / 222.64 / 1113.19, scaling with glitch size |

**And it would not have mattered either way.** This layer reads `GPS_RAW_INT`
and never consumes `GLOBAL_POSITION_INT` (`plugins.py:151-176`, with a source
comment saying the fused output hides exactly what an integrity monitor exists
to detect). The EKF's treatment of the step is not in the layer's evidence
path. The hypothesis could have been true in both halves and still not
explained the non-alarm.

### 4.2 What is actually happening

| Position error | Min GPS trust | Min physics residual | Ticks at floor | Alarm |
|---|---|---|---|---|
| baseline (1.5 m) | 0.9831 | 1.0000 | 0 | no |
| 5.6 m | 0.9237 | **0.0000** | 26 | no |
| 22.3 m | 0.9089 | 0.0000 | 32 | no |
| 55.7 m | 0.9063 | 0.0000 | 33 | no |
| 222.6 m | 0.9061 | 0.0000 | 33 | no |
| 1113.2 m | 0.9061 | 0.0000 | 33 | no |
| **5566.0 m** | 0.8881 | 0.0000 | 40 | **no** |

The detector fires at every magnitude including the smallest. Trust saturates
near 0.906 from 55 m upward against a 0.75 threshold. **There is no step
magnitude at which this system alarms**, tested to 5.6 km.

The mechanism: the step detector's output saturates at zero, and its 0.85
per-tick decay bounds how long the floor lasts to 26 to 40 ticks regardless of
size. The trust recursion integrates over a window long enough that a burst
that short cannot cross the threshold. **Detection happened; escalation did
not.** Per the brief, this belongs in the abstract, and it is there.

### 4.3 Ramp versus step inverts the expected ordering

| Injection | Min trust | Ticks at floor | Alarm |
|---|---|---|---|
| step, 222.6 m | 0.9061 | 33 | no |
| ramp over 5 s, 222.6 m | 0.7181 | 104 | **yes** |
| ramp over 20 s | 0.7169 | 168 | **yes** |
| ramp over 60 s | 0.7227 | 139 | **yes** |

The brief expected a ramp to be *more* invisible than a step. It is the
opposite here: a slow error holds the residual above threshold long enough to
move the recursion. **And it is the opposite of the EKF's behaviour** on the
same runs: the 20 s and 60 s ramps are absorbed completely (fraction 1.0) with
EKF variance staying near baseline, so they are close to invisible to the EKF
and clearly visible to the CSIA layer, while the step is the reverse. Each
monitor is blind to what the other sees. That is an argument for keeping both,
and it is not one we set out to make.

---

## 5. Part 3 — false-healthy exposure

`research/wp_c7/false_healthy.py`, 15 flights.

### 5.1 The four states, from source

The implementation has no `NOT_APPLICABLE` state. What it emits instead is the
finding.

| State | Condition | Emitted as |
|---|---|---|
| `HEALTHY` | failsafe NORMAL and top cause `nominal` | itself |
| `FAULT` | failsafe above NORMAL, or top cause not `nominal` | itself |
| `UNKNOWN` | no evidence, Beta belief held (`engine.py:140,146`) | **`HEALTHY`** |
| `NOT_APPLICABLE` | hypothesis support entirely silenced (`bayes.py`, `if gate <= 1e-9: continue`) | **`HEALTHY`** |

Two lines of source produce the last two rows. In the diagnosis a gated feature
is skipped outright, so when a hypothesis's whole support is gated its
likelihood ties with `nominal` over the surviving features and the prior
decides. In the trust recursion a node that loses every evidence source has its
belief **held** rather than driven down, which is the right choice given the
available vocabulary. A held belief and a confirmed one are the same number at
the output.

### 5.2 Measured, both channels

| Arm | T_FH attribution | T_FH status | T_FH abstaining | Silenced ticks | Onset dep → abs |
|---|---|---|---|---|---|
| `nominal` | 0.00 | 0.00 | 0.00 | 0 / 624 | — |
| `denial` | **23.97** | 1.04 | **0.00** | 614 / 624 | 1.48 → **0.44** |
| `glitch` | 0.00 | 0.00 | 0.00 | 0 / 624 | 1.52 |
| `link loss` | **24.48** | 1.04 | **0.00** | 612 / 624 | 1.56 → **0.52** |
| `denial, recovered` | 14.68 | 1.04 | 0.00 | 382 / 624 | 1.48 → 0.44 |

**Two numbers, and reporting either alone misleads.** The attribution channel
spends 96% of the window asserting `nominal` while its evidence is silenced.
The reported status spends 1.04 s, because the freshness disjunct drives the
failsafe out of NORMAL at 1.48 s without consulting the diagnosis. The
escalation path holds. The naming path does not. My first version of this
measurement folded the failsafe in and reported only 1.04 s, which would have
understated the failure this paper is about by a factor of 23.

Gate transitions in the window: 0 in the quiet arms, so no chatter contributes.
The freshness disjunct accounts for every CAUTION in the fault arms.

### 5.3 The abstaining baseline

Research code only. A counterfactual policy emitting `NOT_APPLICABLE` when a
hypothesis's entire support is silenced, scored on the same tick stream so the
comparison is paired.

- **T_FH falls to 0.00 s in every arm.** By construction, and the construction
  is the point: the state exists to be reported.
- **Onset improves by about 1 s**, 1.48 → 0.44 s under denial. The abstention
  is available the moment the gate closes, without waiting for the freshness
  watchdog.
- **Nuisance cost is zero.** In `nominal` and `glitch`, zero silenced ticks and
  zero abstentions. Identical behaviour to the deployed system.
- **Recovery costs nothing.** Both policies return to health 5.71 s after
  denial ends, which is the failsafe's own de-escalation dwell.

One-sided on this evidence, and reported as a measured counterfactual rather
than a recommendation to ship. Three flights per arm against one simulator is
not the basis for a production change, and a policy that abstains whenever any
support is silenced will abstain more on a platform with more gates.

---

## 6. Part 4 — manuscript

Reframed around false-healthy exposure. Changes:

1. **Abstract rewritten.** Leads with T_FH. Carries both scope corrections
   explicitly: self-occlusion is specific to fix-loss faults, and no step
   magnitude alarms up to 5.6 km.
2. **The observability claim is retracted and replaced affirmatively.**
   "Receiver observables detect GNSS denial well; the failure we measure is one
   of evidence routing and applicability semantics, not of detectability." The
   receiver observables are named. **This claim currently carries no citation**
   (section 7 below).
3. **`U_h` relativised to `(M, S, R)`** and the unrestricted irreparability
   claim withdrawn in the text, not just softened.
4. **Containment stated as a linear-time subset test** that runs in the test
   suite on every commit, affirmatively, so the objection's "difficult to
   compute" clause is answered rather than left open.
5. **The design-rule section now leads with the knife edge**: one ungated
   relation suffices, absorption 1.000 to 0.000 with exactly one feature
   outside `C_h` at every density.
6. **Both corrections carried visibly**: the column-dependence retraction and
   the `temp_gps` formal-escape-but-zero-information finding, in the sections
   and in the claim table.
7. New sections for the variance check, the satellite ladder, the glitch
   mechanism and false-healthy exposure. Three new figures.

**Hard rules, checked mechanically:** 0 em dashes, 0 en dashes, 0 "novel", 0
theorem labels, braces 617/617, environments matched, 9 of 9 cite keys resolve,
9 of 9 figures present. The single bare "theorem" is inside the referee
objection quoted verbatim, and the checker prints it for review rather than
banning the string.

---

## 7. Part 5 — bibliography, and a standing blocker

**No new BibTeX arrived in this brief.** The 14 `VERIFY` placeholders from
WP-C6 remain exactly as they were. Nothing was upgraded; nothing was invented.

**Takai 2021 and Kang 2024 stay uncited**, per the brief's explicit
instruction. This creates one loose end I want on the record rather than
buried: Part 4 of the brief asks the manuscript to "state affirmatively that
receiver observables do detect denial and cite the survey", and Part 5 says
Kang 2024 stays uncited until a title arrives. Those two instructions conflict.
**I followed Part 5**, because it is the more specific instruction and because
citing a work whose content I cannot check would assert something unverified.
The affirmative claim is in the manuscript and currently has no citation
attached. It needs one before submission.

**The manuscript has never been compiled.** No LaTeX toolchain exists in this
environment: `pdflatex`, `xelatex`, `latexmk` and `tectonic` are all absent.
Every check reported here is structural. **This is now a standing blocker on
submission** and it has been one since WP-C5.

---

## 8. Part 6 — which outcome would have weakened the paper

### Part 1.2, the variance check

| Outcome | Effect |
|---|---|
| **Wind and home both cosmetic** | Fatal to the campaign. 24 flights would be one condition replicated 24 times, and every number in the SITL section would need withdrawing. This is why it ran first. |
| **Wind cosmetic, home real** (what happened) | Survivable and still a correction. The campaign's variation is half what it was described as. |
| **Between-spec spread within jitter** | Same as the first row. Test D exists because test B alone cannot distinguish them. |
| **Gate response varying across flights** | Would have been *better* for the intervals and worse for the story: a varying gate response means the bootstrap has something to resample and the WP-C6 degenerate interval was a fluke rather than a property. |

### Part 2, the glitch mechanism

| Outcome | Effect |
|---|---|
| **Detector never fires** | Would have made the layer blind in the position domain and merged this failure into the self-occlusion story, which would be tidier and wrong. |
| **A step magnitude does alarm** | Would have made the non-alarm a sensitivity threshold rather than a structural ceiling, and downgraded it from an abstract-level finding to a tuning note. Strictly better for the system, worse for the paper. |
| **Ramp invisible, step visible** | The brief's expectation. Would have supported an estimator-tracking story. The opposite happened and the paper has to explain it. |
| **EKF innovation staying small** | Would have made the brief's hypothesis correct and my alternative unnecessary. Half of it was correct. |

### Part 3, false-healthy exposure

| Outcome | Effect |
|---|---|
| **T_FH near zero on the attribution channel** | Would have refuted the paper's central claim on a second generator. The 40 s episode would look like a one-off. |
| **T_FH near zero on the status channel** (what happened, 1.04 s) | Cuts both ways and is reported as such. It means the vehicle is well protected and the paper's exposure claim must be scoped to attribution. Reporting only the 23.97 s would have been the flattering half. |
| **Nuisance alerts under abstention** | Would have made the fix expensive and the comparison genuinely two-sided. It came back at zero, which is the outcome that favours us, so it is reported with its limits: three flights, one simulator, one gate set. |
| **Recovery penalty under abstention** | Would have been a real operational cost. There is none; both policies wait the same 5.71 s dwell. |

### The satellite ladder

| Outcome | Effect |
|---|---|
| **A clean flip point** | What the brief wanted and what I expected. Would have given a crisp operational boundary. |
| **No flip at all** (what happened) | Removes the boundary claim entirely and exposes a simulator fidelity limit. It also produced better evidence for the routing argument than a flip point would have. |
| **The gate closing at 9 satellites** | Would have meant the `nominal` arm was near the edge and the whole campaign's baseline was fragile. |

---

## 9. What the campaigns cost us

A programme that reports what its own best experiments took away is more
credible than one that reports only what they gained. The SITL work has now
removed the following, all of which we had asserted:

1. **"Self-occlusion applies to GNSS faults."** Corrected to fix-loss faults
   only. The `glitch` arm closes the gate zero times.
2. **"The fourth arm measured partial constellation loss."** Corrected to
   receiver link loss. The satellite count contributes nothing.
3. **"The gate closes when the constellation degrades."** Refuted. It does not
   close at any satellite count down to zero on this generator.
4. **"The campaign varied home site and wind."** Corrected. Wind applies no
   force in this build.
5. **"The layer reports healthy throughout the fault window."** Split. True on
   the attribution channel at 96% of the window, false on the reported status,
   which the freshness disjunct rescues in 1.04 s.
6. **"The glitch non-alarm has an untested cause."** Now tested, and it is a
   second defect rather than an instance of the first.
7. **"Unrestricted irreparability."** Withdrawn permanently; `U_h` is definable
   only relative to `(M, S, R)`.
8. **"Containment might be hard to establish."** Withdrawn. It is a linear-time
   subset test and we say so.

Earlier packages had already removed fifteen claims. This one removes eight
more, six of them from the experiment we were most pleased with.

---

## 10. What I got wrong, and how I found out

1. **My variance verdict read a crashed probe as a finding.** The first hover
   probe returned `None` for tilt, readback and groundspeed in all three runs,
   and my verdict logic converted that into `WIND_IS_COSMETIC` — the right
   answer, reached with no evidence. The cause was a missing `import math`
   caught in the `except` and stored as `rec["error"]`, which my summary print
   did not surface. **Caught because three identical `None`s is not a
   measurement.** Fixed twice over: the import, and a `probe_produced_usable_data`
   gate that now raises `WIND_PROBE_FAILED` instead of a substantive verdict.
   This is the most serious error in the package: it would have put a real
   conclusion in the paper on the strength of a NameError.
2. **My glitch verdict was decided by the wrong runs.** `alarming` included the
   ramp flights, so a ramp alarm flipped the verdict to "escalated at some
   magnitude", the exact opposite of what the step sweep shows. Caught on
   reading the printed verdict against the printed table. Now the verdict
   branches on step runs only and the ramp is reported separately.
3. **I measured false-healthy exposure on the wrong channel first.** Folding
   the failsafe level into the health status gave 1.04 s and I nearly reported
   that as *the* number. It understates the attribution failure by a factor of
   23. Both are now measured and both are reported.
4. **I attributed the WP-C6 `degraded` arm to constellation loss** without
   testing the satellite axis separately. The ladder shows the satellite count
   does nothing. Two injections in one arm, and I attributed the effect to the
   wrong one.
5. **My first satellite ladder had no flip point and my code reported
   `flip: None` with no interpretation**, which reads as a missing result
   rather than a finding. Now the artifact carries both readings explicitly.

---

## 11. What I could not determine

- **Where a real receiver's fix flag flips against satellite count.** This
  simulator's does not flip at all. The operational boundary the brief asked
  for does not exist on this generator.
- **Whether any of this reproduces on a current ArduPilot or on PX4.** The only
  reachable binary is ArduCopter 3.3 from 2015.
- **Whether the abstaining policy's zero nuisance cost survives a platform with
  more gates.** Three flights per arm, one gate set.
- **Whether the manuscript compiles.**
- **Titles for four supplied citations**, and venue and year for the
  φ-diagnosability entry.

---

## 12. Open, with owners

| Item | Owner | Blocking |
|---|---|---|
| **Verify every bib entry** | You | submission blocker; 14 `VERIFY` strings |
| **A citation for the receiver-observables claim** | You / research agent | the claim is in the manuscript uncited |
| **Compile the manuscript** | You | standing blocker since WP-C5; no LaTeX here |
| Re-run every SITL result on a current ArduPilot and on PX4 | WP-E2 | needs a host with GitHub access |
| `q_gvalid` on real annotated telemetry | WP-E2 | corpus + network; spec is ready |
| Plumb `satellites_used`, `noise_per_ms`, DOP | Engineering | nothing. The ladder is a live demonstration of the cost |
| Decide whether `NOT_APPLICABLE` becomes a production state | You | measured; not recommended on this evidence alone |
| Fix duration-limited escalation (the glitch defect) | Engineering | separate from self-occlusion, no fix attempted |
| `failsafe.py:106` fail-open on `att` | Engineering | unanalysed since WP1 |
| `engine.py:104` stale "12 edges" comment | Trivial | nothing |

---

## 13. Reproducing

```sh
curl -sSLO https://dronekit-assets.s3.amazonaws.com/sitl/copter/sitl-linux-copter-3.3.tar.gz
mkdir -p sitl && tar xf sitl-linux-copter-3.3.tar.gz -C sitl
pip install -e '.[mavlink]'
export CSIA_SITL_BINARY=$PWD/sitl/apm CSIA_SITL_EEPROM=$PWD/sitl/default_eeprom.bin
PYTHONPATH=. python research/wp_c7/variance_investigation.py   # 15 flights, run first
PYTHONPATH=. python research/wp_c7/glitch_mechanism.py         # 10 flights
PYTHONPATH=. python research/wp_c7/campaign_expanded.py        # 17 flights
PYTHONPATH=. python research/wp_c7/false_healthy.py            # 15 flights
PYTHONPATH=. python research/wp_c7/figures.py
python papers/csia_systems/check.py
```

`glitch_mechanism.py` and `campaign_expanded.py` accept `--reanalyse` to
rebuild their reports from flights already on disk. Without the binary every
script emits `SITL_UNAVAILABLE` and substitutes nothing.
