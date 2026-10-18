# README claim audit — WP1

Audited commit: `bc3ed977e14d6eb6c5dc3a8b771b2349337de91a`
Audit branch: `research/formalization`
Method: every claim resolved against source or a committed artifact and, where
measurable, re-measured. No claim is marked VERIFIED because the README asserts it.

**Audit-list provenance.** The 25 claims supplied for this audit reference
`v0.7.0` and a 39-test suite. The README at this commit states `v0.8.0` and
77 tests, and the suite actually collects 418. The claim list is therefore
itself stale relative to the README it audits. Each row below records the
supplied claim, and separately what the current README says, so both are
traceable.

Status vocabulary: `VERIFIED` · `VERIFIED_WITH_QUALIFICATION` · `STALE` ·
`CONTRADICTED` · `NOT_REPRODUCIBLE` · `UNSUPPORTED` · `UNRESOLVED`

---

### C-01 — Current release is v0.7.0
**Supplied claim:** release is `v0.7.0`. **README says:** "Validation status
(v0.8.0)" (README:40), quick start `python3.13 -m venv` (README:27).
**Source:** `pyproject.toml:7` → `version = "0.8.0"`. `git tag` → no tags exist.
**Status: `STALE`** (supplied claim) / **`VERIFIED`** (README vs pyproject).
**Evidence:** package version is 0.8.0; the repository publishes no tags at all,
so "current release" has no tag-based referent.
**Corrected wording:** "Package version 0.8.0 (`pyproject.toml`); the repository
is untagged — there is no released artifact, only commits."

### C-02 — Full suite contains 39 tests
**Supplied claim:** 39 tests. **README says:** "full test suite (77 tests)"
(README:37) and "Simulated fault harness (77 tests, CI)" (README:44).
**Measured:** `python -m pytest --collect-only` → **418 tests**, all passing,
0 skipped, 2m14.9s, exit 0.
**Status: `CONTRADICTED`** (both the supplied 39 and the README's 77).
**Evidence:** 418 collected across 22 modules (per-module counts in
`source_inventory.md`). The 77 figure predates the ACEG slices (`test_causal`
22, `test_hypothesis` 44, `test_datasets` 38, `test_anytime_validity` 15,
`test_data_lake` 21, plus the acquisition suites 150).
**Corrected wording:** "full test suite (418 tests)".

### C-03 — Dynamic Trust Graph has 8 nodes and 11 edges
**Source:** `csia/trust_graph/graph.py:20-29` (NODES, 8 entries), `:33-56`
(EDGES, 11 entries). **Measured:** `build_trust_graph()` →
`number_of_nodes()==8`, `number_of_edges()==11`, undirected (`nx.Graph`).
Pinned by `tests/test_native.py:137`.
**Status: `VERIFIED`.**

### C-04 — Runtime-cost measurement uses 8 nodes and 12 edges
**Source:** `csia/trust_engine/engine.py:104` — comment `# incident map rebuilt
cheaply from the edge dict (12 edges)`.
**Status: `CONTRADICTED`.**
**Evidence:** this is the *only* occurrence of "12 edges" in the repository and
it is a code comment, not a measurement. No timing harness uses 12 edges. The
production graph is 11 edges; `tests/test_native.py:137` asserts `(8, 11)`. The
runtime builds 11 edge keys: 10 unique relation names (two edges share the
relation `velocity_gps_doppler`), then `online.py:206-208` re-splits that
relation into `velocity_gps_doppler_0/_1` and pops the merged key.
**This resolves the README's 11/12 discrepancy: there is no 12-edge graph. The
comment is stale.**
**Corrected wording:** delete the parenthetical, or `# (11 edges)`.

### C-05 — Real-log alert rate is 4.5 per flight-hour
**Supplied claim:** 4.5/flight-hour. **README says:** "3.86 episodes/h, 95% CI
0.47–13.94" on 0.518 monitored hours (README:47).
**Source:** `datasets/reports/exposure_v2.json` →
`rates_by_health_category.UNANNOTATED.rate_per_hour = 3.859`,
`alert_episodes = 2`, `exposure_hours = 0.5183`.
`data/real_logs_report.json` → `total_transitions = 3`, `total_hours = 0.663`.
**Status: `STALE`** (supplied) / **`VERIFIED`** (README).
**Evidence — exact provenance of the stale number:** 3 transitions ÷ 0.663 raw
hours = **4.52/h**. The current figure changed on *both* axes: numerator
transitions→alert *episodes* (3→2) and denominator raw→*monitored* hours
(0.663→0.5183), giving 2/0.5183 = 3.86/h.
**Corrected wording:** "3.86 alert episodes per monitored flight-hour (2
episodes / 0.518 h), 95% CI 0.47–13.94. Not comparable to the earlier 4.5/h,
which counted transitions over raw duration."

