#!/usr/bin/env bash
# Launches a downloaded release as its downloader would, at the Mac, and records what
# macOS did: the app copied out of the image into a scratch Downloads folder, still
# quarantined; a first launch, through Gatekeeper's prompt, which App Translocation runs
# from a randomized path; a relaunch; a move from Terminal; and a move in Finder.
# Interactive by design, and never run in CI. scripts/check-release.sh runs it with
# LAUNCH=1, after its other checks pass:
#
#   make macos-check-release TAG=macos-vX.Y.Z BUILT=local LAUNCH=1
#   scripts/launch-release.sh DMG
#
# It runs the unmodified release bundle, whose identity is an installed release's, so it
# refuses while any Metabrowser runs, backs up that identity's defaults, the session
# both variants share, and its recent documents into build/, clears them so the launch
# is a first launch, and restores them when it ends; a backup it could not restore stays
# in build/, and the script says where. Each scratch copy is unregistered from
# LaunchServices afterwards, as scripts/check-setup-flows.sh does. On a VM or another
# account, which the runbook prefers, none of that state is the owner's.
#
# Its last lines are the record of the run for the release record (README.md, Building a
# Release).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh
# shellcheck source=check-release-lib.sh
source scripts/check-release-lib.sh

dmg="${1:?usage: scripts/launch-release.sh DMG}"
[[ -f "$dmg" ]] || die "$dmg does not exist"
[[ "${CI:-}" != true ]] || die "the launch check is interactive and never runs in CI"
[[ -t 0 ]] || die "the launch check is interactive: run it in Terminal at the Mac"
variant_settings release
lsregister=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

running_pids() {
  pgrep -f "/$product.app/Contents/MacOS/$product" || true
}
[[ -z "$(running_pids)" ]] ||
  die "a Metabrowser is running ($(running_pids | tr '\n' ' ')); quit every copy first, since this launches the release identity"

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
  if restore_release_state "$state/backup" "$bundle_id"; then
    rm -rf "$state"
  else
    check_fail "could not restore $bundle_id's defaults, session, and recent documents; the backup is in $state/backup"
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

# Asks a yes-or-no question and records the answer.
ask() {
  local answer
  read -r -p "   $1 [y/n] " answer
  record+=("$1 ${answer:-no answer}")
}

# Launches the copy at "$1" as a double-click in Finder does, waits for the person at the
# Mac, then records the path it runs from and whether that is translocated.
launch() {
  local copy="$1" label="$2" pid path
  registered+=("$copy")
  open "$copy"
  step "$label" "${@:3}"
  pid="$(running_pids | head -n 1)"
  if [[ -z "$pid" ]]; then
    check_fail "$label: no Metabrowser is running"
    record+=("$label: not running")
    return
  fi
  path="$(ps -o command= -p "$pid")"
  if is_translocated_path "$path"; then
    record+=("$label: translocated ($path)")
  else
    record+=("$label: not translocated ($path)")
  fi
  echo "   runs from: $path"
}

backup_release_state "$state/backup" "$bundle_id"
echo "Backed up and cleared $bundle_id's defaults, session, and recent documents into $state/backup"

hdiutil attach -quiet -readonly -nobrowse -noautoopen -mountpoint "$mounted" "$dmg"
ditto "$mounted/$product.app" "$downloads/$product.app"
detach_image "$mounted"
if xattr -p com.apple.quarantine "$downloads/$product.app" >/dev/null 2>&1; then
  record+=("the copy in Downloads is quarantined, as the image's contents are")
else
  # Recorded, since it means a copy out of a quarantined image is not quarantined here.
  swiftc -O scripts/quarantine.swift -o "$state/quarantine" 2>/dev/null ||
    die "could not build scripts/quarantine.swift, which needs Xcode"
  "$state/quarantine" "$downloads/$product.app" >/dev/null || die "could not quarantine the copy"
  record+=("the copy in Downloads was not quarantined, so it was quarantined as a download is (simulated)")
fi

launch "$downloads/$product.app" "First launch, from the Downloads folder" \
  "Gatekeeper asks whether to open Metabrowser, downloaded from the internet: choose Open." \
  "Then the launch notice: \"Move Metabrowser to Applications\", saying macOS runs it from" \
  "a temporary, read-only copy. Leave it open."
ask "Did Gatekeeper ask once, and the launch notice say it runs from a temporary copy?"
quit_app

launch "$downloads/$product.app" "Relaunch, from the same place" \
  "Gatekeeper should not ask again. Note whether the launch notice appears."
ask "Did it open without Gatekeeper asking?"
quit_app

mv "$downloads/$product.app" "$moved/$product.app"
launch "$moved/$product.app" "After a move from Terminal (mv)" \
  "Note whether the launch notice appears: a move in Finder is what Apple says ends translocation."
quit_app

open "$moved"
open "$finder"
step "Move it in Finder" \
  "Drag Metabrowser.app from \"$(basename "$moved")\" to \"$(basename "$finder")\" in Finder."
[[ -d "$finder/$product.app" ]] || check_fail "$finder/$product.app is not there; was it dragged?"
launch "$finder/$product.app" "After a move in Finder" \
  "The launch notice should not appear: a copy moved in Finder is not translocated."
quit_app

echo
echo "Launch record for $(basename "$dmg") on macOS $(sw_vers -productVersion), $(date -u '+%Y-%m-%d %H:%M UTC'):"
printf '  %s\n' "${record[@]}"
