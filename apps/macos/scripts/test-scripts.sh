#!/usr/bin/env bash
# Tests the release scripts' shared checks in scripts/common.sh against real codesign
# results and generated casks, and the icon renderer's reject check (scripts/build-icon.sh
# --check) on a copy of its fixtures, without building the app. `make test` runs it after
# the Swift tests. It also runs scripts/test-release-logic.sh, which Linux CI runs too,
# here with macOS's bash, BSD tools, and LibreSSL; and on a CI runner only, the keychain
# reader and the signing doctor against a throwaway keychain.
#
#   scripts/test-scripts.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh
# shellcheck source=gatekeeper-lib.sh
source scripts/gatekeeper-lib.sh

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

# signature_facts, on real ad hoc signatures of copies of a system binary, with and
# without the hardened runtime: what check-dmg.sh requires of every build's app.
cp /usr/bin/true "$work/runtime"
quietly codesign --force --sign - --options runtime "$work/runtime"
clean_facts="$(signature_facts <<<"$(codesign -dvvv "$work/clean" 2>&1)")"
runtime_facts="$(signature_facts <<<"$(codesign -dvvv "$work/runtime" 2>&1)")"
if [[ "$(fact runtime <<<"$clean_facts")$(fact runtime <<<"$runtime_facts")" == 01 &&
  "$(fact adhoc <<<"$clean_facts")$(fact adhoc <<<"$runtime_facts")" == 11 &&
  "$(fact timestamp <<<"$runtime_facts")" == none && -z "$(fact team <<<"$runtime_facts")" ]]; then
  pass "signature_facts reads an ad hoc signature, and its hardened runtime flag only when it has one"
else
  fail "signature_facts read: without the runtime: $clean_facts; with it: $runtime_facts"
fi
runtime_problems="$(developer_id_problems "$runtime_facts" app "")"
if [[ "$runtime_problems" == *"no secure timestamp"* ]]; then
  pass "an ad hoc signature is not taken for a Developer ID one"
else
  fail "developer_id_problems passed an ad hoc signature: $runtime_facts"
fi

# The app's minimum macOS:
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

# write_cask:
# Each architecture label a build can produce: the cask must download the image whose
# checksum it carries, declare the architecture the image runs on, and require the macOS
# the app requires, so Homebrew refuses to install it where it cannot launch.
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

# slices_of and require_slices, on what the real lipo prints for binaries compiled here:
# the image's name is taken from it. lipo ends a list of several with a space
# ("x86_64 arm64 "), which normalize_arches reads as it reads ARCHES.
echo 'int main(void) { return 0; }' >"$work/main.c"
if xcrun clang -arch arm64 -o "$work/thin" "$work/main.c" 2>"$work/out" &&
  xcrun clang -arch x86_64 -arch arm64 -o "$work/fat" "$work/main.c" 2>>"$work/out"; then
  if [[ "$(slices_of "$work/thin")" == "arm64" && "$(slices_of "$work/fat")" == "arm64 x86_64" &&
    "$(arch_label_for "$(lipo -archs "$work/fat")")" == universal ]]; then
    pass "slices_of reads lipo's list for an arm64 binary and a universal one, in the canonical order"
  else
    fail "slices_of read '$(slices_of "$work/thin")' and '$(slices_of "$work/fat")' from lipo's '$(lipo -archs "$work/thin")' and '$(lipo -archs "$work/fat")'"
  fi
  if stops require_slices "$work/thin" "arm64 " && stops require_slices "$work/fat" "x86_64 arm64"; then
    pass "a binary with the slices asked for passes, however the request is written"
  else
    fail "require_slices refused the slices asked for: $(cat "$work/out")"
  fi
  if stops require_slices "$work/thin" "arm64 x86_64"; then
    fail "an arm64 binary passed as the universal one asked for"
  elif grep -q "has the slices 'arm64', but 'arm64 x86_64' was asked for" "$work/out"; then
    pass "an arm64 binary where a universal one was asked for stops the build"
  else
    fail "an arm64 binary stopped require_slices for another reason: $(cat "$work/out")"
  fi
