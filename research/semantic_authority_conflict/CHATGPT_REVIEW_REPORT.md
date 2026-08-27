# Assurance under conflicting semantic authorities — Stage 0 review report

Base: commit `d2cb07b`. Prior-art kill test, formal model, source-grounded
conflict reproduction, set-valued feasibility. No paper, no novelty claim, no
change to production semantics, no physical HIL, no exploit tooling.

Written for hostile review. The instruction that governed the work was: try
to show the standard alone is enough, the conflicts are merely bugs, all
interpretations lead to the same decision, and robust decision theory already
subsumes the mathematics. **Three of those four attacks succeed.**

---

## 1. Executive verdict

**`ENGINEERING_INCONSISTENCY_ONLY`. Novelty: NOT ESTABLISHED.**

The hypothesis was that protocol, producer, consumer and runtime semantics
"need not agree", and that an assurance layer must therefore reason about
which authority to believe. Measured against three real cases, the picture is
different and simpler:

**The authorities do not conflict.** Zero `SPEC_VS_PRODUCER` conflicts across
all three cases. On the battery, MAVLink declares `invalid="-1"` and
ArduPilot writes exactly `-1` when it has no current — the specification and
the producer say the same thing. Where they appear to differ, the higher
authority is **silent**, not contradicting.

**All 17 counted conflicts are consumer-side**: 8 `CROSS_CONSUMER`,
6 `PRODUCER_VS_CONSUMER`, 3 `SPEC_VS_CONSUMER`. Three decoders disagreeing
with an authority that speaks with one voice is not semantic uncertainty. It
is three bugs.

**No conflict reaches the ACTION level.** 0 of 9 authority pairs. The failsafe
issues an identical action set whichever consumer is used. The deepest
consequence found anywhere is a **failsafe latency difference** on GNSS.

**The mathematics is textbook.** Item 44's proposition is the definition of
robustness over an ambiguity set.

## 2. Research question

> Can an autonomous assurance system represent and reason safely about
> conflicting semantic authorities without silently choosing one
> interpretation as truth?

It can — the machinery is a few hundred lines and it runs. On these cases it
does not need to, because there is nothing above the consumer to disagree
about and nothing below it that changes.

## 3. Closest prior art

| component | subsumed by |
|---|---|
| multiple authorities, inconsistency **tolerated** rather than resolved | **ViewPoints / multi-perspective specifications** — Hunter & Nuseibeh TSE 1994; *Managing inconsistent specifications* TOSEM 1998; Easterbrook & Nuseibeh SEJ 1996 |
| set-valued interpretation, no weights, robustness as invariance | **credal sets / imprecise probability / distributionally robust optimization** |
| implementations disagreeing on identical raw input | **parser differentials / LangSec**; *A Survey of Parser Differential Anti-Patterns* (LangSec 2023); ParDiff (OOPSLA 2024); N-version programming |
| conflicting evidence in a safety argument | **Dempster–Shafer safety-case confidence**; evidence-theory fault diagnosis |

## 4. What prior art kills

1. Representing conflicting specifications without resolving them —
   ViewPoints, thirty years ago, with "tolerate inconsistency" as its stated
   principle.
2. Set-valued output under model ambiguity — credal sets.
3. Robustness-as-invariance (item 44) — a definition, not a result.
4. Implementations disagreeing on one raw input, including the security
   framing item 48 raises — LangSec.
5. Conflicting evidence in a safety case — Dempster–Shafer.

## 5. Exact surviving candidate

> Applying an established multi-authority, set-valued formulation to
> **sensor-interface semantics in an autonomy ingest path**, and measuring how
> far the disagreement propagates.

The measurement was made and it removes the candidate: the disagreement is
consumer-side and never reaches an action.

## 6. Semantic authority definitions

`AUTHORITY_MODEL.md`. Four kinds, 16 rows, **every citation re-read from disk
and 16 of 16 verify**.

| authority | source | tier |
|---|---|---|
| `C_spec` | MAVLink message definition, attribute + description | protocol schema |
| `C_producer` | ArduPilot's own executable source | producer source |
| `C_consumer_{A,B,C}` | the three committed CSIA ingest paths | consumer source |
| `C_observed_{A,B,C}` | what each path actually puts into the frozen core | runtime |

**No authority carries a weight** (item 10). The analysis uses set inclusion,
equality of downstream outcome, and silence.

