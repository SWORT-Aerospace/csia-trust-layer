# Request: owner authorization for sensor-bus hardware operation

**THIS DOCUMENT GRANTS NOTHING.** It is a request addressed to the program
owner, Andres Felipe Pena Avila. Until a decision is recorded, `E2M_STATUS`
stays `NOT_RUN`, `csia_bus_provenance` stays simulator-only, and no hardware
is operated.

It asks for a **narrow exception**, in the same shape as the existing
`research/active_evidence/realized_current/OWNER_AUTHORIZATION.md`: a scoped
permission recorded beside the rule, **not a revision of the rule.**
`docs/CURRENT_PROGRAM_STATE.md` §1 would stand unchanged and unedited, and
would continue to read `HARDWARE — NOT CURRENT GATE` to anybody who opens it.

---

## 1. What is being asked for

Permission to operate a **bench I²C sensor bus** — a TCA9548A multiplexer,
three low-voltage sensors, a host computer, and a logic analyser — in order to
run the campaign preregistered in `E2M_MUX_IDENTITY_PREREG.md`.

Concretely, and this is the whole list:

| # | action | why it needs permission |
|---|---|---|
| 1 | power a TCA9548A breakout and up to three I²C sensors from a bench supply or host USB | hardware operation |
| 2 | write and read the multiplexer's channel register from a host | hardware operation |
| 3 | read sensor registers over I²C | hardware operation |
| 4 | interrupt the multiplexer's supply rail to create the `BROWNOUT` condition | hardware operation, deliberately fault-inducing |
| 5 | attach a logic analyser to SDA/SCL and record traces | hardware operation |
| 6 | import an I²C interface library in code **outside** `csia_bus_provenance` | it would breach the structural clause in §4 |

## 2. What is **not** being asked for

Stated at least as precisely as §1, because the value of a narrow permission
is entirely in its edges.

* **No motor, propeller, ESC or thrust stand.** Those are E4 and are not in
  scope at any point in this request.
* **No battery loading**, no pack under load, no energy-domain hardware. The
  energy-domain work stays simulator-only under its own authorization.
* **No flight controller**, no autopilot, no MAVLink, no serial link to any
  vehicle. This is a bench bus, not E2.
* **No armed vehicle, no HIL actuation, no flight test.**
* **No airframe, no airspace, no site.**
* **No change to the frozen core**, production defaults, deployed authority or
  failsafe behaviour.
* **No actuator authority of any kind.** `csia_bus_provenance` declares
  `HAS_ACTUATOR_AUTHORITY = False` and a test asserts it.
* **No merging, tagging, force-pushing, or opening a pull request.**
* **No paper claim.** Results would be post-freeze, research-only, quarantined
  on the same basis as the energy-domain work.

## 3. Why it is needed, and what it blocks

`csia_bus_provenance` models a defect the repository's own findings imply but
have never observed: a **misattributed reading** — a healthy sensor reporting a
true measurement of itself, under another sensor's name.

`research/evidence_semantics/` records three findings, all of the form *an
absence collapsing into a usable value*. `CANONICAL_STATE_MODEL.md` §3 gives
value-provenance three coordinates — `REAL`, `RETAINED`, `IMPUTED` — and none
expresses a real value from the wrong real producer.

Everything committed so far is a **model**. The simulator shares an author with
the model it tests, so their agreement demonstrates internal consistency and
not correctness — the limitation the repository already states for its five-way
differential. Specifically, these remain unanswered and are unanswerable in
simulation:

1. Does a real TCA9548A behave as `datasheet.py` describes — does a readback
   actually reflect the switch state, and can a write land partially?
2. Under what observed rate does `NO_VERIFY` misattribute on real silicon? If
   the answer is *never*, the discipline this package argues for costs bus time
   and buys nothing measurable, **and that is a result worth having.**
3. Does `VERIFY_BOTH` misattribute anyway? If so, readback is not sufficient
   and the package's central claim is withdrawn.

All three outcomes, including the two that refute the work, are preregistered
as acceptable in `E2M_MUX_IDENTITY_PREREG.md` §6.

## 4. How the prohibition is currently held, and what would change

The existing authorization holds the hardware prohibition **structurally**, not
by promise:

> hardware operation | no hardware exists in this environment and no interface
> to any is imported

That clause is currently enforced by a test that walks every module in
`csia_bus_provenance` and asserts none imports `smbus`, `smbus2`, `periphery`,
`serial`, `spidev`, `RPi`, `board`, `busio`, `adafruit_tca9548a` or `gpiozero`.

