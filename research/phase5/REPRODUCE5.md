# Reproducing Phase 5 — the hybrid detector study

**Phase 5 is an EXPERIMENTAL study of additive modules.** Nothing in it is a
production-core result: `B4` and `B6` rest on a **shadow** support map that
the frozen core does not use. No hardware, no RF, no HIL, no SITL, no armed
vehicle, no flight, no autopilot execution.

## 0. Preconditions

```
python -m pytest tests/test_phase5_hybrid.py tests/test_phase5_pipeline.py -q
python -c "import json,hashlib;b=json.load(open('docs/v1/FROZEN_BASELINE.json'));\
print([f for f,h in b['files'].items() if hashlib.sha256(open(f,'rb').read()).hexdigest()!=(h if isinstance(h,str) else h['sha256'])])"
```

The second must print `[]`. Phase 5 imports the frozen core and never edits
it.

## 1. Development — where every parameter is chosen

```
python research/phase5/campaign5.py --partition development \
    --out research/phase5/results/PHASE5_RUNS_DEVELOPMENT.json
```

12 seeds × 34 cells = **408 runs**, about 8 minutes. Thresholds, the fast
path's `h_fast`, and the multi-timescale configuration are selected here and
**only** here.

## 2. Validation — one dress rehearsal

```
python research/phase5/campaign5.py --partition validation \
    --out research/phase5/results/PHASE5_RUNS_VALIDATION.json
```

16 seeds × 34 = **544 runs**. Read once, after the preregistration is
committed and before `locked`. A parameter chosen on development and
evaluated on development is not a measurement.

## 3. Locked — opened once

```
python research/phase5/campaign5.py --partition locked \
    --i-am-opening-the-locked-partition \
    --out research/phase5/results/PHASE5_RUNS_LOCKED.json
```

40 seeds × 34 = **1360 runs**, about 27 minutes. The partition raises
`PermissionError` unless the call site spells out that it is opening it.

## 4. Replay check

```
python research/phase5/campaign5.py --partition locked \
    --i-am-opening-the-locked-partition --out /tmp/p5_locked2.json
python research/phase4/replay_check4.py \
    research/phase5/results/PHASE5_RUNS_LOCKED.json /tmp/p5_locked2.json
```

**Deliberately not `cmp`.** The document carries `ns_total`, a wall-clock
measurement, which is not a function of the seed, so two honest passes are
never byte-identical. The campaign declares `environment_specific_fields` and
the checker strips exactly those (**FL-036**). Phase 4's checker is reused
rather than copied.

## 5. Evaluation

```
python research/phase5/evaluate5.py \
    research/phase5/results/PHASE5_RUNS_DEVELOPMENT.json \
    research/phase5/results/PHASE5_RUNS_LOCKED.json \
    --out research/phase5/results/PHASE5_RESULTS_LOCKED.json
```

The evaluator is standard library only and imports no CSIA module — asserted
in a fresh interpreter. `test_build_reproduces_the_sealed_result_from_the_committed_runs`
re-derives the sealed result and compares it byte for byte, so this step is
checked by the suite and not only by hand.

## 6. Mutation

```
python tools/mutation/run_phase5_mutations.py
```

A **fifth** runner, separate from E2M (38/36/2), Phase-3.1 (11/8/3),
Phase-3.2 (12/12/0) and Phase-4 (17/17/0). **The Phase-4 score is not
evidence about this code.** The runner aborts unless the unmutated selection
passes in the sandbox and the canary dies, and it never converts a collection
error, a missing artifact or a timeout into a kill.

## 7. Manifest

```
python research/phase5/build_manifest5.py
```

## What reproduction does not establish

That the numbers reproduce says the pipeline is deterministic and the
write-up matches the artifacts. It says nothing about hardware, flight,
airworthiness or prevalence; it is **not** pooled with Phases 3, 3.1, 3.2 or
4; and it is **not** evidence that CSIA outperforms CUSUM, which Phase 4
measured the other way on latency.
