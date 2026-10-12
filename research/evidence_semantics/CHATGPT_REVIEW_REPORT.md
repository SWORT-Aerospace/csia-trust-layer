# End-to-end evidence-semantic equivalence verification — Stage 0 review report

Base: commit `9071766`. Prior-art red team, formalization, multi-path
feasibility. No paper, no large campaign, no change to CSIA production
behaviour.

Written for hostile review. The instruction that governed the work was:
*do not prove the checker is new; try to show existing verification and
conformance techniques already subsume it, and keep a contribution only if
something specific, useful and defensible survives.* That is what was
attempted, and the reduction largely succeeded.

---

## 1. Executive verdict

**`IMPLEMENTATION_DEFECTS_ONLY`.**

The research question — *can an assurance pipeline be automatically verified
for end-to-end preservation of evidence semantics?* — is answerable **yes**,
cheaply, and the answer is not worth a dissertation chapter. Every component
of the method is established prior art, and the four conditions item 26 lists
as kill conditions are each met by existing work. What the exercise produced
is a set of concrete, reproducible, source-localised defects in this codebase,
and a 500-line checker that finds them in three minutes.

Three defects, three families, three different first-collapse sites:

| family | witness | first collapse | site |
|---|---|---|---|
| gnss | `I` (1 message) | `T5_core_bridge` | `base.py:306-337` |
| battery | `X` (1 message) | `T5_core_bridge` | `base.py:306-337` |
| mag | `Z` (1 message) | **`T3_ingest`** | `base.py:140-177` |

And one number that stands on its own: **three committed decoders turn one
raw condition into three different battery currents — 5.00 A, 0.00 A and
−1.00 A — feeding the same frozen core.**

The strongest downstream consequence measured anywhere is a **failsafe
latency of 0.12–0.32 s**. The failsafe never issues a different action, on any
word, in any family. That ceiling is stated here rather than at the bottom.

## 2. Closest prior art

Four works, any one of which would be cited against a novelty claim.

1. **Codd's A-marks / I-marks (1979)** — the state model. Two semantically
   distinct kinds of absence, and the consequences of a system merging them.
   The GNSS `I ≡ N` collapse is that mistake in a different domain.
2. **DES diagnosability under observation masks** (Sampath et al. 1995;
   abstraction-based diagnosis, Schmidt 2009) — the formal result. Coarsening
   an observation destroys diagnosability; conditions under which abstraction
   preserves it are published.
3. **ParDiff, OOPSLA 2024** — the method. Static differential analysis across
   multiple protocol-parser implementations, lifting each to a symbolic FSA
   specifically to find semantic discrepancies. This package does the same
   comparison dynamically and less efficiently.
4. **AUTOSAR E2E protection / ISO 26262** — the property. End-to-end
   preservation of a status through a communication chain, with a receiver
   state machine, standardised and shipped for two decades.

Plus a fifth that is closer than any of them and is **internal**:
`docs/simulation/CHANNEL_SEMANTICS.yaml` already states, per channel, the
exact distinctions this package's contracts encode — in prose, unchecked.

## 3. What is unquestionably known

* Trace equivalence, bisimulation, refinement, model checking, symbolic
  execution, shortest-counterexample generation, differential testing.
* Value + status representations and their propagation rules: ARINC 429 SSM,
  SEVA, NAMUR NE 107, OPC UA StatusCode. OPC UA even specifies the
  allowed-merge rule (worst-of severity across an array).
* That merging distinct absences loses information (Codd; SQL nulls;
  missing-indicator methods).
* That abstraction can destroy diagnosability (DES).
* That local guarantees compose (assume-guarantee refinement).
* The data-processing inequality.

None of these is challenged, extended or claimed here.

## 4. Exact candidate contribution that survives

Stated as narrowly as the evidence supports:

> **A stage-indexed differential probe that, for a declared pair of source
> states a sensor-ingest pipeline must keep apart, names the first
> transformation that stops keeping them apart, and measures how far
> downstream the loss is still observable.**

What is *not* in that sentence, deliberately: the search algorithm, the state
model, the contract format, the compositional argument, the equivalence
hierarchy. All four are prior art.

