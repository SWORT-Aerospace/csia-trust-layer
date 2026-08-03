# CSIA Repository Audit

**Audit baseline:** commit `3ecd788` (branch `claude/code-reviewer-repo-export-zicovg`)
**Date:** 2026-08-03
**Scope:** full repository — native runtime, Python runtime, simulation,
metrics, tests, CI, documentation, evidence artifacts.
**Method:** every finding below was produced by reading repository source or
executing repository code. Numbers quoted from prior documents that could not
be re-executed in this environment are marked **UNVERIFIED HERE** and are not
restated as fact.

---

## 0. Verification log (what was actually executed)

| Check | Command | Result |
|---|---|---|
| Test suite | `pytest -q` | **62 passed** (not 39 — see F-11) |
| Test inventory | `pytest --collect-only -q` | 8 + 7 + 4 + 3 + 6 + 4 + 4 + 17 + 9 = 62 |
| Trust graph size | `build_trust_graph()` | **8 nodes, 11 edges** |
| Campaign reproducibility | `bench()` → diff vs `campaigns/bench.json` | **bit-identical** ✅ |
| Real-log corpus | `data/real_logs_report.json` | 26 flights, 2385.9 s = **0.663 h** |
| False-alert recount | recomputed from committed report | **3 transitions = 2 escalations + 1 recovery** |
| Native core in runtime path | `grep` over `csia/runtime`, `csia/trust_engine` | **not imported** (see F-03) |

`data/real_logs/*.ulg` is **not** in the repository (gitignored; fetched on
demand by `tools/fetch_real_logs.py`). Real-log figures were therefore
recomputed from the committed `data/real_logs_report.json`, not by re-running
the analyzer. Re-running requires re-fetching the corpus.

---

## 1. Repository architecture

### 1.1 Layout

```
csia/
  cli.py              entry point: build / serve / report / run / service /
                      analyze-logs / bench / mc / info
  scenarios.py        canonical scenario catalog (9) + pipeline assembly
  profiles.py         VehicleProfile registry (sow001_quad, …, interceptor_seeker)
  validation.py       bench() truth table + monte_carlo() campaign
  sensors/            truth generator + 8 sensor models + fault injection
  prediction/         comparator (edge residuals, physics self-models), Holt
                      predictors, complementary attitude filter
  trust_graph/        graph definition (8 nodes / 11 edges)
  trust_engine/       TrustCore (per-tick Bayesian update) + batch driver
  diagnosis/          gate-aware naive Bayes over consistency signature
  runtime/            OnlineTrustLayer, FailsafePolicy, TrustLayerRuntime,
                      MAVLink + ULog sources, systemd service
  native/             csia_core.c + ctypes bindings (parity-tested, see F-03)
  seeker/             interceptor extension (separate trust graph, 3 nodes)
  dashboard/          replay export + stdlib web server + HUD front-end
tests/                62 tests: unit + tests/scenarios/ fault harness
tools/                sitl_validate, soak, perf_regression, fetch_real_logs,
                      benchmark_pi, stress_pi, interceptor_*, dashboard builder
docs/                 requirements, traceability, FMEA, evidence matrix,
                      hardware/embedded plans, TRL, validation protocol
campaigns/            committed bench.json, monte_carlo.json, perf baselines
deliverables/         whitepaper, summaries, seeker MC results, plots
```

### 1.2 Data flow (replay path)

```
truth.generate_flight(profile)      ground-truth kinematics @100 Hz
   └─> sensors.*.sample(truth, faults)          per-sensor streams + faults
        └─> PredictionComparator.build()        TickData @25 Hz:
             edges{lam,gate}, physics{lam,gate}, hist{lam}, var_ratio, fresh
             ├─> TrustEngine.run() → TrustCore.step()   → TrustHistory
             └─> CausalDiagnosis.run()                  → posterior over causes
                  └─> FailsafePolicy.update()           → Transitions + Actions
                       └─> dashboard.export_replay()    → data/replay/*.json
```

### 1.3 Data flow (live path)

`MavlinkSource | UlogSource | SimulatedFlightSource` → `OnlineTrustLayer`
(sample-by-sample, holds the same `TrustCore`) → `FailsafePolicy` →
`LoggingActuator | MavlinkActuator` → `state.jsonl`.

