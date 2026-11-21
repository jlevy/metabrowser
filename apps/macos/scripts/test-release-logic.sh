#!/usr/bin/env bash
# Tests what the release scripts decide, on stand-ins for Apple's tools, so that it runs
# on Linux as well as on a Mac: `make test` runs it through
# tests/test_macos_release_scripts.py, and `make macos-test` through
# scripts/test-scripts.sh. It needs bash, jq, openssl, pgrep, and shasum, and none of
# Apple's tools. What only a Mac can show, a signed build or a real keychain, is the
# runbook's signing-session checks (README.md, Building a Release).
#
#   scripts/test-release-logic.sh
#
# Where the inputs come from:
#   - fixtures/notary/apple-example-invalid.json is the example log in Apple's
#     "Customizing the notarization workflow", copied verbatim. The other logs follow its
#     format with made-up values; submit-output.json is what `notarytool submit
#     --output-format json` prints, and unparsable.json a log cut short.
#   - fixtures/AppleIncRootCertificate.cer is Apple Root CA, from Apple PKI
#     (https://www.apple.com/appleca/AppleIncRootCertificate.cer); the committed G2
#     intermediate is checked against it with the real openssl.
#   - The security, xcrun, xcodebuild, and codesign -dvvv stand-ins print output in the
#     form those tools print it, written for these tests rather than captured from a run;
#     the certificates they return are generated here with openssl, with Apple's names
#     and made-up keys, so expiry and issuer are real. Real output meets these readers in
#     scripts/test-scripts.sh, on macOS CI (ad hoc signatures, a throwaway keychain), and
#     on the build Mac (the runbook's signing-session checks).
#   - keychain_status stands in for scripts/keychain-status.swift, whose output this
#     repository defines; scripts/test-scripts.sh runs the real one, in CI, on a
#     throwaway keychain.
#   - The gh stand-in returns releases in the shape `gh release view --json` gives them
#     (gh 2.97, read from a public release), with made-up assets.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh
# shellcheck source=signing-lib.sh
source scripts/signing-lib.sh
# shellcheck source=notary-lib.sh
source scripts/notary-lib.sh
# shellcheck source=gatekeeper-lib.sh
source scripts/gatekeeper-lib.sh
# shellcheck source=check-release-lib.sh
source scripts/check-release-lib.sh

for tool in jq openssl pgrep shasum; do
  command -v "$tool" >/dev/null || die "$tool is missing; these tests need it"
done

work="$(scratch_dir metabrowser-release-logic)"
trap 'rm -rf "$work"' EXIT
fixtures="$PWD/scripts/fixtures"
failures=0

pass() {
  echo "ok: $*"
}

fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}

# Runs "$@" in a subshell, since die exits, with its output in $work/out, and sets
# status to its exit status.
run() {
  set +e
  ("$@") >"$work/out" 2>&1
  status=$?
  set -e
}

# Whether the last run's output has a line containing "$1".
said() {
  grep -qF -- "$1" "$work/out"
}

export HOME="$work/home"
mkdir -p "$HOME/Library/Keychains"
unset SIGN_KEYCHAIN SIGN_IDENTITY APPLE_KEYCHAIN_PROFILE APPLE_API_KEY APPLE_API_KEY_ID APPLE_API_ISSUER ONLINE

# ── sign ─────────────────────────────────────────────────────
# Ad hoc signing gets no keychain and no timestamp; a Developer ID identity is looked
# for only in the release keychain, SIGN_KEYCHAIN or its default.
codesign() {
  printf '%s\n' "$@" >"$work/codesign-args"
}
sign - "$work/Some.app" --options runtime
if [[ "$(tr '\n' ' ' <"$work/codesign-args")" == "--force --sign - --timestamp=none --options runtime $work/Some.app " ]]; then
  pass "sign - signs ad hoc, with no keychain and no timestamp"
else
  fail "sign - ran codesign $(tr '\n' ' ' <"$work/codesign-args")"
fi
identity="Developer ID Application: Example Developer (A1B2C3D4E5)"
sign "$identity" "$work/Some.app" --options runtime
if [[ "$(tr '\n' '|' <"$work/codesign-args")" == "--force|--sign|$identity|--keychain|$HOME/Library/Keychains/metabrowser-release.keychain-db|--timestamp|--options|runtime|$work/Some.app|" ]]; then
  pass "a Developer ID signature uses the default release keychain and a secure timestamp"
else
  fail "a Developer ID signature ran codesign $(tr '\n' '|' <"$work/codesign-args")"
fi
SIGN_KEYCHAIN="$work/other.keychain-db" sign "$identity" "$work/Some.dmg"
if grep -qx -- "$work/other.keychain-db" "$work/codesign-args"; then
  pass "SIGN_KEYCHAIN names the keychain codesign looks in"
else
  fail "SIGN_KEYCHAIN did not reach codesign: $(tr '\n' ' ' <"$work/codesign-args")"
fi
# is_developer_id_signed reads all of codesign's output: the Authority line comes before
# many others, which a `| grep -q` pipeline would cut off, failing it under pipefail.
codesign() {
  local line
  echo "Executable=/tmp/Metabrowser.app/Contents/MacOS/Metabrowser" >&2
  echo "Authority=Developer ID Application: Example Developer (A1B2C3D4E5)" >&2
  for line in $(seq 2000); do echo "Sealed Resources line $line" >&2; done
}
if is_developer_id_signed "$work/Some.app"; then
  pass "a Developer ID signature is found whatever codesign prints after it"
else
  fail "a Developer ID signature followed by more output was not found"
fi
codesign() {
  echo "Signature=adhoc" >&2
}
if is_developer_id_signed "$work/Some.app"; then
  fail "an ad hoc signature was taken for a Developer ID one"
else
  pass "an ad hoc signature is not a Developer ID one"
fi
unset -f codesign

# ── notary_credentials ───────────────────────────────────────
joined() {
  local IFS='|'
  echo "$*"
}
if APPLE_KEYCHAIN_PROFILE=metabrowser-notary notary_credentials &&
  [[ "$(joined "${notary_auth[@]}")" == "--keychain-profile|metabrowser-notary|--keychain|$HOME/Library/Keychains/metabrowser-release.keychain-db" ]]; then
  pass "a keychain profile is read from the release keychain"
else
  fail "a keychain profile gave notarytool: $(joined "${notary_auth[@]:-}")"
fi
: >"$work/AuthKey_TEST.p8"
if APPLE_API_KEY="$work/AuthKey_TEST.p8" APPLE_API_KEY_ID=KEYID APPLE_API_ISSUER=ISSUER notary_credentials &&
  [[ "$(joined "${notary_auth[@]}")" == "--key|$work/AuthKey_TEST.p8|--key-id|KEYID|--issuer|ISSUER" ]]; then
  pass "an API key passes its path, ID, and issuer"
else
  fail "an API key gave notarytool: $(joined "${notary_auth[@]:-}")"
fi
if notary_credentials; then
  fail "no credentials were taken as credentials"
else
  pass "no credentials is a skip, not credentials"
fi
run env APPLE_API_KEY="$work/AuthKey_TEST.p8" bash -c 'source scripts/common.sh; source scripts/notary-lib.sh; notary_credentials'
if ((status != 0)) && said "APPLE_API_KEY_ID is required"; then
  pass "an API key without its ID stops"
else
  fail "an API key without its ID: $(cat "$work/out")"
fi

# ── read_notary_log ──────────────────────────────────────────
run read_notary_log "$fixtures/notary/apple-example-invalid.json"
if ((status == 1)) &&
  said "notary record: Overnight TextEditor.app, submission 2EFE2717-52EF-43A5-96DC-0797E4CA1041, Invalid, 1 error(s), 0 warning(s)" &&
  said "notary error: Overnight TextEditor.app/Contents/MacOS/Overnight TextEditor: The signature of the binary is invalid."; then
  pass "Apple's example log, Invalid with an error, fails and names the error's path"
else
  fail "Apple's example log gave status $status: $(cat "$work/out")"
fi
run read_notary_log "$fixtures/notary/accepted.json"
if ((status == 0)) && said "Accepted, 0 error(s), 0 warning(s)"; then
  pass "an accepted log with no issues passes, with its record line"
else
  fail "an accepted log gave status $status: $(cat "$work/out")"
fi
run read_notary_log "$fixtures/notary/accepted-warning.json"
if ((status == 0)) && said "Accepted, 0 error(s), 1 warning(s)" &&
  said "notary warning: Metabrowser-0.1.0-arm64.dmg/Metabrowser.app/Contents/MacOS/Metabrowser: An example warning"; then
  pass "an accepted log with a warning passes and prints the warning with its path"
else
  fail "an accepted log with a warning gave status $status: $(cat "$work/out")"
fi
: >"$work/empty.json"
for unreadable in "$work/missing.json" "$work/empty.json" "$fixtures/notary/unparsable.json" "$fixtures/notary/submit-output.json"; do
  run read_notary_log "$unreadable"
  if ((status == 2)); then
    pass "$(basename "$unreadable") is not a readable notary log"
  else
    fail "$(basename "$unreadable") gave status $status: $(cat "$work/out")"
  fi
done

# ── fetch_notary_log ─────────────────────────────────────────
# A stand-in notarytool whose log download fails until try $log_ok_on.
xcrun() {
  [[ "$1 $2" == "notarytool log" ]] || return 99
  log_tries=$((log_tries + 1))
  ((log_tries >= log_ok_on)) || return 1
  cp "$fixtures/notary/accepted.json" "${*: -1}"
}
sleep() { :; }
notary_auth=(--keychain-profile metabrowser-notary)
log_tries=0
log_ok_on=3
if fetch_notary_log ID "$work/fetched.json" 2>/dev/null && ((log_tries == 3)) && [[ -s "$work/fetched.json" ]]; then
  pass "a log download that fails twice is retried until it succeeds"
else
  fail "the log download was tried $log_tries times"
fi
log_tries=0
log_ok_on=1000
if fetch_notary_log ID "$work/never.json" 2>/dev/null; then
  fail "a log that never downloads was fetched"
elif ((log_tries == notary_log_tries)); then
  pass "a log that never downloads is tried $notary_log_tries times, then given up"
