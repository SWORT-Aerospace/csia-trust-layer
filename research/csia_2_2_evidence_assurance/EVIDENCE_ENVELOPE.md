# The evidence envelope (Phases 3 and 5)

**2026-10-01. Code:** `csia_evidence_assurance/envelope.py`.

**The rule applied to every field:** which demonstrated failure does it
prevent? A field without an answer was removed or deferred.

The failure codes (L1, L2, L6, L8, L9, L12) and preview cases are those of the
shadow study's `DEPENDENCY_METADATA_PREVIEW.md`. E1 is the configuration
transition of `TRANSITION_DESIGN.json`. "372" is the replay failure described
in `CONTENT_TIME.md`.

## 1. The fields kept

| field | prevents | demonstrated where |
|---|---|---|
| `producer_id` | a republished output counted as a second producer (L8) | preview case 5; DUPLICATE status, dataset G (`relay:imu1_threshold`) |
| `producer_version` | a producer read with the semantics of another version (L9) | a v1.1 payload computed with other CUSUM constants is CONTRACT_INVALID (`test_cusum_adapter_wraps_the_frozen_bank_and_states_coverage`) |
| `contract_version` | an output read under a contract it was not written for (L9) | contract-failure taxonomy |
| `claim` | a result read with a meaning it does not have (L6); an undeclared claim | UNKNOWN_CLAIM, CLAIM_RECORD_MISMATCH |
| `record` | nothing on its own: it is the 2.1.1 evidence itself | — |
| `lineage` | false independence between monitors of one source (L1, L2, L12) | preview cases 1 and 3; three-monitor regression; CUSUM power_sag (three alarms, one line) |
| `content_time` | an old content read as current; processing latency read as freshness | preview case 6; STALE; the XSYS V4 window; the 152 ms PX4 lag (`CONTENT_TIME.md`) |
| `produced_time` | impossible metadata (content after production, production in the future) going unnoticed | contract-failure taxonomy, "healthy with impossible metadata" |
| `config_epoch` | evidence from a configuration no longer in force | E1: 9 stale ticks before R-3, 0 after, the same through 2.2 |
| `producer_health` | a NOMINAL from a faulted monitor read as healthy aircraft evidence | Phase 22 metamorphic tests; dataset G (`imu1:faulted_monitor`) |
| `detail` | nothing: free trace for the engineer, never read by admissibility | — |

## 2. Derived, not supplied

**`evidence_id`** = `producer|claim|record|content_time`.

**Why derived.** The same output always gets the same id, which makes reports
byte-stable and receipts comparable. A producer-supplied id could collide or
drift.

## 3. Deferred or removed

| candidate field | decision | why |
|---|---|---|
| `profile_version` per envelope | **deferred** | the profile is a property of the analysis, checked once at load (`profile_gate.py`); the contract lists the profiles it is compatible with (PROFILE_MISMATCH). A copy on every envelope would only be a second place for one fact to disagree |
| `payload` beside `record` | **removed** | the 2.1.1 record already carries the measured value, expected value and residual; a second payload had no reader |
| `source_lineage` as a graph | **removed** | a set of roots is enough for every demonstrated case (`LINEAGE_AND_DEPENDENCE.md`) |
| `operating_regime` | **deferred** | no producer here has a validated regime restriction other than an event window, which the contract's `validity` expresses |

## 4. Size

**An envelope is:**
- a record;
- a sorted tuple of at most 16 lineage roots;
- two floats, a small epoch map and an enum.

It is hashable, comparable and serialisable as it stands (`to_dict()`).