What the sentence buys, concretely: item 22's own illustrative example
attributes the GNSS collapse to the adapter. **Measured, the adapter is not
where it happens** — `_ingest_gps` pops the retained fix and records
`MissingReason.NO_3D_FIX`, and both survive to `T4`. The collapse is one stage
later at the core bridge. Reading the code would have produced the wrong fix.
Three families give first collapses at `T3`, `T5` and `T5`, so the
localisation discriminates rather than always naming one boundary.

That is worth an engineering tool and a workshop note. It is not worth a
dissertation chapter, and §21 says so at length.

## 5. Canonical semantic model

`CANONICAL_STATE_MODEL.md`. `E = (x, q)`; six quality states, each with a
named producer in this repository:

`V` observed-valid · `I` observed-invalid · `N` not-observed · `S` stale ·
`X` sentinel · `R` retained-after-disavowal.

Plus a value-provenance coordinate: `REAL`, `RETAINED`
(`ardupilot.py:181`, no pop), `IMPUTED` (`plugins.py:158`, `plugins.py:194`).

`M = IMPUTED` was **kept** — it is measured, the `plugins_py` battery
vocabulary is `['M','V']`. `E = ESTIMATED` was **kept in the model and marked
NOT EXERCISED**: justified by `plugins.py:177` feeding EKF-fused
`GLOBAL_POSITION_INT` into the same `gps` slot as raw receiver output with no
marker, but no word in these alphabets reaches it. Nothing else was added; in
particular there is no `DEGRADED` and no confidence scalar, because no
committed code produces one.

`R` is the load-bearing member: it is a state the code can be **in** and
cannot **express**. The adapter holds `sentinel_counts()["battery.current"]
== 1` and serves `5.00 A` as usable at the same instant.

## 6. Equivalence hierarchy

`EQUIVALENCE_LEVELS.md`. VALUE · STATE · EVIDENCE · DIAGNOSIS · ASSURANCE,
each read at a named stage, each measured. The order is the pipeline's order,
not a lattice — none implies another.

Every cross-path projection is order-only or a duration from word onset, so
the two stamping conventions (tick time vs message time) cannot manufacture a
result; residual error is one tick, 0.040 s, against effects of 0.12–0.32 s.

Every number is accompanied by a **null control** `V^k` at the same length. A
level whose control already diverges is reported `CONFOUNDED_BY_CONTROL` and
contributes nothing. Control trust deltas: gnss 0.0001, battery 0.034, mag
0.025 for pairs involving `plugins.py`; **0.0** for `v1_1_adapter` vs
`ulog_source.py` on gnss and battery, which is why that pair carries the
clean results.

## 7. Formal preservation property

For raw states `r1, r2` and pipeline `T = T_n ∘ … ∘ T_1`:

```
if P(r1, r2):    T(r1) ≁_D T(r2)
```

`~_D` is not fixed to one relation. Each `forbidden_merges` clause names the
downstream consumer that needs the distinction, cited to a line in
`failsafe.py`, and the checker reports the **first level at which the two runs
become equivalent** rather than asserting a definition — so a reader who
disagrees about which level should count can re-read the same result at their
own level.

Item 9's warning is enforced structurally: a merge is a violation only if it
appears in `forbidden_merges` with a `needed_by` clause. `allowed_merges` are
declared and never reported — `N`/`S` is merged deliberately in all three
contracts.

## 8. GNSS reproduction

`GNSS_SEMANTIC_TRACE.md`. Shortest witness **`I`, one message**; exhaustive
over 120 words of length ≤ 4, so minimal by construction.

| stage | `"I"` | `"N"` | same? |
|---|---|---|---|
| `T1`–`T2` | `I@12 N@12.32` | `V@12 N@12.12` | no |
| `T3_ingest` | `I@12` | `V@12` | no |
| `T4_channel` | `I@12 N@13.04` | `V@12 S@12.84` | no |
| **`T5_core_bridge`** | **`-@12`** | **`-@12`** | **YES** |
| `T6`–`T9` | identical | identical | yes |

`downstream_consequence: NONE` — the collapse is total. Admissibility closes
at the same tick (12.32) on both; the failsafe escalates at the same tick with
the same actions.

