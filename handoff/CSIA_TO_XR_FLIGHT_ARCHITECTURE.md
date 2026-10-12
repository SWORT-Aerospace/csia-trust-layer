# CSIA → XR-1: from a validated evidence core to a mission-product architecture

**Status at this commit.** Every layer below is either *frozen evidence*,
*implemented software*, or *a future role with no code*. The three are never
mixed, and each row says which it is.

---

## The stack

```
    VEHICLE / PAYLOAD                       XR-1, not yet built
        |
    CANONICAL EVIDENCE                      csia/aircraft/, adapters
        |
    FROZEN CSIA CORE                        csia/  --- FROZEN, ZERO DIFF
        |
    INDEPENDENT SUPPORT FIREWALL            csia_assurance/
        |
    CAPABILITY ASSURANCE                    csia_mission.capability   [NEW]
        |
    MISSION PRODUCT ASSURANCE               csia_mission.product      [NEW]
        |
    FUTURE ZETH PLANNER                     gated, not implemented

    FUTURE FORGE      design time     --- forge_seed is a SEED, not Forge
    FUTURE SACA       compute backend --- ComputeEvidence has no SACA dependency
```

Every arrow points down. There is no API by which a product reaches a
capability, or a capability reaches the firewall, or a planner reaches any of
them. **That absence is the mechanism**, not a convention — a future
mission-planning system cannot override evidence semantics because there is no
code path by which it could.

---

## 1. CURRENT FROZEN CSIA CORE

| | |
|---|---|
| paths | `csia/trust_engine`, `csia/diagnosis`, `csia/runtime/online.py`, `csia/runtime/failsafe.py`, `csia/scenarios.py`, `csia/profiles.py` |
| tag | `csia-v1.0-research-final` (**local only** — push refused 403) |
| diff against tag | **EMPTY** |
| state | **E1 — CURRENT-STACK REPEATED SOFTWARE VALIDATION**, frozen |
| freeze manifest | `research/physical_validation/E1_FREEZE_MANIFEST.yaml`, byte-unchanged |

**Nothing in this phase touched it.** No threshold, gate, weight, prior,
signature, hypothesis definition, smoothing constant, freshness rule, failsafe
threshold or support semantic was changed.

## 2. CURRENT SUPPORT FIREWALL

`csia_assurance/` — 5 verdicts, 11 fail-closed reasons, 15 conformance
vectors, 83 tests. Independent of `csia` and verified so in a fresh
interpreter. Emits `EXPERIMENTAL_SUPPORT_CERTIFICATE`.

## 3. NEW CAPABILITY LAYER

`csia_mission.capability` — **implemented software, experimental**.

| | |
|---|---|
| states | `SUPPORTED`, `DEGRADED_SUPPORTED`, `NOT_SUPPORTED`, `NOT_EVALUABLE`, `UNKNOWN` |
| the rule | **`UNKNOWN` is never promoted to `SUPPORTED`** — not by a default, not by an `or`, not by absence of evidence of failure |
| ranking | **no parameter exists.** Structural, not checked: you cannot pass one |
| reason codes | 20, declared; a test asserts nothing outside the vocabulary is emitted |
| certificate | `EXPERIMENTAL_CAPABILITY_SUPPORT_CERTIFICATE`. No expiry means **not valid later**, never "valid forever" |
| contracts | 13, in `csia_mission/xr1_contracts.py` |

## 4. NEW PRODUCT LAYER

`csia_mission.product` — **implemented software, experimental**.

The idea that makes it worth having: **quality properties are qualified
independently.**

> Lose GNSS support and `bridge_rgb_inspection` becomes `PRODUCT_DEGRADED`:
> `imagery_quality` **SUPPORTED**, `relative_geometry` **SUPPORTED**,
> `absolute_geolocation` **NOT_SUPPORTED**.
> Permitted: `visual_damage_assessment`.
> Prohibited: `survey_grade_absolute_measurement`.

The photograph survives. A layer reporting one boolean would have thrown the
imagery away with the geolocation.

## 5. FUTURE FORGE ROLE — design time

**`csia_mission/forge_seed.py` is a SEED, and the name is the scope.** It is a
topological sort with cycle detection that turns contracts plus a vehicle
profile into runtime dependency tables. Deterministic, stable output hash,
independently checked by a second closure algorithm. It fails closed on cycles
and on dependencies nothing provides.

Full Forge — design-time synthesis — is **not implemented and not started**.

## 6. FUTURE SACA ROLE — compute backend

`csia_mission/compute.py` defines a **platform-neutral** `ComputeEvidence`
record. A Linux collector populates availability, deadline, scheduler, memory
and thermal state today.

**`execution_state` and `integrity_state` stay `UNKNOWN`** and are listed in
`NOT_MEASURABLE_HERE`. There is no attestation hardware, so there is no
integrity evidence, and a field reading "OK" would be a fabrication. SACA
could populate more later; **nothing here requires it**.

## 7. FUTURE ZETH ROLE — gated, not implemented

`csia_mission/planner.py` is **two small things**: a gate, and a deterministic
mock to test the gate with.

- `authorize()` has **no `override`, no `force`, no `advisory`** parameter, and
  no way to assert a capability state. The absence is the enforcement.
- `attempt_override()` exists solely so the absence is greppable — it raises
  and explains.
