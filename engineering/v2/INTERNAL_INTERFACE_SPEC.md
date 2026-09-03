# THE HIGH-PERFORMANCE INTERNAL INTERFACE

Phase C §§15–20, 43. Implementation: `csia/v2/ingest.py`,
`csia/v1_1/output_api.py`. Evidence: `V2_PHASEC_COMPUTE.json`,
`INTERNAL_EXTERNAL_EQUIVALENCE.json`.

---

## 1. The 28 ms was a defect, not the cost of validation

Phase B measured ~28 ms per tick in what was labelled "the core". Timing each
domain separately showed the figure was almost entirely one call:
`jsonschema.validate()`, which **re-checks and re-compiles the schema on every
invocation**.

| path | µs/tick | note |
|---|---|---|
| Phase B, uncached `jsonschema.validate` | 22130.0 | the defect |
| cached validator, same full validation | 673.6 | ~33× faster, nothing weakened |
| external full parse | 691.8 | strict boundary, unchanged semantics |
| external typed ingest | 644.0 | parse + typed construction |
| **internal typed ingest** | **9.2** | no schema walk at all |

Two separate improvements, reported separately because they are different
claims:

1. **Building the validator once.** This is a pure defect fix. The same
   validation runs, the same errors are raised, and a test asserts the
   replacement is byte-identical *including which error message
   `best_match()` selects* across the corpus. Nothing was traded away.
2. **The internal typed path.** This removes the schema walk entirely and is
   legitimate only under §20's conditions, below.

Hot path 22130.0 µs → 9.2 µs, a factor of 2405. **No target-hardware figure
exists and none is claimed**; these are CPython on a general-purpose host,
and they move by ±10% between runs on a shared machine. The two-thousand-fold
ratio is the claim; the third significant figure is not.

The Final Rule is the reason this work came before any decision-layer
optimisation: localization costs 46 µs median per tick against an interface
that was costing 22 ms. Optimising the decision would have been optimising
0.2% of the problem.

## 2. §20's conditions, in full

> Internal typed path may only be used: same process, version-locked
> components, construction-controlled objects. Any: network / IPC / file /
> untrusted / plugin boundary continues to require explicit validation.

All three conditions are enforced, not documented:

**Same process.** `NavigationDomainInput` is never serialised. A test asserts
no JSON is produced anywhere on the internal path — the moment an object
crosses a process boundary it must be serialised, so "no serialisation
exists" is a mechanical proxy for "no boundary was crossed".

**Version-locked.** `SUPPORTED_MAJOR_MINOR = ("1.1",)`. `__post_init__`
rejects any other major.minor by construction, so a wrongly-versioned object
cannot exist, let alone be consumed. `_from_parts` additionally re-reads the
frozen CUSUM constants (`CUSUM_H`, `CUSUM_K`) from `csia.v1_1.sequential` and
refuses a payload whose detector does not match them: a foreign detector
producing v1.1-shaped output is not v1.1 evidence.

**Construction-controlled.** The dataclass is frozen and every mapping is
wrapped in `MappingProxyType`, so a domain cannot mutate a caller's state.
The plugin contract's determinism guarantee has to survive the caller as well
as the plugin.

## 3. Two constructors, one type

```
    from_external_payload(payload)   calls csia.v1_1.monitor.parse
                                     -> the strict boundary. provenance="external"
    from_trusted_payload(payload)    structural checks only
                                     -> §20's fast path. provenance="internal"
```

Both converge on the **same typed object** before any evidence exists. That is
why equivalence is structural rather than coincidental: there is one record
builder downstream, and a test parses the AST of `domains/navigation.py` to
assert that the only builders called are `_evaluate_input` and `_missing`.

`provenance_path` is carried into the ledger so a replay can tell which
interface produced a run. It is **excluded from `semantic_key()`** — the same
evidence reached by two routes is the same evidence, and letting the route
into the key would make identical runs compare unequal.

## 4. Equivalence, measured

`INTERNAL_EXTERNAL_EQUIVALENCE.json`: **13,500 payloads across 9 mechanisms,
0 mismatches, `identical: true`.**

The comparison is the **full `SystemAssurance` document per tick** — domain
evidence, function results, cross-domain attribution, localization and plugin
status — not a summary. Zero tolerance: these are discrete outputs and a
single differing reason code is a failure.

| mechanism | payloads | mismatches |
|---|---|---|
| CLEAN, GNSS_RAMP_SLOW, GNSS_RAMP_FAST, GNSS_FIX_LOSS, IMU0_BIAS_DRIFT, DUAL_IMU_FAILURE, MAG_DEGRADED, POWER_SAG, VIBRATION_ANOMALY | 1500 each | 0 each |

## 5. What the external boundary still does

Nothing was removed from it. Every property v1.1's parser enforced is still
enforced on every payload that arrives from outside: schema validation, the
strict field checks, the rejection of unknown versions. A test feeds the
external path the payloads the monitor rejects and asserts it still rejects
them.

The fast path is an **optimisation between components that were already
inside the trust boundary**, not a relaxation of the boundary. If a caller
cannot satisfy all three of §20's conditions, the external constructor is the
only correct entry point, and it is now ~33× cheaper than it was in Phase B
regardless.

## 6. Per-phase cost (§43)

| phase | median µs/tick | max µs/tick |
|---|---|---|
| `api_build_and_evaluate` | 2745.4 | — |
| `domains_total` (six plugins) | 747.1 | 982.4 |
| `explanation` | 87.3 | 167.2 |
| `localization_alone` | 45.8 | — |
| `ledger` | 14.1 | 743.8 |

68 records and 9 symptoms evaluated per tick. The decision layer — the thing
Phase C added — is 45.8 µs. Everything expensive is upstream of it.
