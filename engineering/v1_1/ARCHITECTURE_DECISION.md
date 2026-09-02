# ARCHITECTURE DECISION — v1.1

§21 requires exactly one choice. §29 requires components retained, components
removed, reasons, supporting scenarios, scenarios where a component has no
coverage, complexity consequences, and residual open questions.

Engineering only. No novelty language, and none is warranted.

---

## THE DECISION

    E:  TRUST_FLAT_PLUS_SEQUENTIAL

- **Neighbour-trust propagation: REMOVE** (subject to review — §30)
- **Trust recursion: KEEP**
- **Sequential (CUSUM) channels: KEEP**
- **Support-aware diagnosis: KEEP**
- **Relation topology and all 11 relations: KEEP**
- **UNKNOWN / unmodeled: remains NOT IMPLEMENTED**

Not "hybrid TBD". The measurements decide it.

---

## 1. WHY SEQUENTIAL IS KEPT (§20)

`T3 − T0` — adding sequential channels to flat trust — improves **5 of 9**
mechanisms and regresses **none**:

| mechanism | T0 trust-flat | T3 flat+seq | Δ |
|---|---:|---:|---:|
| `GNSS_RAMP_SLOW` | 32.48 s | **24.40 s** | **−8.08 s** |
| `VIBRATION_ANOMALY` | 34.16 s | **28.08 s** | **−6.08 s** |
| `MAG_DEGRADED` | 30.04 s | **25.08 s** | **−4.96 s** |
| `POWER_SAG` | 33.72 s | **30.12 s** | **−3.60 s** |
| `GNSS_RAMP_FAST` | 24.36 s | **21.16 s** | **−3.20 s** |
| `GNSS_FIX_LOSS` | 26.00 s | 26.00 s | 0.00 |
| `DUAL_IMU_FAILURE` | 34.12 s | 34.12 s | 0.00 |
| `IMU0_BIAS_DRIFT` | censored | censored | — |
| `CLEAN` | censored | censored | — |

**Zero clean violations**: 0 CUSUM alarms on the clean arm at `h = 500`, the
historical zero-clean-alarm condition reproduced.

On `GNSS_RAMP_SLOW` sequential is not merely faster — the **diagnosis never
attributes the slow drift at all** (0 correct-unique ticks across the window).
Without a sequential channel that mechanism is covered only by a late trust
transition.

## 2. WHY TRUST IS KEPT (§19)

Trust is **not** the same thing as neighbour-trust propagation, and it is the
only cover for two mechanisms:

| mechanism | trust | sequential |
|---|---:|---|
| `GNSS_FIX_LOSS` | **26.00 s** | **censored** |
| `DUAL_IMU_FAILURE` | **34.12 s** | **censored** |

The sequential bank has in-control statistics for `gps`, `mag`, `battery`,
`motor_esc`, `vibration` and **no per-IMU residual at all**. Deleting trust
because CUSUM wins on ramps would remove the only cover for the IMU family.

## 3. WHY NEIGHBOUR-TRUST PROPAGATION IS REMOVED (§18)

All four of §18's removal conditions hold.

| condition | result |
|---|---|
| no mechanism-level coverage benefit | **holds** — `T1 − T0` and `T4 − T3` identical on 8 of 9 |
| no correct-attribution benefit | **holds, structurally** — the frozen diagnosis never reads `TrustHistory.trust`, so it cannot affect attribution at all |
| no clean-behaviour improvement | **holds** — clean identical in both |
| no material assurance improvement | **holds** — and it is *worse* where it differs |

`T4 − T3`, the incremental value of propagation once sequential is present,
differs on **exactly one** mechanism:

    DUAL_IMU_FAILURE   T4 (graph) 34.40 s   vs   T3 (flat) 34.12 s

Propagation is **0.28 s later**. §18's tie-breaker — "especially if FLAT is
equal or earlier on all meaningful responses" — is satisfied outright.

§18 also says not to require statistical significance for deterministic
scenario comparisons, and none is claimed.

## 4. SCENARIOS WHERE EACH COMPONENT HAS NO COVERAGE

Stated plainly so the decision cannot be over-read:

- **Sequential:** no coverage on `GNSS_FIX_LOSS`, `IMU0_BIAS_DRIFT`,
  `DUAL_IMU_FAILURE`. Recorded as `NO_SEQUENTIAL_COVERAGE`, not as a miss.
- **Trust:** no assurance transition on `IMU0_BIAS_DRIFT` — correct, since
  `att_caution` is on `max(imu0, imu1)` and single-IMU degradation is
  redundancy working.
- **Diagnosis:** never attributes `GNSS_RAMP_SLOW`; no correct hypothesis
  exists for `DUAL_IMU_FAILURE` (single-fault model, two injected faults).
- **Neighbour-trust propagation:** no coverage benefit anywhere.

## 5. COMPLEXITY CONSEQUENCES (§22, §26)

Removing propagation deletes the inter-node read of `trust[]` inside the
neighbour weight. It does **not** delete `trust[]`, which is still computed
from α/β and still reported.

Mutable runtime state, unchanged by the decision except for the coupling:

| | floats | bytes |
|---|---:|---:|
| trust recursion (α, β) | 16 | 128 |
| trust carried between ticks for propagation | 8 | 64 |
| sequential CUSUM `S` per covered node | 5 | 40 |
| diagnosis smoothing per hypothesis | 8 | 64 |

Adding sequential costs **5 floats and one comparison per covered node per
tick**. That is the cheapest component in the system and it buys 3.2–8.1 s on
five mechanisms.

Where two architectures were functionally equivalent within the catalogue
(GRAPH vs FLAT on 8 of 9 mechanisms), §22's rule applies and the simpler one
wins: fewer cross-node dependencies, easier C equivalence, easier
verification.

## 6. SUPPORT-AWARE DIAGNOSIS SURVIVES EVERY ARM (§23)

Identical across all five arms — neither the graph nor the sequential channel
feeds the frozen diagnosis, so active evidence, discriminating evidence,
identifiability, ambiguity and prior sensitivity are the same objects
everywhere.

§11 is respected by construction: **a sequential alarm cannot convert an
unidentifiable cause into a unique attribution**, because the CUSUM output
never enters the diagnosis. On `GNSS_FIX_LOSS` the leader stays
`NON_IDENTIFIABLE / AMBIGUOUS` for 200 of 201 ticks in **every** arm,
including the ones where sequential is present. The sequential channel is
per-node and carries no cause-discriminating evidence, so it is not permitted
to promote a diagnosis, and it does not.

What v1 would have presented as an ordinary unique diagnosis, and v1.1 reports
as safe ambiguity:

| mechanism | ticks |
|---|---:|
| `GNSS_FIX_LOSS` | **200** |
| `CLEAN` | 76 — the startup window before GPS becomes fresh; initialisation, not a defect |

## 7. RESIDUAL OPEN QUESTIONS

1. **`OPEN_ENGINEERING_QUESTION`: would an established IMU change detector
   permit removing or simplifying the trust recursion?** Trust is retained
   *solely* because the sequential bank has no IMU residual. §28 forbids
   implementing one here. See `PHASE3C_FEASIBILITY_NOTE.md`.
2. **No GNSS step mechanism was tested** — no step injector exists in the
   frozen `KNOWN_KINDS`. The ramp results should not be read as covering steps.
3. **Deterministic simulation only.** No HIL, no real flight, no noisier trust
   trajectories where a 0.047 difference might cross a threshold.
4. **`UNKNOWN` remains unimplemented** (§24), pending a model-adequacy test.
