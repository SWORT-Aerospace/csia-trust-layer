```
===============================================================
CSIA POST-E1 HARDENING + E2 STATUS
===============================================================

HEAD:    d9aa672
BRANCH:  claude/code-reviewer-repo-export-zicovg

TESTS:     2179
FAILURES:  0

FROZEN CORE DIFF:  EMPTY

  git diff csia-v1.0-research-final -- csia/trust_engine csia/diagnosis \
      csia/runtime/online.py csia/runtime/failsafe.py csia/scenarios.py \
      csia/profiles.py

  produces no output. Not one byte of the frozen scientific core changed.
  E1_FREEZE_MANIFEST.yaml is byte-unchanged (`git diff --stat` empty).

  CAVEAT, unchanged since E1: the tag `csia-v1.0-research-final` is LOCAL
  ONLY. Pushing it was refused HTTP 403, so the tag-diff test SKIPS on a
  clean clone. This diff was run here, where the tag exists.
```

---

# SOFTWARE HARDENING

| item | status | measured |
|---|---|---|
| independent assurance firewall | **DONE** | `csia_assurance/`, outside `csia/`. 5 verdicts, 15 conformance vectors, 83 tests |
| fail-closed coverage | **11 / 11** | every one of the 11 `FAIL_CLOSED_REASONS` is exercised. 5 by a committed conformance vector, 6 more by tests or campaign artifacts |
| firewall independence | **DONE** | it never recomputes the CSIA score; a large score cannot force support. Pinned by `tests/test_assurance_independence.py` (6 tests) |
| support witness output | **DONE** | emitted for AMBIGUOUS and NON_IDENTIFIABLE too, `complete=false`. Labelled `EXPERIMENTAL_SUPPORT_CERTIFICATE`, never "certified" |
| failure-containment contract | **DONE** | exception → `NOT_EVALUABLE` with the exception named. Never nominal, never "keep the previous certificate" |
| executable reference semantics | **DONE** | `docs/ASSURANCE_REFERENCE_SEMANTICS.md` + the clean-room reference it loads by path |
| bounded SMT verification (P1–P8) | **DONE** | z3 5.1.0. P1/P2 `STRUCTURAL_BY_CONSTRUCTION`; P3/P4/P5/P6/P8 **no counterexample in the bounded domain** (max 4 hypotheses, 6 evidence); P7 `sat` **by design** — a hazard demonstration — then run through the real firewall, where it **HOLDS**. 0 `unknown` results. Cross-check: **4096 concrete cases, 0 semantic mismatches, 0 ranking or prior sensitivities** |
| counterexample minimization | **DONE** | delta debugging with a load-bearing invariant. Minimum admitted **LOCAL**, every reduction re-verified |
| metamorphic testing | **DONE** | 15 tests |
| property-based testing | **DONE** | hypothesis 6.167.1 |
| hostile telemetry fuzzing | **DONE** | **27** declared classes — the 26 the programme named plus `unknown_schema_field`. REJECTED 21, HANDLED 22, DEGRADED 4, NOT_APPLICABLE 34. **SILENT_HEALTHY 0, CRASH 0, HANG 0** |
| adapter-boundary fuzzing | **DONE** | covered within the 27 classes where the adapter is the target; wire-level malformity recorded as an adapter concern |
| **decision-level replay** | **DONE, RESULT NEGATIVE** | **DIVERGENT on both platforms.** ArduPilot 511 of 750 compared ticks differ categorically; PX4 144 of 750. **Cannot be counted PASS in this gate** |
| cross-environment semantic conformance | **PARTIAL** | probe written and run; matrix has **one row** — containers cannot run here |
| semantic portability contract | **DONE** | 4 levels, separated. Level 4 is bounds, **not** equivalence |
| OS / compute stress campaign | **DONE** | 5 stressors, criteria declared before the runs. **0 silent decision divergence**, verdict `NO_SILENT_DIVERGENCE` |
| resource-envelope characterization | **DONE, WITH AN ADMITTED HOLE** | every run banded NORMAL (p50 ≈ 6–7 µs against a 2000 µs budget), so **the NORMAL/DEGRADED boundary is UNTESTED** and the artifact says so |
| process failure and recovery | **DONE** | 6 scenarios, `NO_FORBIDDEN_TRANSITION`. SIGKILL → restart: `RECOMPUTED_IDENTICAL`, nothing carried. **Restart-by-supervisor is UNTESTED — there is no supervisor in this repository** |
| configuration proof system | **DONE, FINDING RECORDED** | all 6 smuggling forms **accepted by the existing loader**, **none reaches the frozen core**. A strict exact-key gate refuses all 6 and accepts the reference config. **Not wired in** — source is not modified automatically |
| build / dependency provenance | **DONE** | interpreter, host, declared extras, installed distributions, frozen-core digests, undeclared-import check (clean). **Not signed, and says so** |
| differential implementation testing | **DONE** | **5 implementations, 1036 comparisons, 0 real disagreements, 0 degenerate** |

