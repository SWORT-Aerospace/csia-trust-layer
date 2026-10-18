#!/usr/bin/env bash
# XSYS-001 pipeline dry run on APPARATUS data (NOT CONFIRMATORY).
#
#   run_dry_run.sh <python> <decompressed apparatus sweep dir> <output dir> [summary.json]
#
# The sweep ULogs are research/px4_actuator_effectiveness/raw_ulog/sweep/*.ulg.xz,
# decompressed, with their .json trial records. The calibration was set on the
# same data, so the result is IN-SAMPLE: it tests the pipeline, not the hypotheses.
#
# Besides the ordinary run it performs two failure-path checks:
#   exclusion  one A flight is withheld: the flight, its analysis trials and
#              its pair must be reported as excluded, not silently dropped
#   seal       one byte of the stage-1 output is changed: stage 2 must refuse
set -euo pipefail
PY=$1; SWEEP=$2; OUT=$3
P=$(cd "$(dirname "$0")/../pipeline" && pwd)
CAL=$(cd "$(dirname "$0")/../calibration" && pwd)/CALIBRATION.json
mkdir -p "$OUT"
"$PY" "$P/dry_run_matrix.py" "$SWEEP" "$OUT"

run() {  # flights_dir out_subdir
  local F=$1 D=$2
  mkdir -p "$D"
  "$PY" "$P/stage0_prepare.py" --mode dry-run --flight-matrix "$OUT/DRY_RUN_FLIGHT_MATRIX.csv" \
      --analysis-matrix "$OUT/DRY_RUN_ANALYSIS_MATRIX.csv" --flights "$F" \
      --blind "$D/blind" --key "$D/KEY.json" --qc "$D/QC.json"
  "$PY" "$P/stage1_evidence.py" --blind "$D/blind" --calibration "$CAL" --out "$D/STAGE1.json"
  "$PY" "$P/stage2_score.py" --stage1 "$D/STAGE1.json" --key "$D/KEY.json" --qc "$D/QC.json" \
      --analysis-matrix "$OUT/DRY_RUN_ANALYSIS_MATRIX.csv" --out "$D/RESULTS.json"
}

echo "== full dry run"
run "$SWEEP" "$OUT/full"

echo "== exclusion path: sweep_eta070_r2 withheld"
mkdir -p "$OUT/excl_flights"
for f in "$SWEEP"/sweep_eta*_r[123].ulg "$SWEEP"/sweep_eta*_r[123].json; do
  case "$(basename "$f")" in sweep_eta070_r2.*) ;; *) ln -sf "$f" "$OUT/excl_flights/";; esac
done
run "$OUT/excl_flights" "$OUT/excl"

echo "== seal path: one byte of the stage-1 output changed"
cp "$OUT/full/STAGE1.json" "$OUT/tampered.json"
cp "$OUT/full/STAGE1.seal.json" "$OUT/tampered.seal.json"
sed -i '0,/"C_T3": /s/"C_T3": /"C_T3":  /' "$OUT/tampered.json"
if "$PY" "$P/stage2_score.py" --stage1 "$OUT/tampered.json" --key "$OUT/full/KEY.json" --qc "$OUT/full/QC.json" \
      --analysis-matrix "$OUT/DRY_RUN_ANALYSIS_MATRIX.csv" --out "$OUT/tampered_results.json" 2> "$OUT/tamper.err"; then
  echo "SEAL CHECK FAILED: stage 2 scored a tampered stage-1 output"; exit 1
fi
echo "stage 2 refused: $(cat "$OUT/tamper.err")"
if [ $# -ge 4 ]; then "$PY" "$(dirname "$0")/summarize_dry_run.py" "$OUT" "$4"; fi
echo DRY_RUN_EXIT=0
