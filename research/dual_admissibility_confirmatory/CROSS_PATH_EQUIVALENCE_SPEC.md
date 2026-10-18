# Cross-path semantic equivalence specification

Item 19. A separate systems-assurance result. **It is not combined
statistically with the main experiment**, and it has its own artifacts and its
own conclusion.

## The question

Three committed ingest paths decode the same raw condition:

| Path | On `fix_type < 3` | Verified at |
|---|---|---|
| `csia/aircraft/adapters/` (v1.1) | deletes the channels, records `NO_3D_FIX`, emits **no** core sample | `ardupilot.py:228-236`, `base.py:317` |
| `csia/runtime/plugins.py` (v1 live MAVLink) | emits a core sample with `valid=False` and **zero** pos/vel | `plugins.py:157-159` |
| `csia/runtime/ulog_source.py` (v1 ULog replay) | emits a core sample with `valid = fix >= 3` and the **real** pos/vel | `ulog_source.py:189` |

Does the choice of decoder alone change `A`, `D`, freshness, or the
mechanism state, for identical input?

## Method

Canonical traces over the alphabet `{V, I, N}` — a 3D fix, a no-fix message,
no message — replayed through each path into the same frozen core.

**Comparison is on semantics, not on stamps.** The v1.1 adapter stamps a
sample with the tick it handed it over on; the v1 decoder stamps with the
message's own receive time. A tick-by-tick diff reports that as a semantic
difference when it is not. The compared projection is therefore:

* `ever_slot_invalid` — does this path ever tell the core the sensor is
  invalid?
* `A_ever_closed` and the A-closed tick count, **reported separately and not
  counted as semantic divergence on its own.**

## What the exploratory pass found

120 words up to length 4: **79 diverge semantically**, shortest divergent word
`'I'` — a single no-fix message. 106 differ in A-closed tick counts, which
includes the stamping effect and is reported apart.

## Confirmatory scope

`ulog_source.py` was **not** exercised: it requires a ULog file and none is
available in this checkout. Its semantics are established by source audit
only, and the confirmatory run will say so rather than implying three paths
were compared when two were.

The confirmatory pass adds:

1. The full alphabet to length 5 (363 words), all three projections recorded.
2. A **shortest distinguishing trace** per diverging path pair.
3. The same comparison run under each of `C0`, `C1`, `C2` — because path
   divergence may itself interact with the admissibility semantics, and if it
   does that is worth knowing before either is changed.

## Reported conclusion

A standalone verdict, one of:

* `PATHS_SEMANTICALLY_EQUIVALENT` — no divergence found up to length 5.
* `PATHS_DIVERGE` — with the shortest witness and the affected projection.

This is a defect report about the codebase. It carries **no** novelty claim and
no statistical content, and it stands whether or not the main experiment
succeeds.
