# DOMAIN-LEVEL ASSURANCE LEDGER — v2 §23

Implementation: `csia/v2/ledger.py`. Tests: `tests/test_v2_api_ledger.py`.

---

## 1. WHAT IS CARRIED OVER FROM v1.1 UNCHANGED

The mechanism, deliberately: canonical JSON, `content_sha256` per event,
`previous_event_hash` linking them, event ids derived from content and
sequence rather than generated. Two ledgers that work differently cannot be
reconciled by an investigator months later, and the v1.1 mechanism already
does what §23 asks.

The same disclaimer applies with the same force, and repeating it is not
boilerplate:

> **This is a simple hash chain. It detects a missing or reordered event. It
> is not a blockchain, is not distributed, and is not tamper-proof against
> anyone who can rewrite the whole file. Do not market it as any of those.**

A test asserts the phrase "not a blockchain" is in the emitted `chain_note`,
and that no identifier in the module is derived from `uuid`, `random`,
`secrets` or `time` — an id that is not a function of content cannot be
reproduced by a replay.

## 2. WHAT §23 ADDS

A v1.1 event says "PRECISION_NAVIGATION went INELIGIBLE, reasons X and Y". A
v2 event has to answer the question that only exists once there are several
domains: **which domain, which component, and what did it depend on?**

| field | why |
|---|---|
| `domain` | which domain's evidence changed the outcome |
| `component` | the specific rail, process, link or actuator |
| `limiting_domain` | which domain set the new function state |
| `affected_functions` | everything this event bears on |
| `dependencies` | the declared cross-domain structure (§22) |
| `attribution` | verdict, candidates, discriminators, common cause |

`component` is chosen deterministically: the component in the limiting domain
carrying the most restrictive evidence for that function, ties broken on name.

## 3. EVENT TYPES

    SYSTEM_STATE_CHANGED       NORMAL / DEGRADED / RESTRICTED / UNAVAILABLE
    DOMAIN_STATE_CHANGED       a domain's observation state moved
    FUNCTION_STATE_CHANGED     a function's eligibility moved
    LIMITING_DOMAIN_CHANGED    the state held; what is holding it back moved
    ATTRIBUTION_CHANGED        the cause-support verdict or candidates moved

`LIMITING_DOMAIN_CHANGED` exists because "still degraded, but now because of
power rather than compute" is exactly what an investigator needs and exactly
what a state-only ledger silently loses.

## 4. WHY THE ATTRIBUTION IS IN EVERY EVENT

Because it changes. The same function can be INELIGIBLE at t=10 with a UNIQUE
cause and INELIGIBLE at t=40 with an AMBIGUOUS one, and a ledger recording
only the state would show nothing happening across the transition that matters
most.

## 5. THE PLUGIN MANIFEST HASH

`V2LedgerContext` carries a SHA-256 over every registered plugin's
declaration, canonicalised and in sorted order. A ledger replayed against a
differently configured plugin set is not a replay, and this makes that
**detectable** rather than merely unlikely. The aircraft and test-stand
profiles produce different hashes; the same profile built twice produces the
same one.

## 6. REPLAY

`verify_chain()` re-seals every event from its own content and compares, and
checks each `previous_event_hash` against the actual predecessor. A test
tampers with one event's `new_state` and confirms the chain reports it.

Determinism is checked end to end: the same scenario run twice produces
byte-identical event dictionaries, hashes included. That holds because domains
are stateless, the registry is sorted, and nothing anywhere reads a clock.

## 7. WHAT IS NOT DONE

- **No pruning or rotation.** The ledger grows with transitions, not ticks,
  but a long deployment needs a retention policy and there is none.
- **No signing.** The chain detects accidental loss and reordering. Detecting
  a deliberate rewrite needs a key, a place to keep it, and a threat model.
- **No cross-run linking.** Each run starts at GENESIS.
