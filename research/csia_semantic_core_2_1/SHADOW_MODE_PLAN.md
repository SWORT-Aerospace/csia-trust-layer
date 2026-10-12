# Shadow-mode plan: 2.0 default, 2.1 in shadow

**PREPARED, NOT EXECUTED. 2026-09-30.**

Nothing in this plan has been wired, deployed or run. Executing it needs a
separate owner go-ahead. This plan exists because the promotion decision is
`SEMANTIC_2_1_READY_FOR_SHADOW` (`PROMOTION_DECISION.md`).

## 1. The rule

| | 2.0.0 (frozen v2) | 2.1.0 (csia_semantic_core) |
|---|---|---|
| runs on | every tick, the same `SystemAssurance.records` | the same records, after 2.0.0 has produced its output |
| controls downstream behaviour | **yes. The only thing that does** | **no. Nothing reads it for any decision, command, display state or ledger event** |
| output goes to | where it goes today | a separate shadow log only |
| may FORGE, the API, the engine or anything else act on it | as today | **no** |

**No automatic action is taken from 2.1.** In particular:
- no adaptation or reconfiguration;
- no flight-control input;
- no suppression or escalation of a 2.0.0 result.

## 2. How it would be wired

This is the design only. It needs no change to `csia/`.

1. **An observer outside `csia/`.**
   - It takes each `SystemAssurance` the engine has **already** returned and
     calls `reason_historical_tick(assurance, core)`, with
     `core = SemanticCore21.from_engine(engine)`, built once per engine.
   - It reads `assurance.records`, which are frozen dataclasses, and never
     writes to them.
2. **An exception barrier.** Any exception inside the observer is caught and
   logged as a shadow fault. It never propagates into the default path. The
   2.0.0 result is returned untouched whether or not the shadow ran.
3. **A difference log.** Per tick, one JSON line:
   - tick time and engine configuration digest;
   - the 2.0.0 decision (verdict, supported, unresolved, rejected per
     localization, and the attribution verdict and candidates);
   - the 2.1 decision in its 2.0.0 view;
   - 2.1's `outcome`, `evaluation`, `withheld_unique_because` and
     `predicate_errors`;
   - the rule responsible, from the same single-switch comparison the
     differential uses.

   Identical ticks log a counter only. The log stays out of the v2 ledger.
4. **A budget.** The shadow runs with `trace=False` by default, at about
   0.3 ms per tick extra on a desktop. Full-trace capture is enabled per
   incident. On a constrained target the shadow runs off the control loop,
   for example on logged records, or not at all. **No embedded
   implementation of 2.1 exists.**

## 3. What shadow mode must show before anything else is considered

| check | pass condition |
|---|---|
| every difference is explained | each logged difference maps to C1, F2, C2, C3, C4 or C6 with a reason code; 0 UNATTRIBUTED |
| no new certainty | 0 cases where 2.1 is UNIQUE and 2.0 is not; 0 SUPPORTED in 2.1 that 2.0 did not give (except the documented C2 case where 2.0 rejected on an UNAVAILABLE record) |
| faults surface | every `PREDICATE_FAULT` is investigated; none is silent |
| profile gaps | the G-1, G-2 and G-3 differences are recognised as such and handed to the owner as profile decisions |
| stability | no shadow exception reaches the default path; no memory growth over a long run |
| XSYS-001 | not re-run in shadow. Its gate already passed on the sealed data |

## 4. What this plan does not do

It does not:
- make 2.1 the default;
- delete or deprecate frozen v2;
- let FORGE or any action layer read 2.1;
- change a profile;
- execute anything.

After shadow mode, promotion to default is a **separate** owner decision with
its own evidence.
