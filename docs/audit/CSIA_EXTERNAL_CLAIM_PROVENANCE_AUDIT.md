# CSIA External-Claim Provenance Audit

**Trigger:** an externally submitted white paper (`SWORT_CSIA.pdf`, referenced
at `docs/evidence/evidence_matrix.md:81`) states two validation figures that
the current repository does not appear to contain:

> "Validated via a 62-test automated fault harness"
> "26 real PX4 flight logs (0.66 flight-hours)"

**Question:** do these numbers correspond to something real, or to nothing?

**Date:** 2026-08-22 · **Audit baseline:** `5b67a39` · **Method:** every number
below was re-derived by executing repository code or by collecting the test
suite at the historical commit named. Nothing is quoted from a prior document
without re-execution. Where a fact could not be established from the
repository, it is marked **CANNOT BE DETERMINED HERE** and not guessed.

---

## 0. Verdict

**Neither "the data exists but is unverifiable" nor "the numbers correspond to
nothing." Both figures are real, reproducible, and traceable to a specific
commit — and both are now wrong, for different reasons.**

| Claim | Was it ever true? | Reproducible today? | Status |
|---|---|---|---|
| "62-test" | **Yes** — exact collected count at `c13889f` (v0.8.0) through `3ecd788` | **Yes**, at that commit (re-derived below) | **STALE + MISCHARACTERIZED** — suite is 445 today, and the 62 were never a fault harness |
| "26 real PX4 flight logs" | **Yes** | **Yes** — committed artifact, 26 UUIDs | **CORRECT** |
| "0.66 flight-hours" | **Yes** — 2385.9 s = 0.6628 h | **Yes** — re-derived to the second | **SUPERSEDED** — corrected denominator is **0.518 monitored h** |
| "Validated via …" | **No** | n/a | **PROHIBITED WORDING** — the repository's own rule W7 forbids it |

There is no fabrication. There is a **failure to propagate a correction the
repository itself made on 2026-08-03** to a document that had already been
submitted. The submitted document is a snapshot of the repository's
2026-07-24 position, and the repository has since withdrawn part of that
position as unsound.

The single most serious item is not either number. It is the word
**"Validated"** attached to the flight-log figure.

---

## 1. Claim A — "62-test automated fault harness"

### 1.1 The number 62 is real

Collected, not counted by hand, at two historical commits, using the current
interpreter against a detached worktree of each commit:

```sh
git worktree add --detach /tmp/wt <commit>
cd /tmp/wt && PYTHONPATH=. python -m pytest --collect-only -q
```

| File | `c13889f` | `3ecd788` |
|---|---|---|
| `tests/scenarios/test_fault_scenarios.py` | 8 | 8 |
| `tests/scenarios/test_seeker_scenarios.py` | 7 | 7 |
| `tests/test_comparator.py` | 4 | 4 |
| `tests/test_diagnosis.py` | 3 | 3 |
| `tests/test_engine.py` | 6 | 6 |
| `tests/test_mavlink_map.py` | 4 | 4 |
| `tests/test_native.py` | 4 | 4 |
| `tests/test_runtime.py` | 17 | 17 |
| `tests/test_sensors.py` | 9 | 9 |
| **TOTAL** | **62** | **62** |

This independently reproduces the inventory recorded at
`docs/audit/CSIA_REPOSITORY_AUDIT.md:19` (`8 + 7 + 4 + 3 + 6 + 4 + 4 + 17 + 9
= 62`) and the executed result at line 18 (`pytest -q` → **62 passed**).

The phrase's origin is exact. `README.md:44` at `3ecd788` read:

```
| Simulated fault harness (62 tests, CI) | spoof 2.2 s @ 89%; IMU isolation
99%/0%; mag/power/vib 100% |
```

The white-paper sentence is a derivative of that table row.

### 1.2 But 62 was the whole suite, not a fault harness

At the same commit the *fault harness proper* is
`tests/scenarios/test_fault_scenarios.py`: **5 scripted fault scenarios**
(`gps_spoof`, `imu0_bias_drift`, `mag_emi`, `power_sag`,
`vibration_anomaly`), exercised by **8 tests**. Adding the seeker scenarios
gives **15**. The remaining 47 are unit and behavioral-contract tests —
causality, online/batch equivalence, C-vs-Python parity, determinism, MAVLink
mapping, bounds safety. Those are software-correctness tests. They are not
fault-detection evidence.

Two defects follow:

- **Scope inflation.** "62-test automated fault harness" attributes the whole
  suite's size to the fault-detection evidence, inflating it by **4×**
  (62 vs 15) or **7.75×** (62 vs 8) depending on how the harness is bounded.
