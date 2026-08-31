---
type: is
id: is-01m1apk3ffp314rs63fy9wq87d
title: "PR #90 P90-07: --format is silently coerced per mode"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:56.110Z
updated_at: 2026-08-31T01:40:12.938Z
closed_at: 2026-08-31T01:40:12.938Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
--show --format yaml falls back to text and --api --format text falls back to json, with no error. docs/cli.md promises a flag never looks accepted while being ignored, which this breaks.
