# Phase 3.1 — reproduction

Paths are relative to the repository root. `.venv/bin/python` is the
interpreter the suite uses.

## 0. Verify the starting state and that Phase 3 has not moved

```sh
git rev-parse HEAD
git status --porcelain                     # must be empty
.venv/bin/python - <<'PY'
import hashlib, json
d = json.load(open("docs/v1/FROZEN_BASELINE.json"))
print("frozen-core mismatches:",
      [r for r, w in d["files"].items()
       if hashlib.sha256(open(r, "rb").read()).hexdigest() != w])
PY
.venv/bin/python -m pytest -q --no-header \
    tests/test_consequence_phase31.py -k phase3_locked_artifacts
```

## 1. Reachability inventory and the magnitude/duration sweep

These informed the amendment and were run on development seeds. Both are
reproduced by the development campaign below plus the tables in
`PREREGISTRATION_PHASE31.md` §4 and §5.

## 2. Development campaign (look freely)

```sh
.venv/bin/python research/consequence/phase31/campaign31.py \
    --partition development \
    --out research/consequence/phase31/results/PHASE31_TRACES_DEVELOPMENT.json

.venv/bin/python research/consequence/phase31/evaluate31.py \
    research/consequence/phase31/results/PHASE31_TRACES_DEVELOPMENT.json \
    --out research/consequence/phase31/results/PHASE31_RESULTS_DEVELOPMENT.json
```

## 3. Locked campaign (opened ONCE, after the amendment was committed)

The amendment freeze is `7b890ba369d250ac481adb945f835f48a068e4b3`. The flag
is required at the call site; the partition refuses to open without it.

```sh
.venv/bin/python research/consequence/phase31/campaign31.py \
    --partition locked --i-am-opening-the-locked-partition \
    --out research/consequence/phase31/results/PHASE31_TRACES_LOCKED.json

.venv/bin/python research/consequence/phase31/evaluate31.py \
    research/consequence/phase31/results/PHASE31_TRACES_LOCKED.json \
    --out research/consequence/phase31/results/PHASE31_RESULTS_LOCKED.json
```

## 4. Deterministic replay

Run step 3's first command twice to different paths and compare. Both locked
runs produced sha256
`e8c2d90d81b16835d48e4ae5c2a35fad54101e751b8d64dda74c50afaf56539e`.

```sh
cmp PHASE31_TRACES_LOCKED.json PHASE31_TRACES_LOCKED_SECOND.json
```

## 5. Tests, guards, mutation

```sh
.venv/bin/python -m pytest -q --no-header tests/test_consequence_phase31.py
.venv/bin/python -m pytest -q --no-header -p no:cacheprovider
make check-blocking
.venv/bin/python tools/mutation/run_phase31_mutations.py
```

**`tools/mutation/run_e2m_mutations.py` is deliberately NOT re-run here and
is not modified.** Phase 3's 38 evaluated / 36 killed / 2 survived stands, and
adding the Phase-3.1 test file to its selection could have killed `P3-03` or
`P3-04` as a side effect — the artificial kill the brief forbids.

## 6. Integrity

```sh
.venv/bin/python -c "
import hashlib, json, pathlib
m = json.load(open('research/consequence/phase31/SHA256_MANIFEST31.json'))
print('mismatches:', [p for p, w in m['files'].items()
                      if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() != w])"
```

## What none of this does

It operates no hardware, transmits no RF, arms no vehicle, commands no
actuator, and starts no autopilot. The SITL binaries present in this container
are not invoked by any command above.
