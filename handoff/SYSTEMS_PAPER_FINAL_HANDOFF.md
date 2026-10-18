# CSIA Systems Paper I — canonical handoff

**For the systems-paper writing agent, who has no repository access.**
Self-contained: every number below is quoted from the artifact that produced
it, with the artifact path and the JSON pointer, so nothing needs to be
re-derived and no repository lookup is required.

| | |
|---|---|
| repository HEAD | `228bebeb14395aebda60d76dbf6a54b292d0e344` |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| evidence freeze tag | `csia-dual-paper-evidence-freeze` = `eb2577d6830208b26d33facb283aa5be0ddf7c86` |
| tests | 1684 collected, all passing |
| build | `make paper-systems` -> 26 pages, all citations resolved |
| Phase-I baseline | `main @ 848f556` (ArduCopter 3.3 SITL), enforced by `tools/publication/phase_guard.py` |

**Everything in this document is verified.** Where a fact could only be
established by running code, it was run and the result is quoted. Where it
could not be established here, it is marked **BLOCKED**.

---

## 1. Canonical manuscript

| | |
|---|---|
| **canonical source** | `papers/csia_systems/main.tex` — the ONLY canonical systems manuscript |
| supplement | `publication/system_paper_i/evidence_export/` (16 files, allowlisted for release) |
| title | Diagnostic self-occlusion in a deployed cross-sensor trust layer |
| page count | **26** |
| bibliography | `papers/csia_systems/refs.bib` — 11 entries, **0 verified** |
| artifact map | `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` |
| claim ledger | `research/systems-paper/CLAIMS.csv` (26 rows) |
| red team | `research/systems-paper/REVIEWER_RED_TEAM.md` |

### Superseded / non-canonical — never write from these

| path | status |
|---|---|
| `CANONICAL_MANUSCRIPT_MANIFEST.md` | GENERATED pointer, states the canonical file at commit `9f39474`. Trust the pointer, not its date |
| `docs/research/PAPER1_EMPIRICAL_SECTION.md` | **belongs to the MATHEMATICAL paper despite the filename.** Naming collision, recorded in the gate-conditioning artifact map |
| `deliverables/*.md` | HISTORICAL packaged deliverables |
| `publication/system_paper_i/PAPER1_CRITICAL_STARTER.txt`, `PAPER1_EVIDENCE_BUNDLE.txt` | GENERATED transfer bundles, not manuscripts |

### Current abstract (verbatim)

```
We report measurements of \emph{false-healthy exposure} on a deployed
cross-sensor diagnostic layer for small uncrewed aircraft: the time the system
spends asserting health while holding no evidence it is entitled to assert it
from. The layer maintains per-sensor trust coefficients over a physics-derived
graph and runs a gated naive-Bayes diagnosis over eight mutually exclusive
causes. A gated feature is skipped rather than down-weighted, and the
implementation has no state meaning ``not assessable'', so absence of
applicable evidence is emitted as health. Under sustained GNSS denial the
diagnosis reports \code{nominal} for the entire fault window and never names
\code{gps\_fault}, while the GPS trust coefficient reads 0.9767. The vehicle is
not blind: the failsafe reaches CAUTION through an independent data-freshness
disjunct and reconfigures navigation. It cannot name the cause.

\textbf{Two scope corrections, both forced by our own controlled-injection
campaign against a real autopilot, are reported here rather than buried.}
First, this behaviour is specific to faults that remove the GNSS fix. A
position glitch that leaves the fix valid does not close the gate at all, so
the evidence remains available. Second, in that case the layer sees the fault
and still does not escalate: its residual detector saturates at the floor for
every injected position error we tested, from 5.6\,m to 5.6\,km, and no step
magnitude produces an alarm. The same total error applied as a ramp does.
Escalation here is duration-limited, not magnitude-limited.

We make no observability claim. Receiver observables detect GNSS denial well;
the failure we measure is one of evidence routing and applicability semantics,
not of detectability. We report a threshold result that yields a checkable
design rule, a chatter-resonance prediction tested against the deployed code
and holding, a one-line repair with its full measured cost, and a counterfactual
abstaining policy measured against current behaviour on the same flights. We
claim engineering contribution and measurement only.
```

### Section structure

1. Introduction
2. Related work: what we instantiate
3. System under measurement
4. The self-occlusion measurement
5. Containment: what is established and what is not
6. Gate closure frequency, measured against a real autopilot
7. The glitch non-alarm has a tested cause
8. Two detectors, and what neither sees
9. False-healthy exposure, and the cost of abstaining
10. Chatter resonance
11. A design rule and its enforcement
12. A repair, measured
13. Limitations
14. Claim table
15. Conclusion

### Canonical contribution statement

Engineering contribution and measurement only. No observability claim, no
novel mathematics, no demonstrated operational harm. The transferable output is
the design rule of §11 and its machine enforcement.

---

## 2. Claim table — all 26, canonical status

Status vocabulary as used in the ledger: `PROVED` (5), `EMPIRICAL_ONLY` (12),
`PROVISIONAL` (3), `KNOWN_SUBSUMED` (2), `REFUTED` (3), `WITHDRAWN` (1).

