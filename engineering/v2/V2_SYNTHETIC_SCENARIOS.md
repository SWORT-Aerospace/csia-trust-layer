# SYNTHETIC SCENARIOS — v2 §§27, 28, 37

Harness: `csia/v2/scenarios.py` (platform-free).
Data: `csia/v2/profiles/aircraft_scenarios.py`,
`csia/v2/profiles/test_stand_scenarios.py`.
Results: `engineering/v2/V2_SCENARIO_RESULTS.json`.
Assertions: `tests/test_v2_scenarios.py`.

---

## 1. WHAT THESE ARE AND ARE NOT

They are **wiring tests for the assurance logic**, not evidence about any real
machine. Every injected value was chosen to exercise a declared threshold;
none is a measurement, and none supports a claim about how a real regulator
sags or how a real ESC behaves when a motor seizes.

The domain thresholds were **declared in the profile first** and were not
adjusted afterwards to make a scenario come out a particular way.

The one non-synthetic input is the v1.1 payload. The SENSOR domain's evidence
comes from real payloads produced by the frozen v1.1 runtime, because a
synthetic v1.1 payload would make §36's baseline test circular.

## 2. THE INJECTION DISCIPLINE

Each scenario perturbs the smallest set of signals that represents its fault,
and perturbs them **at the source of the fault, never at the conclusion**.

`CPU_OVERLOAD` raises `cpu_load` and lets the runtime, the latency and the
missed deadline follow from it. It does not set `deadline_misses` by hand. A
scenario that wrote down its own expected answer would test nothing.

`POWER_SAG` drops the battery terminal voltage and lets the rails follow,
because they are downstream — that is the declared topology, not an extra
injection.

## 3. DETERMINISM

No RNG anywhere. Every signal is an exact function of the tick index, so a
scenario replays bit-for-bit and a ledger over it is reproducible. Ramps are
linear between declared endpoints from a declared onset.
`tests/test_v2_scenarios.py` runs every scenario twice and compares full
dictionaries.

## 4. §27's EIGHT

| scenario | injected | expectation written before the run |
|---|---|---|
| `POWER_SAG` | battery terminal voltage collapses under unchanged load | POWER limits functions; the BATTERY is the candidate and the rails follow it, so the source is **not** exonerated |
| `REGULATOR_FAILURE` | 5 V rail leaves tolerance, battery untouched | distribution candidate; battery affirmatively nominal and named as exonerated |
| `CPU_OVERLOAD` | CPU load rises; runtime and latency follow | COMPUTE then TIMING; functions with a no-degradation TIMING requirement stop first |
| `PROCESS_STALL` | estimator heartbeat and output age grow | `process_alive` VIOLATED; sensor domain untouched |
| `NETWORK_LATENCY` | telemetry transport and queue delay rise | COMMUNICATION and TIMING degrade; SENSOR stays source-valid |
| `PACKET_LOSS` | GNSS serial loses messages and falls below rate | COMMUNICATION is the candidate; **not** a sensor failure |
| `CLOCK_DRIFT` | validity stamps run ahead of arrival | `TIMING_CLOCK_INCONSISTENT`; no latency published from bad stamps |
| `ACTUATOR_NO_RESPONSE` | commanded and transmitted; current collapses | `ACT_NO_ELECTRICAL_RESPONSE`; ESC, power path and wiring named as inseparable |

## 5. §28's FIVE CROSS-DOMAIN CASES

Several are a §27 scenario looked at through a cross-domain question. Where
that is true the table says so rather than duplicating the injection under a
second name; each carries a `scenario_a`…`scenario_e` tag, and a test asserts
all five tags exist so a case cannot be dropped by deleting its test.

