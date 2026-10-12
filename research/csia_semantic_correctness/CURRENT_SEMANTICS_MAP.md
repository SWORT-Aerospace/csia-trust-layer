# Current semantics map: frozen v2 localization and attribution

CSIA semantic correctness audit, 2026-09-29. **Read-only with respect to
frozen v2.**

**What was read.** The files below are byte-identical to the Phase C freeze
commit `50c5d35`:

- `csia/v2/attribution.py`
- `csia/v2/localization.py`
- `csia/v2/signatures.py`
- `csia/v2/evidence.py`

Since the freeze, `csia/v2` has changed only by two lint edits and one removed
unused import, in `engine.py`, `plugin_runtime.py` and `matched_scenarios.py`.
Line numbers below are for HEAD (`c46067c`). Every behaviour described here
is therefore the frozen Phase C behaviour.

Result ids (`R…`, `E…`, `P…`, `N…`, `X…`, `SH…`) refer to
`semantic_probe_results.json`, produced by `semantic_probe.py`.

## 1. The pipeline, per tick

```
AssuranceEngine.evaluate (engine.py:279-306)
  for each domain, in sorted id order:
      PluginSupervisor.run -> records    (a failed plugin emits one UNAVAILABLE
                                          `plugin.status` record, attributable=False)
  FunctionGraph.evaluate(records)        -> per-function ELIGIBLE/DEGRADED/INELIGIBLE/UNKNOWN
  localize_all(SYMPTOMS, records, PREDICATES)    (localization.py:352-359)
      index = EvidenceIndex(records)
      for spec: for subject in spec.detect(index): localize(spec, index, subject, predicates)
  attribute(records, relations)          (attribution.py:113-237)
```

The following hold per tick:

- **Stateless.** Nothing is carried from one tick to the next except the
  ledger, which is append-only.
- **Separate functions.** Localization and attribution are computed by
  separate functions from the same records. **Neither reads the other's
  output.**

## 2. Localization, `localize()` (localization.py:282-349)

| step | code | semantics |
|---|---|---|
| evaluate | 289-293 | every predicate named by any hypothesis is evaluated once; `values[pid]` is True, False or None |
| elimination | 302-307 | a hypothesis is **rejected** if ANY of its `refuted_by` predicates is True. This happens **before** confirmation is looked at, so a hypothesis that is both confirmed and refuted is rejected, and nothing records that it was also confirmed |
| confirmation | 308-315 | not rejected: **supported** if any `confirmed_by` predicate is True (all, if `confirm_requires_all`); otherwise **unresolved**. An `unmodelled` hypothesis is always unresolved |
| verdict | 321-335 | see the table below |

| supported | unresolved | verdict | code line |
|---|---|---|---|
| 0 | 0 | UNSUPPORTED ("everything declared was ruled out") | 326 |
| 1 | 0 | SUPPORTED | 328 |
| 0 | 1 | UNSUPPORTED ("one survivor, nothing confirms it") | 333 |
| 0 | ≥2 | AMBIGUOUS | 333 |
| ≥1 | ≥1, or ≥2 supported | AMBIGUOUS | 335 |

**Predicate call** (localization.py:136-140). Any exception is caught and
returned as None, which is the value that means "not measurable". This
happens in `Predicate.__call__`, so it covers every predicate, including the
derived `_FALSE` negations (signatures.py:815-825).

**Truth test** (localization.py:303, 310-311). A value counts only if it is
`is True`. A value that is neither True nor None (for example `numpy.True_`,
`1` or `"yes"`) is treated as not True, **and it is also not listed as
unmeasurable** (R10).

**Container access** (localization.py:92-94). `EvidenceIndex.one(relation,
component)` returns the **first** matching record in insertion order. It is
the only order-sensitive primitive (R6).

## 3. Predicates (signatures.py)

There are 26 base predicates, each with a derived `_FALSE` negation. They
fall into four groups by **how they treat a record that could not look**
(UNAVAILABLE) or had nothing to look at (NOT_APPLICABLE).

