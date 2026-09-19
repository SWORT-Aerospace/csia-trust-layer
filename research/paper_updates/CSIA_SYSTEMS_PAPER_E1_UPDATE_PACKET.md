# CSIA Systems Paper I (E1) — evidence-to-paper update packet

**GENERATED** by `tools/research/build_paper_update_packet.py` from measured artifacts. Edit the script, not this file.

**This packet does not edit the manuscript and creates no scientific claim.** It reports what is currently measurable, what the existing claim register says, and which wording is permitted.

> **The short version for the paper agent.** Nothing in the recent work bears on any claim the paper makes. The paper is about a diagnostic core evaluated in simulation and SITL; the new work is an acquisition layer for a bench that has never been powered. The recommended main-paper change is **none**. The one real hazard is a word collision on *coverage*, described in §D.

## A. Repository identity

| field | value |
|---|---|
| starting commit | `d87f97491f7425110be83324007d779c1db21f12` |
| ending commit | `d87f97491f7425110be83324007d779c1db21f12` |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| frozen-core digest | `b0b011c61426a70ead42e170855a2650d5c62feb640c7a50fffc27bb915ba5a8` |
| frozen-core files | 12/12 identical: True |
| test command | `python -m pytest -q -rs` |
| test result | 3733 passed, 2 skipped, 0 failed, exit 0 |
| blocking guards | `make check-blocking` → **PASS** |

Skip reasons, in full — **a skip is not a pass**:

* `SKIPPED [1] tests/test_e2m_acquisition.py:612: E2M gate 4: NO_HARDWARE_ACCESS. No /dev/ttyACM*, /dev/ttyUSB* or COM* port is present. This test is NOT evidence about hardware and a skip must not be reported as physical validation.`
* `SKIPPED [1] tests/test_e2m_acquisition.py:618: E2M gate 4: NO_HARDWARE_ACCESS. No /dev/ttyACM*, /dev/ttyUSB* or COM* port is present. This test is NOT evidence about hardware and a skip must not be reported as physical validation.`

## B. Verified current software-assurance results

| result | value | evidence | command |
|---|---|---|---|
| suite | 3733 passed / 2 skipped / 0 failed | recorded pytest run | `python -m pytest -q -rs` |
| code coverage | 94.49% | coverage.json | `python -m coverage report` |
| mutation | 18/18 = 1.0 | `research/bus_provenance/results/E2M_MUTATION_RESULTS.json` | `python tools/mutation/run_e2m_mutations.py` |
| CRC differential | agreement on every tested vector | `hardware/host_tests/crc_harness.c` | `python -m pytest tests/test_e2m_crc_differential.py -q` |

Per-file test counts, measured:

| file | tests |
|---|---|
| `tests/test_e2m_properties.py` | 21 |
| `tests/test_e2m_schemas.py` | 57 |
| `tests/test_e2m_transport.py` | 17 |
| `tests/test_e2m_crc_differential.py` | 8 |
| `tests/test_e2m_acquisition.py` | 52 |
| `tests/test_bus_provenance.py` | 34 |

Coverage by file:

| module | % |
|---|---|
| `csia_bus_provenance/__init__.py` | 100.0 |
| `csia_bus_provenance/datasheet.py` | 92.59 |
| `csia_bus_provenance/provenance.py` | 94.79 |
| `csia_bus_provenance/simulator.py` | 98.36 |
| `csia_bus_provenance/topology.py` | 90.91 |
| `csia_e2m/__init__.py` | 100.0 |
| `csia_e2m/ancestry.py` | 92.31 |
| `csia_e2m/fake_controller.py` | 98.21 |
| `csia_e2m/faults.py` | 95.08 |
| `csia_e2m/identity.py` | 97.1 |
| `csia_e2m/logging.py` | 93.41 |
| `csia_e2m/protocol.py` | 93.1 |
| `csia_e2m/replay.py` | 95.89 |
| `csia_e2m/transport.py` | 90.0 |

### Mutation detail

Targets: `csia_bus_provenance/provenance.py`, `csia_e2m/identity.py`, `csia_e2m/logging.py`, `csia_e2m/protocol.py`, `csia_e2m/replay.py`

| family | evaluated | killed | score |
|---|---|---|---|
| CHANNEL | 2 | 2 | 1.0 |
| CRC | 4 | 4 | 1.0 |
| IDENTITY | 5 | 5 | 1.0 |
| MISSING | 3 | 3 | 1.0 |
| SEQUENCE | 1 | 1 | 1.0 |
| TIME | 1 | 1 | 1.0 |
| TOPOLOGY | 2 | 2 | 1.0 |

