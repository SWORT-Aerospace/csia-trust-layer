# Vehicle profile vs deployment config

**Status:** CANONICAL for the boundary between `profiles/*.yaml` and
`configs/vehicle/*.yaml`.
**Written:** 2026-09-06, physical-validation program §1.
**Supersedes nothing.** FL-005 recorded this seam as *exposed and unresolved*;
this document resolves the *policy* question and deliberately leaves the
*unification* question closed.

---

## 1. The two files

This repository has two configuration files that both describe one vehicle.
That is not an accident and it is not a duplication to be cleaned up.

| | `profiles/*.yaml` | `configs/vehicle/*.yaml` |
|---|---|---|
| name | vehicle profile | deployment config |
| answers | *what does this airframe provide?* | *how do I connect to it, and how is this run recorded?* |
| written by | whoever integrates a new airframe | whoever sets up a particular bench or aircraft |
| changes when | the airframe changes | the bench, port, log destination or run changes |
| loader | `csia/aircraft/profile.py` | `csia/deploy/deployment.py` |
| consumed by | capability negotiation, `csia-edge validate` | `csia-shadow` (the runtime) |
| in the flight log | not yet | **yes — its SHA-256 is in every header** |
| may set a diagnostic parameter | **no, refused at load** | **two, and they are declared** |

The last row is the one that matters and it is the subject of §3.

## 2. Which file wins

Neither. **Disagreements are reported, never resolved.**

`csia-edge validate --profile P --deployment D` cross-checks the two and exits
**3** on any conflict, printing each one. It does not prefer either file.

The reason is specific rather than stylistic: the two files overlap on
autopilot family, and silently preferring one would decode a PX4 stream with
the ArduPilot dialect. The result is not a crash — it is a run that reports
channels missing that were arriving all along, which reads as a sensor fault.
A fallback would invent evidence.

Conflicts detected today (`csia/deploy/deployment.py:conflicts`):

| conflict | why it is not resolvable automatically |
|---|---|
| autopilot family | selects the message dialect; guessing invents faults |
| transport / port | the deployment config is authoritative for the link, but a profile that states a *different* one is describing a vehicle nobody is connecting to |
| a mode with command authority | refused at load, not reported as a preference |
| profile reference mismatch (schema 2) | validating one profile against another's deployment proves nothing about either |

## 3. The asymmetry, stated exactly

A **vehicle profile may not set a diagnostic parameter.** Not a threshold,
weight, prior, signature, gate or smoothing constant, at any nesting depth,
under any spelling. `csia/aircraft/firewall.py` derives the protected namespace
from the frozen core with `ast` and `tests/test_profile_science_firewall.py`
fuzzes every name through six respellings, every framing prefix, four nesting
depths and five environment-reference forms.

**The deployment config has no such firewall,** and two of its values are
passed into the frozen core. This was measured by following the call, not
inferred from the key names:

| key | route | effect |
|---|---|---|
| `csia.tick_hz` | `cli.py` → `ShadowConfig.tick_hz` → `csia/deploy/shadow.py:123` `OnlineTrustLayer(tick_hz=)`; also the loop `dt` at `shadow.py:307` | The diagnostic smoothing is an EWMA over **ticks** (`SMOOTH_ALPHA = 0.06`, ~15 ticks), so the tick rate sets the smoothing **time constant**: ~0.6 s at 25 Hz, ~1.5 s at 10 Hz. 25 Hz and 10 Hz are not the same detector. |
| `csia.field_mode` | `cli.py` → `ShadowConfig.field_mode` → `OnlineTrustLayer(field_mode=)` | Selects the real-world tolerance package rather than the simulator's. |

### 3.1 The one that looks like it reaches the core and does not

`csia.profile` (`FIELD_DERIVED_NOISE`) appears at exactly one place in the
shadow runtime: `csia/deploy/shadow.py:285`, the flight-log header. **It selects
nothing.** It is a provenance label, and it has to be — a shadow deployment
reads real telemetry and has no simulated noise to parameterise.

The first draft of `csia/deploy/deployment.py` got this wrong in a way worth
recording. It resolved the string through `csia/profiles.py:get_profile()` and
raised on the only committed deployment config. `FIELD_DERIVED_NOISE` is in
`csia/simulation/profiles.py` (`IDEAL_SIM` / `REALISTIC_SIM` /
`FIELD_DERIVED_NOISE`); `csia/profiles.py` holds *vehicle* profiles
(`sow001_quad`, `interceptor_seeker`). **Two registries, one word.** The loader
now validates the label against the noise registry — not because it selects
anything, but because a typo would put a name in the permanent evidence record
that resolves to nothing, and a later reader cannot tell a typo from a rename.

### 3.2 Why the asymmetry is defensible and what still backs it

It is defensible because a deployment config genuinely has to state a tick rate
— the same core running at a different rate is a legitimate deployment, and
refusing it would make `csia-shadow` unusable.

What backs it today is **provenance, not prevention**: the config's SHA-256 is
in every flight-log header, so what was used is recorded rather than
reconstructed. That is sufficient for an audit *after* a run and insufficient
to stop a run being configured wrong.

