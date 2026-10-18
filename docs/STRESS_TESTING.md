# Stress testing the frozen core

**What it does:** composes simultaneous sensor degradations through the frozen
core's public API and measures detection, escalation, recovery and attribution.

**What it never does:** modify the frozen core. `csia/trust_engine`,
`csia/diagnosis`, `csia/runtime/online.py`, `csia/runtime/failsafe.py`,
`csia/scenarios.py` and `csia/profiles.py` are untouched. Every number below
was obtained by *calling* the core, never by adjusting it.

**And it transmits nothing.** A "GNSS-denied" profile is a `dropout` fault on a
simulated sensor. There is no jammer and no spoofing transmitter here.

---

## 1. Why a stress profile can lie, and what stops it

`Fault.__post_init__` rejects an unknown *kind*. `sample_streams` rejects an
unknown *target*. **Neither checks the pair.** Each sensor applies only the
kinds it implements and silently ignores the rest, so

```python
Fault("gps_spoof", "mag", 20.0, 10.0)     # accepted by every guard
```

changes nothing at all. Measured: of the 48 combinations the frozen core
accepts, **30 are inert and 18 are live**. Most syntactically valid faults do
nothing.

So profiles are validated against a matrix **derived by injection**, and one
containing an inert pair is refused at construction. A stress run cannot report
clean because it stressed nothing.

The matrix is **two-stage**, and it had to become so:

| stage | question | why it is not enough alone |
|---|---|---|
| stream | does the fault perturb the sampled sensor stream? | the runs consume an *event stream*, one layer downstream |
| transport | does the perturbation survive into the events the layer sees? | — |

One pair is live in the stream and inert after transport — `dropout` on the
vibration node (SR-002). It is **reported in every artifact**, not quietly
dropped: "this rig cannot deliver that fault" is something a reader of a stress
result needs to know.

## 2. Recovery is defined by the system, not by me

The tempting definition is "time until trust climbs back above *X*". Any *X* I
choose is a threshold I invented sitting next to a frozen core whose thresholds
are exactly what may not be retuned.

So recovery is read off the failsafe's own `NORMAL` state. `FailsafeConfig`
already defines what recovery means — `dwell_down = 5.0 s` of sustained health
— and **that dwell is inside the measured number, not subtracted from it**,
because that is when the aircraft actually gets its authority back.

Two defects in this instrument were found by running it, and both are fixed:

- Recovery was measured from the first return to `NORMAL` after the first
  *escalation*. For an intermittent GNSS profile that recovers between denial
  cycles, this reported **0.0 s** while the run was still being faulted 19 s
  later. It is now measured from the last fault clearing.
- A profile whose faults cleared 5 s before the flight ended was reported
  `NOT_RECOVERED`, when a recovery could not have been *observed* at all.
  Profiles that cannot answer their own recovery question are now refused at
  construction, and the runtime status `RECOVERY_WINDOW_TOO_SHORT` exists so
  the two can never be confused.

`NOT_DETECTED` is never folded into a pass. A profile that injects live faults
and never trips the failsafe is a finding.

## 3. The named catalog — measured

Ten profiles, all detected, all recovered.

| profile | peak | detect (s) | recover (s) |
|---|---|---|---|
| `msrd_gps_spoof_mag_drift_fast` | CAUTION | 2.84 | 2.84 |
| `msrd_gnss_denied_imu_drift` | CRITICAL | 1.04 | 1.24 |
| `msrd_power_and_structure` | CRITICAL | 6.08 | 8.04 |
| `msrd_four_class_cascade` | CRITICAL | 4.00 | 8.52 |
| `msrd_dual_imu_with_gnss_denied` | **EMERGENCY** | 1.04 | 6.76 |
| `env_gnss_denied` | CAUTION | 1.04 | 5.04 |
| `env_gnss_denied_intermittent` | CAUTION | 1.04 | 5.04 |
| `env_motor_thrust_loss` | CRITICAL | 4.28 | 12.00 |
| `env_prop_damage_vibration` | CRITICAL | 6.20 | 8.04 |
| `env_gnss_denied_fast_cruise` | CAUTION | 1.04 | 5.04 |

## 4. What attribution does under concurrent faults

Measured, not asserted as desirable:

- **A dropout is detected but never attributed.** Under GNSS denial the causal
  diagnosis reads `nominal` for 100% of the fault window while the failsafe
  escalates on validity. Confirmed against the **frozen** `gps_dropout`
  scenario through the stock runtime with none of this harness involved — so it
  is pre-existing and correct by design: a dropout supplies no inconsistency to
  diagnose.
- **Concurrent faults are not separately accused.** In the requested
  spoof + magnetometer-drift case the top-1 cause is `gps_fault` for 81% of the
  window and the magnetometer is *never* named. In the four-class cascade,
  three of four injected targets are named and `mag_interference` takes 79%.
- **Two of eight sensors cannot be named at all.** `LEGACY_CAUSE_SOURCE` has no
  label pointing at `baro` or `motor_esc`, so a fault on either is structurally
  unnameable however clearly the trust layer sees it. That is a property of the
  vocabulary, not a detection failure.

## 5. SR-001 — loss of data supervises one sensor in eight

The campaign's most substantive finding. `dropout` dominated the undetected
variations, and the minimal reproducer is unambiguous:

