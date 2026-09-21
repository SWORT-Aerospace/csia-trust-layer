# Reproducing Phase 4 — detector performance

Phase 4 measures **detector delay against false alarms**. It measures no
consequence, runs no autopilot, arms nothing and touches no hardware. Every
command below runs on a CPU in this container with no network.

## 0. Preconditions

```
python -m pytest tests/test_phase4_detectors.py tests/test_phase4_pipeline.py -q
python -c "import json,hashlib;b=json.load(open('docs/v1/FROZEN_BASELINE.json'));\
print([f for f,h in b['files'].items() if hashlib.sha256(open(f,'rb').read()).hexdigest()!=h])"
```

The second command must print `[]`. Phase 4 imports the frozen core and does
not modify it.

## 1. Development partition

Thresholds are selected here and **only** here.

```
python research/phase4/campaign4.py --partition development \
    --out research/phase4/results/PHASE4_RUNS_DEVELOPMENT.json
```

12 seeds × (1 nominal + 5 gains × 4 onsets) = **252 runs**, about 90 s.

## 2. Locked partition

The locked partition refuses casual access; opening it is a deliberate act
and the flag says so.

```
python research/phase4/campaign4.py --partition locked \
    --i-am-opening-the-locked-partition \
    --out research/phase4/results/PHASE4_RUNS_LOCKED.json
```

40 seeds × 21 = **840 runs**, about 5 min.

## 3. Replay check

Run the locked partition a second time and compare:

```
python research/phase4/campaign4.py --partition locked \
    --i-am-opening-the-locked-partition --out /tmp/p4_locked2.json
python research/phase4/replay_check4.py \
    research/phase4/results/PHASE4_RUNS_LOCKED.json /tmp/p4_locked2.json
```

**This is deliberately not `cmp`.** The document carries `ns_total`, a
wall-clock timing measurement, because computational cost is a preregistered
reported quantity — and wall clock is not a function of the seed. Two honest
passes are therefore never byte-identical, and a byte-identity check would
fail every time while saying nothing. The campaign declares
`environment_specific_fields`, the checker strips exactly those and compares
everything else, and it refuses outright to run on a document that declares
nothing. The first version of this step **was** a `cmp`, it reported a
failure that was not one, and that is recorded as **FL-036**.

Expect `P4_REPLAY_IDENTICAL=yes`: all 840 runs, all three detectors, every
declared threshold, all three alarm times.

**Three** passes were run for the committed result, compared pairwise
(1 vs 2, 1 vs 3, 2 vs 3). All three agree.

## 4. Evaluation

The evaluator is standard library only and imports no CSIA module — a test
asserts that in a fresh interpreter.

```
python research/phase4/evaluate4.py \
    research/phase4/results/PHASE4_RUNS_DEVELOPMENT.json \
    research/phase4/results/PHASE4_RUNS_LOCKED.json \
    --out research/phase4/results/PHASE4_RESULTS_LOCKED.json
```

`tests/test_phase4_pipeline.py::test_build_reproduces_the_sealed_result_from_the_committed_runs`
re-derives the sealed result from the committed runs and compares it byte for
byte, so this step is checked by the suite and not only by hand.

**One number in the sealed result is not reproducible from a fresh campaign,
and that is expected.** `computational_cost` is derived from the `ns_*` wall
clock fields, so evaluating the *committed* runs reproduces it exactly while
evaluating a *newly generated* pair will not. Every other figure — every
alarm time, every rate, every delay, every interval, every matched operating
point — is a deterministic function of the seeds and does reproduce.

## 5. Mutation

```
python tools/mutation/run_phase4_mutations.py
```

A **fourth** runner, separate from `run_e2m_mutations.py` (38/36/2),
`run_phase31_mutations.py` (11/8) and `run_phase32_mutations.py` (12/12), so
that widening this selection cannot kill one of the five earlier survivors as
a side effect. It aborts unless the unmutated selection passes in the sandbox
and the canary dies. The sha256 manifest guard is deselected and the reason
is in the runner: a manifest guard fails for every mutant because mutating a
file changes its hash, which manufactures a perfect score (**FL-033**).

## 6. Manifest

```
python research/phase4/build_manifest4.py
```

## What reproduction does not establish

Reproducing these numbers establishes that the pipeline is deterministic and
that the write-up matches the artifacts. It establishes nothing about
hardware, flight, autopilot execution, airworthiness or prevalence, and it is
**not** pooled with the consequence phases — different partitions, different
question, different unit of analysis.
