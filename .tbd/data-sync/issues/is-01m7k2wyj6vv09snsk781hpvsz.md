---
type: is
id: is-01m7k2wyj6vv09snsk781hpvsz
title: "macOS app: check before submitting, read the notary log, and fail on errors"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2xcrjxtgfe2mepxas1434
  - type: blocks
    target: is-01m7k2xdgr9b8sra4vrd372fe2
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:08.069Z
updated_at: 2026-11-16T22:07:18.823Z
---
Phase 1 of the publishing plan. Before each submission, notarize.sh runs syspolicy_check notary-submission on the app, or on the app inside the image, and stops on a failure, so a rejection costs no round trip against the daily limit (PR #485 A19). After each submission it fetches the notary log, retrying, reads it with plutil, fails on any issue of severity error, prints each warning with its path, and prints one line with the submission ID, status and issue counts for the release record. Under NOTARIZE=1 a log it could not fetch or parse is fatal (PR #485 A8). Done when scripts/test-scripts.sh runs the reader on fixture logs: accepted with no issues, accepted with a warning, invalid with an error, and a missing and an unparsable log under NOTARIZE=1; the pre-submission check is proven by the first signed build.
