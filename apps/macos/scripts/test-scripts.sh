#!/usr/bin/env bash
# Tests the release scripts' shared checks in scripts/common.sh against real codesign
# results and generated casks, without building the app. `make test` runs it after the
# Swift tests.
#
#   scripts/test-scripts.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh

work="$(mktemp -d -t metabrowser-script-tests)"
trap 'rm -rf "$work"' EXIT
failures=0

pass() {
  echo "ok: $*"
}

fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}

# Runs "$@" in a subshell, since die exits, and reports whether it stopped.
stops() {
  ("$@") >"$work/out" 2>&1
}

# ── require_no_entitlements ────────────────────────────────────
# A failed read, a clean signature, and a signature with entitlements, on copies of a
# system binary.
cp /usr/bin/true "$work/unsigned"
codesign --remove-signature "$work/unsigned"
cp /usr/bin/true "$work/clean"
codesign --force --sign - "$work/clean" 2>/dev/null
cp /usr/bin/true "$work/entitled"
cat >"$work/entitlements.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>com.apple.security.cs.allow-jit</key><true/></dict></plist>
EOF
codesign --force --sign - --entitlements "$work/entitlements.plist" "$work/entitled" 2>/dev/null

if stops require_no_entitlements "$work/unsigned"; then
  fail "an unreadable signature passed the entitlement check"
elif grep -q "could not read the entitlements" "$work/out"; then
  pass "an unreadable signature stops the entitlement check"
else
  fail "an unreadable signature stopped the check for another reason: $(cat "$work/out")"
fi
if stops require_no_entitlements "$work/missing"; then
  fail "a missing file passed the entitlement check"
else
  pass "a missing file stops the entitlement check"
fi
if stops require_no_entitlements "$work/clean"; then
  pass "a signature without entitlements passes"
else
  fail "a signature without entitlements was refused: $(cat "$work/out")"
fi
if stops require_no_entitlements "$work/entitled"; then
  fail "a signature with entitlements passed"
elif grep -q "has entitlements" "$work/out"; then
  pass "a signature with entitlements stops the check"
else
  fail "a signature with entitlements stopped the check for another reason: $(cat "$work/out")"
fi

# ── The app's minimum macOS ────────────────────────────────────
# Package.swift's deployment target and Info.plist's LSMinimumSystemVersion name one
# release, the one every cask below must require.
minimum="$(app_minimum_macos)"
deployment="$(sed -n 's/.*platforms: \[\.macOS(\.v\([0-9_]*\))\].*/\1/p' Package.swift)"
deployment="${deployment//_/.}"
if [[ -n "$deployment" && "$deployment" == "${minimum%.0}" ]]; then
  pass "Package.swift and Info.plist both require macOS $minimum"
else
  fail "Package.swift deploys to macOS '$deployment', but Info.plist requires $minimum"
fi
if macos_name="$(homebrew_macos_name "$minimum")"; then
  pass "Homebrew names macOS $minimum :$macos_name"
else
  fail "homebrew_macos_name knows no name for macOS $minimum"
  macos_name=""
fi

# ── write_cask ─────────────────────────────────────────────────
# Each architecture label a build can produce: the cask must download the image whose
# checksum it carries, declare the architecture the image runs on, and require the macOS
# the app requires, so Homebrew refuses to install it where it cannot launch.
check_cask() {
  local label="$1" dmg cask url
  dmg="$work/$(basename "$(dmg_path Metabrowser 1.2.3 "$label")")"
  cask="$work/cask-$label.rb"
  printf 'image %s\n' "$label" >"$dmg"
  write_checksum "$dmg"
  if ! stops write_cask "$dmg" "$cask" 1.2.3 "$label"; then
    fail "write_cask refused a $label image: $(cat "$work/out")"
    return
  fi
  url="$(sed -n 's/^ *url "\(.*\)"$/\1/p' "$cask")"
  [[ "$url" == "https://github.com/jlevy/metabrowser/releases/download/macos-v#{version}/Metabrowser-#{version}-$label.dmg" ]] ||
    fail "the $label cask downloads $url"
  grep -qx "  sha256 \"$(cut -d' ' -f1 "$dmg.sha256")\"" "$cask" || fail "the $label cask has another checksum"
  grep -qx '  version "1.2.3"' "$cask" || fail "the $label cask has another version"
  case "$label" in
    universal)
      ! grep -q 'depends_on arch' "$cask" || fail "the universal cask declares an architecture"
      ;;
    *) grep -qx "  depends_on arch: :$label" "$cask" || fail "the $label cask does not declare :$label" ;;
  esac
  grep -qx "  depends_on macos: :$macos_name" "$cask" ||
    fail "the $label cask requires $(sed -n 's/^ *depends_on macos: //p' "$cask"), not macOS $minimum (:$macos_name)"
  ! grep -q '^#' "$cask" || fail "the $label cask kept the template's comment"
  pass "the $label cask downloads Metabrowser-1.2.3-$label.dmg with its checksum and requires macOS $minimum"
}
for label in arm64 x86_64 universal; do
  check_cask "$label"
done
if stops write_cask "$work/Metabrowser-1.2.3-arm64.dmg" "$work/cask-mismatch.rb" 1.2.3 universal; then
  fail "write_cask wrote a universal cask for an arm64 image"
else
  pass "a cask whose URL would name another image stops the release"
fi
if stops write_cask "$work/Metabrowser-1.2.3-arm64.dmg" "$work/cask-bad.rb" 1.2.3 ppc; then
  fail "write_cask accepted the architecture label ppc"
else
  pass "an unknown architecture label stops the release"
fi
# A template left behind when the app's minimum moved, as macOS 15 was: write_cask, run
# from a copy of the folder with that template, refuses it.
mkdir -p "$work/stale/packaging" "$work/stale/Resources"
cp Resources/Info.plist "$work/stale/Resources/"
sed 's/^  depends_on macos: .*/  depends_on macos: :sequoia/' packaging/metabrowser-app.rb.template \
  >"$work/stale/packaging/metabrowser-app.rb.template"
if ! grep -qx '  depends_on macos: :sequoia' "$work/stale/packaging/metabrowser-app.rb.template"; then
  fail "the template has no depends_on macos line to make stale"
elif (cd "$work/stale" && stops write_cask "$work/Metabrowser-1.2.3-arm64.dmg" "$work/cask-stale.rb" 1.2.3 arm64); then
  fail "write_cask wrote a cask that admits macOS 15 for an app that requires $minimum"
elif grep -q "does not require macOS $minimum" "$work/out"; then
  pass "a cask that admits a macOS older than the app's minimum stops the release"
else
  fail "a stale macOS requirement stopped write_cask for another reason: $(cat "$work/out")"
fi

if ((failures)); then
  die "$failures script check(s) failed"
fi
echo "Script checks passed"
