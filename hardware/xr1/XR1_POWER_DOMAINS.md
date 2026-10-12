# Power-domain dependency model — requirements only

**No power electronics are designed here.** This document states what the
assurance architecture needs from the power system and why. Component
selection, topology and sizing are separate work.

---

## The two logical domains

| domain | carries | the claim it must support |
|---|---|---|
| **FLIGHT_CRITICAL_POWER** | flight computer, servos, receiver, GNSS | the aircraft stays controllable |
| **RESEARCH_POWER** | research compute (CM4), payload cameras, reference sensors, research logger | the research payload runs |

## The claim this separation exists to make testable

> **A research-compute failure does not imply flight-control loss.**

If both domains share one route, that claim can never be *tested* — every
research-power failure is simultaneously a flight-power failure, and the
experiment that would separate them does not exist.

This matters to the capability contracts directly. `stable_flight` requires
`attitude_hold` and `altitude_hold` and **does not require any compute
domain**. `local_mapping` requires `compute:mapping`. That distinction is
written into `csia_mission/xr1_contracts.py` — and it is a fiction unless the
power routing supports it.

## Common-mode dependencies, which must be modelled and not wished away

Separating the routes does not make the domains independent. These remain
shared and each is a real path by which one domain takes the other down:

| shared element | the failure it propagates |
|---|---|
| **the battery** | a cell failure or a disconnect takes both domains |
| **the main harness / connector** | one connector, both domains |
| **the airframe structure** as a ground return | a structural ground fault couples them |
| **thermal environment** | a research component overheating in a shared bay affects flight components |
| **electromagnetic environment** | research switching noise couples into flight sensing |

**So the correct model is two domains with a declared shared set, not two
independent domains.** A model claiming independence would be a stronger claim
than the hardware supports, and the assurance layer would then certify
capabilities on the strength of it.

## Requirements

| # | requirement | why |
|---|---|---|
| P1 | **Separate power routes** from the shared source to each domain | makes the separation claim testable at all |
| P2 | **Independent protection per domain** — a research fault must not open the flight domain's protection | otherwise the routes are separate and the failure is not |
| P3 | **Current and voltage telemetry on each domain, separately** | `power.telemetry.supported` is declared evidence. One combined reading cannot attribute a fault to a domain |
| P4 | **A research-domain kill that leaves flight power up** | the direct test of the claim. Without it the claim is argued, not demonstrated |
| P5 | **The shared set declared explicitly** in the vehicle profile | so a common-mode failure is a modelled event rather than a surprise |
| P6 | **Reference sensors on RESEARCH_POWER** | supports the power-path independence candidate in `XR1_IMU_COMMON_MODE.md` — a reference IMU sharing the flight rail shares its brownouts |

P1–P4 are **FIRST_FLIGHT_REQUIRED** (R2, R4 in the requirements document).
P5–P6 follow from them.

## What this does not do

- It does **not** design a BEC, a regulator, a protection device or a harness.
- It does **not** specify voltages, currents or wire gauges — none is derivable
  from anything supplied to this session.
- It does **not** claim the two domains would be independent. They share a
  battery, a harness and an airframe, and the model says so.
- It does **not** make a flight-safety argument. Nothing here has been
  reviewed for airworthiness and none of it is a safety case.
