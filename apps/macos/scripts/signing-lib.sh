# The signing doctor's checks, sourced by scripts/check-signing.sh and by
# scripts/test-release-logic.sh, which runs them on stand-ins for Apple's tools. They
# only read: nothing here unlocks a keychain, changes one, or asks for anything, and
# scripts/keychain-status.swift, which reads the release keychain's state, turns keychain
# prompts off before it reads.
#
# run_signing_doctor prints one line per check, "ok:", "warn:", or "FAIL:", and each miss
# names the owner step that fixes it: O1 to O9 in README.md, Building a Release.
# shellcheck shell=bash

# The release keychain locks on sleep and after at most this many seconds idle: longer
# than one notarization, which Apple says usually finishes within 5 minutes, and short
# enough that a keychain left unlocked after a release locks itself soon after.
release_keychain_lock_seconds=900

# A Developer ID certificate this many days or fewer from expiry fails the doctor, and
# one within the warning window warns, so the yearly renewal (O9) starts while a release
# can still be signed: Apple's account help says G2 certificates last one year.
expiry_fail_days=30
expiry_warn_days=90

# Apple's "Developer ID - G2" intermediate, the file Apple PKI publishes at
# https://www.apple.com/certificateauthority/DeveloperIDG2CA.cer, and that file's
# SHA-256, reviewed in SUPPLY-CHAIN-SECURITY.md. codesign builds an identity's chain from
# the keychains on the search list, and macOS's own roots hold only the G1 intermediate.
g2_intermediate=packaging/DeveloperIDG2CA.cer
g2_intermediate_sha256=f16cd3c54c7f83cea4bf1a3e6a0819c8aaa8e4a1528fd144715f350643d2df3a
# When the G1 intermediate expires (Apple's notice of 2026-10-01).
g1_intermediate_expiry=2027-02-01

# The notary profile the owner steps store, when APPLE_KEYCHAIN_PROFILE names none.
default_notary_profile=metabrowser-notary

# How long `notarytool history` may take before the doctor gives up on it: a stalled
# network would otherwise hang ONLINE=1 and a release's preflight.
notary_history_timeout_seconds=60

# Where macOS keeps its root certificates and the system-wide ones.
system_roots=/System/Library/Keychains/SystemRootCertificates.keychain
system_keychain=/Library/Keychains/System.keychain

doctor_failures=0
doctor_warnings=0

doctor_ok() {
  echo "ok: $*"
}

doctor_warn() {
  echo "warn: $*"
  doctor_warnings=$((doctor_warnings + 1))
}

doctor_fail() {
  echo "FAIL: $*"
  doctor_failures=$((doctor_failures + 1))
}

# ── Readers ──────────────────────────────────────────────────

# Reads `security find-identity -p codesigning` output and prints one line per identity
# it matched: the SHA-1 hash, a tab, "valid" or the reason security gives for the
# identity not being valid (CSSMERR_TP_NOT_TRUSTED, say), a tab, and the name. An
# identity is valid when security lists it again under "Valid identities only".
parse_identities() {
  local line section=matching matching="" valid=" " hash name reason
  local pattern='^ *[0-9]+\) ([0-9A-Fa-f]+) "(.*)"( \(([^)]*)\))?$'
  while IFS= read -r line; do
    case "$line" in
      *"Valid identities only"*)
        section=valid
        continue
        ;;
    esac
    [[ "$line" =~ $pattern ]] || continue
    hash="$(tr '[:lower:]' '[:upper:]' <<<"${BASH_REMATCH[1]}")"
    name="${BASH_REMATCH[2]}"
    reason="${BASH_REMATCH[4]:-invalid}"
    if [[ "$section" == valid ]]; then
      valid="$valid$hash "
    else
      matching="$matching$hash"$'\t'"$reason"$'\t'"$name"$'\n'
    fi
  done
  while IFS=$'\t' read -r hash reason name; do
    [[ -n "$hash" ]] || continue
    if [[ "$valid" == *" $hash "* ]]; then
      reason=valid
    fi
    printf '%s\t%s\t%s\n' "$hash" "$reason" "$name"
  done <<<"$matching"
}

