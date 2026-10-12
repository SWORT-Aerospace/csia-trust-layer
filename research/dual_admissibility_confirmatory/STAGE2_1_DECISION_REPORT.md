# STAGE 2.1 — DECISION REPORT

Base: `cea85f1` (preregistration, unmodified). The 10+10 confirmatory campaign
was **not** run. Three held-out matched pairs were captured and scored, which
is what item 4 asks for.

## Verdict

**`IMPLEMENTATION_DEFECTS_ONLY`.**

The kill test did its job. On genuinely held-out data with exactly matched `A`,
the coupled arm carries **no live mechanism information** — every field is
constant, frozen, or inherited-and-converging — and `C0_STRONG` scores **0.333
balanced accuracy**, below chance, after failing to fit its own development
data (in-sample 0.500). The status-only split scores **1.000** on all three
pairs.

That is CASE B: the split does provide information the coupled arm lacks. But
CASE B does not make it a research contribution. The principle is
`KNOWN/SUBSUMED` (SEVA, NAMUR NE 107), the operational recommendation was
already shown identical across every arm, and the status-only classifier's
success is close to definitional given its inputs. What is left is a set of
measured, fixable defects in this codebase and a checker that found them.

---

## 1. Was the ARINC NCD ≡ TRANSPORT_UNAVAILABLE mapping correct?

**No. It was wrong, and it is withdrawn.**

The SSM is carried **inside a transmitted word**, so all four states are
source-side statuses the source chose to send. `Failure Warning` = a failure
makes the data suspect. `No Computed Data` = data missing or inaccurate *for
some reason other than a failure* (autopilot command words carry NCD when the
autopilot is not engaged). **Both map to `SENSOR_INVALID`.**

Absence of the word has **no SSM encoding** — it cannot, since the SSM lives in
the word. ARINC 429 receivers detect a stopped transmitter or broken wire by
**refresh-rate monitoring**, de-asserting data-valid at ~`1.5 × T_refresh`.

Corrected mapping in `PRIOR_ART_CORRECTION.md` §1. The correction replaces a
wrong dismissal with a sharper one: separating invalid from absent requires an
in-band vocabulary **and** an out-of-band timeout, combined — and CSIA has both
ingredients but routes them into one variable.

## 2. What exactly does SEVA subsume?

The principle itself. SEVA sensors emit Validated Measurement Value, Validated
Uncertainty and **Measurement Value Status**, designed so a measurement can be
unsuitable for control while its status stays informative about what went
wrong. NAMUR NE 107 adds a prescribed operator-summary / technician-detail
split of the same device state.

So this claim is **not available**: *"it is new to distinguish operational
usability from diagnostic utility."* **`KNOWN/SUBSUMED`.**

## 3. Does any broad A/D novelty claim survive?

**No.** Five levels assessed separately (`PRIOR_ART_CORRECTION.md` §4):
principle `KNOWN/SUBSUMED`; status taxonomy `KNOWN`; consumer-side semantic
collapse, matched-`A` experiment and cross-ingest CI property each
`EMPIRICAL FINDING — NOVELTY NOT ESTABLISHED`; the checker technique
`KNOWN/SUBSUMED`.

## 4. Are the three held-out A trajectories exactly matched?

**Yes, all three, by hash.**

| Pair | scored ticks | `A` mismatches | `A_trace_sha256` equal | `A == 0` throughout |
|---|---|---|---|---|
| `PAIR_01` | 115 | 0 | **yes** | yes |
| `PAIR_02` | 190 | 0 | **yes** | yes |
| `PAIR_03` | 265 | 0 | **yes** | yes |

Scored window `[inject + 0.5 + 0.2, release − 0.5 − 0.2]`, taken from the
**recorded** intervention times rather than the commanded ones.

Mechanism separation at the wire, per `heldout_capture.py`:

| | `GPS_RAW_INT` during condition | fix types |
|---|---|---|
| `SENSOR_INVALID` ×3 | 301 / 451 / 601 | `{1: 300, 6: 1}`, `{1: 450, 6: 1}`, `{1: 600, 6: 1}` |
| `TRANSPORT_UNAVAILABLE` ×3 | 0 / 1 / 0 | `{}`, `{6: 1}`, `{}` |

## 5. C0_STRONG results on all three pairs

Threshold fitted on **development traces only** (six onsets), one value applied
to all three held-out pairs, exactly as `cea85f1` requires.
`theta = 0.937260277`, **in-sample accuracy 0.5000** — it could not separate
even the data it was fitted on.

