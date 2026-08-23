# WP-C2 Part 4 — Novelty attack: reading list request

**Status: BLOCKED, again.** Full-text access was retried this session and
refused. `www.sciencedirect.com` returned `EGRESS_BLOCKED`, as did
`arxiv.org`, `inria.hal.science`, `drops.dagstuhl.de` and
`faultdiagnosistoolbox.github.io` in WP-C1. Search snippets work; PDFs do not.

The WP-C1 conclusion stands and is unchanged: **claim novelty nowhere.** What
remains open is the narrower question of whether the composition is *occupied*
or merely *unexplored* — and that cannot be settled from abstracts.

## What to send

Any of: PDFs dropped into `docs/external/reading/`, or pasted text of the
relevant definitions and theorems. Section numbers alone are enough if the
definitions are quoted.

## Per source: the exact question that must be answered

### 1. Carvalho, Moreira, Basilio, Lafortune — *Robust diagnosis of discrete-event systems against permanent loss of observations*, Automatica 49(1), 2013

Closest known result: worst-case diagnosability when an unknown subset of
sensors has failed and the diagnoser is unaware.

**Variable mapping to ours:** their unobservable-event subsets ↔ our absent
channels; their robust diagnosability verification ↔ `Δ_guaranteed` restricted
to the channel mechanism.

**Questions that must be answered:**

1. Does the formulation distinguish **availability** (a sensor is gone) from
   **gating** (a sensor is present but its evidence is conditionally
   suppressed) as two mechanisms over one lattice, or is there only one?
2. Is there any notion corresponding to **endogeneity** — the loss probability
   depending on the fault hypothesis under diagnosis? Specifically, anything
   of the form P(observation lost | fault f) ≠ P(observation lost | nominal)?
3. Is the guarantee a **boolean** diagnosability verdict, or is any graded
   index of partition coarsening defined?
4. Is the sensor-failure set **reachability-constrained** (some failure
   combinations impossible), or is every subset admitted?

**Decision rule:** if (1) and (2) are both YES, the composition is occupied
and we report the match and stop. If (2) is NO, the endogeneity half is open
regardless of the rest.

### 2. Krysander & Frisk — sensor placement for maximum fault isolability (IEEE SMC-A 2008; *Sensor placement for fault isolation in linear differential-algebraic systems*, Automatica 2009); Fault Diagnosis Toolbox

Closest known result: minimal sensor sets achieving an isolability
specification. **Already assessed YES for our Part 3** — the design inverse is
their method and we claim nothing there.

**Questions:**

1. Is isolability computed as a **guarantee over all degraded
   configurations**, or only at the nominal design point with the chosen
   sensor set present?
2. Does the method admit sensors that are **present but conditionally
   uninformative**, as distinct from absent?
3. Does the toolbox expose a worst-case-over-configurations isolability
   query, or only per-model analysis?

**Decision rule:** if (1) is YES, our Part 1 is occupied too.

### 3. Blanke, Kinnaert, Lunze & Staroswiecki — *Diagnosis and Fault-Tolerant Control*, sensor-placement chapter

Closest known result: isolate only to the granularity reconfiguration
requires. **Already assessed PARTIAL/YES for our Part 2 principle.**

**Questions:**

1. Is the response-equivalence partition formalised (an explicit equivalence
   on faults induced by the reconfiguration map), or stated as a design
   principle in prose?
2. If formalised, is it ever **intersected with a degraded-configuration
   guarantee** — i.e. "which reconfiguration-relevant distinctions survive
   sensor loss"?
3. Does anything correspond to distinguishing responses by their
   **parameters** (our `SELECT_IMU(use=imu0)` vs `SELECT_IMU(use=imu1)`)?

**Decision rule:** if (2) is YES, our Part 2 is occupied.

### 4. Hashemniya & Krysander — *Fault Diagnosability Analysis of Multi-Mode Systems*; *Test Selection for Diagnosing Multimode Systems*, DX 2024

Closest known result: residual subsets with "the same diagnosability across
all modes."

**Questions:**

1. Is "across all modes" an intersection over a **reachability-constrained**
   mode set, or over an assumed-full product of mode variables?
2. Do modes there include **sensor availability**, or only plant/actuator
   configuration?
3. Is a graded coarsening index defined, or is diagnosability boolean per mode?
4. Is the mode a function of the **fault** in any case (a fault that forces a
   mode change), which would be the endogeneity structure?

**Decision rule:** if (1) is reachability-constrained AND (2) includes sensor
availability, our Part 1 is fully occupied and we report the match.

### 5. Open sweep — the term to search once access exists

The candidate that would most cleanly pre-empt us, and which snippet search
could not resolve: any work computing diagnosability under **observation
suppression that is itself fault-dependent** — variously "fault-induced
unobservability", "self-masking faults", "diagnosis under fault-correlated
sensor degradation". If this literature exists, it owns the endogeneity result
and not merely the lattice.

## What is NOT in question

- We claim no novelty now and will not claim any regardless of what comes
  back. This exercise determines whether to cite prior work as *the method we
  applied* (current posture) or as *prior work that already did this
  specifically*, which is a stronger and more honest citation.
- The engineering value of the certificate is independent of the answer. It
  identified a free repair that measurably works (WP-C2 Part 2) and an
  unrepairable exposure with a ranked design study (Part 3). None of that
  depends on who invented the machinery.

## Honest statement of the current epistemic position

We have read **zero** full texts on this subject. Every claim in
`research/wp_c1/NOVELTY_ATTACK.md` about what prior work does or does not
cover rests on search-result abstracts and recall, and the bibliographic
details there are unverified and may be wrong. **Absence of a closer match is
weak evidence and should not be reported as a literature review.**
