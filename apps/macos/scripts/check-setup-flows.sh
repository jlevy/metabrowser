  # Before the image is detached, since the copy launched may be on it.
  [[ -z "$launched" ]] || "$lsregister" -u "$launched" || note "could not unregister $launched"
  [[ ! -d "$volume" ]] || detach_image "$volume"
#!/usr/bin/env bash
# Manual checks of what a new user sees first, on the built development app: the first
# run without metab, an older metab and an upgrade under a running server, and a launch
# from a disk image. A person watches the screen; the script sets up each case, says
# what to look for, waits for Return between steps, and checks that no server is left.
#
#   make macos-app            # first, and `make install` at the repository root
#   scripts/check-setup-flows.sh no-metab|old-metab|disk-image
#
# Each run uses a copy of the app with its own bundle identifier, so it never reads or
# changes the development app's saved runtime, recent folders, or LaunchServices entry,
# and a scratch HOME, so discovery finds only what the script puts there. Nothing is
# downloaded or installed: "installing" uv or metab links the uv on PATH and this
# checkout's .venv/bin/metab into the scratch ~/.local/bin, which is all the app sees
# of a real install. The scratch folder's server log stays in ~/Library/Logs/Metabrowser.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh

scenario="${1:-}"
case "$scenario" in
  no-metab | old-metab | disk-image) ;;
  *) die "usage: scripts/check-setup-flows.sh no-metab|old-metab|disk-image" ;;
esac

variant_settings dev
[[ -d "$app" ]] || die "$app is missing; run make macos-app first"
checkout_metab="$(cd ../.. && pwd)/.venv/bin/metab"
[[ -x "$checkout_metab" ]] || die "$checkout_metab is missing; run make install at the repository root"
uv_path="$(command -v uv)" || die "uv is not on PATH"
for other in /opt/homebrew/bin/metab /usr/local/bin/metab; do
  [[ ! -e "$other" ]] || die "$other would be found before the scratch HOME's; these checks need a Mac without it"
done

check_id="io.github.jlevy.metabrowser.setupcheck"
# Canonical, as the app opens folders, so a server's command line names this path.
work="$(cd "$(mktemp -d -t metabrowser-setup-check)" && pwd -P)"
home="$work/home"
folder="$work/notes"
copy="$work/Metabrowser Setup Check.app"
volume="$work/volume"
mkdir -p "$home" "$folder"
printf '# Notes\n\nA folder for the setup checks.\n' >"$folder/README.md"
lsregister=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
# The copy LaunchServices registered by opening it, which cleanup unregisters.
launched=""

running_pids() {
  pgrep -f "$work/.*/Contents/MacOS/" || true
}

server_pids() {
  pgrep -f -- "metab $folder" || true
}

cleanup() {
  local pid tries=0
  for pid in $(running_pids); do kill -TERM "$pid"; done
  while [[ -n "$(running_pids)" ]] && ((tries < 30)); do
    sleep 0.5
    tries=$((tries + 1))
  done
  if [[ -n "$(running_pids)" ]]; then
    note "FAIL: the app did not quit within 15 s of SIGTERM, killing it: $(running_pids)"
    for pid in $(running_pids); do kill -KILL "$pid"; done
  fi
  if [[ -n "$(server_pids)" ]]; then
    note "FAIL: servers left running after the app quit, stopping them: $(server_pids)"
    pkill -TERM -f -- "metab $folder" || note "could not stop them"
  fi
  # Before the image is detached, since the copy launched may be on it.
  [[ -z "$launched" ]] || "$lsregister" -u "$launched" || note "could not unregister $launched"
  [[ ! -d "$volume" ]] || detach_image "$volume"
  defaults delete "$check_id" 2>/dev/null || true  # absent when the app saved nothing
  rm -rf "$work"
}
trap cleanup EXIT

step() {
  echo
  echo "== $1"
  shift
  local line
  for line in "$@"; do echo "   $line"; done
  read -r -p "   Press Return when checked. " _
}

# A link made under a temporary name and renamed over the target, as an installer
# replaces a file: the app never sees a half-made one.
install_link() {
  ln -s "$1" "$2.new"
  mv -f "$2.new" "$2"
}

install_script() {
  printf '%s\n' "$1" >"$2.new"
  chmod 755 "$2.new"
  mv -f "$2.new" "$2"
}

