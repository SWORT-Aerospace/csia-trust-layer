# IMU common-mode risk — recorded, not resolved

## The fact

The Holybro Kakute H743-Wing and the Mikroe 6DOF IMU 14 Click reference
carrier both use **ICM-42688-P class** devices.

## The three independence questions, answered separately

They are separate because they fail separately, and a system that reports one
number for "independence" cannot say which one it has.

| independence | status | what it means |
|---|---|---|
| **acquisition path** | `POSSIBLE` / `YES_DEPENDING_ON_IMPLEMENTATION` | Different bus, different driver, different sampling code. Achievable by design and **not yet designed** — so it is `POSSIBLE`, not `YES` |
| **power path** | `CANDIDATE` | Separable if the reference sensor sits on the research power domain rather than the flight domain. That is what `XR1_POWER_DOMAINS.md` R2 reserves, so it is a candidate rather than a fact |
| **device family** | **`NO`** | Both are ICM-42688-P class. This is not improvable by wiring |

## Why the third one is the one that matters

A shared device family means a shared **failure mode**: the same errata, the
same temperature-dependent bias behaviour, the same response to a mechanical
resonance, the same firmware bug if any. Two units of the same part agreeing
is weaker evidence than two different parts agreeing, and the amount weaker is
not quantifiable from here.

This bears directly on the frozen trust graph. `redundant_imu` is a relation
in it, and the relation's diagnostic value rests on the two IMUs being able to
disagree for independent reasons. If they cannot, the relation is measuring
something narrower than its name suggests.

**That is a limitation of a future XR configuration, not a finding about
CSIA.** No CSIA result depends on it, and nothing in Paper I is affected.

## The future requirement

> **Reserve an optional heterogeneous reference-IMU interface**: a mount and
> a bus that can accept a reference IMU from a *different device family*.

Tier: **LATER_RESERVED** (R8 in `XR1C_ASSURANCE_ARCHITECTURE_REQUIREMENTS.md`).

**DO NOT SELECT OR PURCHASE HARDWARE YET.** The reservation is space, a
mounting datum and a bus. Choosing a specific alternative device needs a
comparison nobody has done, against requirements — noise, bandwidth,
temperature behaviour, availability — that F1 has not yet produced.

## What must be measured before the reservation can be sized

- The candidate device family's footprint, once one is chosen.
- Its bus requirements, which may differ from the Click board's.
- Whether it fits the reference-sensor spine (R11) or needs its own mount.

None of these is knowable today, and the reservation is therefore *space and
a datum*, not a specific footprint.

## What this does not say

- It does **not** say the current pairing is unusable. Two same-family IMUs
  still detect a great many faults — a hard failure, a stuck value, a
  mechanical mounting problem, a bias that develops in one unit and not the
  other.
- It does **not** quantify the residual risk. Doing so would need a
  common-mode failure rate for this device family, which is not available
  here and would be invented if stated.
- It does **not** affect any E1 result. E1 ran in simulation on two autopilot
  stacks and this is a statement about a future physical article.
