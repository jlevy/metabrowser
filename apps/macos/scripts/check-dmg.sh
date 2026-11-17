#!/usr/bin/env bash
# Checks a disk image as a downloader meets it: the image verifies and is signed, mounts
# read-only, holds only the app, the Applications link, and the volume icon, and the app
# inside is intact and carries its variant's icon: never the canary icon in a release.
# The app is signed with the hardened runtime, ad hoc or not. A Developer ID build must
# also carry a secure timestamp, a Team ID (EXPECTED_TEAM_ID when set), and the chain to
# Apple Root CA on the app and the image, and pass Gatekeeper: stapled tickets,
# `syspolicy_check distribution` on the app, `codesign --check-notarization` on both,
# and `spctl` on both. With NOTARIZE=1 every one of those is required; otherwise the
# notarization checks run once the image is stapled. Works on a downloaded image too,
# and describes its quarantine attribute, for information only. With EXPECTED_VERSION
# and EXPECTED_COMMIT (a full SHA), which scripts/check-release.sh sets from the tag, the
# app must also be the release variant, that version, and built from that commit with
# nothing uncommitted.
#
#   scripts/check-dmg.sh build/Metabrowser-0.1.0-arm64.dmg
#   NOTARIZE=1 EXPECTED_TEAM_ID=TEAMID scripts/check-dmg.sh ~/Downloads/Metabrowser-0.1.0-arm64.dmg
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh
# shellcheck source=gatekeeper-lib.sh
source scripts/gatekeeper-lib.sh

dmg="${1:?usage: scripts/check-dmg.sh DMG}"
[[ -f "$dmg" ]] || die "$dmg does not exist"
require_tickets=0
[[ "${NOTARIZE:-auto}" != 1 ]] || require_tickets=1

ok() {
  echo "ok: $*"
}

# A stapled ticket is required with NOTARIZE=1 and reported otherwise.
check_ticket() {
  if xcrun stapler validate "$1" >/dev/null 2>&1; then
    ok "$1 has a stapled notarization ticket"
  elif ((require_tickets)); then
    die "$1 has no stapled notarization ticket"
  else
    note "$1 has no stapled ticket; it is not notarized, or Gatekeeper must look it up online"
  fi
}

hdiutil verify -quiet "$dmg"
ok "hdiutil verify"
codesign --verify --strict "$dmg"
ok "the image's signature is valid"
if quarantine="$(xattr -p com.apple.quarantine "$dmg" 2>/dev/null)"; then
  note "quarantined: $(describe_quarantine "$quarantine") (for information: the attribute's format is not API); Gatekeeper assesses it when it is opened"
else
  note "not quarantined: a browser download is, a local build or a curl download is not"
fi

work="$(mktemp -d -t metabrowser-check)"
mounted=""
cleanup() {
  [[ -z "$mounted" ]] || detach_image "$mounted"
  rm -rf "$work"
}
trap cleanup EXIT
mounted="$work/mount"
mkdir -p "$mounted"
hdiutil attach -quiet -readonly -nobrowse -noautoopen -mountpoint "$mounted" "$dmg"
ok "attached read-only at $mounted"

