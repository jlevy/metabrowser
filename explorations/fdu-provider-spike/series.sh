#!/usr/bin/env bash
# The timed series behind evidence/performance.json. Run from the Metabrowser checkout
# with WHEEL set to the exact fdu wheel; raw results land in the gitignored
# .bench/fdu-spike/ and summarize.py normalizes them. STAGES selects a subset: the
# recorded series ran "synthetic" first, then "tree floor projections discovery" as a
# second invocation after a harness fix to the tree mode's response parsing.
set -euo pipefail
: "${WHEEL:?set WHEEL to the fdu wheel path}"
RUN=(uv --config-file uv.toml run --frozen --with "$WHEEL" python)
export PYTHONPATH=src:explorations/fdu-provider-spike
SPIKE=explorations/fdu-provider-spike
STAGES=${STAGES:-synthetic tree floor projections discovery}
SYNTHETIC_TRIALS=${SYNTHETIC_TRIALS:-3}
TREE_TRIALS=${TREE_TRIALS:-2}
FLOOR_TRIALS=${FLOOR_TRIALS:-4}

for stage in $STAGES; do
  case $stage in
    synthetic)
      # The serving benchmark's own synthetic corpus, unchanged harness.
      "${RUN[@]}" "$SPIKE/bench.py" synthetic --trials "$SYNTHETIC_TRIALS" --files 100000
      ;;
    tree)
      # Real trees through the same server path.
      "${RUN[@]}" "$SPIKE/bench.py" tree --corpus .bench/corpus-checkout \
        --label tree-checkout --trials "$TREE_TRIALS" --rounds 8
      "${RUN[@]}" "$SPIKE/bench.py" tree --corpus .bench/project-10 \
        --label tree-project-10 --trials "$TREE_TRIALS" --rounds 5
      ;;
    floor)
      # Engine floors: each engine alone, a fresh process per sample.
      for corpus in corpus-synthetic-100000 corpus-checkout project-10; do
        "${RUN[@]}" "$SPIKE/bench.py" floor --corpus ".bench/$corpus" \
          --label "floor-$corpus" --trials "$FLOOR_TRIALS"
      done
      ;;
    projections)
      # Per-projection latency at fresh versions, in process.
      "${RUN[@]}" "$SPIKE/projections.py" --corpus .bench/corpus-checkout --samples 7 \
        --label checkout
      "${RUN[@]}" "$SPIKE/projections.py" --corpus .bench/corpus-synthetic-100000 \
        --samples 5 --label synthetic-100000
      "${RUN[@]}" "$SPIKE/projections.py" --corpus .bench/project-10 --samples 3 \
        --label project-10
      ;;
    discovery)
      # Open to first answer per projection kind while discovery runs.
      "${RUN[@]}" "$SPIKE/discovery.py" --corpus .bench/corpus-synthetic-100000 \
        --trials 3 --label synthetic-100000
      "${RUN[@]}" "$SPIKE/discovery.py" --corpus .bench/project-10 --trials 2 \
        --label project-10
      ;;
    *)
      echo "unknown stage $stage" >&2
      exit 2
      ;;
  esac
done
