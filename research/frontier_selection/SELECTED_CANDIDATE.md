# SELECTED CANDIDATE

**Candidate B — Runtime collapse of effective evidence independence at an
assurance monitor's input.**

Weighted frontier score **5.900**, the highest of twelve. Selected under item
32 on `novelty survival × scientific depth × falsifiability × tractability`,
not on excitement.

---

## 1. WHY THIS ONE

Four reasons, in order of weight.

**It is the only candidate whose kill test does not require a model, a label,
a threshold, or a fitted parameter.** The primary endpoint is computed from
source-code provenance and observed message arrival. Nothing is tuned. Given
this repository's history — three consecutive packages in which the interesting
effect either failed to reach an action or turned out to be published — a
candidate that cannot be rescued by tuning is worth more than a candidate with
a higher ceiling.

**Its null can win, cleanly and quickly.** If κ equals its nominal value
everywhere on real data, the phenomenon does not exist on this stack and the
direction closes in days. If every κ drop is already named in a design-time
common-cause group, the baseline wins. Both outcomes are cheap and decisive.

**It sits exactly on the boundary the literature map identified.** Sections 1
and 5 of `LITERATURE_FRONTIER_MAP.md` show three mature layers (control,
specification, argument) sitting on one thin one (evidence), with every layer
above taking the evidence layer as given in language the papers state and never
revisit. B is the only candidate aimed at that layer.

**CSIA is unusually well positioned to test it, in the specific sense item 32
intends.** Not "CSIA could run it" — most of the twelve could. CSIA has the
*instrument*: three independent decode paths over the same wire data, the
ArduPilot and PX4 producer sources on disk, a real 9.6 MB PX4 ULog, a
deterministic stage-indexed replay harness, and a frozen core that fixes the
downstream semantics so that a change in κ cannot be confused with a change in
the monitor.

---

## 2. WHY NOT THE OTHER TWO

**A** is ranked second and may already be closed by a single 2025 TOSEM paper
(S016). Selecting a candidate whose fate turns on one unread paper would be
choosing to find out later rather than now.

**J** has `FORMAL_DEPTH = 4` and a primary endpoint that depends on human
classification. Its best outcome is a good empirical software-engineering
paper, which is not what this stage is selecting for.

---

## 3. PRE-MORTEM (item 33)

*"This candidate will probably fail if…"* — seven reasons, written before the
Stage-0 design, not after.

**1. Someone already computes it under a certification name.** ARP4761
common-mode analysis, zonal safety analysis and particular-risks analysis are
established aerospace *processes* for exactly this question. If the runtime
version exists as an industrial practice rather than a research result, B is
"CCA with a clock" and dies. **This is the most likely single cause of death**,
and it is the one this environment could not check, because the standards are
paywalled.

**2. S063 already does it.** *Testing conditional independence to determine
shared information in a data/signal fusion process* detects shared information
between fusion inputs. If its full text attaches that verdict to a monitor's
decision, the gap closes.

**3. κ turns out to be static.** If the provenance graph never changes shape
in flight, there is no runtime phenomenon — only a design-time fact that a
diagram would have shown. The whole "runtime" framing collapses to a drawing.

**4. κ turns out to be trivially 1 everywhere.** If every channel routes
through the EKF, the answer is "everything shares the estimator", which is
obvious to any engineer on the project and worth nothing as a finding.

**5. The ACTION-level null wins again.** Three consecutive CSIA packages found
that the effect under study never changed a failsafe action. There is no
reason to assume this one is different, and the design must be able to report
"κ drops and nothing downstream cares" as the result.

**6. Provenance cannot be established soundly from source.** Configuration-
dependent wiring, runtime parameter selection and conditional compilation may
make a sound static provenance graph impossible, in which case the primary
endpoint is unmeasurable and the honest output is a negative methods result.

**7. Reviewer J is right.** Twelfth idea, eleven abandoned. Even a correct
result arrives with a credibility discount that only a full-text prior-art
audit can repay, and this stage could not perform one.

