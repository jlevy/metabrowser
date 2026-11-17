#!/usr/bin/env bash
# Launches a downloaded release as its downloader would, at the Mac, and checks what
# macOS did: the app copied out of the image into a scratch Downloads folder, still
# quarantined; a first launch, through Gatekeeper's prompt, which App Translocation must
# run from a randomized path; a relaunch; a move from Terminal; and a move in Finder,
# after which it must not be translocated. Interactive by design, and never run in CI.
# scripts/check-release.sh runs it with LAUNCH=1, after its other checks pass:
#
#   make macos-check-release TAG=macos-vX.Y.Z BUILT=local EXPECTED_TEAM_ID=TEAMID LAUNCH=1
#   scripts/launch-release.sh DMG
#   scripts/launch-release.sh --restore build/launch-check-TIME   # after an interrupted run
#
# It exits nonzero on any miss: a first launch that is not translocated, a launch after
# the Finder move that is, a copy out of the image that is not quarantined, and any
# confirmation answered no (answer_meaning in check-release-lib.sh). The relaunch and
# the Terminal move are recorded, not judged: their outcome is what the run measures.
#
# It runs the unmodified release bundle, whose identity is an installed release's, so it
# refuses while any Metabrowser runs, backs up that identity's defaults, the session both
# variants share, and its recent documents into build/launch-check-TIME/backup, clears
# them so the launch is a first launch, and restores them when it ends. A run that ends
# before restoring (killed, or the Mac off) leaves the backup as the only copy: the next
# run refuses until `--restore` puts it back, and `make clean` refuses to delete it.
# `--restore` refuses while any Metabrowser runs too, since a running copy saves its
# session over the restored one, and unregisters the run's copies before it deletes the
# folder. It does not back up or clear the identity's WebKit data, caches, HTTP storage,
# or saved window state, or the server logs, which a launch also writes. Each scratch
# copy is unregistered from LaunchServices afterwards, as scripts/check-setup-flows.sh
# does. On a VM or another account, which the runbook prefers, none of that state is the
# owner's.
#
# Its last lines are the record of the run for the release record (README.md, Building a
# Release).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh
# shellcheck source=check-release-lib.sh
source scripts/check-release-lib.sh

variant_settings release
lsregister=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

running_pids() {
  pgrep -f "/$product.app/Contents/MacOS/$product" || true
}
# Both variants write the one session.json, and the app saves it on every change and at
# quit, so a running copy would overwrite what a launch clears or a restore puts back.
refuse_running() {
  [[ -z "$(running_pids)" ]] ||
    die "a Metabrowser is running ($(running_pids | tr '\n' ' ')); quit every copy first, since $1"
}

if [[ "${1:-}" == --restore ]]; then
  folder="${2:?usage: scripts/launch-release.sh --restore build/launch-check-TIME}"
  refuse_running "it would save its session over the one this restores"
  [[ ! -d "$folder/mount/$product.app" ]] || detach_image "$folder/mount"
  restore_release_state "$folder/backup" "$bundle_id" ||
    die "could not restore $bundle_id's state from $folder/backup, which is kept"
  while IFS= read -r copy; do
    [[ -n "$copy" ]] || continue
    "$lsregister" -u "$copy" 2>/dev/null || note "could not unregister $copy"
  done <<<"$(launch_copies "$folder" "$product")"
  rm -rf "$folder"
  echo "Restored $bundle_id's defaults, session, and recent documents, and removed $folder"
  exit 0
fi

dmg="${1:?usage: scripts/launch-release.sh DMG, or --restore FOLDER}"
leftover="$(leftover_launch_checks "$PWD/build")"
[[ -z "$leftover" ]] ||
  die "an earlier launch check ended before restoring $bundle_id's state, and its backup is the only copy; quit Metabrowser, then restore it: scripts/launch-release.sh --restore $(head -n 1 <<<"$leftover")"
[[ -f "$dmg" ]] || die "$dmg does not exist"
[[ "${CI:-}" != true ]] || die "the launch check is interactive and never runs in CI"
[[ -t 0 ]] || die "the launch check is interactive: run it in Terminal at the Mac"
refuse_running "this launches the release identity"

state="$PWD/build/launch-check-$(date -u +%Y%m%dT%H%M%SZ)"
downloads="$state/Downloads"
moved="$state/Moved in Terminal"
finder="$state/Moved in Finder"
mounted="$state/mount"
mkdir -p "$state/backup" "$downloads" "$moved" "$finder" "$mounted"
registered=()
record=()

quit_app() {
  [[ -n "$(running_pids)" ]] || return 0
  osascript -e "tell application id \"$bundle_id\" to quit" >/dev/null 2>&1 || true
  stop_listed running_pids "the app" 20
}

