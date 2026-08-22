---
type: is
id: is-01m0nvgsazf8j1v5drad1n3pc5
title: "PR #66 review F4: docstring names max_stale_s, parameter is min_stale_s"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0nvgqxqbb35etfxh3xbbkh9
created_at: 2026-08-22T23:04:59.998Z
updated_at: 2026-08-22T23:07:24.021Z
closed_at: 2026-08-22T23:07:24.020Z
close_reason: "Fixed: docstring no longer names a nonexistent max_stale_s."
---
inventory.py:592-595. The two read as opposites: min_stale_s is a floor on a derived bound, not a maximum.
