---
type: is
id: is-01m7k2wyj6vv09snsk781hpvsz
title: "macOS app: check before submitting, read the notary log, and fail on errors"
kind: task
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2xcrjxtgfe2mepxas1434
  - type: blocks
    target: is-01m7k2xdgr9b8sra4vrd372fe2
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:06:08.069Z
updated_at: 2026-11-17T08:17:07.330Z
started_at: 2026-11-17T07:36:57.592Z
---
Phase 1 of the publishing plan. Before each submission, notarize.sh runs syspolicy_check notary-submission on the app, or on the app inside the image, and stops on a failure, so a rejection costs no round trip against the daily limit (PR #485 A19). After each submission it fetches the notary log, retrying, reads it with plutil, fails on any issue of severity error, prints each warning with its path, and prints one line with the submission ID, status and issue counts for the release record. Under NOTARIZE=1 a log it could not fetch or parse is fatal (PR #485 A8). Done when scripts/test-scripts.sh runs the reader on fixture logs: accepted with no issues, accepted with a warning, invalid with an error, and a missing and an unparsable log under NOTARIZE=1; the pre-submission check is proven by the first signed build.

## Notes

2026-11-17: implemented in #509 (head 6e4c2a138): notarize.sh runs syspolicy_check notary-submission on the app or the app in the image before each submission, fetches the log with retries (notary_log_tries in notary-lib.sh), reads it with jq (not plutil: logs carry null, which a plist cannot hold, and jq runs in Linux CI; macOS has /usr/bin/jq from 15), fails on severity error, prints warnings with paths and a notary record: line; NOTARIZE=1 makes a missing or unparsable log fatal. test-release-logic.sh runs the reader on Apple's documented example log (verbatim), accepted, accepted-with-warning, missing, empty, unparsable, and not-a-log, and notarize.sh end to end with stand-ins. Left in progress: the pre-submission check and the reader on real logs are proven only by the first signed build (README signing-session checks 6-7).
