# Intermittent invalidity masking — report for independent review

**Status: source audit complete, mechanism characterised and measured, no
large campaign run.** The brief said not to preregister or launch one, and none
was launched. Everything below is either a static read of committed source, a
reanalysis of one already-committed recording, or a deterministic replay of a
programmed schedule over that recording's non-GPS telemetry.

Reproduce: `make invalidity-masking` (about one minute; the sweep dominates).

---

## 1. The one-paragraph version

The v1.1 ArduPilot adapter handles a lost GPS fix correctly and deliberately:
it deletes the stale position, records the *specific* reason `NO_3D_FIX`, and
its own comment says **"a lost fix is information"**. That information is then
destroyed one function later, because `to_core_samples` can express only two
states — *sample* or *nothing* — where the receiver reported three, and every
sample it does emit carries `valid=True` hard-coded. The frozen core therefore
cannot tell *"the receiver says it has no fix"* from *"no message arrived"*,
and its validity gate times out from the last **accepted** sample rather than
from the last **observation**. One accepted fix inside the 0.5 s window resets
that clock, so intermittent invalidity — however dense — never closes the gate.

On the one real jamming episode available, 29% of GPS observations reported no
fix and the gate stayed open for **100%** of the affected ticks. On a
synthetic schedule at 80% invalidity the gate never closed once in 35 seconds.

And then the result that runs the other way: **this did not weaken detection.**
See §5.

---

## 2. What was verified, and how

`source_to_gate_trace.py` pins 28 source facts. Each is a pattern required to
occur **exactly once** in its file; the script fails if a pattern is missing or
ambiguous, so a refactor breaks the artifact rather than silently invalidating
it. Full text and per-file SHA-256 in `results/SOURCE_TO_GATE_TRACE.json`.

The item-3 statement is adjudicated in `SOURCE_TO_GATE_TRACE.md`:
**`PARTLY_TRUE`** — true of the deployed v1.1 path, false of the two committed
v1 paths, which propagate invalidity instead.

### The correction that mattered

The first reading of the source was that `gvalid` (`online.py:482`) has no
staleness term at all, so the gate could *never* close. That reading is
**wrong**, and it is recorded as superseded in the claim ledger. All four
`gvalid`-carrying relations turn out to have `gps` as an endpoint — resolved
from `csia.trust_graph.EDGES` rather than assumed — so all four are also
multiplied by `fresh["gps"]`, which does have the timeout. The gate closes; it
just measures from the wrong event. The missing term in `gvalid` is a **latent
hazard** (any future relation carrying `gvalid` without `gps` as an endpoint
would inherit an uncloseable gate), not the mechanism.

---

## 3. The mechanism, exactly

Derived in `RETAINED_STATE_MODEL.md`. On the deployed path:

```
G_gps(t) = 1[ever accepted a sample] . 1[t - t_A(t) <= 0.5 s]
```

with `A` the set of **accepted** samples. The brief's candidate
`1[t - t_last < tau]` differs in the one place that matters: `t_A` ignores
rejected observations entirely.

Consequences, all derived and then measured:

- masked duration per gap = `min(gap, 0.5 s)`
- **density does not determine masking** — only the largest accepted-sample gap does
- **faster observation rates mask more**, because every gap gets shorter
- **no accumulation** — 1000 rejections separated by single accepted fixes are exactly as invisible as one

Model versus implementation, 26 runs across two rates and six patterns:
6 disagreeing ticks in total, **all six exactly on a transition instant**, none
further than one tick period from one. The model is exact away from the
0.04 s quantisation at which `last_t` is stamped.

---

## 4. The measurements

### Real recording, `NON_SCORED_TEST_FIXTURE_M1` (N = 1 episode)

ArduCopter V4.8.0-dev @ 01a504b, `SIM_GPS1_JAM = 1` at t = 7.004 s.

