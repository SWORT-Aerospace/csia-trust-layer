# engineering/v1_1 — CSIA v1.1 hardening

**Engineering, not research.** FIXED / HARDENED / VALIDATED / SIMPLIFIED /
IMPROVED. Nothing here is a novelty claim (item 48).

| | |
|---|---|
| frozen v1 tag | `csia-v1.0-research-final` @ `ec5acd1` |
| v1.1 start | `1ba69a5` |
| branch | `csia-v1.1-engineering` (local); pushes go to `claude/code-reviewer-repo-export-zicovg` |
| **Phase 1** | **COMPLETE** — canonical ingestion + known defect fixes |
| Phases 2–6 | not started |
| tests | 971 → 984 passing |

---

## What Phase 1 did

Four ingest defects, each **reproduced and hashed before being fixed**, then
fixed, then re-run with the same script.

| | raw condition | v1 said | v1.1 says |
|---|---|---|---|
| **D1** | `current_battery = -1` after a real 5.00 A reading | `5.0 A`, present, INFORMATIVE | absent, `SENTINEL` |
| **D2** | all-zero magnetometer triple | the previous field, present | absent, `SENTINEL` |
| **D3** | ULog `current_a == -1.0` | `-1.0 A`, valid | absent, invalid |
| **D4** | plugins `current_battery = -1` | `0.0 A`, valid | absent, invalid |
| **D5** | GNSS `fix_type < 3` *(control)* | absent, `NO_3D_FIX` | **unchanged** |

**Three decoders gave three answers to one raw condition — 5.00 A, 0.00 A,
−1.00 A. They now agree.**

The root cause of D1 and D2 was one asymmetry: `_put` cleared `_sentinel_at`,
so a value superseded an earlier sentinel — but `_reject_sentinel` did not
clear `_latest`, so a sentinel never superseded an earlier value. Since
`_channel_value` consults `_latest` first, the producer's disavowal was
recorded and then ignored, and the channel eventually died as **STALE** rather
than as the producer's own declaration. The GNSS path had worked around this
locally; that workaround is now the general rule, applied once.

## Files

| file | |
|---|---|
| `V1_1_ENGINEERING_MANIFEST.md` | **read first** — baseline, every production behaviour changed, every result requiring remeasurement, gate status |
| `KNOWN_DEFECTS_PRE_FIX.md` / `.json` | the frozen pre-fix record, `sha256 7fdd3d65…` |
| `KNOWN_DEFECTS_POST_FIX.md` / `.json` | the same script after the fixes, `sha256 7fff288a…` |
| `CANONICAL_INGEST_SPEC.md` | rules R1–R5, and why no new type was added |
| `channel_semantics/canonical_channel_semantics.yaml` | executable semantics for the four audited channels, every rule cited |
| `reproduce_defects.py` | the reproduction harness |
| `V1_1_CHANGELOG.md` | |
| `V1_1_TEST_MATRIX.csv` | |
| `V1_1_CHATGPT_REVIEW_REPORT.md` | the 30-item report |

Guards: `tests/test_v1_1_canonical_ingest.py` — `make v1-1-ingest-check`.
Reproduce: `make v1-1-defects`.

## The frozen core

Untouched. `FROZEN_PATHS` carries **zero diff** against the frozen tag and
`tests/test_v1_frozen.py` passes. Phase 1 needed no core change: fixing what
reaches the bridge did not require touching what is on the other side of it.

## What this invalidates

Several v1 research numbers describe ingestion that no longer exists — the
battery three-way split most obviously. **No v1 result was edited.** They stay
labelled v1; `V1_1_ENGINEERING_MANIFEST.md` §5 lists which require
remeasurement for v1.1, and the remeasurement has not been done.

Two research citation verifiers were **repointed**, not rewritten: they now
resolve `csia/` citations against the commit the citations were taken at
rather than against the working tree. A v1 claim verified against today's code
was wrong in both directions, and the v1.1 fixes proved it.

## What Phase 1 did not do

- No canonical `ChannelSample` type. `ChannelValue` already carries what item
  3 asks for except provenance, which belongs to Phase 9. Adding a second type
  would be the ontology inflation item 3 warns against — the gap was a rule,
  not a field.
- No five-path ingest-equivalence matrix. Four defect cases on three paths.
- No remeasurement of the affected research campaigns.
- No specs for phases 2–6. Item 52 forbids writing a layer's spec before the
  layer, and an empty file that looks like a deliverable is worse than none.

## Banked, deliberately not fixed here (item 37)

- `MaxAge["gnss.position"] = 1.00 s` vs the frozen core's
  `STALE_TIMEOUT_S["gps"] = 0.5 s` — the two layers disagree about when a fix
  goes stale. Not an ingest sentinel defect, and changing a freshness limit
  moves admissibility for every downstream result.
- `csia/runtime/ulog_source.py:66` — unused local `u`. Pre-existing; verified
  by lint on the stashed tree.
- `vibration.rms` provenance: its producer instance is selected at runtime
  from sensor health and the wire message does not say which. See
  `research/effective_evidence_independence/`. Phase 9 at the earliest, and
  Stage 0A item 33 forbids turning it into a production metric.
