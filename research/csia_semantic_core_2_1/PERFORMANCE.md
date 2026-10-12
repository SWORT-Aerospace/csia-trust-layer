# Runtime cost of Semantic Core 2.1 (Phase I)

**2026-09-30.** Numbers come from `PHASE_I_BENCHMARK.json`, written by
`benchmark_2_1.py`. **These are desktop CPython timings of one container**
(Python 3.12, Linux x86_64). They vary between runs by tens of percent, and
they say **nothing** about an embedded target.

**The C runtime (`embedded/`) does not implement 2.1**, and no claim of
H743-class readiness is made or implied here.

## 1. Stage timings, per tick

Medians of repeated runs. The two corpora are all 2,640 shipped ticks and the
44 final ticks.

| stage | frozen 2.0.0 | 2.1, full trace | 2.1, `trace=False` |
|---|---|---|---|
| localization | 0.085 ms | 0.38 ms | 0.31 ms |
| attribution | 0.039 ms | — | 0.28 ms |
| combined | **0.128 ms** | **0.52 ms** (4.0x) | **0.44 ms** (3.4x) |

On the 44 final ticks alone the combined ratios are 3.8x with the trace and
3.1x without it.

**Where the extra time goes, all of it linear in the tick's records:**
- the C6 pass over the records: duplicates and same-key conflicts;
- the predicate wrapper: the C4 check, plus the read log when tracing;
- the C1 walk of declared alternatives;
- the C5 split and the `components_not_observed` set;
- the F2 comparison with the tick's localizations.

**Does this meet the brief's target?** In absolute terms the successor adds
about 0.3 ms per tick on this machine. That is small in absolute terms. It
is **not** negligible as a ratio: it roughly triples or quadruples the
reasoning step, and the step is already the smallest part of an engine tick.
No optimization was attempted before correctness was established, as the
brief asks.

## 2. Asymptotics and worst cases

| test | log-log slope | verdict |
|---|---|---|
| one final tick padded with unconnected records, 68 to 2,176 records | frozen 0.89; 2.1 trace 0.90; 2.1 no trace 1.02 | **linear**, the same order as frozen |
| C6: k different records under ONE (domain, component, relation) key, k = 8 to 512 | **1.00** | linear |
| C3 scope closure and C1 alternative walk: a dependency chain of length 8 to 512 | 0.78 | linear or better |

**A quadratic case was found and removed during this phase.**
- **What it was.** C6's first implementation compared every record against
  every kept record sharing its (domain, component, relation). The slope
  was 1.93.
- **The fix.** Records are now pre-bucketed on every hashable field, and
  dataclass equality decides only inside a bucket.
- **What stayed the same.** The semantics are unchanged: equal records
  collapse, even when their dicts were built in a different order; a
  malformed record falls back to the coarse key. The identity and shadow
  cross-checks were re-run after the change.

**No unbounded search exists.**
- The alternative walk and the scope closure visit each declared node once.
- The predicate set is fixed by the symptom table.
- 2.1 adds no enumeration over subsets.
- `minimum_resolving_subsets` is frozen v2's and is not used by 2.1.

## 3. Memory and allocation

| | frozen | 2.1 trace | 2.1 no trace |
|---|---|---|---|
| peak traced memory for one tick (largest final tick, 68 records) | 27.6 KB | 90.0 KB | 79.8 KB |
| blocks allocated by the result | 195 | 578 | 487 |
| retained after 2,640 ticks with one reasoner reused | — | **0 bytes** | — |

**2.1 holds no state between ticks**, so there is no evidence-history
growth. The largest per-tick allocation is the read log and the trace
dictionaries.

**Trace size** (`SEMANTIC_CORE_2_1_RESULTS.json` J, JSON bytes per tick):

| | mean | median | max |
|---|---|---|---|
| frozen 2.0.0 localization and attribution | 3,964 | 4,157 | 10,933 |
| 2.1 with trace | 7,655 | 6,277 | 23,067 |
| 2.1, `trace=False` | 3,943 | 4,228 | 8,486 |

## 4. Test overhead, reported separately

`tests/test_semantic_core_2_1.py` takes **about 16 s** of wall time in its own
pytest process. That includes:
- the 2,640-tick identity check;
- the exhaustive P1 and P5 checks;
- the bounded property-based tests.

The full differential harness takes about 20 minutes, mostly the audit's
enumerations. The test-migration probe takes about 90 s. **None of this is
runtime overhead.** They are validation costs, paid once per change.

## 5. What this does not establish

- **Nothing about H743 timing or memory.** A Python dictionary-heavy trace
  has no bearing on a static C implementation.
- **No C implementation of 2.1 exists**, and none was attempted, since it is
  not in scope.
- **Nothing about field loads.** The evidence sizes are the shipped
  scenarios' (up to about 70 records a tick) and synthetic padding up to
  2,176 records.