| ID | status | claim |
|---|---|---|
| `SC-01` | **EMPIRICAL_ONLY** | Under sustained GNSS denial the diagnosis reports nominal for the entire fault window and never names gps_fault, while the GPS trust coefficient reads 0.9767. |
| `SC-02` | **PROVED** | The mechanism is structural: with the GPS physics feature gated out, no active feature distinguishes nominal from gps_fault, so their log posterior ratio equals the log prior ratio exactly. |
| `SC-03` | **PROVED** | An independent structural checker, importing no CSIA module and no part of the support-aware implementation, agrees with the production discriminating-term analysis on 378,000 of 378,000 tick-by-pair comparisons. |
| `SC-04` | **EMPIRICAL_ONLY** | gps_fault\|nominal is the only hypothesis pair in the deterministic scenario catalogue that ever becomes structurally indistinguishable. |
| `SC-05` | **EMPIRICAL_ONLY** | The pair is also structurally indistinguishable for 76 ticks at the start of EVERY scenario, including clean flight, before the GPS physics gate opens. |
| `SC-06` | **EMPIRICAL_ONLY** | Under GNSS fix loss the pair is additionally indistinguishable for 200 consecutive ticks (8.0 s at 25 Hz) starting at tick 625. |
| `SC-07` | **EMPIRICAL_ONLY** | Smoothing changes threshold-crossing behaviour, and the direction and size of the change depend on the arm. |
| `SC-08` | **EMPIRICAL_ONLY** | In the pre-onset window smoothing cuts threshold crossings from 36 to 9 out of 374 ticks, a 4x reduction in false crossings. |
| `SC-09` | **EMPIRICAL_ONLY** | The CUSUM alarms earlier than the trust threshold in every faulted arm and never in the clean window. |
| `SC-10` | **KNOWN_SUBSUMED** | No CUSUM novelty is claimed. |
| `SC-11` | **KNOWN_SUBSUMED** | The general mechanism of fault-state-dependent observation loss is prior art and CSIA asserts no priority over it. |
| `SC-12` | **EMPIRICAL_ONLY** | The behaviour is specific to faults that remove the GNSS fix; a position glitch that leaves the fix valid does not close the gate. |
| `SC-13` | **EMPIRICAL_ONLY** | The residual detector saturates at the floor for every injected step from 5.6 m to 5.6 km and no step magnitude produces an alarm; the same total error as a ramp does. |
| `SC-14` | **EMPIRICAL_ONLY** | q_gvalid = 0.984 over 3744 monitored ticks per arm; first gate closure 0.44 s after injection in every denial flight. |
| `SC-15` | **PROVED** | E_h subset-of C_h containment holds for gps_fault by inspection. |
| `SC-16` | **WITHDRAWN** | U_h subset-of C_h containment. |
| `SC-17` | **REFUTED** | The WP-C8 mass-invariance 'theorem'. |
| `SC-18` | **REFUTED** | R16, slow IMU bias detection. |
| `SC-19` | **REFUTED** | 'The campaign varied two axes.' |
| `SC-20` | **PROVED** | The posterior is not confidence: a leader at high posterior with zero discriminating evidence is reported as SUPPORT_LOST_FOR_REQUIRED_INFORMATION, not as eligibility. |
| `SC-21` | **PROVED** | No observability claim is made. Receiver observables detect GNSS denial well; the failure measured is one of evidence routing and applicability semantics. |
| `SC-22` | **PROVISIONAL** | A public-log exposure study over PX4 Flight Review logs. |
| `SC-23` | **PROVISIONAL** | Mechanism A reproduced on the CURRENT ArduPilot stack and, where the route is valid, on PX4. |
| `SC-24` | **EMPIRICAL_ONLY** | Mechanism B replicates on ArduPilot 4.8: given the platform's own measured banked state and measured per-tick evidence and forgetting factor, the source recursion reproduces the runtime trust trajectory and predicts the observed threshold crossing. |
| `SC-25` | **PROVISIONAL** | Mechanism B is INAPPLICABLE on PX4 SIH and was not tested there. |
| `SC-26` | **EMPIRICAL_ONLY** | On 15,595 ticks from 20 real ArduPilot 4.8 SITL trials in which the GNSS fix was never lost, the structural predicate reports the nominal\|gps_fault pair DISTINGUISHABLE at every tick and never collapses. |

### The six the brief asks about, in detail

**`SC-02` — PROVED**

- *statement*: The mechanism is structural: with the GPS physics feature gated out, no active feature distinguishes nominal from gps_fault, so their log posterior ratio equals the log prior ratio exactly.
- *type*: PROVED
- *artifact*: `research/math-paper/results/proof_audit.json`
- *commit*: `HEAD`
- *source*: `research/math-paper/proof_audit.py; csia/diagnosis/bayes.py CAUSES`
- *baseline*: Any tick where phys_gps is active: the pair is distinguishable and the ratio moves.
- *counter-evidence*: None. The identity is verified symbolically and to 8.882e-16 numerically.
- *alternative explanation*: The posterior could be pinned for a numerical reason rather than a structural one. Excluded: the symbolic check holds for arbitrary positive priors and likelihoods.

**`SC-03` — PROVED**

- *statement*: An independent structural checker, importing no CSIA module and no part of the support-aware implementation, agrees with the production discriminating-term analysis on 378,000 of 378,000 tick-by-pair comparisons.
- *type*: MEASUREMENT
- *artifact*: `research/systems-paper/results/checker_agreement.json`
- *commit*: `HEAD`
- *source*: `research/systems-paper/independent_checker.py; engineering/v1_1/support/decompose.py`
- *baseline*: Production analysis: engineering/v1_1/support/decompose.py Decomposition.discriminating (numeric, |delta| > tau).
- *counter-evidence*: One disagreement class exists in theory (c == 0.5 makes the two definitions differ) and was NOT observed: 0 degenerate cases in 378,000.
- *alternative explanation*: Agreement could be circular if the checker read production's answer. Excluded: the checker's only inputs are the committed signature YAML and an active-set export that carries no support analysis, and a test asserts no csia module is imported.

**`SC-07` — EMPIRICAL_ONLY**

- *statement*: Smoothing changes threshold-crossing behaviour, and the direction and size of the change depend on the arm.
- *type*: MEASUREMENT
- *artifact*: `research/systems-paper/results/mechanism_b.json`
- *commit*: `HEAD`
- *source*: `research/systems-paper/mechanism_b.py; csia/prediction/comparator.py`
- *baseline*: Clean arm with no fault injected, same flight profile.
- *counter-evidence*: On the clean arm the SAME threshold is crossed by both series, so the 'latency' there is a false alarm, not a detection. Reported.
- *alternative explanation*: Smoothing could simply add lag. Partly true: the lag is +0.12 s (slow ramp), +0.08 s (3 m/s spoof), +0.04 s (fast ramp) - it SHRINKS as the fault gets faster, which lag alone does not explain.

**`SC-22` — PROVISIONAL**

- *statement*: A public-log exposure study over PX4 Flight Review logs.
- *type*: PROVISIONAL
- *artifact*: `NONE - NOT RUN`
- *commit*: `n/a`
- *source*: `n/a`
- *baseline*: n/a
- *counter-evidence*: n/a
- *alternative explanation*: BLOCKED: review.px4.io and logs.px4.io are denied by this environment's egress policy (403 at CONNECT). No data was downloaded and no result exists. The plan is committed; the study is not done.

**`SC-24` — EMPIRICAL_ONLY**

- *statement*: Mechanism B replicates on ArduPilot 4.8: given the platform's own measured banked state and measured per-tick evidence and forgetting factor, the source recursion reproduces the runtime trust trajectory and predicts the observed threshold crossing.
- *type*: EMPIRICAL_ONLY
- *artifact*: `research/v1_1/results/current_stack_replication.json`
- *commit*: `HEAD`
- *source*: `csia/trust_engine/engine.py; tools/deploy/mechanism_b_campaign.py`
- *baseline*: CLEAN, STEP_SMALL and STEP_LARGE arms, 15 trials, all predeclared as non-crossing.
- *counter-evidence*: None. 20/20 trials valid; reconstruction error 1.0e-15 to 2.0e-15 against a 1e-6 tolerance; crossing error 0 ticks on all 5 ramps; 0/5 control crossings.
- *alternative explanation*: The crossing tick differs from the 2015 ArduCopter 3.3 figure because the banked state differs. That is expected and predeclared: the mechanism replicates, not the number. Testing against 93.31 ticks would have produced a false non-replication.

