#!/usr/bin/env bash
# The `plan` job of .github/workflows/ci.yml: what a run checks beyond its own jobs.
#
# The design is "A Red main" and "Stacks" in
# docs/project/specs/active/plan-2026-11-16-fast-ci.md, and tests/test_ci_plan.py holds
# each case of its rule. It writes these step outputs, and the same facts to the job
# summary, so a run always says what it decided and from what:
#
#   main-state      green or red, for a pull request to main and for any other pull
#                   request whose tested commit contains main's head, as a formal
#                   GitHub stack's does; none otherwise
#   main-run        the main run that gave that state
#   main-run-sha    that run's head while main is red; empty while it is green
#   tests-red       yes when the commit this run tests contains main-run-sha, else no
#   path            pull-request for a pull request while main is not red, which gets
#                   the short path below; main for a push to main and for a pull
#                   request while main is red, which get main's whole matrix
#   pythons         every tier's interpreters as a JSON list: PR_CHROME_PYTHON alone on
#                   the pull-request path, else PYTHONS
#   chrome          whole or none: the whole Chrome tier (make test-chrome) on the main
#                   path, and on the pull-request path when the change touches a browser
#                   path (BROWSER_PATHS); else no Chrome job at all. There is no partial
#                   tier: until 2026-11-25 a pull request left out the tests measured at
#                   20 s or more, and three that week merged green and turned main red
#                   on one of them (#835, #855, #858; bead mb-593d)
#   unit-shards, goldens-shards, chrome-shards, admitted-git-shards
#                   each tier's parts as a JSON list of I/N, every I from 1 to N
#   admitted-gits   the Git releases admitted-git builds: PR_ADMITTED_GIT alone on the
#                   pull-request path, else ADMITTED_GITS
#   integration     for a stacked pull request: contained when the tested commit
#                   already contains main's head; else identical, needed, or conflict,
#                   by whether merging main into the head changes the tree; none for
#                   anything but a stacked pull request
#   main-sha        the main commit a needed stack-integration merges
#
# Its inputs are the step's environment: EVENT, BASE, HEAD_SHA, REPO, GH_TOKEN, PYTHONS,
# PR_CHROME_PYTHON, ADMITTED_GITS, PR_ADMITTED_GIT, GITHUB_OUTPUT, and GITHUB_STEP_SUMMARY. HEAD is the commit the other
# jobs check out: for a pull request, its merge with the base branch.
#
# Not knowing main's state costs runner minutes, never coverage: a read that fails, or
# answers with a run id or head that is not one, counts as red, which runs main's whole
# matrix.

set -euo pipefail

: "${EVENT:?}" "${PYTHONS:?}" "${PR_CHROME_PYTHON:?}" "${GITHUB_OUTPUT:?}" "${GITHUB_STEP_SUMMARY:?}"
: "${ADMITTED_GITS:?}" "${PR_ADMITTED_GIT:?}"
BASE=${BASE:-}
HEAD_SHA=${HEAD_SHA:-}
REPO=${REPO:-}

# The push runs of ci.yml on main that one read returns, newest first. A first attempt
# still going is passed over, so the page has to reach past every push to main still
# running at once. Agents merge only once main's newest run has completed (AGENTS.md,
# Git), so few are. This is GitHub's default page size.
RUNS_PER_PAGE=30

