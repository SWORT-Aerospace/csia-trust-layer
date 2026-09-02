# v1.1 AS THE SENSOR DOMAIN — v2 §§19, 20, 36

Implementation: `csia/v2/domains/navigation.py`.
Baseline test: `tests/test_v2_navigation_baseline.py`, plus
`engineering/v2/V2_BASELINE_V1_1.json` over every real payload.

> Do NOT rewrite v1.1 logic. (§20)
> The plugin layer may not alter assurance state, function eligibility,
> support or diagnosis. (§36)

---

## 1. THE MECHANISM

The wrapper **consumes the published v1.1 output payload** — schema 1.1.0, the
same artifact `csia-monitor` reads — through the same strict parser
(`csia.v1_1.monitor.parse`), and transcribes it.

It imports **no v1.1 producer**: not the trust engine, not the diagnosis, not
the eligibility policy, not the ledger. A test parses its import graph and
fails if any of those appear.

That is the guarantee, and it is structural rather than careful: **the wrapper
cannot alter a v1.1 verdict because it has no way to compute one.**

## 2. WHAT IT EMITS

| relation | component | attributable | affected functions |
|---|---|---|---|
| `v1_1.function_eligibility` | `v1_1.<NAME>` | no | that one function |
| `v1_1.source_health` | `source.<node>` | yes | **none** |
| `v1_1.support` | `v1_1.diagnosis` | no | none |
| `sensor.aggregate` | `sensor.aggregate` | no | the v2 cross-domain functions |

Three of the four are `attributable=False`: a transcribed verdict, a support
statement and an aggregate are conclusions computed from other records, not
components that can fail.

## 3. THE BIJECTION

    ELIGIBLE   <-> NOMINAL        DEGRADED   <-> DEGRADED
    INELIGIBLE <-> VIOLATED       UNKNOWN    <-> UNAVAILABLE

Four states in, four out, nothing merged. A many-to-one map would lose a
distinction v1.1 makes, and a test asserts the map is injective.

## 4. WHY PER-SOURCE HEALTH NAMES NO FUNCTION

This is §36's sharpest edge and the easiest place to break it by accident.

Per-node trust and freshness are useful evidence — they are what lets a
communication fault be distinguished from a sensor fault. But if a source
record were attached to a v1.1 function, a low trust reading could degrade a
function that v1.1 had called ELIGIBLE. That is precisely the alteration §36
forbids.

So `v1_1.source_health` records carry `affected_functions = ()`. They enter
the attribution pool, they carry their declared power dependencies, and they
can move nothing.

## 5. THE OPTIONAL TRUST FLOOR

`NavigationAssuranceDomain(trust_floor=...)` is `None` by default, and when it
is `None` **no threshold on trust exists in this module**. A host that wants
one states it. The plugin does not invent one, because v1.1's own thresholds —
inherited by name from the frozen `FailsafeConfig` — already decided its
functions, and a second threshold here would be a new engineering requirement
smuggled in as a wrapper detail.

## 6. PLATFORM WIRING — §22

`source_dependencies` is a host-supplied map, `{node: ("POWER/rail_5v", ...)}`.

It is a fact about the harness. v1.1 does not know it and nothing here infers
it. Two sources sharing an entry is a structural statement, not a correlation
estimate, and it is what lets §28-E's common-cause walk find a shared rail
under a sensor and a link at once.

The aircraft profile declares it in `csia/v2/profiles/aircraft.py` alongside
the rails' own `affected_functions`, so the two halves — which rail feeds a
source, and what losing that rail costs — are written next to each other.

## 7. FAILURE MODES

| input | result |
|---|---|
| no payload in the snapshot | `UNAVAILABLE`, `V1_1_PAYLOAD_MISSING` |
| payload fails the strict parse | `UNAVAILABLE`, `V1_1_PAYLOAD_REJECTED` |
| unknown `schema_version` | rejected by the parser, as above |

There is no permissive path and no partial interpretation, because the parser
has none. §16's strictness is inherited rather than reimplemented.

## 8. WHAT §36 IS CHECKED AGAINST

`tests/test_v2_navigation_baseline.py` checks the two committed example
payloads — enough for CI, not enough for a claim.

`engineering/v2/run_v2.py` regenerates the **complete per-tick payload stream**
for every applicable v1.1 mechanism using the Phase 4D machinery — the same
`_payloads()` that produced those committed examples — and checks:

- **exactness** on every payload: the SENSOR-only engine's function states
  equal the payload's `function_eligibility` exactly
- **monotonicity and the SENSOR-column identity** on a stated stride, against
  a snapshot where every other domain is at its worst — the input that would
  expose any leakage

Results, with the stride and the counts, are in `V2_BASELINE_V1_1.json`.

**The sharpest case is `SHARED_SOURCE`.** Its real payload calls all five v1.1
functions `ELIGIBLE` while two of its sources are raising sequential alarms —
because a sequential alarm is not a cause attribution (Phase 4 §11) — and v2
calls the same five `INELIGIBLE` on POWER evidence. Both are true at once, and
`domain_states["SENSOR"]` still reads exactly `ELIGIBLE`. That is the input a
leak in the wrapper would show up in, because it is the one where the two
answers disagree.

## 9. THE COST OF THE SEAM

Measured, not estimated: `csia.v1_1.monitor.parse` re-validates the payload
against the v1.1 JSON Schema on every call, and that dominates the v2 tick by
roughly two orders of magnitude (`V2_COMPUTE.json`).

It is a property of ingesting schema 1.1.0 **strictly**, not of the v2
decision, and an integration that validates once at ingest rather than once
per consumer does not pay it repeatedly. **Nothing was changed in v1.1 to
improve the number** (§19); it is reported as measured, and what to do about
it is a decision for a later phase.
