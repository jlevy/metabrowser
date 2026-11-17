#!/usr/bin/env bash
# The `plan` job of .github/workflows/ci.yml: what a run checks beyond its own jobs.
#
# The design is "A Red main" and "Stacks" in
# docs/project/specs/active/plan-2026-11-16-fast-ci.md, and tests/test_ci_plan.py holds
# each case of its rule. It writes these step outputs, and the same facts to the job
# summary, so a run always says what it decided and from what:
#
#   main-state      for a pull request to main: green or red; none otherwise
#   main-run        the main run that gave that state
#   main-run-sha    that run's head while main is red; empty while it is green
#   tests-red       yes when the commit this run tests contains main-run-sha, else no
#   chrome-pythons  the Chrome tier's interpreters as a JSON list: PR_CHROME_PYTHON
#                   alone for a pull request while main is not red, PYTHONS otherwise
#   integration     for a stacked pull request: identical, needed, or conflict, by
#                   whether merging main changes the tree; none otherwise
#   main-sha        the main commit a needed stack-integration merges
#
# Its inputs are the step's environment: EVENT, BASE, HEAD_SHA, REPO, GH_TOKEN, PYTHONS,
# PR_CHROME_PYTHON, GITHUB_OUTPUT, and GITHUB_STEP_SUMMARY. HEAD is the commit the other
# jobs check out: for a pull request, its merge with the base branch.
#
# Not knowing main's state costs runner minutes, never coverage: a read that fails
# counts as red, which runs main's whole matrix.

set -euo pipefail

: "${EVENT:?}" "${PYTHONS:?}" "${PR_CHROME_PYTHON:?}" "${GITHUB_OUTPUT:?}" "${GITHUB_STEP_SUMMARY:?}"
BASE=${BASE:-}
HEAD_SHA=${HEAD_SHA:-}
REPO=${REPO:-}

# The push runs of ci.yml on main that one read returns, newest first. A first attempt
# still going is passed over, so the page has to reach past every push to main still
# running at once. Agents merge only once main's newest run has completed (AGENTS.md,
# Git), so few are. This is GitHub's default page size.
RUNS_PER_PAGE=30

# Prints "<green|red> <run id> <head sha>" for main by the rule of A Red main, or
# "red none none" when no run in the page has a completed attempt. Fails when a read
# fails or answers with something other than runs.
main_state_from_api() {
  local runs rows id status attempt conclusion sha previous
  runs=$(gh api "repos/$REPO/actions/workflows/ci.yml/runs?branch=main&event=push&exclude_pull_requests=true&per_page=$RUNS_PER_PAGE") || return 1
  rows=$(jq -r '.workflow_runs[] | [.id, .status, .run_attempt, (.conclusion // "none"), .head_sha] | @tsv' <<<"$runs") || return 1
  while IFS=$'\t' read -r id status attempt conclusion sha; do
    [ -n "$id" ] || continue
    case $attempt in '' | *[!0-9]*) return 1 ;; esac
    if [ "$status" != completed ]; then
      # A first attempt still going says nothing yet, so the run before it decides.
      [ "$attempt" -gt 1 ] || continue
      # A rerun still going: the attempt before it, which has completed, decides.
      previous=$(gh api "repos/$REPO/actions/runs/$id/attempts/$((attempt - 1))") || return 1
      conclusion=$(jq -r '.conclusion // "none"' <<<"$previous") || return 1
    fi
    # Only success is green: failure, cancelled, timed out, and anything else are red.
    if [ "$conclusion" = success ]; then
      echo "green $id $sha"
    else
      echo "red $id $sha"
    fi
    return 0
  done <<<"$rows"
  echo "red none none"
}

if ! jq -e --arg python "$PR_CHROME_PYTHON" 'type == "array" and index($python) != null' \
  <<<"$PYTHONS" >/dev/null; then
  echo "::error::PR_CHROME_PYTHON ($PR_CHROME_PYTHON) must be one of PYTHONS ($PYTHONS)"
  exit 1
fi

