#!/usr/bin/env bash
# Builds the app bundle from this SwiftPM package: a release build, the bundle layout,
# the variant's identity and icon, and a code signature. No Xcode project.
#
#   scripts/build-app.sh                    # build/Metabrowser Dev.app, signed ad hoc
#   VARIANT=release scripts/build-app.sh    # build/Metabrowser.app
#   VARIANT=release SIGN_IDENTITY="Developer ID Application: Name (TEAMID)" scripts/build-app.sh
#
# Environment:
#   VARIANT        dev (the default) or release; scripts/common.sh lists what each sets.
#   SIGN_IDENTITY  codesign identity; "-" or empty (the default) signs ad hoc, which runs
#                  on this Mac but is refused by notarization and by Gatekeeper elsewhere.
#   BUILD          CFBundleVersion (default: the commit count of HEAD).
#   ARCHES         space-separated architectures (default arm64); "arm64 x86_64" builds
#                  each slice and merges them with lipo.
#   ICON           0 skips the icon.
#
# CFBundleShortVersionString is the VERSION file, and nothing overrides it.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh

variant_settings "${VARIANT:-dev}"
build="$(build_number)"
identity="${SIGN_IDENTITY:--}"
executable="Metabrowser"  # the SwiftPM product, and CFBundleExecutable in both variants
arches="${ARCHES:-arm64}"
if [[ "${ICON:-1}" != 0 && ! -f "$icon_source" ]]; then
  die "$icon_source does not exist; scripts/build-icon.sh builds it"
fi

slices=()
for arch in $arches; do
  swift build -c release --arch "$arch" --product "$executable"
  slices+=("$(swift build -c release --arch "$arch" --show-bin-path)/$executable")
done

rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
lipo -create "${slices[@]}" -output "$app/Contents/MacOS/$executable"
strip -x "$app/Contents/MacOS/$executable" 2>/dev/null  # local symbols: about 0.5 MB; re-signed below

plist="$app/Contents/Info.plist"
cp Resources/Info.plist "$plist"
plutil -replace CFBundleIdentifier -string "$bundle_id" "$plist"
plutil -replace CFBundleName -string "$product" "$plist"
plutil -replace CFBundleDisplayName -string "$product" "$plist"
plutil -replace CFBundleShortVersionString -string "$version" "$plist"
plutil -replace CFBundleVersion -string "$build" "$plist"
[[ -z "$scheme_suffix" ]] || suffix_url_schemes "$plist" "$scheme_suffix" "$bundle_id"
printf 'APPL????' >"$app/Contents/PkgInfo"

# The variant's icon: the canary icon for dev, the published icon for release.
[[ "${ICON:-1}" == 0 ]] || cp "$icon_source" "$app/Contents/Resources/AppIcon.icns"

plutil -lint "$plist"

# The hardened runtime needs no entitlements here: page JavaScript runs in Apple's
# WebContent process, and the server is a separate process with its own signature.
# Sign inside out; this bundle has no nested code yet. Never sign with --deep.
sign "$identity" "$app" --options runtime
codesign --verify --deep --strict --verbose=2 "$app"
if codesign -d --entitlements - --xml "$app" 2>/dev/null | grep -q '<key>'; then
  die "$app has entitlements; add one only for a verified need, and document it here"
fi
codesign -dvv "$app" 2>&1 | grep -E '^(Identifier|CodeDirectory|Signature|Authority|Timestamp|TeamIdentifier)' || true
echo "Built $app: $variant $version ($build), $(du -sh "$app" | cut -f1)"
