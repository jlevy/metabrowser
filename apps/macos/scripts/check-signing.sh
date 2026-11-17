#!/usr/bin/env bash
# The signing doctor: says whether this Mac can sign and notarize a release, and names
# what is missing and the owner step that fixes it (O1 to O9, README.md, Building a
# Release). It only reads. It never unlocks a keychain, changes one, or asks for
# anything; scripts/signing-lib.sh holds its checks and the limits they use.
#
#   scripts/check-signing.sh                # make signing-check
#   ONLINE=1 scripts/check-signing.sh       # also asks the notary service
#   scripts/check-signing.sh --for-release  # what scripts/release.sh's preflight runs
#
# It checks the release keychain (exists, on the search list, locks on sleep and when
# idle, locked or not), the Developer ID Application identity in it (valid, the one
# SIGN_IDENTITY names, its expiry and issuer), a copy left in the login keychain, the
# committed G2 intermediate (the reviewed file, chained to Apple Root CA, installed),
# Xcode and notarytool, and the notary credentials. --for-release also requires the
# keychain unlocked, which is the owner's go-ahead for a release, and SIGN_IDENTITY set.
#
# Environment:
#   SIGN_KEYCHAIN           the release keychain (default: release_keychain in common.sh)
#   SIGN_IDENTITY           the identity a release signs with, when set
#   APPLE_KEYCHAIN_PROFILE  the notary profile in the release keychain (default
#                           metabrowser-notary); or APPLE_API_KEY, APPLE_API_KEY_ID, and
#                           APPLE_API_ISSUER, as scripts/notarize.sh takes them
#   ONLINE                  1 runs `notarytool history`, which needs the keychain unlocked
#
# It exits 0 when nothing failed; warnings do not fail it. It never prints a secret.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh
# shellcheck source=signing-lib.sh
source scripts/signing-lib.sh
# shellcheck source=notary-lib.sh
source scripts/notary-lib.sh

for_release=0
case "${1:-}" in
  "") ;;
  --for-release) for_release=1 ;;
  *) die "usage: scripts/check-signing.sh [--for-release]" ;;
esac

work="$(scratch_dir metabrowser-signing-check)"
trap 'rm -rf "$work"' EXIT

# The keychain reader is compiled each run: it takes a few seconds, and nothing stale
# can stand in for it.
if ! output="$(swiftc -suppress-warnings -O scripts/keychain-status.swift -o "$work/keychain-status" 2>&1)"; then
  die "could not build scripts/keychain-status.swift, which needs Xcode: $output"
fi
keychain_status() {
  "$work/keychain-status" "$@"
}

if run_signing_doctor "$for_release" "$work"; then
  exit 0
fi
exit 1