else
  fail "a log that never downloads was tried $log_tries times"
fi
unset -f xcrun sleep

# ── notarize.sh, end to end ──────────────────────────────────
# With exported stand-ins for codesign, syspolicy_check, ditto, xcrun, spctl, and
# sleep, which a child bash runs before anything on PATH. Each records its call.
stub_calls="$work/calls"
export stub_calls fixtures
codesign() {
  echo "codesign $*" >>"$stub_calls"
  echo "Authority=Developer ID Application: Example Developer (A1B2C3D4E5)" >&2
}
syspolicy_check() {
  echo "syspolicy_check $*" >>"$stub_calls"
  [[ "${stub_presubmission:-pass}" == pass ]] || {
    echo "App has failed one or more pre-notarization checks." >&2
    return 1
  }
}
ditto() {
  echo "ditto $*" >>"$stub_calls"
  : >"${*: -1}"
}
xcrun() {
  echo "xcrun $*" >>"$stub_calls"
  case "$1 $2" in
    "notarytool submit")
      echo "{\"id\":\"0B4C3B1E-7A2D-4F55-9E1C-2D6A8F0E5C11\",\"message\":\"Processing complete\",\"status\":\"${stub_status:-Accepted}\"}"
      ;;
    "notarytool log")
      [[ "$stub_log" != none ]] || return 1
      cp "$fixtures/notary/$stub_log" "${*: -1}"
      ;;
    "stapler staple" | "stapler validate") echo "The staple and validate action worked!" ;;
    *) return 99 ;;
  esac
}
spctl() {
  echo "spctl $*" >>"$stub_calls"
}
sleep() { :; }
export -f codesign syspolicy_check ditto xcrun spctl sleep
mkdir -p "$work/release/Metabrowser.app/Contents"
notarize() {
  : >"$stub_calls"
  run env SIGN_KEYCHAIN="$work/release.keychain-db" APPLE_KEYCHAIN_PROFILE=metabrowser-notary "$@" \
    scripts/notarize.sh "$work/release/Metabrowser.app"
}

notarize stub_presubmission=fail stub_log=accepted.json NOTARIZE=1
if ((status != 0)) && said "fails the notary service's checks; nothing was submitted" &&
  ! grep -q "notarytool submit" "$stub_calls"; then
  pass "a failed pre-submission check stops before anything is submitted"
else
  fail "a failed pre-submission check: status $status: $(cat "$work/out")"
fi
notarize stub_log=accepted-warning.json NOTARIZE=1
if ((status == 0)) && said "notary record:" && said "notary warning:" &&
  grep -q "notarytool submit .* --keychain-profile metabrowser-notary --keychain $work/release.keychain-db" "$stub_calls" &&
  grep -q "stapler staple" "$stub_calls" && [[ -s "$work/release/notary-Metabrowser.app.json" ]]; then
  pass "an accepted submission with a warning is stapled, with its record and warning printed and its log kept"
else
  fail "an accepted submission with a warning: status $status: $(cat "$work/out")"
fi
notarize stub_log=apple-example-invalid.json NOTARIZE=1
if ((status != 0)) && said "lists errors" && ! grep -q "stapler staple" "$stub_calls"; then
  pass "a log that lists an error stops before stapling"
else
  fail "a log that lists an error: status $status: $(cat "$work/out")"
fi
notarize stub_log=unparsable.json NOTARIZE=1
if ((status != 0)) && said "NOTARIZE=1 needs it" && ! grep -q "stapler staple" "$stub_calls"; then
  pass "under NOTARIZE=1, an unparsable log is fatal"
else
  fail "under NOTARIZE=1, an unparsable log: status $status: $(cat "$work/out")"
fi
notarize stub_log=none NOTARIZE=1
if ((status != 0)) && said "NOTARIZE=1 needs it" &&
  [[ "$(grep -c "notarytool log" "$stub_calls")" == "$notary_log_tries" ]]; then
  pass "under NOTARIZE=1, a log that cannot be fetched is fatal, after $notary_log_tries tries"
else
  fail "under NOTARIZE=1, a missing log: status $status: $(cat "$work/out")"
fi
notarize stub_log=none NOTARIZE=auto
if ((status == 0)) && said "its warnings are unknown" && grep -q "stapler staple" "$stub_calls"; then
  pass "under NOTARIZE=auto, a log that cannot be fetched is a note, and an accepted file is stapled"
else
  fail "under NOTARIZE=auto, a missing log: status $status: $(cat "$work/out")"
fi
notarize stub_status="In Progress" stub_log=accepted.json NOTARIZE=1
if ((status != 0)) && said "has no verdict yet (status In Progress), submission 0B4C3B1E-7A2D-4F55-9E1C-2D6A8F0E5C11" &&
  said "notarytool wait 0B4C3B1E-7A2D-4F55-9E1C-2D6A8F0E5C11" && ! grep -q "notarytool log" "$stub_calls"; then
  pass "a submission with no verdict stops with its status and ID, without waiting on a log"
else
  fail "a submission with no verdict: status $status: $(cat "$work/out")"
fi

# The image: notarize.sh mounts it, checks the one app inside, and detaches it, also when
# it stops. An hdiutil stand-in mounts a folder holding stub_apps apps.
hdiutil() {
  echo "hdiutil $*" >>"$stub_calls"
  case "$1" in
    attach)
      local i
      mkdir -p "${*: -2:1}"
      for ((i = 1; i <= ${stub_apps:-1}; i++)); do mkdir -p "${*: -2:1}/App$i.app"; done
      ;;
    detach) rm -rf "${*: -1}" ;;
    *) return 99 ;;
  esac
}
export -f hdiutil
printf 'image\n' >"$work/release/Metabrowser-0.0.0-arm64.dmg"
notarize_image() {
  : >"$stub_calls"
  run env SIGN_KEYCHAIN="$work/release.keychain-db" APPLE_KEYCHAIN_PROFILE=metabrowser-notary "$@" \
    scripts/notarize.sh "$work/release/Metabrowser-0.0.0-arm64.dmg"
}
notarize_image stub_log=accepted.json NOTARIZE=1
if ((status == 0)) && grep -q "syspolicy_check notary-submission .*/App1.app" "$stub_calls" &&
  grep -q "hdiutil detach" "$stub_calls" && grep -q "notarytool submit $work/release/Metabrowser-0.0.0-arm64.dmg" "$stub_calls"; then
  pass "an image's one app is checked before the image is submitted, and the image is detached"
else
  fail "an image with one app: status $status: $(cat "$work/out"); calls: $(cat "$stub_calls")"
fi
notarize_image stub_apps=0 stub_log=accepted.json NOTARIZE=1
if ((status != 0)) && said "must hold exactly one app" && grep -q "hdiutil detach" "$stub_calls" &&
  ! grep -q "notarytool submit" "$stub_calls"; then
  pass "an image without an app stops, detached, before anything is submitted"
else
  fail "an image without an app: status $status: $(cat "$work/out"); calls: $(cat "$stub_calls")"
fi
notarize_image stub_presubmission=fail stub_log=accepted.json NOTARIZE=1
if ((status != 0)) && said "the app in Metabrowser-0.0.0-arm64.dmg fails the notary service's checks" &&
  grep -q "hdiutil detach" "$stub_calls" && ! grep -q "notarytool submit" "$stub_calls"; then
  pass "an image whose app fails the pre-submission check stops, detached, before anything is submitted"
else
  fail "an image whose app fails the check: status $status: $(cat "$work/out"); calls: $(cat "$stub_calls")"
fi
unset -f hdiutil
unset -f codesign syspolicy_check ditto xcrun spctl sleep

# ── The signing doctor ───────────────────────────────────────
# Certificates with Apple's names, made here: a G2 and a G1 Developer ID intermediate,
# an unrelated root, and Developer ID Application certificates that expire in 400, 60,
# and 20 days, issued by the G2 one, and one issued by the G1 one.
certs="$work/certs"
mkdir -p "$certs"
make_ca() {
  openssl req -x509 -new -newkey rsa:2048 -nodes -days 3650 -subj "$2" \
    -keyout "$certs/$1.key" -out "$certs/$1.pem" >/dev/null 2>&1
}
make_leaf() {
  openssl req -new -newkey rsa:2048 -nodes -subj "$4" -keyout "$certs/$1.key" -out "$certs/$1.csr" >/dev/null 2>&1
  openssl x509 -req -in "$certs/$1.csr" -CA "$certs/$2.pem" -CAkey "$certs/$2.key" -set_serial "$RANDOM" \
    -days "$3" -out "$certs/$1.pem" >/dev/null 2>&1
}
leaf_subject="/UID=A1B2C3D4E5/CN=Developer ID Application: Example Developer (A1B2C3D4E5)/OU=A1B2C3D4E5/O=Example Developer/C=US"
make_ca fake-g2 "/CN=Developer ID Certification Authority/OU=G2/O=Apple Inc./C=US"
make_ca fake-g1 "/CN=Developer ID Certification Authority/OU=Apple Certification Authority/O=Apple Inc./C=US"
make_ca other-root "/CN=Apple Root CA/OU=Apple Certification Authority/O=Not Apple/C=US"
make_leaf leaf400 fake-g2 400 "$leaf_subject"
make_leaf leaf60 fake-g2 60 "$leaf_subject"
make_leaf leaf20 fake-g2 20 "$leaf_subject"
make_leaf leafg1 fake-g1 400 "$leaf_subject"
make_leaf second fake-g2 300 "/CN=Developer ID Application: Example Developer (A1B2C3D4E5)/OU=A1B2C3D4E5/C=US"
openssl x509 -inform DER -in "$g2_intermediate" -out "$certs/apple-g2.pem"
openssl x509 -inform DER -in "$fixtures/AppleIncRootCertificate.cer" -out "$certs/apple-root.pem"
hash_of() {
  cert_fingerprint "$certs/$1.pem" sha1 | tr '[:lower:]' '[:upper:]'
}
identity_name="Developer ID Application: Example Developer (A1B2C3D4E5)"