### C-06 — 24 of 26 flights are alarm-free
**Measured:** `data/real_logs_report.json` → 26 flights, 24 with zero
transitions. `exposure_v2.json` → `flights_with_0_episodes = 24`,
`flights_with_1_episode = 2`.
**Status: `VERIFIED`.**
**Qualification the README already makes and must keep:** the logs are
UNANNOTATED; `VERIFIED_HEALTHY.exposure_hours = 0.0`. Silence is not evidence
of health.

### C-07 — Real-log duration is 0.66 hours
**Measured:** `data/real_logs_report.json:total_hours = 0.663`;
`exposure_v2.json:total_raw_hours = 0.6627`, `total_monitored_hours = 0.5183`.
**Status: `VERIFIED_WITH_QUALIFICATION`.**
**Qualification:** 0.663 h is *raw* duration. Monitored exposure is 0.518 h —
raw overstates the alertable window by 21.8% because no alert can be raised
inside `arm_time`. Any rate must use the monitored basis.

### C-08 — Online and batch execution are "exact"
**Source:** README:194-197 claims causality makes batch "an exact replay of an
online sample-by-sample loop". `tests/test_runtime.py:23-45`.
**Status: `CONTRADICTED` as stated; `VERIFIED_WITH_QUALIFICATION` as tested.**
**Evidence:** the test does **not** assert exactness. It asserts
`early < 0.07` for `5 s < t < 20 s` and `late < 0.01` for `t > 20 s`
(`test_runtime.py:42-43`). The online path calibrates IMU bias causally by
replaying a buffered ground window; the batch path does it retroactively
(`online.py:212-216`). These are different computations, and the divergence is
bounded, not zero.
**Corrected wording:** "the batch pipeline and the online runtime share the same
per-tick cores and converge to <0.01 trust divergence after t=20 s; they are
*not* bit-identical, because IMU ground calibration is causal online and
retroactive in batch."
**Note:** `tests/test_comparator.py::test_causality_no_lookahead` separately
proves *no-lookahead* (bit-identical with/without future data). That is a
different and genuinely exact property. The README conflates the two.

### C-09 — Online/batch divergence is below 0.01 after convergence
**Source:** `tests/test_runtime.py:43` — `assert late < 0.01` for `t > 20`.
**Status: `VERIFIED`** (asserted and passing; scenario `gps_spoof` only).
**Qualification:** verified on **one** scenario (`gps_spoof`), not across the
catalog.

### C-10 — Trust uses Beta (α, β) beliefs
**Source:** `csia/trust_engine/engine.py:96-99` (`self.alpha`, `self.beta`
initialised to `alpha0=8.0`, `beta0=2.0`), `:147-149` update, `:149`
`T = α/(α+β)`.
**Status: `VERIFIED`.** T(0) = 8/10 = 0.8.

### C-11 — Adaptive forgetting uses ρ ∈ [0.95, 0.998]
**Source:** `engine.py:59-60` `rho_max=0.998`, `rho_min=0.95`; `:144`
`rho = rho_max - (rho_max - rho_min) * d`; `:65-66` validates
`0 < rho_min <= rho_max < 1`.
**Status: `VERIFIED`.**
**Mechanism (recorded because the README does not state it):** `d` is the
*spread* of available sub-scores, `d = max(scores) - min(scores)` (`:143`), and
`d = 0` when fewer than two sub-scores are available. Since sub-scores lie in
(0,1], `d ∈ [0,1]` and ρ spans the full band.

### C-12 — Four evidence subscores are fused
**Source:** `engine.py:118-140` — `c_nbr`, `c_phys`, `c_temp`, `c_stat` with
weights `w_nbr=0.35, w_phys=0.30, w_temp=0.20, w_stat=0.15` (`:55-58`).
**Status: `VERIFIED`.**

### C-13 — Inactive or invalid checks contribute zero evidence
**Source:** `engine.py:131-140`.
**Status: `VERIFIED_WITH_QUALIFICATION`.**
**Evidence — the mechanism is exclusion, not a zero term:** unavailable
sub-scores are dropped from `avail` and the weights are **renormalised** over
what remains (`evidence = Σ w·c / Σ w`). A gated-out check therefore does not
pull evidence toward zero; it does not participate at all. Contributing "zero
evidence" would be a maximally negative observation — the opposite of the
implemented semantics.
**Edge case:** if *no* sub-score is available, `evidence = 0.5` is reported as a
placeholder and **the Beta belief is not updated** (`:146`
`if avail and fresh.get(n, True)`). Trust holds. Mirrored in C
(`csia_core.c`) and pinned by `test_native_trust_no_evidence_parity`.
**Corrected wording:** "gated or unavailable checks are excluded from the fusion
and the remaining weights renormalise; they contribute neither support nor
doubt."

