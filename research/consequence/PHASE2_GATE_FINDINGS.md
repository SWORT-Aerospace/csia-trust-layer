# Phase 2 — uncovered-occlusion enumeration

**Evidence level: `SOURCE_ANALYSIS`.** This is what `csia/runtime/online.py`
says the gates do. Whether a closure occurs in a given run, and with what
consequence, is a separate question at a higher evidence level and is **not**
answered here.

Artifacts: `results/GATE_INVENTORY.json`,
`results/INDEPENDENT_GATE_EVALUATION.json`.

## The structure the phase turns on

`online.py` multiplies every evidence term by its own gate **and** by the
freshness of the sensors involved:

```python
E = {key: (lam, gate * fresh[a] * fresh[b]) ...}
P = {n:   (lam, gate * fresh[n]) ...}
```

So evidence disappears two ways, and they are not the same thing:

* **`FRESHNESS_COUPLED`** — the gate closes only when the sensor is also stale
  or invalid. A freshness monitor sees the same event.
* **`FRESHNESS_INDEPENDENT`** — the gate closes while the sensor's own data is
  fresh and valid. Nothing in the freshness path reacts.

The second class is H1's subject.

## Counts

| quantity | value |
|---|---|
| evidence terms enumerated | 18 |
| `ALWAYS_OPEN` | 7 |
| `FRESHNESS_COUPLED` | 3 |
| `FRESHNESS_INDEPENDENT` | 8 |
| uncovered candidates, **including** the withdrawal path | **8** |
| uncovered candidates, **excluding** it | **7** |

**Both counts are reported because the difference is a judgement, not a
measurement.** `hist_vr_withdrawal` is not a multiplicative gate on `E` or `P`;
it sets `hist` and `vr` to `None` when a channel's adaptive level exceeds 25.
It has H1's exact shape — evidence vanishes, data stay fresh, no freshness
signal marks the absence — and it is the most self-referential case, since a
channel withdraws its own evidence precisely when its residuals are largest,
which is also when a fault is most likely. Excluding it on a technicality about
where the multiplication happens would hide that. A reader who disagrees can
recount; the inventory carries both numbers.

**On the alleged eight.** A figure of eight has been asserted elsewhere. This
enumeration reached eight *including* the withdrawal path and seven without.
The agreement in the first case is not treated as confirmation: the membership
of whatever list produced the earlier figure has not been compared, and until
it is, the match is a coincidence of totals rather than corroboration.

## The eight candidates

| gate | protects | closes when | why uncovered |
|---|---|---|---|
| `accel_motor_current` | accel vs current-derived thrust | disarmed, or in the 1 s spin-up ramp | `armed_gate` is vehicle state, not data health |
| `accel_esc_rpm` | accel vs rpm-derived thrust | same | same, other IMU |
| `heading_course` | mag heading vs GPS course | horizontal speed below 2 m/s | closing is **correct** — course is undefined at low speed — and the relation still vanishes unmarked |
| `temp_bias_drift` | baro temperature rate | never opens fully | constant 0.2 weight, permanently attenuated |
| `phys_gps` | GPS self-consistency | first 3 s after start | `tau > 3.0` warm-up, GPS fresh and valid throughout |
| `phys_mag` | field norm vs reference | until a reference is established | `mag_ref_ready` |
| `phys_vibration` | vibration vs rpm envelope | ESC telemetry stale | **cross-sensor**: gated by a *different* sensor's freshness while the vibration channel's own stays green |
| `hist_vr_withdrawal` | temporal-predictor evidence | adaptive level above 25 in field mode | withdrawal, not a gate; see above |

`heading_course` deserves emphasis: the gate is *right*. Ground course is
meaningless below a few m/s and feeding it in would be worse. H1 is not a claim
that these gates are bugs. It is a claim that the **absence of the relation is
not reported**, and a correct gate that silently removes attribution capability
is exactly as uncovered as an incorrect one.

## Independent corroboration, and an honest note on sequence

`independent_gate_evaluator.py` imports the standard library only — not the
inventory, not `csia.runtime.online`, not any `csia` module, asserted by a test
that inspects `sys.modules` in a fresh interpreter. It parses the gate
expressions out of the source text and classifies them by what they depend on.

It reaches the **same seven** freshness-independent terms as the hand-read
inventory, plus the withdrawal path, for eight.

**The two disagreed on the first run.** The evaluator mis-parsed four terms and
missed every `P[...]` term, because their commas sit inside a wrapping
parenthesis and it was splitting on the last comma in a regex slice. Those were
parse defects in the evaluator and were fixed as such. **The fixes were made
after seeing the disagreement.** They are defensible on their own — a term that
does not parse is a bug in the parser, not a finding about the code — but the
sequence is recorded here and in the test's docstring so a reader can weigh it
rather than take the agreement at face value.

Two edge terms, `velocity_gps_doppler_0` and `_1`, are assigned through a loop
variable and are **not** matched by the evaluator's literal-key pattern. They
are absent from its evaluation rather than defaulted, and the limitation is
recorded in its output. The inventory classifies them as `gvalid`-gated, i.e.
freshness-coupled, so their absence does not change either count.

## What this does not establish

Nothing about runtime. Nothing about consequence. Nothing about prevalence in
any other codebase. No claim that a closure ever occurred in a real run, that
it mattered, or that any vehicle behaved differently because of one. Those are
Phases 3 and 6, and they have not been run.