Two coordinates were added after the first run gave a wrong answer, and both
are recorded rather than repaired quietly:

* **`scope`** — which raw state the authority speaks about.
  `C_producer_absence` describes "no GPS configured", a different raw state;
  pooling it made `IMPLEMENTATION_FIRST` read as self-inconsistent on GNSS.
* **`aspect`** — which part of it. `C_spec` says what `fix_type` MEANS;
  `C_producer` says what lat/lon/alt CONTAIN. Comparing them manufactured the
  only `SPEC_VS_PRODUCER` conflict in the first run. After the correction that
  type is empty everywhere.

## 7. Formal conflict definition

Conflict at raw state `r` iff two authorities sharing `scope` and `aspect`
both speak and map `r` to non-equivalent interpretations:

```
CONFLICT            both speak, and disagree
UNDERSPECIFICATION  one is SILENT -- the other contradicts nothing
AGREEMENT           both speak, and agree
OUT_OF_SCOPE        different raw state or different aspect
```

**`SILENT` is not an interpretation.** Item 8 defines conflict as
`|{C_a(r)}| > 1`; encoding silence as a value would report all 7
underspecification pairs as disagreements. Nobody is wrong because nobody
said.

Equivalence is semantic, not syntactic (item 20): enum `INVALID` and
`valid=False` agree; the producer's `-1` **is** the spec's `NOT_MEASURED`
expressed in the spec's own encoding. Reading those as different was the trap
this definition exists to avoid.

## 8. Interpretation-set model

```
S*(r) = { C_a(r) : a admissible, C_a(r) != SILENT }
```

A set, not a distribution. No weights, no priors, no combination rule.

| case | `\|S*\|` | composition |
|---|---|---|
| battery | 3 | `NOT_MEASURED` (spec **and** producer) vs three consumer readings |
| GNSS position fields | 4 | spec SILENT; producer and three consumers each different |
| magnetometer | 2 | spec SILENT; two consumer readings |

## 9. Decision robustness definition

A conclusion is **semantically robust** for `w` at a level iff
`|{F(C_a,w)}| = 1` over the admissible authorities; otherwise **semantically
ambiguous**. Item 44's proposition, and it is the standard definition of
robustness over an ambiguity set.

Every comparison carries a **null control** `V^k`. Levels that already
disagree on an all-nominal word are reported `CONFOUNDED_BY_CONTROL` and
count for nothing — 27.8% of level cells, including DIAGNOSIS in all three
cases.

## 10. Battery authority conflict

Reproduced exactly before anything was built: **5.00 A / 0.00 A / −1.00 A**.

| authority | interpretation | citation |
|---|---|---|
| `C_spec` | `NOT_MEASURED` | `common.xml:BATTERY_STATUS.current_battery`, `invalid="-1"` |
| `C_producer` | `NOT_MEASURED` | `GCS_Common.cpp:390-393` — `else { current = -1; }` |
| `C_consumer_A` | `RETAIN_PREVIOUS` | `ardupilot.py:181` |
| `C_consumer_B` | `SUBSTITUTE_ZERO` | `plugins.py:194` |
| `C_consumer_C` | `LITERAL_MINUS_ONE` | `ulog_source.py:196-199` |

**Spec and producer agree exactly.** Nine conflicts, every one involving a
consumer. Robust at EVIDENCE, ASSURANCE and ACTION.

## 11. GNSS authority conflict

| authority | aspect | interpretation |
|---|---|---|
| `C_spec` | `fix_type` meaning | `NO_POSITION_INFORMATION` |
| `C_spec_position_fields` | position fields | **`SILENT`** |
| `C_producer` | position fields | `STALE_POSITION_WITH_HONEST_FIX_TYPE` (`AP_GPS.cpp:1399-1417`) |
| `C_consumer_A/B/C` | position fields | drop / zero / pass-through |

**The schema says nothing about what lat/lon/alt contain when `fix_type < 3`.**
ArduPilot fills them with the last known `Location` and relies on `fix_type`
to carry the warning — which the spec permits, because the spec did not
speak. The three consumers are each making a **licensed** choice.

A second producer fact: with no GPS configured the message is not sent at all
(`AP_GPS.cpp:1394-1396`), so at the producer "no fix" and "no message" are
genuinely distinct — which is what makes the consumer-side collapse a loss.

The only case reaching ASSURANCE. Still robust at ACTION.