# Apple Root CA's SHA-256, as Apple PKI serves the file, reviewed in
# SUPPLY-CHAIN-SECURITY.md: the fixture must be that file, so the chain check below starts
# from a pinned root rather than from whatever the fixture holds.
apple_root_ca_sha256=b0b1730ecbc7ff4505142c49f1295e6eda6bcaed7e2c68c5be91b5a11001f024
if [[ "$(shasum -a 256 "$fixtures/AppleIncRootCertificate.cer" | cut -d' ' -f1)" == "$apple_root_ca_sha256" ]]; then
  pass "the Apple Root CA fixture is the reviewed file"
else
  fail "fixtures/AppleIncRootCertificate.cer is not the reviewed Apple Root CA"
fi
if [[ "$(shasum -a 256 "$g2_intermediate" | cut -d' ' -f1)" == "$g2_intermediate_sha256" &&
  "$(developer_id_generation "$(cert_subject "$certs/apple-g2.pem")")" == G2 ]] &&
  openssl verify -CAfile "$certs/apple-root.pem" "$certs/apple-g2.pem" >/dev/null 2>&1; then
  pass "$g2_intermediate is the reviewed file, the G2 intermediate, and chains to Apple Root CA"
else
  fail "$g2_intermediate is not the reviewed G2 intermediate chained to Apple Root CA"
fi

# A `security find-identity -p codesigning` listing, in the form security(1) prints:
# every identity under "Matching identities", with the reason when it is not valid,
# then the valid ones again under "Valid identities only". Each argument is
# "CERT|REASON", with an empty REASON for a valid identity.
identity_listing() {
  local entry cert reason count=0 valid=0
  printf '\nPolicy: Code Signing\n  Matching identities\n'
  for entry in "$@"; do
    cert="${entry%%|*}"
    reason="${entry#*|}"
    count=$((count + 1))
    printf '  %d) %s "%s"%s\n' "$count" "$(hash_of "$cert")" "$identity_name" "${reason:+ ($reason)}"
  done
  printf '     %d identities found\n\n  Valid identities only\n' "$count"
  for entry in "$@"; do
    cert="${entry%%|*}"
    reason="${entry#*|}"
    [[ -z "$reason" ]] || continue
    valid=$((valid + 1))
    printf '  %d) %s "%s"\n' "$valid" "$(hash_of "$cert")" "$identity_name"
  done
  printf '     %d valid identities found\n' "$valid"
}

test_release="$HOME/Library/Keychains/metabrowser-release.keychain-db"
test_login="$HOME/Library/Keychains/login.keychain-db"
# Not $work, which the doctor names a local of its own.
history_call="$work/history-call"
: >"$test_login"
# A notary service that does not answer: a script whose sleep is its child, as a tool
# that forks would leave one, which keeps the doctor's capture of its output open until
# the sleep is stopped too.
stall="$work/stall"
stall_seconds=30
printf '#!/usr/bin/env bash\nsleep %s\necho "the stall was not stopped"\n' "$stall_seconds" >"$stall"
chmod +x "$stall"

# Each case sets these, and the stand-ins below read them.
reset_case() {
  # What macOS 26 reports for a keychain set with `set-keychain-settings -l -u -t`
  # (macOS CI, scripts/test-scripts.sh): use_lock_interval stays 0.
  case_status=$'exists=1\nunlocked=0\nlock_on_sleep=1\nuse_lock_interval=0\nlock_interval=900\nprofile=found'
  case_release_identities="leaf400|"
  case_login_identities=""
  case_listed=1
  case_intermediates="apple-g2"
  case_roots="apple-root"
  case_history=0
  : >"$test_release"
  unset SIGN_IDENTITY ONLINE APPLE_KEYCHAIN_PROFILE APPLE_API_KEY APPLE_API_KEY_ID APPLE_API_ISSUER
}

security() {
  local keychain="${*: -1}" entry cert
  case "$1" in
    list-keychains)
      case "$case_listed" in
        failed) return 50 ;;
        empty) ;;
        0) printf '    "%s"\n' "$test_login" ;;
        *) printf '    "%s"\n    "%s"\n' "$test_login" "$test_release" ;;
      esac
      ;;
    login-keychain) printf '    "%s"\n' "$test_login" ;;
    find-identity)
      if [[ "$keychain" == "$test_release" ]]; then
        # shellcheck disable=SC2086 # one word per identity
        identity_listing $case_release_identities
      elif [[ -n "$case_login_identities" ]]; then
        # shellcheck disable=SC2086
        identity_listing $case_login_identities
      else
        identity_listing
      fi
      ;;
    find-certificate)
      case "$*" in
        *"Apple Root CA"*) for cert in $case_roots; do cat "$certs/$cert.pem"; done ;;
        *"Developer ID Application"*)
          [[ "$keychain" == "$test_release" ]] || return 44
          for entry in $case_release_identities; do cat "$certs/${entry%%|*}.pem"; done
          ;;
        *"Developer ID Certification Authority"*)
          [[ "$keychain" == "$test_login" && -n "$case_intermediates" ]] || return 44
          for cert in $case_intermediates; do cat "$certs/$cert.pem"; done
          ;;
      esac
      ;;
    *) return 99 ;;
  esac
}
keychain_status() {
  printf '%s\n' "$case_status"
}
xcodebuild() {
  printf 'Xcode 26.6\nBuild version 17F00\n'
}
xcrun() {
  case "$1 $2" in
    "notarytool --version") echo 1.1.2 ;;
    "notarytool history")
      echo "history $*" >"$history_call"
      if [[ "$case_history" == hang ]]; then
        "$stall"
        return 1
      fi
      return "$case_history"
      ;;
    *) return 99 ;;
  esac
}

# Runs the doctor for the case, for a release when "$1" is 1, and checks its exit
# status "$2" and its number of failed checks "$3", then that each other argument is
# in its report.
doctor() {
  local for_release="$1" want_status="$2" want_failures="$3" label="$4" line failed
  shift 4
  rm -rf "$work/doctor"
  mkdir -p "$work/doctor"
  run run_signing_doctor "$for_release" "$work/doctor"
  failed="$(grep -c '^FAIL:' "$work/out" || true)"
  if ((status != want_status || failed != want_failures)); then
    fail "doctor, $label: status $status with $failed failed check(s), not $want_status with $want_failures: $(cat "$work/out")"
    return
  fi
  for line in "$@"; do
    if ! said "$line"; then
      fail "doctor, $label: no \"$line\" in: $(cat "$work/out")"
      return
    fi
  done
  pass "doctor, $label"
}

# Today's build Mac (the publishing plan's Current State): no release keychain, the
# identity in the login keychain and untrusted, no G2 intermediate, no notary profile.
reset_case
rm -f "$test_release"
case_status="exists=0"
case_login_identities="leaf400|CSSMERR_TP_NOT_TRUSTED"
case_intermediates=""
doctor 0 1 3 "the build Mac before the owner steps names exactly the keychain, the intermediate, and the profile" \
  "FAIL: the release keychain does not exist (O1: create it)" \
  "FAIL: the Developer ID - G2 intermediate is not installed" \
  "FAIL: no notary profile metabrowser-notary: it belongs in the release keychain, which does not exist (O3)" \
  "warn: the login keychain holds a Developer ID Application identity too"

reset_case
doctor 0 0 0 "everything ready and the keychain locked" \
  "ok: Xcode 26.6 Build version 17F00" "ok: notarytool 1.1.2" "ok: it is locked" \
  "ok: it locks on sleep and after 900 s idle" "ok: $identity_name ($(hash_of leaf400)) is valid" \
  "days" "ok: $identity_name is issued by Developer ID Certification Authority, G2" \
  "ok: $g2_intermediate is the reviewed copy, and chains to this Mac's Apple Root CA" \
  "ok: the Developer ID - G2 intermediate is installed, in $test_login" \
  "ok: the release keychain holds the notary profile metabrowser-notary"

reset_case
case_release_identities="leaf400|CSSMERR_TP_NOT_TRUSTED"
case_intermediates=""
doctor 0 1 2 "a missing intermediate leaves the identity untrusted" \
  "is not valid: CSSMERR_TP_NOT_TRUSTED: macOS cannot build its chain" \
  "FAIL: the release keychain holds no valid Developer ID Application identity (O1)" \
  "FAIL: the Developer ID - G2 intermediate is not installed"

reset_case
case_release_identities="leaf20|"
doctor 0 1 1 "a certificate 20 days from expiry fails" "day(s); renew it now (O9)"
reset_case
case_release_identities="leaf60|"
doctor 0 0 0 "a certificate 60 days from expiry warns" "warn: $identity_name expires on" "days; renew it (O9)"

reset_case
export SIGN_IDENTITY="Developer ID Application: Someone Else (Z9Y8X7W6V5)"
doctor 0 1 1 "a SIGN_IDENTITY that matches no identity fails" \
  "FAIL: SIGN_IDENTITY (Developer ID Application: Someone Else (Z9Y8X7W6V5)) names no valid identity"
reset_case
SIGN_IDENTITY="$(hash_of leaf400 | tr '[:upper:]' '[:lower:]')"
export SIGN_IDENTITY
doctor 0 0 0 "a SIGN_IDENTITY hash, in any case, names its identity" "ok: SIGN_IDENTITY names $identity_name"
reset_case
case_release_identities="leaf400| second|"
doctor 0 1 1 "two valid identities with one name are ambiguous" "codesign would refuse the name as ambiguous"

reset_case
case_intermediates="fake-g2"
doctor 0 1 2 "an intermediate with Apple's name and other contents is refused" \
  "is not Apple PKI's" "FAIL: the Developer ID - G2 intermediate is not installed"
reset_case
case_roots="other-root"
doctor 0 1 1 "the committed intermediate must chain to this Mac's Apple Root CA" \
  "FAIL: $g2_intermediate does not chain to an Apple Root CA"
reset_case
case_release_identities="leafg1|"
doctor 0 0 0 "a G1 certificate warns that its intermediate expires" "issued by the G1 Developer ID intermediate"

reset_case
doctor 1 1 2 "a release refuses a locked keychain and an unnamed identity" \
  "FAIL: it is locked; unlocking it is the go-ahead for this release" "(O7)" "FAIL: SIGN_IDENTITY is not set"