Two consequences worth stating plainly. First, the flight log records
**"GPS data invalid"** (`failsafe.py:145-152`) for both inputs, including the
one where no GPS message arrived and the receiver never said anything about
validity. Second, `plugins_py` and `ulog_source_py` **PASS** this clause — the
path with the careful `MissingReason` handling is the one that loses the
distinction.

## 9. Battery reproduction

`BATTERY_SEMANTIC_TRACE.md`. Shortest witness **`X`, one message**; shortest
collapsing pair `V`/`X`, found after two words explored.

The numeric value **stays equal**: both `X` and `V` put `5.00 A` into the core.
This is item 6's example measured — `(5.00 A, OBSERVED_VALID)` and
`(5.00 A, RETAINED_AFTER_SENTINEL)` are VALUE-equivalent *and*
STATE-equivalent, so no level can separate them.

Responsible transformation: **first collapse at `T5_core_bridge`**, enabled by
the missing `pop` at `ardupilot.py:181`. `_channel_value` tests
`entry is None` first (`base.py:199`), so the recorded sentinel is never
consulted. Executed window: `5.00 A` served as usable for **0.5 s** after the
producer disowned it, and when it finally goes the reason is `STALE`, not
`SENTINEL`.

The second clause `X` vs `N` behaves differently — it survives to `T9` and is
classified `DIAGNOSIS_SCORE` — which is the evidence that the checker is not
simply returning FAIL everywhere.

## 10. Three-path equivalence result

Item 12's hard stop **cleared exactly**: 79/120, shortest `'I'`, re-executed
from the committed checker, with an independently written stage probe agreeing
on the one fact both instruments can see.

Contract results, 120 words per family, lengths 1–4:

| family | `v1_1_adapter` | `plugins_py` | `ulog_source_py` |
|---|---|---|---|
| gnss | **FAIL** (`I` unrepresentable; collapse `T5`) | PASS | PASS |
| battery | **FAIL** (`X` unrepresentable; collapse `T5`) | **FAIL** (`X` unrepresentable; collapse `T6`) | **FAIL** (`X` unrepresentable; collapse `T6`) |
| mag | **FAIL** (`X` unrepresentable; collapse **`T3`**) | **FAIL** (collapse `T5`) | **FAIL** (collapse `T9`) |

Emitted vocabularies at the core boundary:

| family | adapter | plugins | ulog |
|---|---|---|---|
| gnss | `['V']` | `['I','V']` | `['I','V']` |
| battery | `['V']` | `['M','V']` | `['V']` |
| mag | `['V']` | `['V']` | `['V']` |

**On word `X`, at `T5`: 5.00 A / 0.00 A / −1.00 A.** Same raw condition, same
frozen core.

## 11. Minimal counterexamples

`MINIMAL_COUNTEREXAMPLES.json`. Shortest collapsing pairs, by exhaustive
breadth-first search:

| family | path | pair | words explored |
|---|---|---|---|
| gnss | `v1_1_adapter` | **`I` / `N`** | 3 |
| gnss | `plugins_py`, `ulog_source_py` | `II` / `INI` | 29 |
| battery | `v1_1_adapter`, `ulog_source_py` | **`V` / `X`** | 2 |
| battery | `plugins_py` | `VNX` / `NVX` | 32 |
| mag | `v1_1_adapter`, `plugins_py` | **`Z` / `N`** | 3 |
| mag | `ulog_source_py` | `ZV` / `ZZ` | 8 |

Three length-1 collapses on the v1.1 adapter, one per family: a single message
each.

## 12. Proof of minimality

Exhaustive breadth-first over the finite alphabet in increasing length order,
so the first witness found is shortest by construction. Recorded per search:
alphabet, maximum length, words explored, distinct downstream signatures,
runtime. 120 words per family at lengths 1–4; nothing shorter than one symbol
exists.

**The bound is a real limit and is not disguised.** A defect requiring a
witness longer than 4 symbols would not be found. Every counterexample here
has length ≤ 3, so the bound never bound — which is not evidence that no
longer witness exists (`CLAIM_LEDGER.json` C24, status `CONJECTURE`).