else
  fail "clang could not compile the slice fixtures: $(cat "$work/out")"
fi
# A system binary's arm64e slice is one no release of the app has.
if stops slices_of /usr/bin/true; then
  fail "slices_of accepted /usr/bin/true's slices: $(cat "$work/out")"
elif grep -q "which is not a supported architecture" "$work/out"; then
  pass "a slice outside the supported architectures stops, by name"
else
  fail "/usr/bin/true stopped slices_of for another reason: $(cat "$work/out")"
fi

# build-icon.sh --check:
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

# source_commit: HEAD's full ID, marked -dirty when apps/macos has changes. A Git
# hook exports GIT_DIR and friends, which would point these commands at this checkout.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
repo="$work/repo"
mkdir -p "$repo/apps/macos"
git -C "$repo" init -q
git -C "$repo" -c user.name=test -c user.email=test@example.invalid commit -q --allow-empty -m one
head="$(git -C "$repo" rev-parse HEAD)"
clean="$(cd "$repo/apps/macos" && source_commit)"
touch "$repo/apps/macos/changed"
dirty="$(cd "$repo/apps/macos" && source_commit)"
outside="$(cd "$work" && GIT_CEILING_DIRECTORIES="$work" source_commit)"
if [[ "$clean" == "$head" && "$dirty" == "$head-dirty" && -z "$outside" ]]; then
  pass "source_commit names HEAD, marks uncommitted changes, and is empty outside Git"
else
  fail "source_commit gave '$clean', '$dirty', and '$outside' (HEAD is $head)"
fi

# Manual checks: shebangs, failures, and stopping what they launched.
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

# The stand-in says it is ready only once its trap is set, after a deliberate delay, and
# the test waits for that, up to 10 s, rather than guessing how long it takes.
rm -f "$work/stubborn-ready"
bash -c 'sleep 0.5; trap "" TERM; : >"$1"; exec sleep 30' _ "$work/stubborn-ready" &
stubborn=$!
disown "$stubborn"  # so its SIGKILL is not reported as a job
for _ in $(seq 100); do
  [[ -e "$work/stubborn-ready" ]] && break
  sleep 0.1
done
stubborn_pids() { alive "$stubborn"; }
if [[ ! -e "$work/stubborn-ready" ]]; then
  fail "the stand-in that ignores SIGTERM did not get ready within 10 s"
elif [[ "$(stop_listed stubborn_pids "the stand-in app" 2 2>"$work/out"; echo "$check_failures")" == 1 ]] \
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


# ── refuse_ambient ─────────────────────────────────────────────
# The setup check's preflight reads one directory per line, so a directory with a space
# or a glob character in its name is looked in whole (mb-j2qo).
mkdir -p "$work/ambient/Shared Tools/bin" "$work/ambient/g[l]ob*/bin" "$work/ambient/plain/bin"
: >"$work/ambient/Shared Tools/bin/uv"
: >"$work/ambient/g[l]ob*/bin/metab"
spaced="$work/ambient/plain/bin
$work/ambient/Shared Tools/bin"
globbed="$work/ambient/plain/bin
$work/ambient/g[l]ob*/bin"
if ! stops refuse_ambient no-metab "$spaced" && grep -q "$work/ambient/Shared Tools/bin/uv would be found" "$work/out"; then
  pass "a uv in a directory with a space in its name stops no-metab"
else
  fail "a uv in a directory with a space in its name: $(cat "$work/out")"
fi
if (refuse_ambient old-metab "$spaced") >"$work/out" 2>&1; then
  pass "a uv elsewhere does not stop old-metab"
else
  fail "old-metab stopped for an ambient uv: $(cat "$work/out")"
fi
if ! stops refuse_ambient old-metab "$globbed" && grep -qF "$work/ambient/g[l]ob*/bin/metab would be found" "$work/out"; then
  pass "a metab in a directory with glob characters in its name stops every case"
else
  fail "a metab in a directory with glob characters in its name: $(cat "$work/out")"
fi

