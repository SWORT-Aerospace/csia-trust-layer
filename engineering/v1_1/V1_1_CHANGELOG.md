# CSIA v1.1 CHANGELOG

Version/claim separation per item 49: **v1** is the historical research
baseline; **v1.1** is the corrected engineering system. Any existing paper
result that uses v1 stays labelled v1. Any v1.1 result must be newly measured.

---

## Phase 1 — canonical ingestion + known defect fixes

### FIXED

- **`csia/aircraft/adapters/base.py`** — `_reject_sentinel` now clears
  `_latest` for the channel, making it symmetric with `_put` clearing
  `_sentinel_at`. A producer's declaration of "not measured now" supersedes
  an earlier value, as an earlier value supersedes a stale sentinel.
  Defects D1 and D2. **Widest-reaching change in Phase 1**: it affects every
  channel on every adapter that reports a sentinel.
- **`csia/aircraft/adapters/ardupilot.py`** — the all-zero magnetometer
  branch now calls `_reject_sentinel("mag.field_ut")` instead of falling
  through in silence. Defect D2.
- **`csia/runtime/ulog_source.py`** — battery `current_a == -1` is no longer
  emitted as a valid physical current. Voltage keeps its own validity against
  its own declared sentinel. Defect D3.
- **`csia/runtime/plugins.py`** — `max(current_battery, 0)` removed; the
  MAVLink not-measured sentinel is no longer clamped to 0.00 A. Defect D4.

### CHANGED (interface)

- The `battery` channel dict from both decode paths gains **`current_valid`**,
  and `current` may now be `None`. `valid` remains the whole-sensor gate and
  is `False` when either constituent is a sentinel. Consumers reading
  `current` unconditionally need updating.

### HARDENED

- `research/semantic_authority_conflict/authorities.py` and
  `research/evidence_semantics/cross_sensor_audit.py` resolve `csia/`
  citations against the commit the citations were taken at
  (`CITED_REVISION`), not the working tree. A v1 claim was being verified
  against today's code, which is wrong in both directions; the Phase 1 fixes
  demonstrated it by breaking four correct citations.

### VALIDATED

- `tests/test_v1_1_canonical_ingest.py` — 13 tests covering rules R1-R5, the
  four defects, the GNSS control, the frozen-core diff, and the integrity of
  the pre-fix record itself.
- Gates A, B, C, J pass. D-I not reached (phases 2-5).

### TESTS CHANGED

- `test_adapter_core_equivalence.py::test_battery_current_sentinel_is_a_deliberate_improvement`
  renamed to `..._is_refused_by_both_paths`. It asserted the legacy path
  returns 0.0; the legacy path is now fixed, so it asserts agreement instead.
- `test_dual_admissibility_confirmatory.py::test_battery_defect_is_reproducible_from_the_committed_adapter`
  renamed to `..._is_fixed_and_its_pre_fix_record_preserved`. Turned from a
  defect reproduction into a defect regression test; the pre-fix evidence is
  preserved with its hash in `KNOWN_DEFECTS_PRE_FIX.json`.

### NOT CHANGED

- The frozen v1 core. Zero diff on `FROZEN_PATHS`.
- Every research finding, report, CSV and claim ledger.
- `MaxAge["gnss.position"]` vs the core's `STALE_TIMEOUT_S["gps"]`. Banked.

### TEST COUNT

971 -> 984.

---

# PHASES 2-3B (summary; full detail in V1_1_CHATGPT_REVIEW_REPORT.md)

### ADDED
- Phase 2 `engineering/v1_1/support/` — support state, identifiability,
  ambiguity, prior sensitivity. Diagnostic METADATA only; the production
  posterior is bit-identical with and without it.
- Phase 3A `engineering/v1_1/ablation/` — GRAPH vs FLAT. Verdict
  `GRAPH_NO_MATERIAL_GAIN`.
- Phase 3B five-arm architecture selection T0-T4. Decision
  `E: TRUST_FLAT_PLUS_SEQUENTIAL`.

### NOT CHANGED
- The frozen v1 core. Zero diff throughout.
- `csia/trust_engine/engine.py:110` still contains the neighbour-trust
  weighting. Nothing was deleted.

### TEST COUNT
984 -> 1040.

---

# PHASE 4 — ARCHITECTURE FREEZE, ELIGIBILITY, LEDGER, OUTPUT API

