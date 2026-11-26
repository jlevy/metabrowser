---
type: is
id: is-01m8b811da43ghay4k4awnjzv3
title: Changes tab file filter (e.g. Documentation) no longer filters the diff
kind: bug
status: in_progress
priority: 0
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T06:17:31.305Z
updated_at: 2026-11-26T06:17:32.697Z
started_at: 2026-11-26T06:17:32.696Z
---
Owner 2026-11-26: on a diff, selecting a file-type subfilter such as Documentation does not filter. Serious regression; find which change broke it and why (bisect), fix it with a test that fails without the fix, and record the cause.
