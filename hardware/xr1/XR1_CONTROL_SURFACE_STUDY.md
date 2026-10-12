# Control-surface architecture study — 2 elevons vs 4 independent zones

**NO CAD IS EDITED BY THIS DOCUMENT.** It is a comparison and a
recommendation.

**THE RECOMMENDATION IS NOT BASED ON APPEARANCE.** Four zones look more
capable. That is not a reason and does not appear below.

---

## Recommendation

# `RESERVE_4`

Build F1 with **two primary elevons**. Reserve the structure, hinge line and
wiring for four independently actuated zones, and adopt them only when a
research question requires them.

---

## Why, in one paragraph

Four zones buy **control-allocation redundancy** and **surface-effectiveness
identification** — both genuinely valuable, and both are **F2/F3 research
questions, not F1 ones**. F1's purpose is a CSIA shadow flight producing
usable evidence; it does not exercise control allocation and cannot identify
surface effectiveness, because **XR-1 has no surface-position sensing**
(`XR1_ACTUATOR_EVIDENCE.md`). Adopting four zones now doubles the servo count,
the wiring and the failure modes to buy capability that F1 cannot use and
cannot measure. Reserving them costs a hinge line and routing decided at design
time, and costs an airframe if deferred past it.

---

## The comparison

| dimension | 2 primary elevons | 4 independent zones |
|---|---|---|
| **research value** | sufficient for F1: fly, log, run CSIA in shadow | higher **at F2/F3** — allocation experiments, per-zone effectiveness, per-zone fault injection |
| **control allocation** | none. Two surfaces, two axes, one solution | a genuine allocation problem: redundant surfaces, a real research subject |
| **single-actuator degradation** | one servo lost ≈ that axis compromised. Little to reallocate to | remaining zones may cover part of the lost authority — the **most valuable** property, and the one that needs allocation software XR does not have |
| **surface-effectiveness identification** | not separable — two surfaces, coupled | separable in principle. **Needs measured surface position, which XR does not have** |
| **mass** | 2 main servos. Reservation `[35, 20, 35] mm`, 40 g each — **PROVISIONAL, part unresolved** | 2 main + 2 outer (KST X08H, 8 g each, GIVEN). Plus linkages, horns, wiring. **A total cannot be computed: the main servo is not selected** |
| **drag** | one hinge line, fewer gaps | more gaps and seams. **Magnitude unknown — no aerodynamic model exists** |
| **wiring** | 2 signal + power runs | 4 runs, longer, further outboard |
| **servo count** | 2 (unresolved) | 4 (2 unresolved + 2 KST X08H) |
| **failure modes** | fewer actuators, less to go wrong. A single failure is more consequential | more actuators, more to go wrong. A single failure is less consequential **if allocation software exists** |
| **hinge moments** | **NOT COMPUTED.** This is why the main servo is unresolved | **NOT COMPUTED.** Smaller surfaces mean lower per-surface moment, but the split is not decided |
| **manufacturing complexity** | one hinge line per side | two per side, plus a structural break, plus sealing |

## The argument that decides it

**A four-zone architecture's value is realised by software XR-1 does not
have.** Degradation coverage needs a control allocator that reallocates when a
zone is lost; effectiveness identification needs measured surface position.
Neither exists, both are F2/F3 work, and building the hardware first means
carrying four servos through F1 to buy nothing F1 can use.

**But the structural decision is not reversible after F1.** A hinge line, a
structural break and outboard wiring are design-time choices. Retrofitting
them means a new wing.

`RESERVE_4` is the only option that keeps both properties: F1 flies the
simpler article, and the four-zone experiment stays available.

## What `RESERVE_4` means concretely

1. Hinge line positioned so it **can** be split into inboard and outboard
   segments.
2. Structural provision at the split — no local reinforcement added later.
3. Wiring routed outboard to the reserved positions, **not fitted**.
4. Servo pockets reserved at the outer positions, sized for the KST X08H
   (23.5 × 8 × 16.8 mm, GIVEN) — the one part in this study whose dimensions
   are known.
5. F1 flies **two** primary elevons. The outer positions are faired over.

## What must be measured before this can become geometry

- **Hinge moments**, powered and unpowered, across the envelope. Nothing
  in this repository has computed them, and they determine the main servo —
  which is why it is `UNRESOLVED`.
- **Main servo selection**, which follows from the above.
- **The aerodynamic envelope**, which does not exist.
- **Battery envelope** — because the CG interacts with where servos and
  wiring add mass, and the battery dominates the CG.

## The condition that would change the recommendation to `ADOPT_4_LATER`

If a control-allocation research programme is committed to **and** surface
position sensing (R10) is adopted, four zones become the article that
programme needs, and the decision moves from reservation to adoption. That is
an F2/F3 decision made with F1 data in hand — not one to make now.

## The conditions that would make it `DO_NOT_PURSUE`

- Hinge-moment analysis shows the split surfaces need servos that do not fit
  the reserved pockets.
- The mass of four actuators plus wiring is unacceptable against an endurance
  requirement — **which does not yet exist**.

Neither can be evaluated today. Both are recorded so the reservation can be
dropped on evidence rather than forgotten.
