#!/usr/bin/env bash
# The `ci-ok` job of .github/workflows/ci.yml: one verdict for the whole run.
#
# It fails unless every job it needs succeeded. It accepts `skipped` only for
# stack-integration, and only when the plan job found no integration to run (`none`), or
# one the other jobs already answer (`identical`, `contained`), and it says so in its log
# and summary, which are the record of the skip with the plan job's summary; a
# `conflict` fails with the message the job printed before the plan job existed. It
# never fails on main's state alone, which would keep a red main from being fixed under
# a required check.
#
# While main is red it writes one line, to its log and as a ::notice:: annotation:
#
#   main-red run=<id> head=<sha> tested=<yes|no>
#
# tested=yes means this run checked main's whole matrix on a commit that contains that
# head. AGENTS.md (Git) merges by it, read from this job's own log (`gh run view --job
# <ci-ok job id> --log`): any job of the run can print a line that looks like it, and
# `gh run view <run id>` lists every job's annotations together.
# tests/test_ci_verdict.py pins the format.
#
# Inputs, from the step's environment: RESULTS (`toJSON(needs)`), INTEGRATION,
# MAIN_STATE, MAIN_RUN, MAIN_RUN_SHA, TESTS_RED, and GITHUB_STEP_SUMMARY.

set -euo pipefail

: "${RESULTS:?}" "${GITHUB_STEP_SUMMARY:?}"
INTEGRATION=${INTEGRATION:-}
MAIN_STATE=${MAIN_STATE:-}

failed=() accepted=
rows=$(jq -r 'to_entries[] | [.key, (.value.result // "unknown")] | @tsv' <<<"$RESULTS")
{
  echo "### ci-ok"
  echo
  echo "| Job | Result |"
  echo "| --- | --- |"
} >>"$GITHUB_STEP_SUMMARY"
while IFS=$'\t' read -r job result; do
  [ -n "$job" ] || continue
  echo "| $job | $result |" >>"$GITHUB_STEP_SUMMARY"
  if [ "$result" = success ]; then
    continue
  fi
  if [ "$job" = stack-integration ] && [ "$result" = skipped ]; then
    case $INTEGRATION in
      none | identical | contained)
        accepted="stack-integration skipped: integration=$INTEGRATION (the plan job's summary says why)"
        continue
        ;;
    esac
  fi
  failed+=("$job ($result)")
done <<<"$rows"

if [ -n "$accepted" ]; then
  echo "$accepted"
  printf '\n%s\n' "$accepted" >>"$GITHUB_STEP_SUMMARY"
fi

if [ "${#failed[@]}" -eq 0 ] && [ -z "$rows" ]; then
  failed+=("no job results")
fi

status=0
if [ "$INTEGRATION" = conflict ]; then
  echo "::error::This branch conflicts with main, so the stack cannot merge as it stands."
  echo "The plan job's summary names the conflicting files."
  status=1
fi
if [ "${#failed[@]}" -gt 0 ]; then
  printf -v named '%s, ' "${failed[@]}"
  echo "::error::Not every job succeeded: ${named%, }"
  status=1
fi

if [ "$MAIN_STATE" = red ]; then
  tested=no
  if [ "${TESTS_RED:-}" = yes ]; then
    tested=yes
  fi
  line="main-red run=${MAIN_RUN:-none} head=${MAIN_RUN_SHA:-none} tested=$tested"
  echo "$line"
  echo "::notice::$line"
  printf '\n%s\n' "$line" >>"$GITHUB_STEP_SUMMARY"
fi

if [ "$status" -eq 0 ]; then
  echo "Every job this run needs succeeded."
fi
exit "$status"
