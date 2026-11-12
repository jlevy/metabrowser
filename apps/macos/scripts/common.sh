# Shared by the scripts in this folder, and sourced, never run: the two variants, the
# version, the build number, and small helpers. Each script first changes to apps/macos.
# shellcheck shell=bash

# Apple's tools first. A shim earlier on PATH, such as a Python `xattr` installed as a
# tool, must not change what a release runs, or break it.
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

die() {
  echo "error: $*" >&2
  exit 1
}

note() {
  echo "note: $*" >&2
}

# Runs "$@" with its output held back, and stops with that output if it fails, so a
# chatty tool stays quiet without hiding why it failed.
quietly() {
  local output
  output="$("$@" 2>&1)" || die "$1 failed: $output"
}

# The variant decides the bundle's identity. Two copies with one bundle identifier share
# user defaults, privacy (TCC) grants, and LaunchServices registration, and a URL scheme
# claimed twice has no defined target, so a development build never takes the release
# identity. Every local build is dev, with the canary (gold-rimmed) icon; only the
# release targets build release, the identity and published icon of official builds.
# Both are named Metabrowser, so each builds into a folder of its own, and their images
# and artifacts keep the variant in their file names:
#
#   release  build/release/Metabrowser.app, io.github.jlevy.metabrowser,
#            Resources/AppIcon.icns, build/Metabrowser-VERSION-ARCH.dmg
#   dev      build/dev/Metabrowser.app, io.github.jlevy.metabrowser.dev,
#            Resources/AppIcon-Dev.icns, build/Metabrowser-Dev-VERSION-ARCH.dmg, and
#            every URL scheme the property list declares with a -dev suffix
#
# Sets variant, product, bundle_id, icon_source, scheme_suffix, artifact_label, version,
# arch_label, app, and dmg.
variant_settings() {
  variant="$1"
  product="Metabrowser"
  case "$variant" in
    release)
      bundle_id="io.github.jlevy.metabrowser"
      icon_source="Resources/AppIcon.icns"
      scheme_suffix=""
      ;;
    dev)
      bundle_id="io.github.jlevy.metabrowser.dev"
      icon_source="Resources/AppIcon-Dev.icns"
      scheme_suffix="-dev"
      ;;
    *) die "VARIANT must be release or dev, not '$variant'" ;;
  esac
  artifact_label="$(artifact_label_of_variant "$variant")"
  version="$(read_version)" || exit 1
  arch_label="$(arch_label_for "${ARCHES:-arm64}")"
  app="build/$variant/$product.app"
  dmg="$(dmg_path "$variant" "$version" "$arch_label")"
}

# The start of a variant's image and artifact names: Metabrowser, or Metabrowser-Dev.
artifact_label_of_variant() {
  case "$1" in
    release) echo Metabrowser ;;
    dev) echo Metabrowser-Dev ;;
    *) die "VARIANT must be release or dev, not '$1'" ;;
  esac
}

# Prints the variant whose bundle identifier is $1, or nothing.
variant_of_bundle_id() {
  local candidate
  for candidate in release dev; do
    (variant_settings "$candidate" && [[ "$bundle_id" == "$1" ]]) && echo "$candidate"
  done
  return 0
}

# Prints the icon a variant ships.
icon_of_variant() {
  (variant_settings "$1" && echo "$icon_source")
}

# Gives each URL scheme in CFBundleURLTypes a suffix and each type the bundle's
# identifier as its name. The property list declares no scheme yet; when one arrives,
# the dev variant claims metabrowser-dev, say, and never the release scheme.
suffix_url_schemes() {
  local plist="$1" suffix="$2" id="$3" type=0 index scheme
  while /usr/libexec/PlistBuddy -c "Print :CFBundleURLTypes:$type" "$plist" >/dev/null 2>&1; do
    index=0
    while scheme="$(/usr/libexec/PlistBuddy -c "Print :CFBundleURLTypes:$type:CFBundleURLSchemes:$index" "$plist" 2>/dev/null)"; do
      /usr/libexec/PlistBuddy -c "Set :CFBundleURLTypes:$type:CFBundleURLSchemes:$index $scheme$suffix" "$plist"
      index=$((index + 1))
    done
    plutil -replace "CFBundleURLTypes.$type.CFBundleURLName" -string "$id" "$plist"
    type=$((type + 1))
  done
}

# The one place the version is set: the VERSION file. A release tag is macos-v<VERSION>.
read_version() {
  local value
  value="$(tr -d '[:space:]' <VERSION)"
  [[ "$value" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "VERSION must be MAJOR.MINOR.PATCH, not '$value'"
  echo "$value"
}

# CFBundleVersion: the commit count of HEAD, which only grows along one branch. A shallow
# clone would count only the commits it fetched, so it is refused unless BUILD is set.
build_number() {
  if [[ -n "${BUILD:-}" ]]; then
    [[ "$BUILD" =~ ^[0-9]+$ ]] || die "BUILD must be a positive integer, not '$BUILD'"
    echo "$BUILD"
    return
  fi
  [[ "$(git rev-parse --is-shallow-repository 2>/dev/null)" != true ]] ||
    die "this clone is shallow, so its commit count is not the build number; fetch the full history or set BUILD"
  git rev-list --count HEAD 2>/dev/null || die "no Git history to count; set BUILD"
}

# "arm64", or "universal" when several architectures are merged.
arch_label_for() {
  case "$1" in
    *" "*) echo universal ;;
    *) echo "$1" ;;
  esac
}