| | |
|---|---|
| Post-onset `GPS_RAW_INT` | 2004 (delivered 50.1 Hz) |
| Reporting no fix (`fix_type = 1`) | 582 — 29.0% |
| Longest continuous invalid interval | 0.343 s |
| Largest gap between accepted fixes | 0.363 s (timeout is 0.500 s) |
| Ticks with `gvalid == 0` | **0 of 999** |
| Ticks with the effective gate closed | **0 of 999** |
| Masking fraction | **1.000** |

The gate never closed because the longest run of continuous invalidity was
shorter than the timeout — by 0.137 s.

### The distinction really is destroyed — tested, not asserted

Two streams, identical except that in one the invalid messages are delivered
and in the other they are simply absent. Deployed path, per-tick comparison:

> **1175 ticks × 13 core-state fields → 0 differing cells.**

The adapter, meanwhile, *did* retain the distinction: `sentinel_counts()`
differs between the two. The information exists and is discarded at the
hand-off. (`results/INDISTINGUISHABILITY_CHECK.json`)

### Arrangement beats density (H2)

Same number of invalidated messages out of the same stream at the same rate;
only the arrangement moves:

| Arrangement | Density | Largest accepted gap | Masking fraction | Gate closed |
|---|---|---|---|---|
| One contiguous burst | 0.398 | 14.20 s | **0.023** | 13.68 s |
| Clustered 4-in-10 | 0.409 | 1.00 s | **0.400** | 8.64 s |
| Interleaved 2-in-5 | 0.403 | 0.60 s | **0.800** | 2.80 s |

A factor of 35 in masking at constant density.

### Rate makes it worse, not better

`P2_PERIODIC_INTERLEAVE`, four invalid for every one accepted:

| Rate | Density | Masking fraction | Gate closed |
|---|---|---|---|
| 5 Hz | 0.801 | 0.400 | 16.80 s |
| 50 Hz | 0.800 | **1.000** | **0.00 s** |

Same duty cycle. At the higher rate the gate never closes at all.

### Null controls (Rule A)

An instrument that reports masking on every input measures nothing.

| Control | Expected | Measured |
|---|---|---|
| `P0_ALL_VALID` | no masking possible, gate always open | 0 invalid ticks, gate open throughout |
| `P5_PERMANENT` | gate MUST close, one timeout after the last accepted fix | closed 34.68 s of the 34.98 s post-onset window; masking fraction 0.008 |
| DROP replayed twice | byte-identical | identical |

---

## 5. The result that runs against the framing

**Masking did not weaken fault detection on this recording. It strengthened it.**

| | DROP (masking) | PROPAGATE_INVALID_HOLD |
|---|---|---|
| Final `gps_fault` posterior | **0.892** | 0.722 |
| Ticks with `gps_fault` as top cause | **963 / 999** | 836 / 999 |
| Minimum `trust_gps` | **0.197** | 0.235 |

Closing the gate on an invalid observation also withdraws the physics evidence
that was detecting the jam. Propagating invalidity makes the system *abstain*,
and abstention is not detection.

This is kept, and stated before any of the interpretation, because the work
package was framed in a direction the evidence does not support. What masking
*actually* changes is measurable and narrower:

> Under DROP, an open gate vouched for a GPS measurement up to **0.360 s** old
> on a stream whose nominal period is 0.020 s — **18 nominal periods**. Under
> either propagating policy the maximum was 0.000 s.

That is the real statement: masking does not hide the *symptom*, it extends
how stale the measurement behind an open gate may be, and it removes the
receiver's own health report from the evidence available for *attribution*.

---

## 6. Hostile review

