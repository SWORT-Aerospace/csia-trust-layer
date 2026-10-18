# CUSUM into CSIA: the template for a mature detector

**2026-09-30. Parts 30 and 43 of the shadow-validation brief. No CUSUM is
implemented here.**

**The repository already has one** (V4):
- **the detector:** `csia/v1_1/sequential.py`, `CusumBank`. This is Page's
  one-sided CUSUM with k = 0.5 and h = 500, frozen with v1.1;
- **how v2 reads it:** v2 reads its alarms from the v1.1 payload
  (`csia/v2/ingest.py`, `sequential_alarming`), and **rejects a payload whose
  k and h differ from the frozen detector's** (ingest.py lines 180-187).

That rejection is an evidence contract in miniature: a producer version check
at the interface. This example generalises it.

## 1. The path

```
raw measurement      z_t = (lambda_t - mu0) / sigma0 for one node
                     (lambda: the smoothed chi-square the layer computes)
      |
CUSUM                S_t = max(0, S_{t-1} + z_t - k); alarm when S_t > h
      |
change statistic     S_t, alarm flag, time of the last reset, the samples
and alarm            counted since, and whether any sample was gated out
      |
adapter              one EvidenceRecord per node:
                     - observation_state: VIOLATED on alarm, NOMINAL when in
                       control after enough samples, UNAVAILABLE when gated,
                       stale or not yet warmed up;
                     - sequential_state: S_t, k, h and the reset time;
                     - dependencies and lineage: the node's source;
                     - provenance: producer id and version
      |
CSIA evidence        the record joins the tick's evidence index
      |
admissibility and    (future layer) admitted only if: the producer's k and h
relevance            match its contract; the content is within its validity (no
                     estimator reset or sensor re-selection since the last
                     CUSUM reset); its lineage is known. Relevant only to the
                     hypotheses its claim names
      |
hypothesis           2.1 localization: a predicate built on the record
reasoning            confirms or refutes the hypotheses the contract names
```

## 2. What CUSUM knows and what CSIA knows

| | CUSUM knows | CSIA knows |
|---|---|---|
| what happened | "the mean of this standardised residual has shifted upward by more than about k·σ, with evidence accumulated past h" | which **hypotheses** that shift supports or refutes, according to the declared signature, for example "a gps-node shift is consistent with SENSOR/navigation_source_invalid and inconsistent with a purely COMPUTE cause" |
| why | nothing. It is a statistic about a sequence | nothing beyond the declared model either. CSIA does not know *why* either; it keeps the candidate set honest |
| whether it is current | how many samples it has accumulated since its last reset | whether the configuration the statistic was accumulated under **still holds**: an estimator reset, a lane switch or a sensor re-selection since the last reset makes the accumulated sum describe a system that no longer exists (L4; `CONFIGURATION_TRANSITION_STUDY.md`) |
| whether it is independent | nothing | whether another admitted record shares its source lineage: a threshold detector on the same node is **not** a second confirmation (`DEPENDENCY_METADATA_PREVIEW.md`, cases 1, 3 and 5) |
| whether it is enough | its false-alarm and detection-delay trade-off, set by k and h (Page; Lorden's minimax result, V0) | whether it is enough for **attribution**. One confirmed shift on one node does not exclude a declared alternative. C1 still needs every declared alternative affirmatively nominal, and F2 still needs the localization not to retain another domain |
| its own health | nothing about itself: a CUSUM fed a frozen input reads "in control" forever | the producer-health rule: a CUSUM whose input is stale reports UNAVAILABLE, never NOMINAL (the `GATING` rule the existing bank already applies to stale samples) |
| coverage | only the nodes it has an in-control model for | what it cannot see. The existing bank has **no** IMU statistic (sequential.py docstring), so its silence says nothing about imu0 or imu1. CSIA must read that as UNKNOWN, not NOMINAL (C2) |

## 3. The contract for this producer

The fields are those of `DEPENDENCY_METADATA_PREVIEW.md` §5.

| field | value for the existing bank |
|---|---|
| producer_id, version | `cusum@<node>`, `v1_1.sequential` with k 0.5 and h 500 (the ingest already enforces these) |
| claim | "upward mean shift of the node's standardised chi-square residual" |
| supports / refutes | per node, from the signature matrix. Never implies a cause on its own |
| source_lineage | {node source}, plus the smoothing model that produces lambda |
| operating_regime | the in-control statistics (mu0, sigma0) were estimated on the clean nominal arm. Outside that regime the false-alarm rate is unknown |
| validity | invalidated by a reset of the node's upstream estimator or a re-selection of the node's sensor. No maximum age while samples keep arriving |
| update_rate | the layer's tick rate; gated samples do not count |
| health | UNAVAILABLE while gated, stale or warming up |
| coverage declaration | gps, mag, battery, motor_esc, vibration. **Not** imu0, imu1 or baro |

## 4. What CSIA adds, and what it must not re-do

**What CSIA adds:**
- hypothesis bookkeeping across domains;
- relevance (which alternatives a CUSUM alarm bears on);
- admissibility across configuration changes;
- the refusal to count a second detector on the same source as
  corroboration;
- a trace that says which of these decided the outcome.

**What CSIA must not re-do.** Tuning k and h, estimating the in-control
model, or choosing between CUSUM, GLR and SPRT. Those belong to the detection
literature and to the producer (`METHOD_REUSE_MAP.md`, `ANTI_ROADMAP.md`).

**The template for any mature detector.**
1. Keep the detector's statistic and its own guarantees.
2. Write down its claim, its lineage, its regime and its invalidating events.
3. Let CSIA decide relevance and admissibility.
4. Never let CSIA reinterpret the statistic.
