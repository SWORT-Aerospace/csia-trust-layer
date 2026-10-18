# SWORT AUTONOMY STACK — FUTURE ARCHITECTURE

**DOCUMENTATION ONLY. NOTHING BELOW IS IMPLEMENTED, AND NOTHING BELOW MAY BE
IMPLEMENTED UNTIL THE PAPER LOCK IS RELEASED.**

See `docs/CURRENT_PROGRAM_STATE.md` for what is actually built today.

---

## The four layers

```
  +-----------------------------------------------------------------+
  |  ZETH                                                            |
  |  AI mission / planning / optimization layer                      |
  |  proposes; never asserts a fact about system health              |
  +-----------------------------------------------------------------+
                      |  intent, plans, options
                      v
  +-----------------------------------------------------------------+
  |  CSIA                                                            |
  |  deterministic cross-system assurance and resilience layer       |
  |  which system functions are still justified, on what evidence,   |
  |  and what limits them                                            |
  +-----------------------------------------------------------------+
                      |  function eligibility + evidence + limits
                      v
  +-----------------------------------------------------------------+
  |  EXISTING CONTROLLER                                             |
  |  PX4 / ArduPilot / ROS / PLC / other                             |
  |  decides what to DO. CSIA issues no command, ever.               |
  +-----------------------------------------------------------------+
                      |  actuation
                      v
  +-----------------------------------------------------------------+
  |  PHYSICAL SYSTEM                                                 |
  +-----------------------------------------------------------------+
```

## The one rule that makes the stack coherent

**AI may help interpret. Deterministic evidence decides.**

There is no back edge from ZETH into CSIA's verdict. An AI layer that could
modify function eligibility would make the assurance verdict unverifiable, and
the assurance ledger would become a record of an opinion. The three
prohibitions are already written down in
`engineering/v2/AI_ANALYST_FUTURE_SPEC.md` and they govern this stack too:

1. an AI component may not modify function eligibility directly;
2. it may not issue control commands;
3. it may not turn an unsupported hypothesis into a confirmed cause.

## What each layer owns

| layer | owns | must never |
|---|---|---|
| ZETH | mission intent, planning, optimisation, option generation | assert a fact about system health; write into the assurance ledger |
| CSIA | which functions are justified; by what evidence; what limits them; what is ambiguous | issue a command; reach an actuator; claim a unique cause without discriminating evidence |
| controller | all authority. Chooses what to do with CSIA's report | be required to trust an `UNKNOWN` as an `ELIGIBLE` |
| physical system | the ground truth nobody has | — |

## Why CSIA sits below the AI layer and above the controller

Below the AI layer, because assurance must be reproducible from a ledger and a
replay. Above the controller, because the controller's job is authority and
CSIA's job is justification, and merging them is how a monitor acquires the
ability to crash a vehicle.

The seam is already load-bearing in the built system: `csia/v1_1/firewall.py`
and the Phase-4 output API exist precisely so a consumer reads a versioned
read-only document rather than reaching into the layer.

## Interfaces that already exist and would carry this

| interface | status today |
|---|---|
| v1.1 output schema `1.1.0` | **built, frozen** — the versioned read-only document a controller reads |
| v2 `SystemAssurance` per-tick document | **built** at Phase C, frozen |
| the assurance ledger (v1.1 and v2) | **built** — hash-chained, replay-verified |
| the internal typed path (`csia/v2/ingest.py`) | **built** — in-process, version-locked, construction-controlled only |
| ZETH ↔ CSIA | **does not exist** |
| Forge → CSIA profile generation | **does not exist** |

## What this document is not

It is not a roadmap with dates, not a commitment, and not authorisation.
Product development is **frozen at v2 Phase C**
(`engineering/v2/V2_PHASEC_FREEZE.md`) until both papers reach
submission-candidate state.
