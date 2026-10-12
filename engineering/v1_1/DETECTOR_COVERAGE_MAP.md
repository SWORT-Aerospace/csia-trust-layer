# DETECTOR COVERAGE MAP

§27. Per mechanism: what evidence is required, which detector covers it, and
where the gap is. This is the basis for later validation and for the C port.

Measured on the deterministic catalogue. `censored` means **no response**, kept
as right-censored and never converted into a latency (§8).

| mechanism | required evidence | trust | sequential | freshness | diagnosis | gap |
|---|---|---|---|---|---|---|
| `CLEAN` | — | no transition | 0 alarms | n/a | nominal, evidence-backed | none |
| `GNSS_RAMP_SLOW` | slow position divergence | **32.48 s** | **24.40 s** | n/a | **never attributes** (0 correct-unique) | diagnosis blind to slow drift |
| `GNSS_RAMP_FAST` | fast position divergence | 24.36 s | **21.16 s** | n/a | 340 correct-unique | none |
| `GNSS_FIX_LOSS` | absence of fix | **26.00 s** | **censored** | primary | 200 safe-ambiguity | **sequential has none** |
| `IMU0_BIAS_DRIFT` | dual-IMU disagreement | **censored** | **censored** | n/a | 104 correct-unique | **no assurance transition by design** — single IMU is redundancy working |
| `DUAL_IMU_FAILURE` | both IMUs drift | **34.12 s** | **censored** | n/a | no correct hypothesis exists | **sequential has none** |
| `MAG_DEGRADED` | heading/field inconsistency | 30.04 s | **25.08 s** | n/a | 185 correct-unique | none |
| `POWER_SAG` | pack V + ESC RPM | 33.72 s | **30.12 s** | n/a | 126 correct-unique | none |
| `VIBRATION_ANOMALY` | vibration envelope | 34.16 s | **28.08 s** | n/a | 284 correct-unique | none |

Bold marks the earlier responder, or the sole responder.

## Sequential residual availability

In-control statistics exist for **`gps`, `mag`, `battery`, `motor_esc`,
`vibration`** — five nodes. `baro` is degenerate on the clean arm (σ₀ ≈ 0) and
carries no residual. **There is no per-IMU physics chi-square in this
construction**, so the sequential bank cannot see `imu0` or `imu1` at all.

## The two coverage facts that decide the architecture

1. **Sequential is earlier on every mechanism it covers** — by 3.20 s to
   8.08 s — and on `GNSS_RAMP_SLOW` it is the only thing that responds at all
   in useful time, because the diagnosis never attributes a slow drift.
2. **Trust is the only cover for `GNSS_FIX_LOSS` and `DUAL_IMU_FAILURE`.**
   Sequential is right-censored on both.

Neither can be deleted. Neither subsumes the other.

## `IMU0_BIAS_DRIFT` — why both are censored, and why that is correct

Neither arm produces an assurance transition. That is **not** a miss: the
failsafe policy's `att_caution` threshold is on `max(imu0, imu1)`, so a single
IMU degrading while the other holds is redundancy working as designed. The
diagnosis still attributes it correctly and identifiably on 104 ticks. The
right reading is "detected and named, no escalation warranted", not "missed".

## Rows with no coverage to map

`GNSS_STEP_SMALL`, `GNSS_STEP_LARGE`, `MAG_INVALID`, `BATTERY_SENTINEL`,
`BARO_FAULT`, `GNSS_TRANSPORT_STARVATION` — see
`MECHANISM_COVERAGE_MATRIX.csv` for the reason on each. In short: no step
injector exists in the frozen `KNOWN_KINDS`; the sentinel cases are
ingest-layer and were fixed and regression-tested in Phase 1; `baro` has no
fault kind and no residual; and `dropout` **is** transport starvation here, so
counting it twice would inflate the matrix.
