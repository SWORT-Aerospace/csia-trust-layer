# Source inventory — WP1

Commit `bc3ed977e14d6eb6c5dc3a8b771b2349337de91a`, branch `research/wp1-formalization`,
worktree clean at audit start. Repository is **untagged**.

Package version `0.8.0` (`pyproject.toml:7`).

## Core modules on the trust/diagnosis/failsafe path

| Module | Lines | sha256[:16] |
|---|---|---|
| `csia/trust_graph/graph.py` | 100 | `51dede11bdc856a0` |
| `csia/trust_engine/engine.py` | 214 | `4bd01311ab07fd0d` |
| `csia/diagnosis/bayes.py` | 155 | `414f429f98881505` |
| `csia/runtime/failsafe.py` | 257 | `0a8d1f5fc8b29ab4` |
| `csia/runtime/online.py` | 658 | `d7a5be6cf4a04345` |
| `csia/runtime/plugins.py` | 287 | `5e0d546155c22b39` |
| `csia/prediction/comparator.py` | 276 | `34d3d5e018be2b18` |
| `csia/prediction/predictors.py` | 79 | `8f279e5f02590ff4` |
| `csia/profiles.py` | 93 | `7ff5ebd0589b8200` |
| `csia/cli.py` | 336 | `64fb3f1ab2080c96` |
| `csia/native/csia_core.c` | 175 | `1c0ff36fa707acd2` |

## Test inventory (measured, not quoted)

`python -m pytest --collect-only -q` → **418 tests** in 22 modules.

```
tests/scenarios/test_fault_scenarios.py: 8
tests/scenarios/test_seeker_scenarios.py: 7
tests/test_acquisition.py: 34
tests/test_anytime_validity.py: 15
tests/test_causal.py: 22
tests/test_ci_env.py: 3
tests/test_comparator.py: 4
tests/test_data_lake.py: 21
tests/test_datasets.py: 38
tests/test_diagnosis.py: 3
tests/test_engine.py: 6
tests/test_hf_acquisition.py: 45
tests/test_hypothesis.py: 44
tests/test_mac_pipeline.py: 37
tests/test_mavlink_map.py: 4
tests/test_metrics_events.py: 15
tests/test_metrics_latency.py: 31
tests/test_native.py: 5
tests/test_partition_integrity.py: 34
tests/test_runtime.py: 17
tests/test_sensors.py: 9
tests/test_shared_power_baselines.py: 16
```

Baseline run: `python -m pytest -q` → **418 passed, 0 failed, 0 skipped,
0 warnings, exit 0, 2m14.9s** (native core built first, so the 5 parity tests
executed rather than skipping).

## Official commands (discovered, not assumed)

Discovered from `.github/workflows/ci.yml`; there is **no** Makefile, tox.ini,
or noxfile.py in this repository, and `pyproject.toml` carries only
`[tool.pytest.ini_options]` — no lint, format, or type-check configuration.

| Purpose | Command | Source |
|---|---|---|
| install | `pip install -e ".[dev,data,logs,mavlink]"` | `ci.yml:22` |
| dependency smoke | `python -c "import duckdb, huggingface_hub, jsonschema, polars, pyarrow, pymavlink, pyulog, yaml"` | `ci.yml:24` |
| native build | `bash csia/native/build.sh` | `ci.yml:25` |
| full suite | `python -m pytest -q` | `ci.yml:28` |
| manifest determinism | `python tools/build_dataset_manifest.py` + `git diff --exit-code` | `ci.yml:34-36` |
| wheel validation | `python -m build --wheel` + install + import | `ci.yml:51-62` |
| CLI smoke | `csia report` | `ci.yml:63` |
| frozen benchmark | `git diff --exit-code campaigns/bench.json` | `ci.yml:66-68` |
| sanitizers | `bash csia/native/build.sh --check` | `ci.yml:78` |

**Finding F-Q1: there is no linter, formatter, or static analysis in this
project.** No ruff/flake8/black/isort/mypy config, no CI step. §16's
"existing lint / formatting / static analysis" therefore has nothing to run.

## Profiles shipped

| Profile | tick_hz | sensors | Source |
|---|---|---|---|
| `sow001_quad` | 25.0 | 8 | `profiles.py:56-63` |
| `sow001_quad_strict` | 25.0 | 8 | `profiles.py:67-76` |
| `interceptor_seeker` | **100.0** | 3 | `profiles.py:80-89` |

README:79-80 names only the first two as shipping.
