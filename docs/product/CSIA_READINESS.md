# CSIA READINESS — WHAT THE FROZEN VERSION IS AND IS NOT READY FOR

**Product maturity: M2 — cross-platform simulation validated. Unchanged.**

This is the honest answer to "is it product ready?". It is ready for some
things, not ready for others, and the boundary is sharp. Every ready claim
below was **exercised this session** rather than asserted; the command that
demonstrates each is named.

**SIMULATION / RESEARCH PROTOTYPE — NOT FLIGHT SOFTWARE.** That line is in the
package's own `csia info` output and it is not a disclaimer to be negotiated
away.

---

## 1. Start here

```
python engineering/v2/quickstart.py
```

Runs from anywhere with the package installed — no repository checkout, no
data directory. Six steps, **each asserting its own result**, so if the
narrative and the behaviour ever diverge it exits non-zero instead of printing
a comforting story. `tests/test_quickstart.py` runs it in CI.

**Read step 1 before anything else.** The obvious first program returns
functions in `UNKNOWN` and a newcomer concludes the library is broken. It is
not: on the aircraft profile the SENSOR domain is the v1.1 wrapper, and with
no v1.1 payload supplied it has no evidence. Absence of evidence is reported
as `UNKNOWN`, never as health.

## 2. What is ready, and what shows it

| ready | evidence |
|---|---|
| **The reasoning layer does what it says.** Symptoms reduce to a supported hypothesis, every elimination names the predicate that did it, and no cause is asserted without a discriminating measurement | quickstart step 3; `LOCALIZATION_RESULTS.csv`; §42 gate `CROSS_DOMAIN_ASSURANCE_FUNCTIONAL` |
| **It refuses to guess.** Where two hypotheses are supported by the same observation and the platform cannot separate them, it returns `AMBIGUOUS` rather than picking one | quickstart step 4; matched set B, 5 members, 0 reach SUPPORTED |
| **Absence of evidence never reads as health.** A silent or crashed domain makes the functions that need it `UNKNOWN`, and the loss is surgical — exactly those functions, not the rest | quickstart steps 1 and 5; `PLUGIN_FAILURE_RESULTS.csv`, 12 injections, 0 healthy claims from a failed domain |
| **A crashed plugin does not crash the engine.** `FAILED`, with the error recorded, while the other five keep reporting | quickstart step 5 |
| **The per-tick document replays bit-for-bit.** No clock, no RNG, no cross-tick state on the decision path; wall-clock figures are kept out of the ledger deliberately | `tests/test_v2_localization.py`; ledger chain verifies on all 19 matched scenarios |
| **The v1.1 verdict is transcribed, never recomputed.** The wrapper imports no v1.1 producer and structurally cannot alter a v1.1 conclusion | `tests/test_v2_framework.py`; import-graph test |
| **Two interfaces, one semantics.** 13,500 payloads across 9 mechanisms, 0 mismatches on the full per-tick document | `INTERNAL_EXTERNAL_EQUIVALENCE.json` |
| **It is not aircraft-specific.** Two of three profiles run in a fresh interpreter with neither `csia.v1_1` nor the aircraft profile ever imported | `tests/test_v2_localization.py` genericity tests |
| **The frozen core is genuinely frozen.** Zero diff against `csia-v1.0-research-final`, checked two ways every run | `tests/test_v1_frozen.py` |
| **It installs and runs as a package.** `csia info`, the v1.1 output schema and the whole v2 surface work from outside the repository | verified from a scratch directory this session |

## 3. What is NOT ready, and none of it is close