main_state=none main_run= main_run_sha= tests_red=no why=
if [ "$EVENT" = pull_request ] && [ "$BASE" = main ]; then
  if answer=$(main_state_from_api); then
    read -r main_state main_run main_run_sha <<<"$answer"
  else
    main_state=red
    why="main's state could not be read"
    echo "::warning::$why, so this run checks main's whole matrix"
  fi
  if [ "$main_run" = none ]; then
    main_run= main_run_sha=
    why="no push run of ci.yml on main among the newest $RUNS_PER_PAGE has a completed attempt"
  fi
  if [ "$main_state" = red ] && [ -z "$why" ]; then
    # Whether the merge commit this run tests contains the head of main's red run.
    # Exit 1 is "not an ancestor"; anything else, such as 128, is a missing commit.
    rc=0
    git merge-base --is-ancestor "$main_run_sha" HEAD || rc=$?
    case $rc in
      0) tests_red=yes ;;
      1) why="the merge commit this run tests predates $main_run_sha" ;;
      *)
        why="git merge-base exited $rc: $main_run_sha is missing from the clone"
        echo "::warning::tests-red is no because $why"
        ;;
    esac
  fi
  if [ "$main_state" = green ]; then
    main_run_sha= # named only while main is red
  fi
fi

if [ "$EVENT" = pull_request ] && [ "$main_state" != red ]; then
  chrome=$(jq -cn --arg python "$PR_CHROME_PYTHON" '[$python]')
else
  chrome=$(jq -c . <<<"$PYTHONS") # a push to main, or a pull request while main is red
fi

integration=none main_sha= tested_tree= merged_tree= conflicts=
if [ "$EVENT" = pull_request ] && [ "$BASE" != main ]; then
  : "${HEAD_SHA:?}"
  git fetch --quiet --no-tags origin main
  main_sha=$(git rev-parse FETCH_HEAD)
  tested_tree=$(git rev-parse "HEAD^{tree}") # the merge commit the other jobs check out
  # Exit 1 is a conflict, and the tree is then the first line; anything else is an error.
  rc=0
  merged=$(git merge-tree --write-tree --name-only --no-messages "$HEAD_SHA" "$main_sha") || rc=$?
  case $rc in
    0)
      merged_tree=$merged
      if [ "$merged_tree" = "$tested_tree" ]; then
        integration=identical
      else
        integration=needed
      fi
      ;;
    1)
      merged_tree=$(head -n 1 <<<"$merged")
      conflicts=$(tail -n +2 <<<"$merged")
      integration=conflict
      ;;
    *)
      echo "::error::git merge-tree exited $rc merging main ($main_sha) into $HEAD_SHA"
      exit 1
      ;;
  esac
fi

{
  echo "chrome-pythons=$chrome"
  echo "integration=$integration"
  echo "main-sha=$main_sha"
  echo "main-state=$main_state"
  echo "main-run=$main_run"
  echo "main-run-sha=$main_run_sha"
  echo "tests-red=$tests_red"
} | tee -a "$GITHUB_OUTPUT"

case $integration in
  none) integration_note="not a stacked pull request" ;;
  identical) integration_note="merging main ($main_sha) leaves tree $tested_tree, which the other jobs check" ;;
  needed) integration_note="merging main ($main_sha) gives tree $merged_tree, not $tested_tree, so the stack-integration jobs check it" ;;
  conflict) integration_note="merging main ($main_sha) conflicts in: $(tr "\n" " " <<<"$conflicts")" ;;
esac
if [ "$main_state" = none ]; then
  main_note="not read: only a pull request to main reads it"
else
  main_note="$main_state, run ${main_run:-none}${main_run_sha:+, head $main_run_sha}; tests-red=$tests_red${why:+ ($why)}"
fi
{
  echo "### What this run checks"
  echo
  echo "| | |"
  echo "| --- | --- |"
  echo "| Event | $EVENT |"
  echo "| Base | ${BASE:-none} |"
  echo "| main | $main_note |"
  echo "| Chrome tier | $chrome |"
  echo "| stack-integration | $integration: $integration_note |"
} | tee -a "$GITHUB_STEP_SUMMARY"
