# Phase 7 — CSIA-Lite, the independent reproduction (H6)

**Evidence level: `DETERMINISTIC_SIMULATION` for its own numbers,
`SOURCE_ANALYSIS` for what it says about CSIA.** Nothing here executed an
autopilot, ran SITL, touched hardware, or measured an aircraft.

| artifact | path |
|---|---|
| implementation | `research/consequence/csia_lite/lite.py` |
| artifact builder | `research/consequence/csia_lite/demo.py` |
| generated numbers | `research/consequence/results/CSIA_LITE_DEMO.json` |
| tests | `tests/test_consequence_lite.py` |

Every figure below is quoted from the generated JSON. A test rebuilds it and
fails if the committed file disagrees, so a stale number cannot survive here.

---

## What H6 asked

> A CSIA-Lite implementation reproduces the two mechanisms without importing
> the proprietary CSIA implementation.
>
> **Killed if:** the reference implementation cannot reproduce them, or can
> only do so by importing the production modules.

**H6 is not killed.** Both halves hold: the mechanisms reproduce, and a fresh
interpreter that imports `lite` loads no `csia` module.

## The limit, stated before the result

Independent of the **code**, not of the **author**. The same author wrote
`csia_consequence/support.py` and this, days apart. So this is a cross-check on
the derivation, not a replication by a second party, and calling it one would
be a worse error than not writing it at all.

What gives the cross-check its value is that it takes a **different route**:

| | production | CSIA-Lite |
|---|---|---|
| separability decided by | set algebra — symmetric difference of the LOW-sets | numeric — is the maximum \|log-likelihood ratio\| non-zero |
| gate handled by | membership in the active set | a multiplicative weight in the likelihood |
| enumerates observations | n/a | no — the ratio is a sum of independent per-feature terms, so its extreme is closed-form |

A test restricted to the three deciding functions (`log_likelihood`,
`max_abs_llr`, `separable`) fails if any of them ever reaches for `^` or
`symmetric_difference`. That test is scoped honestly: `support()` *does* use
`(k in A) != (k in B)` when it reports **which** features separate a pair, and
that is a symmetric difference in all but spelling. It runs after the numeric
verdict is already taken, so it decides nothing — and pretending otherwise by
writing a check that happens to pass would be the same dishonesty this phase
studies.

Agreement is then checked on 500 randomized instances (1–4 hypotheses, 6
features, gate weights drawn from `{0.0, 0.0, 0.25, 1.0}`), seeded from the
preregistered **development** partition. A companion test breaks Lite's verdict
on purpose and confirms the comparison notices — a cross-check that cannot fail
proves nothing.

## Mechanism 1 — a relation disappears with nothing stale

Three hypotheses over three features, **constructed** so that one pair is
separated by exactly one feature. The construction is an illustration, not a
finding.

| hypothesis | LOW features |
|---|---|
| `h_pitot_blocked` | `f_airspeed_vs_ground`, `f_airspeed_vs_throttle` |
| `h_wind_shear` | `f_airspeed_vs_throttle` |
| `h_static_port_blocked` | `f_baro_vs_gnss_alt` |

Closing the gate on `f_airspeed_vs_ground` — the relation both PX4 and
ArduPilot suspend outside fixed-wing flight, per the phase 6 audit — while every
measurement stays fresh:

| | support | reason | unseparated |
|---|---|---|---|
| all gates open | `IDENTIFIABLE` | `ALL_PAIRS_SEPARATED` | — |
| one gate closed | `AMBIGUOUS` | `SOME_PAIRS_UNSEPARATED` | `h_pitot_blocked` / `h_wind_shear` |
| all gates closed | `NON_IDENTIFIABLE` | `NOTHING_SEPARATES_ANY_PAIR` | all |

The pair's maximum \|LLR\| is **exactly `0.0`** after the gate closes, against
`2.197` before. Not "small" — the terms cancel, so the number is zero, and a
test asserts the literal.

**Freshness is not a variable in this module at all.** Nothing in `lite.py` can
represent a staleness signal, so the change in the answer cannot be blamed on
one. That is the point of writing the demonstration this way rather than
modelling freshness and setting it to 1.

## Mechanism 2 — the posterior answers anyway

With the same gate closed, the normalized posterior is:

| hypothesis | posterior |
|---|---|
| `h_pitot_blocked` | **0.4969** |
| `h_wind_shear` | **0.4969** |
| `h_static_port_blocked` | 0.0061 |

The two tied candidates are the pair the evidence can no longer distinguish.
The distribution sums to one, `max()` returns a value near 0.5, and a consumer
reading `argmax` gets **"pitot blocked, 49.7%"** — a number produced by
dictionary order. Nothing in the posterior marks it as a coin flip.

That is the whole argument for reporting support before confidence, and here it
is arithmetic rather than assertion.

## What redundancy does, and why the first draft failed

The first version of the demonstration used LOW-sets in which the two airspeed
hypotheses *also* differed on `f_baro_vs_gnss_alt`. Closing the airspeed gate
changed the support state not at all: it stayed `IDENTIFIABLE`.

That failure is kept in the record because it is the honest shape of the
mechanism. **Occlusion bites only where the closing relation is the sole
separator of two candidates.** A redundantly instrumented system absorbs the
same gate closure without losing identifiability. Any write-up that shows the
occlusion without showing this is overstating it.

## What this phase may not conclude

- Not a measurement of anything.
- Not evidence about PX4, ArduPilot, or any aircraft. The feature names are
  borrowed from the phase 6 audit to make the toy legible; no autopilot was
  run.
- Not a replication by an independent party. See the limit above.
- Not a validation, not a safety argument, and not a claim that abstention
  solves anything. `AMBIGUOUS` is a report that the question cannot be
  answered, not an answer.
- Nothing about hardware.

## Removal action

A genuine independent reproduction needs a second implementer working from the
preregistration and the published mechanism description alone, without reading
`csia_consequence`. That is a people problem, not a code problem, and no amount
of further work in this repository closes it.
