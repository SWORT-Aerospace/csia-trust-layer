# Permanent discipline tests (Phase 19)

**2026-10-02.** **Tests:** `tests/test_csia_2_3_stock_bridge.py`. They run
on SYNTHETIC stock logs built in the test file (`synth`), so they need no
raw flight data and run in every suite. They pin the product's logic, not
its accuracy on real flights.

## 1. The five rules and the tests that hold them

| rule | test | what it checks |
|---|---|---|
| NO_COVERAGE is not NOMINAL | `test_no_coverage_is_not_nominal` | a log without `esc_status`: no propulsion output exists; a coverage notice names the compensation producer; the record is not observed; the topic is listed absent; attribution is not justified; no symptom is invented and no motor is called healthy |
| UNAVAILABLE is not NOMINAL | `test_unavailable_is_not_nominal` | battery current -1: source health UNAVAILABLE at every tick; not counted as observed; POWER/path_unavailable is in the diagnosability floor and stays a candidate |
| NOT_APPLICABLE is not NOMINAL | `test_not_applicable_is_not_nominal` | the healthy motors' compensation is NOT_APPLICABLE (no local deficit to test); 2.1.1's PHYSICAL_RESPONSE_NOMINAL and its negation both return None on such a record, so nothing is eliminated by it |
| a FAULTED producer is not a vehicle fault | `test_faulted_producer_is_not_a_vehicle_fault` | a VIOLATED physical-response output with producer health FAULTED is refused by admissibility and raises no symptom; the same output with health VALID raises `COMMAND_NO_RESPONSE|motor_0` |
| UNKNOWN is not HEALTHY | `test_unknown_is_not_healthy` | a nominal hover: no event, no symptom, attribution NO_EVIDENCE, not justified; fewer records observed than expected; the battery current gap is listed; the human summary never calls the vehicle healthy |

**Log gaps follow the same rule.** They are covered by:
- `test_a_log_gap_is_neither_nominal_nor_a_vehicle_fault`;
- `test_logger_dropouts_make_overlapping_outputs_unavailable`.

An output over a gap is UNAVAILABLE as producer health and refused. The
fault under the gap is then NOT localised from it, which is the honest
outcome.

## 2. Finding D-1: 2.1.1 reads the state, not the applicability

**What was found.** While writing the NOT_APPLICABLE test, a direct probe
of 2.1.1's predicates found this:
- A record with observation state NOMINAL and applicability NOT_APPLICABLE
  is read by PHYSICAL_RESPONSE_NOMINAL as True.
- The predicate reads the state field.

**Why the stock producers are not exposed.** They never emit that pair:
- NOT_APPLICABLE outputs carry the NOT_APPLICABLE state;
- missing ones carry UNAVAILABLE.

**The rule, and its test.**
`test_stock_producers_never_emit_nominal_with_a_non_applicable_applicability`
holds it over the motor-loss, telemetry-only and nominal synthetic logs,
for every checkpoint.

**2.1.1 is not changed** (governance). The rule binds every future
producer: a NOMINAL state must mean APPLICABLE.

## 3. The rest of the file

| area | tests |
|---|---|
| the product path (synthetic) | motor loss discovered, localized to the right motor, response_sensor eliminated, mechanical left, attribution not justified; telemetry-only deficit stays context (power gate NOMINAL); nominal hover gives nothing; the known-onset hook gives the same decision; reports are byte-deterministic |
| SB-1 | an RPM-only deficit placed on `actuation.mechanical_response` would make 2.1.1 eliminate ACTUATION/mechanical through STALL_SIGNATURE_FALSE (the reason the telemetry claim is context) |
| events | clustering joins triggers within 3 s only; an in-flight battery warning is a trigger and context, not a diagnosis; the frozen CUSUM reports no coverage on a PX4 log |
| profile and contracts | the quad profile passes its gate with 29 records and is not the historical base; the packaged calibration is the committed research calibration (revision 2); the five stock contracts load with the producer version |
| diagnosability | with SIH stock evidence the never-eliminable explanations on a motor are drive_no_current, command_not_delivered, path_unavailable; the probe does not change the core |
| report | the engineer's questions come first, WHAT HAPPENED? before DETAIL; every propulsion value carries a unit, threshold and window |
| the command line | `analyze V1.ulg` takes the stock path and writes a schema-4 report with a path-free manifest (skips without the raw flight) |

## 4. Why synthetic

**Raw flight logs are not committed.** A test that needs them would skip
on every machine but this one.

**What the synthetic logs are.** They are deterministic hovers at PX4's
default logging intervals, with the effect of a motor loss written in from
the SIH model:
- the command rises by 1/eta;
- RPM follows the effective thrust;
- a rate transient appears on the loss axis.

They test what the product does with such data. Whether real data looks
like this is tested by the XSYS-001 replay (`UNKNOWN_ONSET.md`) and the
validation flights (`VALIDATION_FLIGHTS.md`).
