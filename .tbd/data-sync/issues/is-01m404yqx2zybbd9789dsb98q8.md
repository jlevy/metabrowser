---
type: is
id: is-01m404yqx2zybbd9789dsb98q8
title: Update storage contracts, fixtures, goldens, and release QA
kind: task
status: in_progress
priority: 2
version: 5
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
hold: null
hold_until: null
created_at: 2026-10-03T05:49:24.257Z
updated_at: 2026-10-04T22:11:18.502Z
started_at: 2026-10-03T06:04:43.930Z
---

## Notes

Final candidate cbb92dc9 is pushed in draft PR https://github.com/jlevy/metabrowser/pull/268. Local pre-push quality gate passed 4005 tests with 8 skips and 278 golden transcript checks. GitHub run 37238447100 completed: Python 3.12/3.13/3.14/3.14t, Git 2.43.7/2.50.1, and distribution checks passed; lint/audit failed only GHSA-vfj7-8cjw-p6xm through Tryscript (mb-19fc). No audit bypass was added. Installed local build 0.11.1.dev669+cbb92dc9 verified on both executable names with 11-plugin doctor passing. Manual release acceptance remains open under mb-m20f, mb-etqi, and mb-p0e2. User approved internal test/golden sandboxes; external dependency caches retained.