### C-14 — GPS dropout causes trust to hold
**Source:** `engine.py:146` (no belief update when `fresh[n]` is False);
README:225 scenario row "gps_dropout … 0.89 (trust holds) … 98% nominal".
**Status: `VERIFIED`.** See §8 of `csia_implemented_system.md` for the full
five-subsystem separation — trust holding and the failsafe *still* reacting are
not in conflict; they are different subsystems.

### C-15 — Sensor silence becomes not-fresh after ≈5 sample periods
**Source:** `csia/runtime/online.py:47-50` — `STALE_TIMEOUT_S = {imu0: 0.05,
imu1: 0.05, baro: 0.1, mag: 0.1, gps: 0.5, motor_esc: 0.1, battery: 0.5,
vibration: 0.5}`.
**Status: `VERIFIED_WITH_QUALIFICATION`.**
**Evidence:** the implementation uses an **absolute per-sensor wall-clock
timeout**, not a count of sample periods. "≈5 sample periods" holds only for
sensors whose native rate makes it so (GPS at 10 Hz → 0.5 s = 5 periods;
IMU at 100 Hz → 0.05 s = 5 periods). It is a derived description, not the rule.
**Corrected wording:** "a sensor is declared not-fresh after a fixed per-sensor
timeout (`STALE_TIMEOUT_S`: 0.05 s IMU, 0.1 s baro/mag/ESC, 0.5 s
GPS/battery/vibration) — ≈5 sample periods at each channel's nominal rate."

### C-16 — Native C is pinned to Python at 1e-12
**Source:** `tests/test_native.py:57,59,87,88,122,176,178` — all assert
`< 1e-12`.
**Status: `VERIFIED_WITH_QUALIFICATION`.**
**Qualification:** equivalence is **kernel-level on a randomised test corpus**,
not full behavioural equivalence. Scope, vector counts and what is *not* covered
are in `python_native_equivalence.md`. Note the whole module is
`skipif(not native.available)` (`test_native.py:11-12`) — parity silently does
not run unless `csia/native/build.sh` has been executed.

### C-17 — Native trust and diagnosis cost totals 674 ns per tick
**Source:** README:50 "trust kernel 247 ns + diagnosis 427 ns"; README:126
"674 ns/tick". Only textual reference in code is `tools/benchmark_pi.py:123`
("the desktop 674 ns figure").
**Status: `NOT_REPRODUCIBLE` in this environment.**
**Evidence:** 247+427 = 674 is internally consistent, but no committed artifact
records the measurement, no test regenerates it, and no harness in `tools/`
emits it. `campaigns/perf_baseline.json` contains no native figure. The number
cannot be confirmed or refuted from the repository.
**Corrected wording:** attach the generating command and a committed result
artifact, or mark the figure as a one-off host measurement with date and CPU.

### C-18 — Active Python runtime costs ≈140 µs per tick
**Source:** README:121-122 "~140 µs/tick in reference Python"; README:204
separately says "~85 µs/tick trust core".
**Measured here:** `TrustCore.step` on the production 8-node/11-edge topology =
**56.4 µs/tick** (3000 ticks, warmed). Committed baseline
`campaigns/perf_baseline.json` records `trust_core_us: 68.62` and
`runtime_tick_us: 304.82` at commit `c13889f`.
**Status: `NOT_REPRODUCIBLE` / `CONTRADICTED`.**
**Evidence:** three different numbers are in play for two different quantities
(trust core ≈85 µs claimed vs 68.62 committed vs 56.4 measured; full runtime
tick ≈140 µs claimed vs 304.82 committed). The full-tick claim of 140 µs is
contradicted by the repository's own baseline, which is 2.2× larger. Host
variance explains the trust-core spread; it does not explain 140 vs 305.
**Corrected wording:** quote `campaigns/perf_baseline.json` directly and name
the host, or drop the figure. README:204-207 already concedes the measured
window "includes replay marshalling as well as the trust core itself (audit
F-08)" — that caveat belongs on the 140 µs figure too.

### C-19 — The runtime executes at 25 Hz
**Source:** `csia/profiles.py:38` `tick_hz: float = 25.0`;
`online.py:149` default `tick_hz=25.0`, `:197` `dt_tick = 1/tick_hz`.
**Measured:** `sow001_quad` 25.0 Hz, `sow001_quad_strict` 25.0 Hz,
**`interceptor_seeker` 100.0 Hz** (`profiles.py:80`).
**Status: `VERIFIED_WITH_QUALIFICATION`.**
**Qualification:** 25 Hz is the quad profiles' rate, not a system constant. A
third shipped profile runs at 100 Hz. Separately, README:79-80 says
"`sow001_quad` and `sow001_quad_strict` ship today" while `PROFILES` contains
**three** entries.