### ADDED

- **`csia/v1_1/`** — the v1.1 runtime layer, outside the frozen path.
  - `trust_mode.py` — `LEGACY_NEIGHBOR_PROPAGATION` / `FLAT_V1_1`,
    default FLAT. LEGACY returns the FROZEN `TrustCore` class itself, so v1
    replay cannot drift from v1.
  - `sequential.py` — the CUSUM bank as the stateful per-tick form Phase 5
    ports. `k = 0.5`, `h = 500`, five covered nodes, in-control statistics
    frozen as constants. Page 1954; no algorithmic novelty claimed.
  - `eligibility.py` — deterministic function-eligibility policy.
  - `reason_codes.py` — loads `REASON_CODES.yaml`, the single source of truth.
  - `ledger.py` — the assurance ledger and its hash chain.
  - `advisory.py` — four advisory strings; imports no transport.
  - `output_api.py` — builds and validates the versioned payload.
  - `firewall.py` — operation-level default-deny read-only policy.
- **`engineering/v1_1/`** — `V1_1_ARCHITECTURE_FREEZE.md`/`.json`,
  `TRUST_MODE_VERSIONING.md`, `TRUST_MODE_REGRESSION.json`,
  `FUNCTION_REQUIREMENTS.yaml`, `FUNCTION_ELIGIBILITY_SPEC.md`,
  `FUNCTION_ELIGIBILITY_RESULTS.csv`, `FUNCTION_TRANSITIONS.json`,
  `REASON_CODES.yaml`, `ASSURANCE_LEDGER_SPEC.md`,
  `ASSURANCE_LEDGER_EXAMPLE.json`, `ASSURANCE_LEDGER_REPRODUCTION.json`,
  `csia_output_v1_1.schema.json`, `API_COMPATIBILITY.md`,
  `STALENESS_LAYER_AUDIT.md`, `PHASE4_COMPUTE.json`,
  `PHASE4_API_VALIDATION.json`, `PHASE4_CLEAN_RESULT.json`,
  `PHASE4_FIXLOSS_RESULT.json`, `PHASE4_DUAL_IMU_RESULT.json`.
- **`embedded/v1_1/GOLDEN_TRACE_PLAN.md`** — cases and comparison rule only.
  No C code, no frozen numbers.

### CHANGED (BEHAVIOUR, v1.1 CONSUMERS)

- **The default neighbour-edge weight is now `w = gate_e`.** A v1.1 consumer
  that names no trust mode gets FLAT. A v1 or research replay must name
  `LEGACY_NEIGHBOR_PROPAGATION` explicitly.
- **`current_valid` is now a versioned schema field**, not a bare one. This
  closes the last unversioned semantic change from Phase 1.

### FIXED

- A rule defect found after first evaluation and disclosed rather than
  absorbed: `PRIOR_SENSITIVE_LEADER` fired on any prior-sensitive leader
  instead of only one the function depends on. 90 -> 83 transitions; every
  changed cell a DEGRADED -> ELIGIBLE reclassification on an IMU mechanism.
  Recorded in `FUNCTION_ELIGIBILITY_SPEC.md` §6.

### NOT CHANGED

- **The frozen v1 core. Zero diff on `FROZEN_PATHS`**, still enforced by both
  the git-diff and the recorded-hash guards.
- `csia/trust_engine/engine.py:110`. The legacy line is still there; the
  default simply no longer selects it. Nothing was deleted.
- `STALE_TIMEOUT_S` and `MaxAge`. `STALENESS_LAYER_AUDIT.md` finds the
  disagreement is six of eight nodes, names PX4 `motor_esc` as the worst case,
  proposes one canonical rule and **does not adopt it**.
- `UNKNOWN` / unmodeled fault. Still NOT IMPLEMENTED.
- Every v1 research finding, report, CSV and claim ledger.

### VALIDATED

- Trust-mode regression: LEGACY and FLAT reproduce the Phase 3A/3B GRAPH and
  FLAT arms **bit-identically**, tolerance declared 0.0 and needed 0.0.
- 13 500 output payloads validate against schema 1.1.0.
- 159 ledger events over 9 mechanisms; 9/9 reproduce identically including
  every id and hash; 9/9 chains verify.
- Gates A-J all pass.

