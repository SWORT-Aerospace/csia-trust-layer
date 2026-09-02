# API COMPATIBILITY — Phase 4 §§20, 22, 26, 28

Schema: `engineering/v1_1/csia_output_v1_1.schema.json`, version **1.1.0**.
Builder and projection: `csia/v1_1/output_api.py`.
Examples: `csia_output_example.json` (clean),
`csia_output_fixloss_example.json` (the t = 26.00 s event).

**13 500 payloads — every tick of all nine mechanisms — validate against the
schema** (`PHASE4_API_VALIDATION.json`).

---

## 1. THE RULE — §26

There are exactly **two** behaviours for an existing consumer, and no third:

1. **Take the compatibility projection.** `project_v1(payload)` returns the
   v1-shaped subset.
2. **Refuse the mismatch loudly.** `assert_schema_version(payload)` raises
   `SchemaVersionError`.

> **No field is ever silently reinterpreted.**

The projection deliberately carries one field v1 never had:
`trust_mode`. A v1 consumer that quietly received `FLAT_V1_1` trajectories
believing them to be v1's would be precisely the silent reinterpretation §26
forbids, so the mode is made unmissable rather than dropped. The projection
also carries `_v1_compat_note` saying what it is.

## 2. VERSIONING POLICY

| change | version effect |
|---|---|
| add an optional field | minor — `1.1.x` |
| add a value to an existing enum | **major** — a consumer switching on the enum has a new unhandled case |
| change what an existing field means | **major**, always |
| tighten a constraint (e.g. `k` becomes something other than 0.5) | **major** |
| rename a field | **major** |

`additionalProperties: false` at the top level and on every nested object, so
an unrecognised field is a validation failure rather than a silent pass. A
schema that accepted anything would not be a contract.

## 3. TWO NAMING DECISIONS THAT ARE NOT COSMETIC

**`posterior`, never `confidence`** — §22. It is a posterior probability under
a stated prior and likelihood. "Confidence" would assert a calibration nothing
in this system establishes, and `GNSS_FIX_LOSS` is exactly where that would
mislead: the leader sits at **0.992 with zero discriminating evidence**. A
consumer reading a field called `confidence` would act on that number. A
consumer reading `posterior` next to `discriminating_evidence_count: 0` and
`support_state: NON_IDENTIFIABLE` has what it needs not to.

**`UNKNOWN` means two different things and never shares a field** — §§8, 34.

| where | meaning |
|---|---|
| `function_eligibility[*].state == "UNKNOWN"` | the **policy** cannot determine eligibility from the available evidence |
| `diagnosis.unknown_fault_model == "NOT_IMPLEMENTED"` | the **unmodeled-fault hypothesis** does not exist |

The second is a `const` in the schema, so a payload cannot claim an
unknown-fault capability that was never built.

## 4. `current_valid` VERSIONING — §28

Phase 1 changed what the battery current channel means: a producer sentinel
(`current_battery = -1`, ULog `current_a = -1.0`) is now **absent** rather than
being delivered as `5.0`, `0.0` or `-1.0` by three decoders that disagreed.
`current_valid` was introduced alongside it as a bare, unversioned field —
listed as blocker 5 in the Phases 1–3 report.

**Phase 4 closes that.** `evidence.current_valid` is now part of a versioned
schema:

- it is `true`, `false` or `null`, and `null` means *the ingest layer did not
  report on it* (the scenario path, which has no adapter) — not `false`;
- its meaning is fixed by `schema_version`, so a change to it forces a version
  bump;
- `evidence.missing_reason` carries the producer's own reason
  (`SENTINEL` / `STALE` / `NOT_RECEIVED` / `NO_3D_FIX`) as a closed enum
  alongside it.

**No unversioned semantic change survives Phase 4** — this was the last one.

## 5. WHAT A CONSUMER CANNOT DO THROUGH THIS API — §25

There is **no field through which a vehicle action can be requested.**
`recommendations` is an advisory enum of four strings; acting on one is the
consumer's decision, taken outside CSIA.

`provenance_summary.authority` is the constant `READ_ONLY`, and that is
structural rather than aspirational — see `OUTPUT_FIREWALL` in
`csia/v1_1/firewall.py` and the transport denial beneath it in
`csia/deploy/guard.py`.

## 6. PROVENANCE IS IN EVERY PAYLOAD, NOT JUST THE HEADER

`software_sha`, `configuration_hash`, `input_trace_hash`, `trust_mode` and
`frozen_core_tag` ride on **every** tick. A payload extracted from a log by
itself is still attributable; it does not become meaningless once separated
from a file header.

## 7. LIMITS

- **No wire format is specified.** This is a JSON schema for a payload. How it
  reaches a consumer — MAVLink, a socket, a file — is a deployment question
  and nothing here assumes one.
- **No rate is specified.** The examples are per-tick at 25 Hz because that is
  what the scenario catalogue runs at. A real deployment would likely publish
  on change plus a heartbeat, and the `ledger_event` field is shaped for that
  — **absent means nothing changed, not that the ledger is unavailable.**
- **No authentication or signing.** The ledger's hash chain detects a missing
  or reordered event; it does not establish who produced the payload.
- **Validated on the deterministic catalogue only.** 13 500 payloads, no
  flight data.