| faults (40 s of a 90 s flight) | freshness at t=30 s | failsafe peak |
|---|---|---|
| GPS dropout | `gps: False` | **CAUTION** |
| **both IMUs dropout** | `imu0: False, imu1: False` | **NORMAL** |
| battery + baro dropout | both `False` | NORMAL |
| mag + baro dropout | both `False` | NORMAL |
| vibration *anomaly* (bad data, control) | fresh | CRITICAL |

Freshness detection **works** — the sensors are correctly marked not fresh.
GPS has an explicit "GPS data invalid" rule; every other rule is gated on
`fresh.get(<sensor>)`, so a sensor that stops delivering is *removed from
supervision* rather than alarmed on. For attitude specifically,
`att = max((T[n] for n in imus), default=1.0)` returns **full confidence** when
neither IMU is fresh, making both attitude rules unreachable.

The exclusion is deliberate in origin and documented in the frozen source —
reasoning over a non-delivering sensor's frozen prior "produced phantom IMU
divergence alarms on real flight logs". That rationale is sound for
*trust-based* rules; it does not by itself supply a *loss-of-data* rule for the
other seven nodes, and GPS shows what one looks like. The pre-existing watchdog
test covers GPS only, so the asymmetry was never pinned.

**Not fixed. `failsafe.py` is frozen.** Four characterization tests pin it from
both sides, including a control showing the same sensors *do* escalate on bad
data as opposed to no data, so the day it changes the change is visible and
deliberate. CSIA is advisory with no command authority: this says what the
trust layer would raise, not what any vehicle would do.

## 6. What this is not

| | status |
|---|---|
| simulation against simulated sensors | **RUN** |
| software-in-the-loop (SITL) | **NOT RUN** — no autopilot is executed; ArduPilot is not installed here and could not be fetched |
| hardware-in-the-loop (HITL) | **NOT RUN** — E2 is blocked on physical hardware the user must supply |

Four phenomena requested of this layer have **no primitive** in the frozen
sensor model, and are recorded as declared gaps rather than approximated by the
nearest available signature:

| phenomenon | nearest available | why the nearest is not it |
|---|---|---|
| RF jamming *as RF* | `dropout` on gps | dropout is the observable end state of denial; it omits the degraded-but-present regime a jammer produces first — rising noise, falling satellite count, a fix still reported and increasingly wrong |
| urban-canyon multipath | `gps_spoof` | a spoof drift is monotonic and unbounded; multipath is bounded, oscillatory and geometry-dependent. **The detector that catches one need not catch the other** |
| control-surface flutter | `vibration_anomaly` | that is a prop/blade damage signature — amplitude growth plus a sub-harmonic. Flutter is a divergent structural mode with a different spectrum and time constant |
| high-throttle maneuvering | `fast_cruise` | high *speed*, not high *throttle*: no thrust model, no load factor, no control input, and its own catalog entry says aerodynamic drag is not modelled |

## 7. A thousand generated variations

Seeded, always multi-fault, drawn only from live pairs, and always given a
window long enough to answer their own recovery question. **1000 runs, 1695 s,
zero crashes.**

| | |
|---|---|
| detected | 783 |
| **not detected** | **217** |
| recovered (of those detected) | 783 — all of them |
| peak level | CAUTION 398, CRITICAL 343, EMERGENCY 42, NORMAL 217 |
| detection latency | min 1.04 s, p50 5.6 s, p95 23.5 s, max 45.7 s |
| recovery time | min 0.01 s, p50 0.44 s, p95 8.5 s, max 13.4 s |
| runs where a **nameable** target was never named | 813 |
| runs with a structurally unnameable target | 578 |

**The 217 undetected runs are not a pass, and they are not noise.** Grouping
them by fault composition shows they are dominated by `dropout` — the SR-001
asymmetry, at scale. The low recovery p50 is explained by the
`recovered_before_faults_cleared` flag: in a staggered profile the failsafe is
often already back at NORMAL when the last window closes, so that run's
recovery time is near zero and is *not* a measurement of how long recovery
took. The flag is recorded per run so those cases can be excluded rather than
read as instant recoveries.

## 8. The regression gate is exact, not tolerant

The campaign is **bit-for-bit deterministic** — fixed sensor seeds, a seeded
generator, a frozen core — verified by running it twice and comparing. So
`tools/xr/stress_regression.py` compares against its baseline **exactly**, with
no tolerance band, because a tolerance band is precisely where a behavioural
change hides.

Compared per profile: `escalated`, peak failsafe level, **detection latency**,
recovery status, **recovery time**, and which targets were named. Any
difference is listed with its before and after; nothing is aggregated away, so
two runs cannot swap outcomes behind a stable mean.

A baseline recorded under a different seed, count, or applicability matrix is
`NOT_COMPARABLE` and exits 2 — MX-015's rule again. Behaviour change exits 1.

```bash
python csia_stress/campaign.py --mode catalog --out research/stress/results/STRESS_CATALOG.json
python csia_stress/campaign.py --mode random --count 1000 --seed 20260907 --quiet
python tools/xr/stress_regression.py --check      # 200 runs, ~5m40s
python tools/xr/stress_regression.py --update     # deliberate re-baseline
pytest tests/test_stress_layer.py tests/test_stress_regression.py -q
```

It runs as a CI job (`stress`) and as three nightly stages. **A `CHANGED`
verdict is not automatically bad** — it may be an improvement, a harness
change, or a regression. Read the listed differences and re-baseline
deliberately if the new behaviour is the intended one.
