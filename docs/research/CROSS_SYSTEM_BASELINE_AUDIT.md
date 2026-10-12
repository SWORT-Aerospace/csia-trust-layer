# Cross-system baseline audit — what CSIA is, today

**A factual reconstruction, read from the implementation.** Every statement
points to a file, a function or a measurement. Status labels:
**HISTORICAL/SEALED** · **CURRENT VALIDATED** · **EXPERIMENTAL** ·
**PROPOSED** · **UNPROVEN**. Written under
`docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`.

Companions: `docs/research/LATENCY_PATH_ANALYSIS.md`,
`docs/research/CROSS_SYSTEM_ARCHITECTURE_SEED.md`,
`docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md`,
`docs/research/SITL_FEASIBILITY_MATRIX.md`.

---

## A. Repository baseline

| | |
|---|---|
| branch | `claude/code-reviewer-repo-export-zicovg` |
| HEAD at the start of this work | `e7594e4f72e71a812ee2e7b959533a3d1e5456c9`, clean, pushed |
| freeze commits (all ancestors of that HEAD) | `csia-v1.0-research-final` @ `ec5acd1`, `csia-v2-phasec-frozen` @ `50c5d35`, `csia-dual-paper-evidence-freeze` @ `eb2577d` |
| freeze **tags** | **local only, never pushed** (`docs/CURRENT_PROGRAM_STATE.md`). Origin carries only `v0.7.0` |
| governance | `docs/CURRENT_PROGRAM_STATE.md` governs what may be worked on: engineering frozen at v2 Phase C; estimator, energy and Forge production code forbidden; this work proceeds under `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md` |

**Test baseline at `e7594e4`:** 4,266 passed, 41 skipped, 0 failed, with
`.venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rs`.

The skips that matter, at `e7594e4`: **`tests/test_v1_frozen.py`**, the v1
zero-diff guard, and six v1.1 freeze tests skip because the freeze tag is not in
this clone. Five native-core parity tests skip because the C core is not built
(CI builds it). Three skip because no ArduPilot tree is present.

---

## B. Existing architecture (CURRENT VALIDATED unless marked)

| component | where | what it is |
|---|---|---|
| **v1 online layer** | `csia/runtime/online.py` `OnlineTrustLayer._tick` | per-tick ingest → freshness → gates → features → trust → diagnosis → failsafe → emit, at 25 Hz |
| v1 batch path | `csia/scenarios.py` `run_pipeline` | `PredictionComparator` → `TrustEngine.run` → `CausalDiagnosis.run`. **Runs no failsafe policy** |
| trust | `csia/trust_engine/engine.py` `TrustCore.step` | a Beta recursion with adaptive forgetting ρ ∈ [0.95, 0.998] over 8 nodes and 11 edges |
| diagnosis | `csia/diagnosis/bayes.py` `DiagnosisCore.step` | a softmax posterior over 8 hypotheses. **Gated features are skipped, not down-weighted** |
| policy | `csia/runtime/failsafe.py` `FailsafePolicy` | per-class thresholds, `dwell_up` 1.0 s, `arm_time` 10 s, recommended actions |
| v1 frozen core | `docs/v1/FROZEN_BASELINE.json` | 12 files under `csia/`, HISTORICAL / SEALED |
| **v1.1 sequential** | `csia/v1_1/sequential.py` | Page's one-sided CUSUM bank, k = 0.5, h = 500; no residual for `imu0`, `imu1` or `baro` |
| **v2 Phase C** | `csia/v2/` | the cross-domain layer: domain plugins, `EvidenceRecord`, function graph, localization, attribution, signatures, ledger. Frozen at `50c5d35` |
| native core | `csia/native/csia_core.c` | the same trust and diagnosis maths in C. **Not on any production execution path** (`docs/research/CSIA_ALGORITHM_EXPOSITION.md` D-10) |
| experimental certificate | `csia_assurance/witness.py` `SupportCertificate` | EXPERIMENTAL firewall-layer certificate. **Not imported by v2** |
| mission layer | `csia_mission/capability.py`, `csia_mission/forge_seed.py` | capability certificates and a FORGE-facing seed |

The authoritative algorithm reference is
`docs/research/CSIA_ALGORITHM_EXPOSITION.md`, with a file:line for each equation.

---

## C. Evidence flow

**v1, one tick** (CURRENT VALIDATED): a channel is fresh if valid and within
`STALE_TIMEOUT_S`. Gates (`armed_gate`, `gvalid`, `speed_gate`, `gps_warmup`)
multiply features. Each edge's λ = (r/σ)²/df is EW-smoothed and turned into a
consistency c = exp(−0.5·max(0, λ − 1)). Fused evidence updates each node's
α and β only when the node is fresh, since stale data freezes belief. The
diagnosis sums log-consistency over each hypothesis's LOW set, smooths it
(α = 0.06), adds the prior and takes a softmax. The policy reads trust against
per-class thresholds, and dwells.

