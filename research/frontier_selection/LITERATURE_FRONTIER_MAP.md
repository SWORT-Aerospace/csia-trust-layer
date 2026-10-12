# LITERATURE FRONTIER MAP

What the 36 queries found, organised by how much room is left in each area
rather than by topic. Source ids refer to `PRIMARY_SOURCE_INDEX.csv`.

All 90 sources are `PARTIAL_SOURCE_ONLY`. Read every "saturated" judgement
below as *saturated as far as titles and snippets show* — which is enough to
kill a direction and not enough to license one.

---

## 1. THE SHAPE OF THE FIELD, IN ONE PARAGRAPH

Runtime assurance for autonomous aircraft has three mature layers and one thin
one. The **control layer** is mature: safety filters, Simplex, CBFs, verified
switching logic, an ASTM standard (S001–S012). The **specification layer** is
mature: monitorability theory, stream monitoring, monitoring under partial and
imperfect information, a real eVTOL deployment (S013–S031). The **argument
layer** is mature: conditional safety certificates, dynamic assurance cases,
defeaters, runtime confidence updating, and — as of 2025 — a systematic
extraction of the assumptions those arguments rest on (S032–S042). The thin
layer is the **evidence layer**: what actually arrived at the monitor's input,
where it came from, and whether the pieces are as separate as the argument
above assumed. Everything above the evidence layer takes the evidence layer as
given, in a form the papers state plainly and never revisit.

That is the whole finding of this stage, and it is what candidate B targets.

---

## 2. SATURATED / DEAD AREAS

Do not enter these looking for a dissertation.

| area | why it is closed | sources |
|---|---|---|
| **Monitorability, including its runtime form** | Property-level monitorability is classical; expressive and totally-ordered verdict domains are done (2022, 2024); timed monitorability is done (2025); and the runtime check — deciding online when the monitor can never conclude — appears in a 2025 TOSEM paper | S013–S020 |
| **Monitoring under partial / imperfect / lossy traces** | Abstraction over gaps, optimal monitoring of partial traces, out-of-order streams, epistemic monitors — all present, all sound, all requiring only a supplied loss model | S019–S023, S026 |
| **Diagnosability under loss of observations** | Permanent loss, intermittent loss, dynamic observations, networked delay, plus a survey and a 2025 Bayesian formulation conditioned on the applied inputs | S043–S049 |
| **Open-set / unknown-fault diagnosis** | Named field with named methods; item 26 hard-kills the reduction | S049, S056, S058, S059 |
| **Label-free calibration under shift** | LaSCal, CaDC, label-shift ECE estimators; conformal beyond exchangeability bounds the failure mode | S072–S076 |
| **Conformal perception monitors for control** | Certified degradation detection, conformal state-estimation regions, conformal shielding, fallback-safe MPC — and a paper whose title pre-empts the OOD retreat | S077–S082 |
| **Stealthy attacks on state estimation** | Optimal stealthy FDI, black-box GPS spoofing of UAVs, an AIAA journal treatment of stealthy attacks on UAS, randomness monitors as the counter | S083–S089 |
| **Decentralised fusion under unknown correlation** | Covariance Intersection, Inverse Covariance Intersection, data-incest management, conditional-independence testing for shared information | S060–S063 |
| **Diagnostic ambiguity → control authority** | The textbook answer (fall back to robust control) plus a 2025 quantitative version | S054–S056, S080 |

Nine areas. Eight of the brief's nine required families land in one of them.

---

## 3. THE ACTIVE FRONTIER (2022–2026)

Where the field is currently pushing, from the dated sources:

- **Runtime evaluation of assurance arguments.** ConSerts (2013) → DDI-based
  monitor synthesis (2020) → ACCESS invalidating fragments from sensor ranges
  (2024) → operationalised dynamic safety cases (2025) → subjective-logic
  runtime confidence updating (2026). S032–S037.
- **Assumptions as first-class objects.** CoCo builds calibrated monitors *for
  verification assumptions* (2022); S042 systematises 423 assumptions across
  104 papers (2025). This is the newest and least settled thread.
