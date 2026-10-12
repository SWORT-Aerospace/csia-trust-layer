# XR-1 assurance architecture — physical requirements

**NO CAD WAS EDITED TO PRODUCE THIS DOCUMENT, AND NONE MAY BE EDITED FROM IT
WITHOUT A SEPARATE DECISION.** Every requirement below is stated as a
*research need it serves*, not as a geometry.

**NO DIMENSION IS INVENTED HERE.** Where a reservation needs a size, this
document says *what must be measured to establish it* rather than supplying a
number. `XR1_DRAFT_PROFILE.yaml` carries the supplied figures with their
provenance; nothing new is added.

---

## How to read the three tiers

| tier | meaning |
|---|---|
| **FIRST_FLIGHT_REQUIRED** | F1 cannot happen without it, or happens without producing usable evidence |
| **LATER_RESERVED** | not needed for F1, but the airframe must not have to be redesigned to accept it later. A reservation is *space, routing and a mounting datum* — not a purchase |
| **OPTIONAL_EXPERIMENTAL** | worth doing if it is cheap. Nothing depends on it |

**A reservation is the cheapest thing on this list and the most expensive to
add later.** Space and a datum cost grams at design time and a new airframe
after first flight.

---

## FIRST_FLIGHT_REQUIRED

| # | requirement | the research need it serves |
|---|---|---|
| R1 | **Known mount datums** for the flight computer, reference IMU, GNSS and each payload position | Every sensor transform in `XR1_PAYLOAD_AND_TRANSFORMS.yaml` is currently `UNKNOWN`. A datum is what makes a transform *measurable at all*. Without it there is no lever arm, and without a lever arm there is no physical residual analysis at any later stage |
| R2 | **Separate research and flight power routes** | The system must be able to show that a research-compute failure does not imply flight-control loss. If they share one route, that is one claim that can never be tested. See `XR1_POWER_DOMAINS.md` |
| R3 | **Hardware timing / event header** | `timebase.supported` is a load-bearing capability that almost everything else depends on. A shared hardware event edge is what lets the flight computer's clock and the research computer's clock be related by *measurement* rather than by assumption |
| R4 | **Power telemetry on both domains** | `power.telemetry.supported` is declared evidence. Without current and voltage on each route, a power-related degradation is invisible to the assurance layer |
| R5 | **Research logger with its own storage** | Raw evidence is archived before reduction. That rule is meaningless if the only copy is on the flight computer's card and the flight computer is what failed |
| R6 | **CSIA in SHADOW ONLY, with no wired command path** | Same discipline as E2 §4.1: the receive line is physically absent, so `NO_COMMAND_PATH_REACHABLE` is a property of the wiring rather than a promise made by software |

## LATER_RESERVED

| # | reservation | the research need it serves | what must be measured first |
|---|---|---|---|
| R7 | **Flight-computer cassette / adapter plate** | Lets the airframe accept the Kakute H743-Wing *and* an FMUv6C/Pixhawk-6C-class board without structural redesign — so the E2 validation article and the XR research article can share one software configuration. See `XR_FC_MODULARITY_REQUIREMENT.md` | Both boards' hole patterns, connector positions and heights; the deepest connector stack |
| R8 | **Heterogeneous reference-IMU mount** | The Kakute and the reference carrier are both ICM-42688-P class. Device-family independence is **NO** today. A second mount that accepts a *different device family* is what makes that recoverable later. See `XR1_IMU_COMMON_MODE.md`. **Do not select or buy a part now** | The candidate device family's footprint, once one is chosen |
| R9 | **Modular RGB / thermal payload cassette** | The two payloads must be able to fail independently — that independence is what makes `bridge_thermal_inspection` survive an RGB failure. A shared cassette with shared power and one data path would create a common mode the contracts say does not exist | Both payloads' envelopes, once selected |
| R10 | **Surface-position sensing provision** | Today the system cannot distinguish *servo command* from *measured surface position*, and `actuator.elevon.command_echo` is honest about being an echo. Routing and a sensor pocket at each hinge is what lets that become real evidence later. See `XR1_ACTUATOR_EVIDENCE.md` | Hinge geometry and the chosen sensing method |
| R11 | **Reference-sensor spine** | A rigid, datum-referenced rail carrying reference sensors. Without one, every reference measurement's lever arm changes when anything is re-mounted, and no two flights are comparable | Spine length and the sensor set it must carry |
| R12 | **Fault-injection service connector** | E3 needs to interrupt a sensor power or data line *physically*. A connector reserved now is a connector; added later it is a wiring loom change | Which lines E3 will interrupt — an E3 decision, not an F1 one |
| R13 | **Battery indexing** | The battery is the largest single mass at 1.22 kg. An indexed position makes the CG repeatable between flights; an unindexed one makes CG a per-flight unknown that pollutes every comparison | **Battery envelope — currently `UNKNOWN` and blocking. Must be measured before CAD freeze** |
| R14 | **Structural-sensor wiring paths** | F2 adds structural instrumentation. Wiring paths reserved now cost nothing; retrofitted, they mean opening the structure | The sensor count and positions, at F2 |

## OPTIONAL_EXPERIMENTAL

| # | item | note |
|---|---|---|
| R15 | **Replaceable aerodynamic tip modules** | Would let tip geometry be a variable in a controlled experiment. Nothing in the assurance architecture needs it |
| R16 | **Second GNSS antenna position** | Would allow a heading-from-baseline experiment. A real research question and not one this programme has posed |

---

## What is deliberately NOT on this list

**Redundant propulsion.** Nothing here assumes it, and
`XR1_PROPULSION_DEGRADATION.md` defines the dependency semantics of powered
flight, unpowered glide and controlled recovery *without* asserting that any
of them is achievable on this airframe.

**Anything with flight authority.** No ZETH, no active Forge, no SACA. CSIA
is in shadow and the planner gate has no actuator path.

**Prices.** Vendor sites are unreachable from this environment (the agent
proxy answers 403 at CONNECT), so any figure would be invented.

**Dimensions for anything not measured.** Every reservation above names what
must be measured first, because a reservation sized from a guess is a guess
with a mounting hole in it.

---

## The blocking item

**The battery envelope is `UNKNOWN` and blocks R13, and R13 blocks a
repeatable CG.** It is the one measurement on this page that can be taken
today, with the part in hand and a set of calipers, and it gates more than
anything else here.
