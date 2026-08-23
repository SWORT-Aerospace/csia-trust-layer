# Dataset Deduplication Report

**Dataset:** `px4_public_v1` · **Generated:** `tools/build_dataset_manifest.py`
**Machine-readable:** `datasets/reports/deduplication_report.json`

## Summary

| Metric | Value |
|---|---|
| Logs in manifest | 26 |
| Files present locally | **0** (corpus not acquired — see provenance audit D-04) |
| Content hashes available | **0** |
| Exact duplicates confirmed | **0** |
| Exact duplicates *excluded* | **undecidable** without content |
| Near-duplicate candidate pairs | **2** |
| Files auto-deleted or auto-excluded | **0** — by policy |

## Exact duplicates

Requires SHA-256 over content. The corpus is absent, so this check is
**undecidable**, not "clean". Recorded as unresolved rather than passed.

## Near-duplicate candidates

Conservative signals: duration match (±0.05 s), identical sensor inventory,
matching vehicle id, matching firmware. Confidence: LOW = 1 signal,
MEDIUM = 2, HIGH = 3+.

| pair | duration | signals | confidence | action |
|---|---|---|---|---|
| two logs at 50.0 s | 50.0 s | duration (+inventory where equal) | LOW–MEDIUM | REVIEW_REQUIRED |
| two logs at 35.4 s | 35.4 s | duration (+inventory where equal) | LOW–MEDIUM | REVIEW_REQUIRED |

Duration collision alone is weak evidence — short PX4 test flights cluster at
round durations. These are **review candidates, not findings**. Neither is
excluded from exposure. If confirmed on acquisition, each confirmed duplicate
removes up to 30 s of monitored exposure (~1.6% of the corpus) and would raise
the alert rate slightly.

## Policy

Nothing is deleted. Duplicates are *marked* (`duplicate_of`) and excluded from
exposure totals by `csia/metrics/exposure.py`, never removed from disk or from
the manifest. Detection is a claim about identity; deletion is irreversible.
