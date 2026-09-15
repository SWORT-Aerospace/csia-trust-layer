# E2M — device identity behind an I²C multiplexer

**TEMPLATE, NOT A COMMITTED PREREGISTRATION. `E2M_STATUS` = `NOT_RUN`.**

Every field marked `[FILL: …]` is blank because it cannot honestly be written
before parts exist on a bench. Everything else is fixed **now**, before any
hardware is purchased, on the precedent set by
`research/physical_validation/prereg/E2_HARDWARE_BOUNDARY_PREREG.md` — so that
no design decision can be made after seeing a measurement.

**This becomes a preregistration when — and only when — all of the following
hold:**

1. The TCA9548A datasheet has been retrieved, hashed, and every constant in
   `csia_bus_provenance/datasheet.py` checked against it, with
   `DATASHEET_STATUS` flipped to `VERIFIED`. It is `NOT_RETRIEVED` today:
   `ti.com` and a mirror both returned `403` at the proxy on 2026-09-15.
2. The parts in §3 are physically present.
3. Owner authorization covering **hardware operation in the sensor-bus
   domain** exists. The current authorization
   (`research/active_evidence/realized_current/OWNER_AUTHORIZATION.md`) is
   **energy-domain, simulator-only**, and explicitly does not permit real
   hardware operation. See §7. The request is written and awaiting a decision:
   `OWNER_AUTHORIZATION_REQUEST.md`.
4. Every `[FILL: …]` is replaced with an observed value.
5. It is committed and the hash recorded **before the first trial**.

Until all five hold, nothing in this file is evidence of anything.

---

## 1. The one question

> When two sensors share an I²C address behind a TCA9548A, under what observed
> rate do the host's own records establish which device produced a given
> reading — and under what rate do they attribute it to the wrong one?

**It is not a hypothesis about any sensor.** No sensor fault is injected. The
devices are assumed healthy throughout, because the defect under study is an
identity defect and a broken sensor would confound it.

## 2. Why this tier exists at all

`research/evidence_semantics/README.md` records three findings, and all three
are one shape: an absence collapsing into a usable value — GNSS `NO_3D_FIX`
indistinguishable from "nothing arrived"; a `−1` battery sentinel served as
`5.00 A`; an all-zero magnetometer triple ingested as a field.

A multiplexer permits a strictly worse member of that family, and the
difference is worth stating precisely. In all three recorded findings the bad
value is *locally* explicable and a careful reader of the wire could catch it.
A misattributed mux reading is a **healthy device reporting a true measurement
of itself, under another device's name**. Nothing in the value is wrong. The
information needed to detect it was never on the bus.

`CANONICAL_STATE_MODEL.md` §3 gives value-provenance three coordinates —
`REAL`, `RETAINED`, `IMPUTED`. None expresses this. The new member is
`MISATTRIBUTED`, and `csia_bus_provenance/provenance.py` is where it lives.

## 3. Parts, and what each is for

None of these is in `hardware/validation_rig/E2_MINIMUM_BOM.csv` today. This
tier adds them; see `BOM_ADDENDUM.csv` beside this file.

| item | qty | purpose | what it does not buy |
|---|---|---|---|
| TCA9548A breakout | 1 | the switch under study | nothing about any sensor |
| Two identical I²C sensors, same fixed address | 2 | the address collision that makes identity non-trivial | nothing about sensor accuracy |
| One sensor at a distinct address | 1 | a control device that no channel selection can confuse | nothing |
| I²C host with a readable bus (SBC or MCU) | 1 | issues selections and readbacks | no timing claim that transfers to flight hardware |
| Logic analyser or scope, ≥2 ch | 1 | an **independent** record of what was on the wire | nothing the host cannot also see |

The logic analyser is not optional and is the reason this tier can produce
evidence at all. Without an independent record, the host's claim about the
register is checked only against the host's other claim about the register, and
the campaign would be self-certifying — the defect recorded as `IV-1`.

## 4. Preregistered conditions

Three selection disciplines, crossed with the fault conditions the harness can
physically create:

| discipline | what the host does |
|---|---|
| `NO_VERIFY` | write the channel register, read the sensor |
| `VERIFY_BEFORE` | write, read the register back, read the sensor |
| `VERIFY_BOTH` | write, read back, read the sensor, read back again |

| condition | how it is created physically |
|---|---|
| `NOMINAL` | nothing |
| `BUS_CONTENTION` | `[FILL: method]` — a competing master or induced NACK |
| `BROWNOUT` | switched supply to the mux only, host unaffected |
| `MULTI_ENABLE` | host writes a two-bit mask deliberately |

## 5. Primary outcome, fixed now

For each (discipline × condition) cell, the **misattribution rate**: the
fraction of reads whose logic-analyser record shows a responder other than the
device the host named.

Adjudication is by the **analyser trace**, not by the host's record. The host's
record is the thing under test and cannot also be the referee.

Secondary, reported always: the distribution of
`csia_bus_provenance` bindings — `VERIFIED`, `ASSUMED`, `AMBIGUOUS`,
`MISATTRIBUTED`, `NO_RESPONDER`, `UNBOUND`.

## 6. Predeclared falsifiers

* **The model is wrong about the part.** If the analyser shows the TCA9548A
  behaving in a way `datasheet.py` does not describe — a write landing
  partially, a readback that does not reflect the switch state — the model is
  corrected and the simulator results built on it are withdrawn, not
  reinterpreted.
* **`VERIFY_BOTH` misattributes anyway.** Then readback is not sufficient, and
  the claim that it establishes identity is withdrawn.
* **`NO_VERIFY` never misattributes.** Then the discipline this package argues
  for costs bus time and buys nothing measurable in this envelope, and that is
  the finding. It would not retroactively justify `ASSUMED` counting as an
  established identity — that is an argument about what is *known*, not about
  what happens to be *true* on one bench.

All three outcomes are accepted in advance.

## 7. Governance — the blocker that is open today

`docs/CURRENT_PROGRAM_STATE.md` §1 lists **HARDWARE — NOT CURRENT GATE**, and
the freeze lifts only when both paper submission-candidate tags exist. The
owner authorization on this branch is scoped to **energy-domain, simulator-only**
work and holds its hardware prohibition structurally: *"no hardware exists in
this environment and no interface to any is imported."*

`csia_bus_provenance` preserves that clause — a test walks its AST and asserts
no module imports `smbus`, `periphery`, `serial`, `spidev`, `board`, `busio` or
any sibling.

**Therefore: this tier may not be run under the authorization that exists.**
Running it needs a separate, explicit owner authorization naming sensor-bus
hardware operation. Writing the model, the simulator and this template does not,
and is what has been done.

That authorization has been **requested**, not assumed:
`OWNER_AUTHORIZATION_REQUEST.md` states what is asked for, what is explicitly
not asked for, and what declining costs. It grants nothing, and the status
there is `AWAITING OWNER DECISION`. Note that permission alone would not start
this tier — the datasheet and the parts are separate open blockers, neither in
the owner's gift.

## 8. What this tier cannot speak to

Nothing electrical — pull-up sizing, bus capacitance, clock stretching, cable
length, channel loading. Those decide whether a wiring works at all and are
invisible to every artifact here.

Nothing about flight, actuators, or any vehicle. No result from this tier may
be cited toward either paper; it is post-freeze research evidence in a domain
the freeze does not cover, and it is quarantined on that basis.

No novelty. An I²C switch is a 2000s-era commodity part and its failure modes
are folklore among people who use them; this tier measures them in one
envelope with a declared method, which is not a contribution to anybody's
literature.
