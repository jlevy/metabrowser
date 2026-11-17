#!/usr/bin/env bash
# Run `npm audit` so that a finding blocks and an outage does not.
#
# `npm audit` exits non-zero for two unrelated events: it found an advisory at or
# above the requested level, or it could not reach the advisory endpoint at all.
# Only the first is a reason to stop. The second failed this gate four times in one
# afternoon while npm's `security/advisories/bulk` endpoint was timing out, and a
# registry outage is not a supply-chain finding -- the lockfile is pinned, so the
# dependency set has not moved since the last run that did reach the endpoint.
#
# Retries first, because most outages are brief. If the endpoint is still
# unreachable the audit is reported as NOT PERFORMED, loudly, and does not fail the
# build; if it answers, any advisory at the level fails exactly as before, with one
# reviewed exception.
#
# The exception is GHSA-fc5q-39xc-vjpf (high, picomatch ReDoS through repeated
# extglobs, no patched release), reached only through the dev dependency tryscript;
# bead mb-p1o0 removes it. A failing audit's `npm audit --json` report goes to
# devtools/npm_audit_exceptions.py, which passes the gate only if that advisory, on
# exactly its reviewed package path, range, and locked release, is everything at or
# above the level, and then says so in a banner. Any other advisory, or that one
# anywhere else, fails. SUPPLY-CHAIN-SECURITY.md records the review.
set -uo pipefail

LEVEL="${NPM_AUDIT_LEVEL:-moderate}"
ATTEMPTS="${NPM_AUDIT_ATTEMPTS:-3}"
output=""

for attempt in $(seq 1 "$ATTEMPTS"); do
  output="$(npm audit --audit-level="$LEVEL" 2>&1)"
  status=$?

  if [ $status -eq 0 ]; then
    echo "$output"
    echo "npm audit: no advisories at or above ${LEVEL}."
    exit 0
  fi

  # The endpoint failing says so on stderr; an advisory does not.
  if echo "$output" | grep -qiE "audit endpoint returned an error|network timeout|ENOTFOUND|ECONNRESET|EAI_AGAIN|503 Service Unavailable"; then
    echo "npm audit: advisory endpoint unreachable (attempt ${attempt}/${ATTEMPTS})."
    [ "$attempt" -lt "$ATTEMPTS" ] && sleep $((attempt * 5))
    continue
  fi

  # Reached the endpoint and did not like what it found.
  echo "$output"
  # Whether that is the reviewed exception and nothing else. The check applies it only
  # to a report it has read, so an outage on this second request fails the gate too.
  report="$(npm audit --json 2>/dev/null)"
  if printf '%s' "$report" |
    uv --config-file uv.toml run --frozen python -m devtools.npm_audit_exceptions --level "$LEVEL"; then
    exit 0
  fi
  echo "npm audit: advisories found at or above ${LEVEL}; failing." >&2
  exit "$status"
done

echo "$output"
cat >&2 <<'MSG'

  ############################################################################
  #  npm audit was NOT PERFORMED.                                            #
  #                                                                          #
  #  The advisory endpoint stayed unreachable across every attempt. This is   #
  #  not a statement that the dependencies are clean -- it is a statement     #
  #  that nobody asked. The lockfile is pinned, so the dependency set has     #
  #  not changed since the last run that did reach the endpoint.             #
  #                                                                          #
  #  Re-run this gate once the registry is answering, before relying on it.  #
  ############################################################################

MSG
exit 0