## 12. Third independent case

Magnetometer all-zero triple. **Chosen and justified before any downstream
outcome was inspected** (item 17): the estimator-health channel is absent from
`CORE_MAP`, so its consequence is empty by construction and choosing it would
have guaranteed a null result.

Spec `SILENT`; two consumers treat the triple as absence *and record nothing
at all*; the third emits the zero vector as a valid field. Disagreement dies
at EVIDENCE and never reaches the failsafe.

## 13. Declared vs effective semantics

`DECLARED_VS_EFFECTIVE_SEMANTICS.csv`. Declared interpretation and measured
core value in separate columns, never conflated.

| case | authority | declared | effective at the core |
|---|---|---|---|
| battery | A | `RETAIN_PREVIOUS` | `V`, 5.0 |
| battery | B | `SUBSTITUTE_ZERO` | `M`, 0.0 |
| battery | C | `LITERAL_MINUS_ONE` | `V`, −1.0 |
| GNSS | A | `DROP_AND_RECORD_REASON` | nothing emitted |
| GNSS | B | `SUBSTITUTE_ZERO_MARK_INVALID` | `I`, (0,0,0) |
| GNSS | C | `PASS_THROUGH_MARK_INVALID` | `I`, (0,−0,0) |
| mag | A, B | `TREAT_AS_ABSENT_SILENTLY` | nothing emitted |
| mag | C | `LITERAL_ZERO_FIELD` | `V`, (0,−0,−0) |

Declared and effective agree in every row. The consumers do what they say —
they simply say different things.

## 14. Cross-path results

`CROSS_PATH_RESULTS.csv`, nine pairs across three cases, each with its
control column. `CONFLICT_PROPAGATION.csv` records first and last stage of
disagreement over the nine pipeline stages, and first and last level.

**`disagreement_reaches_ACTION` is false for all nine.**

## 15. Cross-platform feasibility

Both trees are local. The producer authority was read from **ArduPilot
source**, unread in any previous package — a genuine second axis, since
earlier work had only `C_spec` and `C_consumer`.

PX4 was not read. Prediction recorded in advance: a uORB study would find
mostly `UNDERSPECIFICATION`, because `.msg` files carry no `invalid=`
attribute, so `C_spec` is `SILENT` by construction. If that holds it
strengthens this finding rather than extending it.

## 16. Shortest authority-conflict traces

One message in every case — the shortest possible in these alphabets, so
minimality is vacuous rather than proved. `MINIMAL_AUTHORITY_COUNTEREXAMPLES.json`
records 7 entries, each a **pair** of authorities: `|subset| = 2` is minimal by
definition, since one authority cannot disagree with itself.

## 17. Conflict propagation depth

| case | first level of disagreement | last level observable | reaches ACTION |
|---|---|---|---|
| battery | VALUE | STATE | **no** |
| GNSS | VALUE | ASSURANCE | **no** |
| mag | VALUE | EVIDENCE | **no** |

Every conflict starts at VALUE. None survives to ACTION.

## 18. Decision sensitivity

`DECISION_SENSITIVITY.csv`. Distinct outcomes per case per level:

| level | battery | GNSS | mag |
|---|---|---|---|
| VALUE | 3 ambiguous | 3 *confounded* | 2 *confounded* |
| STATE | 2 ambiguous | 2 ambiguous | 2 ambiguous |
| EVIDENCE | **1 robust** | 2 ambiguous | 2 ambiguous |
| DIAGNOSIS | 2 *confounded* | 3 *confounded* | 3 *confounded* |
| ASSURANCE | **1 robust** | 2 ambiguous | **1 robust** |
| ACTION | **1 robust** | **1 robust** | **1 robust** |

Ambiguity rate 0.389, robust rate 0.333, confounded 0.278 over 18 cells.

## 19. SPEC_FIRST baseline

**Resolves 2 of 3.** Battery `NOT_MEASURED`; GNSS `fix_type` meaning. Fails on
the magnetometer and on the GNSS position fields — not because another
authority disagrees, but because the schema is `SILENT`.

Reviewer B's position — trust the standard and fix the code — is correct
wherever the standard speaks, and inapplicable where it does not.

## 20. IMPLEMENTATION_FIRST baseline

**Resolves 2 of 3**, and on the battery gives the identical answer to
SPEC_FIRST. Fails on the magnetometer, where there is no producer-side
convention either.

