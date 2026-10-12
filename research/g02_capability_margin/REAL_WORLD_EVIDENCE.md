# Real-world evidence for G02

G02 kill test, 2026-09-28. Source ids `Knnn` are defined in
`research/g02_capability_margin/G02_DEEP_AUDIT.md` §1.

The brief asks for documented incidents where **no single component clearly
failed**, but interacting performance limitations caused or contributed to a
loss of control or an inability to complete a manoeuvre. Priority goes to
electric aircraft, multirotors, rotorcraft, eVTOL and autonomous UAS. The
brief also asks to separate direct evidence from analogy.

## 1. Incidents examined

| incident | what failed | combined performance limitation, no component failure? | direct or analogy | source |
|---|---|---|---|---|
| helicopter hover accidents (density altitude + weight + wind) | nothing failed; OGE hover unavailable even below maximum weight | **yes** | **direct, conventional helicopters** | K044 (gap-search R066) |
| transport-aircraft loss of control | factors "alone or more often in combination" | often | analogy (fixed-wing) | K044 (gap-search R039) |
| AAIB DJI Matrice 210 RTK (2019) | battery reached critical voltage shortly after a low-voltage warning **set below the manufacturer's recommendation**; near free fall | partly: energy/voltage depletion plus configuration; not a four-way composition | direct (multirotor), but a **battery depletion and configuration** case | K040 |
| Joby JAS4-2 (2022) | propeller-blade separation during envelope expansion | **no**: a component failure | not evidence for G02 | K041 |
| Pipistrel Alpha Electro, Norway (2019) | power-controller overheat from low coolant | **no**: a component failure | not evidence for G02 | K042 |
| Aurora PAV | false on-ground rotor-speed reduction from vibration | **no**: logic and sensing | not evidence for G02 | K043 |
| field reports: "throttle saturation and uncontrolled descent"; UK AAIB UAS reports on "power failure" | saturation or power loss in multirotors | possibly; cause attribution not in the summaries | anecdotal (V0 SS) | K045 |
| delivery drones (Wing, Zipline, Matternet, Amazon MK30) | various | **no** case found in the searched sources attributed to combined performance limitation | — | gap-search R062; KQ39 |
| cold-weather voltage-sag operational guidance (industry) | none; guidance only | the physical mechanism is described (sag → more current → more sag) | guidance, not an incident | KQ36 |

## 2. Assessment

- **The best direct evidence remains conventional helicopters.** The
  brief's instruction was: "If the best evidence remains conventional
  helicopters, say so." It does.
- **No electric-rotorcraft, eVTOL or autonomous-UAS incident was identified**
  in the searched sources that is attributed to a composition of
  individually acceptable battery-power, propulsor, wind and mass
  limitations with no component failure.
- The nearest multirotor case (K040) is battery **depletion** with a
  misconfigured warning. It is not a four-way composition.
- **The mechanism itself is physically real and well described:**
  - voltage sag under load, amplified by cold (KQ36, K020);
  - thrust limited by terminal voltage (K001, K002);
  - fielded code protects against it with a sag-limited throttle ceiling
    (K051).

  The fact that ArduPilot implements a current ceiling to prevent sag below
  a minimum voltage is itself evidence that practitioners meet the problem.
  It is also evidence that the basic protection is **already fielded**.
- **Practical value: moderate.** The mechanism is real. Basic protection is
  fielded. Direct incident evidence for the composed case in electric
  aircraft was not found.
