#!/usr/bin/env bash
# Runs `swift test` with the given arguments and fails unless swift-testing said its run
# passed: a summary line such as "Test run with 41 tests in 5 suites passed after 0.6
# seconds." and at least one test. `make test` runs each test process through it.
#
# A process can end with exit status 0 before its tests finish. On 2026-11-24, an event
# from the window server stopped the test runner's main run loop, which swift-testing
# drives without NSApplication.run, and swift_task_asyncMainDrainQueue then called
# exit(0) with the suite's tests unrun and no summary printed (runAppKitEventLoop in
# Tests/ShellCoreTests/Support.swift). A run whose filters match nothing passes the same
# way. The status alone passes both.
#
#   SWIFT=swift scripts/swift-test.sh --filter SettingsWindowTests
set -uo pipefail

swift="${SWIFT:-swift}"
log="$(mktemp -t metabrowser-swift-test)"
trap 'rm -f "$log"' EXIT

"$swift" test "$@" 2>&1 | tee "$log"
status="${PIPESTATUS[0]}"
if [[ "$status" != 0 ]]; then
  exit "$status"
fi
if ! grep -Eq 'Test run with [1-9][0-9]* tests? in [0-9]+ suites? passed' "$log"; then
  echo "error: swift test $* exited 0 without reporting a passed run of at least one test" >&2
  exit 1
fi