**v2, one snapshot** (CURRENT VALIDATED): each `AssuranceDomain` observes the
snapshot and emits `EvidenceRecord`s. Localization applies three-valued
predicates from the signature matrix and eliminates refuted hypotheses.
Attribution labels the survivors. The function graph states which functions
remain justified and which domain limits them. The ledger records changes.
**No evidence accumulates across snapshots.**

---

## D. Existing detectors and baselines

| detector | where | status |
|---|---|---|
| trust persistence (`B0`) | v1 trust + policy | HISTORICAL/SEALED: Phase 5 median 2.54 s, false-alarm rate 0.000, 9 of 9 thresholds clean |
| CUSUM | `csia/v1_1/sequential.py` | frozen; `h = 5.0` kept as a committed **negative** result (2,681 clean alarm ticks) |
| bare threshold | Phase 4/5 `B2` | HISTORICAL/SEALED: 1 of 6 thresholds clean |
| hybrid fast + CSIA (`B3`, `B4`, `B6`) | Phase 5 | HISTORICAL/SEALED: 0.24 s, false-alarm rate 0.100, H5 **killed** |
| multi-timescale (`B5`) | Phase 5 | HISTORICAL/SEALED: 0.36 s, false-alarm rate 0.000, 12 of 12 thresholds clean |

Sources: `research/phase5/PHASE5_RESULTS.md`,
`research/phase4/results/PHASE4_RESULTS_LOCKED.json`,
`research/systems-paper/MECHANISM_B.md`.

---

## E. Existing latency methodology

- `csia/metrics/latency.py`: the owner of every time-to-X calculation, with
  four explicitly non-equal onset bases. **Never run on a real scenario by
  committed code**; only `tests/test_metrics_latency.py` calls it, on fakes.
- `docs/audit/CSIA_LATENCY_PATH_AUDIT.md`: a 12-stage path audit from executed
  code. It found the published "detection latency" used a 0.85 analysis
  threshold with no operational effect.
- `TrustState.latency_us` (`csia/runtime/online.py:645`): per-tick compute.
- `engineering/v2/V2_PHASEC_COMPUTE.json`: v2 localization at 45.8 µs per tick,
  the full API at 2.7 ms, with no target-hardware figure claimed.

The decomposition measured for this work is in
`docs/research/LATENCY_PATH_ANALYSIS.md` §3.

---

## F. Existing non-sensor and component work

| work | where | status |
|---|---|---|
| `power_fault` hypothesis, and power/motor edges | `csia/diagnosis/bayes.py`; `accel_motor_current`, `accel_esc_rpm`, `power_thrust` | CURRENT VALIDATED. **One** hypothesis covers battery, ESC and motor |
| `power_sag` scenario | `csia/scenarios.py` | injects on `battery` **and** `motor_esc` at once |
| v2 POWER and ACTUATION domains | `csia/v2/domains/power.py`, `csia/v2/domains/actuation.py` | CURRENT VALIDATED, frozen |
| the motor test stand profile | `csia/v2/profiles/test_stand.py` | has a torque channel; resolves Set B members 4 and 5 |
| battery equivalent-circuit models, realized-current certification | `csia_active_evidence/battery_1rc.py`, `csia_active_evidence/rcec.py` | EXPERIMENTAL, under the simulator-only energy exception |
| the power-thrust information contract | `research/phase2/INFORMATION_CONTRACT_POWER_THRUST.md` | HISTORICAL: ArduPilot SITL's ESC "RPM" is the motor command scaled by a vibration constant, not a motor-speed model |

---

## G. Existing cross-system-like behaviour

- **v1 cross-domain edges** (CURRENT VALIDATED): `accel_motor_current` and
  `accel_esc_rpm` compare inertial acceleration against propulsion
  telemetry, and `power_thrust` relates power to thrust. They are cross-domain
  relations inside one flat graph.
- **v2 localization and attribution** (CURRENT VALIDATED): the cross-domain
  mechanism proper. Set A resolves four causes of a stale output. **Set B does
  not resolve on the multirotor and does on the bench.** Set C does not
  resolve, because of a profile-level blind spot
  (`engineering/v2/MATCHED_SCENARIOS.md`).
- **ESC telemetry as a conditioning variable** (HISTORICAL/SEALED): Phase 5's
  `EA` / `EG` conditions. With ESC telemetry absent, the corrected support map
  recovers `{imu0, imu1}` identifiability from Doppler edges already computed,
  p = 1.8e-12.

---