# The parts each tier is dealt into, on the main path and on the pull-request path. A
# pull request runs one interpreter, so it can afford more, shorter parts: the owner
# asked for a routine cycle of about three minutes (the fast CI plan, 2026-11-22), which
# is some 140 s for the slowest job after the 30 s a run takes to start and before
# ci-ok. A job spends 45 to 60 s before its first test: 16 to 30 s of checkout and
# setup, then make install and pytest's collection of the whole suite, 27 to 40 s (runs
# 45062416967 and 45069289704). The pull-request counts, with what run 45069289704
# measured of each, dealt by the seconds in devtools/shard_weights.json:
#
#   unit      4. In 3, the parts took 150 to 189 s: 480 s of tests on four workers in
#             127 s, after 58 s. One file, tests/test_github_pulls.py, takes 112 s on its
#             worker, so no count brings its part under about 175 s; 4 brings the others
#             to about 140.
#   goldens   3 on both paths: 115 to 133 s on the pull request's interpreter, a third
#             of the goldens (63 s at four at a time) and of the serial tier, with one
#             collection between them. In two, the slower interpreters' parts took 3.9
#             minutes of the job's 5 on main (run 45066732637).
#   chrome    4 on main and 6 on a pull request, which runs the whole tier as main
#             does. Its 84 tests took 1065 s, each test's median over the interpreters
#             of main's runs 45752768224 and 45751344037. Dealt by the committed weights
#             that is 244 to 297 s of tests a part in 4, 197 to 234 in 5, 155 to 198 in
#             6, and 117 to 174 in 7. Until 2026-11-25 a pull request ran 4 parts
#             without the 14 tests measured at 20 s or more (451 s of the 1065): 131 to
#             180 s of tests a part, in jobs of 181 to 255 s (runs 45752121797 and
#             45747488810). So 6 parts add 18 s to the longest part and two jobs to the
#             run; 7 would add none and a third job, about a minute of setup each. One
#             test takes 94 s, the floor under any count.
#   admitted-git  2 on the one release: 146 to 163 s. Its 572 s of tests on four workers
#             include tests/test_github_pulls.py at 108 s on its worker, so a third part
#             would not shorten the longest.
UNIT_SHARDS_MAIN=2 UNIT_SHARDS_PR=4
GOLDENS_SHARDS_MAIN=3 GOLDENS_SHARDS_PR=3
CHROME_SHARDS_MAIN=4 CHROME_SHARDS_PR=6
ADMITTED_GIT_SHARDS_MAIN=1 ADMITTED_GIT_SHARDS_PR=2

# Prints the parts 1/N through N/N as a JSON list.
shards() {
  jq -cn --argjson count "$1" '[range(1; $count + 1) | "\(.)/\($count)"]'
}

# The paths a change has to touch for a pull request to run the Chrome tier while main is
# green: what a Chrome test can see in the browser, and what decides or runs the tier.
# The owner's direction (the fast CI plan, 2026-11-22): a change to the CLI or the
# backend alone does not pay for Chrome on its pull request. A backend change can still
# break a Chrome test, since each drives a real server; every push to main runs the whole
# tier on every interpreter, and that is the net. A change that does touch one runs
# every Chrome test, since nothing narrower is safe: #858 renumbered keys in the shell's
# scripts and broke a test of the Files tab that pressed the old one. Each entry is a
# shell pattern, in which
# `*` also matches `/`, then a tab, then why it is here.
BROWSER_PATHS=(
  $'src/metabrowser/static/*\tthe shell: the scripts, styles, and vendored libraries the browser loads'
  $'src/metabrowser/builtin_plugins/*\tbuilt-in plugins: their manifests, renderers, and styles'
  $'src/metabrowser/server.py\tbuilds the shell page and writes METABROWSER_SETTINGS and the plugin manifest into it'
  $'src/metabrowser/settings.py\twhat METABROWSER_SETTINGS carries'
  $'src/metabrowser/keymap.py\tthe reserved key table METABROWSER_SETTINGS carries'
  $'src/metabrowser/capabilities.py\tthe content-trust capabilities the client settings carry'
  $'src/metabrowser/source_kind_marks.py\tthe glyphs the shell writes into its first paint'
  $'src/metabrowser/asset_stamps.py\tthe addresses the shell loads its assets from'
  $'src/metabrowser/encoded_assets.py\thow the shell\'s assets are served'
  $'src/metabrowser/plugin_loader/*\tthe plugin manifest the shell is configured from'
  $'src/metabrowser/plugin_paths.py\twhich plugin directories are loaded'
  $'package.json\tthe Node packages the Chrome and DOM harnesses run on'
  $'package-lock.json\tthe Node packages the Chrome and DOM harnesses run on'
  $'pyproject.toml\tthe Python packages the server under Chrome runs on, and pytest\'s settings'
  $'uv.lock\tthe Python packages the server under Chrome runs on'
  $'.github/workflows/ci.yml\tthe workflow that runs the tier'
  $'.github/workflows/nightly.yml\tthe soak that repeats the tier'
  $'Makefile\tthe targets that run the tier'
  $'devtools/ci_*\tthis decision and the verdict on it'
  $'devtools/shard_weights*\tthe measured seconds the tier is dealt into parts by'
  $'tests/*\ttest support the Chrome tests share: fixtures, helpers, the DOM harness, and conftest'
)

# How many of the changed browser paths the summary names.
NAMED_PATHS=8