## 13. First-collapse / causal blame

`CAUSAL_BLAME_TRACES.json`. A stage is the collapse site when its own trace is
identical **and** every later stage is identical — a stage that coincides
transiently and separates again has destroyed nothing. Traces keep the time
each token first appears, so a stage that says the same things half a second
later is not counted as identical.

Stages a path does not **have** are never named. `plugins_py` and
`ulog_source_py` have no `T3` or `T4`; the checker reports
`no_representation_stage: ["T3_ingest","T4_channel"]` and refuses to blame a
file those paths never execute.

The mag result is the one that shows the localisation earns its keep: it
collapses at `T3_ingest`, two stages earlier than the other families, because
`ardupilot.py:143` has **no `else` branch at all** — no `_put` and no
`_reject_sentinel`, so the adapter's state after an all-zero triple is
identical to its state after no message. GNSS and battery at least record
something before the bridge discards it.

## 14. Downstream consequence

`DOWNSTREAM_CONSEQUENCES.csv`. 189 attributable rows of 952; every row whose
level is confounded by the control is marked and excluded.

| family | consequence | attributable rows |
|---|---|---|
| gnss | `ASSURANCE_STATE` | 106 |
| gnss | `DIAGNOSIS_SCORE` | 29 |
| gnss | `STATE_ONLY` | 6 |
| gnss | `EVIDENCE_AVAILABILITY` | 2 |
| battery | `DIAGNOSIS_SCORE` | 45 |
| battery | `STATE_ONLY` | 1 |
| mag | — | 0 attributable |

**All 106 `ASSURANCE_STATE` rows are a latency and nothing else.** Identical
level history `NORMAL → CAUTION`, identical action set
(`SWITCH_NAV_INERTIAL`, `INHIBIT_GPS_MODES`), escalation later by **0.32 s**
(80 rows) or **0.12 s** (26 rows) on the v1.1 adapter. The action sets never
differ, on any word, in any family.

`CONTROL_FAILSAFE` is **not reached** and is not claimed. No battery or mag
word produces any failsafe difference at all: `power_fault` needs
`T["battery"] < 0.70` and battery trust does not fall that far in a 15 s run.
The mechanism by which a CRITICAL could be raised on a disowned current is
documented in the previous package but **was not observed here**.

## 15. Checker self-audit

`TOOL_SELF_AUDIT.json`. Four injected NON-SCORED fixtures, all four detected,
instrument restored exactly.

Two disciplines enforced mechanically, both from real prior failures:
`assert C.P is P` and `assert sys.modules["probe"] is P` (the Stage 2
self-audit once passed because it patched a different module object); and
detection defined in advance as "at least one published quantity moves", with
the *prediction* of which quantity scored separately.

**D1's prediction was wrong and was not re-aimed.** The measured GNSS
`A`-close delay does not move under a one-message phase shift — because on
that path the no-fix report does not affect admissibility at all. An
independent confirmation of §8 arriving from a direction nobody aimed at.

## 16. Multi-sensor feasibility

`CROSS_SENSOR_AUDIT.csv`. All 10 channels across 9 families audited; every
citation pinned by a regex required to match exactly once, with the published
line re-read and compared against the match.

Five channels have an explicit source-side "no value" encoding: `gnss` (fix
type), `battery.current` (−1), `battery.voltage` (65535 per cell), `mag`
(all-zero triple, in the decoders' own reading), `estimator.variances` (the
EKF flags bitfield). Five do not: baro, imu, esc, vibration, vehicle_status.

Two additional families selected, the limit item 23 sets:

* **`mag`** — probed fully. Worse than GNSS: no `_reject_sentinel`, so nothing
  is recorded at all.
* **`estimator_health`** — **structural row only.** `estimator.variances` is
  absent from `CORE_MAP`, so the autopilot's own estimator health signal is
  decoded, stored, and never crosses the core boundary. There is no trace to
  run; the absence is the finding.

`battery.voltage` was **rejected** despite having an explicit sentinel: same
family as `battery.current`, so it would not be an independent replication.

## 17. PX4 feasibility

`PX4_FEASIBILITY.md`. The same contracts run against `PX4Adapter` as a fourth
path.