apps=("$mounted"/*.app)
[[ ${#apps[@]} == 1 && -d "${apps[0]}" ]] || die "the image must hold exactly one app"
app="${apps[0]}"
name="$(basename "$app")"
expected="$(printf '%s\n' .VolumeIcon.icns Applications "$name" | sort)"
actual="$(cd "$mounted" && ls -A | sort)"
[[ "$actual" == "$expected" ]] || die "the image holds:"$'\n'"$actual"$'\n'"expected:"$'\n'"$expected"
[[ -L "$mounted/Applications" && "$(readlink "$mounted/Applications")" == /Applications ]] ||
  die "Applications is not a link to /Applications"
flags="$(xattr -px com.apple.FinderInfo "$mounted" 2>/dev/null | tr -d ' \n' | cut -c17-18)"
((0x${flags:-00} & 0x04)) || die "the volume root does not show its custom icon"
ok "contents: $name, Applications -> /Applications, and the volume icon"

plutil -lint -s "$app/Contents/Info.plist"
codesign --verify --deep --strict "$app"
require_no_entitlements "$app"
plist="$app/Contents/Info.plist"
ok "$name: $(plutil -extract CFBundleIdentifier raw -o - "$plist")" \
  "$(plutil -extract CFBundleShortVersionString raw -o - "$plist")" \
  "($(plutil -extract CFBundleVersion raw -o - "$plist")), signature valid"
if [[ -n "${EXPECTED_VERSION:-}${EXPECTED_COMMIT:-}" ]]; then
  [[ -n "${EXPECTED_VERSION:-}" && -n "${EXPECTED_COMMIT:-}" ]] || die "EXPECTED_VERSION and EXPECTED_COMMIT go together"
  problems="$(release_identity_problems "$(plutil -extract CFBundleIdentifier raw -o - "$plist")" \
    "$(plutil -extract CFBundleShortVersionString raw -o - "$plist")" \
    "$(plutil -extract MetabrowserSourceCommit raw -o - "$plist" 2>/dev/null || true)" \
    "$EXPECTED_VERSION" "$EXPECTED_COMMIT")"
  [[ -z "$problems" ]] || die "$name is not the release it is checked as:"$'\n'"$problems"
  ok "$name is the release variant, version $EXPECTED_VERSION, built from $EXPECTED_COMMIT"
fi
# The canary icon marks development builds and never ships in a release, and a release
# carries the published icon. The icons compared are this checkout's, so check an image
# from the commit that built it.
icon="$app/Contents/Resources/AppIcon.icns"
cmp -s "$icon" "$mounted/.VolumeIcon.icns" || die "the volume icon is not the app's icon"
shipped_id="$(plutil -extract CFBundleIdentifier raw -o - "$plist")"
shipped_variant="$(variant_of_bundle_id "$shipped_id")"
[[ -n "$shipped_variant" ]] || die "$name has the bundle identifier $shipped_id, which is neither variant's"
published_icon="$(icon_of_variant release)"
canary_icon="$(icon_of_variant dev)"
for expected_icon in "$published_icon" "$canary_icon"; do
  [[ -f "$expected_icon" ]] || die "$expected_icon does not exist; scripts/build-icon.sh builds it"
done
if [[ "$shipped_variant" == release ]]; then
  if cmp -s "$icon" "$canary_icon"; then
    die "$name is a release build with the canary icon ($canary_icon)"
  fi
  cmp -s "$icon" "$published_icon" || die "$name is a release build without the published icon ($published_icon)"
  ok "$name has the published icon"
else
  if cmp -s "$icon" "$published_icon"; then
    die "$name is a development build with the published icon"
  fi
  cmp -s "$icon" "$canary_icon" || die "$name is a development build without the canary icon ($canary_icon)"
  ok "$name has the canary icon"
fi

# The hardened runtime, which build-app.sh signs with whatever the identity: notarization
# requires it, and an ad hoc build without it would hide that until a release.
app_facts="$(codesign -dvvv "$app" 2>&1)" || die "codesign could not read the signature of $name: $app_facts"
app_facts="$(signature_facts <<<"$app_facts")"
[[ "$(fact runtime <<<"$app_facts")" == 1 ]] || die "$name is not signed with the hardened runtime"
ok "$name is signed with the hardened runtime"

# Runs one of Gatekeeper's checks, and stops with its output when it refuses.
gatekeeper() {
  local output
  output="$("$@" 2>&1)" || die "$* refused: $output"
}

if is_developer_id_signed "$app"; then
  image_facts="$(codesign -dvvv "$dmg" 2>&1)" || die "codesign could not read the image's signature: $image_facts"
  image_facts="$(signature_facts <<<"$image_facts")"
  for kind in app image; do
    if [[ "$kind" == app ]]; then facts="$app_facts"; else facts="$image_facts"; fi
    problems="$(developer_id_problems "$facts" "$kind" "${EXPECTED_TEAM_ID:-}")"
    [[ -z "$problems" ]] || die "the $kind's Developer ID signature has:"$'\n'"$problems"
  done
  [[ "$(fact team <<<"$app_facts")" == "$(fact team <<<"$image_facts")" ]] ||
    die "the app and the image are signed by different teams"
  ok "$name and the image: $(fact authorities <<<"$app_facts" | cut -d'|' -f1), team $(fact team <<<"$app_facts")${EXPECTED_TEAM_ID:+, as EXPECTED_TEAM_ID says}, a secure timestamp, and the chain to Apple Root CA"
  if ((require_tickets)) || xcrun stapler validate "$dmg" >/dev/null 2>&1; then
    check_ticket "$app"
    check_ticket "$dmg"
    gatekeeper spctl --assess --type open --context context:primary-signature -vv "$dmg"
    gatekeeper spctl --assess --type execute -vv "$app"
    ok "Gatekeeper accepts the image and the app (spctl)"
    # Apple DTS's check for an app on macOS 14 and later.
    gatekeeper syspolicy_check distribution "$app"
    ok "$name passes syspolicy_check distribution"
    # DTS gives this for code other than an app; on an app and an image it is this
    # repository's own check, which only a signed release can prove.
    gatekeeper codesign -vvvv -R="notarized" --check-notarization "$app"
    gatekeeper codesign -vvvv -R="notarized" --check-notarization "$dmg"
    ok "codesign --check-notarization finds the app and the image notarized"
  else
    note "the image is not notarized, so Gatekeeper refuses it until it is (make release)"
  fi
elif ((require_tickets)); then
  die "$name is not signed with a Developer ID Application identity"
else
  note "$name is signed ad hoc: it runs on this Mac, and Gatekeeper refuses it on any Mac that downloads it"
fi
echo "Checked $dmg"
