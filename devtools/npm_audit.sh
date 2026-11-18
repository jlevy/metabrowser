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
# npm writes the report to stdout and its own errors to stderr, so the two are kept
# apart. A report is a finding whatever its advisories' titles say. Only stderr is
# searched for an outage, and only when there is no report. Any other failure, such
# as a missing lockfile, fails.
#
# Retries first, because most outages are brief. If the endpoint is still
# unreachable the audit is reported as NOT PERFORMED, loudly, and does not fail the
# build.
#
# Every npm package here is a dev dependency, so `--include=dev`: an ambient
# NODE_ENV=production or NPM_CONFIG_OMIT=dev would otherwise make npm audit nothing
# and report it clean.
set -uo pipefail

LEVEL="${NPM_AUDIT_LEVEL:-moderate}"
ATTEMPTS="${NPM_AUDIT_ATTEMPTS:-3}"
REPORT_HEADER="# npm audit report"
OUTAGE="audit endpoint returned an error|network timeout|ENOTFOUND|ECONNRESET|EAI_AGAIN|503 Service Unavailable"

# A count that is not a positive integer would run no attempt and report NOT PERFORMED.
if ! [[ "$ATTEMPTS" =~ ^[1-9][0-9]*$ ]]; then
  echo "npm audit: NPM_AUDIT_ATTEMPTS must be a positive integer, not '${ATTEMPTS}'; failing." >&2
  exit 2
fi

errors="$(mktemp "${TMPDIR:-/tmp}/npm-audit-stderr.XXXXXX")" || exit 2
trap 'rm -f "$errors"' EXIT
output=""

for attempt in $(seq 1 "$ATTEMPTS"); do
  output="$(npm audit --include=dev --audit-level="$LEVEL" 2>"$errors")"
  status=$?

  if [ $status -eq 0 ]; then
    echo "$output"
    cat "$errors" >&2
    echo "npm audit: no advisories at or above ${LEVEL}."
    exit 0
  fi

  # A report: the endpoint answered, and something in it is at or above the level.
  if [[ "$output" == "$REPORT_HEADER"* ]]; then
    echo "$output"
    cat "$errors" >&2
    echo "npm audit: advisories found at or above ${LEVEL}; failing." >&2
    exit "$status"
  fi

  # No report, and npm says on stderr that the endpoint did not answer.
  if grep -qiE "$OUTAGE" "$errors"; then
    cat "$errors" >&2
    echo "npm audit: advisory endpoint unreachable (attempt ${attempt}/${ATTEMPTS})."
    [ "$attempt" -lt "$ATTEMPTS" ] && sleep $((attempt * 5))
    continue
  fi

  # No report and no outage: npm itself failed, for instance without a lockfile.
  echo "$output"
  cat "$errors" >&2
  echo "npm audit: npm failed without an audit report or an outage; failing." >&2
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
