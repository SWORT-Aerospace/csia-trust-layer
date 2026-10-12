# FORGE — FUTURE, DOCUMENTATION ONLY

**THERE IS NO FORGE PRODUCTION CODE IN THIS REPOSITORY AND NONE MAY BE
WRITTEN.** This directory contains two markdown files and nothing else. A
`.py` appearing here before the paper lock is released is a violation of the
current program state, and `tests/test_program_state.py` asserts the directory
stays code-free.

Read `docs/CURRENT_PROGRAM_STATE.md` first.

---

## 1. What Forge would be

A tool that turns **engineering artifacts an organisation already has** into a
CSIA profile — the rails, processes, links, actuators, functions and
dependency structure that `csia/v2/profiles/` currently contains as
hand-written Python.

Today a profile is written by hand. That is why the genericity result is
n = 3 and single-author, and why Set C's dependency-model blind spot exists at
all: nobody declared the real sampling and bus dependencies of each source,
because declaring them by hand is tedious and nothing forced it.

## 2. Inputs — IMPORT, DO NOT INVENT

> DO NOT invent another modeling language unless a demonstrated gap requires
> it.

| input | what it carries |
|---|---|
| **SysML v2** | components, parts, ports, connections, requirements |
| **AADL** | components, bindings, buses, processors, threads, memory |
| **EMV2** (AADL error-model annex) | error types, propagations, error flows, fault behaviour |
| **CycloneDX** | the software bill of materials — versions, components, dependencies |
| **platform configuration** | the actual rails, links and sensors as configured |
| **controller configuration** | PX4/ArduPilot parameters, ROS launch, PLC configuration |

Every one of these is an existing standard with existing tooling. A new DSL
would need to justify itself against all six, and a "we needed a cleaner
syntax" justification is not a demonstrated gap.

**EMV2 is the closest fit to what CSIA needs** and is the first thing to
evaluate: error propagation paths are exactly the dependency structure §13's
common-cause reasoning is blind without.

## 3. Canonical IR

One intermediate representation, targeted by every importer and consumed by
the profile emitter:

```
  components          the things that can fail
  sources             what produces evidence
  power domains       rails, converters, batteries; the shared-node structure
  links               buses, serial, network; who rides what
  compute             processes, nodes, budgets, deadlines
  actuation           drives, motors, valves; command and response paths
  functions           what the system is for, and what each function needs
  fault propagation   how a failure in one component reaches another
  evidence            which relation observes which component, and when it is
                      applicable
  redundancy          one-of-N groups, at COMPONENT granularity (the pump-skid
                      lesson: two pumps are both ACTUATION)
  resources           what is contended for
  alternate configs   fallback requirement sets
```

This list is not aspirational — it is the union of what `csia/v2/functions.py`
and the three existing profiles already need. The IR's job is to be the thing
an importer can fill and a profile emitter can read.

## 4. Solvers — USE, DO NOT WRITE

> DO NOT implement a custom solver.

| solver | for |
|---|---|
| **Z3** | satisfiability over configurations; "is there a configuration safe for every hypothesis still supported"; structural diagnosability questions |
| **OR-Tools / CP-SAT** | assignment and selection under constraints; sensor placement; redundancy allocation |

Both are mature, both are used in exactly this space, and a hand-rolled solver
would be a research project that is not this research project.

## 5. What Forge would NOT do

- **It would not diagnose.** It emits a profile; the deterministic layer
  decides.
- **It would not reconfigure anything.** Reconfiguration is the controller's
  authority.
- **It would not replace a hand-written profile silently.** A generated
  profile must be diffable against the hand-written one, and the aircraft
  profile is the natural first test: Forge is credible only if it can
  regenerate what a human already wrote.

## 6. The first thing to build, when it is allowed

Not the importer. **The IR plus a round-trip test against the existing
`pump_skid` profile.** If the IR cannot express one-of-N redundancy at
component granularity and a fallback requirement set — the two things the
pump skid exists to exercise — the IR is wrong and no importer will fix it.

## 7. Gate

Nothing in this directory may become code until:

- tag `systems-paper-submission-candidate` exists, **and**
- tag `math-paper-submission-candidate` exists, **and**
- `forge/PRIOR_ART_REQUIRED.md` has been worked through and its conclusions
  recorded.
