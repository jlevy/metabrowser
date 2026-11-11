#!/usr/bin/env bash
# The whole release, in order: build and sign the app, notarize and staple it, package
# it as a disk image, notarize and staple the image, check the image as a downloader
# meets it, and write its checksum and, for the release variant, a Homebrew cask.
#
#   SIGN_IDENTITY="Developer ID Application: Name (TEAMID)" \
#     APPLE_KEYCHAIN_PROFILE=metabrowser-notary scripts/release.sh   # official
#   NOTARIZE=0 scripts/release.sh             # rehearsal: ad hoc, notarization skipped
#   VARIANT=dev NOTARIZE=0 scripts/release.sh # a development DMG (`make dmg`)
#
# VARIANT defaults to release here, and the release variant defaults to NOTARIZE=1: an
# official build, which must be signed with a Developer ID, notarized, built from a
# commit, and carry the published icon, and which checks all of that before it builds.
# NOTARIZE=0 rehearses the same steps and says which it skipped; the dev variant
# defaults to NOTARIZE=auto. SIGN_IDENTITY, the notary credentials, and ARCHES are
# documented in build-app.sh and notarize.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh

export VARIANT="${VARIANT:-release}"
variant_settings "$VARIANT"
if [[ "$variant" == release ]]; then
  export NOTARIZE="${NOTARIZE:-1}"
else
  export NOTARIZE="${NOTARIZE:-auto}"
fi

# An official build checks what it needs before it spends a build on it.
if [[ "$NOTARIZE" == 1 ]]; then
  problems=()
  if [[ "${SIGN_IDENTITY:--}" == "-" ]]; then
    problems+=("SIGN_IDENTITY is not set; an official build is signed with a Developer ID Application identity")
  elif ! security find-identity -v -p codesigning | grep -qF -- "$SIGN_IDENTITY"; then
    problems+=("no valid signing identity matches SIGN_IDENTITY in the keychain search list")
  fi
  if [[ -z "${APPLE_KEYCHAIN_PROFILE:-}" && -z "${APPLE_API_KEY:-}" ]]; then
    problems+=("no notary credentials: set APPLE_KEYCHAIN_PROFILE, or APPLE_API_KEY and APPLE_API_KEY_ID")
  fi
  if [[ "$variant" == release && ! -f "$icon_source" ]]; then
    problems+=("$icon_source does not exist; an official build carries the published icon")
  fi
  if [[ "$variant" == release && -n "$(git status --porcelain -- . 2>/dev/null)" ]]; then
    problems+=("apps/macos has uncommitted changes; an official build is built from a commit")
  fi
  if ((${#problems[@]})); then
    printf 'error: %s\n' "${problems[@]}" >&2
    die "not an official build; NOTARIZE=0 rehearses it with an ad hoc signature"
  fi
elif [[ -n "$(git status --porcelain -- . 2>/dev/null)" ]]; then
  note "apps/macos has uncommitted changes, so this build matches no commit"
fi

scripts/build-app.sh
# The app is notarized and stapled before it is packaged, so a copy dragged out of the
# image carries its own ticket and opens without reaching Apple.
scripts/notarize.sh "$app"
scripts/make-dmg.sh "$app"
scripts/notarize.sh "$dmg"
scripts/check-dmg.sh "$dmg"

sha256="$(cut -d' ' -f1 "$dmg.sha256")"
outputs=("$app" "$dmg" "$dmg.sha256")
if [[ "$variant" == release ]]; then
  cask="build/metabrowser-app.rb"
  write_cask "$dmg" "$cask" "$version" "$arch_label"
  outputs+=("$cask")
fi

if is_developer_id_signed "$dmg" && xcrun stapler validate "$dmg" >/dev/null 2>&1; then
  state="Developer ID signed, notarized, and stapled"
elif is_developer_id_signed "$dmg"; then
  state="Developer ID signed, not notarized: Gatekeeper refuses it"
else
  state="signed ad hoc, not notarized: for this Mac only"
fi
[[ "$NOTARIZE" != 1 && "$variant" == release ]] && state="$state; a rehearsal, not an official build"
echo
echo "$product $version ($(build_number)), $arch_label, $state:"
for output in "${outputs[@]}"; do
  if [[ -d "$output" ]]; then
    size="$(du -sk "$output" | cut -f1) KB on disk"
  else
    size="$(stat -f %z "$output") bytes"
  fi
  printf '  %-44s %s\n' "$output" "$size"
done
echo "  sha256 $sha256"