# A variant's image: dmg_path VARIANT VERSION ARCH_LABEL.
dmg_path() {
  echo "build/$(artifact_label_of_variant "$1")-$2-$3.dmg"
}

# The commit the build comes from, for the About box: HEAD's short hash, with -dirty when
# apps/macos has uncommitted changes. Prints nothing outside a Git checkout.
source_commit() {
  local commit changes
  commit="$(git rev-parse --short=7 HEAD 2>/dev/null)" || return 0
  changes="$(git status --porcelain -- . 2>&1)" || die "git status failed: $changes"
  if [[ -n "$changes" ]]; then
    echo "$commit-dirty"
  else
    echo "$commit"
  fi
}

# Signs a bundle or disk image: ad hoc ("-") without a timestamp, or with the given
# identity, the hardened runtime, and a secure timestamp. Extra arguments go to codesign.
sign() {
  local identity="$1" target="$2"
  shift 2
  if [[ "$identity" == "-" ]]; then
    codesign --force --sign - --timestamp=none "$@" "$target"
  else
    codesign --force --sign "$identity" --timestamp "$@" "$target"
  fi
}

# Stops unless codesign reads the target's signature and finds no entitlements in it.
# A failed read is an error, never a clean result: tested inside an `if`, a failing
# `codesign | grep` pipeline is indistinguishable from one that found nothing.
require_no_entitlements() {
  local target="$1" output
  if ! output="$(codesign -d --entitlements - --xml "$target" 2>&1)"; then
    die "could not read the entitlements of $target: $output"
  fi
  if [[ "$output" == *"<key>"* ]]; then
    die "$target has entitlements; add one only for a verified need, and document it in scripts/build-app.sh"
  fi
}

# The oldest macOS the app runs on: LSMinimumSystemVersion in Resources/Info.plist, the
# release Package.swift deploys to (scripts/test-scripts.sh checks that they agree).
app_minimum_macos() {
  /usr/libexec/PlistBuddy -c "Print :LSMinimumSystemVersion" Resources/Info.plist 2>/dev/null ||
    die "Resources/Info.plist sets no LSMinimumSystemVersion"
}

# Homebrew's name for the macOS release $1, the form a cask's `depends_on macos:` takes
# for its minimum (MacOSVersion::RELEASES in Homebrew). Homebrew names major releases
# only. Add a release here when the app's minimum moves to it.
homebrew_macos_name() {
  case "$1" in
    26 | 26.0) echo tahoe ;;
    *) return 1 ;;
  esac
}

# Writes the Homebrew cask for the release image $1 to $2 from packaging/: the version $3,
# the image's checksum, and its architecture label $4 (arm64, x86_64, or universal), so
# the cask downloads the image it was checksummed from. A universal image declares no
# architecture. Then checks that the cask's URL names that image and carries its checksum,
# and that it requires the macOS the app does, so Homebrew installs it only where it runs.
write_cask() {
  local dmg="$1" cask="$2" version="$3" label="$4" sha256 url minimum release
  sha256="$(cut -d' ' -f1 "$dmg.sha256")"
  local -a arch_rule
  case "$label" in
    arm64 | x86_64) arch_rule=(-e "s/{{ARCH_SYMBOL}}/:$label/") ;;
    universal) arch_rule=(-e '/{{ARCH_SYMBOL}}/d') ;;
    *) die "no cask for the architecture label '$label'; it must be arm64, x86_64, or universal" ;;
  esac
  # The template's leading comment is about the template, so the cask drops it.
  sed -e '1,/^cask /{/^#/d;}' "${arch_rule[@]}" -e "s/{{VERSION}}/$version/" -e "s/{{SHA256}}/$sha256/" \
    -e "s/{{ARCH}}/$label/" packaging/metabrowser-app.rb.template >"$cask"
  url="$(sed -n 's/^ *url "\(.*\)"$/\1/p' "$cask")"
  url="${url//\#\{version\}/$version}"
  [[ "${url##*/}" == "$(basename "$dmg")" ]] || die "$cask downloads ${url##*/}, not $(basename "$dmg")"
  grep -qx "  sha256 \"$sha256\"" "$cask" || die "$cask does not carry the checksum of $(basename "$dmg")"
  minimum="$(app_minimum_macos)" || exit 1
  release="$(homebrew_macos_name "$minimum")" ||
    die "homebrew_macos_name knows no name for macOS $minimum, the app's minimum; add Homebrew's"
  grep -qx "  depends_on macos: :$release" "$cask" ||
    die "$cask does not require macOS $minimum (:$release), the app's minimum; correct packaging/metabrowser-app.rb.template"
  ! grep -q '{{' "$cask" || die "$cask has an unfilled placeholder"
}

# Whether the target carries a Developer ID Application signature, the only kind the
# notary service accepts.
is_developer_id_signed() {
  codesign -dvv "$1" 2>&1 | grep -q '^Authority=Developer ID Application:'
}

# Writes NAME.sha256 beside the file, naming the file without its directory, so
# `shasum -a 256 -c NAME.sha256` works wherever both are downloaded.
write_checksum() {
  (cd "$(dirname "$1")" && shasum -a 256 "$(basename "$1")" >"$(basename "$1").sha256")
}

# Detaches a mounted image, retrying while Spotlight or Finder still holds it.
detach_image() {
  local tries=0
  until hdiutil detach -quiet "$1"; do
    tries=$((tries + 1))
    if ((tries >= 5)); then
      hdiutil detach -quiet -force "$1"
      return
    fi
    sleep 1
  done
}