* **gnss: identical in every respect** — vocabulary, clause results, first
  collapse. `px4.py:220-227` matches `ardupilot.py:226-236`. The collapse
  belongs to the shared bridge, not to either autopilot.
* **battery: PX4 emits nothing** (`vocabulary: []`). A
  `platform_qualification` override in `CHANNEL_SEMANTICS.yaml` sets
  `battery.current` to `UNAVAILABLE` on PX4 with a measured justification, so
  the retained-value defect cannot occur there. **The mechanism is a static
  declaration, not a preservation check.**
* **mag: NOT RUN**, deliberately. PX4 reads it from `HIGHRES_IMU` behind a
  `fields_updated` bitmask — a different source interface. Item 24 says not to
  force identical semantics.
* **Real log:** 345 `vehicle_gps_position` samples, all `fix_type == 3` (the
  invalid branch is not exercised by real data available here); 216
  `battery_status` samples, **all with `current_a == -1.0`**. The
  `ulog_source.py` finding is therefore not synthetic — it would feed −1.00 A
  into the core as a usable current 216 times on that flight.

## 18. Compositional result

`COMPOSITIONAL_ANALYSIS.md`. Local preservation composes by trivial induction
and the general theory (assume-guarantee refinement) is complete. **Neither is
claimed.**

The finding that survives is a negative one: **per-stage contracts would not
have caught this pipeline.** Every stage passes a reasonable local contract —
the decoder reads `fix_type` correctly, the adapter discards and records a
reason, the ChannelValue carries it, the bridge emits only admissible
channels. The end-to-end property fails anyway, because the bridge's output
alphabet is **two tokens wide** (`base.py:335` writes `valid = True`
unconditionally; the only alternative is `continue`) against an upstream
vocabulary of six.

That is the data-processing inequality with the constant made explicit. The
domain-specific corollary — end-to-end preservation is bounded by the
narrowest inter-stage interface — is a bottleneck argument in domain clothing.
`KNOWN/SUBSUMED`.

## 19. Which generic verification methods subsume the math

| method | subsumes |
|---|---|
| Trace / observational equivalence, bisimulation | the equivalence-level hierarchy |
| Refinement, assume-guarantee contracts | the compositional argument |
| Model checking, CEGAR | shortest-counterexample generation |
| Differential testing, ParDiff | the entire cross-path comparison |
| DES diagnosability under observation masks | the collapse-destroys-diagnosis result |
| Data-processing inequality | the alphabet-width bottleneck |
| Information-flow / taint tracking | "verify a metadata tag is not dropped along a program's dataflow" |
| Codd's A/I-marks; SQL null semantics | the two-kinds-of-absence state model |

Every mathematical statement in this package appears in that table.

## 20. What those methods do NOT provide

Honestly, and it is short:

1. **A stage index tied to source lines.** Differential testing tells you two
   implementations disagree, not which of five transformations lost the
   distinction. Here that mattered: the intuitive answer (the adapter) is
   wrong, and three families give three different answers on one path.
2. **A consequence measurement.** DES diagnosability proves a distinction can
   be destroyed. It does not tell you the failsafe still escalates, with the
   same actions, 0.32 s later.
3. **A declaration format that names forbidden merges with the consumer that
   needs them.** OPC UA specifies *allowed* merges; NE 107 defines the
   vocabulary. Neither says "these two must stay apart, because `failsafe.py:145`
   reads it."

Item 25's list, assessed: **A** (domain-specific evidence semantics) — no,
NE 107 and Codd have it. **B** (automatic extraction from real interfaces) —
no, nothing here is automatic; the contracts are hand-written. **C**
(multi-level equivalence) — no, standard. **D** (automatic downstream
consequence tracing) — **partially yes**, this is the thinnest gap found.
**E** (cross-ingest-path consistency) — no, ParDiff. **F** (actionable
shortest evidence-semantic counterexamples) — no, minimisation is standard.

One and a half of six.

## 21. Strongest surviving novelty candidate

Stated at full strength so it can be knocked down:

> *Verifying that a safety-assurance pipeline preserves the source-side
> evidence distinctions its own specification declares, by localising each
> loss to a transformation and measuring its effect on the diagnostic and
> failsafe layers.*

**It does not survive contact with §2.** Point by point:

* "Preserves declared distinctions" — AUTOSAR E2E for a different property,
  DQ-array propagation as an engineering convention, information-flow
  tracking as a formal one.
* "Localising each loss to a transformation" — the only genuinely thin spot,
  and it is a debugging affordance, not a result.
* "Measuring the effect on diagnosis" — DES diagnosability, as theory. The
  measurement is new to this codebase, not to the field.
* And the declaration this checker verifies against **already exists in this
  repository as prose** (`CHANNEL_SEMANTICS.yaml`'s `missing_semantics`, used
  at exactly one site as a `note=` string). The package's contribution to the
  contract is to make three sentences checkable.

Four of item 26's four kill conditions are met by existing work individually.
A combination of four established techniques applied to one codebase is not a
dissertation contribution, and no rewording changes that. Item 26 says: mark
`KNOWN/SUBSUMED`, stop the direction as dissertation novelty, do not rename
it. **That is done.**

## 22. Strongest forbidden novelty wording

Wordings that would be unsupported and must not appear:

* "A new framework for evidence-semantic verification" — it is a bounded
  differential test with a stage index.
* "The first end-to-end preservation check for autonomy sensor pipelines" —
  AUTOSAR E2E, DQ propagation, RV-for-ROS.
* "A new equivalence hierarchy for assurance pipelines" — multi-level
  observational equivalence is standard.
* "We show that abstraction destroys diagnosability" — Sampath et al. 1995.
* "A new class of defect: evidence-semantic collapse" — Codd, 1979.
* "Formally verified" — nothing here is verified. It is **bounded exhaustive
  testing to length 4** over a 3-symbol alphabet.
* "Proves the pipeline is correct" — a PASS means "no counterexample of
  length ≤ 4 in this alphabet", nothing more.
* Any severity language above the measurement. The failsafe **never** issues a
  different action. Writing "changes failsafe behaviour" without "by
  0.12–0.32 s of latency" would be false.

## 23. Physical validation plan

`TOOLING_FEASIBILITY.md` §3. **No physical HIL was executed; no hardware is
connected** — `pyserial` enumerates only `/dev/ttyS0`. Item 27 forbids
executing it without hardware and it was not executed.

Criterion 0 first: confirm the raw conditions occur on a physical link, with
`I` and `N` produced by **physically different causes** (antenna fault vs link
loss), not by one parameter. Then three falsifiable predictions, of which the
sharpest needs no matched pair: *on a power module reporting
`current_battery = -1`, the CSIA log shows `battery.current` usable for up to
0.5 s after the first sentinel, with a `sentinel_counts` entry for the same
channel and window.*

Hardware: Pixhawk-class FC on ArduCopter 4.8, GNSS receiver with detachable
antenna, telemetry radio pair, and a power module whose current sense can be
disabled — or a protocol emulator, which is the cheaper route. SITL can answer
criterion 0 for GNSS (the previous package did, and labelled it a simulator
result); it **cannot** for the battery sentinel, because SITL always reports a
current — which is precisely why the PX4 override exists.

## 24. Product / CI feasibility

`TOOLING_FEASIBILITY.md` §4. Designed, not productionised (item 32).

Trigger on a change to any file in a contract's `stage_sites`; extract the
alphabet from `accepted_input_states`; run the bounded checker; block on FAIL
with the shortest counterexample. Runtime **191 s** for three families ×
three paths × 120 words — fine nightly, marginal pre-merge, under 60 s if
restricted to families whose `stage_sites` a diff touches. Deterministic: no
randomness, no wall-clock dependence, byte-identical artifacts on re-run.

**The binding limitation is not the tool.** Its value is bounded above by a
hand-written declaration, and the declaration is the hard part. If nobody
writes down that `current_battery == -1` means something, the checker has
nothing to check. The realistic engineering path is to make
`CHANNEL_SEMANTICS.yaml`'s existing `missing_semantics` field machine-readable
rather than to introduce a second contract format — which makes this package's
JSON schema an intermediate artifact, not a deliverable.

