# Product boundary (Phase 25)

**2026-10-01.**

**Rule:** choose the boundary on demonstrated value, not on the size of the
market or the elegance of the idea.

## 1. The four options against the evidence

| option | what it would be | what the pilot demonstrated for it | what it lacks |
|---|---|---|---|
| **A. Flight Assurance Analyzer** | `analyze` on an operator's own flight logs, after any flight | the command, the report, the manifest, determinism, 66 logs at about 2.8 s each (median) | **any diagnosis on a stock log:** 0 of 68 profile records observed (G1); witnesses need a known onset (G2); a one-motor profile (G3); SITL only (G4) |
| **B. SITL/HIL Validator** | the Analyzer over simulation or HIL campaigns with injected faults and several monitors: per-run diagnosis, independence of the corroboration, refused evidence, coverage, reproducible manifests | **all three NEW ENGINEERING VALUE elements, measured here** (`FALSE_VALUE_SEARCH.md`): <br>- the independent-line count, right in 121/121; <br>- the shared-source warning, in 110/110 fault trials; <br>- invalid-window refusal, which turns 55/55 wrong into 55/55 correct-ambiguous. <br>Also: batch, coverage matrix, byte-stable reports | monitors run continuously rather than from sealed features; one autopilot version; no HIL yet |
| **C. Incident Replay** | one incident log, analysed deeply after the fact | key moments, the WHEN questions, configuration changes in PX4 terms (S1) | everything A lacks, plus a real incident log; the onset is unknown by definition |
| **D. combined** | A + B + C | the parts above | it would be sold on the strength of B and used as A, where it has nothing to say |

## 2. Decision: B, the SITL/HIL Validator

**Why B.**
1. It is the only option where every condition the measured value
   depends on already holds:
   - several real monitors on one event;
   - a known onset;
   - ground truth to check against.
2. Its users want what 2.2 adds over the monitors. A team validating
   monitors asks:
   - "is my corroboration independent?";
   - "did any monitor read outside its validated window?";
   - "what did my campaign not cover?".

   The reports answer all three. Individual monitors answer none.
3. Its inputs are under the user's control. The user can log the topics
   the producers need and record the onset. G1-G3 become the user's
   configuration, not 2.2's unsolved problem.
4. It needs no authority and no onboard code. It stays inside the 2.2
   boundary: offboard, observational, no control authority.

**Why not A now.**
- On a stock log, A today says "no symptom" with "0 of 68 records
  observed". That is honest and useless.
- A is the natural extension once producers that read stock topics exist
  (G1).

**Why not C now.** It inherits A's gaps, and an incident has no known
onset.

**Why not D.** D would be sold on B's evidence and used where A's gaps
apply.

## 3. The boundary, stated

**In scope (B):**
- offline analysis of simulation and HIL runs;
- producers with contracts;
- injected faults with recorded ground truth;
- per-run reports;
- a campaign index and coverage matrix;
- reproduction manifests.

**Out of scope:**
- flight-control authority;
- onboard execution;
- autonomous recovery;
- FORGE;
- fleet analytics and trend scoring;
- maintenance recommendations;
- any claim about a real flight log until G1-G4 are closed.

**The decision is reversible.** Extending to A needs:
- G1-G3;
- one hardware log analysed end to end;
- the external user test.

It needs no change to 2.2's semantics.