- **Category error.** All five fault scenarios are **synthetic** — generated
  by `csia/sensors` fault injection from fixed seeds. No real fault data is
  involved. A reader takes "validated via a fault harness" to mean faults were
  detected on representative data; what was demonstrated is that scripted
  injections cross fixed thresholds set below previously measured performance.

The repository's own internal wording is more honest than the white paper's:
`docs/TRANSITION_REPORT.md:67` calls it a "62-test CI suite of *behavioral
contracts*."

### 1.3 The count timeline — every published figure was true when published

| Commit | Date | Collected | Published as |
|---|---|---|---|
| `f2786f6` (v0.6.0) | 2026-07-12 | — (35 `def test_`) | — |
| `c13889f` (v0.8.0) | 2026-07-22 | **62** | README "62 tests" ✔ |
| `3ecd788` | 2026-07-24 | **62** | README "62 tests" ✔ |
| `944134f` | 2026-08-03 02:29 | **77** | — |
| `5ad44d9` | 2026-08-03 03:32 | **109** | README/C19 updated to "77" ✘ (stale by one commit) |
| `5b67a39` (HEAD) | 2026-08-04 | **445** | README still says "77" ✘ |

Every number this project has published was correct at some commit. None
survived contact with the next one. **"77" is not fabricated** — it is the
exact collected count at `944134f`, written into `README.md:37,44` and
`evidence_matrix.md:39` one commit later, when the count had already moved to
109. That is a one-commit lag, not an invention.

The systemic defect is that the test count is a hand-maintained literal in
prose. It has been wrong in a public artifact for most of this project's life.

---

## 2. Claim B — "26 real PX4 flight logs (0.66 flight-hours)"

### 2.1 Both numbers are exactly right, and both are committed

`data/real_logs_report.json` **is under version control** — the repository
gitignores `/data/` and then explicitly re-admits this one file
(`.gitignore:14-15`):

```
/data/
!/data/real_logs_report.json
```

| Property | Value |
|---|---|
| Path | `data/real_logs_report.json` |
| SHA-256 | `3fc299136873826a3db09077fb8e2c100aef31597e0068e744be5c9b0347fbd2` |
| Size | 11,753 bytes |
| Committed at | `f2786f6` (v0.6.0, 2026-07-12) — **never modified since** |

Re-derived directly from that artifact:

| Quantity | Re-derived | Claimed |
|---|---|---|
| Flights | **26** (26 unique `fr_<uuid>.ulg` names) | 26 ✔ |
| Raw duration | **2385.9 s = 0.66275 h** | 0.66 h ✔ |
| Shortest / longest | 31.5 s / 393.4 s | — |
| Transitions | **3** — 2 CAUTION escalations + 1 NORMAL recovery | — |
| Logs with any transition | **2** → **24 of 26 alarm-free** | — |
| Logs under 40 s | **7** | — |
| Duplicate-duration collisions | 2 pairs (50.0 s, 35.4 s) | — |

So the answer to "does the data exist?" is **yes, the derived evidence is in
the repository and every published figure regenerates from it.**

### 2.2 The raw corpus is not in version control — but it is re-acquirable

The 26 `.ulg` files were never committed. `data/real_logs/` is gitignored and
empty here. The corpus is nonetheless **identified**, not lost:

- The 26 UUIDs are embedded in the committed report as `fr_<uuid>.ulg`.
- `tools/fetch_real_logs.py` reads those UUIDs and re-downloads each from
  `https://review.px4.io/download_log?log=<uuid>`, verifying the `ULog` magic
  bytes before writing.
- `datasets/reports/acquisition_backlog.json` (committed) holds all 26 with
  source URLs, `acquisition_succeeded: false`, and the exact two-command
  reproduction path.
- `datasets/manifests/px4_public_v1.json` (committed) carries per-log records
  with `content_sha256: null` and an explicit note that hashes are null
  **because the corpus was not acquired**, not because they were omitted.

This is the correct posture for un-redistributable third-party data, and it
was recorded honestly. What it is **not** is content-addressed: because no
`.ulg` was ever hashed, **there is no way to prove that a future re-download
yields the same bytes the campaign ran on.** PX4 Flight Review logs can be
deleted or replaced by their uploaders. Reproducibility here is *nominal*
(same UUIDs) rather than *cryptographic* (same content).

### 2.3 "0.66 flight-hours" is the superseded denominator

The repository corrected this itself on 2026-08-03, and the correction is
reproducible:

- `arm_time` is 20 s in the offline posture; **no alert can be raised inside
  it**. Across 26 logs that is exactly **520.0 s = 21.8%** of recorded time.
- Corrected exposure: 2385.9 − 520.0 = **1865.9 s = 0.5183 monitored hours**.
- Corrected rate: 2 alert episodes / 0.5183 h = **3.86/h, Poisson 95% CI
  [0.47, 13.94]**.

The white paper's 0.66 h is the **raw** figure. As a false-alarm-rate
denominator it is inflated: 21.8% of the quoted time is unmonitored
(520.0/2385.9), equivalently the raw denominator is 27.9% larger than the
correct one (0.6628/0.5183), so the resulting rate is understated by that
factor. The earlier published rate of "4.5/flight-hour" was separately
found to have counted a failsafe *recovery* edge as an alarm (audit F-01, a
1.50× over-count).

### 2.4 "Validated" is the prohibited word

This is the finding that matters most, and it is not a rounding issue.

Per `docs/audit/CSIA_DATASET_PROVENANCE_AUDIT.md` (findings D-01, D-03) and
`docs/evidence/evidence_matrix.md` (rule W7):

- **All 26 logs are `UNANNOTATED`.** No log carries a ground-truth health
  label. **Verified-healthy exposure is 0.000 h.**
- **All 26 influenced thresholds and architecture.** `field_mode` exists
  *because of* these logs. **Held-out exposure is 0.000 h.** There is no
  train/test separation — every log is a training log.
- Absence of a CSIA alert on an unannotated log is **the hypothesis under
  test**, not evidence for it.

W7 states the required form verbatim and marks the alternative **PROHIBITED
WORDING**:

> Required: *"No CSIA alert episode occurred during X hours of unannotated
> real-flight-log replay."*
> Never: *"CSIA demonstrated zero false alerts during X healthy flight-hours."*

The rule is machine-enforced at
`tests/test_datasets.py::TestCommittedCorpus::test_no_log_is_classified_verified_healthy`,
which asserts `by_health["VERIFIED_HEALTHY"] == 0.0`.

"Validated via … 26 real PX4 flight logs" asserts exactly what W7 prohibits.
An Army reviewer reading it will take it to mean the system was evaluated
against real flight data. It was **exercised on** real flight data that had
already shaped its tolerances, and no outcome was ground-truthed.

---

## 3. What the repository already fixed, and when

The correction landed in commits `944134f` and `5ad44d9` (2026-08-03) and is
recorded in `CHANGELOG.md` under **"Corrected (claims, not behavior)"**:

- "Healthy flight hours" **withdrawn**.
- Rate denominator corrected: 3.02/h on 0.663 raw → **3.86/h on 0.518
  monitored** hours.
- Held-out exposure recorded as **0.000 h**.
- Explicitly: *"No trust-algorithm, threshold, failsafe or recommendation
  change. `campaigns/bench.json` regenerates bit-identical."* The correction
  was to the **claims**, not the system.

`README.md:47` today already carries the fully corrected form. **The
repository's public surface is honest. The submitted PDF is not, because it
predates the correction and was never reissued.**

---

## 4. Delta: submitted document vs. current defensible position

| Submitted | Defensible today |
|---|---|
| "Validated via a 62-test automated fault harness" | "Regression-gated by a 445-test CI suite of behavioral contracts, including a 5-scenario synthetic fault harness (8 tests)." |
| "26 real PX4 flight logs (0.66 flight-hours)" | "26 unannotated public PX4 logs; 0.518 **monitored** flight-hours (0.663 h raw, of which 21.8% lies inside the arm window where no alert can fire)." |
| Implied: real-data validation | "No CSIA alert episode occurred in 24 of 26 logs. 2 alert episodes / 0.518 h → 3.86/h, 95% CI [0.47, 13.94]. Verified-healthy exposure 0.000 h. Held-out exposure 0.000 h. Not a reliability claim." |

### 4.1 Drop-in replacement text

> CSIA is regression-gated by a 445-test CI suite of behavioral contracts
> (causality, online/batch equivalence, C-vs-Python parity at 1e-12,
> determinism, bounds safety), which includes a five-scenario synthetic fault
> harness. Fault-detection performance figures are measured on **simulated**
> injections from fixed seeds.
>
> Separately, CSIA was replayed against 26 public PX4 Flight Review logs
> totalling 0.518 monitored flight-hours. No alert episode occurred in 24 of
> the 26; 2 episodes across the corpus give 3.86 episodes/hour (Poisson 95% CI
> 0.47–13.94). These logs are **unannotated** — none carries a ground-truth
> health label — and all 26 informed the system's field-mode tolerances, so
> **held-out exposure is 0.000 hours**. This is a sanity result on real data,
> not a validated false-alarm rate.

