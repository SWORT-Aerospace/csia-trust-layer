# CSIA PRIME-1: final freeze

**NO NEW PRODUCT DEVELOPMENT ON THIS FROZEN REFERENCE.**

**Freeze tag:** `csia-prime1-freeze` (annotated). It points to the commit
that carries this file; the tag annotation records that commit and its tree.

**Decision:** CSIA_PRIME1_READY_FOR_EXTERNAL_PILOT.

| gate | state |
|---|---|
| P1 KNOWN_DEFECTS_CLOSED | MET |
| P2 EVENT_DISCOVERY_COMMERCIALLY_USABLE | MET, SIMULATION ONLY |
| P3 EXTERNAL_PILOT_PACKAGE_READY | MET |
| P4 REAL_DATA_READY | MET (processing only, not correctness on real faults) |
| P5 PHYSICAL_VALIDATION | **NOT MET** |

## 1. What is frozen

This exact software, wheel, claim set, support matrix, test state and
validation boundary is PRIME-1. Every hash is in
`PRIME1_FREEZE_MANIFEST.json`.

| element | identity |
|---|---|
| product | CSIA Flight Assurance, release `prime1` (`csia-assure`) |
| code | `csia_evidence_assurance`, `csia_semantic_core` and `csia` at the tag: git trees and the code digest in the manifest |
| wheel | `release/csia_trust_layer-0.8.0-py3-none-any.whl`, the exact wheel inside the participant bundle; SHA-256 in the manifest |
| versions | analyzer 2.2.1; Semantic Core 2.1.1; profile multirotor-quad r1; event discovery prime1; telemetry producer csia-prime1-stock-tel-r1; view prime1-view-2; support contract prime1-r1 |
| claim set | `research/csia_prime1/CLAIM_EVIDENCE_MATRIX_PRIME1.md`, `PUBLIC_CLAIMS.md` |
| support matrix | `csia_evidence_assurance/support_contract_prime1.json` (rendered: `research/csia_prime1/SUPPORT_MATRIX.md`) |
| decision | `research/csia_prime1/PRIME1_REVIEW_AND_DECISION.md`, `FINAL_STATE_PRIME1.json` |
| test state | TEST_STATE |
| freeze-time verification | `verification/` (re-measured at the freeze; PRIME-1's own records are unchanged) |

**Why:** the decision was accepted. Results from future real data must be
comparable with one exact, reproducible reference.

## 2. What it can do

**Form:**
- OFFBOARD;
- a services-assisted pilot;
- PX4-focused;
- local, reproducible analysis.

**Intended use:**
- analysis of SITL and HIL logs;
- engineering validation;
- evidence-quality review of flight-test logs;
- incident replay and assurance analysis.

It states:
- what the evidence in a PX4 ULog justifies, and what it does not;
- which evidence it refused, and why;
- which sources are shared;
- what the log could not observe.

It refuses to interpret vehicles outside its support matrix.

## 3. What it can NOT claim

- **Any onboard authority, autonomous recovery or FORGE integration.**
  ZERO CONTROL authority.
- **Airworthiness or certification.**
- **Real physical fault attribution.** Every diagnostic result is validated
  in PX4 simulation only. No real propulsion fault has been analysed against
  independent truth.
- **General aircraft or generic PX4 compatibility.** Quad X only, with full
  analysis tested on one PX4 version (547e2ca).
- **A real-flight alert rate.** The event-discovery numbers come from 0.298
  nominal SITL hours.

## 4. How to verify the freeze

```
git cat-file -p csia-prime1-freeze                                         # the annotation
git checkout csia-prime1-freeze
.venv/bin/python research/csia_prime1_freeze/verify_prime1_freeze.py check  # seconds; writes nothing
```

**`check` confirms:**
- every frozen file's SHA-256, the product code digests and git trees;
- the exact wheel;
- the decision and gates as recorded;
- that the tag is annotated, carries this manifest and is on the remote
  branch.

**The measurements behind the manifest can be re-run** (they need the raw
data on the original analysis machine):
- `research/csia_prime1/verify_prime1_baseline.py --final`;
- `historical_gate.py`;
- `fresh_install_prime1.py`;
- `build_pilot_bundle_prime1.py --out <scratch>`;
- the full `pytest` suite.

**Custody:** the participant bundle zip (12 blinded logs, 98 MB) and its
experimenter answer key are outside git, by design. Their hashes are in the
manifest; the wheel is preserved here. Archiving the zip and the key
off-machine is an owner action.

## 5. When development may resume

PRIME-1 engineering may resume only if one of the following occurs:

- **A.** real external pilot data exposes a concrete defect;
- **B.** physical or HIL testing exposes a concrete defect;
- **C.** a security, reproducibility or package defect affects the frozen
  release;
- **D.** a supported dependency breaks the release.

**Even then, PRIME-1 remains frozen.** Any behavioural change becomes a
separately versioned successor, branched from the tag. The frozen baseline is
never mutated. The branch `claude/csia-prime-pilot` is kept, and its history
is not rewritten.

## 6. PRIME-2

**CSIA_PRIME2_WAITING_FOR_REAL_PILOT_DATA.** This is not a PRIME-1 failure.
The pilot infrastructure is ready; a qualifying external dataset is absent
(`research/csia_prime2/PILOT_DATA_REQUEST.md`). No synthetic substitute is
authorised.

## 7. Publication boundary

- **Paper I predates PRIME-1** and evaluates a distinct frozen diagnostic
  implementation. PRIME-1 must not be inserted retroactively into Paper I's
  experimental results.
- **Paper II may cite later CSIA development** only where relevant and only
  where the underlying experiment or artifact supports it.
- **No paper was modified during this freeze.**
