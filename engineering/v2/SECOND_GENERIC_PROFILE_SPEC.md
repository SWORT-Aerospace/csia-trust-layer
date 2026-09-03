# THE SECOND GENERIC PROFILE — PUMP SKID

Phase C §30, §37. Implementation: `csia/v2/profiles/pump_skid.py`.

---

## 1. What §30 asks for and why a third machine

> ONE second structurally different synthetic profile.

The electric motor test stand (§37) already proved the framework carries no
aircraft assumption: it registers no SENSOR domain, uses no v1.1, and needs no
aviation vocabulary. But the bench is structurally the **same shape** as the
aircraft — a set of required domains per function, each either fine or not.

A second profile only earns its place if it needs something the first two
could not express. The pump skid does:

| construct | aircraft | test stand | pump skid |
|---|---|---|---|
| REQUIRED domains | yes | yes | yes |
| SUPPORTING domains | yes | yes | yes |
| REDUNDANT one-of-N | — | — | **yes** |
| FALLBACK requirement set | — | — | **yes** |
| OPTIONAL domain | — | — | **yes** |

## 2. The machine

A two-pump skid holding pressure on a line, running unattended.

| function | requires | structure |
|---|---|---|
| `FLOW_DELIVERY` | POWER (+COMPUTE supporting) | one-of-N over `ACTUATION/pump_a`, `ACTUATION/pump_b` |
| `PRESSURE_REGULATION` | COMPUTE, TIMING, COMMUNICATION | falls back to `OPEN_LOOP_ON_SPEED` requiring COMPUTE + POWER |
| `CONDITION_MONITORING` | COMPUTE | TIMING is **optional** — its absence is not a fault |
| `UNATTENDED_OPERATION` | POWER, COMPUTE, TIMING, COMMUNICATION | one-of-N over the two pumps |

## 3. What building it changed in the framework

**Redundancy had to move from domains to components.** The first
implementation grouped redundant *domains*. Both pumps are `ACTUATION`, so a
domain-level group cannot express "either pump will do" — it can only say
"ACTUATION is required", which is exactly what it already said. Groups are now
over component ids (`"DOMAIN/component"`), and redundancy is computed per
member from the evidence records.

This is the entire value of a second profile: it found a modelling error that
neither existing profile could expose, because neither had two interchangeable
things in one domain.

**Two reason codes came out of it**, and both are visible to callers:

- `REDUNDANT_GROUP_EXHAUSTED` — every member of a group is adverse
- `REDUNDANCY_REDUCED` — the requirement is still met, without margin. Emitted
  **alongside** `ALL_REQUIREMENTS_MET`, because "running on one pump" is an
  operational fact an operator needs even though nothing is currently lost.

**Fallback needed to be a requirement set, not a string.** The aircraft's
`fallback` field is prose for a human. `PRESSURE_REGULATION` needs the system
to *evaluate* whether the fallback is satisfiable and to report
`active_fallback` when it is carrying the function. That is
`fallback_requirements: {name: (domains,)}`.

## 4. The genericity claim, and how it is tested

A test runs the pump skid in a **fresh interpreter** and asserts that neither
`csia.v1_1` nor the aircraft profile appears in `sys.modules` afterwards. The
same test exists for the bench. This is the only form of the claim worth
making — a README saying "generic" is not evidence.

It required a real change to make true: `csia/v2/profiles/__init__.py` and
`csia/v2/domains/__init__.py` use lazy PEP-562 `__getattr__`, because eager
re-exports meant importing *any* domain pulled in the whole v1.1 stack. The
test failed, and the code was fixed rather than the test.

A second test asserts the structural difference is real rather than cosmetic:
the pump skid declares redundant groups and fallback requirement sets, and the
bench declares neither.

## 5. Scenarios

Six, over `PUMP_SKID_NOMINAL`, covering: one pump lost (redundancy reduced,
function still eligible), both pumps lost (group exhausted), the regulation
loop losing its link and running open-loop on the fallback, and the optional
TIMING domain going silent without degrading anything.

## 6. What this profile does NOT show

It has no SENSOR domain and no v1.1, so it says nothing about the navigation
plugin. It is a **synthetic** profile: the numbers are invented, and no real
pump skid data exists anywhere in this repository. Its purpose is structural —
to prove the function model can express one-of-N and fallback, and to have
found the component-level redundancy error before a real platform did.
