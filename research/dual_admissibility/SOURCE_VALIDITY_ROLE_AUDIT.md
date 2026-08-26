# Where "validity" does two jobs

Resolved from the working tree by `source_validity_role_audit.py`. Every cited
line is a pattern required to occur exactly once in its file, resolved to a
line number and then re-read to confirm that number before it is published.
16 gates, all verified. Per-file SHA-256 in
`results/SOURCE_VALIDITY_ROLE_AUDIT.json`.

## Definitions, narrower than the words suggest

**A — operational admissibility.** Whether a state may drive an action or an
operational recommendation. Inside this repository the only such consumer is
`FailsafePolicy`, and it is advisory: `csia/deploy/shadow.py` enforces no
command authority. The vehicle's own navigation stack is outside the tree.

**D — diagnostic evidential admissibility.** Whether a state may contribute to
`TrustCore` belief or `DiagnosisCore` likelihood.

**Coupled.** One value feeds both roles with no way to set them independently.

## Result

| | |
|---|---|
| Gates audited | 16 |
| Serving D only | 11 |
| Serving A only | 3 |
| **Coupled — one value, both roles** | **3** |

The three coupled gates are `CV_USABLE`, `SLOT_VALID_WRITE` and — the one that
matters — **`FRESH`**.

## The coupling, exactly

`fresh` is computed once per tick:

```python
# csia/runtime/online.py:603
fresh = {n: s[n].valid and s[n].seen
         and (tau - s[n].last_t) <= self._stale[n]
         for n in SENSORS}
```

and is then used for **both** roles from that single value:

*Diagnostic (D).* It multiplies every edge gate (`online.py:610`) and every
physics gate (`online.py:613`), and it gates the Beta update itself
(`csia/trust_engine/engine.py:146`, `if avail and fresh.get(n, True):`).

*Operational (A).* The same dict is published on `TrustState.fresh` and read
by the failsafe:

```python
# csia/runtime/failsafe.py:100
fresh = state.fresh
# csia/runtime/failsafe.py:144-146
if (T["gps"] < cfg.nav_caution and fresh.get("gps")) or \
        (not fresh.get("gps", True) and gps_was_monitored):
    why = "GPS data invalid" if not fresh.get("gps", True) \
        else f"GPS trust {T['gps']:.2f}"
```

which raises `nav_degraded` → `SWITCH_NAV_INERTIAL`, `INHIBIT_GPS_MODES`.

> **`D_gps == A_gps == fresh["gps"]` by construction.** The coupled
> architecture the research question asks about is not a hypothetical
> alternative; it is what is implemented.

## Why the coupling bites here specifically

`CAUSES["gps_fault"] == ["phys_gps"]` (`csia/diagnosis/bayes.py:47`). The
hypothesis has exactly **one** supporting feature, and that feature's gate
carries `fresh["gps"]`. So a GNSS fault that makes the receiver report no fix
closes the only gate that could evidence it. That is the formal condition in
`FORMAL_RESULTS.md` T2, satisfied by construction.

## The hypothesis is NOT refuted at source level

Item 34 asks whether the core already represents A and D independently. It
does not. Two near-misses are worth recording, because each is a place where
the distinction *almost* exists:

**`Quality.admissible` is scoped to evidence, not to operation.** Its docstring
reads *"Whether a present value may be used as diagnostic evidence"*
(`csia/aircraft/sample.py:32-47`). So the qualification layer's vocabulary is
already D-only. But `ChannelValue.usable` (`sample.py:115`) is then consumed by
both `to_core_samples` (D) and the operational sample view — `usable_channels`,
`_armed`, the flight log, `shadow.py:412`'s stale-tick counter. The **word** is
D-scoped; the **use** is coupled.

**`csia_may_use` is a second, independent gate — but both halves are about
evidence.** `ChannelContract.admissible` is `quality.admissible and may_use`
(`qualification.py:138`), and the docstring explains why they are separate:
`estimator.variances` is genuinely `INFORMATIVE` and must still never enter
diagnosis, because an assurance layer cannot be independent of an estimator it
consumes. That is a policy channel, not an A/D split.

## One existing partial decoupling, by omission

`temp_<sensor>` features are built with the gate hard-coded to `1.0`:

```python
# csia/runtime/online.py:630
feats[f"temp_{n}"] = (1.0, 0.0) if hist[n] is None else (
    float(np.exp(-0.5 * max(0.0, hist[n] - 1.0))), 1.0)
```

`hist[n]` is `slot.hist_val`, frozen at the last accepted sample. So `temp_gps`
keeps contributing a **retained** score after `fresh["gps"]` has closed —
`D != A` already, for one feature family. This does not look designed: it is
the same retained-state hazard the invalidity-masking work package documented,
appearing on the evidence path rather than the gate path. Recorded as an
observation, not as prior art for the split.

## Unconditional side effects worth knowing about

`_apply` feeds the GPS step detector (`online.py:371`) and the Holt historical
predictor (`online.py:401`; GPS is in `HIST_CHANNELS`,
`csia/prediction/predictors.py:56`) from **every emitted sample, before any
validity flag is consulted**. The committed v1 live-MAVLink path emits zeros on
`fix_type < 3` (`csia/runtime/plugins.py:158-159`), so on that path a lost fix
injects a fictitious position step into a detector whose job is catching
position steps. The gate suppresses the resulting evidence; the state change
has already happened.

## Full table

`results/SOURCE_VALIDITY_ROLE_AUDIT.csv` — one row per gate with file,
function, line, upstream state, downstream use, both role flags, whether it is
coupled, and the consequence of the gate being zero.