**Decision after the pre-mortem: still worth testing.** Reasons 1 and 2 are
answered by *reading*, not by experiment, and the Stage-0 prompt puts that
reading first as a hard gate. Reasons 3, 4 and 5 are answered by the audit
itself, in days, and each of them is a publishable negative result about a real
autopilot stack rather than a wasted month. Reason 6 is a genuine risk that the
design mitigates by requiring every edge to be pinned to a verified `file:line`
and by voiding the run if the audit is not reproducible twice. Reason 7 is not
answerable by this stage and is recorded rather than argued.

---

## 4. CURRENT-STACK FEASIBILITY AUDIT (item 16)

Nothing below is modified. This is an estimate only.

| asset | supports candidate B? | how |
|---|---|---|
| Frozen CSIA runtime (`csia/trust_engine`, `csia/diagnosis`, `csia/runtime/online.py`, `csia/runtime/failsafe.py`) | **yes, unmodified** | fixes downstream semantics so a κ change cannot be confused with a monitor change; `tests/test_v1_frozen.py` enforces this |
| ArduPilot 4.8.0-dev source at `/home/user/ardupilot/ardupilot` | **yes, essential** | producer-side provenance edges; already used and cited at `file:line` in three prior packages |
| PX4 source at `/home/user/px4` | **yes, essential** | second producer, needed for cross-platform replication |
| Real PX4 ULog (9.6 MB, 345 GNSS samples, 216 battery samples) | **yes** | real-data evaluation of κ, not simulated |
| Deterministic replay (`research/evidence_semantics/probe.py`) | **yes** | stage-indexed tick grid already exists; reused read-only |
| SITL | **yes** | single-upstream-fault injection cell |
| Existing fault injection | **partially** | existing injections act at the channel level; B needs an *upstream* injection, which is new work in Stage 1, not Stage 0 |
| Raw MAVLink captures | **yes** | wire-level provenance ground truth |
| Existing log corpus | **yes** | multiple flights for κ variability |
| Counterexample / replay infrastructure | **yes** | reused |
| Frozen diagnosis core | **yes, as a fixed reference** | must not be touched (item 36) |
| HIL-ready architecture | **yes** | bench path defined; no hardware present in this environment |
| MAVLink + uORB field universe (106 fields, `research/ai_contract_synthesis/`) | **yes** | the vertex set of the provenance graph is already enumerated |

**Not available:** any physical hardware (`pyserial` sees only `/dev/ttyS0`);
any scholarly full text (`SEARCH_PROTOCOL.md` §0).

---

## 5. DATA REQUIREMENTS (item 19)

| question | answer |
|---|---|
| Data needed | producer source (ArduPilot, PX4); consumer source (3 CSIA decode paths); ≥1 real PX4 ULog; ≥1 real MAVLink capture; SITL runs for the injection cell |
| Data already available | all of the above except the upstream-fault SITL runs |
| Data missing | SITL runs with an *upstream* (pre-decoder, pre-estimator) fault; any bench-HIL capture |
| Labels required? | **none.** κ is structural; the injection cell's ground truth is the injection itself |
| Number of scenarios | Stage 0: 1 provenance audit over the full channel set + 1 paired injection cell (fault vs. nominal). Not a campaign |
| Deterministic or statistical? | **deterministic.** κ is a graph quantity; the injection is paired and replayed |
| Are iid assumptions valid? | **not applicable, and deliberately so** — see item 20 below |

---

## 6. STATISTICAL TEST (item 20)

Item 20 ends with: *"Do not add statistics where deterministic falsification is
stronger."* It is stronger here, and no inferential statistics are proposed for
Stage 0.

- **Unit of analysis:** the (verdict, tick) pair. Reported as counts and
  fractions, not as an estimate of a population parameter.
- **Sample size rationale:** none needed. A single (verdict, tick) pair with
  κ < nominal falsifies the null H0a; a full pass with κ = nominal everywhere
  falsifies H1. Neither is a sampling question.
