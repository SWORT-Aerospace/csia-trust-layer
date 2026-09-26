# Cross-system architecture seed — extending v2, not replacing it

**Status: PROPOSED.** This document proposes research directions on top of an
architecture that **already exists**. It does not claim any proposed capability
exists. Written under `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`. Base
commit `e7594e4`.

**Position.** CSIA v2 Phase C is the cross-system assurance foundation. It is
frozen at `50c5d35` with the verdict `CROSS_DOMAIN_ASSURANCE_FUNCTIONAL`
(`engineering/v2/V2_PHASEC_FREEZE.md`). There is **no** parallel L1/L2 hierarchy
here. The research question is:

> How can temporal evidence and physical cross-domain witnesses extend the
> resolving power of the architecture that already exists?

---

## 1. The proposed L0–L3 hierarchy, mapped onto what exists

| layer (owner's sketch) | what already exists | status |
|---|---|---|
| **L0** local evidence | `EvidenceRecord` (`csia/v2/evidence.py`): `measured_value`, `expected_value`, `expected_relation`, `residual`, three timestamps (`timestamp_validity`, `timestamp_arrival`, `timestamp_processed`), and a **`sequential_state`** slot. v1's per-edge λ is the sensor-domain equivalent | CURRENT VALIDATED. **`sequential_state` is never assigned** anywhere in `csia/v2/` |
| **L1** subsystem evidence | `AssuranceDomain` plugins (`csia/v2/domain.py`): POWER, ACTUATION, NAVIGATION, COMPUTE, COMMUNICATION, TIMING (`csia/v2/domains/`) | CURRENT VALIDATED, frozen. **PERCEPTION** does not exist. ESTIMATOR, THERMAL and the energy domain are named in `DOMAIN_IDS` but **forbidden** by the freeze |
| **L2** cross-system reasoning | the cross-domain signature matrix (`csia/v2/signatures.py`); localization by three-valued set elimination (`csia/v2/localization.py`); attribution UNIQUE / AMBIGUOUS / UNSUPPORTED / NO_EVIDENCE with common-cause retention (`csia/v2/attribution.py`); the function graph, "which functions are still justified … and what domain is limiting them" (`csia/v2/functions.py`) | CURRENT VALIDATED, frozen |
| **L3** FORGE / action | the v1 failsafe is the only policy that recommends actions (`csia/runtime/failsafe.py`). FORGE is documentation only: `forge/` holds two Markdown files and no code, which a test asserts | FORGE production code **forbidden** |

Two pieces sit outside that mapping and must not be confused with it.

- **`SupportCertificate`** (`csia_assurance/witness.py`) is an **EXPERIMENTAL**
  firewall-layer certificate: "the leader was separated from EVERY competitor
  … by at least one ACTIVE discriminator". It is **not part of v2**: `csia/v2/`
  never imports it, and it is built only in its own tests. For v2 the
  justified-decision endpoint is a localization verdict of `SUPPORTED`.
- **v1** (`csia/runtime/online.py`) is a temporal, Bayesian, cross-**sensor**
  layer with eight hypotheses. It and v2 are **not bridged**.

---

## 2. What v2 does not do — the gaps this research addresses (UNPROVEN)

| gap | evidence | why it matters |
|---|---|---|
| **G1 v2 is atemporal** | "Nothing here reads time order" (`csia/v2/localization.py`); the only cross-tick state is the ledger, which records changes and accumulates no evidence (`csia/v2/ledger.py`) | isolation and certification latency are **undefined** for cross-domain reasoning today |
| **G2 no physical witness for actuation on a multirotor** | Set B: all five causes AMBIGUOUS, "no independent physical channel on the shaft" (`engineering/v2/MATCHED_SCENARIOS.md`) | the candidate set has a floor of two that only the test stand's torque channel breaks |
| **G3 no bridge from v1's temporal evidence into v2** | `sequential_state` unused; no adapter from v1 output into an `EvidenceRecord` | the only temporal accumulation in the codebase cannot inform cross-domain reasoning |
| **G4 profile-level dependency blindness** | Set C: dependency predicates return "not measurable" for COMMUNICATION, COMPUTE and TIMING | recorded there as a **profile** change, not a framework change |

---

## 3. Proposed extensions (PROPOSED)

Every extension lives **outside** `csia/` and `csia/v2/`, reads their outputs,
and changes no frozen behaviour, threshold or certificate semantics.

### E1 — physical cross-domain witnesses

New **predicates** — evidence, not reasoning — whose inputs come from a
different domain than the hypothesis they test. The first is dynamics evidence
for actuation hypotheses: allocation achievement, command asymmetry and
dynamics transients (`docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md` §6).

- **Constraint.** Each is three-valued, with "not measurable" eliminating
  nothing, and localization's rule is unchanged: `SUPPORTED` only for the last
  candidate standing **and** affirmatively confirmed.
- **Test.** Does the Set B floor of two fall to one, correctly?

### E2 — temporal resolution of predicates

A predicate is not decidable at the instant of onset. Evidence has to
accumulate first. The proposal is to evaluate v2's localization **per
snapshot, over time**, and to record the times its candidate set shrinks.

- **v2 isolation time** is the first snapshot with a single survivor.
- **v2 certification time** is the first snapshot with a `SUPPORTED` verdict.

**Constraint carried from v2's own rules.** "Do not emit CAUSE = X merely
because X changed first" (`csia/v2/localization.py`, §2). Time may be used to
**accumulate** evidence for a predicate. It must never be used to **order**
causes. A witness that fires first is not thereby the cause.

### E3 — local evidence producers, as timestamps rather than beliefs

A sequential detector may fill `sequential_state` and supply **t2**, a
suspicion timestamp.

- **Constraint, from HISTORICAL / SEALED Phase 5.** A λ-based fast path wired
  into the belief update lost threshold robustness (H5 killed) and added false
  alarms (`research/phase5/PHASE5_RESULTS.md`). So a producer may **report**;
  it may not **update belief** without re-running that question, and that is
  not proposed.

### E4 — a read-only v1 → v2 bridge

An adapter that turns frozen v1 output into SENSOR-domain `EvidenceRecord`s,
so v1's temporal accumulation can inform v2 predicates.

- **Constraint.** It reads v1's emitted states only; `csia/runtime/` is not
  modified and does not import it.
- **Open question.** Whether v1's trust scalar can serve as an
  `observation_state` at all without inventing semantics. That has to be
  argued before it is built.

---

## 4. Constraints carried from sealed evidence

These are not preferences. Each is a result this repository already holds.

| constraint | source |
|---|---|
| resolving power is a property of the **instrumentation**, not the algorithm | Set B, multirotor against bench (`engineering/v2/MATCHED_SCENARIOS.md`) |
| a confident answer produced from an **absence** is a defect | Set C's first version, which read "no dependency recorded" as "independent" |
| ambiguity is a valid, reportable output | `csia/v2/attribution.py` §29; Phase 2's `NON_IDENTIFIABLE` |
| robustness came from the trust recursion, not the dwell | Phase 5 H5 |
| a fast path changes **when** a response is issued, not **whether** it is right | Phase 5 finding 3: action-conflict rate identical |
| cross-sensor evidence already recovers attribution that a frozen map discarded | Phase 5 H3: Doppler edges under ESC-absent conditions, p = 1.8e-12 |

---

## 5. Where the owner's original sketch conflicted with the repository

Recorded so that the change of plan is traceable.

| original assumption | repository evidence | resolution |
|---|---|---|
| cross-system assurance must be built | it exists in v2 Phase C | build on v2 (owner decision 1) |
| L0 as fast CUSUM-style local detection feeding CSIA | Phase 5 measured the costs | producers report t2; they do not update belief (E3) |
| a battery → ESC → motor → dynamics chain can be tested on the existing simulator | faults never modify truth; the bench simulator is open-loop (`csia/sensors/truth.py`, `csia/sensors/motor.py`) | SITL, starting with the smaller Set-B-plus-dynamics question (owner decision 4) |
| battery, ESC and motor degradation are separate hypotheses | v1 has **one** `power_fault` hypothesis; `power_sag` scored on `motor_esc` reads as incorrect isolation | ground truth for propagating faults must be the **root cause**, not the affected sensor |
| `SupportCertificate` is part of v2 | it is a separate EXPERIMENTAL firewall layer | corrected here |

---

## 6. What would change this plan

- **G1 or G2 of the SITL gating read fails** (`docs/research/SITL_FEASIBILITY_MATRIX.md`
  §4): no motor injection, or an RPM channel that echoes the command. The first
  experiment then narrows or stops.
- **E1's witnesses do not separate A from B** (falsifier F1). Then dynamics do
  not provide the missing channel on this platform, and Set B's floor of two
  stands, now with stronger evidence.
- **The observability window closes under compensation** (F3). Then physical
  witnesses exist but arrive too late to help, which is a latency result in
  its own right.
