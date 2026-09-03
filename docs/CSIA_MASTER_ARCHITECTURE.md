# CSIA MASTER ARCHITECTURE

What exists, what is frozen, and where the future attaches.
**Everything marked FUTURE is documentation only and is not authorised for
implementation.**

---

## 1. What is built, in one picture

```
  raw platform signals                    v1.1 output payload (schema 1.1.0)
          |                                          |
          v                                          v
  +----------------------------------------------------------------------+
  |  v2 DOMAIN PLUGINS                                                     |
  |  POWER  COMPUTE  TIMING  COMMUNICATION  ACTUATION                      |
  |  SENSOR = the v1.1 wrapper (transcribes; computes nothing)             |
  +----------------------------------------------------------------------+
          |  EvidenceRecord: categorical verdict + OPTIONAL numbers
          v
  +----------------------------------------------------------------------+
  |  FUNCTION GRAPH        which functions are still justified             |
  |  LOCALIZATION          which domain the evidence supports, by          |
  |                        deterministic set elimination                   |
  |  EXPLANATION           limiting / possible / cleared, per function      |
  +----------------------------------------------------------------------+
          |
          v
  SYSTEM  +  per domain  +  per function  +  WHAT LIMITS EACH FUNCTION
          |
          v
  the controller decides what to DO.  CSIA issues no command.
```

## 2. The three frozen layers

| layer | tag / commit | what it is | status |
|---|---|---|---|
| **v1** | `csia-v1.0-research-final` @ `ec5acd18` | the trust recursion, the gated naive-Bayes diagnosis, the failsafe policy, the scenario catalogue | **FROZEN, zero diff, verified twice per run** (git diff + SHA-256) |
| **v1.1** | output schema `1.1.0` | function eligibility, support state, the CUSUM bank, the assurance ledger, the versioned read-only output API and firewall | **FROZEN** |
| **v2 Phase C** | `50c5d35`, tag proposal `csia-v2-phasec-frozen` | six domain plugins, the function graph, cross-domain localization, the plugin supervisor, three profiles | **FROZEN by management decision** |

`tests/test_v1_frozen.py` enforces the first. `tools/publication/phase_guard.py`
enforces the phase separation. `engineering/v2/V2_PHASEC_FREEZE.md` records the
third.

## 3. Design commitments that do not change

1. **Absence of evidence is not health.** `UNKNOWN` outranks `INELIGIBLE`. A
   failed plugin makes functions `UNKNOWN`, never `ELIGIBLE`.
2. **A posterior is not confidence.** A leader at 0.9998 with zero
   discriminating evidence is `SUPPORT_LOST_FOR_REQUIRED_INFORMATION`.
3. **No unique cause without a discriminating measurement.** Survival of
   elimination is not evidence. `AMBIGUOUS` is a permitted, and often correct,
   answer.
4. **Three-valued predicates.** `True` / `False` / **not measurable**. Absence
   of a declared dependency is not evidence of independence.
5. **Determinism on the decision path.** No clock, no RNG, no network, no
   cross-tick state in a domain. The ledger replays bit for bit.
6. **The layer issues no command.** Ever. There is no code path to an
   actuator.
7. **Negative results are permanent.** Refuted claims, defective runs and
   withdrawn requirements stay committed.

## 4. Where the platform knowledge lives

| lives in | contains |
|---|---|
| `csia/v2/*.py` — the framework core | no aircraft term, no threshold, no platform noun. A test parses the AST and asserts it over identifiers |
| `csia/v2/profiles/` | every rail, process, link, actuator, function name and threshold |
| `engineering/v2/FUNCTION_REQUIREMENTS_V2.yaml` | the profiles' requirements as reviewable data, generated from them |

Three profiles exist: `aircraft` (wraps v1.1), `test_stand` (no SENSOR domain
at all), `pump_skid` (one-of-N redundancy, fallback requirement sets, an
optional domain). Both non-aircraft profiles run in a fresh interpreter with
neither `csia.v1_1` nor the aircraft profile ever imported — asserted by test,
because a README saying "generic" is not evidence.

## 5. FUTURE — where new capability would attach

**None of this is implemented. None of it is authorised.**

| future component | attaches at | what it would do |
|---|---|---|
| Forge | *above* the profiles | import existing engineering artifacts (SysML v2, AADL, EMV2, CycloneDX, platform and controller configuration) and emit a CSIA profile. See `forge/README_FUTURE.md` |
| new domains (estimator, firmware, thermal, energy, security, storage) | as plugins, same contract | the plugin contract already accommodates them; §44 of the Phase C brief froze them until localization worked, and the freeze is now a *paper* lock |
| ZETH | *above* CSIA, read-only | mission planning and optimisation. No back edge. See `docs/SWORT_AUTONOMY_STACK.md` |
| an AI analyst | downstream of `Localization` and `FunctionExplanation` | prose and prioritisation for a human. Three hard prohibitions in `engineering/v2/AI_ANALYST_FUTURE_SPEC.md` |
| automatic reconfiguration | *not in CSIA* | this is the controller's authority. If it is ever proposed, it must first reduce against `research/FUTURE_RESEARCH_FRONTIER.md` |

## 6. The two open engineering findings carried into the freeze

1. **The dependency model is the ceiling on common-cause reasoning.** Set C's
   `dependency_model_blind_to` reports `COMMUNICATION|COMPUTE|TIMING` for the
   `battery`/`motor_esc` pair. Closing it is a profile change, not a framework
   change — and it is frozen.
2. **Resolving power is a property of instrumentation, not of the algorithm.**
   The bench resolves what the multirotor cannot, using identical hypotheses
   and predicates, because it has a torque channel. This is the most useful
   result Phase C produced and it points at hardware, not at more inference.

## 7. Reading order for someone new

1. `docs/CURRENT_PROGRAM_STATE.md` — what is happening right now
2. `RESEARCH_STATE.md` — what is established, refuted and withdrawn
3. `CLAIMS_INDEX.md` — which of the claim registers governs what
4. `engineering/v2/V2_PHASEC_REVIEW_REPORT.md` — the current engineering tip
5. `engineering/v2/V2_PHASEC_FREEZE.md` — why it stops there