cleanup() {
  local status=$? copy
  quit_app
  for copy in ${registered[@]+"${registered[@]}"}; do
    "$lsregister" -u "$copy" 2>/dev/null || note "could not unregister $copy"
  done
  [[ ! -d "$mounted/$product.app" ]] || detach_image "$mounted"
  if [[ ! -f "$state/backup/complete" ]]; then
    note "the backup did not complete, so nothing of $bundle_id's was cleared"
    rm -rf "$state"
  elif restore_release_state "$state/backup" "$bundle_id"; then
    rm -rf "$state"
  else
    check_fail "could not restore $bundle_id's defaults, session, and recent documents, which are cleared; the backup is in $state/backup: quit Metabrowser, then run scripts/launch-release.sh --restore $state"
  fi
  exit "$(check_status "$status")"
}
trap cleanup EXIT

step() {
  echo
  echo "== $1"
  shift
  local line
  for line in "$@"; do echo "   $line"; done
  read -r -p "   Press Return when done. " _
}

# Asks a yes-or-no question until the answer is one (answer_meaning) and records it; no,
# or the end of input, is a failed check. A check that fails on a typo costs a person
# several minutes and a fresh download to repeat.
ask() {
  local answer meaning=""
  while [[ -z "$meaning" ]]; do
    if ! read -r -p "   $1 [y/n] " answer; then
      record+=("$1 no answer")
      check_fail "$1 There was no answer."
      return 0
    fi
    meaning="$(answer_meaning "$answer")"
    [[ -n "$meaning" ]] || echo "   Answer y or n."
  done
  record+=("$1 $meaning")
  [[ "$meaning" == yes ]] || check_fail "$1 The answer was '$answer'."
}

# Launches the copy at "$1" as a double-click in Finder does, waits for the person at the
# Mac, then records the path it runs from and whether that is translocated. "$3" is
# translocated or installed, where it must run (ran_as_expected), or measure, to record
# it only.
launch() {
  local copy="$1" label="$2" expect="$3" pid path where
  registered+=("$copy")
  open "$copy"
  step "$label" "${@:4}"
  pid="$(running_pids | head -n 1)"
  if [[ -z "$pid" ]]; then
    check_fail "$label: no Metabrowser is running"
    record+=("$label: not running")
    return
  fi
  path="$(ps -o command= -p "$pid")"
  if is_translocated_path "$path"; then where=translocated; else where="not translocated"; fi
  record+=("$label: $where ($path)")
  echo "   runs from: $path"
  if [[ "$expect" != measure ]] && ! ran_as_expected "$path" "$expect"; then
    check_fail "$label: it ran $where, and it must run $expect"
  fi
}

backup_release_state "$state/backup" "$bundle_id"
echo "Backed up and cleared $bundle_id's defaults, session, and recent documents into $state/backup"

hdiutil attach -quiet -readonly -nobrowse -noautoopen -mountpoint "$mounted" "$dmg"
ditto "$mounted/$product.app" "$downloads/$product.app"
detach_image "$mounted"
if xattr -p com.apple.quarantine "$downloads/$product.app" >/dev/null 2>&1; then
  record+=("the copy in Downloads is quarantined, as the image's contents are")
else
  # A failed check, and quarantined anyway, so the launches still measure something.
  check_fail "the app copied out of the quarantined image is not quarantined"
  swiftc -O scripts/quarantine.swift -o "$state/quarantine" 2>/dev/null ||
    die "could not build scripts/quarantine.swift, which needs Xcode"
  "$state/quarantine" "$downloads/$product.app" >/dev/null || die "could not quarantine the copy"
  record+=("the copy in Downloads was not quarantined, so it was quarantined as a download is (simulated)")
fi

launch "$downloads/$product.app" "First launch, from the Downloads folder" translocated \
  "Gatekeeper asks whether to open Metabrowser, downloaded from the internet: choose Open." \
  "Then the launch notice: \"Move Metabrowser to Applications\", saying macOS runs it from" \
  "a temporary, read-only copy. Leave it open."
ask "Did Gatekeeper ask once, and the launch notice say it runs from a temporary copy?"
quit_app

launch "$downloads/$product.app" "Relaunch, from the same place" measure \
  "Gatekeeper should not ask again. Note whether the launch notice appears."
ask "Did it open without Gatekeeper asking?"
quit_app

mv "$downloads/$product.app" "$moved/$product.app"
launch "$moved/$product.app" "After a move from Terminal (mv)" measure \
  "Note whether the launch notice appears: a move in Finder is what Apple says ends translocation."
quit_app

open "$moved"
open "$finder"
step "Move it in Finder" \
  "Drag Metabrowser.app from \"$(basename "$moved")\" to \"$(basename "$finder")\" in Finder."
if [[ -d "$finder/$product.app" ]]; then
  launch "$finder/$product.app" "After a move in Finder" installed \
    "The launch notice should not appear: a copy moved in Finder is not translocated."
  ask "Did it open without the launch notice?"
  quit_app
else
  check_fail "$finder/$product.app is not there; was it dragged?"
fi

echo
echo "Launch record for $(basename "$dmg") on macOS $(sw_vers -productVersion), $(date -u '+%Y-%m-%d %H:%M UTC'):"
printf '  %s\n' "${record[@]}"