# Keeps the Developer ID Application identities of parse_identities' lines.
developer_id_only() {
  local hash reason name
  while IFS=$'\t' read -r hash reason name; do
    [[ "$name" == "Developer ID Application: "* ]] && printf '%s\t%s\t%s\n' "$hash" "$reason" "$name"
  done
  return 0
}

# Prints the keychains that `security list-keychains` or `security login-keychain`
# lists, one per line, without the quotes and the indentation.
parse_keychain_list() {
  sed -n 's/^[[:space:]]*"\(.*\)"[[:space:]]*$/\1/p'
}

# Prints the value of KEY in scripts/keychain-status.swift's KEY=VALUE lines on stdin.
status_value() {
  sed -n "s/^$1=//p" | head -n 1
}

# Splits the PEM certificates on stdin into files in the folder "$1" and prints their
# paths, one per line.
split_pems() {
  awk -v dir="$1" '
    /-----BEGIN CERTIFICATE-----/ { count++; file = dir "/" count ".pem"; writing = 1 }
    writing { print > file }
    /-----END CERTIFICATE-----/ { if (writing) { close(file); print file }; writing = 0 }
  '
}

# A certificate's subject or issuer, in RFC 2253 form ("CN=...,OU=G2,O=Apple Inc.,C=US"),
# its notAfter date as openssl prints it, and its SHA-1 or SHA-256 fingerprint, in
# lowercase hex.
cert_subject() {
  openssl x509 -noout -subject -nameopt RFC2253 -in "$1" | sed 's/^subject= *//'
}

cert_issuer() {
  openssl x509 -noout -issuer -nameopt RFC2253 -in "$1" | sed 's/^issuer= *//'
}

cert_not_after() {
  openssl x509 -noout -enddate -in "$1" | sed 's/^notAfter=//'
}

cert_fingerprint() {
  openssl x509 -noout -fingerprint "-$2" -in "$1" | sed 's/^.*=//' | tr -d ':' | tr '[:upper:]' '[:lower:]'
}

# Which Developer ID intermediate a distinguished name is: G2, G1, or nothing.
developer_id_generation() {
  local dn=",$1,"
  [[ "$dn" == *",CN=Developer ID Certification Authority,"* ]] || return 0
  case "$dn" in
    *",OU=G2,"*) echo G2 ;;
    *",OU=Apple Certification Authority,"*) echo G1 ;;
  esac
  return 0
}

# Whole days from now to a date as openssl prints one, negative once it has passed.
days_until() {
  local end now
  end="$(epoch_of_date "$1" 2>/dev/null)" || return 1
  now="$(date -u +%s)"
  echo $(((end - now) / 86400))
}

# The notary profile the doctor looks for.
notary_profile_name() {
  echo "${APPLE_KEYCHAIN_PROFILE:-$default_notary_profile}"
}

# ── Checks ───────────────────────────────────────────────────

doctor_tools() {
  local output
  if output="$(xcodebuild -version 2>&1)"; then
    doctor_ok "$(tr '\n' ' ' <<<"$output" | sed 's/ *$//')"
  else
    doctor_fail "xcodebuild -version failed, so no Xcode is selected; install Xcode and select it with xcode-select: $(head -n 1 <<<"$output")"
  fi
  if output="$(xcrun notarytool --version 2>&1)"; then
    doctor_ok "notarytool $output"
  else
    doctor_fail "notarytool is missing; it comes with Xcode: $(head -n 1 <<<"$output")"
  fi
}

