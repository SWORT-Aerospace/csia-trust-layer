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
