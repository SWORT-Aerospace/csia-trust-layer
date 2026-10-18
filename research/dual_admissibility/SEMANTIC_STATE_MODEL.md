# The semantic state space

Only the states this implementation can actually express are defined. Item 4
offers seven candidates; four of them have no representation anywhere in this
tree and are recorded as absent rather than invented.

## Observation state `O_j(t)`

| State | Represented here? | Where |
|---|---|---|
| `OBSERVED_VALID` | **yes** | `GPS_RAW_INT` with `fix_type >= 3` |
| `OBSERVED_INVALID` | **yes** | `fix_type < 3`; the adapter records `MissingReason.NO_3D_FIX` |
| `NOT_OBSERVED` | **yes** | no message; ages to `MissingReason.NOT_RECEIVED` or `STALE` |
| `STALE` | **yes, but as a DOWNSTREAM state** | `MissingReason.STALE` at the adapter, `(tau - last_t) > STALE_TIMEOUT_S` at the core. It is not an upstream observation; it is what retention produces. |
| `RETAINED` | **implicitly** | the core slot holds `latest`, `valid`, `last_t` with no marker that the value is held rather than current. There is no `RETAINED` symbol. |
| `IMPUTED` | **no** | nothing in this tree substitutes a modelled value for a missing one. |
| `ESTIMATED` | **no, and deliberately** | `estimator.variances` is the only estimator-derived channel and the contract sets `csia_may_use = False` on it. |

The minimum the study needs — and the maximum the source supports as *upstream*
states — is the first three.

## The two admissibility variables

```
A_j(t) in {0,1}   operational admissibility
D_j(t) in {0,1}   diagnostic evidential admissibility
```

**As implemented** (`SOURCE_VALIDITY_ROLE_AUDIT.md`):

```
A_gps(t) = D_gps(t) = fresh["gps"](t)
         = valid . seen . 1[t - t_last_accepted <= 0.5 s]
```

one value, both roles.

**Under the split**, `D` is decomposed by what the evidence is *about*:

```
A_gps(t)         unchanged; the value gate stays where the frozen core puts it
D_value(t)       = A_gps(t)                 -- the navigation value never
                                               becomes admissible evidence
                                               while the receiver disowns it
D_status(t)      = 1[t - t_last_message <= 0.5 s]
D_hacc(t)        = 1[hacc_valid(last usable h_acc message)]
                   . 1[t - t_that_message <= 0.5 s]
```

Two things about this are load-bearing and easy to get wrong:

1. **`D_status` is gated on MESSAGE arrival, not on sample acceptance.** That
   is the only thing separating "the receiver reported no fix" from "no
   message arrived". Gate it on anything derived from `last_t` and the status
   feature fires on transport starvation, which would be worse than having no
   status feature at all. The transport control tests exactly this.

2. **`D_hacc` requires a usable `h_acc`, not merely a message.** The first
   version of this study gated it on message arrival, which reproduced the
   retained-state defect the previous work package documented: a healthy
   pre-onset accuracy kept being served as a current statement while every
   arriving message carried `h_acc = 0`. That was found by looking at a
   result, so the corrected arms (`S2b2`, `S2c2`) are labelled POST_HOC
   everywhere they appear.

## Value versus status

The split is only defensible if the invalid navigation value stays out. Each
field is classified in `results/VALUE_VS_STATUS_EVIDENCE_MATRIX.csv` by a
single question: **does this field's meaning depend on the navigation solution
being valid?**

* `gnss.position`, `gnss.velocity` — **VALUE**. Meaningless without a solution.
  Deleted by the adapter on `fix_type < 3` and never admitted by any arm.
* `fix_type`, `h_acc`, `satellites_visible`, `eph` — **STATUS**. Statements the
  receiver makes about itself. `h_acc` is an accuracy estimate, not a function
  of the reported position.
* message arrival — **PROVENANCE**. Not evidence about the receiver; the gate
  that makes status evidence meaningful.

`v_acc`, `vel_acc`, `hdg_acc` are status fields that this work package does
**not** use, because nothing here established their semantics. Leaving usable
signal on the table is the correct default when the contract has not qualified
it.

## What the frozen core lets a wrapper express

`DiagnosisCore.step(features)` takes `{name: (c, gate)}` with `c` in `[0,1]`,
and skips any feature with `gate <= 1e-9`. So the wrapper can express
`D_j = 0` (omit or zero the gate) and `D_j = 1` with any consistency. It
cannot express partial admissibility except through the gate, which is a
weight, not a probability. Both arms use `gate in {0, 1}` only.

## What is NOT expressible without touching the frozen core

* **A per-feature `A`.** `fresh` is per-SENSOR. A relation cannot be
  operationally inadmissible while its endpoint sensor is admissible.
* **A `RETAINED` marker.** The core slot has no field saying "this value is
  held". Everything downstream infers currency from `last_t`, which is exactly
  the quantity the previous work package showed is measured from the wrong
  event.
* **Distinguishing `STALE` from `NOT_OBSERVED` at the core.** Both are
  `fresh == False` with no reason attached. The adapter knows which; the
  hand-off cannot say.
