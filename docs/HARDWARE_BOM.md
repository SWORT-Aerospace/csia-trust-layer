# CSIA Trust Layer — Validation Hardware BOM

**Baseline:** commit `c13889f` (v0.8.0). **Purpose:** exactly what to buy to
move CSIA from desktop-validated to target-hardware- and flight-validated,
for an Army xTech / SBIR transition, on a $500 ceiling.

> **Prices are 2026 approximate (USD) — verify at purchase.** I cannot query
> live retail prices; these are planning estimates. Part numbers are real and
> chosen for **representativeness to the SOW001 stack**, not lowest cost.

## Read this first — the honesty part (systems-engineering call)

You asked "cruise missile or drone." For a $500 component-level validation of
**this software**, the answer is unambiguous: **build a small multirotor UAV
surrogate, not a missile.**

- CSIA is a **platform-agnostic trust/diagnosis layer** — that is the
  repository's central, validated thesis (`csia/profiles.py`). The *same*
  trust core runs on a quad and on the synthetic seeker. So a $300–500 quad
  exercises the exact software path an interceptor would, at 1/1000th the
  cost and zero range-safety burden.
- A real cruise-missile / interceptor test article is **six figures, ITAR/
  range-controlled, and impossible to procure or fly on Amazon.** Attempting
  it would be unsafe, likely unlawful without a program of record, and buys
  no additional software evidence over the surrogate.
- The seeker/interceptor line stays where your whitepaper correctly puts it:
  **synthetic Monte Carlo now, HWIL later with a government/prime partner and
  GFI data.** No $500 purchase changes that; do not let a BOM imply otherwise.

So: the BOM below builds a **UAV surrogate that is representative of the
SOW001 flight stack**, which is exactly what raises the *software's* TRL and
is exactly what an xTech reviewer wants to see de-risked first.

Design choice that matters: the recommended flight controller uses the
**STM32H743** — the *same MCU family as the SOW001 FC* — and an
**ICM-42688-P IMU**, the *same IMU in the repo's sensor models*. This means
your bench work is representative, and you retain a path to eventually run the
native C core (`csia/native/`) on the **actual target MCU class**, not just
the Pi. That is a materially stronger TRL story than a generic FC.

---

## Tier 1 — Minimum ($150): embedded validation, no flight

Establishes the **target-compute** evidence (REQ-050/051/052) that is the
#1 thing blocking TRL 5. No autopilot, no flight — drive it with SITL or
replayed logs on the Pi.

| # | Item | Part | ~$ | Why / what it validates | TRL impact | Optional? |
|---|---|---|---|---|---|---|
| 1 | SBC (companion computer) | Raspberry Pi 5, 8 GB | 80 | Runs the CSIA advisory service; the SOW001 companion. Target for on-Pi latency + soak. | Embedded LOW→MOD; **required for TRL 5** | No |
| 2 | Active cooler | Official Pi 5 Active Cooler | 10 | Sustained load without thermal throttle → valid soak (REQ-052). | Enables valid endurance data | No |
| 3 | Storage | 64 GB A2 microSD (or NVMe HAT + 256 GB) | 12 | OS + logs. NVMe if you want realistic log-write throughput. | Reliability realism | No (SD ok) |
| 4 | PSU | Official 27 W USB-C | 12 | Stable power under CPU load; brownouts invalidate soak. | Valid measurements | No |
| 5 | Heatsinks/case | Basic case | 8 | Mechanical + airflow. | Minor | Yes |
| | **Tier 1 subtotal** | | **~122** | Runs `install_pi.sh`, `benchmark_pi.py`, `stress_pi.py` | | |

**What Tier 1 buys you:** REQ-050 (p99 tick latency on target), REQ-051
(native C build + 1e-12 parity on aarch64), REQ-052 (overnight soak). Fills
`latency_report_template.md` + `reliability_report_template.md`. Moves
embedded maturity LOW→MODERATE — the single highest-leverage spend.

---

## Tier 2 — Recommended ($300): + live autopilot integration (bench)

Adds a **real STM32H743 autopilot** so CSIA consumes genuine MAVLink: real
HEARTBEAT arm/disarm, real GPS_RAW_INT, real reboots, real link drops — on a
bench, no props.

