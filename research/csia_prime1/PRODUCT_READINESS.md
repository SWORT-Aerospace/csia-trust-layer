# Product readiness (PRIME-1 Phases 27-28, 37-39)

**2026-10-03. "Boring to install, difficult to fool, explicit about what it
does not know, reproducible."** Each line below is measured; the artifact is
named.

## 1. Install (Phase 39, `FRESH_INSTALL_PRIME1.json`)

| check | result |
|---|---|
| the exact wheel inside the participant bundle (SHA-256 `04e2ec961de9...`, checked against the bundle record), installed from file into a new virtual environment | exit 0 (numpy, scipy, networkx, matplotlib, pyulog from PyPI) |
| `csia-assure <log> --out <dir>` from an empty directory, no PYTHONPATH | exit 0 on all 8 sample logs |
| outputs against the repository's committed sample outputs | **byte-identical**, every file of every log |
| modules loaded from the repository | none; the package file is inside the new environment |
| research code, tests, logs or answer keys inside the wheel | none |

**D-PRIME-3 was found here.** The first fresh-install run crashed on every
analysable log: the wheel had never carried `stock_calibration.json`.
PRIME's own install check had installed from the source tree, not from the
wheel, and passed. The package data now covers every product JSON file, a
permanent test checks it, and the check above tests the artifact that ships
(`KNOWN_DEFECT_REGISTER.md`).

## 2. Performance (Phase 38, `PERFORMANCE_PRIME1.json`)

One machine (4 CPUs, Python 3.12), nothing else running, median of 3 runs.
The analysis stage re-parses the log, as the product does.

| log | size | startup | support check | parse | discovery | analysis and report | **total (CLI)** | peak memory | report size |
|---|---|---|---|---|---|---|---|---|---|
| SITL hover loss (V1) | 18.7 MB | 0.24 s | 0.23 s | 0.27 s | 0.08 s | 1.16 s | **1.47 s** | 78 MiB | 204 kB |
| SITL maneuvering loss (V13) | 32.8 MB | 0.23 s | 0.41 s | 0.49 s | 0.18 s | 1.98 s | **2.33 s** | 98 MiB | 263 kB |
| SITL long nominal (CAL1) | 28.1 MB | 0.27 s | 0.36 s | 0.41 s | 0.14 s | 1.65 s | **2.01 s** | 90 MiB | 101 kB |
| real AUAV X2.1 | 4.1 MB | 0.24 s | 0.07 s | 0.08 s | 0.00 s | 0.24 s | **0.59 s** | 51 MiB | 51 kB |
| real boat (withheld) | 26.8 MB | 0.25 s | 0.53 s | — | — | 1.77 s | **1.96 s** | 56 MiB | 9 kB |

**A pilot of 20 logs is under a minute of computing.** Performance is not a
constraint on the pilot.

## 3. Local engagement workflow (Phase 27, `engagement.py`)

```
csia-assure engagement init    engagements/E-001 --label "<customer>" --mode blind
csia-assure engagement ingest  engagements/E-001 flight1.ulg flight2.ulg --intake intake.json
csia-assure engagement run     engagements/E-001
csia-assure engagement seal    engagements/E-001
csia-assure engagement reveal  engagements/E-001 customer_diagnosis.json
csia-assure engagement verify  engagements/E-001
```

| property | how it is enforced |
|---|---|
| inputs hashed, read-only, append-only intake | `raw/INTAKE.json`; the raw copy is made read-only |
| immutable run manifest with versions and report hashes | `derived/RUNS.json`: release, analyzer, semantics, profile, support contract, producer versions, code digest, every output's SHA-256 |
| raw / derived / final separated | `raw/`, `derived/`, `final/` |
| blind mode | an expected event time is refused at intake |
| one run | `run` is refused after the seal |
| reveal after seal only | `reveal` refused before the seal; the reveal records the seal hash |
| tamper evidence | `verify` recomputes every sealed hash and reports any mismatch; never repairs |
| customer data never committed | `.gitignore`: `engagements/`, `customer_data/`, `*.ulg`, `*.ULG` |

## 4. REAL_DATA_READY_CHECK (Phase 28, `REAL_DATA_READY_CHECK.json`)

**Question:** if a team sends a real PX4 log tomorrow, can it be analysed
blind, sealed and revealed without writing code?

| check | result |
|---|---|
| every real log available gets a support state, no crash (7 logs: 6 pyulog samples from real boards, the PX4 docs boat) | yes: UNKNOWN_VERSION 1, PARTIAL 4, UNSUPPORTED_VEHICLE_CONFIGURATION 2 |
| the same log twice, the second with every proxy variable removed | byte-identical |
| the blind engagement, end to end, command line only | init, ingest, run, seal, reveal, verify: all as specified |
| blind mode refuses an expected event time | refused |
| rerun after seal; reveal before seal | both refused |
| an altered output after the seal | `verify` fails |
| customer paths ignored by git | yes |
| network code in the product | none |

**REAL_DATA_READY: yes, for receiving, analysing, sealing and revealing.**

**What this check cannot show:**
- whether any conclusion is right on a real propulsion fault: no reachable
  real log has one;
- the real false-observation rate of the propulsion producers: every
  threshold is SITL-calibrated, and no real log here carries both
  `actuator_motors` and ESC RPM;
- behaviour on PX4 versions other than 547e2ca beyond "no crash, support
  state stated".

## 5. Physical validation (Phase 29)

**Not faked, not claimed.** Nothing in the support contract is
PHYSICAL_VALIDATED. The matched physical A/B (PRIME
`B4_MATCHED_AB_PROTOCOL.md`) is designed and not run. If real logs arrive
(Phase 30), they go through section 3 exactly: hash, freeze, analyse blind,
seal, then reveal.

## 6. Regression (Phase 37)

The full suite is run before the final commit; the result is recorded in
`PRIME1_REVIEW_AND_DECISION.md` and `research/physical_validation/results/BUILD_PROVENANCE.json`.

**No hidden expected failure is added by PRIME-1.**
- PRIME's two strict expected-failures (D-PRIME-1 and D-PRIME-2 on the
  historical path) are kept: they pin the historical release's recorded
  behaviour, and they still fail as expected.
- The fixed behaviour is pinned by ordinary tests on the successor path
  (`tests/test_csia_prime1.py`).