Schema 2 (§4) closes that gap opt-in, by requiring a reason. It does **not**
forbid the values, and the difference matters: forbidding `tick_hz` in a
deployment config would break the only committed configuration in the
repository, and a guard that breaks the shipped case gets disabled.

## 4. Schema versions

| schema | declared how | adds | hash |
|---|---|---|---|
| `csia.deployment/1` | **by the absence of a `schema:` key** | — | unchanged, forever |
| `csia.deployment/2` | `schema: csia.deployment/2` | `vehicle_profile:` reference; `science_surface:` declarations | new file, new hash |

### 4.1 Why schema 1 is implicit

`csia/deploy/flight_log.py` computes the header field as:

```
sha256(json.dumps(vehicle_config, sort_keys=True))[:16]
```

over the **parsed dict**. Adding a `schema:` key to an existing deployment
config would therefore change that file's hash and orphan every flight log and
trial manifest citing it — silently, because nothing recomputes an old hash.

So the absence of the key *is* the schema. `configs/vehicle/example_quad.yaml`
hashes to `da6321053178df5b`, the value it had before
`csia/deploy/deployment.py` existed, and
`tests/test_deployment_schema.py::test_the_committed_schema_1_config_hash_is_unchanged`
pins it to that literal.

### 4.2 `science_surface` is derived, not declared by the author

A schema-2 config lists the keys that reach the frozen core, each with a
reason. **The author does not decide what belongs on that list.**
`csia/deploy/deployment.py:core_reachable_keys()` derives it by reading two
call sites:

1. `csia/deploy/cli.py` — which `csia.<key>` becomes which `ShadowConfig` field;
2. `csia/deploy/shadow.py` — which `ShadowConfig` fields are handed to
   `OnlineTrustLayer(...)`.

A key that reaches the core without a declaration is a **load error**. Wire a
new value into the core and every schema-2 config stops loading until somebody
writes down why.

Two sources are used, and neither finds the other's cases:

* **reaches-core** (the derivation above) finds `csia.field_mode`, which
  shadows no frozen-core constant and would pass a name-based check;
* **shadows-constant** (the vehicle-profile firewall's generated namespace)
  finds a key that does not reach the core today but would read as setting one.

## 5. Compatibility matrix

| deployment | vehicle profile | result |
|---|---|---|
| schema 1 | none | supported. The historical path; capability negotiation is unavailable, so `csia-edge validate` cannot be run for this vehicle |
| schema 1 | any | supported. Cross-check runs on the fields both files state (autopilot, transport, mode) |
| schema 2 | the one it references | supported, and the only fully checked combination |
| schema 2 | a different profile | **conflict**, exit 3. Reported, not resolved |
| schema 2 | none | schema 2 requires `vehicle_profile:`; refused at load |
| unknown schema | any | refused at load. A config claiming a schema this build does not implement is not read under a guessed one |
| schema 1 with `schema: csia.deployment/1` written explicitly | any | **refused** by `test_no_schema_1_config_in_the_repository_declares_a_schema`. Writing the key changes the hash, which is the thing schema 1 exists to avoid |

## 6. Migration policy

**A schema-1 deployment config is never rewritten in place.**

Its SHA-256 is in the header of every flight log it produced. Editing it — even
to add a key that changes nothing else — breaks the link between a log and the
configuration that produced it.

To adopt schema 2, **write a new file**. The new file has a new hash, which is
correct: it is a different configuration. Logs produced under the old file
still resolve against the old file and nothing has to be re-derived.

There is deliberately **no `--upgrade` flag**, and
`test_there_is_no_in_place_upgrade_path` asserts no `upgrade()` function
exists. A migration tool for this would be used once, in a hurry, on the file
whose hash the trial manifests cite.

The canonical statement is `csia/deploy/deployment.py:MIGRATION_POLICY`; this
section paraphrases it and the test pins the string.

## 7. What is still open

**Unification is NOT decided here**, and that is unchanged from FL-005. Merging
the two files into one would change the flight-log header hash and therefore
every committed trial manifest. That is a decision with evidence consequences,
it belongs to the user, and it is listed in `USER_ACTION_REQUIRED.md`.

What this program did instead: made the two files *checkable against each
other*, made what reaches the science *derived from source rather than
remembered*, and made the asymmetry between them *stated rather than implied*.

## 8. Files

| path | role |
|---|---|
| `csia/aircraft/profile.py` | vehicle-profile loader and hand-written forbidden list |
| `csia/aircraft/firewall.py` | protected namespace generated from the frozen core |
| `csia/deploy/deployment.py` | deployment-config loader, schema detection, derived science surface, conflict reporting |
| `csia/deploy/edge.py` | `csia-edge validate`, which calls both |
| `configs/vehicle/example_quad.yaml` | the schema-1 reference. Not to be edited |
| `configs/vehicle/reference_quad_ardupilot_v2.yaml` | the schema-2 reference |
| `tests/test_deployment_schema.py` | hash pinning, derivation control, schema-2 behaviour |
| `tests/test_profile_science_firewall.py` | the fuzz suite behind §3's first paragraph |
| `research/physical_validation/FAILURE_LEDGER.yaml` | FL-005 (the seam), FL-009 (the wrong-registry error in §3.1) |
