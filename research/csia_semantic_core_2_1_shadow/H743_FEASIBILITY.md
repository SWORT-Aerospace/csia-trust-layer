# H743 feasibility of a C implementation of 2.1

**2026-09-30. Part 28 of the shadow-validation brief.**

**No hardware readiness is claimed.** No STM32H743 build, toolchain or
measurement exists in this repository
(`docs/embedded/NATIVE_RUNTIME_STATUS.md`).

Every figure below is labelled **MEASURED**, **ESTIMATED** or **UNKNOWN**.
MEASURED means measured on a desktop, never on the target.

## 1. What is measured, and where

| quantity | value | class | source |
|---|---|---|---|
| v1 C trust kernel, host | about 247 ns/tick | MEASURED (x86-64 host, `-O2`) | NATIVE_RUNTIME_STATUS.md |
| v2.0 reasoning (localize + attribute), CPython | median 210 µs, p99 554 µs, max 722 µs per tick | MEASURED (desktop CPython) | `SHADOW_RUNTIME.json` |
| 2.1 reasoning, trace off, CPython | median 547 µs, p99 1,090 µs, max 1,550 µs | MEASURED (desktop CPython) | same |
| 2.1 reasoning, trace on, CPython | median 630 µs, p99 1,441 µs, max 2,086 µs | MEASURED (desktop CPython) | same |
| 2.1 per-tick workload | at most 68 records, 5 localizations, 39 predicate evaluations, 64 evidence rows read | MEASURED (dataset A) | same |
| STM32H743 core and memory | Cortex-M7 at 480 MHz, about 1 MB SRAM, 2 MB flash | datasheet figures, not verified here (V0) | `research/csia_usefulness_architecture/08_PERFORMANCE_SAFETY_BOUNDARY.md` |

**CPython time says nothing about C time.** It is dominated by interpreter
overhead, object allocation and dictionary lookups. None of these exists in a
fixed-struct C port.

## 2. Estimate

The operation count comes from the measured workload (`C_RUNTIME_DELTA.md`
§3): about 5,000-10,000 simple operations per tick at 68 records, bounded
and linear.

**Assumptions** (ESTIMATED): 1-2 cycles per simple operation on a Cortex-M7,
times a 3-10 factor for branches, memory latency and bitset bookkeeping. That
gives about 15,000-200,000 cycles per tick, or **about 30-400 µs per tick at
480 MHz**. The upper end assumes the pessimistic factor at the pessimistic
count and code running from flash without cache hits.

| rate | tick budget | 2.1 estimate as a share of the budget | plausibility |
|---|---|---|---|
| 25 Hz | 40 ms | 0.1-1.0 % | plausible |
| 50 Hz | 20 ms | 0.2-2.0 % | plausible |
| 100 Hz | 10 ms | 0.3-4.0 % | plausible |
| 200 Hz | 5 ms | 0.6-8.0 % | plausible for the reasoning core; the upper end would matter on a busy flight controller |

**Memory** (ESTIMATED, from `C_RUNTIME_DELTA.md`): about 12-13 KB RAM and
about 20-40 KB flash. Both are small against the datasheet figures.

**Why 2.1 does not change the picture relative to v2.0.**
- **In desktop CPython, 2.1 costs 2.6× v2.0 (trace off).** The extra work is
  linear in the records (C6, the C4 wrapper, C1's walk, F2).
- **Record scaling is superlinear for both engines, and 2.1 is not the
  worse.** Padding the largest tick with renamed copies of its own records,
  up to 32× (2,176 records), gave log-log slopes of 1.44 for v2.0 and 1.31
  (trace off) / 1.35 (trace on) for 2.1.
  - **What drives it:** copies of real relations lengthen every per-relation
    list, which several frozen predicates and the attribution scan.
  - **The earlier Phase I measurement differs because it measured something
    else.** It padded with *unconnected* records and found slopes near 1.0.
  - **The ratio falls with size:** 2.1 at 5.0× v2.0 at 68 records, 3.7× at
    2,176.
  - **What it means for a port:** a hard record cap of about 128 keeps the
    worst case bounded.

## 3. What is UNKNOWN, and decides the answer

| unknown | why it matters | how it becomes known |
|---|---|---|
| WCET on the target | the only number an integrator can budget against | port step 8: a target build, instrumented |
| cache and memory placement (ITCM/DTCM against flash and AXI SRAM) | can move the estimate by the full 3-10 factor | the same build |
| interrupt and scheduler contention | CSIA runs beside the flight stack | a HIL measurement under a representative load |
| **the cost of producing the evidence** | adapters from uORB topics to records, and producers such as CUSUM and estimator summaries. Probably larger than the reasoning core | port step 0 (`C_RUNTIME_DELTA.md` §4), measured separately |
| the double-precision cost, if kept | the v1 core uses `double`; the M7 FPU has reduced double throughput (NATIVE_RUNTIME_STATUS.md) | 2.1's decision logic is categorical and needs no floating point beyond the producers |

## 4. Answer

**A C implementation of the 2.1 reasoning core is plausible at 25, 50, 100
and 200 Hz on an H743-class target, as an ESTIMATE.**
- **What stands behind it:** a measured, bounded and small per-tick workload,
  a design that is fixed-size and allocation-free, and no subset search.
- **What is missing:** every target number is UNKNOWN until a build exists.
- **What is not claimed:** hardware readiness.

**The shadow runner is not a candidate for the target.**
- **Its cost:** median 2.4 ms per tick on the desktop, 12.5× v2.0 alone,
  dominated by hashing the tick's evidence and building the comparison
  record.
- **Where it belongs:** SITL, replay and ground tools.
