# API CONSUMER SPEC — `csia-monitor` — Phase 4.5 §§13–18

Gate C. A schema that only its own producer has ever read is not an
integration; it is a serialisation format with a validator attached. Phase 4
validated 13 500 payloads and zero integrations. This closes that.

Implementation: `csia/v1_1/monitor.py`.
Results: `API_CONSUMER_RESULTS.json`.
Stream: `api_consumer_stream.jsonl`.

    python -m csia.v1_1.monitor api_consumer_stream.jsonl

    GATE E  consumer   PASS
    GATE F  firewall   PASS

---

## 1. WHAT MAKES IT A REAL CONSUMER

**It imports no producer.** Not the trust engine, not the diagnosis, not the
eligibility policy, not the ledger, not the adapters. A test parses its
imports and fails on any of them.

That constraint is the whole experiment. If the monitor could reach into the
system it would recompute what the payload failed to carry, and the schema
would never be tested for sufficiency. Anything the monitor can show came out
of `csia_output_v1_1` and nothing else.

**It is not another source of truth.** It renders and it refuses. It does not
score, decide, or correct.

## 2. WHAT IT SURFACES — §14

Every field §14 lists: `timestamp`, assurance state, per-function eligibility
with reason codes, diagnosis leader and posterior, support state, ambiguity,
active and discriminating evidence counts, sequential alarms, recommendations,
and the ledger event.

The schema carried all of them. **Nothing had to be added to the schema to
make this consumer work**, which is the result Gate C was asking for.

## 3. THE DESIGN RULE THAT MATTERS — §15

On the GNSS fix-loss payload:

    trust["gps"]                   0.987      <-- the sensor looks healthy
    leader / posterior             nominal / 0.9925
    discriminating_evidence_count  0
    support_state                  NON_IDENTIFIABLE

A consumer that led with either number would report a healthy GPS while four
of five functions were unavailable. So:

> **The primary status is computed from function eligibility and support. The
> posterior is not an input to it.**

That is enforced structurally rather than by wording. `MonitorView.
primary_status` reads `function_eligibility` and `support_state` only, and a
test proves it by parsing two views that differ *only* in the posterior
(0.9925 against 0.0001) and asserting the primary status is identical.

What the monitor actually prints for that payload:

    t=   26.00  4 OF 5 FUNCTIONS UNAVAILABLE — support NON_IDENTIFIABLE
      assurance          CAUTION
      diagnosis          nominal p=0.9925 [NON_IDENTIFIABLE, 0 discriminating, AMBIGUOUS]
      evidence           16 active, 0 discriminating
      sequential alarms  none
      COARSE_NAVIGATION      INELIGIBLE  REQUIRED_SOURCE_NOT_FRESH, REQUIRED_RELATION_NOT_APPLICABLE, SUPPORT_LOST_FOR_REQUIRED_INFORMATION
      GEOFENCE_SUPPORT       INELIGIBLE  ...
      INERTIAL_CONTINUATION  ELIGIBLE    ALL_REQUIREMENTS_MET
      POSITION_HOLD          INELIGIBLE  ...
      PRECISION_NAVIGATION   INELIGIBLE  ...
      advisory           RESTRICT_PRECISION_NAV, INHIBIT_GPS_MODES, SWITCH_NAV_INERTIAL
      ledger             ASSURANCE_STATE_CHANGED assurance NORMAL->CAUTION

**The posterior is shown, and never bare.** `format_leader` cannot emit
`p=0.9925` without the support state, the discriminating-evidence count and
the ambiguity beside it; a test asserts all three are present in every
rendering. Suppressing the posterior would have been the easy answer and the
wrong one — it is real information. What it must not do is travel alone.

A test also asserts the primary status contains none of "healthy", "ok",
"nominal", "fine" or "99".

## 4. STRICT PARSING — §16

Six rejection paths, each perturbing exactly one thing, all refused:

| case | what it does | outcome |
|---|---|---|
| `unknown_schema_version` | `schema_version: "2.0.0"` | **refused** — no coercion |
| `malformed_payload` | a string where an object belongs | **refused** |
| `missing_required_field` | `diagnosis.posterior` deleted | **refused** — not defaulted |
| `sequential_kh_mismatch` | `h = 5.0`, the textbook value that failed | **refused** |
| `unknown_trust_mode` | `FLAT_V2_EXPERIMENTAL` | **refused** |
| `unknown_function_state` | `PROBABLY_FINE` | **refused** |

Plus an unknown reason code, refused for the same reason.

**There is no permissive path.** Every failure raises `PayloadRejected`; there
is no "best effort" degradation and no default for a missing field. A monitor
that guessed at a malformed assurance payload would be worse than one that
stopped.

The `k`/`h` check deserves a note: a payload carrying `h = 5.0` came from a
**differently configured detector**, and reading it as if it came from this
one would silently mix two detectors' outputs in one log. The constants are
part of the contract, not decoration.

At the stream level a rejection is **recorded, not raised**: one bad line does
not end the run, and `evidence()` says how many were refused and why.

## 5. COMPATIBILITY — §17

Two behaviours, no third:

| input | v1 consumer | result |
|---|---|---|
| `project_v1(payload)` | accepts | takes the documented projection |
| raw v1.1 payload | **refuses** | does not carry the v1 field set |
| payload at `schema_version 2.0.0` | `SchemaVersionError` | refused before projection |

The projection carries `trust_mode`, which v1 never had, so a v1 consumer
cannot quietly receive `FLAT_V1_1` trajectories believing them to be v1's.
**No silent reinterpretation** — the modelled v1 consumer is deliberately
non-permissive, because that is the behaviour §26 requires of a consumer
facing a schema it does not understand.

## 6. FIREWALL INTEGRATION — §18

Every action the monitor might be asked to take goes through
`OutputFirewall.request`. There is no branch that bypasses it: even accepting
a payload calls `request("EMIT_OUTPUT")`.

| operation | result |
|---|---|
| `SET_FLIGHT_MODE` | **denied** |
| `WRITE_PARAMETER` | **denied** |
| `RTL` | **denied** |
| `LAND` | **denied** |
| `SOMETHING_NOBODY_HAS_WRITTEN_YET` | **denied** — default-deny |
| `READ_TELEMETRY`, `WRITE_LOG`, `EMIT_OUTPUT` | permitted |

Every denial is recorded before it raises and appears in `evidence()`, so a
deployment carries a record that a command was *attempted*, which is the more
important half of the event.

A test also asserts the module imports no `socket`, `pymavlink`, `serial`,
`requests`, `urllib`, `http` or `subprocess` — it could not transmit if the
firewall were removed.

## 7. WHAT THIS DOES NOT ESTABLISH

- **Two payloads, not a flight.** The stream is the clean tick and the
  fix-loss tick from the Phase 4 examples. It exercises the schema, not
  throughput or long-run behaviour.
- **One consumer, written by the same author as the producer.** A genuinely
  independent integration would test assumptions this one may share without
  noticing. That limitation is real and is not closed by Gate C.
- **No transport.** The monitor reads JSONL from a file. How a payload
  reaches a consumer is still unspecified (`API_COMPATIBILITY.md` §7).
- **No UI.** It renders text. "TUI" in §13 was offered as an option and a
  terminal renderer is what was built.