reset_case
case_status="${case_status/unlocked=0/unlocked=1}"
export SIGN_IDENTITY="$identity_name"
doctor 1 0 0 "a release goes ahead with the keychain unlocked" "ok: it is unlocked, for this release"
reset_case
case_status="${case_status/unlocked=0/unlocked=1}"
doctor 0 0 0 "an unlocked keychain outside a release warns" "warn: it is unlocked; lock it whenever no release is running"

reset_case
case_status="${case_status/lock_interval=900/lock_interval=3600}"
doctor 0 1 1 "a keychain that stays unlocked an hour fails" \
  "(O1: security set-keychain-settings -l -u -t $release_keychain_lock_seconds \"$test_release\")"
reset_case
case_status="${case_status/lock_on_sleep=1/lock_on_sleep=0}"
doctor 0 1 1 "a keychain that does not lock on sleep fails" "lock on sleep: 0"
reset_case
case_status=$'exists=1\nunlocked=0\nsettings=unreadable: User interaction is not allowed.\nprofile=unknown: User interaction is not allowed.'
doctor 0 0 0 "what a locked keychain hides is a warning, not a pass" \
  "warn: its lock settings could not be read" "warn: whether the release keychain holds the notary profile"
reset_case
case_status="${case_status/lock_interval=900/lock_interval=2147483647}"
doctor 0 1 1 "a keychain with no idle timeout (INT_MAX) fails" "after 2147483647 s idle"
reset_case
case_status="${case_status/lock_interval=900/lock_interval=0}"
doctor 0 1 1 "a keychain with a zero idle timeout fails" "after 0 s idle"
reset_case
case_listed=0
doctor 0 1 1 "a release keychain off the search list fails, with the command that keeps the list" \
  "FAIL: it is not on the user search list (O1: security list-keychains -d user -s \"$test_login\" \"$test_release\")"
# `-s` replaces the whole list, so with no list read, a printed command would take the
# login keychain off it. The intermediate is looked for on the same list, so it is not
# found either.
for unread in failed empty; do
  reset_case
  case_listed="$unread"
  doctor 0 1 2 "a search list read as $unread fails, and prints no command that would replace it" \
    "FAIL: the user search list could not be read" "FAIL: the Developer ID - G2 intermediate is not installed"
  if said "list-keychains -d user -s"; then
    fail "doctor, a search list read as $unread: it printed a -s command: $(cat "$work/out")"
  fi
done
reset_case
case_status="${case_status/profile=found/profile=absent}"
doctor 0 0 0 "a profile item the lookup misses warns, since its name is undocumented, and names the check" \
  "warn: the release keychain holds no item named as notarytool 1.1 names the profile metabrowser-notary" "ONLINE=1 says whether the profile works"
reset_case
case_status="${case_status/profile=found/profile=absent}"
case_status="${case_status/unlocked=0/unlocked=1}"
export ONLINE=1
doctor 0 0 0 "ONLINE=1 overrides a missed profile item when the notary service answers" \
  "ok: the notary service answered notarytool history with the profile metabrowser-notary"
reset_case
case_status="${case_status/profile=found/profile=absent}"
case_status="${case_status/unlocked=0/unlocked=1}"
export SIGN_IDENTITY="$identity_name"
rm -f "$history_call"
doctor 1 0 0 "a release's preflight asks the notary service when the profile item is missed" \
  "ok: the notary service answered notarytool history with the profile metabrowser-notary"
[[ -s "$history_call" ]] || fail "the preflight did not ask the notary service about a missed profile item"
reset_case
case_status="${case_status/profile=found/profile=absent}"
case_status="${case_status/unlocked=0/unlocked=1}"
export SIGN_IDENTITY="$identity_name"
case_history=1
doctor 1 1 1 "a release's preflight fails a missed profile item the notary service refuses" \
  "FAIL: notarytool history failed (O2, O3)"
reset_case
case_status="${case_status/unlocked=0/unlocked=1}"
export ONLINE=1
case_history=hang
saved_history_timeout="$notary_history_timeout_seconds"
notary_history_timeout_seconds=1
started="$SECONDS"
doctor 0 1 1 "a notary service that does not answer is a failure after notary_history_timeout_seconds" \
  "FAIL: notarytool history failed (O2, O3)" "stopped after 1 s"
# The rest of the doctor takes a second or two; a wait for the stall's sleep, its child,
# would take all of stall_seconds.
if ((SECONDS - started < stall_seconds / 2)); then
  pass "bounded stops the stalled call and its child, in $((SECONDS - started)) s"
else
  fail "the stalled call took $((SECONDS - started)) s, past its bound of 1 s: bounded left its child running"
fi
notary_history_timeout_seconds="$saved_history_timeout"

# The API key, as notarize.sh takes it, and the same choice when both kinds are set.
api_key="$work/AuthKey_DOCTOR.p8"
: >"$api_key"
chmod 600 "$api_key"
reset_case
export APPLE_API_KEY="$api_key" APPLE_API_KEY_ID=KEYID APPLE_API_ISSUER=ISSUER
doctor 0 0 0 "an API key with its ID and issuer passes" "ok: the notary credentials are an API key"
reset_case
export APPLE_API_KEY="$api_key" APPLE_API_KEY_ID=KEYID APPLE_API_ISSUER=ISSUER ONLINE=1
rm -f "$history_call"
doctor 0 0 0 "ONLINE=1 asks the notary service with the API key" "ok: the notary service answered notarytool history"
if grep -qF -- "--key $api_key --key-id KEYID --issuer ISSUER" "$history_call" 2>/dev/null; then
  pass "notarytool history gets the API key's path, ID, and issuer"
else
  fail "notarytool history ran with the API key as: $(cat "$history_call" 2>/dev/null)"
fi
reset_case
export APPLE_API_KEY="$api_key"
doctor 0 1 1 "an API key without its ID fails" "FAIL: APPLE_API_KEY_ID is not set"
reset_case
chmod 644 "$api_key"
export APPLE_API_KEY="$api_key" APPLE_API_KEY_ID=KEYID
doctor 0 0 0 "an API key others can read, and no issuer, warn" "can be read by other accounts" "APPLE_API_ISSUER is not set"
chmod 600 "$api_key"
reset_case
case_status="${case_status/profile=found/profile=absent}"
export APPLE_KEYCHAIN_PROFILE=metabrowser-notary APPLE_API_KEY="$api_key" APPLE_API_KEY_ID=KEYID
doctor 0 0 0 "with both kinds set, the doctor checks the profile, as notarize.sh uses it" \
  "the profile metabrowser-notary"
if said "the notary credentials are an API key"; then
  fail "with both kinds set, the doctor checked the API key, which notarize.sh does not use"
fi
reset_case
case_release_identities=""
doctor 0 1 1 "an empty release keychain fails" "FAIL: the release keychain holds no Developer ID Application identity (O1"

reset_case
export ONLINE=1
doctor 0 1 1 "ONLINE=1 never unlocks the keychain" \
  "FAIL: ONLINE=1 asks the notary service, which needs the release keychain unlocked"
reset_case
case_status="${case_status/profile=found/profile=absent}"
export SIGN_IDENTITY="$identity_name"
doctor 1 1 2 "a locked preflight that would ask the notary service says why, without naming ONLINE=1" \
  "FAIL: it is locked; unlocking it is the go-ahead for this release" \
  "FAIL: the keychain lookup missed the profile, so this preflight asks the notary service whether it works, which needs the release keychain unlocked"
if said "ONLINE=1"; then
  fail "a locked preflight named ONLINE=1, which it was not given: $(cat "$work/out")"
fi
reset_case
export ONLINE=1
case_status="${case_status/unlocked=0/unlocked=1}"
rm -f "$history_call"
doctor 0 0 0 "ONLINE=1 asks the notary service with the profile in the release keychain" \
  "ok: the notary service answered notarytool history"
if grep -qF -- "--keychain-profile metabrowser-notary --keychain $test_release" "$history_call" 2>/dev/null; then
  pass "notarytool history reads the profile from the release keychain"
else
  fail "notarytool history ran as: $(cat "$history_call" 2>/dev/null)"
fi
reset_case
export ONLINE=1
case_status="${case_status/unlocked=0/unlocked=1}"
case_history=1
doctor 0 1 1 "ONLINE=1 fails when the notary service refuses" "FAIL: notarytool history failed (O2, O3)"
unset -f security keychain_status xcodebuild xcrun
unset ONLINE SIGN_IDENTITY

# ── signature_facts and developer_id_problems ────────────────
# `codesign -dvvv` output for a notarizable app: a Developer ID signature with the
# hardened runtime flag, a secure timestamp (Timestamp=), a Team ID, and the chain.
developer_id_app='Executable=/Volumes/Metabrowser 0.1.0/Metabrowser.app/Contents/MacOS/Metabrowser
Identifier=io.github.jlevy.metabrowser
Format=app bundle with Mach-O thin (arm64)
CodeDirectory v=20500 size=1234 flags=0x10000(runtime) hashes=28+7 location=embedded
Hash type=sha256 size=32
CandidateCDHash sha256=0123456789abcdef0123456789abcdef01234567
CandidateCDHashFull sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
Hash choices=sha256
CMSDigest=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
CMSDigestType=2
CDHash=0123456789abcdef0123456789abcdef01234567
Signature size=9000
Authority=Developer ID Application: Example Developer (A1B2C3D4E5)
Authority=Developer ID Certification Authority
Authority=Apple Root CA
Timestamp=Nov 17, 2026 at 09:00:00
Info.plist entries=24
TeamIdentifier=A1B2C3D4E5
Runtime Version=26.0.0
Sealed Resources version=2 rules=13 files=2
Internal requirements count=1 size=200'
developer_id_image='Executable=/private/tmp/download/Metabrowser-0.1.0-arm64.dmg
Identifier=io.github.jlevy.metabrowser.dmg
Format=disk image
CodeDirectory v=20100 size=200 flags=0x0(none) hashes=1+6 location=embedded
Signature size=9000
Authority=Developer ID Application: Example Developer (A1B2C3D4E5)
Authority=Developer ID Certification Authority
Authority=Apple Root CA
Timestamp=Nov 17, 2026 at 09:05:00
TeamIdentifier=A1B2C3D4E5'
adhoc_app='Executable=/tmp/Metabrowser.app/Contents/MacOS/Metabrowser
Identifier=io.github.jlevy.metabrowser.dev
CodeDirectory v=20400 size=1234 flags=0x10002(adhoc,runtime) hashes=28+7 location=embedded
Signature=adhoc
Info.plist entries=24
TeamIdentifier=not set'
facts="$(signature_facts <<<"$developer_id_app")"
if [[ "$(tr '\n' ' ' <<<"$facts")" == "adhoc=0 runtime=1 timestamp=secure team=A1B2C3D4E5 authorities=Developer ID Application: Example Developer (A1B2C3D4E5)|Developer ID Certification Authority|Apple Root CA " ]] &&
  [[ -z "$(developer_id_problems "$facts" app A1B2C3D4E5)" ]]; then
  pass "a notarizable app's signature reads as one, with nothing wrong"