## 25. Claim ledger

`CLAIM_LEDGER.json`. 24 claims. Summary:

| status | count |
|---|---|
| `KNOWN/SUBSUMED` | 6 |
| `EMPIRICAL ONLY` | 11 |
| `PROVED — NOVELTY NOT ESTABLISHED` | 2 |
| `PROVISIONAL` | 2 |
| `CONJECTURE` | 1 |
| `REFUTED` | 2 |
| `PROVED — POSSIBLE NOVEL CONTRIBUTION` | **0** |

Three refuted predictions are recorded and kept rather than edited away: the
D1 self-audit prediction; item 22's attribution of the GNSS collapse to the
adapter; and the expectation that the magnetometer would behave like the other
two families.

Four corrections to work done inside this package are also recorded: the mag
runs driven at 5 Hz against a 0.1 s watchdog (so admissibility was closed
throughout and nothing could be observed); `proj_value` returning a token
rather than a number (so VALUE and STATE were the same measurement twice);
untimed stage traces (so a stage saying the same things 0.5 s later looked
identical); and collapse sites named in files two of the paths never execute.

## 26. Recommendation

**Stop this direction as dissertation novelty. Keep the tool and fix the
defects.**

Three things are worth doing, in order:

1. **Fix the three defects.** They are independent of every research question
   and each is a small change:
   * `ardupilot.py:181` — `pop` the retained current and pass
     `MissingReason.SENTINEL`, mirroring the GNSS branch six lines away.
   * `ardupilot.py:143` — add an `else` that calls `_reject_sentinel` for the
     all-zero magnetometer triple. Today nothing is recorded at all.
   * `ulog_source.py:196-199` — read `current_a == -1.0` as a sentinel rather
     than emitting `valid=True`. On the one real log available it is wrong
     216 times out of 216.

2. **Decide deliberately about the bridge.** `to_core_samples`' two-token
   output is the root of two of the three collapses, and widening it means
   touching the frozen core — which is forbidden, and rightly. The realistic
   option is to make the *reason* available beside the core sample rather than
   inside it, so the flight log stops saying "GPS data invalid" when nothing
   arrived. That is a design decision for the v1.1 layer, not a research
   question, and this package does not make it.

3. **Make `missing_semantics` machine-readable.** The declarations already
   exist. Turning them into checkable clauses and running the bounded checker
   in CI is a few days of engineering with a clear payoff and no novelty claim
   attached.

What not to do: do not run a large campaign, do not build the symbolic
version, and do not look for a fourth sensor family. The reduction §21
performs is not going to be reversed by more measurements of the same kind.

---

### Artifact index

| item | artifact |
|---|---|
| prior art | `PRIOR_ART_MATRIX.md` |
| state model | `CANONICAL_STATE_MODEL.md` |
| equivalence levels | `EQUIVALENCE_LEVELS.md` |
| contract schema | `EVIDENCE_SEMANTICS_CONTRACT.schema.json` |
| contracts | `ARDUPILOT_INGEST_CONTRACTS/{gnss,battery,mag}.json` |
| GNSS | `GNSS_SEMANTIC_TRACE.md` |
| battery | `BATTERY_SEMANTIC_TRACE.md` |
| cross-path | `CROSS_PATH_EQUIVALENCE.csv` |
| minimality | `MINIMAL_COUNTEREXAMPLES.json` |
| blame | `CAUSAL_BLAME_TRACES.json` |
| consequence | `DOWNSTREAM_CONSEQUENCES.csv` |
| self-audit | `TOOL_SELF_AUDIT.json` |
| composition | `COMPOSITIONAL_ANALYSIS.md` |
| sensors | `CROSS_SENSOR_AUDIT.csv` |
| PX4 | `PX4_FEASIBILITY.md`, `results/PX4_FEASIBILITY.json` |
| tooling / HIL / CI | `TOOLING_FEASIBILITY.md` |
| ledger | `CLAIM_LEDGER.json` |
| item-12 hard stop | `results/PRIOR_RESULT_REPRODUCTION.json` |
| full check output | `results/EVIDENCE_SEMANTICS_CHECK.json` |
