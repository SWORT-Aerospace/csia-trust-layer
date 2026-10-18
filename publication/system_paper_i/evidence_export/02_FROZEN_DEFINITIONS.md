# 02 — Frozen definitions

**BLOCKING FILE.** Every exposure number in this export is meaningless
without these. They are quoted verbatim from source first; plain English
follows separately.

---

## 1. The four exposure quantities

### 1.1 Verbatim, from source

`research/wp_c8/four_quantity_metrics.py`, commit `3597f18c953e52111978f09af17c9432c6b794c9`:

```
so the quantity splits four ways. Let A_h = 1 mean the test for hypothesis h is
applicable at this tick, and F_h = 1 mean the injection schedule says h is
truly present.

    T_NA    = time{ A_h = 0 }                              inapplicable
    T_UH    = time{ A_h = 0  AND  healthy }                unsupported healthy
    T_FH    = time{ F_h = 1  AND  healthy }                false healthy
    T_SOFH  = time{ F_h = 1  AND  A_h = 0  AND  healthy }  self-occluded
                                                           false healthy

```

### 1.2 As re-emitted into the result artifact

`research/wp_c8/results/four_quantity_metrics.json`, key `decomposition`:

```json
{
 "T_FH": "time{ F_h = 1 AND healthy } false healthy",
 "T_NA": "time{ A_h = 0 } inapplicable",
 "T_SOFH": "time{ F_h = 1 AND A_h = 0 AND healthy } self-occluded false healthy",
 "T_UH": "time{ A_h = 0 AND healthy } unsupported healthy"
}
```

### 1.3 Field-by-field contract

| item | T_NA | T_UH | T_FH | T_SOFH |
|---|---|---|---|---|
| **indicator** | `A_h = 0` | `A_h = 0 AND healthy` | `F_h = 1 AND healthy` | `F_h = 1 AND A_h = 0 AND healthy` |
| **units** | seconds (also emitted as a fraction) | seconds / fraction | seconds / fraction | seconds / fraction |
| **denominator** | `window_ticks` | `window_ticks` | `window_ticks` | `window_ticks` |
| **needs ground truth** | no | no | **yes** | **yes** |
| **estimable from an unannotated corpus** | yes | yes | **no** | **no** |

**The denominator, exactly.** `window_ticks` counts ticks satisfying all of:

```
    if not (st.armed and st.t >= PREREG["arm_time_s"]):
        return
    if not (INJECT_S <= st.t < INJECT_S + WINDOW_S):
        return
    acc["window"] += 1

```

so: armed, layer time at or past `arm_time_s`, and inside
`[INJECT_S, INJECT_S + WINDOW_S)`. With `TICK_S = 1/tick_hz`:

- `tick_hz` = 25.0
- `WINDOW_S` = 25.0 s
- `arm_time_s` = 20.0 s (`research/wp_c6/q_gvalid_campaign.py` `PREREG`)

Seconds are `count * TICK_S`; fractions are `count / window_ticks`.

### 1.4 How A_h and F_h are computed

```
    silenced = support_state(st)
    # A_h = 1 means the test for h is applicable at this tick.
    a_h = not silenced.get(TARGET, False)
    if not a_h:
        acc["na"] += 1
    # F_h = 1 comes from the injection schedule, never from the layer.
    f_h = ARM_GROUND_TRUTH.get(arm_name, False)
    if f_h and recovery_at is not None and st.t >= recovery_at:
        f_h = False
```

`A_h` inverts `support_state`, `research/wp_c7/false_healthy.py`, commit
`9daa084926dbee1e76179cbc7d8e60f34bb7ac0a`:

```
def support_state(st):
    """Per hypothesis: is its entire evidence support silenced at this tick?"""
    out = {}
    for h, feats in CAUSES.items():
        if not feats:                       # `nominal` has no support
            continue
        avail = [feature_available(st, f) for f in feats]
        known = [a for a in avail if a is not None]
        out[h] = bool(known) and not any(known)
    return out
```

**`F_h` never comes from the layer.** It is the injection schedule, declared
per arm in `ARM_GROUND_TRUTH`, and it is switched off after a recovery time
where one is scheduled.

### 1.5 `healthy` depends on which channel is scored

Three status channels are scored from the same tick stream. Each defines
`healthy` differently, and the four quantities are reported per channel.

```
def deployed_status(st, level_name):
    """What the shipping system reports overall, in four-state vocabulary.

    This folds in the failsafe level, which means the freshness disjunct
    rescues it: under denial the level leaves NORMAL about 1.5 s after onset
    without the diagnosis contributing anything. Reporting only this number
    would understate the attribution failure, which is why
    `attribution_status` below is measured alongside it.
    """
    top = st.top_causes(1)[0]
    if level_name != "NORMAL":
        return "FAULT"
    return "HEALTHY" if top[0] == "nominal" else "FAULT"


def attribution_status(st):
    """What the DIAGNOSIS says, with the failsafe excluded.

    This is the channel the paper's claim is about: naming the cause. The
    freshness disjunct does not consult it and cannot rescue it.
    """
    return "HEALTHY" if st.top_causes(1)[0][0] == "nominal" else "FAULT"


def abstaining_status(st, level_name, silenced):
    """The counterfactual. Research code only; nothing in production changes.

    If any hypothesis's entire support is silenced, the system cannot assert
    health with respect to that hypothesis and says so, EVEN IF the failsafe
    is otherwise quiet. A fault signalled by another channel still wins,
    because a known fault is more actionable than an abstention.
    """
    if level_name != "NORMAL":
        return "FAULT"
    if any(silenced.values()):
        return "NOT_APPLICABLE"
    top = st.top_causes(1)[0]
    return "HEALTHY" if top[0] == "nominal" else "FAULT"
```