**Design strength worth preserving:** `TrustCore` is genuinely shared between
the batch replay path and the online runtime, so there is one algorithm, not
two that drift. `tests/test_comparator.py::test_causality_no_lookahead`
asserts outputs to time *T* are bit-identical with or without data after *T* —
this is the property that makes the batch path a faithful replay of the online
loop, and it should be treated as a load-bearing invariant.

---

## 2. Findings

Severity: **HIGH** = affects a published claim or embedded safety ·
**MEDIUM** = correctness/maintainability risk · **LOW** = hygiene.
"Safe to change now" = can be modified without redesign or migration.

---

### F-01 — Three inconsistent false-alert definitions; the published one is the loosest · **HIGH**

**Files / symbols**
- `csia/cli.py:179,197-199` — `_analyze_logs`: `n_alarm = len(summary.transitions)`
- `csia/validation.py:87` — `bench`: `sum(1 for tr in s.transitions if tr.level.name != "NORMAL")`
- `csia/validation.py:121-122` — `monte_carlo`: same as `bench`
- `csia/runtime/failsafe.py:252-255` — `_transition` appends on **both** escalation and de-escalation

**Why it matters.** `Transition` records every state-machine edge, including
recoveries (`CAUTION → NORMAL`, which issues `RESUME_NORMAL`). `_analyze_logs`
counts all of them and prints the result as *"failsafe activations … per
flight hour"* — the headline commercial metric. A recovery is not an operator
alert. `bench` and `monte_carlo` already use the stricter, correct-direction
definition, so the repository reports the same quantity three ways and
publishes the loosest.

**Measured impact** (recomputed from the committed `data/real_logs_report.json`):

| Definition | Count | Rate | Status |
|---|---|---|---|
| all transitions (published) | 3 | **4.52 / flight-hour** | over-counts by **1.50×** |
| escalation edges only | 2 | **3.02 / flight-hour** | operator-facing episodes |
| recovery edges | 1 | — | counted as alarms today; they are not alerts |

The published figure is *pessimistic* — the honest direction for an error to
run — but it is still wrong, and it is the number quoted to customers.

**Additional defects in the same metric.** There is no episode merging or
debounce. Consequently (a) a flapping condition produces one "alarm" per
oscillation, and (b) an escalation *within* one incident (`CAUTION → CRITICAL`)
counts as two alerts. Neither corresponds to operator burden.

**Recommended action.** Extract one metrics module owning the exact
definitions of *false-positive sample*, *alert event*, *alert episode*, and
*nuisance episode / flight-hour*, with a configurable merge window; make all
three call sites consume it. Restate the public number with its definition
attached.

**Safe to change now:** yes — additive module; call sites are three lines.

---

### F-02 — "Detection" is measured at an internal threshold that matches no operator-visible event · **HIGH**

**Files / symbols**
- `csia/validation.py:53-64` — `_detection`: hard-coded `v < 0.85`
- `csia/cli.py:67-70` — `_report`: hard-coded `< 0.85`
- `csia/runtime/failsafe.py:58-64` — the actual product thresholds:
  `nav_caution=0.75`, `att_caution=0.82`, `att_emergency=0.70`,
  `struct_critical=0.60`, `power_critical=0.70`, `heading_caution=0.60`

**Why it matters.** Every published detection latency (README: 2.2 s spoof,
13.0 s IMU drift, 1.5 s mag EMI) is the time for a trust coefficient to cross
`0.85`. Nothing in the system *does* anything at 0.85. The operator-visible
event is a failsafe transition, which requires a per-class threshold **plus**
`dwell_up` (1.0 s default, 3.0 s offline posture) **plus** `arm_time`. The
published latency is therefore systematically optimistic relative to the
alert the operator actually receives, and it is not the quantity a PX4/
ArduPilot baseline comparison would produce (those expose health flags /
lane switches, i.e. events).

`0.85` is also un-named and duplicated in two files — changing the detector
posture silently invalidates the metric.

**Recommended action.** Define and report **two** distinct metrics:
*time-to-trust-threshold* (detector-internal, keep for ablation sensitivity)
and *time-to-alert* (failsafe edge, the number for baseline comparison and
customer claims). Move `0.85` into config with a name.

