# XSYS-001-A2 — results of the corrected C4 on fresh nominal pilots

**Every gate passes.** Every acceptance gate of the corrected design holds on
fresh, nominal-only validation data:

- C1, C2, C3 and C5 as established by A1;
- fresh C1 and fresh C5;
- C4-A2 and the evidence-signal gate EV-A2.

The rule was specified, and its code committed, before any of these data
existed (`4f3378f`, `docs/research/XSYS_001_A2_C4_CORRECTION.md`). **No
confirmatory flight was flown, and running the confirmatory campaign is not
authorized by this amendment.**

| | |
|---|---|
| chain | XSYS-001 `868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b` → XSYS-001-A1 `55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b` → XSYS-001-A2 (`research/xsys_confirmatory_001/amendment_a2/FREEZE_MANIFEST_A2.sha256`). Both earlier stages are unchanged |
| A1 | still NOT ACCEPTED. Its C4 failed and stays failed. Its executor still refuses to fly |
| results file | `research/xsys_confirmatory_001/amendment_a2/C4_A2_RESULTS.json` |
| pilots | `research/xsys_confirmatory_001/amendment_a2/pilot_logs/` (10 logs, `SHA256SUMS`) |
| confirmatory flights / analysis trials | **0 / 0** |

## 1. What was run

Ten fresh nominal-only pilots were flown, exactly as frozen in
`research/xsys_confirmatory_001/amendment_a2/PILOT_MATRIX_A2.csv`. All ran
with η = 1.00, no fault, no corruption and no CSIA scoring. The stopping
rule held:

- the flights ran in matrix order;
- every flight completed on its first attempt;
- nothing was evaluated before the last flight;
- the frozen `research/xsys_confirmatory_001/amendment_a2/analyze_a2.py` was
  then run once.

The flights:

| role | flights | construction |
|---|---|---|
| independent reference | R1 (8.182°), R2 (188.182°) | long nominal hovers; 30 spans of 20 s at onsets arm + 20 s + 25 s·k |
| candidate | D1–D8 at A1 slots 0, 1, 2, 3, 5, 7, 9, 10 | flown exactly as the A1 25 s segmentation schedules a condition (pre-arm dwell, onset = arm + 20 s) |

**Reference pairs.** There were 420 valid pairs: within each hover and
across the two, all with onsets ≥ 25 s apart. **None** was excluded by C1.
**Candidate pairs:** all 28.

## 2. Reference and candidate |r| distributions

Preprocessing was identical for both: the frozen A1 `trajectory_corr` over
[t0 − 5, t0 + 15).

| signal | reference mean \|r\| (median, p95, max) | candidate mean \|r\| (median, max) |
|---|---|---|
| gyro projection (W_DYN input) | 0.038 (0.030, 0.095, 0.144) | 0.039 (0.029, 0.104) |
| κ₀ (W_CTRL input) | 0.018 (0.015, 0.042, 0.066) | 0.021 (0.017, 0.060) |
| ρ₀ (W_RPM input) | 0.021 (0.018, 0.052, 0.082) | 0.020 (0.019, 0.056) |
| true roll rate | 0.106 (0.086, 0.256, 0.478) | 0.083 (0.065, 0.340) |
| true pitch rate | 0.101 (0.082, 0.245, 0.384) | 0.104 (0.077, 0.323) |

The candidate conditions are as correlated as independent nominal spans of
the same aircraft, and no more. The true pitch rate again exceeded the
old absolute limit of 0.1 in several candidate pairs (max 0.323). The
independent reference does the same, which is why A1's criterion was the
wrong test.

## 3. The gates

**C4-A2.** For each signal, Δ = candidate mean |r| − reference mean |r|, and
U95 is its one-sided 95% bootstrap bound. The bootstrap used 20000
replicates, seed 20260927, and discarded none.

| signal | Δ | U95 | margin | result |
|---|---|---|---|---|
| gyro projection | 0.0002 | 0.022 | 0.10 | pass |
| κ₀ | 0.0031 | 0.011 | 0.10 | pass |
| ρ₀ | −0.0011 | 0.007 | 0.10 | pass |
| true roll rate | −0.0224 | 0.012 | 0.10 | pass |
| true pitch rate | 0.0030 | 0.051 | 0.10 | pass |

**C4-A2: PASS**, with all five signals passing.

**EV-A2** (hard gate on the evidence inputs):

| evidence signal | U95 (limit 0.05) | max candidate \|r\| (cap 0.20) | result |
|---|---|---|---|
| gyro projection | 0.022 | 0.104 | pass |
| κ₀ | 0.011 | 0.060 | pass |
| ρ₀ | 0.007 | 0.056 | pass |

**EV-A2: PASS.**

**The remaining gates:**

| gate | source | result |
|---|---|---|
| C1 | A1 | PASS (max I 0.00079) |
| C1, fresh, unchanged | 28 candidate pairs | **PASS** (max I 0.00059 ≤ 0.001) |
| C2 | A1 | PASS (S = 25 s ≥ 20.332 s) |
| C3 | A1 | PASS (worst −0.075) |
| C3, fresh, descriptive | R1, R2 | worst 0.077 and 0.074, both within 0.1 |
| C5 | A1 | PASS |
| C5, fresh, unchanged | all 10 flights | **PASS**. Every null statistic is below its threshold; the closest is R2's \|D_T1\| max of 0.0210 against 0.0246. Heading error ≤ 0.60° |

**Decision recorded by the frozen code:** `C1 C2 C3 C4-A2 C5 ALL PASS (guard tests still required)`.

## 4. What this makes executable, and what it does not

- **Run parameters.** The confirmatory matrix and order are A1's,
  unchanged: 66 flights, 121 analysis trials, 11 conditions on disjoint
  noise segments. So are every threshold, window, hypothesis, endpoint and
  decision rule.
- **Executor.**
  `research/xsys_confirmatory_001/amendment_a2/execution_a2/run_confirmatory_a2.py`
  verifies the XSYS-001, A1 and A2 manifests. It flies only because
  `C4_A2_RESULTS.json` records that every gate passed.
- **Stages.** Stage 0 and stage 2 run through the unchanged A1 wrappers with
  `--freeze-manifest` set to the A2 manifest. Stage 1 runs frozen with the
  same manifest.
- **Data location.** Campaign data must be written **outside**
  `research/xsys_confirmatory_001/`. The XSYS-001 guard binds any campaign
  there to the XSYS-001 manifest. The A1 and A2 guards reject campaigns under
  a manifest that does not allow execution.
- **Authorization.** This amendment authorized validation only. The
  confirmatory campaign needs a further grant.

## 5. Validation

`research/xsys_confirmatory_001/amendment_a2/post_freeze_check_a2.py` writes
`research/xsys_confirmatory_001/amendment_a2/POST_FREEZE_CHECK_A2.json`. It
checks:

- XSYS-001, A1 and their manifests are unchanged;
- A2 is frozen;
- C1, C2, C3 and C5 are unchanged;
- the confirmatory matrix and order are unchanged;
- η, thresholds, windows, hypotheses, primary endpoint, zero-WRONG, v2 and
  the PX4 patch are unchanged;
- confirmatory flights and analysis trials are 0;
- the executor's dry run lists the 66 flights in A1 order, and its gate
  matches the decision;
- tampering is detected;
- all three guard tests pass.