**`SC-26` — EMPIRICAL_ONLY**

- *statement*: On 15,595 ticks from 20 real ArduPilot 4.8 SITL trials in which the GNSS fix was never lost, the structural predicate reports the nominal|gps_fault pair DISTINGUISHABLE at every tick and never collapses.
- *type*: MEASUREMENT
- *artifact*: `research/systems-paper/results/current_stack_structural.json`
- *commit*: `HEAD`
- *source*: `research/systems-paper/current_stack_structural.py; research/v1_1/results/mechanism_b_gps/ticks/`
- *baseline*: The bench catalogue, where the same predicate DOES collapse for 200 ticks under injected fix loss.
- *counter-evidence*: None. 0 gate-closed ticks and 0 collapses across CLEAN (5100), RAMP (887) and STEP (9608).
- *alternative explanation*: This is a NEGATIVE CONTROL, not a replication of self-occlusion. Self-occlusion needs a fault that removes the fix, and no fix-loss arm exists on ArduPilot 4.8 in this repository. The trials are fix-preserving by their own validity criterion, so they CANNOT exhibit it, and none is claimed.

---

## 3. Mechanism A — complete record

**What it is.** Under sustained GNSS fix loss the diagnosis reports
`nominal` for the whole fault window and never names `gps_fault`.

| field | value | source |
|---|---|---|
| fault / scenario | GNSS denial (fix loss), injected | `research/wp_c4/self_occlusion_experiment.py` |
| platform | bench simulator, `csia/scenarios.py` pipeline | — |
| autopilot version (Phase-I baseline) | ArduCopter 3.3 SITL, dronekit-assets prebuilt 2015-10-22 | `phase_guard.py` baseline `848f556` |
| CSIA freeze | v1 core at `csia-v1.0-research-final`, zero diff | `tests/test_v1_frozen.py` |
| sampling | 25 Hz | `constants_from_source/tick_hz` in `escalation_algebra.json` |
| leader hypothesis | `nominal` | checker verdicts |
| leader normalized hypothesis weight | 0.9767 GPS **trust** during denial; leader weight up to 0.999822 at collapsed ticks | `research/wp_c4/results/self_occlusion.json`, `engineering/v1_1/SUPPORT_STATE_RESULTS.csv` |
| gate state | `gvalid` CLOSED (receiver reports no valid fix) | `csia/prediction/comparator.py` |
| discriminating evidence count | **0** for `(nominal, gps_fault)` while the gate is shut | `checker_verdicts.json` |
| support state | `NON_IDENTIFIABLE` | `SUPPORT_STATE_RESULTS.csv` |
| ambiguity state | `AMBIGUOUS` | same |
| first support-collapse | tick 0 of every scenario (76-tick smoother warm-up) | `checker_verdicts.json` |
| collapse under injected fix loss | **200 consecutive ticks** = 8.0 s at 25 Hz — exactly the injected window | same |
| recovery | when the fix returns and `gvalid` reopens | same |

### The source-code mechanism

- **Hypothesis pair**: `(nominal, gps_fault)`.
- **Distinguishing relation**: `phys_gps`, the GNSS internal-physics
  consistency check (position-derivative versus Doppler velocity).
- **Where the signature is defined**: `research/formalization/diagnostic_signature_matrix.yaml`,
  and `csia/diagnosis/bayes.py` `CAUSES` (the frozen v1 core).
- **Gate that suppresses it**: `gvalid`, which closes when the receiver
  reports no valid fix.
- **Exact code path**: `csia/diagnosis/bayes.py`, the scoring loop —
  `for fname, (c, gate) in features.items(): if gate <= 1e-9: continue`.
  A gated feature is **skipped**, not down-weighted, so it contributes
  nothing to any hypothesis.
- **Commit**: frozen at `ec5acd189295dab9259d4989657d42184d6142a3`.

### What is proved structurally versus merely empirical

| | |
|---|---|
| **STRUCTURAL (`SC-02`, PROVED)** | with `phys_gps` gated out, no active feature distinguishes `nominal` from `gps_fault`. This follows from the signature table and the gate alone. It is `D(a,b) = (LOW(a) △ LOW(b)) ∩ ACTIVE = ∅` and is decidable before the system runs |
| **EMPIRICAL (`SC-01`, `SC-04`–`SC-06`)** | that the pair is the *only* one of 28 that ever collapses; the 76-tick startup window; the 200-tick fault window; the 0.9767 trust reading. All are measurements on this catalogue |

---

## 4. Independent structural checker

| field | value |
|---|---|
| path | `research/systems-paper/independent_checker.py` |
| comparison driver | `research/systems-paper/compare_checker_vs_production.py` |
| production side | `engineering/v1_1/support/decompose.py` `Decomposition.discriminating` (numeric, `|delta| > tau`) |
| **tick-by-pair comparisons** | **378,000** |
| **agreements** | **378,000** |
| **real disagreements** | **0** |
| degenerate-only cases | 0 |
| verdict | `CHECKER_AGREES_WITH_PRODUCTION` |
| `tau_num` | 1e-12 |
| `gate_eps` | 1e-09 |
| commit | `50c5d3576e9084e7c2789167628392c5de992b6f` |

**VERIFIED: 378,000 / 378,000 is correct.** 9 scenarios x 1500 ticks x 28
unordered pairs = 378,000.

### Implementation philosophy

The checker exists so the collapse claim is not an artifact of the analysis
pipeline that produced it. It evaluates the structural predicate **directly
from the committed configuration**, and shares no code with production.

- **imports**: Python standard library and `yaml`, nothing else.
- **does NOT import**: `csia.diagnosis.bayes`, `engineering/v1_1/support/support.py`,
  `engineering/v1_1/support/decompose.py` — or any CSIA module at all. A test
  runs it in a fresh interpreter and asserts no diagnostic module appears in
  `sys.modules` afterwards.
- **inputs**: the committed signature table
  (`research/formalization/diagnostic_signature_matrix.yaml`) and a per-tick
  record of which features were active
  (`research/systems-paper/results/active_sets.json`). Its input carries **no
  leader, no weight and no support label**.

### Algorithm, sufficient to write Methods without the repository