# The release keychain: that it exists and is on the search list, its lock settings,
# and whether it is unlocked, which only a release may need.
doctor_keychain() {
  local keychain="$1" status="$2" for_release="$3" entry listed=0 unlocked settings
  local on_sleep uses_interval interval listing="" restore=""
  if [[ "$(status_value exists <<<"$status")" != 1 ]]; then
    doctor_fail "the release keychain does not exist (O1: create it)"
    return
  fi
  doctor_ok "the release keychain exists"
  listing="$(security list-keychains -d user 2>/dev/null | parse_keychain_list)" || listing=""
  while IFS= read -r entry; do
    [[ -n "$entry" ]] || continue
    restore="$restore \"$entry\""
    if [[ "$entry" -ef "$keychain" ]]; then
      listed=1
    fi
  done <<<"$listing"
  if [[ -z "$restore" ]]; then
    # A list this doctor did not read gives no keychains to keep, and a `-s` command
    # without them would take the login keychain, which holds the G2 intermediate, off
    # the list, so no command is printed.
    doctor_fail "the user search list could not be read: security list-keychains -d user failed or listed nothing, so whether the release keychain is on it is unknown (O1)"
  elif ((listed)); then
    doctor_ok "it is on the user search list"
  else
    # `security create-keychain` does not add it, and `-s` replaces the whole list, so the
    # command keeps every keychain on it now.
    doctor_fail "it is not on the user search list (O1: security list-keychains -d user -s$restore \"$keychain\")"
  fi

  unlocked="$(status_value unlocked <<<"$status")"
  case "$unlocked" in
    1)
      if ((for_release)); then
        doctor_ok "it is unlocked, for this release; lock it when the release is done: security lock-keychain \"$keychain\""
      else
        doctor_warn "it is unlocked; lock it whenever no release is running: security lock-keychain \"$keychain\" (O1)"
      fi
      ;;
    0)
      if ((for_release)); then
        doctor_fail "it is locked; unlocking it is the go-ahead for this release, so type its password at the prompt of: security unlock-keychain \"$keychain\" (O7)"
      else
        doctor_ok "it is locked"
      fi
      ;;
    *) doctor_fail "whether it is locked could not be read: ${unlocked:-no answer}" ;;
  esac

  settings="$(status_value settings <<<"$status")"
  if [[ -n "$settings" ]]; then
    doctor_warn "its lock settings could not be read ($settings); unlock it, run this again, and lock it"
    return
  fi
  # The idle lock is the interval: after `set-keychain-settings -l -u -t 600`, macOS 26
  # reports use_lock_interval=0 with lock_interval=600, so that flag decides nothing and is
  # only reported. With no -t, the interval is INT_MAX, "no timeout", which fails here.
  on_sleep="$(status_value lock_on_sleep <<<"$status")"
  uses_interval="$(status_value use_lock_interval <<<"$status")"
  interval="$(status_value lock_interval <<<"$status")"
  if [[ "$on_sleep" == 1 && "$interval" =~ ^[0-9]+$ ]] &&
    ((interval > 0 && interval <= release_keychain_lock_seconds)); then
    doctor_ok "it locks on sleep and after $interval s idle"
  else
    doctor_fail "it must lock on sleep and after at most $release_keychain_lock_seconds s idle, and it is set to lock on sleep: ${on_sleep:-?}, after ${interval:-?} s idle (use-lock-interval: ${uses_interval:-?}) (O1: security set-keychain-settings -l -u -t $release_keychain_lock_seconds \"$keychain\")"
  fi
}

# The certificate checks for one identity: expiry, and which intermediate issued it.
doctor_certificate() {
  local pem="$1" name="$2" end days issuer
  end="$(cert_not_after "$pem" 2>/dev/null)" || end=""
  if ! days="$(days_until "$end")"; then
    doctor_fail "could not read when $name expires (notAfter: ${end:-none})"
  elif ((days <= expiry_fail_days)); then
    doctor_fail "$name expires on $end, in $days day(s); renew it now (O9)"
  elif ((days <= expiry_warn_days)); then
    doctor_warn "$name expires on $end, in $days days; renew it (O9)"
  else
    doctor_ok "$name expires on $end, in $days days"
  fi
  issuer="$(cert_issuer "$pem" 2>/dev/null)" || issuer="an unreadable issuer"
  case "$(developer_id_generation "$issuer")" in
    G2) doctor_ok "$name is issued by Developer ID Certification Authority, G2" ;;
    G1)
      doctor_warn "$name is issued by the G1 Developer ID intermediate, which expires on $g1_intermediate_expiry; its replacement is a G2 certificate (O9)"
      ;;
    *) doctor_fail "$name is issued by $issuer, which is not a Developer ID intermediate" ;;
  esac
}

