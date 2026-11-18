# What scripts/check-dmg.sh reads from a signature and a quarantine attribute, sourced by
# it and by scripts/test-release-logic.sh, which runs these on `codesign -dvvv` output in
# the form codesign prints it, and scripts/test-scripts.sh on real ad hoc signatures.
# shellcheck shell=bash

# The chain a Developer ID signature carries, below the signing certificate, as
# `codesign -dvvv` lists its Authority lines.
developer_id_chain="Developer ID Certification Authority|Apple Root CA"

# Reads `codesign -dvvv` output on stdin and prints KEY=VALUE lines:
#   adhoc=0|1         an ad hoc signature (Signature=adhoc, or the adhoc flag)
#   runtime=0|1       the hardened runtime flag on the CodeDirectory (flags=...(runtime))
#   timestamp=secure  a Timestamp= line, a secure timestamp; "none" when there is none or
#                     only a Signed Time= line, which Apple says means no secure timestamp
#                     ("Resolving common notarization issues")
#   team=ID           the TeamIdentifier, empty when it is "not set"
#   authorities=A|B|C the Authority lines, in order
signature_facts() {
  local line flags="" adhoc=0 timestamp=none team="" authorities=""
  local flag_pattern='flags=0x[0-9a-fA-F]+\(([^)]*)\)'
  while IFS= read -r line; do
    case "$line" in
      CodeDirectory\ *)
        [[ "$line" =~ $flag_pattern ]] && flags=",${BASH_REMATCH[1]},"
        ;;
      Signature=adhoc) adhoc=1 ;;
      Timestamp=*) timestamp=secure ;;
      TeamIdentifier=*)
        team="${line#TeamIdentifier=}"
        [[ "$team" != "not set" ]] || team=""
        ;;
      Authority=*) authorities="$authorities${authorities:+|}${line#Authority=}" ;;
    esac
  done
  [[ "$flags" != *",adhoc,"* ]] || adhoc=1
  echo "adhoc=$adhoc"
  if [[ "$flags" == *",runtime,"* ]]; then echo "runtime=1"; else echo "runtime=0"; fi
  echo "timestamp=$timestamp"
  echo "team=$team"
  echo "authorities=$authorities"
}

# The value of KEY in signature_facts' lines on stdin.
fact() {
  sed -n "s/^$1=//p" | head -n 1
}

# Prints, one per line, what is wrong with a Developer ID signature, given its
# signature_facts "$1", whether it is an app's or an image's ("$2"), and the Team ID it
# must carry ("$3", or empty for any): the hardened runtime, on an app only, since a disk
# image is not code that runs; a secure timestamp; the Team ID; and the chain to Apple
# Root CA. Prints nothing when the signature has all of them.
developer_id_problems() {
  local facts="$1" kind="$2" expected_team="$3" authorities team
  authorities="$(fact authorities <<<"$facts")"
  team="$(fact team <<<"$facts")"
  if [[ "$kind" == app && "$(fact runtime <<<"$facts")" != 1 ]]; then
    echo "no hardened runtime (codesign -dvvv shows no runtime flag); the notary service refuses it"
  fi
  if [[ "$(fact timestamp <<<"$facts")" != secure ]]; then
    echo "no secure timestamp (codesign -dvvv shows no Timestamp line); the notary service refuses it"
  fi
  if [[ -z "$team" ]]; then
    echo "no Team ID"
  elif [[ -n "$expected_team" && "$team" != "$expected_team" ]]; then
    echo "the Team ID is $team, not EXPECTED_TEAM_ID $expected_team"
  fi
  if [[ "$authorities" != "Developer ID Application: "*"|$developer_id_chain" ]]; then
    echo "the chain is ${authorities:-empty}, not Developer ID Application, $developer_id_chain"
  fi
  return 0
}

# Replaces each \xHH in "$1" with the character it names: macOS stores a quarantine
# agent's name with its spaces as \x20 ("Metabrowser\x20check-release", macOS 26 on CI).
# Anything else, a lone backslash included, is kept as it is.
decode_hex_escapes() {
  local text="$1" out="" prefix char
  while [[ "$text" == *'\x'[0-9a-fA-F][0-9a-fA-F]* ]]; do
    prefix="${text%%\\x[0-9a-fA-F][0-9a-fA-F]*}"
    text="${text:${#prefix}}"
    printf -v char "\\x${text:2:2}"
    out="$out$prefix$char"
    text="${text:4}"
  done
  echo "$out$text"
}

# Describes a com.apple.quarantine value, "FLAGS;TIME;AGENT;EVENT" with the flags and
# the time in hex and the agent's name escaped, for information only: Apple DTS says its
# on-disk format is not API, so nothing passes or fails on it.
describe_quarantine() {
  local flags time agent event when
  IFS=';' read -r flags time agent event <<<"$1"
  agent="$(decode_hex_escapes "$agent")"
  if [[ "$time" =~ ^[0-9a-fA-F]+$ ]] && when="$(date_of_epoch "$((16#$time))" 2>/dev/null)"; then
    :
  else
    when="an unreadable time ($time)"
  fi
  echo "flags 0x$flags, set $when, by ${agent:-no agent}${event:+, event $event}"
}

# Prints, one per line, what is wrong with an app's identity for a release: it must be
# the release variant ("$1" is its bundle identifier), the version "$4" ("$2" is its
# CFBundleShortVersionString), and built from the commit "$5", the tag's full SHA, with
# nothing uncommitted ("$3" is its MetabrowserSourceCommit, a short hash that
# scripts/build-app.sh records, with -dirty for uncommitted changes).
release_identity_problems() {
  local id="$1" version="$2" commit="$3" want_version="$4" want_commit="$5"
  [[ "$(variant_of_bundle_id "$id")" == release ]] || echo "the app is $id, not the release variant"
  [[ "$version" == "$want_version" ]] || echo "the app is version ${version:-unknown}, not $want_version"
  if [[ -z "$commit" ]]; then
    echo "the app records no source commit (MetabrowserSourceCommit)"
  elif [[ "$commit" == *-dirty ]]; then
    echo "the app was built from $commit, with uncommitted changes"
  elif ((${#commit} < 7)) || [[ "$want_commit" != "$commit"* ]]; then
    echo "the app was built from $commit, not from $want_commit, the tag's commit"
  fi
  return 0
}