- **Diagnosability made quantitative and input-conditioned.** S049 (2025).
- **Monitoring moved onto real certified aircraft.** RTLola on a Volocopter
  eVTOL (2024), with active/scheduled monitoring following in 2025.
  S029–S031, S033.
- **Robustness of learned policies to degraded navigation.** S011 (2026)
  names the GNSS-accuracy assumption and attacks it by worst-case bounding.

---

## 4. WHERE THE OPEN ASSUMPTIONS CLUSTER

From `OPEN_ASSUMPTION_LEDGER.csv`: 9 rows are `OPEN_SNIPPET_LEVEL`, 1 is open
but rests on an unread standard, 1 is foundational-and-known, and 11 are
subsumed. The open ones cluster in exactly two places.

### Cluster 1 — the monitor's inputs are assumed sound

- S004: the Simplex architecture "does not address sensors".
- S011: learned policies "assume accurate position and velocity information
  derived from GNSS; an assumption that fails" under multipath, blockage and
  interference.
- S067: the method compares sensors "which do not share component dependency"
  — asserted as a design property, never rechecked.
- S002/S003: the RTA standard's monitor checks behaviour against limits; what
  happens when the limits cannot be evaluated is not visible.

### Cluster 2 — the dependency structure among evidence sources is a design-time constant

- S066 (IEC 61508 via a secondary description): diagnostic coverage is an
  FMEDA-derived constant entering the SIL calculation.
- S069: diverse redundancy's effectiveness is determined by failure
  correlation between channels — treated as a design property.
- S041 (CoCo): assumption monitors are composed; the composition's calibration
  bounds depend on how the constituents relate.
- S060–S063: correlation between fused estimates is handled — for the
  *estimate*, not for a *diagnostic test's power*.

**Both clusters are the same assumption seen from two sides:** that what
reaches the monitor is what the design said would reach it, from where the
design said it would come. That is the assumption candidate B proposes to
measure.

---

## 5. THE BOUNDARY THAT DECIDES CANDIDATE B

The fusion literature (S060–S063) is the strongest attack on candidate B, and
the whole selection turns on one distinction:

| | object repaired | failure mode addressed | what it outputs |
|---|---|---|---|
| Covariance Intersection / ICI | a **fused estimate** | over-confident covariance from double-counted information | a consistent (conservative) estimate |
| Conditional-independence testing in fusion (S063) | a **fusion input set** | unrecognised shared information between inputs | a statistical verdict on shared information |
| Candidate B | a **diagnostic test's power** | a cross-check that cannot detect the fault in the source both channels share | how many distinct upstream sources currently back a verdict |

A consistent fused estimate and a powerless cross-check can coexist: widening
a covariance does not restore a residual's ability to separate hypotheses.
Whether S063 already crosses this line **cannot be determined from a snippet**,
which is why it is flagged as the single most dangerous source for the
selected candidate and why the Stage-0 prompt opens by reading it.

---

## 6. WHAT WAS NOT SEARCHED, AND SHOULD BE

Honest gaps in coverage, to be closed before Stage 0 runs:

- **Aerospace certification literature proper** — ARP4754A/ARP4761 dependency
  and common-cause analysis (CCA/PRA/ZSA/CMA). Common-mode analysis is an
  established aerospace *process*, and it is the most likely place for
  candidate B to already exist under a certification name rather than a
  research one. This was not reachable (paywalled standards) and is the
  largest known hole in this stage.
- **Provenance and lineage in dataflow systems** — data-provenance theory has
  its own literature (why-, where-, how-provenance) that may already supply
  the graph construction candidate B needs.
- **Reliability block diagrams / fault-tree minimal cut sets** — a minimum cut
  in a provenance graph is formally close to a minimal cut set, and fault-tree
  analysis owns that object. If candidate B's κ is just a minimal cut set
  recomputed online, that must be said.

These three are written into the Stage-0 prompt as mandatory prior-art
searches before any code is written.
