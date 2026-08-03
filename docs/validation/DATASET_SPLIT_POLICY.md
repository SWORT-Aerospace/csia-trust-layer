# Dataset Split Policy

**Version:** 1.0.0 · **Implementation:** `csia/datasets/manifest.py` ·
**Enforced by:** `tests/test_datasets.py`, CI

## Partitions

| Partition | Meaning | Restricted |
|---|---|---|
| `DEVELOPMENT` | Freely inspected during design. Contaminated by definition. | no |
| `THRESHOLD_TUNING` | Used to select thresholds. | yes |
| `REGRESSION` | Pinned expected results; changes must be deliberate. | yes |
| `HELD_OUT_EVALUATION` | Never inspected during development. | yes |
| `BLIND_EXTERNAL` | Labels withheld; for third-party evaluation. | yes |
| `UNASSIGNED` | Not yet classified. Cannot back any claim. | no |

## Rules

1. **Data inspected during development is not blind.** Irreversible — looking
   at it cannot be undone by reassigning a field.
2. **Data used to select thresholds is not held out.**
3. **Time windows from the same flight cannot span partitions.** Splitting one
   flight leaks the vehicle, environment and sensor set across the boundary.
4. **Related logs share a `split_group_id`** — same aircraft, same campaign,
   same session.
5. **Duplicates and transformed copies stay in one partition.**
6. **Synthetic scenarios from one family and parameter source are grouped.**
7. **Assignment is deterministic and version-controlled**, in
   `datasets/manifests/*.json`.
8. **Changing a split requires a dataset-version change** — a new
   `dataset_id`, not an edit in place.

## Enforcement

`check_split_leakage()` fails if one `split_group_id` appears in two
*restricted* partitions. `check_tuning_not_heldout()` fails if a log flagged
`used_for_threshold_tuning` or `used_for_architecture_design` sits in
`HELD_OUT_EVALUATION` / `BLIND_EXTERNAL`, or is marked blind-eligible. Both
run in CI.

`DEVELOPMENT` is intentionally unrestricted: it is the contaminated pool, and
overlap within it carries no information.

## Current assignment

**All 26 logs of `px4_public_v1` are `DEVELOPMENT`**, one split group
(`px4_public_v1_all`), all flagged `used_for_threshold_tuning=true` and
`used_for_architecture_design=true`.

`field_mode` — adaptive residual normalization, χ²-tail tolerance, anti-alias
downsampling, minimum-rate channel screening — exists *because of* these logs.
The offline failsafe posture (`arm_time=20`, `dwell_up=3`, `att_caution=0.45`)
was chosen against them.

**Held-out evaluation exposure: 0.000 h. Blind evaluation exposure: 0.000 h.**

This is not a defect in the split policy; it is the honest state of the
evidence. Every future acquisition must be assigned *before* inspection, and
a portion reserved untouched.
