# CSIA Dataset Provenance Audit

**Baseline:** commit `5ad44d9` · **Date:** 2026-08-03 · **Slice:** 3A
**Method:** every figure was produced by executing repository code. Metadata
not present in a repository artifact is recorded as `UNKNOWN`. Nothing is
inferred.

---

## 0. Headline findings

| # | Finding | Severity |
|---|---|---|
| **D-01** | **Zero flight-hours are verified healthy.** All 26 logs are unannotated. The repository described them as "24/26 flights alarm-free" in a validation table headed *healthy* — absence of a CSIA alert was being used as evidence of health, which is the hypothesis under test. | **HIGH** |
| **D-02** | **The alert-rate denominator included time in which no alert can be raised.** 21.8% of recorded duration lies inside `arm_time` (20 s, offline posture). Corrected rate is **3.86/h**, not 3.02/h. | **HIGH** |
| **D-03** | **No log is eligible for held-out or blind evaluation.** All 26 were inspected while `field_mode` tolerances and the offline failsafe posture were developed. Held-out evaluation exposure is **0.000 h**. | **HIGH** |
| **D-04** | **The corpus is not present in the repository and cannot be re-acquired here.** `review.px4.io` is denied by this environment's network policy (proxy returned 403 to CONNECT). Content hashes are therefore `null`, and exact-duplicate detection cannot run on content. | **MEDIUM** |
| **D-05** | **No firmware, airframe, or vehicle metadata exists** for any log. Diversity of the corpus is unmeasurable. | **MEDIUM** |
| **D-06** | 7 of 26 logs are shorter than 40 s, contributing under 20 s of monitored time each. 2 near-duplicate candidates share exact durations. | **MEDIUM** |

---

## 1. Data sources

### 1.1 `px4_public_v1` — public PX4 Flight Review logs

| Property | Value |
|---|---|
| Physical location | `data/real_logs/` — **empty in this environment** (gitignored) |
| Source | `https://review.px4.io/download_log?log=<uuid>` |
| Acquisition method | `tools/fetch_real_logs.py`, UUIDs read from `data/real_logs_report.json` |
| Files | 26 referenced, **0 present** |
| Total apparent duration | 2385.9 s = **0.6627 h** raw; **0.5183 h** monitored |
| Hash status | **`null` for all 26** — content unavailable, not invented |
| Annotation status | `UNANNOTATED` (26/26) |
| Health label | `UNANNOTATED` (26/26). `VERIFIED_HEALTHY`: **0** |
| Autopilot | PX4 (26/26, from the source service) |
| Firmware version | `UNKNOWN` (26/26) |
| Aircraft type | `UNKNOWN` (26/26) |
| Sensor availability | 2–5 of 8 trust-graph nodes carried usable data |
| Missing channels | recorded per log in `excluded_channels` |
| Redistribution rights | **`UNKNOWN`** — publicly viewable is not permission to redistribute |
| Confidentiality | `PUBLIC` |
| Influenced thresholds | **Yes — all 26** |
| Influenced architecture | **Yes — all 26** (`field_mode` exists because of these logs) |
| Eligible for held-out eval | **No — 0 of 26** |
| Duplication risk | 2 near-duplicate candidates (duration collisions at 50.0 s and 35.4 s) |
| Known parsing failures | none recorded in the committed artifact |

### 1.2 `csia_sim_v1` — simulation replays

`data/replay/*.json`, 9 scenarios, regenerated deterministically by
`csia build` from fixed seeds. **Not flight exposure.** Simulated time must
never be added to real-flight hours; the exposure module counts only
`source_type=REAL_FLIGHT`.

### 1.3 Campaign artifacts

`campaigns/bench.json`, `campaigns/monte_carlo.json`,
`deliverables/montecarlo_results.*` — derived artifacts, regenerated from
fixed seeds, `SIMULATION` evidence environment. `campaigns/perf_*.json` are
host benchmarks.

### 1.4 ArduPilot

**No support.** `csia/runtime/ulog_source.py` reads PX4 ULog only. No
DataFlash parser exists. Recorded as a gap, not a plan.

---

## 2. Answers to the ten required questions

| # | Question | Answer |
|---|---|---|
| 1 | Unique real flight logs | **26** referenced (by UUID); 0 present locally |
| 2 | Usable | **26** parsed in the committed campaign, all degraded (2–5 of 8 nodes) |
| 3 | Exact / near duplicates | **0 exact** (undecidable without content); **2 near-duplicate candidate pairs** |
| 4 | Verified-healthy hours | **0.000** |
| 5 | Unannotated hours | **0.5183** monitored (0.6627 raw) |
| 6 | Known-fault / anomaly hours | **0.000** — no annotations exist |
| 7 | Logs that influenced design or thresholds | **26 of 26** |
| 8 | Legitimately held-out | **0 of 26** |
| 9 | Corrected rate by category | UNANNOTATED: 2 episodes / 0.5183 h = **3.86/h, 95% CI [0.47, 13.94]**. VERIFIED_HEALTHY: no exposure |
| 10 | Additional exposure required | See `docs/validation/EXPOSURE_PRECISION_PLAN.md` — ~3 h zero-event to bound below 1/h; ~30 h to bound below 0.1/h |

---

## 3. Acquisition status

**Acquisition was attempted and failed for environmental reasons, not
repository ones.**

```
$ curl https://review.px4.io/download_log?log=62522f3a-...
curl: (56) CONNECT tunnel failed, response 403
$ curl "$HTTPS_PROXY/__agentproxy/status"
  "recentRelayFailures": [{ "kind": "connect_rejected",
    "detail": "gateway answered 403 to CONNECT (policy denial ...)",
    "host": "review.px4.io:443" }]
```

The ingestion path was therefore built and tested against the committed
campaign artifact. **No acquisition success is claimed.** The exact backlog is
`datasets/reports/acquisition_backlog.json` — 26 UUIDs with source URLs, ready
to run unmodified on a network-permitted machine:

```sh
python tools/fetch_real_logs.py --no-run     # populate data/real_logs/
python tools/build_dataset_manifest.py       # hash, dedup, classify, account
```

On that run, `content_sha256` populates, exact-duplicate detection becomes
decisive, and near-duplicate candidates can be confirmed or dismissed.

---

## 4. Metadata that must be captured on acquisition

Currently `UNKNOWN` for all 26 and obtainable from the ULog headers once the
files exist: firmware version (`ver_sw`), airframe type (`SYS_AUTOSTART`),
vehicle UUID (`sys_uuid`), flight mode history, and arming events. Until then,
corpus diversity — the thing that determines whether a false-alarm rate
generalises — is **unmeasured**.

---

## 5. Redistribution

Marked `UNKNOWN` for all 26, deliberately. The logs are publicly viewable on
PX4 Flight Review; that is not a grant of redistribution rights, and no
per-log licence was recorded at acquisition. **Do not republish these files**
in any public artifact until per-log terms are established. Derived
statistics are unaffected.
