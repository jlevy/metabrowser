#!/usr/bin/env bash
# Packages an app as a compressed disk image that holds the app, a link to
# /Applications to drag it to, and the app's icon as the volume icon, then signs the
# image and writes its checksum. Only Apple's tools: ditto, hdiutil, xattr, codesign.
#
#   scripts/make-dmg.sh build/release/Metabrowser.app  # build/Metabrowser-0.1.0-arm64.dmg
#   scripts/make-dmg.sh build/dev/Metabrowser.app      # build/Metabrowser-Dev-0.1.0-arm64.dmg
#
# The image's name, volume name, version, and architecture come from the app, and its
# variant from the app's bundle identifier, since both variants are named Metabrowser.
# SIGN_IDENTITY signs the image as scripts/build-app.sh signs the app; "-" or empty (the
# default) signs it ad hoc. scripts/check-dmg.sh checks the result.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh

app="${1:?usage: scripts/make-dmg.sh APP}"
[[ -f "$app/Contents/Info.plist" ]] || die "$app is not an app bundle"
plist="$app/Contents/Info.plist"
product="$(plutil -extract CFBundleName raw -o - "$plist")"
version="$(plutil -extract CFBundleShortVersionString raw -o - "$plist")"
bundle_id="$(plutil -extract CFBundleIdentifier raw -o - "$plist")"
executable="$(plutil -extract CFBundleExecutable raw -o - "$plist")"
arch_label="$(arch_label_for "$(lipo -archs "$app/Contents/MacOS/$executable")")"
app_variant="$(variant_of_bundle_id "$bundle_id")"
[[ -n "$app_variant" ]] || die "$app has the bundle identifier $bundle_id, which is neither variant's"
dmg="$(dmg_path "$app_variant" "$version" "$arch_label")"
volume="$product $version"
identity="${SIGN_IDENTITY:--}"

work="$(mktemp -d -t metabrowser-dmg)"
mounted=""
cleanup() {
  [[ -z "$mounted" ]] || detach_image "$mounted"
  rm -rf "$work"
}
trap cleanup EXIT

stage="$work/stage"
mkdir -p "$stage"
ditto "$app" "$stage/$(basename "$app")"
ln -s /Applications "$stage/Applications"
if [[ -f "$app/Contents/Resources/AppIcon.icns" ]]; then
  cp "$app/Contents/Resources/AppIcon.icns" "$stage/.VolumeIcon.icns"
fi

# hdiutil does not carry the staging folder's own Finder flags to the volume root, so
# build a read-write image, mark its root as having a custom icon, then compress it.
hdiutil create -quiet -fs HFS+ -volname "$volume" -srcfolder "$stage" -format UDRW -ov "$work/rw.dmg"
mounted="$work/mount"
mkdir -p "$mounted"
hdiutil attach -quiet -readwrite -nobrowse -noautoopen -noverify -mountpoint "$mounted" "$work/rw.dmg"
if [[ -f "$mounted/.VolumeIcon.icns" ]]; then
  # FinderInfo is 32 bytes; bytes 8 and 9 are the Finder flags, and 0x0400 is
  # kHasCustomIcon. The volume root has no other Finder information to keep.
  xattr -wx com.apple.FinderInfo 0000000000000000040000000000000000000000000000000000000000000000 "$mounted"
fi
rm -rf "$mounted/.fseventsd" "$mounted/.Trashes"
detach_image "$mounted"
mounted=""

rm -f "$dmg" "$dmg.sha256"
hdiutil convert -quiet "$work/rw.dmg" -format UDZO -imagekey zlib-level=9 -o "$dmg"
sign "$identity" "$dmg" --identifier "$bundle_id.dmg"
codesign --verify --strict --verbose=1 "$dmg"
write_checksum "$dmg"
echo "Built $dmg: \"$volume\", $(du -h "$dmg" | cut -f1)"
