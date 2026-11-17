#!/bin/bash
# Back-to-back pairs of pr-view.mjs runs of two builds, from one environment that alternates
# only the Metabrowser wheel and the KPress version that wheel pins.
#
#   pr-view-pairs.sh <rounds> <pr|pulls|both> <label-a> <wheel-a> <label-b> <wheel-b>
#
# Environment: ROOT (measurement directory: caches, logs, profiles), ENV (the one virtual
# environment), CHECKOUT (the GitHub checkout served), OUT (the JSON lines file), UV_CONFIG
# (the checkout's uv.toml); relative paths are taken from the current directory. Make ENV
# once from the checkout's locked runtime dependencies, without the project:
#   uv --config-file uv.toml export --frozen --no-dev --no-emit-project --no-hashes \
#     --output-file <dir>/runtime-constraints.txt
#   uv --config-file uv.toml venv <dir>/env
#   uv --config-file uv.toml pip install --python <dir>/env/bin/python --compile-bytecode \
#     -r <dir>/runtime-constraints.txt
# Optionally PR_FRESH (default 470), PR_STORE (default 487),
# PR_PREP (default 514), MIN_CORE (default 1500), MIN_DISK_GB (default 2).
#
# A round is five steps, each run for both builds back to back, in the round's order (odd
# rounds a first, even rounds b first), so every step's pair is adjacent:
#
#   pr-fresh    /pull/PR_FRESH on an empty cache: no Git store, so no Diff summary. After
#               it, the same server attaches a store with PR_PREP's comparison (unrecorded).
#   pr-store    /pull/PR_STORE on that cache: a record never read, a store attached.
#   pr-warm     /pull/PR_STORE again: record, store, and comparison all cached; then the
#               same document again from the same server (pr-warm-reload).
#   pulls-cold  /pulls on an empty cache of its own.
#   pulls-warm  /pulls again on that cache, then again from the same server
#               (pulls-warm-reload).
#
# Each install compiles bytecode (--compile-bytecode): a reinstalled package otherwise
# recompiles on its first requests, which costs a larger build more and shows as a slower
# first answer from every fresh server. Before a round it stops when GitHub's core budget
# is under MIN_CORE or the disk under MIN_DISK_GB.
set -uo pipefail
rounds=$1 which=$2
labels=("$3" "$5")
wheels=("$4" "$6")
: "${ROOT:?}" "${ENV:?}" "${CHECKOUT:?}" "${OUT:?}" "${UV_CONFIG:?}"
absolute() { (cd "$(dirname "$1")" && echo "$(pwd)/$(basename "$1")"); }
ROOT=$(mkdir -p "$ROOT" && absolute "$ROOT") ENV=$(absolute "$ENV")
CHECKOUT=$(absolute "$CHECKOUT") OUT=$(absolute "$OUT") UV_CONFIG=$(absolute "$UV_CONFIG")
HERE=$(cd "$(dirname "$0")" && pwd)
PR_FRESH=${PR_FRESH:-470}
PR_STORE=${PR_STORE:-487}
PR_PREP=${PR_PREP:-514}
MIN_CORE=${MIN_CORE:-1500}
MIN_DISK_GB=${MIN_DISK_GB:-2}
UV="uv --config-file $UV_CONFIG"

use_wheel() { # <wheel>: install it and the KPress it pins, then check the environment
  local pin want got
  pin=$(unzip -p "$1" 'metabrowser-*.dist-info/METADATA' |
    sed -n 's/^Requires-Dist: \(kpress==[^ ;]*\).*/\1/p')
  $UV pip install -q --python "$ENV/bin/python" --no-deps --compile-bytecode \
    --reinstall-package metabrowser "$1" "$pin" &&
    $UV pip check -q --python "$ENV/bin/python" >/dev/null || return 1
  want="metab $(basename "$1" | cut -d- -f2)"
  got=$("$ENV/bin/metab" --version) || return 1
  [ "$got" = "$want" ] || { echo "expected '$want', got '$got'" >&2; return 1; }
}

step() { # <build index> <step name> <round>
  local i=$1 name=$2 round=$3 extra=()
  use_wheel "${wheels[$i]}" || exit 1
  case $name in
    pr-fresh) extra=(--scenario pr --pr "$PR_FRESH" --fresh-cache --prepare-store "$PR_PREP"
      --cache "$ROOT/cache-pr-${labels[$i]}" --seconds 30) ;;
    pr-store) extra=(--scenario pr --pr "$PR_STORE" --expect-summary
      --cache "$ROOT/cache-pr-${labels[$i]}" --seconds 30) ;;
    pr-warm) extra=(--scenario pr --pr "$PR_STORE" --expect-summary --reload
      --cache "$ROOT/cache-pr-${labels[$i]}" --seconds 30) ;;
    pulls-cold) extra=(--scenario pulls --fresh-cache --cache "$ROOT/cache-pulls-${labels[$i]}"
      --seconds 60) ;;
    pulls-warm) extra=(--scenario pulls --reload --cache "$ROOT/cache-pulls-${labels[$i]}"
      --seconds 30) ;;
  esac
  node "$HERE/pr-view.mjs" --metab "$ENV/bin/metab" --checkout "$CHECKOUT" --root "$ROOT" \
    --label "${labels[$i]}" --step "$name" --round "$round" --out "$OUT" "${extra[@]}"
}

case $which in
  pr) steps=(pr-fresh pr-store pr-warm) ;;
  pulls) steps=(pulls-cold pulls-warm) ;;
  *) steps=(pr-fresh pr-store pr-warm pulls-cold pulls-warm) ;;
esac
for r in $(seq "$rounds"); do
  core=$(gh api rate_limit --jq .resources.core.remaining)
  free=$(df -g / | awk 'NR==2 {print $4}')
  echo "round $r: core=$core disk=${free}G load=$(sysctl -n vm.loadavg)"
  [ "$core" -ge "$MIN_CORE" ] || { echo "stop: core budget $core < $MIN_CORE"; exit 2; }
  [ "$free" -ge "$MIN_DISK_GB" ] || { echo "stop: disk ${free}G < ${MIN_DISK_GB}G"; exit 2; }
  if [ $((r % 2)) = 1 ]; then order=(0 1); else order=(1 0); fi
  for s in "${steps[@]}"; do
    for i in "${order[@]}"; do step "$i" "$s" "$r"; done
  done
done