### C-20 — The diagnosis model is gate-aware naïve Bayes
**Source:** `csia/diagnosis/bayes.py:96-114`. Gate awareness: `:99-100`
(`if gate <= 1e-9: continue`) and `:104` (`ll[ci] += gate * (...)`). Naïve
independence: log-likelihoods summed across features with no interaction term.
**Status: `VERIFIED`.**

### C-21 — Simultaneous independent faults are not handled gracefully
**Source:** `bayes.py:44-56` — `CAUSES` is a flat map of single causes; there is
no joint or multi-label hypothesis. `:110-113` softmax forces a single
normalised distribution over mutually exclusive causes.
**Status: `VERIFIED`.** The README's own limitation (README:314-316) is accurate
and understated: the model has no representation for a joint fault at all, so
"posteriors will split" is the *only* available behaviour.

### C-22 — Failsafe behaviour is deterministic with dwell and hysteresis
**Source:** `csia/runtime/failsafe.py:206-236`. Dwell up: `:208-209`
(`t - cond_since >= dwell_up`, default 1.0 s). Hysteresis down: `:224-227`
(`dwell_down`, default 5.0 s). No RNG anywhere in the module.
**Status: `VERIFIED`.**
**Required qualification (README does not state it):** determinism is not a
safety property. There is no reachability, liveness, or time-to-detect
guarantee. Recorded explicitly in `csia_implemented_system.md` §11.

### C-23 — A 10-second arming delay exists
**Source:** `failsafe.py:68` `arm_time: float = 10.0`; enforced at `:198-199`
(`if t < cfg.arm_time: return []`).
**Status: `VERIFIED_WITH_QUALIFICATION`.**
**Qualification:** two independent gates exist and the README describes only
one. `:191-197` returns early whenever the source reports `armed is False`,
*regardless of t*, and calls `reset_timers()`. The 10 s delay is the fallback
for sources that never report an armed flag. Also note
`exposure_v2.json:arm_time_s = 20.0` — the real-log exposure analysis used a
**20 s** arm window, not 10 s.

### C-24 — MavlinkActuator commands are opt-in
**Source:** README:118-120 (`enable_commands=True`);
`csia/runtime/service.py` MavlinkActuator. Default actuator is
`LoggingActuator` (advisory).
**Status: `VERIFIED`.**

### C-25 — PX4 fused outputs can conceal a GPS glitch seen in the raw stream
**Source:** README:130-134 and README:49 report a SITL result: 55 m glitch
invisible in fused output, caught from `GPS_RAW_INT`.
**Status: `UNRESOLVED` (not reproducible here).**
**Evidence:** the mechanism is architecturally supported — the GPS node consumes
the raw stream, and `MavlinkSource` maps `GPS_RAW_INT`. But the *claim* is an
empirical SITL measurement. No committed artifact records it, `tools/sitl_validate.py`
requires a live ArduPilot SITL unavailable in this environment, and README:285-288
itself states the SITL rows "were measured before the 2026-07 …hardening and must
be refreshed before any new claim."
**Corrected wording:** keep the architectural rationale; mark the 55 m figure as
pending re-measurement, consistent with README's own Path-to-flight gate 1.

---

## Summary

| Status | Count | Claims |
|---|---|---|
| `VERIFIED` | 9 | C-03, C-06, C-10, C-11, C-12, C-14, C-20, C-21, C-22, C-24 (10 incl. C-24) |
| `VERIFIED_WITH_QUALIFICATION` | 6 | C-07, C-13, C-15, C-16, C-19, C-23 |
| `STALE` | 2 | C-01, C-05 |
| `CONTRADICTED` | 3 | C-02, C-04, C-08 |
| `NOT_REPRODUCIBLE` | 2 | C-17, C-18 |
| `UNRESOLVED` | 1 | C-25 |

Nothing in the README was edited by this audit.

**The three findings that matter most:**

1. **C-04 resolves the 11/12 edge discrepancy: there is no 12-edge graph.** A
   stale comment in `engine.py:104` is the sole source of "12 edges".
2. **C-08: "exact" is wrong.** Online and batch are bounded-divergent by
   construction (causal vs retroactive IMU calibration), and the test asserts
   `<0.01`, not equality. A separate, genuinely exact property (no-lookahead)
   is being conflated with it.
3. **C-18: the repository contradicts itself on runtime cost** — 140 µs claimed
   vs 304.82 µs in its own committed baseline.
