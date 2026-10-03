---
type: is
id: is-01m404yqx2zybbd9789dsb98q8
title: Update storage contracts, fixtures, goldens, and release QA
kind: task
status: in_progress
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
hold: null
hold_until: null
created_at: 2026-10-03T05:49:24.257Z
updated_at: 2026-10-03T06:31:44.051Z
started_at: 2026-10-03T06:04:43.930Z
---

## Notes

Validation: make verify completed 4004 pytest tests with 8 skips and 278 transcript checks; lint/types/hygiene/security/parity passed. The only failing gate is the pre-existing Tryscript/braces advisory (mb-19fc). After the final delayed-stream fix, 367 focused regressions passed. User approved internal test and golden sandboxes; dependency caches/build outputs remain external. Installed-wheel build smoke passed. Manual release acceptance remains open under mb-m20f, mb-etqi, and mb-p0e2; commit/PR handoff awaits approval after automatic review blocked that workflow.