| case | scenario | expected | observed |
|---|---|---|---|
| **A** sensor healthy, network delayed | `NETWORK_LATENCY` | communication/timing degrade, sensor stays source-valid | SENSOR NOMINAL; COMMUNICATION + TIMING adverse; TELEMETRY limited, navigation untouched; no SENSOR candidate |
| **B** battery healthy, 5 V rail failing | `REGULATOR_FAILURE` | power distribution issue, not battery fault | UNIQUE `POWER/rail_5v`; battery in `unsupported`; `POWER_DISTRIBUTION_SUSPECT`; inertial continuation, logging and propulsion stay ELIGIBLE |
| **C** command sent, ESC receives, current rises, RPM does not | `STALLED_ACTUATOR` | actuation/mechanical issue | UNIQUE `ACTUATION/motor_0` with `ACT_STALLED`, **not** `ACT_NO_ELECTRICAL_RESPONSE`; POWER and COMMUNICATION affirmatively NOMINAL |
| **D** sensor fresh, estimator late | `ESTIMATOR_LATE` | compute/timing limitation, not sensor failure | SENSOR NOMINAL; COMPUTE + TIMING adverse; `PRECISION_NAVIGATION` INELIGIBLE, `COARSE_NAVIGATION` ELIGIBLE; no SENSOR or COMMUNICATION candidate |
| **E** shared rail affects several dependants | `SHARED_RAIL` | common power cause **retained as an alternative** | AMBIGUOUS with `common_cause = POWER/rail_5v`; the rail and its dependants all candidates; the rail is **not** adopted as the answer |
| **E** literal: two sensors on one shared node | `SHARED_SOURCE` | same, with two SENSORS | AMBIGUOUS with `common_cause = POWER/battery`; candidates are the source plus `SENSOR/source.battery` and `SENSOR/source.motor_esc`, from a real unedited payload |

### §28-E in its literal form, and how it was found

§28-E says "shared rail fault affects **two sensors**". The `SHARED_RAIL`
scenario runs the real GNSS-fix-loss payload — one adverse source — alongside
two links declared on the same 5 V rail, so its common cause is found under
one source and two links.

That was initially reported as the best available, on the strength of a search
for ticks where two or more sources on one declared node were **unfresh**
together. **That search was too narrow and the conclusion drawn from it was
wrong.** The v1.1 wrapper calls a source adverse when it is unfresh *or* named
in `sequential.alarming`, and searching on the wrapper's own definition finds
**745 ticks** in the real corpus: `battery` and `motor_esc`, both alarming,
both declared on `POWER/battery`, in the POWER_SAG mechanism.

So `SHARED_SOURCE` was added, running §28-E literally:

- the v1.1 payload is **real and unedited**, extracted by
  `engineering/v2/extract_shared_source_payload.py` from the same
  `run_p4d.py:_payloads` that produced the two committed examples
- the only injection is a battery droop past its declared limit; the rails are
  untouched, so the shared node is the only thing both sensors reach
- the result is `AMBIGUOUS` with `common_cause = POWER/battery` and **two
  SENSOR candidates** plus the source itself

It is also the sharpest §36 case in the set. The payload's own
`function_eligibility` is `ELIGIBLE` across all five functions — a sequential
alarm is not a cause attribution (Phase 4 §11) — while v2 calls the same five
`INELIGIBLE` on POWER evidence. Both are true at once, and
`domain_states["SENSOR"]` still reads exactly what v1.1 said. A leak in the
wrapper would show here, because this is the case where the two answers
disagree.

Both scenarios are kept and both are tagged `scenario_e`.

## 6. §37's SIX — THE TEST STAND

Same harness, same domain classes, a machine that does not fly:
`TS_NOMINAL`, `TS_SUPPLY_SAG`, `TS_REGULATOR_FAILURE`, `TS_STALLED`,
`TS_ENCODER_LOSS`, `TS_CPU_OVERLOAD`.

No SENSOR domain is registered, no v1.1 payload is supplied, and no module in
`csia/v2/` was changed to support it. `TS_REGULATOR_FAILURE` reproduces §28-B's
exoneration with no aviation code anywhere in the path.

## 7. HOW THE HARNESS STAYS PLATFORM-FREE

`csia/v2/scenarios.py` originally held `AIRCRAFT_NOMINAL`, and the core
hygiene test in `tests/test_v2_framework.py` failed on it — correctly. A core
that ships one platform's battery voltages has an opinion about what it is
attached to, and §37's question would have been decided in that file rather
than tested.

The nominal tables and injections now live with their profiles. The harness
keeps only what is true of every machine: a scenario is a declared
perturbation of a nominal signal set, timestamps derive from per-channel
offsets, and nothing consults a clock or an RNG.
