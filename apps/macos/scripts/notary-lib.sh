# What scripts/notarize.sh decides, sourced by it and by scripts/test-release-logic.sh,
# which runs these on Apple's documented notary log and on logs in the same format: the
# credentials notarytool gets, the check before a submission, fetching the notary log,
# and reading it.
#
# The log is JSON, and jq reads it: notary logs carry null for "no issues" and "no
# ticket", which a property list cannot hold, so plutil is not used for them. macOS
# includes jq from macOS 15, and Linux CI runs these tests with its own.
# shellcheck shell=bash

# notarize.sh asks for a log up to this many times, this many seconds apart: a log that
# a failed download left unread is a release with no record of its warnings.
notary_log_tries=5
notary_log_retry_seconds=15

# Which credentials notarytool gets, the one choice notarize.sh and the signing doctor
# share: "profile" when APPLE_KEYCHAIN_PROFILE is set, whatever else is; "api-key" when
# only APPLE_API_KEY is; "none" otherwise.
notary_credential_kind() {
  if [[ -n "${APPLE_KEYCHAIN_PROFILE:-}" ]]; then
    echo profile
  elif [[ -n "${APPLE_API_KEY:-}" ]]; then
    echo api-key
  else
    echo none
  fi
}

# Sets the array notary_auth to notarytool's credential arguments: a keychain profile,
# read from the release keychain (release_keychain in common.sh), or an App Store
# Connect API key. Returns 1 when there are no credentials, and stops when they are
# incomplete.
notary_credentials() {
  notary_auth=()
  local kind
  kind="$(notary_credential_kind)"
  if [[ "$kind" == profile ]]; then
    notary_auth=(--keychain-profile "$APPLE_KEYCHAIN_PROFILE" --keychain "$(release_keychain)")
  elif [[ "$kind" == api-key ]]; then
    [[ -f "$APPLE_API_KEY" ]] || die "APPLE_API_KEY must be the path of an App Store Connect API key (.p8)"
    [[ -n "${APPLE_API_KEY_ID:-}" ]] || die "APPLE_API_KEY_ID is required with APPLE_API_KEY"
    notary_auth=(--key "$APPLE_API_KEY" --key-id "$APPLE_API_KEY_ID")
    [[ -z "${APPLE_API_ISSUER:-}" ]] || notary_auth+=(--issuer "$APPLE_API_ISSUER")
  else
    return 1
  fi
}

# Runs `syspolicy_check notary-submission`, which "Runs the same checks on an app as the
# Apple notary service" (man syspolicy_check), on the app "$1", so a rejection costs no
# submission against the daily limit. Returns its status; it prints its own findings.
presubmission_check() {
  echo "notarize: checking $(basename "$1") as the notary service would (syspolicy_check notary-submission)"
  syspolicy_check notary-submission "$1"
}

# Downloads the notary log of submission "$1" to "$2", with the credentials in
# notary_auth, retrying notary_log_tries times. Returns 1 when every try failed.
fetch_notary_log() {
  local id="$1" log="$2" try
  for ((try = 1; try <= notary_log_tries; try++)); do
    if xcrun notarytool log "$id" "${notary_auth[@]}" "$log" >/dev/null; then
      return 0
    fi
    if ((try < notary_log_tries)); then
      note "could not fetch the notary log of $id (try $try of $notary_log_tries); retrying in $notary_log_retry_seconds s"
      sleep "$notary_log_retry_seconds"
    fi
  done
  return 1
}

# Reads a notary log, the JSON `notarytool log` writes, and prints one line for the
# release record (the archive, the submission ID, the status, and the issue counts), then
# each issue with its severity and path. Returns 0 when the log reads and its status is
# Accepted with no issue of severity error; 1 when it lists an error or another status;
# and 2 when it is missing, empty, or not a notary log.
read_notary_log() {
  local log="$1" fields id status errors warnings others archive
  if [[ ! -s "$log" ]]; then
    echo "notary log: $log is missing or empty"
    return 2
  fi
  # A notary log has a jobId and a status, and issues is null or a list of objects.
  if ! fields="$(jq -r '
      if type != "object" or (.jobId | type) != "string" or (.status | type) != "string"
        or ((.issues // []) | type) != "array"
      then error("not a notary log") else . end
      | (.issues // []) as $issues
      | [.jobId, .status,
         ([$issues[] | select(.severity == "error")] | length),
         ([$issues[] | select(.severity == "warning")] | length),
         ([$issues[] | select(.severity != "error" and .severity != "warning")] | length),
         (.archiveFilename // "an unnamed archive")]
      | map(tostring) | join("\t")' "$log" 2>&1)"; then
    echo "notary log: $log is not a notary log: $fields"
    return 2
  fi
  IFS=$'\t' read -r id status errors warnings others archive <<<"$fields"
  echo "notary record: $archive, submission $id, $status, $errors error(s), $warnings warning(s), $others other issue(s)"
  jq -r '(.issues // [])[] | "notary \(.severity // "issue"): \(.path // "(no path)"): \(.message // "(no message)")"' "$log"
  if [[ "$status" != Accepted ]] || ((errors > 0)); then
    return 1
  fi
  return 0
}