| Pair | balanced accuracy |
|---|---|
| `PAIR_01` | **0.0000** |
| `PAIR_02` | 0.5000 |
| `PAIR_03` | 0.5000 |
| **mean** | **0.3333** |

Why: the frozen `trust_gps` values climb with onset time
(sensor `0.9359 → 0.9726` across the fit onsets) while the between-mechanism
gap is only ~1.3 × 10⁻³. The classes interleave completely, so no single
threshold works. The residue is **relational** — transport sits slightly above
sensor *at the same onset* — and no runtime rule can use that, because a
runtime classifier sees one mechanism, not both.

## 6. STATUS_ONLY_SPLIT results on all three pairs

**1.0000 balanced accuracy on all three.** Zero unresolved.

Honest qualification: the classifier reads "did a message arrive within
0.5 s, and did it report no fix", and the mechanisms are defined by exactly
that. Its success is close to definitional. **The informative half of this
comparison is C0's failure, not C2's success.**

## 7. Which C0 fields are live versus inherited?

Held-out, over the matched interval. **No field is `LIVE_INFORMATION`.**

| Field | Classification | Separation at closure → end |
|---|---|---|
| `temp_gps_component` | `CONSTANT` | 0 → 0 |
| `trust_gps` | `FROZEN_STATE` | 2.59e-3 → 2.59e-3 (never changes) |
| `post_gps_fault` | `PRE_CLOSURE_HISTORY` | 2.95e-3 → **3.6e-5 / 3.6e-7 / 4e-9** |
| `post_nominal` | `PRE_CLOSURE_HISTORY` | 2.94e-3 → 2.5e-4 / 2.1e-6 / 1.3e-8 |
| `post_unexpected_maneuver` | `PRE_CLOSURE_HISTORY` | 1.88e-7 → 1.6e-8 / 0 / 0 |

`trust_gps` freezes because the Beta update is gated on `fresh`
(`engine.py:146`). The posteriors **converge** — the longer the condition
lasts, the harder the mechanisms are to tell apart. The development sweep over
six onsets found the same: 48 `PRE_CLOSURE_HISTORY`, 30 `CONSTANT`, 6
`FROZEN_STATE`, **0 `LIVE_INFORMATION`**.

I predicted before measuring that `temp_gps` would leak live information,
because it is ungated (`online.py:630`) and a propagated invalid sample still
feeds the Holt filters. **That prediction was wrong** — it is `CONSTANT`,
because the HOLD semantics re-feed the last accepted value and the innovation
converges to the same place in both mechanisms.

## 8. What happens after inherited-state matching/removal?

Nothing survives. `any_discrimination_grows_after_closure = False`; every
`PRE_CLOSURE_HISTORY` field shrinks. Once the value at `A`-closure is taken as
the baseline, the coupled arm has **zero** discriminating signal.

*(An earlier version of this flag used `abs(sep_end − sep_closure) > 0`, which
counted a separation that shrank as evidence of live information — backwards.
Corrected.)*

## 9. Does the split still provide information unavailable to the coupled arm?

**Yes, and this is CASE B.** Under matched `A`, the coupled arm cannot
distinguish the mechanisms at any point in the pipeline; the status channel
distinguishes them perfectly. The information exists in the raw stream and the
coupled architecture discards it before any decision can use it.

What that does **not** establish: that it matters operationally (Stage 2 found
the failsafe outcome bit-identical across all arms), that it is new (§2–3), or
that it generalises past GNSS.

## 10. Does the cross-ingest-path semantic defect reproduce?

**Yes.** 120 words over `{V, I, N}` up to length 4:

* **79 semantic divergences** between the v1.1 adapter and `plugins.py` —
  "does this path ever mark the GPS slot invalid?"
* 106 tick-count divergences, reported separately because they also move with
  the stamping convention and are not attributable on their own.

`ulog_source.py` was **executed** on a real 9.6 MB PX4 ULog: 344 gps samples,
**0 with `valid=False`**. The log contains no `fix_type < 3` sample, so its
invalid branch is `NOT_EXERCISED` and its mapping remains source-established
only. Reported rather than glossed.

## 11. Shortest distinguishing traces

| Comparison | Shortest witness |
|---|---|
| v1.1 adapter vs `plugins.py` | **`'I'`** — one message reporting no fix |
| `S0` self-collapse (`I` vs `N`) | **length 1** |
| `S1` coupled self-collapse | `('VV', 'IV')`, length 2 |
| `S2c2` split self-collapse | `('III', 'INI')`, length 3 |

