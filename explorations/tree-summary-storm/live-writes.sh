#!/bin/bash
# Live writes, as an active repository sees them: append a line to a log beside the
# tracked files and to one under node_modules every INTERVAL seconds. Each write moves
# the root aggregate once the walk has finished, which is what asks every open page for
# a fresh root summary.
#
#   explorations/tree-summary-storm/live-writes.sh CORPUS [INTERVAL]
set -euo pipefail
CORPUS=$1
INTERVAL=${2:-0.25}
mkdir -p "$CORPUS/logs" "$CORPUS/node_modules/pkg-0/live"
i=0
while true; do
  i=$((i + 1))
  echo "tick $i" >> "$CORPUS/logs/live.log"
  echo "tick $i" >> "$CORPUS/node_modules/pkg-0/live/ignored.log"
  sleep "$INTERVAL"
done