# ── The quarantine helper ──────────────────────────────────────
# The first call sets a quarantine attribute. A second call leaves its bytes intact.
quietly swiftc -O scripts/quarantine.swift -o "$work/quarantine"
printf x >"$work/download"
if first="$("$work/quarantine" "$work/download" 2>&1)" &&
  [[ "$first" == simulated ]] &&
  initial_attribute="$(xattr -px com.apple.quarantine "$work/download")" &&
  [[ -n "$initial_attribute" ]] &&
  second="$("$work/quarantine" "$work/download" 2>&1)" &&
  [[ "$second" == already ]] &&
  final_attribute="$(xattr -px com.apple.quarantine "$work/download")" &&
  [[ "$final_attribute" == "$initial_attribute" ]]; then
  pass "the quarantine helper sets the attribute once and leaves it unchanged"
else
  fail "expected 'simulated' then 'already' with unchanged quarantine; got '${first:-no output}', then '${second:-no output}'"
fi

# ── The release scripts' decisions ─────────────────────────────
# The same checks Linux CI runs, on this Mac's tools.
if scripts/test-release-logic.sh; then
  pass "the release-logic checks pass with macOS's tools"
else
  fail "the release-logic checks failed with macOS's tools (above)"
fi

# ── The keychain reader and the signing doctor, on a real keychain ──
# Only on a CI runner, which is discarded after the job: this creates a keychain, puts
# it on the search list, changes its settings, and deletes it, restoring the list. A
# keychain prompt would hang rather than fail, so each run is bounded (common.sh), and a
# stop is a failure. Each check prints what macOS reported, so a run records it.
ci_bound=120
# Whether the user search list holds the keychain "$1", as security prints the list.
listed() {
  local list
  list="$(security list-keychains -d user | parse_keychain_list)"
  [[ $'\n'"$list"$'\n' == *$'\n'"$1"$'\n'* ]]
}
# Runs the signing doctor on the keychain into "$1", and sets doctor_status.
doctor_on() {
  set +e
  SIGN_KEYCHAIN="$keychain" bounded "$ci_bound" scripts/check-signing.sh >"$1" 2>&1
  doctor_status=$?
  set -e
}
if [[ "${CI:-}" == true && -n "${RUNNER_TEMP:-}" ]]; then
  # shellcheck source=signing-lib.sh
  source scripts/signing-lib.sh
  keychain="$RUNNER_TEMP/signing-doctor-test.keychain-db"
  # A throwaway password for a throwaway keychain, deleted below; it guards nothing.
  password="$(openssl rand -hex 16)"
  search_list="$(security list-keychains -d user | parse_keychain_list)"
  quietly swiftc -suppress-warnings -O scripts/keychain-status.swift -o "$work/keychain-status"
  quietly security create-keychain -p "$password" "$keychain"
  if listed "$keychain"; then created_listed=1; else created_listed=0; fi
  echo "note: after security create-keychain, the user search list is: $(security list-keychains -d user | parse_keychain_list | tr '\n' ' ')"
  quietly security set-keychain-settings -l -u -t 600 "$keychain"
  quietly security lock-keychain "$keychain"
  if locked="$(bounded "$ci_bound" "$work/keychain-status" "$keychain" metabrowser-notary 2>&1)" &&
    grep -qx exists=1 <<<"$locked" && grep -qx unlocked=0 <<<"$locked"; then
    pass "the keychain reader sees a locked keychain as locked, without a prompt: $(grep -E '^(settings|profile|lock_|use_)' <<<"$locked" | tr '\n' ' ')"
  else
    fail "the keychain reader on a locked keychain: $locked"
  fi
  # The doctor's search-list check against the list itself, before anything adds it.
  doctor_on "$work/doctor-locked"
  if ((created_listed)); then expected_line="ok: it is on the user search list"; else expected_line="FAIL: it is not on the user search list"; fi
  if ((doctor_status == 1)) && grep -q "holds no Developer ID Application identity" "$work/doctor-locked" &&
    grep -qF "$expected_line" "$work/doctor-locked"; then
    pass "the signing doctor reads a locked keychain without a prompt, finds no identity, and agrees with security that create-keychain left it $( ((created_listed)) && echo on || echo off) the search list"
  else
    fail "the signing doctor on a locked keychain exited $doctor_status (create-keychain left it listed: $created_listed): $(cat "$work/doctor-locked")"
  fi
  if ((created_listed == 0)); then
    # The command the doctor prints for it, which keeps the keychains listed now.
    remedy="$(sed -n 's/^FAIL: it is not on the user search list (O1: \(.*\))$/\1/p' "$work/doctor-locked")"
    if [[ "$remedy" == "security list-keychains -d user -s "*"\"$keychain\"" ]] && eval "$remedy" && listed "$keychain" &&
      [[ -z "$(comm -23 <(sort <<<"$search_list") <(security list-keychains -d user | parse_keychain_list | sort))" ]]; then
      pass "the doctor's command adds the keychain to the search list and keeps the keychains on it: $remedy"
    else
      fail "the doctor's search-list command, '$remedy', left: $(security list-keychains -d user | parse_keychain_list | tr '\n' ' ')"
    fi
  fi
  quietly security unlock-keychain -p "$password" "$keychain"
  unlocked="$(bounded "$ci_bound" "$work/keychain-status" "$keychain" metabrowser-notary 2>&1)" || true
  if grep -qx unlocked=1 <<<"$unlocked" && grep -qx lock_on_sleep=1 <<<"$unlocked" &&
    grep -qx lock_interval=600 <<<"$unlocked" && grep -qx profile=absent <<<"$unlocked"; then
    pass "the keychain reader reads an unlocked keychain's lock settings and finds no profile: $(grep -E '^(lock_|use_)' <<<"$unlocked" | tr '\n' ' ')"
  else
    fail "the keychain reader on an unlocked keychain: $unlocked"
  fi
  doctor_on "$work/doctor-unlocked"
  if ((doctor_status == 1)) && grep -q "^ok: it is on the user search list" "$work/doctor-unlocked" &&
    grep -q "^ok: it locks on sleep and after 600 s idle" "$work/doctor-unlocked" &&
    grep -q "^warn: the release keychain holds no item named as notarytool 1.1 names the profile metabrowser-notary" "$work/doctor-unlocked" &&
    ! grep -q "notary profile" <(grep '^FAIL' "$work/doctor-unlocked"); then
    pass "the signing doctor passes -l -u -t 600, and warns, not fails, that it found no profile item"
  else
    fail "the signing doctor on an unlocked keychain exited $doctor_status: $(cat "$work/doctor-unlocked")"
  fi
  # A keychain that locks on sleep but never when idle, which the doctor must refuse.
  quietly security set-keychain-settings -l "$keychain"
  sleep_only="$(bounded "$ci_bound" "$work/keychain-status" "$keychain" 2>&1)" || true
  doctor_on "$work/doctor-sleep-only"
  if grep -q "^FAIL: it must lock on sleep and after at most $release_keychain_lock_seconds s idle" "$work/doctor-sleep-only"; then
    pass "the signing doctor refuses a keychain set with -l alone, which reads: $(grep -E '^(lock_|use_)' <<<"$sleep_only" | tr '\n' ' ')"
  else
    fail "the signing doctor on a keychain set with -l alone ($(grep -E '^(lock_|use_)' <<<"$sleep_only" | tr '\n' ' ')): $(cat "$work/doctor-sleep-only")"
  fi
  quietly security delete-keychain "$keychain"
  # delete-keychain takes it off the list; put back exactly what was there.
  restore_list=()
  while IFS= read -r entry; do
    [[ -n "$entry" ]] && restore_list+=("$entry")
  done <<<"$search_list"
  quietly security list-keychains -d user -s ${restore_list[@]+"${restore_list[@]}"}
else
  echo "note: the keychain reader's live checks run only on a CI runner (CI=true, RUNNER_TEMP set)"
fi

if ((failures)); then
  die "$failures script check(s) failed"
fi
echo "Script checks passed"