# The identities in the release keychain: one valid Developer ID Application identity,
# the one SIGN_IDENTITY names when it is set, and its certificate.
doctor_identities() {
  local keychain="$1" status="$2" work="$3" for_release="$4" listing identities hash reason name
  local wanted matches=0 match_hash="" match_name="" valid_count=0 pem pems
  [[ "$(status_value exists <<<"$status")" == 1 ]] || return 0
  if ! listing="$(security find-identity -p codesigning "$keychain" 2>&1)"; then
    doctor_fail "security find-identity could not read the release keychain: $listing"
    return
  fi
  identities="$(parse_identities <<<"$listing" | developer_id_only)"
  if [[ -z "$identities" ]]; then
    doctor_fail "the release keychain holds no Developer ID Application identity (O1: import it with -x)"
    return
  fi
  wanted="$(tr '[:lower:]' '[:upper:]' <<<"${SIGN_IDENTITY:-}")"
  while IFS=$'\t' read -r hash reason name; do
    if [[ "$reason" != valid ]]; then
      case "$reason" in
        CSSMERR_TP_NOT_TRUSTED) reason="$reason: macOS cannot build its chain, so check the intermediate below" ;;
        CSSMERR_TP_CERT_EXPIRED) reason="$reason (O9)" ;;
      esac
      doctor_warn "$name ($hash) is not valid: $reason"
      continue
    fi
    valid_count=$((valid_count + 1))
    # As codesign reads -s: a SHA-1 hash, or a part of the name.
    if [[ -z "$wanted" || "$hash" == "$wanted" || "$name" == *"${SIGN_IDENTITY:-}"* ]]; then
      matches=$((matches + 1))
      match_hash="$hash"
      match_name="$name"
    fi
  done <<<"$identities"

  if ((valid_count == 0)); then
    doctor_fail "the release keychain holds no valid Developer ID Application identity (O1)"
    return
  fi
  if [[ -n "${SIGN_IDENTITY:-}" ]] && ((matches == 0)); then
    doctor_fail "SIGN_IDENTITY ($SIGN_IDENTITY) names no valid identity in the release keychain"
    return
  fi
  if ((matches > 1)); then
    doctor_fail "$matches valid Developer ID Application identities match${SIGN_IDENTITY:+ SIGN_IDENTITY}, so codesign would refuse the name as ambiguous; delete the old one, or set SIGN_IDENTITY to one's SHA-1 hash"
    return
  fi
  if [[ -n "${SIGN_IDENTITY:-}" ]]; then
    doctor_ok "SIGN_IDENTITY names $match_name ($match_hash), valid"
  elif ((for_release)); then
    doctor_fail "SIGN_IDENTITY is not set; a release names the identity: SIGN_IDENTITY=\"$match_name\""
  else
    doctor_ok "$match_name ($match_hash) is valid; a release names it as SIGN_IDENTITY"
  fi

  mkdir -p "$work/identities"
  pems="$(security find-certificate -a -c "Developer ID Application" -p "$keychain" 2>/dev/null | split_pems "$work/identities")" || true
  while IFS= read -r pem; do
    [[ -n "$pem" ]] || continue
    if [[ "$(cert_fingerprint "$pem" sha1 | tr '[:lower:]' '[:upper:]')" == "$match_hash" ]]; then
      doctor_certificate "$pem" "$match_name"
      return
    fi
  done <<<"$pems"
  doctor_warn "could not read the certificate of $match_name, so its expiry and issuer are not checked"
}

# A Developer ID identity left in the login keychain signs without the release
# keychain's lock.
doctor_login_keychain() {
  local keychain="$1" login identities names
  login="$(security login-keychain -d user 2>/dev/null | parse_keychain_list | head -n 1)" || true
  [[ -n "$login" && ! "$login" -ef "$keychain" ]] || return 0
  identities="$(security find-identity -p codesigning "$login" 2>/dev/null | parse_identities | developer_id_only)" || true
  [[ -n "$identities" ]] || return 0
  names="$(cut -f3 <<<"$identities" | sort -u | paste -s -d ';' - | sed 's/;/; /g')"
  doctor_warn "the login keychain holds a Developer ID Application identity too, which signs without the release keychain's lock: $names; delete it there once the release keychain holds it (O1)"
}

