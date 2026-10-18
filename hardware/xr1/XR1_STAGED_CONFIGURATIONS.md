# Staged flight-research configurations F0 → F6

**NO STAGE MAY PROMOTE ITSELF.** Each gate below is a thing that must be
*shown*, to a person, before the next stage begins. There is no automatic
promotion path and none may be added.

---

## The stages

| stage | what it is | CSIA role | authority |
|---|---|---|---|
| **F0** | integration article. **NO FLIGHT** | shadow, on the bench | none |
| **F1** | minimal CSIA shadow flight | shadow | none |
| **F2** | heterogeneous sensing, thermal, surface/structural instrumentation | shadow | none |
| **F3** | controlled benign physical fault-injection research | shadow | none |
| **F4** | Forge-seed compiled mission-product contracts | shadow | none |
| **F5** | SACA compute backend | shadow | none |
| **F6** | ZETH evidence-bounded mission continuation | shadow + advisory | **still no command authority** |

**CSIA remains SHADOW in every stage listed.** Nothing on this page grants
command authority to anything, at any stage, including F6.

---

## F0 — integration article

**No flight.** The airframe exists, everything is mounted, powered and
talking.

**Gate to F1 — all of these, shown:**
- every declared evidence id in `XR1_DRAFT_PROFILE.yaml` actually produced by
  the actual hardware, at a measured rate;
- **every `UNKNOWN` in `XR1_PAYLOAD_AND_TRANSFORMS.yaml` that F1 depends on
  resolved to `MEASURED`** — mount datums, and the transforms that rest on
  them;
- battery envelope measured, CG computed and within a stated limit;
- `NO_COMMAND_PATH_REACHABLE` verified **physically**: the CSIA link's
  receive wire traced and confirmed unconnected;
- research-domain kill exercised on the bench, flight domain stays up (P4 in
  `XR1_POWER_DOMAINS.md`);
- an F1 preregistration committed, with hypothesis, arms, n, stopping rule
  and captured quantities fixed.

## F1 — minimal CSIA shadow flight

See `XR1_FIRST_FLIGHT_CONFIGURATION.md` for the configuration.

**Gate to F2:**
- F1 flown, evidence archived raw before any reduction;
- the capability and product layers evaluated against **real flight
  evidence** and their behaviour reconciled with the contracts — a
  disagreement is a **result**, and reconciling it is the gate, not passing it;
- CSIA's shadow output compared against the flight computer's own log;
- no in-flight event requiring a control intervention attributable to the
  research payload.

## F2 — heterogeneous sensing and structural instrumentation

Adds: the heterogeneous reference IMU (R8), thermal payload, surface-position
sensing (R10) if adopted, structural sensors.

**Gate to F3:**
- each new sensor's transform `MEASURED`, not `PROVISIONAL`;
- **surface-position sensing working, if F3's fault set includes an
  actuator** — F3 cannot inject an actuator fault it cannot observe;
- the heterogeneous IMU actually a different device family, or
  `XR1_IMU_COMMON_MODE.md` still applies and F3's scope excludes IMU
  common-mode questions;
- a fault-injection protocol written and reviewed **before** any fault.

## F3 — controlled benign physical fault injection

**Benign only.** Interrupting a sensor's data or power line. Not a structural
fault, not a propulsion fault, not anything with a stored-energy hazard.

**Gate to F4:**
- fault injection demonstrated **on the bench** first, with the same harness;
- an abort criterion per fault, written before the flight;
- E3-class evidence produced and archived.

## F4 — Forge-seed compiled contracts

The compiled dependency tables (`csia_mission/forge_seed.py`) drive the
runtime rather than being an artifact beside it.

**Gate to F5:**
- compiled tables and hand-written contracts agree on flight data, not only
  in the independent checker;
- the compiler's output hash recorded in every flight log header;
- a compile failure demonstrated to **stop** a flight, not warn about it.

## F5 — SACA compute backend

SACA populates the richer `ComputeEvidence` fields.

**Gate to F6:**
- **fields SACA cannot answer still read `UNKNOWN`.** A richer backend that
  fills every field is a backend that is guessing;
- compute evidence shown to change a product qualification — otherwise the
  backend is decorative;
- the Linux provider still works, so the platform-neutrality claim survives.

## F6 — ZETH evidence-bounded mission continuation

A planner that chooses among benign branches within the supported capability
set.

**Gate: none. F6 is the last stage on this page.**

**What F6 still does not have:**
- command authority. The planner proposes; it does not actuate;
- the ability to override a support state. `csia_mission/planner.py` has no
  override, and BAD_PRODUCT_06 exists to keep it that way;
- anything to do with weapons, counter-UAS, evasion, or autonomous targeting.
  Out of scope for this programme entirely.

---

## The promotion rule

> **No stage may automatically promote itself. Each requires an explicit
> evidence gate, evaluated by a person, recorded before the next stage
> begins.**

A gate is not passed by the absence of a failure. It is passed by the presence
of the evidence listed, which is a different thing and the distinction this
whole programme is about.

## What is deliberately absent from every stage

Full Forge. SACA before F5. ZETH before F6. Flight authority at any stage. A
new autopilot. A new flight controller beyond the cassette question in
`XR_FC_MODULARITY_REQUIREMENT.md`.