else
  fail "a notarizable app's signature read as: $facts; problems: $(developer_id_problems "$facts" app A1B2C3D4E5)"
fi
if [[ -z "$(developer_id_problems "$(signature_facts <<<"$developer_id_image")" image "")" ]]; then
  pass "a Developer ID image needs no hardened runtime, which is for code that runs"
else
  fail "a Developer ID image: $(developer_id_problems "$(signature_facts <<<"$developer_id_image")" image "")"
fi
facts="$(signature_facts <<<"$adhoc_app")"
if [[ "$(fact adhoc <<<"$facts")$(fact runtime <<<"$facts")$(fact timestamp <<<"$facts")" == 11none && -z "$(fact team <<<"$facts")" ]]; then
  pass "an ad hoc signature with the hardened runtime reads as both, with no Team ID or timestamp"
else
  fail "an ad hoc signature read as: $facts"
fi
expect_problem() {
  local label="$1" text="$2" kind="$3" team="$4" want="$5" problems
  problems="$(developer_id_problems "$(signature_facts <<<"$text")" "$kind" "$team")"
  if [[ "$problems" == *"$want"* ]]; then
    pass "$label"
  else
    fail "$label: the problems were: ${problems:-none}"
  fi
}
expect_problem "an app without the hardened runtime is refused" \
  "${developer_id_app/flags=0x10000(runtime)/flags=0x0(none)}" app "" "no hardened runtime"
expect_problem "a Signed Time is not a secure timestamp" \
  "${developer_id_app/Timestamp=/Signed Time=}" app "" "no secure timestamp"
expect_problem "another team than EXPECTED_TEAM_ID is refused" \
  "$developer_id_app" app Z9Y8X7W6V5 "the Team ID is A1B2C3D4E5, not EXPECTED_TEAM_ID Z9Y8X7W6V5"
expect_problem "a development certificate's chain is not a Developer ID chain" \
  "${developer_id_app/Developer ID Application: /Apple Development: }" app "" "not Developer ID Application"
expect_problem "an ad hoc signature is no Developer ID signature" "$adhoc_app" app "" "no Team ID"
expect_problem "a chain without Apple Root CA is refused" \
  "${developer_id_app/$'\n'Authority=Apple Root CA/}" app "" "not Developer ID Application"
expect_problem "a chain without the Developer ID intermediate is refused" \
  "${developer_id_app/$'\n'Authority=Developer ID Certification Authority/}" app "" "not Developer ID Application"
expect_problem "an image with a Signed Time, not a secure timestamp, is refused" \
  "${developer_id_image/Timestamp=/Signed Time=}" image "" "no secure timestamp"

# ── describe_quarantine ──────────────────────────────────────
described="$(describe_quarantine "0083;6735a1c4;Safari;3F1A2B3C-4D5E-6F70-8192-A3B4C5D6E7F8")"
if [[ "$described" == "flags 0x0083, set 2024-11-14 07:07:48 UTC, by Safari, event 3F1A2B3C-4D5E-6F70-8192-A3B4C5D6E7F8" ]]; then
  pass "a quarantine attribute is described: its flags, time, agent, and event"
else
  fail "a quarantine attribute was described as: $described"
fi
if [[ "$(describe_quarantine "01c1;zz;")" == "flags 0x01c1, set an unreadable time (zz), by no agent" ]]; then
  pass "an unreadable quarantine attribute is described, not refused"
else
  fail "an unreadable quarantine attribute: $(describe_quarantine "01c1;zz;")"
fi
# What macOS 26 stored for scripts/quarantine.swift on CI: the agent's spaces as \x20.
# The flags, time, and agent are the capture's; the event ID is made up.
described="$(describe_quarantine '0081;6afc0e31;Metabrowser\x20check-release\x20(simulated\x20download);3A5B7E4F-1C2D-4E5F-8A9B-0C1D2E3F4A5B')"
if [[ "$described" == "flags 0x0081, set 2026-11-17 08:20:01 UTC, by Metabrowser check-release (simulated download), event 3A5B7E4F-1C2D-4E5F-8A9B-0C1D2E3F4A5B" ]]; then
  pass "an agent name macOS stored with \\x20 for its spaces is described with its spaces"
else
  fail "the stored agent name was described as: $described"
fi
if [[ "$(decode_hex_escapes 'a\b\x41c\x')" == 'a\bAc\x' ]]; then
  pass "only a backslash, x, and two hex digits is decoded"
else
  fail "decode_hex_escapes gave: $(decode_hex_escapes 'a\b\x41c\x')"
fi

# ── The release's names, tag, assets, and checksum ───────────
if [[ "$(release_assets 0.1.0 arm64 | tr '\n' ' ')" == "Metabrowser-0.1.0-arm64.dmg Metabrowser-0.1.0-arm64.dmg.sha256 " ]]; then
  pass "a release's assets are its image and the image's checksum"
else
  fail "release_assets gave: $(release_assets 0.1.0 arm64 | tr '\n' ' ')"
fi
run version_of_tag macos-v0.1.0
if ((status == 0)) && [[ "$(cat "$work/out")" == 0.1.0 ]]; then
  pass "macos-v0.1.0 is version 0.1.0"
else
  fail "version_of_tag macos-v0.1.0: $(cat "$work/out")"
fi
for bad in v0.1.0 macos-v0.1 macos-v0.1.0-rc1 "macos-v0.1.0 "; do
  run version_of_tag "$bad"
  if ((status != 0)); then
    pass "'$bad' is not an app release tag"
  else
    fail "'$bad' was taken for an app release tag"
  fi
done

# A release as `gh release view --json tagName,isDraft,isImmutable,assets` gives it.
version_now="$(read_version)"
release_tag="macos-v$version_now"
downloads="$work/downloads"
mkdir -p "$downloads"
image_name="Metabrowser-$version_now-arm64.dmg"
printf 'not really an image\n' >"$downloads/$image_name"
write_checksum "$downloads/$image_name"
image_sha="$(cut -d' ' -f1 "$downloads/$image_name.sha256")"
release_json() {
  jq -n --arg tag "$1" --argjson draft "$2" --argjson immutable "$3" --arg image "$image_name" \
    --arg digest "$4" --arg sums_digest "sha256:$(shasum -a 256 "$downloads/$image_name.sha256" | cut -d' ' -f1)" '{
      tagName: $tag, isDraft: $draft, isImmutable: $immutable,
      assets: [
        {apiUrl: "https://api.github.com/repos/jlevy/metabrowser/releases/assets/1", contentType: "application/x-apple-diskimage",
         digest: $digest, name: $image, size: 20, state: "uploaded"},
        {apiUrl: "https://api.github.com/repos/jlevy/metabrowser/releases/assets/2", contentType: "text/plain",
         digest: $sums_digest, name: ($image + ".sha256"), size: 96, state: "uploaded"}
      ]}'
}
facts="$(release_json "$release_tag" true false "sha256:$image_sha" | release_facts "$release_tag" "$image_name" "$image_name.sha256")"
if [[ "$facts" == *"draft=true"* && "$facts" == *"immutable=false"* && "$facts" == *"digest $image_name=sha256:$image_sha"* ]]; then
  pass "a draft release's state and its assets' digests are read"
else
  fail "release_facts read: $facts"
fi
run release_facts macos-v9.9.9 "$image_name" "$image_name.sha256" <<<"$(release_json "$release_tag" true false x)"
if ((status != 0)) && said "is not macos-v9.9.9's"; then
  pass "another tag's release is refused"
else
  fail "another tag's release: $(cat "$work/out")"
fi

for change in '.assets += [{name: "Unexpected.dmg"}]' '.assets |= .[:1]' '.assets[1] = .assets[0]'; do
  run release_facts "$release_tag" "$image_name" "$image_name.sha256" \
    <<<"$(release_json "$release_tag" true false "sha256:$image_sha" | jq "$change")"
  if ((status != 0)) && said "must attach exactly $image_name and $image_name.sha256"; then
    pass "the draft must have the exact asset set ($change)"
  else
    fail "an unexpected asset set passed ($change): $(cat "$work/out")"
  fi
done

sums_digest="sha256:$(shasum -a 256 "$downloads/$image_name.sha256" | cut -d' ' -f1)"
if [[ -z "$(github_digest_problem "$downloads/$image_name.sha256" "$sums_digest")" &&
  "$(github_digest_problem "$downloads/$image_name.sha256" "sha256:$image_sha")" == *"GitHub's digest for $image_name.sha256 is"* &&
  "$(github_digest_problem "$downloads/$image_name.sha256" "")" == *"GitHub gives no digest for $image_name.sha256"* ]]; then
  pass "the downloaded checksum requires its own matching GitHub digest"
else
  fail "the downloaded checksum did not validate GitHub's digest correctly"
fi

if [[ -z "$(asset_problems "$downloads/$image_name" "$downloads/$image_name.sha256" "sha256:$image_sha")" ]]; then
  pass "an image that matches its checksum file and GitHub's digest passes"
else
  fail "a matching image: $(asset_problems "$downloads/$image_name" "$downloads/$image_name.sha256" "sha256:$image_sha")"