## The five implementations, since this is the strongest new result

| | source | kind |
|---|---|---|
| PRODUCTION | `engineering/v1_1/support/decompose.py` | numeric, `|Δ| > 1e-12` |
| CHECKER | `research/systems-paper/independent_checker.py` | structural |
| CLEANROOM | `research/physical_validation/cleanroom/structural_reference.py` | structural, stdlib only |
| FIREWALL | `csia_assurance/firewall.py` | asked through `competitors_without_witness` |
| DEA | `tools/dea/conformance.py` `separators()` | the published profile's own definition |

**1036 of 1036 unanimous** across nine scenarios and 28 hypothesis pairs.

**What that does not prove, stated in the artifact itself:** five
implementations of a wrong definition agree perfectly. This bounds
IMPLEMENTATION error. It says nothing about whether the definition is right.

**The DEA column is a declared specialisation.** DEA separation is
DIRECTIONAL — "evidence against you is not evidence for you" — so it coincides
with the symmetric structural question only at the observation matching the
asserted hypothesis. That is the observation used, and it is stated rather
than buried.

## Findings this programme produced (HF-001 … HF-009)

All in `research/physical_validation/FAILURE_LEDGER.yaml`.

| id | what | verdict |
|---|---|---|
| HF-001 | a **subnormal** gate weight (5e-324) licensed `SUPPORTED_UNIQUE` | **FIXED** as a validity rule (`INVALID_GATE_STATE`), deliberately **not** a tolerance |
| HF-002 | the minimizer produced a confident wrong answer **twice** | FIXED with a load-bearing invariant |
| HF-003 | scalar S11's declared artifact does not contain its value | **SPECIFIED, NOT APPLIED** — the map is hashed by the immutable freeze |
| HF-004 | decision replay **DIVERGENT on both platforms** | **RECORDED, NOT FIXED** at the time. **Later CLOSED 2026-09-09 (HF-018)**: the divergence was in the comparison, not the replay (HF-017), and is 0 on both platforms once joined on the layer's tick index. Never tuned; the tolerance is unchanged and the join is stricter. Values still do not reproduce |
| HF-005 | my differential harness read an absent firewall answer as a positive one, then **accused the firewall** of the defect | FIXED |
| HF-006 | the deployment loader accepts all six smuggling forms | RECORDED; none reaches the core; strict gate written, not wired |
| HF-007 | the provenance tool reported frozen-core drift where there was none | FIXED by sharing the freeze manifest's own digest functions |
| HF-008 | the support certificate asserted freshness it never read | FIXED; now read back, contradictions surfaced |
| HF-009 | a forbidden-word guard fired on the documentation of the rule it enforces | FIXED; **the seventh time** |

**Two of the nine were my own instruments producing confident wrong answers
about a system that was behaving correctly** (HF-005, HF-007), and HF-004's
earlier form was a third. The shape is now named in the ledger: a measurement
path that cannot distinguish "no answer" from "the answer is yes" will
eventually produce a confident wrong one.

## What was NOT completed, and is not being reported as done

- **Cross-distribution portability matrix.** Blocked: docker client present,
  **no daemon**. Reported as one row rather than approximated. Running a second
  interpreter on the same host and calling it a second environment would be
  worse than a blank row.