```
for each scenario, for each tick k:
    ACTIVE <- set of feature names with gate > gate_eps at tick k
    for each unordered pair (a, b) of the 8 hypotheses:
        D <- (LOW(a) symmetric-difference LOW(b)) intersect ACTIVE
        checker_says_distinguishable <- (D is non-empty)
        production_says_distinguishable <- (production |delta| > tau_num)
        if the two agree:                       count agreement
        elif consistency == 0.5 exactly:        count degenerate_only
        else:                                   count real_disagreement
```

`LOW(h)` is the set of features hypothesis `h` drives low, read from the
signature table.

### The one known disagreement class, predicted before the comparison

> c == 0.5 makes log(1-c+eps) == log(c+eps), so a structurally distinguishing term contributes zero numeric difference. Counted separately as `degenerate_only`, never as agreement.

It occurred **0 times**.

### What the result establishes, and what it cannot

- **Establishes**: the collapse is not an artifact of the production analysis
  pipeline. Two implementations sharing no code reach the same verdict every
  time.
- **Cannot establish**: that the signature table is right. Both sides read
  `LOW(h)` from the same committed configuration, so a table that misdescribes
  what the features measure would be misdescribed identically 378,000 times.
  **The paper says this explicitly and must keep saying it.**

---

## 5. Current-stack negative control

| field | value |
|---|---|
| artifact | `research/systems-paper/results/current_stack_structural.json` |
| generator | `research/systems-paper/current_stack_structural.py` |
| source ticks | `research/v1_1/results/mechanism_b_gps/ticks` |
| **total ticks** | **15,595** |
| **trials** | **20** |
| **gate-closed ticks** | **0** |
| **pair-not-distinguishable ticks** | **0** |

### Decomposition — VERIFIED

| condition | trials | ticks | gate-closed | collapses |
|---|---|---|---|---|
| `CLEAN` | 5 | 5,100 | 0 | 0 |
| `RAMP` | 5 | 887 | 0 | 0 |
| `STEP` | 10 | 9,608 | 0 | 0 |
| **total** | **20** | **15,595** | **0** | **0** |

5,100 + 887 + 9,608 = 15,595. 5 + 5 + 10 = 20. Both check.

- **Selection rule**: every tick of every trial in the preregistered
  ArduPilot 4.8 Mechanism-B campaign.
- **Validity condition**: the campaign's own criterion was that the **GNSS fix
  is never lost**. That is why the fix remains present throughout.
- **Structural prediction**: with the fix present, `gvalid` stays open,
  `phys_gps` stays active, `D(nominal, gps_fault)` is non-empty at every tick,
  and the predicate must report the pair **distinguishable everywhere**.
- **Observed**: 0 collapses in 15,595 ticks.

**THIS IS A NEGATIVE CONTROL. IT IS NOT A FIX-LOSS REPLICATION.** No fix-loss
arm exists on that platform in our data, so the mechanism itself was not
reproduced there — only its prediction in the fix-present regime.

**What would have falsified the structural account**: a single collapse tick
with the fix present. The predicate depends only on the signature table and the
gate; if it had reported the pair indistinguishable while `phys_gps` was
active, either the table or the account of the gate would be wrong. It did
not.

---

## 6. Current-stack replication — the canonical table

This table resolves the "bench-only versus ArduPilot 4.8 replicated"
contradiction. **Both statements were true of different things.**

| mechanism | platform | version | scenario | status | artifact |
|---|---|---|---|---|---|
| **A** (self-occlusion) | bench simulator | `csia/scenarios.py` | GNSS denial | **MEASURED** | `research/wp_c4/results/self_occlusion.json` |
| **A** | ArduPilot | 4.8 SITL | fix loss | **NOT RUN** — `SC-23` is `PROVISIONAL` | — |
| **A** (predicate only) | ArduPilot | 4.8 SITL | fix-preserving trials | **NEGATIVE CONTROL**, 15,595 ticks, 0 collapses | `current_stack_structural.json` |
| **A** | PX4 | current | — | **NOT RUN** | — |
| **B** (threshold-crossing persistence) | bench simulator | `csia/scenarios.py` | 4 ramp arms | **MEASURED** | `research/systems-paper/results/mechanism_b.json` |
| **B** | ArduPilot | 4.8 SITL | 5 ramps, preregistered | **REPLICATED** — 20/20 valid, trajectory reconstruction error 1.0e-15 to 2.0e-15 against a 1e-6 tolerance, crossing error **0 ticks** on all five ramps, 0/5 control crossings | `research/v1_1/CURRENT_STACK_REPLICATION.md` |
| **B** | PX4 | SIH | — | **INAPPLICABLE** — no fix-preserving GNSS offset exists there; four source routes checked; substitution forbidden, so zero trials run | same |

The campaign verdicts recorded in the artifact itself:
`ardupilot = REPLICATED`,
`px4 = INAPPLICABLE`.

**How to state it in the paper.** Mechanism B replicates on a current
autopilot. Mechanism A does not have a current-stack replication; what it has
is a negative control that would have falsified it and did not. Conflating the
two is the error this table exists to prevent.

---

## 7. Mechanism B — final detector-level numbers

Four arms on the `hover_circle` profile, GPS drift injected at t = 20.0 s for
15.0 s. Thresholds all inherited: trust 0.75 (`FailsafeConfig.nav_caution`),
lambda mu0+3sigma0 = 1.8118, CUSUM k = 0.5 / h = 500.

| arm | ramp | trust, raw | policy dwell | **trust, detector only** | **CUSUM** | ground truth |
|---|---|---|---|---|---|---|
| `slow_ramp` | 1.0 m/s | 8.72 | 1.0 | **7.72** | **2.96** | faulted |
| `spoof_3ms` | 3.0 m/s | 3.36 | 1.0 | **2.36** | **1.16** | faulted |
| `fast_ramp` | 6.0 m/s | 3.24 | 1.0 | **2.24** | **0.72** | faulted |
| `clean` | none | **none** | — | **none** | **none** | **CLEAN — any crossing is a false alarm** |

**VERIFIED: 7.72 vs 2.96, 2.36 vs 1.16, 2.24 vs 0.72 are all correct**, and
they are the detector-to-detector figures.

### Values that MUST NOT be quoted, and why

| value | why it must not be quoted alone |
|---|---|
| trust 8.72 s against CUSUM 2.96 s | this is **detector-plus-policy against detector**. The failsafe requires `dwell_up = 1.0 s` of persistence; the CUSUM has no dwell. Quoting the raw pair flatters the CUSUM by one dwell period. Red-team objection 2.3 identified this; **quote 7.72 against 2.96** and say the 8.72 includes the dwell |
| the `clean` arm's lambda crossings (2.92 s instantaneous, 24.88 s smoothed) | **these are FALSE ALARMS, not latencies.** The clean arm has no fault. The artifact carries `ground_truth_faulted: false` and `crossings_are_false_alarms: true` on that row so the numbers cannot be lifted out of context |
| the bare lambda threshold as a detector | it fires 36 times in 374 clean pre-onset ticks. It is a diagnostic device for putting both series in the same units, not a threshold the system uses |