fi
expect_asset() {
  local label="$1" digest="$2" want="$3" problems
  problems="$(asset_problems "$downloads/$image_name" "$downloads/$image_name.sha256" "$digest")"
  if [[ "$problems" == *"$want"* ]]; then
    pass "$label"
  else
    fail "$label: the problems were: ${problems:-none}"
  fi
}
expect_asset "a digest that differs from the download fails" "sha256:$(printf '0%.0s' {1..64})" "GitHub's digest for $image_name is"
expect_asset "an asset GitHub gives no digest for fails" "" "GitHub gives no digest"
cp "$downloads/$image_name.sha256" "$work/sums.keep"
sed "s/  .*/  Other.dmg/" "$work/sums.keep" >"$downloads/$image_name.sha256"
expect_asset "a checksum file for another file fails" "sha256:$image_sha" "is not one shasum -a 256 line for $image_name"
cp "$work/sums.keep" "$downloads/$image_name.sha256"
printf 'changed\n' >>"$downloads/$image_name"
expect_asset "an image changed after its checksum fails" "sha256:$image_sha" "does not match $image_name.sha256"
printf 'not really an image\n' >"$downloads/$image_name"

# ── Build provenance and publication ─────────────────────────
# A gh stand-in: an attestation verifies only when attestation_ok is 1, and the Latest
# release is $latest_tag.
gh() {
  echo "gh $*" >>"$work/gh-calls"
  case "$1 $2" in
    "attestation verify") ((attestation_ok)) ;;
    "release verify" | "release verify-asset") return 0 ;;
    "api repos/jlevy/metabrowser/releases/latest") echo "$latest_tag" ;;
    *) return 99 ;;
  esac
}
: >"$work/gh-calls"
attestation_ok=0
run check_build_provenance ci "$release_tag" "$downloads/$image_name"
if ((status != 0)) && said "BUILT=ci, and $image_name has no build provenance attestation from $release_workflow"; then
  pass "BUILT=ci fails when the image carries no build provenance attestation"
else
  fail "BUILT=ci without an attestation: status $status: $(cat "$work/out")"
fi
attestation_ok=1
run check_build_provenance ci "$release_tag" "$downloads/$image_name"
if ((status == 0)) &&
  grep -qxF "gh attestation verify $downloads/$image_name --repo jlevy/metabrowser --signer-workflow jlevy/metabrowser/.github/workflows/macos-release.yml --source-ref refs/tags/$release_tag" "$work/gh-calls"; then
  pass "BUILT=ci verifies the release workflow's attestation for the tag"
else
  fail "BUILT=ci with an attestation: status $status: $(cat "$work/out"); gh ran: $(cat "$work/gh-calls")"
fi
: >"$work/gh-calls"
run check_build_provenance local "$release_tag" "$downloads/$image_name"
if ((status == 0)) && said "build provenance: none, as BUILT=local says" && [[ ! -s "$work/gh-calls" ]]; then
  pass "BUILT=local expects no attestation, and asks for none"
else
  fail "BUILT=local: status $status: $(cat "$work/out")"
fi
run check_build_provenance "" "$release_tag" "$downloads/$image_name"
if ((status != 0)) && said "BUILT must be local or ci"; then
  pass "a build kind left out is refused, never inferred"
else
  fail "no BUILT: status $status: $(cat "$work/out")"
fi

latest_tag=v0.13.0
immutable_on=true
verify_ok=1
verify_asset_ok=1
gh() {
  echo "gh $*" >>"$work/gh-calls"
  case "$1 $2" in
    "attestation verify") ((attestation_ok)) ;;
    "release verify") ((verify_ok)) ;;
    "release verify-asset") ((verify_asset_ok)) ;;
    "api repos/jlevy/metabrowser/releases/latest") echo "$latest_tag" ;;
    "api repos/jlevy/metabrowser/immutable-releases") echo "$immutable_on" ;;
    *) return 99 ;;
  esac
}
: >"$work/gh-calls"
run check_publication "$release_tag" true false "$downloads/$image_name"
if ((status == 0)) && said "not yet, since $release_tag is a draft; immutable releases are on"; then
  pass "a draft has no release attestation yet, and immutable releases are on, and it says both"
else
  fail "a draft's publication: status $status: $(cat "$work/out")"
fi
immutable_on=false
run check_publication "$release_tag" true false "$downloads/$image_name"
if ((status != 0)) && said "immutable releases are off for jlevy/metabrowser, so publishing $release_tag would leave it mutable"; then
  pass "a draft fails while the repository's immutable releases are off, before it is published"
else
  fail "a draft with immutable releases off: status $status: $(cat "$work/out")"
fi
immutable_on=true
run check_publication "$release_tag" false false "$downloads/$image_name"
if ((status != 0)) && said "not immutable; turn on immutable releases (O5)"; then
  pass "a published release that is not immutable fails"
else
  fail "a mutable published release: status $status: $(cat "$work/out")"
fi
: >"$work/gh-calls"
run check_publication "$release_tag" false true "$downloads/$image_name" "$downloads/$image_name.sha256"
if ((status == 0)) && said "the Latest release is v0.13.0" &&
  grep -qxF "gh release verify $release_tag --repo jlevy/metabrowser" "$work/gh-calls" &&
  grep -qxF "gh release verify-asset $release_tag $downloads/$image_name --repo jlevy/metabrowser" "$work/gh-calls" &&
  grep -qxF "gh release verify-asset $release_tag $downloads/$image_name.sha256 --repo jlevy/metabrowser" "$work/gh-calls"; then
  pass "a published, immutable, attested release that is not Latest passes, with the release and each asset verified"
else
  fail "a published release: status $status: $(cat "$work/out"); gh ran: $(cat "$work/gh-calls")"
fi
verify_ok=0
run check_publication "$release_tag" false true "$downloads/$image_name"
if ((status != 0)) && said "gh release verify $release_tag failed"; then
  pass "a published release whose release attestation does not verify fails"
else
  fail "a release attestation that does not verify: status $status: $(cat "$work/out")"
fi
verify_ok=1
verify_asset_ok=0
run check_publication "$release_tag" false true "$downloads/$image_name"
if ((status != 0)) && said "gh release verify-asset $release_tag $image_name failed"; then
  pass "a published release whose asset does not verify fails"
else
  fail "an asset that does not verify: status $status: $(cat "$work/out")"
fi
verify_asset_ok=1
latest_tag="$release_tag"
run check_publication "$release_tag" false true "$downloads/$image_name"
if ((status != 0)) && said "is the repository's Latest release"; then
  pass "an app release published as Latest fails"
else
  fail "an app release published as Latest: status $status: $(cat "$work/out")"
fi
unset -f gh

# tag_commit, for a lightweight tag, an annotated one, and a tag on something else.
tag_sha=0123456789abcdef0123456789abcdef01234567
gh() {
  case "$*" in
    *"git/ref/tags/macos-v1.0.0 "*) echo "commit $tag_sha" ;;
    *"git/ref/tags/macos-v1.0.1 "*) echo "tag fedcba9876543210fedcba9876543210fedcba98" ;;
    *"git/tags/fedcba9876543210fedcba9876543210fedcba98 "*) echo "commit $tag_sha" ;;
    *"git/ref/tags/macos-v1.0.2 "*) echo "tree $tag_sha" ;;
    *) return 1 ;;
  esac
}
if [[ "$(tag_commit macos-v1.0.0)|$(tag_commit macos-v1.0.1)" == "$tag_sha|$tag_sha" ]]; then
  pass "a lightweight tag and an annotated one both name their commit"
else
  fail "tag_commit gave: $(tag_commit macos-v1.0.0 2>&1)|$(tag_commit macos-v1.0.1 2>&1)"
fi
for bad in macos-v1.0.2 macos-v1.0.3; do
  run tag_commit "$bad"
  if ((status != 0)); then
    pass "tag_commit stops for $bad, a tag on no commit or no tag"
  else
    fail "tag_commit accepted $bad: $(cat "$work/out")"
  fi
done
unset -f gh

# ── The app's identity against the tag ───────────────────────
expect_identity() {
  local label="$1" want="$2" problems
  shift 2
  problems="$(release_identity_problems "$@" "$version_now" "$tag_sha")"
  if [[ -z "$want" && -z "$problems" ]] || [[ -n "$want" && "$problems" == *"$want"* ]]; then
    pass "$label"
  else
    fail "$label: the problems were: ${problems:-none}"
  fi
}
expect_identity "the release variant, version, and commit pass" "" \
  io.github.jlevy.metabrowser "$version_now" "$tag_sha"
expect_identity "a development build is not the release" "not the release variant" \
  io.github.jlevy.metabrowser.dev "$version_now" "$tag_sha"
expect_identity "another version is not the release" "not $version_now" \
  io.github.jlevy.metabrowser 9.9.9 "$tag_sha"
expect_identity "another commit, with the same VERSION, is not the release" "not from $tag_sha" \
  io.github.jlevy.metabrowser "$version_now" 89abcdef0123456789abcdef0123456789abcdef
expect_identity "a build with uncommitted changes is not the release" "with uncommitted changes" \
  io.github.jlevy.metabrowser "$version_now" "$tag_sha-dirty"
expect_identity "a build that records no commit is not the release" "records no source commit" \
  io.github.jlevy.metabrowser "$version_now" ""
# The build records the full ID, so a prefix of the tag's commit, as an older build
# recorded, is another commit as far as the check can tell.
expect_identity "a short commit ID is not taken as a match" "not from $tag_sha" \
  io.github.jlevy.metabrowser "$version_now" "${tag_sha:0:7}"
expect_identity "a shorter prefix is not taken as a match" "not from $tag_sha" \
  io.github.jlevy.metabrowser "$version_now" 0123

