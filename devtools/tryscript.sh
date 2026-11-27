#!/usr/bin/env bash
# Run tryscript in the environment the goldens are recorded in, from any shell.
#
#   devtools/tryscript.sh run tests/golden/cli-doctor.tryscript.md
#   devtools/tryscript.sh run --update tests/golden/cli-doctor.tryscript.md
#
# The Makefile's TRYSCRIPT is this script, so `make test-goldens`, `make golden-update`,
# devtools/run_goldens.py, and a command typed in a shell run tryscript with one
# environment. It was a Make variable before, whose `$$PATH` reached a shell unexpanded
# when the command was copied out of the Makefile, so the copy found no npx.
#
# - A failing gh is first on PATH (tests/no-real-gh/gh), so no golden reaches a
#   developer's signed-in gh; pytest has the same guard in tests/conftest.py.
# - The server logs a request slower than SLOW_OPERATION_LOG_SECONDS (settings.py) to
#   stderr, which a transcript captures, so a loaded machine changed what a golden
#   recorded: at a load average near 100, nine `--api` requests of
#   cli-api-cache.tryscript.md took 2.4 to 8.0 s and each printed the line. It is a
#   wall-clock measurement and not behavior, so the threshold is put past tryscript's
#   own 30 s command timeout, where it cannot fire before the command fails.
# - A golden that serves writes no event log into the state directory of whoever runs it
#   (METABROWSER_EVENT_LOG=0, as tests/conftest.py sets for pytest); one that reads the
#   log names its own directory. Nor does a stand-in gh that fails make it probe the
#   network (METABROWSER_NETWORK_PROBE=0, as tests/conftest.py also sets).
# - A free-space reserve the developer set (METABROWSER_CACHE_RESERVE_MB) would change
#   what a golden reports about the cache's volume; cli-doctor.tryscript.md, the golden
#   that reports it, sets its own.
# - uv prints a deprecation warning on every command while UV_NATIVE_TLS is set, as some
#   cloud containers set it, and a transcript captures the warning from the `uv run`
#   lines that build fixtures: cli-github-guided-review.tryscript.md and
#   cli-github-pull-files.tryscript.md failed on it. Those commands pass `--no-sync` and
#   reach no network, so the certificates uv would trust do not matter there.
#
# tryscript is run from node_modules/.bin rather than through `npx --no-install`, which
# devtools/run_goldens.py would start once for each golden. On a shared 4-processor
# machine (2026-11-26), npx took 0.36 to 0.44 s to start `tryscript --version` and the
# binary 0.12 to 0.20 s, five runs each at a load average near 1.4, and 16 goldens four at
# a time took 15.4 to 21.2 s through npx and 13.6 to 13.8 s from the binary, three runs
# each at a load average of 1.5 to 3.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tryscript="${root}/node_modules/.bin/tryscript"
if [[ ! -x "$tryscript" ]]; then
  echo "tryscript.sh: ${tryscript} is missing; run \`make install\` in ${root}" >&2
  exit 127
fi

unset METABROWSER_CACHE_RESERVE_MB UV_NATIVE_TLS
export PATH="${root}/tests/no-real-gh:${PATH}"
export METABROWSER_SLOW_SERVER_MS=60000 METABROWSER_EVENT_LOG=0 METABROWSER_NETWORK_PROBE=0
exec "$tryscript" "$@"
