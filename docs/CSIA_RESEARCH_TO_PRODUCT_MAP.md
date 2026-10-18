# RESEARCH TO PRODUCT MAP

Which research finding produced which product behaviour, and which findings
produced nothing. Both directions matter: a research programme whose
negative results left no trace is not being audited.

**Product development is FROZEN at v2 Phase C.** Nothing in the right-hand
column may grow until the paper lock is released.

---

## 1. Findings that became product behaviour

| finding | where established | product consequence | where it lives |
|---|---|---|---|
| A gated feature is *skipped*, so absence of applicable evidence is emitted as health | WP-C4 self-occlusion | `support_state` with four values, of which `NO_APPLICABLE_EVIDENCE` is one | `engineering/v1_1/support/support.py`, `csia/v1_1/eligibility.py` |
| A high posterior with no discriminating evidence is not eligibility | WP-C4 / WP-C8 | `SUPPORT_LOST_FOR_REQUIRED_INFORMATION`, fired **independently of freshness** so removing the freshness rule cannot rescue it | `csia/v1_1/eligibility.py` |
| Escalation is duration-limited, not magnitude-limited | WP-C7 glitch mechanism, closed form in `main.tex` | the CUSUM bank was promoted from the ablation harness into the runtime | `csia/v1_1/sequential.py` |
| The textbook CUSUM `h = 5.0` false-alarms badly (2681 clean alarm ticks) | Phase 3B ablation | `h = 500`, fixed by a zero-clean-alarm rule; the failure is retained as a committed negative result | `engineering/v1_1/SEQUENTIAL_DETECTOR_SPEC.md` |
| A sequential alarm says the evidence changed, not what changed it | Phase 3B | a sequential alarm degrades and never attributes | `csia/v1_1/eligibility.py` |
| Two IMU hypotheses collapsed to a shared signature at disarm | WP1 F-D1 | `attitude_gravity_mag` added to `imu0_bias_drift`'s LOW set, breaking the tie; ungated so it survives disarm | `csia/diagnosis/bayes.py` (repaired in WP-C3) |
| `E_h ⊆ C_h` containment holds; `U_h ⊆ C_h` is not well posed | WP-C6 | the effective-signature machinery kept; the `U_h` claim **withdrawn permanently** | `research/formalization/` |
| Absence of a declared dependency is not evidence of independence | v2 Phase C, C4 | shared-dependency predicates return **not measurable** for an uncovered domain; `dependency_model_blind_to` reports the gap | `csia/v2/signatures.py` |
| Resolving power is a property of instrumentation | v2 Phase C, matched set B vs bench B | the bench profile exists to demonstrate it; no algorithm change was made | `csia/v2/profiles/test_stand.py` |
| Redundancy must be expressed over components, not domains | v2 Phase C, building the pump skid | `redundant_groups` over `"DOMAIN/component"`; `REDUNDANCY_REDUCED` emitted alongside `ALL_REQUIREMENTS_MET` | `csia/v2/functions.py` |
| `jsonschema.validate` recompiles the schema every call | v2 Phase C, C1 | a validator built once — byte-identical behaviour, ~33× cheaper | `csia/v1_1/output_api.py` |

## 2. Findings that produced NOTHING, deliberately

| finding | why no product change |
|---|---|
| B4 (CUSUM) outperforms the frozen layer on the correct-diagnostic ledger across three flight specs | it *did* ship (§1), but `INVENTION_GATE = CLOSED`, verdict `ESTABLISHED_METHOD_SOLVES`: no **new** detector is justified. A textbook method that works closes the gate rather than opening a research line |
| ArduPilot already implements a cumulative GPS drift monitor, gated on `onGround` | E1 became a **scope** result, not a new CSIA feature. The mechanism that would own that regime exists upstream |
| `INFORMATIVE_VALIDITY` — a channel can be present, fresh, valid, correctly decoded and carry no physical information | registered as research candidate `C25`, `PROVISIONAL`. **Not implemented.** It does not open the invention gate |
| B3 (mass cap) | refuted: breaks R10 at every setting tried. Retained as a negative result |
| R16 slow IMU bias detection | TPR 0.00 over 150 Monte Carlo runs. Requirement **withdrawn** from `docs/REQUIREMENTS.md` rather than weakened |
| Set C's dependency-model blind spot | the fix is a profile change and would be cheap. **It is frozen.** Doing it now would be product expansion |
| Set D's D2/D4 hypothesis-granularity collapse | an estimator domain would resolve it. **Explicitly not authorised** |

## 3. Findings that became a paper claim and nothing else

| finding | paper | product consequence |
|---|---|---|
| the posterior ratio is pinned to the prior ratio when no active term distinguishes a pair | mathematical, P3 | none — it is an explanation of behaviour that already exists |
| `KL(q‖p)` is exactly the Jensen gap of `log w` | mathematical, P5a | none |
| 76 ticks of every clean flight have `nominal|gps_fault` indistinguishable | systems, `SC-05` | none. It is a startup-window property and the failsafe is unarmed for 10 s anyway |
| smoothing cuts pre-onset false crossings 36 → 9 | systems, `SC-08` | none. It documents an existing design choice |

## 4. The direction of travel this map shows

Early phases produced **product changes**. Recent phases produce **scope
corrections and negative results**. That is the expected shape of a programme
approaching a publication lock, and it is the reason the management decision
to stop product expansion is the right one: the marginal product change is now
small and the marginal paper claim is large.

## 5. What would reopen the product line

Per `engineering/v2/V2_PHASEC_FREEZE.md` §12: both submission-candidate tags
existing. Then, in the order the Phase C evidence actually implies:

1. declare the real dependencies in the aircraft profile (closes §2's blind
   spot, cheapest real improvement available);
2. an estimator domain (resolves the D2/D4 collapse);
3. instrumentation before inference — set B's floor of two is solved by a
   shaft observation, not by another domain, and the bench already proves it.
