#!/usr/bin/env bash
# Nightly assurance run for the OptiPlex validation node.
#
# DOES NOT MODIFY SOURCE. It reports; a human decides.
#
# Every stage runs even if an earlier one fails, so one broken stage cannot
# hide the rest. A stage that could not run is INCONCLUSIVE and is NEVER
# folded into PASS -- a skipped check reading as green is a failure mode this
# repository has already hit.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PY:-$ROOT/.venv/bin/python}"
OUT="${CSIA_NIGHTLY_OUT:-$ROOT/build/nightly/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT"

pass=0; fail=0; inconclusive=0
declare -a RESULTS

stage() {
  local name="$1"; shift
  local log="$OUT/${name}.log"
  if ! command -v "${1}" >/dev/null 2>&1 && [ ! -x "${1}" ]; then
    RESULTS+=("$name INCONCLUSIVE (command not available)")
    inconclusive=$((inconclusive+1)); return
  fi
  if timeout "${CSIA_STAGE_TIMEOUT:-3600}" "$@" >"$log" 2>&1; then
    RESULTS+=("$name PASS"); pass=$((pass+1))
  else
    local rc=$?
    if [ "$rc" -eq 124 ]; then
      RESULTS+=("$name INCONCLUSIVE (timeout)"); inconclusive=$((inconclusive+1))
    else
      RESULTS+=("$name FAIL (exit $rc, see $log)"); fail=$((fail+1))
    fi
  fi
}

stage environment    "$PY" tools/assurance/portability_probe.py --out "$OUT/host.json"
stage unit_tests     "$PY" -m pytest tests/ -q
stage guards         make check-blocking
stage firewall       "$PY" -m pytest tests/test_assurance_firewall.py tests/test_assurance_independence.py tests/test_assurance_metamorphic.py tests/test_assurance_vectors.py -q
stage bounded_formal "$PY" tools/assurance/bounded_verify.py --out "$OUT/bounded.json"
stage hostile_input  "$PY" tools/assurance/hostile_input.py --out "$OUT/hostile.json"
stage decision_replay "$PY" tools/assurance/decision_replay.py --out "$OUT/replay.json"
stage resource_env   "$PY" tools/assurance/resource_envelope.py --out "$OUT/envelope.json" --quick
stage differential   "$PY" tools/assurance/differential.py --out "$OUT/differential.json"
stage recovery       "$PY" tools/assurance/process_recovery.py --out "$OUT/recovery.json"
stage config_proof   "$PY" tools/assurance/config_proof.py --out "$OUT/config_proof.json"
stage provenance     "$PY" tools/assurance/build_provenance.py --out "$OUT/provenance.json"

# ---------------------------------------------------------------------------
# QUALITY RATCHET. Coverage and mutation score may not fall below the recorded
# floor. The floor is a MEASUREMENT of what was achieved, not a target, and it
# only ever moves up -- by a deliberate `--update` in the commit that earned
# it. See tools/xr/quality_ratchet.py.
#
# The mutation probe is SLOW (minutes, not seconds) and runs against a COPY of
# the tree, so it is last: a nightly that never reaches the fast stages
# because the slow one hung would be worse than no nightly.
stage mission_tests  "$PY" -m pytest tests/test_mission_assurance.py \
                        tests/test_mission_untested_modules.py \
                        tests/test_mission_boundaries.py \
                        tests/test_mission_survivor_kills.py \
                        tests/test_mission_registries_and_schemas.py \
                        tests/test_bad_product_references.py \
                        tests/test_paper_i_scope_guard.py -q
stage mutation_probe "$PY" tools/xr/mutation_probe.py --sample 250 \
                        --out "$OUT/mutation.json"
stage quality_ratchet "$PY" tools/xr/quality_ratchet.py --check

if [ -f "$ROOT/research/physical_validation/results/PORTABILITY_HOST_current.json" ] \
   && [ -f "$OUT/host.json" ]; then
  stage portability "$PY" tools/assurance/portability_probe.py --compare \
    "$ROOT/research/physical_validation/results/PORTABILITY_HOST_current.json" \
    "$OUT/host.json"
fi

{
  echo "CSIA nightly $(date -u +%FT%TZ)"
  echo "host: $(uname -srm)"
  echo "commit: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo
  printf '%s\n' "${RESULTS[@]}"
  echo
  if [ "$fail" -gt 0 ]; then echo "VERDICT: REGRESSION"
  elif [ "$inconclusive" -gt 0 ]; then echo "VERDICT: INCONCLUSIVE"
  else echo "VERDICT: PASS"; fi
} | tee "$OUT/REPORT.txt"

[ "$fail" -eq 0 ] || exit 1
[ "$inconclusive" -eq 0 ] || exit 2
exit 0