# Prints the version a metab reports, without the checkout's description.
version_of() {
  "$1" --version | sed -n 's/^metab \([^ ]*\).*/\1/p'
}

launch() {
  local bundle="$1"
  shift
  launched="$bundle"
  open -n -F -a "$bundle" --env HOME="$home" --env METABROWSER_METAB= --env UV_TOOL_BIN_DIR= \
    --env XDG_BIN_HOME= --env XDG_DATA_HOME= "$@"
}

ditto "$app" "$copy"
plutil -replace CFBundleIdentifier -string "$check_id" "$copy/Contents/Info.plist"
sign - "$copy" 2>/dev/null
mkdir -p "$home/.local/bin"
current="$(version_of "$checkout_metab")"
echo "Scratch HOME: $home"
echo "Folder: $folder"
echo "This checkout's metab: $current"

case "$scenario" in
  no-metab)
    launch "$copy" "$folder"
    step "No uv and no metab" \
      "Settings opens: \"Metabrowser needs the metab command-line tool\"." \
      "1. Install uv, with the curl command and Copy (and \"brew install uv\" if Homebrew is installed)." \
      "2. Install metab: \"In a new Terminal window, so that it finds uv:\" and uv tool install metabrowser." \
      "\"Waiting for metab in ~/.local/bin…\" and the uv tool update-shell suggestion." \
      "No folder window opens."
    install_link "$uv_path" "$home/.local/bin/uv"
    step "uv installed (linked into the scratch ~/.local/bin)" \
      "Within a few seconds, without clicking anything, only \"1. Install metab.\" is left."
    install_link "$checkout_metab" "$home/.local/bin/metab"
    step "metab installed (this checkout's, linked into the scratch ~/.local/bin)" \
      "Within a few seconds, without clicking anything, the notes folder opens in its own window." \
      "Settings shows metab $current from ~/.local/bin."
    ;;
  old-metab)
    install_link "$uv_path" "$home/.local/bin/uv"
    install_script '#!/bin/sh
[ "$1" = --version ] && { echo "metab 0.12.0"; exit 0; }
echo "this stand-in for an old metab only reports its version" >&2
exit 1' "$home/.local/bin/metab"
    launch "$copy" "$folder"
    step "An older metab (a stand-in that reports 0.12.0)" \
      "Settings opens: \"Metabrowser needs metab 0.12.1 or later\"." \
      "1. Upgrade metab: ~/.local/bin/metab is metab 0.12.0, and Metabrowser needs 0.12.1 or later." \
      "The command is uv tool install --upgrade 'metabrowser>=0.12.1', with Copy." \
      "No folder window opens."
    if [[ -n "$(server_pids)" ]]; then
      note "FAIL: a server started from the older metab: $(server_pids)"
    else
      echo "   ok: no server is running for the folder"
    fi
    install_link "$checkout_metab" "$home/.local/bin/metab"
    step "Upgraded (the stand-in replaced by this checkout's metab)" \
      "Within a few seconds, without clicking anything, the notes folder opens in its own window."
    install_script "#!/bin/sh
[ \"\$1\" = --version ] && { echo \"metab 0.13.0\"; exit 0; }
exec \"$checkout_metab\" \"\$@\"" "$home/.local/bin/metab"
    step "Upgraded again under the running server (a wrapper that reports 0.13.0)" \
      "Within a few seconds an alert: \"metab was updated to 0.13.0\"," \
      "\"1 open folder runs a server started from metab ${current%%+*}…\"." \
      "Restart Servers reloads the folder's window on a new port; Settings shows metab 0.13.0."
    ;;
  disk-image)
    install_link "$checkout_metab" "$home/.local/bin/metab"
    mkdir -p "$work/image"
    ditto "$copy" "$work/image/Metabrowser Setup Check.app"
    hdiutil create -quiet -volname "Metabrowser Setup Check" -srcfolder "$work/image" -format UDZO "$work/check.dmg"
    hdiutil attach -quiet -readonly -nobrowse -mountpoint "$volume" "$work/check.dmg"
    launch "$volume/Metabrowser Setup Check.app"
    step "Opened from a disk image" \
      "An alert: \"Move Metabrowser to Applications\", naming the disk image \"Metabrowser Setup Check\"." \
      "Show in Finder opens the Applications folder and selects the app in the image; nothing is moved." \
      "Continue dismisses it, and Don't remind me stops it for this copy's identity."
    ;;
esac
echo
echo "Quitting the app and checking that no server is left."