### TEST COUNT

1040 -> 1133.

---

# PHASE 4.5 — DEPLOYMENT-BLOCKER CLOSURE, REAL CONSUMER, GOLDEN FREEZE

### ADDED

- **`csia/v1_1/staleness.py`** — `build_runtime_stale_timeouts(platform)`.
  One canonical rule, no constant of its own; `MAX_AGE_MARGIN` is imported
  from the adapter where it was already declared.
- **`csia/v1_1/monitor.py`** — `csia-monitor`, the first real consumer of the
  v1.1 output schema. Imports no producer.
- **`engineering/v1_1/`** — `TRUST_MODE_FINAL_DECISION.md`,
  `STALENESS_RUNTIME_SPEC.md`, `API_CONSUMER_SPEC.md`,
  `API_CONSUMER_RESULTS.json`, `PHASE4_5_COMPUTE.json`,
  `api_consumer_stream.jsonl`.
- **`validation/v1_1/deployment/`** — `run_staleness.py`,
  `verify_phase4_unaffected.py`, `STALENESS_MATRIX.csv`,
  `STALENESS_REGRESSION_SUMMARY.json`,
  `PX4_MOTOR_ESC_STALENESS_{PRE,POST}_FIX.csv`,
  `PX4_ULOG_TOPIC_RATES.csv`, `PHASE4_REGRESSION_AFTER_TIMEOUT.json`.
- **`embedded/v1_1/`** — `build_golden.py`, `golden/` (11 cases, 13 500
  ticks, 964 KB), `MANIFEST.json`, `CORPUS_SHA256`,
  `NUMERIC_EQUIVALENCE_SPEC.md`, `DECISION_MARGIN_AUDIT.csv`,
  `PHASE5_AUTHORIZATION.md`.

### CHANGED (BEHAVIOUR, DEPLOYMENT PATH ONLY)

- **`csia/deploy/shadow.py` now passes `stale_timeout_s`** derived per
  platform from the channel contract. The live shadow path previously took
  the frozen defaults while the ULog CLI already passed an override.
  Measured effect: `baro` false-stale under ±30% jitter goes from 2.77%
  (ArduPilot) / 3.69% (PX4) to **0.00%**; worst hard-dropout detection
  latency goes from 0.56 s to 1.08 s, bounded by construction.

### FIXED — TWO OF MY OWN PHASE 4 CLAIMS

- **Phase 4 §68 predicted PX4 `motor_esc` would be stale ~90% of every
  publish period. It would not.** The node is INADMISSIBLE on both platforms
  — `esc.current` is a documented stub on each, `esc.rpm` is a stub on
  ArduPilot and `AVAILABLE_UNVALIDATED` on PX4 — so it never reaches the
  frozen core, withheld by qualification one layer before any watchdog runs.
  Pre- and post-fix CSVs both show `motor_esc_reached_core` False on every
  tick at 0.1 s **and** at 5.0 s. Committed as the negative result it is.
- **Phase 4 §68 said the node timeout is `min` over required channels.**
  It is `max`. No published number changes — every node's required channels
  share a declared rate — but a justification that happens to give the right
  answer is still wrong.

### NOT CHANGED

- **The frozen v1 core. Zero diff**, still enforced by both guards.
- `STALE_TIMEOUT_S` itself. The fix is an argument, never an edit.
- `csia/trust_engine/engine.py:110`. The legacy line stays; the default no
  longer selects it, and Phase 5 ports `FLAT_V1_1` only.
- Every Phase 4 result — verified structurally and behaviourally,
  `NO_BEHAVIOURAL_CHANGE`.
- `UNKNOWN` / unmodeled fault. Still NOT IMPLEMENTED.

### VALIDATED

- Gates A–I all pass. `PHASE5_READY: YES`.
- 11 golden cases frozen, Tier A run-length encoded **losslessly** (20 MB →
  964 KB, corpus hash unchanged), Tier B at stride 10 with full-series hashes.
- Tier-B tolerance derived from `u = 2⁻²⁴` **before any C exists**; a test
  asserts `embedded/` contains no C source.
- 2 of 13 500 ticks flagged `NUMERICALLY_NEAR_BOUNDARY`, both trust-threshold
  crossings, enumerated in advance for Phase 5.

### TEST COUNT

1133 -> 1211.
