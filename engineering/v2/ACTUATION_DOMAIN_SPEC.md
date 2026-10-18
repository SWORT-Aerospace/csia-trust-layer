# ACTUATION / PROPULSION DOMAIN — v2 §8

Implementation: `csia/v2/domains/actuation.py`.

Built as the **sixth** domain. §26 permits one "if architecture remains
clean", and this is the one that tests the claim: it spans electrical and
mechanical evidence, it is what §37's motor test stand is built around, and it
needed **no framework change at all**. That last point is the finding.

---

## 1. THE CHAIN

    requested command -> transmitted command -> controller/ESC response
    -> current -> RPM/position -> physical response

Each arrow is a relation, and the value is in **which arrow breaks**:

| relation | adverse signature | candidate |
|---|---|---|
| `actuation.command_path` | requested ≠ transmitted | COMMUNICATION or command path |
| `actuation.electrical_response` | command up, current flat | power path / ESC / wiring |
| `actuation.mechanical_response` | current up, RPM flat | mechanical / load |
| `actuation.physical_response` | RPM up, no physical response | transmission / structure |

## 2. CANDIDATES, NOT CAUSES — §8

> Never uniquely attribute without sufficient evidence.

`ACT_NO_ELECTRICAL_RESPONSE` says "commanded and drawing no current". Whether
that is the ESC, the power path or the wiring is **not decidable from these
signals**, so the record's `dependencies` name the alternatives and the
attribution layer reports them rather than picking one. A test asserts the
alternatives are named.

## 3. WHY "HIGH CURRENT + LOW RPM" IS A SEPARATE RELATION

They point in opposite directions. A motor drawing its expected current and
not turning is mechanically obstructed or has lost its position feedback; a
motor drawing nothing is not being driven. Merging them into one "actuator
unhealthy" would discard the only discriminating information the domain has.

The stall signature requires **both halves**: current at or above a declared
fraction of expected, *and* RPM at or below a declared fraction. Declaring a
stall on low RPM alone would mean a dead ESC reads as a seized motor, and a
test checks that it does not.

## 4. LEVEL FORM, BECAUSE THE DOMAIN IS STATELESS

§8 writes its relations as trends ("command ↑ → RPM ↑"). A stateless domain
cannot difference across ticks, so the relations here are the **level-form**
equivalents: at a declared command level, a declared current and RPM are
expected within declared tolerances.

Below `min_command` every relation reports `NOT_APPLICABLE`: near idle the
expected response is not distinguishable from standing losses, and a domain
that reported a fault there would fire on every idle tick. Where a host does
compute a trend it can supply it as a signal; nothing here fabricates one.

## 5. DECLARATIONS

`ActuatorSpec` carries `full_current_a` and `full_rpm` — the values at command
= 1.0 — plus tolerances, the stall fractions, an overcurrent fraction, an
optional physical channel (`physical_signal` + `full_physical`), and
`depends_on`. They come from a motor/ESC datasheet or a bench
characterisation. **The defaults are the synthetic harness's and are not a
measurement of any hardware.**

## 6. WHAT IS NOT MODELLED

- **A motor model.** No thermal derating, no back-EMF, no torque constant. The
  expectation is linear in command because the host declared two endpoints.
- **Multi-actuator interaction.** Each actuator is judged alone. A quadrotor's
  mixer relationships are not represented.
- **Control performance.** Whether the controller is tracking well is an
  ESTIMATOR/control question (`ESTIMATOR_DOMAIN_SPEC.md`), not this one.