### What Mechanism B demonstrates, and what is prior art

- **Demonstrated**: on this deployed layer, with these frozen constants,
  accumulation reaches an alarm at 2.96 s on a 1 m/s ramp against 7.72 s for
  the trust path's detector alone, while adding zero clean-flight false alarms.
  Smoothing costs +0.12 s at 1 m/s, +0.08 s at 3 m/s, +0.04 s at 6 m/s — a
  shrinking cost, not a fixed lag. Smoothing buys a 4x reduction in false
  crossings (36 -> 9 over 374 pre-onset ticks).
- **Prior art, claimed as KNOWN (`SC-10`)**: the detector is Page's 1954
  one-sided CUSUM, labelled as prior art inside `csia/v1_1/sequential.py`'s own
  docstring. `k = 0.5` is textbook. `h = 500` was fixed by a zero-clean-alarm
  rule on a grid before these arms existed, and the textbook `h = 5.0` is
  retained as a committed **negative** result (2681 clean alarm ticks).
- **NOT claimed as novel**: CUSUM, sequential change detection, cumulative
  innovations, sequential monitoring. `PRIOR_ART_MATRIX.csv` row `Page 1954`
  carries status `KNOWN`.

### Limits to state with the result

- Four arms, one flight profile, one node (`gps` only). The CUSUM bank has no
  residual for `imu0`, `imu1` or `baro` at all (`sequential.py` `NO_RESIDUAL`),
  so "no alarm" must never be read as "no fault" for those nodes.
- Bench simulator, not a real autopilot. The current-stack question is
  answered separately by the preregistered campaign in §6.
- Ground truth is the injection schedule. That is what makes the false-alarm
  counts meaningful, and it is why the same counts cannot be produced on
  public logs.


---

## 8. The escalation-delay decomposition — the 118.82 chain, settled

The systems-paper agent challenged the earlier explanation. **The challenge was
correct**; the earlier explanation was wrong, and the manuscript value was
right. Full chain:

| quantity | value | source | interpretation | canonical? |
|---|---|---|---|---|
| `S_0` | **475.6775** | `/verification_against_shipping_trustcore/settled_mass_S0` | **MEASURED settled Beta mass** | **YES** |
| `S_0` (cap) | 500.0 | `/…/concentration_cap_1_over_1_minus_rho_max` | theoretical `1/(1-rho_max)`; the mass never reaches it | no |
| `T_0` | **0.999791** | `/…/settled_trust_T0` | **MEASURED settled trust** | **YES** |
| `T_0` = 1.0 | 1.0 | script docstring only | idealised | no |
| `T_0` = 0.98764 | — | **NOWHERE** | see below | **NO** |
| `T*` | 0.75 | `FailsafeConfig.nav_caution` | `nav_caution` threshold | **YES** |
| `e_f` | 0.7 | `/evidence_asymptote_e_f` | evidence floor: gating out `w_phys = 0.30` leaves 0.70 | **YES** |
| `rho` | 0.95 | `/…/rho_observed` | at `rho_min`, spread `d = 1` | **YES** |
| `M = 1/(1-rho)` | 20.0 | derived | fault-phase mass | **YES** |
| **mass term** `S_0(T_0-T*)` | **118.82** | `/what_dominates_N_star/mass_term_S0_times_T0_minus_Tstar` | banked agreement | **YES — quote this** |
| margin term `M(T*-e_f)` | 1.0 | `/what_dominates_N_star/margin_term_…` | evidence margin | **YES** |
| `N*` | 93.31 ticks = 3.732 s | `/ticks_required_N_star` | predicted crossing | **YES** |
| observed crossing | tick 94 | `/…/first_tick_at_or_below_threshold` | shipping code | **YES** |
| max abs error vs eq. (1) | 0.0 | `/…/max_abs_error_vs_equation_1` | closed form matches shipping code exactly | **YES** |

### The formula

```
equation (1):  T_N = (x S_0 T_0 + (1-x) M e_f) / (x S_0 + (1-x) M),  x = rho^N, M = 1/(1-rho)
equation (2):  N*  = ln( M(T*-e_f) / (S_0(T_0-T*) + M(T*-e_f)) ) / ln(rho)
```

Artifact: `research/wp_c8/results/escalation_algebra.json`.
Generator: `research/wp_c8/escalation_algebra.py`.

### Every candidate value, recomputed independently with `Decimal`

| expression | value | what it is |
|---|---|---|
| `500 x (1.0 - 0.75)` | **125.00** | the generating script's DOCSTRING illustration, using the theoretical cap and an idealised `T_0` |
| `475.6775 x (1.0 - 0.75)` | **118.919375** -> 118.92 | measured `S_0`, idealised `T_0`. In no artifact |
| **`475.6775 x (0.999791 - 0.75)`** | **118.8199584025** -> **118.82** | **BOTH MEASURED. CANONICAL** |
| `475.6775 x (0.98764 - 0.75)` | 113.040001100 -> 113.04 | measured `S_0` with the bogus `T_0` |
| `500 x (0.98764 - 0.75)` | **118.82000** | **the coincidence that produced the error** |

### Answers to the brief's twelve questions

| | answer |
|---|---|
| **A. exact `S_0`** | `475.6775` (measured settled mass). **Not 500** |
| **B. exact `T_0`** | `0.999791` (measured settled trust). **Not 1.0, not 0.98764** |
| **C. exact `T*`** | `0.75` |
| **D. formula** | `S_0 (T_0 - T*)`, the numerator's mass term in equation (2) |
| **E. artifact** | `research/wp_c8/results/escalation_algebra.json` |
| **F. key** | `/what_dominates_N_star/mass_term_S0_times_T0_minus_Tstar` |
| **G. computed value** | `118.8199584025`, reported as `118.82` |
| **H. where 125 came from** | `research/wp_c8/escalation_algebra.py` module docstring: *"against S_0(T_0 - T*) = 500 * 0.25 = 125"*. A pedagogical illustration at the idealised cap. The manuscript had transcribed it as a result |
| **I. does 125 exist in a committed artifact?** | **In no RESULT artifact.** It exists in the generating script's docstring. An earlier report said "no artifact", which was imprecise |
| **J. does 0.98764 refer to a different variable?** | **NO. It refers to nothing.** It was back-solved from `118.82/500 + 0.75` and reproduces 118.82 only because `500 x 0.23764 = 118.82` exactly. An arithmetic coincidence presented as a measurement |
| **K. current manuscript value** | `118.82` at `papers/csia_systems/main.tex:892` — **CORRECT** |
| **L. current claim-ledger value** | scalar `S13` in `PAPER1_ARTIFACT_MAP.yaml`, value `"118.82"` — **CORRECT**. `publication/system_paper_i/evidence_export/05_ESCALATION_RESULT.md` also already carried 118.82 |

