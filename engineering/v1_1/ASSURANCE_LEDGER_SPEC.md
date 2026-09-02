# ASSURANCE LEDGER SPEC — Phase 4 §§15–19

A deterministic, machine-readable record of **why the assurance state
changed**, reproducible from the trace, the configuration and the software
SHA.

Implementation: `csia/v1_1/ledger.py`. Artifacts:
`ASSURANCE_LEDGER_EXAMPLE.json`, `ASSURANCE_LEDGER_REPRODUCTION.json`.
Codes: `REASON_CODES.yaml`.

---

## 1. WHAT OPENS AN EVENT — §15

A change in any of five things, and nothing else:

    ASSURANCE_STATE_CHANGED         NORMAL / CAUTION / CRITICAL / EMERGENCY
    FUNCTION_ELIGIBILITY_CHANGED    one per function that moved
    SUPPORT_STATE_CHANGED           the Phase 2 support label
    AMBIGUITY_CHANGED               UNIQUE <-> AMBIGUOUS
    SEQUENTIAL_STATE_CHANGED        the set of alarming CUSUM nodes

Per-tick sampling is not a ledger. 1500 ticks × nine mechanisms produced
**159 events** — every one of them a state change with a reason.

Event order **within** a tick is fixed — assurance, then functions in sorted
name order, then support, ambiguity, sequential — because a ledger whose event
order depended on dict iteration would not reproduce.

## 2. EVENT CONTENT — §16, ALL OF IT

| | |
|---|---|
| identity | `event_id`, `sequence`, `timestamp`, `event_type`, `subject` |
| transition | `previous_state`, `new_state`, `reason_codes` |
| provenance | `platform`, `software_sha`, `configuration_hash`, `input_trace_hash`, `trust_mode`, `schema_version` |
| sources | `fresh` per node, `missing_reason` per node, `trust` per node |
| relations | `active_relations`, `suppressed_relations`, `suppression_reasons` |
| detector | `sequential_state` — `k`, `h`, and the alarming set |
| diagnosis | `leader`, `posterior`, `active_evidence_count`, `discriminating_evidence_count`, `leader_identifiable`, `prior_sensitive`, `ambiguity`, `support_state` |
| functions | `function_eligibility` — state and reason codes per function |
| assurance | `assurance_state`, `recommendations` |
| integrity | `content_sha256`, `previous_event_hash` |

`configuration_hash` covers everything that can change the answer:
`FUNCTION_REQUIREMENTS.yaml`, `REASON_CODES.yaml`, and the five v1.1 runtime
modules. Change any of them and every event's context changes, which is the
point — a ledger that looked identical across a policy change would be
worthless.

**Suppression reasons distinguish two different facts.** The frozen runtime
multiplies every edge gate by both endpoints' freshness
(`csia/runtime/online.py:610`), so a suppressed relation is either
`GATE_CLOSED` (the check did not apply) or
`ENDPOINT_NOT_FRESH:<node>` (a sensor went away). Collapsing them would lose
the distinction Phase 2 exists to preserve.

## 3. DETERMINISM — §17

    event_id  = sha256({"seq": n, "content": content_sha256})[:32]

**Hashes of content and timing. No random UUIDs**, exactly as §17 requires,
because an identifier that changed on replay would make reproduction
unprovable.

`ASSURANCE_LEDGER_REPRODUCTION.json` builds every mechanism **twice**, in two
independent `AssuranceLedger` instances, and compares the full event list
including every id and hash:

| | |
|---|---|
| mechanisms | 9 |
| total events | **159** |
| identical on rerun | **all 9** |
| chain verified | **all 9** |

`verify_chain()` re-derives every hash from the stored content rather than
trusting the stored hash, so the check would fail on a hand-edited file.

## 4. THE HASH CHAIN, AND WHAT IT IS NOT — §18

`content_sha256` per event, `previous_event_hash` linking to the one before,
genesis of 64 zeros.

