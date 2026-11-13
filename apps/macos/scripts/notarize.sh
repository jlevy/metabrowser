#!/usr/bin/env bash
# Notarizes each file given (an .app, submitted as a ZIP, or a .dmg), waits for Apple's
# verdict, saves the notary log, staples the ticket, and asks Gatekeeper to assess it.
#
#   APPLE_KEYCHAIN_PROFILE=metabrowser-notary scripts/notarize.sh build/release/Metabrowser.app
#
# Credentials, either:
#   APPLE_KEYCHAIN_PROFILE  a profile saved by `xcrun notarytool store-credentials`, the
#                           local choice: the secret stays in the login keychain; or
#   APPLE_API_KEY           the path of an App Store Connect API key (.p8), the CI
#                           choice, with APPLE_API_KEY_ID, and APPLE_API_ISSUER for a
#                           team key (an individual key has no issuer).
# Other settings:
#   NOTARIZE        auto (the default) skips, saying why, when the file is not signed
#                   with a Developer ID or there are no credentials; 1 fails instead; 0
#                   always skips.
#   NOTARY_TIMEOUT  how long to wait for the verdict (default 30m). Apple says most
#                   submissions finish within 5 minutes.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh

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
if [[ -n "${APPLE_KEYCHAIN_PROFILE:-}" ]]; then
  auth=(--keychain-profile "$APPLE_KEYCHAIN_PROFILE")
elif [[ -n "${APPLE_API_KEY:-}" ]]; then
  [[ -f "$APPLE_API_KEY" ]] || die "APPLE_API_KEY must be the path of an App Store Connect API key (.p8)"
  [[ -n "${APPLE_API_KEY_ID:-}" ]] || die "APPLE_API_KEY_ID is required with APPLE_API_KEY"
  auth=(--key "$APPLE_API_KEY" --key-id "$APPLE_API_KEY_ID")
  [[ -z "${APPLE_API_ISSUER:-}" ]] || auth+=(--issuer "$APPLE_API_ISSUER")
else
  skip "no notary credentials (set APPLE_KEYCHAIN_PROFILE, or APPLE_API_KEY and APPLE_API_KEY_ID)"
fi

work="$(mktemp -d -t metabrowser-notarize)"
trap 'rm -rf "$work"' EXIT

for file in "$@"; do
  name="$(basename "$file")"
  case "$file" in
    *.app)
      # The service takes a ZIP of the app, and the ticket is stapled to the app itself.
      submission="$work/${name%.app}.zip"
      ditto -c -k --keepParent "$file" "$submission"
      ;;
    *.dmg) submission="$file" ;;
    *) die "$file is not an .app or a .dmg" ;;
  esac

  echo "notarize: submitting $name; waiting up to $timeout"
  result="$(xcrun notarytool submit "$submission" "${auth[@]}" --wait --timeout "$timeout" --output-format json)" || true
  echo "$result"
  id="$(plutil -extract id raw -o - - <<<"$result" 2>/dev/null)" || die "notarize: no submission id for $name"
  status="$(plutil -extract status raw -o - - <<<"$result" 2>/dev/null)" || status="unknown"

  # Read the log even after an Accepted verdict: it lists warnings too.
  log="$(dirname "$file")/notary-${name// /-}.json"  # beside the file: both variants are Metabrowser.app
  xcrun notarytool log "$id" "${auth[@]}" "$log" || note "could not fetch the notary log of $id"
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