### **SCIENTIFIC RESULT UNCHANGED.**

The manuscript is correct and was corrected once, from the docstring's 125 to
the artifact's 118.82. Only the *explanation* of the provenance was wrong, in
two places, both of which are documentation:

- `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` scalar `S13` note — corrected;
- `tests/test_systems_paper_numeric_claims.py` module docstring — corrected,
  and a new test now pins `S_0` and `T_0` themselves rather than only their
  product, because pinning the product could not catch either wrong story.

The wrong explanation also appears in two immutable git commit messages
(`eb2577d`, and the CHANGELOG entry under "Unreleased 2026-09"). Those are
historical record and are not rewritten; this document is the correction.

---

## 9. Historical Monte Carlo limitation

**Confirmed by direct measurement at HEAD.**

| | |
|---|---|
| function | `csia.sensors.truth.generate_flight(duration, dt, seed, profile)` |
| truth fields compared | **12** (every field of `FlightTruth`) |
| seeds checked | **6** — `0, 1, 7, 2**31-1, None, 999999`, against a `seed=42` base |
| differing fields | **0** |
| byte-identical across every seed | **YES** |
| profiles checked | both `hover_circle` and `fast_cruise` |

The scripted truth is a closed-form function of `t` with no noise term, so
`seed` cannot affect it. Sensor noise is applied downstream in `csia/sensors`,
which is where a seed does do something.

**The defect.** `csia/validation.py` `monte_carlo()` drew a fresh seed per trial
and passed it to `generate_flight`, which reads as per-trial flight
randomization and is not one. **All 150 runs of the committed campaign flew the
same trajectory.**

| varies across the campaign | does NOT vary |
|---|---|
| fault class (5 classes) | **the flight trajectory** |
| amplitude scale, `uniform(0.5, 2.0)` | the flight profile |
| onset time, `uniform(15.0, 35.0)` | duration, dt, sampling |
| the clean/faulted split, `p = 0.4` | — |

**No numerical campaign artifact changed.** `campaigns/monte_carlo.json` was
regenerated before and after the fix and is bit-identical both times. The
stream draw was deliberately RETAINED as a bare expression, because `rng` is a
single stream and dropping a draw would shift every subsequent
`rng.random()` and `rng.uniform()`.

### Manuscript statements to check and correct

Search the manuscript for any wording implying independent flights,
flight-to-flight variability, or a Monte Carlo over trajectories. Corrected
wording to use:

> The campaign randomizes fault class, amplitude, onset and the clean/faulted
> split over a **single fixed trajectory**. Every confidence interval it
> reports is conditioned on that trajectory, and none of them is a statement
> about flight-to-flight variability.

`tests/test_flight_truth_determinism.py` pins the behavioural property, the
structural property (no RNG call inside `generate_flight`, by AST), that no
caller passes `seed=`, and that the stream draw survives.

---

## 10. Public-log study

| | |
|---|---|
| plan | `research/systems-paper/PUBLIC_LOG_STUDY_PLAN.md` |
| preregistration status | **committed and preregistered** |
| claim | `SC-22`, status **PROVISIONAL** |
| required for submission? | it is submission gate 5 in `docs/CURRENT_PROGRAM_STATE.md` §3, currently **BLOCKED** |
| run? | **NO** |
| why not | `review.px4.io` and `logs.px4.io` are denied by egress policy (403 at CONNECT) |
| re-tested this session? | the same proxy denies every external host tested; no route exists from here |

**NOT RUN, and not runnable from this environment.** The plan is committed so
that a host with egress can execute it unchanged. Nothing was substituted for
it, and `SC-22` remains `PROVISIONAL` rather than being quietly dropped.

---

## 11. Strict numeric audit — the 49 unmapped prose literals

`make artifact-map --strict-numbers` reports these as present in the manuscript
prose and not individually bound to an artifact. **The list is informational**:
54 further literals live inside mapped tables and are already covered.

The writing agent decides which of these are scientific results needing
artifact binding. Classification hints: version numbers (`3.3`, `4.8`),
equation constants (`1.5`, `0.85`), section/list numerals, and worked examples
do not need binding; measured quantities do.