| group | predicates | treatment of UNAVAILABLE | correct in Kleene's strong logic (L05)? |
|---|---|---|---|
| single record via `_nominal` | SOURCE_INTERVAL, TRANSPORT, PROCESSING, CLOCK, COMMAND_DELIVERED, V1_1_FUNCTION_ELIGIBLE, RAIL_WITHIN_TOLERANCE, SOURCE_WITHIN_TOLERANCE | None | yes |
| single record, reads reason codes | CURRENT_PRESENT (184), STALL_SIGNATURE (192) | reads the codes of the UNAVAILABLE record as if it had looked: CURRENT_PRESENT becomes **True**, STALL_SIGNATURE **False** | no |
| single record, reads the state | PHYSICAL_RESPONSE_NOMINAL (199) | **False** ("did not move") | no |
| aggregate "no row adverse" | CHANNEL_LINK, ACTUATOR_LINK, ACTUATOR_POWER (via `_any_adverse_id`, 64-76); PRODUCER_PROCESS_HEALTHY (106), PRODUCER_DEADLINE_MET (126), PROCESS_ALIVE_AND_PRODUCING (138), CPU_HEADROOM (154), ESTIMATOR_PROCESS_HEALTHY (324), FUNCTION_LINKS (360), NO_TIMING_SEGMENT_OVER_BUDGET (343), FUNCTION_TIMING_WITHIN_DEADLINE (335, via an APPLICABLE filter that drops UNAVAILABLE rows) | an UNAVAILABLE row counts as **fine** | no |
| shared-node | SHARED_ADVERSE_{POWER,COMM,COMPUTE}_DEPENDENCY, NO_SHARED_ADVERSE_DEPENDENCY (218-307; the status test is line 238) | a shared node nobody reported, or reported UNAVAILABLE, counts as **not adverse** (`_any_adverse_id(...) is True`, 238) | no |

**Static reading and execution agree.**

- **Static.** The rows marked "no" above cover 18 of the 26 base predicates.
- **Executed (P12).** On the shipped corpus, 15 of them returned an answer
  with one record UNAVAILABLE that one of the record's two completions
  (NOMINAL, VIOLATED) contradicts.
- **The other three.** SHARED_ADVERSE_COMM_DEPENDENCY,
  SHARED_ADVERSE_COMPUTE_DEPENDENCY and NO_SHARED_ADVERSE_DEPENDENCY are not
  exercised in that form by the corpus. They are exercised by R17 and N6.

**Subject scope.** The `(index, subject)` signature is shared by every
predicate, but five of them ignore the subject and aggregate over the
**whole tick**:

- `_cpu_headroom_ok` (154);
- `_estimator_ok` (324: any COMPUTE process);
- `_nav_timing_ok` (335: any end-to-end channel);
- `_no_segment_over_budget` (343: any channel's segments);
- `_nav_link_ok` (360: any link).

The POSITION_UNAVAILABLE detector (`_degraded_position_functions`, 488-504)
calls three of them. As a result, any late process, late channel or down link
anywhere makes every navigation function a symptom subject (SC-05).

**Subject mismatch.** VOLTAGE_RAIL_LOW passes the rail as subject (507).
SOURCE_WITHIN_TOLERANCE looks up `power.source_health` **by that rail's
name** (371), and no source-health record carries a rail name. The predicate
is therefore None for every rail, in every scenario (R12). Two further
predicates are declared but no hypothesis uses them, in either polarity:
RAIL_WITHIN_TOLERANCE and PRODUCER_DEADLINE_MET (R13).

## 4. Attribution, `attribute()` (attribution.py:113-237)

| step | code | semantics |
|---|---|---|
| filter | 117-120 | `adverse` = attributable DEGRADED or VIOLATED. `nominal` = attributable NOMINAL. UNAVAILABLE and NOT_APPLICABLE records are neither, but their `dependencies` still enter the graph (147-151) |
| candidates | 126-136 | one candidate per distinct `(domain, component)` among the adverse records. Duplicates collapse here |
| common cause | 145-160 | a node reachable from two or more adverse candidates, which is itself adverse |
| `unsupported` field | 163-167 | every component that a relation firing on an adverse domain implicates, **minus the adverse ones**. It does not look at whether the component was observed, UNAVAILABLE or NOMINAL |
| one candidate | 169-205 | `discriminators` = **every** attributable NOMINAL record whose domain differs from the candidate's (174-176). Non-empty gives UNIQUE; empty gives AMBIGUOUS |
| several candidates | 214-237 | AMBIGUOUS, with `domains_excluded` and discriminators |

**What UNIQUE requires, in the code.** Exactly one adverse attributable
component, plus at least one attributable NOMINAL record from any other
domain. **No other condition exists.** Nothing checks that the NOMINAL record
is about an alternative explanation of the candidate (SC-01).

**Three statements of the UNIQUE rule, which disagree:**

| source | what it says |
|---|---|
| module docstring, attribution.py:22-28 | "every other domain that *would* have shown adverse evidence under a competing explanation is affirmatively NOMINAL" (relevance required) |
| code comment, attribution.py:170-172 | "the nominal readings from OTHER domains that would have gone adverse under a competing explanation" (relevance claimed; the code on the next line does not implement it) |
| spec, `engineering/v2/CROSS_DOMAIN_RELATION_SPEC.md` §2 | "`UNIQUE` requires at least one discriminator: a `NOMINAL` record from a different domain" (no relevance; this is what the code does) |

`tests/test_v2_framework.py:261-268` encodes the spec's version.

**`attribute_unsupported()`** (252-259) is the only function that returns the
attribution verdict UNSUPPORTED. No caller exists anywhere in the repository
(R13). The verdict is therefore unreachable, yet it is listed in
`api.ATTRIBUTION_VERDICTS` and in spec §1.

## 5. Where relevance is represented

Part 2 of the brief asks what "relevant evidence" means in current CSIA.
**No explicit relevance relation exists.** It is inferred, differently in
each place:

| place | how relevance is inferred | from which structure |
|---|---|---|
| attribution discriminator | domain differs from the candidate's | domain label only |
| attribution common cause | reachable through declared `dependencies` | dependency graph |
| attribution `unsupported` | named by a relation whose domains include an adverse record's domain | relation table |
| localization, channel or actuator subjects | the subject's declared `dependencies` in a domain (`_deps_in`, 58) | dependency graph |
| localization, process subjects | component name equals the subject | naming |
| localization, function subjects | **none**: whole-tick aggregates | nothing |
| function graph | `affected_functions` on each record | per-record declaration |
| `EvidenceRecord.source` | **never read by any reasoning path** (R18_source_field_read) | — |

Two different structures (dependencies and `affected_functions`) describe the
same wiring. Nothing checks that they agree (SC-18).

## 6. Exception behaviour by stage

| stage | on an exception | visible downstream? |
|---|---|---|
| domain plugin `evaluate` | caught by `PluginSupervisor`; emits an UNAVAILABLE `plugin.status` record; ledger event | yes |
| predicate | caught (localization.py:139); becomes None | **no**: it looks exactly like "not measurable" |
| symptom detector | propagates out of `engine.evaluate` | yes: the tick fails |
| missing predicate id | `KeyError` propagates | yes: the tick fails |
| `attribute()` on a malformed record (`dependencies=None`, `reason_codes=None`) | `TypeError` propagates | yes: the tick fails |
| `EvidenceRecord.__post_init__` | validates the enum types and three non-empty strings; does **not** validate tuple fields | — |

## 7. Downstream consumers of these outputs

| consumer | reads | decides anything? |
|---|---|---|
| `explanation.explain()` | localization supported / unresolved / rejected → limiting / possible / cleared domains | no: a derived report. A domain rejected by a missing-evidence refutation is reported as **cleared**, "measured and found fine" |
| `ledger.py` 257-290 | the localization and attribution verdicts, as events | no |
| `api.py` | the attribution verdict is validated against the four-word vocabulary | no. The API "issues no command" (tests/test_v2_api_ledger.py:228-256) |
| XSYS-001 | `localize()` with its **own** spec and predicates (`xsys_v2_adapter.py`); never `attribute()`, never `signatures.PREDICATES` | a sealed experimental result |
| FORGE | nothing (FORGE production code is forbidden: `docs/CURRENT_PROGRAM_STATE.md` §1) | — |

No path in the repository actuates anything on a v2 localization or
attribution verdict. This bounds the **current** severity of every finding
(`FINDINGS.csv`).
