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
# One `npm audit --json` request per attempt decides: its status, and its answer.
# An answer that is an audit report is a finding, whatever its advisories' titles
# say; only an answer that is not a report can be an outage, and only when it says
# the endpoint failed. npm's text report is fetched afterwards for reading only.
#
# The exception is GHSA-fc5q-39xc-vjpf (high, picomatch ReDoS through repeated
# extglobs, no patched release), reached only through the dev dependency tryscript;
# bead mb-p1o0 removes it. A failing report goes to devtools/npm_audit_exceptions.py,
# which passes the gate only if that advisory, exactly as reviewed and on exactly its
# reviewed path, is everything at or above the level, and then says so in a banner.
# Any other advisory, or that one changed or anywhere else, fails.
# SUPPLY-CHAIN-SECURITY.md records the review.
set -uo pipefail

LEVEL="${NPM_AUDIT_LEVEL:-moderate}"
ATTEMPTS="${NPM_AUDIT_ATTEMPTS:-3}"
OUTAGE="audit endpoint returned an error|network timeout|ENOTFOUND|ECONNRESET|EAI_AGAIN|503 Service Unavailable"
# devtools/npm_audit_exceptions.py's NOT_A_REPORT: npm's answer is not an audit report.
NOT_A_REPORT=3
answer=""
errors="$(mktemp)"
trap 'rm -f "$errors"' EXIT

# npm's text report, for the log. Its status and content decide nothing.
show_text_report() {
  npm audit --audit-level="$LEVEL" 2>&1
  return 0
}

for attempt in $(seq 1 "$ATTEMPTS"); do
  answer="$(npm audit --json --audit-level="$LEVEL" 2>"$errors")"
  status=$?

  if [ $status -eq 0 ]; then
    show_text_report
    echo "npm audit: no advisories at or above ${LEVEL}."
    exit 0
  fi

  verdict="$(uv --config-file uv.toml run --frozen python -m devtools.npm_audit_exceptions \
    --level "$LEVEL" <<<"$answer" 2>&1)"
  checked=$?

  if [ $checked -eq $NOT_A_REPORT ]; then
    # Not a report. The endpoint failing says so; any other error fails the gate.
    if grep -qiE "$OUTAGE" "$errors" || grep -qiE "$OUTAGE" <<<"$answer"; then
      echo "npm audit: advisory endpoint unreachable (attempt ${attempt}/${ATTEMPTS})."
      [ "$attempt" -lt "$ATTEMPTS" ] && sleep $((attempt * 5))
      continue
    fi
    echo "$answer"
    cat "$errors" >&2
    echo "$verdict" >&2
    echo "npm audit: npm returned an error, not an audit report; failing." >&2
    exit "$status"
  fi

  # Reached the endpoint and did not like what it found.
  show_text_report
  echo "$verdict" >&2
  if [ $checked -eq 0 ]; then
    exit 0
  fi
  echo "npm audit: advisories found at or above ${LEVEL}; failing." >&2
  exit "$status"
done

echo "$answer"
cat "$errors"
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
