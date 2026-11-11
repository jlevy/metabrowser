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

if ((failures)); then
  die "$failures script check(s) failed"
fi
echo "Script checks passed"
