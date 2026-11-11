#!/usr/bin/env bash
# Checks a disk image as a downloader meets it: the image verifies and is signed, mounts
# read-only, holds only the app, the Applications link, and the volume icon, and the app
# inside is intact and carries its variant's icon: never the canary icon in a release.
# A Developer ID build must also pass Gatekeeper, and with NOTARIZE=1 the image and the
# app must carry stapled notarization tickets. Works on a downloaded image too, and
# reports whether it is quarantined.
#
#   scripts/check-dmg.sh build/Metabrowser-0.1.0-arm64.dmg
#   NOTARIZE=1 scripts/check-dmg.sh ~/Downloads/Metabrowser-0.1.0-arm64.dmg
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh

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
  note "quarantined ($quarantine): Gatekeeper assesses it when it is opened"
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
plist="$app/Contents/Info.plist"
ok "$name: $(plutil -extract CFBundleIdentifier raw -o - "$plist")" \
  "$(plutil -extract CFBundleShortVersionString raw -o - "$plist")" \
  "($(plutil -extract CFBundleVersion raw -o - "$plist")), signature valid"
if codesign -d --entitlements - --xml "$app" 2>/dev/null | grep -q '<key>'; then
  die "$name has entitlements"
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

if is_developer_id_signed "$app"; then
  ok "$name: $(codesign -dvv "$app" 2>&1 | grep -m1 '^Authority=')"
  if ((require_tickets)) || xcrun stapler validate "$dmg" >/dev/null 2>&1; then
    check_ticket "$app"
    check_ticket "$dmg"
    spctl --assess --type open --context context:primary-signature -vv "$dmg"
    spctl --assess --type execute -vv "$app"
    ok "Gatekeeper accepts the image and the app"
  else
    note "the image is not notarized, so Gatekeeper refuses it until it is (make release)"
  fi
elif ((require_tickets)); then
  die "$name is not signed with a Developer ID Application identity"
else
  note "$name is signed ad hoc: it runs on this Mac, and Gatekeeper refuses it on any Mac that downloads it"
fi
echo "Checked $dmg"
