# The retained-state model

The brief offered `g(t) = 1[t - t_last < tau]` as a candidate and said not to
force the source into it if additional terms exist. They do, and the shape of
the extra terms is the finding, so the derivation starts from source.

## Symbols

| Symbol | Meaning | Source |
|---|---|---|
| `A` | times of **accepted** GPS samples — those that reached `_apply` | `online.py:302` |
| `t_A(t)` | `max{a in A : a <= t}`, undefined if `A` is empty before `t` | — |
| `v(t)` | `slot.valid` at `t` | `online.py:316` |
| `s(t)` | `slot.seen` at `t` | `online.py:314` |
| `tau_gps` | `STALE_TIMEOUT_S["gps"] = 0.5` s | `online.py:48` |
| `f_n(t)` | `fresh[n]` at `t` | `online.py:603` |

Note that `A` is the set of **accepted** samples, not of observations. That
substitution is the whole mechanism.

## Stage 1 — the slot

`seen`, `last_t` and `valid` are written in one place, `_apply`, and cleared
nowhere (verified: the only `.valid =` in `online.py` is line 316; `slots` is
constructed once at line 200). So for `t` after the first accepted sample:

```
s(t) = 1
last_t(t) = t_A(t)
v(t) = valid flag of the sample at t_A(t)
```

and before it, `s(t) = 0`, `v(t) = 0`, `last_t(t) = -1e9`.

## Stage 2 — the platform term

On the **v1.1 aircraft-adapter path** the hand-off writes
`chans["valid"] = True` unconditionally (`base.py:334`) and emits nothing at
all when a channel is unusable (`base.py:319`). So on that path

```
v(t) = s(t)                       (v1.1 adapter path)
```

— `valid` carries no information beyond `seen`. On the **v1 `plugins.py` and
`ulog_source.py` paths** the flag is the receiver's own:

```
v(t) = 1[fix_type at t_A(t) >= 3]  (v1 paths)
```

and on those paths a rejected observation is *itself* an accepted sample, so
`A` is the set of all observations and `t_A(t)` advances regardless.

## Stage 3 — the two gates

```
gvalid(t) = v(t) . s(t)
f_gps(t)  = v(t) . s(t) . 1[t - t_A(t) <= tau_gps]
```

`gvalid` has **no time term**. `fresh` has one, measured from `t_A`.

## Stage 4 — the effective gate

Every relation carrying `gvalid` also carries `fresh` for both its endpoints
(`online.py:610-613`; endpoint resolution verified in
`results/SOURCE_TO_GATE_TRACE.json`, all four have `gps` as an endpoint), so
for a relation `r` with endpoints `{gps, m}`:

```
G_r(t) = gate_r(t) . gvalid(t) . f_gps(t) . f_m(t)
       = gate_r(t) . v(t) . s(t) . 1[t - t_A(t) <= tau_gps] . f_m(t)
```

## The model, on the deployed path

Substituting `v = s` gives the equation this work is about:

```
G_gps(t) = 1[A is non-empty before t] . 1[t - t_A(t) <= tau_gps]
```

Compare the brief's candidate, `1[t - t_last < tau]`. Three differences:

1. **`t_A`, not `t_last_observation`.** The clock is reset by accepted samples
   only. A rejected observation is invisible to it. This is the mechanism.
2. **A separate "ever accepted" term**, which is what `gvalid` alone reduces to
   and which never falls once set.
3. **`<=`, not `<`.** Immaterial except exactly at the boundary instant — and
   that is precisely where the six boundary-tick disagreements in the sweep
   land (see below).

## Consequences, derived

For a maximal interval `(t_L, t_R)` containing no accepted sample, with
`G = t_R - t_L`:

```
gate open   on (t_L, t_L + tau_gps]
gate closed on (t_L + tau_gps, t_R)
masked duration           = min(G, tau_gps)
masked fraction of gap    = min(1, tau_gps / G)
```

With observations at period `p`, the ticks whose *most recent observation* was
invalid occupy `[t_L + p, t_R)`, so

```
masked fraction of invalid-observation ticks = clamp((tau_gps - p) / (G - p), 0, 1)
```

Three things follow that are worth stating separately, because they are what
make the behaviour non-obvious:

* **Density does not determine masking.** Only the largest gap between
  accepted samples does.
* **Higher observation rates mask more, not less.** A faster stream makes
  every gap shorter for the same invalidity density.
* **There is no accumulation.** A thousand rejected observations separated by
  one accepted fix each are exactly as invisible as one rejected observation.

## Does the model match the implementation?

`boundary_sweep.py` computes `G_gps(t)` from the message schedule and compares
it against the core's published `fresh["gps"]` at every tick, over 26 runs
spanning two observation rates and six temporal patterns.

| | |
|---|---|
| Runs | 26 |
| Agreement | 1.0 on 20 runs, 0.998857 on 6 |
| Total disagreeing ticks | 6 |
| Disagreements further than one tick period from a predicted transition | **0** |
| Max distance from a disagreement to the nearest transition | **0.0 s** |

All six disagreements sit exactly *on* a transition instant. That is the
`<=`-versus-`<` boundary combined with the fact that the core stamps `last_t`
with the tick it handed the sample over on, not the message receive time —
a 0.04 s quantisation. Away from transitions the model is exact.

The model is therefore **validated to within one tick period**, which is the
resolution at which the implementation can be distinguished from it at all.
