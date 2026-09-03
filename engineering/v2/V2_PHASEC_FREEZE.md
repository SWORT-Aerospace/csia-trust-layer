# CSIA v2 PHASE C — FREEZE RECORD

**NO FURTHER V2 IMPLEMENTATION UNTIL PAPER LOCK RELEASE.**

Product expansion is stopped by management decision. Until **both** current
CSIA papers reach submission-candidate state, this repository does not gain:
an estimator domain, an energy domain, a thermal domain, Forge production
code, automatic reconfiguration, ZETH integration, CSIA Edge, new UAV
features, or a new recovery planner.

Documentation of the future architecture is permitted and is in `docs/` and
`forge/`. **Implementation is not.**

---

## 1. What is frozen

| | |
|---|---|
| frozen commit | `50c5d3576e9084e7c2789167628392c5de992b6f` |
| short | `50c5d35` |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| tree at freeze | clean, no uncommitted changes |
| proposed tag | `csia-v2-phasec-frozen` — **created locally, NOT pushed. Pushing requires authorization.** |
| tests | **1,512 pass** |
| Phase C verdict | `CROSS_DOMAIN_ASSURANCE_FUNCTIONAL` |

Upstream freezes still hold and are unaffected:

| | |
|---|---|
| CSIA v1 | `csia-v1.0-research-final` @ `ec5acd189295dab9259d4989657d42184d6142a3` — **zero diff, verified by `tests/test_v1_frozen.py`** |
| CSIA v1.1 | unchanged; output schema `1.1.0` unchanged |
| Systems Paper I baseline | `main @ 848f556` — a Phase-I number may not move |

## 2. Phase C commits

| commit | what |
|---|---|
| `933247d` | C1 — two interfaces; the 28 ms turns out to have been a defect |
| `1d405d7` | C2 — cross-domain causal localization by deterministic set elimination |
| `d75cc2d` | C3 — plugin isolation, watchdog, §11 redundancy/fallback, second profile |
| `5bb6a34` | C4 — the §41 properties, and three answers that were confident and wrong |
| `50c5d35` | C5 — the seven Phase C specs and the §45 report |

## 3. Artifact hashes at freeze

SHA-256 of each generated artifact as committed at `50c5d35`. Regenerate with
`python engineering/v2/run_phase_c.py`; the CSV/JSON contents are
deterministic except `V2_PHASEC_COMPUTE.json`, which contains wall-clock
timings and will differ.

```
ebc0154ef6ca59bc2549a06353d62740366d563e55ff7d40eb5821b99773812f  V2_PHASEC_GATE.json
fca6cda24ee2c3a67271ea9d6282a480d908131fa74213437b241919bc04692c  INTERNAL_EXTERNAL_EQUIVALENCE.json
78412c640ac023b3d4e21f6e5f4d25d9ecfe18cb1b4678c9d281315b0fc997a7  V2_PHASEC_COMPUTE.json   (timings; not reproducible bit-for-bit)
5bd441f49f3fe02b73ef0fd47c4ed116da858b847c9861e8a0fd5e164eb5c062  LOCALIZATION_RESULTS.csv
f45f905c27b2f48b3410fadce667bfac20b1b5882e63272ba883866f94a4a0c8  CROSS_DOMAIN_SIGNATURE_MATRIX.csv
ab8fa92fefb8f3698dc1881f1e143a806228ada931e791b5a0a440857c179c5f  EVIDENCE_SUBSET_RESULTS.csv
5049fd05adb5dfcb2cb4d4476ed442a83ce91abb143bf15fa9cdac3e82a48f5f  PLUGIN_FAILURE_RESULTS.csv
5788cf38ef1cb814dd729d394e4d5df23cc26e990357a74b27f4144beb147f13  LOCALIZATION_LEDGER.json
2a28ddb3ce473fdd410c8eddcef2bada743d13cf179f30d4b606e29029fed1b3  FUNCTION_REQUIREMENTS_V2.yaml
```

## 4. The 13,500-payload equivalence result

`INTERNAL_EXTERNAL_EQUIVALENCE.json`:

| | |
|---|---|
| payloads compared | **13,500** |
| mechanisms | 9 (CLEAN, GNSS_RAMP_SLOW, GNSS_RAMP_FAST, GNSS_FIX_LOSS, IMU0_BIAS_DRIFT, DUAL_IMU_FAILURE, MAG_DEGRADED, POWER_SAG, VIBRATION_ANOMALY), 1,500 each |
| mismatches | **0** |
| `identical` | `true` |
| compared on | the FULL per-tick `SystemAssurance` document — domain evidence, function results, cross-domain attribution, localization and plugin status. Not a summary. |
| tolerance | zero. These are discrete outputs; one differing reason code is a failure. |

Equality is structural rather than coincidental: both constructors converge on
one typed object before any evidence exists, and a test parses the AST of the
navigation domain to assert there is exactly one record builder.

## 5. Hot-path measurements

CPython on a general-purpose host. **No target-hardware figure exists and none
is claimed.** These move ±10% between runs on a shared machine; the ratio is
the claim, the third significant figure is not.

| path | µs/tick |
|---|---|
| Phase B, uncached `jsonschema.validate` | 22,130.0 |
| cached validator, same full validation | 673.6 |
| external full parse | 691.8 |
| external typed ingest | 644.0 |
| **internal typed ingest** | **9.2** |

Ratio ≈ **2,400×**. The Phase B figure was a **defect** — `jsonschema.validate`
re-checks and re-compiles the schema on every call — not the cost of
validating. Building the validator once is a pure defect fix; a test asserts
the replacement is byte-identical including which error message
`best_match()` selects.

Per phase:

| phase | median µs/tick | max µs/tick |
|---|---|---|
| `api_build_and_evaluate` | 2,745.4 | — |
| six domains through the supervisor | 747.1 | 982.4 |
| explanation | 87.3 | 167.2 |
| localization | 45.8 | — |
| ledger | 14.1 | 743.8 |
| internal typed ingest | 9.2 | — |

68 records, 9 symptoms evaluated per tick.

## 6. Localization results

27 rows over 19 scenarios: **18 SUPPORTED, 9 AMBIGUOUS, 0 UNSUPPORTED**. No
unique cause was ever emitted without a discriminating predicate confirming
it.

§42 gate, strict reading (the member → hypothesis map must be injective over
the whole set):

| set | members | reduced | distinct | qualifies |
|---|---|---|---|---|
| `A_STALE_OUTPUT` | 4 | 4 | 4 | **yes** |
| `B_ACTUATOR_RESPONSE` | 5 | 0 | 0 | no — no member reached SUPPORTED |
| `B_ACTUATOR_RESPONSE_BENCH` | 2 | 2 | 2 | **yes** |
| `C_MULTI_SENSOR` | 4 | 0 | 0 | no — the dependency model is blind to two of the four causes |
| `D_POSITION_FUNCTION` | 4 | 4 | 3 | no — D2 and D4 are the same hypothesis |

**Verdict: `CROSS_DOMAIN_ASSURANCE_FUNCTIONAL`** on two qualifying sets. Under
the looser reading ("more than one distinct answer") four sets qualified; the
criterion was tightened and the verdict survived.

## 7. Known blind spots, carried into the freeze

1. **The dependency model is the ceiling on common-cause reasoning (§13).**
   The only real v1.1 payload with two adverse sources has `battery` and
   `motor_esc`. They share a POWER node; the battery declares no link and
   neither declares a compute node. `dependency_model_blind_to` reports
   `COMMUNICATION|COMPUTE|TIMING` for all four Set C members. Closing it is a
   **profile** change (declaring the real dependencies), not a framework
   change — but that is implementation and is frozen.
2. **Hypothesis granularity is fixed by declaration.** `COMPUTE/estimator_stale`
   covers both "stopped" and "over budget", which is why D2 and D4 collapse.
3. **Set B has an irreducible floor of two on the multirotor.** No independent
   physical channel exists on the shaft, so `SENSOR/response_sensor` can never
   be refuted. The bench resolves it because it is instrumented, which is the
   finding, not a defect.
4. **No probability is attached to an ambiguous set.** Ranking survivors needs
   priors nobody has measured.
5. **Localization is per tick.** Onset order is in the ledger and is unused,
   because using it needs state the domain contract forbids.
6. **Three profiles, one author.** The genericity result is n=3 and all three
   were written by the same person who wrote the framework.
7. **Two of the three profiles are synthetic.** The bench and the pump skid
   contain invented numbers. No real bench or skid data exists here.
8. **The matched sets are constructed, not observed.** The injections are
   authored. What is real is the v1.1 evidence they are injected into, and the
   fact that no ground truth reaches the decision (asserted by test).
9. **No target-hardware measurement.** Every timing is CPython on a shared
   general-purpose host.

## 8. Profiles at freeze

| profile | functions | v1.1 | notable |
|---|---|---|---|
| `aircraft` | 10 | wrapped as the SENSOR domain | `PRECISION_LANDING` deliberately absent — v1.1 omits it for want of a landing reference |
| `test_stand` | 4 | **none** | no SENSOR domain registered at all |
| `pump_skid` | 4 | **none** | one-of-N over `ACTUATION/pump_a\|pump_b`; fallback `OPEN_LOOP_ON_SPEED`; optional TIMING |

Both non-aircraft profiles run in a fresh interpreter with neither
`csia.v1_1` nor the aircraft profile in `sys.modules`, asserted by test.

## 9. Domains at freeze

Six, and **no more may be added**: `SENSOR` (the v1.1 wrapper), `POWER`,
`COMPUTE`, `TIMING`, `COMMUNICATION`, `ACTUATION`.

Not implemented and not authorized: estimator, firmware, thermal, security,
storage, energy.

## 10. Unresolved issues carried forward

| id | issue | blocks |
|---|---|---|
| V2-U1 | Set C's dependency-model blind spot (§7.1) | completeness of §13, not the papers |
| V2-U2 | D2/D4 hypothesis-granularity collapse (§7.2) | Set D's gate qualification |
| V2-U3 | `PLUGIN_FAILURE_RESULTS.csv` covers `raise` and `silent`; a `hang` column exists only in tests, not in the artifact | artifact completeness |
| V2-U4 | `V2_PHASEC_COMPUTE.json` is not bit-reproducible (wall-clock), so it cannot be regression-tested the way the other artifacts are | artifact hygiene |
| V2-U5 | genericity is n=3, single author | the §38 product claim's strength |
| V2-U6 | no target-hardware timing | any deployment claim |

None of these blocks either paper. **None of them may be worked on until the
paper lock is released.**

## 11. Relationship to the two papers

**Neither paper depends on v2.** Systems Paper I is Phase-I evidence on
ArduCopter 3.3 SITL and the bench simulator, frozen at `848f556`. The
mathematical paper is about gate conditioning and posterior distortion. v2 may
appear in **FUTURE WORK only**, and `tools/publication/phase_guard.py` already
fails a Phase-I build that references later phases.

## 12. Release condition

This freeze lifts when **both** of the following exist:

- tag `systems-paper-submission-candidate`
- tag `math-paper-submission-candidate`

and not before. The gates for each are in `docs/CURRENT_PROGRAM_STATE.md`.
