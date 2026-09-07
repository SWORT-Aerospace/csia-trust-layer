# Actuator evidence — three distinct quantities, and why the difference matters

## The three quantities

They are routinely conflated, and conflating them is how a control system
comes to believe a surface is where it commanded it to be.

| quantity | what it is | who knows it |
|---|---|---|
| **commanded control demand** | what the control law asked for — a moment, a rate, a deflection in engineering units | the control law |
| **servo command** | the PWM or protocol value actually sent to the servo | the flight computer's output stage |
| **measured surface position** | where the control surface physically is | **nobody, on this airframe** |

## Current status

| quantity | availability |
|---|---|
| commanded control demand | derivable from the flight computer's logs |
| servo command | available — this is what `actuator.elevon.command_echo` is |
| **measured surface position** | **`NOT_AVAILABLE`** |

**`NOT_AVAILABLE` unless a repository artifact says otherwise, and none does.**
No position feedback path exists in `XR1_DRAFT_PROFILE.yaml`, no such evidence
id appears in `csia_mission/xr1_contracts.py`, and none is claimed.

## Why the evidence id is named `command_echo` and not `elevon_position`

Because it is an echo. It says *this value was sent*. It does not say the
servo moved, that the linkage is intact, that the horn has not slipped, that
the surface is not jammed, or that the servo has not stalled against a load.

**Servo command is not surface position, and a system that treats them as the
same has assumed away every actuator failure mode there is.** The name is the
guard: an evidence id called `elevon_position` would be used as one.

This is the same discipline the whole programme runs on — the distinction
between *what was asserted* and *what the evidence supports* — applied one
layer down, to an actuator instead of a hypothesis.

## What follows for the capability contracts

`stable_flight` and `controlled_glide` both declare
`requires_actuators=("elevon_left", "elevon_right")`. The actuator state
handed to `evaluate_capabilities` today can only be derived from the command
echo, so:

> **An actuator reported SUPPORTED today means "the command path is
> answering", not "the surface is where it was asked to be".**

That is a weaker statement than the capability name suggests, and it is
recorded here rather than left for someone to discover from a flight.

## The future evidence source

> **Surface-position sensing should become an OPTIONAL evidence source.**

Tier: **LATER_RESERVED** (R10). What the reservation is:

- routing to each hinge,
- a sensor pocket or mounting provision at each surface,
- a datum from which a measured angle is meaningful.

**Not a sensor selection.** Hall-effect, potentiometric and optical
approaches all exist with different mass, reliability and resolution
trade-offs, and nothing here has evaluated them.

## What it would buy, stated concretely

With measured surface position as evidence, several things become possible
that are not possible now:

1. **A real actuator health relation** — command against measured position,
   which detects a jam, a slipped horn, a stalled servo and a linkage failure.
   None of these is detectable from an echo.
2. **Surface effectiveness identification** — measured deflection against
   measured aircraft response, which is the F2/F3 research question that the
   four-zone control study in `XR1_CONTROL_SURFACE_STUDY.md` turns on.
3. **An honest `controlled_glide` contract** — a glide capability that
   depends on surfaces actually moving, rather than on commands being sent.

## What must not be done in the meantime

- **Do not add an `elevon_position` evidence id populated from the command.**
  That is BAD_PRODUCT-shaped: a value that looks like a measurement and is a
  restatement of the input.
- **Do not upgrade `actuator.elevon.command_echo`'s meaning** without the
  sensor. The contracts would silently start claiming more than the hardware
  supports.
