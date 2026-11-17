#!/usr/bin/env bash
# The timed series behind evidence/performance.json, in the order it was run.
# Run from the Metabrowser checkout with WHEEL set to the exact fdu wheel; raw results
# land in the gitignored .bench/fdu-spike/ and summarize.py normalizes them.
set -euo pipefail
: "${WHEEL:?set WHEEL to the fdu wheel path}"
RUN=(uv --config-file uv.toml run --frozen --with "$WHEEL" python)
export PYTHONPATH=src:explorations/fdu-provider-spike
SPIKE=explorations/fdu-provider-spike
SYNTHETIC_TRIALS=${SYNTHETIC_TRIALS:-3}
TREE_TRIALS=${TREE_TRIALS:-2}
FLOOR_TRIALS=${FLOOR_TRIALS:-4}

# 1. The serving benchmark's own synthetic corpus, unchanged harness.
"${RUN[@]}" "$SPIKE/bench.py" synthetic --trials "$SYNTHETIC_TRIALS" --files 100000
# 2. Real trees through the same server path.
"${RUN[@]}" "$SPIKE/bench.py" tree --corpus .bench/corpus-checkout --label tree-checkout \
  --trials "$TREE_TRIALS" --rounds 8
"${RUN[@]}" "$SPIKE/bench.py" tree --corpus .bench/project-10 --label tree-project-10 \
  --trials "$TREE_TRIALS" --rounds 5
# 3. Engine floors: each engine alone, fresh process per sample.
for corpus in corpus-synthetic-100000 corpus-checkout project-10; do
  "${RUN[@]}" "$SPIKE/bench.py" floor --corpus ".bench/$corpus" --label "floor-$corpus" \
    --trials "$FLOOR_TRIALS"
done
# 4. Per-projection latency at fresh versions, in process.
"${RUN[@]}" "$SPIKE/projections.py" --corpus .bench/corpus-checkout --samples 7 --label checkout
"${RUN[@]}" "$SPIKE/projections.py" --corpus .bench/corpus-synthetic-100000 --samples 5 \
  --label synthetic-100000
"${RUN[@]}" "$SPIKE/projections.py" --corpus .bench/project-10 --samples 3 --label project-10