| # | Item | Part | ~$ | Why / what it validates | TRL impact | Optional? |
|---|---|---|---|---|---|---|
| 6 | Flight controller | Matek H743-WING/SLIM (STM32H743 + ICM-42688-P) | 75 | **Exact MCU + IMU match to SOW001/repo.** Real HEARTBEAT→armed gating (REQ-014), reboot re-anchor (REQ-023), raw GPS vz path. | Validation MOD→HIGH; relevant-environment (partial) | No |
| 7 | GPS+compass | M10 GPS w/ QMC5883 (e.g. Matek M10-5883) | 25 | Real GPS_RAW_INT + mag → exercises the flagship spoof-detector path on live data. | Real-sensor evidence | No |
| 8 | Telemetry | SiK 915 MHz radio pair | 35 | Wireless MAVLink like a real GCS link; test link-drop reconnect (REQ-024). | Resilience evidence | Yes (USB-UART works on bench) |
| 9 | Wiring/adapters | USB-UART (CP2102), Dupont, JST | 20 | Bench harness FC↔Pi. | Enables integration | No |
| 10 | Bench power | 4S bench PSU or 1 LiPo + alarm | 15 | Power the FC/ESC bench-side. | Enables integration | No |
| | **Tier 2 subtotal (incl. Tier 1)** | | **~292** | Runs `csia run --source mavlink` on the Pi off a real FC | | |

**What Tier 2 adds:** live MAVLink integration on target compute — REQ-014,
023, 024 verified against a *real* autopilot instead of unit fixtures. This
is the "relevant environment (bench)" tier. Refreshes evidence C12/C13 intent
without waiting on flight. Do the SITL re-run here too (free, no hardware).

---

## Tier 3 — Ideal ($500): + advisory flight heritage

Adds a flyable airframe so you can log **one supervised advisory-only flight**
— the act that makes "flown in an advisory role" TRUE (REQ-053).

| # | Item | Part | ~$ | Why / what it validates | TRL impact | Optional? |
|---|---|---|---|---|---|---|
| 11 | Airframe kit | 5" freestyle frame + 4× 2207 motors + 45 A 4-in-1 ESC + props | 130 | Carries FC+Pi+GPS aloft. FC from Tier 2 mounts here. | Enables REQ-053 | No (for flight) |
| 12 | Battery ×2 | 4S 1300–1500 mAh LiPo | 40 | Flight power; 2 packs = a real sortie. | Enables flight | No |
| 13 | Charger | Basic 4S balance charger | 30 | Charge/store LiPos safely. | Safety/enabler | No |
| 14 | RC link | ELRS receiver (+ use existing/borrowed TX) | 20 | Safety-pilot manual control (advisory-only; CSIA commands nothing). | Range-safety | No |
| | **Trim to fit:** drop SiK (item 8, −35), use USB-UART bench + WiFi-to-Pi in flight logging to SD | | | | | |
| | **Tier 3 subtotal (incl. Tier 1+2, minus SiK)** | | **~477** | One advisory flight, `state.jsonl` recorded | | |

**What Tier 3 adds:** REQ-053 flight heritage. A quad is a valid CSIA test
article because the trust core is platform-agnostic; the flight exercises the
identical software an interceptor companion would run. After a clean flight
log, the README/whitepaper may honestly say **"flown in an advisory role
(N flights, X min, zero contained errors)."** That single sentence is worth
more to an xTech reviewer than any synthetic result.

> **Budget note:** $500 is tight for Pi 5 + H743 FC + full flying quad. The
> table hits ~$477 by dropping the SiK pair (bench-only telemetry + onboard
> SD logging in flight). If you already own an RC transmitter, LiPos, or a
> charger, reallocate that headroom to the NVMe HAT (better log throughput
> realism) or a second FC (keep one for destructive/edge testing).

---

## Recommended single purchase for the Army program ($500)

Buy **Tier 3** as specified. Rationale in one paragraph for the proposal file:
*A Raspberry Pi 5 companion running the CSIA advisory service, integrated over
MAVLink with a STM32H743/ICM-42688-P autopilot — the same MCU and IMU class as
the SOW001 flight stack — mounted on a 5" multirotor surrogate. This article
validates on-target real-time latency, endurance, live sensor integrity
monitoring, and advisory flight heritage for the platform-agnostic trust core,
while the interceptor-seeker application remains in synthetic/HWIL maturity
pending government-furnished seeker data. Total procurement < $500, COTS, no
ITAR-controlled components, no range assets required.*

## What NOT to buy (and why)
- **A "cruise missile" / rocket / seeker head:** not procurable on this
  budget, ITAR/range-controlled, and adds zero *software* evidence over the
  surrogate. The seeker line advances via HWIL with a partner, not hardware
  you buy.
- **A bigger drone / more sensors than the profile models:** representativeness
  beats scale. Match the profile (8 nodes, this FC/IMU), don't exceed it.
- **A DO-178C toolchain:** that is a funded qualification program, not a
  bench purchase, and not what raises TRL from 4 to 5.

## Traceability
This BOM maps directly to the open embedded requirements:
Tier 1 → REQ-050/051/052 · Tier 2 → REQ-014/023/024 (live) · Tier 3 → REQ-053.
Fill `docs/hardware_validation.md` gate sign-offs as each arrives.