- **Binding the 42 SCIENTIFIC_RESULT prose literals.** They are CLASSIFIED,
  not BOUND.
- **The three specified pointer corrections and the S11 artifact correction.**
  Deferred to a deliberate re-freeze.
- **Supervisor / restart-policy testing.** No supervisor exists here.
- **Signing the provenance record.** Nothing is signed.

---

# PROVENANCE

```
Unmapped scientific prose numbers:   50 total, 0 unclassified
    SCIENTIFIC_RESULT                42   classified, NOT bound
    SOURCE_CONSTANT                   3
    DERIVED_QUANTITY                  3
    FORMATTING                        2

Scalar pointers:                     19 total
    dereferenceable                  13
    adjudicated                       6
    unresolved                        0

RAW_TO_CLAIM DAG:  research/provenance/RAW_TO_CLAIM_DAG.yaml
    research scalars                 13
    paper scalars                    17
    claims                           16
    honest limits recorded            4

Publication hardening manifest:
    research/physical_validation/E1_PUBLICATION_HARDENING_MANIFEST.yaml
    scientific_semantics_changed:  false
    scientific_core_diff_is_empty: true
```

**Why the 42 were not bound by search, recorded because the attempt was made:**
a numeric scan of 131 committed result artifacts matched **all 45** numeric
literals, most of them many times — `0.906` matched a phase-2 lambda sample,
`1.0` matched a hundred places. That is coincidence, not provenance, and
binding on it would manufacture the exact false chain this audit exists to
find. Many matches were under `research/phase2/`, which the phase guard forbids
a Phase-I map from citing.

**The target was never "0 numeric literals."** A version number and 1/α are not
results. The target is **0 UNSUPPORTED scientific prose literals**, and the gap
to it is 42 bindings, each needing its owning section's artifact opened.

---

# OPTIPLEX VALIDATION NODE

**Decision: `OPTIPLEX_SUFFICIENT` for E2.** The companion SBC is **deferred**,
with the exact conditions that would flip it written down
(`hardware/validation_rig/E2_COMPANION_COMPUTE_DECISION.md`).

Not recommended for purchase now, and specifically **not** on the reasoning
that a deployed UAV will eventually need onboard compute — that is a reason to
buy one **later**, for a tier that measures deployment-class timing, not a
reason to buy one for E2.

`scripts/optiplex_nightly.sh`, 14 stages, three outcomes: **PASS**,
**REGRESSION**, **INCONCLUSIVE** — and `INCONCLUSIVE` is never folded into
PASS, because a skipped check reading as green is a failure mode this
repository has already hit.

**Stage 8 (decision replay) is expected to FAIL.** It runs anyway so the day it
changes is visible, in either direction.

**The distribution is DETECTED, not assumed.** This host measured:
Ubuntu 24.04.4 LTS, kernel 6.18.44-fc-v24, x86_64, CPython 3.12.3.

---

# E2 HARDWARE

**Board class: Pixhawk FMUv6C. Reference board: Holybro Pixhawk 6C.**

Selected **from both projects' own source trees**, not from reputation:
450 ArduPilot hwdef boards, 120 PX4 boards, 49 SIH-enabled, **15 supported by
both**.

| | ArduPilot | PX4 |
|---|---|---|
| identifier | `Pixhawk6C` | `px4/fmu-v6c` |
| evidence | `libraries/AP_HAL_ChibiOS/hwdef/Pixhawk6C/hwdef.dat` | `boards/px4/fmu-v6c/default.px4board` |
| MCU as each tree declares it | `STM32H7xx STM32H743xx` | `STM32H743VI` |
| MCU family agrees | **yes** | **yes** |
| PX4 SIH on the default target | — | **yes** |

**Why:** FMUv6C is a published Pixhawk FMU standard, so several vendors build
compliant boards and availability does not depend on one supplier — every other
H7 candidate in the survey is a single-vendor design. Four IMUs declared in the
hwdef, which is what lets E2 test whether PX4's narrow E1 demonstration (1 of 4
GNSS-gated relations live) was a property of the **simulator** or of the
**platform**. That is the single most informative thing E2 can measure.