**Baseline before the new tests: 16/18 = 0.8889, two survivors** (`ID-05`, a CONFLICTED identity was not asserted contradicted; `CRC-02`, the missing-delimiter guard was redundant for control flow). Both are now killed. The baseline is reported because a score quoted without the run that produced it is not a measurement.

## C. Mandatory qualification language

Every one of these must appear wherever the corresponding number does. They are not stylistic.

* The mutation score is for a SELF-AUTHORED, DECLARED mutant set. The same person wrote the mutants and the tests that kill them.
* The mutation score is NOT comparable to another project's score, or to this repository's other scores, without matching mutant definitions. Different mutant lists are different measurements.
* No live hardware was operated.
* No physical sensor was tested.
* No TCA9548A timing was measured.
* No UART timing was measured.
* No brownout was observed.
* No flight, HIL, propulsion, actuator or autopilot validation occurred.
* Fake-driver and fake-port results are not hardware validation.
* Replay is not acquisition.
* Authorized is not executed.
* Skipped hardware tests are not passes.

## D. Claim audit of the existing systems paper

Register: `research/systems-paper/CLAIMS.csv`, 26 claims.

**Claims affected by this work: 0.**

Every SC-claim concerns the frozen diagnostic core evaluated in simulation or ArduPilot/PX4 SITL. The E2M work is an acquisition layer for a bench that has never been powered, plus software assurance over it. It produces no measurement of any quantity any SC-claim is about, so it neither supports nor weakens one. Folding it into an existing claim would be the error this packet exists to prevent.

