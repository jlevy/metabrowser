#!/usr/bin/env bash
# The timed series behind evidence/performance.json. Run from the Metabrowser checkout
# with WHEEL set to the exact fdu wheel; raw results land in the gitignored
# .bench/fdu-spike/ and summarize.py normalizes them. STAGES selects a subset.
#
# Before anything is timed, every script the series runs must be committed and
# unmodified, and their commit and digests are written to
# .bench/fdu-spike/frozen-digests.txt, so a record always names sources a commit holds.
# The performance loop's series lock serializes timed runs across worktrees; a lock left
# by a crashed run is reported and left for a person to remove, never removed here.
set -euo pipefail
: "${WHEEL:?set WHEEL to the fdu wheel path}"
RUN=(uv --config-file uv.toml run --frozen --with "$WHEEL" python)
export PYTHONPATH=src:explorations/fdu-provider-spike
SPIKE=explorations/fdu-provider-spike
STAGES=${STAGES:-synthetic tree floor projections discovery}
SYNTHETIC_TRIALS=${SYNTHETIC_TRIALS:-3}
TREE_TRIALS=${TREE_TRIALS:-2}
FLOOR_TRIALS=${FLOOR_TRIALS:-4}
OUT=.bench/fdu-spike
SOURCES=(adapter.py probe.py launcher.py bench.py projections.py discovery.py series.sh)

mkdir -p "$OUT"
for source in "${SOURCES[@]}"; do
  if ! git ls-files --error-unmatch "$SPIKE/$source" >/dev/null 2>&1 ||
    ! git diff --quiet HEAD -- "$SPIKE/$source"; then
    echo "error: $SPIKE/$source is not committed as it stands; commit it before timing" >&2
    exit 1
  fi
done

lock="$(git rev-parse --path-format=absolute --git-common-dir)/metabrowser-series.lock"
if ! mkdir "$lock" 2>/dev/null; then
  echo "error: the series lock $lock is held:" >&2
  cat "$lock/owner" >&2 2>/dev/null || echo "(no owner file)" >&2
  exit 1
fi
printf 'pid %s\nstarted %s\nby %s series.sh\n' "$$" "$(date -u +%FT%TZ)" "$SPIKE" >"$lock/owner"
trap 'rm -r -- "$lock"' EXIT

{
  echo "commit $(git rev-parse HEAD)"
  echo "started $(date -u +%FT%TZ)"
  echo "stages $STAGES"
  echo "wheel $(basename "$WHEEL") $(shasum -a 256 "$WHEEL" 2>/dev/null | cut -d' ' -f1 || sha256sum "$WHEEL" | cut -d' ' -f1)"
  for source in "${SOURCES[@]}"; do
    echo "source $(shasum -a 256 "$SPIKE/$source" 2>/dev/null | cut -d' ' -f1 || sha256sum "$SPIKE/$source" | cut -d' ' -f1) $source"
  done
} >"$OUT/frozen-digests.txt"

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