**NEGATIVE FINDING, kept:** `both_support_simulation_on_hardware` is **false
for all 15** intersection rows. No board supports simulation-on-hardware on
both stacks. The tempting symmetric design — each stack's own on-board
simulator — **does not exist** and was not pretended into existence.

**A board-survey alias bug was caught by the survey's own MCU cross-check**:
`Pixracer-periph` (STM32F427) had been aliased to `mro/pixracerpro`
(STM32H743). Removed, with the reason in a comment.

**One board, flashed sequentially.** Two boards would add unit-to-unit sensor
variation to an experiment designed to have one variable — the same confound as
FL-017.

---

# E2 CAMPAIGN

```
E2_STATUS:  NOT_RUN
REASON:     no flight-controller hardware is present
```

Nothing about E2 is claimed. Not hardware evidence, not flight validation, not
physical sensor validation, not airworthiness.

Prepared and waiting:

| artifact | what it fixes before purchase |
|---|---|
| `hardware/validation_rig/E2_BUILD_PACKET.md` | objective, wiring, flashing order, board verification, expected telemetry, logs, abort conditions |
| `hardware/validation_rig/E2_BOARD_SELECTION.md` | the board, from source |
| `hardware/validation_rig/E2_MINIMUM_BOM.csv` | 15 rows, tiered E2 / E3 / E4 / E5 |
| `hardware/validation_rig/E2_TIMING_CONTRACT.md` | three clocks; what is measured, what is bounded, what is **not measurable and must not be reported** |
| `research/physical_validation/prereg/E2_HARDWARE_BOUNDARY_PREREG.md` | **NEW.** Every design decision fixed now; every environment field `[FILL:]` until a board exists |

The preregistration fixes, **before** hardware is bought: the hypothesis (not
a mechanism hypothesis); the pinned environment — longer than E1's by exactly
the field E1 got wrong, the runtime stale-timeout source, FL-017; three arms
including a **null control** under RULE A; `planned = valid + invalid +
not_attempted`; the captured quantities; the four equivalence levels; and
**"success is not *it matches*"** — a hardware/simulator disagreement is a
result, written down before any trial can produce one.

**§4.1 of the build packet: the TELEM2 receive wire is cut on purpose.**
`NO_COMMAND_PATH_REACHABLE` becomes a property of the wiring rather than a
promise made by software.

---

# CLAIM IMPACT

**NONE. Not one manuscript number, claim or qualification changes.**

`research/physical_validation/E1_FINAL_CLAIM_TABLE.csv` is unchanged: 16
claims, 10 REPEATED, 1 REFUTED_SUPERSEDED, 2 NOT_REPEATABLE, 1
CONFIGURATION_DEPENDENT, 1 MEASURED, 1 UNRESOLVED.

FL-016, FL-017 and FL-019 are intact and carried visibly. FL-016 — that the
control arm rose ~2.9× (ArduPilot) and ~2.7× (PX4) more than the fault arm,
with disjoint ranges — remains in the manuscript as **"the repeated campaigns
took a claim away, and it is ours."**

Every finding of this programme is about an **instrument**, a **loader**, a
**certificate field** or a **guard**. None is about a scientific result. A
hardening round with no claim impact is the outcome to hope for, not a
shortfall.

Recorded as `PE-004` in `POST_E1_PAPER_IMPACT_LEDGER.yaml`, with the four
upgrades it does **not** license spelled out:

- *"The definition is verified."* **FALSE** — agreement bounds implementation
  error only.
- *"Configuration is hardened."* **FALSE** — the strict gate is not wired in.
- *"Recovery is verified."* **FALSE** — restart behaviour is untested.
- *"The build is attested."* **FALSE** — nothing is signed.

---

# USER ACTION

**Hardware is absent. E2 cannot begin.** The one decision that is yours: buy
the REQUIRED rows below, or E2 does not start.

## Buy — REQUIRED for E2

