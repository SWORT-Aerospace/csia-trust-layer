# Do local preservation guarantees compose?

Item 21. **Short answer: yes, trivially, and the trivial theorem is standard
and useless here — because the stage that breaks composition in this pipeline
would satisfy any per-stage contract you could reasonably write for it.**

---

## The trivial direction

Let `T = T_n ∘ … ∘ T_1`, and let `~_i` be the equivalence at the output of
stage `i`. Say stage `i` **preserves** the pair `(r1, r2)` when

```
T_i(a) ≁_i T_i(b)   whenever   a ≁_{i-1} b
```

i.e. `T_i` is injective on the quotient by `~_{i-1}`. If every stage preserves,
then `T(r1) ≁_n T(r2)` by induction. That is it. This is the composition of
injections and it is not a result; the general compositional statement is
assume-guarantee refinement, which is well developed (Benveniste et al.;
Pacti, ACM TCPS 2025; AG refinement via LP, 2021) and **not claimed here** —
item 21 says not to, and there is nothing to claim.

The interesting question is the contrapositive, and it has bite.

## Why per-stage contracts would not have caught this pipeline

Take the GNSS collapse. Each stage, judged **on its own**, is defensible:

| stage | a reasonable local contract | does it hold? |
|---|---|---|
| `T2_decode` | "read `fix_type` correctly and do not fabricate a position" | **holds** — `ardupilot.py:228` |
| `T3_ingest` | "on an explicit no-value report, discard the retained value and record a specific reason" | **holds** — `ardupilot.py:232-235`, records `NO_3D_FIX` |
| `T4_channel` | "never serve a value the producer has withdrawn; report a `MissingReason`" | **holds** — `base.py:198-229` |
| `T5_core_bridge` | "emit only channels that are admissible; never emit a fabricated value" | **holds** — `base.py:306-337` |
| `T6`–`T9` | "gate evidence on admissibility" | **holds** — `engine.py:146` |

Every stage passes. The end-to-end property fails anyway, because
`T5_core_bridge`'s **output alphabet is too small to carry the input
distinction**. Its contract says nothing false; it simply cannot say `I`.

So the composition failure is not a broken guarantee. It is a **missing
requirement**: no stage contract mentions the cardinality of the alphabet it
must be able to express, because a per-stage contract is written in terms of
that stage's own vocabulary.

## The condition that actually matters

Stage `i` preserves the required distinctions iff, for the declared partition
`P` on raw states,

```
|image of T_i restricted to the distinctions P requires|  ≥  |P|
```

— an alphabet-width condition, not a behavioural one. Measured widths in this
pipeline:

| stage | distinct tokens it can carry |
|---|---|
| `T1`/`T2` | 3 per family |
| `T4_channel` | up to 6 observed; `MissingReason` defines 7 |
| **`T5_core_bridge`** | **2** — emit with `valid=True`, or emit nothing |

`base.py:335` writes `chans["valid"] = True` unconditionally and the only
alternative is `continue`. A three-state input cannot survive a two-state
channel, and no amount of care in stages 1–4 changes that.

**This is the data-processing inequality with the constant made explicit, and
the data-processing inequality is known.** Item 20 says so and no novelty is
claimed. What the measurement adds is only that the bottleneck in *this*
pipeline is a single named line, and that four upstream stages are doing
correct work whose output that line discards.

## Is there a useful domain-specific corollary?

Item 21 asks. The candidate is:

> For a sensor-ingest pipeline, the end-to-end preservation of a declared set
> of source states is bounded by the narrowest inter-stage interface, so a
> contract on any single stage is insufficient; the interface widths must be
> declared and checked jointly.

Assessed honestly: **this is a restatement of the min-cut / bottleneck
argument in domain clothing.** It is worth writing in an engineering
guideline. It is not a theorem, it is not new, and it should not be presented
as either. `CLAIM_LEDGER.json` records it as `KNOWN/SUBSUMED`.

## What the checker does that a per-stage contract does not

One concrete difference, and it is the only one:

* A per-stage contract is checked against **that stage's** specification.
* The checker fixes a pair of raw states the *whole pipeline* must keep
  apart, and asks each stage whether it still keeps them apart, so it can
  name the first stage that does not.

The three families give three different answers on the same path, which is
the evidence that the localisation is doing work rather than always pointing
at the same boundary:

| family | v1.1 adapter, first collapse |
|---|---|
| gnss (`I` vs `N`) | `T5_core_bridge` — `base.py:306-337` |
| battery (`X` vs `V`) | `T5_core_bridge` — `base.py:306-337` |
| mag (`Z` vs `N`) | **`T3_ingest`** — `base.py:140-177` |

The magnetometer collapses **two stages earlier** than the other two, because
`ardupilot.py:143` has no `else` branch at all: an all-zero triple produces no
`_put` and no `_reject_sentinel`, so the adapter's retained state after `Z` is
byte-identical to its state after `N`. GNSS and battery at least *record*
something before the bridge discards it; the magnetometer records nothing.

## Multi-stage vs single-stage, on the other two paths

`plugins_py` and `ulog_source_py` have **no `T3` or `T4` at all** — they map a
message directly to a core sample. The checker reports this as
`no_representation_stage: ["T3_ingest", "T4_channel"]` and refuses to name a
collapse site in a file those paths never execute.

The consequence is instructive. Having fewer stages makes them **better** on
the GNSS clause (both PASS; the v1.1 adapter FAILs), because with no
representation stage there is nothing to lose the reason *in* — the decoder's
`valid=False` goes straight through. It makes them **worse** on the battery
clause, because there is also nowhere to notice a sentinel: `plugins.py`
fabricates `0.00 A` and `ulog_source.py` forwards `−1.00 A`.

Neither is a design lesson this package is entitled to draw from three
families in one codebase. It is recorded as an observation.

## References

Compositional verification and assume-guarantee contracts are cited in
`PRIOR_ART_MATRIX.md`. The relevant point for this document is that the
general theory is complete and none of it is at issue: the gap here is that
nobody wrote the joint requirement down, not that the theory is missing.