| claim | register status | packet status | evidence level | affected | replacement wording |
|---|---|---|---|---|---|
| `SC-01` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-02` | PROVED | SUPPORTED (proved) | ANALYTIC_OR_STRUCTURAL | no | none required by this work |
| `SC-03` | PROVED | SUPPORTED (proved) | ANALYTIC_OR_STRUCTURAL | no | none required by this work |
| `SC-04` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-05` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-06` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-07` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-08` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-09` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-10` | KNOWN_SUBSUMED | SUPPORTED (scope statement, prior art) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-11` | KNOWN_SUBSUMED | SUPPORTED (scope statement, prior art) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-12` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-13` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-14` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-15` | PROVED | SUPPORTED (proved) | ANALYTIC_OR_STRUCTURAL | no | none required by this work |
| `SC-16` | WITHDRAWN | WITHDRAWN | SIMULATION_OR_SITL | no | none required by this work |
| `SC-17` | REFUTED | WITHDRAWN (refuted) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-18` | REFUTED | WITHDRAWN (refuted) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-19` | REFUTED | WITHDRAWN (refuted) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-20` | PROVED | SUPPORTED (proved) | ANALYTIC_OR_STRUCTURAL | no | none required by this work |
| `SC-21` | PROVED | SUPPORTED (proved) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-22` | PROVISIONAL | NEEDS QUALIFICATION (provisional) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-23` | PROVISIONAL | NEEDS QUALIFICATION (provisional) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-24` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-25` | PROVISIONAL | NEEDS QUALIFICATION (provisional) | SIMULATION_OR_SITL | no | none required by this work |
| `SC-26` | EMPIRICAL_ONLY | SUPPORTED (empirical, in its declared scope) | SIMULATION_OR_SITL | no | none required by this work |

### Stale-number scan

* test-count claims found: **0**. main.tex refers to 'the project's test suite' qualitatively at lines 457, 1217, 1316 and 1544 and never quotes a test count, so no test-count claim is stale. The suite has since grown; that is not a correction to the paper because the paper never stated a figure.
* mutation claims: **0**; hardware-validation claims: **0**; certification claims: **0**; novelty claims: **0**.
* SC-10 and SC-11 are explicit non-novelty scope statements and are correct as written.

> **CRITICAL FOR THE PAPER AGENT. 'Coverage' in main.tex Section 'Two detectors, and what neither sees' means DETECTOR coverage over a 21-cell amplitude-slew grid (38% and 43% uncovered). It does NOT mean code coverage. The 94.49% figure in this packet is CODE coverage of two new packages and must never be placed near those numbers.**

**The manuscript's existing scope statements are correct and must be preserved, not weakened.** It already says *"The one frequency we measure is measured in a simulator"* and *"No detection performance on real flight data is claimed anywhere in this paper"*. Nothing in this packet licenses softening either sentence, and adding an acquisition-layer supplement must not read as a step toward hardware evidence.

## E. Recommended paper changes

### 1. Main paper

**NONE REQUIRED.** No E2M result bears on any claim the main paper makes. The main paper is about a diagnostic core evaluated in simulation and SITL; this work is acquisition-layer preparation for a bench that has not been powered.

### 2. Appendix

**OPTIONAL: a short reproducibility note**

> The diagnostic core's test suite, the acquisition layer's tests and the publication guards run on every commit; counts are recorded in the repository rather than in this paper.

Keeps the paper free of a number that changes every commit. The paper's existing practice already does this and should not be abandoned.

### 3. Supplement only

**E2M acquisition-layer software assurance may be described in a supplement**

Permitted framing:

> A sensor-bus acquisition layer and its software assurance were prepared in advance of any hardware. Device identity behind an I2C multiplexer is modelled explicitly, and the layer refuses to treat a commanded channel or a control-register readback as proof of which physical device answered. No hardware has been operated.

Required adjacent sentence:

> No sensor, multiplexer, bus or board was powered; all results are from a deterministic fake controller, recorded fixtures and a compiled host copy of the firmware CRC.

This is engineering preparation, not a scientific result about the paper's subject.

### 4. Claims that must not be added

* Any statement that CSIA was validated on hardware.
* Any statement that a TCA9548A, a sensor or a UART was tested, timed or characterised.
* Any statement that a brownout, dropout or misattribution was OBSERVED on a bench. The misattribution demonstration is in a simulator and is labelled as one.
* Any statement that the acquisition layer is flight-ready, deployment-ready, production-ready, fault-tolerant or certified.
* Any novelty claim for the identity model, the mutation set, the CRC differential or the multiplexer failure taxonomy. An I2C switch is a commodity part and its failure modes are folklore.
* Any comparison of the 1.0 mutation score to another project's score, or to this repository's other mutation scores.
* Any use of the 94.49% code-coverage figure near the paper's detector-coverage percentages.

## F. Reproducibility map

| number | source | command | expected | artifact sha256 |
|---|---|---|---|---|
| 3733 passed, 2 skipped, 0 failed | `tests/` | `python -m pytest -q -rs` | PYTEST_EXIT=0; two skips, both gate-4 hardware | — |
| 94.49% code coverage | `csia_bus_provenance/, csia_e2m/` | `python -m coverage run --source=csia_bus_provenance,csia_e2m -m pytest tests/test_bus_provenance.py tests/test_e2m_*.py -q && python -m coverage report` | TOTAL 94.49% | — |
| mutation 18/18 = 1.0 | `tools/mutation/run_e2m_mutations.py` | `python tools/mutation/run_e2m_mutations.py` | evaluated 18  killed 18  survived 0  score 1.0 | `7abb3e29b481cf26…` |
| CRC host/firmware differential: agreement on all vectors | `hardware/host_tests/crc_harness.c, csia_e2m/protocol.py` | `python -m pytest tests/test_e2m_crc_differential.py -q` | 8 passed | `b02b4c9cc8d2b1df…` |
| blocking guards PASS | `Makefile` | `make check-blocking` | BLOCKING GUARDS: PASS | — |
| frozen-core digest | `docs/v1/FROZEN_BASELINE.json` | `python -m pytest tests/test_v1_frozen.py -q` | b0b011c61426a70ead42e170855a2650d5c62feb640c7a50fffc27bb915ba5a8 | `4261f96095dade50…` |

## G. Machine-readable status

See `CSIA_SYSTEMS_PAPER_E1_UPDATE_PACKET.json`, key `G_machine_readable_status`. Each entry carries `claim_id`, `claim_text`, `status`, `evidence_level`, `source_path`, `verification_command`, `numeric_values`, `permitted_paper_wording` and `prohibited_wording`.

## Corrections to the request that produced this packet

Recorded rather than quietly reconciled. In each case the **measured** value is what appears above.

* **requested:** 21 CRC differential test categories — **measured:** 8 CRC differential test functions. 21 is the count of PROPERTY tests in tests/test_e2m_properties.py, not CRC categories. The CRC differential file contains 8 test functions covering 8 named edge-payload categories plus the check vector, real frames, four frame lengths, single-bit mutations, truncations and 400 seeded random payloads. No 21-category CRC grouping exists and none was invented.
* **requested:** starting commit 913113c / d87f974 — **measured:** d87f97491f7425110be83324007d779c1db21f12. HEAD at the start of this task was d87f974. An earlier instruction named 913113c, which was one commit behind.
* **requested:** audit of the attached manuscript — **measured:** papers/csia_systems/main.tex at this commit. No attachment reached this session. The audit is against the manuscript source in the repository. If the attached file differs, this audit does not cover it and must be re-run.

