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

# quietly: silent when the command succeeds, and its output when it fails.
if ! stops quietly sh -c 'echo chatter'; then
  fail "quietly stopped on a command that succeeded: $(cat "$work/out")"
elif [[ -s "$work/out" ]]; then
  fail "quietly printed a successful command's output: $(cat "$work/out")"
else
  pass "quietly holds back a successful command's output"
fi
if stops quietly sh -c 'echo the reason; exit 3'; then
  fail "quietly passed a command that failed"
elif grep -q "sh failed: the reason" "$work/out"; then
  pass "quietly stops with a failed command's output"
else
  fail "quietly stopped without the command's output: $(cat "$work/out")"
fi

# require_no_entitlements:
# A failed read, a clean signature, and a signature with entitlements, on copies of a
# system binary.
cp /usr/bin/true "$work/unsigned"
codesign --remove-signature "$work/unsigned"
cp /usr/bin/true "$work/clean"
quietly codesign --force --sign - "$work/clean"
cp /usr/bin/true "$work/entitled"
cat >"$work/entitlements.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>com.apple.security.cs.allow-jit</key><true/></dict></plist>
EOF
quietly codesign --force --sign - --entitlements "$work/entitlements.plist" "$work/entitled"

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

# write_cask:
# Each architecture label a build can produce: the cask must download the image whose
# checksum it carries, and declare the architecture the image runs on.
check_cask() {
  local label="$1" dmg cask url
  dmg="$work/$(basename "$(dmg_path release 1.2.3 "$label")")"
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
  ! grep -q '^#' "$cask" || fail "the $label cask kept the template's comment"
  pass "the $label cask downloads Metabrowser-1.2.3-$label.dmg with its checksum"
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

# variant_settings: both variants are Metabrowser.app, each in a folder of its own, and
# their images keep the variant in their names.
dev_app="$(variant_settings dev && echo "$app|$dmg|$bundle_id")"
release_app="$(variant_settings release && echo "$app|$dmg|$bundle_id")"
version="$(read_version)"
if [[ "$dev_app" == "build/dev/Metabrowser.app|build/Metabrowser-Dev-$version-arm64.dmg|io.github.jlevy.metabrowser.dev" &&
  "$release_app" == "build/release/Metabrowser.app|build/Metabrowser-$version-arm64.dmg|io.github.jlevy.metabrowser" ]]; then
  pass "each variant builds Metabrowser.app in its own folder, and its image names the variant"
else
  fail "the variants' paths: dev $dev_app, release $release_app"
fi
if [[ "$(variant_of_bundle_id io.github.jlevy.metabrowser.dev)" == dev &&
  "$(variant_of_bundle_id io.github.jlevy.metabrowser)" == release &&
  -z "$(variant_of_bundle_id io.github.jlevy.other)" ]]; then
  pass "a bundle identifier names its variant, and an unknown one names none"
else
  fail "variant_of_bundle_id did not map the bundle identifiers"
fi

# source_commit: HEAD's short hash, marked -dirty when apps/macos has changes. A Git
# hook exports GIT_DIR and friends, which would point these commands at this checkout.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
repo="$work/repo"
mkdir -p "$repo/apps/macos"
git -C "$repo" init -q
git -C "$repo" -c user.name=test -c user.email=test@example.invalid commit -q --allow-empty -m one
head="$(git -C "$repo" rev-parse --short=7 HEAD)"
clean="$(cd "$repo/apps/macos" && source_commit)"
touch "$repo/apps/macos/changed"
dirty="$(cd "$repo/apps/macos" && source_commit)"
outside="$(cd "$work" && GIT_CEILING_DIRECTORIES="$work" source_commit)"
if [[ "$clean" == "$head" && "$dirty" == "$head-dirty" && -z "$outside" ]]; then
  pass "source_commit names HEAD, marks uncommitted changes, and is empty outside Git"
else
  fail "source_commit gave '$clean', '$dirty', and '$outside' (HEAD is $head)"
fi

if ((failures)); then
  die "$failures script check(s) failed"
fi
echo "Script checks passed"