**Safe to change now:** yes, if both metrics are reported during transition so
no historical series breaks.

---

### F-03 — The native C core is not in the runtime path; embedded claims rest on an unused implementation · **HIGH**

**Files / symbols**
- `csia/native/csia_core.c` (140 lines), `csia/native/__init__.py` (ctypes)
- `csia/runtime/online.py`, `csia/trust_engine/engine.py` — **no import of
  `csia.native`** (verified by grep across both packages)
- `tests/test_native.py:15-16` — parity fixture: `NODES` = 4, `EDGES` = 3

**Why it matters.** `OnlineTrustLayer` — the thing `csia run`, `csia service`
and `deploy/` actually execute — uses the **Python** `TrustCore`. The C core is
a parity-pinned reference implementation, not the deployed one. The
`247 ns / 427 ns` per-tick figures and the `0.04 % of STM32H743 @ 25 Hz`
estimate therefore describe code that no runtime path executes. That is a
defensible *port-readiness* claim; it is not a claim about the running system,
and the distinction is not currently drawn in the README.

Compounding this: C↔Python equivalence is verified on a **4-node / 3-edge**
graph while production is **8 nodes / 11 edges**. The parity test does not
cover the deployed topology, and neither implementation is exercised at
production scale by that test.

**Recommended action.** (1) State plainly in README which implementation runs
where. (2) Extend the parity fixture to the production 8/11 topology. (3) Decide
and document whether the C core is intended to become the runtime (then wire it
behind a flag with parity assertions) or to remain a port reference.

**Safe to change now:** (1) and (2) yes. (3) is a design decision, not a patch.

---

### F-04 — Edge indices are unvalidated in the C core → out-of-bounds read · **MEDIUM** (HIGH once config is external)

**File / symbols** — `csia/native/csia_core.c:31-57`

```c
double new_trust[CSIA_MAX_NODES];
if (n < 0 || n > CSIA_MAX_NODES) return -1;   /* n and nc are checked … */
for (int e = 0; e < m; e++) {                  /* … m is NOT bounds-checked */
    if (ea[e] == i) other = eb[e];             /* … and ea/eb are NOT range-checked */
    double w = egate[e] * trust[other];        /* OOB read if other ∉ [0, n) */
```

**Why it matters.** `n` (line 45) and `nc`/`nf` (line 113) are bounds-checked —
that hardening is real. But the edge count `m` is unbounded, and the edge
endpoint indices `ea[e]` / `eb[e]` are used directly to index `trust[]` with no
range validation. A malformed or corrupted edge table produces an
out-of-bounds read — undefined behavior in a component targeted at STM32H7
deployment. Today the indices are generated internally from
`build_trust_graph()`, so this is defense-in-depth rather than a live bug;
it becomes a genuine hazard the moment the graph is loaded from external
configuration, which is the natural next step for a deployable product.

Also worth noting: the guard is `n > CSIA_MAX_NODES`, which is correct for a
`[0, n)` write loop but reads as off-by-one; a comment would prevent a future
"fix" from breaking it.

**Recommended action.** Bound `m` against a `CSIA_MAX_EDGES`; validate
`0 <= ea[e] < n && 0 <= eb[e] < n` and reject with `-1`. Add a negative test.

**Safe to change now:** yes — pure addition of guards, no behavior change on
valid input.

---

### F-05 — No unified experiment provenance; results cannot be tied to code + data + config + environment · **HIGH**

**Files / symbols**
- `tools/perf_regression.py:126-130` — records `commit` (and `"unknown"` fallback)
- `tools/benchmark_pi.py:32-35` — records platform/python
- `csia/validation.py:138-139` — records `runs`, `field_mode`, `seed`
- everything else — records nothing

