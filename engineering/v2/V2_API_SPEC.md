# CSIA SYSTEM ASSURANCE API v2 — v2 §24

Implementation: `csia/v2/api.py`. Schema version `2.0.0`.

> Do not change schema 1.1.0. (§24)

---

## 1. THE RELATIONSHIP BETWEEN THE TWO SCHEMAS

    v1.1 output (schema 1.1.0)  --INGESTED BY-->  v2 (schema 2.0.0)

**One direction only.** v2 reads v1.1 payloads through
`csia.v1_1.monitor.parse` — the same strict parser the external monitor uses —
and produces its own document. Nothing in v2 writes, extends, reinterprets or
re-versions schema 1.1.0. A v1.1 consumer pointed at a v1.1 producer sees
byte-identical output whether or not v2 exists anywhere in the system.

That is structural, not a convention to be careful about: `csia/v2/` imports
exactly one thing from `csia/v1_1/`, and
`tests/test_v2_api_ledger.py::test_the_only_thing_v2_imports_from_v1_1_is_the_payload_parser`
parses the import graph of every v2 module and fails on anything else.

## 2. THE DOCUMENT

```
schema_version   "2.0.0"
ingests          {"csia_output_v1_1": "1.1.0"}
profile          which platform profile produced it
provenance       software sha, configuration hash
t                tick time
system           NORMAL / DEGRADED / RESTRICTED / UNAVAILABLE
domains          {domain_id: observation state}
functions        {name: {state, limiting_domain, domain_states,
                         reason_codes, evidence_count, fallback, detail}}
limiting_domains the distinct domains limiting anything
attribution      {verdict, candidates, candidate_detail, discriminators,
                  common_cause, unsupported, detail}
evidence         every record, with provenance, dependencies, latencies
unevaluated      what could not be looked at, and why
ledger_events    the events this tick opened
declarations     optional: the full plugin/function/relation declaration
```

## 3. WHAT IT REFUSES TO CONTAIN

**No scalar system health.** `validate()` raises on a top-level `score`,
`health`, `confidence`, `index`, `grade` or `percentage`. §3's rule is not
only about the record type: a "system health: 82%" field would re-import
exactly the false comparability that keeping evidence categorical exists to
prevent, and it would be a breaking change in *meaning* even though it is an
additive change in schema.

**No command, no mode, no switch** (§33). No function in the module has a name
containing `command`, `send`, `set_mode`, `switch`, `actuate`, `arm`, `land`
or `rtl`, and a test asserts it.

## 4. STRICTNESS

Every rejection raises `SchemaVersionError`. There is no permissive path, no
best-effort degradation and no default for a missing field — a consumer that
guessed at a malformed assurance document would be worse than one that
stopped. An unknown schema major is refused rather than coerced.

Validation is hand-written rather than a JSON Schema file, deliberately: v1.1
ships a schema file because it is frozen and externally consumed, while v2 is
still moving, and a schema file that drifts from the code it describes is
worse than none. When v2 freezes it gets one the same way v1.1 did.

## 5. THE §33 INTERFACE

```python
API.function_eligible(doc, "PRECISION_NAVIGATION")
# -> {"function": ..., "eligible": False, "state": "INELIGIBLE",
#     "limiting_domain": "POWER", "reason_codes": [...],
#     "domain_states": {...}, "fallback": "COARSE_NAVIGATION",
#     "why": "limited by POWER: POWER_RAIL_OUT_OF_TOLERANCE, ..."}
```

§33's worked example, as an actual call: the autopilot asks, CSIA answers, and
**the autopilot owns the switching action**.

It returns the answer *and why*, because an integration that only got a
boolean would have no way to log what it acted on. `fallback` is the host's
own declaration reported back — reporting a host's declaration to it is not
CSIA choosing anything.

A function the profile does not declare returns `eligible: None` with
`state: "UNKNOWN"` and an explanation, never a guess.

`API.limiting_report(doc)` is §17's central column on its own: which domain is
holding back which functions, and which functions nothing is holding back.

## 6. VERSIONING POLICY

`2.0.0`. A new domain, a new relation or a new reason code is **additive** and
does not change it: consumers read `domains` and `functions` as maps.

The major changes if a state enum gains or loses a member, if `limiting_domain`
stops being present on every function, or if the meaning of any state changes.
`assert_schema_version()` exists for a consumer that wants to pin exactly.