## 21. OBSERVATION_FIRST baseline

**Resolves 0 of 3.** There are three runtimes and they disagree; privileging
runtime behaviour cannot yield a unique answer unless the consumers already
agree. Reviewer C's position is not implementable here — which is itself the
answer to it.

## 22. SET_VALUED baseline

Flags ambiguity at VALUE/STATE (battery), STATE/EVIDENCE/ASSURANCE (GNSS),
STATE/EVIDENCE (mag). **In 0 of 3 cases does that ambiguity reach ACTION.**

Item 38's question — does B3 expose meaningful uncertainty the others conceal,
or just make everything ambiguous? On these cases: it exposes real upstream
disagreement that B0/B1/B2 each resolve by fiat, and none of it changes what
the vehicle would do.

## 23. Diagnosis consequences

DIAGNOSIS is `CONFOUNDED_BY_CONTROL` in **all three** cases: the paths' trust
trajectories already differ on an all-nominal word, because they differ in
sample rate and timestamp convention. Without the control this would have been
reported as authority-driven diagnostic divergence in every case. It is an
artifact.

**No attributable diagnostic consequence was measured anywhere.**

## 24. Assurance consequences

One case, GNSS, `SEMANTICALLY_AMBIGUOUS` at ASSURANCE — and only as timing.
The level history and issued actions are identical; the previous package
measured the gap as 0.12–0.32 s of failsafe latency.

## 25. Action / failsafe consequences

**None.** ACTION is robust in all three cases; 0 of 9 pairs reach it. Item
29's `NO_DECISION_RELEVANT_SEMANTIC_AMBIGUITY` holds at the action level.

## 26. Unsupported unique conclusions

Item 30 asks where a single-contract implementation would make a unique
conclusion another source-supported interpretation contradicts.

The honest answer: **at VALUE and STATE, yes; at ACTION, never.** A system
committed to `C_consumer_A` concludes "battery current is 5.00 A" when
`C_spec` and `C_producer` both say it was not measured — a genuinely
unsupported unique conclusion about the *value*. It does not become an
unsupported unique conclusion about the *action*, because the action is the
same either way.

## 27. Semantic ambiguity exposure

Item 31's integral was **not computed**. With one word per case there is no
time series to integrate, and a number derived from three points would be
decoration. Recorded as not done rather than estimated.

## 28. Whether one authority dominates

Item 33's question, and the answer matters.

**Yes, where it speaks.** `C_spec` and `C_producer` agree wherever both speak,
and every conflict counted is a consumer departing from that agreement.
Precedence would resolve every genuine conflict in this package.

Where the spec is silent — 7 pairs — no precedence rule applies at all,
because there is no higher authority to defer to. That residue is a
specification gap, not a tie.

## 29. Whether simple bug fixes eliminate the phenomenon

Item 52's kill test, answered **analytically, not by measurement** — item 51
requires the research branch to retain pre-fix behaviour, so no fix was
applied.

From the authority table: all 17 conflicts involve a consumer departing from
an authority that speaks with one voice. Making the three consumers honour
the spec removes every one. The remaining 7 pairs are underspecification,
which a decision closes.

Recorded as `PROVISIONAL` in the ledger, with the falsification test named:
implement the fixes on a branch and re-run `conflicts.py`; item 52 predicts
the count drops to zero.

## 30. Formal results

Three, none of them new:

1. Robustness as invariance over the authority set (item 44) — a definition.
2. Conflict requires two speaking authorities sharing scope and aspect;
   silence is not disagreement — a modelling necessity, and the
   incompleteness/inconsistency axis is already named in the multi-perspective
   requirements literature.
3. `|minimal subset| = 2` — one authority cannot disagree with itself.

## 31. Which mathematics is KNOWN/SUBSUMED

All of it. Robustness over ambiguity sets (credal sets, imprecise probability,
DRO); set-valued semantics (nondeterministic transition systems, abstract
interpretation); reasoning without choosing (paraconsistent logic, belief
revision); disagreement detection across implementations (N-version, parser
differentials, ParDiff); conflicting evidence in an argument (Dempster–Shafer).

Item 43 asks whether any one directly subsumes the formulation. **Credal-set
robustness does**, exactly.

## 32. Strongest surviving novelty candidate

> The `CONFLICT` versus `UNDERSPECIFICATION` distinction, applied to sensor
> interfaces: measuring not whether authorities disagree but whether the
> higher one spoke at all.