- The mock is a sorted list and an `if`. No search, no optimisation, no model.

**ZETH itself is not implemented.**

## 8. XR PHYSICAL INTERFACE REQUIREMENTS

`hardware/xr1/XR1C_ASSURANCE_ARCHITECTURE_REQUIREMENTS.md` — 16 requirements
in three tiers.

**FIRST_FLIGHT_REQUIRED (6):** known mount datums · separate research/flight
power routes · hardware timing/event header · per-domain power telemetry ·
independent research logger · CSIA shadow with a physically absent command
path.

**LATER_RESERVED (8):** flight-computer cassette · heterogeneous reference-IMU
mount · modular RGB/thermal payload cassette · surface-position sensing ·
reference-sensor spine · fault-injection connector · battery indexing ·
structural-sensor wiring paths.

**OPTIONAL_EXPERIMENTAL (2):** replaceable tip modules · second GNSS antenna
position.

**No dimension is invented.** Each reservation names what must be measured
first. **No CAD was edited.**

## 9. FIRST FLIGHT MINIMUM

`hardware/xr1/XR1_FIRST_FLIGHT_CONFIGURATION.md` — eight items, each producing
evidence F1 needs: flight controller · GNSS · calibrated airspeed · reference
IMU · RGB payload · research logger/CM4 · power telemetry · timing markers.

**CSIA SHADOW ONLY.** No ZETH authority, no active Forge, no SACA, no
deliberate physical fault.

## 10. STAGED EXPANSION

F0 integration → F1 CSIA shadow flight → F2 heterogeneous sensing → F3 benign
fault injection → F4 forge-seed compiled contracts → F5 SACA backend → F6 ZETH
continuation.

**No stage may promote itself.** Each gate is evidence shown to a person,
recorded before the next stage begins. **CSIA remains SHADOW at every stage,
including F6.**

## 11. CURRENT SCIENTIFIC EVIDENCE

**What this phase measured** (all software, all synthetic):

| | |
|---|---|
| disaster-corridor benchmark | **6/6 scenarios matched the declared expectations**; **0 false product certifications**; provenance chains intact |
| bounded verification | **8/8 properties, 813 cases, no counterexample in the bounded domain**, 0 vacuous |
| conformance suite | **9/9 implementations judged correctly** — 7 bad rejected, good passed, name-trap control passed |
| forge-seed | deterministic across repeats and input orders; independent checker agrees |
| reconfiguration | 6 transitions, 2 self-occluding, **and it discriminates** — it does not flag every reduction |
| mission replay | deterministic **given its inputs**, over 5 passes |

**What this phase did NOT measure:** anything on hardware, anything in flight,
anything about a fault, any rate or prevalence, anything about XR-1's
aerodynamics or airworthiness.

**Six findings**, MX-001 … MX-006, in `FAILURE_LEDGER.yaml`. Two were caught by
an expectation table written before the run; one was an expectation of mine
that was wrong and is recorded as corrected with its justification.

## 12. OPEN QUESTIONS

1. **Every XR-1 sensor transform is `UNKNOWN`.** No physical residual analysis
   is possible until mount datums exist and transforms are measured.
2. **The battery envelope is `UNKNOWN` and blocks CAD freeze.** It is the one
   measurement that could be taken today with the part and calipers.
3. **Device-family IMU independence is `NO`.** Recorded, not resolved.
4. **Surface position is not measurable.** `command_echo` is an echo.
5. **The core decision replay reproduces decisions but not values.** The
   categorical divergence is gone (HF-004 closed by HF-018, 0 of 2248 and 0
   of 2242), but ArduPilot puts **zero** decisions within the declared 1e-12
   tolerance, worst 1.80e-05. The mission replay's determinism is still
   conditional on inputs the core replay does not reproduce at that
   tolerance.
6. **No prior-art search has been done** for any mission-layer idea.
7. **E2 has not run.** No hardware.

## 13. PROHIBITED CLAIMS

Not licensed by anything in this phase, and not to be written anywhere:

- that XR-1 exists, flies, glides, or has been tested;
- that any capability or product assurance has been demonstrated **on
  hardware** or **in flight**;
- that any certificate here is certified, certification-grade, or airworthy;
- that the complete pipeline is deterministic — **the core replay diverges**;
- that any mission-layer idea is **novel** —
  `docs/mission/NOVELTY_CLASSIFICATION.md` reads `NOVELTY_NOT_ESTABLISHED` on
  every row;
- that any of this is an **E1 result** — `PAPER_I_SCOPE_GUARD.md`;
- any rate, frequency, prevalence or population probability;
- that the bounded properties are theorems. They are exhaustive enumeration
  over a small declared domain.

---

## Where to start reading

| you want | read |
|---|---|
| the idea | `csia_mission/product.py` docstring |
| what it does under degradation | `research/mission/results/DISASTER_CORRIDOR.json` |
| what could go wrong | `csia_mission/bad_references/` |
| what went wrong here | `FAILURE_LEDGER.yaml`, MX-001…MX-006 |
| what to build | `hardware/xr1/XR1C_ASSURANCE_ARCHITECTURE_REQUIREMENTS.md` |
| what not to claim | `PAPER_I_SCOPE_GUARD.md`, §13 above |