# ── check-release.sh, end to end, as far as Linux goes ───────
# With an exported gh stand-in that serves the release above, as a draft or, with
# stub_published=1, published: each case stops at the step it is about, and a good
# release reaches step 6, the quarantine helper, which needs a Mac's swiftc.
gh() {
  case "$1 $2" in
    "release view")
      if [[ "${stub_published:-0}" == 1 ]]; then
        release_json "$release_tag" false true "${stub_digest:-sha256:$image_sha}"
      else
        release_json "$release_tag" true false "${stub_digest:-sha256:$image_sha}"
      fi
      ;;
    "release download") cp "$downloads/${*:7:1}" "${*: -1}/" ;;  # release download TAG --repo R --pattern ASSET --dir DIR
    "attestation verify") return 1 ;;
    "release verify") [[ "${stub_verify:-ok}" == ok ]] ;;
    "release verify-asset") return 0 ;;
    "api repos/jlevy/metabrowser/git/ref/tags/$release_tag") echo "commit 0123456789abcdef0123456789abcdef01234567" ;;
    "api repos/jlevy/metabrowser/immutable-releases") echo true ;;
    "api repos/jlevy/metabrowser/releases/latest") echo v0.13.0 ;;
    *) return 99 ;;
  esac
}
swiftc() {
  echo "swiftc is not here" >&2
  return 1
}
export -f gh release_json swiftc
export release_tag image_sha downloads image_name
team=A1B2C3D4E5
run env TAG="$release_tag" BUILT=ci EXPECTED_TEAM_ID="$team" scripts/check-release.sh
if ((status != 0)) && said "checksum: $image_name matches" &&
  said "BUILT=ci, and $image_name has no build provenance attestation"; then
  pass "check-release.sh with BUILT=ci checks the checksum and digest, then stops without an attestation"
else
  fail "check-release.sh with BUILT=ci and no attestation: status $status: $(cat "$work/out")"
fi
run env TAG="$release_tag" BUILT=local EXPECTED_TEAM_ID="$team" stub_digest="sha256:$(printf '0%.0s' {1..64})" scripts/check-release.sh
if ((status != 0)) && said "GitHub's digest for $image_name is" && ! said "checksum: $image_name matches"; then
  pass "check-release.sh stops at the checksum step when GitHub's digest differs from the download"
else
  fail "check-release.sh with a wrong digest: status $status: $(cat "$work/out")"
fi
run env TAG="$release_tag" BUILT=local EXPECTED_TEAM_ID="$team" stub_published=1 stub_verify=fail scripts/check-release.sh
if ((status != 0)) && said "build provenance: none" && said "gh release verify $release_tag failed"; then
  pass "check-release.sh stops at the publication step when a published release's attestation does not verify"
else
  fail "check-release.sh with an unverified release: status $status: $(cat "$work/out")"
fi
run env TAG="$release_tag" BUILT=local EXPECTED_TEAM_ID="$team" stub_published=1 scripts/check-release.sh
if ((status != 0)) && said "release attestation: verified for $release_tag" && said "could not build scripts/quarantine.swift"; then
  pass "check-release.sh runs every check before the quarantine on a good published release, and stops only for swiftc"
else
  fail "check-release.sh on a good published release: status $status: $(cat "$work/out")"
fi
run env TAG="$release_tag" BUILT=local EXPECTED_TEAM_ID="$team" scripts/check-release.sh
if ((status != 0)) && said "immutable releases are on, so publishing makes it immutable" && said "could not build scripts/quarantine.swift"; then
  pass "check-release.sh checks a draft's immutable releases before the quarantine"
else
  fail "check-release.sh on a good draft: status $status: $(cat "$work/out")"
fi
for team_case in "" "a1b2c3d4e5" "TOO-LONG-TEAM"; do
  run env TAG="$release_tag" BUILT=local EXPECTED_TEAM_ID="$team_case" scripts/check-release.sh
  if ((status != 0)) && said "EXPECTED_TEAM_ID must be the publisher's 10-character Team ID"; then
    pass "check-release.sh refuses EXPECTED_TEAM_ID '$team_case'"
  else
    fail "check-release.sh with EXPECTED_TEAM_ID '$team_case': status $status: $(cat "$work/out")"
  fi
done
run env TAG="$release_tag" EXPECTED_TEAM_ID="$team" scripts/check-release.sh
if ((status != 0)) && said "BUILT must be local or ci"; then
  pass "check-release.sh refuses to run without BUILT"
else
  fail "check-release.sh without BUILT: status $status: $(cat "$work/out")"
fi
run env TAG=macos-v99.0.0 BUILT=local EXPECTED_TEAM_ID="$team" scripts/check-release.sh
if ((status != 0)) && said "check out the release's commit"; then
  pass "check-release.sh refuses a tag whose version this checkout does not have"
else
  fail "check-release.sh for another version: status $status: $(cat "$work/out")"
fi

# Steps 6 and 7 and the summary, from a copy of the scripts whose check-dmg.sh records
# what it was given, with a swiftc that builds a quarantine helper answering as it does
# for a gh download. check-dmg.sh takes the team, version, and commit as optional, so a
# call that dropped them would still pass, and only this record shows it.
app_copy() {
  rm -rf "$1"
  mkdir -p "$1"
  cp -R scripts "$1/"
  cp VERSION "$1/"
}
app_copy "$work/release-copy"
cat >"$work/release-copy/scripts/check-dmg.sh" <<'EOF'
#!/usr/bin/env bash
printf 'NOTARIZE=%s EXPECTED_TEAM_ID=%s EXPECTED_VERSION=%s EXPECTED_COMMIT=%s image=%s\n' "${NOTARIZE:-}" \
  "${EXPECTED_TEAM_ID:-}" "${EXPECTED_VERSION:-}" "${EXPECTED_COMMIT:-}" "$(basename "$1")" >"$check_dmg_record"
EOF
chmod +x "$work/release-copy/scripts/check-dmg.sh"
swiftc() {
  # swiftc -O scripts/quarantine.swift -o OUTPUT
  printf '#!/usr/bin/env bash\necho simulated\n' >"${*: -1}"
  chmod +x "${*: -1}"
}
check_dmg_record="$work/check-dmg-record"
export -f swiftc
export check_dmg_record
rm -f "$check_dmg_record"
# Values in its own environment that check-release.sh must override, as check-dmg.sh
# would otherwise inherit them. EXPECTED_TEAM_ID is its input, passed on unchanged.
run env TAG="$release_tag" BUILT=local EXPECTED_TEAM_ID="$team" LAUNCH=0 NOTARIZE=0 EXPECTED_VERSION=9.9.9 \
  EXPECTED_COMMIT=89abcde "$work/release-copy/scripts/check-release.sh"
want="NOTARIZE=1 EXPECTED_TEAM_ID=$team EXPECTED_VERSION=$version_now EXPECTED_COMMIT=0123456789abcdef0123456789abcdef01234567 image=$image_name"
if ((status == 0)) && [[ "$(cat "$check_dmg_record" 2>/dev/null)" == "$want" ]] && said "quarantine: simulated" &&
  said "check-dmg.sh with NOTARIZE=1: passed, team $team, the release variant $version_now from 0123456789abcdef0123456789abcdef01234567"; then
  pass "check-release.sh runs check-dmg.sh with NOTARIZE=1 and the team, version, and commit it then reports"
else
  fail "check-release.sh's step 7: status $status; check-dmg.sh got: $(cat "$check_dmg_record" 2>/dev/null); output: $(cat "$work/out")"
fi
unset -f gh release_json swiftc
unset check_dmg_record

# ── The launch check's backup ────────────────────────────────
# A defaults stand-in that keeps each domain as a file, and the release identity's
# state: defaults, a session, and recent documents, all of which must come back as
# they were, and nothing where there was nothing.
defaults_store="$work/defaults"
mkdir -p "$defaults_store"
defaults() {
  case "$1" in
    read) [[ -f "$defaults_store/$2" ]] ;;
    export) cp "$defaults_store/$2" "$3" ;;
    import) cp "$3" "$defaults_store/$2" ;;
    delete) rm -f "$defaults_store/$2" ;;
    *) return 99 ;;
  esac
}
release_id=io.github.jlevy.metabrowser
session_file="$(release_session_file)"
recents_dir="$(release_recents_dir)"
mkdir -p "$(dirname "$session_file")" "$recents_dir"
echo "the owner's settings" >"$defaults_store/$release_id"
echo "the owner's session" >"$session_file"
echo "the owner's recents" >"$recents_dir/$release_id.sfl3"
backup_release_state "$work/backup" "$release_id"
if [[ ! -e "$defaults_store/$release_id" && ! -e "$session_file" && ! -e "$recents_dir/$release_id.sfl3" ]]; then
  pass "the launch check clears the release identity's state after backing it up"
else
  fail "the launch check left the release identity's state in place"
fi
echo "the launch's settings" >"$defaults_store/$release_id"
echo "the launch's session" >"$session_file"
echo "the launch's recents" >"$recents_dir/$release_id.sfl3"
if restore_release_state "$work/backup" "$release_id" &&
  [[ "$(cat "$defaults_store/$release_id")|$(cat "$session_file")|$(cat "$recents_dir/$release_id.sfl3")" == "the owner's settings|the owner's session|the owner's recents" ]]; then
  pass "the launch check restores the owner's defaults, session, and recent documents"
else
  fail "the launch check restored: $(cat "$defaults_store/$release_id" "$session_file" "$recents_dir/$release_id.sfl3" 2>&1 | tr '\n' '|')"
fi
rm -rf "$work/backup" "$defaults_store/$release_id" "$session_file" "$recents_dir/$release_id.sfl3"
backup_release_state "$work/backup" "$release_id"
echo "the launch's settings" >"$defaults_store/$release_id"
echo "the launch's session" >"$session_file"
echo "the launch's recents" >"$recents_dir/$release_id.sfl3"
if restore_release_state "$work/backup" "$release_id" &&
  [[ ! -e "$defaults_store/$release_id" && ! -e "$session_file" && ! -e "$recents_dir/$release_id.sfl3" ]]; then
  pass "where the owner had no state, the launch check leaves none"
else
  fail "where the owner had no state, the launch check left some"
fi
if restore_release_state "$work/no-backup" "$release_id"; then
  fail "a restore without a complete backup reported success"
else
  pass "a restore without a complete backup fails, so the script keeps what it has"
fi
unset -f defaults
for path in "/private/var/folders/xy/abc/T/AppTranslocation/0A1B2C3D/d/Metabrowser.app/Contents/MacOS/Metabrowser" \
  "/Applications/Metabrowser.app/Contents/MacOS/Metabrowser"; do
  if is_translocated_path "$path"; then
    verdict=translocated
  else
    verdict=installed
  fi
  echo "$verdict" >>"$work/translocation"