It does not survive. The incompleteness-versus-inconsistency axis is explicit
in the multi-perspective requirements literature that already subsumes the
framing, and this package's contribution to it is one column in a CSV.

What is genuinely useful is not novel: **the residue in this codebase is 7
places where MAVLink is silent and three implementations each guessed
differently.** That is a finding about a standard, worth a note to the MAVLink
community, and it is not research.

## 33. Strongest forbidden novelty wording

* "novel", "first", "new paradigm", "unprecedented", "new theorem".
* "Semantic authorities conflict in real autonomy pipelines." Measured, they
  do not: zero spec-versus-producer conflicts.
* "Set-valued assurance exposes unsafe unique conclusions." Not at the action
  level, in any case here.
* "Conflicts change assurance behaviour." One case reaches ASSURANCE and only
  as 0.12–0.32 s of latency; none changes an action.
* "Robust decision making under semantic uncertainty" as though it named
  something new — it is credal-set robustness.
* Any use of the DIAGNOSIS-level distinct-outcome counts without the
  `CONFOUNDED_BY_CONTROL` column.
* "Verified", "proved" for anything empirical here. Three cases, one word each.

## 34. Physical validation plan

`PHYSICAL_AUTHORITY_VALIDATION_PLAN.md`. **No hardware; nothing executed.**
`pyserial` sees only `/dev/ttyS0`.

The gap this package cannot close is `C_producer` versus `C_observed`: the
producer authority was read from a source tree, and nothing confirms the
flying binary matches. Level 1 is an emulator into a physical controller;
Level 2 adds a real GNSS with a detachable antenna and a power module with no
current sense. The sharpest test is the GNSS position fields under no fix,
precisely because the specification does not cover them.

## 35. Security implications — conceptual only

`SECURITY_IMPLICATIONS_NOTES.md`. Recorded, not developed; no exploit tooling,
per item 48.

Where two consumers of one stream disagree about what a byte means, a party
controlling the encoding can choose an input they read differently. **This is
LangSec parser differentials**, a mature research area, and everything in the
note is that literature applied here. The underspecification cases are the
more interesting ones: where the standard is silent there is no violated rule
to detect. The security framing contributes **nothing** to the verdict.

## 36. Negative results

1. Zero spec-versus-producer conflicts.
2. Zero conflicts reaching ACTION.
3. No attributable diagnostic consequence — DIAGNOSIS confounded in all three
   cases.
4. `OBSERVATION_FIRST` resolves nothing.
5. Set-valued output adds no action-relevant information here.
6. The ambiguity-exposure integral could not be computed.
7. Item 47's requirement — two independent real conflicts, at least one with a
   consequence beyond numeric representation — is met only in the weakest
   sense: GNSS reaches ASSURANCE as latency.

## 37. Unexpected results

1. **The producer agrees with the specification**, exactly, on the case that
   motivated the whole brief. `else { current = -1; }` is the spec's own
   encoding.
2. **The specification is silent** where the brief assumed conflict. The GNSS
   position fields carry no `invalid=` attribute and no clause — so the three
   consumers are not violating anything.
3. **Two category errors of mine inflated the conflict count** before they
   were caught: pooling an authority about a different raw state, and
   comparing authorities about different aspects. The headline "zero
   `SPEC_VS_PRODUCER`" exists only after correcting a classifier that had
   manufactured one.
4. **The citation verifier caught five bad citations in the first run**,
   including one of my own line numbers.
5. **The null control disqualified DIAGNOSIS in all three cases** — the level
   that would have looked most like a semantic finding.

## 38. Hostile review

**A — "This is just inconsistent specifications."** Conceded. ViewPoints,
TSE 1994, with "tolerate inconsistency" as the stated principle. §3.

**B — "Trust the standard and fix the code."** Tested as `SPEC_FIRST`:
resolves 2 of 3, fails only where the standard is silent. For every genuine
conflict, correct.

**C — "Runtime behaviour is the only thing that matters."** Tested as
`OBSERVATION_FIRST`: resolves 0 of 3, because there are three runtimes and
they disagree. The position is not implementable here.

**D — "Set-valued output is just robust decision making."** Conceded
entirely. Credal-set robustness subsumes item 44 exactly. §31.

