#!/usr/bin/env bash
# Builds build/Metabrowser.app from this SwiftPM package: a release build, the bundle
# layout, a generated icon, and a code signature. No Xcode project, no notarization.
#
#   scripts/build-app.sh
#   SIGN_IDENTITY="Developer ID Application: Name (TEAMID)" scripts/build-app.sh
#
# Environment:
#   SIGN_IDENTITY  codesign identity; "-" (the default) signs ad hoc, which runs on this
#                  Mac but is refused by notarization and by Gatekeeper elsewhere.
#   VERSION        CFBundleShortVersionString (default 0.1.0).
#   BUILD          CFBundleVersion (default: the commit count of HEAD).
#   ARCHES         space-separated architectures (default arm64); "arm64 x86_64" builds
#                  each slice and merges them with lipo.
#   ICON           0 skips the icon.
set -euo pipefail
cd "$(dirname "$0")/.."

product="Metabrowser"
app="build/$product.app"
version="${VERSION:-0.1.0}"
build="${BUILD:-$(git rev-list --count HEAD 2>/dev/null || echo 1)}"
identity="${SIGN_IDENTITY:--}"
arches="${ARCHES:-arm64}"

slices=()
for arch in $arches; do
  swift build -c release --arch "$arch" --product "$product"
  slices+=("$(swift build -c release --arch "$arch" --show-bin-path)/$product")
done

rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
lipo -create "${slices[@]}" -output "$app/Contents/MacOS/$product"
strip -x "$app/Contents/MacOS/$product" 2>/dev/null  # local symbols: about 0.5 MB; re-signed below
cp Resources/Info.plist "$app/Contents/Info.plist"
plutil -replace CFBundleShortVersionString -string "$version" "$app/Contents/Info.plist"
plutil -replace CFBundleVersion -string "$build" "$app/Contents/Info.plist"
printf 'APPL????' > "$app/Contents/PkgInfo"

if [[ "${ICON:-1}" != 0 ]]; then
  icns="build/AppIcon.icns"
  if [[ ! -f "$icns" || scripts/generate-icon.swift -nt "$icns" ]]; then
    rm -rf build/AppIcon.iconset
    if ! { swift scripts/generate-icon.swift build/AppIcon.iconset &&
      iconutil -c icns build/AppIcon.iconset -o "$icns"; }; then
      echo "warning: icon generation failed; the app keeps the generic icon" >&2
      rm -f "$icns"
    fi
  fi
  [[ -f "$icns" ]] && cp "$icns" "$app/Contents/Resources/AppIcon.icns"
fi

plutil -lint "$app/Contents/Info.plist"

# The hardened runtime needs no entitlements here: page JavaScript runs in Apple's
# WebContent process, and the server is a separate process with its own signature.
# Sign inside out; this bundle has no nested code yet. Never sign with --deep.
if [[ "$identity" == "-" ]]; then
  codesign --force --sign - --options runtime --timestamp=none "$app"
else
  codesign --force --sign "$identity" --options runtime --timestamp "$app"
fi
codesign --verify --deep --strict --verbose=2 "$app"
codesign -dv "$app" 2>&1 | grep -E '^(Identifier|CodeDirectory|Signature|TeamIdentifier)' || true
echo "Built $app ($(du -sh "$app" | cut -f1))"