- **Pairing:** the injection cell is paired by construction — identical seed,
  identical scenario, identical tick grid, fault on/off.
- **Censoring:** ticks before the failsafe arm time (10.0 s) are excluded from
  the action-level secondary endpoint, as in prior packages, and the exclusion
  is declared in advance.
- **Multiple comparisons:** κ is computed for every monitored verdict, so the
  audit is a multiple-quantity report. Because the endpoint is deterministic
  and not a hypothesis test, no correction applies — but **every** verdict's κ
  must be reported, not only the ones that dropped. Selective reporting is the
  live risk here, and the design forbids it.
- **Effect size / confidence interval:** not applicable to a deterministic
  graph quantity. Reported instead: the exact κ per verdict, the exact tick
  ranges where it fell, and the exact cut vertex responsible.

If Stage 1 later compares detection performance across configurations, that is
where statistics enter. Not here.

---

## 7. ADVERSARIAL NULL (item 21)

Three nulls, any one of which kills the direction. The design must let them
win.

**H0a — Structural null.** For every monitored verdict *v* and every tick *t*,
κ_t(v) equals the nominal independence count the design assumed. *There is no
runtime collapse.*

**H0b — Baseline null.** Every (v, t) with κ_t(v) < nominal falls inside a
dependency that a competent design-time common-cause analysis of this stack
would already have listed. *The phenomenon is real and already handled.*

**H0c — Consequence null.** κ drops occur and are not in the design-time list,
but no assurance decision differs between the κ-aware and κ-blind readings of
the same trace. *The phenomenon is real, novel, and inert* — which is exactly
what the three previous CSIA packages found for their own phenomena, and is
therefore the most probable outcome.

H0c is stated third because it is the most likely, not the least. If it wins,
the honest report is "measured, real, no consequence", and that is the result.

---

## 8. DISSERTATION-QUALITY GATE (item 27)

Of the eight listed outputs, candidate B plausibly produces four:

| | output | plausible? |
|---|---|---|
| A | new problem formulation | **yes** — effective independence of a verdict, computed at runtime |
| B | nontrivial formal result | **no** — the proposition is a Menger corollary and is labelled as one |
| C | new algorithm / system architecture | **yes** — sound provenance-graph construction from producer and consumer source, plus the per-tick κ computation |
| D | controlled causal evidence | **yes** — the paired single-upstream-fault injection |
| E | cross-platform replication | **yes, plausibly** — ArduPilot and PX4 are both on disk and both were used in prior packages |
| F | HIL / physical validation | **yes** — bench HIL at $100–$500 |
| G | reusable benchmark / dataset | **partially** — the provenance graph itself is reusable; a benchmark would need more flights |
| H | operational design principle | **yes** — "do not credit agreement you cannot trace to distinct sources" |

Item 27's bar is three of eight. B clears it on A, C, D, F and H. It does **not**
clear B (formal result), and this package does not pretend otherwise.

**Ceiling, stated honestly: one strong dissertation chapter and one systems
paper — not the dissertation core.** A dissertation core would need the formal
result that this candidate does not have.

---

## 9. WHAT MUST BE TRUE BEFORE ANY CODE IS WRITTEN

Non-negotiable, and enforced as §1 of `SELECTED_CANDIDATE_STAGE0_PROMPT.md`:

1. Full text of **S063**, **S060**, **S062** and **S041** obtained and read.
2. Full text or authoritative summary of **ARP4761 common-mode analysis**
   obtained, and the question answered in writing: *is runtime κ just CCA with
   a clock?*
3. Two further prior-art searches run — data-provenance theory (why/where/how
   provenance) and fault-tree minimal cut sets — because κ may already be one
   of those objects.
4. If any of the above already computes a runtime effective-independence count
   for a monitor's verdict: **STOP, record the kill, do not adjust the
   candidate to survive.**