**A. "This is a staleness timeout working exactly as designed. There is no
finding."**
Partly conceded, and it is why the verdict is not "new mechanism". The timeout
does work as designed. What is not by design is that it is measured from
accepted samples while the adapter one layer up has explicitly established a
three-valued vocabulary (`MissingReason`, whose docstring reads *"Never
collapse these to None"*) and then cannot express it across the interface. The
falsifiable content is the arrangement-versus-density result: a system whose
watchdog behaved as an operator would assume would show masking as a function
of invalidity *density*. It does not — factor 35 at constant density.

**B. "Your `PROPAGATE_INVALID` control is a strawman you wrote yourself."**
Rejected on the facts. `csia/runtime/plugins.py:157-159` and
`csia/runtime/ulog_source.py:189` are **committed code** implementing exactly
that semantics for the same raw condition, feeding the same frozen core. The
research subclass exists only to run it on the same bytes and the same cadence
as the deployed path — a one-factor control, verified by test to override three
methods and change one parameter. Conceded: the subclass is not itself
deployed code, and `PROPAGATE_INVALID_ZERO` reproduces v1's *semantics* on
v1.1's *cadence*, which is not the same experiment as running v1's path.

**C. "N = 1. You have one recording."**
Fully conceded, and labelled as such in every artifact. The real-recording
numbers are properties of one realisation, not estimates over runs. No
interval, no p-value, and no statistical claim appears anywhere in this
package. The mechanism claims (H1, H3) do not rest on that recording — they
rest on the source trace and on deterministic replay, where there is nothing
to sample.

**D. "The synthetic fixture is fabricated data."**
Partly conceded, and scoped accordingly. The GPS validity schedule is
programmed and the GPS payload is one real fix held constant. That fixture is
used to measure **the gate and nothing else**, which the source trace shows is
a function of *which samples are accepted and when* — never of their values
(facts G1–G4). The sweep therefore reports no trust and no posterior numbers.
Every such number in this package comes from the real recording.

**E. "You measured a gate. You did not show anything bad happened."**
Conceded, and §5 says so more strongly than a reviewer would: the one
consequence measured runs the *other* way. The defensible harm statement is
narrow — an open gate vouching for a 0.36 s-old measurement, and the loss of
receiver-reported health as an attribution input — not "missed detection".

**F. "This is not novel."**
Not contested. `CLAIM_LEDGER.json` records novelty as `NOT_ESTABLISHED`; no
literature search was performed. `PRIOR_ART_SEARCH_TERMS.md` flags **on-off
attacks on trust and reputation systems** as the most likely place this already
exists under another name, because the arrangement-versus-density result is
structurally the same shape. No adversary model was built and no attack claim
is made.

---

## 7. Verdict

**Primary: `KNOWN_BEHAVIOR_NEW_INSTANCE`.**

The mechanism is real, exactly characterised, and validated against the
implementation to within one tick period. It is almost certainly an instance of
something already named elsewhere, the harm hypothesis it was framed around is
refuted on the available evidence, and no novelty search was run.
`STRONG_NEW_SYSTEMS_MECHANISM` is not available on this evidence and would not
survive review B or F.

**Secondary, and independent of the above: `USEFUL_IMPLEMENTATION_DEFECT`.**

Three committed ingest paths implement three different semantics for the same
raw condition (`fix_type < 3`), feeding the same frozen core, with nothing in
the repository documenting the difference. That is a defect whether or not the
masking matters, and it does not depend on preferring either semantics. The
`gvalid` latent hazard (§2) is a second, smaller one.

**No repair is proposed here.** The frozen core cannot be changed, the adapter
interface change is a design decision rather than a bug fix, and — given §5 —
it is not established that the current behaviour is the worse one. What is
established is that the choice is currently being made three different ways by
accident.

---

## 8. What a reviewer should attack next

1. **Get a second real episode.** Every real number here is N = 1. A second
   jamming recording with a different duty cycle would test whether the
   detection result in §5 survives, and it is cheap — the capture tooling
   exists.
2. **The `PROPAGATE_INVALID_ZERO` side effect.** `_apply` feeds the GPS step
   detector and the Holt predictor before consulting any validity flag
   (`online.py:371`, `:401`), and v1's propagated sample carries zeros. That
   perturbation was never measured on v1's own path. It is the strongest
   argument *against* naive propagation and it is currently unquantified.
3. **Search the on-off-attack literature** before anyone writes the word
   "novel" in a paper draft.