Every figure in that paragraph regenerates from committed artifacts.

---

## 5. Residual stale references inside the repository

Documentation-only; no behavior implicated. Listed so they are not propagated
into the next external document.

| File | Line | Says | Actual |
|---|---|---|---|
| `README.md` | 37 | "full test suite (77 tests)" | 445 |
| `README.md` | 44 | "Simulated fault harness (77 tests, CI)" | 445 suite / 8 fault tests — and the label conflates the two |
| `docs/evidence/evidence_matrix.md` | 39 | C19 "77-test suite" at baseline `c13889f` | 62 at `c13889f`; 445 today |
| `docs/TRL_ASSESSMENT.md` | 23 | "62-test CI-gated suite" | 445 |
| `docs/TRANSITION_REPORT.md` | 67 | "62-test CI suite of behavioral contracts" | 445 (characterization is correct) |
| `docs/audit/CSIA_REPOSITORY_AUDIT.md` | 18-19, 55 | 62 | correct **as a record of its own baseline** — leave as historical |

**Recommendation:** stop writing the count in prose. Either drop the number
entirely ("CI-gated test suite") or generate it. A hand-maintained literal
that changes every commit will be wrong in every external document that
quotes it.

---

## 6. What this audit cannot determine

- **`SWORT_CSIA.pdf` has never been under version control.** No PDF appears
  anywhere in this repository's history (`git log --all --name-only` over
  `*.pdf` returns nothing). The only white-paper-like artifact tracked is
  `deliverables/HANDOFF_WHITEPAPER.md`, which is the **seeker** handoff,
  is labelled SYNTHETIC throughout, and contains neither claim.
- Therefore **the exact submitted wording cannot be diffed here.** The two
  sentences in section 0 are as quoted to me. The corrections in section 4
  address those sentences; any other claim in the PDF is unaudited.
- **CANNOT BE DETERMINED HERE:** which version was submitted, on what date,
  through which channel, and whether the submitted text differs from what is
  quoted above. Resolving that requires the submitted file.

**Required next step (human):** put the submitted PDF, or its source, under
version control alongside this audit. A claim that cannot be diffed against
the evidence base cannot be maintained. Every future external document should
be tracked in-repo so that a correction to the evidence mechanically flags the
documents that quote it.

---

## 7. Getting the corpus under version control

The derived evidence is already committed and hashed. The gap is the raw
corpus. Ranked by value:

1. **Hash what exists.** On any network-permitted machine:
   ```sh
   python tools/fetch_real_logs.py --no-run     # populate data/real_logs/
   python tools/build_dataset_manifest.py       # hash, dedup, classify
   ```
   This populates `content_sha256` for all 26 in
   `datasets/manifests/px4_public_v1.json`, makes exact-duplicate detection
   decisive, and settles the two near-duplicate candidates. **Commit the
   manifest, not the logs** — redistribution rights are `UNKNOWN` (provenance
   audit §5) and publicly viewable is not permission to republish.
2. **Recover the metadata.** Firmware (`ver_sw`), airframe (`SYS_AUTOSTART`),
   vehicle UUID (`sys_uuid`), flight modes and arming events are all in the
   ULog headers and are currently `UNKNOWN` for all 26. Until they exist,
   corpus diversity — the property that decides whether any false-alarm rate
   generalises — is unmeasured.
3. **DVC or equivalent** only after (1). Content-addressing without hashes
   accomplishes nothing; with hashes, the manifest already *is* the
   content-addressed index, and DVC would add a storage backend rather than
   new integrity.

Note the ordering consequence: **until step 1 runs, the 0.518 h figure rests
on an artifact whose inputs cannot be re-verified.** The arithmetic is
reproducible; the inputs are not. That is a materially weaker guarantee than
the rest of this repository's evidence, and it should be stated as such
wherever the figure appears.

---

## 8. Bottom line

Nothing was fabricated. Both figures were true, reproducible, and correctly
sourced on 2026-07-24.

The repository found the flaw in its own real-data claim on 2026-08-03,
corrected it, wrote down why, and enforced the new wording with a test. That
correction reached the README. It did not reach the document already in the
Army's hands.

The action required is a **correction through the submission channel**, not a
retraction: restate the test claim without scope inflation, restate the
exposure on the monitored denominator, and remove the word "validated" from
the flight-log sentence. Then track the document in-repo so this cannot
recur.