**Why it matters.** Provenance exists in three fragments and no two agree.
Nothing anywhere records: dirty-working-tree status, dataset identity or hash,
compiler version/flags, build type, CSIA configuration, threshold
configuration, or an output schema version. Project question 11 ("can every
technical claim be regenerated from version-controlled code, data,
configuration and test artifacts") cannot currently be answered *yes* for any
artifact except `campaigns/bench.json`, whose reproducibility I did verify
bit-identically — that reproducibility is real, but it is a property of fixed
seeds, not of recorded provenance. A result file cannot today state which code
produced it.

**Recommended action.** One manifest emitter used by every experiment
entry point, plus a versioned JSON schema for results; validate in CI.

**Safe to change now:** yes — additive.

---

### F-06 — Diagnosis and failsafe can disagree without either flagging it · **MEDIUM**

**Observed during `bench()` execution (this audit):**

```
failsafe NORMAL -> CRITICAL @ t=25.0s: structural vibration anomaly
                   (trust 0.46; diagnosis nominal p=0.72)
```

**Why it matters.** The failsafe escalated to CRITICAL and issued
`LIMIT_THROTTLE` + `LAND_SOON` on a trust threshold while the causal diagnosis
simultaneously reported *nominal* as the most likely cause at p = 0.72. The
two subsystems reached opposite conclusions from the same tick and nothing
recorded the contradiction. The reason string embeds the diagnosis callout, so
the disagreement is printed — but it is not measured, tested, or surfaced as a
health signal. For a product whose thesis is "probability distribution over
causes, never a binary flag", an unmeasured detector/diagnosis incoherence rate
is a substantive gap.

**Recommended action.** Log a `diagnosis_incoherent` counter when a transition
fires with `p(nominal)` above a configured level; report it as a first-class
metric; add a regression test.

**Safe to change now:** yes — observability only, no behavior change.

---

### F-07 — Fault ontology is 6 kinds and is coupled into each sensor model · **MEDIUM**

**Files / symbols** — `csia/sensors/faults.py:25-28` (`KNOWN_KINDS`), and each
`csia/sensors/*.py::sample()` which dispatches on `f.kind`.

`KNOWN_KINDS = {bias_drift, dropout, emi_spike, gps_spoof, vibration_anomaly,
power_sag}` — **6**, against a program target of 20–30 mechanisms including
timing/communication faults (latency, timestamp drift, packet reorder, stale
data), common-cause faults, and compound faults.

**Why it matters.** Fault application lives *inside* each sensor's `sample()`,
so every new mechanism requires editing every affected sensor model. Timing and
transport faults have no natural home at all — they are properties of the
delivery path, not of a sensor's value. The current structure will not scale to
the target ontology without a decoupled injection layer.

**Recommended action.** Introduce a fault-application layer that operates on
(timestamp, value, validity) records between sensor sampling and the
comparator, so value faults, timing faults, and transport faults share one
parameterized schema. Keep the existing 6 kinds working unchanged.

**Safe to change now:** no — needs a migration plan; existing scenarios and
the committed campaign artifacts depend on current behavior byte-for-byte.

---

### F-08 — Reported trust-core latency includes replay marshalling overhead · **MEDIUM**

**File / symbols** — `csia/trust_engine/engine.py:189-212`

`t0 = time.perf_counter()` is taken at the top of the loop body, *before* the
per-tick construction of `edges_now`, `phys_now`, `hist_now`, `vr_now`,
`fresh_now` from NumPy arrays. Those dict comprehensions — including
`np.asarray(...).flat[...]` per edge per tick — are replay-harness marshalling,
not trust-core work, yet they land inside the measured window reported as
"trust core µs/tick" (README: ~85 µs).

**Why it matters.** The published per-tick cost overstates the algorithm and
understates the achievable embedded figure, and it moves if the replay
harness changes while the algorithm does not.

**Recommended action.** Time `core.step()` only; report marshalling separately.

**Safe to change now:** yes, but it will shift a published number — do it in
the same change that restates the metric definitions.

---

### F-09 — Real-log evidence base is very small and partly degenerate · **MEDIUM**

**File** — `data/real_logs_report.json`

26 flights / **0.663 flight-hours** total — a mean of 92 s per flight. One
contributing flight is 35.4 s long; with the offline posture's `arm_time=20.0 s`
(`csia/cli.py:163-165`) that leaves ≈ 15 s of armed monitoring, and its single
CAUTION at t = 32.0 s never resolves before the log ends. A per-flight-hour
rate derived from 0.663 h has a Poisson 95 % interval spanning roughly
0.4–11 alerts/h on 2 events — the point estimate (whether 4.5 or 3.0) carries
far less information than its two significant figures imply.

**Why it matters.** The false-alarm rate is the headline commercial claim and
it currently rests on 2 events. Any comparison against PX4/ArduPilot baselines
at this sample size cannot reach significance.

**Recommended action.** Report the confidence interval alongside the rate
everywhere it appears; set a minimum-duration inclusion criterion and state
excluded-case counts; expand the corpus.

**Safe to change now:** yes for reporting; corpus expansion is a separate task.

---

### F-10 — README internal inconsistency: 11 vs 12 edges · **LOW**

`README.md:169` states "8 nodes / 11 edges" (correct — verified).
`README.md:201` states "8 nodes / 12 edges" in the latency claim. One of the
two numbers attached to a published performance figure is wrong.

**Safe to change now:** yes.

---

### F-11 — Stated test count is stale · **LOW**

The project brief describes a "39-test regression harness". Actual: **62 tests
collected, 62 passing**. README already says 62 and is correct. Recording here
so the brief's figure is not propagated.

**Safe to change now:** n/a — documentation already correct.

---

## 3. Cross-cutting observations

### 3.1 Genuine strengths (do not rewrite)

- **Reproducibility is real where it is claimed.** `campaigns/bench.json`
  regenerated bit-identical in this audit.
- **Evidence grading already exists.** `docs/evidence/evidence_matrix.md`
  labels the 55 m GPS finding as *"Supported (SITL, single scenario)",
  Medium confidence* rather than as a general result. This intellectual
  honesty is an asset and should be the template for new claims.
- **Requirements + traceability scaffolding exists** (36 `REQ-` entries;
  traceability matrix marks gaps **MISSING** rather than fabricating links).
  Phase 13 should extend this, not replace it.
- **Causality is tested, not asserted** (`test_causality_no_lookahead`).
- **Known gaps are published, not hidden** — `CHANGELOG.md` records the
  withdrawn slow-IMU-drift claim (MC TPR 0.00 [0, 0.30]).
- **The C core is embedded-appropriate**: fixed-size stack scratch, no
  `malloc`, bounded loops, no recursion, no global mutable state.

### 3.2 Technical debt

- Root-level `phase1_raw_sensors.py`, `phase2_trust_demo.py`,
  `phase3_dashboard_demo.py` are historical demo scripts outside the package
  and outside CI.
- `dashboard_standalone.html` is a 4.4 MB generated artifact committed to the
  repository; it is a build output, and it will churn the diff on every
  dashboard change.
- CI (`.github/workflows/ci.yml`) runs formatting-free: no linter, no static
  analysis, no sanitizers, no compiler warning flags — `build.sh` is invoked
  without `-Wall -Wextra`. For a C component targeting flight hardware this is
  the largest single CI gap.

### 3.3 Simulation ↔ production divergence risks

- `field_mode` toggles the tolerance package; `validation.py`'s own docstring
  records that detection was once measured with it **off** while false alarms
  were measured with it **on**. The C1 truth table exists precisely to prevent
  that recurring — this must remain enforced for every new metric.
- Sensor tolerances are quad-tuned; the `high_speed_dash` scenario is labeled
  kinematic-only with drag unmodeled. Correctly disclosed today; the labeling
  discipline must survive the ontology expansion.

---

## 4. Prioritized remediation order

| # | Finding | Action | Risk of acting |
|---|---|---|---|
| 1 | F-01 | Single metrics module; episode semantics; restate public number | low |
| 2 | F-02 | Split time-to-threshold vs time-to-alert; de-magic `0.85` | low |
| 3 | F-05 | Experiment manifest + result schema | low |
| 4 | F-10, F-11 | Documentation corrections | none |
| 5 | F-04 | C bounds guards + negative test | low |
| 6 | F-06 | Incoherence counter | low |
| 7 | F-08 | Re-scope latency measurement window | low (moves a number) |
| 8 | F-09 | CIs everywhere; inclusion criteria | low |
| 9 | F-03 | README correction now; runtime decision separately | mixed |
| 10 | F-07 | Decoupled fault-injection layer + ontology expansion | **needs migration plan** |

Items 1–8 are additive or documentation-only. Item 10 is the first change that
requires a migration plan, because the committed campaign artifacts are
byte-for-byte dependent on current fault behavior.
