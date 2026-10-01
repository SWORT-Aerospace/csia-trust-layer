# H743 feasibility, updated for R-1, R-2 and R-3 (Phase 16)

**2026-10-01.** This updates `research/csia_semantic_core_2_1_shadow/H743_FEASIBILITY.md`,
which is not edited.

**No hardware readiness is claimed:**
- no STM32H743 build, toolchain or measurement exists in this repository
  (`docs/embedded/NATIVE_RUNTIME_STATUS.md`);
- the C runtime does not implement v2.0 or 2.1 (`C_RUNTIME_DELTA_UPDATE.md`).

**Every figure carries one of three labels, kept apart:**
- **MEASURED (desktop CPython):** measured here, on a desktop, never on the
  target;
- **ESTIMATED (C):** derived from those measurements and from operation
  counts;
- **UNKNOWN (H743):** needs a target build.

## 1. What changed, MEASURED (desktop CPython)

Source: `RUNTIME_REVISION.json`, dataset A, 2,640 ticks, three passes.

| quantity | 2.1.0 | 2.1.1 + r2 | change |
|---|---|---|---|
| reasoning, trace off, median / p99 / worst | 554 / 1,143 / 1,690 µs | 626 / 1,300 / 2,057 µs | +13 % median |
| reasoning, trace on, median / p99 / worst | 596 / 1,450 / 1,896 µs | 640 / 1,722 / 2,533 µs | +7 % median |
| peak memory, largest tick | 24.0 KB | 26.1 KB | +2.1 KB |
| record-scaling slope (trace off) | 1.12 | 1.09 | none |
| fault-policy cost (one predicate failed) | — | 0.99× | none |
| epoch check, 68 stamped records, all current | — | 158 µs | linear (slope 1.03) |
| epoch invalidation, 68 records all stale | — | 754 µs | linear (slope 1.06); about 9 µs more per invalidated record (a dataclass copy) than the 2.3 µs check |
| state retained between ticks | none | none | — |

**What the 13 % is.** It is the cost of CPython objects: the per-record
provenance lookup, the PACING predicate's node scan, and the `fault_impact`
dictionaries. None of it is an algorithmic term.

## 2. What each revision adds in C, ESTIMATED

Per tick, at the 128-record design cap the shadow study set.

| revision | onboard work in C | operations per tick | RAM | flash |
|---|---|---|---|---|
| R-1 | for each localization with a fault bit set: AND the fault mask with the supported hypothesis's refuter mask (and, rarely, its confirmer mask); set an outcome code | about 5 localizations × a few bit operations; **0 when no predicate faulted** | a 2-byte withheld-reason code per localization (about 16 B) | about 0.5-1 KB |
| R-2 | one predicate: for each declared pacing input (1-4), read its node's state from the index and fold ALL/ANY in 2-bit Kleene logic; the declaration is a compiled table entry | about 10-40 | a pacing table: 1-8 entries × (component id, mode, 4 input ids) ≈ 100 B | about 0.5 KB |
| R-3 | per record, compare the stamped epoch with the current epoch for its key (a small array lookup); on mismatch, set the record's state to UNAVAILABLE and clear its reason bits **in place**; one pass to drop superseded records | about 128 compares + a second pass; about 1-2 k simple operations at worst | per record: key index u8 + epoch u32 (or u32+u32 composite) = 5-9 B × 128 ≈ 0.6-1.2 KB; context table: ≤ 16 keys × 8 B ≈ 128 B | about 1-2 KB |

**Per-tick totals:**
- **Operations:** the shadow study's estimate was about 5,000-10,000 simple
  operations per tick. The revisions add at most about 2,000 (R-3's
  worst-case pass), so about 5,000-12,000.
- **Time:** at the same 3-10× factor for branches and memory, about 15,000-
  240,000 cycles, or **about 30-500 µs per tick at 480 MHz**.

**Memory:**
- **RAM:** the shadow study's 12-13 KB, plus about 1-1.5 KB, so **about
  13-15 KB**.
- **Flash:** the shadow study's 20-40 KB, plus about 2-3.5 KB, so **about
  22-44 KB**.

**Do R-1, R-2 and R-3 change the earlier estimate materially? No.**
- **The upper time bound moves from about 400 to about 500 µs.** The cause is
  R-3's worst case, every record stamped and stale at once. In E1, one record
  per tick was invalidated.
- **RAM and flash move by about 10 %.**
- **What does not change:** the 25-200 Hz plausibility table of the shadow
  study, and the answer.

| rate | tick budget | 2.1.1 estimate as a share of the budget |
|---|---|---|
| 25 Hz | 40 ms | 0.1-1.3 % |
| 50 Hz | 20 ms | 0.2-2.5 % |
| 100 Hz | 10 ms | 0.3-5 % |
| 200 Hz | 5 ms | 0.6-10 % |

## 3. UNKNOWN (H743)

The shadow study's unknowns stand:
- WCET;
- cache and memory placement;
- contention with the flight stack;
- the cost of producing the evidence.

The revisions add three more:

| unknown | why it matters | how it becomes known |
|---|---|---|
| where the epoch context comes from on the target | R-3 needs `instance_changed_count` (and, if used, `sensor_selection` and the reset counters) at reasoning time. On PX4 these are uORB topics, so a subscription per key | the evidence-adapter port step, measured with it |
| how many records carry a stamp | the R-3 cost is linear in stamped records; only configuration-dependent producers stamp (one record per tick in E1) | the producer contracts of a real integration |
| narrow-counter unwrapping | the uint8 reset counters need unwrapping in the adapter (`R3_CONFIGURATION_EPOCH.md` §6) | the adapter design |

## 4. Answer

**A C implementation of 2.1.1's reasoning core remains plausible at 25-200 Hz
on an H743-class target, as an ESTIMATE.**

**R-1, R-2 and R-3 add bounded, allocation-free work:**
- a bitmask test;
- a small table scan;
- a per-record compare.

**The one Python cost that looks large,** copying a record to make it
UNAVAILABLE, becomes an in-place flag in C.

**Nothing on the target is measured,** and nothing here claims hardware
readiness.