**This is a simple hash chain for detecting a missing or reordered event.**
That is its whole purpose and its whole capability.

It is **not** a blockchain. It is not distributed, not consensus-based, not
tamper-evident against anyone who can rewrite the file — recomputing the chain
after an edit is trivial. §18 says a simple hash chain is sufficient if
implemented, and marketing it as more than that would be the failure mode the
instruction guards against. The artifact says so in its own `chain_note`
field.

## 5. REASONS ARE CODES — §19

Structured codes from `REASON_CODES.yaml`, which is the single source of
truth. A test fails if any emitted code is undefined there, so a new code
cannot reach a flight record without reaching the table.

`Event.render()` produces a sentence for a human display —
`"PRECISION_NAVIGATION ELIGIBLE -> INELIGIBLE"` — from the code. **The
sentence is never the canonical record.** No generated prose is stored as
evidence.

## 6. WHAT THE LEDGER ACTUALLY SHOWS — THE FIX-LOSS EVENT

`ASSURANCE_LEDGER_EXAMPLE.json`, `GNSS_FIX_LOSS`, event 9 at **t = 26.00 s**:

    trust["gps"]                     0.987      <-- the sensor looks healthy
    fresh["gps"]                     false
    leader                           nominal
    posterior                        0.992
    leader_identifiable              false
    active_evidence_count            16
    discriminating_evidence_count    0          <-- nothing separates it
    support_state                    NON_IDENTIFIABLE
    suppressed_relations             altitude_baro, heading_course,
                                     velocity_gps_doppler
    suppression_reasons              all: ENDPOINT_NOT_FRESH:gps
    function_eligibility             COARSE_NAVIGATION      INELIGIBLE
                                     POSITION_HOLD          INELIGIBLE
                                     PRECISION_NAVIGATION   INELIGIBLE
                                     GEOFENCE_SUPPORT       INELIGIBLE
                                     INERTIAL_CONTINUATION  ELIGIBLE
    reason_codes                     REQUIRED_SOURCE_NOT_FRESH,
                                     REQUIRED_RELATION_NOT_APPLICABLE,
                                     SUPPORT_LOST_FOR_REQUIRED_INFORMATION
    recommendations                  RESTRICT_PRECISION_NAV,
                                     INHIBIT_GPS_MODES, SWITCH_NAV_INERTIAL

**GPS trust is 0.987 and every GNSS function is ineligible.** A trust-only
system reading that first number would have reported the GPS healthy. The
ledger records the reason it is not enough — no discriminating evidence, three
relations suppressed naming `gps` as the stale endpoint — and names the
function that is still justifiable.

That is the whole point of the layer, in one event, reproducibly.

## 7. RECOMMENDATIONS ARE ADVISORY — §24

`csia/v1_1/advisory.py` returns strings from a fixed set:
`RESTRICT_PRECISION_NAV`, `INHIBIT_GPS_MODES`, `SWITCH_NAV_INERTIAL`,
`MANUAL_REVIEW`. A test asserts nothing else can ever be returned.

**Nothing here transmits anything.** The module imports no transport and holds
no connection; the output firewall denies the transmit surface regardless of
what is recommended. The mapping introduces no threshold and no new evidence —
if a recommendation appears, some function's eligibility already changed and
already carries its reason codes.

## 8. LIMITS

- **Deterministic simulation only.** Every event here came from the scenario
  catalogue. No flight, no HIL.
- **`missing_reason` is empty in these artifacts.** The scenario path does not
  run the ingest layer, so the field is present and unpopulated rather than
  absent. On a real platform it carries the producer's own reason.
- **No storage or rotation policy.** 159 events for 9 × 60 s of flight is
  small, but nothing here bounds a long flight's ledger, and that is a Phase 5
  or deployment question rather than something silently assumed away.
- **The chain proves ordering, not authenticity.** See §4.