# The committed G2 intermediate: the reviewed file, chained to this Mac's Apple Root CA,
# and installed on the search list or in the System keychain with the same contents.
doctor_intermediate() {
  local work="$1" actual entry pem subject fingerprint found="" foreign="" login
  local -a keychains=()
  if [[ ! -f "$g2_intermediate" ]]; then
    doctor_fail "$g2_intermediate is missing from this checkout"
    return
  fi
  actual="$(shasum -a 256 "$g2_intermediate" | cut -d' ' -f1)"
  if [[ "$actual" != "$g2_intermediate_sha256" ]]; then
    doctor_fail "$g2_intermediate is not the reviewed copy: its SHA-256 is $actual, and SUPPLY-CHAIN-SECURITY.md records $g2_intermediate_sha256"
    return
  fi
  if ! openssl x509 -inform DER -in "$g2_intermediate" -out "$work/g2.pem" 2>/dev/null; then
    doctor_fail "openssl cannot read $g2_intermediate"
    return
  fi
  security find-certificate -a -c "Apple Root CA" -p "$system_roots" >"$work/roots.pem" 2>/dev/null || true
  if [[ -s "$work/roots.pem" ]] && openssl verify -CAfile "$work/roots.pem" "$work/g2.pem" >/dev/null 2>&1; then
    doctor_ok "$g2_intermediate is the reviewed copy, and chains to this Mac's Apple Root CA"
  else
    doctor_fail "$g2_intermediate does not chain to an Apple Root CA in $system_roots"
  fi

  while IFS= read -r entry; do
    [[ -n "$entry" ]] && keychains+=("$entry")
  done <<<"$(security list-keychains -d user 2>/dev/null | parse_keychain_list)"
  keychains+=("$system_keychain")
  mkdir -p "$work/intermediates"
  for entry in "${keychains[@]}"; do
    rm -f "$work/intermediates"/*.pem
    while IFS= read -r pem; do
      [[ -n "$pem" ]] || continue
      subject="$(cert_subject "$pem" 2>/dev/null)" || continue
      [[ "$(developer_id_generation "$subject")" == G2 ]] || continue
      fingerprint="$(cert_fingerprint "$pem" sha256 2>/dev/null)" || continue
      if [[ "$fingerprint" == "$g2_intermediate_sha256" ]]; then
        found="$found${found:+, }$entry"
      else
        foreign="$foreign${foreign:+; }$entry holds one with the SHA-256 $fingerprint"
      fi
    done <<<"$(security find-certificate -a -c "Developer ID Certification Authority" -p "$entry" 2>/dev/null | split_pems "$work/intermediates")"
  done
  if [[ -n "$foreign" ]]; then
    doctor_fail "a certificate named Developer ID Certification Authority, G2, is not Apple PKI's: $foreign; delete it (O1)"
  fi
  if [[ -n "$found" ]]; then
    doctor_ok "the Developer ID - G2 intermediate is installed, in $found"
  else
    login="$(security login-keychain -d user 2>/dev/null | parse_keychain_list | head -n 1)" || true
    doctor_fail "the Developer ID - G2 intermediate is not installed, so macOS cannot build a G2 identity's chain (O1: install $g2_intermediate, Apple PKI's copy, into the login keychain: security import $g2_intermediate -k \"${login:-LOGIN_KEYCHAIN}\")"
  fi
}

# The notary credentials, chosen as scripts/notarize.sh chooses them
# (notary_credential_kind in notary-lib.sh): a profile in the release keychain, or the
# API key variables. With ONLINE=1, or in a release's preflight when the keychain lookup
# did not find the profile, notarytool history asks the notary service, and its answer
# decides: the lookup uses notarytool's undocumented item name, so it never fails a
# profile that works.
doctor_notary() {
  local keychain="$1" status="$2" for_release="$3" profile found output online=0 reason next
  local -a auth=()
  [[ "${ONLINE:-0}" != 1 ]] || online=1
  case "$(notary_credential_kind)" in
    api-key)
      if [[ ! -f "$APPLE_API_KEY" ]]; then
        doctor_fail "APPLE_API_KEY names no file; it is the path of the App Store Connect API key (.p8)"
        return
      fi
      if [[ -n "$(find "$APPLE_API_KEY" -prune \( -perm -g+r -o -perm -o+r \) 2>/dev/null)" ]]; then
        doctor_warn "$APPLE_API_KEY can be read by other accounts; chmod 600 it"
      fi
      if [[ -z "${APPLE_API_KEY_ID:-}" ]]; then
        doctor_fail "APPLE_API_KEY_ID is not set; APPLE_API_KEY needs it"
        return
      fi
      auth=(--key "$APPLE_API_KEY" --key-id "$APPLE_API_KEY_ID")
      if [[ -n "${APPLE_API_ISSUER:-}" ]]; then
        auth+=(--issuer "$APPLE_API_ISSUER")
      else
        doctor_warn "APPLE_API_ISSUER is not set; a team key needs its issuer, and only an individual key has none"
      fi
      doctor_ok "the notary credentials are an API key (APPLE_API_KEY, APPLE_API_KEY_ID)"
      ;;
    *)
      profile="$(notary_profile_name)"
      if [[ "$(status_value exists <<<"$status")" != 1 ]]; then
        doctor_fail "no notary profile $profile: it belongs in the release keychain, which does not exist (O3)"
        return
      fi
      auth=(--keychain-profile "$profile" --keychain "$keychain")
      found="$(status_value profile <<<"$status")"
      case "$found" in
        found) doctor_ok "the release keychain holds the notary profile $profile" ;;
        absent)
          if ((online == 0 && for_release)); then
            online=1
          elif ((online == 0)); then
            doctor_warn "the release keychain holds no item named as notarytool 1.1 names the profile $profile, a name Apple does not document; with it unlocked, ONLINE=1 says whether the profile works (O3: xcrun notarytool store-credentials $profile --keychain \"$keychain\")"
          fi
          ;;
        *)
          doctor_warn "whether the release keychain holds the notary profile $profile could not be read (${found:-no answer}); unlock it and run this again, or run it with ONLINE=1"
          ;;
      esac
      ;;
  esac

  ((online)) || return 0
  if [[ "$(notary_credential_kind)" != api-key && "$(status_value unlocked <<<"$status")" != 1 ]]; then
    # A preflight reaches this without ONLINE=1, when the lookup missed the profile.
    if [[ "${ONLINE:-0}" == 1 ]]; then
      reason="ONLINE=1 asks the notary service"
      next="unlock it, run this again, and lock it"
    else
      reason="the keychain lookup missed the profile, so this preflight asks the notary service whether it works"
      next="unlock it and run this again"
    fi
    doctor_fail "$reason, which needs the release keychain unlocked, since notarytool reads the profile's key and this doctor never unlocks it; $next"
    return
  fi
  if output="$(bounded "$notary_history_timeout_seconds" xcrun notarytool history "${auth[@]}" 2>&1)"; then
    doctor_ok "the notary service answered notarytool history${profile:+ with the profile $profile}"
  else
    doctor_fail "notarytool history failed (O2, O3): $(tail -n 3 <<<"$output" | tr '\n' ' ')"
  fi
}

# The whole report. "$1" is 1 for a release's preflight, which needs the keychain
# unlocked and SIGN_IDENTITY set; "$2" is a scratch folder. Returns nonzero when any
# check failed. The checks call security, openssl, xcodebuild, xcrun, and
# keychain_status, which check-signing.sh defines and the tests replace.
run_signing_doctor() {
  local for_release="$1" work="$2" keychain status
  doctor_failures=0
  doctor_warnings=0
  keychain="$(release_keychain)"
  echo "Signing doctor: it only reads, and never unlocks a keychain or asks for anything."
  echo "Release keychain: $keychain"
  doctor_tools
  if ! status="$(keychain_status "$keychain" "$(notary_profile_name)" 2>&1)"; then
    doctor_fail "could not read the release keychain's state: $status"
    status=""
  fi
  doctor_keychain "$keychain" "$status" "$for_release"
  doctor_identities "$keychain" "$status" "$work" "$for_release"
  doctor_login_keychain "$keychain"
  doctor_intermediate "$work"
  doctor_notary "$keychain" "$status" "$for_release"
  echo "Signing doctor: $doctor_failures problem(s), $doctor_warnings warning(s)."
  ((doctor_failures == 0))
}
