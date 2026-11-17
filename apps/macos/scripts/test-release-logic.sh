#!/usr/bin/env bash
# Tests what the release scripts decide, on stand-ins for Apple's tools, so that it runs
# on Linux as well as on a Mac: `make test` runs it through
# tests/test_macos_release_scripts.py, and `make macos-test` through
# scripts/test-scripts.sh. It needs bash, jq, openssl, and shasum, and none of Apple's
# tools. What only a Mac can show, a signed build or a real keychain, is the runbook's
# signing-session checks (README.md, Building a Release).
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
#   - The security, xcrun, and xcodebuild stand-ins print output in the form those tools
#     print it, written for these tests rather than captured from a run; the
#     certificates they return are generated here with openssl, with Apple's names and
#     made-up keys, so expiry and issuer are real. Real output meets these readers in
#     scripts/test-scripts.sh, on macOS CI (a throwaway keychain), and on the build Mac
#     (the first run of the signing doctor).
#   - keychain_status stands in for scripts/keychain-status.swift, whose output this
#     repository defines; scripts/test-scripts.sh runs the real one, in CI, on a
#     throwaway keychain.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh
# shellcheck source=signing-lib.sh
source scripts/signing-lib.sh
# shellcheck source=notary-lib.sh
source scripts/notary-lib.sh

for tool in jq openssl shasum; do
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
    "notarytool submit") echo '{"id":"0B4C3B1E-7A2D-4F55-9E1C-2D6A8F0E5C11","message":"Processing complete","status":"Accepted"}' ;;
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

# Each case sets these, and the stand-ins below read them.
reset_case() {
  case_status=$'exists=1\nunlocked=0\nlock_on_sleep=1\nuse_lock_interval=1\nlock_interval=900\nprofile=found'
  case_release_identities="leaf400|"
  case_login_identities=""
  case_listed=1
  case_intermediates="apple-g2"
  case_roots="apple-root"
  case_history=0
  : >"$test_release"
  unset SIGN_IDENTITY ONLINE APPLE_KEYCHAIN_PROFILE
}

security() {
  local keychain="${*: -1}" entry cert
  case "$1" in
    list-keychains)
      printf '    "%s"\n' "$test_login"
      ((case_listed == 0)) || printf '    "%s"\n' "$test_release"
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
case_listed=0
doctor 0 1 1 "a release keychain off the search list fails" "FAIL: it is not on the user search list (O1"
reset_case
case_status="${case_status/profile=found/profile=absent}"
doctor 0 1 1 "a missing profile names its owner step" "FAIL: the release keychain holds no notary profile metabrowser-notary (O3"
reset_case
case_release_identities=""
doctor 0 1 1 "an empty release keychain fails" "FAIL: the release keychain holds no Developer ID Application identity (O1"

reset_case
export ONLINE=1
doctor 0 1 1 "ONLINE=1 never unlocks the keychain" "FAIL: ONLINE=1 needs the release keychain unlocked"
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
