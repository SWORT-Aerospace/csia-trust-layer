# CONTROLLER INTEGRATION

Phase C §§21–23, 31, 43. Implementation: `csia/v2/plugin_runtime.py`,
`csia/v2/ledger.py`. Evidence: `PLUGIN_FAILURE_RESULTS.csv`,
`LOCALIZATION_LEDGER.json`, `V2_PHASEC_COMPUTE.json`.

---

## 1. Plugin isolation (§21)

> Do not catch errors and continue as healthy.

Every domain runs behind `PluginSupervisor.run()`, which catches
`BaseException` around **`domain.evaluate` only**. A programming error in the
supervisor itself still raises: only the plugin's own call is inside the
boundary, so a bug in the supervisor cannot hide behind a domain's failure
state.

Four states, and none of them is "assume fine":

| state | meaning |
|---|---|
| `AVAILABLE` | ran, produced evidence, inside its deadline |
| `DEGRADED` | ran and overran its declared deadline |
| `FAILED` | raised |
| `NOT_CONFIGURED` | ran and produced nothing — configured to watch something this platform is not reporting |

`NOT_CONFIGURED` is deliberately distinct from both `FAILED` and healthy. A
plugin that ran and said nothing has told you something specific, and
collapsing it into either neighbour loses it.

A `FAILED` plugin emits `UNAVAILABLE` evidence **attached to every function it
declared**. The failure propagates as absence of evidence, which the function
graph already knows how to handle — `UNKNOWN` outranks `INELIGIBLE`, and no
evidence is not good news.

### Measured (`PLUGIN_FAILURE_RESULTS.csv`)

12 injections, 2 modes × 6 domains, on `NOMINAL`:

| mode | result | healthy claim from the failed domain | other domains still reporting |
|---|---|---|---|
| `raise` | `FAILED` in all 6 | **False** in all 6 | 5 of 5 in all 6 |
| `silent` | `NOT_CONFIGURED` in all 6 | **False** in all 6 | 5 of 5 in all 6 |

Blast radius varies by declaration and that is correct: POWER failing degrades
10 of 10 functions, ACTUATION 2 of 10. A domain-wide blast radius would mean
the per-component `affected_functions` wiring was not being read.

## 2. Watchdog (§22)

Each plugin may declare a deadline. Overrunning it increments
`deadline_misses` and sets `DEGRADED`. Consecutive errors are counted and held
across ticks — the supervisor is **deliberately stateful** while the domains
are stateless by contract, because "this plugin has failed nine times in a
row" is exactly the memory §22 asks for.

### The stopwatch does not reach the ledger

`PluginStatus` has two serialisations and the difference matters:

- `to_dict()` — everything, including `last_execution_s`, `max_execution_s`,
  `deadline_misses`. **Observability only.**
- `deterministic_dict()` — what may appear in the per-tick document and the
  ledger. Wall-clock figures are absent.

A wall-clock reading in the replayed document would differ between two replays
of the same trace, and the ledger's verifiability is the property everything
downstream assumes. This was found by the replay tests failing after the
supervisor was wired in; the fix was to split the serialisation, not to relax
the replay test. A further test asserts exactly one module imports `time` and
that nothing it measures reaches the per-tick document.

## 3. Plugin identity in the ledger (§23)

Every ledger context carries a `plugin_manifest_hash` built from each
registered plugin's `identity()`:

```
    domain_id, schema_version, configuration_hash, implementation
```

`configuration_hash` is derived from the plugin's own declarations, so
changing a threshold in a profile changes the hash. A replay against a
different configuration is detectable rather than silently different.

`DomainRegistry.replace()` exists so fault injection goes through the
registry's own API. Reaching into its private dict would let a future
refactor stop injecting anything while the watchdog tests continued to pass
against nothing.

## 4. The localization ledger (§31)

`LOCALIZATION_CHANGED` is a distinct event type carrying the full structured
localization. Its emission rule differs from a function state's, deliberately:

> A symptom **appearing** is itself the event.

For a function, the first observation is only a baseline — there is nothing to
report until it changes. For a symptom, the first observation *is* the news.
So a prior of `None` still emits, and the event carries §32's structure
verbatim: `initial_domains`, `supported`, `rejected` as
`(hypothesis, refuting predicate)` pairs, `unresolved`, `unmeasurable`.

Chain verification passes on every matched scenario, and a test asserts two
runs of the same trace produce byte-identical event lists.

## 5. Cost (§43)

| phase | median µs/tick | max µs/tick |
|---|---|---|
| six domains through the supervisor | 747.1 | 982.4 |
| localization | 45.8 | — |
| explanation | 87.3 | 167.2 |
| ledger | 14.1 | 743.8 |
| internal typed ingest | 9.2 | — |

68 records, 9 symptoms per tick. The supervisor's overhead is inside
`domains_total` and is two `perf_counter` reads plus a `try`.

## 6. What a controller integrator must know

1. **The internal typed path is for in-process, version-locked callers only.**
   Anything arriving over network, IPC, file, or from an untrusted or plugin
   boundary goes through `from_external_payload`, which validates. See
   `INTERNAL_INTERFACE_SPEC.md` §2.
2. **No command is ever issued.** This layer reports which functions are
   justified and by what evidence. Acting on that is the controller's
   decision, and nothing here has a path to an actuator.
3. **`UNKNOWN` is not `ELIGIBLE`.** A failed plugin makes functions `UNKNOWN`,
   and a consumer that treats absent evidence as permission has inverted the
   contract.
4. **`possible_domains` are not causes.** They are alternatives nobody could
   rule out. Presenting one as a diagnosis is the failure §2 forbids.
5. **The wall-clock fields are observability.** Do not put them in anything
   that has to replay.