## H. Existing FORGE interfaces

`forge/` contains two Markdown files and **no code**
(`tests/test_program_state.py` asserts it). `csia_mission/forge_seed.py` and
the capability certificates are research-side seeds. FORGE production code is
**forbidden** by `docs/CURRENT_PROGRAM_STATE.md` §1, and this work adds none.

---

## I. Relevant tests

| area | tests |
|---|---|
| freezes | `tests/test_v1_frozen.py` (skips without the tag), `tests/test_phase_c_freeze.py`, `tests/test_program_state.py`, `tests/test_evidence_extension_is_append_only.py` |
| v1 runtime and formal properties | `tests/test_runtime.py`, `tests/test_formalization_lock.py` |
| v2 | `tests/test_v2_framework.py`, `tests/test_v2_domains.py`, `tests/test_v2_localization.py`, `tests/test_v2_scenarios.py`, `tests/test_v2_api_ledger.py`, `tests/test_v2_navigation_baseline.py` |
| latency | `tests/test_metrics_latency.py` |
| CUSUM | `tests/test_v1_1_sequential_gate.py` |
| certificate | `tests/test_assurance_firewall.py` |
| platforms | `tests/test_platform_contract.py`, `tests/test_simulation_contract.py` |
| native parity | `tests/test_native.py` (skips when the C core is not built) |
| sealed pipelines | `tests/test_phase4_pipeline.py`, `tests/test_phase5_pipeline.py` |

**No test covers `research/systems-paper/mechanism_b.py`.** That is how the
dwell error recorded in `docs/research/MECHANISM_B_DWELL_DISCREPANCY.md`
stayed in place.

---

## J. Relevant experimental artifacts (HISTORICAL / SEALED — not modified)

- **22** tracked locked, sealed or freeze artifacts: the Phase 3 / 3.1 / 3.2 /
  4 / 5 `*_LOCKED.json` files, `engineering/v2/V2_PHASEC_FREEZE.md`,
  `engineering/v1_1/V1_1_ARCHITECTURE_FREEZE.json`, and others.
- **32** preregistrations and amendments: for example
  `research/phase4/PREREGISTRATION_PHASE4.md` and
  `research/phase5/PREREGISTRATION_PHASE5.md`.
- **6** SHA-256 manifests: `docs/v1/FROZEN_BASELINE.json` and the per-phase
  manifests.

None was modified by this work. `docs/research/MECHANISM_B_DWELL_DISCREPANCY.md`
and `docs/research/SC09_PROPOSED_CORRECTION.md` record the preserved hashes of
the Mechanism B artifacts.

**The failure ledger is itself hash-pinned.**
`research/physical_validation/FAILURE_LEDGER.yaml` is listed in the Phase 3.2,
Phase 4 and Phase 5 SHA-256 manifests, so any append changes a sealed-manifest
hash record. That is why the Mechanism B discrepancy is held in a separate
record and not appended.

---

## K. Current limitations

1. **The bench simulator does not propagate faults.** `csia/sensors/truth.py`
   is a scripted, open-loop profile, and no fault modifies truth; faults
   corrupt sensor outputs only (`csia/sensors/motor.py`). A physical power
   fault and a lying power sensor are therefore **identical** there.
2. **v1 has one propulsion hypothesis.** Battery, ESC and motor degradation
   cannot be separated by construction. Per-sensor scoring of `power_sag`
   marks `motor_esc` as incorrect isolation.
3. **v2 is atemporal.** Cross-domain isolation and certification latency are
   undefined.
4. **Set B's floor of two** on the multirotor.
5. **SITL ESC telemetry**: a stub on ArduPilot (command-derived RPM,
   placeholder current); varying but semantically unread on PX4, where it
   arrives at about 1 Hz.
6. **The latency module is unused on real runs**, and t1 and t2 are not
   implemented in it.
7. **Neither SITL is installed** in this container, and the one SIH log the
   repository discusses is gitignored.
8. **The v1 zero-diff guard skips** in a clone without the freeze tags.

---

## L. Unknowns that need experiments (UNPROVEN)

| unknown | how it would be settled |
|---|---|
| can vehicle dynamics refute `SENSOR/response_sensor` on a multirotor? | `docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md`, H1 |
| does compensation close the observability window before a witness decides? | the same experiment, falsifier F3 |
| is PX4 SIH's ESC RPM a rotor measurement or a command echo? | a source read at `547e2ca` (gating item G1) |
| does PX4 SIH honour motor failure injection, and partially? | a source read (G2, G4) |
| how long does v2 take to name a cause as evidence accumulates? | architecture seed E2, with post-hoc instrumentation P5 |
| is command-path loss ever separable from thrust loss without a delivery witness? | experiment H2; predicted **no** |