| not ready | why |
|---|---|
| **Flight software** | It is a simulation/research prototype. No DO-178C or equivalent process, no target build, no qualification evidence. Nothing here is a candidate for airborne use |
| **Any timing claim on target hardware** | Every figure is CPython on a shared general-purpose host and moves ±10% between runs. **No target-hardware measurement exists and none is claimed** |
| **Evidence about a real vehicle** | Phase-I evidence is ArduCopter 3.3 SITL and a bench simulator; the current-stack work is ArduPilot 4.8 SITL. **No flight data.** PX4 SIH is recorded `INAPPLICABLE` for Mechanism B with the reason |
| **A claim about how common the defect class is** | n = 1 deployed layer. A structural-analysis FDI design would mark the fault set unisolable instead and would not exhibit this at all |
| **Common-cause reasoning on the aircraft profile** | The dependency model is blind to shared COMMUNICATION, COMPUTE and TIMING for the `battery`/`motor_esc` pair. `dependency_model_blind_to` reports it per row. Closing it is a profile change — and the profile is frozen |
| **Distinguishing "estimator stopped" from "estimator too slow"** | `COMPUTE/estimator_stale` covers both, which is why matched set D has 3 distinct answers from 4 scenarios. An estimator domain would fix it and is **not authorised** |
| **Export** | `ECCN_PENDING`. See `docs/compliance/EXPORT_CONTROL_REVIEW.md`. No public release is authorised on classification grounds |
| **Two of the three profiles as evidence of anything physical** | The bench and the pump skid are **synthetic**: the numbers are invented. They demonstrate that the framework is expressible, not that any machine behaves that way |

## 4. What a consumer must not do

From `engineering/v2/CONTROLLER_INTEGRATION_SPEC.md` §6, restated because
each one is a way to misuse a correct output:

1. **Do not treat `UNKNOWN` as `ELIGIBLE`.** A failed plugin makes functions
   `UNKNOWN`; a consumer that reads absent evidence as permission has
   inverted the contract.
2. **Do not present `possible_domains` as a cause.** They are alternatives
   nobody could rule out.
3. **Do not use the internal typed path across a boundary.** In-process,
   version-locked, construction-controlled only. Network, IPC, file, or
   anything untrusted goes through `from_external_payload`, which validates.
4. **Do not put the wall-clock fields in anything that has to replay.** They
   are observability, and they are deliberately absent from the per-tick
   document for that reason.
5. **Do not expect a command.** The layer issues none, ever. There is no code
   path from it to an actuator; the controller decides what to do.

## 5. What it is genuinely good for today

Three things, and they are real:

- **As a monitoring layer in a simulation or a bench harness**, where its
  output is read by a human or logged, and the consumer honours §4. It will
  tell you which functions are still justified, on what evidence, and what
  limits them — and it will say `AMBIGUOUS` when it cannot tell.
- **As a worked example of applicability semantics done explicitly.** The
  distinction between `UNAVAILABLE`, `NOT_APPLICABLE` and `NOT_CONFIGURED`,
  and between concentration and discriminating support, is implemented rather
  than described.
- **As the evidence base for the two papers.** That is its current job.

## 6. What would move it past M2

Not more features. In the order the Phase C evidence actually implies:

1. **Declare the real dependencies in the aircraft profile** — closes §3's
   common-cause blind spot and is the cheapest real improvement available.
2. **Instrumentation before inference.** Matched set B's floor of two is not
   solved by another domain; it is solved by a shaft observation, and the
   bench already proves that.
3. **A target-hardware measurement**, so that any timing statement means
   something.
4. **Real vehicle data**, so that "evidence about a system" stops meaning
   "evidence about a simulator".

**All four are frozen** until both papers reach submission-candidate state.
See `docs/CURRENT_PROGRAM_STATE.md`.

## 7. Fitness for the two papers

| | |
|---|---|
| **Systems paper** | The frozen layer **is** the system under measurement, and the measurements are bound to it: `CLAIMS.csv` (26 rows, each with counter-evidence and an alternative explanation), the artifact map, and an independent checker agreeing 378,000/378,000. Remaining blockers are the bibliography and the public-log study — **neither is a property of CSIA** |
| **Mathematical paper** | The layer supplies the implemented instance: a deployed system that fails the ignorability condition, for 200 consecutive ticks, confirmed by a checker that imports none of it. Remaining blocker is the bibliography — again not a property of CSIA |

**Neither paper is blocked by anything in the code.** That is the strongest
readiness statement available, and it is narrower than "product ready".