## 12. Counterexample-checker feasibility

**MEDIUM.**

For: it found the length-1 `I ≡ N` witness with no domain knowledge, found the
79 cross-path divergences, and **caught a real bug in this study's own
instrumentation** — the one-message phase misalignment — which the frozen
regression guard now re-injects and re-detects on every run.

Against: it is a dynamic search over a hand-coded three-symbol alphabet driving
concrete Python objects. The reusable interface item 15 describes — canonical
state-transition model in, equivalence plus shortest counterexample plus
responsible state fields out — would need a state-machine abstraction of each
ingest path that nothing here prototypes. `HIGH` would require that; `LOW`
would understate a search that has already earned its keep three times.

## 13. HIL criterion 0 executed?

**No.** Checked, not assumed: no `/dev/ttyUSB*`, `/dev/ttyACM*` or
`/dev/serial*`; `pyserial` reports only `/dev/ttyS0`, the container console.
**No physical hardware is attached and nothing here is a HIL result.**

## 14. If executed, exact hardware result

Not executed. But the **SITL analogue was measured** and it passes: with
`SIM_GPS1_ENABLE = 0`, ArduPilot @ `01a504b` keeps emitting `GPS_RAW_INT`
throughout the condition — 301 / 451 / 601 messages, `fix_type = 1` on all but
the one in-flight straggler. Explicit source invalidity *is* transported to the
consumer interface in simulation. That makes the hardware question worth
asking; it does not answer it.

## 15. If not, exact physical procedure

`HIL_CRITERION_0_PLAN.md`: Pixhawk-class board on ArduPilot `01a504b`, UBX
emulator on a host UART at 230400, `UBX-NAV-PVT` at 5 Hz, the
`VALID·VALID·INVALID·INVALID·VALID` sequence ×3, three clocks recorded and none
corrected, and a stated pass/fail — PASS if ≥ 90% of the pre-onset delivered
rate continues with `fix_type < 3` on ≥ 95% of messages. The `UBX-CFG-*` /
`UBX-MON-VER` handshake is called out as the bulk of the work.

## 16. Strongest KNOWN/SUBSUMED claim

*Operationally unusable data may remain diagnostically informative, and the
value/status split belongs at the interface.* SEVA and NAMUR NE 107.
**No part of the A/D framing survives as a contribution.**

## 17. Strongest POSSIBLE NOVEL CONTRIBUTION remaining

Stated at its honest strength, which is low:

> A consumer can decode a protocol-supplied status **correctly** and then
> destroy it, by routing an in-band invalidity report and an out-of-band
> absence timeout into a single admissibility variable — measurably, with a
> length-1 witness, and reproducibly across three committed decoders of the
> same codebase.

Status: **`EMPIRICAL FINDING — NOVELTY NOT ESTABLISHED`.** The search was
targeted, not systematic; absence of hits is not evidence of absence. This is
a defect report with a method, not a result.

## 18. Should the 10+10 confirmatory campaign be run?

**No.**

1. It would confirm what three pairs already settled. `C0_STRONG` at 0.333
   held-out after 0.500 in-sample does not improve with more trials — the
   classes interleave structurally, not noisily.
2. Its outcome cannot change the prior-art position, which is settled
   independently of any measurement.
3. The Stage-2 finding stands: the operational recommendation is identical
   across every arm, so neither outcome changes what an operator sees.
4. The remaining genuinely open question is **hardware criterion 0**, and no
   number of SITL captures addresses it.

---

## Decision

**`IMPLEMENTATION_DEFECTS_ONLY`.** Stop the architectural line. Bank the
defects:

| # | Defect | Status | Depends on the A/D question? |
|---|---|---|---|
| D1 | Consumer-side semantic collapse: `OBSERVED_INVALID` and `NOT_OBSERVED` produce identical core state on the v1.1 path. Length-1 witness. | measured | no |
| D2 | Cross-ingest-path non-equivalence: three committed decoders, three meanings for `fix_type < 3`, into one frozen core. 79/120 words diverge, shortest `'I'`. | measured | no |
| D3 | Battery retained invalid current: `-1` is sentinel-counted but the value is **not** deleted, so `5.00 A` is served as usable for 0.5 s after the producer disowned it — and the eventual absence reports `STALE`, not `SENTINEL`. | measured | no |

All three are fixable independently, and D3's fix is two lines mirroring the
GNSS handling.

**Do not** write "novel" anywhere. **Do not** run the campaign. **Do** run
hardware criterion 0 if the GNSS line is ever reopened.