| # | item | qty | what it buys | what it does **not** buy |
|---|---|---|---|---|
| 1 | **Flight controller, Pixhawk FMUv6C class** — reference: **Holybro Pixhawk 6C** | 1 | the tier itself: real autopilot firmware on real MCU silicon, supported by **both** stacks from one board; and whether `redundant_imu` goes live on hardware, which PX4 SIH could not answer | nothing about a fault (E3), nothing about flight (E5), no timing claim that transfers to a companion computer |
| 2 | **MicroSD card** | 2 | firmware and the FC's **own** onboard log — the independent record against CSIA's — plus one spare | nothing scientific on its own |
| 3 | **GNSS + compass module** | 1 | `gnss.position`, `gnss.velocity`, `mag.field_ut` from a real receiver, so the four GNSS-gated relations are **live before** any fault | nothing about a GNSS **fault**. That is E3 |

## Check your existing stock first — do not buy if you have them

| # | item | purpose |
|---|---|---|
| 4 | **USB data cable** for the FC (not charge-only) | the GCS command link: arm, set parameters, request streams. Deliberately **not** CSIA's path |
| 5 | **USB-to-serial adapter, 3.3 V TTL** | CSIA's **passive** link on TELEM2 |
| 6 | **Dupont / JST-GH jumper leads** for TELEM2 | TX, GND — and RX **left unconnected** |

## Wiring — exact

```
FC TELEM2 TX  ->  adapter RX
FC TELEM2 GND ->  adapter GND
FC TELEM2 RX  ->  NOTHING. The wire is absent, on purpose.
adapter USB   ->  the OptiPlex
```

Cutting that one wire is what turns "CSIA cannot command" from a software
promise into a physical fact.

## Reuse — buy nothing

- **Your existing OptiPlex** is the Linux host. `OPTIPLEX_SUFFICIENT` —
  `E2_COMPANION_COMPUTE_DECISION.md`.

## Do **not** buy yet

| item | why not |
|---|---|
| **Companion SBC** (Raspberry Pi 5 or similar) | buys a latency distribution on target-class compute. **E2 asks nothing that needs it.** The conditions that would flip this decision are written down |
| Fault-injection interface board, signal-interruption harness | **E3 only** |
| Thrust stand, ESC, motor, **propellers** | **E4 / E5 only.** Props are absent at E2 **by rule** — they are the only stored-energy hazard on the bench and E2 does not need them |
| Airframe, pilot kill switch | **E5 only.** Money does not solve site or airspace clearance |
| Bench power supply | **OPTIONAL.** Check whether USB suffices first — many FMUv6C boards run fine on USB with no servo-rail load |

## Deliberately unpriced

**No price appears anywhere in this packet.** Vendor sites are unreachable from
this environment — the agent proxy answers **403 at CONNECT** — so every figure
would have been invented. `docs/HARDWARE_BOM.md` carries 2026 planning
estimates that say on their face to verify at purchase.

---

# PUSH

```
db54f91  Post-E1 hardening round 2: A16-A19, E2 preregistration template
8bb3520  Guard the first hardening round's artifacts, which had none
d9aa672  Post-E1 hardening and E2 status report; nightly node covers the new tools
```

All three pushed to `claude/code-reviewer-repo-export-zicovg`.

```
TESTS:                     2179 passed, 0 failed
make check-blocking:       PASS
frozen core diff:          EMPTY
E1_FREEZE_MANIFEST.yaml:   byte-unchanged
```

---

## The target, restated

> CSIA's qualified assurance semantics are stable across declared supported
> environments, and when an environment or evidence contract fails, the system
> degrades explicitly rather than silently claiming support.

**Where that now stands, honestly:**

- **"Degrades explicitly rather than silently claiming support"** — this is the
  part with real evidence. 0 silent-healthy outcomes across 27 hostile classes, 81 cases;
  0 silent decision divergence under 5 stressors; 6 recovery scenarios with no
  forbidden transition; 11 of 11 fail-closed reasons exercised; 6 of 6
  configuration smuggling forms failing to reach the core.
- **"Stable across declared supported environments"** — **one environment is
  measured.** The contract that defines what stability means exists and
  separates the four levels; the matrix that would populate it has a single
  row. This is the weakest claim in the programme and the honest word for it is
  *unestablished*, not *pending*.
- **"Declared supported environments"** — the declaration exists
  (`docs/SEMANTIC_PORTABILITY_CONTRACT.md`). Nothing has been declared
  supported that was not measured.
