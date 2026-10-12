# POWER INTEGRITY DOMAIN — v2 §4

Implementation: `csia/v2/domains/power.py`. Tests: `tests/test_v2_domains.py`.

> No novel algorithm required. (§4)

Nothing here is novel and nothing is claimed to be. P = V·I is Joule's law, a
regulator tolerance band comes off a datasheet, and droop under load is Ohm's
law across an internal resistance. The engineering content is **which
comparison is made, what is declared rather than inferred, and what the result
is allowed to conclude**.

---

## 1. THE RELATION THAT IS ACTUALLY WORTH SOMETHING — §28 SCENARIO B

> battery healthy + 5 V rail failing → downstream regulator/distribution
> suspicion, **not** battery fault

"POWER: FAULT" tells an operator nothing they can act on. The distinction
between "the battery is failing" and "the battery is fine and the thing
between it and your sensors is failing" is the whole value, and it is
available for free from telemetry most platforms already have — provided two
things:

1. the **source is monitored separately from the rails it feeds**, and
2. a healthy source emits an **affirmative** NOMINAL record rather than
   staying silent. Silence cannot exonerate anything.

`power.source_health` therefore emits on every good tick. When a rail is
adverse and the source is affirmatively healthy, the rail's record gains
`POWER_DISTRIBUTION_SUSPECT` and `detail.source_exonerated`, and the battery
appears in the attribution's `unsupported` list — named by the relation,
carrying no evidence of its own.

The exoneration is **conditional**, and a test checks the negative case: when
the source itself is drooping, the rail gets no distribution finding. A rule
that always fires is not a finding.

## 2. RELATIONS

| relation | needs | verdict |
|---|---|---|
| `power.source_health` | voltage, current | UNAVAILABLE if either absent, else NOMINAL |
| `power.p_equals_vi` | + an independent `power_w` | DEGRADED beyond declared tolerance |
| `power.droop_vs_current` | + `esr_ohm`, `voltage_reference_v`, limits | DEGRADED / VIOLATED on excess sag |
| `power.cell_balance` | `cell_voltages` + declared spread limits | DEGRADED / VIOLATED |
| `power.rail_tolerance` | rail voltage + declared band | DEGRADED / VIOLATED |
| `power.load_current_response` | declared `LoadSpec` | DEGRADED when current is far below demand |

Where a declared input is absent the relation is **not evaluated** and appears
in `unevaluated` with the reason. It does not fall back to a default and it
does not quietly pass.

## 3. WHAT IS CONFIGURATION AND WHAT IS PHYSICS

Every threshold is host-declared on `RailSpec` / `BatterySpec` / `LoadSpec`.
The defaults are the synthetic harness's, chosen as ordinary electronics
practice — a 5 V regulator specified to ±5%, a 2% warning band inside it — and
they are **not derived from any hardware measurement**, because no hardware
has been measured. A deployment states its own from its own datasheets.

## 4. STATELESSNESS AND THE DROOP REFERENCE

Open-circuit voltage varies with state of charge, so a fixed constant would be
wrong for a discharging pack. The domain is stateless by contract, so it
cannot filter its own reference either.

The host supplies `voltage_reference_v` as a **signal** — a slow no-load
estimate it is already computing. Expected terminal voltage is
`V_ref − I·ESR`; the residual is the excess sag. When the reference or the ESR
is not declared, the relation is not evaluated. That keeps the filtering where
the host already does it and keeps the domain replayable.

## 5. THE LOAD RELATION IS ONE-SIDED, DELIBERATELY

Current far **below** the declared expectation at a given demand is a
power-path finding. Current **above** it is an actuation or mechanical
finding (§8), and claiming it here would count one event against the wrong
domain. Below a declared `min_demand_frac` the relation reports
`NOT_APPLICABLE`: near zero demand the expected current is inside the noise of
any shunt.

The full command → current → motion chain belongs to ACTUATION. What POWER can
say alone is narrower, and is kept narrower.

## 6. PER-RAIL FUNCTION SCOPING

`RailSpec.affected_functions` says what each rail feeds. The aircraft profile
declares 5 V carrying the GNSS receiver and telemetry radio, and 3V3 carrying
the inertial set, magnetometer and barometer; the battery feeds everything.

The first version attached every rail to every function, and on a 5 V
regulator failure reported total loss of a vehicle that could still navigate
inertially, log, and fly home. That was corrected, and
`tests/test_v2_scenarios.py::test_scenario_b_does_not_report_the_whole_vehicle_as_lost`
now holds it in place.

## 7. WHAT IS NOT MODELLED

- **State of charge / remaining endurance.** Nothing here estimates it, and a
  fuel gauge is a different product with different failure modes.
- **Cell chemistry.** The spread limits are declared, not inferred from a
  chemistry model.
- **Transient response.** Every relation is evaluated per snapshot; inrush,
  ripple and sag *duration* would need state the contract forbids.
- **The regulator itself as a component.** A failing rail implicates "the
  regulator/distribution path" as a phrase, not as a monitored component,
  because the platform reports no telemetry from it. A component that emitted
  no telemetry of its own would enter attribution as a candidate on nothing
  but our say-so.