# Prints why a changed path can change what a Chrome test sees, or nothing. Under tests/,
# a golden never does: they are tryscript transcripts of the CLI, which no Chrome test
# reads. A test module does when it asks for Chrome, by the chrome_profile fixture or
# require_chrome, which every module of the Chrome tier does (tests/suite_tiers.py,
# tests/suite_gates.py); one a Chrome module only imports a helper from does not, and
# main is where a break through it shows. Everything else there is shared support.
# Otherwise the first of BROWSER_PATHS that matches decides.
browser_reason() {
  local path=$1 entry pattern reason
  case $path in
    \"*)
      echo "a path git quotes, which is not matched against the patterns"
      return
      ;;
    tests/golden/*) return ;;
    tests/test_*.py)
      if git grep -qE 'chrome_profile|require_chrome' HEAD -- "$path" 2>/dev/null; then
        echo "a test module that asks for Chrome"
      fi
      return
      ;;
  esac
  for entry in "${BROWSER_PATHS[@]}"; do
    pattern=${entry%%$'\t'*} reason=${entry#*$'\t'}
    # shellcheck disable=SC2053 # the right side is a pattern on purpose
    if [[ $path == $pattern ]]; then
      echo "$reason"
      return
    fi
  done
}

# Prints "<green|red> <run id> <head sha>" for main by the rule of A Red main, or
# "red none none" when no run in the page has a completed attempt. Fails when a read
# fails or answers with something other than runs.
main_state_from_api() {
  local runs rows id status attempt conclusion sha previous
  runs=$(gh api "repos/$REPO/actions/workflows/ci.yml/runs?branch=main&event=push&exclude_pull_requests=true&per_page=$RUNS_PER_PAGE") || return 1
  rows=$(jq -r '.workflow_runs[] | [.id, .status, .run_attempt, (.conclusion // "none"), .head_sha] | @tsv' <<<"$runs") || return 1
  while IFS=$'\t' read -r id status attempt conclusion sha; do
    [ -n "$id" ] || continue
    # The id goes into a request path and the outputs, and the head to git: refuse a
    # shape either should not have.
    [[ $id =~ ^[0-9]+$ && $sha =~ ^[0-9a-f]{40}$ ]] || return 1
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
if ! jq -e --arg git "$PR_ADMITTED_GIT" 'type == "array" and index($git) != null' \
  <<<"$ADMITTED_GITS" >/dev/null; then
  echo "::error::PR_ADMITTED_GIT ($PR_ADMITTED_GIT) must be one of ADMITTED_GITS ($ADMITTED_GITS)"
  exit 1
fi

# A stacked pull request: main's head, and whether the commit this run tests contains it.
# A formal GitHub stack's merge ref merges the head into its base merged with main, so
# it does; an informal chain's merges the head into the branch below alone.
main_sha= contains_main=no
if [ "$EVENT" = pull_request ] && [ "$BASE" != main ]; then
  [[ $HEAD_SHA =~ ^[0-9a-f]{40}$ ]] || {
    echo "::error::HEAD_SHA ($HEAD_SHA) is not a commit"
    exit 1
  }
  git fetch --quiet --no-tags origin main
  main_sha=$(git rev-parse FETCH_HEAD)
  rc=0
  git merge-base --is-ancestor "$main_sha" HEAD || rc=$?
  case $rc in
    0) contains_main=yes ;;
    1) ;;
    *)
      echo "::error::git merge-base exited $rc asking whether HEAD contains main ($main_sha)"
      exit 1
      ;;
  esac
fi

# main's state is read wherever the red-main rule can apply: a pull request to main, and
# one whose tested commit contains main's head (the plan's "A Red main"). An informal
# chain's run tests no main, so it is not.
main_state=none main_run= main_run_sha= tests_red=no why=
if [ "$EVENT" = pull_request ] && { [ "$BASE" = main ] || [ "$contains_main" = yes ]; }; then
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

chrome_note=
if [ "$EVENT" = pull_request ] && [ "$main_state" != red ]; then
  # The short path: one interpreter, the lowest admitted Git, more and shorter parts,
  # and the Chrome tier, all of it, only when the change touches a browser path.
  path=pull-request
  pythons=$(jq -cn --arg python "$PR_CHROME_PYTHON" '[$python]')
  admitted_gits=$(jq -cn --arg git "$PR_ADMITTED_GIT" '[$git]')
  unit_shards=$(shards "$UNIT_SHARDS_PR")
  goldens_shards=$(shards "$GOLDENS_SHARDS_PR")
  chrome_shards=$(shards "$CHROME_SHARDS_PR")
  admitted_git_shards=$(shards "$ADMITTED_GIT_SHARDS_PR")
  chrome=whole
  # What the pull request changes: the merge commit this run tests against its first
  # parent, the base branch. Anything that keeps that from being read runs Chrome.
  touched=() count=0
  if ! git rev-parse --quiet --verify 'HEAD^2' >/dev/null; then
    chrome_note="the commit this run tests is not a merge commit, so its change is not read"
  elif ! changed=$(git -c core.quotePath=true diff --name-only 'HEAD^1' HEAD); then
    chrome_note="the change could not be read"
  else
    while IFS= read -r changed_path; do
      [ -n "$changed_path" ] || continue
      reason=$(browser_reason "$changed_path")
      [ -n "$reason" ] || continue
      count=$((count + 1))
      # The summary names the first few; one is enough to decide.
      if [ "$count" -le "$NAMED_PATHS" ]; then
        touched+=("\`$changed_path\` ($reason)")
      fi
    done <<<"$changed"
    if [ "$count" -eq 0 ]; then
      chrome=none
      chrome_note="no changed path is a browser path (BROWSER_PATHS in devtools/ci_plan.sh), so no Chrome job runs; every push to main runs the whole tier"
    else
      printf -v chrome_note '%s; ' "${touched[@]}"
      chrome_note="for $count changed browser path(s): ${chrome_note%; }"
      if [ "$count" -gt "$NAMED_PATHS" ]; then
        chrome_note+="; and $((count - NAMED_PATHS)) more"
      fi
    fi
  fi
else
  # A push to main, or a pull request while main is red: main's whole matrix.
  path=main
  pythons=$(jq -c . <<<"$PYTHONS")
  admitted_gits=$(jq -c . <<<"$ADMITTED_GITS")
  unit_shards=$(shards "$UNIT_SHARDS_MAIN")
  goldens_shards=$(shards "$GOLDENS_SHARDS_MAIN")
  chrome_shards=$(shards "$CHROME_SHARDS_MAIN")
  admitted_git_shards=$(shards "$ADMITTED_GIT_SHARDS_MAIN")
  chrome=whole
  chrome_note="the main path"
fi

integration=none tested_tree= merged_tree= conflicts=
if [ "$EVENT" = pull_request ] && [ "$BASE" != main ]; then
  tested_tree=$(git rev-parse "HEAD^{tree}") # the merge commit the other jobs check out
fi
if [ "$contains_main" = yes ]; then
  # The other jobs already check the head with main and every layer below it; merging
  # main into the head alone would check a subset of that, which never lands.
  integration=contained
elif [ "$EVENT" = pull_request ] && [ "$BASE" != main ]; then
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
  echo "path=$path"
  echo "pythons=$pythons"
  echo "chrome=$chrome"
  echo "unit-shards=$unit_shards"
  echo "goldens-shards=$goldens_shards"
  echo "chrome-shards=$chrome_shards"
  echo "admitted-git-shards=$admitted_git_shards"
  echo "admitted-gits=$admitted_gits"
  echo "integration=$integration"
  echo "main-sha=$main_sha"
  echo "main-state=$main_state"
  echo "main-run=$main_run"
  echo "main-run-sha=$main_run_sha"
  echo "tests-red=$tests_red"
} | tee -a "$GITHUB_OUTPUT"

case $integration in
  none) integration_note="not a stacked pull request" ;;
  contained) integration_note="the commit this run tests (tree $tested_tree) already contains main ($main_sha), so the other jobs check it" ;;
  identical) integration_note="merging main ($main_sha) leaves tree $tested_tree, which the other jobs check" ;;
  needed) integration_note="merging main ($main_sha) gives tree $merged_tree, not $tested_tree, so the stack-integration jobs check it" ;;
  conflict) integration_note="merging main ($main_sha) conflicts in: $(tr "\n" " " <<<"$conflicts")" ;;
esac
if [ "$main_state" = none ] && [ "$EVENT" = pull_request ]; then
  main_note="not read: the commit this run tests does not contain main's head ($main_sha)"
elif [ "$main_state" = none ]; then
  main_note="not read: only a pull request reads it"
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
  echo "| Path | $path: unit, goldens, and serial on $pythons in $unit_shards and $goldens_shards |"
  if [ "$chrome" = none ]; then
    echo "| Chrome tier | none: $chrome_note |"
  else
    echo "| Chrome tier | whole (make test-chrome), slow tests included: $chrome_note, in $chrome_shards on $pythons |"
  fi
  echo "| admitted-git | $admitted_gits in $admitted_git_shards |"
  echo "| stack-integration | $integration: $integration_note |"
} | tee -a "$GITHUB_STEP_SUMMARY"
