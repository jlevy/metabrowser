---
type: is
id: is-01m6f3a4ab0xx86kma2fv9t9cy
title: List refresh job
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a4rcc45rvvzgy17a392p
parent_id: is-01m2h7hrjfx06hzpr7ptz7k9wn
hold: null
hold_until: null
created_at: 2026-11-02T21:40:40.394Z
updated_at: 2026-11-02T22:34:16.686Z
started_at: 2026-11-02T22:28:26.088Z
---
Coordinator key per source and state, per-page conditional requests, the account read before and after, the reader rules, and waiting for reset_at, applied to ServedPull too.

## Notes

2026-11-02: refresh_pull_list in pull_list_refresh.py: key <slug>:pulls/<name>, per-page If-None-Match, account read before and after, more reads only the next page, reader rules. refresh_is_due waits a window and for reset_at. Followed the plan and left the same rule on ServedPull to step 2; this bead's text says here. PR 279.
