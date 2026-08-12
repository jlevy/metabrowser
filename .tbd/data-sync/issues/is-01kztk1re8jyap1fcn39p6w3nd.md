---
type: is
id: is-01kztk1re8jyap1fcn39p6w3nd
title: Restart inventory progress polling for a scanning tree response
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-12T08:57:29.288Z
updated_at: 2026-08-12T09:04:54.413Z
closed_at: 2026-08-12T09:04:54.413Z
close_reason: Implemented with regression coverage; full make verify passed on 2026-08-12.
---
The initial progress request can observe completion and stop before an in-flight /api/tree response paints a conservative scanning snapshot. That leaves newly rendered pending totals until the 10-second watchdog. Have loadTree restart the idempotent progress poll whenever its response is still scanning.

## Notes

loadTree now idempotently restarts inventory progress polling whenever a conservatively labeled scanning tree response paints, closing the race where an earlier progress request stopped after seeing completion. Regression coverage was strengthened. Full make verify passed on 2026-08-12.
