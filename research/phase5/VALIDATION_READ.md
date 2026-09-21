# Phase 5 — the validation read, recorded as an event

**Read once, on 2026-09-21, after the preregistration and both amendments
were committed (`1e713ee`) and before the `locked` partition was opened.**

The preregistration permits exactly one validation read and requires that a
candidate failing its hypothesis here is **still carried to locked and
reported as failing**. Nothing was dropped, added or retuned after this read,
and this file exists so that claim is checkable rather than asserted.

## What validation showed

16 seeds, 544 runs, 0 invalid. Thresholds selected on `development` and
applied unchanged.

| hypothesis | validation verdict |
|---|---|
| H1 — hybrid latency | **SUPPORTED** — `B3`/`B4`/`B6` median 0.24 s against `B0` 2.54 s, gain 2.30 s, bootstrap intervals disjoint |
| H2 — assurance preservation | **SUPPORTED** |
| H3 — support-map correction | **SUPPORTED** — availability 0.000 → 1.000, exact McNemar p = 3.05 × 10⁻⁵ |
| H4 — multi-timescale | **SUPPORTED** |
| H5 — threshold robustness | **KILLED** — `B3`/`B4`/`B6` at 0.200 against `B0` at 1.000 |

Dominance: **`HYBRID_IMPROVES_LATENCY_ONLY`**, with clause 2 (*false alarms
no worse*) unmet.

## What was changed afterwards

**Nothing.** No threshold moved, no candidate was dropped, no hypothesis was
reworded and no margin was adjusted. The two arms that fail — `H5` for the
fast-path baselines, and dominance clause 2 — are carried to `locked` and
reported there as they fall.

## What this read is for

It is a rehearsal of the frozen design on seeds the parameters were not
chosen on, and nothing more. It is **not** a result, it is **not** pooled
with the locked evaluation, and no claim in any write-up rests on it. Its
only job was to confirm that the pipeline produces interpretable numbers
before the one partition that counts was opened — and to make it impossible
to later claim the design was frozen after seeing locked data, since the
failing arms were already on the record here.