**If this request is granted, that test must not simply be deleted.** The
proposed replacement, offered for the owner's approval rather than assumed:

* the AST test stays exactly as it is, so `csia_bus_provenance` remains
  import-clean and provably unable to reach a bus;
* any I²C interface lives in a **separate** module, outside the package, whose
  own test asserts it is imported by nothing except the E2M campaign runner;
* `require_verified_datasheet()` stays a raise, so the gate in §5 cannot be
  bypassed by having permission.

The point is that granting permission should move exactly one boundary, and
leave every other structural guard load-bearing.

## 5. Permission is necessary but **not sufficient**

Granting this does not start experiments. Two independent blockers remain, and
neither is in the owner's gift:

| blocker | status | who clears it |
|---|---|---|
| **TCA9548A datasheet not retrieved.** `ti.com` and a mirror both returned `403` at the proxy on 2026-09-15. Every device constant is unverified general knowledge and `require_verified_datasheet()` raises | **OPEN** | a human with document access |
| **Parts do not exist.** No item in `BOM_ADDENDUM.csv` is in this environment, and none is in `hardware/validation_rig/E2_MINIMUM_BOM.csv` | **OPEN** | whoever purchases |

Stated plainly so that a "yes" is not mistaken for a start date.

## 6. Hazard assessment, honestly

The physical hazard here is **low, and the low hazard is not the interesting
risk.**

Bench I²C at 3.3 V or 5 V, with total current in the tens of milliamps, has no
stored-energy hazard. `E2_BUILD_PACKET.md` §10 identifies props, motors and
ESCs as *"the only stored-energy hazard here"*, and none is present. The
`BROWNOUT` condition interrupts a logic-level supply rail to one small IC.

The risks actually worth the owner's attention are two, and neither is
electrical:

* **Precedent.** This would be the first hardware operation authorized under
  the dual-paper freeze. A narrow exception that is later read as a general
  one is the failure mode, which is why §2 is as long as §1 and why the
  governing rule is left unedited.
* **Scope creep.** A bench bus is one bench-supply and one connector away from
  a flight controller. The abort conditions in
  `E2M_MUX_IDENTITY_PREREG.md` and `E2_BUILD_PACKET.md` §10 apply unchanged,
  including *"a prop, motor or ESC is present on the bench"* as an immediate
  abort.

## 7. What is being asked of the owner

A decision, in any of these forms. **Declining is a complete and legitimate
answer** and the consequence is stated so the cost of "no" is visible rather
than implied.

| decision | consequence |
|---|---|
| **Decline** | `E2M_STATUS` stays `NOT_RUN` permanently or until reconsidered. `csia_bus_provenance` remains a simulator-only model and says so on its face. Nothing already committed becomes wrong; it becomes *unvalidated*, which it already declares itself to be. No work is lost |
| **Defer** until both paper submission-candidate tags exist | the freeze governs as written; this request is simply early. Nothing is lost, and the model is ready when the gate opens |
| **Grant a subset** | e.g. items 1–3 and 5 (read-only bus operation) while withholding item 4 (`BROWNOUT`). The campaign then runs with that condition recorded as `NOT_AUTHORIZED` rather than as a null result |
| **Grant in full** | §1 items 1–6, under §2's exclusions and §4's structural replacement |

## 8. A drafting note the owner should weigh

A draft authorization is **not** included here, and the omission is deliberate.

An authorization drafted by the party who benefits from it is weak evidence of
consent, and this repository already treats paraphrased authorization as no
authorization —`OWNER_AUTHORIZATION.md` reproduces its text verbatim precisely
*"because a paraphrased authorization is not an authorization."*

If the owner grants any part of this, the authorization should be written in
the owner's own words and recorded verbatim, in the manner of the existing
file. §1 and §2 are offered as a **checklist of what such a text needs to
settle** — not as wording to adopt.

## 9. What a granted authorization would still not license

Even in full, it would not authorize a novelty claim, a certification claim, an
airworthiness claim, a production-readiness claim, or any formal-safety claim.

An I²C switch is a commodity part whose failure modes are folklore among people
who use them. E2M would measure them in one envelope with a declared method,
against one bench, with one instrument. That is a measurement, not a
contribution to anybody's literature, and `E2M_MUX_IDENTITY_PREREG.md` §8 says
so in advance.

---

**Status: AWAITING OWNER DECISION. No hardware operated. No permission
assumed.**
