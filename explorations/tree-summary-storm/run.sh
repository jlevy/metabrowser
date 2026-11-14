#!/bin/bash
# One trial: a fresh server on CORPUS, so its first walk runs, opened in ENGINE with
# probe.js, which opens the Commits tab CLICK_AT_MS after navigation start.
#
#   CORPUS=<dir> [DRIVER=<WebKitDriver>] [LIVE_WRITES=0.25] [FRAMES=3] \
#     explorations/tree-summary-storm/run.sh webkit|chrome|none PORT LABEL [CLICK_AT_MS]
#
# LIVE_WRITES appends to two logs in CORPUS every so many seconds, as an active
# repository is written; FRAMES adds that many same-origin pages, standing in for other
# tabs on the server. Writes LABEL.json, LABEL-server.log and LABEL-probe.js to OUT
# (default: a directory named trials beside this script; keep it out of the commit).
set -uo pipefail
ENGINE=$1
PORT=$2
LABEL=$3
CLICK_AT_MS=${4:-20000}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
CORPUS=${CORPUS:?set CORPUS to the tree make-corpus.sh built}
DRIVER=${DRIVER:-$REPO/apps/macos/.build/debug/WebKitDriver}
OUT=${OUT:-$HERE/trials}
mkdir -p "$OUT"
PROBE=$OUT/$LABEL-probe.js
{
  printf "globalThis.__stormClickAtMs = %s; globalThis.__stormFrames = %s;\n" \
    "$CLICK_AT_MS" "${FRAMES:-0}"
  cat "$HERE/probe.js"
} > "$PROBE"

cd "$REPO"
METABROWSER_REQUEST_LOG=verbose uv --config-file uv.toml run --frozen metab "$CORPUS" \
  --no-open --port "$PORT" --host 127.0.0.1 > "$OUT/$LABEL-server.log" 2>&1 &
SERVER=$!
WRITER=
trap 'kill $WRITER $SERVER 2>/dev/null; wait $SERVER 2>/dev/null' EXIT
for _ in $(seq 1 200); do
  if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/index/progress"; then break; fi
  sleep 0.1
done
if [ -n "${LIVE_WRITES:-}" ]; then
  bash "$HERE/live-writes.sh" "$CORPUS" "$LIVE_WRITES" &
  WRITER=$!
fi
URL="http://127.0.0.1:$PORT/"
case "$ENGINE" in
  webkit) "$DRIVER" measure "$URL" "$PROBE" < /dev/null > "$OUT/$LABEL.json" ;;
  chrome) node "$HERE/chrome.mjs" "$URL" "$PROBE" "$OUT/$LABEL.json" ;;
  none)
    start=$(date +%s)
    until curl -s "http://127.0.0.1:$PORT/api/index/progress" | grep -q '"status":"done"'; do
      sleep 1
    done
    echo "walk took $(( $(date +%s) - start )) s"
    ;;
  *) echo "unknown engine $ENGINE" >&2; exit 2 ;;
esac
if [ "$ENGINE" != none ]; then
  node "$HERE/summarize.mjs" "$OUT/$LABEL.json" "$OUT/$LABEL-server.log"
fi