**E — "Your ambiguity is manufactured from known bugs."** Substantially
conceded. The battery case is three bugs against an agreed authority. What is
not a bug is the 7 underspecification pairs — and those are a gap in MAVLink,
not ambiguity to be reasoned about at runtime. The known defects are kept
separate (item 50) and contribute nothing to novelty.

**F — "Nothing changes the actual failsafe."** **Correct.** 0 of 9 pairs
reach ACTION. Conceded and the verdict downgraded accordingly.

**G — "This is only a semantic-interoperability problem."** Largely conceded;
the interoperability literature resolves by canonical model, which is exactly
what `SPEC_FIRST` does successfully here.

**H — "Every software stack has inconsistent docs."** The requirement was a
downstream assurance consequence, not mere inconsistency. The strongest found
is 0.12–0.32 s of failsafe latency on one case.

**I — "Your semantic authorities are arbitrarily chosen."** Each corresponds
to an independently identifiable source, and all 16 citations are re-read
from disk. The `scope` and `aspect` coordinates exist because the first
version *was* comparing things that should not be compared — conceded, and
recorded.

**J — "You keep moving the novelty target."** Chronology conceded without
qualification. This is the fourth direction in sequence. It began with
explicit kill conditions, three of the four attacks succeeded, and the answer
is to stop.

## 39. Claim ledger

`CLAIM_LEDGER.json`, 16 claims: 2 `KNOWN/SUBSUMED`, 11 `EMPIRICAL ONLY`,
1 `PROVED — NOVELTY NOT ESTABLISHED`, 1 `PROVISIONAL`, 1 `REFUTED`,
**0 `PROVED — POSSIBLE NOVEL CONTRIBUTION`**. Three refuted predictions kept.

## 40. Recommendation

**Stop. The direction is closed, and the reason is not prior art — it is the
measurement.**

Item 60's ten conditions for `STRONG_SEMANTIC_UNCERTAINTY_CANDIDATE`: (1)
fails, (4) fails outright — no conflict changes diagnosis or assurance output
in an attributable way, (5) fails — spec precedence resolves every genuine
conflict, (6) fails — set-valued output exposes no action-relevant unsupported
conclusion. Four of ten fail; all ten are required.

Three things are worth doing and none is research:

1. **Fix the three consumers** to honour `invalid="-1"`. The specification and
   the producer already agree; the code does not. This closes every genuine
   conflict in the package.
2. **Close the 7 underspecification pairs by deciding.** Where MAVLink is
   silent about the GNSS position fields under no fix, and about the
   magnetometer all-zero triple, someone has to choose and write it down —
   ideally upstream, as a MAVLink clarification, since the gap is theirs.
3. **Keep the null control.** It disqualified the DIAGNOSIS level in all three
   cases. Any future cross-path comparison without it will report sample-rate
   artifacts as semantic findings.

What not to do: do not build set-valued runtime machinery. On these cases it
carries no information that changes an action, and item 39 is right that more
ambiguity is not automatically safer.

---

### Artifact index

| item | artifact |
|---|---|
| prior art | `PRIOR_ART_MATRIX.md` |
| authority model | `AUTHORITY_MODEL.md`, `AUTHORITY_TABLE.csv` |
| equivalence | `SEMANTIC_EQUIVALENCE_MODEL.md` |
| battery | `BATTERY_AUTHORITY_TRACE.md` |
| GNSS | `GNSS_AUTHORITY_TRACE.md` |
| third case | `THIRD_CASE_AUTHORITY_TRACE.md` |
| conflicts | `AUTHORITY_CONFLICTS.csv` |
| declared vs effective | `DECLARED_VS_EFFECTIVE_SEMANTICS.csv` |
| decision sensitivity | `DECISION_SENSITIVITY.csv` |
| set-valued | `SET_VALUED_ASSURANCE_RESULTS.json` |
| propagation | `CONFLICT_PROPAGATION.csv` |
| minimal counterexamples | `MINIMAL_AUTHORITY_COUNTEREXAMPLES.json` |
| baselines | `BASELINE_COMPARISON.csv`, `results/BASELINE_SUMMARY.json` |
| cross-path | `CROSS_PATH_RESULTS.csv` |
| cross-platform | `CROSS_PLATFORM_FEASIBILITY.md` |
| physical plan | `PHYSICAL_AUTHORITY_VALIDATION_PLAN.md` |
| security note | `SECURITY_IMPLICATIONS_NOTES.md` |
| ledger | `CLAIM_LEDGER.json` |