| # | literal | line | context |
|---|---|---|---|
| 1 | `0` | 35 | \code{gps\_fault}, while the GPS trust coefficient reads 0.9767. The vehicle is |
| 2 | `0.000` | 315 | $\kappa(S) = 0.000$ over 8 classes, and |
| 3 | `0.001597` | 587 | both) while the GPS channel's fresh fraction falls from 1.0 to 0.001597. The |
| 4 | `0.006` | 804 | small: reported horizontal position variance rises from about 0.006 to between |
| 5 | `0.0127` | 728 | with a between-site standard deviation of 0.0127\,rad against a within-site |
| 6 | `0.0227` | 677 | $p = 0.0227$, while the failsafe reaches CAUTION at $t = 61.5$\,s through the |
| 7 | `0.066` | 1260 | target hypothesis falls by 0.066, because a larger LOW set requires more features to |
| 8 | `0.088` | 785 | $q_{\mathrm{gvalid}}$ of 0.088, 0.208 and 0.609 over the fixed 25\,s window, |
| 9 | `0.143` | 316 | $\kappa(S_{\mathrm{eff}}) = 0.143$ over 7 classes, the merged pair being |
| 10 | `0.159` | 733 | a vehicle commanded to hold position tilts $0.159^\circ$ at 0\,m/s and |
| 11 | `0.208` | 785 | $q_{\mathrm{gvalid}}$ of 0.088, 0.208 and 0.609 over the fixed 25\,s window, |
| 12 | `0.609` | 785 | $q_{\mathrm{gvalid}}$ of 0.088, 0.208 and 0.609 over the fixed 25\,s window, |
| 13 | `0.640319` | 586 | bit-identical between the two runs (mean 0.9155, min 0.640319, max 1.0 in |
| 14 | `0.678` | 901 | measured floor ranges 0.678 to 0.700. |
| 15 | `0.697` | 979 | cruise and descent gives minimum trust 0.697, 0.735 and 0.744; only the climb |
| 16 | `0.700` | 901 | measured floor ranges 0.678 to 0.700. |
| 17 | `0.7000` | 882 | saturated cells of the sweep: \textbf{0.7000}. |
| 18 | `0.717` | 844 | applied as a 5, 20 or 60\,s ramp does alarm, with minimum trust 0.717 to 0.723 |
| 19 | `0.723` | 844 | applied as a 5, 20 or 60\,s ramp does alarm, with minimum trust 0.717 to 0.723 |
| 20 | `0.735` | 979 | cruise and descent gives minimum trust 0.697, 0.735 and 0.744; only the climb |
| 21 | `0.744` | 979 | cruise and descent gives minimum trust 0.697, 0.735 and 0.744; only the climb |
| 22 | `0.906` | 691 | The layer did not use it. GPS trust fell only to 0.906--0.934 against a |
| 23 | `0.9155` | 586 | bit-identical between the two runs (mean 0.9155, min 0.640319, max 1.0 in |
| 24 | `0.934` | 691 | The layer did not use it. GPS trust fell only to 0.906--0.934 against a |
| 25 | `0.977` | 676 | same window reports \code{nominal} at $p = 0.977$ with \code{gps\_fault} at |
| 26 | `0.981` | 648 | \code{link loss} & 3744 & 3672 & \textbf{0.981} & satellites 9.93 $\to$ 0.17 \\ |
| 27 | `0.982` | 781 | $q_{\mathrm{gvalid}}$ of 0.984, 0.984, 0.984 and 0.982, with first closure |
| 28 | `0.9997` | 693 | diagnosis stayed at \code{nominal} $p = 0.9997$. \textbf{That is a different |
| 29 | `0.9998` | 1409 | $0.9998$ with no evidence distinguishing it from its nearest rival carries no |
| 30 | `1.0` | 586 | bit-identical between the two runs (mean 0.9155, min 0.640319, max 1.0 in |
| 31 | `1.000` | 485 | 5 & \textbf{0.0000} & \textbf{0.000} & \textbf{0.1429} & \textbf{1.000} \\ |
| 32 | `1.2` | 805 | 1.2 and 1113, scaling with glitch size. And neither half would have explained |
| 33 | `1.48` | 1139 | \item Onset of a non-healthy status moves from 1.48\,s to \textbf{0.44\,s} |
| 34 | `1.5` | 248 | followed by exponential smoothing with $\alpha_s = 0.06$, tempering by 1.5, |
| 35 | `1.56` | 1140 | under denial and 1.56\,s to 0.52\,s under link loss. The abstention is |
| 36 | `12.3` | 900 | at $+0.7$ and $-12.3$ ticks, and the model assumes a constant $e_f$ where the |
| 37 | `16.67` | 1171 | at $1/\alpha_s = 16.67$ frames. |
| 38 | `2.4` | 463 | this system averages 2.4 features per hypothesis, and \code{gps\_fault} has |
| 39 | `22.3` | 820 | 22.3 & 0.9089 & 0.0000 & 32 & no \\ |
| 40 | `222.6` | 822 | 222.6 & 0.9061 & 0.0000 & 33 & no \\ |
| 41 | `3.3` | 1355 | named.} Every measurement in this paper is against \textbf{ArduCopter 3.3 |
| 42 | `3.7` | 888 | \right)}{\ln \rho} \approx 93 \text{ ticks} = 3.7\,\text{s} |
| 43 | `4.8` | 1366 | frozen before its first trial, on \textbf{ArduPilot 4.8} SITL: twenty valid |
| 44 | `5.71` | 1147 | policies return to health after 5.71\,s, the failsafe's own de-escalation |
| 45 | `5.9` | 729 | standard deviation of $5.9 \times 10^{-5}$\,rad, measured by flying one site |
| 46 | `556.6` | 978 | \paragraph{Flight phase.} Injecting the same 556.6\,m 4\,s ramp during climb, |
| 47 | `61.5` | 677 | $p = 0.0227$, while the failsafe reaches CAUTION at $t = 61.5$\,s through the |
| 48 | `84.4` | 377 | \code{nominal} on top & 33.5\% & \textbf{100\%} & 84.4\% \\ |
| 49 | `93.3` | 905 | 200 ticks, and the predicted crossing at 93.3 ticks against an observed |

**Already audited by hand this session and confirmed against their artifacts**:
`0.001597`, `0.640319`, `0.9155` (temp_gps escape); `0.0227`, `61.5` (denial
flight); `5.71` (recovery); `93.3`, `+0.7`, `-12.3` (escalation boundary);
`22.3`, `222.6` (magnitude sweep). One was wrong — the `125` now corrected to
`118.82` — and is bound as `S13`.

---

## 12. Bibliography — 11 entries, 0 verified

**Every entry is UNVERIFIED. `make bib-guard` fails, correctly.** 37 provenance
markers across `papers/csia_systems/refs.bib`.

Six verification routes tested from this environment; all six return HTTP 403
at CONNECT: `api.crossref.org`, `doi.org`, `dblp.org`, `api.openalex.org`,
`api.semanticscholar.org`, `export.arxiv.org`. The last three are
`rejected_routes` in the ledger and could not have retired a marker even on
success.

| key | status | risk |
|---|---|---|
| `dong2024statedependent` | UNVERIFIED | confirm only — All numeric fields supplied by the WP-C6 brief; the title rendering was not independently confirmed. Cited in the related-work section, where the paper concedes priority over the general mechanism -- so a wrong attribution here would misdir |
| `carvalho2012intermittent` | UNVERIFIED | confirm only — Complete except that no DOI was supplied, so bib-verify cannot key on one. |
| `carvalho2013permanent` | UNVERIFIED | confirm only — Complete with a DOI; needs confirmation only. |
| `takai2021diagnosability` | UNVERIFIED | **HIGH** — Title is a literal VERIFY placeholder here. A search-derived CANDIDATE exists in BIB_VERIFICATION_CANDIDATES.md finding 2; it was NOT copied into this file, because a candidate is not a verification. |
| `yin_phidiagnosability` | UNVERIFIED | **HIGH** — THE WEAKEST ENTRY IN EITHER FILE, and now searched TWICE without a match -- once for the reconstructed title, once for uniform phi-diagnosability attributed to Yin, Gao and Li under state-dependent observation. An unsuccessful search is not |
| `krysander2024multimode` | UNVERIFIED | **HIGH** — Title is a placeholder. Candidate in BIB_VERIFICATION_CANDIDATES.md finding 3, including a possible OASIcs volume number the entry lacks. |
| `krysander2008sensorplacement` | UNVERIFIED | confirm only — Complete with a DOI; needs confirmation only. |
| `hurdle2007faulttree` | UNVERIFIED | **HIGH** — APPEARS TO CONFLATE TWO DIFFERENT PAPERS, and unlike kang2024gnss this one IS cited by main.tex. The title matches a 2009 Reliability Engineering & System Safety paper; the journal, volume, pages, year and DOI prefix all match a 2007 Proc.  |
| `reeves2019sensorselection` | UNVERIFIED | **HIGH** — Title is a placeholder. Candidate in BIB_VERIFICATION_CANDIDATES.md finding 4; every numeric field already matches it. |
| `kang2024gnss` | UNVERIFIED | **HIGH** — PROBABLY FILED UNDER THE WRONG SUBJECT. It sits under a GNSS integrity heading, but a search for its DOI returns a discrete-event-systems sensor-attack paper (BIB_VERIFICATION_CANDIDATES.md finding 1). It is also UNCITED by main.tex. Verify |
| `blanke2003ftc` | UNVERIFIED | **HIGH** — Reconstructed. TWO later editions exist, not one: 1st 2003 (Springer Berlin, 571 pp), 2nd 2006, 3rd 2015 (DOI 10.1007/978-3-662-47943-8). year = 2003 is a real 1st-edition year; the publisher location and the edition number are the missing  |

### The four the brief asks about

| key | exact state |
|---|---|
| **`hurdle2007faulttree`** | **APPEARS TO CONFLATE TWO DIFFERENT PAPERS**, and unlike `kang2024gnss` it **IS cited by `main.tex`**. The title matches a 2009 *Reliability Engineering & System Safety* paper while the entry is filed as 2007. **Unsafe to cite as written** |
| **`blanke2003ftc`** | RECONSTRUCTED. **Three editions exist, not one**: 1st 2003 (Springer Berlin, 571 pp), 2nd 2006, 3rd 2015 (DOI 10.1007/978-3-662-47943-8). `year = 2003` must be checked against the edition actually intended. **EDITION_AMBIGUOUS** |
| **`yin_phidiagnosability`** | **THE WEAKEST ENTRY IN EITHER FILE.** Searched twice without a match — once for the reconstructed title, once for uniform phi-diagnosability attribution. **NOT_FOUND** |
| **`kang2024gnss`** | **PROBABLY FILED UNDER THE WRONG SUBJECT.** It sits under a GNSS-integrity heading, but a search for its DOI returns a discrete-event-systems sensor-attack paper. **WRONG_SUBJECT.** Mitigating: it is **not cited by `main.tex`** |

Three further entries carry literal `VERIFY` placeholder titles:
`takai2021diagnosability`, `krysander2024multimode`, `reeves2019sensorselection`.
Search-derived candidates exist in `papers/csia_systems/BIB_VERIFICATION_CANDIDATES.md` and
were deliberately **not** copied into `refs.bib`, because a candidate is not a
verification.

**Rule the writing agent must not break.** Deleting a marker to make the guard
pass is falsification. `papers/BIB_VERIFICATION_LEDGER.yaml` plus
`tests/test_bib_verification_ledger.py` make it mechanically detectable: an
entry with no marker must carry a `VERIFIED` row with an accepted route, a
named checker, a date and the record consulted.


---

## 13. Red team — objections that remain unresolved

`research/systems-paper/REVIEWER_RED_TEAM.md`, four reviewers, eleven
objections: 7 answered, 1 CLOSED by correction, 3 that cannot be answered from
this environment and are now stated in the manuscript itself.

| # | objection | state |
|---|---|---|
| 1.1 | "your baseline is an autopilot from 2015" | **answered, weakness remains**: the paper cannot show the 4.8 result without breaking its own phase guard, so the referee must take §Limitations' word for it |
| 1.2 | "the vehicle was never actually in danger" | **conceded in the abstract**. Remaining weakness: no evidence that a misattribution ever cost anything operationally, and the paper cannot supply it |
| 2.3 | CUSUM-vs-trust compares detector against detector-plus-policy | **CLOSED BY CORRECTION** — the objection was right, the dwell decomposition was computed, and the conclusion survived. Quote 7.72 vs 2.96 |
| 3.2 | "378,000 agreements between two implementations of the same definition validates nothing" | **conceded in full.** Nothing in the comparison validates the signature table, and the paper's whole structural argument is downstream of it |
| — | prevalence of the skip-style gate | **UNRESOLVED**: n = 1. One deployed layer; prevalence not established, and the paper says so |
| — | public-log exposure | **BLOCKED** by egress |
| — | bibliography | **BLOCKED** |

## 14. Terminology policy — binding

Full policy and the exact replacement table: `research/PAPER_CROSS_CONSISTENCY.md`.

**Short form.** The deployed diagnosis output is a **normalized hypothesis
weight**, not a posterior and not a probability. Four independent reasons, any
one sufficient: the `EPS = 0.02` floor inside the logarithm is not a density;
the evidence term is an exponential moving average over ~15 ticks rather than a
product of per-tick likelihoods; it is tempered by `EVIDENCE_MULT = 1.5` before
normalization; the softmax runs over eight causes asserted exhaustive by the
signature table.

**The manuscript already states this correctly at line 251.** Two later lines
contradict it and need the substitution:

| line | current | correct |
|---|---|---|
| 1405 | "The diagnosis posterior is a tempered softmax over exponentially smoothed pseudo-log-likelihoods." | "The diagnosis output is a normalized hypothesis weight: a tempered softmax over exponentially smoothed feature log-scores." |
| 1408 | "we deliberately do not call the posterior a *confidence*" | "we deliberately call it neither a posterior nor a *confidence*" |

Ledger row `SC-20` in `research/systems-paper/CLAIMS.csv` needs the same
substitution.

**"Confidence" is forbidden for both objects in both papers**, except as a
disclaimer about the word itself. A test enforces this.

**Collision hazard.** The mathematical paper's `w_h` is the per-hypothesis
**validity factor**, a different object from this paper's normalized
hypothesis weight. Neither paper may use the bare word "weight" for the
other's object.

## 15. What is BLOCKED, and what the writing agent must not do

| blocked | why |
|---|---|
| bibliography verification | no route from any tested host |
| the public-log study | egress policy |
| a current-stack replication of Mechanism A | no fix-loss arm exists in our 4.8 data |
| establishing prevalence of the gate pattern | n = 1 |

**Must not**: delete a bibliography marker; quote 8.72 against 2.96 without
saying the 8.72 includes a dwell; quote the clean arm's lambda crossings as
latencies; call the negative control a replication; call the diagnosis output a
posterior or a probability; claim novelty for CUSUM or for the general
fault-state-dependent-observation-loss mechanism; assert that the checker
agreement validates the signature table.