done
if [[ "$(tr '\n' ' ' <"$work/translocation")" == "translocated installed " ]]; then
  pass "a path under AppTranslocation is translocated, and one in Applications is not"
else
  fail "is_translocated_path judged: $(tr '\n' ' ' <"$work/translocation")"
fi

translocated_path="/private/var/folders/xy/abc/T/AppTranslocation/0A1B2C3D/d/Metabrowser.app/Contents/MacOS/Metabrowser"
moved_path="/Applications/Metabrowser.app/Contents/MacOS/Metabrowser"
if ran_as_expected "$translocated_path" translocated && ran_as_expected "$moved_path" installed &&
  ! ran_as_expected "$moved_path" translocated && ! ran_as_expected "$translocated_path" installed; then
  pass "the launch check fails a first launch that is not translocated, and a moved copy that still is"
else
  fail "ran_as_expected judged a launch wrongly"
fi

# A launch check that ended before restoring: the next run, and make clean, find it.
leftovers="$work/leftovers"
mkdir -p "$leftovers/launch-check-20261117T090000Z/backup" "$leftovers/launch-check-20261117T100000Z/backup"
: >"$leftovers/launch-check-20261117T090000Z/backup/complete"
if [[ "$(leftover_launch_checks "$leftovers")" == "$leftovers/launch-check-20261117T090000Z" &&
  -z "$(leftover_launch_checks "$work/no-such-build")" ]]; then
  pass "a launch check's complete backup is found, and an incomplete one, which cleared nothing, is not"
else
  fail "leftover_launch_checks found: $(leftover_launch_checks "$leftovers")"
fi
mkdir -p "$work/clean/scripts" "$work/clean/build/launch-check-20261117T090000Z/backup" "$work/clean/.build"
cp Makefile "$work/clean/"
cp scripts/common.sh scripts/check-release-lib.sh "$work/clean/scripts/"
: >"$work/clean/build/launch-check-20261117T090000Z/backup/complete"
if ! make -s -C "$work/clean" clean >"$work/out" 2>&1 && [[ -f "$work/clean/build/launch-check-20261117T090000Z/backup/complete" ]] &&
  said "scripts/launch-release.sh --restore"; then
  pass "make clean keeps build/ while it holds a launch check's backup, and names the restore"
else
  fail "make clean with a launch check's backup: $(cat "$work/out")"
fi
rm -rf "$work/clean/build/launch-check-20261117T090000Z"
if make -s -C "$work/clean" clean >"$work/out" 2>&1 && [[ ! -e "$work/clean/build" && ! -e "$work/clean/.build" ]]; then
  pass "make clean removes build/ and .build when no backup is left"
else
  fail "make clean without a backup: $(cat "$work/out")"
fi

# --restore, end to end, with the defaults stand-in exported.
defaults() {
  case "$1" in
    read) [[ -f "$defaults_store/$2" ]] ;;
    export) cp "$defaults_store/$2" "$3" ;;
    import) cp "$3" "$defaults_store/$2" ;;
    delete) rm -f "$defaults_store/$2" ;;
    *) return 99 ;;
  esac
}
# A pgrep stand-in, so that no case depends on what runs on this Mac: it lists
# $stub_running, the pids of a running Metabrowser, if any.
pgrep() {
  [[ -z "${stub_running:-}" ]] || echo "$stub_running"
}
echo "the owner's settings" >"$defaults_store/$release_id"
echo "the owner's session" >"$session_file"
backup_release_state "$work/interrupted/backup" "$release_id"
echo "the launch's session" >"$session_file"
export defaults_store
export -f defaults pgrep
run env stub_running=4242 scripts/launch-release.sh --restore "$work/interrupted"
if ((status != 0)) && said "a Metabrowser is running (4242 ); quit every copy first" &&
  [[ -f "$work/interrupted/backup/complete" && "$(cat "$session_file")" == "the launch's session" ]]; then
  pass "launch-release.sh --restore refuses while a Metabrowser runs, and keeps the backup"
else
  fail "launch-release.sh --restore with a Metabrowser running: status $status: $(cat "$work/out")"
fi
run scripts/launch-release.sh --restore "$work/interrupted"
if ((status == 0)) && [[ ! -e "$work/interrupted" ]] &&
  [[ "$(cat "$defaults_store/$release_id")|$(cat "$session_file")" == "the owner's settings|the owner's session" ]]; then
  pass "launch-release.sh --restore puts back an interrupted run's state and removes its folder"
else
  fail "launch-release.sh --restore: status $status: $(cat "$work/out")"
fi
run scripts/launch-release.sh --restore "$work/interrupted"
if ((status != 0)) && said "could not restore"; then
  pass "launch-release.sh --restore without a backup fails"
else
  fail "launch-release.sh --restore without a backup: status $status: $(cat "$work/out")"
fi
unset -f defaults pgrep
rm -f "$defaults_store/$release_id" "$session_file"

# The next run refuses while an interrupted run's backup is left, before it needs a
# terminal, so this runs where nothing is launched: in a copy, whose build/ is its own.
app_copy "$work/launch-copy"
mkdir -p "$work/launch-copy/build/launch-check-20261117T090000Z/backup"
: >"$work/launch-copy/build/launch-check-20261117T090000Z/backup/complete"
run "$work/launch-copy/scripts/launch-release.sh" "$work/some.dmg"
# The folder is named as the script's cd spells it, which can differ from $work's.
if ((status != 0)) && said "quit Metabrowser, then restore it: scripts/launch-release.sh --restore " &&
  said "/launch-copy/build/launch-check-20261117T090000Z"; then
  pass "launch-release.sh refuses to launch while an interrupted run's backup is left, and names the restore"
else
  fail "launch-release.sh with a backup left: status $status: $(cat "$work/out")"
fi

# What --restore unregisters, and what an answer to a question means.
mkdir -p "$work/copies/Downloads/Metabrowser.app" "$work/copies/Moved in Finder/Metabrowser.app" \
  "$work/copies/mount/Metabrowser.app" "$work/copies/backup"
if [[ "$(launch_copies "$work/copies" Metabrowser)" == "$work/copies/Downloads/Metabrowser.app"$'\n'"$work/copies/Moved in Finder/Metabrowser.app" ]]; then
  pass "a launch check's copies are the ones it opened, and not the image's own"
else
  fail "launch_copies found: $(launch_copies "$work/copies" Metabrowser | tr '\n' '|')"
fi
meanings=""
for answer in y Y yes YES n N no No "" yep "y es" maybe; do
  meanings="$meanings$(answer_meaning "$answer")|"
done
if [[ "$meanings" == "yes|yes|yes|yes|no|no|no|no|||||" ]]; then
  pass "y and yes, in either case, are yes, n and no are no, and anything else is asked again"
else
  fail "answer_meaning read: $meanings"
fi
# The rest of launch-release.sh, its launches and its questions, needs a terminal and a
# Mac's Gatekeeper, so no test here runs it; the runbook's LAUNCH=1 run at the Mac does.

# ── The metab floor ──────────────────────────────────────────
mkdir -p "$work/floor/Sources/ShellCore/Setup"
run metab_floor_released
if said "no longer declares"; then
  fail "metab_floor_released cannot read this checkout's declaration: $(cat "$work/out")"
else
  pass "metab_floor_released reads this checkout's MetabRequirement.isReleased (released: $( ((status == 0)) && echo yes || echo no))"
fi
sed 's/public static let isReleased = false/public static let isReleased = true/' Sources/ShellCore/Setup/MetabVersion.swift \
  >"$work/floor/Sources/ShellCore/Setup/MetabVersion.swift"
if (cd "$work/floor" && metab_floor_released); then
  pass "an official release goes ahead once MetabRequirement.isReleased is true"
else
  fail "metab_floor_released refused isReleased = true"
fi
sed 's/public static let isReleased = .*/public static var isReleased: Bool { true }/' Sources/ShellCore/Setup/MetabVersion.swift \
  >"$work/floor/Sources/ShellCore/Setup/MetabVersion.swift"
run bash -c 'cd "$1" && source "$2/scripts/common.sh" && metab_floor_released' _ "$work/floor" "$PWD"
if ((status != 0)) && said "no longer declares MetabRequirement.isReleased"; then
  pass "a declaration of isReleased this does not read stops the release, rather than passing it"
else
  fail "a changed isReleased declaration: status $status: $(cat "$work/out")"
fi
# release.sh's preflight, from a copy whose declaration is false, so the case holds once
# the real one is true, and whose build-app.sh records that it ran.
app_copy "$work/release-floor"
mkdir -p "$work/release-floor/Sources/ShellCore/Setup"
sed 's/public static let isReleased = true/public static let isReleased = false/' Sources/ShellCore/Setup/MetabVersion.swift \
  >"$work/release-floor/Sources/ShellCore/Setup/MetabVersion.swift"
printf '#!/usr/bin/env bash\n: >"$(dirname "$0")/../built"\n' >"$work/release-floor/scripts/build-app.sh"
run env -u SIGN_IDENTITY VARIANT=release NOTARIZE=1 "$work/release-floor/scripts/release.sh"
if ((status != 0)) && said "MetabRequirement.isReleased is false" && said "not an official build" &&
  [[ ! -e "$work/release-floor/built" ]]; then
  pass "release.sh's preflight lists an unreleased metab floor, and stops before it builds"
else
  fail "release.sh with the metab floor unreleased: status $status: $(cat "$work/out")"
fi

# ── parse_identities on an unusual listing ───────────────────
listing='  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Application: A "quoted" name (A1B2C3D4E5)" (CSSMERR_TP_CERT_EXPIRED)
     1 identities found'
if [[ "$(parse_identities <<<"$listing")" == $'0123456789ABCDEF0123456789ABCDEF01234567\tCSSMERR_TP_CERT_EXPIRED\tDeveloper ID Application: A "quoted" name (A1B2C3D4E5)' ]]; then
  pass "an identity's name may hold quotes, and its reason is kept"
else
  fail "parse_identities read: $(parse_identities <<<"$listing")"
fi

if ((failures)); then
  die "$failures release-logic check(s) failed"
fi
echo "Release-logic checks passed"
