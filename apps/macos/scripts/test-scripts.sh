#!/usr/bin/env bash
# Tests the release scripts' shared checks in scripts/common.sh against real codesign
# results and generated casks, and the icon renderer's reject check (scripts/build-icon.sh
# --check) on a copy of its fixtures, without building the app. `make test` runs it after
# the Swift tests.
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

# ── build-icon.sh --check ──────────────────────────────────────
# On a copy of the reject fixtures with one more, sorted last, that the renderer accepts:
# every real fixture is refused for its reason, the accepted one stops the check, and
# nothing the check started outlives it. Each process it starts inherits descriptor 9,
# so any holder of that file after the check exits is a process it left running.
mkdir -p "$work/icon/scripts" "$work/icon/AppIcon/rejects"
cp scripts/build-icon.sh "$work/icon/scripts/"
cp AppIcon/render-svg.swift "$work/icon/AppIcon/"
cp AppIcon/rejects/*.svg "$work/icon/AppIcon/rejects/"
cat >"$work/icon/AppIcon/rejects/zz-renders.svg" <<'EOF'
<!-- render-svg refuses: nothing; it renders this square -->
<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="16" height="16" fill="#FF0000"/>
</svg>
EOF
if "$work/icon/scripts/build-icon.sh" --check >"$work/out" 2>&1 9>"$work/held"; then
  fail "the reject check passed a fixture the renderer accepts"
elif grep -q "^AppIcon/rejects/zz-renders.svg: render-svg accepted it" "$work/out"; then
  pass "the reject check refuses every fixture and stops at one the renderer accepts"
else
  fail "the reject check stopped for another reason: $(cat "$work/out")"
fi
left="$(lsof -t "$work/held" 2>/dev/null | tr '\n' ',' || true)"
if [[ -z "$left" ]]; then
  pass "the reject check leaves no process running"
else
  fail "the reject check left processes running: $(ps -o pid=,command= -p "${left%,}" | tr '\n' ';')"
fi


# ── Manual checks: shebangs, failures, and stopping what they launched ─────────
# Each script that runs directly, all but the sourced common.sh, must name its
# interpreter on its first line.
for script in scripts/*.sh; do
  [[ -x "$script" ]] || continue
  if [[ "$(head -c 2 "$script")" == "#!" ]]; then
    pass "$script starts with its interpreter line"
  else
    fail "$script does not start with #!, so it cannot run directly"
  fi
done

# A live process this test started, or nothing: a zombie no longer counts.
alive() {
  [[ -n "$1" ]] && ps -o stat= -p "$1" 2>/dev/null | grep -qv Z && echo "$1" || true
}

sleep 30 &
polite=$!
disown "$polite"
polite_pids() { alive "$polite"; }
if [[ "$(stop_listed polite_pids "a process that stops on SIGTERM" 4 2>"$work/out"; echo "$check_failures")" == 0 ]] \
  && [[ -z "$(polite_pids)" ]]; then
  pass "a process that stops on SIGTERM is stopped without a failure"
else
  fail "stopping a process that honors SIGTERM: $(cat "$work/out")"
fi

bash -c 'trap "" TERM; exec sleep 30' &
stubborn=$!
disown "$stubborn"  # so its SIGKILL is not reported as a job
sleep 0.2  # until the trap is set
stubborn_pids() { alive "$stubborn"; }
if [[ "$(stop_listed stubborn_pids "the stand-in app" 2 2>"$work/out"; echo "$check_failures")" == 1 ]] \
  && [[ -z "$(stubborn_pids)" ]] && grep -q "FAIL: the stand-in app did not stop within 1 s of SIGTERM" "$work/out"; then
  pass "a process that ignores SIGTERM is killed and counted as a failed check"
else
  fail "stopping a process that ignores SIGTERM: $(cat "$work/out")"
fi

# A failed check makes the script exit nonzero after its cleanup, and an earlier
# nonzero status is kept.
for case in "0 pass 0" "0 fail 1" "4 fail 4" "3 pass 3"; do
  read -r code outcome expected <<<"$case"
  cat >"$work/check.sh" <<FIXTURE
#!/usr/bin/env bash
set -euo pipefail
source "$PWD/scripts/common.sh"
cleanup() { local status=\$?; echo cleaned; exit "\$(check_status "\$status")"; }
trap cleanup EXIT
[[ "$outcome" == pass ]] || check_fail "an injected failure"
exit $code
FIXTURE
  chmod 755 "$work/check.sh"
  set +e
  "$work/check.sh" >"$work/out" 2>&1
  status=$?
  set -e
  if [[ "$status" == "$expected" ]] && grep -q cleaned "$work/out"; then
    pass "a check script exiting $code after a $outcome exits $expected, after its cleanup"
  else
    fail "a check script exiting $code after a $outcome exited $status: $(cat "$work/out")"
  fi
done

if ((failures)); then
  die "$failures script check(s) failed"
fi
echo "Script checks passed"
