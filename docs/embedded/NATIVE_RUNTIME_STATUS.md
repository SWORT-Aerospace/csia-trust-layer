# Native Runtime Status

**Purpose:** state precisely which CSIA implementation executes in which
context, so no external-facing document implies native execution that does not
occur. **Date:** 2026-08-03 · **Baseline:** commit `944134f`
**Audience:** external technical review, due diligence, customer engineering.

---

## Statement of record

> CSIA currently operates through its Python online runtime. A native C
> implementation of selected trust-core functionality exists and is
> parity-tested against the Python implementation over the production trust
> graph. Host execution measurements demonstrate implementation efficiency but
> do **not** constitute measured STM32H7 runtime performance, and do **not**
> constitute evidence that the complete production runtime currently executes
> natively.

This wording is the approved form for external use. Do not paraphrase it into
a stronger claim.

---

## What runs where

| Context | Implementation that executes | Verified by |
|---|---|---|
| `csia run`, `csia service`, `deploy/` systemd unit | **Python** `TrustCore` via `OnlineTrustLayer` | `csia/runtime/online.py` imports no native module |
| `csia build`, `csia report`, dashboard replay | **Python** `TrustCore` via `TrustEngine.run` | `csia/trust_engine/engine.py` imports no native module |
| `tests/test_native.py` | **C**, through ctypes, compared against Python | parity assertions to 1e-12 |
| STM32H743 flight controller | **nothing yet** — no target build, no target measurement | — |

**The C core is not on any production execution path.** It is a
parity-pinned reference implementation and the intended deployment path.

## Scope of parity verification

| Property | Status |
|---|---|
| Trust step, 4 nodes / 3 edges | Verified, 500 randomized steps, 1e-12 |
| Trust step, **production 8 nodes / 11 edges** | **Verified**, 300 randomized steps, 1e-12 (added 2026-08-03; previously untested) |
| No-evidence branch parity | Verified |
| Diagnosis step parity | Verified |
| Invalid-input rejection | Verified — 29 negative cases under ASan + UBSan |
| Long-duration numerical drift | **Not verified** |
| Fixed-point / reduced-precision behaviour | **Not applicable** — implementation is `double`; STM32H743 has a double-precision FPU but at reduced throughput vs single |

## Performance claims — what each number is

| Figure | Class | Meaning |
|---|---|---|
| trust kernel ≈ 247 ns/tick, diagnosis ≈ 427 ns/tick | **Host benchmark** | x86-64 desktop, C compiled `-O2`. Not the running system; not target hardware. |
| ≈ 85 µs/tick "trust core" | **Host benchmark, Python** | The implementation that actually runs. Also currently includes replay marshalling (audit F-08). |
| "≈ 7–15 µs on STM32H743" | **Estimate** | Extrapolation from host timing. No target measurement exists. |
| "≈ 0.04 % FC CPU at 25 Hz" | **Estimate derived from an estimate** | Do not present as measured. |

Required labelling for any performance figure: **host benchmark**,
**simulated target estimate**, **measured target result**, or
**conservatively bounded target result**. Only the first two exist today.

## Safety properties of the C core

Verified: no dynamic allocation; no recursion; all loops bounded by validated
counts; fixed-size stack scratch (`CSIA_MAX_NODES` 64, `CSIA_MAX_CAUSES` 32,
`CSIA_MAX_EDGES` 512); no global mutable state; caller owns all state.
Compiles clean under `-std=c11 -Wall -Wextra -Wpedantic -Werror`.

Input validation occurs **before any state mutation**, so a rejected tick
leaves `alpha`/`beta`/`trust` and all output buffers untouched. Status codes:

| Code | Value | Condition |
|---|---|---|
| `CSIA_OK` | 0 | success |
| `CSIA_ERR_NODES` | −1 | `n` outside `[0, CSIA_MAX_NODES]` |
| `CSIA_ERR_EDGES` | −2 | `m` outside `[0, CSIA_MAX_EDGES]` |
| `CSIA_ERR_EDGE_INDEX` | −3 | an edge endpoint outside `[0, n)` |
| `CSIA_ERR_NULL` | −4 | a required pointer is NULL |
| `CSIA_ERR_CAUSES` | −5 | `nc`/`nf` out of bounds |

**Backward compatibility:** the previous contract was 0 on success and −1 on a
rejected count. Every rejection remains `< 0`, so callers testing `rc != 0` or
`rc < 0` are unaffected. No signature changed; no migration required.

## Open gaps before any native-execution claim

1. No STM32H743 build, toolchain, or linker configuration in-repo.
2. No target-hardware measurement of any kind (WCET, stack high-water, flash/RAM).
3. The C core is not wired into `OnlineTrustLayer`; doing so requires a
   parity-asserting integration path and a rollback flag.
4. Long-duration numerical-drift equivalence unverified.
5. No scheduler, interrupt-contention, or watchdog behaviour characterised.

Until 1–3 close, external material must not describe CSIA as running natively
or as measured on flight hardware.
