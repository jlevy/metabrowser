#!/usr/bin/env bash
# Notarizes each file given (an .app, submitted as a ZIP, or a .dmg): checks it as the
# notary service would, submits it and waits for Apple's verdict, saves and reads the
# notary log, staples the ticket, and asks Gatekeeper to assess it.
#
#   APPLE_KEYCHAIN_PROFILE=metabrowser-notary scripts/notarize.sh build/release/Metabrowser.app
#
# Credentials, either:
#   APPLE_KEYCHAIN_PROFILE  a profile saved by `xcrun notarytool store-credentials` in the
#                           release keychain (SIGN_KEYCHAIN; release_keychain in
#                           common.sh), the local choice: the secret stays there; or
#   APPLE_API_KEY           the path of an App Store Connect API key (.p8), the CI
#                           choice, with APPLE_API_KEY_ID, and APPLE_API_ISSUER for a
#                           team key (an individual key has no issuer).
# Other settings:
#   NOTARIZE        auto (the default) skips, saying why, when the file is not signed
#                   with a Developer ID or there are no credentials; 1 fails instead, and
#                   also fails when the notary log cannot be fetched or read; 0 always
#                   skips.
#   NOTARY_TIMEOUT  how long to wait for the verdict (default 30m). Apple says most
#                   submissions finish within 5 minutes.
#
# Before each submission, `syspolicy_check notary-submission` runs on the app, or on the
# app inside the image, and a failure stops here. After it, the log is saved beside the
# file as notary-NAME.json and read (scripts/notary-lib.sh): an issue of severity error
# fails, each warning is printed with its path, and one "notary record:" line gives the
# submission ID, the status, and the counts for the release record.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh
# shellcheck source=notary-lib.sh
source scripts/notary-lib.sh

(($# > 0)) || die "usage: scripts/notarize.sh APP_OR_DMG..."
mode="${NOTARIZE:-auto}"
case "$mode" in auto | 0 | 1) ;; *) die "NOTARIZE must be auto, 0, or 1, not '$mode'" ;; esac
timeout="${NOTARY_TIMEOUT:-30m}"

skip() {
  [[ "$mode" != 1 ]] || die "notarize: $1"
  echo "notarize: skipped: $1"
  exit 0
}

[[ "$mode" != 0 ]] || skip "NOTARIZE=0"
for file in "$@"; do
  [[ -e "$file" ]] || die "$file does not exist"
  is_developer_id_signed "$file" ||
    skip "$file is not signed with a Developer ID Application identity, and the notary service accepts no other (set SIGN_IDENTITY)"
done
notary_credentials ||
  skip "no notary credentials (set APPLE_KEYCHAIN_PROFILE, or APPLE_API_KEY and APPLE_API_KEY_ID)"
command -v jq >/dev/null || die "jq is missing; macOS includes it from macOS 15, and the notary log is read with it"

work="$(scratch_dir metabrowser-notarize)"
mounted=""
cleanup() {
  [[ -z "$mounted" ]] || detach_image "$mounted"
  rm -rf "$work"
}
trap cleanup EXIT

for file in "$@"; do
  name="$(basename "$file")"
  case "$file" in
    *.app)
      presubmission_check "$file" || die "notarize: $name fails the notary service's checks; nothing was submitted"
      # The service takes a ZIP of the app, and the ticket is stapled to the app itself.
      submission="$work/${name%.app}.zip"
      ditto -c -k --keepParent "$file" "$submission"
      ;;
    *.dmg)
      mounted="$work/mount"
      mkdir -p "$mounted"
      hdiutil attach -quiet -readonly -nobrowse -noautoopen -mountpoint "$mounted" "$file"
      apps=("$mounted"/*.app)
      [[ ${#apps[@]} == 1 && -d "${apps[0]}" ]] || die "notarize: $name must hold exactly one app"
      presubmission_check "${apps[0]}" || die "notarize: the app in $name fails the notary service's checks; nothing was submitted"
      detach_image "$mounted"
      mounted=""
      submission="$file"
      ;;
    *) die "$file is not an .app or a .dmg" ;;
  esac

  echo "notarize: submitting $name; waiting up to $timeout"
  result="$(xcrun notarytool submit "$submission" "${notary_auth[@]}" --wait --timeout "$timeout" --output-format json)" || true
  echo "$result"
  id="$(jq -er '.id | strings' <<<"$result" 2>/dev/null)" || die "notarize: no submission id for $name"
  status="$(jq -er '.status | strings' <<<"$result" 2>/dev/null)" || status="unknown"

  # Read the log even after an Accepted verdict: it lists warnings too.
  log="$(dirname "$file")/notary-${name// /-}.json"  # beside the file: both variants are Metabrowser.app
  rm -f "$log"
  if fetch_notary_log "$id" "$log"; then
    verdict=0
    read_notary_log "$log" || verdict=$?
  else
    echo "notary log: could not fetch the log of $id"
    verdict=2
  fi
  case "$verdict" in
    1) die "notarize: the notary log of $name lists errors, or a status other than Accepted; see $log" ;;
    2)
      [[ "$mode" != 1 ]] || die "notarize: the notary log of $name could not be fetched or read, and NOTARIZE=1 needs it"
      note "the notary log of $name could not be fetched or read, so its warnings are unknown"
      ;;
  esac
  [[ "$status" == Accepted ]] || die "notarize: $name was not accepted (status $status); see $log"

  xcrun stapler staple "$file"
  xcrun stapler validate "$file"
  case "$file" in
    *.app) spctl --assess --type execute -vv "$file" ;;
    *.dmg)
      spctl --assess --type open --context context:primary-signature -vv "$file"
      # Stapling rewrote the image, so its checksum must be written again.
      [[ ! -f "$file.sha256" ]] || write_checksum "$file"
      ;;
  esac
  echo "notarize: $name is notarized and stapled"
done
