# Phase 3 — reproduction

Every command below was run to produce the committed artifacts. Paths are
relative to the repository root. `.venv/bin/python` is the interpreter the
suite uses.

## 0. Verify the starting state

```sh
git rev-parse HEAD
git status --porcelain            # must be empty
.venv/bin/python - <<'PY'
import hashlib, json
d = json.load(open("docs/v1/FROZEN_BASELINE.json"))
bad = [r for r, want in d["files"].items()
       if hashlib.sha256(open(r, "rb").read()).hexdigest() != want]
print("frozen-core mismatches:", bad)          # must be []
PY
.venv/bin/python -m pytest -q --no-header -p no:cacheprovider
make check-blocking
```

## 1. Development campaign (look freely)

```sh
.venv/bin/python research/consequence/phase3/campaign.py \
    --partition development \
    --out research/consequence/phase3/results/PHASE3_TRACES_DEVELOPMENT.json

.venv/bin/python research/consequence/phase3/independent_consequence_evaluator.py \
    research/consequence/phase3/results/PHASE3_TRACES_DEVELOPMENT.json \
    --out research/consequence/phase3/results/PHASE3_EVALUATION_DEVELOPMENT.json
```

## 2. Locked campaign (opened ONCE, after the design was committed)

The design freeze is commit `d2a5ee9a62978be35e91380bf036a6aea3020155`. The
flag is required at the call site; the partition refuses to open without it.

```sh
.venv/bin/python research/consequence/phase3/campaign.py \
    --partition locked --i-am-opening-the-locked-partition \
    --out research/consequence/phase3/results/PHASE3_TRACES_LOCKED.json

.venv/bin/python research/consequence/phase3/independent_consequence_evaluator.py \
    research/consequence/phase3/results/PHASE3_TRACES_LOCKED.json \
    --out research/consequence/phase3/results/PHASE3_EVALUATION_LOCKED.json

.venv/bin/python research/consequence/phase3/analyze.py \
    research/consequence/phase3/results/PHASE3_EVALUATION_LOCKED.json \
    --out research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json
```

## 3. Deterministic replay

Run step 2's first command twice to different paths and compare. Both locked
runs produced sha256 `78d132988a38ad9fb16c5b85ff7f91e51df78c31b27d596469a49cfdfa238b57`.

```sh
cmp PHASE3_TRACES_LOCKED.json PHASE3_TRACES_LOCKED_SECOND.json
```

## 4. Tests, guards, mutation

```sh
.venv/bin/python -m pytest -q --no-header tests/test_consequence_phase3.py
.venv/bin/python -m pytest -q --no-header -p no:cacheprovider
make check-blocking
.venv/bin/python tools/mutation/run_e2m_mutations.py
```

The mutation runner refuses to report unless the **unmutated** selection
passes in its sandbox, and the artifact records
`kills_attributed_to_a_bare_file` so a collection error cannot be read as a
kill.

## 5. Integrity

```sh
.venv/bin/python -c "
import hashlib, json, pathlib
m = json.load(open('research/consequence/phase3/SHA256_MANIFEST.json'))
bad = [p for p, want in m['files'].items()
       if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() != want]
print('mismatches:', bad)"
```

## What none of this does

It operates no hardware, transmits no RF, arms no vehicle, commands no
actuator, and starts no autopilot. The SITL binaries present in this
container are not invoked by any command above.
