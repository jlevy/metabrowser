---
type: is
id: is-01m404yqx2zybbd9789dsb98q8
title: Update storage contracts, fixtures, goldens, and release QA
kind: task
status: in_progress
priority: 2
version: 4
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
hold: null
hold_until: null
created_at: 2026-10-03T05:49:24.257Z
updated_at: 2026-10-04T21:56:01.865Z
started_at: 2026-10-03T06:04:43.930Z
---

## Notes

Validation: make verify completed 4004 pytest tests with 8 skips and 278 transcript checks; lint/types/hygiene/security/parity passed. The only failing gate is the pre-existing Tryscript/braces advisory (mb-19fc). After the final delayed-stream fix, 367 focused regressions passed. User approved internal test and golden sandboxes; dependency caches/build outputs remain external. Installed-wheel smoke passed. Commit cbb92dc9 contains the final changes. User approved commit/push/draft PR on October 4; pre-push full tests running. Local installed build 0.11.1.dev669+cbb92dc9 confirmed. Manual release acceptance remains open under mb-m20f, mb-etqi, and mb-p0e2.
