# Phase 3.2 — reproduction

Paths are relative to the repository root.

## 0. Verify the starting state and that nothing earlier has moved

```sh
git rev-parse HEAD
git status --porcelain                     # must be empty
.venv/bin/python -m pytest -q --no-header \
    tests/test_consequence_phase32.py -k "earlier_locked_artifacts or ledger or survivors"
```

## 1. Development campaign (look freely)

```sh
.venv/bin/python research/consequence/phase32/campaign32.py \
    --partition development \
    --out research/consequence/phase32/results/PHASE32_TRACES_DEVELOPMENT.json

.venv/bin/python research/consequence/phase32/evaluate32.py \
    research/consequence/phase32/results/PHASE32_TRACES_DEVELOPMENT.json \
    --out research/consequence/phase32/results/PHASE32_RESULTS_DEVELOPMENT.json
```

## 2. Locked campaign (opened ONCE, after the preregistration was committed)

Preregistration freeze: `e95c616ce9543af5f62fa5f1a5e8f94a7d5e33ae`.

```sh
.venv/bin/python research/consequence/phase32/campaign32.py \
    --partition locked --i-am-opening-the-locked-partition \
    --out research/consequence/phase32/results/PHASE32_TRACES_LOCKED.json

.venv/bin/python research/consequence/phase32/evaluate32.py \
    research/consequence/phase32/results/PHASE32_TRACES_LOCKED.json \
    --out research/consequence/phase32/results/PHASE32_RESULTS_LOCKED.json
```

## 3. Deterministic replay

Run step 2's first command twice to different paths and compare. Both locked
runs produced sha256
`f9a198b9cf70507733f95a4093941ac256bcdbc34a6fd7c9b35c072255a83e7b`.

## 4. Tests, guards, mutation

```sh
.venv/bin/python -m pytest -q --no-header tests/test_consequence_phase32.py
.venv/bin/python -m pytest -q --no-header -p no:cacheprovider
make check-blocking
.venv/bin/python tools/mutation/run_phase32_mutations.py
```

**`run_e2m_mutations.py` and `run_phase31_mutations.py` are deliberately NOT
re-run and NOT modified.** Their five survivors — `P3-03`, `P3-04`, `31-03`,
`31-07`, `31-11` — must stay alive, and adding a new test file to either
selection could have killed one as a side effect.

## 5. Integrity

```sh
.venv/bin/python -c "
import hashlib, json, pathlib
m = json.load(open('research/consequence/phase32/SHA256_MANIFEST32.json'))
print('mismatches:', [p for p, w in m['files'].items()
                      if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() != w])"
```

## What none of this does

It operates no hardware, transmits no RF, arms no vehicle, commands no
actuator, and starts no autopilot.
