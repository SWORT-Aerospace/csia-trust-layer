# DOMAIN PLUGIN CONTRACT — v2 §§2, 21, 22

Implementation: `csia/v2/domain.py`, `csia/v2/registry.py`.

---

## 1. THE CONTRACT

A plugin declares seven things and implements one method.

| declaration | purpose |
|---|---|
| `domain_id` | stable id; must be in `DOMAIN_IDS` |
| `schema_version` | this plugin's evidence version, independent of the core |
| `required_inputs` | signals without which it can do nothing |
| `optional_inputs` | signals it uses if present and works without if absent |
| `relations` | the checks it can emit, as stable ids |
| `affected_functions` | the system functions its evidence can bear on |
| `reason_codes` | the codes it can emit |

```python
def evaluate(self, snapshot: Snapshot) -> DomainResult
```

`DomainResult` carries `records` (the evidence) and `unevaluated` — the
components or relations it could not assess, **and why**. The second field is
not decoration: a domain that silently skips a relation looks identical to one
that found it healthy, and the difference is the whole point of the system.

§2 offers a candidate interface with `observe()`, `evaluate()` and
`evidence()` as separate calls, and says not to commit to names before
reviewing the v1.1 APIs. Having reviewed them, the three collapsed into one.
Splitting them would require the plugin to hold state between the calls, and
holding state is exactly what the determinism requirement forbids; a domain
that could not be replayed from a single snapshot would make the ledger
unreplayable too.

## 2. DETERMINISM IS PART OF THE CONTRACT

Same snapshot in, same records out. No clock reads, no randomness, no network,
no global state, no accumulation between ticks. Restart counts and
deadline-miss counts are **read from the snapshot**, not counted here.

Where a domain would want history — a jitter estimate, a filtered no-load
voltage reference — the host supplies it as a signal. That keeps the
computation the host already does where the host already does it, and keeps
the domain replayable. `tests/test_v2_domains.py` runs each domain twice on
the same snapshot and compares.

## 3. THE REGISTRY — §21

`DomainRegistry.register()` refuses, loudly, a plugin that:

- declares no `domain_id`, or one the core does not know
- duplicates an already-registered `domain_id`
- declares a schema major other than the core's
- declares no relations, or no affected functions

Every rejection raises. None is downgraded to a warning, because a silently
dropped domain is a domain whose evidence stops appearing while everything
still looks like it is working.

`domains()` returns them **sorted by id**. Two hosts that registered the same
plugins in different orders therefore produce the same evidence sequence and
the same ledger — a property the tests check directly, because it is the
difference between a reproducible ledger and one that depends on start-up
order.

## 4. WHAT A DOMAIN MAY NOT DO

- **Import another domain.** A domain that reached into another domain's
  module would be a cross-domain relation written in the wrong place. Those
  are declared in the relation table where they can be listed and reviewed.
- **Invent a threshold.** Every limit is host-declared on a spec object.
  Where a limit is absent the relation is *not evaluated* and says so in
  `unevaluated`; it does not fall back to a default and it does not pass.
- **Manufacture a number.** `observation_state` is required and categorical;
  `measured_value` / `residual` are optional. A domain without a residual
  reports none.
- **Attach its evidence to a function the host did not declare.** Per-component
  `affected_functions` is how a rail limits the functions it actually feeds.

## 5. DEPENDENCIES ARE STRUCTURE, NOT A SCORE — §22

Every record may carry `dependencies`: a tuple of `"DOMAIN/component"` ids the
host has declared. Two sensors on one 5 V rail are not independent evidence,
and **saying which rail** is the honest first step. Inventing a correlation
number for it is not, and §22 says not to.

The attribution layer walks that declared graph transitively to find a shared
adverse dependency (`CROSS_DOMAIN_RELATION_SPEC.md` §3). Walking a declared
graph is deterministic and reviewable. Estimating independence from data is a
different thing, is not done, and is not planned for v2.

## 6. THE COST OF ADDING A DOMAIN

One module implementing `evaluate`, plus its declarations in a profile. **No
core module changes.** The six built domains are the evidence for that claim;
the five specified-but-not-built ones (`FIRMWARE_DOMAIN_SPEC.md`,
`ESTIMATOR_DOMAIN_SPEC.md`, `SECURITY_DOMAIN_FUTURE_SPEC.md`, plus THERMAL and
STORAGE) are the test of it that has not yet been run, and the report says so
rather than assuming it passes.

## 7. THE `attributable` FLAG

A record may set `attributable=False`. It stays full evidence for the domain
state and the function graph, but it cannot become a **cause candidate**.

This is for derived statements — a roll-up, an aggregate, a transcribed
verdict. A v1.1 function eligibility is a conclusion computed from other
records in the same tick; admitting it as a candidate counts its own inputs
twice and fills the candidate list with things that are not components and
cannot fail. The v1.1 wrapper sets it on three of its five relations.