### 1.6 Relations between the four

Directly from the indicators, for a fixed channel and window:

- `T_SOFH = time{ F_h = 1 AND A_h = 0 AND healthy } <= min(T_UH, T_FH)`
- `T_UH <= T_NA` (both require `A_h = 0`; `T_UH` adds `healthy`)
- `T_FH` and `T_UH` are **not** ordered in general: one conditions on ground
  truth, the other on applicability.
- `T_SOFH = 0` while `T_FH > 0` is the signature of a fault that is missed
  **while its evidence remained applicable** — a sensitivity failure, not
  self-occlusion.

### 1.7 Plain English

- **T_NA** — time the system held no applicable test for `h`. Says nothing
  about whether `h` was present.
- **T_UH** — time the system said "healthy" while holding no applicable test.
  The verdict may still be right by luck; it is unsupported, not false.
- **T_FH** — time the system said "healthy" while `h` was actually present.
  This is the false one, and it requires injected ground truth.
- **T_SOFH** — time the system said "healthy" while `h` was present **and**
  `h` had removed its own applicability. This is self-occlusion.

### 1.8 Superseded version

An earlier single quantity named `T_FH` measured `A_h = 0 AND healthy`, i.e.
what is now `T_UH`. It was **refuted and split** because it called an
unsupported verdict a false one. Recorded in `10_CORRECTIONS_LEDGER.md`. The
four definitions above are the final frozen set; no other definition of these
symbols is current anywhere in the repository.

---

## 2. Self-Occlusion Index (SOI)

### 2.1 Verbatim

`research/wp_c3/effective_signature.py`, commit `8464417e9e377d8a2886fe405e85a0ee27998569`:

```
def soi(low, unknown_as=False):
    out = {}
    for h, feats in low.items():
        if not feats:
            out[h] = {"soi": None, "n_features": 0, "silenced": [],
                      "note": "empty LOW set; SOI undefined"}
            continue
        sil = sorted(f for f in feats if silences(h, f, unknown_as))
        out[h] = {"soi": round(len(sil) / len(feats), 4),
                  "n_features": len(feats), "silenced": sil}
    return out
```

### 2.2 Normalization

**SOI is RELATION-NORMALIZED (feature-normalized).** It is not
duration-normalized, not channel-normalized and not event-normalized.

```
SOI(h) = |{ f in LOW(h) : h silences f }| / |LOW(h)|
```

- **numerator** — features in `h`'s LOW set that `h` itself silences, via
  `silences(h, f)`: `f` is gated by some gate `g` and `closes(h, g)` is true.
- **denominator** — `|LOW(h)|`, the number of features in `h`'s LOW signature
  set. Undefined (`None`) when that set is empty.
- **range** — [0, 1]. Dimensionless.

### 2.3 The effective signature matrix it rests on

```
S_eff[f,h] = S[f,h] AND NOT (exists g in gate(f): closes(h,g))
```

Computed against the **post-promotion** matrix:
`computed against the POST-PROMOTION signature matrix, i.e. with attitude_gravity_mag already in imu0_bias_drift (WP-C3 promotion)`

### 2.4 Derivation of SOI(gps_fault) = 1.0

Two settings differ only in how the 3 `UNKNOWN` cells of the `closes` table
are read. `gps_fault` is 1.0 in both.

| reading | SOI(gps_fault) | features in LOW(gps_fault) | silenced |
|---|---|---|---|
| unknown as open | 1.0 | 1 | `phys_gps` |
| unknown as closed | 1.0 | 1 | `phys_gps` |

So `1` of
`1` features that would name a GPS fault
are gated by a gate that a GPS fault closes. The ratio is 1.0 by construction
of the numerator equalling the denominator, not by rounding.

**Closure coverage.** `closes` is derived from source for
29 of 32 cells
(0.9062); the
3 `UNKNOWN` cells are
`gps_fault/speed_gate`, `power_fault/speed_gate`, `unexpected_maneuver/speed_gate` and are reported both
ways above.

### 2.5 Full SOI ranking (unknown as open)

| hypothesis | SOI | features | silenced |
|---|---|---|---|
| `gps_fault` | 1.0 | 1 | `phys_gps` |
| `imu0_bias_drift` | 0.0 | 3 | none |
| `imu1_bias_drift` | 0.0 | 2 | none |
| `mag_interference` | 0.0 | 4 | none |
| `nominal` | undefined | 0 | none |
| `power_fault` | 0.0 | 5 | none |
| `unexpected_maneuver` | 0.0 | 1 | none |
| `vibration_anomaly` | 0.0 | 3 | none |

**Artifact:** `research/wp_c3/results/effective_signature.json`
**Script:** `research/wp_c3/effective_signature.py`
**Commit:** `8464417e9e377d8a2886fe405e85a0ee27998569`
**SHA256 of artifact:** `8a38a4e21f10007ab92d5892af3a74b103674a1c88218631eb880d6f51c55667`
